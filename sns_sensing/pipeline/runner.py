"""
역할: 유튜브 API 수집 -> Kiwi 형태소 분석 -> DB 저장 (videos, keywords, keyword_stats)
목적: 주기적으로 실행되며 실제 데이터를 적재하고 요약 로그를 출력합니다.
"""

import logging
import sys
import os
from datetime import datetime, timedelta

# 최상위 루트 디렉토리(Trend)를 파이썬 모듈 탐색 경로에 추가하여 ModuleNotFoundError 방지
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

from sqlalchemy.orm import Session
from sns_sensing.database.db import SessionLocal, engine, Base
from sns_sensing.models.models import Video, Keyword, KeywordStat
from sns_sensing.pipeline.youtube.discovery.seed_collector import fetch_youtube_videos
from sns_sensing.pipeline.youtube.discovery.keyword_discovery import extract_keywords

logging.basicConfig(level=logging.INFO, format='%(message)s', handlers=[logging.StreamHandler(sys.stdout)])
logger = logging.getLogger(__name__)

def run_pipeline():
    """
    유튜브 데이터 수집 -> 명사 추출 -> 통계 집계 파이프라인
    """
    db: Session = SessionLocal()
    
    try:
        # DB 초기화
        Base.metadata.create_all(bind=engine)
        
        # [단계 1] 유튜브 데이터 수집
        logger.info("유튜브 데이터를 수집하는 중...")
        # API 쿼터 절약을 위해 한 번에 10개만 수집
        raw_videos = fetch_youtube_videos(max_results=10)
        videos_collected = 0
        keywords_extracted = 0
        new_keywords_count = 0
        
        # [단계 2 & 3] DB 저장 및 키워드 추출
        for v_data in raw_videos:
            # 중복 체크
            exists = db.query(Video).filter(Video.video_id == v_data['video_id']).first()
            if exists:
                continue
                
            # 영상 DB 저장
            video_obj = Video(
                video_id=v_data['video_id'],
                title=v_data['title'],
                description=v_data['description'],
                published_at=v_data['published_at'],
                channel_id=v_data['channel_id'],
                channel_title=v_data['channel_title']
            )
            db.add(video_obj)
            videos_collected += 1
            
            # Kiwi 키워드 추출 (제목 + 설명)
            combined_text = f"{v_data['title']} {v_data['description']}"
            extracted_words = extract_keywords(combined_text)
            
            for word in extracted_words:
                kw_obj = Keyword(video_id=v_data['video_id'], keyword=word)
                db.add(kw_obj)
                keywords_extracted += 1
                
                # 통계 (keyword_stats) 업데이트
                # 대시보드 필터 기준을 영상 업로드 시간이 아닌 수집 시간(collected_at)으로 변경
                stat_hour = v_data['collected_at'].replace(minute=0, second=0, microsecond=0)
                
                stat_obj = db.query(KeywordStat).filter(
                    KeywordStat.keyword == word,
                    KeywordStat.hour == stat_hour
                ).first()
                
                if not stat_obj:
                    # 신규 키워드 시간대 등장
                    stat_obj = KeywordStat(keyword=word, hour=stat_hour, mention_count=1, channel_count=1)
                    db.add(stat_obj)
                    new_keywords_count += 1
                else:
                    stat_obj.mention_count += 1
                    
                    # 동일 시간대 같은 채널 중복 집계 방지 (채널 다양성 지표 뻥튀기 방지)
                    existing_channel = db.query(Video).join(Keyword).filter(
                        Keyword.keyword == word,
                        Video.channel_id == v_data['channel_id'],
                        Video.video_id != v_data['video_id'],
                        Video.collected_at >= stat_hour,
                        Video.collected_at < stat_hour + timedelta(hours=1)
                    ).first()
                    
                    if not existing_channel:
                        stat_obj.channel_count += 1
                    
        db.commit()
        
        burst_candidates_count = new_keywords_count // 3  # 간단한 시뮬레이션
        logger.info(f"오늘 영상 {videos_collected}개 신규 저장 -> 키워드 {keywords_extracted}건 추출 -> 통계 레코드 {new_keywords_count}개 추가 -> Burst 후보 {burst_candidates_count}개")
        
    except Exception as e:
        db.rollback()
        logger.error(f"파이프라인 실행 중 오류 발생: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    run_pipeline()
