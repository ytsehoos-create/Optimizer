"""Data structures for backtest results."""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

import pandas as pd


METRIC_LABELS = {
    "net_profit": "Net Profit (%)",
    "net_profit_abs": "Net Profit ($)",
    "profit_factor": "Profit Factor",
    "percent_profitable": "Win Rate (%)",
    "total_trades": "Total Trades",
    "max_drawdown": "Max Drawdown (%)",
    "max_drawdown_abs": "Max Drawdown ($)",
    "sharpe_ratio": "Sharpe Ratio",
    "sortino_ratio": "Sortino Ratio",
    "calmar_ratio": "Calmar Ratio",
    "avg_trade": "Avg Trade (%)",
    "avg_win": "Avg Win (%)",
    "avg_loss": "Avg Loss (%)",
    "win_loss_ratio": "Win/Loss Ratio",
    "composite_score": "Composite Score",
}


@dataclass
class BacktestMetrics:
    net_profit: Optional[float] = None
    net_profit_abs: Optional[float] = None
    profit_factor: Optional[float] = None
    percent_profitable: Optional[float] = None
    total_trades: Optional[int] = None
    max_drawdown: Optional[float] = None
    max_drawdown_abs: Optional[float] = None
    sharpe_ratio: Optional[float] = None
    sortino_ratio: Optional[float] = None
    calmar_ratio: Optional[float] = None
    avg_trade: Optional[float] = None
    avg_win: Optional[float] = None
    avg_loss: Optional[float] = None
    win_loss_ratio: Optional[float] = None
    composite_score: Optional[float] = None

    def get(self, metric: str) -> Optional[float]:
        return getattr(self, metric, None)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class OptimizationResult:
    params: Dict[str, Any]
    metrics: BacktestMetrics
    score: float = 0.0
    rank: int = 0
    trial_id: int = 0
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = {}
        d.update(self.params)
        d.update(self.metrics.to_dict())
        d["score"] = self.score
        d["rank"] = self.rank
        d["trial_id"] = self.trial_id
        if self.error:
            d["error"] = self.error
        return d


class ResultsCollection:
    """Holds all optimization results and provides analysis helpers."""

    def __init__(self):
        self._results: List[OptimizationResult] = []

    def add(self, result: OptimizationResult):
        result.trial_id = len(self._results)
        self._results.append(result)

    def __len__(self) -> int:
        return len(self._results)

    def __iter__(self):
        return iter(self._results)

    @property
    def successful(self) -> List[OptimizationResult]:
        return [r for r in self._results if r.error is None]

    def rank(self, metric: str = "score", maximize: bool = True):
        valid = self.successful
        valid.sort(key=lambda r: r.score if metric == "score" else (r.metrics.get(metric) or float('-inf')),
                   reverse=maximize)
        for i, r in enumerate(valid):
            r.rank = i + 1

    def top_n(self, n: int = 10) -> List[OptimizationResult]:
        ranked = sorted(self.successful, key=lambda r: r.rank)
        return ranked[:n]

    def to_dataframe(self) -> pd.DataFrame:
        rows = [r.to_dict() for r in self._results]
        return pd.DataFrame(rows)

    def best(self) -> Optional[OptimizationResult]:
        valid = self.successful
        if not valid:
            return None
        return min(valid, key=lambda r: r.rank)

    def save_csv(self, path: str):
        df = self.to_dataframe()
        df.to_csv(path, index=False)

    def save_json(self, path: str):
        data = [r.to_dict() for r in self._results]
        with open(path, "w") as f:
            json.dump(data, f, indent=2, default=str)
