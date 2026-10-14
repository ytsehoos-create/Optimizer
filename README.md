# PineScript Strategy Optimizer

Automates TradingView's Strategy Tester to backtest thousands of parameter combinations and surface the settings with the best outcomes.

## Features

- **4 search algorithms** — Grid, Random, Genetic (DEAP), Bayesian (scikit-optimize)
- **Multiple metrics** — Net Profit, Profit Factor, Win Rate, Sharpe, Sortino, Calmar, or a weighted composite
- **Browser automation** — Selenium drives TradingView; no private API needed
- **Rich reporting** — dark-themed HTML report + CSV export
- **Extensible** — add any strategy by defining a `ParameterSpace` file

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure credentials

Copy `.env.example` to `.env` and fill in your details:

```bash
cp .env.example .env
# edit .env
TV_USERNAME=your_email_or_username
TV_PASSWORD=your_password
TV_CHART_URL=https://www.tradingview.com/chart/XXXXXXXX/
```

Or set them in `config.yaml` under `tradingview:`.

### 3. Add your PineScript strategy to TradingView

Paste one of the example scripts from the top of each `examples/*.py` file into the Pine Editor, add it to your chart, and copy the chart URL into `.env`.

### 4. Define your parameter space

Create a file like `examples/my_strategy.py`:

```python
from optimizer import ParameterSpace, IntParameter, FloatParameter, CategoricalParameter

PARAMETER_SPACE = ParameterSpace([
    IntParameter(
        name="fast_length",
        label="Fast Length",   # must match EXACTLY the Inputs dialog label
        start=5, stop=50, step=5,
    ),
    FloatParameter(
        name="stop_pct",
        label="Stop Loss %",
        start=1.0, stop=5.0, step=0.5, decimals=1,
    ),
    CategoricalParameter(
        name="source",
        label="Source",
        options=["close", "hl2", "hlc3"],
    ),
])
```

### 5. Run the optimizer

```bash
# Grid search (exhaustive) using the MACD example
python main.py --strategy examples/macd_strategy.py

# Genetic algorithm for a large space
python main.py --strategy examples/macd_strategy.py --algorithm genetic

# Random search, 200 trials, maximize Sharpe Ratio
python main.py --strategy examples/rsi_bb_strategy.py --algorithm random --trials 200 --metric sharpe_ratio

# Validate setup without launching TradingView
python main.py --strategy examples/macd_strategy.py --dry-run

# Headless browser
python main.py --strategy examples/macd_strategy.py --headless
```

## Algorithms

| Algorithm | Best for | Config key |
|-----------|----------|------------|
| `grid` | Small spaces (< ~1,000 combos) | `optimization.algorithm: grid` |
| `random` | Medium spaces | `optimization.algorithm: random` |
| `genetic` | Large spaces with clear fitness landscape | `optimization.algorithm: genetic` |
| `bayesian` | Expensive evaluations, needs `scikit-optimize` | `optimization.algorithm: bayesian` |

## Metrics

Set `optimization.metric` in `config.yaml` or via `--metric`:

| Key | Description |
|-----|-------------|
| `net_profit` | Net profit % |
| `profit_factor` | Gross profit / gross loss |
| `percent_profitable` | Win rate % |
| `sharpe_ratio` | Sharpe ratio |
| `sortino_ratio` | Sortino ratio |
| `calmar_ratio` | Calmar ratio |
| `max_drawdown` | Max drawdown % (lower is better) |
| `composite` | Weighted combination (configure weights in YAML) |

## Output

Reports are saved to `reports/` by default:

- `results_YYYYMMDD_HHMMSS.html` — Interactive dark-themed report with top results highlighted
- `results_YYYYMMDD_HHMMSS.csv` — Full results table for further analysis

## Configuration

Edit `config.yaml` to control every aspect:

```yaml
tradingview:
  headless: false
  backtest_wait: 8        # seconds to wait after changing inputs

optimization:
  algorithm: genetic
  metric: composite
  composite_weights:
    net_profit: 0.30
    profit_factor: 0.25
    percent_profitable: 0.20
    sharpe_ratio: 0.15
    max_drawdown: -0.10   # negative = penalize large drawdown

  genetic:
    population_size: 40
    generations: 30

reporting:
  top_n: 25
  formats: [html, csv]
```

