import os
import sys
import pandas as pd
import json
from datetime import datetime, timedelta

# 현재 파일 위치 기준 상위 상위 디렉토리를 sys.path에 추가 (new 폴더)
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(parent_dir)

from pipeline.feature_engine.burst import calculate_burst
from pipeline.feature_engine.growth import calculate_growth
from pipeline.feature_engine.persistence import calculate_persistence
from pipeline.feature_engine.acceleration import calculate_acceleration
from pipeline.feature_engine.stability import calculate_stability
from pipeline.feature_engine.volume import calculate_volume
from pipeline.feature_engine.trend_scorer import calculate_trend_score
from pipeline.models.trend_result import TrendResult

def detect_weak_signals(target_date_str=None) -> list[TrendResult]:
    dataset_path = os.path.join(parent_dir, "datasets", "historical_fb_data.csv")
    
    if not os.path.exists(dataset_path):
        print("데이터셋이 존재하지 않습니다.")
        return []

    df = pd.read_csv(dataset_path, encoding='utf-8')
    df['date'] = pd.to_datetime(df['date'])
    
    if target_date_str:
        target_dt = pd.to_datetime(target_date_str)
        df = df[df['date'] <= target_dt]
        
    results = []
    
    for keyword, group in df.groupby('keyword'):
        group = group.sort_values(by='date').reset_index(drop=True)
        volumes = group['search_volume_est'].tolist()
        
        # 33일치 데이터가 안되면 스킵 (burst_ratio 계산 최소 조건)
        if len(volumes) < 33:
            continue
            
        burst = calculate_burst(volumes)
        growth = calculate_growth(volumes)
        persistence = calculate_persistence(volumes)
        accel = calculate_acceleration(volumes)
        stability = calculate_stability(volumes)
        volume = calculate_volume(volumes)
        
        features = {
            **burst,
            **persistence,
            **accel,
            **stability,
            **volume
        }
        
        scorer = calculate_trend_score(features)
        
        res: TrendResult = {
            "keyword": keyword,
            "burst_ratio": burst["burst_ratio"],
            "burst_score": burst.get("burst_score", 0.0),
            "persistence_score": persistence["persistence_score"],
            "acceleration_score": accel["acceleration_score"],
            "stability_score": stability["stability_score"],
            "volume_score": volume["volume_score"],
            "trend_score": scorer["trend_score"],
            "signal_level": scorer["signal_level"],
            "growth_rate": growth["growth_rate"]
        }
        results.append(res)
        
    # 점수 높은 순 정렬
    results = sorted(results, key=lambda x: x["trend_score"], reverse=True)
    return results

async def detect_weak_signals_live(keywords: list[str], days_ago: int = 60) -> list[TrendResult]:
    from naver_api import fetch_naver_trend
    from naver_ad_api import fetch_search_ad_volume
    
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d")
    
    # 1. Fetch Search Ad Volume for all keywords
    ad_volumes = await fetch_search_ad_volume(keywords)
    
    # 2. Chunk keywords into groups of 5 for Datalab API
    chunk_size = 5
    results = []
    
    for i in range(0, len(keywords), chunk_size):
        chunk = keywords[i:i+chunk_size]
        keyword_groups = [{"groupName": kw, "keywords": [kw]} for kw in chunk]
        
        try:
            naver_response = await fetch_naver_trend(
                start_date=start_date,
                end_date=end_date,
                time_unit="date",
                keyword_groups=keyword_groups
            )
            
            datalab_results = naver_response.get("results", [])
            for group in datalab_results:
                kw = group.get("title")
                data = group.get("data", [])
                
                # 정규화 (비율 0~100 -> 실제 검색량(건))
                group_monthly_volume = ad_volumes.get(kw, 0.0)
                
                volumes = []
                
                if group_monthly_volume > 0 and len(data) > 0:
                    total_ratio = sum(item["ratio"] for item in data)
                    days_queried = len(data)
                    estimated_monthly_ratio_sum = (total_ratio / days_queried) * 30
                    if estimated_monthly_ratio_sum > 0:
                        multiplier = group_monthly_volume / estimated_monthly_ratio_sum
                        for item in data:
                            volumes.append(item["ratio"] * multiplier)
                    else:
                        volumes = [0]*len(data)
                else:
                    volumes = [item["ratio"] for item in data]
                
                # 33일치 이상인지 확인
                if len(volumes) < 33:
                    continue
                    
                burst = calculate_burst(volumes)
                growth = calculate_growth(volumes)
                persistence = calculate_persistence(volumes)
                accel = calculate_acceleration(volumes)
                stability = calculate_stability(volumes)
                volume = calculate_volume(volumes)
                
                features = {
                    **burst,
                    **persistence,
                    **accel,
                    **stability,
                    **volume
                }
                
                scorer = calculate_trend_score(features)
                
                res: TrendResult = {
                    "keyword": kw,
                    "burst_ratio": burst["burst_ratio"],
                    "burst_score": burst.get("burst_score", 0.0),
                    "persistence_score": persistence["persistence_score"],
                    "acceleration_score": accel["acceleration_score"],
                    "stability_score": stability["stability_score"],
                    "volume_score": volume["volume_score"],
                    "trend_score": scorer["trend_score"],
                    "signal_level": scorer["signal_level"],
                    "growth_rate": growth["growth_rate"]
                }
                results.append(res)
                
        except Exception as e:
            print(f"Error fetching naver trend for {chunk}: {e}")
            
        import asyncio
        await asyncio.sleep(0.5) # Rate limit 방어
            
    # 점수 높은 순 정렬
    results = sorted(results, key=lambda x: x["trend_score"], reverse=True)
    return results

if __name__ == "__main__":
    final_output = detect_weak_signals()
    print(json.dumps(final_output, ensure_ascii=False, indent=2))
