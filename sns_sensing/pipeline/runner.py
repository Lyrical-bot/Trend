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
from sns_sensing.models.models import Video, Keyword, KeywordStat, VideoStat
from sns_sensing.pipeline.youtube.discovery.seed_collector import fetch_youtube_videos, fetch_video_stats_batch
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
        
        # [단계 2] 비디오 정보 수집 및 키워드 추출 (임시 저장)
        video_to_keywords = {}
        all_extracted_keywords = set()
        
        import asyncio
        from sns_sensing.pipeline.openai_keyword_filter.keyword_filter import classify_keywords_batch
        
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
            
            # Kiwi 키워드 1차 추출 (단일명사 + 복합명사 + 룰베이스 필터)
            combined_text = f"{v_data['title']} {v_data['description']}"
            extracted_words = extract_keywords(combined_text)
            
            video_to_keywords[v_data['video_id']] = {
                'v_data': v_data,
                'words': extracted_words
            }
            all_extracted_keywords.update(extracted_words)

        # [단계 2.5] 비디오 데이터를 DB에 선반영하여 외래키(ForeignKey) 에러 방지
        db.flush()
            
        # [단계 3] LLM 2차 배치 필터링 (비용 절감을 위해 한 번에 전송)
        valid_food_keywords = set()
        if all_extracted_keywords:
            logger.info(f"LLM 2차 필터링을 위해 {len(all_extracted_keywords)}개의 키워드를 전송합니다...")
            # 비동기 함수 동기적으로 실행
            filtered_list = asyncio.run(classify_keywords_batch(list(all_extracted_keywords)))
            valid_food_keywords = set(filtered_list)
            logger.info(f"LLM 필터링 완료: {len(all_extracted_keywords)}개 중 {len(valid_food_keywords)}개 생존")
            
        # [단계 4] 최종 생존 키워드 DB 저장 및 통계 업데이트
        for video_id, data in video_to_keywords.items():
            v_data = data['v_data']
            words = data['words']
            
            # LLM 필터를 통과한 단어만 남김
            final_words = [w for w in words if w in valid_food_keywords]
            
            for word in final_words:
                kw_obj = Keyword(video_id=video_id, keyword=word)
                db.add(kw_obj)
                keywords_extracted += 1
                
                # 통계 (keyword_stats) 업데이트
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
                        
        # [단계 4] 과거 7일 이내 수집된 영상들의 시계열 통계(VideoStat) 배치 업데이트
        logger.info("과거 7일 내 수집된 영상의 통계를 배치로 갱신합니다...")
        seven_days_ago = datetime.now() - timedelta(days=7)
        recent_videos = db.query(Video.video_id).filter(Video.collected_at >= seven_days_ago).all()
        recent_video_ids = [v[0] for v in recent_videos]
        
        batch_updated_count = 0
        current_hour = datetime.now().replace(minute=0, second=0, microsecond=0)
        
        # 50개씩 묶어서 처리
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
                    batch_updated_count += 1
                    
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
