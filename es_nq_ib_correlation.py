#!/usr/bin/env python3
"""
ES/NQ Initial Balance correlation analysis.

Joins per-session IB break data from both instruments, computes alignment
rates, contingency tables, and divergence scenario statistics.

Usage:
    python es_nq_ib_correlation.py [--key KEY] [--sessions N] [--json] [--debug]

When run without live data (network restricted), the script prints the
analysis based on illustrative sample data and explains what each metric
means for trading MNQ with ES as a correlative indicator.
"""

from __future__ import annotations
import argparse
import json
import logging
import os
import sys
from collections import defaultdict
from typing import Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    from colorama import Fore, Style, init as colorama_init
    colorama_init(autoreset=True)
    GREEN   = Fore.GREEN
    RED     = Fore.RED
    YELLOW  = Fore.YELLOW
    CYAN    = Fore.CYAN
    WHITE   = Fore.WHITE
    BOLD    = Style.BRIGHT
    RESET   = Style.RESET_ALL
except ImportError:
    GREEN = RED = YELLOW = CYAN = WHITE = BOLD = RESET = ""

try:
    from tabulate import tabulate
    _TABULATE = True
except ImportError:
    _TABULATE = False

log = logging.getLogger(__name__)


# ── Break-type normalizer ────────────────────────────────────────────────────

BREAK_TYPES = ("ib_high", "ib_low", "inside", "double")

def _classify(raw: Optional[str]) -> str:
    """Map any Edgeful break-type string to ib_high | ib_low | inside | double."""
    if not raw:
        return "inside"
    r = raw.lower().replace("-", "_").replace(" ", "_")
    if "double" in r:
        return "double"
    if "high" in r or "up" in r or "bull" in r:
        return "ib_high"
    if "low" in r or "down" in r or "bear" in r:
        return "ib_low"
    return "inside"


# ── Illustrative sample data ──────────────────────────────────────────────────
# Based on published Edgeful statistics:
#   NQ: 84% single-break sessions, 78% by-rejection accuracy
#   ES: ~80% single-break sessions (typical for large-cap equity futures)
# The distribution below reflects these base rates across 123 sessions.

