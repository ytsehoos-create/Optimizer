"""Load and merge configuration from yaml file and environment variables."""
from __future__ import annotations

import logging
import os
from typing import Any, Dict

import yaml
from dotenv import load_dotenv

log = logging.getLogger(__name__)


def load_config(path: str = "config.yaml") -> Dict[str, Any]:
    load_dotenv()

    with open(path, "r") as f:
        cfg = yaml.safe_load(f) or {}

    # Allow env vars to override credentials
    tv = cfg.setdefault("tradingview", {})
    if os.getenv("TV_USERNAME"):
        tv["username"] = os.getenv("TV_USERNAME")
    if os.getenv("TV_PASSWORD"):
        tv["password"] = os.getenv("TV_PASSWORD")
    if os.getenv("TV_CHART_URL"):
        tv["chart_url"] = os.getenv("TV_CHART_URL")

    return cfg


def setup_logging(cfg: Dict[str, Any]):
    log_cfg = cfg.get("logging", {})
    level = getattr(logging, log_cfg.get("level", "INFO").upper(), logging.INFO)
    log_file = log_cfg.get("log_file", "optimizer.log")

    handlers = [logging.StreamHandler()]
    if log_file:
        handlers.append(logging.FileHandler(log_file))

    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=handlers,
    )
