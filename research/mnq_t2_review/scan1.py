from common import *
B = default_params(); B["t3On"] = True
_prior = m15()[m15().index < m5().index[0]]
def line(lbl, P, prior=True):
    tr, _ = run(m5(), P, exp20=exp20())
    a, b = tr[tr.entry_t < CUT6], tr[tr.entry_t >= CUT6]
    s = "%-50s 12m n=%3d net=%6.0f pf=%.2f dd=%5.0f | first6 %6.0f pf=%.2f | LAST6 n=%2d %6.0f pf=%.2f dd=%5.0f" % (
        lbl, len(tr), tr.pnl.sum(), pf(tr.pnl), maxdd(tr), a.pnl.sum(), pf(a.pnl), len(b), b.pnl.sum(), pf(b.pnl), maxdd(b))
    if prior:
        tp, _ = run(_prior, P, bar_min=15, exp20=exp20())
        s += " | prior2y~ n=%3d %6.0f pf=%.2f dd=%5.0f" % (len(tp), tp.pnl.sum(), pf(tp.pnl), maxdd(tp))
    print(s); return tr
line("BASE (as traded: defaults + T3 on)", B)
print("-- T3 changes")
P = copy.deepcopy(B); P["t3Days"] = [False, True, True, True, True]; line("T3 Monday off", P); M = copy.deepcopy(P)
P = copy.deepcopy(M); P.update(expMax=1.7, t3ExpOff=True); line("T3 Monday off + T3 off when EXP20>1.7", P)
P = copy.deepcopy(M); P.update(expMax=1.6, t3ExpOff=True); line("T3 Monday off + T3 off when EXP20>1.6", P)
print("-- regime dial on the T2R fade (on top of T3 Monday off)")
for th in (1.6, 1.7):
    for m in (0.0, 0.5):
        P = copy.deepcopy(M); P.update(expMax=th, t3ExpOff=True, rExpMult=m); line("EXP20>%.1f: T3 off, T2R risk x%.1f" % (th, m), P)
P = copy.deepcopy(M); P.update(expMax=1.7, t3ExpOff=True, rExpMult=0.5, calmMax=1.4, rCalmMult=1.5); line("EXP20>1.7: T3 off,T2R x.5; <=1.4: T2R x1.5", P)
print("-- cutoffs")
for c in (1200, 1300, 1500, 1545):
    P = copy.deepcopy(M); P["cutR"] = c; line("T2R cutoff %d (default 1400)" % c, P)
for c in (1200, 1400, 1500):
    P = copy.deepcopy(M); P["cutX"] = c; line("T2X cutoff %d (default 1300)" % c, P)
print("-- gates / filters")
for k in ("useR1", "useR2", "useR3", "useR7", "alignOn"):
    P = copy.deepcopy(M); P[k] = False; line("%s off" % k, P)
for v in (0.7, 0.8, 1.0, 1.1):
    P = copy.deepcopy(M); P["largeIB"] = v; line("largeIB %.1f (default 0.9)" % v, P)
for v in (0, 250, 400, 500):
    P = copy.deepcopy(M); P["maxRisk"] = v; line("risk ceiling %d (default 300)" % v, P)
print("-- weekday cells that are switched off: what each adds when switched on (its own row settings)")
for k, d in (("ru", 0), ("rd", 0), ("xu", 3), ("xd", 0), ("xd", 3)):
    P = copy.deepcopy(M); P[k]["on"][d] = True; line("%s %s ON" % (k, DAYS[d]), P)
print("-- weekday cells that are on: what happens when each is switched off")
for k in ("ru", "rd", "xu", "xd"):
    for d in range(5):
        if B[k]["on"][d]:
            P = copy.deepcopy(M); P[k]["on"][d] = False; line("%s %s OFF" % (k, DAYS[d]), P, prior=False)
