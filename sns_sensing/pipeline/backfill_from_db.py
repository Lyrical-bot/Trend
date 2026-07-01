import os
import sys
import asyncio
import logging

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sns_sensing.database.db import SessionLocal
from sns_sensing.models.models import Video, Keyword, KeywordStat, CanonicalKeyword, CoOccurrence
from sns_sensing.pipeline.youtube.discovery.keyword_discovery import extract_keywords
from sns_sensing.pipeline.keyword_extractor import KeywordExtractor
from sns_sensing.pipeline.candidate_selector import select_candidates, local_dictionary_matching
from sns_sensing.pipeline.openai_keyword_filter.keyword_filter import extract_keywords_info
from sns_sensing.pipeline.runner import save_gpt_results_to_db

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def run_backfill():
    db: Session = SessionLocal()
    try:
        videos = db.query(Video).order_by(Video.published_at.desc()).limit(150).all()
        logger.info(f"DB에서 {len(videos)}개의 영상을 가져와서 재분석합니다...")
        
        extractor = KeywordExtractor()
        video_to_keywords = {}
        
        for v in videos:
            combined_text = f"{v.title} {v.description}"
            extracted_words = extract_keywords(combined_text)
            
            video_to_keywords[v.video_id] = {
                'v_data': {
                    'channel_id': v.channel_id,
                    'video_id': v.video_id,
                    'collected_at': v.collected_at
                },
                'words': extracted_words
            }
            extractor.add_document(extracted_words)
            
        co_occurrences = extractor.get_co_occurrences(min_count=2)
        for w1, w2, count in co_occurrences:
            existing = db.query(CoOccurrence).filter(CoOccurrence.keyword == w1, CoOccurrence.co_keyword == w2).first()
            if existing:
                existing.count += count
            else:
                new_co = CoOccurrence(keyword=w1, co_keyword=w2, count=count)
                db.add(new_co)
        db.commit()

        top_candidates = extractor.get_top_candidates(top_n=120)
        final_candidates = select_candidates(db, top_candidates, current_time=datetime.now())
        
        matched_results, unmatched_candidates = local_dictionary_matching(db, final_candidates)
        logger.info(f"GPT 전송 대상: {len(unmatched_candidates)}개")
        
        recent_canonicals = [c[0] for c in db.query(CanonicalKeyword.canonical_name).limit(100).all()]
        gpt_results = asyncio.run(extract_keywords_info(unmatched_candidates, recent_canonicals))
        
        gpt_mapping = save_gpt_results_to_db(db, gpt_results)
        
        final_raw_to_canonical = {}
        for kw, info in matched_results.items():
            final_raw_to_canonical[kw] = info.get("canonical", kw)
        for kw, canonical in gpt_mapping.items():
            final_raw_to_canonical[kw] = canonical
            
        keywords_extracted = 0
        new_keywords_count = 0
        
        for video_id, data in video_to_keywords.items():
            v_data = data['v_data']
            words = data['words']
            
            valid_canonicals = set()
            for w in words:
                if w in final_raw_to_canonical:
                    valid_canonicals.add(final_raw_to_canonical[w])
                    
            for c_word in valid_canonicals:
                kw_obj = Keyword(video_id=video_id, keyword=c_word)
                db.add(kw_obj)
                keywords_extracted += 1
                
                stat_hour = v_data['collected_at'].replace(minute=0, second=0, microsecond=0)
                stat_obj = db.query(KeywordStat).filter(KeywordStat.keyword == c_word, KeywordStat.hour == stat_hour).first()
                if not stat_obj:
                    stat_obj = KeywordStat(keyword=c_word, hour=stat_hour, mention_count=1, channel_count=1)
                    db.add(stat_obj)
                    new_keywords_count += 1
                else:
                    stat_obj.mention_count += 1
                    stat_obj.channel_count += 1
                    
        db.commit()
        logger.info(f"재추출 완료! (통계 {new_keywords_count}개 추가)")
        
    except Exception as e:
        db.rollback()
        logger.error(f"오류: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    run_backfill()
