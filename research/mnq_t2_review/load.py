"""Find and load the TradingView exports this review runs on.

Put the CSVs in one folder and point MNQ_DATA at it (default: ./data next to this file). File names do not matter:
each file is recognised by its bar size and by whether it has overnight bars.
  m5_rth   5-minute, regular hours   (with the 'RTH VWAP' indicator column)   -> exact strategy replica
  m5_eth   5-minute, extended hours                                            -> overnight check on finer bars
  m15_rth  15-minute, regular hours, as far back as the export allows          -> prior years, regime reading
  m15_eth  15-minute, extended hours                                           -> overnight search
  h4, d1   240-minute and daily                                                -> long-run context
  trades   the strategy's 'List of trades' export                              -> replica validation
"""
import os, glob
import pandas as pd

DATA = os.environ.get("MNQ_DATA", os.path.join(os.path.dirname(os.path.abspath(__file__)), "data"))
_found = None

def _scan():
    global _found
    if _found is not None: return _found
    found = {}
    for p in sorted(glob.glob(os.path.join(DATA, "*.csv"))):
        with open(p, encoding="utf-8-sig") as fh: head = fh.readline()
        if head.startswith("Trade number"):
            found["trades"] = p; continue
        if not head.startswith("time,"): continue
        t = pd.read_csv(p, usecols=["time"])["time"]
        step = int(t.diff().median())
        et = pd.to_datetime(t, unit="s", utc=True).dt.tz_convert("America/New_York")
        eth = bool((et.dt.hour < 9).any())
        key = {300: "m5", 900: "m15"}.get(step)
        key = (key + ("_eth" if eth else "_rth")) if key else {14400: "h4", 86400: "d1"}.get(step)
        if key and "MCL" in os.path.basename(p).upper(): key = "mcl_" + key      # other instruments get a prefix
        if key and (key not in found or len(t) > found[key][1]): found[key] = (p, len(t))
    _found = {k: (v if isinstance(v, str) else v[0]) for k, v in found.items()}
    return _found

def path(key):
    f = _scan()
    if key not in f: raise FileNotFoundError("no '%s' export found in %s (have: %s)" % (key, DATA, ", ".join(sorted(f)) or "nothing"))
    return f[key]

def load(key):
    df = pd.read_csv(path(key))
    df["dt"] = pd.to_datetime(df["time"], unit="s", utc=True).dt.tz_convert("America/New_York")
    return df.set_index("dt")

if __name__ == "__main__":
    for k, p in sorted(_scan().items()):
        if k == "trades": print("%-8s %s" % (k, os.path.basename(p))); continue
        df = load(k); print("%-8s %6d bars  %s -> %s  %s" % (k, len(df), df.index[0].date(), df.index[-1].date(), os.path.basename(p)))
