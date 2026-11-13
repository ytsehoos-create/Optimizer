import sys, os, copy
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pandas as pd, numpy as np
from t2sim import *
from load import load
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 40)
m5 = load_m5_rth()
m15 = load("m15_rth").rename(columns={"VWAP": "vwap_rth"})[["open", "high", "low", "close", "vwap_rth"]]
def pf(s): return s[s > 0].sum() / max(1e-9, -s[s <= 0].sum()) if len(s) else np.nan
B = default_params(); B["t3On"] = True
U = copy.deepcopy(B); U["ibSizeOn"] = False
for k in ("ru", "rd"): U[k].update(on=[True]*5, e=[.2]*5, s=[.3]*5, t=[.25]*5, rk=[0]*5)
U["xu"].update(on=[True]*5, e=[.2]*5, s=[.6]*5, t=[.3]*5, rk=[0]*5); U["xd"].update(on=[True]*5, e=[.3]*5, s=[.6]*5, t=[.25]*5, rk=[0]*5)
trU, dU = run(m15, U, bar_min=15); trB, dB = run(m15, B, bar_min=15)
trU.to_pickle("tr15_uniform.pkl"); dU.to_pickle("d15_uniform.pkl")
tz = "America/New_York"
yrs = [("Nov23-Nov24", "2023-11-01", "2024-11-17"), ("Nov24-Nov25", "2024-11-17", "2025-11-17"), ("Nov25-Nov26", "2025-11-17", "2026-12-01")]
for nm, tr in (("FITTED settings on 15m bars", trB), ("ONE-SETTING version on 15m bars", trU)):
    print("==", nm)
    for lbl, a0, a1 in yrs:
        x = tr[(tr.entry_t >= pd.Timestamp(a0, tz=tz)) & (tr.entry_t < pd.Timestamp(a1, tz=tz))]
        print("  %s: " % lbl + "  ".join("%s n=%3d net=%6.0f pf=%.2f win=%2.0f%%" % (k, len(g), g.pnl.sum(), pf(g.pnl), (g.pnl > 0).mean() * 100) for k, g in x.groupby("id")) + "  | all net=%6.0f pf=%.2f" % (x.pnl.sum(), pf(x.pnl)))
# T3 is exact on 15m bars: detail by year, weekday, side
t3 = trB[trB.id == "T3"].copy(); t3["yr"] = np.where(t3.entry_t < pd.Timestamp("2024-11-17", tz=tz), "y1", np.where(t3.entry_t < pd.Timestamp("2025-11-17", tz=tz), "y2", "y3"))
t3["dow"] = t3.entry_t.dt.dayofweek
print("== T3 (exact) net by year x weekday"); print(t3.pivot_table(index="yr", columns="dow", values="pnl", aggfunc=["count", "sum"]).round(0).to_string())
print("== T3 (exact) net by year x side"); print(t3.pivot_table(index="yr", columns="side", values="pnl", aggfunc=["count", "sum"]).round(0).to_string())
