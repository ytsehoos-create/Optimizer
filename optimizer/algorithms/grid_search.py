"""Exhaustive grid search over all parameter combinations."""
from __future__ import annotations

import logging
from typing import Any, Callable, Dict

from tqdm import tqdm

from ..parameter_space import ParameterSpace
from ..results import OptimizationResult, ResultsCollection
from .base import BaseOptimizer

log = logging.getLogger(__name__)


class GridSearchOptimizer(BaseOptimizer):

    def run(self, objective: Callable[[Dict[str, Any]], Any]) -> ResultsCollection:
        total = self.space.total_combinations
        log.info("Grid search: %d combinations to evaluate.", total)

        results = ResultsCollection()
        pbar = tqdm(self.space.grid_iterator(), total=total, desc="Grid Search", unit="trial")

        for params in pbar:
            result = objective(params)
            results.add(result)
            best = results.best()
            pbar.set_postfix(
                score=f"{result.score:.4f}",
                best=f"{best.score:.4f}" if best else "N/A",
            )

        return results
