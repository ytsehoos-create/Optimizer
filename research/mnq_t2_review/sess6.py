from common import *
from seng import *
pd.set_option("display.width", 250); pd.set_option("display.max_rows", 300)
e15 = load("m15_eth")[["open", "high", "low", "close"]]; e5 = load("m5_eth")[["open", "high", "low", "close"]]
def detail(lbl, t):
    t = t.copy(); t["m"] = t.date.dt.strftime("%Y-%m")
    print("==", lbl, {k: (round(v, 2) if isinstance(v, float) else v) for k, v in stats(t).items()})
    g = t.groupby("m").pnl
    print("   month:", "  ".join("%s %5.0f(%d)" % (k[2:], v, n) for (k, v), n in zip(g.sum().items(), g.size())))
    print("   months positive: %d of %d" % ((g.sum() > 0).sum(), g.ngroups))
    g = t.groupby("dow").pnl
    print("   weekday (0=Mon):", "  ".join("%d %5.0f(%d)" % (k, v, n) for (k, v), n in zip(g.sum().items(), g.size())))
    g = t.groupby("side").pnl; print("   side:", {int(k): (round(v), int(n)) for (k, v), n in zip(g.sum().items(), g.size())}, " exits:", t.why.value_counts().to_dict(),
          " avg qty %.1f  avg bars held %.1f  avg win %.0f avg loss %.0f" % (t.qty.mean(), t.bars.mean(), t.pnl[t.pnl > 0].mean(), t.pnl[t.pnl <= 0].mean()))
S = build_sessions(e15, 200, 60, 240, 15)          # 02:00-03:00 range, flat 07:00
lx = run_setup(S, "X", e=.3, s=.8, t=1.0, max_risk=400.0); detail("London pullback (15m, conservative fills, flat 07:00)", lx)
lx0 = run_setup(S, "X", e=.3, s=.8, t=1.0, max_risk=400.0, th_ticks=0); print("   with TradingView-style touch fills:", {k: round(v, 2) for k, v in stats(lx0).items()})
S5 = build_sessions(e5, 200, 60, 240, 5)
x5 = run_setup(S5, "X", e=.3, s=.8, t=1.0, max_risk=400.0); c5 = x5.date.min()
print("   Aug-Nov only: 5m bars", {k: round(v, 2) for k, v in stats(x5).items()}, " | 15m bars same dates", {k: round(v, 2) for k, v in stats(lx[lx.date >= c5]).items()})
S = build_sessions(e15, 1800, 60, 240, 15)
gm = run_setup(S, "ZC", zone=.2, s=.85, t=.3, max_risk=400.0); detail("Globex first-hour momentum (15m, conservative, flat 23:00)", gm)
gm2 = run_setup(S, "ZC", zone=.25, s=.7, t=.3, max_risk=400.0); detail("  variant zone .25 stop .7", gm2)
lx.to_pickle("lx15.pkl"); gm.to_pickle("gm15.pkl")
# do the overnight trades overlap in time with each other / diversify the RTH script?
rth = pd.read_pickle("tr_base.pkl"); rth["date"] = pd.to_datetime(rth.entry_t.dt.strftime("%Y-%m-%d"))
d = pd.concat([rth.groupby("date").pnl.sum().rename("rth"), lx.groupby("date").pnl.sum().rename("lx"), gm.groupby("date").pnl.sum().rename("gm")], axis=1).fillna(0)
d = d[d.index >= "2026-01-02"]
print("\ndaily P&L correlation since Jan 2026:\n", d.corr().round(2).to_string())
w = d.resample("W").sum(); print("weekly: RTH alone worst %.0f, losing weeks %d/%d ; all three worst %.0f, losing weeks %d/%d" % (w.rth.min(), (w.rth < 0).sum(), len(w), w.sum(axis=1).min(), (w.sum(axis=1) < 0).sum(), len(w)))
m = d.resample("ME").sum(); m["all"] = m.sum(axis=1); print(m.round(0).to_string())
