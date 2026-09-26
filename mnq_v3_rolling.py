"""Does re-tuning on recent months beat fixed rules? Monthly rolling walk-forward.

Each month M: select rules with mnq_v3_select.select() using only the sessions in
the lookback window before M (split into 3 equal chunks; a change must add net P&L
in >= 2 of 3 chunks), then trade month M blind. Risk cap from argv (default $200).
"""
import sys
import numpy as np
import pandas as pd
import mnq_v3 as v
import mnq_v3_select as m

v.RISK_CAP = float(sys.argv[1]) if len(sys.argv) > 1 else 200.0
S = m.SESSIONS
months = sorted({s.date[:7] for s in S})


def chunks(sess, k=3):
    return [list(c) for c in np.array_split(np.array(sess, dtype=object), k)]


def run_mode(lookback):          # lookback in months; None = expanding (all prior data)
    out = []
    for i, mo in enumerate(months):
        start = 0 if lookback is None else i - lookback
        if i < 6 or start < 0:   # common test window: last 7 months need 6 months of history
            continue
        train = [s for s in S if months[start] <= s.date[:7] < mo]
        P = m.select(chunks(train), lambda s: None)
        test = [s for s in S if s.date[:7] == mo]
        df = v.run(test, P)
        out.append((mo, df.net.sum(), df))
    return out


def fixed(P):
    out = []
    for i, mo in enumerate(months):
        if i < 6:
            continue
        test = [s for s in S if s.date[:7] == mo]
        df = v.run(test, P)
        out.append((mo, df.net.sum(), df))
    return out


def summarize(name, res):
    df = pd.concat([r[2] for r in res])
    d = df.groupby("date").net.sum().cumsum()
    dd = float((d.cummax().clip(lower=0) - d).max())
    print(f"{name:34s} net ${df.net.sum():>8,.0f}  DD ${dd:>6,.0f}  n {len(df):3d}  months " +
          " ".join(f"{r[1]:>6,.0f}" for r in res))


if __name__ == "__main__":
    print("test months:", " ".join(mo for mo in months[6:]))
    summarize("fixed v1", fixed(v.V1))
    summarize("rolling 3-month re-tune", run_mode(3))
    summarize("rolling 6-month re-tune", run_mode(6))
    summarize("expanding (all prior data)", run_mode(None))
    summarize("v3 (fit on full year; in-sample)", fixed(v.V3))
