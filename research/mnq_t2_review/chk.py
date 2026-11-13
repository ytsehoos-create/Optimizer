from common import *
import pickle
E = pickle.load(open("exp.pkl", "rb"))
tr = pd.read_pickle("tr_rec.pkl"); t3 = tr[tr.id == "T3"]
print("T3 in the recommended set, exact 12m: n=%d net=%.0f pf=%.2f win=%.0f%%" % (len(t3), t3.pnl.sum(), pf(t3.pnl), (t3.pnl > 0).mean() * 100))
l6 = t3[t3.entry_t >= CUT6]; print("  last 6m: n=%d net=%.0f pf=%.2f" % (len(l6), l6.pnl.sum(), pf(l6.pnl)))
base = pd.read_pickle("tr_base.pkl"); base["exp"] = base.entry_t.dt.strftime("%Y-%m-%d").map(E["E15"])
for th in (1.6, 1.7):
    r = base[base.id == "T2R"]; lo = r[r.exp <= th]; hi = r[r.exp > th]
    print("T2R exact 12m split at %.1f: <= n=%d net=%.0f pf=%.2f | > n=%d net=%.0f pf=%.2f" % (th, len(lo), lo.pnl.sum(), pf(lo.pnl), len(hi), hi.pnl.sum(), pf(hi.pnl)))
    x = base[base.id == "T2X"]; lo = x[x.exp <= th]; hi = x[x.exp > th]
    print("T2X exact 12m split at %.1f: <= n=%d net=%.0f pf=%.2f | > n=%d net=%.0f pf=%.2f" % (th, len(lo), lo.pnl.sum(), pf(lo.pnl), len(hi), hi.pnl.sum(), pf(hi.pnl)))
print("by setup, recommended:", {k: (len(g), round(g.pnl.sum()), round(pf(g.pnl), 2)) for k, g in tr.groupby("id")})
l6 = tr[tr.entry_t >= CUT6]; print("by setup, recommended last 6m:", {k: (len(g), round(g.pnl.sum()), round(pf(g.pnl), 2)) for k, g in l6.groupby("id")})
# share of days by regime state
e = pd.Series(E["E15"]).dropna(); e.index = pd.to_datetime(e.index)
for lbl, a, b in (("prior 2y", "2023-11-01", "2025-11-16"), ("last 12m", "2025-11-17", "2026-12-01"), ("last 6m", "2026-05-13", "2026-12-01")):
    x = e[a:b]; print("%s: days %d  calm<=1.4 %.0f%%  normal %.0f%%  expanding>1.7 %.0f%%  median %.2f" % (lbl, len(x), (x <= 1.4).mean() * 100, ((x > 1.4) & (x <= 1.7)).mean() * 100, (x > 1.7).mean() * 100, x.median()))
