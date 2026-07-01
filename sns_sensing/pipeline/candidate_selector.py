from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
from sns_sensing.models.models import KeywordStat, BrandDictionary, CanonicalKeyword, CoOccurrence
from typing import List, Dict, Tuple
import math
from dataclasses import dataclass

# --- 카테고리어 구체화 사전 및 상수 ---
CATEGORY_DICT = {
    "초콜릿", "케이크", "피자", "아이스크림", "빵", "과자",
    "젤리", "음료", "커피", "라면", "김밥", "샐러드",
    "도시락", "디저트", "간식", "치킨", "떡", "쿠키",
}

FORMAT_TAG_DICT = {
    "신상리뷰", "신상 리뷰", "언박싱", "먹방", "브이로그", "vlog",
    "리뷰", "후기", "추천", "꿀조합", "레시피", "만들기",
}

DEFAULT_PMI_THRESHOLD = 0.6
MAX_PROMOTIONS_PER_CATEGORY = 3

@dataclass
class PromotedCandidate:
    category_word: str
    modifier: str
    combined: str
    pmi: float
    co_count: int

def is_category_word(word: str) -> bool:
    return word in CATEGORY_DICT

def is_format_tag(word: str) -> bool:
    return word in FORMAT_TAG_DICT

def _get_total_corpus_count(db: Session) -> int:
    result = db.query(func.sum(KeywordStat.mention_count)).scalar()
    return int(result) if result else 1

def _get_word_freq(db: Session, word: str) -> int:
    result = db.query(func.sum(KeywordStat.mention_count)).filter(KeywordStat.keyword == word).scalar()
    return int(result) if result else 0

def compute_npmi(db: Session, word_a: str, word_b: str, co_count: int, total: int) -> float:
    freq_a = _get_word_freq(db, word_a)
    freq_b = _get_word_freq(db, word_b)
    
    if freq_a == 0 or freq_b == 0 or co_count == 0:
        return -1.0
        
    p_a = freq_a / total
    p_b = freq_b / total
    p_ab = co_count / total
    
    pmi = math.log(p_ab / (p_a * p_b))
    npmi = pmi / (-math.log(p_ab))
    return npmi

def find_specific_combinations(db: Session, category_word: str, pmi_threshold: float, max_results: int) -> List[PromotedCandidate]:
    total = _get_total_corpus_count(db)
    
    rows = db.query(CoOccurrence.co_keyword, CoOccurrence.count).filter(
        CoOccurrence.keyword == category_word
    ).order_by(CoOccurrence.count.desc()).limit(50).all()
    
    candidates = []
    for co_keyword, co_count in rows:
        if is_category_word(co_keyword) or is_format_tag(co_keyword):
            continue
            
        npmi = compute_npmi(db, category_word, co_keyword, co_count, total)
        if npmi >= pmi_threshold:
            candidates.append(
                PromotedCandidate(
                    category_word=category_word,
                    modifier=co_keyword,
                    combined=f"{co_keyword} {category_word}",
                    pmi=round(npmi, 3),
                    co_count=co_count
                )
            )
            
    candidates.sort(key=lambda c: c.pmi, reverse=True)
    return candidates[:max_results]

def specify_candidates(db: Session, raw_candidates: List[str], pmi_threshold: float = DEFAULT_PMI_THRESHOLD) -> List[str]:
    final_candidates = []
    for word in raw_candidates:
        if is_format_tag(word):
            continue
            
        if is_category_word(word):
            promoted = find_specific_combinations(db, word, pmi_threshold, MAX_PROMOTIONS_PER_CATEGORY)
            if promoted:
                final_candidates.extend([p.combined for p in promoted])
            continue
            
        final_candidates.append(word)
        
    seen = set()
    deduped = []
    for w in final_candidates:
        if w not in seen:
            seen.add(w)
            deduped.append(w)
    return deduped

def select_candidates(db: Session, current_candidates: List[str], current_time: datetime) -> List[str]:
    """
    절대 순위(현재 TF-IDF 기반) 후보들과 과거 데이터 기반 증가율 상위 후보들을 합쳐서 반환합니다.
    (MVP 이원화 컷오프 정책 구현)
    """
    final_candidates = set(current_candidates)
    
    recent_start = current_time - timedelta(days=3)
    past_start = current_time - timedelta(days=6)
    
    # 최근 3일 카운트
    recent_counts = db.query(KeywordStat.keyword, func.sum(KeywordStat.mention_count).label('count')).filter(
        KeywordStat.hour >= recent_start,
        KeywordStat.hour <= current_time
    ).group_by(KeywordStat.keyword).all()
    
    # 과거 3일 카운트
    past_counts = db.query(KeywordStat.keyword, func.sum(KeywordStat.mention_count).label('count')).filter(
        KeywordStat.hour >= past_start,
        KeywordStat.hour < recent_start
    ).group_by(KeywordStat.keyword).all()
    
    past_map = {row[0]: row[1] for row in past_counts}
    
    growth_rates = []
    for kw, recent_count in recent_counts:
        past_count = past_map.get(kw, 0)
        if past_count > 0:
            growth = (recent_count - past_count) / past_count
        else:
            growth = 999.0 if recent_count >= 3 else 0 
            
        if growth > 0:
            growth_rates.append((kw, growth))
            
    growth_rates.sort(key=lambda x: x[1], reverse=True)
    top_growth = [kw for kw, _ in growth_rates[:30]]
    
    final_candidates.update(top_growth)
    
    # 3. NPMI 기반 카테고리어 구체화 (광범위한 카테고리를 구체적 수식어 조합으로 변경)
    specified_list = specify_candidates(db, list(final_candidates))
    return specified_list

def local_dictionary_matching(db: Session, candidates: List[str]) -> Tuple[Dict[str, dict], List[str]]:
    """
    브랜드 및 기존 Canonical Name 사전(로컬 DB)과 매칭하여 
    GPT 호출을 건너뛸 수 있는 항목들을 필터링합니다.
    반환값: (매칭된_결과_딕셔너리, 매칭되지_않은_나머지_후보_리스트)
    """
    matched_results = {}
    unmatched_candidates = []
    
    # 1. 브랜드 매칭
    brands = db.query(BrandDictionary.brand_name).all()
    brand_set = {b[0] for b in brands}
    
    # 2. Canonical Name 매칭
    canonicals = db.query(CanonicalKeyword.canonical_name).all()
    canonical_set = {c[0] for c in canonicals}
    
    for kw in candidates:
        if kw in brand_set:
            matched_results[kw] = {"brand": kw, "canonical": kw}
            continue
            
        # 단순 일치 매칭 (추후 자모 분리 등 고도화 가능)
        # 단어가 포함되어 있거나 띄어쓰기 차이 정도만 매칭
        kw_nospace = kw.replace(" ", "")
        matched = False
        for c in canonical_set:
            if kw_nospace == c.replace(" ", ""):
                matched_results[kw] = {"canonical": c}
                matched = True
                break
                
        if not matched:
            unmatched_candidates.append(kw)
        
    return matched_results, unmatched_candidates
