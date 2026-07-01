"""
역할: 트렌드 분석을 위한 핵심 지표(Growth, Burst, Channel Diversity)를 계산합니다.
목적: Trend Score를 대체하는 3대 지표를 산출하여 키워드의 확산 강도와 신뢰성(어뷰징 여부)을 평가합니다.
"""

from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
import statistics
from sns_sensing.models.models import KeywordStat, Video, Keyword, VideoStat

def calculate_growth(db: Session, keyword: str, current_time: datetime, trend_window_days: int = 7) -> float:
    """
    언급 증가율(Growth)을 계산합니다.
    '업로드 시점(published_at)' 기준으로 최근 N일 대비 과거 N일의 영상 개수 증가율.
    베이지안 스무딩 (K=10)을 적용하여 작은 표본의 착시 현상(절벽 효과)을 방지합니다.
    """
    recent_start = current_time - timedelta(days=trend_window_days)
    past_start = current_time - timedelta(days=trend_window_days * 2)

    # 최근 N일 업로드된 영상 수
    recent_count = db.query(func.count(func.distinct(Video.video_id))).join(
        Keyword, Keyword.video_id == Video.video_id
    ).filter(
        Keyword.keyword == keyword,
        Video.published_at >= recent_start,
        Video.published_at <= current_time
    ).scalar() or 0

    # 과거 N일 업로드된 영상 수
    past_count = db.query(func.count(func.distinct(Video.video_id))).join(
        Keyword, Keyword.video_id == Video.video_id
    ).filter(
        Keyword.keyword == keyword,
        Video.published_at >= past_start,
        Video.published_at < recent_start
    ).scalar() or 0

    # 베이지안 스무딩 (K=10) 적용
    K = 10
    growth = ((recent_count - past_count) / (past_count + K)) * 100
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

def calculate_channel_diversity(db: Session, keyword: str, current_time: datetime, trend_window_days: int = 7) -> dict:
    """
    채널 다양성(Channel Diversity)을 계산합니다.
    (업로드 시점 기준 최근 N일 이내 영상 대상)
    """
    recent_start = current_time - timedelta(days=trend_window_days)
    
    stats = db.query(
        func.count(func.distinct(Video.channel_id)).label('unique_channels'),
        func.count(func.distinct(Video.video_id)).label('total_videos')
    ).join(Keyword, Keyword.video_id == Video.video_id).filter(
        Keyword.keyword == keyword,
        Video.published_at >= recent_start
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
    diversity_data = calculate_channel_diversity(db, keyword, current_time)
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

def calculate_sns_trend_score(db: Session, keyword: str, current_time: datetime, tf_idf_score: float = 0.0) -> dict:
    """
    유튜브 지표 기반 종합 트렌드 스코어를 계산합니다.
    공식: (TF-IDF * Weight) + 영상 증가율 + 조회수 증가율 + (다양성 가중치 * 최우선) + 최근성(Recency)
    """
    signals = calculate_all_signals(db, keyword, current_time)
    
    growth = signals["growth"]
    velocity_views = signals["velocity_views"]
    channel_diversity = signals["channel_diversity"]
    unique_channels = signals["unique_channels"]
    
    # 1. 다양성 가중치 (최우선 중요도)
    # unique_channels가 1이면(한 채널 도배) 페널티, 여러 채널일수록 기하급수적 보상
    diversity_weight = (unique_channels ** 1.5) * channel_diversity * 10
    
    # 2. 영상 증가율 점수 (최대 100점 캡)
    growth_score = min(growth, 100)
    
    # 3. 조회수 증가율 점수 (가속도 반영)
    velocity_score = min(velocity_views / 1000, 50)
    
    # 4. TF-IDF 반영
    tf_idf_weight = tf_idf_score * 5
    
    # 종합 점수
    total_score = tf_idf_weight + growth_score + velocity_score + diversity_weight
    
    return {
        "total_score": round(total_score, 2),
        "diversity_weight": round(diversity_weight, 2),
        "growth_score": round(growth_score, 2),
        "velocity_score": round(velocity_score, 2),
        "tf_idf_weight": round(tf_idf_weight, 2),
        "signals": signals
    }
