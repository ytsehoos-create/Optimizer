import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pandas as pd, numpy as np
from load import path
tv = pd.read_csv(path("trades"), encoding="utf-8-sig")
ent = tv[tv.Type.str.startswith("Entry")].set_index("Trade number")
ext = tv[tv.Type.str.startswith("Exit")].set_index("Trade number")
T = pd.DataFrame(dict(entry_t=ent["Date and time"], side=ent.Type.str.contains("long").map({True:1,False:-1}), id=ent.Signal,
     entry_px=ent["Price USD"], qty=ent["Size (qty)"], exit_t=ext["Date and time"], sig=ext.Signal, exit_px=ext["Price USD"], pnl=ent["Net PnL USD"])).sort_index()
T.to_pickle("tv_trades.pkl")
mine = pd.read_pickle("tr_base.pkl")
mine["entry_s"] = mine.entry_t.dt.strftime("%Y-%m-%d %H:%M"); mine["exit_s"] = mine.exit_t.dt.strftime("%Y-%m-%d %H:%M")
bad = 0
for k in range(len(T)):
    a = T.iloc[k]; b = mine.iloc[k]
    ok = (a.entry_t == b.entry_s and a.exit_t == b.exit_s and a.id == b.id and a.side == b.side and a.qty == b.qty and
          abs(a.entry_px - b.entry_px) < 1e-6 and abs(a.exit_px - b.exit_px) < 1e-6 and abs(a.pnl - b.pnl) < 0.02 and a.sig == b.sig)
    if not ok:
        bad += 1
        print("MISMATCH", k+1, dict(a), "\n   mine:", b.entry_s, b.exit_s, b.id, b.side, b.qty, b.entry_px, b.exit_px, round(b.pnl,2), b.sig)
print("trades", len(T), len(mine), "mismatches", bad)
