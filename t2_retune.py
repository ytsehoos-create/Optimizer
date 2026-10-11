"""Re-tune the combined T2 script (pine/T2_combined_v3.pine) on the latest chart data.

Rule (set 2026-10-11): only the last 12 months count. Every level must have worked
over the whole 12 months, and levels are tuned to the last 6 months. Re-run every
1-2 months on a fresh chart export.

Data: TradingView exports of CME_MINI:MNQ1! 5-min bars in data/mnq_5m_rth*.csv
(columns time, open, high, low, close, RTH VWAP). Files are read oldest first; a
later file only adds bars after the earlier ones end.

Simulator: run() is the Python port of the Pine script that reproduced TradingView's
Strategy Tester trade-for-trade (Oct 2025 - Oct 2026: 102 trades, within $18).
Bar-close decisions mirror the script; intrabar fills/exits use the engine conventions
(stop wins when a bar touches both, no target on the fill bar, 15:55 flatten).

Selection, greedy, one change at a time, best first:
  candidates  each weekday row: on/off, entry/stop/target +/-0.05 IB
              each setup+direction: entry/stop/target +/-0.05 IB on all its rows at once
  accept if   last-6-month net gains >= MIN_GAIN, and in >= 2 of its three 2-month blocks,
              and 12-month net gains too (the earlier 6 months cannot give back more),
              and every row the change touches is still net positive over the 12 months,
              and those rows had >= MIN_TRADES trades in the last 6 months (single rows rarely
              do, so most changes move a whole setup+direction; this blocks 2-trade "edges").

Usage:
  python3 t2_retune.py                   re-tune as of the last session in the data
  python3 t2_retune.py 2026-08-31        re-tune as of a past date
  python3 t2_retune.py --walkforward     test the process: re-tune every 2 months, trade the next 2 blind
"""
import copy
import glob
import math
import sys
from multiprocessing import Pool

import numpy as np
import pandas as pd

TICK, PV, COMM, SLIP = 0.25, 2.0, 1.24, 0.25
MIN_GAIN = 150.0
MIN_TRADES = 6          # trades in the last 6 months on the rows a change touches (before or after it)
DOW = ["Mon", "Tue", "Wed", "Thu", "Fri"]

# Script defaults (pine/T2_combined_v3.pine). rows: (setup, break dir, weekday) -> (entry, stop, target) in IB
# multiples. T2R: entry/stop beyond the broken edge, target back inside. T2X: entry/stop inside, target beyond.
CURRENT = dict(
    rows={("T2R", 1, 1): (.30, .50, .25), ("T2R", 1, 2): (.20, .30, .25), ("T2R", 1, 3): (.30, .50, .50),
          ("T2R", 1, 4): (.20, .30, .25),
          ("T2R", -1, 1): (.20, .30, .25), ("T2R", -1, 2): (.20, .30, .25), ("T2R", -1, 3): (.20, .30, .25),
          ("T2R", -1, 4): (.20, .30, .25),
          ("T2X", 1, 0): (.10, .30, .20), ("T2X", 1, 1): (.20, .60, .40), ("T2X", 1, 2): (.20, .60, .30),
          ("T2X", 1, 4): (.50, .60, .20),
          ("T2X", -1, 1): (.30, .60, .25), ("T2X", -1, 2): (.50, .60, .25), ("T2X", -1, 4): (.40, .60, .25)},
    risk={("T2R", 1, 2): 300, ("T2X", 1, 2): 300},     # $ per trade; everything else DEFAULT_RISK
    t2r_ib_mult=None,                                  # optional (lo %, hi %, x): T2R risk x when IB in [lo, hi) % of price
)
DEFAULT_RISK, MAX_RISK, CUT_R, CUT_X, LARGE_IB, FILTER_B, ALIGN = 200, 300, 1400, 1300, 0.9, 0.20, True
# Levels a row starts from when the search switches it on.
NEW_ROW = {("T2R", 1): (.20, .30, .25), ("T2R", -1): (.20, .30, .25),
           ("T2X", 1): (.20, .60, .30), ("T2X", -1): (.40, .60, .25)}
