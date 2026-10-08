# Pine Script strategies (MNQ v3)

## T1_Zone1_v3.pine — T1 Zone 1

**Chart:** MNQ1! (or the front-month MNQ contract), 5-minute, exchange time. RTH-only or ETH chart both work. The script keeps its own 09:30–16:00 ET clock and anchors VWAP at 09:30.

**Settings:**
- **Risk per trade:** $200 by default.
- **Skip if the trade risks more than:** $300 by default, 0 turns it off. On wide-IB days even 1 contract can risk more than the risk setting. The largest in the backtest was $276, so this ceiling would never have triggered.
- **Daily label:** at 10:30 a label shows the day's setup and its risk, or why it was skipped.

**If the backtest shows no trades:** the strategy turns margin simulation off (`margin_long = 0, margin_short = 0`). TradingView's default of 100% requires the full contract value (about $60K per MNQ) in cash and silently rejects every order. Keep those two settings at 0. If a copy of the script still shows nothing, check:
- that the chart is 5-minute
- that the date range covers enough sessions
- what the daily labels say

**Reference results** (v3 engine, Sep 2025 – Sep 2026, $200 risk, net of costs): 95 trades, 65.3% win rate, PF 1.56, +$2,860, max drawdown $636.
- The trade-by-trade list is in `output/2026.09.24-mnq-ib-v3/T1_Zone1_expected_trades.csv`. Compare it with TradingView's List of Trades.
- The Pine decision logic was ported to Python and matched the engine on all 95 trades: entry, stop, target and fill bar. One lot size differs because the script rounds prices to tick first.

**Expected differences in TradingView's backtest:**
- **Stop and target on the same 5-minute bar:** TradingView guesses the order inside the bar. The engine always assumes the stop.
- **Target on the fill bar:** TradingView can hit the target on the bar that fills the entry. The engine doesn't count it.
- **15:55 flatten:** TradingView applies 1 tick of slippage. The engine doesn't.
- **Holiday half-days:** the engine skipped these; TradingView trades them.

### Automating it

1. Add the strategy to the chart. Set **Risk per trade** (default $200) and the **Ticker sent to bridge** your broker connection expects.
2. Create one alert:
   - Condition: **MNQ v3 · T1 Zone 1** → **alert() function calls only**
   - Webhook URL: your bridge (TradersPost, PickMyTrade, etc.)
   - Message: leave blank (the script writes it)
   - Expiration: open-ended
3. The script sends three kinds of messages, in TradersPost-style JSON:
   - **Place:** at the 10:25 bar close, a limit entry with stop and target attached. It's sent again if VWAP flips back to the right side.
   - **Cancel:** when VWAP moves to the wrong side of the entry, or at the 14:00 cutoff.
   - **Exit:** at the 15:55 bar close, if still in a trade.

   If your bridge uses different keys, edit only `f_msgPlace`, `f_msgCancel` and `f_msgExit`.

### Cautions
- **Run it on one account first.** Check that the bridge accepts limit plus bracket orders, cancels and exits.
- **TradingView's simulated fills and your broker's real fills can differ.** A touch fills a limit in the backtest, but not always at the broker. Reconcile them daily.
- **Half-day sessions** (e.g. day after Thanksgiving, Christmas Eve) close before 14:00 or 15:55. Switch the strategy off or set the day toggles on those dates.
- **The VWAP filter is evaluated by the script, not the broker.** It works by cancelling and re-placing the resting order, so the alert must stay active all session.

## T1_Zone3a_v3.pine — T1 Zone 3a

**What it trades:** at the 10:30 close, if that close sits 50–75% of the IB range away from IB2, it goes market toward IB1:
- **Short** when IB2 is the high: stop IBH − 0.25R, target IBL.
- **Long** when IB2 is the low: stop IBL + 0.25R, target IBH.

Other rules:
- Same gap filter (skip at 1.0% or more), sizing, $300 ceiling and 15:55 flatten as Zone 1.
- No VWAP filter and no cutoff: it enters at 10:30 or not at all.
- It never trades on the same day as Zone 1, because the two zones don't overlap.

**Chart:** same as Zone 1: MNQ1! 5-minute, RTH or ETH, margin simulation off.

**Reference results** (v3 engine, Sep 2025 – Sep 2026, $200 risk, net of costs): 21 trades, 61.9% win rate, PF 1.70, +$961, max drawdown $490. The largest risk on a single trade was $298, just under the ceiling.
- The trade-by-trade list is in `output/2026.09.24-mnq-ib-v3/T1_Zone3a_expected_trades.csv`.
- The script's logic, ported to Python, matched the engine on all 21 trades: direction, entry, stop, target, lots, exit reason and exit bar.
- **Checked against TradingView** (Oct 13 2025 – Oct 8 2026): 21 trades, 11 wins, +$169.02, PF 1.097. The engine over the same window gives 21 trades, 11 wins, +$169.89, PF 1.098.
  - The engine's window is 19 trades from the list above plus 2 new ones: Sep 29 2026 long (stopped, −$164) and Oct 6 2026 short (stopped, −$201).
  - TradingView's max drawdown ($546) is higher than the engine's ($490) because TradingView includes open-trade drawdown.

**Automation:** one alert, "alert() function calls only", pointed at your bridge.
- **Enter:** at 10:30, a market order with stop and target attached.
- **Exit:** at 15:55, if still in the trade.

**Running both T1 scripts:** add each to its own chart (or both to one) with its own alert. They can't conflict, because Zone 1 and Zone 3a never trade on the same day.
