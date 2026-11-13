"""Standard RSI / MACD / volume-spike entries on MNQ 5-minute RTH bars, 12 months. One position at a time, entry at the
next bar's open, stop and target in multiples of the 14-bar ATR, flat at 15:55, $1.74 per contract round trip + stop slippage."""
from common import *
df = load("m5_rth"); cut = pd.Timestamp("2026-05-13", tz=TZ)
o, h, l, c, v = (df[k].values for k in ("open", "high", "low", "close", "Volume"))
hm = (df.index.hour * 100 + df.index.minute).values
pc = np.roll(c, 1); tr_ = np.maximum(h - l, np.maximum(abs(h - pc), abs(l - pc))); atr = pd.Series(tr_).rolling(14).mean().values
rsi = df.RSI.values; hist = df.Histogram.values; macd = df.MACD.values
v20 = pd.Series(v).rolling(20).mean().shift(1).values
def X(a, lvl): return (a > lvl) & (np.roll(a, 1) <= lvl)          # crosses above
def Y(a, lvl): return (a < lvl) & (np.roll(a, 1) >= lvl)          # crosses below
up_bar = c > o; big = (h - l) >= 1.5 * atr; spike = v >= 2.5 * v20
sig = {
 "RSI fade 30/70 (buy cross under 30, sell cross over 70)": Y(rsi, 30) * 1 - X(rsi, 70) * 1,
 "RSI fade 25/75": Y(rsi, 25) * 1 - X(rsi, 75) * 1,
 "RSI fade 20/80": Y(rsi, 20) * 1 - X(rsi, 80) * 1,
 "RSI momentum (buy cross over 60, sell cross under 40)": X(rsi, 60) * 1 - Y(rsi, 40) * 1,
 "MACD histogram crosses zero, go with it": X(hist, 0) * 1 - Y(hist, 0) * 1,
 "MACD histogram crosses zero, fade it": Y(hist, 0) * 1 - X(hist, 0) * 1,
 "MACD line crosses zero, go with it": X(macd, 0) * 1 - Y(macd, 0) * 1,
 "Volume spike on a wide bar, fade the bar": (spike & big) * np.where(up_bar, -1, 1),
 "Volume spike on a wide bar, go with the bar": (spike & big) * np.where(up_bar, 1, -1),
}
def sim(s, ks, kt):
    out = []; i = 20; n = len(c)
    while i < n - 1:
        if s[i] != 0 and 935 <= hm[i] <= 1500 and atr[i] == atr[i]:
            sd = int(np.sign(s[i])); e = o[i + 1] + sd * 0.25; S = e - sd * ks * atr[i]; T = e + sd * kt * atr[i]; j = i + 1
            while True:
                hitS = l[j] <= S if sd > 0 else h[j] >= S; hitT = h[j] >= T if sd > 0 else l[j] <= T
                if hitS: x = S - sd * 0.25; break
                if hitT: x = T; break
                if hm[j] >= 1555 or j == n - 1 or hm[j + 1] < hm[j]: x = c[j] - sd * 0.25; break
                j += 1
            risk = ks * atr[i] * 2
            out.append((df.index[i + 1], ((x - e) * sd * 2 - 1.24) / risk)); i = j + 1
        else: i += 1
    return pd.DataFrame(out, columns=["t", "R"])
print("%-58s %5s %6s %5s %7s | %s" % ("entry rule (stop 1.0 ATR, target 1.5 ATR)", "n", "avgR", "PF", "win", "PF first6 / last6"))
pfR = lambda r: r[r > 0].sum() / max(1e-9, -r[r <= 0].sum())
for k, s in sig.items():
    t = sim(s, 1.0, 1.5); a = t[t.t < cut]; b = t[t.t >= cut]
    print("%-58s %5d %6.3f %5.2f %6.0f%% | %.2f / %.2f" % (k, len(t), t.R.mean(), pfR(t.R), (t.R > 0).mean() * 100, pfR(a.R), pfR(b.R)))
