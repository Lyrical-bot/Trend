import os
import json
import asyncio
from datetime import datetime
from pipeline.services.trend_detector import detect_weak_signals_live
from pipeline.velocity_model import get_velocity_ranking_live
from naver_api import fetch_datalab_top_keywords

parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
datasets_dir = os.path.join(parent_dir, "datasets")

WEAK_SIGNALS_CACHE = os.path.join(datasets_dir, "cached_food_signals.json")
VELOCITY_CACHE = os.path.join(datasets_dir, "cached_food_velocity.json")

# 수집 중인지 상태를 기록하는 파일 (Lock)
LOCK_FILE = os.path.join(datasets_dir, "scheduler_lock.txt")

async def run_food_collection_job():
    """식품 카테고리(Top 500) 데이터를 수집하고 분석하여 캐시에 저장합니다."""
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 백그라운드 식품 Top 500 수집 작업을 시작합니다...")
    
    if os.path.exists(LOCK_FILE):
        print("이미 수집 작업이 진행 중입니다. 스킵합니다.")
        return
        
    try:
        # 1. Lock 걸기
        with open(LOCK_FILE, "w", encoding="utf-8") as f:
            f.write("running")
            
        # 2. 식품(50000006) 카테고리의 Top 500 키워드 가져오기
        keywords = await fetch_datalab_top_keywords(cid="50000006", count=500)
        
        if not keywords:
            print("키워드 수집에 실패했습니다. 다음 주기에 다시 시도합니다.")
            return
            
        print(f"✅ Top 500 키워드 수집 완료. 분석을 시작합니다 (키워드 수: {len(keywords)})")
        
        # 3. Weak Signal 분석 및 저장
        print("  -> Weak Signal 점수 계산 중...")
        weak_signals_result = await detect_weak_signals_live(keywords, days_ago=60)
        with open(WEAK_SIGNALS_CACHE, "w", encoding="utf-8") as f:
            json.dump({"data": weak_signals_result, "updated_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S')}, f, ensure_ascii=False)
            
        # 4. Velocity Ranking 분석 및 저장
        print("  -> Velocity Ranking 점수 계산 중...")
        velocity_result = await get_velocity_ranking_live(keywords)
        if "error" in velocity_result:
            velocity_data = []
        else:
            velocity_data = velocity_result.get("data", [])
            
        with open(VELOCITY_CACHE, "w", encoding="utf-8") as f:
            json.dump({"data": velocity_data, "updated_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S')}, f, ensure_ascii=False)
            
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 백그라운드 데이터 수집 및 캐싱 완료!")
        
    except Exception as e:
        print(f"백그라운드 수집 중 에러 발생: {e}")
    finally:
        # Lock 해제
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)

def sync_run_food_collection_job():
    """APScheduler에서 호출하기 위한 동기 래퍼 함수"""
    asyncio.run(run_food_collection_job())

def init_scheduler():
    from apscheduler.schedulers.background import BackgroundScheduler
    scheduler = BackgroundScheduler()
    # 6시간마다 실행 (운영체제의 타임존에 따름)
    scheduler.add_job(sync_run_food_collection_job, 'interval', hours=6, id="food_top500_job")
    scheduler.start()
    print("백그라운드 스케줄러가 시작되었습니다. (주기: 6시간)")
    
    # 만약 캐시 파일이 없다면 서버 시작 시 즉시 백그라운드로 1회 실행 트리거
    if not os.path.exists(WEAK_SIGNALS_CACHE) or not os.path.exists(VELOCITY_CACHE):
        print("초기 캐시 데이터가 없습니다. 즉시 수집을 시작합니다...")
        # 백그라운드 스레드에서 실행되도록 asyncio 래퍼를 씀
        import threading
        t = threading.Thread(target=sync_run_food_collection_job)
        t.start()
