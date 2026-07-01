"""
역할: 영상 제목 및 설명 텍스트에서 주요 명사(트렌드 키워드)를 추출합니다.
목적: 노이즈가 많은 유튜브 데이터에서 의미 있는 키워드(예: 버터떡, 두바이초콜릿)만 선별합니다.
"""

from kiwipiepy import Kiwi
import re

# Kiwi 형태소 분석기 전역 초기화 (싱글톤)
kiwi = Kiwi()

# 1. 절대 불가: 완전 일치 불용어 (단어 자체가 쓰레기인 경우)
STOPWORDS = {
    "추천", "영상", "오늘", "내일", "어제", "이번", "저번",
    "진짜", "너무", "완전", "대박", "미쳤", "정말", "솔직", "후기", "유튜브",
    "구독", "좋아요", "알림", "설정", "채널", "브이로그", "일상",
    "신상", "편의점", "다이소", "올리브영", "최고", "최악", "가성비", "존맛탱",
    "감성", "개봉", "느낌", "분위기", "언박싱", "하울",
    "웨이팅", "맛집", "과자", "우유", "디저트", "신상과자", "조합", "간식", "크림", "출시", "난리", "서울", "식감",
    "사람", "생각", "시간", "정도", "이거", "그거", "저거", "우리", "여러분", "친구",
    "요즘", "최근", "마지막", "처음", "진행", "시작", "준비", "도전", "성공", "실패",
    "극강", "비쥬얼", "비주얼", "역대급", "미친", "존맛"
}

# 콘텐츠 포맷 태그 (음식 트렌드가 아닌 영상 형식/포맷을 나타내는 단어)
FORMAT_TAGS = {
    "신상리뷰", "신상 리뷰", "언박싱", "먹방", "브이로그", "vlog",
    "리뷰", "후기", "추천", "꿀조합", "레시피", "만들기",
}

# 2. 부분 일치 불가: 이 단어가 포함되어 있으면 무조건 버림 (엔터/인방/마케팅 노이즈 제거)
NOISE_SUBSTRINGS = [
    "걸그룹", "보이그룹", "아이돌", "키비츠", "멤버", "소속사", "엔터", "직캠", "팬싸", "팬미",
    "컴백", "티저", "뮤비", "안무", "댄스", "가수", "배우", "드라마", "영화", "출연", "방송", "예능",
    "댓글", "구독", "조회수", "링크", "인스타", "틱톡", "트위터", "협찬", "광고", "마켓", "공구",
    "브랜드", "할인", "이벤트", "쇼핑몰", "구매", "결제", "무료", "증정", "배송", "택배",
    "스토어", "쿠폰", "프로모션", "공식", "오픈", "마감", "매진", "품절", "재입고"
]

def clean_text(text: str) -> str:
    """텍스트에서 특수문자나 이모지를 제거합니다."""
    if not text:
        return ""
    # 간단한 정규식으로 알파벳, 한글, 숫자, 공백만 남김
    text = re.sub(r'[^a-zA-Z0-9가-힣\s]', ' ', text)
    return text

def is_valid_keyword(word: str) -> bool:
    """
    추출된 단어가 트렌드 분석에 유효한지 깐깐하게 검증합니다.
    """
    # 1. 1글자는 무조건 제외
    if len(word) < 2:
        return False
        
    # 2. 숫자로만 이루어진 단어 제외
    if word.isdigit():
        return False
        
    # 3. 절대 불가 불용어 또는 포맷 태그 사전 매칭
    if word in STOPWORDS or word in FORMAT_TAGS:
        return False
        
    # 4. 부분 일치 노이즈 사전 매칭
    for noise in NOISE_SUBSTRINGS:
        if noise in word:
            return False
            
    # 5. ~님 으로 끝나는 단어(사람 이름/호칭) 제외
    if word.endswith("님") or word.endswith("씨") or word.endswith("쨩"):
        return False
        
    # 6. 영어로만 이루어진 2글자 단어 (보통 의미 없음)
    if re.match(r'^[a-zA-Z]{2}$', word):
        return False
        
    return True

def extract_keywords(text: str) -> list:
    """
    텍스트를 입력받아 NNG(일반명사), NNP(고유명사), UN(미등록어), XR(어근), SL(알파벳/외국어), MAG(일반부사) 태그를 추출합니다.
    또한 이들이 연속으로 나타나는 구간을 덩어리(Chunk)로 묶어 길이 2~4의 N-gram을 모두 생성합니다.
    추가로, 원본 띄어쓰기 단위의 단어(Raw Word)도 후보군에 포함시켜 형태소 분석기가 과도하게 쪼개는 신조어(예: 두바이쫀득쿠키)를 보완합니다.
    """
    text = clean_text(text)
    if not text.strip():
        return []
        
    # 1. 띄어쓰기 단위 원본 단어(Raw words) 추출 (형태소 분석기가 과하게 쪼개는 것을 방어)
    raw_words = []
    for word in text.split():
        if 2 <= len(word) <= 15:
            if is_valid_keyword(word):
                raw_words.append(word)

    # 형태소 분석
    result = kiwi.tokenize(text)
    tokens_list = list(result)
    
    valid_tags = {'NNG', 'NNP', 'UN', 'XR', 'SL', 'MAG'}
    
    # 2. 단일 태그 추출
    single_nouns = []
    for token in tokens_list:
        if token.tag in valid_tags:
            if is_valid_keyword(token.form):
                single_nouns.append(token.form)
                
    # 3. N-gram 청킹(Chunking) 추출
    compound_nouns = []
    current_chunk = []
    
    # 청크 단위로 분리 (유효 태그가 연속되는 구간을 찾음)
    for token in tokens_list:
        if token.tag in valid_tags:
            current_chunk.append(token.form)
        else:
            if len(current_chunk) >= 2:
                # 덩어리 안에서 길이 2부터 4까지의 모든 부분집합(N-gram) 생성
                chunk_len = len(current_chunk)
                for n in range(2, min(5, chunk_len + 1)):
                    for start in range(chunk_len - n + 1):
                        ngram_words = current_chunk[start:start + n]
                        compound = " ".join(ngram_words)
                        if is_valid_keyword(compound):
                            compound_nouns.append(compound)
            current_chunk = []
            
    # 마지막으로 남은 청크 처리
    if len(current_chunk) >= 2:
        chunk_len = len(current_chunk)
        for n in range(2, min(5, chunk_len + 1)):
            for start in range(chunk_len - n + 1):
                ngram_words = current_chunk[start:start + n]
                compound = " ".join(ngram_words)
                if is_valid_keyword(compound):
                    compound_nouns.append(compound)
                
    # 중복 제거 후 반환 (원시 단어 + 형태소 단어 + N-gram)
    all_terms = list(set(single_nouns + compound_nouns + raw_words))
    return all_terms
