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

## T2R_v3.pine — T2R

**What it trades:** the first break of the IB from 10:30 on. At the close of the bar that breaks, it rests a limit order beyond the broken edge to fade the extension back into the IB.
- **Break up:** short at IBH + e·R, stop IBH + s·R, target IBH − t·R.
- **Break down:** long at IBL − e·R, stop IBL − s·R, target IBL + t·R.

| Weekday | Break up: entry / stop / target (× R) | Break down: entry / stop / target (× R) |
|---|---|---|
| Mon | off | off |
| Tue | 0.30 / 0.50 / 0.25 | 0.20 / 0.30 / 0.25 |
| Wed | 0.20 / 0.30 / 0.25 | 0.20 / 0.30 / 0.25 |
| Thu | 0.30 / 0.50 / 0.50 | 0.20 / 0.30 / 0.25 |
| Fri | 0.20 / 0.30 / 0.25 | 0.20 / 0.30 / 0.25 |

Other rules:
- **No trade if:**
  - the IB range is above 0.9% of the 10:30 price (large IB)
  - the breaking bar already ran 0.20R or more beyond the edge (filter B)
  - the breaking bar itself reached the T2R entry. Filter B already covers this, because every v3 entry is 0.20R or more past the edge. In the backtest, 18 breaking bars reached the entry and filter B skipped all of them. The script also checks it directly, so the rule holds if you lower an entry below the filter B setting.
  - one bar breaks both sides first
- **R1:** if T1 wins before T2R fills, T2R is cancelled. The script works out T1 itself (Zone 1 and Zone 3a, same rules and settings as the two T1 scripts) but never trades it. The table in the top-right corner shows T1's state.
- **Cancel** at 14:00 if unfilled. A later break of the other side does not cancel it.
- **Flatten** at the 15:55 bar close. One trade a day. No gap filter (that's T1 only).

**Sizing:** "Risk per trade" ($200) applies to every row unless the row sets its own risk in its last box.
- **Wednesday break-up fades risk $300** by default (the sized-up cell). Its trades risked $268–$298, at 7–13 lots.
- Every other row risked at most $200. The stop is only 0.10–0.20R, so it's usually 4–6 lots (2–15 in the backtest).
- The $300 ceiling still applies. A row set above $300 would have its trades skipped, so raise the ceiling with it.

**Chart:** MNQ1! 5-minute, RTH or ETH, margin simulation off (same as the T1 scripts).

**Reference results** (script logic with the backtest's fill rules, $200 risk with Wednesday break-up fades at $300, net of costs):

| Window | Trades | Win rate | PF | Net | Max drawdown |
|---|---|---|---|---|---|
| Sep 23 2025 – Sep 22 2026 (uploaded data) | 51 | 41.2% | 2.75 | +$11,009 | $906 |
| Oct 13 2025 – Oct 8 2026 (TradingView's window for Zone 3a) | 51 | 43.1% | 2.98 | +$11,980 | $906 |

With every row at $200 the uploaded year is +$9,557 (PF 2.70, max drawdown $781). The Wednesday size-up adds about $1,450 and $125 of drawdown.

- The trade-by-trade list is in `output/2026.09.24-mnq-ib-v3/T2R_expected_trades.csv`, including 4 trades from Sep 24 – Oct 7 2026 computed from live TradingView bars.
- **Checked against TradingView** (Oct 13 2025 – Oct 8 2026): 53 trades, 23 wins, +$12,453.30, PF 2.943, max drawdown $912.
  - That equals the 51 expected trades plus 2 on holiday half-days, which the backtest skipped: Nov 28 2025 short 10 lots, target, +$818; Dec 24 2025 short 25 lots, stopped, −$344.
  - The combined total is 53 trades, 23 wins, +$12,454.30, PF 2.943.
- Ported to Python, the script matched the v3 engine on all 51 trades: direction, fill bar, exit bar and exit reason.
  - One lot size differs (Jun 18 2026: 2 lots instead of 1) because the stop distance rounds to exactly $100 a lot.
  - The engine's exact-price total, with every row at $200, is +$9,623.
- **Levels round away from price:** each level is rounded to the tick in the direction price reaches it from. A short's stop of 29636.85 becomes 29637.00, which is where a real stop order triggers. That keeps every touch on the same bar as the backtest.

**Expected differences in TradingView's backtest:**
- **Same-bar target and stop:** TradingView may hit the target on the fill bar, or pick a different order when one bar touches both stop and target. The engine never takes a target on the fill bar and always assumes the stop. T2R's stop is tight, so this matters more than for T1.
- **15:55 flatten:** TradingView adds 1 tick of slippage.
- **Holiday half-days:** TradingView trades them; the backtest skipped them.
- **R1 uses T1's backtest rules:** when a single bar touches T1's stop and target, R1 counts it as a T1 loss, even if your live T1 trade won.

**Automation:** one alert, "alert() function calls only", pointed at your bridge.
- **Place:** at the close of the breaking bar, a limit entry with stop and target attached.
- **Cancel:** when T1 wins (R1) or at the 14:00 cutoff.
- **Exit:** at 15:55, if still in the trade.

**Running T2R with the T1 scripts: use a different account.**
- **Cancel and exit can hit T1's orders:** many bridges cancel and exit by ticker, not by order. On one account, a T2R cancel could cancel T1's resting order or its stop and target.
- **Brokers net opposite positions:** a T1 long and a T2R short in the same account would cancel out.
- **What separate scripts change:** in the combined backtest, an opposite fill closed the other trade. Separate scripts never do that.
  - T2R: about the same (+$158).
  - T1 Zone 1: −$560.
  - T2X: −$385.
  - Whole system: $21,290 instead of $22,077.
