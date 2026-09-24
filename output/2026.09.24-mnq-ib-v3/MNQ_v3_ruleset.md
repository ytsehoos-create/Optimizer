# MNQ IB Suite — v3 Ruleset (2026-09-24)

MNQ 5-min, RTH 09:30–16:00 ET. $2/pt. Lots = max(1, floor(300 ÷ (risk_pts × 2))).
IB = 09:30–10:30. R = IB range (IBH − IBL). All levels are multiples of R.

## Performance (MNQ1! 5m, 2025-09-23 → 2026-09-22, 249 sessions, net of $1.24/contract RT + 1 tick stop slippage)

| | v1 baseline | **v3** |
|---|---|---|
| Net P&L (in-sample, full year) | $20,353 | **$34,536** |
| **Walk-forward blind estimate** (select on 3 quarters, trade the 4th) | — | **$25,039** |
| Trades / WR / PF | 186 / 59.1% / 2.02 | 212 / 59.9% / 2.55 |
| Max drawdown | $1,687 | **$1,490** |
| Net ÷ max DD | 12× | 23× |
| Quarters | 2.7K / 10.0K / 4.3K / 3.3K | 7.4K / 12.1K / 7.5K / 7.5K |
| Profitable months | 9/13 | 12/13 (worst −$267) |

Plan on the walk-forward figure (~$25K), not the full-year fit.

---

## 1. Session state machine (the order of events is never assumed)

Every 5-min bar is processed in this fixed order. Every rule reads only what is known at that bar.

1. **Fills.** Pending limit orders fill if the bar touches the level (at the bar open if it gaps through). Gates (section 5) are checked at the moment of the fill.
2. **Exits.** Stop, then target. If a bar touches both, it counts as a stop. No target is counted on the bar the order fills. Flatten everything at the 15:55 bar close.
3. **Break bookkeeping.** The first bar whose high > IBH or low < IBL is the **first break**. The T2R and T2X orders are created at its close and are live from the next bar. If that bar breaks both sides, there is no T2R or T2X that session.
4. **T2X arming.** The T2X limit goes live only after a later bar **closes back inside the IB**.

### Out-of-sequence rules

| Situation | v3 rule | Evidence |
|---|---|---|
| IB breaks before the T1 limit fills | **Keep the T1 order live** until 14:00. | 30/91 Zone 1 fills came after the break (+$2,707). Cancelling cost −$4,929 and lost in all 4 quarters. |
| An order fills opposite to an open position (e.g. T2X long while T2R short is open) | **Reverse.** Close the open position at the new fill price, then hold only the new one. Never hold opposing positions. | Blocking the new entry cost −$3,059. The hedged v1 simulation isn't executable in one account. 14 reversals net +$12.2K. |
| T2X fills before T2R | Allowed. If T2R later fills, the reversal rule applies. | 6 sessions, +$3,204 |
| Opposite side breaks later (double break) | Pending post-break orders **stay live**. Open trades are managed by their own stops. | Cancelling improved only 1 of 4 quarters (+$248). 17 post-break trades on double-break days netted +$4,210. |
| T1 and T2X in the same direction | Stacking allowed. | — |
| A gated setup is still pending or open when the gate is checked | It counts as not resolved. Only closed outcomes trigger R1 or R3. | — |

---

## 2. T1 — Initial Balance second-side (armed 10:30)

IB2 = the IB extreme formed last. Closing zone = |10:30 close − IB2| ÷ R × 100.
**Gap filter:** skip T1 if |RTH open − prior RTH close| ≥ **1.0%**.

| Zone | Condition | Direction | Entry | Stop | Target |
|---|---|---|---|---|---|
| **Zone 1** | zone ≤ 25% | LONG if IB2 = IBH | limit IBH − 0.25R | IBH − 0.55R | IBH |
| | | SHORT if IB2 = IBL | limit IBL + 0.20R | IBL + 0.45R | IBL |
| **Zone 3a** | 50% ≤ zone ≤ 75% | toward IB1 | market at 10:30 close | IB2 ∓ 0.25R | IB1 boundary |

- **VWAP filter (Zone 1 only):** at fill, long needs VWAP below entry; short needs VWAP above entry.
- Zone 1 limit cancels at **14:00** if unfilled. No re-entries.
- **Skip** zones 25–50% and 75–100%.
- **Zone 3a stays on.** Removing it adds about $1.8K but raises max DD from $1,490 to $2,350; it's the portfolio's hedge.

## 3. T2R — first-break extension fade

**Filters (all must pass):** first break before 16:00 · IB ≤ **0.9%** of the 10:30 price · first-break bar extends **< 0.20R** past the IB edge.
Breakout (BO) = short fade above IBH. Breakdown (BD) = long fade below IBL.

| Day | Direction | Entry | Stop | Target |
|---|---|---|---|---|
| Mon | — | off | | |
| Tue | BO short | IBH + 0.30R | IBH + 0.50R | IBH − 0.25R |
| Tue | BD long | IBL − 0.20R | IBL − 0.30R | IBL + 0.25R |
| Wed | BO short | IBH + 0.20R | IBH + 0.30R | IBH − 0.25R |
| **Wed** | **BD long (new)** | IBL − 0.20R | IBL − 0.30R | IBL + 0.25R |
| Thu | BO short | IBH + 0.30R | IBH + 0.50R | IBH − 0.50R |
| Thu | BD long | IBL − 0.20R | IBL − 0.30R | IBL + 0.25R |
| Fri | BO short | IBH + 0.20R | IBH + 0.30R | IBH − 0.25R |
| **Fri** | **BD long (new)** | IBL − 0.20R | IBL − 0.30R | IBL + 0.25R |

