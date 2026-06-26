def calculate_volume(daily_volumes: list[float]) -> dict:
    """
    Volume Score 계산
    최근 3일 평균 검색량이 1,000건 이상이면 100점.
    """
    if len(daily_volumes) < 3:
        return {"volume_score": 0.0}
        
    recent_avg = sum(daily_volumes[-3:]) / 3.0
    
    # 1,000건 -> 100점. (건당 0.1점)
    score = min(100.0, recent_avg * 0.1)
    
    return {
        "volume_score": round(score, 1)
    }
