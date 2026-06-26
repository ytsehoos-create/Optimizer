#!/usr/bin/env python3
"""
NQ contract volume — average daily volume + first-15-minute volume.

Pulls per-session contract volume for NQ (Nasdaq-100 E-mini futures) over the
past N trading days (default 30) and reports:
  • Average total session volume per day
  • Average volume in the opening window (default: first 15 minutes of RTH)
  • The opening window's share of the full day's volume

Tries the live Edgeful API first (requires EDGEFUL_API_KEY + network access to
api.edgeful.com). Falls back to a clearly-labeled, deterministic illustrative
sample when the live API is unreachable, matching the convention used by
es_nq_ib_correlation.py and nq_today.py elsewhere in this repo.

Usage:
    python nq_volume_analysis.py                  # past 30 trading days, NQ
    python nq_volume_analysis.py --days 20
    python nq_volume_analysis.py --window 5        # first 5 minutes instead of 15
    python nq_volume_analysis.py --json
    python nq_volume_analysis.py --dashboard       # also write output/<date>-nq-volume-analysis/dashboard.html
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import random
import statistics
import sys
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    from colorama import Fore, Style, init as colorama_init
    colorama_init(autoreset=True)
    GREEN, RED, YELLOW, CYAN, BOLD, RESET = (
        Fore.GREEN, Fore.RED, Fore.YELLOW, Fore.CYAN, Style.BRIGHT, Style.RESET_ALL,
    )
except ImportError:
    GREEN = RED = YELLOW = CYAN = BOLD = RESET = ""

try:
    from tabulate import tabulate
    _TABULATE = True
except ImportError:
    _TABULATE = False

log = logging.getLogger(__name__)


# ── Trading-day calendar ─────────────────────────────────────────────────────

def _trailing_trading_days(n: int, end: Optional[date] = None) -> List[date]:
    """Most recent *n* weekdays (Mon-Fri) up to and including *end*, oldest first."""
    end = end or date.today()
    days: List[date] = []
    cursor = end
    while len(days) < n:
        if cursor.weekday() < 5:  # Mon=0 .. Fri=4
            days.append(cursor)
        cursor -= timedelta(days=1)
    return list(reversed(days))


# ── Illustrative sample data ──────────────────────────────────────────────────
# NQ front-month contract volume has averaged roughly 350k-450k contracts/day
# over recent periods, with the opening 15 minutes typically carrying ~8-12%
# of the full session's volume due to open-auction / imbalance participation.

def _generate_sample_sessions(
    days: List[date], window_minutes: int, seed: int = 42,
) -> List[Dict]:
    rng = random.Random(seed)
    sessions = []
    for d in days:
        total_volume = max(150_000, round(rng.gauss(390_000, 45_000)))
        # Scale the opening-window share with window size: a 5-min window
        # captures less of the day than a 60-min window, but with diminishing
        # marginal share as the window widens past the open.
        base_pct = 0.095 * (window_minutes / 15) ** 0.55
        pct = max(0.02, min(0.45, rng.gauss(base_pct, base_pct * 0.18)))
        window_volume = round(total_volume * pct)
        sessions.append({
            "date": d.isoformat(),
            "total_volume": total_volume,
            "opening_window_volume": window_volume,
        })
    return sessions


# ── Live data fetch ───────────────────────────────────────────────────────────

def _fetch_live_sessions(
    api_key: str, symbol: str, days: int, window_minutes: int,
) -> Optional[List[Dict]]:
    try:
        from optimizer.edgeful import EdgefulClient
        client = EdgefulClient(api_key=api_key)
        data = client.get_volume_profile(symbol, lookback_days=days, opening_window_minutes=window_minutes)
        sessions = data.get("sessions") if isinstance(data, dict) else None
        if not sessions:
            return None
        return sessions
    except Exception as e:
        log.debug("Live fetch failed: %s", e)
        return None


# ── Analysis ──────────────────────────────────────────────────────────────────

def analyze(sessions: List[Dict], window_minutes: int) -> Dict:
    totals = [s["total_volume"] for s in sessions]
    windows = [s["opening_window_volume"] for s in sessions]
    pcts = [w / t for w, t in zip(windows, totals) if t]

    n = len(sessions)

    def _round(x):
        return round(x) if x is not None else None

    return {
        "n_sessions": n,
        "window_minutes": window_minutes,
        "date_range": [sessions[0]["date"], sessions[-1]["date"]] if sessions else [],
        "avg_daily_volume": _round(statistics.mean(totals)) if totals else None,
        "median_daily_volume": _round(statistics.median(totals)) if totals else None,
        "min_daily_volume": min(totals) if totals else None,
        "max_daily_volume": max(totals) if totals else None,
        "avg_opening_window_volume": _round(statistics.mean(windows)) if windows else None,
        "median_opening_window_volume": _round(statistics.median(windows)) if windows else None,
        "min_opening_window_volume": min(windows) if windows else None,
        "max_opening_window_volume": max(windows) if windows else None,
        "avg_opening_window_pct": round(100 * statistics.mean(pcts), 2) if pcts else None,
        "sessions": sessions,
    }


# ── Console rendering ─────────────────────────────────────────────────────────

def _fmt_vol(v) -> str:
    return f"{v:,.0f}" if isinstance(v, (int, float)) else "—"


def _print_results(result: Dict, symbol: str, live: bool) -> None:
    source = "live Edgeful API" if live else "illustrative sample data (not real market data)"
    w = result["window_minutes"]
    start, end = result["date_range"][0], result["date_range"][-1]

    print(f"\n{BOLD}{CYAN}{symbol} contract volume — past {result['n_sessions']} trading days{RESET}")
    print(f"{'─' * 60}")
    print(f"Date range: {start} → {end}   Source: {source}")
    print()
    print(f"  {'Average volume per day:':<38} {GREEN}{_fmt_vol(result['avg_daily_volume'])}{RESET} contracts")
    print(f"  {'  median / min / max:':<38} {_fmt_vol(result['median_daily_volume'])} / "
          f"{_fmt_vol(result['min_daily_volume'])} / {_fmt_vol(result['max_daily_volume'])}")
    print()
    print(f"  {f'Average volume, first {w} min:':<38} {GREEN}{_fmt_vol(result['avg_opening_window_volume'])}{RESET} contracts")
    print(f"  {'  median / min / max:':<38} {_fmt_vol(result['median_opening_window_volume'])} / "
          f"{_fmt_vol(result['min_opening_window_volume'])} / {_fmt_vol(result['max_opening_window_volume'])}")
    print()
    print(f"  {f'First {w} min share of day (avg):':<38} {YELLOW}{result['avg_opening_window_pct']}%{RESET}")
    print()

    rows = [
        [s["date"], _fmt_vol(s["total_volume"]), _fmt_vol(s["opening_window_volume"]),
         f"{100 * s['opening_window_volume'] / s['total_volume']:.1f}%"]
        for s in result["sessions"]
    ]
    headers = ["Date", "Day volume", f"First {w}m volume", f"% of day"]
    if _TABULATE:
        print(tabulate(rows, headers=headers, tablefmt="simple"))
    else:
        print("  " + "  ".join(f"{h:>14}" for h in headers))
        for r in rows:
            print("  " + "  ".join(f"{str(c):>14}" for c in r))
    print()

    if not live:
        print(f"{YELLOW}Note: live Edgeful API unreachable (no EDGEFUL_API_KEY / network policy). "
              f"Figures above are an illustrative model, not real market data.{RESET}\n")


# ── Dashboard ──────────────────────────────────────────────────────────────────

_DASHBOARD_TEMPLATE = """\
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{symbol} contract volume · day + first {window}min · {date_range}</title>
<script src="https://cdn.tailwindcss.com"></script>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;500&display=swap" rel="stylesheet">
<style>
  body {{ font-family: 'Poppins', sans-serif; background: #09090B; color: #C7C7C7; }}
  .card {{ background: #09090B; border: 1px solid #2A2A2A; border-radius: 12px; }}
  .stat-num {{ font-weight: 500; font-feature-settings: "tnum"; }}
  table {{ font-feature-settings: "tnum"; }}
  .subsection-header {{ background: #121212; border-bottom: 1px solid #2A2A2A; padding: 12px 24px; border-top-left-radius: 12px; border-top-right-radius: 12px; }}
  .source-label {{ font-size: 12px; color: #555555; text-transform: lowercase; }}
  .source-label a {{ color: #555555; text-decoration: none; border-bottom: 1px dashed rgba(85,85,85,0.5); }}
  .source-label a:hover {{ color: #C7C7C7; }}
  .meta-line {{ font-size: 12px; color: #FFFFFF; display: flex; flex-wrap: wrap; align-items: center; gap: 4px 8px; }}
  .meta-sep {{ color: #555555; }}
  .meta-line a.meta-link {{ color: #0075FF; text-decoration: none; }}
  .section-divider {{ border-top: 1px solid #2A2A2A; margin: 3rem 0 2rem; }}
</style>
</head>
<body class="min-h-screen">
<div class="max-w-7xl mx-auto px-6 py-10">

<header class="mb-8">
  <div class="text-xs uppercase tracking-wider text-neutral-500 mb-2">volume analysis · {generated_on}</div>
  <h1 class="text-3xl font-medium text-white mb-2 lowercase">{symbol} contract volume · day vs first {window} min</h1>
  <p class="meta-line">
    <span>{symbol} session volume + opening window volume</span>
    <span class="meta-sep">|</span>
    <span>{date_range}</span>
    <span class="meta-sep">|</span>
    <span>{n_sessions} trading days</span>
    <span class="meta-sep">|</span>
    <a class="meta-link" href="https://edgeful.com" target="_blank" rel="noopener">edgeful.com</a>
  </p>
  <p class="source-label mt-2">data: {source_label}</p>
</header>

<div class="card p-6 mb-8">
  <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
    <div>
      <div class="text-xs uppercase tracking-wider text-neutral-500 mb-2">what this shows</div>
      <p class="text-sm text-neutral-300 leading-relaxed lowercase">total {symbol} contract volume per trading session, and how much of that volume trades within the first {window} minutes of the session, over the trailing {n_sessions} trading days.</p>
    </div>
    <div>
      <div class="text-xs uppercase tracking-wider text-neutral-500 mb-2">how to read it</div>
      <p class="text-sm text-neutral-300 leading-relaxed lowercase">the opening window typically carries a disproportionate share of the day's volume due to overnight-imbalance unwind and opening-auction participation. the chart below pairs each day's total volume with its opening-window volume.</p>
    </div>
    <div>
      <div class="text-xs uppercase tracking-wider text-neutral-500 mb-2">key takeaway</div>
      <p class="text-sm text-neutral-300 leading-relaxed lowercase">average daily volume is {avg_daily} contracts; the first {window} minutes average {avg_window} contracts, or {avg_pct}% of the full session.</p>
    </div>
  </div>
</div>

<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
  <div class="card p-6">
    <div class="text-xs uppercase tracking-wider text-neutral-500 mb-2">avg volume / day</div>
    <div class="stat-num text-3xl" style="color:#4ADE80">{avg_daily}</div>
    <div class="text-xs text-neutral-500 mt-1">contracts · median {median_daily}</div>
  </div>
  <div class="card p-6">
    <div class="text-xs uppercase tracking-wider text-neutral-500 mb-2">avg first {window}m volume</div>
    <div class="stat-num text-3xl" style="color:#4ADE80">{avg_window}</div>
    <div class="text-xs text-neutral-500 mt-1">contracts · median {median_window}</div>
  </div>
  <div class="card p-6">
    <div class="text-xs uppercase tracking-wider text-neutral-500 mb-2">first {window}m share of day</div>
    <div class="stat-num text-3xl" style="color:#FACC15">{avg_pct}%</div>
    <div class="text-xs text-neutral-500 mt-1">average across sessions</div>
  </div>
  <div class="card p-6">
    <div class="text-xs uppercase tracking-wider text-neutral-500 mb-2">daily volume range</div>
    <div class="stat-num text-3xl" style="color:#60A5FA">{min_daily}</div>
    <div class="text-xs text-neutral-500 mt-1">low · high {max_daily}</div>
  </div>
</div>

<div class="section-divider"></div>
<div class="flex items-center gap-3 mb-4">
  <h2 class="text-lg font-medium text-white lowercase">daily volume vs opening-window volume</h2>
</div>

<div class="card overflow-hidden mb-8">
  <div class="subsection-header">
    <span class="text-sm font-medium text-white">{symbol} session volume</span>
    <span class="text-xs text-neutral-500 ml-2">total session volume (blue) vs first {window}-min volume (amber) · {n_sessions} trading days</span>
  </div>
  <div class="p-6">
    <div style="height:280px"><canvas id="volChart"></canvas></div>
  </div>
</div>

<div class="card overflow-hidden mb-8">
  <div class="subsection-header">
    <span class="text-sm font-medium text-white">session-by-session detail</span>
  </div>
  <div class="p-6 overflow-x-auto">
    <table class="w-full text-sm">
      <thead>
        <tr class="text-xs text-neutral-500 border-b border-neutral-800">
          <th class="text-left pb-2">date</th>
          <th class="text-right pb-2">day volume</th>
          <th class="text-right pb-2">first {window}m volume</th>
          <th class="text-right pb-2">% of day</th>
        </tr>
      </thead>
      <tbody class="divide-y divide-neutral-800">
{table_rows}
      </tbody>
    </table>
  </div>
</div>

<footer class="mt-12 pt-6 border-t border-neutral-800">
  <div class="flex flex-wrap items-center justify-between gap-4">
    <p class="source-label">data: {source_label} · {n_sessions} trading days · {date_range}</p>
    <p class="text-xs text-neutral-700">{footer_note}</p>
  </div>
</footer>

</div>
<script>
const PRIMARY = '#0075FF';
const WARNING = '#D89700';
const TEXT    = '#C7C7C7';
const GRID    = 'rgba(42,42,42,0.8)';

Chart.defaults.color = TEXT;
Chart.defaults.font.family = 'Poppins';
Chart.defaults.font.size = 12;

new Chart(document.getElementById('volChart'), {{
  type: 'bar',
  data: {{
    labels: {labels_json},
    datasets: [
      {{
        label: 'day volume',
        data: {day_volume_json},
        backgroundColor: 'rgba(0,117,255,0.55)',
        borderColor: PRIMARY, borderWidth: 1, borderRadius: 3,
      }},
      {{
        label: 'first {window}m volume',
        data: {window_volume_json},
        backgroundColor: 'rgba(216,151,0,0.85)',
        borderColor: WARNING, borderWidth: 1, borderRadius: 3,
      }}
    ]
  }},
  options: {{
    responsive: true, maintainAspectRatio: false,
    plugins: {{
      legend: {{ display: true, labels: {{ boxWidth: 10, padding: 12, color: TEXT }} }},
      tooltip: {{
        backgroundColor: '#1A1A1A', borderColor: '#2A2A2A', borderWidth: 1,
        titleColor: '#FFFFFF', bodyColor: TEXT, padding: 10,
        callbacks: {{ label: ctx => ` ${{ctx.dataset.label}}: ${{ctx.parsed.y.toLocaleString()}}` }}
      }}
    }},
    scales: {{
      x: {{ grid: {{ color: GRID }}, ticks: {{ color: TEXT, maxRotation: 60, minRotation: 60 }} }},
      y: {{ grid: {{ color: GRID }}, ticks: {{ color: TEXT, callback: v => v.toLocaleString() }} }}
    }}
  }}
}});
</script>
</body>
</html>
"""


def _write_dashboard(result: Dict, symbol: str, live: bool, out_path: str) -> None:
    sessions = result["sessions"]
    w = result["window_minutes"]
    date_range = f"{result['date_range'][0]} - {result['date_range'][-1]}"
    source_label = (
        f'<a href="https://edgeful.com/reports/futures/{symbol}/volume" target="_blank" rel="noopener">'
        f'{symbol} volume profile</a> <span style="color:#60A5FA">{symbol}</span>'
        if live else "illustrative model · pending live API access"
    )
    footer_note = (
        "live edgeful data · not financial advice" if live
        else "illustrative model data pending live API access · not financial advice"
    )

    table_rows = "\n".join(
        f'        <tr><td class="py-2 text-neutral-300">{s["date"]}</td>'
        f'<td class="py-2 text-right text-neutral-300">{_fmt_vol(s["total_volume"])}</td>'
        f'<td class="py-2 text-right text-neutral-300">{_fmt_vol(s["opening_window_volume"])}</td>'
        f'<td class="py-2 text-right" style="color:#FACC15">'
        f'{100 * s["opening_window_volume"] / s["total_volume"]:.1f}%</td></tr>'
        for s in sessions
    )

    html = _DASHBOARD_TEMPLATE.format(
        symbol=symbol,
        window=w,
        date_range=date_range,
        generated_on=datetime.now().strftime("%A, %B %-d %Y"),
        n_sessions=result["n_sessions"],
        source_label=source_label,
        footer_note=footer_note,
        avg_daily=_fmt_vol(result["avg_daily_volume"]),
        median_daily=_fmt_vol(result["median_daily_volume"]),
        min_daily=_fmt_vol(result["min_daily_volume"]),
        max_daily=_fmt_vol(result["max_daily_volume"]),
        avg_window=_fmt_vol(result["avg_opening_window_volume"]),
        median_window=_fmt_vol(result["median_opening_window_volume"]),
        avg_pct=result["avg_opening_window_pct"],
        table_rows=table_rows,
        labels_json=json.dumps([s["date"][5:] for s in sessions]),
        day_volume_json=json.dumps([s["total_volume"] for s in sessions]),
        window_volume_json=json.dumps([s["opening_window_volume"] for s in sessions]),
    )

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Average NQ contract volume per day and in the opening window, over the past N trading days."
    )
    parser.add_argument("--key",       default=os.getenv("EDGEFUL_API_KEY"), help="Edgeful API key")
    parser.add_argument("--symbol",    default="NQ",                        help="Futures symbol (default: NQ)")
    parser.add_argument("--days",      type=int, default=30,                help="Trailing trading days to include")
    parser.add_argument("--window",    type=int, default=15,                help="Opening window size in minutes")
    parser.add_argument("--json",      action="store_true", dest="as_json", help="Output raw JSON")
    parser.add_argument("--dashboard", action="store_true",                 help="Also write an HTML dashboard to output/")
    parser.add_argument("--debug",     action="store_true",                 help="Enable debug logging")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.debug else logging.WARNING)

    symbol = args.symbol.upper()
    days = _trailing_trading_days(args.days)

    live = False
    sessions = None
    if args.key:
        sessions = _fetch_live_sessions(args.key, symbol, args.days, args.window)
        if sessions:
            live = True

    if not sessions:
        if args.key:
            print(
                f"{YELLOW}Note: live Edgeful API unreachable (network policy or no data). "
                f"Using illustrative sample data.{RESET}",
                file=sys.stderr,
            )
        sessions = _generate_sample_sessions(days, args.window)

    result = analyze(sessions, args.window)
    result["data_source"] = "live" if live else "sample"
    result["symbol"] = symbol

    if args.as_json:
        print(json.dumps(result, indent=2))
    else:
        _print_results(result, symbol, live)

    if args.dashboard:
        slug = f"{date.today().isoformat().replace('-', '.')}-{symbol.lower()}-volume-analysis"
        out_path = os.path.join("output", slug, "dashboard.html")
        _write_dashboard(result, symbol, live, out_path)
        print(f"Dashboard written to {out_path}")


if __name__ == "__main__":
    main()
