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

def calculate_spike_candidates(db: Session, current_time: datetime, min_mentions: int = 10, max_candidates: int = 30) -> list:
    """
    1차 스파이크 필터(배치 쿼리):
    최근 3일간의 언급량이 N건 이상이고, 
    이전 14일 대비 일평균 언급량이 200% 이상 증가했거나 (혹은 이전 14일 언급량이 0인 콜드스타트)
    조건을 만족하는 키워드를 추출합니다. 예산 초과 방지를 위해 상위 K개를 리턴합니다.
    """
    from sqlalchemy import case
    
    recent_start = current_time - timedelta(days=3)
    past_start = recent_start - timedelta(days=14)
    
    # KeywordStat을 한 번에 스캔하여 과거와 최근 합계를 집계
    stats = db.query(
        KeywordStat.keyword,
        func.sum(case((KeywordStat.hour >= recent_start, KeywordStat.mention_count), else_=0)).label('recent_sum'),
        func.sum(case((KeywordStat.hour < recent_start, KeywordStat.mention_count), else_=0)).label('past_sum')
    ).filter(
        KeywordStat.hour >= past_start,
        KeywordStat.hour <= current_time
    ).group_by(KeywordStat.keyword).all()
    
    candidates = []
    for stat in stats:
        recent_sum = stat.recent_sum or 0
        past_sum = stat.past_sum or 0
        
        # 1. 절대량 하한선 (최근 3일간 합계)
        if recent_sum < min_mentions:
            continue
            
        recent_daily_avg = recent_sum / 3.0
        past_daily_avg = past_sum / 14.0
        
        spike_ratio = 0.0
        is_spike = False
        
        # 2. 콜드스타트 & 증가율 필터
        if past_sum == 0:
            is_spike = True
            spike_ratio = 999.0 # 매우 큰 값
        else:
            spike_ratio = recent_daily_avg / past_daily_avg
            if spike_ratio >= 2.0: # 200% 이상
                is_spike = True
                
        if is_spike:
            score = recent_sum * spike_ratio # Cut-off 랭킹용
            candidates.append({
                "keyword": stat.keyword,
                "recent_sum": recent_sum,
                "past_sum": past_sum,
                "spike_ratio": spike_ratio,
                "score": score
            })
            
    # Score 내림차순 정렬 후 최대 K개 반환 (Cut-off)
    candidates.sort(key=lambda x: x['score'], reverse=True)
    return candidates[:max_candidates]

def update_expired_trends(db: Session, current_time: datetime, min_mentions: int = 5):
    """
    기존에 TREND 상태인 키워드들 중, 
    최근 3일간의 언급량 합계가 절대량 하한선(min_mentions) 미만으로 떨어진 키워드를 EXPIRED로 상태 변경합니다.
    """
    from sns_sensing.models.models import TrendingKeyword
    from sqlalchemy import case
    
    recent_start = current_time - timedelta(days=3)
    
    # TREND 상태인 키워드 조회
    trend_keywords = db.query(TrendingKeyword).filter(TrendingKeyword.status == "TREND").all()
    if not trend_keywords:
        return
        
    trend_kws = [tk.keyword for tk in trend_keywords]
    
    # 해당 키워드들의 최근 3일 언급량 집계
    stats = db.query(
        KeywordStat.keyword,
        func.sum(KeywordStat.mention_count).label('recent_sum')
    ).filter(
        KeywordStat.keyword.in_(trend_kws),
        KeywordStat.hour >= recent_start,
        KeywordStat.hour <= current_time
    ).group_by(KeywordStat.keyword).all()
    
    stat_map = {row.keyword: (row.recent_sum or 0) for row in stats}
    
    expired_count = 0
    for tk in trend_keywords:
        recent_sum = stat_map.get(tk.keyword, 0)
        if recent_sum < min_mentions:
            tk.status = "EXPIRED"
            tk.updated_at = current_time
            expired_count += 1
            
    if expired_count > 0:
        try:
            db.commit()
        except:
            db.rollback()


