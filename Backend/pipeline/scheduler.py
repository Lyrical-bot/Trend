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
YOUTUBE_SEEDS_CACHE = os.path.join(datasets_dir, "cached_youtube_seeds.json")

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
            
        print(f"[Success] Top 500 키워드 수집 완료. 분석을 시작합니다 (키워드 수: {len(keywords)})")
        
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
            
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 기존 백그라운드 데이터 수집 및 캐싱 완료!")
        
        # 5. 유튜브 수집용 동적 시드(Seed) 풀 업데이트 (5개 세부 카테고리)
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 유튜브 검색 시드용 세부 카테고리 확장을 시작합니다...")
        
        TARGET_CIDS = {
            "유가공품": "50000150",
            "다이어트식품": "50000024",
            "빵/베이커리": "50022959",
            "스낵/과자": "50022619",
            "젤리/사탕/초콜릿": "50022439"
        }
        
        youtube_seeds = {}
        for cat_name, cid in TARGET_CIDS.items():
            print(f"  -> [{cat_name}] 카테고리 키워드 수집 중...")
            # 초기 트렌드(초동)를 잡기 위해 30일이 아닌 최근 7일(주간) 기준으로 좁힘
            cat_keywords = await fetch_datalab_top_keywords(cid=cid, count=500, days_ago=7)
            if not cat_keywords:
                continue
                
            # 가중치 부여 (1~50위: 5, 51~150위: 3, 151~300위: 2, 301~500위: 1)
            for idx, kw in enumerate(cat_keywords):
                rank = idx + 1
                if rank <= 50:
                    weight = 5
                elif rank <= 150:
                    weight = 3
                elif rank <= 300:
                    weight = 2
                else:
                    weight = 1
                    
                # 이미 수집된 키워드라면 더 높은 가중치 유지
                if kw in youtube_seeds:
                    youtube_seeds[kw] = max(youtube_seeds[kw], weight)
                else:
                    youtube_seeds[kw] = weight
                    
            await asyncio.sleep(1.0) # API 예의 (딜레이)
            
        if youtube_seeds:
            with open(YOUTUBE_SEEDS_CACHE, "w", encoding="utf-8") as f:
                json.dump({"data": youtube_seeds, "updated_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S')}, f, ensure_ascii=False, indent=2)
            print(f"[Success] 유튜브 시드 {len(youtube_seeds)}개 갱신 완료 (cached_youtube_seeds.json 저장)")
        
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 모든 백그라운드 수집 작업 완료!")
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
    from sns_sensing.pipeline.runner import run_pipeline
    
    scheduler = BackgroundScheduler()
    # 6시간마다 식품 키워드 실행 (운영체제의 타임존에 따름)
    scheduler.add_job(sync_run_food_collection_job, 'interval', hours=6, id="food_top500_job")
    # 3시간마다 유튜브 파이프라인 실행
    scheduler.add_job(run_pipeline, 'interval', hours=3, id="youtube_pipeline_job")
    
    scheduler.start()
    print("백그라운드 스케줄러가 시작되었습니다. (주기: 식품 6시간, 유튜브 3시간)")
    
    import threading
    import time
    
    cache_needs_update = True
    if os.path.exists(WEAK_SIGNALS_CACHE) and os.path.exists(VELOCITY_CACHE):
        file_mod_time = os.path.getmtime(WEAK_SIGNALS_CACHE)
        # 파일이 생성된지 6시간(21600초)이 지나지 않았다면 업데이트 생략
        if time.time() - file_mod_time < 6 * 3600:
            cache_needs_update = False
            
    if cache_needs_update:
        print("초기 캐시 데이터가 없거나 6시간 이상 경과했습니다. 식품 데이터 수집을 즉시 시작합니다...")
        t1 = threading.Thread(target=sync_run_food_collection_job)
        t1.start()
        
    print("유튜브 트렌드 수집기(SNS Sensing) 1회차 즉시 가동을 시작합니다...")
    t2 = threading.Thread(target=run_pipeline)
    t2.start()
