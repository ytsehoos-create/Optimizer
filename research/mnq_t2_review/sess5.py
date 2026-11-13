from common import *
from seng import *
pd.set_option("display.width", 250); pd.set_option("display.max_rows", 300)
e15 = load("m15_eth")[["open", "high", "low", "close"]]; e5 = load("m5_eth")[["open", "high", "low", "close"]]
cut = pd.Timestamp("2026-05-13")
def one(S, kind, **g):
    t = run_setup(S, kind, max_risk=400.0, **g); a = stats(t[t.date < cut]); b = stats(t[t.date >= cut]); al = stats(t)
    return t, "n=%3d net=%6.0f pf=%.2f dd=%6.0f win=%2.0f%% | Jan-May %6.0f pf=%.2f | last6m %6.0f pf=%.2f" % (al["n"], al["net"], al["pf"], al["dd"], al["win"], a["net"], a["pf"], b["net"], b["pf"])
print("== X (retrace continuation) e=.3 s=.8 t=1.0 / e=.4 s=.8 t=1.5: does it depend on the exact range window? (trade until 09:25)")
for hm_ in (0, 100, 130, 200, 230, 300, 330, 400, 500):
    for orm in (30, 60, 90):
        st = pd.Timestamp("2026-01-01 %02d:%02d" % (hm_ // 100, hm_ % 100)); end = st + pd.Timedelta(minutes=orm)
        win = int((pd.Timestamp("2026-01-01 09:25") - end).total_seconds() // 60)
        if orm % 15 or hm_ % 100 not in (0, 30): continue
        S = build_sessions(e15, hm_, orm, win, 15)
        print("  range %04d +%2dmin  A: %s" % (hm_, orm, one(S, "X", e=.3, s=.8, t=1.0)[1]))
        print("                     B: %s" % one(S, "X", e=.4, s=.8, t=1.5)[1])
print("\n== X on the 02:00-03:00 range: time exit and entry cutoff")
for endhm in ("06:00", "07:00", "08:25", "09:25"):
    win = int((pd.Timestamp("2026-01-01 " + endhm) - pd.Timestamp("2026-01-01 03:00")).total_seconds() // 60)
    S = build_sessions(e15, 200, 60, win, 15)
    for cb in (None, 8, 12, 16):
        print("  flat %s, last entry %s: %s" % (endhm, "any" if cb is None else "03:00+%dmin" % (cb * 15), one(S, "X", e=.3, s=.8, t=1.0, cutoff_bars=cb)[1]))
print("\n== ZC (first-hour momentum) zone=.2 s=.85 t=.3 : other first hours / range lengths (flat 6h after the range)")
for hm_ in (1800, 1900, 2000, 2100, 200, 300):
    for orm in (30, 60, 90):
        S = build_sessions(e15, hm_, orm, 360, 15)
        print("  range %04d +%2dmin: %s" % (hm_, orm, one(S, "ZC", zone=.2, s=.85, t=.3)[1]))
print("\n== Globex ZC: time exit")
for win in (120, 180, 240, 360, 480, 540):
    S = build_sessions(e15, 1800, 60, win, 15)
    print("  flat %3d min after 19:00: %s" % (win, one(S, "ZC", zone=.2, s=.85, t=.3)[1]))
