"""
역할: 유튜브 API 수집 -> N-gram 추출 -> PMI/TF-IDF -> 로컬 매칭 -> GPT 통합 매칭 -> DB 저장
목적: 주기적으로 실행되며 실제 데이터를 적재하고 요약 로그를 출력합니다.
"""

import logging
import sys
import os
from datetime import datetime, timedelta
import asyncio

# 최상위 루트 디렉토리(Trend)를 파이썬 모듈 탐색 경로에 추가하여 ModuleNotFoundError 방지
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

from sqlalchemy.orm import Session
from sqlalchemy import func
from sns_sensing.database.db import SessionLocal, engine, Base
from sns_sensing.models.models import Video, Keyword, KeywordStat, VideoStat, BrandDictionary, CanonicalKeyword, RawKeywordMapping, CoOccurrence, TrendingKeyword
from sns_sensing.pipeline.youtube.discovery.seed_collector import fetch_youtube_videos, fetch_video_stats_batch, fetch_historical_youtube_videos
from sns_sensing.pipeline.youtube.discovery.keyword_discovery import extract_keywords
from sns_sensing.pipeline.keyword_extractor import KeywordExtractor
from sns_sensing.pipeline.candidate_selector import select_candidates, local_dictionary_matching
from sns_sensing.pipeline.openai_keyword_filter.keyword_filter import extract_keywords_info

# GPT-Native 파이프라인 활성화 플래그 (True 시 형태소 분석기 생략)
USE_GPT_NATIVE_EXTRACTOR = True


logging.basicConfig(level=logging.INFO, format='%(message)s', handlers=[logging.StreamHandler(sys.stdout)])
logger = logging.getLogger(__name__)

def save_gpt_results_to_db(db: Session, gpt_results: dict):
    """
    GPT 추출 결과를 DB에 저장합니다.
    - 새로운 Brand가 있으면 BrandDictionary에 추가
    - CanonicalKeyword 저장
    - RawKeywordMapping 연결
    반환값: { raw_keyword: canonical_name } 딕셔너리
    """
    final_mapping = {}
    for raw_kw, info in gpt_results.items():
        canonical_name = info.get("canonical_name") or raw_kw
        brand_name = info.get("brand")
        category = info.get("category")
        action = info.get("action")
        
        final_mapping[raw_kw] = canonical_name
        
        # 1. 브랜드 자동 업데이트
        if brand_name:
            existing_brand = db.query(BrandDictionary).filter(BrandDictionary.brand_name == brand_name).first()
            if not existing_brand:
                new_brand = BrandDictionary(brand_name=brand_name)
                db.add(new_brand)
                try:
                    db.commit()
                except:
                    db.rollback()
                    
        # 2. Canonical Keyword 업데이트/저장
        canonical_obj = db.query(CanonicalKeyword).filter(CanonicalKeyword.canonical_name == canonical_name).first()
        if not canonical_obj:
            canonical_obj = CanonicalKeyword(
                canonical_name=canonical_name,
                brand_name=brand_name,
                category=category,
                action=action
            )
            db.add(canonical_obj)
            try:
                db.commit()
            except:
                db.rollback()
                canonical_obj = db.query(CanonicalKeyword).filter(CanonicalKeyword.canonical_name == canonical_name).first()
                
        # 3. Raw Mapping 저장
        if canonical_obj:
            existing_mapping = db.query(RawKeywordMapping).filter(RawKeywordMapping.raw_keyword == raw_kw).first()
            if not existing_mapping:
                new_mapping = RawKeywordMapping(
                    raw_keyword=raw_kw,
                    canonical_id=canonical_obj.id
                )
                db.add(new_mapping)
                try:
                    db.commit()
                except:
                    db.rollback()
                    
    return final_mapping


