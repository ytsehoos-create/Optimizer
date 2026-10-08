// MNQ v3 T1 evaluation from 5-minute bars: the same rules as the backtest
// engine (mnq_v3.py) and the Pine strategy (pine/T1_Zone1_v3.pine).
//   IB 09:30-10:30 ET; IB2 = the extreme formed last; zone = |10:30 close - IB2| / R.
//   Zone 1 (zone <= 25%): long IBH-0.25R / stop IBH-0.55R / target IBH,
//                         short IBL+0.20R / stop IBL+0.45R / target IBL,
//                         VWAP (prior bar) below a long / above a short entry,
//                         a touch while VWAP is wrong skips the day, cancel 14:00.
//   Zone 3a (50-75%):     market at the 10:30 close toward IB1, stop IB2 -/+ 0.25R.
//   Gap >= 1.0% skips T1. Flat at the 15:55 close. Lots = max(1, floor(risk / (pts x $2))).

export type Bar = { t: number; o: number; h: number; l: number; c: number; v: number }
type EtBar = Bar & { date: string; hm: number; dow: number }

export type T1Snapshot = {
  /** The status-line text. */
  line: string
  /** A longer readout for the /t1 command. */
  detail: string
  /** 'none' before a setup exists or when skipped; otherwise the order's state. */
  state: 'waiting' | 'skip' | 'working' | 'withheld' | 'open' | 'target' | 'stop' | 'eod' | 'cancelled' | 'vwap-skip'
}

const TICK = 0.25
const PT_VALUE = 2
const round = (x: number) => Math.round(x / TICK) * TICK
const px = (x: number) => x.toFixed(2)
const usd = (x: number) => (x >= 0 ? '+$' : '-$') + Math.abs(Math.round(x)).toLocaleString('en-US')
const hhmm = (hm: number) => `${Math.floor(hm / 100)}:${String(hm % 100).padStart(2, '0')}`

/** US Eastern offset from UTC in hours for a UTC instant (DST: 2nd Sun Mar 2am to 1st Sun Nov 2am). */
export function etOffsetHours(ms: number): number {
  const y = new Date(ms).getUTCFullYear()
  const sunday = (month: number, nth: number) => {
    const firstDow = new Date(Date.UTC(y, month, 1)).getUTCDay()
    return 1 + ((7 - firstDow) % 7) + 7 * (nth - 1)
  }
  const start = Date.UTC(y, 2, sunday(2, 2), 7) // 02:00 EST
  const end = Date.UTC(y, 10, sunday(10, 1), 6) // 02:00 EDT
  return ms >= start && ms < end ? -4 : -5
}

/** Eastern date (YYYY-MM-DD), HHMM and weekday (0 = Sunday) of a UTC instant. */
export function etParts(ms: number): { date: string; hm: number; dow: number } {
  const d = new Date(ms + etOffsetHours(ms) * 3_600_000)
  const date = `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, '0')}-${String(d.getUTCDate()).padStart(2, '0')}`
  return { date, hm: d.getUTCHours() * 100 + d.getUTCMinutes(), dow: d.getUTCDay() }
}

/** Finds the bars array in a TradingView MCP get-ohlcv answer (text or object). */
export function parseBars(answer: unknown): Bar[] {
  const visit = (x: unknown, depth: number): Bar[] | undefined => {
    if (depth > 6 || x === null || x === undefined) return undefined
    if (typeof x === 'string') {
      const at = x.indexOf('{')
      if (at < 0 || !x.includes('"bars"')) return undefined
      try {
        return visit(JSON.parse(x.slice(at)), depth + 1)
      } catch {
        return undefined
      }
    }
    if (Array.isArray(x)) {
      for (const item of x) {
        const found = visit(item, depth + 1)
        if (found) return found
      }
      return undefined
    }
    if (typeof x === 'object') {
      const rec = x as Record<string, unknown>
      if (Array.isArray(rec.bars)) {
        return rec.bars
          .map(b => b as Record<string, unknown>)
          .filter(b => typeof b.t === 'number' && typeof b.c === 'number')
          .map(b => ({ t: Number(b.t), o: Number(b.o), h: Number(b.h), l: Number(b.l), c: Number(b.c), v: Number(b.v ?? 0) }))
      }
      for (const value of Object.values(rec)) {
        const found = visit(value, depth + 1)
        if (found) return found
      }
    }
    return undefined
  }
  return visit(answer, 0) ?? []
}

