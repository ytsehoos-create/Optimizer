#!/usr/bin/env python3
"""
PineScript Strategy Optimizer — entry point.

Usage:
    python main.py --strategy examples/macd_strategy.py
    python main.py --strategy examples/rsi_bb_strategy.py --algorithm genetic
    python main.py --strategy examples/macd_strategy.py --algorithm random --trials 50
    python main.py --dry-run   # validate setup without TradingView
"""
import argparse
import importlib.util
import logging
import sys

from optimizer.config import load_config, setup_logging

log = logging.getLogger(__name__)


def load_strategy_module(path: str):
    spec = importlib.util.spec_from_file_location("strategy", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    parser = argparse.ArgumentParser(
        description="TradingView PineScript Strategy Optimizer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--strategy", "-s",
        required=False,
        help="Path to strategy definition file (e.g. examples/macd_strategy.py)",
    )
    parser.add_argument(
        "--config", "-c",
        default="config.yaml",
        help="Path to config YAML (default: config.yaml)",
    )
    parser.add_argument(
        "--algorithm", "-a",
        choices=["grid", "random", "genetic", "bayesian"],
        help="Override optimization algorithm",
    )
    parser.add_argument(
        "--metric", "-m",
        help="Override optimization metric (e.g. net_profit, sharpe_ratio)",
    )
    parser.add_argument(
        "--trials", "-n",
        type=int,
        help="Override number of random search trials",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run browser in headless mode",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate config and parameter space without running TradingView",
    )
    parser.add_argument(
        "--output", "-o",
        help="Override report output directory",
    )

    args = parser.parse_args()

    cfg = load_config(args.config)
    setup_logging(cfg)

    # Apply CLI overrides
    if args.algorithm:
        cfg["optimization"]["algorithm"] = args.algorithm
    if args.metric:
        cfg["optimization"]["metric"] = args.metric
    if args.trials:
        cfg["optimization"].setdefault("random_search", {})["n_trials"] = args.trials
    if args.headless:
        cfg["tradingview"]["headless"] = True
    if args.output:
        cfg["reporting"]["output_dir"] = args.output

    # Load strategy definition
    strategy_path = args.strategy
    if not strategy_path:
        # Default to MACD example if no strategy specified
        strategy_path = "examples/macd_strategy.py"
        log.info("No strategy specified — using %s", strategy_path)

    mod = load_strategy_module(strategy_path)
    space = mod.PARAMETER_SPACE

    if args.dry_run:
        from colorama import Fore, Style, init
        init(autoreset=True)
        print(f"\n{Fore.CYAN}Dry-run mode — TradingView will NOT be launched.{Style.RESET_ALL}")
        print(f"\n{space}")
        print(f"\nAlgorithm : {cfg['optimization']['algorithm']}")
        print(f"Metric    : {cfg['optimization']['metric']}")
        print(f"Max?      : {cfg['optimization']['maximize']}")
        return 0

    from optimizer import StrategyOptimizer
    optimizer = StrategyOptimizer(space=space, config=cfg)

    log.info("Starting optimization with strategy: %s", strategy_path)
    results = optimizer.run()
    optimizer.report(results)

    best = results.best()
    if best:
        log.info("Optimization complete. Best score: %.4f | Params: %s", best.score, best.params)
    else:
        log.warning("Optimization complete but no successful trials found.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
