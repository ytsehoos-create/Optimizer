"""v3 selection: stepwise, rationale-backed rule changes + small level nudges,
validated walk-forward.

Why not a free grid search: with lots sized to a fixed $300 risk, P&L is
R-multiples x $300, and an unconstrained grid over ~250 sessions finds
tiny-stop / far-target lottery cells that do not survive out of sample
(see mnq_v3_optimize.py: blind quarters -$2.3K vs v1 +$20.4K).

Procedure select(train):
  1. Start from v1 made executable (opposite positions -> reverse, not hedge).
  2. Stepwise: try every candidate change on top of the current set; accept the
     best one if it adds > $250 net AND improves at least all-but-one of the
     training quarters. Repeat until nothing qualifies.
  3. Level nudges: shift each setup/direction's entry, stop or target by
     +/-0.05 IB (all day-cells together; stop >= entry + 0.10 IB), same
     acceptance rule, repeat until nothing qualifies.
Walk-forward: select() on 3 quarters, trade the 4th blind; 4 folds.
The final V3 in mnq_v3.py is this full-year selection with Zone 3a kept ON
(selection drops it for +$1.8K, but it raises max DD $1,490 -> $2,350).
"""
import copy
import json
import sys
from multiprocessing import Pool

import numpy as np

import mnq_v3 as v

SESSIONS = v.load_sessions()
QIDX = np.array_split(np.arange(len(SESSIONS)), 4)
MIN_GAIN = 250.0


def base_params():
    P = copy.deepcopy(v.V1)
    P["conflict"] = "close_other"
    P["t2r"].update({"up": (0.3, 0.5, 0.25), "dn": (0.2, 0.3, 0.25)})   # defaults for newly enabled days
    P["t2x"].update({"up": (0.2, 0.6, 0.3), "dn": (0.4, 0.6, 0.2)})
    return P


def candidates():
    C = {}
    def put(name, fn):
        C[name] = fn
    for k, val in (("r1", False), ("r3", False), ("r6", False), ("r7", False),
                   ("cancel_on_double", True), ("t2x_arm", "touch"), ("vwap", False),
                   ("z3a", False), ("t1_cancel_on_break", True), ("conflict", "block"),
                   ("filter_b", 0.20), ("filter_b", 0.30), ("gap_max", 0.75), ("gap_max", 1.25),
                   ("z1_max", 20), ("z1_max", 30), ("brk_cutoff", 1200), ("brk_cutoff", 1300),
                   ("t2r_cutoff", 1300), ("t2x_cutoff", 1200), ("t2x_cutoff", 1400)):
        put(f"{k}={val}", lambda P, k=k, val=val: P.__setitem__(k, val))
    for x in (0.7, 1.2, 1.5):
        put(f"large_ib={x}", lambda P, x=x: P.__setitem__("large_ib", {d: x for d in range(5)}))
    for d in range(5):
        put(f"t1_day{d} toggle", lambda P, d=d: P.__setitem__("t1_days", set(P["t1_days"]) ^ {d}))
        for setup in ("t2r", "t2x"):
            for side in ("up", "dn"):
                def fn(P, d=d, setup=setup, side=side):
                    P[f"{setup}_days"] = copy.deepcopy(P[f"{setup}_days"])
                    P[f"{setup}_days"][side] = set(P[f"{setup}_days"][side]) ^ {d}
                put(f"{setup}_{side}_{v.DOW[d]} toggle", fn)
    # The infographic's per-cell grids are deliberately NOT candidates: they were fit on
    # data covering every test quarter, which would leak into the walk-forward.
    return C


