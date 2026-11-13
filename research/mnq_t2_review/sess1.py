from common import *
from seng import *
pd.set_option("display.width", 250)
e15 = load("m15_eth")[["open", "high", "low", "close"]]
e5 = load("m5_eth")[["open", "high", "low", "close"]]
# descriptive: opening-range size and behaviour by candidate session (15m, Jan-Nov 2026)
cands = dict(Globex18=(1800, 60, 360), Asia19=(1900, 60, 300), Asia20=(2000, 60, 360), Asia21=(2100, 60, 300), Euro02=(200, 60, 300), London03=(300, 60, 330), London04=(400, 60, 270), PreUS07=(700, 60, 140), PreUS08=(800, 60, 80))
for nm, (hm_, orm, win) in cands.items():
    S = build_sessions(e15, hm_, orm, win, 15)
    R = np.array([s["R"] for s in S]); pct = np.array([s["ibPct"] for s in S])
    ext = []; brk = 0; ret = 0; both = 0; rng = []
    for s in S:
        up = s["h"] > s["ibH"]; dn = s["l"] < s["ibL"]
        rng.append((max(s["h"].max(), s["ibH"]) - min(s["l"].min(), s["ibL"])) / s["R"])
        k = next((i for i in range(len(up)) if up[i] or dn[i]), None)
        if k is None: continue
        if up[k] and dn[k]: both += 1; continue
        brk += 1
        isUp = up[k]
        e = ((s["h"] - s["ibH"]) if isUp else (s["ibL"] - s["l"])) / s["R"]
        ext.append(e[k:].max())
        ret += int(((s["c"][k:] < s["ibH"]) if isUp else (s["c"][k:] > s["ibL"])).any())
    ext = np.array(ext)
    print("%-9s sessions=%3d  OR median %5.1f pts (%.2f%%)  broke %2.0f%%  medExt %.2fR  ext>=1R %2.0f%%  closed back inside %2.0f%%  window range/OR median %.2f" % (
        nm, len(S), np.median(R), np.median(pct), brk / len(S) * 100, np.median(ext), (ext >= 1).mean() * 100, ret / max(1, brk) * 100, np.median(rng)))
