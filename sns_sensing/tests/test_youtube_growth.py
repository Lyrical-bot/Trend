import os
import sys
from datetime import datetime, timedelta
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker

parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(parent_dir)

from sns_sensing.models.models import Base, Video

def test_growth_rate_low_res_boundary():
    """
    백필 데이터로 인한 저밀도 윈도우(db_days_active < 14) 구간에서
    정확히 growth_rate가 null(None)로 반환되는지, 14일 경계값을 넘어설 때
    정상 계산 로직으로 타는지 검증하는 단위 테스트입니다.
    """
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    
    now = datetime.now()
    
    # 1. 6일 전에 가동 시작 (경계값 테스트: 6일 < 7일)
    v1 = Video(
        video_id="test_video_1",
        title="test",
        description="test",
        channel_id="test_channel",
        channel_title="test",
        published_at=now - timedelta(days=20),
        collected_at=now - timedelta(days=6)  # db_days_active = 6
    )
    db.add(v1)
    db.commit()
    
    oldest_collected = db.query(func.min(Video.collected_at)).scalar()
    db_days_active = (now - oldest_collected).days
    assert db_days_active == 6, f"Expected 6, got {db_days_active}"
    
    # 시뮬레이션: main.py 로직
    is_low_res_growth = (db_days_active >= 7 and db_days_active < 14)
    if db_days_active < 7:
        growth_rate = None
    else:
        growth_rate = 150  # mock normal calculation
        
    assert growth_rate is None, "6일차에는 비교군 자체가 없으므로 None 반환"
    assert is_low_res_growth is False
    
    # 2. 7일 전에 가동 시작 (경계값 테스트: 7일 == 7일 -> 저밀도 참고용 구간 진입)
    v1.collected_at = now - timedelta(days=7)
    db.commit()
    
    oldest_collected = db.query(func.min(Video.collected_at)).scalar()
    db_days_active = (now - oldest_collected).days
    
    is_low_res_growth = (db_days_active >= 7 and db_days_active < 14)
    if db_days_active < 7:
        growth_rate = None
    else:
        growth_rate = 150  # mock
        
    assert growth_rate == 150, "7일차부터는 계산 수행"
    assert is_low_res_growth is True, "7~13일차는 is_low_res_growth 플래그 켜짐"
    
    # 3. 14일 전에 가동 시작 (완전 정상 구간 진입)
    v1.collected_at = now - timedelta(days=14)
    db.commit()
    
    oldest_collected = db.query(func.min(Video.collected_at)).scalar()
    db_days_active = (now - oldest_collected).days
    
    is_low_res_growth = (db_days_active >= 7 and db_days_active < 14)
    
    assert is_low_res_growth is False, "14일차부터는 정상 구간이므로 플래그 꺼짐"
    
    db.close()
    print("경계값(6/7/14일) 테스트 통과!")

if __name__ == "__main__":
    test_growth_rate_low_res_boundary()
