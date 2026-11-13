"""Python port of pine/mnq_overnight.pine (same statement order), run on the TradingView-style broker emulator."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import math
import numpy as np, pandas as pd
from t2sim import Broker, tick_up, tick_dn, lots, PV, summarize

def on_params():
    return dict(riskCap=200.0, maxRisk=300.0, lxOn=True, lxStart=200, lxEnd=300, lxE=.30, lxS=.80, lxT=1.00, lxCutMin=180, lxHoldMin=240,
                gmOn=True, gmStart=1800, gmEnd=1900, gmZone=.20, gmS=.85, gmT=.30, gmHoldMin=240)

def run_on(df, P=None, bar_min=15, broker=None):
    P = P or on_params()
    idx = df.index; O = df.open.values; H = df.high.values; Lo = df.low.values; C = df.close.values
    HM = (idx.hour * 100 + idx.minute).values
    nxt = idx + pd.Timedelta(minutes=bar_min); NHM = (nxt.hour * 100 + nxt.minute).values
    T = idx.asi8 // 10**6 if str(idx.dtype).endswith("ns, America/New_York]") else (idx.asi8 // 10**3)
    T = (idx.tz_convert("UTC").tz_localize(None) - pd.Timestamp("1970-01-01")) // pd.Timedelta(milliseconds=1)
    T = np.asarray(T, dtype="int64"); NT = T + bar_min * 60000
    B = broker or Broker()
    lSt = 0; lH = lL = lR = None; lTEnd = None; lSide = 0; lE = lS = lT = None; lQty = 0; lBrk = None
    gSt = 0; gH = gL = None; gTEnd = None; gSide = 0
    seen = 0; pinL = pinG = False
    for i in range(len(df)):
        o, h, l, c = O[i], H[i], Lo[i], C[i]; hm = HM[i]; nextHm = NHM[i]
        B.process(i, idx[i], o, h, l, c)
        inL = P["lxStart"] <= hm < P["lxEnd"]; inG = P["gmStart"] <= hm < P["gmEnd"]
        newL = inL and not pinL; newG = inG and not pinG; pinL, pinG = inL, inG
        if newL or newG:
            B.cancel_all()
            if B.pos() != 0: B.close_all(c, "carried over: closed")
        if newL: lH, lL, lSt, lSide = h, l, 1, 0
        elif inL and lSt == 1: lH = max(lH, h); lL = min(lL, l)
        if newG: gH, gL, gSt, gSide = h, l, 1, 0
        elif inG and gSt == 1: gH = max(gH, h); gL = min(gL, l)
        if len(B.closed) > seen:
            for k in range(seen, len(B.closed)):
                eid = B.closed[k]["id"]
                if eid == "LX" and lSt != 6: lSt = 6
                elif eid == "GM" and gSt != 4: gSt = 4
            seen = len(B.closed)
        openId = B.open[0]["id"] if B.open else ""
        if openId == "LX" and lSt == 4: lSt = 5
        if openId == "GM" and gSt == 2: gSt = 3
        # LX
        if inL and lSt == 1 and nextHm == P["lxEnd"]:
            lR = lH - lL; lTEnd = NT[i]
            lSt = 6 if (not P["lxOn"] or lR <= 0) else 2
        lMinsNext = 0.0 if lTEnd is None else (NT[i] - lTEnd) / 60000.0
        if lSt in (2, 3, 4) and not inL and lMinsNext >= P["lxCutMin"]:
            if lSt == 4: B.cancel("LX"); B.cancel_exit("LX")
            lSt = 6
        if lSt == 2 and not inL:
            up = h > lH; dn = l < lL
            if up and dn: lSt = 6
            elif up or dn:
                eN = tick_dn(lH - P["lxE"] * lR) if up else tick_up(lL + P["lxE"] * lR)
                sN = tick_dn(lH - P["lxS"] * lR) if up else tick_up(lL + P["lxS"] * lR)
                tN = tick_up(lH + P["lxT"] * lR) if up else tick_dn(lL - P["lxT"] * lR)
                n = lots(P["riskCap"], abs(eN - sN)); rkN = n * abs(eN - sN) * PV
                if abs(eN - sN) <= 0: lSt = 6
                elif P["maxRisk"] > 0 and rkN > P["maxRisk"]: lSt = 6
                else: lSt = 3; lSide = 1 if up else -1; lE, lS, lT, lQty, lBrk, lRisk = eN, sN, tN, n, i, rkN
        if lSt == 3 and i > lBrk and (c < lH if lSide > 0 else c > lL):
            B.order("LX", lSide, lQty, lE); B.orders["LX"]["meta"] = dict(setup="LX", risk=lRisk)
            B.exit("LX exit", "LX", stop=lS, limit=lT)
            lSt = 4
        if lSt == 5 and lMinsNext >= P["lxHoldMin"]:
            B.cancel_exit("LX"); B.close_id("LX", c, "LX time"); lSt = 6
        # GM
        if inG and gSt == 1 and nextHm == P["gmEnd"]:
            gR = gH - gL; gTEnd = NT[i]; gSt = 4
            if P["gmOn"] and gR > 0:
                pos0 = (c - gL) / gR
                if not (P["gmZone"] <= pos0 <= 1 - P["gmZone"]):
                    sd = 1 if pos0 > 1 - P["gmZone"] else -1
                    sN = tick_dn(gH - P["gmS"] * gR) if sd > 0 else tick_up(gL + P["gmS"] * gR)
                    tN = tick_up(gH + P["gmT"] * gR) if sd > 0 else tick_dn(gL - P["gmT"] * gR)
                    dist = abs(c - sN); n = lots(P["riskCap"], dist) if dist > 0 else 0; rkN = n * dist * PV
                    if (c - sN) * sd <= 0 or (tN - c) * sd <= 0 or dist < 0.1 * gR: pass
                    elif P["maxRisk"] > 0 and rkN > P["maxRisk"]: pass
                    else:
                        gSt = 2; gSide = sd
                        B.order("GM", sd, n, None); B.orders["GM"]["meta"] = dict(setup="GM", risk=rkN)
                        B.exit("GM exit", "GM", stop=sN, limit=tN)
        gMinsNext = 0.0 if gTEnd is None else (NT[i] - gTEnd) / 60000.0
        if gSt == 3 and gMinsNext >= P["gmHoldMin"]:
            B.cancel_exit("GM"); B.close_id("GM", c, "GM time"); gSt = 4
    return pd.DataFrame(B.closed)

if __name__ == "__main__":
    from load import load
    cut = pd.Timestamp("2026-05-13", tz="America/New_York")
    def pf(s): return s[s > 0].sum() / max(1e-9, -s[s <= 0].sum())
    for key, bm in (("m15_eth", 15), ("m5_eth", 5)):
        df = load(key)[["open", "high", "low", "close"]]
        for lbl, br in (("TradingView fills", None), ("limit needs 1 tick through", Broker(through=1))):
            tr = run_on(df, bar_min=bm, broker=br)
            for su in ("LX", "GM"):
                x = tr[tr.id == su]; a = x[x.entry_t < cut]; b = x[x.entry_t >= cut]
                print("%-8s %-27s %s n=%3d net=%6.0f pf=%.2f dd=%6.0f win=%2.0f%% | Jan-May %6.0f pf=%.2f | last6m %6.0f pf=%.2f | exits %s" % (
                    key, lbl, su, len(x), x.pnl.sum(), pf(x.pnl), summarize(x.reset_index(drop=True))["maxdd"], (x.pnl > 0).mean() * 100,
                    a.pnl.sum(), pf(a.pnl) if len(a) else float("nan"), b.pnl.sum(), pf(b.pnl), x.sig.value_counts().to_dict()))
            if key == "m15_eth" and br is None: tr.to_pickle("on_tv15.pkl")
