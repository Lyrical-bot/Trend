from typing import TypedDict

class TrendResult(TypedDict):
    keyword: str
    burst_ratio: float
    persistence_score: float
    acceleration_score: float
    stability_score: float
    volume_score: float
    trend_score: float
    signal_level: str
    growth_rate: float
