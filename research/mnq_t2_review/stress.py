import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pandas as pd, numpy as np
from t2sim import *
df = load_m5_rth()
P = default_params(); P["t3On"] = True
t0 = time.time(); tr, _ = run(df, P); print("base", summarize(tr), "secs %.2f" % (time.time() - t0))
cut = pd.Timestamp("2026-05-13", tz="America/New_York")
def rep(lbl, **kw):
    tr, _ = run(df, P, broker=Broker(**kw))
    by = tr.groupby("id").pnl.agg(["size", "sum"]).round(0)
    l6 = tr[tr.entry_t >= cut]
    print("%-34s n=%3d net=%7.0f pf=%.2f dd=%6.0f | last6 net=%6.0f pf=%.2f | " % (lbl, len(tr), tr.pnl.sum(), summarize(tr)["pf"], summarize(tr)["maxdd"], l6.pnl.sum(), summarize(l6)["pf"]),
          " ".join("%s:%d/%.0f" % (k, r["size"], r["sum"]) for k, r in by.iterrows()))
rep("TV default (touch fills)")
for th in (1, 2, 4):
    rep("limit needs %d tick(s) through" % th, through=th)
for ss in (2, 4):
    rep("stop slippage %d ticks" % ss, stop_slip=ss * TICK)
for es in (1, 2, 4):
    rep("entry %d tick(s) worse" % es, entry_slip=es * TICK)
rep("through 1 + stop slip 2 + entry 1", through=1, stop_slip=2 * TICK, entry_slip=1 * TICK)
rep("through 2 + stop slip 4 + entry 2", through=2, stop_slip=4 * TICK, entry_slip=2 * TICK)
