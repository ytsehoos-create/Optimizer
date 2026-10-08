import { describe, expect, mock, test } from 'claude-code/testing'
import { etParts, evaluate, parseBars, type Bar } from '../hooks/t1'
import { oct2, sep18, sep22 } from './fixtures'

const TOOL = 'mcp__Trading_View__mcp-tv-get-ohlcv'
const toBars = (rows: readonly (readonly number[])[]): Bar[] =>
  rows.map(([t = 0, o = 0, h = 0, l = 0, c = 0, v = 0]) => ({ t, o, h, l, c, v }))

describe('T1 evaluation on real MNQ days (matches the v3 backtest)', () => {
  test('2026-09-18: Zone 1 short, 2 lots, filled at the 10:30 open, stopped 10:50', () => {
    const snap = evaluate(toBars(sep18), 200)
    expect(snap.state).toBe('stop')
    expect(snap.line).toContain('T1 Z1 SHORT 2 @29724.25')
    expect(snap.line).toContain('S 29762.00 · T 29694.00')
    expect(snap.line).toContain('STOPPED 10:50 -$134')
  })

  test('2026-09-22: Zone 1 long, 1 lot, filled 10:40, target 13:50', () => {
    const snap = evaluate(toBars(sep22), 200)
    expect(snap.state).toBe('target')
    expect(snap.line).toContain('T1 Z1 LONG 1 @30931.50 · S 30864.25 · T 30987.50')
    expect(snap.line).toContain('TARGET 13:50 +$112')
  })

  test('2026-10-02: skipped for the 1.22% gap', () => {
    const snap = evaluate(toBars(oct2), 200)
    expect(snap.state).toBe('skip')
    expect(snap.line).toContain('skip: gap 1.22%')
  })

  test('mid-session: the order is shown working before it fills', () => {
    const upTo1035 = toBars(sep22).filter(b => etParts(b.t * 1000).hm <= 1035 || etParts(b.t * 1000).date < '2026-09-22')
    const snap = evaluate(upTo1035, 200)
    expect(['working', 'withheld']).toContain(snap.state)
    expect(snap.line).toContain('LONG 1 @30931.50')
  })

  test('risk cap sizes lots: 37.75-pt stop is 2 lots at $200, 3 at $300', () => {
    expect(evaluate(toBars(sep18), 200).line).toContain('SHORT 2 @29724.25')
    expect(evaluate(toBars(sep18), 300).line).toContain('SHORT 3 @29724.25')
  })

  test('Eastern time across DST', () => {
    expect(etParts(Date.UTC(2026, 8, 22, 13, 30)).hm).toBe(930) // EDT
    expect(etParts(Date.UTC(2026, 11, 1, 14, 30)).hm).toBe(930) // EST
  })

  test('parses the bars out of the MCP text answer', () => {
    const text = JSON.stringify({ success: true, bars: [{ t: 1, o: 2, h: 3, l: 1, c: 2, v: 5 }] })
    expect(parseBars(text)).toEqual([{ t: 1, o: 2, h: 3, l: 1, c: 2, v: 5 }])
  })
})

describe('the plugin', () => {
  test('/t1 fetches bars, shows the readout and sets the status line', async ($, on) => {
    const statuses: (string | undefined)[] = []
    on('ui.status', ($, e, next) => {
      statuses.push(e.text)
      return next(e)
    })
    on('tool.call', { tool: TOOL }, () => {
      const bars = toBars(sep22)
      return { result: { bars }, text: JSON.stringify({ success: true, bars }) }
    })
    const out = await $.command.run({
      command: 't1',
      args: '',
      origin: { kind: 'composer' },
      presentation: { isFullscreen: false, columns: 120 },
    })
    expect(out.text).toContain('T1 Z1 LONG 1 @30931.50')
    expect(out.text).toContain('TARGET 13:50 +$112')
    expect(statuses.at(-1)).toContain('MNQ T1 Z1 LONG 1')
  })

  test('the 5-minute timer refreshes during RTH only', async ($, on) => {
    const clock = mock.clock(on, { now: Date.UTC(2026, 8, 22, 17, 0) }) // 13:00 ET Tuesday
    let calls = 0
    on('session.start', ($, e) => ({ cwd: e.cwd }))
    on('command.register', ($, e) => ({ value: { command: e.name } }))
    on('tool.call', { tool: TOOL }, () => {
      calls += 1
      const bars = toBars(sep22)
      return { result: { bars }, text: JSON.stringify({ bars }) }
    })
    await $.session.start({ cwd: '/', surface: 'terminal', isInteractive: true })
    await clock.settle()
    const afterStart = calls
    await clock.advance(5 * 60_000)
    expect(calls).toBe(afterStart + 1)
    await clock.set(Date.UTC(2026, 8, 22, 23, 0)) // 19:00 ET: no polling
    const evening = calls
    await clock.advance(15 * 60_000)
    expect(calls).toBe(evening)
  })
})
