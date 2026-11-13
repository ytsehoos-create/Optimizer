"""Generic 'session opening range' research engine with conservative fills.
A session = an opening range (OR) window + a trading window after it. Setups are evaluated standalone,
one trade per session, sized like the T2 script (qty = max(1, floor(risk$ / stop$)), skipped above a ceiling)."""
import math
import numpy as np, pandas as pd
TICK = 0.25; PV = 2.0; COMM = 0.62; SLIP = 0.25

def build_sessions(df, start_hm, or_min, win_min, bar_min):
    """Split bars into sessions starting at start_hm (ET). Returns list of dicts with OR stats and post-OR arrays."""
    idx = df.index
    hm = idx.hour * 100 + idx.minute
    starts = np.where(hm == start_hm)[0]
    n_or = or_min // bar_min; n_post = win_min // bar_min
    O, H, L, C = (df[c].values for c in ("open", "high", "low", "close"))
    out = []
    for s in starts:
        e = s + n_or
        if e + 2 >= len(df): continue
        # the OR bars must be contiguous
        if (idx[e - 1] - idx[s]) != pd.Timedelta(minutes=bar_min * (n_or - 1)): continue
        t_end = idx[s] + pd.Timedelta(minutes=or_min + win_min)
        j = e
        while j < len(df) and idx[j] < t_end and (idx[j] - idx[j - 1]) <= pd.Timedelta(minutes=bar_min): j += 1
        if j - e < max(4, n_post // 3): continue          # truncated session (holiday / half day)
        ibH = H[s:e].max(); ibL = L[s:e].min(); R = ibH - ibL
        if R <= 0: continue
        tdate = (idx[s] + pd.Timedelta(hours=6)).normalize() if start_hm >= 1800 else idx[s].normalize()   # evening sessions belong to next trade date
        out.append(dict(t0=idx[s], date=tdate.tz_localize(None), dow=tdate.dayofweek, ibH=ibH, ibL=ibL, R=R, cIB=C[e - 1], oIB=O[s],
                        ibPct=R / C[e - 1] * 100, pos=(C[e - 1] - ibL) / R,
                        o=O[e:j], h=H[e:j], l=L[e:j], c=C[e:j], t=idx[e:j]))
    return out

def _walk(o, h, l, c, k0, side, E, S, T, entry_kind, th, end_k, be=None):
    """From bar k0 try to enter (limit / stop / market at open) then manage to stop/target/time exit.
    Conservative resolution of anything the bar can't tell us. Returns (entry_k, entry_px, exit_k, exit_px, reason) or None."""
    n = len(o)
    ent_k = None; px = None
    last_entry_k = min(end_k, n - 1)
    for k in range(k0, last_entry_k + 1):
        if entry_kind == "market":
            ent_k = k; px = o[k] + side * SLIP; break
        if entry_kind == "limit":
            if side > 0:
                if o[k] <= E: ent_k = k; px = o[k]; break
                if l[k] <= E - th: ent_k = k; px = E; break
            else:
                if o[k] >= E: ent_k = k; px = o[k]; break
                if h[k] >= E + th: ent_k = k; px = E; break
        if entry_kind == "stop":
            if side > 0:
                if o[k] >= E: ent_k = k; px = o[k] + SLIP; break
                if h[k] >= E: ent_k = k; px = E + SLIP; break
            else:
                if o[k] <= E: ent_k = k; px = o[k] - SLIP; break
                if l[k] <= E: ent_k = k; px = E - SLIP; break
    if ent_k is None: return None
    # entry bar
    k = ent_k
    hitS = (l[k] <= S) if side > 0 else (h[k] >= S)
    hitT = (h[k] >= T) if side > 0 else (l[k] <= T)
    if entry_kind == "market":
        if hitS: return (k, px, k, S - side * SLIP, "stop")              # both hit -> stop (conservative)
        if hitT: return (k, px, k, T, "target")
    elif entry_kind == "limit":
        # adverse move continues through the limit: certain. Target on the entry bar only if the bar CLOSES through it.
        if (side > 0 and px <= S) or (side < 0 and px >= S): return (k, px, k, px - side * SLIP, "stop")
        if hitS: return (k, px, k, S - side * SLIP, "stop")
        if (c[k] >= T) if side > 0 else (c[k] <= T): return (k, px, k, T, "target")
    else:   # stop entry (breakout): a same-bar reversal to the stop is ambiguous -> count it as a loss
        if hitS: return (k, px, k, S - side * SLIP, "stop")
        if hitT: return (k, px, k, T, "target")
    for k in range(ent_k + 1, n):
        if side > 0:
            if o[k] <= S: return (ent_k, px, k, o[k] - SLIP, "stop")
            if l[k] <= S: return (ent_k, px, k, S - SLIP, "stop")
            if o[k] >= T: return (ent_k, px, k, o[k], "target")
            if h[k] >= T + th: return (ent_k, px, k, T, "target")
        else:
            if o[k] >= S: return (ent_k, px, k, o[k] + SLIP, "stop")
            if h[k] >= S: return (ent_k, px, k, S + SLIP, "stop")
            if o[k] <= T: return (ent_k, px, k, o[k], "target")
            if l[k] <= T - th: return (ent_k, px, k, T, "target")
    return (ent_k, px, n - 1, c[n - 1] - side * SLIP, "time")

def run_setup(sessions, kind, e=0.2, s=0.3, t=0.25, zone=0.25, cutoff_bars=None, risk=200.0, max_risk=300.0, th_ticks=1,
              ib_min=0.0, ib_max=9.0, days=None, side_only=0, fixed_qty=None):
    """kind: 'R' fade first-break extension | 'X' retrace continuation | 'ZF' zone fade at OR close | 'ZC' zone continuation
             | 'BO' breakout continuation (stop entry beyond the OR)
    R : limit beyond broken edge at e*R; stop at s*R beyond; target t*R back inside.
    X : after a close back inside, limit e*R inside the broken edge in the break direction; stop s*R inside; target t*R beyond.
    ZF: OR close in the outer `zone` -> fade at next open; stop s*R beyond that edge; target t*R inside from it.
    ZC: OR close in the outer `zone` -> go with it at next open; stop s*R inside from that edge; target t*R beyond it.
    BO: stop entry e*R beyond either edge; stop s*R inside from that edge; target t*R beyond it."""
    th = th_ticks * TICK
    rows = []
    for S_ in sessions:
        if not (ib_min < S_["ibPct"] <= ib_max): continue
        if days is not None and S_["dow"] not in days: continue
        o, h, l, c = S_["o"], S_["h"], S_["l"], S_["c"]; n = len(o)
        ibH, ibL, R = S_["ibH"], S_["ibL"], S_["R"]
        cut = n - 2 if cutoff_bars is None else min(cutoff_bars, n - 2)
        res = None; side = 0
        if kind in ("ZF", "ZC"):
            p = S_["pos"]
            if zone <= p <= 1 - zone: continue
            top = p > 1 - zone
            if kind == "ZF":
                side = -1 if top else 1
                Sx = ibH + s * R if top else ibL - s * R
                Tx = ibH - t * R if top else ibL + t * R
            else:
                side = 1 if top else -1
                Sx = tick_dn(ibH - s * R) if top else tick_up(ibL + s * R)
                Tx = tick_up(ibH + t * R) if top else tick_dn(ibL - t * R)
            ref = S_["cIB"]
            if (Tx - ref) * side <= 0 or (ref - Sx) * side <= 0: continue
            dist = abs(ref - Sx)
            if dist < 0.1 * R: continue                                   # stop too close to the price to be a real trade
            res = _walk(o, h, l, c, 0, side, None, Sx, Tx, "market", th, 0)
        elif kind == "BO":
            Eu = ibH + e * R; Ed = ibL - e * R
            ku = next((k for k in range(0, cut + 1) if h[k] >= Eu), None); kd = next((k for k in range(0, cut + 1) if l[k] <= Ed), None)
            if ku is None and kd is None: continue
            if ku is not None and kd is not None and ku == kd: continue
            up = kd is None or (ku is not None and ku < kd)
            side = 1 if up else -1
            Ex = Eu if up else Ed
            Sx = ibH - s * R if up else ibL + s * R
            Tx = ibH + t * R if up else ibL - t * R
            dist = abs(Ex - Sx)
            res = _walk(o, h, l, c, ku if up else kd, side, Ex, Sx, Tx, "stop", th, cut)
        else:
            up = h > ibH; dn = l < ibL
            k = next((i for i in range(n) if up[i] or dn[i]), None)
            if k is None or (up[k] and dn[k]) or k >= cut: continue
            isUp = bool(up[k])
            if kind == "R":
                side = -1 if isUp else 1
                Ex = ibH + e * R if isUp else ibL - e * R
                Sx = ibH + s * R if isUp else ibL - s * R
                Tx = ibH - t * R if isUp else ibL + t * R
                if (h[k] >= Ex) if isUp else (l[k] <= Ex): continue      # break bar already at the entry
                dist = abs(Ex - Sx)
                res = _walk(o, h, l, c, k + 1, side, Ex, Sx, Tx, "limit", th, cut)
            else:
                side = 1 if isUp else -1
                j = next((i for i in range(k + 1, n) if (c[i] < ibH if isUp else c[i] > ibL)), None)
                if j is None or j >= cut: continue
                Ex = tick_dn(ibH - e * R) if isUp else tick_up(ibL + e * R)
                Sx = tick_dn(ibH - s * R) if isUp else tick_up(ibL + s * R)
                Tx = tick_up(ibH + t * R) if isUp else tick_dn(ibL - t * R)
                dist = abs(Ex - Sx)
                res = _walk(o, h, l, c, j + 1, side, Ex, Sx, Tx, "limit", th, cut)
        if res is None: continue
        if side_only and side != side_only: continue
        ek, epx, xk, xpx, why = res
        qty = fixed_qty or max(1, int(math.floor(risk / (dist * PV))))
        rk = qty * dist * PV
        if max_risk and rk > max_risk and not fixed_qty: continue
        pnl = (xpx - epx) * side * qty * PV - 2 * COMM * qty
        rows.append(dict(date=S_["date"], dow=S_["dow"], side=side, qty=qty, entry_t=S_["t"][ek], exit_t=S_["t"][xk], entry=epx, exit=xpx, why=why,
                         pnl=pnl, risk=rk, Rm=pnl / rk, ibPct=S_["ibPct"], R=R, bars=xk - ek))
    return pd.DataFrame(rows)

def tick_up(x): return math.ceil(x / TICK - 1e-6) * TICK
def tick_dn(x): return math.floor(x / TICK + 1e-6) * TICK

def stats(tr):
    if len(tr) == 0: return dict(n=0, net=0.0, pf=float("nan"), win=float("nan"), avgR=float("nan"), dd=0.0)
    p = tr.pnl
    eq = p.cumsum()
    return dict(n=len(tr), net=float(p.sum()), pf=float(p[p > 0].sum() / max(1e-9, -p[p <= 0].sum())), win=float((p > 0).mean() * 100),
                avgR=float(tr.Rm.mean()), dd=float((eq - eq.cummax().clip(lower=0)).min()))
