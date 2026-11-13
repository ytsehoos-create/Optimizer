import sys, os, copy
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pandas as pd, numpy as np
from t2sim import *
from load import load
m5 = load_m5_rth()
m15 = load("m15_rth").rename(columns={"VWAP": "vwap_rth"})[["open", "high", "low", "close", "vwap_rth"]]
m15p = m15[m15.index < m5.index[0]]       # prior two years only
cut = pd.Timestamp("2026-05-13", tz="America/New_York")
def pf(s): return s[s > 0].sum() / max(1e-9, -s[s <= 0].sum())
def line(lbl, P):
    tr, _ = run(m5, P)
    a, b = tr[tr.entry_t < cut], tr[tr.entry_t >= cut]
    tp, _ = run(m15p, P, bar_min=15)
    bs = " ".join("%s:%d/%.0f" % (k, r["size"], r["sum"]) for k, r in tr.groupby("id").pnl.agg(["size", "sum"]).iterrows())
    print("%-44s 12m n=%3d net=%6.0f pf=%.2f dd=%5.0f | first6 %6.0f pf=%.2f | last6 %6.0f pf=%.2f | prior2y(15m approx) n=%3d net=%6.0f pf=%.2f | %s" % (
        lbl, len(tr), tr.pnl.sum(), pf(tr.pnl), summarize(tr)["maxdd"], a.pnl.sum(), pf(a.pnl), b.pnl.sum(), pf(b.pnl), len(tp), tp.pnl.sum(), pf(tp.pnl) if len(tp) else 0, bs))
    return tr
B = default_params()
line("base (script defaults, T3 off)", B)
P = copy.deepcopy(B); P["ibSizeOn"] = False; line("no IB-size x1.5", P)
P = copy.deepcopy(B); P["ibSizeOn"] = False; P["ru"]["rk"] = [0]*5; P["xu"]["rk"] = [0]*5; line("flat $200 everywhere", P)
F = copy.deepcopy(P)   # flat-risk baseline
P = copy.deepcopy(F)
for k in ("ru", "rd", "xu", "xd"): P[k]["on"] = [True]*5
line("flat $200 + every weekday on", P)
P = copy.deepcopy(F)
for k in ("ru", "rd"): P[k].update(on=[True]*5, e=[.2]*5, s=[.3]*5, t=[.25]*5)
P["xu"].update(on=[True]*5, e=[.2]*5, s=[.6]*5, t=[.3]*5); P["xd"].update(on=[True]*5, e=[.3]*5, s=[.6]*5, t=[.25]*5)
line("flat $200 + one setting for all weekdays", P); U = copy.deepcopy(P)
P = copy.deepcopy(U); P.update(useR1=False, useR2=False, useR3=False, useR7=False); line("  ... and no T1 gates (R1/R2/R3/R7)", P)
P = copy.deepcopy(U); P["filterB"] = 9; line("  ... and no break-bar filter", P)
P = copy.deepcopy(U); P["largeIB"] = 9; line("  ... and no large-IB skip", P)
P = copy.deepcopy(U); P["alignOn"] = False; line("  ... and no target alignment", P)
P = copy.deepcopy(U); P["xu"]["on"] = [False]*5; P["xd"]["on"] = [False]*5; line("  uniform T2R only", P)
P = copy.deepcopy(U); P["ru"]["on"] = [False]*5; P["rd"]["on"] = [False]*5; line("  uniform T2X only", P)
P = copy.deepcopy(B); P["xu"]["on"] = [False]*5; P["xd"]["on"] = [False]*5; line("base T2R only", P)
P = copy.deepcopy(B); P["ru"]["on"] = [False]*5; P["rd"]["on"] = [False]*5; line("base T2X only", P)
