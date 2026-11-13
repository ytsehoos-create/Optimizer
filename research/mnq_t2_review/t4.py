from common import *
from seng import *
r15 = m15()[["open", "high", "low", "close"]]
S = build_sessions(r15, 930, 60, 325, 15)
print("RTH sessions", len(S))
def line(lbl, t):
    s = "%-40s" % lbl
    for y, a0, a1 in Y:
        x = t[(t.date >= a0) & (t.date < a1)]; st = stats(x); s += " | %s n=%3d %6.0f pf=%.2f" % (y, st["n"], st["net"], st["pf"])
    st = stats(t); print(s + " | 3y n=%3d net=%6.0f pf=%.2f dd=%6.0f win=%2.0f%%" % (st["n"], st["net"], st["pf"], st["dd"], st["win"]))
print("== narrow-IB continuation at 10:30 (10:25 close in the outer zone -> go WITH it), by IB size")
for lo, hi in ((0, 0.4), (0.4, 0.5), (0, 0.5), (0.5, 0.7), (0.7, 0.9)):
    for z, s, t in ((0.25, 0.5, 0.3), (0.25, 0.5, 0.5), (0.25, 0.7, 0.5), (0.25, 0.7, 1.0), (0.2, 0.5, 0.5)):
        line("IB %.1f-%.1f%% zone %.2f stop %.1f tgt %.1f" % (lo, hi, z, s, t), run_setup(S, "ZC", zone=z, s=s, t=t, ib_min=lo, ib_max=hi, max_risk=300.0))
print("== London pullback: stop-width neighbours with tick-size checks (02:00-03:00, flat 07:00)")
e15 = load("m15_eth")[["open", "high", "low", "close"]]
SL = build_sessions(e15, 200, 60, 240, 15); cut = pd.Timestamp("2026-05-13")
for e in (0.2, 0.3, 0.4):
    for s in (0.7, 0.75, 0.8, 0.85, 0.9, 1.0):
        t = run_setup(SL, "X", e=e, s=s, t=1.0, max_risk=400.0, th_ticks=2); a = stats(t[t.date < cut]); b = stats(t[t.date >= cut]); al = stats(t)
        print("  e=%.1f s=%.2f t=1.0 (2 ticks through): n=%3d net=%6.0f pf=%.2f dd=%6.0f | Jan-May pf=%.2f | last6m pf=%.2f" % (e, s, al["n"], al["net"], al["pf"], al["dd"], a["pf"], b["pf"]))
