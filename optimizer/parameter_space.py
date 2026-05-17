"""Parameter space definitions for strategy optimization."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Iterator, List, Optional, Union


@dataclass
class Parameter:
    """Base class for a single optimizable parameter."""
    name: str
    label: str          # Exact label shown in TradingView strategy inputs dialog
    description: str = ""

    def values(self) -> List[Any]:
        raise NotImplementedError

    def random_value(self, rng) -> Any:
        raise NotImplementedError

    def __len__(self) -> int:
        return len(self.values())


@dataclass
class IntParameter(Parameter):
    """Integer parameter with inclusive start/stop and step."""
    start: int = 0
    stop: int = 100
    step: int = 1

    def values(self) -> List[int]:
        return list(range(self.start, self.stop + 1, self.step))

    def random_value(self, rng) -> int:
        vals = self.values()
        return rng.choice(vals)

    def __len__(self) -> int:
        return math.ceil((self.stop - self.start + 1) / self.step)


@dataclass
class FloatParameter(Parameter):
    """Float parameter with inclusive start/stop and step."""
    start: float = 0.0
    stop: float = 1.0
    step: float = 0.1
    decimals: int = 2

    def values(self) -> List[float]:
        vals = []
        v = self.start
        while v <= self.stop + 1e-9:
            vals.append(round(v, self.decimals))
            v += self.step
        return vals

    def random_value(self, rng) -> float:
        vals = self.values()
        return rng.choice(vals)

    def __len__(self) -> int:
        return len(self.values())


@dataclass
class CategoricalParameter(Parameter):
    """Parameter with a fixed set of allowed string/number options."""
    options: List[Any] = field(default_factory=list)

    def values(self) -> List[Any]:
        return list(self.options)

    def random_value(self, rng) -> Any:
        return rng.choice(self.options)

    def __len__(self) -> int:
        return len(self.options)


class ParameterSpace:
    """Collection of parameters defining the full search space."""

    def __init__(self, parameters: List[Parameter]):
        self.parameters = parameters
        self._validate()

    def _validate(self):
        names = [p.name for p in self.parameters]
        if len(names) != len(set(names)):
            raise ValueError("Parameter names must be unique.")
        for p in self.parameters:
            if len(p) == 0:
                raise ValueError(f"Parameter '{p.name}' has no values.")

    @property
    def total_combinations(self) -> int:
        result = 1
        for p in self.parameters:
            result *= len(p)
        return result

    def grid_iterator(self) -> Iterator[dict]:
        """Yield every combination in the grid."""
        from itertools import product
        value_lists = [p.values() for p in self.parameters]
        for combo in product(*value_lists):
            yield {p.name: v for p, v in zip(self.parameters, combo)}

    def random_sample(self, rng, n: int) -> List[dict]:
        samples = []
        seen = set()
        max_attempts = n * 20
        attempts = 0
        while len(samples) < n and attempts < max_attempts:
            attempts += 1
            combo = {p.name: p.random_value(rng) for p in self.parameters}
            key = tuple(combo[p.name] for p in self.parameters)
            if key not in seen:
                seen.add(key)
                samples.append(combo)
        return samples

    def decode_individual(self, individual: List[int]) -> dict:
        """Convert a list of indices (genetic algorithm genome) to a param dict."""
        result = {}
        for i, param in enumerate(self.parameters):
            vals = param.values()
            idx = max(0, min(int(individual[i]), len(vals) - 1))
            result[param.name] = vals[idx]
        return result

    def encode_individual(self, params: dict) -> List[int]:
        """Convert a param dict to a list of indices."""
        result = []
        for param in self.parameters:
            vals = param.values()
            v = params[param.name]
            idx = vals.index(v) if v in vals else 0
            result.append(idx)
        return result

    def bounds(self):
        """Return (low, high) index bounds for each parameter (for bayesian search)."""
        return [(0, len(p) - 1) for p in self.parameters]

    def __repr__(self) -> str:
        lines = [f"ParameterSpace ({self.total_combinations:,} combinations):"]
        for p in self.parameters:
            lines.append(f"  {p.name}: {len(p)} values  [{p.values()[0]} … {p.values()[-1]}]")
        return "\n".join(lines)
