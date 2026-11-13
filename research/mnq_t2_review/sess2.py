from common import *
from seng import *
import itertools, time
pd.set_option("display.width", 250); pd.set_option("display.max_rows", 300)
e15 = load("m15_eth")[["open", "high", "low", "close"]]
SESS = dict(Globex18=(1800, 60, 360), Asia20=(2000, 60, 360), Euro02=(200, 60, 385), London03=(300, 60, 325), London04=(400, 60, 265),
            AsiaRange_to_London=(1800, 540, 325), PreUS07=(700, 60, 145))
grids = dict(
    R=[dict(e=e, s=round(e + w, 2), t=t) for e in (0.2, 0.3, 0.5, 0.75, 1.0) for w in (0.1, 0.2, 0.3, 0.5) for t in (-0.1, 0.0, 0.25, 0.5) if not (t < 0 and e < 0.3)],
    X=[dict(e=e, s=round(e + w, 2), t=t) for e in (0.1, 0.2, 0.3, 0.5) for w in (0.2, 0.3, 0.5) for t in (0.2, 0.3, 0.5, 1.0)],
    ZF=[dict(zone=z, s=s, t=t) for z in (0.2, 0.3) for s in (0.15, 0.3, 0.5) for t in (0.3, 0.5, 0.7)],
    ZC=[dict(zone=z, s=s, t=t) for z in (0.2, 0.3) for s in (0.3, 0.5, 0.7) for t in (0.3, 0.5, 1.0, 1.5)],
    BO=[dict(e=e, s=s, t=t) for e in (0.0, 0.1, 0.25) for s in (0.25, 0.5, 1.0) for t in (0.5, 1.0, 1.5, 2.5)],
)
cut = pd.Timestamp("2026-05-13")
rows = []; t0 = time.time()
for sn, (hm_, orm, win) in SESS.items():
    S = build_sessions(e15, hm_, orm, win, 15)
    for kind, G in grids.items():
        for g in G:
            tr = run_setup(S, kind, max_risk=400.0, **g)
            if len(tr) == 0: continue
            a = stats(tr[tr.date < cut]); b = stats(tr[tr.date >= cut]); al = stats(tr)
            rows.append(dict(sess=sn, kind=kind, **{k: g.get(k) for k in ("e", "s", "t", "zone")}, n=al["n"], net=al["net"], pf=al["pf"], dd=al["dd"], win=al["win"],
                             nA=a["n"], netA=a["net"], pfA=a["pf"], nB=b["n"], netB=b["net"], pfB=b["pf"], ddB=b["dd"]))
T = pd.DataFrame(rows); T.to_pickle("sess_scan15.pkl")
print("configs", len(T), "secs %.0f" % (time.time() - t0))
print("\n== family summary (15m bars, Jan-Nov 2026; A = Jan..May12, B = last 6 months). Conservative fills, $200 risk")
g = T.groupby(["sess", "kind"])
fam = pd.DataFrame(dict(cells=g.size(), medPF=g.pf.median().round(2), medPF_A=g.pfA.median().round(2), medPF_B=g.pfB.median().round(2),
    both_pos=(g.apply(lambda x: ((x.netA > 0) & (x.netB > 0)).mean(), include_groups=False) * 100).round(0),
    strong=(g.apply(lambda x: ((x.pfA > 1.3) & (x.pfB > 1.3) & (x.n >= 40)).mean(), include_groups=False) * 100).round(0),
    medNet=g.net.median().round(0), bestNet=g.net.max().round(0)))
print(fam.to_string())
