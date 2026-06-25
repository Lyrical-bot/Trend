def calculate_persistence(daily_volumes: list[float]) -> dict:
    """
    Persistence Score 계산
    연속 상승 일수 기반.
    """
    if len(daily_volumes) < 2:
        return {"persistence_score": 0.0}
        
    consecutive_up_days = 0
    # 뒤에서부터 연속 상승 확인
    for i in range(len(daily_volumes)-1, 0, -1):
        if daily_volumes[i] > daily_volumes[i-1]:
            consecutive_up_days += 1
        else:
            break
            
    # 최대 5일 연속 상승을 100점으로 정규화 (1일당 20점)
    score = min(100.0, consecutive_up_days * 20.0)
    
    return {
        "persistence_score": round(score, 1)
    }
