import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pandas as pd, numpy as np
from t2sim import *
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 30)
tr = pd.read_pickle("tr_base.pkl"); days = pd.read_pickle("days_base.pkl")
tr["date"] = tr.entry_t.dt.strftime("%Y-%m-%d"); tr["dow"] = tr.entry_t.dt.dayofweek
tr["month"] = tr.entry_t.dt.strftime("%Y-%m")
tr["risk"] = tr.meta.apply(lambda m: m["risk"]); tr["Rmult"] = tr.pnl / tr.risk
tr["dur"] = tr.exit_bar - tr.entry_bar
tr = tr.merge(days[["date", "ibPct", "R", "brk", "brkHm", "gapPct"]], on="date", how="left")
def tab(g):
    return pd.DataFrame(dict(n=g.size(), net=g.pnl.sum().round(0), win=(g.pnl.apply(lambda s: (s > 0).mean()) * 100).round(0),
        pf=g.pnl.apply(lambda s: s[s > 0].sum() / max(1e-9, -s[s <= 0].sum())).round(2), avg=g.pnl.mean().round(0),
        avgR=g.Rmult.mean().round(2), worst=g.pnl.min().round(0), best=g.pnl.max().round(0)))
print("== by setup"); print(tab(tr.groupby("id")))
print("== by exit signal"); print(tab(tr.groupby(["id", "sig"])))
print("== by setup x side"); print(tab(tr.groupby(["id", "side"])))
print("== by setup x dow"); print(tab(tr.groupby(["id", "dow"])))
print("== by month"); print(tab(tr.groupby("month")).T.to_string())
tr["half"] = np.where(tr.entry_t >= pd.Timestamp("2026-05-13", tz="America/New_York"), "last6", "first6")
print("== by half"); print(tab(tr.groupby(["half", "id"])))
print("== same-bar exits (dur==0)"); print(tab(tr.groupby(["id", tr.dur == 0])))
print("== qty buckets"); print(tab(tr.groupby(pd.cut(tr.qty, [0, 1, 2, 5, 10, 30]))))
print("== ibPct buckets (T2 only)"); print(tab(tr[tr.id != "T3"].groupby(["id", pd.cut(tr.ibPct, [0, .3, .4, .5, .6, .75, .9])])))
print("top 15 trades share:", round(tr.pnl.nlargest(15).sum()), " of ", round(tr.pnl.sum()))
print("days traded", tr.date.nunique(), " total days", len(days))
dd = tr.groupby("date").pnl.sum()
print("daily: win days %.0f%%  best %.0f worst %.0f  max losing streak(days) %d" % ((dd > 0).mean() * 100, dd.max(), dd.min(),
      max((len(list(g)) for k, g in __import__("itertools").groupby(dd <= 0) if k), default=0)))
tr.to_pickle("tr_base_x.pkl")
