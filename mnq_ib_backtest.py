"""MNQ 5-min backtest: T1 / T2R / T2X IB setups under v1 Baseline vs v2 Optimized rulesets.

Spec source: "MNQ Ruleset: v1 Baseline vs v2 Optimized" doc.

Usage: python mnq_ib_backtest.py [data/mnq_5m_rth_12mo.csv]

Data: TradingView CME_MINI:MNQ1! 5-min export (back-adjusted continuous, RTH),
with the chart's "RTH VWAP" column.

Modelling conventions (not dictated by the spec):
  * IB = 09:30-10:30 ET RTH bars; 10:30 close = close of the 10:25 bar.
  * Limit fills when a bar touches the level; fill price = level, or the bar open
    if the bar opens through the level (gap-through).
  * A bar that touches both stop and target counts as a stop (conservative).
    On the fill bar only the stop is checked (target could have preceded the fill).
  * Open positions are flattened at the 15:55 bar close.
  * VWAP filter uses the chart's RTH VWAP as of the prior bar's close.
  * Gap % = |RTH open - prior RTH close| / prior RTH close.
  * Cross-setup gates are evaluated in real time: a gate uses only outcomes
    known at the moment the gated order would fill.
  * P&L is gross ($2/pt MNQ, no commission/slippage).
"""
import sys
from dataclasses import dataclass, field

import pandas as pd

PT = 2.0          # MNQ $ per point
RISK_CAP = 300.0

RULESETS = {
    "v1": dict(gap_max=1.00, vwap_filter=True, filter_b=0.25,
               large_ib=lambda dow: 0.9),
    "v2": dict(gap_max=1.25, vwap_filter=False, filter_b=0.20,
               large_ib=lambda dow: {1: 0.7, 3: 0.9}.get(dow, 1.5)),
}

# T2R: (entry, stop, target) as multiples of IB range from the broken boundary,
# signed away from the IB (+ = beyond the boundary).
T2R_CELLS = {
    ("up", 1): (0.3, 0.5, -0.25), ("up", 2): (0.2, 0.3, -0.25),
    ("up", 3): (0.3, 0.5, -0.50), ("up", 4): (0.2, 0.3, -0.25),
    ("dn", 1): (0.2, 0.3, -0.25), ("dn", 3): (0.2, 0.3, -0.25),
}
# T2X: (entry, stop, target) signed INTO the IB (+ = inside the IB).
T2X_CELLS = {
    ("up", 0): (0.10, 0.30, -0.20), ("up", 1): (0.20, 0.60, -0.40),
    ("up", 2): (0.20, 0.60, -0.30), ("up", 4): (0.50, 0.60, -0.20),
    ("dn", 1): (0.30, 0.60, -0.20), ("dn", 2): (0.50, 0.60, -0.20),
    ("dn", 4): (0.40, 0.60, -0.20),
}
DOW = ["Mon", "Tue", "Wed", "Thu", "Fri"]


@dataclass
class Trade:
    date: str
    setup: str
    side: int            # +1 long, -1 short
    entry: float
    stop: float
    target: float
    lots: int = 0
    fill_i: int = -1
    exit_i: int = -1
    exit_px: float = 0.0
    result: str = ""     # win / loss / eod
    note: str = ""

    @property
    def pnl(self):
        return (self.exit_px - self.entry) * self.side * self.lots * PT


