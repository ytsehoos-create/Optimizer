from common import *
B = default_params(); B["t3On"] = True; B["t2On"] = False
def t3line(lbl, P):
    tr, _ = run(m15(), P, bar_min=15, exp20=exp20())
    tr = tr[tr.id == "T3"]
    s = "%-46s" % lbl
    for y in ("y1", "y2", "y3"):
        x = yr(tr, y); s += " | %s n=%2d %6.0f pf=%.2f" % (y, len(x), x.pnl.sum(), pf(x.pnl))
    l6 = tr[tr.entry_t >= CUT6]
    print(s + " | 3y n=%3d net=%6.0f pf=%.2f dd=%5.0f | last6m %5.0f (%d)" % (len(tr), tr.pnl.sum(), pf(tr.pnl), maxdd(tr), l6.pnl.sum(), len(l6)))
    return tr
t3line("T3 default (zone .25, stop .15, back .40)", B)
P = copy.deepcopy(B); P["t3Days"] = [False, True, True, True, True]; t3line("  Monday off", P)
P = copy.deepcopy(B); P.update(expMax=1.6, t3ExpOff=True); t3line("  regime gate: only when EXP20 <= 1.6", P)
P = copy.deepcopy(B); P.update(expMax=1.6, t3ExpOff=True, t3Days=[False, True, True, True, True]); t3line("  Monday off + regime gate 1.6", P); G = copy.deepcopy(P)
P = copy.deepcopy(B); P.update(expMax=1.7, t3ExpOff=True, t3Days=[False, True, True, True, True]); t3line("  Monday off + regime gate 1.7", P)
print("-- parameter surface (ungated, all weekdays) to see whether the default sits on a plateau")
for z in (0.15, 0.2, 0.25, 0.3, 0.35):
    P = copy.deepcopy(B); P["t3Zone"] = z; t3line("  zone %.2f" % z, P)
for sx in (0.05, 0.10, 0.15, 0.20, 0.30):
    P = copy.deepcopy(B); P["t3StopX"] = sx; t3line("  stop %.2f" % sx, P)
for bk in (0.25, 0.3, 0.4, 0.5, 0.6):
    P = copy.deepcopy(B); P["t3Back"] = bk; t3line("  back %.2f" % bk, P)
print("-- which IB sizes does the T3 idea work on? (standalone, ungated / gated)")
for lo, hi in ((0.0, 0.5), (0.5, 0.7), (0.7, 0.9), (0.9, 1.2), (1.2, 9)):
    P = copy.deepcopy(B); P.update(t3IbMin=lo, t3IbMax=hi, maxRisk=0); t3line("  IB %.1f-%.1f%% ungated (no risk ceiling)" % (lo, hi), P)
    P = copy.deepcopy(G); P.update(t3IbMin=lo, t3IbMax=hi, maxRisk=0); t3line("  IB %.1f-%.1f%% Mon off + gate 1.6" % (lo, hi), P)
