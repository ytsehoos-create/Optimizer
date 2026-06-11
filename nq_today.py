#!/usr/bin/env python3
"""
NQ Today — Edgeful market-data dashboard for NQ (Nasdaq 100 futures).

Fetches and displays real Edgeful data for NQ using the confirmed API:
  • Gap fill statistics (standard + by weekday + by size)
  • Opening stats (where today's open sits relative to prior high/low)
  • Outside days (bullish/bearish outside day reversals)
  • Previous day's range breakout probabilities
  • Overnight continuation stats
  • ADR / ATR range stats
  • Performance by weekday
  • Live screener snapshot (What's in Play)

Usage:
    python nq_today.py                    # uses EDGEFUL_API_KEY from .env
    python nq_today.py --key ef_live_…    # explicit key
    python nq_today.py --symbol ES        # different symbol
    python nq_today.py --json             # dump raw JSON instead
    python nq_today.py --days 180         # lookback window in days (default 365)
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

load_dotenv()

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


def _hr(char: str = "─"):
    print(dim(char * WIDTH))


def _section(title: str):
    print()
    _hr("═")
    print(bold(cyan(f"  {title}")))
    _hr("─")


def _kv(key: str, value: Any, width: int = 34):
    v = "—" if value is None else str(value)
    print(f"  {dim(key.ljust(width))} {v}")


def _prob_colour(p: Optional[float]):
    try:
        p = float(p)
    except (TypeError, ValueError):
        return dim
    if p >= 70:
        return green
    if p >= 55:
        return yellow
    return red


def _fmt_prob(p) -> str:
    try:
        p = float(p)
    except (TypeError, ValueError):
        return dim("—")
    fn = _prob_colour(p)
    return fn(f"{p:.1f}%")


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

def _show_gap_fill(data: Optional[Dict]):
    _section("Gap Fill")
    if not data or not isinstance(data, dict):
        print(dim("  No gap-fill data."))
        return

    summary = data.get("summary", [])
    rows = []
    for item in summary if isinstance(summary, list) else []:
        cat  = item.get("category", "")
        freq = item.get("frequency", "")
        pct  = item.get("percentage")
        if pct is not None:
            rows.append([cat, _fmt_prob(pct), str(freq)])
    if rows:
        print(tabulate(rows, headers=["Category", "Pct", "n"], tablefmt="simple"))
    else:
        print(dim("  No gap-fill summary rows."))


def _show_gap_fill_weekday(data: Optional[Dict]):
    _section("Gap Fill by Weekday")
    if not data or not isinstance(data, dict):
        print(dim("  No data."))
        return

    summary = data.get("summary", {})
    rows = []
    for day, items in (summary.items() if isinstance(summary, dict) else []):
        for item in (items if isinstance(items, list) else []):
            cat = item.get("category", "")
            if "filled" in cat.lower() and "not" not in cat.lower():
                pct = item.get("percentage")
                freq = item.get("frequency", "")
                rows.append([day, cat, _fmt_prob(pct), str(freq)])
    if rows:
        print(tabulate(rows, headers=["Day", "Category", "Fill %", "n"], tablefmt="simple"))
    else:
        print(dim("  No weekday breakdown available."))


def _show_opening_stats(data: Optional[Dict]):
    _section("Opening Stats (vs Prior High/Low)")
    if not data or not isinstance(data, dict):
        print(dim("  No data."))
        return

    s = data.get("summary", {})
    if not isinstance(s, dict):
        print(dim("  No data."))
        return

    total = s.get("totalDays", 0)
    above = s.get("daysAbovePreviousHigh", 0)
    between = s.get("daysBetweenPreviousHighAndLow", 0)
    below = s.get("daysBelowPreviousLow", 0)

    def pct(n):
        return f"{100*n/total:.1f}%" if total else "—"

    _kv("Total days",               total)
    _kv("Open above prior high",    f"{above}  ({pct(above)})")
    _kv("Open between prior H/L",   f"{between}  ({pct(between)})")
    _kv("Open below prior low",     f"{below}  ({pct(below)})")


def _show_outside_days(data: Optional[Dict]):
    _section("Outside Days")
    if not data or not isinstance(data, dict):
        print(dim("  No data."))
        return

    s = data.get("summary", {})
    if not isinstance(s, dict):
        print(dim("  No data."))
        return

    for key, label in [
        ("outsideDayHigh",          "Bullish outside day"),
        ("outsideDayHighReversal",  "  → reversal down"),
        ("outsideDayHighNoReversal","  → no reversal"),
        ("outsideDayLow",           "Bearish outside day"),
        ("outsideDayLowReversal",   "  → reversal up"),
        ("outsideDayLowNoReversal", "  → no reversal"),
    ]:
        v = s.get(key)
        if not isinstance(v, dict):
            continue
        pct  = v.get("percentage")
        cnt  = v.get("count", "")
        fn   = green if "reversal" in key.lower() and "no" not in key.lower() else dim
        _kv(label, fn(f"{pct}%  (n={cnt})") if pct is not None else "—")


def _show_prev_day_range(data: Optional[Dict]):
    _section("Previous Day's Range Breakout")
    if not data or not isinstance(data, dict):
        print(dim("  No data."))
        return

    s = data.get("summary", {})
    if not isinstance(s, dict):
        print(dim("  No data."))
        return

    for key, label in [
        ("prevDayHigh", "Broke prior high"),
        ("prevDayLow",  "Broke prior low"),
    ]:
        v = s.get(key)
        if not isinstance(v, dict):
            continue
        pct  = v.get("percentage")
        cnt  = v.get("count", "")
        _kv(label, _fmt_prob(pct) + f"  (n={cnt})" if pct is not None else "—")

        sub = v.get("subCategories") or []
        for sub_item in sub if isinstance(sub, list) else []:
            sub_cat = sub_item.get("category", "")
            sub_pct = sub_item.get("percentage")
            sub_cnt = sub_item.get("count", "")
            fn = green if "green" in sub_cat.lower() else (red if "red" in sub_cat.lower() else dim)
            _kv(f"    {sub_cat}", fn(f"{sub_pct}%  (n={sub_cnt})") if sub_pct is not None else "—")


def _show_overnight_continuation(data: Optional[Dict]):
    _section("Overnight Continuation")
    if not data or not isinstance(data, dict):
        print(dim("  No data."))
        return

    s = data.get("summary", {})
    if not isinstance(s, dict):
        print(dim("  No data."))
        return

    for key, label in [
        ("greenOvernightGreenDay", "Gap up  → closed green"),
        ("greenOvernightRedDay",   "Gap up  → closed red"),
        ("redOvernightGreenDay",   "Gap down → closed green"),
        ("redOvernightRedDay",     "Gap down → closed red"),
    ]:
        v = s.get(key)
        if not isinstance(v, dict):
            continue
        pct = v.get("percentage")
        cnt = v.get("count", "")
        is_continuation = ("greenOvernight" in key and "Green" in key) or \
                          ("redOvernight"   in key and "Red"   in key)
        fn = green if is_continuation else red
        _kv(label, fn(f"{pct}%  (n={cnt})") if pct is not None else "—")


def _show_adr(data: Optional[Dict]):
    _section("ADR (Average Daily Range)")
    if not data or not isinstance(data, dict):
        print(dim("  No data."))
        return

    s = data.get("summary", {})
    if not isinstance(s, dict):
        print(dim("  No data."))
        return

    adr = data.get("currentADR") or s.get("currentADR")
    if adr is not None:
        _kv("Current ADR", bold(f"{adr:,.2f}"))

    for key, label in [
        ("exceeded", "Range exceeded ADR"),
        ("respected", "Range respected ADR"),
    ]:
        v = s.get(key)
        if not isinstance(v, dict):
            continue
        pct = v.get("percentage")
        cnt = v.get("frequency", v.get("count", ""))
        fn = green if key == "exceeded" else dim
        pct_str = f"{float(pct):.1f}%" if pct is not None else "—"
        _kv(f"  {label}", fn(f"{pct_str}  (n={cnt})"))


def _show_performance_by_weekday(data: Optional[Dict]):
    _section("Performance by Weekday")
    if not data or not isinstance(data, dict):
        print(dim("  No data."))
        return

    s = data.get("summary", {})
    if not isinstance(s, dict):
        print(dim("  No data."))
        return

    rows = []
    for day in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]:
        v = s.get(day)
        if not isinstance(v, dict):
            continue
        avg_ret  = v.get("averageReturn") or v.get("avgReturn") or v.get("performance")
        green_n  = v.get("greenDays") or v.get("green", "")
        red_n    = v.get("redDays")   or v.get("red",   "")
        total_n  = (green_n or 0) + (red_n or 0) if isinstance(green_n, int) else ""
        green_pct = f"{100*green_n/total_n:.0f}%" if isinstance(green_n, int) and total_n else "—"
        ret_str  = (green if avg_ret and avg_ret > 0 else red)(f"{avg_ret:+.3f}%") if avg_ret is not None else "—"
        rows.append([day[:3], ret_str, green_pct, str(total_n)])
    if rows:
        print(tabulate(rows, headers=["Day", "Avg ret", "Green%", "n"], tablefmt="simple"))
    else:
        print(dim("  No weekday performance data."))


def _show_screener(screener_data: Optional[Dict], symbol: str):
    _section(f"Screener Snapshot — {symbol}")
    if not screener_data or not isinstance(screener_data, dict):
        print(dim("  No screener data available."))
        return

    sym_data = screener_data.get(symbol) or screener_data.get(symbol.upper())
    if not sym_data or not isinstance(sym_data, dict):
        print(dim(f"  No screener data for {symbol}."))
        return

    rows = []
    for report_slug, report_data in sym_data.items():
        if not isinstance(report_data, dict):
            continue
        # Pull the most informative summary fields available
        s = report_data.get("summary") or report_data
        if isinstance(s, list) and s:
            for item in s:
                if isinstance(item, dict):
                    cat = item.get("category", report_slug)
                    pct = item.get("percentage")
                    n   = item.get("frequency", "")
                    if pct is not None:
                        rows.append([report_slug[:38], cat[:28], _fmt_prob(pct), str(n)])
            continue
        if isinstance(s, dict):
            for k, v in list(s.items())[:3]:
                if isinstance(v, dict):
                    pct = v.get("percentage")
                    cnt = v.get("frequency", v.get("count", ""))
                    if pct is not None:
                        rows.append([report_slug[:38], k[:28], _fmt_prob(pct), str(cnt)])

    if rows:
        print(tabulate(rows, headers=["Report", "Category", "Pct", "n"], tablefmt="simple"))
    else:
        print(dim(f"  Screener data present but no summary rows extracted."))
        print(dim(f"  Reports available: {', '.join(list(sym_data.keys())[:5])}"))


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Fetch and display Edgeful market data for a futures symbol."
    )
    parser.add_argument("--key",    default=os.getenv("EDGEFUL_API_KEY", ""),
                        help="Edgeful API key (default: EDGEFUL_API_KEY env var)")
    parser.add_argument("--symbol", default="NQ",
                        help="Futures symbol to query (default: NQ)")
    parser.add_argument("--days",   type=int, default=365,
                        help="Lookback window in days (default: 365, max 365 on Pro plan)")
    parser.add_argument("--json",   action="store_true",
                        help="Dump raw JSON from all endpoints")
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

    end_date   = date.today().isoformat()
    start_date = (date.today() - timedelta(days=args.days)).isoformat()

    def fetch(slug: str, **kw) -> Optional[Dict]:
        return _safe(client.get_report, slug, "futures", symbol,
                     start_date, end_date, default=None, **kw)

    gap_fill     = fetch("gap-fill-standard")
    gap_weekday  = fetch("gap-fill-by-weekday")
    opening_stats = fetch("opening-stats-standard")
    outside_days  = fetch("outside-days-standard")
    prev_day      = fetch("previous-days-range-standard")
    overnight     = fetch("overnight-continuation-standard")
    adr           = fetch("adr-average-daily-range-standard")
    perf_weekday  = fetch("performance-by-weekday-standard")
    screener      = _safe(client.get_screener, "futures", tickers=[symbol], default=None)

    if args.json:
        print(json.dumps({
            "symbol":           symbol,
            "start_date":       start_date,
            "end_date":         end_date,
            "timestamp":        datetime.now().isoformat(),
            "gap_fill":         gap_fill,
            "gap_fill_weekday": gap_weekday,
            "opening_stats":    opening_stats,
            "outside_days":     outside_days,
            "prev_day_range":   prev_day,
            "overnight":        overnight,
            "adr":              adr,
            "perf_weekday":     perf_weekday,
            "screener":         screener,
        }, indent=2, default=str))
        return

    _banner(symbol)
    _show_gap_fill(gap_fill)
    _show_gap_fill_weekday(gap_weekday)
    _show_opening_stats(opening_stats)
    _show_outside_days(outside_days)
    _show_prev_day_range(prev_day)
    _show_overnight_continuation(overnight)
    _show_adr(adr)
    _show_performance_by_weekday(perf_weekday)
    _show_screener(screener, symbol)

    print()
    _hr("═")
    print(dim(f"  Fetched at {datetime.now().strftime('%H:%M:%S')}  ·  {symbol}  ·  {start_date} → {end_date}"))
    _hr("═")
    print()


if __name__ == "__main__":
    main()
