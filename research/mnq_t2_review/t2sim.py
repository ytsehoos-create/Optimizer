"""Faithful port of 'MNQ v3 · T2R + T2X (one account)' with a TradingView-style broker emulator.
Bars: RTH 5-minute (America/New_York index) with columns open, high, low, close, vwap_rth."""
import math, copy, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd

TICK = 0.25
PV = 2.0          # MNQ $ per point
COMM = 0.62       # per contract per side
SLIP = 1 * TICK   # market + stop orders

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri"]

def default_params():
    P = dict(
        riskCap=200.0, maxRisk=300.0,
        ibSizeOn=True, ibSizeLo=0.40, ibSizeHi=0.60, ibSizeX=1.5,
        largeIB=0.9, filterB=0.20, useR1=True, useR3=True, useR7=True, useR2=True,
        cutR=1400, cutX=1300, alignOn=True, flatHM=1555,
        # per weekday: on, e, s, t, risk
        ru=dict(on=[False, True, True, True, True], e=[.20, .30, .20, .30, .20], s=[.30, .50, .30, .50, .30],
                t=[.25, .25, .25, .50, .25], rk=[0, 0, 300, 0, 0]),
        rd=dict(on=[False, True, True, True, True], e=[.20] * 5, s=[.30] * 5, t=[.25] * 5, rk=[0] * 5),
        xu=dict(on=[True, True, True, False, True], e=[.10, .20, .20, .20, .50], s=[.30, .60, .60, .60, .60],
                t=[.20, .40, .30, .30, .20], rk=[0, 0, 300, 0, 0]),
        xd=dict(on=[False, True, True, False, True], e=[.30, .30, .50, .30, .40], s=[.60] * 5, t=[.25] * 5, rk=[0] * 5),
        t1Z1On=True, t1Z3aOn=True, t1GapMax=1.0, t1ZoneMax=25.0, t1Vwap=True,
        t1LongE=.25, t1LongS=.55, t1LongT=0.0, t1ShortE=.20, t1ShortS=.45, t1ShortT=0.0, t1Cutoff=1400,
        t1Z3aLo=50.0, t1Z3aHi=75.0, t1Z3aS=.25, t1Days=[True] * 5,
        t3On=False, t3Zone=.25, t3StopX=.15, t3Back=.40, t3Risk=0.0,
        t2On=True,
        t3Days=[True] * 5, t3IbMin=None, t3IbMax=None,     # T3 weekday switches; IB band (default: > largeIB)
        expMax=0.0,                                        # regime: prior-20-day median (RTH range / IB range) threshold, 0 = off
        t3ExpOff=False, rExpMult=1.0, xExpMult=1.0, t3ExpMult=1.0, calmMax=0.0, rCalmMult=1.0,
    )
    return P

def tick_up(x): return math.ceil(x / TICK - 1e-6) * TICK
def tick_dn(x): return math.floor(x / TICK + 1e-6) * TICK
def rnd(x): return round(x / TICK) * TICK
def lots(rk, pts): return max(1, int(math.floor(rk / (pts * PV))))