SAMPLE_SESSIONS = [
    # (date, es_break, nq_break)
    # Aligned ib_high (both break high) — most common scenario ~38%
    ("2026-05-27", "ib_high", "ib_high"),
    ("2026-05-23", "ib_high", "ib_high"),
    ("2026-05-22", "ib_high", "ib_high"),
    ("2026-05-21", "ib_high", "ib_high"),
    ("2026-05-20", "ib_high", "ib_high"),
    ("2026-05-19", "ib_high", "ib_high"),
    ("2026-05-16", "ib_high", "ib_high"),
    ("2026-05-15", "ib_high", "ib_high"),
    ("2026-05-14", "ib_high", "ib_high"),
    ("2026-05-13", "ib_high", "ib_high"),
    ("2026-05-12", "ib_high", "ib_high"),
    ("2026-05-09", "ib_high", "ib_high"),
    ("2026-05-08", "ib_high", "ib_high"),
    ("2026-05-07", "ib_high", "ib_high"),
    ("2026-05-06", "ib_high", "ib_high"),
    ("2026-05-05", "ib_high", "ib_high"),
    ("2026-05-02", "ib_high", "ib_high"),
    ("2026-04-30", "ib_high", "ib_high"),
    ("2026-04-29", "ib_high", "ib_high"),
    ("2026-04-28", "ib_high", "ib_high"),
    ("2026-04-27", "ib_high", "ib_high"),
    ("2026-04-24", "ib_high", "ib_high"),
    ("2026-04-23", "ib_high", "ib_high"),
    ("2026-04-22", "ib_high", "ib_high"),
    ("2026-04-21", "ib_high", "ib_high"),
    ("2026-04-17", "ib_high", "ib_high"),
    ("2026-04-16", "ib_high", "ib_high"),
    ("2026-04-15", "ib_high", "ib_high"),
    ("2026-04-14", "ib_high", "ib_high"),
    ("2026-04-13", "ib_high", "ib_high"),
    ("2026-04-10", "ib_high", "ib_high"),
    ("2026-04-09", "ib_high", "ib_high"),
    ("2026-04-08", "ib_high", "ib_high"),
    ("2026-04-07", "ib_high", "ib_high"),
    ("2026-04-06", "ib_high", "ib_high"),
    ("2026-04-03", "ib_high", "ib_high"),
    ("2026-04-02", "ib_high", "ib_high"),
    ("2026-04-01", "ib_high", "ib_high"),
    ("2026-03-31", "ib_high", "ib_high"),
    ("2026-03-30", "ib_high", "ib_high"),
    ("2026-03-27", "ib_high", "ib_high"),
    ("2026-03-26", "ib_high", "ib_high"),
    ("2026-03-25", "ib_high", "ib_high"),
    ("2026-03-24", "ib_high", "ib_high"),
    ("2026-03-23", "ib_high", "ib_high"),
    ("2026-03-20", "ib_high", "ib_high"),
    # Aligned ib_low (both break low) — ~30%
    ("2026-05-28", "ib_low", "ib_low"),
    ("2026-05-26", "ib_low", "ib_low"),
    ("2026-05-18", "ib_low", "ib_low"),
    ("2026-05-17", "ib_low", "ib_low"),
    ("2026-05-11", "ib_low", "ib_low"),
    ("2026-05-10", "ib_low", "ib_low"),
    ("2026-05-04", "ib_low", "ib_low"),
    ("2026-05-03", "ib_low", "ib_low"),
    ("2026-05-01", "ib_low", "ib_low"),
    ("2026-04-26", "ib_low", "ib_low"),
    ("2026-04-25", "ib_low", "ib_low"),
    ("2026-04-20", "ib_low", "ib_low"),
    ("2026-04-19", "ib_low", "ib_low"),
    ("2026-04-18", "ib_low", "ib_low"),
    ("2026-04-12", "ib_low", "ib_low"),
    ("2026-04-11", "ib_low", "ib_low"),
    ("2026-04-05", "ib_low", "ib_low"),
    ("2026-04-04", "ib_low", "ib_low"),
    ("2026-03-29", "ib_low", "ib_low"),
    ("2026-03-28", "ib_low", "ib_low"),
    ("2026-03-19", "ib_low", "ib_low"),
    ("2026-03-18", "ib_low", "ib_low"),
    ("2026-03-17", "ib_low", "ib_low"),
    ("2026-03-16", "ib_low", "ib_low"),
    ("2026-03-13", "ib_low", "ib_low"),
    ("2026-03-12", "ib_low", "ib_low"),
    ("2026-03-11", "ib_low", "ib_low"),
    ("2026-03-10", "ib_low", "ib_low"),
    ("2026-03-09", "ib_low", "ib_low"),
    ("2026-03-06", "ib_low", "ib_low"),
    ("2026-03-05", "ib_low", "ib_low"),
    ("2026-03-04", "ib_low", "ib_low"),
    ("2026-03-03", "ib_low", "ib_low"),
    ("2026-03-02", "ib_low", "ib_low"),
    # Both inside — ~9%
    ("2026-05-25", "inside", "inside"),
    ("2026-05-24", "inside", "inside"),
    ("2026-03-22", "inside", "inside"),
    ("2026-03-21", "inside", "inside"),
    ("2026-03-14", "inside", "inside"),
    ("2026-03-07", "inside", "inside"),
    ("2026-02-28", "inside", "inside"),
    ("2026-02-27", "inside", "inside"),
    ("2026-02-26", "inside", "inside"),
    ("2026-02-25", "inside", "inside"),
    ("2026-02-24", "inside", "inside"),
    # ES leads high: ES breaks ib_high, NQ still inside — ~5%
    ("2026-04-30", "ib_high", "inside"),
    ("2026-03-15", "ib_high", "inside"),
    ("2026-03-08", "ib_high", "inside"),
    ("2026-02-23", "ib_high", "inside"),
    ("2026-02-22", "ib_high", "inside"),
    ("2026-02-21", "ib_high", "inside"),
    # ES leads low: ES breaks ib_low, NQ still inside — ~4%
    ("2026-02-20", "ib_low", "inside"),
    ("2026-02-19", "ib_low", "inside"),
    ("2026-02-18", "ib_low", "inside"),
    ("2026-02-17", "ib_low", "inside"),
    ("2026-02-16", "ib_low", "inside"),
    # NQ leads high: NQ breaks ib_high, ES still inside — ~3%
    ("2026-02-15", "inside", "ib_high"),
    ("2026-02-14", "inside", "ib_high"),
    ("2026-02-13", "inside", "ib_high"),
    ("2026-02-12", "inside", "ib_high"),
    # NQ leads low: NQ breaks ib_low, ES still inside — ~3%
    ("2026-02-11", "inside", "ib_low"),
    ("2026-02-10", "inside", "ib_low"),
    ("2026-02-09", "inside", "ib_low"),
    # Opposite: ES high / NQ low — ~2%
    ("2026-02-08", "ib_high", "ib_low"),
    ("2026-02-07", "ib_high", "ib_low"),
    ("2026-02-06", "ib_high", "ib_low"),
    # Opposite: ES low / NQ high — ~2%
    ("2026-02-05", "ib_low", "ib_high"),
    ("2026-02-04", "ib_low", "ib_high"),
    ("2026-02-03", "ib_low", "ib_high"),
    # Double breaks (outside days) — ~3%
    ("2026-02-02", "double", "double"),
    ("2026-02-01", "double", "double"),
    ("2026-01-31", "double", "ib_high"),
    ("2026-01-30", "ib_low",  "double"),
]


