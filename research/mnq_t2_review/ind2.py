from common import *
from probe import run_probe, line
mnq = load("m5_rth"); cut = pd.Timestamp("2026-05-13", tz=TZ)
def show(lbl, tr):
    a = tr[tr.entry_t < cut]; b = tr[tr.entry_t >= cut]
    print("  %-46s %s | first6 n=%2d pf=%.2f | last6 n=%2d pf=%.2f" % (lbl, line(tr), len(a), pf(a.pnl), len(b), pf(b.pnl)))
print("== T2R one setting (e .2, s .3, t .25), 12 months")
show("no volume filter", run_probe(mnq, 1))
for th in (1.0, 1.5, 2.0):
    show("break bar volume >= %.1fx prior 20 bars" % th, run_probe(mnq, 1, vf=1, vthr=th)); show("break bar volume <  %.1fx" % th, run_probe(mnq, 1, vf=2, vthr=th))
for th in (0.8, 1.0, 1.2, 1.5):
    show("order live only after a bar >= %.1fx (dynamic)" % th, run_probe(mnq, 1, vf=3, vthr=th)); show("order live only after a bar <  %.1fx" % th, run_probe(mnq, 1, vf=4, vthr=th))
print("== T3 as shipped, 12 months")
show("no volume filter", run_probe(mnq, 3, s=.15, t=.4))
for th in (0.9, 1.0, 1.1):
    show("IB volume >= %.1fx its 20-day average" % th, run_probe(mnq, 3, s=.15, t=.4, vf=1, vthr=th)); show("IB volume <  %.1fx" % th, run_probe(mnq, 3, s=.15, t=.4, vf=2, vthr=th))
print("== T3 Tue-Fri"); show("no filter", run_probe(mnq, 3, s=.15, t=.4, mon=False)); show("IB volume >= 1.0x", run_probe(mnq, 3, s=.15, t=.4, mon=False, vf=1)); show("IB volume < 1.0x", run_probe(mnq, 3, s=.15, t=.4, mon=False, vf=2))
