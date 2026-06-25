def calculate_trend_score(features: dict) -> dict:
    """
    최종 Trend Score 및 Signal Level 계산
    trend_score = 0.35 * Burst + 0.25 * Persistence + 0.20 * Accel + 0.10 * Stability + 0.10 * Volume
    """
    score = (
        0.35 * features.get('burst_score', 0.0) +
        0.25 * features.get('persistence_score', 0.0) +
        0.20 * features.get('acceleration_score', 0.0) +
        0.10 * features.get('stability_score', 0.0) +
        0.10 * features.get('volume_score', 0.0)
    )
    score = round(score, 1)
    
    if score >= 90:
        level = "VERY HIGH"
    elif score >= 80:
        level = "HIGH"
    elif score >= 70:
        level = "MEDIUM"
    elif score >= 60:
        level = "LOW"
    else:
        level = "IGNORE"
        
    return {
        "trend_score": score,
        "signal_level": level
    }