# The original v1 rows (before any fitting on this data), the walk-forward's starting point.
V1 = dict(CURRENT, rows={k: v for k, v in CURRENT["rows"].items() if k not in {("T2R", -1, 2), ("T2R", -1, 4)}})
V1["rows"].update({k: v[:2] + (.20,) for k, v in V1["rows"].items() if k[:2] == ("T2X", -1)})


# ----------------------------------------------------------------------------- data
def load_bars(pattern="data/mnq_5m_rth*.csv"):
    parts, last = [], -1
    for p in sorted(glob.glob(pattern), key=lambda p: pd.read_csv(p, usecols=["time"]).time.min()):
        raw = pd.read_csv(p)
        raw = raw[raw.time > last]
        if raw.empty:
            continue
        last = raw.time.max()
        parts.append(raw[["time", "open", "high", "low", "close", "RTH VWAP"]])
    raw = pd.concat(parts, ignore_index=True)
    dt = pd.to_datetime(raw.time, unit="s", utc=True).dt.tz_convert("America/New_York")
    df = pd.DataFrame(dict(date=dt.dt.strftime("%Y-%m-%d"), hm=dt.dt.hour * 100 + dt.dt.minute, dow=dt.dt.dayofweek,
                           open=raw.open, high=raw.high, low=raw.low, close=raw.close, vwap=raw["RTH VWAP"]))
    return df[(df.hm >= 930) & (df.hm < 1600)].reset_index(drop=True)


# ----------------------------------------------------------------------------- simulator
rt = lambda x: round(x / TICK) * TICK
cu = lambda x: math.ceil(x / TICK - 1e-6) * TICK
fl = lambda x: math.floor(x / TICK + 1e-6) * TICK


def lots_of(rp, risk):
    return max(1, math.floor(risk / (rp * PV)))


def closer(d, own, lvl):
    return own if lvl is None else (min(own, lvl) if d > 0 else max(own, lvl))


