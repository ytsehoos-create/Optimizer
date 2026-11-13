# Pine scripts

| File | Chart | What changed |
|---|---|---|
| `mnq_t2_v3_1.pine` | MNQ1! 5-minute | The T2 script (T2R + T2X, optional T3) with three additions: T3 weekday switches (Monday off), a regime reading shown in the status table, and a T3 skip while that reading is above 1.7. A T2R regime dial is included and ships at ×1 (no change). Everything else is the v3 script unchanged. |
| `mnq_overnight.pine` | MNQ1! 15-minute, extended hours | New. LX, a London-open pullback on the 02:00–03:00 ET range, and GM, a momentum trade on the 18:00–19:00 ET Globex reopen hour. Alerts are off by default. |

## Checks when you load them

- **v3.1 is your script plus the additions.** With T3 on, T3 Monday on and "T3: no trade while expanding" off, the Strategy Tester on the 5-minute chart must show the v3 result again: 151 trades, +$28,825.32 through Nov 12 2026. All 152 inherited input defaults were checked against the saved "T2 Combo" script.
- **v3.1 defaults with T3 on**, same chart: the Python replica gives 136 trades and +$29,866. With T3 off nothing changes from v3.
- **Overnight**, 15-minute extended-hours chart from Jan 2 2026: the port gives LX 160 trades, +$8,767 and GM 90 trades, +$3,086 through Nov 13 2026.

## What TradingView has and has not seen

- The overnight script compiled in TradingView. The connector used for the check runs the regular session only, so it was not backtested there.
- The new v3.1 code (T3 weekday switches, regime arrays, T3 skip, T2R dial, status-table row) compiled in TradingView, and its regime reading matched the Python value on five dates to four decimals (for example 1.5828 on Nov 10 2026).
- The whole v3.1 file was not compiled in one piece. If the editor reports an error, the line number and message are enough to fix it.

Run both on a simulator account before live use.

The research and the evidence for each default are in `research/mnq_t2_review/` and
`output/2026.11.13-mnq-t2-review/dashboard.html`.
