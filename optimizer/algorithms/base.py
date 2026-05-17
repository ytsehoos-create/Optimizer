"""Abstract base for all optimization algorithms."""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Callable, Dict, Any

from ..parameter_space import ParameterSpace
from ..results import ResultsCollection

log = logging.getLogger(__name__)


class BaseOptimizer(ABC):
    """All optimizers receive an objective function and return a ResultsCollection."""

    def __init__(self, space: ParameterSpace, config: dict):
        self.space = space
        self.config = config

    @abstractmethod
    def run(self, objective: Callable[[Dict[str, Any]], float]) -> ResultsCollection:
        """
        Run the optimization.

        objective(params) -> score (higher = better)
        """
