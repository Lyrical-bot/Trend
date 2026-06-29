"""
역할: Trend Bot의 API 라우터와 엔드포인트를 정의합니다.
목적: 대시보드(프론트엔드)에서 필요한 키워드 타임라인 등의 데이터를 제공합니다.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from sns_sensing.database.db import get_db, engine, Base
from sns_sensing.models.models import KeywordStat
from sqlalchemy import func
from sns_sensing.pipeline.youtube.analytics.signal_engine import calculate_all_signals

# DB 초기화 (테스트용)
Base.metadata.create_all(bind=engine)

router = APIRouter()

@router.get("/keyword/{keyword}")
def get_keyword_timeline(keyword: str, db: Session = Depends(get_db)):
    """
    특정 키워드의 시간대별 언급량 타임라인 데이터 및 핵심 지표를 반환합니다.
    """
    stats = db.query(KeywordStat).filter(KeywordStat.keyword == keyword).order_by(KeywordStat.hour).all()
    
    current_time = datetime.now()
    signals = calculate_all_signals(db, keyword, current_time)
    
    # DB에 없는 새로운 키워드인지 확인 (간단 로직: stats가 없으면 신규)
    is_new_keyword = len(stats) == 0
    signals["is_new_keyword"] = is_new_keyword
    
    if not stats:
        return {"keyword": keyword, "timeline": [], "signals": signals}
    
    timeline = [{"hour": stat.hour.isoformat(), "count": stat.mention_count} for stat in stats]
    
    return {
        "keyword": keyword,
        "timeline": timeline,
        "signals": signals
    }

@router.get("/discovered-keywords")
def get_discovered_keywords(db: Session = Depends(get_db)):
    """
    최근 24시간 내에 Discovery Engine이 수집한 가장 많이 언급된 트렌드 키워드 Top 15를 반환합니다.
    """
    recent_start = datetime.now() - timedelta(days=1)
    
    # 최근 24시간 내 언급량 합계 기준 내림차순 정렬
    top_stats = db.query(
        KeywordStat.keyword,
        func.sum(KeywordStat.mention_count).label('total_mentions')
    ).filter(
        KeywordStat.hour >= recent_start
    ).group_by(
        KeywordStat.keyword
    ).order_by(
        func.sum(KeywordStat.mention_count).desc()
    ).limit(15).all()
    
    # 딕셔너리 형태로 변환하여 반환
    results = [{"keyword": stat.keyword, "mentions": stat.total_mentions} for stat in top_stats]
    return results