class Broker:
    """Minimal TradingView broker emulator: limit/market entries via strategy.order/entry,
    strategy.exit brackets (stop/limit) bound to an entry id, intrabar path O-H-L-C / O-L-H-C."""
    def __init__(self, through=0, stop_slip=SLIP, entry_slip=0.0):
        self.through = through * TICK      # limit orders need price to trade this far THROUGH them to fill
        self.stop_slip = stop_slip          # slippage on stop / market exits
        self.entry_slip = entry_slip        # adverse slippage on limit entries (market-at-the-level style)
        self.orders = {}     # id -> dict(side, qty, limit|None(market))
        self.exits = {}      # from_entry -> dict(stop, limit, name)
        self.open = []       # list of dict(id, side, qty, px, bar, t, mfe, mae)
        self.closed = []
        self.bar = -1
        self.t = None

    # -- script API
    def order(self, oid, side, qty, limit=None): self.orders[oid] = dict(side=side, qty=qty, limit=limit)
    def exit(self, name, from_entry, stop=None, limit=None): self.exits[from_entry] = dict(stop=stop, limit=limit, name=name)
    def cancel(self, oid): self.orders.pop(oid, None)
    def cancel_exit(self, from_entry): self.exits.pop(from_entry, None)
    def cancel_all(self):
        self.orders.clear(); self.exits.clear()
    def pos(self): return sum(tr["side"] * tr["qty"] for tr in self.open)
    def close_all(self, px, comment):
        for tr in list(self.open):
            self._close(tr, tr["qty"], px - tr["side"] * SLIP, comment)
    def close_id(self, oid, px, comment):
        for tr in list(self.open):
            if tr["id"] == oid:
                self._close(tr, tr["qty"], px - tr["side"] * SLIP, comment)

    # -- internals
    def _close(self, tr, qty, px, sig):
        pnl = (px - tr["px"]) * tr["side"] * qty * PV - 2 * COMM * qty
        self.closed.append(dict(id=tr["id"], side=tr["side"], qty=qty, entry_px=tr["px"], exit_px=px, entry_bar=tr["bar"],
                                exit_bar=self.bar, entry_t=tr["t"], exit_t=self.t, pnl=pnl, sig=sig,
                                mfe=tr["mfe"], mae=tr["mae"], meta=tr.get("meta")))
        tr["qty"] -= qty
        if tr["qty"] <= 0:
            self.open.remove(tr)

    def _fill_entry(self, oid, px):
        o = self.orders.pop(oid)
        side, qty = o["side"], o["qty"]
        # close opposite positions first
        for tr in list(self.open):
            if qty <= 0: break
            if tr["side"] == -side:
                q = min(qty, tr["qty"])
                self._close(tr, q, px, oid)
                qty -= q
        if qty > 0:
            self.open.append(dict(id=oid, side=side, qty=qty, px=px, bar=self.bar, t=self.t, mfe=0.0, mae=0.0, meta=o.get("meta")))

    def _candidates(self, p, q):
        """Orders triggered when moving from p to q (p exclusive, q inclusive). Returns list of (dist, kind, key, fillpx)."""
        up = q > p
        out = []
        for oid, o in self.orders.items():
            L = o["limit"]
            if L is None: continue
            th = self.through; es = self.entry_slip
            if o["side"] > 0 and not up and q <= L - th < p: out.append((p - (L - th), 1, "entry", oid, L + es))
            if o["side"] < 0 and up and p < L + th <= q: out.append((L + th - p, 1, "entry", oid, L - es))
        for tr in self.open:
            ex = self.exits.get(tr["id"])
            if not ex: continue
            S, T = ex["stop"], ex["limit"]
            if tr["side"] > 0:
                if S is not None and not up and q <= S < p: out.append((p - S, 0, "stop", tr["id"], S - self.stop_slip))
                if T is not None and up and p < T + self.through <= q: out.append((T + self.through - p, 0, "limit", tr["id"], T))
            else:
                if S is not None and up and p < S <= q: out.append((S - p, 0, "stop", tr["id"], S + self.stop_slip))
                if T is not None and not up and q <= T - self.through < p: out.append((p - (T - self.through), 0, "limit", tr["id"], T))
        return out

    def _marketable(self, p, at_open):
        """Orders already triggered at price p (bar open gap, or bracket activated beyond its level)."""
        out = []
        if at_open:
            for oid, o in self.orders.items():
                L = o["limit"]
                if L is None: out.append((0, 1, "entry", oid, p + o["side"] * SLIP))
                elif (o["side"] > 0 and p <= L) or (o["side"] < 0 and p >= L): out.append((0, 1, "entry", oid, p))
        for tr in self.open:
            ex = self.exits.get(tr["id"])
            if not ex: continue
            S, T = ex["stop"], ex["limit"]
            if tr["side"] > 0:
                if S is not None and p <= S: out.append((0, 0, "stop", tr["id"], p - self.stop_slip))
                elif T is not None and p >= T: out.append((0, 0, "limit", tr["id"], p))
            else:
                if S is not None and p >= S: out.append((0, 0, "stop", tr["id"], p + self.stop_slip))
                elif T is not None and p <= T: out.append((0, 0, "limit", tr["id"], p))
        return out

    def _apply(self, c):
        _, _, kind, key, px = c
        if kind == "entry":
            self._fill_entry(key, px)
        else:
            ex = self.exits.get(key)
            for tr in list(self.open):
                if tr["id"] == key:
                    self._close(tr, tr["qty"], px, ex["name"])

    def _track(self, p):
        for tr in self.open:
            ex = (p - tr["px"]) * tr["side"]
            if ex > tr["mfe"]: tr["mfe"] = ex
            if ex < tr["mae"]: tr["mae"] = ex

    def process(self, i, t, o, h, l, c):
        self.bar, self.t = i, t
        if not self.orders and not self.open: return
        p = o
        guard = 0
        while True:
            m = self._marketable(p, True)
            if not m or guard > 10: break
            m.sort(key=lambda x: (x[0], x[1])); self._apply(m[0]); guard += 1
        path = [h, l, c] if (h - o) < (o - l) else [l, h, c]
        for q in path:
            guard = 0
            while p != q and guard < 20:
                cand = self._candidates(p, q)
                if not cand:
                    break
                cand.sort(key=lambda x: (x[0], x[1]))
                cnd = cand[0]
                lvl = p + (cnd[0] if q > p else -cnd[0])
                self._track(lvl)
                self._apply(cnd)
                p = lvl
                guard += 1
                m = self._marketable(p, False)
                while m and guard < 20:
                    m.sort(key=lambda x: (x[0], x[1])); self._apply(m[0]); guard += 1
                    m = self._marketable(p, False)
            self._track(q)
            p = q