def run_pipeline():
    db: Session = SessionLocal()
    
    try:
        # DB 초기화
        Base.metadata.create_all(bind=engine)
        
        # [단계 1] 유튜브 데이터 수집
        oldest_published = db.query(func.min(Video.published_at)).scalar()
        if oldest_published is None or (datetime.now() - oldest_published).days < 13:
            logger.info("과거 14일치 소급 데이터가 부족합니다. 초기 백필 수집을 시작합니다.")
            raw_videos = fetch_historical_youtube_videos(days_ago=14, max_results_per_day=5)
        else:
            logger.info("유튜브 데이터를 수집하는 중...")
            raw_videos = fetch_youtube_videos(max_results=10)
            
        videos_collected = 0
        
        # 비디오 수집 후 DB 저장 로직 (공통)
        for v_data in raw_videos:
            exists = db.query(Video).filter(Video.video_id == v_data['video_id']).first()
            if not exists:
                video_obj = Video(
                    video_id=v_data['video_id'],
                    title=v_data['title'],
                    description=v_data['description'],
                    published_at=v_data['published_at'],
                    channel_id=v_data['channel_id'],
                    channel_title=v_data['channel_title'],
                    subscriber_count=v_data.get('subscriber_count', 0)
                )
                db.add(video_obj)
                videos_collected += 1
                
                stat_hour = v_data['collected_at'].replace(minute=0, second=0, microsecond=0)
                vstat_obj = VideoStat(
                    video_id=v_data['video_id'],
                    hour=stat_hour,
                    view_count=v_data.get('view_count', 0),
                    like_count=v_data.get('like_count', 0),
                    comment_count=v_data.get('comment_count', 0)
                )
                db.add(vstat_obj)
        db.flush()
        db.commit()

        if USE_GPT_NATIVE_EXTRACTOR:
            logger.info("GPT-Native 추출 파이프라인 시작 (Kiwi 대체)")
            from sns_sensing.pipeline.openai_keyword_filter.gpt_extractor import get_canonical_names_sample, run_gpt_extractor, force_compound_flag
            import os
            from openai import OpenAI, AzureOpenAI
            from sns_sensing.pipeline.youtube.analytics.signal_engine import update_expired_trends, calculate_spike_candidates
            
            # Azure OpenAI 또는 OpenAI 클라이언트 초기화
            if os.getenv("AZURE_OPENAI_API_KEY"):
                client = AzureOpenAI(
                    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
                    api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2025-01-01-preview"),
                    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
                )
            else:
                client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            
            # Canonical Names 앵커링 데이터 준비
            canonical_rows = db.query(CanonicalKeyword.canonical_name, CanonicalKeyword.category, CanonicalKeyword.created_at).order_by(CanonicalKeyword.id.desc()).all()
            canonical_dicts = [{"canonical_name": row[0], "category": row[1], "created_at": row[2]} for row in canonical_rows]
            sampled_canonicals = get_canonical_names_sample(canonical_dicts, total_limit=50)
            
            gpt_results_list = []
            # 배치 크기 10으로 분할 전송 (토큰 리밋 및 혼동 방지)
            for i in range(0, len(raw_videos), 10):
                batch_videos = raw_videos[i:i+10]
                try:
                    batch_result = run_gpt_extractor(client, batch_videos, sampled_canonicals)
                    gpt_results_list.extend(batch_result)
                except Exception as e:
                    logger.error(f"GPT 배치 처리 중 에러: {e}")
                    
            keywords_extracted = 0
            new_keywords_count = 0
            
            for v_result in gpt_results_list:
                vid = v_result["video_id"]
                v_data = next((v for v in raw_videos if v['video_id'] == vid), None)
                if not v_data:
                    continue
                    
                stat_hour = v_data['collected_at'].replace(minute=0, second=0, microsecond=0)
                
                for kw_info in v_result["keywords"]:
                    kw = kw_info["keyword"]
                    is_compound = kw_info["is_compound"]
                    is_compound = force_compound_flag(kw, is_compound)
                    
                    # 1. Keyword 적재
                    kw_obj = Keyword(video_id=vid, keyword=kw)
                    db.add(kw_obj)
                    keywords_extracted += 1
                    
                    # 2. KeywordStat 업데이트
                    stat_obj = db.query(KeywordStat).filter(KeywordStat.keyword == kw, KeywordStat.hour == stat_hour).first()
                    if not stat_obj:
                        stat_obj = KeywordStat(keyword=kw, hour=stat_hour, mention_count=1, channel_count=1)
                        db.add(stat_obj)
                        new_keywords_count += 1
                    else:
                        stat_obj.mention_count += 1
                        
                    # 3. TrendingKeyword 상태 설정 (추출 게이트)
                    existing_trend = db.query(TrendingKeyword).filter(TrendingKeyword.keyword == kw).first()
                    if not existing_trend:
                        # 일반명사는 영구 NOISE 처리하여 절대 TREND 승격 방지
                        status = "PENDING" if is_compound else "NOISE"
                        reason = "초기 추출" if is_compound else "단일 일반 식재료(is_compound=False)"
                        new_trend = TrendingKeyword(keyword=kw, status=status, reason=reason, detected_at=datetime.now())
                        db.add(new_trend)
                    
                    try:
                        db.flush()
                    except Exception as e:
                        db.rollback()
                        logger.error(f"DB Flush 에러 (키워드: {kw}): {e}")
            db.commit()
            
            # 4. 승격 게이트 (Spike Filter)
            update_expired_trends(db, current_time=datetime.now(), min_mentions=5)
            # 최근 14일치 백필 데이터가 있으면 스파이크가 즉시 감지됨
            spike_candidates = calculate_spike_candidates(db, current_time=datetime.now(), min_mentions=5, max_candidates=100)
            
            promoted_count = 0
            for sc in spike_candidates:
                kw = sc['keyword']
                trend = db.query(TrendingKeyword).filter(TrendingKeyword.keyword == kw).first()
                # 오직 PENDING 상태인 경우만 승격 (NOISE는 무시됨)
                if trend and trend.status == "PENDING":
                    trend.status = "TREND"
                    trend.reason = "스파이크 달성 (GPT-Native)"
                    trend.updated_at = datetime.now()
                    promoted_count += 1
            db.commit()
            
            logger.info(f"[GPT-Native] 통계 레코드 {new_keywords_count}개 갱신, {promoted_count}개 키워드 TREND 승격 완료")
            
        else:
            # [단계 2] 레거시 N-gram 명사구 추출 및 통계 수집
            extractor = KeywordExtractor()
            video_to_keywords = {}
            
            for v_data in raw_videos:
                combined_text = f"{v_data['title']} {v_data['description']}"
                extracted_words = extract_keywords(combined_text)
                
                video_to_keywords[v_data['video_id']] = {
                    'v_data': v_data,
                    'words': extracted_words
                }
                extractor.add_document(extracted_words)
                
            # Co-occurrence 저장
            co_occurrences = extractor.get_co_occurrences(min_count=2)
            for w1, w2, count in co_occurrences:
                existing = db.query(CoOccurrence).filter(CoOccurrence.keyword == w1, CoOccurrence.co_keyword == w2).first()
                if existing:
                    existing.count += count
                else:
                    new_co = CoOccurrence(keyword=w1, co_keyword=w2, count=count)
                    db.add(new_co)
            db.commit()
    
            # [단계 3] 유망 후보 선별 및 기존 트렌드 만료 처리
            from sns_sensing.pipeline.youtube.analytics.signal_engine import update_expired_trends
            update_expired_trends(db, current_time=datetime.now(), min_mentions=5)
            
            top_candidates = extractor.get_top_candidates(top_n=120)
            final_candidates = select_candidates(db, top_candidates, current_time=datetime.now())
            logger.info(f"선별된 최종 유망 후보 키워드 개수: {len(final_candidates)}개")
    
            # [단계 4] 로컬 사전 1차 매칭
            matched_results, unmatched_candidates = local_dictionary_matching(db, final_candidates)
            logger.info(f"로컬 사전 매칭 성공: {len(matched_results)}개, GPT 전달 대상: {len(unmatched_candidates)}개")
    
            # [단계 4.5] GPT 전달용 Context 구성 (최근순 5개 제목 + 타임스탬프)
            unmatched_contexts = []
            for kw in unmatched_candidates:
                # kw가 등장한 비디오들을 추출
                vids_with_kw = []
                for vid, data in video_to_keywords.items():
                    if kw in data['words']:
                        vids_with_kw.append(data['v_data'])
                
                # published_at 기준으로 내림차순 정렬 (최신순)
                vids_with_kw.sort(key=lambda x: x['published_at'], reverse=True)
                
                # 상위 5개 가져오기
                top_5_vids = vids_with_kw[:5]
                context_str = " ".join([f"[{v['published_at'].strftime('%Y-%m-%d %H:%M')}] {v['title']}" for v in top_5_vids])
                
                unmatched_contexts.append({"keyword": kw, "context": context_str})
                
                # TrendingKeyword에 상태를 PENDING으로 등록/갱신
                existing_trend = db.query(TrendingKeyword).filter(TrendingKeyword.keyword == kw).first()
                if existing_trend:
                    existing_trend.status = "PENDING"
                    existing_trend.updated_at = datetime.now()
                else:
                    new_trend = TrendingKeyword(keyword=kw, status="PENDING", detected_at=datetime.now(), updated_at=datetime.now())
                    db.add(new_trend)
            try:
                db.commit()
            except:
                db.rollback()
    
            # [단계 5] GPT Extraction & 표기 통합 동시 수행
            # 눈덩이(Snowball) 효과 방지를 위해, 최신순으로 무작정 100개를 가져오지 않고
            # 카테고리별로 골고루 최신 키워드를 수집하여 전달합니다.
            import random
            recent_canonicals = []
            categories = db.query(CanonicalKeyword.category).filter(CanonicalKeyword.category.isnot(None)).distinct().all()
            
            for cat_row in categories:
                cat = cat_row[0]
                cat_canonicals = db.query(CanonicalKeyword.canonical_name)\
                    .filter(CanonicalKeyword.category == cat)\
                    .order_by(CanonicalKeyword.id.desc())\
                    .limit(5).all()
                recent_canonicals.extend([c[0] for c in cat_canonicals])
                
            # 카테고리 없는 초기 데이터나, 데이터가 너무 적을 때를 대비한 폴백(Fallback)
            if len(recent_canonicals) < 20:
                fallback = db.query(CanonicalKeyword.canonical_name).order_by(CanonicalKeyword.id.desc()).limit(20).all()
                recent_canonicals.extend([c[0] for c in fallback])
                
            # 중복 제거 및 섞기, 최대 50개
            recent_canonicals = list(set(recent_canonicals))
            random.shuffle(recent_canonicals)
            recent_canonicals = recent_canonicals[:50]
            
            gpt_results = asyncio.run(extract_keywords_info(unmatched_contexts, recent_canonicals))
    
            # GPT 결과에 따라 TrendingKeyword 상태 업데이트 (TREND / NOISE)
            for ctx in unmatched_contexts:
                kw = ctx['keyword']
                existing_trend = db.query(TrendingKeyword).filter(TrendingKeyword.keyword == kw).first()
                if existing_trend:
                    if kw in gpt_results:
                        existing_trend.status = "TREND"
                    else:
                        existing_trend.status = "NOISE"
                    existing_trend.updated_at = datetime.now()
            try:
                db.commit()
            except:
                db.rollback()
    
            # [단계 6] GPT 결과물 DB 저장 (Brand 자동 업데이트, Raw->Canonical 매핑)
            gpt_mapping = save_gpt_results_to_db(db, gpt_results)
            
            # 전체 매핑 딕셔너리 병합
            final_raw_to_canonical = {}
            for kw, info in matched_results.items():
                final_raw_to_canonical[kw] = info.get("canonical", kw)
            for kw, canonical in gpt_mapping.items():
                final_raw_to_canonical[kw] = canonical
                
            # [단계 7] 최종 생존 키워드 DB 저장 및 통계 업데이트
            keywords_extracted = 0
            new_keywords_count = 0
            
            for video_id, data in video_to_keywords.items():
                v_data = data['v_data']
                words = data['words']
                
                # 최종 필터(매핑 딕셔너리에 존재하는 경우만)
                valid_canonicals = set()
                for w in words:
                    if w in final_raw_to_canonical:
                        valid_canonicals.add(final_raw_to_canonical[w])
                        
                for c_word in valid_canonicals:
                    kw_obj = Keyword(video_id=video_id, keyword=c_word)
                    db.add(kw_obj)
                    keywords_extracted += 1
                    
                    stat_hour = v_data['collected_at'].replace(minute=0, second=0, microsecond=0)
                    
                    stat_obj = db.query(KeywordStat).filter(
                        KeywordStat.keyword == c_word,
                        KeywordStat.hour == stat_hour
                    ).first()
                    
                    if not stat_obj:
                        stat_obj = KeywordStat(keyword=c_word, hour=stat_hour, mention_count=1, channel_count=1)
                        db.add(stat_obj)
                        new_keywords_count += 1
                    else:
                        stat_obj.mention_count += 1
                        
                        existing_channel = db.query(Video).join(Keyword).filter(
                            Keyword.keyword == c_word,
                            Video.channel_id == v_data['channel_id'],
                            Video.video_id != v_data['video_id'],
                            Video.collected_at >= stat_hour,
                            Video.collected_at < stat_hour + timedelta(hours=1)
                        ).first()
                        
                        if not existing_channel:
                            stat_obj.channel_count += 1
                            
            db.commit()

        
        # 과거 7일 시계열 업데이트
        seven_days_ago = datetime.now() - timedelta(days=7)
        recent_videos = db.query(Video.video_id).filter(Video.collected_at >= seven_days_ago).all()
        recent_video_ids = [v[0] for v in recent_videos]
        
        current_hour = datetime.now().replace(minute=0, second=0, microsecond=0)
        
        for i in range(0, len(recent_video_ids), 50):
            batch_ids = recent_video_ids[i:i+50]
            stats_dict = fetch_video_stats_batch(batch_ids)
            
            for vid, stats in stats_dict.items():
                exists = db.query(VideoStat).filter(VideoStat.video_id == vid, VideoStat.hour == current_hour).first()
                if not exists:
                    new_stat = VideoStat(
                        video_id=vid,
                        hour=current_hour,
                        view_count=stats['view_count'],
                        like_count=stats['like_count'],
                        comment_count=stats['comment_count']
                    )
                    db.add(new_stat)
        db.commit()
        
        logger.info(f"완료: 영상 {videos_collected}개 -> 통계 레코드 {new_keywords_count}개 갱신 (Canonical Name 기준)")
        
    except Exception as e:
        db.rollback()
        logger.error(f"파이프라인 실행 중 오류 발생: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    run_pipeline()
