"""
역할: YouTube Data API v3를 활용하여 시드 키워드로 영상을 검색하고 수집합니다.
목적: 최신 유튜브 영상 데이터를 수집하여 트렌드 분석 파이프라인의 원천 데이터로 사용합니다.
"""

import os
from googleapiclient.discovery import build
from dotenv import load_dotenv
from datetime import datetime, timezone
import random

# .env 로드
load_dotenv()
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
    for item in search_response.get('items', []):
        video_id = item['id']['videoId']
        snippet = item['snippet']
        
        # 날짜 문자열 파싱
        published_at_str = snippet['publishedAt']
        # 예: '2026-06-28T10:00:00Z'
        published_at = datetime.strptime(published_at_str, "%Y-%m-%dT%H:%M:%SZ")
        
        video_data = {
            "video_id": video_id,
            "title": snippet['title'],
            "description": snippet['description'],
            "published_at": published_at,
            "channel_id": snippet['channelId'],
            "channel_title": snippet['channelTitle'],
            "collected_at": datetime.now()
        }
        videos.append(video_data)
        
    return videos
