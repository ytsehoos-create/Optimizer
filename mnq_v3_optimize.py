"""Robust optimizer + walk-forward validation for the MNQ IB suite (v3).

Method
  * Objective on a training set (net of costs): J = total + min(half1, half2) - 0.5 * maxDD,
    where half1/half2 are the chronological halves of the training set. A parameter
    only scores well if it earns in both halves.
  * Level grids (entry/stop/target) are scored after smoothing each point with its
    grid neighbours (plateau selection, not peak selection).
  * Coordinate descent over parameter groups, 2 passes.
  * Walk-forward: 4 quarterly folds. For each fold, optimize on the other three
    quarters and trade the held-out quarter blind. The sum of the four blind
    quarters is the honest estimate of the method; the final v3 is then fit on
    all 12 months.

Usage: python mnq_v3_optimize.py   (writes output/…/v3_params.json and fold results)
"""
import copy
import itertools
import json
import sys
from multiprocessing import Pool

import numpy as np

import mnq_v3 as v

SESSIONS = v.load_sessions()
ALL = [0, 1, 2, 3, 4]
F = lambda a, b, st: [round(x, 2) for x in np.arange(a, b + 1e-9, st)]


def score(P, sess):
    df = v.run(sess, P)
    dates = [s.date for s in sess]
    mid = dates[len(dates) // 2]
    a = df[df.date < mid].net.sum()
    b = df[df.date >= mid].net.sum()
    m = v.metrics(df, col="net")
    return a + b + min(a, b) - 0.5 * m["dd"]


def smooth(grid_scores, shape):
    """Mean over the 3^k neighbourhood (edges clipped)."""
    arr = np.array(grid_scores).reshape(shape)
    out = np.zeros_like(arr)
    it = np.ndindex(*shape)
    for idx in it:
        sl = tuple(slice(max(0, j - 1), j + 2) for j in idx)
        out[idx] = arr[sl].mean()
    return out.ravel()


def best_of(P, sess, setter, options, shape=None):
    scores = []
    for opt in options:
        Q = copy.deepcopy(P)
        setter(Q, opt)
        scores.append(score(Q, sess))
    sm = smooth(scores, shape) if shape else np.array(scores)
    k = int(np.argmax(sm))
    Q = copy.deepcopy(P)
    setter(Q, options[k])
    return Q, options[k], scores[k]


def set_key(key):
    def f(Q, val):
        Q[key] = val
    return f


def set_levels(kind, d):
    def f(Q, val):
        e, r, t = val
        Q[kind] = {k: x for k, x in Q[kind].items() if not (isinstance(k, tuple) and k[0] == d)}
        Q[kind][d] = (e, round(e + r, 2), t)
    return f


def set_z1(side):
    def f(Q, val):
        e, r, t = val
        Q[f"z1_{side}_e"], Q[f"z1_{side}_s"], Q[f"z1_{side}_t"] = e, round(e + r, 2), t
    return f


def opt_days(P, sess, key, d=None):
    """Greedy day-mask selection: drop/add single days while J improves."""
    cur = set(P[key][d] if d else P[key])
    def setter(Q, days):
        if d:
            Q[key] = dict(Q[key]); Q[key][d] = set(days)
        else:
            Q[key] = set(days)
    base = score(P, sess)
    improved = True
    while improved:
        improved = False
        for day in ALL:
            cand = cur ^ {day}
            Q = copy.deepcopy(P); setter(Q, cand)
            s = score(Q, sess)
            if s > base + 50:          # require a material gain to change a day
                base, cur, P, improved = s, cand, Q, True
    return P


def optimize(sess, start=None, passes=2, log=None):
    P = copy.deepcopy(start or v.V1)
    P["conflict"] = "close_other"           # opposite positions must be executable
    # per-direction levels replace per-day cells as the starting point
    P["t2r"] = {"up": (0.3, 0.5, 0.25), "dn": (0.2, 0.3, 0.25)}
    P["t2x"] = {"up": (0.2, 0.6, 0.3), "dn": (0.4, 0.6, 0.2)}
    T2R_G = list(itertools.product(F(.10, .45, .05), F(.05, .30, .05), F(.05, .60, .05)))
    T2X_G = list(itertools.product(F(.05, .60, .05), F(.05, .40, .05), F(.05, .60, .05)))
    Z1_G = list(itertools.product(F(.10, .40, .05), F(.15, .45, .05), [-.10, -.05, 0, .05, .10]))
    for p in range(passes):
        steps = [
            ("rules", None),
            ("z1_long", lambda P: best_of(P, sess, set_z1("long"), Z1_G, (7, 7, 5))),
            ("z1_short", lambda P: best_of(P, sess, set_z1("short"), Z1_G, (7, 7, 5))),
            ("z1_max", lambda P: best_of(P, sess, set_key("z1_max"), [15, 20, 25, 30, 35], (5,))),
            ("gap_max", lambda P: best_of(P, sess, set_key("gap_max"), [0.75, 1.0, 1.25, 1.5, 99], (5,))),
            ("z3a_s", lambda P: best_of(P, sess, set_key("z3a_s"), [0.15, 0.2, 0.25, 0.3, 0.35], (5,))),
            ("t1_cutoff", lambda P: best_of(P, sess, set_key("t1_cutoff"), [1200, 1300, 1400, 1500], (4,))),
            ("t2r_up", lambda P: best_of(P, sess, set_levels("t2r", "up"), T2R_G, (8, 6, 12))),
            ("t2r_dn", lambda P: best_of(P, sess, set_levels("t2r", "dn"), T2R_G, (8, 6, 12))),
            ("t2x_up", lambda P: best_of(P, sess, set_levels("t2x", "up"), T2X_G, (12, 8, 12))),
            ("t2x_dn", lambda P: best_of(P, sess, set_levels("t2x", "dn"), T2X_G, (12, 8, 12))),
            ("filter_b", lambda P: best_of(P, sess, set_key("filter_b"), [0.15, 0.2, 0.25, 0.3, 0.4, 9], (6,))),
            ("large_ib", lambda P: best_of(P, sess, set_key("large_ib"),
                                           [{d: x for d in ALL} for x in (0.7, 0.9, 1.1, 1.3, 1.5, 99)], (6,))),
            ("t2r_cutoff", lambda P: best_of(P, sess, set_key("t2r_cutoff"), [1200, 1300, 1400, 1500], (4,))),
            ("t2x_cutoff", lambda P: best_of(P, sess, set_key("t2x_cutoff"), [1100, 1200, 1300, 1400, 1500], (5,))),
            ("brk_cutoff", lambda P: best_of(P, sess, set_key("brk_cutoff"), [1100, 1200, 1300, 1400, 1600], (5,))),
            ("days", None),
        ]
        for name, fn in steps:
            if name == "rules":
                for key, opts in (("vwap", [True, False]), ("z3a", [True, False]),
                                  ("t1_cancel_on_break", [True, False]), ("cancel_on_double", [True, False]),
                                  ("conflict", ["close_other", "block"]), ("t2x_arm", ["close", "touch"]),
                                  ("r1", [True, False]), ("r3", [True, False]),
                                  ("r6", [True, False]), ("r7", [True, False])):
                    P, val, s = best_of(P, sess, set_key(key), opts)
                    if log: log(f"pass{p} {key}={val} J={s:.0f}")
            elif name == "days":
                P = opt_days(P, sess, "t1_days")
                for d in ("up", "dn"):
                    P = opt_days(P, sess, "t2r_days", d)
                    P = opt_days(P, sess, "t2x_days", d)
                if log: log(f"pass{p} days t1={sorted(P['t1_days'])} t2r={ {k: sorted(x) for k, x in P['t2r_days'].items()} } "
                            f"t2x={ {k: sorted(x) for k, x in P['t2x_days'].items()} }")
            else:
                P, val, s = fn(P)
                if log: log(f"pass{p} {name}={val} J={s:.0f}")
    return P


def to_json(P):
    def conv(x):
        if isinstance(x, set):
            return sorted(x)
        if isinstance(x, dict):
            return {("|".join(map(str, k)) if isinstance(k, tuple) else str(k)): conv(y) for k, y in x.items()}
        if isinstance(x, (np.floating, np.integer)):
            return x.item()
        return x
    return conv(P)


def fold_job(k):
    q = np.array_split(np.arange(len(SESSIONS)), 4)
    test_idx = set(q[k]) if k is not None else set()
    train = [s for i, s in enumerate(SESSIONS) if i not in test_idx]
    lines = []
    P = optimize(train, log=lines.append)
    return k, P, lines


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "output/2026.09.24-mnq-ib-v3"
    import os
    os.makedirs(out, exist_ok=True)
    with Pool(4) as pool:
        results = pool.map(fold_job, [0, 1, 2, 3])
    q = np.array_split(np.arange(len(SESSIONS)), 4)
    folds = []
    for k, P, lines in results:
        test = [SESSIONS[i] for i in q[k]]
        row = {"fold": k, "test_from": test[0].date, "test_to": test[-1].date}
        for name, PP in (("v3_blind", P), ("v1", v.V1), ("v2i", v.V2I)):
            df = v.run(test, PP)
            row[name + "_gross"] = round(df.pnl.sum(), 2)
            row[name + "_net"] = round(df.net.sum(), 2)
            row[name + "_n"] = len(df)
        folds.append(row)
        with open(f"{out}/fold{k}_params.json", "w") as f:
            json.dump(to_json(P), f, indent=1)
        with open(f"{out}/fold{k}_log.txt", "w") as f:
            f.write("\n".join(lines))
        print(row, flush=True)
    json.dump(folds, open(f"{out}/walkforward.json", "w"), indent=1)
    _, P, lines = fold_job(None)
    json.dump(to_json(P), open(f"{out}/v3_params.json", "w"), indent=1)
    open(f"{out}/v3_fit_log.txt", "w").write("\n".join(lines))
    print("\n".join(lines))
