"""MNQ IB suite v3 engine: state-machine simulation of T1 / T2R / T2X.

Unlike mnq_ib_backtest.py (which reproduces the v1/v2 spec), this engine makes
no assumption about the order in which setups trigger. Every bar is processed
in the same fixed order and every rule reads only the state known at that bar:

  1. Pending limit orders try to fill (gates checked at the fill moment).
  2. Open positions check stop, then target (stop wins if both are touched;
     no target on the fill bar), then the 15:55 flatten.
  3. Break bookkeeping from this bar's high/low: first break creates the
     T2R/T2X orders (live from the next bar); an opposite-side break
     (double break) can cancel pending post-break orders.
  4. T2X arming from this bar's close (back inside the IB).

Prices: $2/pt, lots = max(1, floor(300 / (risk_pts * 2))), gross of costs.
"""
from dataclasses import dataclass

import numpy as np
import pandas as pd

PT, RISK_CAP = 2.0, 300.0
COMMISSION_RT = 1.24     # $ per contract round trip (typical MNQ all-in)
SLIP_PTS = 0.25          # 1 tick adverse slippage on stop exits and market entries
DOW = ["Mon", "Tue", "Wed", "Thu", "Fri"]


def lots_for(risk):
    return max(1, int(RISK_CAP // (risk * PT)))


@dataclass
class Session:
    date: str
    dow: int
    o: np.ndarray
    h: np.ndarray
    l: np.ndarray
    c: np.ndarray
    vw: np.ndarray
    hm: np.ndarray
    i0: int
    ibh: float
    ibl: float
    rng: float
    ib2: str | None
    c1030: float
    gap: float


def load_sessions(path="data/mnq_5m_rth_12mo.csv"):
    raw = pd.read_csv(path)
    dt = pd.to_datetime(raw.time, unit="s", utc=True).dt.tz_convert("America/New_York")
    raw["date"] = dt.dt.strftime("%Y-%m-%d")
    raw["hm"] = dt.dt.hour * 100 + dt.dt.minute
    rth = raw[(raw.hm >= 930) & (raw.hm < 1600)]
    out, prev_close = [], None
    for d, g in rth.groupby("date"):
        if len(g) != 78:          # holiday half-days
            continue
        o, h, l, c = (g[k].to_numpy(float) for k in ("open", "high", "low", "close"))
        hm = g.hm.to_numpy()
        i0 = int((hm < 1030).sum())
        ibh, ibl = h[:i0].max(), l[:i0].min()
        hi_i, lo_i = int(h[:i0].argmax()), int(l[:i0].argmin())
        ib2 = "hi" if hi_i > lo_i else ("lo" if lo_i > hi_i else None)
        gap = abs(o[0] - prev_close) / prev_close * 100 if prev_close else None
        if gap is not None:
            out.append(Session(d, pd.Timestamp(d).dayofweek, o, h, l, c,
                               g["RTH VWAP"].to_numpy(float), hm, i0, ibh, ibl,
                               ibh - ibl, ib2, c[i0 - 1], gap))
        prev_close = c[-1]
    return out


@dataclass
class Pos:
    setup: str
    side: int
    entry: float
    stop: float
    target: float
    lots: int
    state: str = "pending"   # pending / open / closed / cancelled
    fill_i: int = -1
    exit_i: int = -1
    exit_px: float = 0.0
    why: str = ""

    @property
    def pnl(self):
        return (self.exit_px - self.entry) * self.side * self.lots * PT if self.state == "closed" else 0.0

    @property
    def cost(self):
        slips = (self.why == "stop") + (self.setup == "T1-Z3a")
        return self.lots * (COMMISSION_RT + slips * SLIP_PTS * PT) if self.state == "closed" else 0.0

    def won(self):
        return self.state == "closed" and self.pnl > 0

    def lost(self):
        return self.state == "closed" and self.pnl <= 0


def _mk(setup, side, entry, stop, target):
    return Pos(setup, side, entry, stop, target, lots_for(abs(entry - stop)))


def simulate(S: Session, P: dict):
    """Run one session under parameter dict P. Returns (positions, info)."""
    R, ibh, ibl, dow = S.rng, S.ibh, S.ibl, S.dow
    n, i0 = len(S.c), S.i0
    info = {"brk": None, "dbl": False, "skip": []}
    pos = {}

    # ---- T1 (armed at 10:30) ----
    if S.ib2 and R > 0 and S.gap < P["gap_max"] and dow in P["t1_days"]:
        dist = (ibh - S.c1030) if S.ib2 == "hi" else (S.c1030 - ibl)
        zone = dist / R * 100
        info["zone"] = zone
        if zone <= P["z1_max"]:
            if S.ib2 == "hi":
                pos["T1"] = _mk("T1-Z1", +1, ibh - P["z1_long_e"] * R, ibh - P["z1_long_s"] * R,
                                ibh - P["z1_long_t"] * R)
            else:
                pos["T1"] = _mk("T1-Z1", -1, ibl + P["z1_short_e"] * R, ibl + P["z1_short_s"] * R,
                                ibl + P["z1_short_t"] * R)
        elif P["z3a"] and P["z3a_lo"] <= zone <= P["z3a_hi"]:
            side = -1 if S.ib2 == "hi" else +1
            stop = ibh - P["z3a_s"] * R if S.ib2 == "hi" else ibl + P["z3a_s"] * R
            tgt = ibl if S.ib2 == "hi" else ibh
            t = _mk("T1-Z3a", side, S.c1030, stop, tgt)
            t.state, t.fill_i = "open", i0 - 1
            pos["T1"] = t

    large = R / S.c1030 * 100 > P["large_ib"][dow]

    def opposite_open(side):
        return [p for p in pos.values() if p.state == "open" and p.side == -side]

    def try_fill(p, i, gate=None):
        o, h, l = S.o[i], S.h[i], S.l[i]
        px = (min(o, p.entry) if l <= p.entry else None) if p.side > 0 else \
             (max(o, p.entry) if h >= p.entry else None)
        if px is None:
            return
        if gate:
            p.state, p.why = "cancelled", gate
            return
        if (p.side > 0 and px <= p.stop) or (p.side < 0 and px >= p.stop):
            p.state, p.why = "cancelled", "gapped through stop"
            return
        opp = opposite_open(p.side)
        if opp:
            if P["conflict"] == "block":
                return                      # stay pending until the other side is flat
            if P["conflict"] == "close_other":
                for q in opp:
                    q.state, q.exit_i, q.exit_px, q.why = "closed", i, px, "reversed"
        p.entry, p.state, p.fill_i = px, "open", i

    t2x_armed = False
    for i in range(i0, n):
        hm = S.hm[i]
        # 1. pending fills
        t1 = pos.get("T1")
        if t1 and t1.state == "pending":
            if hm >= P["t1_cutoff"]:
                t1.state, t1.why = "cancelled", "cutoff"
            else:
                vw = S.vw[i - 1]
                gate = None
                if P["vwap"] and ((t1.side > 0 and not vw < t1.entry) or (t1.side < 0 and not vw > t1.entry)):
                    gate = "VWAP"
                try_fill(t1, i, gate)
        t2r = pos.get("T2R")
        if t2r and t2r.state == "pending":
            if hm >= P["t2r_cutoff"]:
                t2r.state, t2r.why = "cancelled", "cutoff"
            else:
                gate = "R1 (T1 won)" if P["r1"] and t1 and t1.won() else None
                try_fill(t2r, i, gate)
        t2x = pos.get("T2X")
        if t2x and t2x.state == "pending" and t2x_armed:
            if hm >= P["t2x_cutoff"]:
                t2x.state, t2x.why = "cancelled", "cutoff"
            else:
                t1_in = t1 is not None and t1.state in ("open", "closed")
                t2r_in = t2r is not None and t2r.state in ("open", "closed")
                gate = None
                if P["r3"] and t1 and t1.lost():
                    gate = "R3 (T1 lost)"
                elif P["r6"] and not t1_in and not t2r_in:
                    gate = "R6 (T1 & T2R out)"
                elif P["r7"] and dow == 0 and not t1_in:
                    gate = "R7 (Mon, no T1)"
                try_fill(t2x, i, gate)
        # 2. manage open positions
        for p in pos.values():
            if p.state != "open" or i < p.fill_i:
                continue
            h, l = S.h[i], S.l[i]
            if (p.side > 0 and l <= p.stop) or (p.side < 0 and h >= p.stop):
                gp = S.o[i] if ((p.side > 0 and S.o[i] < p.stop) or (p.side < 0 and S.o[i] > p.stop)) else p.stop
                p.state, p.exit_i, p.exit_px, p.why = "closed", i, gp, "stop"
            elif i > p.fill_i and ((p.side > 0 and h >= p.target) or (p.side < 0 and l <= p.target)):
                p.state, p.exit_i, p.exit_px, p.why = "closed", i, p.target, "target"
            elif hm == 1555:
                p.state, p.exit_i, p.exit_px, p.why = "closed", i, S.c[i], "eod"
        # 3. break bookkeeping
        up, dn = S.h[i] > ibh, S.l[i] < ibl
        if info["brk"] is None and (up or dn):
            info["brk"] = "both" if up and dn else ("up" if up else "dn")
            info["brk_hm"] = hm
            brk = info["brk"]
            t1 = pos.get("T1")
            if t1 and t1.state == "pending" and P["t1_cancel_on_break"] and brk != "both":
                t1_tgt_side = "up" if t1.side > 0 else "dn"
                if t1.setup == "T1-Z1" and brk == t1_tgt_side:
                    t1.state, t1.why = "cancelled", "target side broke before fill"
            if brk != "both" and hm < P["brk_cutoff"] and not large:
                ext = (S.h[i] - ibh) if brk == "up" else (ibl - S.l[i])
                c = P["t2r"].get((brk, dow), P["t2r"].get(brk))
                if c and dow in P["t2r_days"][brk] and ext < P["filter_b"] * R:
                    e, s_, t = c
                    pos["T2R"] = (_mk("T2R", -1, ibh + e * R, ibh + s_ * R, ibh - t * R) if brk == "up"
                                  else _mk("T2R", +1, ibl - e * R, ibl - s_ * R, ibl + t * R))
                c = P["t2x"].get((brk, dow), P["t2x"].get(brk))
                if c and dow in P["t2x_days"][brk]:
                    e, s_, t = c
                    pos["T2X"] = (_mk("T2X", +1, ibh - e * R, ibh - s_ * R, ibh + t * R) if brk == "up"
                                  else _mk("T2X", -1, ibl + e * R, ibl + s_ * R, ibl - t * R))
            brk_i = i
        elif info["brk"] in ("up", "dn") and not info["dbl"] and ((info["brk"] == "up" and dn) or (info["brk"] == "dn" and up)):
            info["dbl"] = True
            if P["cancel_on_double"]:
                for k in ("T2R", "T2X"):
                    p = pos.get(k)
                    if p and p.state == "pending":
                        p.state, p.why = "cancelled", "double break"
        # 4. T2X arming (close back inside IB after the break bar)
        if not t2x_armed and info["brk"] in ("up", "dn") and "T2X" in pos and i > brk_i:
            touch = P.get("t2x_arm", "close") == "touch"
            if (info["brk"] == "up" and (S.l[i] if touch else S.c[i]) < ibh) or \
               (info["brk"] == "dn" and (S.h[i] if touch else S.c[i]) > ibl):
                t2x_armed = True
    for p in pos.values():
        if p.state == "open":   # safety
            p.state, p.exit_i, p.exit_px, p.why = "closed", n - 1, S.c[-1], "eod"
        if p.state == "pending":
            p.state, p.why = "cancelled", "no fill"
    return pos, info


def run(sessions, P):
    trades = []
    for S in sessions:
        pos, info = simulate(S, P)
        for k, p in pos.items():
            if p.fill_i >= 0 and p.state == "closed":
                trades.append((S.date, S.dow, p.setup, p.side, p.lots, p.entry, p.stop, p.target,
                               p.exit_px, p.pnl, p.pnl - p.cost, p.why, S.hm[p.fill_i], S.hm[p.exit_i]))
    return pd.DataFrame(trades, columns=["date", "dow", "setup", "side", "lots", "entry", "stop", "target",
                                         "exit", "pnl", "net", "exit_why", "fill_hm", "exit_hm"])


def metrics(df, dates=None, col="pnl"):
    if dates is not None:
        df = df[df.date.isin(dates)]
    pnl = df[col].sum()
    daily = df.groupby("date")[col].sum()
    eq = daily.cumsum()
    dd = float((eq.cummax().clip(lower=0) - eq).max()) if len(eq) else 0.0
    x = df[col]
    wins, losses = x[x > 0].sum(), -x[x <= 0].sum()
    return dict(n=len(df), pnl=pnl, wr=(x > 0).mean() * 100 if len(df) else 0,
                pf=wins / losses if losses else float("inf"), dd=dd)


ALL = {0, 1, 2, 3, 4}

# v1 baseline expressed in v3 parameters (sequencing knobs set to the v1 behaviour).
V1 = dict(
    gap_max=1.0, vwap=True, t1_days=ALL, t1_cutoff=1400,
    z1_max=25, z1_long_e=0.25, z1_long_s=0.55, z1_long_t=0.0,
    z1_short_e=0.20, z1_short_s=0.45, z1_short_t=0.0,
    z3a=True, z3a_lo=50, z3a_hi=75, z3a_s=0.25,
    large_ib={d: 0.9 for d in ALL}, filter_b=0.25, brk_cutoff=1600,
    # (entry, stop, target) in IB-range multiples; keys (dir, dow) override dir.
    # T2R: entry/stop beyond the broken edge, target back inside it.
    # T2X: entry/stop inside the IB, target beyond the broken edge.
    t2r={("up", 1): (0.3, 0.5, 0.25), ("up", 2): (0.2, 0.3, 0.25), ("up", 3): (0.3, 0.5, 0.50),
         ("up", 4): (0.2, 0.3, 0.25), ("dn", 1): (0.2, 0.3, 0.25), ("dn", 3): (0.2, 0.3, 0.25)},
    t2r_days={"up": {1, 2, 3, 4}, "dn": {1, 3}},
    t2x={("up", 0): (0.10, 0.30, 0.20), ("up", 1): (0.20, 0.60, 0.40), ("up", 2): (0.20, 0.60, 0.30),
         ("up", 4): (0.50, 0.60, 0.20), ("dn", 1): (0.30, 0.60, 0.20), ("dn", 2): (0.50, 0.60, 0.20),
         ("dn", 4): (0.40, 0.60, 0.20)},
    t2x_days={"up": {0, 1, 2, 4}, "dn": {1, 2, 4}},
    t2r_cutoff=1400, t2x_cutoff=1300,
    r1=True, r3=True, r6=True, r7=True,
    t1_cancel_on_break=False, cancel_on_double=False, conflict="allow",
)

# Infographic "Verified Ruleset v2" (2026-09-22), as published.
V2I = dict(V1, gap_max=1.25, vwap=False, filter_b=0.20, r1=False,
           large_ib={0: 1.5, 1: 0.7, 2: 1.5, 3: 0.9, 4: 1.5},
           t2r={("up", 1): (0.35, 0.45, 0.15), ("up", 2): (0.20, 0.30, 0.25), ("up", 3): (0.35, 0.45, 0.60),
                ("up", 4): (0.15, 0.25, 0.25), ("dn", 1): (0.25, 0.35, 0.35), ("dn", 3): (0.20, 0.30, 0.25)},
           t2x={("up", 0): (0.15, 0.35, 0.30), ("up", 1): (0.25, 0.55, 0.40), ("up", 2): (0.20, 0.60, 0.30),
                ("up", 4): (0.55, 0.60, 0.30), ("dn", 1): (0.35, 0.55, 0.30), ("dn", 2): (0.50, 0.60, 0.20),
                ("dn", 4): (0.45, 0.55, 0.30)})

# v3 (2026-09-24): v1 core + walk-forward-selected changes. See output/2026.09.24-mnq-ib-v3/.
V3 = dict(
    V1,
    conflict="close_other",                       # opposite signal reverses the open position
    r6=False,                                     # R6 removed
    filter_b=0.20,                                # T2R first-break bar filter 0.20x
    t2r_days={"up": {1, 2, 3, 4}, "dn": {1, 2, 3, 4}},   # breakdown fades added Wed + Fri
    t2r={**V1["t2r"], ("dn", 2): (0.2, 0.3, 0.25), ("dn", 4): (0.2, 0.3, 0.25)},
    t2x={**V1["t2x"], ("dn", 1): (0.30, 0.60, 0.25), ("dn", 2): (0.50, 0.60, 0.25),
         ("dn", 4): (0.40, 0.60, 0.25)},         # breakdown T2X targets 0.25x beyond IBL
)
