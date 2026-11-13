#!/usr/bin/env bash
# Re-runs the whole review, in dependency order. Usage:  MNQ_DATA=/path/to/exports ./run_all.sh
set -euo pipefail
cd "$(dirname "$0")"
run() { echo; echo "################ $1"; python3 -I r.py "$1"; }
python3 -I r.py load.py
run t2sim.py        # exact replica of the as-traded script (T3 on)          -> tr_base.pkl
run validate.py     # trade-for-trade check against the TradingView list
run decomp.py       # where the 12 months come from
run stress.py       # harsher fills
run defit.py        # how much depends on weekday tuning, sizing and gates
run prior.py        # same rules on 15-minute bars, three years               -> tr15.pkl
run ibstruct.py     # opening-range structure per day                         -> f15.pkl, f5.pkl
run feats.py        # daily regime features known before 10:30                -> X.pkl
run regime1.py      # tuned vs one-setting by year; T3 by weekday and side    -> tr15_uniform.pkl
run regime2.py      # which features separate good trades from bad
run regime3.py      # low/high split per year; persistence of results
run regime4.py      # thresholds per leg; the range-expansion reading on T3
run regime5.py      # shuffle test; the reading as a gate, by year
run t3deep.py       # T3 over three years: weekdays, gate, parameter plateau
run scan1.py        # one-at-a-time changes to the day script
run final1.py       # as traded vs v3.1, with the reading computed as Pine does -> exp.pkl, tr_rec.pkl
run sess1.py        # overnight sessions: opening-range behaviour
run sess2.py        # overnight search: 5 setup families x 7 windows          -> sess_scan15.pkl
run sess3.py        # detail grids of the leading families
run sess4.py        # finer grids, and 15-minute vs 5-minute bars
run sess5.py        # sensitivity to the exact window, exit time and cutoff
run sess6.py        # by month, weekday and side; correlation with the day script
run t4.py           # narrow-IB continuation idea (not adopted); LX stop-width neighbours
run final2.py       # overnight figures under the Pine rules; drawdown resampling
run onsim.py        # Python port of pine/mnq_overnight.pine                  -> on_tv15.pkl
run perm.py
run chk.py
run repdata.py      # series for the report                                   -> repdata.json
python3 -I build_report.py
