import sys, os, copy
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pandas as pd, numpy as np
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 40); pd.set_option("display.max_rows", 200)
X = pd.read_pickle("X.pkl")
def prep(tr):
    tr = tr.copy(); tr["date"] = pd.to_datetime(tr.entry_t.dt.strftime("%Y-%m-%d"))
    tr["risk"] = tr.meta.apply(lambda m: m["risk"]); tr["Rm"] = tr.pnl / tr.risk
    tr["yr"] = np.where(tr.date < "2024-11-17", "y1", np.where(tr.date < "2025-11-17", "y2", "y3"))
    return tr.join(X, on="date")
def pf(s): return s[s > 0].sum() / max(1e-9, -s[s <= 0].sum()) if len(s) else np.nan
t5 = prep(pd.read_pickle("tr_base.pkl")); b15 = prep(pd.read_pickle("tr15.pkl")); u15 = prep(pd.read_pickle("tr15_uniform.pkl"))
print("== EXACT last 12 months, fitted settings: net $ (n) below / above threshold, per setup")
for f, th in (("rngOverIB_20", 1.6), ("trend1_20", 0.25), ("trend1_40", 0.22), ("er_20", 0.2), ("ibRel20", 0.92), ("ibPct", 0.67), ("rv20", 20), ("dayRng_10", 1.3), ("atr14", 1.9)):
    s = "%-13s<=%-5s" % (f, th)
    for su in ("T2R", "T2X", "T3"):
        x = t5[t5.id == su]; lo = x[x[f] <= th]; hi = x[x[f] > th]
        s += " | %s %6.0f (%2d, pf %.1f) / %6.0f (%2d, pf %.1f)" % (su, lo.pnl.sum(), len(lo), pf(lo.pnl), hi.pnl.sum(), len(hi), pf(hi.pnl))
    print(s)
print("\n== T3 is exact for all 3 years. T3 net $ (n) by year, split on prior-20-day median (RTH range / IB range)")
t3 = b15[b15.id == "T3"]
for th in (1.5, 1.55, 1.6, 1.65, 1.7):
    s = "EXP20 <= %.2f:" % th
    for y in ("y1", "y2", "y3"):
        x = t3[t3.yr == y]; lo = x[x.rngOverIB_20 <= th]; hi = x[x.rngOverIB_20 > th]
        s += "  %s %6.0f (%2d) / %6.0f (%2d)" % (y, lo.pnl.sum(), len(lo), hi.pnl.sum(), len(hi))
    lo = t3[t3.rngOverIB_20 <= th]; hi = t3[t3.rngOverIB_20 > th]
    s += "  | 3y: pf %.2f (%d) / pf %.2f (%d)" % (pf(lo.pnl), len(lo), pf(hi.pnl), len(hi))
    print(s)
for f, ths in (("trend1_20", (0.15, 0.2, 0.25, 0.3)), ("rv20", (15, 18, 22, 26)), ("opp_20", (0.15, 0.2, 0.25))):
    for th in ths:
        s = "%s <= %.2f:" % (f, th)
        for y in ("y1", "y2", "y3"):
            x = t3[t3.yr == y]; lo = x[x[f] <= th]; hi = x[x[f] > th]
            s += "  %s %6.0f (%2d) / %6.0f (%2d)" % (y, lo.pnl.sum(), len(lo), hi.pnl.sum(), len(hi))
        lo = t3[t3[f] <= th]; hi = t3[t3[f] > th]
        print(s + "  | 3y: pf %.2f (%d) / pf %.2f (%d)" % (pf(lo.pnl), len(lo), pf(hi.pnl), len(hi)))
print("\n== T3 exact, excluding Mondays, by year:", {y: (round(t3[(t3.yr == y) & (t3.entry_t.dt.dayofweek != 0)].pnl.sum()), int(((t3.yr == y) & (t3.entry_t.dt.dayofweek != 0)).sum())) for y in ("y1", "y2", "y3")})
x = t3[(t3.entry_t.dt.dayofweek != 0) & (t3.rngOverIB_20 <= 1.6)]
print("T3 no-Monday + EXP20<=1.6 by year:", x.groupby("yr").pnl.agg(["size", "sum"]).round(0).to_dict("index"))
# how the regime variables looked through time (quarter means on all days)
Xq = X.copy(); Xq["q"] = Xq.index.to_period("Q").astype(str)
print("\n== regime variables by quarter (mean over days)")
print(Xq.groupby("q")[["ibPct_20", "rngOverIB_20", "trend1_20", "er_20", "rv20", "atr14", "dayRng_20", "returned_20"]].mean().round(2).to_string())
