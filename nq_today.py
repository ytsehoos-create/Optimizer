#!/usr/bin/env python3
"""
NQ Today — Edgeful market-data dashboard for NQ (Nasdaq 100 futures).

Fetches and displays every available Edgeful data point for NQ:
  • Gap fill probability (today's gap direction, size, day-of-week breakdown)
  • Opening Range Breakout statistics (5 / 15 / 30 / 60-min)
  • Initial Balance levels and extension probabilities
  • Previous-day / overnight key levels
  • Live "What's in Play?" setups
  • All NQ probability reports (sorted by probability)
  • Account / subscription info

Usage:
    python nq_today.py                    # uses EDGEFUL_API_KEY from .env
    python nq_today.py --key ef_live_…    # explicit key
    python nq_today.py --symbol ES        # different symbol
    python nq_today.py --json             # dump raw JSON instead
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

load_dotenv()

# ── colour helpers ────────────────────────────────────────────────────────────
try:
    from colorama import Fore, Style, init as _cinit
    _cinit(autoreset=True)
    def green(s):  return Fore.GREEN  + str(s) + Style.RESET_ALL
    def red(s):    return Fore.RED    + str(s) + Style.RESET_ALL
    def yellow(s): return Fore.YELLOW + str(s) + Style.RESET_ALL
    def cyan(s):   return Fore.CYAN   + str(s) + Style.RESET_ALL
    def bold(s):   return Style.BRIGHT + str(s) + Style.RESET_ALL
    def dim(s):    return Style.DIM   + str(s) + Style.RESET_ALL
except ImportError:
    def green(s):  return str(s)
    def red(s):    return str(s)
    def yellow(s): return str(s)
    def cyan(s):   return str(s)
    def bold(s):   return str(s)
    def dim(s):    return str(s)

try:
    from tabulate import tabulate
except ImportError:
    def tabulate(rows, headers=(), tablefmt=""):  # type: ignore[override]
        lines = ["  ".join(str(h) for h in headers)]
        lines += ["  ".join(str(c) for c in r) for r in rows]
        return "\n".join(lines)

WIDTH = 72


# ── formatting helpers ────────────────────────────────────────────────────────

def _hr(char: str = "─"):
    print(dim(char * WIDTH))


def _section(title: str):
    print()
    _hr("═")
    print(bold(cyan(f"  {title}")))
    _hr("─")


def _kv(key: str, value: Any, width: int = 32):
    v = "—" if value is None else str(value)
    print(f"  {dim(key.ljust(width))} {v}")


def _prob_colour(p: Optional[float]):
    if p is None:
        return dim
    if p >= 70:
        return green
    if p >= 55:
        return yellow
    return red


def _fmt_prob(p: Optional[float]) -> str:
    if p is None:
        return dim("—")
    return _prob_colour(p)(f"{p:.1f}%")


def _fmt_price(p: Optional[float]) -> str:
    if p is None:
        return "—"
    return f"{p:,.2f}"


def _safe(fn, *args, default=None, **kwargs):
    try:
        return fn(*args, **kwargs)
    except Exception as exc:
        logging.debug("%s: %s", getattr(fn, "__name__", fn), exc)
        return default


# ── banner ────────────────────────────────────────────────────────────────────

def _banner(symbol: str):
    now = datetime.now()
    print()
    _hr("═")
    print(bold(cyan(f"  {symbol} TODAY  ·  {now.strftime('%A, %B %-d %Y')}  ·  {now.strftime('%H:%M:%S')}")))
    print(dim("  Powered by Edgeful  ·  edgeful.com"))
    _hr("═")


# ── section renderers ─────────────────────────────────────────────────────────

def _show_account(client):
    data = _safe(client.get_account_info, default={})
    if not data:
        return
    _section("Account")
    for k, v in data.items():
        _kv(k, v)


def _show_gap_fill(client, symbol: str):
    _section("Gap Fill Probability")
    data = _safe(client.get_gap_fill_probability, symbol, default={})
    if not isinstance(data, dict) or not data:
        print(dim("  No gap-fill data available."))
        return

    gap_dir  = data.get("gap_direction", "—")
    gap_size = data.get("gap_size_pct")
    prob     = data.get("probability")
    hist     = data.get("historical_fill_rate")
    fill_min = data.get("avg_fill_time_min")
    as_of    = data.get("as_of", "—")

    dir_fn = green if str(gap_dir).lower() == "up" else red
    _kv("Gap direction",            dir_fn(gap_dir))
    _kv("Gap size",                 f"{gap_size:.2f}%" if gap_size else "—")
    _kv("Fill probability (today)", _fmt_prob(prob))
    _kv("Historical fill rate",     _fmt_prob(hist))
    _kv("Avg fill time",            f"{fill_min:.0f} min" if fill_min else "—")
    _kv("As of",                    dim(str(as_of)))

    # Day-of-week breakdown
    dow = data.get("day_of_week_stats") or data.get("by_weekday") or {}
    if isinstance(dow, dict) and dow:
        print()
        print(f"  {dim('Day-of-week fill rates:')}")
        rows = []
        for day, stats in dow.items():
            if isinstance(stats, dict):
                p = stats.get("fill_rate") or stats.get("probability")
                n = stats.get("sample_size") or stats.get("count", "")
            else:
                p, n = stats, ""
            rows.append([day, _fmt_prob(p), str(n)])
        print(tabulate(rows, headers=["Day", "Fill %", "n"], tablefmt="simple"))

    # Size-bucket breakdown
    buckets = data.get("by_size") or data.get("size_buckets") or {}
    if isinstance(buckets, dict) and buckets:
        print()
        print(f"  {dim('Fill rate by gap size:')}")
        rows = []
        for rng, v in buckets.items():
            p = v if isinstance(v, float) else (v.get("fill_rate") if isinstance(v, dict) else None)
            rows.append([rng, _fmt_prob(p)])
        print(tabulate(rows, headers=["Gap range", "Fill %"], tablefmt="simple"))


def _show_orb(client, symbol: str):
    _section("Opening Range Breakout (ORB)")
    rows = []
    for minutes in (5, 15, 30, 60):
        data = _safe(client.get_orb_statistics, symbol, minutes, default={})
        if not isinstance(data, dict):
            continue
        p_up   = data.get("breakout_up_probability")  or data.get("break_up_prob")
        p_dn   = data.get("breakout_down_probability") or data.get("break_down_prob")
        ext    = data.get("avg_extension_atr")         or data.get("avg_extension")
        false_ = data.get("false_breakout_rate")       or data.get("false_break_pct")
        best   = data.get("best_time_window", "")
        rows.append([
            f"{minutes}-min",
            _fmt_prob(p_up),
            _fmt_prob(p_dn),
            f"{ext:.2f} ATR" if ext else "—",
            _fmt_prob(false_) if false_ is not None else "—",
            dim(str(best)),
        ])
    if rows:
        print(tabulate(rows,
                       headers=["Period", "Break Up", "Break Down", "Avg Ext", "False Break", "Best Window"],
                       tablefmt="simple"))
    else:
        print(dim("  No ORB data available."))


def _show_initial_balance(client, symbol: str):
    _section("Initial Balance")
    data = _safe(client.get_initial_balance, symbol, default={})
    if not isinstance(data, dict) or not data:
        print(dim("  No initial balance data available."))
        return

    _kv("IB High",           bold(green(_fmt_price(data.get("ib_high")))))
    _kv("IB Low",            bold(red(_fmt_price(data.get("ib_low")))))
    _kv("IB Range",          f"{data['ib_range']:,.2f}" if data.get("ib_range") else "—")
    _kv("Value Area High",   _fmt_price(data.get("value_area_high") or data.get("vah")))
    _kv("Value Area Low",    _fmt_price(data.get("value_area_low")  or data.get("val")))
    _kv("Point of Control",  _fmt_price(data.get("point_of_control") or data.get("poc")))

    # Extension probabilities
    ext_rows = []
    for key in ("extension_0.5x", "extension_1x", "extension_1.5x",
                "extension_2x",   "extension_3x"):
        v = data.get(key) or data.get(key.replace(".", "_"))
        if v is None:
            continue
        if isinstance(v, dict):
            prob  = v.get("probability") or v.get("prob")
            reach = v.get("avg_reach")   or v.get("avg_ticks", "")
            n     = v.get("sample_size") or v.get("count", "")
        else:
            prob, reach, n = v, "", ""
        ext_rows.append([
            key.replace("extension_", "") + " IB",
            _fmt_prob(prob),
            f"{reach:.1f}" if isinstance(reach, float) else str(reach),
            str(n),
        ])
    if ext_rows:
        print()
        print(f"  {dim('IB extension probabilities:')}")
        print(tabulate(ext_rows, headers=["Extension", "Prob", "Avg Reach", "n"],
                       tablefmt="simple"))

    for side in ("single_break_up", "single_break_down",
                 "ib_break_up_prob", "ib_break_down_prob"):
        v = data.get(side)
        if v is not None:
            _kv(side.replace("_", " ").title(), _fmt_prob(v if isinstance(v, float) else None))


def _show_prev_day_levels(client, symbol: str):
    _section("Previous Day & Overnight Levels")
    data = _safe(client.get_previous_day_levels, symbol, default={})
    if not isinstance(data, dict) or not data:
        print(dim("  No previous-day level data available."))
        return

    _kv("Prev Day High",   bold(green(_fmt_price(data.get("pdh") or data.get("prev_day_high")))))
    _kv("Prev Day Low",    bold(red(_fmt_price(data.get("pdl")  or data.get("prev_day_low")))))
    _kv("Prev Day Close",  _fmt_price(data.get("pdc") or data.get("prev_day_close")))
    _kv("Overnight High",  _fmt_price(data.get("overnight_high") or data.get("on_high")))
    _kv("Overnight Low",   _fmt_price(data.get("overnight_low")  or data.get("on_low")))

    for key, label in [
        ("pdh_reaction_prob", "PDH reaction prob"),
        ("pdl_reaction_prob", "PDL reaction prob"),
        ("weekly_high",       "Weekly High"),
        ("weekly_low",        "Weekly Low"),
        ("monthly_high",      "Monthly High"),
        ("monthly_low",       "Monthly Low"),
        ("vwap",              "VWAP"),
    ]:
        v = data.get(key)
        if v is None:
            continue
        if "prob" in key:
            _kv(label, _fmt_prob(v if isinstance(v, float) else None))
        else:
            _kv(label, _fmt_price(v) if isinstance(v, float) else str(v))


def _show_live_setups(client, symbol: str):
    _section("Live Setups — What's in Play?")
    all_setups = _safe(client.get_live_setups, default=[]) or []
    nq_setups  = [s for s in all_setups
                  if isinstance(s, dict) and
                  (s.get("symbol", "").upper() == symbol or not s.get("symbol"))]

    if not nq_setups:
        print(dim(f"  No active {symbol} live setups at this time."))
        return

    for i, s in enumerate(nq_setups, 1):
        prob      = s.get("probability")
        rname     = s.get("report_name") or s.get("setup_type") or "Setup"
        direction = s.get("direction", "")
        entry     = s.get("entry_zone") or s.get("entry")
        target    = s.get("target")
        stop      = s.get("stop")
        ts        = s.get("timestamp") or s.get("as_of") or ""

        fn     = _prob_colour(prob)
        dir_fn = green if str(direction).lower() in ("long", "buy", "up") else red

        prob_str = fn(f"{prob:.1f}%") if prob is not None else ""
        dir_str  = dir_fn(direction.upper()) if direction else ""
        print(f"\n  {bold(f'#{i}  {rname}')}  —  {prob_str}  {dir_str}")
        if entry:
            print(f"       Entry   {_fmt_price(entry) if isinstance(entry, float) else entry}")
        if target:
            print(f"       Target  {bold(green(_fmt_price(target) if isinstance(target, float) else target))}")
        if stop:
            print(f"       Stop    {bold(red(_fmt_price(stop) if isinstance(stop, float) else stop))}")
        if ts:
            print(f"       {dim(str(ts))}")


def _show_market_summary(client):
    _section("Market Summary")
    data = _safe(client.get_live_summary, default={})
    if not isinstance(data, dict) or not data:
        print(dim("  No summary data available."))
        return
    for k, v in data.items():
        _kv(k, v)


def _show_reports(client, symbol: str):
    _section(f"{symbol} Probability Reports")

    reports = _safe(client.list_reports, symbol=symbol, default=[]) or []
    if not reports:
        # fallback: fetch all and filter
        reports = [
            r for r in (_safe(client.list_reports, default=[]) or [])
            if isinstance(r, dict) and symbol in str(r.get("symbol") or r.get("symbols") or "")
        ]

    if not reports:
        print(dim(f"  No {symbol} reports found."))
        return

    def sort_key(r: dict) -> float:
        stats = r.get("statistics") or {}
        return -(stats.get("probability") or stats.get("win_rate") or 0)

    reports.sort(key=sort_key)

    rows = []
    for r in reports:
        stats = r.get("statistics") or {}
        prob  = stats.get("probability") or stats.get("win_rate")
        n     = stats.get("sample_size") or stats.get("count") or r.get("sample_size", "")
        name  = r.get("name") or r.get("report_name") or r.get("id") or "—"
        cat   = r.get("category") or r.get("type") or ""
        rows.append([name[:48], _fmt_prob(prob), str(n) if n else "—", dim(str(cat))])

    print(tabulate(rows, headers=["Report", "Win %", "n", "Category"], tablefmt="simple"))


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Fetch and display all Edgeful market data for NQ today."
    )
    parser.add_argument("--key",    default=os.getenv("EDGEFUL_API_KEY", ""),
                        help="Edgeful API key (default: EDGEFUL_API_KEY env var)")
    parser.add_argument("--symbol", default="NQ",
                        help="Symbol to query (default: NQ)")
    parser.add_argument("--json",   action="store_true",
                        help="Dump raw JSON from all endpoints instead of formatted output")
    parser.add_argument("--debug",  action="store_true",
                        help="Enable debug logging")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )

    symbol  = args.symbol.upper()
    api_key = args.key.strip()

    if not api_key:
        print(red("Error: Edgeful API key not set."))
        print("  Set EDGEFUL_API_KEY in your .env file, or pass --key ef_live_…")
        sys.exit(1)

    try:
        from optimizer.edgeful import EdgefulClient
    except ImportError:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from optimizer.edgeful import EdgefulClient

    client = EdgefulClient(api_key=api_key)

    if args.json:
        payload = {
            "symbol":          symbol,
            "timestamp":       datetime.now().isoformat(),
            "account":         _safe(client.get_account_info,         default=None),
            "gap_fill":        _safe(client.get_gap_fill_probability, symbol, default=None),
            "orb_5m":          _safe(client.get_orb_statistics,       symbol, 5,  default=None),
            "orb_15m":         _safe(client.get_orb_statistics,       symbol, 15, default=None),
            "orb_30m":         _safe(client.get_orb_statistics,       symbol, 30, default=None),
            "orb_60m":         _safe(client.get_orb_statistics,       symbol, 60, default=None),
            "initial_balance": _safe(client.get_initial_balance,      symbol, default=None),
            "prev_day_levels": _safe(client.get_previous_day_levels,  symbol, default=None),
            "live_setups":     _safe(client.get_live_setups,          default=None),
            "market_summary":  _safe(client.get_live_summary,         default=None),
            "reports":         _safe(client.list_reports, symbol=symbol, default=None),
        }
        print(json.dumps(payload, indent=2, default=str))
        return

    _banner(symbol)
    _show_account(client)
    _show_gap_fill(client, symbol)
    _show_orb(client, symbol)
    _show_initial_balance(client, symbol)
    _show_prev_day_levels(client, symbol)
    _show_live_setups(client, symbol)
    _show_market_summary(client)
    _show_reports(client, symbol)

    print()
    _hr("═")
    print(dim(f"  Fetched at {datetime.now().strftime('%H:%M:%S')}  ·  Symbol: {symbol}  ·  edgeful.com"))
    _hr("═")
    print()


if __name__ == "__main__":
    main()
