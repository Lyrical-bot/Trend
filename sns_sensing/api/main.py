"""
역할: Trend Bot의 API 라우터와 엔드포인트를 정의합니다.
목적: 대시보드(프론트엔드)에서 필요한 키워드 타임라인 등의 데이터를 제공합니다.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from sns_sensing.database.db import get_db, engine, Base
from sns_sensing.models.models import KeywordStat, Video, Keyword
from sqlalchemy import func
import math
from sns_sensing.pipeline.youtube.analytics.signal_engine import calculate_all_signals
from sns_sensing.pipeline.youtube.discovery.keyword_discovery import STOPWORDS

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
    최근 24시간 내에 수집된 키워드들을 TF-IDF 기반으로 가중치를 주어 Top 15 트렌드 키워드를 반환합니다.
    (흔한 수식어는 점수가 깎이고, 특이한 명사들이 상위로 올라오게 됩니다)
    
    [TF-IDF 알고리즘 설명]
    - TF (Term Frequency, 단어 빈도): 
      특정 단어가 최근 24시간 동안 얼마나 많이 언급되었는가? (절대적인 인기도)
    - DF (Document Frequency, 문서 빈도):
      특정 단어가 과거부터 지금까지 총 몇 개의 유튜브 영상에 등장했는가?
      ("리뷰", "편의점" 같은 단어는 DF가 무척 높고, "크루키" 같은 신조어는 DF가 낮음)
    - IDF (Inverse Document Frequency, 역문서 빈도):
      DF의 역수로, log(전체 영상 수 / DF)로 계산. 흔한 단어일수록 0에 가까워지고, 희귀한 단어일수록 값이 커짐.
    - Score (TF * IDF):
      단순 언급량(TF)에 희귀도(IDF) 가중치를 곱하여, '흔하게 쓰이는 쓰레기 단어'를 하위권으로 밀어내고
      '최근에 갑자기 등장한 진짜 트렌드 단어'를 최상단으로 끌어올리는 수학적 필터링 기법.
    """
    recent_start = datetime.now() - timedelta(days=1)
    
    # 1. 1차 후보군 추출: 최근 24시간 내 언급량(TF) 상위 100개
    top_tf_stats = db.query(
        KeywordStat.keyword,
        func.sum(KeywordStat.mention_count).label('total_mentions')
    ).filter(
        KeywordStat.hour >= recent_start
    ).group_by(
        KeywordStat.keyword
    ).order_by(
        func.sum(KeywordStat.mention_count).desc()
    ).limit(100).all()

    if not top_tf_stats:
        return []

    # 2. IDF 계산을 위한 전체 문서(비디오) 수 조회
    total_videos = db.query(Video).count()
    if total_videos == 0:
        total_videos = 1  # 0 나누기 방지

    # 3. 각 후보 키워드별 TF-IDF 점수 계산
    scored_keywords = []
    for stat in top_tf_stats:
        kw = stat.keyword
        
        # STOPWORDS 필터링 (과거에 수집된 흔한 단어 즉각 숨김 처리)
        if kw in STOPWORDS or len(kw) < 2:
            continue
            
        tf = stat.total_mentions
        
        # DF(Document Frequency): 이 키워드가 전체 기간 동안 총 몇 개의 비디오에 등장했는지
        df = db.query(Keyword.video_id).filter(Keyword.keyword == kw).distinct().count()
        
        # IDF (흔한 단어일수록 값이 작아짐, 희귀 단어일수록 커짐)
        # 1을 더하여 0으로 나누거나 log(0)이 되는 것을 방지
        idf = math.log(total_videos / (df + 1)) + 1
        
        tf_idf_score = tf * idf
        
        scored_keywords.append({
            "keyword": kw,
            "mentions": tf,  # 원본 TF (표시용)
            "score": tf_idf_score
        })

    # 4. TF-IDF 점수 기준으로 내림차순 정렬 후 Top 15 반환
    scored_keywords.sort(key=lambda x: x["score"], reverse=True)
    top_15 = scored_keywords[:15]
    
    return top_15