def lots_for(risk_pts):
    return max(1, int(RISK_CAP // (risk_pts * PT)))


def load(path):
    raw = pd.read_csv(path)
    df = raw[["time", "open", "high", "low", "close", "RTH VWAP"]].copy()
    df.columns = ["t", "o", "h", "l", "c", "vwap"]
    df["dt"] = pd.to_datetime(df.t, unit="s", utc=True).dt.tz_convert("America/New_York")
    df["date"] = df.dt.dt.strftime("%Y-%m-%d")
    df["hm"] = df.dt.dt.hour * 100 + df.dt.dt.minute
    rth = df[(df.hm >= 930) & (df.hm < 1600)].copy()
    sessions = [g.reset_index(drop=True) for _, g in rth.groupby("date")]
    return [s for s in sessions if len(s) == 78]  # drops holiday half-days


def try_fill(t, b, side):
    """Limit fill check; returns fill price or None. side=+1 buy limit, -1 sell limit."""
    if side > 0 and b.l <= t.entry:
        return min(b.o, t.entry)
    if side < 0 and b.h >= t.entry:
        return max(b.o, t.entry)
    return None


def manage(t, bars, i):
    """Advance an open trade on bar i. Returns True when closed."""
    b = bars.iloc[i]
    hit_stop = b.l <= t.stop if t.side > 0 else b.h >= t.stop
    hit_tgt = b.h >= t.target if t.side > 0 else b.l <= t.target
    if hit_stop:
        gap_px = b.o if (t.side > 0 and b.o < t.stop) or (t.side < 0 and b.o > t.stop) else t.stop
        t.exit_i, t.exit_px, t.result = i, gap_px, "loss"
        return True
    if hit_tgt and i > t.fill_i:
        t.exit_i, t.exit_px, t.result = i, t.target, "win"
        return True
    if b.hm == 1555:
        t.exit_i, t.exit_px = i, b.c
        t.result = "eod"
        return True
    return False


def status_at(t, i):
    """What is known about trade t at the start of bar i: out / pending / open / win / loss."""
    if t is None or t.fill_i < 0:
        return "out"
    if t.fill_i >= i:
        return "pending"
    if t.exit_i < 0 or t.exit_i >= i:
        return "open"
    return "win" if t.pnl > 0 else "loss"


def run_session(bars, prev_close, rs):
    date = bars.date[0]
    dow = pd.Timestamp(date).dayofweek
    ib = bars[bars.hm < 1030]
    ibh, ibl = ib.h.max(), ib.l.min()
    rng = ibh - ibl
    hi_i, lo_i = ib.h.idxmax(), ib.l.idxmin()
    ib2 = "hi" if hi_i > lo_i else ("lo" if lo_i > hi_i else None)
    c1030 = ib.c.iloc[-1]
    i0 = len(ib)  # first bar after IB
    gap_pct = abs(bars.o[0] - prev_close) / prev_close * 100 if prev_close else 0.0
    ib_pct = rng / c1030 * 100
    vwap = bars.vwap
    info = dict(date=date, dow=DOW[dow], ibh=ibh, ibl=ibl, rng=rng, ib2=ib2,
                gap=round(gap_pct, 2), ib_pct=round(ib_pct, 2))
    trades, log = {}, []

    # ---------- T1 ----------
    t1 = None
    if ib2 is None or rng <= 0:
        log.append("T1 out: no IB2")
    elif gap_pct >= rs["gap_max"]:
        log.append(f"T1 out: gap {gap_pct:.2f}%")
    else:
        dist = (ibh - c1030) if ib2 == "hi" else (c1030 - ibl)
        zone = dist / rng * 100
        info["zone"] = round(zone, 1)
        if zone <= 25:
            if ib2 == "hi":
                t1 = Trade(date, "T1-Z1", +1, ibh - .25 * rng, ibh - .55 * rng, ibh)
            else:
                t1 = Trade(date, "T1-Z1", -1, ibl + .20 * rng, ibl + .45 * rng, ibl)
        elif 50 <= zone <= 75:
            if ib2 == "hi":   # IB1 is the low -> short toward IBL
                t1 = Trade(date, "T1-Z3a", -1, c1030, ibh - .25 * rng, ibl)
            else:
                t1 = Trade(date, "T1-Z3a", +1, c1030, ibl + .25 * rng, ibh)
            t1.fill_i = i0 - 1  # market at the 10:30 close (last IB bar)
        else:
            log.append(f"T1 out: zone {zone:.0f}%")
        if t1:
            t1.lots = lots_for(abs(t1.entry - t1.stop))

    # ---------- First IB break (shared by T2R / T2X) ----------
    brk_i, brk_dir = None, None
    for i in range(i0, len(bars)):
        b = bars.iloc[i]
        up, dn = b.h > ibh, b.l < ibl
        if up or dn:
            brk_i = i
            brk_dir = "both" if (up and dn) else ("up" if up else "dn")
            break
    info["break"] = f"{brk_dir}@{bars.hm[brk_i]}" if brk_i is not None else "none"
    large_ib = ib_pct > rs["large_ib"](dow)

    # ---------- T2R setup ----------
    t2r = None
    cell = T2R_CELLS.get((brk_dir, dow)) if brk_dir in ("up", "dn") else None
    if dow == 0:
        log.append("T2R out: Monday")
    elif brk_i is None or brk_dir == "both":
        log.append("T2R out: no clean break")
    elif cell is None:
        log.append(f"T2R out: {brk_dir} inactive {DOW[dow]}")
    elif large_ib:
        log.append(f"T2R out: large IB {ib_pct:.2f}%")
    else:
        b = bars.iloc[brk_i]
        ext = (b.h - ibh) if brk_dir == "up" else (ibl - b.l)
        if ext >= rs["filter_b"] * rng:
            log.append(f"T2R out: filter B ext {ext / rng:.2f}x")
        else:
            e, s, g = cell
            if brk_dir == "up":
                t2r = Trade(date, "T2R", -1, ibh + e * rng, ibh + s * rng, ibh + g * rng)
            else:
                t2r = Trade(date, "T2R", +1, ibl - e * rng, ibl - s * rng, ibl - g * rng)
            t2r.lots = lots_for(abs(t2r.entry - t2r.stop))

    # ---------- T2X setup ----------
    t2x = None
    xcell = T2X_CELLS.get((brk_dir, dow)) if brk_dir in ("up", "dn") else None
    if brk_i is None or brk_dir == "both":
        log.append("T2X out: no clean break")
    elif xcell is None:
        log.append(f"T2X out: {brk_dir} inactive {DOW[dow]}")
    elif large_ib:
        log.append(f"T2X out: large IB {ib_pct:.2f}%")
    else:
        e, s, g = xcell
        if brk_dir == "up":
            t2x = Trade(date, "T2X", +1, ibh - e * rng, ibh - s * rng, ibh - g * rng)
        else:
            t2x = Trade(date, "T2X", -1, ibl + e * rng, ibl + s * rng, ibl + g * rng)
        t2x.lots = lots_for(abs(t2x.entry - t2x.stop))

    # ---------- Bar loop ----------
    t2x_armed = False
    for i in range(i0, len(bars)):
        b = bars.iloc[i]
        # T1 zone-1 limit
        if t1 and t1.fill_i < 0 and b.hm < 1400:
            px = try_fill(t1, b, t1.side)
            if px is not None:
                vw = vwap.iloc[i - 1]
                if rs["vwap_filter"] and ((t1.side > 0 and not vw < t1.entry) or
                                          (t1.side < 0 and not vw > t1.entry)):
                    t1.note = f"VWAP skip ({vw:.2f})"
                    log.append(f"T1 out: VWAP filter at {b.hm}")
                    t1 = None
                elif (t1.side > 0 and px <= t1.stop) or (t1.side < 0 and px >= t1.stop):
                    t1 = None
                    log.append("T1 out: opened through stop")
                else:
                    t1.entry, t1.fill_i = px, i
        # T2R limit, placed after the break bar closes
        if t2r and t2r.fill_i < 0 and brk_i < i and b.hm < 1400:
            if t1 and status_at(t1, i) == "win":
                log.append(f"T2R out: Rule 1 (T1 won) at {b.hm}")
                t2r = None
            else:
                px = try_fill(t2r, b, t2r.side)
                if px is not None:
                    if (t2r.side > 0 and px <= t2r.stop) or (t2r.side < 0 and px >= t2r.stop):
                        log.append("T2R out: opened through stop")
                        t2r = None
                    else:
                        t2r.entry, t2r.fill_i = px, i
        # T2X: arm once a bar after the break closes back inside the IB
        if t2x and t2x.fill_i < 0 and b.hm < 1300:
            if t2x_armed:
                s1, s2 = status_at(t1, i), status_at(t2r, i)
                veto = None
                if s1 == "loss":
                    veto = "Rule 3 (T1 lost)"
                elif s1 == "out" and s2 == "out":
                    veto = "Rule 6 (T1 & T2R out)"
                elif dow == 0 and s1 == "out":
                    veto = "Rule 7 (Mon, no T1)"
                px = try_fill(t2x, b, t2x.side)
                if px is not None:
                    if veto:
                        log.append(f"T2X out: {veto} at {b.hm}")
                        t2x = None
                    elif (t2x.side > 0 and px <= t2x.stop) or (t2x.side < 0 and px >= t2x.stop):
                        log.append("T2X out: opened through stop")
                        t2x = None
                    else:
                        t2x.entry, t2x.fill_i = px, i
                        if s2 == "out":
                            t2x.note = "Rule 5: T2R unfilled (reduced confidence)"
            elif i > brk_i and ((brk_dir == "up" and b.c < ibh) or (brk_dir == "dn" and b.c > ibl)):
                t2x_armed = True
        # Manage open positions
        for t in (t1, t2r, t2x):
            if t and t.fill_i >= 0 and t.exit_i < 0 and i >= t.fill_i:
                manage(t, bars, i)
    for t in (t1, t2r, t2x):
        if t and t.fill_i >= 0:
            if t.exit_i < 0:  # safety: flatten at last bar
                t.exit_i, t.exit_px, t.result = len(bars) - 1, bars.c.iloc[-1], "eod"
            t.note = (t.note + f" | fill {bars.hm[t.fill_i]} exit {bars.hm[t.exit_i]}").strip(" |")
            trades[t.setup] = t
        elif t and t.fill_i < 0:
            log.append(f"{t.setup} out: no fill")
    return info, trades, log


def stats(ts):
    n = len(ts)
    if not n:
        return dict(n=0, wr=0.0, pf=0.0, pnl=0.0)
    wins = [t.pnl for t in ts if t.pnl > 0]
    losses = [-t.pnl for t in ts if t.pnl <= 0]
    pf = sum(wins) / sum(losses) if losses and sum(losses) else float("inf")
    return dict(n=n, wr=len(wins) / n * 100, pf=pf, pnl=sum(t.pnl for t in ts))


def backtest(path, rs_name):
    rs = RULESETS[rs_name]
    sessions = load(path)
    out, prev_close = [], None
    for s in sessions:
        if prev_close is None:
            prev_close = s.c.iloc[-1]
            continue
        info, trades, log = run_session(s, prev_close, rs)
        out.append((info, trades, log))
        prev_close = s.c.iloc[-1]
    return out


def max_dd(pnls):
    eq = peak = dd = 0.0
    for p in pnls:
        eq += p
        peak = max(peak, eq)
        dd = max(dd, peak - eq)
    return dd


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "data/mnq_5m_rth_12mo.csv"
    for name in RULESETS:
        res = backtest(path, name)
        all_t = [t for _, tr, _ in res for t in tr.values()]
        print(f"\n===== {name} =====  sessions={len(res)}")
        for key in ("T1", "T2R", "T2X"):
            st = stats([t for t in all_t if t.setup.startswith(key)])
            print(f"{key:4s} n={st['n']:3d} WR={st['wr']:5.1f}% PF={st['pf']:5.2f} P&L=${st['pnl']:9.2f}")
        st = stats(all_t)
        daily = [sum(t.pnl for t in tr.values()) for _, tr, _ in res]
        print(f"ALL  n={st['n']:3d} WR={st['wr']:5.1f}% PF={st['pf']:5.2f} P&L=${st['pnl']:9.2f}"
              f"  maxDD(daily)=${max_dd(daily):.2f}")
        for info, tr, log in res:
            line = " ".join(f"{t.setup}:{t.result}{t.pnl:+.0f}({t.lots}x)" for t in tr.values())
            print(f"  {info['date']} {info['dow']} IB={info['rng']:.1f}({info['ib_pct']}%) "
                  f"IB2={info['ib2']} z={info.get('zone', '-')} gap={info['gap']}% brk={info['break']} | "
                  f"{line or '-'} ${sum(t.pnl for t in tr.values()):+.0f}")
            for l in log:
                print(f"      {l}")