Place the limit at the close of the first-break bar. Cancel at **14:00**. One entry, no re-entries.

## 4. T2X — post-break retrace resumption

**Filters:** IB ≤ **0.9%** of the 10:30 price. Arms after a bar closes back inside the IB (section 1, step 4).
BO = long (retrace down into the IB, target above IBH). BD = short (retrace up into the IB, target below IBL).

| Day | Direction | Entry | Stop | Target |
|---|---|---|---|---|
| Mon | BO long | IBH − 0.10R | IBH − 0.30R | IBH + 0.20R |
| Tue | BO long | IBH − 0.20R | IBH − 0.60R | IBH + 0.40R |
| Tue | BD short | IBL + 0.30R | IBL + 0.60R | **IBL − 0.25R** |
| Wed | BO long | IBH − 0.20R | IBH − 0.60R | IBH + 0.30R |
| Wed | BD short | IBL + 0.50R | IBL + 0.60R | **IBL − 0.25R** |
| Thu | — | off | | |
| Fri | BO long | IBH − 0.50R | IBH − 0.60R | IBH + 0.20R |
| Fri | BD short | IBL + 0.40R | IBL + 0.60R | **IBL − 0.25R** |

Breakdown-short targets moved 0.20R → 0.25R past IBL. Cancel at **13:00**. One entry, no re-entries.

## 5. Cross-setup gates (checked when the gated order would fill)

| Rule | v3 | Condition → effect |
|---|---|---|
| R1 | **ON** | T1 already closed as a **winner** → cancel pending T2R (21 vetoes) |
| R2 | info | T1 won → keep T2X (no action) |
| R3 | **ON** | T1 already closed as a **loser** → cancel pending T2X (6 vetoes). Turning it off lost money in all 4 quarters. |
| R4 / R5 | info | T2R loss / no fill → keep T2X (no action) |
| **R6** | **REMOVED** | "T1 & T2R both out → skip T2X". At the moment T2X fills, "not filled yet" isn't the same as "out", so the rule vetoed good trades. +$8.5K net, better in 3 of 4 quarters, and chosen in all 4 walk-forward folds. |
| R7 | **ON** | Monday and T1 not filled → skip T2X (8 vetoes) |

---

## 6. What changed from v1, and why

| Change | Net effect | Walk-forward |
|---|---|---|
| Reverse on opposite fills (executable) | +$917 vs v1's hedged simulation | required for real execution |
| R6 removed | +$8.5K | chosen in 4/4 folds |
| T2R Fri breakdown fade | +$2.95K | chosen in 4/4 folds |
| T2R Wed breakdown fade | +$2.0K | chosen in 3/4 folds |
| First-break filter 0.25R → 0.20R | +$0.5K, lower DD | chosen in 3/4 folds |
| T2X breakdown target 0.20R → 0.25R | +$0.5K | chosen in 3/4 folds |

**Tested and rejected** (fewer than 3 of 4 quarters improved, or DD cost too high):
- gap 1.25%
- VWAP off
- per-day large-IB thresholds
- flat 1.2% / 1.5% large-IB thresholds
- cancel T1 on break
- cancel on double break
- touch-armed T2X
- R1 off
- Monday T2R
- Thursday T2X
- the infographic's per-cell grids (fit on the test data, so not a clean candidate)
- a free grid search (blind −$2.3K)

## 7. Edgeful cross-reference (NQ, 5-min, 60-min IB, wick breaks, 2025-09-26 → 2026-09-22)

- **Data validation:** the chart's IB break type matches Edgeful on 246/248 sessions (99.2%). Retracement depth after the break has a median difference of 0.45 pts. Edgeful's 25/50/75% hit rates: breakouts 58/30/11%, breakdowns 71/44/12%. The chart gives 63/30/10% and 76/42/13%.
- **Breakdowns retrace further than breakouts** (25%-into-IB hit rate 71% vs 58%). This supports fading breakdowns on more days: T2R BD targets sit at +0.25R, which is exactly the 25% level.
- **By weekday (breakdown, 25% retrace):** Wed 79%, Fri 75%, Mon 71%, Thu 68%, Tue 61%. The two strongest days are the new v3 cells. Tuesday is weakest, and T2R Tue BD is v3's only losing cell (−$149, n=6). It stays in (dropping it improved only 2/4 quarters) but is **on watch**.
- **By weekday (breakout, 25% retrace):** Mon 37.5% (lowest) supports Monday T2R off and the shallow Monday T2X entry (0.10R). Fri 78% (highest) supports Friday T2R BO and the deep Friday T2X entry (0.50R).
- **Double-break rate is highest on Tuesdays (21%)**, which is consistent with Tuesday's weaker fades.

## 8. Risks and fragility

- **Concentration:** T2X Wed BD made +$7.2K from 6 trades (1:7 reward-to-risk cell, about 8–9 lots). Without it, v3 nets about $27K.
- Several cells have n ≤ 6, so their per-cell P&L is anecdotal.
- 5-min bars can't show which of stop or target came first inside a bar. The engine assumes the stop (conservative).
- One year of data, one market regime. Re-run `python mnq_v3_select.py` as new months arrive.

Files: `mnq_v3.py` (engine; `V1`, `V2I`, `V3` params) · `mnq_v3_select.py` (walk-forward selection) · `output/2026.09.24-mnq-ib-v3/` (trades, fold logs, params).