def run(df, P=None, log=None, broker=None, bar_min=5, exp20=None):
    P = P or default_params()
    idx = df.index
    O = df["open"].values; H = df["high"].values; Lo = df["low"].values; C = df["close"].values
    VW = df["vwap_rth"].values
    HM = (idx.hour * 100 + idx.minute).values
    DOW = idx.dayofweek.values       # 0 = Mon
    nxt = idx + pd.Timedelta(minutes=bar_min)
    NHM = (nxt.hour * 100 + nxt.minute).values
    DATE = idx.strftime("%Y-%m-%d").values
    B = broker or Broker()
    n = len(df)
    flatAt = min(P["flatHM"], 1555) if bar_min == 5 else 1545
    lastIBhm = 1025 if bar_min == 5 else 1015

    prevRthClose = lastRthClose = rthOpen = ibH = ibL = c1030 = ibPctDay = None
    ibHBar = ibLBar = brkBar = None
    dayLive = False; brk = 0
    rSt = 0; rDead = False; rSide = 0; rE = rS = rT = None; rQty = 0
    xSt = 0; xDead = False; xHeld = False; xSide = 0; xE = xS = xT = None; xQty = 0
    rAtBroker = xAtBroker = False; rTgtOut = xTgtOut = None; rQtyPine = xQtyPine = 0
    seenClosed = 0
    t1St = 0; t1Side = 0; t1Tag = ""; t1E = t1S = t1T = t1Px = None; t1Fill = None
    t3St = 0
    days = {}   # per-day info
    cur = None
    rMeta = xMeta = None
    expHot = expCalm = False

    for i in range(n):
        o, h, l, c = O[i], H[i], Lo[i], C[i]
        hm = HM[i]; nextHm = NHM[i]; dIdx = DOW[i]
        B.process(i, idx[i], o, h, l, c)

        isRTH = 930 <= hm < 1600
        newRTH = hm == 930
        inIB = 930 <= hm < 1030
        lastIBBar = hm == lastIBhm
        afterIB = 1030 <= hm < 1600
        isWeekday = 0 <= dIdx <= 4
        isMonday = dIdx == 0
        evt = []

        if newRTH:
            prevRthClose = lastRthClose
            rthOpen = o; ibH = h; ibL = l; ibHBar = ibLBar = i
            c1030 = None; ibPctDay = None; dayLive = False; brk = 0; brkBar = None
            rSt = 0; rDead = False; rSide = 0; xSt = 0; xDead = False; xHeld = False; xSide = 0
            rAtBroker = xAtBroker = False
            t3St = 0; t1St = 0; t1Side = 0; t1Tag = ""
            B.cancel_all()
            if B.pos() != 0:
                B.close_all(c, "carried over: closed")
            cur = dict(date=DATE[i], dow=dIdx, notes=[])
            expv = exp20.get(DATE[i]) if exp20 is not None else None
            expHot = bool(P["expMax"] > 0 and expv is not None and expv == expv and expv > P["expMax"])
            expCalm = bool(P["calmMax"] > 0 and expv is not None and expv == expv and expv <= P["calmMax"])
            cur["exp20"] = expv
            days[DATE[i]] = cur
        elif inIB and ibH is not None:
            if h > ibH: ibH = h; ibHBar = i
            if l < ibL: ibL = l; ibLBar = i
        if isRTH:
            lastRthClose = c
        if ibH is None:
            continue
        R = ibH - ibL

        if lastIBBar:
            c1030 = c
            ibPct = R / c * 100
            ibPctDay = ibPct
            anyOn = isWeekday and (P["ru"]["on"][dIdx] or P["rd"]["on"][dIdx] or P["xu"]["on"][dIdx] or P["xd"]["on"][dIdx])
            cur.update(ibH=ibH, ibL=ibL, R=R, ibPct=ibPct, c1030=c, rthOpen=rthOpen, prevClose=prevRthClose)
            if not anyOn: pass
            elif ibPct > P["largeIB"]: cur["notes"].append("large IB")
            else: dayLive = P["t2On"]
            if P["t3On"]:
                t3lo = P["largeIB"] if P["t3IbMin"] is None else P["t3IbMin"]
                t3hi = 1e9 if P["t3IbMax"] is None else P["t3IbMax"]
                if isWeekday and P["t3Days"][dIdx] and t3lo < ibPct <= t3hi and R > 0 and not (P["t3ExpOff"] and expHot):
                    pos0 = (c - ibL) / R
                    if not (P["t3Zone"] <= pos0 <= 1 - P["t3Zone"]):
                        sd3 = -1 if pos0 > 1 - P["t3Zone"] else 1
                        s3 = tick_up(ibH + P["t3StopX"] * R) if sd3 < 0 else tick_dn(ibL - P["t3StopX"] * R)
                        tg3 = tick_dn(ibH - P["t3Back"] * R) if sd3 < 0 else tick_up(ibL + P["t3Back"] * R)
                        n3 = lots((P["t3Risk"] if P["t3Risk"] > 0 else P["riskCap"]) * (P["t3ExpMult"] if expHot else 1.0), abs(c - s3))
                        rk3 = n3 * abs(c - s3) * PV
                        if (tg3 - c) * sd3 <= 0: pass
                        elif P["maxRisk"] > 0 and rk3 > P["maxRisk"]: cur["notes"].append("T3 skipped: risk")
                        else:
                            t3St = 1
                            B.order("T3", sd3, n3, None)
                            B.orders["T3"]["meta"] = dict(setup="T3", risk=rk3, pos0=pos0)
                            B.exit("T3 exit", "T3", stop=s3, limit=tg3)
            gapPct = None if prevRthClose is None else abs(rthOpen - prevRthClose) / prevRthClose * 100
            ib2Hi = ibHBar > ibLBar; ib2Lo = ibLBar > ibHBar
            zone = (ibH - c) / R * 100 if (ib2Hi and R > 0) else (c - ibL) / R * 100 if (ib2Lo and R > 0) else None
            t1St = 5
            if not (isWeekday and P["t1Days"][dIdx]): pass
            elif R <= 0 or not (ib2Hi or ib2Lo): pass
            elif gapPct is None: pass
            elif gapPct >= P["t1GapMax"]: pass
            elif zone <= P["t1ZoneMax"] and P["t1Z1On"]:
                t1Side = 1 if ib2Hi else -1; t1Tag = "Z1"
                t1E = rnd(ibH - P["t1LongE"] * R if ib2Hi else ibL + P["t1ShortE"] * R)
                t1S = rnd(ibH - P["t1LongS"] * R if ib2Hi else ibL + P["t1ShortS"] * R)
                t1T = rnd(ibH - P["t1LongT"] * R if ib2Hi else ibL + P["t1ShortT"] * R)
                t1Risk = lots(P["riskCap"], abs(t1E - t1S)) * abs(t1E - t1S) * PV
                if not (P["maxRisk"] > 0 and t1Risk > P["maxRisk"]): t1St = 1
            elif P["t1Z3aLo"] <= zone <= P["t1Z3aHi"] and P["t1Z3aOn"]:
                t1Side = -1 if ib2Hi else 1; t1Tag = "Z3a"
                t1E = c
                t1S = rnd(ibH - P["t1Z3aS"] * R if ib2Hi else ibL + P["t1Z3aS"] * R)
                t1T = rnd(ibL if ib2Hi else ibH)
                t1Risk = lots(P["riskCap"], abs(t1E - t1S)) * abs(t1E - t1S) * PV
                if not (P["maxRisk"] > 0 and t1Risk > P["maxRisk"]):
                    t1St = 2; t1Px = c; t1Fill = i
            cur.update(gapPct=gapPct, zone=zone, ib2=("H" if ib2Hi else "L" if ib2Lo else "-"), t1Tag=t1Tag if t1St in (1, 2) else "")

        # T1 bar by bar
        if afterIB and t1St == 1:
            if hm >= P["t1Cutoff"]: t1St = 5
            else:
                touched = l <= t1E if t1Side > 0 else h >= t1E
                if touched:
                    vprev = VW[i - 1]
                    vwapBlocked = P["t1Vwap"] and (not (vprev < t1E) if t1Side > 0 else not (vprev > t1E))
                    px = min(o, t1E) if t1Side > 0 else max(o, t1E)
                    if vwapBlocked: t1St = 5
                    elif (t1Side > 0 and px <= t1S) or (t1Side < 0 and px >= t1S): t1St = 5
                    else: t1St = 2; t1Px = px; t1Fill = i
        if afterIB and t1St == 2 and i >= t1Fill:
            hitStop = l <= t1S if t1Side > 0 else h >= t1S
            hitTgt = i > t1Fill and (h >= t1T if t1Side > 0 else l <= t1T)
            if hitStop: t1St = 4
            elif hitTgt: t1St = 3
            elif hm == flatAt: t1St = 3 if (c - t1Px) * t1Side > 0 else 4
            if t1St >= 3: cur["t1Res"] = ("W" if t1St == 3 else "L") + idx[i].strftime("%H%M")
        t1In = t1St in (2, 3, 4); t1Lost = t1St == 4; t1Won = t1St == 3

        # Fills seen at this bar close
        if len(B.closed) > seenClosed:
            for k in range(seenClosed, len(B.closed)):
                eid = B.closed[k]["id"]
                if eid == "T2R" and rSt != 3: rSt = 3; rAtBroker = False
                elif eid == "T2X" and xSt != 4: xSt = 4; xAtBroker = False
                elif eid == "T3" and t3St != 3: t3St = 3
            seenClosed = len(B.closed)
        openId = B.open[0]["id"] if B.open else ""
        if openId == "T2R" and rSt != 2: rSt = 2; rAtBroker = False
        if openId == "T2X" and xSt != 3: xSt = 3; xAtBroker = False
        if openId == "T3" and t3St == 1: t3St = 2

        exitedDead = False
        if openId == "T2R" and rDead:
            B.close_id("T2R", c, "cancelled order filled"); seenClosed = seenClosed  # counted next bar like TV
            rSt = 3; rDead = False; exitedDead = True
        if openId == "T2X" and xDead:
            B.close_id("T2X", c, "cancelled order filled")
            xSt = 4; xDead = False; exitedDead = True
        inTrade = len(B.open) > 0 and not exitedDead
        # note: TV's strategy.opentrades is still > 0 on the bar where close(immediately) was issued
        if exitedDead: inTrade = False

        # Gates and cutoffs
        if xSt == 2 and xHeld and (l <= xE if xSide > 0 else h >= xE):
            xSt = 4; cur["notes"].append("T2X skipped R7 touch")
        if rSt == 1 and not rDead:
            why = "R1" if (P["useR1"] and t1Won) else "cutoff" if (nextHm >= P["cutR"] or nextHm < 930) else ""
            if why:
                if inTrade and rAtBroker: rDead = True
                else: rSt = 3
                cur["notes"].append("T2R cancel " + why)
        if xSt in (1, 2) and not xDead:
            why = ("R3" if (P["useR3"] and t1Lost) else "R2" if (P["useR2"] and t1Won and t1Side != xSide) else
                   "cutoff" if (nextHm >= P["cutX"] or nextHm < 930) else "R7" if (P["useR7"] and isMonday and t1St == 5) else "")
            if why:
                if inTrade and xAtBroker: xDead = True
                else: xSt = 4
                cur["notes"].append("T2X cancel " + why)

        # First break
        if afterIB and brk == 0 and c1030 is not None:
            up = h > ibH; dn = l < ibL
            if up or dn:
                brk = 2 if (up and dn) else 1 if up else -1
                brkBar = i
                cur.update(brk=brk, brkHm=hm, brkExt=((h - ibH) if up else (ibL - l)) / R if R > 0 else None)
                if dayLive and isWeekday and brk != 2:
                    isUp = brk == 1
                    ext = h - ibH if isUp else ibL - l
                    Rp = P["ru"] if isUp else P["rd"]
                    if not Rp["on"][dIdx]: cur["notes"].append("T2R off")
                    elif ext >= P["filterB"] * R: cur["notes"].append("T2R filterB")
                    elif nextHm >= P["cutR"] or nextHm < 930: cur["notes"].append("T2R after cutoff")
                    elif P["useR1"] and t1Won: cur["notes"].append("T2R R1 pre")
                    else:
                        e, s, t, rk = Rp["e"][dIdx], Rp["s"][dIdx], Rp["t"][dIdx], Rp["rk"][dIdx]
                        rMult = P["ibSizeX"] if (P["ibSizeOn"] and P["ibSizeLo"] <= ibPctDay < P["ibSizeHi"]) else 1.0
                        rMult *= (P["rExpMult"] if expHot else 1.0) * (P["rCalmMult"] if expCalm else 1.0)
                        eN = tick_up(ibH + e * R) if isUp else tick_dn(ibL - e * R)
                        sN = tick_up(ibH + s * R) if isUp else tick_dn(ibL - s * R)
                        tN = tick_dn(ibH - t * R) if isUp else tick_up(ibL + t * R)
                        nn = lots((rk if rk > 0 else P["riskCap"]) * rMult, abs(eN - sN))
                        rkN = nn * abs(eN - sN) * PV
                        if rMult <= 0: cur["notes"].append("T2R regime off")
                        elif (h >= eN) if isUp else (l <= eN): cur["notes"].append("T2R break bar hit entry")
                        elif P["maxRisk"] > 0 and rkN > P["maxRisk"] * max(rMult, 1.0): cur["notes"].append("T2R risk ceiling")
                        else:
                            rSt = 1; rSide = -1 if isUp else 1; rE, rS, rT, rQty = eN, sN, tN, nn
                            rMeta = dict(setup="T2R", risk=rkN, rMult=rMult)
                    Xp = P["xu"] if isUp else P["xd"]
                    if not Xp["on"][dIdx]: cur["notes"].append("T2X off")
                    elif nextHm >= P["cutX"] or nextHm < 930: cur["notes"].append("T2X after cutoff")
                    elif P["useR3"] and t1Lost: cur["notes"].append("T2X R3 pre")
                    elif P["useR2"] and t1Won and t1Side != (1 if isUp else -1): cur["notes"].append("T2X R2 pre")
                    elif P["useR7"] and isMonday and t1St == 5: cur["notes"].append("T2X R7 pre")
                    else:
                        e, s, t, rk = Xp["e"][dIdx], Xp["s"][dIdx], Xp["t"][dIdx], Xp["rk"][dIdx]
                        eN = tick_dn(ibH - e * R) if isUp else tick_up(ibL + e * R)
                        sN = tick_dn(ibH - s * R) if isUp else tick_up(ibL + s * R)
                        tN = tick_up(ibH + t * R) if isUp else tick_dn(ibL - t * R)
                        xMult = P["xExpMult"] if expHot else 1.0
                        nn = lots((rk if rk > 0 else P["riskCap"]) * xMult, abs(eN - sN))
                        rkN = nn * abs(eN - sN) * PV
                        if xMult <= 0: cur["notes"].append("T2X regime off")
                        elif P["maxRisk"] > 0 and rkN > P["maxRisk"] * max(xMult, 1.0): cur["notes"].append("T2X risk ceiling")
                        else:
                            xSt = 1; xSide = 1 if isUp else -1; xE, xS, xT, xQty = eN, sN, tN, nn
                            xMeta = dict(setup="T2X", risk=rkN)

        # T2X arming
        if xSt == 1 and afterIB and brkBar is not None and i > brkBar and (c < ibH if xSide > 0 else c > ibL):
            xSt = 2

        # Broker sync (only while flat)
        xHeld = False
        if (not inTrade) and (not exitedDead) and afterIB and 930 <= nextHm < 1600:
            wantR = rSt == 1 and not rDead
            r7Hold = xSt == 2 and not xDead and P["useR7"] and isMonday and not t1In
            wantX = xSt == 2 and not xDead and not r7Hold
            xHeld = r7Hold
            def closer(d, own, lvl): return min(own, lvl) if d > 0 else max(own, lvl)
            tgtR = (closer(rSide, rT, xE) if (P["alignOn"] and wantX) else rT) if wantR else None
            tgtX = (closer(xSide, xT, rE) if (P["alignOn"] and wantR) else xT) if wantX else None
            stale = rDead or xDead
            changed = (wantR != rAtBroker) or (wantX != xAtBroker) or (wantR and tgtR != rTgtOut) or (wantX and tgtX != xTgtOut)
            if changed or stale:
                if not wantR: B.cancel("T2R"); B.cancel_exit("T2R")
                if not wantX: B.cancel("T2X"); B.cancel_exit("T2X")
                if rDead: rSt = 3; rDead = False
                if xDead: xSt = 4; xDead = False
                rAtBroker = xAtBroker = False
                if wantR:
                    B.order("T2R", rSide, rQty, rE); B.orders["T2R"]["meta"] = rMeta
                    B.exit("T2R exit", "T2R", stop=rS, limit=tgtR)
                    rQtyPine = rQty; rAtBroker = True; rTgtOut = tgtR
                if wantX:
                    B.order("T2X", xSide, xQty, xE); B.orders["T2X"]["meta"] = xMeta
                    B.exit("T2X exit", "T2X", stop=xS, limit=tgtX)
                    xQtyPine = xQty; xAtBroker = True; xTgtOut = tgtX

        # Handoff emulation
        if inTrade:
            posQty = int(abs(B.pos()))
            if openId == "T2X" and rAtBroker and xTgtOut == rE:
                B.order("T2R", rSide, rQty + posQty, rE); B.orders["T2R"]["meta"] = rMeta
                B.exit("T2X exit", "T2X", stop=xS, limit=None)
                rQtyPine = rQty + posQty
            elif openId == "T2R" and xAtBroker and rTgtOut == xE:
                B.order("T2X", xSide, xQty + posQty, xE); B.orders["T2X"]["meta"] = xMeta
                B.exit("T2R exit", "T2R", stop=rS, limit=None)
                xQtyPine = xQty + posQty
        elif not exitedDead:
            if rAtBroker and rQtyPine != rQty:
                B.order("T2R", rSide, rQty, rE); B.orders["T2R"]["meta"] = rMeta; rQtyPine = rQty
            if xAtBroker and xQtyPine != xQty:
                B.order("T2X", xSide, xQty, xE); B.orders["T2X"]["meta"] = xMeta; xQtyPine = xQty

        # Flatten
        if hm == flatAt:
            B.cancel_all()
            if B.pos() != 0:
                B.close_all(c, "EOD")
            rAtBroker = xAtBroker = False

    tr = pd.DataFrame(B.closed)
    return tr, pd.DataFrame(days.values())

def load_m5_rth(key="m5_rth"):
    from load import load
    df = load(key)
    df = df.rename(columns={"RTH VWAP": "vwap_rth"})
    return df[["open", "high", "low", "close", "vwap_rth"]]

def summarize(tr, label=""):
    if len(tr) == 0:
        return dict(label=label, n=0)
    w = tr[tr.pnl > 0].pnl.sum(); ls = -tr[tr.pnl <= 0].pnl.sum()
    eq = tr.pnl.cumsum()
    dd = (eq - eq.cummax().clip(lower=0)).min()
    return dict(label=label, n=len(tr), net=round(tr.pnl.sum(), 0), pf=round(w / ls, 2) if ls > 0 else float("inf"),
                win=round((tr.pnl > 0).mean() * 100, 1), avg=round(tr.pnl.mean(), 1), maxdd=round(dd, 0))

if __name__ == "__main__":
    df = load_m5_rth()
    P = default_params(); P["t3On"] = True
    tr, days = run(df, P)
    print(summarize(tr, "all"))
    tr.to_pickle("tr_base.pkl"); days.to_pickle("days_base.pkl")
    print(tr.head(12).to_string())
