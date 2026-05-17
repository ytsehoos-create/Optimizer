"""Random sampling across the parameter space."""
from __future__ import annotations

import logging
from typing import Any, Callable, Dict

import numpy as np
from tqdm import tqdm

from ..parameter_space import ParameterSpace
from ..results import OptimizationResult, ResultsCollection
from .base import BaseOptimizer

log = logging.getLogger(__name__)


class RandomSearchOptimizer(BaseOptimizer):

    def run(self, objective: Callable[[Dict[str, Any]], Any]) -> ResultsCollection:
        cfg = self.config.get("random_search", {})
        n_trials = cfg.get("n_trials", 100)
        seed = cfg.get("seed", 42)
        rng = np.random.default_rng(seed)

        total = self.space.total_combinations
        n_trials = min(n_trials, total)
        log.info("Random search: %d / %d combinations.", n_trials, total)

        samples = self.space.random_sample(rng, n_trials)
        results = ResultsCollection()
        pbar = tqdm(samples, desc="Random Search", unit="trial")

        for params in pbar:
            result = objective(params)
            results.add(result)
            best = results.best()
            pbar.set_postfix(
                score=f"{result.score:.4f}",
                best=f"{best.score:.4f}" if best else "N/A",
            )

        return results
