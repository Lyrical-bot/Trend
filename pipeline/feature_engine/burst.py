import pandas as pd

def calculate_burst(daily_volumes: list[float]) -> dict:
    """
    Burst Ratio 및 Burst Score 계산
    최근 3일 평균과 직전 30일 평균을 비교.
    """
    if len(daily_volumes) < 33:
        return {"burst_ratio": 1.0, "burst_score": 0.0}
        
    recent_avg = sum(daily_volumes[-3:]) / 3.0
    baseline_avg = sum(daily_volumes[-33:-3]) / 30.0
    
    if baseline_avg == 0:
        baseline_avg = 1.0
        
    burst_ratio = recent_avg / baseline_avg
    
    # 선형 정규화: ratio <= 1 -> 0, ratio >= 10 -> 100
    if burst_ratio <= 1.0:
        burst_score = 0.0
    elif burst_ratio >= 10.0:
        burst_score = 100.0
    else:
        burst_score = ((burst_ratio - 1.0) / 9.0) * 100.0
        
    return {
        "burst_ratio": round(burst_ratio, 2),
        "burst_score": round(burst_score, 1)
    }