## How It Works

1. Selenium launches Chrome/Firefox and logs in to TradingView
2. Navigates to your chart URL and opens the Strategy Tester panel
3. For each parameter combination the optimizer wants to test:
   - Opens the strategy Settings dialog
   - Sets each input field to the trial value
   - Clicks OK and waits for the backtest to recalculate
   - Reads performance metrics from the Strategy Tester overview
4. Scores each trial, tracks the best, and moves on
5. Generates an HTML report and CSV when done

## Connection Test Strategy

`strategies/connection_test.pine` is not a trading strategy. It checks the alert → webhook → bridge → funded-account chain before you run the live strategy. On a 1-minute chart it sends one order alert every 2 minutes, alternating entry and exit. It stops flat after 5 round trips.

1. Add it to a 1-minute chart of the live symbol. The default messages are NinjaView JSON, so set **NinjaTrader account(s)** (e.g. `Sim101`) and **NinjaTrader instrument** (e.g. `MNQ 12-26`, not `MNQ1!`). For another bridge, replace the **Entry message** and **Exit message** inputs; tokens such as `%instrument%`, `%action%` and `%qty%` are filled in by the script.
2. Create an alert on it: **Order fills only**. Set the message to `{{strategy.order.alert_message}}` and use the same webhook URL as the live alert.
3. Confirm each account receives every order. Then delete the alert and check that every account is flat.

The status panel on the chart shows the exact message the next alert will send.

On history it shows a preview of the last 4 hours of the schedule so the Strategy Tester has trades to inspect. Historical fills never send alerts, and the preview is closed flat before live bars begin. It also respects a trading window (default 18:00–15:55 ET) and closes any position left open outside that window.

## NinjaView: alert fires but no order

`tools/ninjaview_check.py` (standard library only) finds which link is broken: TradingView → NinjaView webhook → NinjaView add-on → NinjaTrader.

```bash
# Check a message: paste it from TradingView's alert log
python tools/ninjaview_check.py lint '{"alert":"market buy","account":"Sim101","ticker":"MNQ 12-26","qty":"1"}'

# Send a Sim order straight to NinjaView, skipping TradingView
python tools/ninjaview_check.py send --url "<NinjaView webhook URL>" --account Sim101 --instrument "MNQ 12-26" buy
python tools/ninjaview_check.py send --url "<NinjaView webhook URL>" --account Sim101 --instrument "MNQ 12-26" close
```

- **Test order appears in NinjaTrader, but TradingView alerts don't trade:** the fault is on the TradingView side. Check the alert's Webhook URL box is ticked and has the current URL (Rotate in NinjaView invalidates the old one). Webhooks also need 2FA on your TradingView account, and the message must be `{{strategy.order.alert_message}}`.
- **Test order reaches NinjaView (HTTP 200) but no order appears:** the fault is between NinjaView and NinjaTrader. NinjaTrader must be open and connected, the NinjaView add-on must show Connected, and Auto-Trade must be on. The account must be the NinjaTrader account **Name** (not Display Name), and the instrument must be the current contract.
- **Using the Chrome extension instead of a webhook:** Chrome must stay open on TradingView with the extension signed in (green check). From the NinjaTrader PC, `--url http://127.0.0.1:5001` tests the local add-on directly.

`send` refuses non-Sim accounts unless you pass `--live`, and won't send a message that fails `lint` unless you pass `--force`. Keep the webhook URL private: anyone who has it can trade your accounts.

## Notes

- **TradingView account required** — a free account works for some strategies; Pro/Pro+ removes the 1-bar limit on backtests
- **Speed** — each trial takes ~10–20 seconds (network + recalculation). A 500-trial random search takes ~2–3 hours
- **Stability** — TradingView's DOM can change. If selectors break, adjust them in `optimizer/tradingview.py → _SEL`
- **`backtest_wait`** — increase this value on slow connections or complex strategies
