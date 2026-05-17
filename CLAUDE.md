# PineScript Strategy Optimizer

Automates TradingView's Strategy Tester to backtest thousands of parameter combinations using Selenium or the TradingView MCP server.

## Project Layout

```
main.py                   # CLI entry point
config.yaml               # All tunable settings
optimizer/
  tradingview.py          # Selenium automation layer
  optimizer.py            # Orchestrates trials
  algorithms/             # grid | random | genetic | bayesian
  parameter_space.py      # IntParameter, FloatParameter, CategoricalParameter
  scoring.py              # Metric extraction and composite scoring
  reporter.py             # HTML + CSV report generation
  results.py              # BacktestMetrics dataclass
examples/                 # Example strategy definitions (*.py + *.pine)
tradingview-mcp/          # TradingView MCP server (CDP-based, Node.js)
```

## TradingView MCP Server

The project includes the `tradingview-mcp` server (configured in `.mcp.json`). It connects to a locally running TradingView Desktop via Chrome DevTools Protocol on port 9222, exposing 78 MCP tools for chart control, Pine Script development, and backtesting.

### Launch TradingView in debug mode

**Linux:**
```bash
bash tradingview-mcp/scripts/launch_tv_debug_linux.sh
```

**macOS:**
```bash
bash tradingview-mcp/scripts/launch_tv_debug_mac.sh
```

**Windows:**
```
tradingview-mcp\scripts\launch_tv_debug.bat
```

Then verify the connection:
```
tv_health_check
```

### Key MCP tools for the optimizer workflow

| Tool | Use |
|------|-----|
| `tv_health_check` | Confirm CDP connection is alive |
| `chart_get_state` | Read current symbol, timeframe, indicators |
| `pine_set_source` | Inject updated Pine Script |
| `pine_smart_compile` | Compile and check for errors |
| `replay_start` / `replay_step` | Step through historical data |
| `data_get_study_values` | Read indicator output values |
| `capture_screenshot` | Visual snapshot of chart state |

## Selenium Optimizer (existing)

Requires TradingView credentials and a chart URL:

```bash
cp .env.example .env   # fill TV_USERNAME, TV_PASSWORD, TV_CHART_URL
python main.py --strategy examples/macd_strategy.py
python main.py --strategy examples/rsi_bb_strategy.py --algorithm genetic --trials 200
python main.py --dry-run   # validate without launching TradingView
```

## Common Commands

```bash
# Install Python deps
pip install -r requirements.txt

# Install MCP server deps
cd tradingview-mcp && npm install

# Run optimizer with genetic algorithm
python main.py --strategy examples/macd_strategy.py --algorithm genetic --metric sharpe_ratio
```
