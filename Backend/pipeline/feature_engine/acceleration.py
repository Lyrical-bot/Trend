def calculate_acceleration(daily_volumes: list[float]) -> dict:
    """
    Acceleration Score 계산
    최근 5일의 증가량의 증가분(이계도함수 느낌) 기반.
    """
    if len(daily_volumes) < 6:
        return {"acceleration_score": 0.0}
        
    # 최근 5일 + 직전 1일 = 총 6일 데이터 사용
    recent_6 = daily_volumes[-6:]
    
    # 1차 증가량
    diffs = [recent_6[i] - recent_6[i-1] for i in range(1, 6)]
    
    # 2차 증가량 (증가량의 증가량)
    diff_of_diffs = [diffs[i] - diffs[i-1] for i in range(1, 5)]
    
    # 연속으로 2차 증가량이 양수인지 확인 (가속도가 붙었는지)
    accel_points = 0
    for dod in diff_of_diffs:
        if dod > 0:
            accel_points += 1
            
    # accel_points 최대 4개 -> 100점 (개당 25점)
    score = accel_points * 25.0
    
    return {
        "acceleration_score": round(score, 1)
    }
