import os
import sys
import logging
from datetime import datetime, timedelta

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy.orm import Session
from sns_sensing.database.db import SessionLocal
from sns_sensing.models.models import Video, Keyword, KeywordStat, CanonicalKeyword, TrendingKeyword
from sns_sensing.pipeline.openai_keyword_filter.gpt_extractor import get_canonical_names_sample, run_gpt_extractor, force_compound_flag
from sns_sensing.pipeline.youtube.analytics.signal_engine import update_expired_trends, calculate_spike_candidates
from openai import OpenAI, AzureOpenAI

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def run_backfill():
    db: Session = SessionLocal()
    try:
        # 최근 7일치 영상 가져오기
        recent_start = datetime.now() - timedelta(days=7)
        videos = db.query(Video).filter(Video.published_at >= recent_start).order_by(Video.published_at.desc()).all()
        
        # runner.py처럼 dict 형태로 변환
        raw_videos = []
        for v in videos:
            raw_videos.append({
                'video_id': v.video_id,
                'title': v.title,
                'description': v.description,
                'published_at': v.published_at,
                'channel_id': v.channel_id,
                'channel_title': v.channel_title,
                'collected_at': v.collected_at
            })
            
        logger.info(f"DB에서 {len(raw_videos)}개의 최근(7일내) 영상을 가져와서 GPT-Native 추출기로 재분석합니다...")
        
        from dotenv import load_dotenv
        load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env"))
        
        if os.getenv("AZURE_OPENAI_API_KEY"):
            client = AzureOpenAI(
                api_key=os.getenv("AZURE_OPENAI_API_KEY"),
                api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2025-01-01-preview"),
                azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
            )
        else:
            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        canonical_rows = db.query(CanonicalKeyword.canonical_name, CanonicalKeyword.category, CanonicalKeyword.created_at).order_by(CanonicalKeyword.id.desc()).all()
        canonical_dicts = [{"canonical_name": row[0], "category": row[1], "created_at": row[2]} for row in canonical_rows]
        sampled_canonicals = get_canonical_names_sample(canonical_dicts, total_limit=50)
        
        gpt_results_list = []
        # 배치 사이즈 10
        for i in range(0, len(raw_videos), 10):
            batch_videos = raw_videos[i:i+10]
            logger.info(f"처리 중: {i}/{len(raw_videos)}...")
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
                    
                # 3. TrendingKeyword 상태 설정
                existing_trend = db.query(TrendingKeyword).filter(TrendingKeyword.keyword == kw).first()
                if not existing_trend:
                    status = "PENDING" if is_compound else "NOISE"
                    reason = "소급 추출" if is_compound else "단일 일반 식재료(is_compound=False)"
                    new_trend = TrendingKeyword(keyword=kw, status=status, reason=reason, detected_at=datetime.now())
                    db.add(new_trend)
                    try:
                        db.flush()
                    except Exception as e:
                        db.rollback()
                        logger.error(f"DB Flush 에러 (키워드: {kw}): {e}")
        db.commit()
        
        # 4. 승격 게이트
        update_expired_trends(db, current_time=datetime.now(), min_mentions=5)
        spike_candidates = calculate_spike_candidates(db, current_time=datetime.now(), min_mentions=5, max_candidates=100)
        
        promoted_count = 0
        for sc in spike_candidates:
            kw = sc['keyword']
            trend = db.query(TrendingKeyword).filter(TrendingKeyword.keyword == kw).first()
            if trend and trend.status == "PENDING":
                trend.status = "TREND"
                trend.reason = "스파이크 달성 (Backfill)"
                trend.updated_at = datetime.now()
                promoted_count += 1
        db.commit()
        
        logger.info(f"재추출 완료! 통계 {new_keywords_count}개 추가, {promoted_count}개 TREND 승격.")
        
    except Exception as e:
        db.rollback()
        logger.error(f"오류: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    run_backfill()
