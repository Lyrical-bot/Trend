"""
역할: 과거 14일치 유튜브 영상 데이터를 강제로 소급 수집(Backfill)합니다.
목적: MVP 대시보드 시연을 위해 비어있는 KeywordStat (시계열 추세 데이터)을 인위적으로 채워넣습니다.
"""
import os
import sys
import argparse
from datetime import datetime, timedelta, timezone

# 최상위 루트 디렉토리 추가
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
if root_dir not in sys.path:
    sys.path.append(root_dir)

from dotenv import load_dotenv
from googleapiclient.discovery import build
from sqlalchemy.orm import Session
from sns_sensing.database.db import SessionLocal, engine, Base
from sns_sensing.models.models import Video, Keyword, KeywordStat, VideoStat
from sns_sensing.pipeline.youtube.discovery.keyword_discovery import extract_keywords
import asyncio
from sns_sensing.pipeline.openai_keyword_filter.keyword_filter import extract_keywords_info

# 환경변수 로드
load_dotenv(os.path.join(root_dir, ".env"))
API_KEY = os.getenv("YOUTUBE_API_KEY")

if not API_KEY:
    print("[Error] YOUTUBE_API_KEY가 설정되지 않았습니다.")
    sys.exit(1)

youtube = build('youtube', 'v3', developerKey=API_KEY)

