from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, List

import numpy as np
import pandas as pd

from pipeline.feature_engine.acceleration import calculate_acceleration
from pipeline.feature_engine.burst import calculate_burst
from pipeline.feature_engine.persistence import calculate_persistence
from pipeline.feature_engine.stability import calculate_stability
from pipeline.feature_engine.trend_scorer import calculate_trend_score
from pipeline.feature_engine.volume import calculate_volume


@dataclass(frozen=True)
class EarlySignalConfig:
    min_history_days: int = 33
    min_current_volume: float = 100.0
    min_trend_score: float = 55.0
    min_burst_ratio: float = 1.5
    min_acceleration_score: float = 25.0
    cooldown_days: int = 14
    max_signals: int = 5
    breakout_horizon_days: int = 30
    breakout_multiplier: float = 3.0
    min_peak_volume: float = 1000.0


DEFAULT_CONFIG = EarlySignalConfig()


def _prepare_history(historical_data: List[Dict[str, Any]]) -> pd.DataFrame:
    df = pd.DataFrame(historical_data)
    df = df.rename(columns={"period": "date", "ratio": "volume"})
    df["date"] = pd.to_datetime(df["date"])
    df["volume"] = df["volume"].astype(float).clip(lower=0)
    return df.sort_values("date").reset_index(drop=True)


def _build_features_for_window(volumes: List[float]) -> Dict[str, float]:
    burst = calculate_burst(volumes)
    persistence = calculate_persistence(volumes)
    acceleration = calculate_acceleration(volumes)
    stability = calculate_stability(volumes)
    volume = calculate_volume(volumes)

    features = {
        **burst,
        **persistence,
        **acceleration,
        **stability,
        **volume,
    }
    scorer = calculate_trend_score(features)

    current = float(volumes[-1])
    recent_3 = float(np.mean(volumes[-3:]))
    prev_7 = float(np.mean(volumes[-10:-3])) if len(volumes) >= 10 else 0.0
    baseline_30 = float(np.mean(volumes[-33:-3])) if len(volumes) >= 33 else 0.0
    growth_7d = ((current - volumes[-8]) / max(1.0, volumes[-8])) * 100 if len(volumes) >= 8 else 0.0

    return {
        "currentVolume": round(current, 2),
        "recent3Avg": round(recent_3, 2),
        "prev7Avg": round(prev_7, 2),
        "baseline30Avg": round(baseline_30, 2),
        "growth7d": round(float(growth_7d), 2),
        "burstRatio": float(burst["burst_ratio"]),
        "burstScore": float(burst.get("burst_score", 0.0)),
        "persistenceScore": float(persistence["persistence_score"]),
        "accelerationScore": float(acceleration["acceleration_score"]),
        "stabilityScore": float(stability["stability_score"]),
        "volumeScore": float(volume["volume_score"]),
        "trendScore": float(scorer["trend_score"]),
        "signalLevel": scorer["signal_level"],
    }


def build_signal_feature_rows(
    historical_data: List[Dict[str, Any]],
    config: EarlySignalConfig = DEFAULT_CONFIG,
) -> List[Dict[str, Any]]:
    df = _prepare_history(historical_data)
    rows: List[Dict[str, Any]] = []

    if len(df) < config.min_history_days:
        return rows

    for idx in range(config.min_history_days - 1, len(df)):
        window = df.iloc[: idx + 1]
        features = _build_features_for_window(window["volume"].tolist())
        rows.append(
            {
                "date": window["date"].iloc[-1].strftime("%Y-%m-%d"),
                **features,
            }
        )

    return rows


def build_breakout_training_rows(
    historical_data: List[Dict[str, Any]],
    config: EarlySignalConfig = DEFAULT_CONFIG,
) -> List[Dict[str, Any]]:
    df = _prepare_history(historical_data)
    feature_rows = build_signal_feature_rows(historical_data, config)
    rows: List[Dict[str, Any]] = []

    for feature in feature_rows:
        signal_date = pd.to_datetime(feature["date"])
        current_volume = feature["currentVolume"]
        future = df[(df["date"] > signal_date) & (df["date"] <= signal_date + pd.Timedelta(days=config.breakout_horizon_days))]
        future_peak = float(future["volume"].max()) if not future.empty else 0.0
        is_breakout = (
            future_peak >= max(config.min_peak_volume, current_volume * config.breakout_multiplier)
            and current_volume < future_peak * 0.6
        )
        rows.append(
            {
                **feature,
                "futurePeakVolume": round(future_peak, 2),
                "isBreakout": bool(is_breakout),
                "config": asdict(config),
            }
        )

    return rows


def detect_early_signals(
    historical_data: List[Dict[str, Any]],
    config: EarlySignalConfig = DEFAULT_CONFIG,
) -> List[Dict[str, Any]]:
    feature_rows = build_signal_feature_rows(historical_data, config)
    signals: List[Dict[str, Any]] = []
    last_signal_date: pd.Timestamp | None = None

    for row in feature_rows:
        current_date = pd.to_datetime(row["date"])
        if last_signal_date is not None and (current_date - last_signal_date).days < config.cooldown_days:
            continue

        strong_score = row["trendScore"] >= config.min_trend_score
        strong_burst = row["burstRatio"] >= config.min_burst_ratio
        enough_volume = row["currentVolume"] >= config.min_current_volume
        accelerating = row["accelerationScore"] >= config.min_acceleration_score or row["persistenceScore"] >= 50
        above_baseline = row["currentVolume"] >= max(1.0, row["baseline30Avg"]) * 1.25

        if strong_score and strong_burst and enough_volume and accelerating and above_baseline:
            signals.append(
                {
                    "date": row["date"],
                    "type": "early_trend",
                    "label": "유행 전조 감지",
                    "score": row["trendScore"],
                    "volume": row["currentVolume"],
                    "burstRatio": row["burstRatio"],
                    "growth7d": row["growth7d"],
                    "accelerationScore": row["accelerationScore"],
                    "persistenceScore": row["persistenceScore"],
                    "reason": "검색량, 폭발력, 가속도, 지속성이 동시에 기준을 넘었습니다.",
                }
            )
            last_signal_date = current_date

        if len(signals) >= config.max_signals:
            break

    return signals
