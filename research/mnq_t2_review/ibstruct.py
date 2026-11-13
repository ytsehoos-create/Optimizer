"""Per-day structure of the RTH session around the initial balance (IB = 9:30-10:30 ET)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pandas as pd, numpy as np
from load import load

def day_features(df, bar_min):
    out = []
    hm = df.index.hour * 100 + df.index.minute
    df = df[(hm >= 930) & (hm < 1600)]
    prev_close = None
    for d, g in df.groupby(df.index.strftime("%Y-%m-%d")):
        ghm = (g.index.hour * 100 + g.index.minute).values
        ib = g[ghm < 1030]; af = g[ghm >= 1030]
        if len(ib) < 60 // bar_min or len(af) < 12:      # skip half days / broken days
            prev_close = g.close.iloc[-1]; continue
        ibH, ibL = ib.high.max(), ib.low.min(); R = ibH - ibL
        c1030 = ib.close.iloc[-1]; o = ib.open.iloc[0]
        row = dict(date=d, dow=g.index[0].dayofweek, ibPct=R / c1030 * 100, R=R, gapPct=None if prev_close is None else (o - prev_close) / prev_close * 100,
                   ibPos=(c1030 - ibL) / R if R > 0 else np.nan, dayRngPct=(g.high.max() - g.low.min()) / c1030 * 100,
                   rngOverIB=(g.high.max() - g.low.min()) / R if R > 0 else np.nan,
                   closePos=(g.close.iloc[-1] - (ibH + ibL) / 2) / R if R > 0 else np.nan, ret=(g.close.iloc[-1] - o) / o * 100)
        H, L, C = af.high.values, af.low.values, af.close.values
        up = H > ibH; dn = L < ibL
        first = None
        for k in range(len(af)):
            if up[k] or dn[k]:
                first = k; break
        if first is None:
            row.update(brk=0)
        elif up[first] and dn[first]:
            row.update(brk=2)
        else:
            s = 1 if up[first] else -1
            ext = (H - ibH) / R if s > 0 else (ibL - L) / R            # extension beyond the broken edge, per bar
            inside = (C < ibH) if s > 0 else (C > ibL)
            ret_k = next((k for k in range(first, len(af)) if inside[k]), None)
            extBefore = ext[first:(ret_k + 1 if ret_k is not None else len(af))].max()
            maxExt = ext[first:].max()
            opp = (dn[first:].any() if s > 0 else up[first:].any())
            # after the first close back inside: how deep, and does it resume to a new extension high?
            resume = np.nan; depth = np.nan
            if ret_k is not None and ret_k + 1 < len(af):
                dep = ((ibH - L) / R if s > 0 else (H - ibL) / R)[ret_k:]
                depth = dep.max()
                resume = float(ext[ret_k + 1:].max() > extBefore)
            row.update(brk=s, brkHm=int(af.index[first].hour * 100 + af.index[first].minute), brkBarExt=ext[first], extBefore=extBefore, maxExt=maxExt,
                       returned=float(ret_k is not None), opp=float(opp), depth=depth, resume=resume,
                       # touch-level proxies of the fade: extension reached 0.2R; stalled before 0.3R / 0.5R
                       reach20=float(maxExt >= 0.2), stall30=float(0.2 <= extBefore < 0.3), stall50=float(0.2 <= extBefore < 0.5), trend1=float(maxExt >= 1.0))
        out.append(row); prev_close = g.close.iloc[-1]
    return pd.DataFrame(out)

if __name__ == "__main__":
    pd.set_option("display.width", 250); pd.set_option("display.max_columns", 40)
    m15 = load("m15_rth"); f15 = day_features(m15, 15); f15.to_pickle("f15.pkl")
    m5 = load("m5_rth"); f5 = day_features(m5, 5); f5.to_pickle("f5.pkl")
    for nm, f in (("15m (3y)", f15), ("5m (1y)", f5)):
        f["per"] = pd.to_datetime(f.date).dt.to_period("Q").astype(str)
        g = f.groupby("per")
        one = f[f.brk.abs() == 1].groupby("per")
        t = pd.DataFrame(dict(days=g.size(), ibPct=g.ibPct.median().round(2), bigIB=(g.ibPct.apply(lambda s: (s > .9).mean()) * 100).round(0),
            dayRng=g.dayRngPct.median().round(2), rngOverIB=g.rngOverIB.median().round(2), absGap=g.gapPct.apply(lambda s: s.abs().median()).round(2),
            noBrk=(g.brk.apply(lambda s: (s == 0).mean()) * 100).round(0), up=(g.brk.apply(lambda s: (s == 1).mean()) * 100).round(0),
            medExt=one.maxExt.median().round(2), extBefore=one.extBefore.median().round(2), returned=(one.returned.mean() * 100).round(0),
            opp=(one.opp.mean() * 100).round(0), trend1=(one.trend1.mean() * 100).round(0), reach20=(one.reach20.mean() * 100).round(0),
            stall30=(one.stall30.sum() / one.reach20.sum() * 100).round(0), stall50=(one.stall50.sum() / one.reach20.sum() * 100).round(0),
            resume=(one.resume.mean() * 100).round(0), absClose=g.closePos.apply(lambda s: s.abs().median()).round(2)))
        print("==", nm); print(t.to_string())
