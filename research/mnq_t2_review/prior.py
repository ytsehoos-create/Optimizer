import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pandas as pd, numpy as np
from t2sim import *
from load import load
pd.set_option("display.width", 250)
m5 = load_m5_rth()
# 5m -> 15m aggregation of the overlap year, to measure what the coarser bars do to the result
a = m5.resample("15min", label="left", closed="left").agg(dict(open="first", high="max", low="min", close="last", vwap_rth="last")).dropna(subset=["open"])
m15 = load("m15_rth").rename(columns={"VWAP": "vwap_rth"})[["open", "high", "low", "close", "vwap_rth"]]
P = default_params(); P["t3On"] = True
tr5, _ = run(m5, P)
trA, _ = run(a, P, bar_min=15)
tr15, d15 = run(m15, P, bar_min=15)
tr15.to_pickle("tr15.pkl"); d15.to_pickle("d15.pkl")
def bys(tr): return " ".join("%s:%d/%.0f" % (k, r["size"], r["sum"]) for k, r in tr.groupby("id").pnl.agg(["size", "sum"]).iterrows())
print("5m truth (Nov25-Nov26)        ", summarize(tr5), bys(tr5))
print("15m aggregated, same window   ", summarize(trA), bys(trA))
ov = tr15[tr15.entry_t >= m5.index[0]]
print("15m file, same window         ", summarize(ov), bys(ov))
# monthly agreement between 5m truth and 15m approx
m5m = tr5.groupby(tr5.entry_t.dt.strftime("%Y-%m")).pnl.sum(); mAm = trA.groupby(trA.entry_t.dt.strftime("%Y-%m")).pnl.sum()
j = pd.concat([m5m, mAm], axis=1, keys=["m5", "m15"]).fillna(0)
print("monthly corr 5m vs 15m approx: %.2f" % j.corr().iloc[0, 1])
d5 = tr5.groupby(tr5.entry_t.dt.strftime("%Y-%m-%d")).pnl.sum(); dA = trA.groupby(trA.entry_t.dt.strftime("%Y-%m-%d")).pnl.sum()
jj = pd.concat([d5, dA], axis=1, keys=["m5", "m15"]).fillna(0); print("daily corr: %.2f  days %d" % (jj.corr().iloc[0, 1], len(jj)))
print("\n== 15m approximation by quarter, 3 years (per setup net / n)")
tr15["q"] = tr15.entry_t.dt.tz_localize(None).dt.to_period("Q").astype(str)
t = tr15.pivot_table(index="q", columns="id", values="pnl", aggfunc=["count", "sum"]).round(0).fillna(0)
t["tot"] = t["sum"].sum(axis=1)
tot = tr15.groupby("q").pnl
t["pf"] = tot.apply(lambda s: s[s > 0].sum() / max(1e-9, -s[s <= 0].sum())).round(2)
print(t.to_string())
for lbl, a0, a1 in (("Nov23-Nov24", "2023-11-01", "2024-11-17"), ("Nov24-Nov25", "2024-11-17", "2025-11-17"), ("Nov25-Nov26", "2025-11-17", "2026-12-01")):
    x = tr15[(tr15.entry_t >= pd.Timestamp(a0, tz="America/New_York")) & (tr15.entry_t < pd.Timestamp(a1, tz="America/New_York"))]
    print(lbl, summarize(x), bys(x))