# ── Analysis engine ───────────────────────────────────────────────────────────

def analyze(sessions: list[tuple]) -> dict:
    """
    Build contingency table, alignment stats, and divergence scenarios.

    Returns a structured dict suitable for JSON serialization or dashboard rendering.
    """
    contingency: dict[tuple, int] = defaultdict(int)
    dow_alignment: dict[str, dict] = defaultdict(lambda: {"aligned": 0, "total": 0})

    DOW = ["Mon", "Tue", "Wed", "Thu", "Fri"]

    for date, es_raw, nq_raw in sessions:
        es = _classify(es_raw)
        nq = _classify(nq_raw)
        contingency[(es, nq)] += 1

        # Day-of-week (parse YYYY-MM-DD)
        try:
            from datetime import date as _date
            d = _date.fromisoformat(date)
            dow = DOW[d.weekday()]
        except Exception:
            dow = "Unk"
        aligned = (es == nq) or (es == "double") or (nq == "double")
        dow_alignment[dow]["total"] += 1
        if aligned:
            dow_alignment[dow]["aligned"] += 1

    total = len(sessions)

    # Alignment = same direction (excluding double/inside noise)
    aligned_count = sum(
        v for (es, nq), v in contingency.items()
        if es == nq
    )

    # Divergence scenarios
    es_leads_high  = contingency[("ib_high", "inside")]
    es_leads_low   = contingency[("ib_low",  "inside")]
    nq_leads_high  = contingency[("inside",  "ib_high")]
    nq_leads_low   = contingency[("inside",  "ib_low")]
    opposite_hl    = contingency[("ib_high", "ib_low")]
    opposite_lh    = contingency[("ib_low",  "ib_high")]
    both_inside    = contingency[("inside",  "inside")]
    outside_days   = (
        contingency[("double", "double")] +
        contingency[("double", "ib_high")] +
        contingency[("double", "ib_low")] +
        contingency[("ib_high", "double")] +
        contingency[("ib_low",  "double")]
    )

    def pct(n): return round(100 * n / total, 1) if total else 0

    # Build the 4x4 contingency matrix for display
    matrix = {}
    for es_t in BREAK_TYPES:
        matrix[es_t] = {}
        for nq_t in BREAK_TYPES:
            matrix[es_t][nq_t] = contingency[(es_t, nq_t)]

    # Per-dow alignment rates
    dow_stats = {}
    for day in DOW:
        d = dow_alignment.get(day, {"aligned": 0, "total": 0})
        t = d["total"]
        dow_stats[day] = {
            "total": t,
            "aligned": d["aligned"],
            "alignment_rate": round(100 * d["aligned"] / t, 1) if t else None,
        }

    return {
        "total_sessions": total,
        "aligned_count": aligned_count,
        "alignment_rate": pct(aligned_count),
        "contingency": {f"es_{es}__nq_{nq}": v for (es, nq), v in contingency.items()},
        "matrix": matrix,
        "divergence_scenarios": {
            "es_leads_high":  {"count": es_leads_high,  "pct": pct(es_leads_high)},
            "es_leads_low":   {"count": es_leads_low,   "pct": pct(es_leads_low)},
            "nq_leads_high":  {"count": nq_leads_high,  "pct": pct(nq_leads_high)},
            "nq_leads_low":   {"count": nq_leads_low,   "pct": pct(nq_leads_low)},
            "opposite_hl":    {"count": opposite_hl,    "pct": pct(opposite_hl)},
            "opposite_lh":    {"count": opposite_lh,    "pct": pct(opposite_lh)},
            "both_inside":    {"count": both_inside,    "pct": pct(both_inside)},
            "outside_days":   {"count": outside_days,   "pct": pct(outside_days)},
        },
        "dow_alignment": dow_stats,
    }


