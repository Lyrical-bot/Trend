def calculate_growth(daily_volumes: list[float]) -> dict:
    """
    Growth Rate 계산 (ML용 Feature)
    최근 7일 평균과 직전 7일 평균을 비교.
    """
    if len(daily_volumes) < 14:
        return {"growth_rate": 0.0}
        
    recent_7_avg = sum(daily_volumes[-7:]) / 7.0
    prev_7_avg = sum(daily_volumes[-14:-7]) / 7.0
    
    if prev_7_avg == 0:
        prev_7_avg = 1.0
        
    growth_rate = (recent_7_avg - prev_7_avg) / prev_7_avg
    
    return {
        "growth_rate": round(growth_rate, 2)
    }
