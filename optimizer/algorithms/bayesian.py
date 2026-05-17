"""Bayesian optimization using scikit-optimize (skopt)."""
from __future__ import annotations

import logging
from typing import Any, Callable, Dict

from tqdm import tqdm

from ..parameter_space import ParameterSpace
from ..results import ResultsCollection
from .base import BaseOptimizer

log = logging.getLogger(__name__)


class BayesianOptimizer(BaseOptimizer):

    def run(self, objective: Callable[[Dict[str, Any]], Any]) -> ResultsCollection:
        try:
            from skopt import gp_minimize
            from skopt.space import Integer
        except ImportError:
            raise ImportError(
                "Install 'scikit-optimize' to use Bayesian optimization: pip install scikit-optimize"
            )

        cfg = self.config.get("bayesian", {})
        n_calls = cfg.get("n_calls", 50)
        n_random_starts = cfg.get("n_random_starts", 10)
        seed = cfg.get("seed", 42)

        bounds = self.space.bounds()
        skopt_space = [Integer(lo, hi, name=p.name) for (lo, hi), p in
                       zip(bounds, self.space.parameters)]

        results = ResultsCollection()
        pbar = tqdm(total=n_calls, desc="Bayesian Search", unit="trial")

        def skopt_objective(indices):
            params = self.space.decode_individual(indices)
            result = objective(params)
            results.add(result)
            pbar.update(1)
            pbar.set_postfix(score=f"{result.score:.4f}")
            return -result.score  # skopt minimizes

        gp_minimize(
            skopt_objective,
            skopt_space,
            n_calls=n_calls,
            n_random_starts=n_random_starts,
            random_state=seed,
            verbose=False,
        )

        pbar.close()
        return results
