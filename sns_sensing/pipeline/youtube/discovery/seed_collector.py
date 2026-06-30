"""
역할: YouTube Data API v3를 활용하여 시드 키워드로 영상을 검색하고 수집합니다.
목적: 최신 유튜브 영상 데이터를 수집하여 트렌드 분석 파이프라인의 원천 데이터로 사용합니다.
"""

import os
from googleapiclient.discovery import build
from dotenv import load_dotenv
from datetime import datetime, timezone
import random

# .env 로드 (실행 경로와 관계없이 Backend/key/.env 파일로 절대 경로 해석)
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))))
dotenv_path = os.path.join(root_dir, "Backend", "key", ".env")
load_dotenv(dotenv_path=dotenv_path)

API_KEY = os.getenv("YOUTUBE_API_KEY")

# 유튜브 API 클라이언트 초기화 (키가 없으면 에러를 뿜지 않고 수집 기능만 스킵)
if not API_KEY:
    print("[Warning] .env 파일에 YOUTUBE_API_KEY가 설정되지 않아 YouTube 영상 수집 기능이 비활성화됩니다.")
    youtube = None
else:
    youtube = build('youtube', 'v3', developerKey=API_KEY)

# 식품/디저트 전용 시드 키워드 풀
FOOD_SEED_KEYWORDS = [
    "편의점 신상", "편의점 디저트", "GS25 신상", "CU 신상", "세븐일레븐 신상",
    "요즘 유행하는 간식", "디저트 카페", "신상 과자", "신상 아이스크림",
    "먹방", "빵지순례", "요즘 핫한 디저트", "웨이팅 맛집", "두바이초콜릿", "크루키"
]

def fetch_youtube_videos(max_results: int = 20) -> list:
    """
    랜덤 시드 키워드로 유튜브 영상을 검색하여 반환합니다.
    (API Quota 절약을 위해 한 번 호출 시 max_results 만큼만 가져옵니다)
    """
    if not youtube:
        return []
        
    # 시드 키워드 중 랜덤으로 1~2개를 섞어 검색 쿼리 생성
    seed = random.sample(FOOD_SEED_KEYWORDS, 1)[0]
    search_query = seed
    
    # 1. 검색 API 호출 (최신순 정렬)
    try:
        search_response = youtube.search().list(
            q=search_query,
            part='id,snippet',
            maxResults=max_results,
            order='date',
            type='video',
            videoDuration='short',
            regionCode='KR'
        ).execute()
    except Exception as e:
        print(f"[Error] 유튜브 API 검색 호출 실패 (Quota 초과 등): {e}")
        return []
    
    videos = []
    video_ids = [item['id']['videoId'] for item in search_response.get('items', [])]
    channel_ids = list(set([item['snippet']['channelId'] for item in search_response.get('items', [])]))
    
    # 2. 비디오 통계 수집 (조회수, 좋아요, 댓글수)
    video_stats_dict = {}
    if video_ids:
        try:
            v_res = youtube.videos().list(part='statistics', id=','.join(video_ids)).execute()
            for v_item in v_res.get('items', []):
                stats = v_item.get('statistics', {})
                video_stats_dict[v_item['id']] = {
                    'view_count': int(stats.get('viewCount', 0)),
                    'like_count': int(stats.get('likeCount', 0)),
                    'comment_count': int(stats.get('commentCount', 0))
                }
        except Exception as e:
            print(f"[Error] 비디오 통계 가져오기 실패: {e}")

    # 3. 채널 통계 수집 (구독자 수)
    channel_stats_dict = {}
    if channel_ids:
        try:
            c_res = youtube.channels().list(part='statistics', id=','.join(channel_ids)).execute()
            for c_item in c_res.get('items', []):
                stats = c_item.get('statistics', {})
                channel_stats_dict[c_item['id']] = int(stats.get('subscriberCount', 0))
        except Exception as e:
            print(f"[Error] 채널 통계 가져오기 실패: {e}")

    for item in search_response.get('items', []):
        video_id = item['id']['videoId']
        snippet = item['snippet']
        channel_id = snippet['channelId']
        
        # 날짜 문자열 파싱
        published_at_str = snippet['publishedAt']
        published_at = datetime.strptime(published_at_str, "%Y-%m-%dT%H:%M:%SZ")
        
        v_stat = video_stats_dict.get(video_id, {'view_count': 0, 'like_count': 0, 'comment_count': 0})
        subscriber_count = channel_stats_dict.get(channel_id, 0)
        
        video_data = {
            "video_id": video_id,
            "title": snippet['title'],
            "description": snippet['description'],
            "published_at": published_at,
            "channel_id": channel_id,
            "channel_title": snippet['channelTitle'],
            "subscriber_count": subscriber_count,
            "view_count": v_stat['view_count'],
            "like_count": v_stat['like_count'],
            "comment_count": v_stat['comment_count'],
            "collected_at": datetime.now()
        }
        videos.append(video_data)
        
    return videos

def fetch_video_stats_batch(video_ids: list) -> dict:
    """
    비디오 ID 목록(최대 50개)을 받아 조회수, 좋아요, 댓글수 통계를 반환합니다.
    (과거 7일치 데이터 배치 업데이트용)
    """
    if not video_ids:
        return {}
        
    video_stats_dict = {}
    try:
        v_res = youtube.videos().list(part='statistics', id=','.join(video_ids)).execute()
        for v_item in v_res.get('items', []):
            stats = v_item.get('statistics', {})
            video_stats_dict[v_item['id']] = {
                'view_count': int(stats.get('viewCount', 0)),
                'like_count': int(stats.get('likeCount', 0)),
                'comment_count': int(stats.get('commentCount', 0))
            }
    except Exception as e:
        print(f"[Error] 비디오 통계 배치 수집 실패: {e}")
        
    return video_stats_dict
