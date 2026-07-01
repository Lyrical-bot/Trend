import asyncio
import os
import sys
import logging
from sqlalchemy.orm import Session
from sqlalchemy import create_engine

# 프로젝트 최상단 경로를 시스템 패스에 추가하여 import 에러 방지
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sns_sensing.database.db import SessionLocal, engine
from sns_sensing.models.models import Keyword, KeywordStat
from sns_sensing.pipeline.openai_keyword_filter.keyword_filter import classify_keywords_batch

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

async def clean_database():
    db: Session = SessionLocal()
    try:
        logger.info("[1/3] DB에서 기존 키워드를 모두 불러옵니다...")
        # DB에 존재하는 모든 고유 키워드 조회
        all_db_keywords = db.query(Keyword.keyword).distinct().all()
        unique_keywords = [kw[0] for kw in all_db_keywords if kw[0]]
        
        logger.info(f"총 {len(unique_keywords)}개의 고유 키워드가 발견되었습니다.")
        
        if not unique_keywords:
            logger.info("정제할 키워드가 없습니다.")
            return

        logger.info("[2/3] OpenAI GPT-4o-mini를 통해 과거 데이터를 재평가합니다...")
        
        valid_food_keywords = set()
        
        # 200개씩 청크(Chunk) 단위로 쪼개서 LLM에 전송 (토큰 리밋 방지)
        chunk_size = 200
        for i in range(0, len(unique_keywords), chunk_size):
            chunk = unique_keywords[i:i + chunk_size]
            logger.info(f" -> 청크 처리 중 ({i+1} ~ {min(i+chunk_size, len(unique_keywords))} / {len(unique_keywords)})")
            
            # LLM 필터링 수행
            filtered_dict = await classify_keywords_batch(chunk)
            valid_food_keywords.update(filtered_dict.keys())
            valid_food_keywords.update(filtered_dict.values())
            
            # API Rate limit 방지를 위한 짧은 대기 (필요시)
            await asyncio.sleep(1)

        # 제거해야 할 노이즈 단어 목록 도출
        original_set = set(unique_keywords)
        noise_keywords = original_set - valid_food_keywords
        
        logger.info(f"평가 완료! 총 {len(unique_keywords)}개 중 생존: {len(valid_food_keywords)}개, 삭제 대상(노이즈): {len(noise_keywords)}개")
        
        if not noise_keywords:
            logger.info("삭제할 노이즈 데이터가 없습니다! 아주 깨끗합니다.")
            return
            
        logger.info("[3/3] 노이즈 키워드를 DB에서 영구 삭제합니다...")
        
        # 1. keywords 테이블에서 삭제
        deleted_kw = db.query(Keyword).filter(Keyword.keyword.in_(noise_keywords)).delete(synchronize_session=False)
        
        # 2. keyword_stats 테이블에서 삭제
        deleted_stat = db.query(KeywordStat).filter(KeywordStat.keyword.in_(noise_keywords)).delete(synchronize_session=False)
        
        db.commit()
        logger.info(f"청소 완료! (keywords 테이블에서 {deleted_kw}건, keyword_stats 테이블에서 {deleted_stat}건 삭제됨)")
        
    except Exception as e:
        db.rollback()
        logger.error(f"스크립트 실행 중 오류 발생: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(clean_database())