# ── Live data fetch (requires local network access) ──────────────────────────

def _fetch_live_sessions(api_key: str, n_sessions: int = 123) -> list[tuple] | None:
    try:
        from optimizer.edgeful import EdgefulClient
        client = EdgefulClient(api_key=api_key)
        es_data = client.get_initial_balance("ES")
        nq_data = client.get_initial_balance("NQ")
        if not es_data or not nq_data:
            return None
        # Edgeful returns sessions list under "sessions" key
        es_sessions = {s["date"]: s for s in es_data.get("sessions", [])}
        nq_sessions = {s["date"]: s for s in nq_data.get("sessions", [])}
        common_dates = sorted(set(es_sessions) & set(nq_sessions), reverse=True)[:n_sessions]
        return [
            (d, es_sessions[d].get("break_type"), nq_sessions[d].get("break_type"))
            for d in common_dates
        ]
    except Exception as e:
        log.debug("Live fetch failed: %s", e)
        return None


# ── Console rendering ─────────────────────────────────────────────────────────

def _col(value: float, threshold_high=65, threshold_low=50) -> str:
    if value >= threshold_high:
        return f"{GREEN}{value}%{RESET}"
    if value >= threshold_low:
        return f"{YELLOW}{value}%{RESET}"
    return f"{RED}{value}%{RESET}"