/** Evaluates today's T1 from bars (oldest first). `riskCap` in dollars. */
export function evaluate(bars: readonly Bar[], riskCap: number): T1Snapshot {
  const all: EtBar[] = bars.map(b => ({ ...b, ...etParts(b.t * 1000) }))
  const rth = all.filter(b => b.hm >= 930 && b.hm < 1600)
  const last = all[all.length - 1]
  if (!last) return { line: 'MNQ T1 · no data', detail: 'No bars came back from TradingView.', state: 'waiting' }
  const asOf = `as of ${hhmm(last.hm)} ET`
  const today = rth.filter(b => b.date === last.date)
  const prior = rth.filter(b => b.date < last.date)
  const prevClose = prior[prior.length - 1]?.c
  const first = today[0]
  if (!first || first.hm !== 930) {
    const msg = prevClose === undefined ? 'waiting for the 9:30 open' : `waiting for the 9:30 open · prior close ${px(prevClose)}`
    return { line: `MNQ T1 · ${msg}`, detail: `${msg} (${asOf}).`, state: 'waiting' }
  }
  const gapPct = prevClose === undefined ? undefined : (Math.abs(first.o - prevClose) / prevClose) * 100
  const gapText = gapPct === undefined ? 'gap n/a' : `gap ${gapPct.toFixed(2)}%`

  const ib = today.filter(b => b.hm < 1030)
  let ibh = -Infinity, ibl = Infinity, hiAt = -1, loAt = -1
  ib.forEach((b, i) => {
    if (b.h > ibh) { ibh = b.h; hiAt = i }
    if (b.l < ibl) { ibl = b.l; loAt = i }
  })
  const range = ibh - ibl
  const ibText = `IB ${px(ibl)}–${px(ibh)}`
  const closeBar = ib[ib.length - 1]
  if (!closeBar || closeBar.hm !== 1025) {
    return { line: `MNQ T1 · building ${ibText} · ${gapText}`, detail: `IB still forming (${asOf}). ${ibText}, ${gapText}.`, state: 'waiting' }
  }
  const skip = (why: string): T1Snapshot => ({
    line: `MNQ T1 · skip: ${why} · ${ibText}`,
    detail: `No T1 today: ${why}. ${ibText} (R ${px(range)}), ${gapText} (${asOf}).`,
    state: 'skip',
  })
  if (gapPct === undefined) return skip('no prior close')
  if (gapPct >= 1.0) return skip(gapText)
  if (range <= 0 || hiAt === loAt) return skip('IB high and low on the same bar')
  const ib2Hi = hiAt > loAt
  const zone = ((ib2Hi ? ibh - closeBar.c : closeBar.c - ibl) / range) * 100

  // VWAP from 09:30 (typical price x volume), per bar.
  let pv = 0, vol = 0
  const vwap = today.map(b => {
    pv += ((b.h + b.l + b.c) / 3) * b.v
    vol += b.v
    return vol > 0 ? pv / vol : b.c
  })
  const after = today.map((b, i) => ({ b, i })).filter(x => x.b.hm >= 1030)

  let side: 1 | -1, entry: number, stop: number, target: number, kind: 'Z1' | 'Z3a'
  if (zone <= 25) {
    kind = 'Z1'
    side = ib2Hi ? 1 : -1
    entry = round(ib2Hi ? ibh - 0.25 * range : ibl + 0.2 * range)
    stop = round(ib2Hi ? ibh - 0.55 * range : ibl + 0.45 * range)
    target = round(ib2Hi ? ibh : ibl)
  } else if (zone >= 50 && zone <= 75) {
    kind = 'Z3a'
    side = ib2Hi ? -1 : 1
    entry = closeBar.c
    stop = round(ib2Hi ? ibh - 0.25 * range : ibl + 0.25 * range)
    target = round(ib2Hi ? ibl : ibh)
  } else {
    return skip(`zone ${zone.toFixed(0)}%`)
  }
  const lots = Math.max(1, Math.floor(riskCap / (Math.abs(entry - stop) * PT_VALUE)))
  const dir = side > 0 ? 'LONG' : 'SHORT'
  const levels = `${dir} ${lots} @${px(entry)} · S ${px(stop)} · T ${px(target)}`
  const head = `MNQ T1 ${kind} ${levels}`

  // Walk the bars after 10:25 the way the engine does.
  let state: T1Snapshot['state'] = kind === 'Z3a' ? 'open' : 'working'
  let fillPx = kind === 'Z3a' ? entry : NaN
  let fillHm = kind === 'Z3a' ? 1025 : 0
  let exitPx = NaN, exitHm = 0
  const closeIdx = today.indexOf(closeBar)
  let working = kind === 'Z3a' || (side > 0 ? (vwap[closeIdx] ?? Infinity) < entry : (vwap[closeIdx] ?? -Infinity) > entry)
  for (const { b, i } of after) {
    if (state === 'working' || state === 'withheld') {
      if (b.hm >= 1400) { state = 'cancelled'; break }
      const touched = side > 0 ? b.l <= entry : b.h >= entry
      if (touched && !working) { state = 'vwap-skip'; break }
      if (touched) {
        state = 'open'
        fillPx = side > 0 ? Math.min(b.o, entry) : Math.max(b.o, entry)
        fillHm = b.hm
      }
    }
    if (state === 'open') {
      const isFillBar = b.hm === fillHm
      if (side > 0 ? b.l <= stop : b.h >= stop) {
        state = 'stop'
        exitPx = (side > 0 ? b.o < stop : b.o > stop) && !isFillBar ? b.o : stop
        exitHm = b.hm
        break
      }
      if (!isFillBar && (side > 0 ? b.h >= target : b.l <= target)) {
        state = 'target'; exitPx = target; exitHm = b.hm; break
      }
      if (b.hm === 1555) { state = 'eod'; exitPx = b.c; exitHm = b.hm; break }
    }
    if (state === 'working' || state === 'withheld') {
      const v = vwap[i] ?? b.c
      working = side > 0 ? v < entry : v > entry
      state = working ? 'working' : 'withheld'
    }
  }
  const lastBar = today[today.length - 1] ?? closeBar
  const pnl = (exit: number) => (exit - fillPx) * side * lots * PT_VALUE
  const tail: Record<T1Snapshot['state'], string> = {
    waiting: '',
    skip: '',
    working: 'order working',
    withheld: 'withheld (VWAP wrong side)',
    open: `filled ${px(fillPx)} at ${hhmm(fillHm)} · open ${usd(pnl(lastBar.c))}`,
    target: `TARGET ${hhmm(exitHm)} ${usd(pnl(exitPx))}`,
    stop: `STOPPED ${hhmm(exitHm)} ${usd(pnl(exitPx))}`,
    eod: `flat 15:55 ${usd(pnl(exitPx))}`,
    cancelled: 'cancelled 14:00 (no fill)',
    'vwap-skip': 'skipped: touched with VWAP on wrong side',
  }
  return {
    line: `${head} · ${tail[state]} · ${hhmm(lastBar.hm)}`,
    detail:
      `T1 ${kind} ${levels} (zone ${zone.toFixed(1)}%, ${gapText}, ${ibText}, R ${px(range)}). ` +
      `Status: ${tail[state]}. Bars to ${hhmm(lastBar.hm)} ET, ~15 min delayed.`,
    state,
  }
}
