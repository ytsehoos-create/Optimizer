"""Do the exported RSI / MACD / volume columns add information, and do they separate winning from losing trades?"""
from common import *
import t2sim
pd.set_option("display.width", 250); pd.set_option("display.max_rows", 200)
new = load("m5_rth")
print("file:", len(new), "bars", new.index[0].date(), "->", new.index[-1].date(), "| columns added: Volume, RSI, MACD, Histogram, Signal line")
# 1. RSI and MACD are functions of the closes
c = new.close; d = c.diff()
up = d.clip(lower=0).ewm(alpha=1/14, adjust=False).mean(); dn = (-d.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
rsi = 100 - 100 / (1 + up / dn)
macd = c.ewm(span=12, adjust=False).mean() - c.ewm(span=26, adjust=False).mean(); hist = macd - macd.ewm(span=9, adjust=False).mean()
k = slice(500, None)
print("RSI rebuilt from closes vs exported: max abs diff %.4f | MACD histogram: max abs diff %.4f" % ((rsi - new.RSI)[k].abs().max(), (hist - new.Histogram)[k].abs().max()))

df = new.rename(columns={"RTH VWAP": "vwap_rth"})
hm = df.index.hour * 100 + df.index.minute; df["hm"] = hm; df["date"] = df.index.strftime("%Y-%m-%d")
df["ema20v"] = df.Volume.rolling(20).mean()
# day-level volume features (known at 10:30): IB volume vs its own 20-day average; first 30 min share
ib = df[(hm >= 930) & (hm < 1030)].groupby("date").Volume.sum(); f30 = df[(hm >= 930) & (hm < 1000)].groupby("date").Volume.sum()
day = pd.DataFrame(dict(ibVol=ib, relVol=ib / ib.shift(1).rolling(20).mean(), front=f30 / ib))
x1025 = df[hm == 1025].set_index("date"); day["rsi1025"] = x1025.RSI; day["hist1025"] = x1025.Histogram / x1025.close * 1e4
print("IB volume: median %.0fK contracts, relVol 10th-90th pct %.2f-%.2f" % (ib.median() / 1e3, day.relVol.quantile(.1), day.relVol.quantile(.9)))

P0 = default_params(); P0["t3On"] = True
U = copy.deepcopy(P0); U.update(ibSizeOn=False, useR1=False, useR2=False, useR3=False, useR7=False)
for kk in ("ru", "rd"): U[kk].update(on=[True]*5, e=[.2]*5, s=[.3]*5, t=[.25]*5, rk=[0]*5)
U["xu"].update(on=[True]*5, e=[.2]*5, s=[.6]*5, t=[.3]*5, rk=[0]*5); U["xd"].update(on=[True]*5, e=[.3]*5, s=[.6]*5, t=[.25]*5, rk=[0]*5)
bars = df[["open", "high", "low", "close", "vwap_rth"]]
rng = np.random.default_rng(5)
rows = []
for name, P in (("as traded", P0), ("one setting, no gates", U)):
    tr, _ = run(bars, P)
    tr = tr[tr.entry_t < pd.Timestamp("2026-11-13", tz=TZ)].copy()
    tr["date"] = tr.entry_t.dt.strftime("%Y-%m-%d"); tr["Rm"] = tr.pnl / tr.meta.apply(lambda m: m["risk"])
    tr = tr.join(day, on="date")
    # bar-level features at the last bar closed before the entry bar (nothing from the fill bar itself)
    pos = df.index.get_indexer(tr.entry_t) - 1
    b = df.iloc[pos]
    tr["rsiDir"] = (b.RSI.values - 50) * tr.side.values            # >0: momentum already in the trade's direction
    tr["histDir"] = b.Histogram.values / b.close.values * 1e4 * tr.side.values
    tr["barVol"] = b.Volume.values / b.ema20v.values                 # volume of the bar before entry vs the prior 20 bars
    tr["half"] = np.where(tr.entry_t < CUT6, 1, 2)
    print("\n== %s: %d trades" % (name, len(tr)))
    for leg in ("T2R", "T2X", "T3"):
        x = tr[tr.id == leg]
        for f in ("relVol", "front", "barVol", "rsiDir", "histDir", "rsi1025", "hist1025"):
            y = x.dropna(subset=[f])
            if len(y) < 30: continue
            med = y[f].median(); lo = y[y[f] <= med]; hi = y[y[f] > med]
            dR = hi.Rm.mean() - lo.Rm.mean()
            perm = np.array([(lambda m: y.Rm.values[m].mean() - y.Rm.values[~m].mean())(rng.permutation((y[f] > med).values)) for _ in range(4000)])
            pv = (np.abs(perm) >= abs(dR)).mean()
            s1 = [yy[yy[f] > med].Rm.mean() - yy[yy[f] <= med].Rm.mean() for _, yy in y.groupby("half")]
            rows.append(dict(set=name, leg=leg, feat=f, n=len(y), lowR=round(lo.Rm.mean(), 2), highR=round(hi.Rm.mean(), 2), lowPF=round(pf(lo.pnl), 2), highPF=round(pf(hi.pnl), 2),
                             p=round(pv, 3), halves="".join("+" if v > 0 else "-" for v in s1)))
T = pd.DataFrame(rows)
print(T.sort_values("p").head(16).to_string(index=False))
print("\ntests run: %d ; expected with p<0.05 by chance alone: %.1f ; found: %d ; with p<0.01: %d" % (len(T), len(T) * .05, (T.p < .05).sum(), (T.p < .01).sum()))
day.to_pickle("day_vol.pkl")
