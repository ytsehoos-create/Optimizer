import sys, os, copy
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pandas as pd, numpy as np
from t2sim import *
from load import load
TZ = "America/New_York"
def pf(s): return s[s > 0].sum() / max(1e-9, -s[s <= 0].sum()) if len(s) else float("nan")
def maxdd(tr):
    if len(tr) == 0: return 0.0
    eq = tr.sort_values("exit_t").pnl.cumsum(); return float((eq - eq.cummax().clip(lower=0)).min())
_m5 = _m15 = _exp = None
def m5():
    global _m5
    if _m5 is None: _m5 = load_m5_rth()
    return _m5
def m15():
    global _m15
    if _m15 is None: _m15 = load("m15_rth").rename(columns={"VWAP": "vwap_rth"})[["open", "high", "low", "close", "vwap_rth"]]
    return _m15
def exp20():
    global _exp
    if _exp is None:
        X = pd.read_pickle("X.pkl"); _exp = {d.strftime("%Y-%m-%d"): v for d, v in X["rngOverIB_20"].items()}
    return _exp
CUT6 = pd.Timestamp("2026-05-13", tz=TZ)
Y = [("y1", "2023-11-01", "2024-11-17"), ("y2", "2024-11-17", "2025-11-17"), ("y3", "2025-11-17", "2026-12-01")]
def yr(tr, y):
    a0, a1 = [(a, b) for (n, a, b) in Y if n == y][0]
    return tr[(tr.entry_t >= pd.Timestamp(a0, tz=TZ)) & (tr.entry_t < pd.Timestamp(a1, tz=TZ))]
