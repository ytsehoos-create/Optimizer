"""Are v3's T1 Zone 1 levels optimal? Checked at a $200 risk cap, full-portfolio scoring.

T1 outcomes gate T2R/T2X (R1, R3, R7), so every candidate is scored on the whole
portfolio's net P&L, not T1 alone.

1. Full-year grid over Zone 1 long and short (entry, stop, target) with neighbour
   smoothing; candidates must beat current levels in >= 3 of 4 quarters.
2. Walk-forward: pick levels on 3 quarters (same rule), trade the 4th blind.
   Done for one global level set and for per-weekday level sets.
3. Zone 3a stop, z1_max and the 10:30 zone boundaries, same acceptance rule.
"""
import copy
import itertools
import sys

import numpy as np

import mnq_v3 as v

v.RISK_CAP = float(sys.argv[1]) if len(sys.argv) > 1 else 200.0
S = v.load_sessions()
QI = np.array_split(np.arange(len(S)), 4)
QS = [[S[i] for i in q] for q in QI]
E = [round(x, 2) for x in np.arange(0.10, 0.401, 0.05)]      # entry depth into IB
RK = [round(x, 2) for x in np.arange(0.15, 0.451, 0.05)]     # stop distance beyond entry
T = [-0.10, -0.05, 0.0, 0.05, 0.10]                          # target offset (neg = beyond IB edge)
GRID = list(itertools.product(E, RK, T))
SHAPE = (len(E), len(RK), len(T))


def qnet(P, qs):
    df = v.run([s for q in qs for s in q], P)
    return np.array([df[df.date.isin({s.date for s in q})].net.sum() for q in qs])


def setz(P, side, e, r, t, dow=None):
    Q = copy.deepcopy(P)
    vals = {f"z1_{side}_e": e, f"z1_{side}_s": round(e + r, 2), f"z1_{side}_t": t}
    if dow is None:
        Q.update(vals)
    else:
        Q.setdefault("z1_by_dow", {})
        Q["z1_by_dow"] = {k: dict(x) for k, x in Q["z1_by_dow"].items()}
        Q["z1_by_dow"].setdefault(dow, {}).update(vals)
    return Q


def smooth(a):
    a = a.reshape(SHAPE); out = np.zeros_like(a)
    for idx in np.ndindex(*SHAPE):
        out[idx] = a[tuple(slice(max(0, j - 1), j + 2) for j in idx)].mean()
    return out.ravel()


def pick(P, qs, side, dow=None):
    """Best smoothed grid point that beats current levels in all-but-one quarter."""
    cur = qnet(P, qs)
    res = [qnet(setz(P, side, *g, dow=dow), qs) for g in GRID]
    tot = np.array([r.sum() for r in res]); sm = smooth(tot)
    need = len(qs) - 1
    ok = [i for i, r in enumerate(res) if ((r - cur) > 0).sum() >= need and r.sum() > cur.sum()]
    if not ok:
        return P, None, cur, None
    i = max(ok, key=lambda i: sm[i])
    return setz(P, side, *GRID[i], dow=dow), GRID[i], cur, res[i]


def current(P, side, dow=None):
    Z = {**P, **P.get("z1_by_dow", {}).get(dow, {})}
    return (Z[f"z1_{side}_e"], round(Z[f"z1_{side}_s"] - Z[f"z1_{side}_e"], 2), Z[f"z1_{side}_t"])


if __name__ == "__main__":
    P0 = copy.deepcopy(v.V3)
    base = qnet(P0, QS)
    print(f"risk cap ${v.RISK_CAP:.0f} | v3 net ${base.sum():,.0f} quarters {base.round().astype(int).tolist()}")
    print("\n1. Full-year grid (entry, stop-beyond-entry, target offset) in R")
    for side in ("long", "short"):
        P, g, cur, new = pick(P0, QS, side)
        res = [qnet(setz(P0, side, *gg), QS).sum() for gg in GRID]
        rank = sorted(range(len(GRID)), key=lambda i: -res[i])
        ci = GRID.index(current(P0, side))
        print(f"  {side}: current {current(P0, side)} -> ${res[ci]:,.0f} (rank {rank.index(ci) + 1}/{len(GRID)}; "
              f"best raw {GRID[rank[0]]} ${res[rank[0]]:,.0f})")
        print(f"    accepted change: {g} " + (f"quarters {cur.round().astype(int).tolist()} -> {new.round().astype(int).tolist()}" if g else "none passes 3/4 quarters"))

    print("\n2. Walk-forward (select on 3 quarters, trade the 4th blind)")
    for mode in ("global", "per-weekday"):
        blind_new, blind_cur, picks = 0.0, 0.0, []
        for k in range(4):
            train = [q for j, q in enumerate(QS) if j != k]
            P = copy.deepcopy(P0)
            for side in ("long", "short"):
                if mode == "global":
                    P, g, *_ = pick(P, train, side); picks.append((k, side, g))
                else:
                    for d in range(5):
                        P, g, *_ = pick(P, train, side, dow=d)
                        if g: picks.append((k, side, v.DOW[d], g))
            blind_new += v.run(QS[k], P).net.sum(); blind_cur += v.run(QS[k], P0).net.sum()
        print(f"  {mode:12s} blind with re-picked T1 levels ${blind_new:,.0f} vs current levels ${blind_cur:,.0f} "
              f"(delta ${blind_new - blind_cur:+,.0f})")
        print(f"    picks: {[p for p in picks if p[-1]] or 'none'}")

    print("\n3. Other T1 knobs (full year, must beat current in >= 3/4 quarters)")
    for key, vals in (("z1_max", [15, 20, 25, 30, 35]), ("z3a_s", [0.15, 0.20, 0.25, 0.30, 0.35]),
                      ("z3a_lo", [40, 45, 50, 55, 60]), ("z3a_hi", [65, 70, 75, 80, 85]),
                      ("gap_max", [0.75, 1.0, 1.25, 1.5]), ("vwap", [True, False]),
                      ("t1_cutoff", [1200, 1300, 1400, 1500])):
        rows = []
        for val in vals:
            Q = copy.deepcopy(P0); Q[key] = val; x = qnet(Q, QS)
            rows.append(f"{val}: ${x.sum():,.0f} ({int(((x - base) > 0).sum())}/4 up)")
        print(f"  {key:9s} current {P0[key]} | " + " | ".join(rows))
