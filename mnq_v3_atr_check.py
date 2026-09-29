"""Test: no T2R/T2X entry once the session range has used X of the 14-day ATR.

1. Full-year sweep of X, net delta by quarter vs v3.
2. X = 0.75 fixed in advance, applied to the blind walk-forward folds (no refit).
3. X offered as a candidate to the walk-forward selection (select on 3 quarters,
   trade the 4th blind).
"""
import copy
import sys

import numpy as np
import pandas as pd

import mnq_v3 as v
import mnq_v3_select as m

v.RISK_CAP = float(sys.argv[1]) if len(sys.argv) > 1 else 200.0
S = m.SESSIONS
SQ = [[S[i] for i in q] for q in m.QIDX]
X = (0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90)


def dd(df):
    d = df.groupby("date").net.sum().cumsum()
    return float((d.cummax().clip(lower=0) - d).max())


def qnet(P):
    return np.array([v.run(q, P).net.sum() for q in SQ])


if __name__ == "__main__":
    base = qnet(v.V3)
    full = v.run(S, v.V3)
    print(f"risk cap ${v.RISK_CAP:.0f} | v3 full year net ${base.sum():,.0f} DD ${dd(full):,.0f}\n")
    print("1. Full-year sweep")
    for x in X:
        P = dict(copy.deepcopy(v.V3), atr_used_max=x)
        q = qnet(P); df = v.run(S, P); dq = q - base
        print(f"  {x:.2f} ATR: net ${q.sum():,.0f} (Δ ${dq.sum():+,.0f}) DD ${dd(df):,.0f} trades removed {len(full) - len(df):2d} "
              f"| Δ by quarter {dq.round().astype(int).tolist()} ({(dq > 0).sum()} up, {(dq < 0).sum()} down)")

    folds = [m.select([q for j, q in enumerate(SQ) if j != k], lambda s: None) for k in range(4)]
    b0 = pd.concat([v.run(SQ[k], folds[k]) for k in range(4)])
    b1 = pd.concat([v.run(SQ[k], dict(copy.deepcopy(folds[k]), atr_used_max=0.75)) for k in range(4)])
    print("\n2. Fixed 0.75 on the blind walk-forward folds (no refit)")
    for name, b in (("blind v3", b0), ("blind v3 + 0.75 ATR rule", b1)):
        print(f"  {name:26s} net ${b.net.sum():,.0f} DD ${dd(b):,.0f} quarters "
              f"{[round(b[b.date.isin({s.date for s in q})].net.sum()) for q in SQ]}")

    orig = m.candidates
    def with_atr():
        C = orig()
        for x in X:
            C[f"atr_used_max={x}"] = lambda P, x=x: P.__setitem__("atr_used_max", x)
        return C
    m.candidates = with_atr
    tot, picks = [], []
    for k in range(4):
        lines = []
        P = m.select([q for j, q in enumerate(SQ) if j != k], lines.append)
        tot.append(v.run(SQ[k], P)); picks.append(P.get("atr_used_max"))
    m.candidates = orig
    b2 = pd.concat(tot)
    print("\n3. ATR threshold offered to the walk-forward selection")
    print(f"  blind net ${b2.net.sum():,.0f} DD ${dd(b2):,.0f} quarters {[round(t.net.sum()) for t in tot]} "
          f"| threshold picked per fold {picks}")
