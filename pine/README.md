# Pine Script strategies (MNQ v3)

**Closing time (all scripts):** every open trade is closed at the 15:55 bar close (4:00 pm ET), inside a 4:30 pm deadline. Two safety nets:
- **RTH-only charts:** there's no bar after 15:55, so a "Flatten at" setting later than 15:55 is treated as 15:55. To hold past 4:00, use an extended-hours chart.
- **Carried-over trades:** if a position is somehow still open at the next 9:30 bar, the script closes it immediately and sends an exit.

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

## T2X_v3.pine — T2X

**What it trades:** the retrace after the first IB break, in the break's direction.
1. **Break:** the first bar from 10:30 on that trades beyond the IB sets the direction.
2. **Arm:** the first later bar that *closes* back inside the IB arms the setup.
3. **Order:** from the next bar, a limit order rests inside the IB:
   - **Break up:** long at IBH − e·R, stop IBH − s·R, target IBH + t·R.
   - **Break down:** short at IBL + e·R, stop IBL + s·R, target IBL − t·R.

| Weekday | Break up, long: entry / stop / target (× R) | Break down, short: entry / stop / target (× R) |
|---|---|---|
| Mon | 0.10 / 0.30 / 0.20 | off |
| Tue | 0.20 / 0.60 / 0.40 | 0.30 / 0.60 / 0.25 |
| Wed | 0.20 / 0.60 / 0.30 | 0.50 / 0.60 / 0.25 |
| Thu | off | off |
| Fri | 0.50 / 0.60 / 0.20 | 0.40 / 0.60 / 0.25 |

Rules that depend on T1 (the script works out T1 itself, with the same rules and settings as the T1 scripts, and never trades it):
- **R3:** T1 lost → cancel T2X.
- **R7:** on Mondays, T2X only trades once T1 is in. Until then the order is held back. If price touches the entry while it's held back, the day is over.
- **R2 safeguard:** T1 won at the opposite edge from T2X's break → cancel T2X. This never happened in the backtest.

Other rules:
- **No trade if** the IB range is above 0.9% of the 10:30 price, or one bar breaks both sides first. There's no filter B for T2X.
- **Cancel** at 13:00 if unfilled, or if the setup never armed. A later break of the other side does not cancel it.
- **Flatten** at the 15:55 bar close. One trade a day.

**Sizing:** "Risk per trade" ($200) applies to every row unless the row sets its own risk in its last box. **Wednesday breakout longs default to $300** (sized-up cell); every other row follows the base.
- **Stop distances range from 0.10R to 0.40R** (stop minus entry), so lots vary a lot by row:
  - Tue breakout longs (0.40R stop): mostly 1 lot. Wed breakout longs, at $300: mostly 2 lots.
  - Wed breakdown shorts and Fri breakout longs (0.10R stop): 3–9 lots.
- **The largest risk at $200 was $206** (1 lot), so the $300 ceiling never triggered.

**Order timing:** this script processes orders from the bar *after* they're placed. The T1 and T2R scripts can fill at the placing bar's close; this one can't.
- **Why:** the arming bar often closes past the T2X entry (14 times in the backtest). The engine then fills at the next bar's open, and so does this script.
- **The 15:55 flatten** still fills at that bar's close.