def backfill_keyword(db: Session, target_keyword: str, days_ago: int = 14, max_results: int = 50):
    print(f"[{target_keyword}] 과거 {days_ago}일치 데이터 백필을 시작합니다...")
    
    # 1. 과거 N일 전 날짜 계산 (RFC 3339 포맷)
    published_after = (datetime.now(timezone.utc) - timedelta(days=days_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    # 2. YouTube Search API 호출
    try:
        search_res = youtube.search().list(
            q=target_keyword,
            part='id,snippet',
            maxResults=max_results,
            publishedAfter=published_after,
            order='relevance',  # 관련도 높은 순 (트렌드 반영)
            type='video',
            regionCode='KR'
        ).execute()
    except Exception as e:
        print(f"[Error] Search API 실패: {e}")
        return

    items = search_res.get('items', [])
    if not items:
        print(f"[{target_keyword}] 검색된 영상이 없습니다.")
        return
        
    video_ids = [item['id']['videoId'] for item in items]
    print(f"[{target_keyword}] {len(video_ids)}개의 영상을 찾았습니다. 통계 추출 중...")
    
    # 3. 비디오 통계(조회수, 좋아요) 수집
    video_stats_dict = {}
    try:
        # 최대 50개는 한번에 호출 가능
        v_res = youtube.videos().list(part='statistics', id=','.join(video_ids)).execute()
        for v_item in v_res.get('items', []):
            stats = v_item.get('statistics', {})
            video_stats_dict[v_item['id']] = {
                'view_count': int(stats.get('viewCount', 0)),
                'like_count': int(stats.get('likeCount', 0)),
                'comment_count': int(stats.get('commentCount', 0))
            }
    except Exception as e:
        print(f"[Error] Videos API 실패: {e}")
        return

    all_extracted_keywords = set()
    video_records = []
    
    for item in items:
        vid = item['id']['videoId']
        snippet = item['snippet']
        
        # 영상 발행일을 기준으로 시계열 날짜 산정
        pub_date_str = snippet['publishedAt']
        pub_date = datetime.strptime(pub_date_str, "%Y-%m-%dT%H:%M:%SZ")
        stat_hour = pub_date.replace(hour=0, minute=0, second=0, microsecond=0) # 일 단위 집계
        
        v_stat = video_stats_dict.get(vid, {'view_count': 0, 'like_count': 0, 'comment_count': 0})
        
        # DB 중복 체크 (Video)
        exists = db.query(Video).filter(Video.video_id == vid).first()
        if not exists:
            v_obj = Video(
                video_id=vid,
                title=snippet['title'],
                description=snippet['description'],
                published_at=pub_date,
                channel_id=snippet['channelId'],
                channel_title=snippet['channelTitle'],
                collected_at=datetime.now()
            )
            db.add(v_obj)
            
            vs_obj = VideoStat(
                video_id=vid,
                hour=stat_hour,
                view_count=v_stat['view_count'],
                like_count=v_stat['like_count'],
                comment_count=v_stat['comment_count']
            )
            db.add(vs_obj)
            
        # 키워드 추출 (해당 키워드 자체를 무조건 포함하도록 보정)
        combined_text = f"{snippet['title']} {snippet['description']}"
        words = extract_keywords(combined_text)
        # 타겟 키워드가 형태소 분석에서 잘리더라도 텍스트에 실제로 존재할 때만 강제 삽입
        clean_target = target_keyword.replace(" ", "")
        if clean_target not in words and clean_target in combined_text.replace(" ", ""):
            words.append(clean_target)
            
        video_records.append({
            'vid': vid,
            'channel_id': snippet['channelId'],
            'stat_hour': stat_hour,
            'words': words,
            'title': snippet['title']
        })
        all_extracted_keywords.update(words)

    # 4. LLM 필터링 (배치)
    valid_food_mapping = {}
    if all_extracted_keywords:
        print(f"[{target_keyword}] 추출된 {len(all_extracted_keywords)}개 키워드를 LLM으로 정제합니다...")
        
        # GPT 전달용 Context 구성
        unmatched_contexts = []
        for kw in all_extracted_keywords:
            context_str = ""
            for record in video_records:
                if kw in record['words']:
                    context_str = f"영상 제목: {record['title']}"
                    break
            unmatched_contexts.append({"keyword": kw, "context": context_str})

        filtered_dict = asyncio.run(extract_keywords_info(unmatched_contexts))
        valid_food_mapping = {}
        for kw, info in filtered_dict.items():
            canonical_name = info.get("canonical_name") or kw
            valid_food_mapping[kw] = canonical_name
        # 타겟 키워드는 강제로 유효 처리
        clean_target = target_keyword.replace(" ", "")
        valid_food_mapping[clean_target] = clean_target
        valid_food_mapping[target_keyword] = target_keyword

    # 5. 시계열 통계(KeywordStat) 기록
    print(f"[{target_keyword}] 정제된 키워드들을 시계열 DB에 저장합니다...")
    for record in video_records:
        vid = record['vid']
        stat_hour = record['stat_hour']
        channel_id = record['channel_id']
        
        final_words = list(set([valid_food_mapping[w] for w in record['words'] if w in valid_food_mapping]))
        
        for word in final_words:
            # 중복 방지: 이미 해당 비디오에 이 키워드가 연결되어 있는지 체크
            kw_exists = db.query(Keyword).filter(Keyword.video_id == vid, Keyword.keyword == word).first()
            if not kw_exists:
                db.add(Keyword(video_id=vid, keyword=word))
            
            # 시계열 스탯 업데이트
            stat_obj = db.query(KeywordStat).filter(
                KeywordStat.keyword == word,
                KeywordStat.hour == stat_hour
            ).first()
            
            if not stat_obj:
                stat_obj = KeywordStat(keyword=word, hour=stat_hour, mention_count=1, channel_count=1)
                db.add(stat_obj)
            else:
                stat_obj.mention_count += 1
                stat_obj.channel_count += 1 # 심플화를 위해 채널수는 업로드마다 1증가로 가정 (MVP용)

    db.commit()
    print(f"[{target_keyword}] 백필 완료! 총 {len(video_records)}개 영상 적재됨.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--keywords", type=str, required=True, help="백필할 키워드 콤마(,) 구분")
    parser.add_argument("--days", type=int, default=14, help="소급할 과거 일수")
    args = parser.parse_args()
    
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    
    try:
        kw_list = [k.strip() for k in args.keywords.split(",")]
        for kw in kw_list:
            backfill_keyword(db, kw, args.days)
    except Exception as e:
        print(f"백필 중 오류 발생: {e}")
        db.rollback()
    finally:
        db.close()
