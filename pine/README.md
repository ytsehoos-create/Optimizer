# Pine scripts

| File | Chart | What changed |
|---|---|---|
| `mnq_t2_v3_1.pine` | MNQ1! 5-minute | The T2 script (T2R + T2X, optional T3) with three additions: T3 weekday switches (Monday off), a regime reading shown in the status table, and a T3 skip while that reading is above 1.7. A T2R regime dial is included and ships at ×1 (no change). Everything else is the v3 script unchanged. |
| `mnq_overnight.pine` | MNQ1! 15-minute, extended hours | New. LX, a London-open pullback on the 02:00–03:00 ET range, and GM, a momentum trade on the 18:00–19:00 ET Globex reopen hour. Alerts are off by default. |

## Checks when you load them

- **v3.1 with T3 on**, 5-minute chart from Nov 17 2025: the Python replica gives 136 trades and +$29,866 through Nov 12 2026 (the v3 script gave 151 trades and +$28,825). With T3 off nothing changes from v3.
- **Overnight**, 15-minute chart from Jan 2 2026: the port gives LX 160 trades, +$8,767 and GM 90 trades, +$3,086 through Nov 13 2026.

Neither file has been compiled in TradingView. If the editor reports an error, the line number and message are enough to fix it. Run both on a simulator account before live use.

The research and the evidence for each default are in `research/mnq_t2_review/` and
`output/2026.11.13-mnq-t2-review/dashboard.html`.