def run(df, P):
    rows, out, prev_close = P["rows"], [], None
    days = {k[2] for k in rows}
    for d, g in df.groupby("date", sort=True):
        g = g.reset_index(drop=True)
        if len(g) != 78:                     # holiday half-days (flattened by hand)
            continue
        o, h, l, c, vw, hmv = (g[k].to_numpy() for k in ("open", "high", "low", "close", "vwap", "hm"))
        dow = int(g.dow.iloc[0]); n = len(g)
        i0 = int((hmv < 1030).sum())
        ibH, ibL = h[:i0].max(), l[:i0].min(); R = ibH - ibL
        hiB, loB = int(h[:i0].argmax()), int(l[:i0].argmin()); c1030 = c[i0 - 1]
        pc = prev_close; prev_close = c[-1]
        if pc is None:
            continue
        gap = abs(o[0] - pc) / pc * 100
        ib_pct = R / c1030 * 100
        live = dow in days and not ib_pct > LARGE_IB
        rmult = 1.0
        if P.get("t2r_ib_mult") and P["t2r_ib_mult"][0] <= ib_pct < P["t2r_ib_mult"][1]:
            rmult = P["t2r_ib_mult"][2]
        # T1 setup (gates only)
        t1 = None
        ib2Hi, ib2Lo = hiB > loB, loB > hiB
        if R > 0 and (ib2Hi or ib2Lo) and gap < 1.0:
            zone = (ibH - c1030) / R * 100 if ib2Hi else (c1030 - ibL) / R * 100
            if zone <= 25:
                sd = 1 if ib2Hi else -1
                E = rt(ibH - .25 * R if ib2Hi else ibL + .20 * R); S_ = rt(ibH - .55 * R if ib2Hi else ibL + .45 * R)
                if not lots_of(abs(E - S_), DEFAULT_RISK) * abs(E - S_) * PV > MAX_RISK:
                    t1 = dict(st=1, side=sd, e=E, s=S_, t=rt(ibH if ib2Hi else ibL))
            elif 50 <= zone <= 75:
                sd = -1 if ib2Hi else 1
                S_ = rt(ibH - .25 * R if ib2Hi else ibL + .25 * R)
                if not lots_of(abs(c1030 - S_), DEFAULT_RISK) * abs(c1030 - S_) * PV > MAX_RISK:
                    t1 = dict(st=2, side=sd, e=c1030, s=S_, t=rt(ibL if ib2Hi else ibH), px=c1030, fill=i0 - 1)
        r = dict(st=0, dead=False, at=False, tout=None); x = dict(st=0, dead=False, at=False, tout=None, held=False)
        pos = None; brk = 0; brk_i = None; trades = []
        for i in range(i0, n):
            hm = hmv[i]; nxt = hmv[i + 1] if i + 1 < n else 1600
            # intrabar: resting orders fill (T2R first, then T2X), then the position is managed
            for k, st in (("T2R", r), ("T2X", x)):
                if not st["at"]:
                    continue
                sd, E = st["side"], st["e"]
                px = (min(o[i], E) if l[i] <= E else None) if sd > 0 else (max(o[i], E) if h[i] >= E else None)
                if px is None:
                    continue
                st["at"] = False
                if (sd > 0 and px <= st["s"]) or (sd < 0 and px >= st["s"]):
                    st["st"] = 3 if k == "T2R" else 4
                    continue
                if pos is not None:                     # opposite trade open: handoff at px
                    why = "target" if (pos["side"] > 0 and px >= pos["t"]) or (pos["side"] < 0 and px <= pos["t"]) else "reversed"
                    pos.update(exit=px, why=why, xi=i); trades.append(pos); pos = None
                pos = dict(tag=k, side=sd, lots=st["lots"], px=px, s=st["s"], t=st["tout"], fill=i, dead=st["dead"],
                           brk=st["brk"])
                st["st"] = 2 if k == "T2R" else 3
            if pos is not None and i >= pos["fill"]:
                sd = pos["side"]
                if (sd > 0 and l[i] <= pos["s"]) or (sd < 0 and h[i] >= pos["s"]):
                    gp = o[i] if ((sd > 0 and o[i] < pos["s"]) or (sd < 0 and o[i] > pos["s"])) else pos["s"]
                    pos.update(exit=gp, why="stop", xi=i)
                elif i > pos["fill"] and ((sd > 0 and h[i] >= pos["t"]) or (sd < 0 and l[i] <= pos["t"])):
                    pos.update(exit=pos["t"], why="target", xi=i)
                elif hm == 1555:
                    pos.update(exit=c[i], why="eod", xi=i)
                elif pos["dead"] and pos["fill"] == i:
                    pos.update(exit=c[i], why="dead order exited", xi=i)
                if "exit" in pos:
                    trades.append(pos); (r if pos["tag"] == "T2R" else x)["st"] = 3 if pos["tag"] == "T2R" else 4; pos = None
            # bar close: T1 shadow
            if t1 and t1["st"] == 1:
                if hm >= 1400:
                    t1["st"] = 5
                else:
                    sd, E = t1["side"], t1["e"]
                    if (sd > 0 and l[i] <= E) or (sd < 0 and h[i] >= E):
                        blocked = not (vw[i - 1] < E) if sd > 0 else not (vw[i - 1] > E)
                        px = min(o[i], E) if sd > 0 else max(o[i], E)
                        if blocked or (sd > 0 and px <= t1["s"]) or (sd < 0 and px >= t1["s"]):
                            t1["st"] = 5
                        else:
                            t1.update(st=2, px=px, fill=i)
            if t1 and t1["st"] == 2 and i >= t1["fill"]:
                sd = t1["side"]
                if (sd > 0 and l[i] <= t1["s"]) or (sd < 0 and h[i] >= t1["s"]):
                    t1["st"] = 4
                elif i > t1["fill"] and ((sd > 0 and h[i] >= t1["t"]) or (sd < 0 and l[i] <= t1["t"])):
                    t1["st"] = 3
                elif hm == 1555:
                    t1["st"] = 3 if (c[i] - t1["px"]) * sd > 0 else 4
            t1st = t1["st"] if t1 else 5
            t1In, t1Lost, t1Won = t1st in (2, 3, 4), t1st == 4, t1st == 3
            t1Side = t1["side"] if t1 else 0
            inTrade = pos is not None
            # gates (deferred while in a trade)
            if x["st"] == 2 and x["held"] and ((x["side"] > 0 and l[i] <= x["e"]) or (x["side"] < 0 and h[i] >= x["e"])):
                x["st"] = 4
            if r["st"] == 1 and not r["dead"]:
                if t1Won or nxt >= CUT_R:
                    if inTrade and r["at"]:
                        r["dead"] = True
                    else:
                        r["st"] = 3
            if x["st"] in (1, 2) and not x["dead"]:
                kill = t1Lost or (t1Won and t1Side != x["side"]) or nxt >= CUT_X or \
                       (x["st"] == 2 and dow == 0 and not t1In and t1st != 1)
                if kill:
                    if inTrade and x["at"]:
                        x["dead"] = True
                    else:
                        x["st"] = 4
            # first break
            if brk == 0:
                up, dn = h[i] > ibH, l[i] < ibL
                if up or dn:
                    brk = 2 if up and dn else (1 if up else -1); brk_i = i
                    if live and brk != 2:
                        isUp = brk == 1
                        lv = rows.get(("T2R", brk, dow)); ext = (h[i] - ibH) if isUp else (ibL - l[i])
                        if lv and ext < FILTER_B * R and nxt < CUT_R and not t1Won:
                            e, s_, t = lv
                            E = cu(ibH + e * R) if isUp else fl(ibL - e * R); S_ = cu(ibH + s_ * R) if isUp else fl(ibL - s_ * R)
                            T = fl(ibH - t * R) if isUp else cu(ibL + t * R)
                            nl = lots_of(abs(E - S_), P["risk"].get(("T2R", brk, dow), DEFAULT_RISK) * rmult)
                            if not (h[i] >= E if isUp else l[i] <= E) and not nl * abs(E - S_) * PV > MAX_RISK * rmult:
                                r.update(st=1, side=-1 if isUp else 1, e=E, s=S_, t=T, lots=nl, brk=brk)
                        lv = rows.get(("T2X", brk, dow))
                        if lv and nxt < CUT_X and not t1Lost and not (t1Won and t1Side != (1 if isUp else -1)):
                            e, s_, t = lv
                            E = fl(ibH - e * R) if isUp else cu(ibL + e * R); S_ = fl(ibH - s_ * R) if isUp else cu(ibL + s_ * R)
                            T = cu(ibH + t * R) if isUp else fl(ibL - t * R)
                            nl = lots_of(abs(E - S_), P["risk"].get(("T2X", brk, dow), DEFAULT_RISK))
                            if not nl * abs(E - S_) * PV > MAX_RISK:
                                x.update(st=1, side=1 if isUp else -1, e=E, s=S_, t=T, lots=nl, brk=brk)
            # T2X arming
            if x["st"] == 1 and i > brk_i and ((x["side"] > 0 and c[i] < ibH) or (x["side"] < 0 and c[i] > ibL)):
                x["st"] = 2
            # broker sync, only while flat
            x["held"] = False
            if not inTrade and 930 <= nxt < 1600:
                wantR = r["st"] == 1 and not r["dead"]
                r7 = x["st"] == 2 and not x["dead"] and dow == 0 and not t1In
                wantX = x["st"] == 2 and not x["dead"] and not r7
                x["held"] = r7
                tR = (closer(r["side"], r["t"], x["e"] if (ALIGN and wantX) else None)) if wantR else None
                tX = (closer(x["side"], x["t"], r["e"] if (ALIGN and wantR) else None)) if wantX else None
                stale = r["dead"] or x["dead"]
                changed = wantR != r["at"] or wantX != x["at"] or (wantR and tR != r["tout"]) or (wantX and tX != x["tout"])
                if changed or stale:
                    if r["dead"]:
                        r.update(st=3, dead=False)
                    if x["dead"]:
                        x.update(st=4, dead=False)
                    r["at"] = wantR; x["at"] = wantX
                    if wantR:
                        r["tout"] = tR
                    if wantX:
                        x["tout"] = tX
            if hm == 1555:
                r["at"] = x["at"] = False
        for p in trades:
            sd = p["side"]; pnl = (p["exit"] - p["px"]) * sd * p["lots"] * PV
            cost = p["lots"] * (COMM + (p["why"] == "stop") * SLIP * PV)
            out.append(dict(date=d, dow=dow, setup=p["tag"], brk=p["brk"], side="long" if sd > 0 else "short",
                            lots=p["lots"], entry=p["px"], stop=p["s"], target=p["t"], fill_hm=hmv[p["fill"]],
                            exit=p["exit"], exit_hm=hmv[p["xi"]], exit_why=p["why"], pnl=pnl, net=pnl - cost))
    cols = ["date", "dow", "setup", "brk", "side", "lots", "entry", "stop", "target", "fill_hm", "exit", "exit_hm",
            "exit_why", "pnl", "net"]
    return pd.DataFrame(out, columns=cols)


