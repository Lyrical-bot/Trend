def calculate_persistence(daily_volumes: list[float]) -> dict:
    """
    Persistence Score 계산 (개선판)
    기존: 끝에서부터 연속 상승일만 카운트 → 하루 빠지면 0점이 되는 취약점
    개선: 최근 7일 중 전일 대비 상승한 날의 비율로 측정 → 노이즈에 강건
    
    예시:
      7일 중 5일 상승 → 5/7 ≈ 71.4점
      7일 중 7일 상승 → 7/7 = 100점
      7일 중 2일 상승 → 2/7 ≈ 28.6점
    """
    if len(daily_volumes) < 8:
        return {"persistence_score": 0.0}
    
    # 최근 7일의 전일 대비 변화를 확인 (8일 데이터 필요: 7개의 diff)
    recent_8 = daily_volumes[-8:]
    up_days = 0
    total_days = 7
    
    for i in range(1, 8):
        if recent_8[i] > recent_8[i - 1]:
            up_days += 1
    
    # 상승 비율을 100점 만점으로 환산
    score = (up_days / total_days) * 100.0
    
    return {
        "persistence_score": round(score, 1)
    }
