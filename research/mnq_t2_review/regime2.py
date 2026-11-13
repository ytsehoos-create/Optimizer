import sys, os, copy
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pandas as pd, numpy as np
from t2sim import *
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 40); pd.set_option("display.max_rows", 200)
X = pd.read_pickle("X.pkl")
tz = "America/New_York"
def prep(tr):
    tr = tr.copy(); tr["date"] = pd.to_datetime(tr.entry_t.dt.strftime("%Y-%m-%d"))
    tr["risk"] = tr.meta.apply(lambda m: m["risk"]); tr["Rm"] = tr.pnl / tr.risk
    tr["yr"] = np.where(tr.date < "2024-11-17", "y1", np.where(tr.date < "2025-11-17", "y2", "y3"))
    return tr.join(X, on="date")
# 3-year one-setting version on 15m bars (same yardstick each year) + exact 5m trades of the last year
u15 = prep(pd.read_pickle("tr15_uniform.pkl"))
t5 = prep(pd.read_pickle("tr_base.pkl"))
feats = [c for c in X.columns if c not in ("dow",)]
rows = []
for f in feats:
    for nm, tr in (("u15", u15), ("t5", t5)):
        for su in (("T2R",), ("T2X",), ("T3",), ("T2R", "T2X", "T3")):
            x = tr[tr.id.isin(su)].dropna(subset=[f])
            if len(x) < 30: continue
            rho = x[[f, "Rm"]].corr(method="spearman").iloc[0, 1]
            rk = x[f].rank(method="first")
            q = pd.cut(rk, [0, len(x) / 3, 2 * len(x) / 3, len(x) + 1], labels=["lo", "mid", "hi"])
            m = x.groupby(q, observed=True).Rm.mean()
            # sign consistency across years (for 3y set)
            cons = ""
            if nm == "u15":
                rr = [x[x.yr == y][[f, "Rm"]].corr(method="spearman").iloc[0, 1] for y in ("y1", "y2", "y3") if (x.yr == y).sum() >= 12]
                cons = "".join("+" if r > 0.03 else "-" if r < -0.03 else "0" for r in rr)
            rows.append(dict(feat=f, set=nm, setup="+".join(su) if len(su) < 3 else "ALL", n=len(x), rho=round(rho, 2), lo=round(m.get("lo", np.nan), 2), mid=round(m.get("mid", np.nan), 2), hi=round(m.get("hi", np.nan), 2), yrs=cons))
T = pd.DataFrame(rows)
T.to_pickle("regime_corr.pkl")
print("== strongest |rho| on the 3-year one-setting series (all setups pooled)")
a = T[(T.set == "u15") & (T.setup == "ALL")].copy(); a["abs"] = a.rho.abs(); print(a.sort_values("abs", ascending=False).head(18).drop(columns="abs").to_string(index=False))
for su in ("T2R", "T2X", "T3"):
    print("== 3y one-setting,", su)
    a = T[(T.set == "u15") & (T.setup == su)].copy(); a["abs"] = a.rho.abs(); print(a.sort_values("abs", ascending=False).head(10).drop(columns="abs").to_string(index=False))
print("== exact last-12-month trades (fitted), all setups")
a = T[(T.set == "t5") & (T.setup == "ALL")].copy(); a["abs"] = a.rho.abs(); print(a.sort_values("abs", ascending=False).head(14).drop(columns="abs").to_string(index=False))
