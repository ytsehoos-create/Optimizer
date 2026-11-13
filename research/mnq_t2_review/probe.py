"""Single-leg opening-range probe on the TradingView-style fill emulator, for any instrument with a Volume column.
It mirrors pine/ib_probe.pine statement for statement so the two can be compared.
leg 1 = T2R one setting (fade the first-break extension), 2 = T2X one setting (retrace continuation), 3 = T3 (wide-IB zone fade).
Volume filters: vf 0 none, 1 need the measure >= vthr, 2 need it < vthr.
  T2R / T2X measure: volume of the bar that broke the IB / average volume of the 20 bars before it.
  T3 measure: IB volume / average IB volume of the previous 20 sessions."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import math
import numpy as np, pandas as pd
import t2sim
from t2sim import Broker

def run_probe(df, leg, tick=0.25, pv=2.0, e=.2, s=.3, t=.25, zone=.25, cut=1400, largeIB=.9, risk=200.0, maxRisk=300.0,
              vf=0, vthr=1.0, mon=True, ibStart=930, ibEnd=1030, flat=1555, comm=0.62):
    t2sim.TICK, t2sim.PV, t2sim.SLIP, t2sim.COMM = tick, pv, tick, comm
    up_ = lambda x: math.ceil(x / tick - 1e-6) * tick
    dn_ = lambda x: math.floor(x / tick + 1e-6) * tick
    idx = df.index; O, H, L, C, V = (df[c].values for c in ("open", "high", "low", "close", "Volume"))
    HM = (idx.hour * 100 + idx.minute).values; DOW = idx.dayofweek.values
    NHM = ((idx + pd.Timedelta(minutes=5)).hour * 100 + (idx + pd.Timedelta(minutes=5)).minute).values
    v20 = pd.Series(V).rolling(20).mean().shift(1).values          # average of the 20 bars before this one
    B = Broker(stop_slip=tick)
    ibH = ibL = None; ibVol = 0.0; ibHist = []; st = 0; side = 0; brkBar = None; R = 0.0; relVol = None; live = False; nclosed = 0; pend = None
    rows = []
    for i in range(len(df)):
        o, h, l, c = O[i], H[i], L[i], C[i]; hm = HM[i]
        B.process(i, idx[i], o, h, l, c)
        if hm == ibStart:
            B.cancel_all()
            if B.pos() != 0: B.close_all(c, "carried")
            ibH, ibL, ibVol, st, side, brkBar, live = h, l, 0.0, 0, 0, None, False
        if ibH is None: continue
        inIB = ibStart <= hm < ibEnd
        if inIB:
            ibH = max(ibH, h); ibL = min(ibL, l); ibVol += V[i]
        if inIB and NHM[i] == ibEnd:                                     # IB closes
            R = ibH - ibL; ibPct = R / c * 100 if c else 0
            relVol = ibVol / np.mean(ibHist[-20:]) if len(ibHist) >= 20 else None
            ibHist.append(ibVol)
            wd = DOW[i] <= 4 and (mon or DOW[i] != 0)
            if leg == 3:
                st = 9
                ok = wd and ibPct > largeIB and R > 0
                if ok and vf: ok = relVol is not None and ((relVol >= vthr) if vf == 1 else (relVol < vthr))
                if ok:
                    p0 = (c - ibL) / R
                    if not (zone <= p0 <= 1 - zone):
                        sd = -1 if p0 > 1 - zone else 1
                        S = up_(ibH + s * R) if sd < 0 else dn_(ibL - s * R)
                        T = dn_(ibH - t * R) if sd < 0 else up_(ibL + t * R)
                        dist = abs(c - S); n = max(1, int(math.floor(risk / (dist * pv)))) if dist > 0 else 0
                        if n and (T - c) * sd > 0 and not (maxRisk > 0 and n * dist * pv > maxRisk):
                            B.order("P", sd, n, None); B.orders["P"]["meta"] = dict(risk=n * dist * pv, mv=relVol); B.exit("x", "P", stop=S, limit=T)
            else:
                st = 1 if (wd and 0 < ibPct <= largeIB) else 9
        after = ibEnd <= hm <= flat
        if st == 1 and after and not inIB:
            up = h > ibH; dn = l < ibL
            if up or dn:
                st = 9
                if not (up and dn) and NHM[i] < cut:
                    isUp = up; ext = (h - ibH) if isUp else (ibL - l)
                    vr = V[i] / v20[i] if v20[i] and v20[i] == v20[i] else None
                    ok = True
                    if vf: ok = vr is not None and ((vr >= vthr) if vf == 1 else (vr < vthr))
                    if leg == 1 and vf in (3, 4) and ext < e * R:          # dynamic: live only after a bar with high (3) / low (4) relative volume
                        side = -1 if isUp else 1
                        E = up_(ibH + e * R) if isUp else dn_(ibL - e * R); S = up_(ibH + s * R) if isUp else dn_(ibL - s * R); T = dn_(ibH - t * R) if isUp else up_(ibL + t * R)
                        dist = abs(E - S); n = max(1, int(math.floor(risk / (dist * pv))))
                        if not (maxRisk > 0 and n * dist * pv > maxRisk): st = 3; pend = (E, S, T, n); nclosed = len(B.closed)
                    elif leg == 1 and vf not in (3, 4) and ok and ext < e * R:
                        side = -1 if isUp else 1
                        E = up_(ibH + e * R) if isUp else dn_(ibL - e * R); S = up_(ibH + s * R) if isUp else dn_(ibL - s * R); T = dn_(ibH - t * R) if isUp else up_(ibL + t * R)
                        dist = abs(E - S); n = max(1, int(math.floor(risk / (dist * pv))))
                        if not (maxRisk > 0 and n * dist * pv > maxRisk):
                            B.order("P", side, n, E); B.orders["P"]["meta"] = dict(risk=n * dist * pv, mv=vr); B.exit("x", "P", stop=S, limit=T); live = True
                    elif leg == 2 and ok:
                        side = 1 if isUp else -1; brkBar = i; st = 2
                        E = dn_(ibH - e * R) if isUp else up_(ibL + e * R); S = dn_(ibH - s * R) if isUp else up_(ibL + s * R); T = up_(ibH + t * R) if isUp else dn_(ibL - t * R)
                        dist = abs(E - S); n = max(1, int(math.floor(risk / (dist * pv))))
                        pend = (E, S, T, n, vr)
                        if maxRisk > 0 and n * dist * pv > maxRisk: st = 9
        if st == 3:
            if B.open or len(B.closed) > nclosed or NHM[i] >= cut:
                st = 9
                if not B.open: B.cancel("P"); B.cancel_exit("P")
            else:
                vr = V[i] / v20[i] if v20[i] and v20[i] == v20[i] else None
                want = vr is not None and ((vr >= vthr) if vf == 3 else (vr < vthr))
                if want and "P" not in B.orders:
                    E, S, T, n = pend
                    B.order("P", side, n, E); B.orders["P"]["meta"] = dict(risk=n * abs(E - S) * pv, mv=vr); B.exit("x", "P", stop=S, limit=T)
                elif not want and "P" in B.orders:
                    B.cancel("P"); B.cancel_exit("P")
        if st == 2 and i > brkBar and (c < ibH if side > 0 else c > ibL):
            st = 9
            if NHM[i] < cut:
                E, S, T, n, vr = pend
                B.order("P", side, n, E); B.orders["P"]["meta"] = dict(risk=n * abs(E - S) * pv, mv=vr); B.exit("x", "P", stop=S, limit=T); live = True
        if live and NHM[i] >= cut and "P" in B.orders:                   # unfilled at the cutoff
            B.cancel("P"); B.cancel_exit("P"); live = False
        if hm == flat:
            B.cancel_all(); live = False
            if B.pos() != 0: B.close_all(c, "EOD")
    tr = pd.DataFrame(B.closed)
    if len(tr):
        tr["risk"] = tr.meta.apply(lambda m: m["risk"]); tr["mv"] = tr.meta.apply(lambda m: m["mv"]); tr["Rm"] = tr.pnl / tr.risk
    return tr

def line(tr):
    if len(tr) == 0: return "n=  0"
    p = tr.pnl; eq = p.cumsum(); dd = (eq - eq.cummax().clip(lower=0)).min()
    return "n=%3d net=%7.0f pf=%.2f win=%2.0f%% avgR=%5.2f dd=%6.0f" % (len(tr), p.sum(), p[p > 0].sum() / max(1e-9, -p[p <= 0].sum()), (p > 0).mean() * 100, tr.Rm.mean(), dd)
