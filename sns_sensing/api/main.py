"""
역할: Trend Bot의 API 라우터와 엔드포인트를 정의합니다.
목적: 대시보드(프론트엔드)에서 필요한 키워드 타임라인 등의 데이터를 제공합니다.

[이번 주 MVP 변경사항]
- TF-IDF "랭킹"은 폐기 -> 복합 Trend Score(100점) 정렬로 교체
- 단, TF-IDF의 IDF가 담당하던 "범용 단어 자동 필터링" 기능은 살려서
  사전 필터(generic word filter)로 유지함. STOPWORDS 고정 리스트만으로는
  새로 생기는 흔한 단어를 못 걸러내기 때문.
- 조회수/구독자는 "채널당 평균" 기준으로 집계 (총합 아님) -> 채널다양성과 중복 카운트 방지
- 채널다양성은 가산점이 아니라 "승수(multiplier)"로 적용
  -> 단일 채널(하꼬 유튜버 1명)은 기본점수가 만점이어도 구조적으로 상위권 진입 불가
- 시간가중 보너스(velocity)는 스키마 확인/백필이 필요해 다음 스프린트로 이연
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from sns_sensing.database.db import get_db, engine, Base
from sns_sensing.models.models import KeywordStat, Video, VideoStat, Keyword, TrendingKeyword
from sqlalchemy import func
import math
from sns_sensing.pipeline.youtube.analytics.signal_engine import calculate_all_signals
from sns_sensing.pipeline.youtube.discovery.keyword_discovery import STOPWORDS

# DB 초기화 (테스트용)
Base.metadata.create_all(bind=engine)

router = APIRouter()

# ============================================================
# Trend Score 계산 로직
# ============================================================

def _score_avg_views(avg_views: float) -> float:
    """평균 조회수 점수 (Max 40)"""
    if avg_views >= 100_000:
        return 40
    if avg_views >= 50_000:
        return 28
    if avg_views >= 10_000:
        return 14
    return 7

def _score_avg_subs(avg_subs: float) -> float:
    """평균 구독자 파워 점수 (Max 20)"""
    if avg_subs >= 100_000:
        return 20
    if avg_subs >= 10_000:
        return 14
    if avg_subs >= 1_000:
        return 7
    return 0

def _score_blue_ocean(avg_views: float, avg_subs: float) -> float:
    """블루오션 비율(평균조회수/평균구독자) 점수 (Max 25)"""
    # 구독자가 0인 신생/초소형 채널은 비율이 무한대로 튀는 걸 방지하기 위해
    # 분모에 최소 1을 보장 (0 나누기 방지 + 과도한 스코어 폭주 방지)
    ratio = avg_views / max(avg_subs, 1)
    if ratio >= 5:
        return 25
    if ratio >= 2:
        return 19
    if ratio >= 1:
        return 13
    return 0

def _score_upload_density(video_count: int) -> float:
    """업로드 밀집도 점수 (Max 15) - 해당 키워드로 잡힌 영상 개수"""
    if video_count >= 4:
        return 15
    if video_count >= 2:
        return 8
    return 0

def _channel_diversity_multiplier(channel_diversity: int) -> float:
    """
    채널 다양성 승수 (Gate 역할).
    ★핵심★: 가산점이 아니라 곱연산이라, 다른 점수가 아무리 높아도
    채널이 1개면 최종 점수가 구조적으로 상위권에 들 수 없음.
    """
    if channel_diversity >= 10:
        return 1.0
    if channel_diversity >= 5:
        return 0.9
    if channel_diversity >= 3:
        return 0.75
    if channel_diversity == 2:
        return 0.55
    return 0.35  # 1개 채널

def _is_generic_word(keyword: str, db: Session, total_videos: int, df_ratio_threshold: float = 0.08) -> bool:
    """
    TF-IDF의 IDF가 하던 '범용 단어 자동 배제' 역할만 분리해서 유지.
    이 키워드가 등장한 영상 수(DF)가 전체 영상 수 대비 threshold(기본 8%)를
    넘으면 "어디서나 쓰이는 흔한 말"로 간주하고 후보에서 제외한다.
    ※ 랭킹에는 관여하지 않음 (랭킹은 Trend Score가 전담) - 오직 통과/탈락만 결정.
    """
    df = db.query(Keyword.video_id).filter(Keyword.keyword == keyword).distinct().count()
    df_ratio = df / total_videos
    return df_ratio >= df_ratio_threshold

def _grade(score: float) -> str:
    if score >= 90:
        return "★★★★★ 확실한 트렌드"
    if score >= 70:
        return "★★★★☆ 강한 확산세"
    if score >= 55:
        return "★★★☆☆ 의미 있는 반응"
    if score >= 40:
        return "초기 신호"
    return "관찰 필요"

def calculate_trend_score(avg_views: float, avg_subs: float, video_count: int, channel_diversity: int) -> dict:
    """
    최종 점수 = 기본점수(100점 만점) × 채널다양성 승수
    기본점수 구성: 조회수(40) + 구독자(20) + 블루오션비율(25) + 업로드밀집도(15) = 100
    """
    base_score = (
        _score_avg_views(avg_views)
        + _score_avg_subs(avg_subs)
        + _score_blue_ocean(avg_views, avg_subs)
        + _score_upload_density(video_count)
    )
    multiplier = _channel_diversity_multiplier(channel_diversity)
    final_score = round(base_score * multiplier, 1)

    return {
        "score": final_score,
        "grade": _grade(final_score),
        "breakdown": {
            "avg_views_score": _score_avg_views(avg_views),
            "avg_subs_score": _score_avg_subs(avg_subs),
            "blue_ocean_score": _score_blue_ocean(avg_views, avg_subs),
            "upload_density_score": _score_upload_density(video_count),
            "base_score_before_multiplier": base_score,
            "channel_diversity_multiplier": multiplier,
        },
    }

# ============================================================
# 엔드포인트
# ============================================================

@router.get("/keyword/{keyword}")
def get_keyword_timeline(keyword: str, db: Session = Depends(get_db)):
    """
    특정 키워드의 시간대별 언급량 타임라인 데이터 및 핵심 지표를 반환합니다.
    """
    stats = db.query(KeywordStat).filter(KeywordStat.keyword == keyword).order_by(KeywordStat.hour).all()

    current_time = datetime.now()
    signals = calculate_all_signals(db, keyword, current_time)

    is_new_keyword = len(stats) == 0
    signals["is_new_keyword"] = is_new_keyword

    if not stats:
        return {"keyword": keyword, "timeline": [], "signals": signals}

    timeline = [{"hour": stat.hour.isoformat(), "count": stat.mention_count} for stat in stats]

    return {
        "keyword": keyword,
        "timeline": timeline,
        "signals": signals,
    }

@router.get("/discovered-keywords")
def get_discovered_keywords(db: Session = Depends(get_db)):
    """
    최근 데이터를 기반으로 '복합 Trend Score(100점 만점)'를 계산하여 Top 15 키워드를 반환합니다.

    [Trend Score 철학]
    - 조회수 총합이 아니라 "채널당 평균"을 사용해, 조회수와 채널다양성이
      서로 다른 신호를 반영하도록 분리합니다.
    - 채널다양성은 승수(0.35~1.0)로 작동해, 단 하나의 채널에서만 언급된
      키워드는 아무리 조회수가 높아도 최상위권에 오를 수 없습니다.
    - "여러 채널이 동시에 이야기하기 시작하는 것"이 진짜 트렌드 전조라는
      비즈니스 판단을 수식으로 강제합니다.
    """
    # N = 7일 기준으로 통일 (과거 띄엄띄엄 올라온 영상들의 백필 착시 현상 방지)
    recent_start = datetime.now() - timedelta(days=7)

    # 1. 키워드별 채널다양성 / 업로드수 / 평균조회수 / 평균구독자 집계 (TREND 상태만)
    rows = (
        db.query(
            Keyword.keyword,
            func.count(func.distinct(Video.channel_id)).label("channel_diversity"),
            func.count(func.distinct(Video.video_id)).label("video_count"),
            func.avg(VideoStat.view_count).label("avg_views"),
            func.avg(Video.subscriber_count).label("avg_subs"),
        )
        .join(TrendingKeyword, TrendingKeyword.keyword == Keyword.keyword)
        .join(Video, Keyword.video_id == Video.video_id)
        .join(VideoStat, Video.video_id == VideoStat.video_id)
        .filter(
            Video.published_at >= recent_start,
            TrendingKeyword.status == "TREND"
        )
        .group_by(Keyword.keyword)
        .all()
    )

    if not rows:
        return []

    # 2. IDF 계산을 위한 전체 문서(비디오) 수 조회 (범용 단어 필터링용)
    total_videos = db.query(Video).count()
    if total_videos == 0:
        total_videos = 1  # 0 나누기 방지

    # 3. 후보군별로 Trend Score 계산
    scored_keywords = []
    for row in rows:
        kw = row.keyword

        # STOPWORDS 필터링 (미리 알려진 흔한 단어 즉각 숨김 처리)
        if kw in STOPWORDS or len(kw) < 2:
            continue

        # 범용 단어 필터링 (STOPWORDS에 없는, 새로 흔해진 단어까지 자동으로 잡아냄)
        if _is_generic_word(kw, db, total_videos):
            continue

        avg_views = float(row.avg_views or 0)
        avg_subs = float(row.avg_subs or 0)
        video_count = int(row.video_count or 0)
        channel_diversity = int(row.channel_diversity or 0)

        result = calculate_trend_score(avg_views, avg_subs, video_count, channel_diversity)

        scored_keywords.append({
            "keyword": kw,
            "score": result["score"],
            "grade": result["grade"],
            "channel_diversity": channel_diversity,
            "video_count": video_count,
            "avg_views": round(avg_views),
            "avg_subs": round(avg_subs),
            "breakdown": result["breakdown"],
        })

    # 3. Trend Score 기준 내림차순 정렬 후 Top 15 반환
    scored_keywords.sort(key=lambda x: x["score"], reverse=True)
    return scored_keywords[:15]


@router.get("/debug-db")
def debug_db(db: Session = Depends(get_db)):
    try:
        from sns_sensing.models.models import Video, TrendingKeyword
        video_count = db.query(Video).count()
        trend_count = db.query(TrendingKeyword).filter(TrendingKeyword.status == 'TREND').count()
        return {
            "dialect": db.bind.dialect.name,
            "url_prefix": str(db.bind.url)[:15],
            "video_count": video_count,
            "trend_count": trend_count,
            "system_time": str(datetime.now())
        }
    except Exception as e:
        return {"error": str(e)}