**Reference results** (script logic with the backtest's fill rules, $200 risk with Wednesday breakout longs at $300, net of costs):

| Window | Trades | Win rate | PF | Net | Max drawdown |
|---|---|---|---|---|---|
| Sep 23 2025 – Sep 22 2026 (uploaded data) | 43 | 65.1% | 4.64 | +$8,842 | $586 |
| Oct 13 2025 – Oct 8 2026, as TradingView will show it | 44 | 65.9% | 5.14 | +$10,043 | $586 |

With every row at $200, the uploaded year was +$8,259.

- **What the TradingView window includes:** the expected list plus 1 half-day trade the backtest skipped, Fri Nov 28 2025: long 10 lots, target, +$1,278.
- **Recent trades:** the trade-by-trade list is in `output/2026.09.24-mnq-ib-v3/T2X_expected_trades.csv`. It includes 2 trades computed from live TradingView bars: Sep 30 2026 long, stopped, −$170; Oct 5 2026 long, target, +$269.
- **Match against the engine:** ported to Python, the script matched the v3 engine (with separate scripts, so no reversals) on 43 of 44 trades: direction, fill bar, exit bar and exit reason.
  - **Jan 5 2026 is skipped by the script.** It's a Monday where T1 and T2X filled on the same bar. The engine processes T1 first and takes the T2X (−$93). The script only releases the Monday order after T1 is in, so it counts the touch as coming first.
  - **Mar 11 2026 trades 5 lots instead of 4,** because the stop distance rounds to exactly $40 a lot.
  - The engine's total is 44 trades, +$7,845.

- **Checked against TradingView** (Oct 13 2025 – Oct 8 2026, run before the Wednesday change, every row at $200): 44 trades, 29 wins, +$9,452.82, PF 5.108, max drawdown $588. That's the expected +$9,460.32 less exactly $7.50: TradingView's 1 tick of slippage on the 15 contracts flattened at 15:55.

**Expected differences in TradingView's backtest:** same as T2R. TradingView may take a target on the fill bar or pick a different order inside a bar. It adds 1 tick of slippage at the 15:55 flatten. It trades holiday half-days, which you flatten by hand.

**Automation:** one alert, "alert() function calls only", pointed at your bridge.
- **Place:** when the setup arms, or on Mondays once T1 is in. A limit entry with stop and target attached.
- **Cancel:** on R3, R2 or the 13:00 cutoff.
- **Exit:** at 15:55, if still in the trade.

As with T2R, run it on its own account. Bridges often cancel and exit by ticker, and brokers net opposite positions.

## T2_combined_v3.pine — T2R + T2X on one account

**When to use it:** to run T2R and T2X on the **same account**. It holds one position at a time. T1 isn't traded; the script works out T1 internally for the R1, R2, R3 and R7 gates. On separate accounts, use `T2R_v3.pine` and `T2X_v3.pine` instead.

**Rules:** same as the T2R and T2X scripts (levels, skips, gates, 14:00 / 13:00 cutoffs, 15:55 flatten), plus these account rules:
1. **Aligned targets.** While the account is flat and both orders are resting, each order's target becomes the other's entry if that's closer. A fill can then only hand off at a single price: the first trade takes profit exactly where the second enters. On Nov 28 2025, for example, T2X's long took profit at 26487.00 on the same bar T2R's short entered at 26487.00.
2. **Nothing changes at the broker while a trade is on.**
   - **T2X waits:** if it arms during a T2R trade, it's placed once the account is flat.
   - **Cancels wait too:** an order due for cancelling (cutoff, R1, R2, R3) stays until the account is flat. If it fills through the handoff in the meantime, the script exits it at that bar's close. This happened 5 times in the backtest year.
3. **Once flat,** the script cancels everything resting and re-places what's still valid.

The point of rule 2: every cancel the script sends happens while the account is flat, so a bridge whose cancel clears the whole ticker can never remove a live trade's stop and target.

**Sizing:** "Risk per trade" applies to every row unless the row sets its own. Two Wednesday rows default to $300, as in the standalone scripts: T2R break-up (short fade) and T2X break-up (long).

**Reference results** (script logic with the backtest's fill rules, defaults: $200, with Wednesday T2R and T2X breakouts at $300, net of costs):

| Window | Trades | Win rate | PF | Net | Max drawdown |
|---|---|---|---|---|---|
| Sep 23 2025 – Sep 22 2026 (uploaded data) | 99 | 53.5% | 3.34 | +$20,139 | $677 |
| Oct 13 2025 – Oct 8 2026 | 99 | 54.5% | 3.51 | +$21,065 | $677 |

- **Half-days:** TradingView will also trade the two holiday half-days, which add 3 trades and +$1,752. Expect about 102 trades and +$22,817 for Oct 13 – Oct 8.
- **Trade list:** `output/2026.09.24-mnq-ib-v3/T2_combined_expected_trades.csv`, including 6 trades from live TradingView bars (Sep 24 – Oct 7 2026).
- **Checks:** on days when only one setup trades, the script's trades match the standalone T2R and T2X scripts exactly (36 and 23 trades). On the 20 days both traded, no two positions were ever open at once.

**Expected differences in TradingView's backtest:** same as the T2R and T2X scripts.

**Fixed Oct 10 2026: positions not closing at 15:55.** The first version sent its 15:55 flatten and then cancelled all resting orders in the same bar. On days when a held-back cancel was still waiting (Aug 7, Aug 12 and Sep 2 2026), the cancel also removed the flatten order and the trade's stop and target. The trade then stayed open, and no new trades were placed afterwards. The script now cancels first and then flattens. Re-add or update the script if you added the first version.

**Automation:** one alert, "alert() function calls only". Messages:
- **Place:** limit entry with stop and target.
- **Cancel:** only ever sent while flat, immediately followed by re-placing whatever is still valid.
- **Exit:** 15:55, or a cancelled order that filled.
