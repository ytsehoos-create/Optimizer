from common import *
from seng import *
e15 = load("m15_eth")[["open", "high", "low", "close"]]; e5 = load("m5_eth")[["open", "high", "low", "close"]]
cut = pd.Timestamp("2026-05-13")
def show(lbl, t):
    a = stats(t[t.date < cut]); b = stats(t[t.date >= cut]); al = stats(t)
    print("%-52s n=%3d net=%6.0f pf=%.2f dd=%6.0f win=%2.0f%% avgR=%.2f | Jan-May %6.0f pf=%.2f | last6m n=%3d %6.0f pf=%.2f dd=%6.0f" % (lbl, al["n"], al["net"], al["pf"], al["dd"], al["win"], al["avgR"], a["net"], a["pf"], b["n"], b["net"], b["pf"], b["dd"]))
# London pullback as the Pine script will run it: range 02:00-03:00, no new entries from 06:00, flat at 07:00
for bm, data, nm in ((15, e15, "15m Jan-Nov"), (5, e5, "5m Aug-Nov")):
    S = build_sessions(data, 200, 60, 240, bm)
    cb = (180 // bm) - 1                      # last bar that may fill starts before 06:00
    for th in (0, 1):
        lx = run_setup(S, "X", e=.3, s=.8, t=1.0, max_risk=300.0, cutoff_bars=cb, th_ticks=th); show("London pullback %s, %s" % (nm, "touch fills" if th == 0 else "1 tick through"), lx)
    if bm == 15: lx.to_pickle("lx_final.pkl")
for bm, data, nm in ((15, e15, "15m Jan-Nov"), (5, e5, "5m Aug-Nov")):
    S = build_sessions(data, 1800, 60, 240, bm)
    gm = run_setup(S, "ZC", zone=.2, s=.85, t=.3, max_risk=300.0); show("Globex momentum %s" % nm, gm)
    if bm == 15: gm.to_pickle("gm_final.pkl")
# circuit-breaker levels: bootstrap the recommended RTH trade list (trade order shuffled by day blocks)
tr = pd.read_pickle("tr_rec.pkl"); tr["d"] = tr.entry_t.dt.strftime("%Y-%m-%d")
days = [g.pnl.values for _, g in tr.groupby("d")]
rng = np.random.default_rng(11); dds = []; lows20 = []; negm = []
for _ in range(5000):
    seq = np.concatenate([days[i] for i in rng.integers(0, len(days), len(days))])
    eq = np.cumsum(seq); dds.append((eq - np.maximum.accumulate(np.maximum(eq, 0))).min())
    r = np.convolve(seq, np.ones(20), "valid"); lows20.append(r.min())
print("\nRTH recommended set, resampled 12-month paths: max drawdown median %.0f, 95th pct %.0f, 99th pct %.0f ; worst 20-trade stretch median %.0f, 5th pct %.0f" % (
    np.median(dds), np.percentile(dds, 5), np.percentile(dds, 1), np.median(lows20), np.percentile(lows20, 5)))
half = tr.pnl.values * 0.5 - 0   # crude 'edge halves' scenario: winners shrink, losers stay
seqw = np.where(tr.pnl.values > 0, tr.pnl.values * 0.5, tr.pnl.values)
print("if every winner were half as big: net %.0f, pf %.2f" % (seqw.sum(), seqw[seqw > 0].sum() / -seqw[seqw <= 0].sum()))
r20 = tr.pnl.rolling(20).sum(); print("actual worst 20-trade stretch in the 12 months: %.0f ; actual losing streak max: %d trades" % (r20.min(), max(len(list(g)) for k, g in __import__("itertools").groupby(tr.pnl <= 0) if k)))
m = tr.groupby(tr.entry_t.dt.strftime("%Y-%m")).pnl.sum(); print("monthly:", m.round(0).to_dict())
