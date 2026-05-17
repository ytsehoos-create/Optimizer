"""Genetic algorithm optimizer using DEAP."""
from __future__ import annotations

import logging
import random
from typing import Any, Callable, Dict

from tqdm import tqdm

from ..parameter_space import ParameterSpace
from ..results import OptimizationResult, ResultsCollection
from .base import BaseOptimizer

log = logging.getLogger(__name__)


class GeneticOptimizer(BaseOptimizer):

    def run(self, objective: Callable[[Dict[str, Any]], Any]) -> ResultsCollection:
        try:
            from deap import base, creator, tools, algorithms
        except ImportError:
            raise ImportError("Install 'deap' to use the genetic algorithm: pip install deap")

        cfg = self.config.get("genetic", {})
        pop_size = cfg.get("population_size", 30)
        n_gen = cfg.get("generations", 20)
        cx_pb = cfg.get("crossover_prob", 0.7)
        mut_pb = cfg.get("mutation_prob", 0.2)
        tourn_size = cfg.get("tournament_size", 3)
        elite_size = cfg.get("elite_size", 2)
        seed = cfg.get("seed", 42)

        random.seed(seed)

        n_params = len(self.space.parameters)
        bounds = self.space.bounds()

        # DEAP setup — guard against re-registration across multiple runs
        if not hasattr(creator, "FitnessMax"):
            creator.create("FitnessMax", base.Fitness, weights=(1.0,))
        if not hasattr(creator, "Individual"):
            creator.create("Individual", list, fitness=creator.FitnessMax)

        toolbox = base.Toolbox()

        def rand_attr(i: int):
            lo, hi = bounds[i]
            return random.randint(lo, hi)

        toolbox.register("individual", tools.initCycle, creator.Individual,
                         [lambda i=i: rand_attr(i) for i in range(n_params)],
                         n=1)
        toolbox.register("population", tools.initRepeat, list, toolbox.individual)
        toolbox.register("select", tools.selTournament, tournsize=tourn_size)
        toolbox.register("mate", tools.cxUniform, indpb=0.5)

        def mutate(individual):
            for i in range(len(individual)):
                if random.random() < (1.0 / n_params):
                    lo, hi = bounds[i]
                    individual[i] = random.randint(lo, hi)
            return (individual,)

        toolbox.register("mutate", mutate)

        results = ResultsCollection()
        eval_cache: Dict[tuple, float] = {}

        def evaluate(individual):
            key = tuple(int(x) for x in individual)
            if key in eval_cache:
                return (eval_cache[key],)
            params = self.space.decode_individual(list(individual))
            result = objective(params)
            results.add(result)
            eval_cache[key] = result.score
            return (result.score,)

        toolbox.register("evaluate", evaluate)

        population = toolbox.population(n=pop_size)
        total_evals = pop_size + (pop_size - elite_size) * n_gen
        pbar = tqdm(total=total_evals, desc="Genetic Search", unit="eval")

        # Evaluate initial population
        for ind in population:
            ind.fitness.values = toolbox.evaluate(ind)
            pbar.update(1)

        for gen in range(n_gen):
            # Elitism: keep top individuals unchanged
            elite = tools.selBest(population, elite_size)
            elite = [toolbox.clone(e) for e in elite]

            offspring = toolbox.select(population, len(population) - elite_size)
            offspring = [toolbox.clone(o) for o in offspring]

            for child1, child2 in zip(offspring[::2], offspring[1::2]):
                if random.random() < cx_pb:
                    toolbox.mate(child1, child2)
                    del child1.fitness.values
                    del child2.fitness.values

            for mutant in offspring:
                if random.random() < mut_pb:
                    toolbox.mutate(mutant)
                    del mutant.fitness.values

            for ind in offspring:
                if not ind.fitness.valid:
                    ind.fitness.values = toolbox.evaluate(ind)
                    pbar.update(1)

            population[:] = elite + offspring

            best = tools.selBest(population, 1)[0]
            log.info("Gen %d/%d — best score: %.4f", gen + 1, n_gen, best.fitness.values[0])

        pbar.close()
        return results
