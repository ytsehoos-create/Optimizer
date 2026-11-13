# MNQ T2 review (Nov 2026)

Research behind `pine/mnq_t2_v3_1.pine` and `pine/mnq_overnight.pine`. The findings page is
`output/2026.11.13-mnq-t2-review/dashboard.html`.

## What is here

| File | What it does |
|---|---|
| `t2sim.py` | Python port of the T2 strategy with a TradingView-style fill emulator. On the 5-minute RTH export it reproduces the TradingView trade list exactly: 151 of 151 trades, same times, prices, sizes and P&L (`validate.py`). It also carries the v3.1 switches (T3 weekdays, regime skip, T2R regime dial). |
| `seng.py` | "Session opening range" tester used for the overnight search: any range window, five setup types, conservative fills (a limit must be traded through; when a bar holds both stop and target, the stop counts). |
| `onsim.py` | Port of `pine/mnq_overnight.pine`, statement for statement, on the same fill emulator. It gives the same trades as `seng.py`. |
| `ibstruct.py`, `feats.py` | Per-day opening-range structure and the daily regime features, all known before 10:30 of the trade day. |
| everything else | One script per analysis step. `run_all.sh` lists them in order with a line on each. |

## Running it

Put the TradingView exports in one folder (names do not matter; `load.py` recognises each by bar size and session):

- 5-minute RTH chart with the RTH-anchored VWAP indicator column (`RTH VWAP`)
- 5-minute and 15-minute extended-hours charts
- 15-minute RTH chart, as far back as it goes
- 240-minute and daily charts
- the strategy's List of trades export

```bash
MNQ_DATA=/path/to/exports ./run_all.sh
```

It needs `pandas` and `numpy` only and takes a few minutes. Working files (`*.pkl`, `repdata.json`) are not committed.

## Monthly check

Re-export the charts and the trade list, run `run_all.sh`, and look at three things:

1. `validate.py` prints `mismatches 0`. If not, the script on the chart and `t2sim.py` have drifted apart.
2. `defit.py`: the "one setting for all weekdays" row over the last six months. If it turns negative while the tuned rows still look good, the tuning is doing all the work.
3. `final1.py`: the regime reading by month, and the as-traded and v3.1 rows.

## What the numbers rest on

- Exact fills exist only for the 12 months of 5-minute history (Nov 2025 – Nov 2026), which is also the window the settings were tuned on.
- Earlier years use the same rules on 15-minute bars. That understates T2R (it captures about 40% of the exact profit in the overlap year) but is the same yardstick each year. T3 enters at the 10:30 open with fixed levels, so it is exact for all three years.
- The overnight setups come from a search over about 1,400 combinations on 10.5 months of data. Treat their figures as an upper bound.
- Neither Pine file has been through TradingView's compiler. Both were checked through the Python ports above.
