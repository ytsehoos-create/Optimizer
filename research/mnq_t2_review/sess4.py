from common import *
from seng import *
pd.set_option("display.width", 250); pd.set_option("display.max_rows", 300)
# A. engine check on RTH: one-setting T2R / T2X with no gates, t2sim (TradingView fills) vs engine (conservative fills)
U = default_params(); U.update(ibSizeOn=False, useR1=False, useR2=False, useR3=False, useR7=False, alignOn=False, largeIB=0.9)
for k in ("ru", "rd"): U[k].update(on=[True]*5, e=[.2]*5, s=[.3]*5, t=[.25]*5, rk=[0]*5)
U["xu"].update(on=[False]*5); U["xd"].update(on=[False]*5)
tr, _ = run(m5(), U); print("t2sim  T2R-only one-setting, no gates: n=%d net=%.0f pf=%.2f" % (len(tr), tr.pnl.sum(), pf(tr.pnl)))
S = build_sessions(m5()[["open", "high", "low", "close"]], 930, 60, 325, 5)
x = run_setup(S, "R", e=.2, s=.3, t=.25, cutoff_bars=(14 * 60 - 10 * 60 - 30) // 5 - 1, ib_max=0.9, max_risk=300.0, th_ticks=0); print("engine R (touch fills):               n=%d net=%.0f pf=%.2f" % (len(x), x.pnl.sum(), stats(x)["pf"]))
x = run_setup(S, "R", e=.2, s=.3, t=.25, cutoff_bars=(14 * 60 - 10 * 60 - 30) // 5 - 1, ib_max=0.9, max_risk=300.0, th_ticks=1); print("engine R (1 tick through):            n=%d net=%.0f pf=%.2f" % (len(x), x.pnl.sum(), stats(x)["pf"]))

e15 = load("m15_eth")[["open", "high", "low", "close"]]; e5 = load("m5_eth")[["open", "high", "low", "close"]]
cut = pd.Timestamp("2026-05-13"); c5 = e5.index[0].tz_localize(None).normalize() + pd.Timedelta(days=1)
def rep(lbl, S15, S5, kind, **g):
    t15 = run_setup(S15, kind, max_risk=400.0, **g)
    kw = dict(g)
    if "cutoff_bars" in kw and kw["cutoff_bars"] is not None: kw["cutoff_bars"] = kw["cutoff_bars"] * 3 + 2
    t5 = run_setup(S5, kind, max_risk=400.0, **kw)
    a = stats(t15[t15.date < cut]); b = stats(t15[t15.date >= cut]); al = stats(t15)
    o15 = stats(t15[t15.date >= c5]); o5 = stats(t5[t5.date >= c5])
    print("%-34s all n=%3d net=%6.0f pf=%.2f dd=%6.0f win=%2.0f%% | Jan-May %6.0f pf=%.2f | last6m %6.0f pf=%.2f | Aug-Nov: 15m %6.0f pf=%.2f (n=%d) vs 5m %6.0f pf=%.2f (n=%d)" % (
        lbl, al["n"], al["net"], al["pf"], al["dd"], al["win"], a["net"], a["pf"], b["net"], b["pf"], o15["net"], o15["pf"], o15["n"], o5["net"], o5["pf"], o5["n"]))
    return t15, t5
print("\n== London 03:00-04:00 range, FADE the first-break extension (R). window to 09:25")
S15 = build_sessions(e15, 300, 60, 325, 15); S5 = build_sessions(e5, 300, 60, 325, 5)
for e in (0.3, 0.4, 0.5, 0.6, 0.75):
    for w in (0.2, 0.3):
        for t in (0.0, 0.25, 0.5):
            rep("e=%.2f s=%.2f t=%.2f" % (e, e + w, t), S15, S5, "R", e=e, s=round(e + w, 2), t=t)
print("\n== Europe 02:00-03:00 range, retrace CONTINUATION (X). window to 09:25")
S15 = build_sessions(e15, 200, 60, 385, 15); S5 = build_sessions(e5, 200, 60, 385, 5)
for e in (0.2, 0.3, 0.4, 0.5):
    for s in (0.7, 0.8, 1.0):
        for t in (0.5, 1.0, 1.5):
            rep("e=%.2f s=%.2f t=%.2f" % (e, s, t), S15, S5, "X", e=e, s=s, t=t)
print("\n== Globex 18:00-19:00 range, first-hour MOMENTUM (ZC). window to 01:00")
S15 = build_sessions(e15, 1800, 60, 360, 15); S5 = build_sessions(e5, 1800, 60, 360, 5)
for z in (0.15, 0.2, 0.25):
    for s in (0.5, 0.6, 0.7, 0.85):
        for t in (0.2, 0.3, 0.5):
            rep("zone=%.2f s=%.2f t=%.2f" % (z, s, t), S15, S5, "ZC", zone=z, s=s, t=t)