def nudges():
    """Shift one component of a whole setup/direction by +/-0.05 IB."""
    N = {}
    for setup in ("t2r", "t2x"):
        for side in ("up", "dn"):
            for comp in (0, 1, 2):
                for dlt in (-0.05, 0.05):
                    def fn(P, setup=setup, side=side, comp=comp, dlt=dlt):
                        cells = {}
                        for k, lv in P[setup].items():
                            if (k == side) or (isinstance(k, tuple) and k[0] == side):
                                lv = list(lv); lv[comp] = round(lv[comp] + dlt, 2); lv = tuple(lv)
                                if lv[0] <= 0 or lv[2] <= 0 or lv[1] < lv[0] + 0.10:
                                    return False
                            cells[k] = lv
                        P[setup] = cells
                    N[f"{setup}_{side}[{'EST'[comp]}]{dlt:+.2f}"] = fn
    for side in ("long", "short"):
        for comp in ("e", "s", "t"):
            for dlt in (-0.05, 0.05):
                def fn(P, side=side, comp=comp, dlt=dlt):
                    P[f"z1_{side}_{comp}"] = round(P[f"z1_{side}_{comp}"] + dlt, 2)
                    if P[f"z1_{side}_s"] < P[f"z1_{side}_e"] + 0.10 or P[f"z1_{side}_e"] <= 0:
                        return False
                N[f"z1_{side}[{comp}]{dlt:+.2f}"] = fn
    return N


def quarter_net(P, sess_q):
    df = v.run([s for q in sess_q for s in q], P)
    return np.array([df[df.date.isin({s.date for s in q})].net.sum() for q in sess_q])


def stepwise(P, sess_q, moves, log, tag):
    cur = quarter_net(P, sess_q)
    need = len(sess_q) - 1
    while True:
        best = None
        for name, fn in moves.items():
            Q = copy.deepcopy(P)
            if fn(Q) is False:
                continue
            x = quarter_net(Q, sess_q)
            gain = (x - cur).sum()
            if gain > MIN_GAIN and ((x - cur) > 0).sum() >= need and (best is None or gain > best[0]):
                best = (gain, name, Q, x)
        if best is None:
            return P
        gain, name, P, x = best
        log(f"{tag} + {name}: +${gain:.0f}  quarters {np.round(x - cur).astype(int).tolist()}")
        cur = x


def select(train_q, log):
    P = base_params()
    P = stepwise(P, train_q, candidates(), log, "rule")
    P = stepwise(P, train_q, nudges(), log, "level")
    P = stepwise(P, train_q, candidates(), log, "rule2")
    return P


def to_json(P):
    def conv(x):
        if isinstance(x, set):
            return sorted(x)
        if isinstance(x, dict):
            return {("|".join(map(str, k)) if isinstance(k, tuple) else str(k)): conv(y) for k, y in x.items()}
        return x
    return conv(P)


def job(k):
    sess_q = [[SESSIONS[i] for i in q] for q in QIDX]
    train = [q for j, q in enumerate(sess_q) if j != k]
    lines = []
    P = select(train, lines.append)
    return k, P, lines


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "output/2026.09.24-mnq-ib-v3"
    import os
    os.makedirs(out, exist_ok=True)
    sess_q = [[SESSIONS[i] for i in q] for q in QIDX]
    with Pool(4) as pool:
        res = pool.map(job, [0, 1, 2, 3])
    folds = []
    for k, P, lines in res:
        test = sess_q[k]
        row = {"fold": k, "test": f"{test[0].date}..{test[-1].date}"}
        for name, PP in (("v3_blind", P), ("v1", v.V1), ("v1_exec", base_params()), ("v2i", v.V2I)):
            df = v.run(test, PP)
            row[name] = round(float(df.net.sum()))
        folds.append(row)
        open(f"{out}/wf_fold{k}_log.txt", "w").write("\n".join(lines))
        json.dump(to_json(P), open(f"{out}/wf_fold{k}_params.json", "w"), indent=1)
        print(row, flush=True)
    tot = {k: sum(r[k] for r in folds) for k in ("v3_blind", "v1", "v1_exec", "v2i")}
    print("walk-forward totals (net):", tot)
    json.dump({"folds": folds, "totals": tot}, open(f"{out}/walkforward.json", "w"), indent=1)
    lines = []
    P = select(sess_q, lines.append)
    open(f"{out}/v3_selection_log.txt", "w").write("\n".join(lines))
    json.dump(to_json(P), open(f"{out}/v3_params.json", "w"), indent=1)
    print("\n".join(lines))