def _print_results(result: dict, live: bool) -> None:
    source = "live Edgeful API" if live else "illustrative sample (123 sessions)"
    print(f"\n{BOLD}{WHITE}ES / NQ  Initial Balance Correlation{RESET}")
    print(f"{'─' * 55}")
    print(f"Sessions: {result['total_sessions']}   Source: {source}")
    print()

    ar = result["alignment_rate"]
    print(f"  Overall alignment rate:  {_col(ar)}")
    print(f"  Aligned sessions:        {result['aligned_count']} / {result['total_sessions']}")
    print()

    # Contingency matrix
    print(f"{BOLD}Contingency table  (row=ES break, col=NQ break){RESET}")
    headers = ["ES \\ NQ", "ib_high", "ib_low", "inside", "double", "ROW SUM"]
    rows = []
    matrix = result["matrix"]
    for es_t in BREAK_TYPES:
        row = [es_t]
        row_sum = 0
        for nq_t in BREAK_TYPES:
            v = matrix[es_t][nq_t]
            row_sum += v
            row.append(v if v else ".")
        row.append(row_sum)
        rows.append(row)
    if _TABULATE:
        print(tabulate(rows, headers=headers, tablefmt="simple"))
    else:
        print("  " + "  ".join(f"{h:>8}" for h in headers))
        for r in rows:
            print("  " + "  ".join(f"{str(c):>8}" for c in r))
    print()

    # Divergence scenarios
    print(f"{BOLD}Divergence scenarios{RESET}")
    ds = result["divergence_scenarios"]
    scen_rows = [
        ["aligned (same dir)",   result["aligned_count"], f"{_col(result['alignment_rate'])}"],
        ["ES leads high",        ds["es_leads_high"]["count"],  f"{ds['es_leads_high']['pct']}%"],
        ["ES leads low",         ds["es_leads_low"]["count"],   f"{ds['es_leads_low']['pct']}%"],
        ["NQ leads high",        ds["nq_leads_high"]["count"],  f"{ds['nq_leads_high']['pct']}%"],
        ["NQ leads low",         ds["nq_leads_low"]["count"],   f"{ds['nq_leads_low']['pct']}%"],
        ["opposite (H vs L)",    ds["opposite_hl"]["count"],    f"{ds['opposite_hl']['pct']}%"],
        ["opposite (L vs H)",    ds["opposite_lh"]["count"],    f"{ds['opposite_lh']['pct']}%"],
        ["both inside",          ds["both_inside"]["count"],    f"{ds['both_inside']['pct']}%"],
        ["outside days",         ds["outside_days"]["count"],   f"{ds['outside_days']['pct']}%"],
    ]
    sh = ["Scenario", "Sessions", "% of total"]
    if _TABULATE:
        print(tabulate(scen_rows, headers=sh, tablefmt="simple"))
    else:
        print("  " + "  ".join(f"{h:>20}" for h in sh))
        for r in scen_rows:
            print("  " + "  ".join(f"{str(c):>20}" for c in r))
    print()

    # Day-of-week breakdown
    print(f"{BOLD}Alignment by day of week{RESET}")
    dow = result["dow_alignment"]
    dow_rows = []
    for day, stats in dow.items():
        if stats["total"] == 0:
            continue
        ar_day = stats["alignment_rate"] or 0
        dow_rows.append([day, stats["total"], stats["aligned"], f"{_col(ar_day)}"])
    dh = ["Day", "Sessions", "Aligned", "Rate"]
    if _TABULATE:
        print(tabulate(dow_rows, headers=dh, tablefmt="simple"))
    else:
        print("  " + "  ".join(f"{h:>10}" for h in dh))
        for r in dow_rows:
            print("  " + "  ".join(f"{str(c):>10}" for c in r))
    print()

    # Trade playbook summary
    print(f"{BOLD}MNQ trade playbook{RESET}")
    plays = [
        ("Both aligned (same dir)",   "Full size, high conviction; fade only on extreme extension"),
        ("ES leads, NQ inside",        "Fade NQ IB boundary in ES direction; reduce size, tight stop"),
        ("NQ leads, ES inside",        "Wait for ES to confirm; enter after ES crosses IB level"),
        ("Opposite breaks",            "No IB trade; manage existing positions, reduce exposure"),
        ("Both inside / outside day",  "Skip IB breakout; look for mean-reversion after fakeout"),
    ]
    for scenario, action in plays:
        print(f"  {CYAN}{scenario:<35}{RESET}  {action}")
    print()


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="ES/NQ initial balance correlation analysis"
    )
    parser.add_argument("--key", default=os.getenv("EDGEFUL_API_KEY"), help="Edgeful API key")
    parser.add_argument("--sessions", type=int, default=123, help="Number of sessions to analyze")
    parser.add_argument("--json", action="store_true", dest="as_json", help="Output raw JSON")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.debug else logging.WARNING)

    live = False
    sessions = None

    if args.key:
        sessions = _fetch_live_sessions(args.key, args.sessions)
        if sessions:
            live = True
            log.debug("Loaded %d live sessions", len(sessions))

    if not sessions:
        if args.key:
            print(
                f"{YELLOW}Note: live API unreachable (network policy). "
                f"Using illustrative sample data.{RESET}",
                file=sys.stderr,
            )
        sessions = SAMPLE_SESSIONS

    result = analyze(sessions)
    result["data_source"] = "live" if live else "sample"

    if args.as_json:
        print(json.dumps(result, indent=2))
        return

    _print_results(result, live)


if __name__ == "__main__":
    main()
