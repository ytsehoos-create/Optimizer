from common import *
import common
def exp_pine(df, n=20):
    """EXP20 exactly as the Pine script computes it: for each completed full RTH day, (RTH high-low)/(IB high-low);
    today's value = median of the previous n stored days (na until n are stored). Half days (no bar at/after 15:00) are not stored."""
    hm = df.index.hour * 100 + df.index.minute
    d = df[(hm >= 930) & (hm < 1600)]
    out = {}; hist = []
    for day, g in d.groupby(d.index.strftime("%Y-%m-%d")):
        out[day] = float(np.median(hist[-n:])) if len(hist) >= n else None
        ghm = g.index.hour * 100 + g.index.minute
        ib = g[ghm < 1030]
        if ghm.max() >= 1500 and len(ib) > 0:
            R = ib.high.max() - ib.low.min()
            if R > 0: hist.append((g.high.max() - g.low.min()) / R)
    return out
E5 = exp_pine(m5()); E15 = exp_pine(m15())
both = [(E5[k], E15[k]) for k in E5 if E5[k] is not None and E15.get(k) is not None]
print("EXP20 from the 5m chart vs from the 15m file: days compared %d, max abs diff %.4f ; first day with a value on the 5m chart: %s" % (len(both), max(abs(a - b) for a, b in both), min(k for k in E5 if E5[k] is not None)))
B = default_params(); B["t3On"] = True
_prior = m15()[m15().index < m5().index[0]]
def line(lbl, P, prior=True, ex=E5):
    tr, _ = run(m5(), P, exp20=ex)
    a, b = tr[tr.entry_t < CUT6], tr[tr.entry_t >= CUT6]
    s = "%-58s 12m n=%3d net=%6.0f pf=%.2f dd=%5.0f | first6 %6.0f | LAST6 n=%2d %6.0f pf=%.2f dd=%5.0f" % (lbl, len(tr), tr.pnl.sum(), pf(tr.pnl), maxdd(tr), a.pnl.sum(), len(b), b.pnl.sum(), pf(b.pnl), maxdd(b))
    if prior:
        tp, _ = run(_prior, P, bar_min=15, exp20=E15)
        s += " | prior2y~ n=%3d %6.0f pf=%.2f dd=%5.0f" % (len(tp), tp.pnl.sum(), pf(tp.pnl), maxdd(tp))
    print(s); return tr
t0 = line("AS TRADED (defaults + T3 on)", B)
P = copy.deepcopy(B); P["t3Days"] = [False, True, True, True, True]; line("1) T3 Monday off", P)
P.update(expMax=1.7, t3ExpOff=True); t1 = line("2) + T3 off when EXP20 > 1.7  [RECOMMENDED]", P); REC = copy.deepcopy(P)
P = copy.deepcopy(REC); P["expMax"] = 1.6; line("   (same with threshold 1.6)", P)
P = copy.deepcopy(REC); P["expMax"] = 1.8; line("   (same with threshold 1.8)", P)
print("-- optional risk shifts on top of the recommended set")
P = copy.deepcopy(REC); P["rExpMult"] = 0.5; line("   T2R half risk when EXP20 > 1.7", P)
for rk in (250, 300):
    P = copy.deepcopy(REC)
    for k in ("xu", "xd"): P[k]["rk"] = [max(rk, v) for v in P[k]["rk"]]
    P["maxRisk"] = 300 * rk / 200; line("   T2X risk $%d (ceiling scaled)" % rk, P)
    P = copy.deepcopy(REC)
    for k in ("xu", "xd"): P[k]["rk"] = [max(rk, v) for v in P[k]["rk"]]
    line("   T2X risk $%d (ceiling stays $300)" % rk, P)
t1.to_pickle("tr_rec.pkl")
# what changed, trade by trade
k0 = set(zip(t0.entry_t, t0.id)); k1 = set(zip(t1.entry_t, t1.id))
rm = t0[[(a, b) not in k1 for a, b in zip(t0.entry_t, t0.id)]]
print("\nremoved trades: n=%d net=%.0f  (Mondays %d / %.0f ; regime %d / %.0f)" % (len(rm), rm.pnl.sum(), (rm.entry_t.dt.dayofweek == 0).sum(), rm[rm.entry_t.dt.dayofweek == 0].pnl.sum(), (rm.entry_t.dt.dayofweek != 0).sum(), rm[rm.entry_t.dt.dayofweek != 0].pnl.sum()))
import pickle; pickle.dump(dict(E5=E5, E15=E15), open("exp.pkl", "wb"))
# current regime read-out
ks = sorted(k for k in E15 if E15[k] is not None)
print("\nEXP20 monthly mean (last 14 months):", {m: round(np.mean([E15[k] for k in ks if k[:7] == m]), 2) for m in sorted(set(k[:7] for k in ks))[-14:]})
print("latest:", ks[-1], round(E15[ks[-1]], 2))
