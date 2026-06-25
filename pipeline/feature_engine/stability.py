import numpy as np

def calculate_stability(daily_volumes: list[float]) -> dict:
    """
    Stability Score 계산
    최근 7일간의 변동계수(CV = 표준편차/평균) 활용.
    """
    if len(daily_volumes) < 7:
        return {"stability_score": 0.0}
        
    recent_7 = daily_volumes[-7:]
    mean_val = np.mean(recent_7)
    
    if mean_val == 0:
        return {"stability_score": 100.0} # 0으로 일정한 경우 안정적이라 볼 수도 있음 (하지만 volume score가 낮아짐)
        
    std_val = np.std(recent_7)
    cv = std_val / mean_val
    
    # CV가 0에 가까울수록 안정적(100점). CV가 1.0 이상이면 0점.
    score = max(0.0, 100.0 - (cv * 100.0))
    
    return {
        "stability_score": round(score, 1)
    }
