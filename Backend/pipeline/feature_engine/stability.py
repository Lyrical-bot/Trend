import numpy as np

def calculate_stability(daily_volumes: list[float]) -> dict:
    """
    Stability Score 계산 (개선판)
    
    기존 문제: 변동계수(CV)로 측정하면 유행 시작 시 검색량이 급등하면서
    CV가 높아져 오히려 감점됨 — 유행 전조와 모순.
    
    개선: '상승 방향의 일관성'을 측정.
    최근 7일간 전일 대비 변화량(diff)의 부호가 얼마나 일관된지 확인.
    모두 양수(꾸준히 상승)이면 100점, 오르락내리락이면 낮은 점수.
    
    이렇게 하면 검색량이 '불안정하게 튀는 노이즈'와 
    '꾸준히 한 방향으로 오르는 진짜 트렌드'를 구분할 수 있음.
    """
    if len(daily_volumes) < 8:
        return {"stability_score": 0.0}
    
    recent_8 = daily_volumes[-8:]
    diffs = [recent_8[i] - recent_8[i - 1] for i in range(1, 8)]
    
    # 방향 일관성: 양수 diff의 비율 측정
    positive_count = sum(1 for d in diffs if d > 0)
    negative_count = sum(1 for d in diffs if d < 0)
    
    total_nonzero = positive_count + negative_count
    if total_nonzero == 0:
        return {"stability_score": 50.0}  # 변동 없음 = 보통
    
    # 한쪽 방향으로 쏠린 정도 (0.5 = 오르락내리락, 1.0 = 한 방향)
    dominant_ratio = max(positive_count, negative_count) / total_nonzero
    
    # 0.5 → 0점, 1.0 → 100점으로 선형 매핑
    score = max(0.0, (dominant_ratio - 0.5) * 200.0)
    
    return {
        "stability_score": round(score, 1)
    }
