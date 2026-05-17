"""Generate HTML and CSV reports from optimization results."""
from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import List

import pandas as pd

from .results import METRIC_LABELS, OptimizationResult, ResultsCollection

log = logging.getLogger(__name__)

_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Strategy Optimizer Report</title>
<style>
  :root {{
    --bg: #0d1117; --surface: #161b22; --border: #30363d;
    --text: #c9d1d9; --accent: #58a6ff; --green: #3fb950;
    --red: #f85149; --yellow: #d29922; --purple: #bc8cff;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: var(--bg); color: var(--text); font-family: 'Segoe UI', system-ui, sans-serif; padding: 24px; }}
  h1 {{ color: var(--accent); font-size: 1.8rem; margin-bottom: 4px; }}
  .subtitle {{ color: #8b949e; margin-bottom: 24px; font-size: 0.9rem; }}
  h2 {{ color: var(--accent); font-size: 1.2rem; margin: 24px 0 12px; border-bottom: 1px solid var(--border); padding-bottom: 6px; }}
  .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; margin-bottom: 24px; }}
  .stat-card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 16px; text-align: center; }}
  .stat-card .value {{ font-size: 1.6rem; font-weight: 700; color: var(--green); }}
  .stat-card .label {{ font-size: 0.78rem; color: #8b949e; margin-top: 4px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.83rem; }}
  th {{ background: var(--surface); color: var(--accent); padding: 10px 12px; text-align: left; position: sticky; top: 0; z-index: 1; border-bottom: 2px solid var(--border); }}
  td {{ padding: 8px 12px; border-bottom: 1px solid var(--border); vertical-align: middle; }}
  tr:hover td {{ background: rgba(88,166,255,0.05); }}
  .rank-1 td {{ background: rgba(63,185,80,0.08) !important; }}
  .rank-2 td {{ background: rgba(63,185,80,0.05) !important; }}
  .rank-3 td {{ background: rgba(63,185,80,0.03) !important; }}
  .badge {{ display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 0.75rem; font-weight: 600; }}
  .badge-gold   {{ background: #b8860b22; color: #ffd700; border: 1px solid #ffd700; }}
  .badge-silver {{ background: #c0c0c022; color: #c0c0c0; border: 1px solid #c0c0c0; }}
  .badge-bronze {{ background: #cd7f3222; color: #cd7f32; border: 1px solid #cd7f32; }}
  .pos {{ color: var(--green); }} .neg {{ color: var(--red); }}
  .table-wrap {{ overflow-x: auto; background: var(--surface); border: 1px solid var(--border); border-radius: 8px; }}
  .section {{ margin-bottom: 32px; }}
  .meta {{ display: flex; gap: 24px; flex-wrap: wrap; margin-bottom: 20px; }}
  .meta-item {{ background: var(--surface); border: 1px solid var(--border); border-radius: 6px; padding: 8px 14px; font-size: 0.83rem; }}
  .meta-item span {{ color: var(--accent); font-weight: 600; }}
  footer {{ margin-top: 40px; text-align: center; color: #8b949e; font-size: 0.78rem; border-top: 1px solid var(--border); padding-top: 16px; }}
</style>
</head>
<body>
<h1>PineScript Strategy Optimizer</h1>
<p class="subtitle">Generated {timestamp}</p>

<div class="meta">
  <div class="meta-item">Algorithm: <span>{algorithm}</span></div>
  <div class="meta-item">Metric: <span>{metric}</span></div>
  <div class="meta-item">Total Trials: <span>{total_trials}</span></div>
  <div class="meta-item">Successful: <span>{successful}</span></div>
  <div class="meta-item">Failed: <span>{failed}</span></div>
</div>

<h2>Best Result</h2>
<div class="stats-grid">
{best_stats}
</div>

<h2>Top {top_n} Results</h2>
<div class="section">
<div class="table-wrap">
<table>
<thead><tr>{headers}</tr></thead>
<tbody>
{rows}
</tbody>
</table>
</div>
</div>

<h2>All Results ({total_trials} trials)</h2>
<div class="section">
<div class="table-wrap">
<table>
<thead><tr>{all_headers}</tr></thead>
<tbody>
{all_rows}
</tbody>
</table>
</div>
</div>

<footer>PineScript Strategy Optimizer &mdash; {timestamp}</footer>
</body>
</html>
"""


def _fmt(v, decimals: int = 2) -> str:
    if v is None:
        return "<span style='color:#8b949e'>—</span>"
    try:
        f = float(v)
        return f"{f:.{decimals}f}"
    except (ValueError, TypeError):
        return str(v)


def _signed_cell(v, suffix: str = "") -> str:
    if v is None:
        return "<span style='color:#8b949e'>—</span>"
    try:
        f = float(v)
        cls = "pos" if f >= 0 else "neg"
        sign = "+" if f > 0 else ""
        return f'<span class="{cls}">{sign}{f:.2f}{suffix}</span>'
    except (ValueError, TypeError):
        return str(v)


class Reporter:
    def __init__(self, results: ResultsCollection, config: dict):
        self.results = results
        self.config = config
        self.out_dir = config.get("output_dir", "reports")
        self.top_n = config.get("top_n", 20)
        self.formats = config.get("formats", ["html", "csv"])

    def generate(self):
        os.makedirs(self.out_dir, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")

        if "csv" in self.formats:
            csv_path = os.path.join(self.out_dir, f"results_{ts}.csv")
            self.results.save_csv(csv_path)
            log.info("CSV saved: %s", csv_path)

        if "html" in self.formats:
            html_path = os.path.join(self.out_dir, f"results_{ts}.html")
            self._write_html(html_path, ts)
            log.info("HTML report saved: %s", html_path)

        self._print_summary()

    # ------------------------------------------------------------------

    def _write_html(self, path: str, ts: str):
        df = self.results.to_dataframe()
        top = self.results.top_n(self.top_n)
        best = self.results.best()
        successful = self.results.successful

        param_cols = list(self.results.successful[0].params.keys()) if successful else []
        metric_cols = [
            "net_profit", "profit_factor", "percent_profitable",
            "total_trades", "max_drawdown", "sharpe_ratio", "score",
        ]
        display_cols = ["rank"] + param_cols + metric_cols

        best_stats = self._build_best_stats(best) if best else ""
        headers = "".join(f"<th>{c.replace('_', ' ').title()}</th>" for c in display_cols)
        rows = self._build_rows(top, display_cols, highlight=True)
        all_rows = self._build_rows(successful[:200], display_cols, highlight=False)

        html = _HTML_TEMPLATE.format(
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            algorithm=self.config.get("algorithm", "N/A"),
            metric=self.config.get("metric", "N/A"),
            total_trials=len(self.results),
            successful=len(successful),
            failed=len(self.results) - len(successful),
            best_stats=best_stats,
            top_n=min(self.top_n, len(successful)),
            headers=headers,
            rows=rows,
            all_headers=headers,
            all_rows=all_rows,
        )

        with open(path, "w", encoding="utf-8") as f:
            f.write(html)

    def _build_best_stats(self, best: OptimizationResult) -> str:
        m = best.metrics
        cards = [
            ("Net Profit", f"{_fmt(m.net_profit)}%"),
            ("Profit Factor", _fmt(m.profit_factor)),
            ("Win Rate", f"{_fmt(m.percent_profitable)}%"),
            ("Total Trades", str(m.total_trades or "—")),
            ("Max Drawdown", f"{_fmt(m.max_drawdown)}%"),
            ("Sharpe Ratio", _fmt(m.sharpe_ratio)),
            ("Score", _fmt(best.score, 4)),
        ]
        html = ""
        for label, value in cards:
            html += f"""
<div class="stat-card">
  <div class="value">{value}</div>
  <div class="label">{label}</div>
</div>"""
        return html

    def _build_rows(self, results: List[OptimizationResult], cols: list, highlight: bool) -> str:
        rows_html = ""
        for r in results:
            row_d = r.to_dict()
            rank = r.rank
            badge = ""
            if rank == 1:
                badge = '<span class="badge badge-gold">🥇 #1</span>'
            elif rank == 2:
                badge = '<span class="badge badge-silver">🥈 #2</span>'
            elif rank == 3:
                badge = '<span class="badge badge-bronze">🥉 #3</span>'

            cls = f'class="rank-{rank}"' if highlight and rank <= 3 else ""
            cells = ""
            for col in cols:
                if col == "rank":
                    cells += f"<td>{badge or rank}</td>"
                elif col in ("net_profit", "avg_trade", "avg_win", "avg_loss"):
                    cells += f"<td>{_signed_cell(row_d.get(col), '%')}</td>"
                elif col == "max_drawdown":
                    v = row_d.get(col)
                    cells += f"<td>{_signed_cell(-abs(float(v)) if v else None, '%')}</td>"
                elif col in ("profit_factor", "sharpe_ratio", "sortino_ratio", "score"):
                    cells += f"<td>{_fmt(row_d.get(col), 3)}</td>"
                elif col == "percent_profitable":
                    cells += f"<td>{_fmt(row_d.get(col))}%</td>"
                else:
                    v = row_d.get(col)
                    cells += f"<td>{v if v is not None else '—'}</td>"

            rows_html += f"<tr {cls}>{cells}</tr>\n"
        return rows_html

    def _print_summary(self):
        from colorama import Fore, Style, init
        init(autoreset=True)
        from tabulate import tabulate

        best = self.results.best()
        if not best:
            print(f"{Fore.RED}No successful results to display.")
            return

        top = self.results.top_n(10)
        if not top:
            return

        param_keys = list(top[0].params.keys())
        headers = ["Rank"] + param_keys + [
            "Net Profit%", "Prof.Factor", "Win Rate%", "Trades", "Drawdown%", "Sharpe", "Score"
        ]

        table_data = []
        for r in top:
            row = [r.rank]
            row += [r.params[k] for k in param_keys]
            m = r.metrics
            row += [
                f"{m.net_profit:.2f}" if m.net_profit is not None else "—",
                f"{m.profit_factor:.3f}" if m.profit_factor is not None else "—",
                f"{m.percent_profitable:.2f}" if m.percent_profitable is not None else "—",
                m.total_trades or "—",
                f"{m.max_drawdown:.2f}" if m.max_drawdown is not None else "—",
                f"{m.sharpe_ratio:.3f}" if m.sharpe_ratio is not None else "—",
                f"{r.score:.4f}",
            ]
            table_data.append(row)

        print(f"\n{Fore.CYAN}{'='*60}")
        print(f"{Fore.CYAN}  PineScript Strategy Optimizer — Top Results")
        print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
        print(tabulate(table_data, headers=headers, tablefmt="rounded_outline"))
        print(f"\n{Fore.GREEN}Best score: {best.score:.4f}  |  Params: {best.params}{Style.RESET_ALL}")