# ----------------------------------------------------------------------------- selection
def windows(dates, end, recent=6):
    """12-month window ending at `end`, its last `recent` months, and the three equal blocks of those."""
    end = pd.Timestamp(end)
    y0, h0 = end - pd.DateOffset(months=12), end - pd.DateOffset(months=recent)
    b = [end - pd.DateOffset(months=recent * m // 3) for m in (3, 2, 1, 0)]
    ts = pd.to_datetime(pd.Series(sorted(set(dates))))
    year = set(ts[(ts > y0) & (ts <= end)].dt.strftime("%Y-%m-%d"))
    blocks = [set(ts[(ts > b[k]) & (ts <= b[k + 1])].dt.strftime("%Y-%m-%d")) for k in range(3)]
    early = set(ts[(ts > y0) & (ts <= h0)].dt.strftime("%Y-%m-%d"))
    return year, early, blocks


def row_key(t):
    return (t.setup, t.brk, t.dow)


def score(T, W):
    year, early, blocks = W
    return np.array([T[T.date.isin(early)].net.sum()] + [T[T.date.isin(b)].net.sum() for b in blocks])


def row_year_net(T, W, keys):
    yr = T[T.date.isin(W[0])]
    return {k: yr[(yr.setup == k[0]) & (yr.brk == k[1]) & (yr.dow == k[2])].net.sum() for k in keys}


def recent_trades(T, W, keys):
    rec = T[T.date.isin(set().union(*W[2]))]
    return int(sum(((rec.setup == k[0]) & (rec.brk == k[1]) & (rec.dow == k[2])).sum() for k in keys))


def moves(P):
    M = {}
    rows = P["rows"]
    for setup in ("T2R", "T2X"):
        for brk in (1, -1):
            keys = [k for k in rows if k[0] == setup and k[1] == brk]
            for comp in range(3):
                for dlt in (-0.05, 0.05):
                    M[f"{setup} {'up' if brk > 0 else 'dn'} all rows {'EST'[comp]}{dlt:+.2f}"] = (keys, comp, dlt)
            for dow in range(5):
                k = (setup, brk, dow)
                M[f"{setup} {'up' if brk > 0 else 'dn'} {DOW[dow]} {'off' if k in rows else 'on'}"] = ([k], None, None)
                if k in rows:
                    for comp in range(3):
                        for dlt in (-0.05, 0.05):
                            M[f"{setup} {'up' if brk > 0 else 'dn'} {DOW[dow]} {'EST'[comp]}{dlt:+.2f}"] = ([k], comp, dlt)
    return M


def apply(P, mv):
    keys, comp, dlt = mv
    Q = copy.deepcopy(P)
    if comp is None:
        k = keys[0]
        if k in Q["rows"]:
            del Q["rows"][k]
        else:
            Q["rows"][k] = NEW_ROW[k[:2]]
        return Q, keys
    for k in keys:
        lv = list(Q["rows"][k]); lv[comp] = round(lv[comp] + dlt, 2)
        e, s, t = lv
        if e <= 0 or t <= 0 or s < e + 0.10 or (k[0] == "T2X" and s > 0.90) or (k[0] == "T2R" and t > 1.0):
            return None, keys
        Q["rows"][k] = tuple(lv)
    return Q, keys


_DF = None


def _init(df):
    global _DF
    _DF = df


def _eval(args):
    name, P, keys, W = args
    T = run(_DF, P)
    return name, P, keys, score(T, W), row_year_net(T, W, keys), recent_trades(T, W, keys)


def retune(df, P, end, log=print, recent=6):
    """Greedy re-tune of P on the 12 months ending `end` (bars after `end` are ignored)."""
    df = df[df.date <= end]
    W = windows(df.date.unique(), end, recent)
    before = [d for d in df.date.unique() if d < min(W[0])]
    if before:                                   # keep one prior session for the gap
        df = df[df.date >= max(before)]
    T = run(df, P)
    cur = score(T, W)
    with Pool(4, initializer=_init, initargs=(df,)) as pool:
        while True:
            jobs = []
            for name, mv in moves(P).items():
                Q, keys = apply(P, mv)
                if Q is not None:
                    jobs.append((name, Q, keys, W))
            best = None
            for name, Q, keys, x, rown, n in pool.imap_unordered(_eval, jobs, chunksize=4):
                d = x - cur
                gain = d[1:].sum()
                if gain < MIN_GAIN or (d[1:] > 0).sum() < 2 or d.sum() <= 0:
                    continue
                if any(v <= 0 for k, v in rown.items() if k in Q["rows"]):
                    continue
                if max(n, recent_trades(T, W, keys)) < MIN_TRADES:
                    continue
                if best is None or gain > best[0]:
                    best = (gain, name, Q, x)
            if best is None:
                return P
            gain, name, P, x = best
            T = run(df, P)
            recent = gain
            d = x - cur
            log(f"  + {name:28s} recent {recent:+7,.0f} (blocks {' '.join(f'{v:+,.0f}' for v in d[1:])})"
                f"  12 mo {d.sum():+7,.0f}")
            cur = x


# ----------------------------------------------------------------------------- reports
def fmt_row(k, lv):
    return f"{k[0]} {'up' if k[1] > 0 else 'dn'} {DOW[k[2]]}: {lv[0]:.2f}/{lv[1]:.2f}/{lv[2]:.2f}"


def diff(P0, P1):
    out = []
    for k in sorted(set(P0["rows"]) | set(P1["rows"]), key=lambda k: (k[0], -k[1], k[2])):
        a, b = P0["rows"].get(k), P1["rows"].get(k)
        if a != b:
            out.append(f"{k[0]} {'breakout' if k[1] > 0 else 'breakdown'} {DOW[k[2]]}: "
                       f"{'off' if a is None else '/'.join(f'{v:.2f}' for v in a)} -> "
                       f"{'off' if b is None else '/'.join(f'{v:.2f}' for v in b)}")
    return out


def summary(df, P, end, label):
    W = windows(df[df.date <= end].date.unique(), end)
    T = run(df[df.date <= end], P)
    x = score(T, W)
    yr = T[T.date.isin(W[0])]
    eq = yr.groupby("date").net.sum().cumsum()
    dd = float((eq.cummax().clip(lower=0) - eq).max()) if len(eq) else 0.0
    print(f"{label:34s} 12 mo ${x.sum():>7,.0f}  first 6 mo ${x[0]:>6,.0f}  last 6 mo ${x[1:].sum():>6,.0f} "
          f"(blocks {' '.join(f'{v:,.0f}' for v in x[1:])})  trades {len(yr)}  max DD ${dd:,.0f}")
    return T, W


def walkforward(df):
    """Re-tune every 2 months on the 12 months available (6-month objective), trade the next 2 months blind."""
    dates = sorted(df.date.unique())
    points = ["2026-03-31", "2026-05-31", "2026-07-31", "2026-09-30"]
    ends = points[1:] + [dates[-1]]
    res = {"6-mo tune every 2 months (from v1)": [], "6-mo tune once at Mar 31 (from v1)": [],
           "12-mo tune every 2 months (from v1)": [], "v1 levels, never tuned": [],
           "current script levels (fit on all data)": []}
    P, P_once, P12 = V1, None, V1
    for a, b in zip(points, ends):
        print(f"\nre-tune at {a} (data {dates[0]} .. {a}), 6-month objective:")
        P = retune(df, P, a)
        print(f"re-tune at {a}, 12-month objective:")
        P12 = retune(df, P12, a, recent=12)
        for line in diff(V1, P):
            print("   6-mo vs v1:", line)
        if P_once is None:
            P_once = P
        seg = df[(df.date >= df[df.date <= a].date.max()) & (df.date <= b)]
        for name, Q in (("6-mo tune every 2 months (from v1)", P), ("6-mo tune once at Mar 31 (from v1)", P_once),
                        ("12-mo tune every 2 months (from v1)", P12),
                        ("v1 levels, never tuned", V1), ("current script levels (fit on all data)", CURRENT)):
            T = run(seg, Q)
            res[name].append(T[T.date > a])
    print(f"\nblind months {points[0][:7]}+1 .. {ends[-1]}  (2-month blocks)")
    for name, parts in res.items():
        T = pd.concat(parts)
        eq = T.groupby("date").net.sum().cumsum()
        dd = float((eq.cummax().clip(lower=0) - eq).max())
        print(f"  {name:42s} ${T.net.sum():>7,.0f}  max DD ${dd:>5,.0f}  trades {len(T):3d}  blocks "
              + " ".join(f"{p.net.sum():>6,.0f}" for p in parts))


if __name__ == "__main__":
    df = load_bars()
    if len(sys.argv) > 1 and sys.argv[1] == "--walkforward":
        walkforward(df)
        sys.exit()
    end = sys.argv[1] if len(sys.argv) > 1 else df.date.max()
    print(f"data {df.date.min()} .. {df.date.max()}; re-tune as of {end}\n")
    summary(df, CURRENT, end, "current script levels")
    print("\nchanges accepted:")
    P = retune(df, CURRENT, end)
    T, W = summary(df, P, end, "\nre-tuned levels")
    print("\nPine input changes:")
    for line in diff(CURRENT, P) or ["(none)"]:
        print("  ", line)
    yr = T[T.date.isin(W[0])]; recent = T[T.date.isin(set().union(*W[2]))]
    print("\nrows, 12-month and last-6-month net:")
    for k, lv in sorted(P["rows"].items(), key=lambda kv: (kv[0][0], -kv[0][1], kv[0][2])):
        a = yr[(yr.setup == k[0]) & (yr.brk == k[1]) & (yr.dow == k[2])]
        b = recent[(recent.setup == k[0]) & (recent.brk == k[1]) & (recent.dow == k[2])]
        print(f"  {fmt_row(k, lv):30s} 12 mo {len(a):2d} trades ${a.net.sum():>7,.0f}   last 6 mo {len(b):2d} trades ${b.net.sum():>7,.0f}")
