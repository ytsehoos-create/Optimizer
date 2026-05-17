"""Main orchestrator: connects algorithms, TradingView connector, and reporting."""
from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, Optional

from .algorithms import (
    GridSearchOptimizer,
    RandomSearchOptimizer,
    GeneticOptimizer,
    BayesianOptimizer,
)
from .parameter_space import ParameterSpace
from .results import BacktestMetrics, OptimizationResult, ResultsCollection
from .scoring import compute_score
from .tradingview import TradingViewConnector

log = logging.getLogger(__name__)


class StrategyOptimizer:
    """
    Top-level optimizer.

    Usage::

        from optimizer import StrategyOptimizer, ParameterSpace, IntParameter, FloatParameter

        space = ParameterSpace([
            IntParameter("fast_length", label="Fast Length", start=5, stop=50, step=5),
            IntParameter("slow_length", label="Slow Length", start=20, stop=200, step=10),
        ])

        opt = StrategyOptimizer(space=space, config=cfg)
        results = opt.run()
        opt.report(results)
    """

    def __init__(self, space: ParameterSpace, config: dict, on_result=None):
        self.space = space
        self.config = config
        self._connector: Optional[TradingViewConnector] = None
        self._on_result = on_result  # callable(OptimizationResult) for live UI updates

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self) -> ResultsCollection:
        opt_cfg = self.config.get("optimization", {})
        algorithm = opt_cfg.get("algorithm", "grid")
        metric = opt_cfg.get("metric", "net_profit")
        maximize = opt_cfg.get("maximize", True)
        weights = opt_cfg.get("composite_weights", {})

        log.info("Space: %s", self.space)
        log.info("Algorithm: %s | Metric: %s | Maximize: %s", algorithm, metric, maximize)

        tv_cfg = self.config.get("tradingview", {})
        self._connector = TradingViewConnector(tv_cfg)

        try:
            self._connector.start()

            def objective(params: Dict[str, Any]) -> OptimizationResult:
                return self._evaluate(params, metric, maximize, weights)

            optimizer = self._build_algorithm(algorithm)
            results = optimizer.run(objective)

        finally:
            self._connector.stop()

        results.rank(maximize=maximize)
        return results

    def report(self, results: ResultsCollection):
        from .reporter import Reporter
        rep_cfg = self.config.get("reporting", {})
        reporter = Reporter(results, rep_cfg)
        reporter.generate()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _evaluate(self, params: Dict[str, Any], metric: str,
                  maximize: bool, weights: dict) -> OptimizationResult:
        try:
            # Convert name→label so TradingView can find inputs by their UI label text
            name_to_label = {p.name: p.label for p in self.space.parameters}
            tv_params = {name_to_label.get(k, k): v for k, v in params.items()}
            self._connector.set_inputs(tv_params)
            metrics = self._connector.read_metrics()
            score = compute_score(metrics, metric, maximize, weights)
            result = OptimizationResult(params=params, metrics=metrics, score=score)
        except Exception as exc:
            log.error("Evaluation error for params %s: %s", params, exc)
            result = OptimizationResult(
                params=params,
                metrics=BacktestMetrics(),
                score=float("-inf"),
                error=str(exc),
            )
        if self._on_result:
            self._on_result(result)
        return result

    def _build_algorithm(self, name: str):
        opt_cfg = self.config.get("optimization", {})
        mapping = {
            "grid": GridSearchOptimizer,
            "random": RandomSearchOptimizer,
            "genetic": GeneticOptimizer,
            "bayesian": BayesianOptimizer,
        }
        cls = mapping.get(name.lower())
        if cls is None:
            raise ValueError(f"Unknown algorithm '{name}'. Choose from: {list(mapping)}")
        return cls(self.space, opt_cfg)
