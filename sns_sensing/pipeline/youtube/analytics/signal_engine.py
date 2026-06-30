"""
역할: 트렌드 분석을 위한 핵심 지표(Growth, Burst, Channel Diversity)를 계산합니다.
목적: Trend Score를 대체하는 3대 지표를 산출하여 키워드의 확산 강도와 신뢰성(어뷰징 여부)을 평가합니다.
"""

from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
import statistics
from sns_sensing.models.models import KeywordStat, Video, Keyword, VideoStat

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

def calculate_engagement_velocity(db: Session, keyword: str, current_time: datetime) -> dict:
    """
    VideoStat 기반의 가속도(Velocity) 및 참여도(Engagement) 스코어를 산출합니다.
    """
    three_hours_ago = current_time - timedelta(hours=3)
    
    # 1. 베이지안 스무딩을 위한 α (전체 풀의 조회수 증가량 중앙값) 계산
    all_videos_stats = db.query(VideoStat.video_id, VideoStat.hour, VideoStat.view_count).filter(
        VideoStat.hour.in_([three_hours_ago, current_time])
    ).all()
    
    view_deltas = []
    video_map = {}
    for vid, hr, views in all_videos_stats:
        if vid not in video_map:
            video_map[vid] = {'past': None, 'curr': None}
        if hr == three_hours_ago:
            video_map[vid]['past'] = views
        elif hr == current_time:
            video_map[vid]['curr'] = views
            
    for vid, stats in video_map.items():
        if stats['past'] is not None and stats['curr'] is not None:
            delta = stats['curr'] - stats['past']
            if delta >= 0:
                view_deltas.append(delta)
                
    alpha = statistics.median(view_deltas) if len(view_deltas) > 0 else 100.0
    if alpha <= 0:
        alpha = 100.0
        
    # 2. 특정 키워드를 포함한 영상들 필터링
    keyword_videos = db.query(Video.video_id).join(Keyword, Keyword.video_id == Video.video_id).filter(
        Keyword.keyword == keyword
    ).all()
    keyword_vids = [v[0] for v in keyword_videos]
    
    if not keyword_vids:
        return {"velocity_views": 0, "engagement_score": 0.0, "alpha_used": alpha}
        
    # 3. 해당 키워드 영상들의 조회수, 좋아요, 댓글 증가량 합산
    kw_stats = db.query(VideoStat).filter(
        VideoStat.video_id.in_(keyword_vids),
        VideoStat.hour.in_([three_hours_ago, current_time])
    ).all()
    
    kw_map = {}
    for stat in kw_stats:
        vid = stat.video_id
        if vid not in kw_map:
            kw_map[vid] = {'past': None, 'curr': None}
        if stat.hour == three_hours_ago:
            kw_map[vid]['past'] = stat
        elif stat.hour == current_time:
            kw_map[vid]['curr'] = stat
            
    total_delta_views = 0
    total_delta_likes = 0
    total_delta_comments = 0
    
    for vid, states in kw_map.items():
        past = states['past']
        curr = states['curr']
        if past and curr:
            d_views = curr.view_count - past.view_count
            d_likes = curr.like_count - past.like_count
            d_comments = curr.comment_count - past.comment_count
            
            if d_views >= 0: total_delta_views += d_views
            if d_likes >= 0: total_delta_likes += d_likes
            if d_comments >= 0: total_delta_comments += d_comments

    # 4. Engagement Score 산출
    engagement_score = (total_delta_likes * 1 + total_delta_comments * 5) / (total_delta_views + alpha)
    
    return {
        "velocity_views": total_delta_views,
        "engagement_score": round(engagement_score, 4),
        "alpha_used": alpha
    }

def calculate_all_signals(db: Session, keyword: str, current_time: datetime) -> dict:
    """
    모든 핵심 지표를 종합하여 반환합니다.
    """
    diversity_data = calculate_channel_diversity(db, keyword)
    engagement_data = calculate_engagement_velocity(db, keyword, current_time)
    
    return {
        "growth": calculate_growth(db, keyword, current_time),
        "burst": calculate_burst(db, keyword, current_time),
        "channel_diversity": diversity_data["diversity_ratio"],
        "unique_channels": diversity_data["unique_channels"],
        "velocity_views": engagement_data["velocity_views"],
        "engagement_score": engagement_data["engagement_score"],
        "alpha_used": engagement_data["alpha_used"]
    }
