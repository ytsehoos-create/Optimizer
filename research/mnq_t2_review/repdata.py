from common import *
import pickle, json
E = pickle.load(open("exp.pkl", "rb"))["E15"]
rec = pd.read_pickle("tr_rec.pkl"); base = pd.read_pickle("tr_base.pkl"); on = pd.read_pickle("on_tv15.pkl")
f15 = pd.read_pickle("f15.pkl")
out = {}
def cum(tr, t="exit_t"):
    d = tr.groupby(tr[t].dt.strftime("%Y-%m-%d")).pnl.sum().cumsum()
    return [[k, round(float(v))] for k, v in d.items()]
out["eq_base"] = cum(base); out["eq_rec"] = cum(rec)
out["eq_lx"] = cum(on[on.id == "LX"]); out["eq_gm"] = cum(on[on.id == "GM"])
e = pd.Series(E).dropna(); out["exp"] = [[k, round(float(v), 3)] for k, v in e.items()]
# monthly table
def mon(tr): return tr.groupby(tr.entry_t.dt.strftime("%Y-%m")).pnl.sum().round(0)
m = pd.concat([mon(base).rename("asTraded"), mon(rec).rename("rec"), mon(on[on.id == "LX"]).rename("lx"), mon(on[on.id == "GM"]).rename("gm")], axis=1).fillna(0)
out["monthly"] = [[k] + [int(v) for v in r] for k, r in zip(m.index, m.values)]
print(m.to_string())
# current read-out
last20 = f15.tail(20); print("last 20 sessions: mean IB%% %.2f, large-IB days %d of 20, latest EXP20 %.2f" % (last20.ibPct.mean(), (last20.ibPct > 0.9).sum(), e.iloc[-1]))
l6 = f15[pd.to_datetime(f15.date) >= "2026-05-13"]; print("last 6m large-IB share %.0f%% ; last 12m %.0f%% ; prior 2y %.0f%%" % ((l6.ibPct > .9).mean() * 100, (f15[pd.to_datetime(f15.date) >= "2025-11-17"].ibPct > .9).mean() * 100, (f15[pd.to_datetime(f15.date) < "2025-11-17"].ibPct > .9).mean() * 100))
# T3 exact by year x regime x Monday
b15 = pd.read_pickle("tr15.pkl"); t3 = b15[b15.id == "T3"].copy(); t3["exp"] = t3.entry_t.dt.strftime("%Y-%m-%d").map(E)
t3["yr"] = np.where(t3.entry_t < pd.Timestamp("2024-11-17", tz=TZ), "y1", np.where(t3.entry_t < pd.Timestamp("2025-11-17", tz=TZ), "y2", "y3"))
t3["mon"] = t3.entry_t.dt.dayofweek == 0; t3["hot"] = t3.exp > 1.7
rows = []
for y in ("y1", "y2", "y3", "all"):
    x = t3 if y == "all" else t3[t3.yr == y]
    keep = x[(~x.mon) & (~x.hot)]; hot = x[x.hot & ~x.mon]; mo = x[x.mon]
    rows.append([y, len(x), round(x.pnl.sum()), round(pf(x.pnl), 2), len(keep), round(keep.pnl.sum()), round(pf(keep.pnl), 2), len(hot), round(hot.pnl.sum()), len(mo), round(mo.pnl.sum())])
    print(rows[-1])
out["t3"] = rows
# combined since Jan 2026 (RTH recommended + LX + GM), weekly
d = pd.concat([rec.groupby(rec.entry_t.dt.strftime("%Y-%m-%d")).pnl.sum().rename("rth"), on[on.id == "LX"].groupby(on.entry_t.dt.strftime("%Y-%m-%d")).pnl.sum().rename("lx"), on[on.id == "GM"].groupby(on.entry_t.dt.strftime("%Y-%m-%d")).pnl.sum().rename("gm")], axis=1).fillna(0)
d.index = pd.to_datetime(d.index); d = d[d.index >= "2026-01-02"]
tot = d.sum(axis=1); eq = tot.cumsum(); dd = (eq - eq.cummax().clip(lower=0)).min(); eqr = d.rth.cumsum(); ddr = (eqr - eqr.cummax().clip(lower=0)).min()
w = d.resample("W").sum()
print("since Jan 2: RTH rec net %.0f dd %.0f losing weeks %d/%d | +LX+GM net %.0f dd %.0f losing weeks %d/%d ; corr rth-lx %.2f rth-gm %.2f" % (d.rth.sum(), ddr, (w.rth < 0).sum(), len(w), tot.sum(), dd, (w.sum(axis=1) < 0).sum(), len(w), d.rth.corr(d.lx), d.rth.corr(d.gm)))
l6d = d[d.index >= "2026-05-13"]; print("last 6m: RTH rec %.0f, LX %.0f, GM %.0f, total %.0f" % (l6d.rth.sum(), l6d.lx.sum(), l6d.gm.sum(), l6d.sum().sum()))
json.dump(out, open("repdata.json", "w"))
print("as-traded last6 by setup:", {k: (len(g), round(g.pnl.sum())) for k, g in base[base.entry_t >= CUT6].groupby("id")})
