"""Ex-ante daily features (known before 10:30 ET of the trade day)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pandas as pd, numpy as np
from load import load
from ibstruct import day_features

def build():
    f = pd.read_pickle("f15.pkl").copy()
    f["date"] = pd.to_datetime(f.date)
    f = f.set_index("date").sort_index()
    f["one"] = (f.brk.abs() == 1)
    X = pd.DataFrame(index=f.index)
    X["ibPct"] = f.ibPct; X["absGap"] = f.gapPct.abs(); X["ibPos"] = f.ibPos; X["dow"] = f.dow
    sh = f.shift(1)          # everything below uses only completed prior days
    for n in (5, 10, 20, 40):
        X[f"ibPct_{n}"] = sh.ibPct.rolling(n).mean()
        X[f"dayRng_{n}"] = sh.dayRngPct.rolling(n).mean()
        X[f"rngOverIB_{n}"] = sh.rngOverIB.rolling(n).median()
        X[f"trend1_{n}"] = sh.trend1.rolling(n, min_periods=n // 2).mean()
        X[f"returned_{n}"] = sh.returned.rolling(n, min_periods=n // 2).mean()
        X[f"absClose_{n}"] = sh.closePos.abs().rolling(n).mean()
        X[f"maxExt_{n}"] = sh.maxExt.rolling(n, min_periods=n // 2).median()
        X[f"opp_{n}"] = sh.opp.rolling(n, min_periods=n // 2).mean()
    X["ibRel20"] = f.ibPct / X["ibPct_20"]          # today's IB vs its 20-day norm
    X["prevRng"] = sh.dayRngPct; X["prevRet"] = sh.ret; X["prevAbsClose"] = sh.closePos.abs()
    # daily (full-session) context, prior completed day
    d = load("d1"); d.index = (d.index + pd.Timedelta(hours=6)).normalize().tz_localize(None)   # 18:00 ET open -> trade date
    c = d.close
    tr = pd.concat([d.high - d.low, (d.high - c.shift()).abs(), (d.low - c.shift()).abs()], axis=1).max(axis=1)
    D = pd.DataFrame(index=d.index)
    D["atr14"] = (tr.rolling(14).mean() / c * 100)
    D["atr5_20"] = tr.rolling(5).mean() / tr.rolling(20).mean()
    for n in (10, 20):
        D[f"er_{n}"] = (c - c.shift(n)).abs() / c.diff().abs().rolling(n).sum()
        D[f"ret_{n}"] = (c / c.shift(n) - 1) * 100
    D["dSma20"] = (c / c.rolling(20).mean() - 1) * 100
    D["dSma50"] = (c / c.rolling(50).mean() - 1) * 100
    D["ddHigh"] = (c / c.rolling(250, min_periods=60).max() - 1) * 100
    D["rv20"] = c.pct_change().rolling(20).std() * np.sqrt(252) * 100
    D = D.shift(1)
    X = X.join(D, how="left")
    return X, f

if __name__ == "__main__":
    X, f = build(); X.to_pickle("X.pkl")
    print(X.tail(3).T.to_string())
