import os
import sys
from datetime import datetime, timedelta
from typing import Dict, Any

# Ensure correct import paths
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sns_sensing.database.db import SessionLocal
from sns_sensing.pipeline.youtube.analytics.signal_engine import calculate_all_signals
from sns_sensing.models.models import Video, Keyword, VideoStat
from naver_ad_api import fetch_search_ad_volume
from weather_api import fetch_weather_data

async def retrieve_trend_context(keyword: str) -> str:
    """
    RAG 컨텍스트 생성을 위해 네이버 데이터랩 검색량, 유튜브 트렌드 지표, 날씨 및 Top 3 영상을 수집하여 텍스트로 변환합니다.
    """
    db = SessionLocal()
    current_time = datetime.now()
    
    # 1. 유튜브 지표 수집
    try:
        sns_signals = calculate_all_signals(db, keyword, current_time)
    except Exception as e:
        sns_signals = {}
        print(f"[RAG Retriever] SNS Signals Error: {e}")

    # 2. Top 3 유튜브 영상 정보 추출
    top_videos_text = ""
    try:
        # 최근 7일 내 키워드가 언급된 영상 중 조회수 순 정렬
        recent_start = current_time - timedelta(days=7)
        rows = (
            db.query(Video, VideoStat)
            .join(Keyword, Keyword.video_id == Video.video_id)
            .join(VideoStat, VideoStat.video_id == Video.video_id)
            .filter(
                Keyword.keyword == keyword,
                Video.published_at >= recent_start
            )
            .order_by(VideoStat.view_count.desc())
            .limit(3)
            .all()
        )
        
        if rows:
            for idx, (video, stat) in enumerate(rows):
                top_videos_text += f"  {idx+1}. 제목: {video.title} | 채널: {video.channel_title} | 조회수: {stat.view_count:,}회 | 좋아요: {stat.like_count:,}개\n"
        else:
            top_videos_text = "  (최근 7일간 수집된 영상 없음)\n"
    except Exception as e:
        top_videos_text = f"  (영상 조회 중 에러 발생: {e})\n"

    # 3. 네이버 검색광고 검색량 수집
    naver_volume = 0
    try:
        ad_volumes = await fetch_search_ad_volume([keyword])
        naver_volume = ad_volumes.get(keyword, 0)
    except Exception as e:
        print(f"[RAG Retriever] Naver AD Error: {e}")

    # 4. 날씨 데이터 수집
    weather_text = ""
    try:
        start_dt = (current_time - timedelta(days=3)).strftime("%Y-%m-%d")
        end_dt = current_time.strftime("%Y-%m-%d")
        weather_data = await fetch_weather_data(start_dt, end_dt)
        if weather_data:
            recent_temps = [float(w.get("avgTa", 0)) for w in weather_data if w.get("avgTa") is not None]
            recent_rains = [float(w.get("sumRn", 0)) for w in weather_data if w.get("sumRn") is not None]
            avg_temp = sum(recent_temps) / len(recent_temps) if recent_temps else 0.0
            avg_rain = sum(recent_rains) / len(recent_rains) if recent_rains else 0.0
            weather_text = f"최근 3일 평균 기온: {avg_temp:.1f}℃ | 평균 강수량: {avg_rain:.1f}mm"
        else:
            weather_text = "날씨 정보 데이터 없음"
    except Exception as e:
        weather_text = f"날씨 조회 에러: {e}"
        
    db.close()

    # 5. 최종 컨텍스트 텍스트 조합
    context = f"""
[분석 대상 키워드]: {keyword}
[기준 일시]: {current_time.strftime('%Y-%m-%d %H:%M:%S')}

1. 네이버 쇼핑 및 검색 데이터
- 월간 총 검색량 (PC + 모바일): {naver_volume:,.0f}건

2. 유튜브 SNS 트렌드 4대 지표
- 최근 7일 언급량 증가율 (Growth): {sns_signals.get('growth', 0.0):.2f}%
- 최근 3시간 언급 급증도 (Burst): {sns_signals.get('burst', 0.0):.1f}배
- 확산 채널 수 (Unique Channels): {sns_signals.get('unique_channels', 0)}개 채널
- 채널 다양성 비율 (Channel Diversity): {sns_signals.get('channel_diversity', 0.0):.4f}

3. 최근 7일 내 실시간 인기 영상 (Top 3)
{top_videos_text}
4. 기상청 최근 날씨 현황
- {weather_text}
"""
    return context.strip()