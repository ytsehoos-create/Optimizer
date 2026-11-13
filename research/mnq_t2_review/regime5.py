import sys, os, copy
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pandas as pd, numpy as np
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 40)
X = pd.read_pickle("X.pkl")
def prep(tr):
    tr = tr.copy(); tr["date"] = pd.to_datetime(tr.entry_t.dt.strftime("%Y-%m-%d"))
    tr["risk"] = tr.meta.apply(lambda m: m["risk"]); tr["Rm"] = tr.pnl / tr.risk
    tr["yr"] = np.where(tr.date < "2024-11-17", "y1", np.where(tr.date < "2025-11-17", "y2", "y3"))
    return tr.join(X, on="date")
def pf(s): return s[s > 0].sum() / max(1e-9, -s[s <= 0].sum()) if len(s) else np.nan
t5 = prep(pd.read_pickle("tr_base.pkl")); b15 = prep(pd.read_pickle("tr15.pkl")); u15 = prep(pd.read_pickle("tr15_uniform.pkl"))
rng = np.random.default_rng(7)
# significance of the T3 split (exact, 3y): permutation test on mean R difference
t3 = b15[b15.id == "T3"].dropna(subset=["rngOverIB_20"])
lo = t3.rngOverIB_20 <= 1.6
obs = t3.Rm[lo].mean() - t3.Rm[~lo].mean()
perm = [(lambda p: t3.Rm[p].mean() - t3.Rm[~p].mean())(rng.permutation(lo.values)) for _ in range(20000)]
print("T3 exact 3y: mean R %.2f (EXP20<=1.6, n=%d, win %.0f%%) vs %.2f (>1.6, n=%d, win %.0f%%); diff %.2f, permutation p = %.4f" % (
    t3.Rm[lo].mean(), lo.sum(), (t3.pnl[lo] > 0).mean() * 100, t3.Rm[~lo].mean(), (~lo).sum(), (t3.pnl[~lo] > 0).mean() * 100, obs, (np.abs(perm) >= abs(obs)).mean()))
# block-ish check: by half-year
t3h = t3.copy(); t3h["h"] = t3h.date.dt.year.astype(str) + np.where(t3h.date.dt.month <= 6, "H1", "H2")
print(t3h.pivot_table(index="h", columns=lo.map({True: "calm<=1.6", False: "expanding>1.6"}), values="pnl", aggfunc=["count", "sum"]).round(0).fillna(0).to_string())
print("\n== gate applied to the fade legs (T2R + T3), continuation leg T2X untouched")
for nm, tr in (("15m fitted, 3y", b15), ("15m one-setting, 3y", u15), ("EXACT 5m fitted, last 12m", t5)):
    for th in (None, 1.5, 1.6, 1.7):
        keep = tr if th is None else tr[(tr.id == "T2X") | (tr.rngOverIB_20 <= th)]
        s = "  %-26s gate=%-4s" % (nm, th)
        for y in sorted(tr.yr.unique()):
            x = keep[keep.yr == y]; s += " | %s n=%3d net=%6.0f pf=%.2f" % (y, len(x), x.pnl.sum(), pf(x.pnl))
        eq = keep.sort_values("entry_t").pnl.cumsum(); dd = (eq - eq.cummax().clip(lower=0)).min()
        print(s + " | total %6.0f pf=%.2f maxDD %.0f" % (keep.pnl.sum(), pf(keep.pnl), dd))
print("\n== exact last 12m by setup and regime bucket (EXP20)")
t5["reg"] = pd.cut(t5.rngOverIB_20, [0, 1.4, 1.6, 1.8, 9], labels=["<=1.4", "1.4-1.6", "1.6-1.8", ">1.8"])
print(t5.pivot_table(index="id", columns="reg", values="pnl", aggfunc=["count", "sum"], observed=True).round(0).to_string())
print("days in each regime bucket, last 12m:", pd.cut(X.loc["2025-11-17":, "rngOverIB_20"], [0, 1.4, 1.6, 1.8, 9]).value_counts().sort_index().to_dict())
print("days in each regime bucket, prior 2y :", pd.cut(X.loc[:"2025-11-16", "rngOverIB_20"], [0, 1.4, 1.6, 1.8, 9]).value_counts().sort_index().to_dict())
