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
u15 = prep(pd.read_pickle("tr15_uniform.pkl")); t5 = prep(pd.read_pickle("tr_base.pkl"))
def pf(s): return s[s > 0].sum() / max(1e-9, -s[s <= 0].sum()) if len(s) else np.nan
feats = ["trend1_10", "trend1_20", "trend1_40", "er_10", "er_20", "rngOverIB_10", "rngOverIB_20", "maxExt_20", "absClose_20", "dayRng_10", "dayRng_20", "atr14", "rv20", "ibPct", "ibRel20", "absGap", "ddHigh", "dSma20", "returned_20", "opp_20"]
print("Median split of each feature (threshold = 3-year median over trade days). Cells: mean R per trade LOW half / HIGH half")
hdr = "%-13s %7s | %-17s %-17s %-17s | %-17s || per setup 3y (lo/hi): %-13s %-13s %-13s" % ("feature", "median", "y1 (15m)", "y2 (15m)", "y3 (15m)", "y3 exact 5m", "T2R", "T2X", "T3")
print(hdr)
for f in feats:
    med = u15[f].median()
    cells = []
    for y in ("y1", "y2", "y3"):
        x = u15[u15.yr == y]; cells.append("%5.2f /%5.2f (%3d)" % (x[x[f] <= med].Rm.mean(), x[x[f] > med].Rm.mean(), len(x)))
    cells.append("%5.2f /%5.2f (%3d)" % (t5[t5[f] <= med].Rm.mean(), t5[t5[f] > med].Rm.mean(), len(t5)))
    per = []
    for su in ("T2R", "T2X", "T3"):
        x = u15[u15.id == su]; per.append("%5.2f /%5.2f" % (x[x[f] <= med].Rm.mean(), x[x[f] > med].Rm.mean()))
    print("%-13s %7.2f | %s %s %s | %s || %s  %s  %s" % (f, med, *cells, *per))
# persistence of the strategy's own results
print("\n== does trailing strategy performance predict the next trades? (3y one-setting series, R per trade)")
u = u15.sort_values("entry_t").reset_index(drop=True)
for n in (10, 20, 30):
    tr_mean = u.Rm.rolling(n).mean().shift(1)
    nxt = u.Rm[::-1].rolling(10).mean()[::-1]
    ok = tr_mean.notna() & nxt.notna()
    lo = u.Rm[ok & (tr_mean <= 0)].mean(); hi = u.Rm[ok & (tr_mean > 0)].mean()
    print("  trailing %d trades: corr(trailing mean, next trade) = %.3f ; next-trade mean R when trailing<=0: %.2f (n=%d) ; when trailing>0: %.2f (n=%d)" % (
        n, np.corrcoef(tr_mean[ok], u.Rm[ok])[0, 1], lo, (ok & (tr_mean <= 0)).sum(), hi, (ok & (tr_mean > 0)).sum()))
# monthly autocorrelation
mo = u.groupby(u.date.dt.to_period("M")).pnl.sum()
print("  month-to-month autocorrelation of P&L (3y, 15m one-setting): %.2f  (n=%d months)" % (mo.autocorr(1), len(mo)))
print(mo.round(0).to_string())
