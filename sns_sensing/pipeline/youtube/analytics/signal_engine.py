"""
역할: 트렌드 분석을 위한 핵심 지표(Growth, Burst, Channel Diversity)를 계산합니다.
목적: Trend Score를 대체하는 3대 지표를 산출하여 키워드의 확산 강도와 신뢰성(어뷰징 여부)을 평가합니다.
"""

from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
from sns_sensing.models.models import KeywordStat, Video, Keyword

def calculate_growth(db: Session, keyword: str, current_time: datetime) -> float:
    """
    언급 증가율(Growth)을 계산합니다.
    (최근 24시간 언급량) 대비 (과거 24시간 언급량)의 비율
    """
    recent_start = current_time - timedelta(days=1)
    past_start = current_time - timedelta(days=2)

    recent_count = db.query(func.sum(KeywordStat.mention_count)).filter(
        KeywordStat.keyword == keyword,
        KeywordStat.hour >= recent_start,
        KeywordStat.hour <= current_time
    ).scalar() or 0

    past_count = db.query(func.sum(KeywordStat.mention_count)).filter(
        KeywordStat.keyword == keyword,
        KeywordStat.hour >= past_start,
        KeywordStat.hour < recent_start
    ).scalar() or 0


    if past_count == 0:
        return 100.0 if recent_count > 0 else 0.0
    
    growth = ((recent_count - past_count) / past_count) * 100
    return round(growth, 2)

def calculate_burst(db: Session, keyword: str, current_time: datetime) -> float:
    """
    급증 정도(Burst)를 계산합니다.
    최근 3시간 언급량을 기반으로 계산합니다.
    """
    recent_start = current_time - timedelta(hours=3)
    
    recent_count = db.query(func.sum(KeywordStat.mention_count)).filter(
        KeywordStat.keyword == keyword,
        KeywordStat.hour >= recent_start,
        KeywordStat.hour <= current_time
    ).scalar() or 0
    
    return float(recent_count)

def calculate_channel_diversity(db: Session, keyword: str) -> dict:
    """
    채널 다양성(Channel Diversity)을 계산합니다.
    """
    stats = db.query(
        func.count(func.distinct(Video.channel_id)).label('unique_channels'),
        func.count(Video.video_id).label('total_videos')
    ).join(Keyword, Keyword.video_id == Video.video_id).filter(
        Keyword.keyword == keyword
    ).one()

    unique_channels = stats.unique_channels or 0
    total_videos = stats.total_videos or 0

    if total_videos == 0:
        diversity = 0.0
    else:
        diversity = unique_channels / total_videos
        
    return {
        "unique_channels": unique_channels,
        "diversity_ratio": round(diversity, 4)
    }

def calculate_all_signals(db: Session, keyword: str, current_time: datetime) -> dict:
    """
    모든 핵심 지표를 종합하여 반환합니다.
    """
    diversity_data = calculate_channel_diversity(db, keyword)
    return {
        "growth": calculate_growth(db, keyword, current_time),
        "burst": calculate_burst(db, keyword, current_time),
        "channel_diversity": diversity_data["diversity_ratio"],
        "unique_channels": diversity_data["unique_channels"]
    }
