import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sns_sensing.database.db import Base
from sns_sensing.models.models import KeywordStat, TrendingKeyword
from sns_sensing.pipeline.youtube.analytics.signal_engine import calculate_spike_candidates, update_expired_trends

# 메모리 DB 사용
engine = create_engine("sqlite:///:memory:")
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture
def db():
    Base.metadata.create_all(bind=engine)
    db_session = TestingSessionLocal()
    yield db_session
    db_session.close()
    Base.metadata.drop_all(bind=engine)

def test_spike_filter_cold_start(db):
    now = datetime.now()
    recent_time = now - timedelta(days=1)
    
    # 과거 데이터 없음, 최근에만 15건 발생 (Cold Start)
    for _ in range(15):
        db.add(KeywordStat(keyword="신규트렌드", hour=recent_time, mention_count=1))
    db.commit()
    
    candidates = calculate_spike_candidates(db, now, min_mentions=10)
    assert len(candidates) == 1
    assert candidates[0]['keyword'] == "신규트렌드"
    assert candidates[0]['spike_ratio'] == 999.0

def test_spike_filter_steady_noise(db):
    now = datetime.now()
    
    # 14일 전부터 지금까지 매일 2건씩 꾸준히 발생
    for i in range(17):
        hour_time = now - timedelta(days=i)
        db.add(KeywordStat(keyword="꾸준한단어", hour=hour_time, mention_count=2))
    db.commit()
    
    candidates = calculate_spike_candidates(db, now, min_mentions=5)
    # 200% 증가율에 미치지 못하므로 탈락해야 함
    assert len(candidates) == 0

def test_spike_filter_noise_blacklist_prevention(db):
    now = datetime.now()
    recent_time = now - timedelta(days=1)
    
    # 예전에 NOISE로 등록됨
    db.add(TrendingKeyword(keyword="억울한노이즈", status="NOISE"))
    # 하지만 최근에 스파이크 발생!
    for _ in range(20):
        db.add(KeywordStat(keyword="억울한노이즈", hour=recent_time, mention_count=1))
    db.commit()
    
    candidates = calculate_spike_candidates(db, now, min_mentions=10)
    # 스파이크 필터는 NOISE 여부를 따지지 않고 후보로 올려야 함 (블랙리스트 방지)
    assert len(candidates) == 1
    assert candidates[0]['keyword'] == "억울한노이즈"

def test_update_expired_trends(db):
    now = datetime.now()
    recent_time = now - timedelta(days=1)
    
    # 1. 유지되어야 하는 트렌드 (최근 10건)
    db.add(TrendingKeyword(keyword="유지트렌드", status="TREND"))
    db.add(KeywordStat(keyword="유지트렌드", hour=recent_time, mention_count=10))
    
    # 2. 만료되어야 하는 트렌드 (최근 0건)
    db.add(TrendingKeyword(keyword="소멸트렌드", status="TREND"))
    
    db.commit()
    
    update_expired_trends(db, now, min_mentions=5)
    
    kept = db.query(TrendingKeyword).filter(TrendingKeyword.keyword == "유지트렌드").first()
    expired = db.query(TrendingKeyword).filter(TrendingKeyword.keyword == "소멸트렌드").first()
    
    assert kept.status == "TREND"
    assert expired.status == "EXPIRED"
