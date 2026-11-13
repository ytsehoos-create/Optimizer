from common import *
from probe import run_probe, line
import seng
pd.set_option("display.width", 250)
mnq = load("m5_rth"); mcl = load("mcl_m5_rth")
cut = pd.Timestamp("2026-05-13", tz=TZ)
def struct(df, name, tick, pv):
    hm = df.index.hour * 100 + df.index.minute; d = df[(hm >= 930) & (hm < 1600)]
    rows = []
    for day, g in d.groupby(d.index.strftime("%Y-%m-%d")):
        ghm = g.index.hour * 100 + g.index.minute; ib = g[ghm < 1030]
        if ghm.max() < 1500 or len(ib) < 12: continue
        R = ib.high.max() - ib.low.min(); c = ib.close.iloc[-1]
        rows.append(dict(R=R, ibPct=R / c * 100, exp=(g.high.max() - g.low.min()) / R if R > 0 else np.nan, vol=g.Volume.sum(), barVol=g.Volume.median()))
    s = pd.DataFrame(rows)
    stop = 0.1 * s.R.median(); cost = 2 * 0.62 + tick * pv        # round-trip commission + one tick of stop slippage, per contract
    print("%-4s IB median %.2f pts = $%.0f per contract (%.2f%% of price) | day range / IB median %.2f | regime reading now %.2f | median 5-min bar volume %.0f contracts" % (
        name, s.R.median(), s.R.median() * pv, s.ibPct.median(), s.exp.median(), s.exp.tail(20).median(), s.barVol.median()))
    print("     a 0.1R stop (T2R's) = %.2f pts = %d ticks = $%.0f per contract; cost per round trip $%.2f = %.0f%% of that risk | a 0.5R stop: cost = %.0f%% of risk" % (
        stop, round(stop / tick), stop * pv, cost, cost / (stop * pv) * 100, cost / (0.5 * s.R.median() * pv) * 100))
struct(mnq, "MNQ", 0.25, 2.0); struct(mcl, "MCL", 0.01, 100.0)
print("\n== the three legs with one setting, no gates, $200 risk, 12 months (same code on both instruments)")
for name, df, tick, pv, big in (("MNQ", mnq, 0.25, 2.0, 0.9), ("MCL", mcl, 0.01, 100.0, 0.9)):
    for leg, lbl, kw in ((1, "T2R fade  e.2 s.3 t.25", dict(e=.2, s=.3, t=.25, cut=1400)), (2, "T2X cont. e.2 s.6 t.3 ", dict(e=.2, s=.6, t=.3, cut=1300)), (3, "T3 wide-IB fade       ", dict(s=.15, t=.4))):
        tr = run_probe(df, leg, tick=tick, pv=pv, largeIB=big, **kw)
        a = tr[tr.entry_t < cut]; b = tr[tr.entry_t >= cut]
        print("  %s %s | %s | first6 pf=%.2f last6 pf=%.2f" % (name, lbl, line(tr), pf(a.pnl), pf(b.pnl)))
# MCL has its own scale: where should the 'large IB' line be? and wider stops, since a 0.1R stop is mostly cost
q = []
hm = mcl.index.hour * 100 + mcl.index.minute
print("\n== MCL: opening-range families on the 09:30-10:30 range (conservative fills, as in the overnight search)")
seng.TICK, seng.PV, seng.SLIP = 0.01, 100.0, 0.01
S = seng.build_sessions(mcl[["open", "high", "low", "close"]], 930, 60, 325, 5)
grids = dict(
    R=[dict(e=e, s=round(e + w, 2), t=t) for e in (0.2, 0.3, 0.5, 0.75) for w in (0.1, 0.2, 0.3, 0.5) for t in (0.0, 0.25, 0.5)],
    X=[dict(e=e, s=round(e + w, 2), t=t) for e in (0.1, 0.2, 0.3, 0.5) for w in (0.2, 0.3, 0.5) for t in (0.2, 0.3, 0.5, 1.0)],
    ZF=[dict(zone=z, s=s, t=t) for z in (0.2, 0.3) for s in (0.15, 0.3, 0.5) for t in (0.3, 0.5, 0.7)],
    ZC=[dict(zone=z, s=s, t=t) for z in (0.2, 0.3) for s in (0.5, 0.7, 0.85) for t in (0.3, 0.5, 1.0)],
    BO=[dict(e=e, s=s, t=t) for e in (0.0, 0.1, 0.25) for s in (0.25, 0.5, 1.0) for t in (0.5, 1.0, 1.5)])
c2 = pd.Timestamp("2026-05-13")
for kind, G in grids.items():
    res = []
    for g in G:
        tr = seng.run_setup(S, kind, max_risk=300.0, **g)
        if len(tr) < 20: continue
        a = seng.stats(tr[tr.date < c2]); b = seng.stats(tr[tr.date >= c2]); al = seng.stats(tr)
        res.append((al["pf"], a["pf"], b["pf"], al["net"], al["n"], g))
    r = pd.DataFrame(res, columns=["pf", "pfA", "pfB", "net", "n", "g"])
    best = r.sort_values("net").iloc[-1]
    print("  %-2s cells %2d | median PF %.2f (first6 %.2f, last6 %.2f) | profitable in both halves %2.0f%% | best cell %s n=%d net=%.0f pf=%.2f (%.2f / %.2f)" % (
        kind, len(r), r.pf.median(), r.pfA.median(), r.pfB.median(), ((r.pfA > 1) & (r.pfB > 1)).mean() * 100, best.g, best.n, best.net, best.pf, best.pfA, best.pfB))
