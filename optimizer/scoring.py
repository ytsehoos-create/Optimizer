"""Scoring functions that convert BacktestMetrics into a single comparable number."""
from __future__ import annotations

from typing import Dict, Optional
from .results import BacktestMetrics


def compute_score(metrics: BacktestMetrics, metric: str, maximize: bool,
                  weights: Optional[Dict[str, float]] = None) -> float:
    if metric == "composite":
        return _composite_score(metrics, weights or {})

    value = metrics.get(metric)
    if value is None:
        return float("-inf") if maximize else float("inf")

    # Invert drawdown so maximizing score still means lower drawdown
    if metric in ("max_drawdown", "max_drawdown_abs") and maximize:
        return -abs(value)

    return float(value) if maximize else -float(value)


def _composite_score(metrics: BacktestMetrics, weights: Dict[str, float]) -> float:
    score = 0.0
    for attr, w in weights.items():
        val = metrics.get(attr)
        if val is None:
            continue
        # For drawdown metrics negative weight already handles direction
        score += w * float(val)
    return score
