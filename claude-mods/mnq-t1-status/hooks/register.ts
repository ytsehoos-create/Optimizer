import type { EngineInterface, Register } from 'claude-code'
import { etParts, evaluate, parseBars, type T1Snapshot } from './t1'

const TOOL = 'mcp__Trading_View__mcp-tv-get-ohlcv'
const EVERY_MS = 5 * 60_000

type Settings = { riskCap: number; maxRisk: number; symbol: string }
let latest: T1Snapshot | undefined

// Fetches ~33h of 5-minute bars (prior close through now), evaluates today's T1
// and writes the status line.
async function refresh($: EngineInterface, settings: Settings): Promise<T1Snapshot> {
  const answer = await $.tool.call({ tool: TOOL, symbol: settings.symbol, interval: '5m', count: 400 })
  const rec = answer as Record<string, unknown>
  if (typeof rec.deny === 'string') {
    latest = { line: `MNQ T1 · data refused: ${rec.deny.slice(0, 60)}`, detail: `TradingView call refused: ${rec.deny}`, state: 'waiting' }
  } else {
    const bars = parseBars(rec.text ?? rec.result)
    latest = bars.length
      ? evaluate(bars, settings.riskCap, settings.maxRisk)
      : { line: 'MNQ T1 · no bars from TradingView', detail: 'The TradingView answer held no bars.', state: 'waiting' }
  }
  $.ui.status(latest.line)
  return latest
}

// Every 5 minutes: refresh only during RTH (Mon-Fri 9:25-16:10 ET).
async function tick($: EngineInterface, settings: Settings): Promise<void> {
  const { hm, dow } = etParts(await $.clock.now())
  if (dow >= 1 && dow <= 5 && hm >= 925 && hm <= 1610) await refresh($, settings)
}

export const register: Register = (on, options) => {
  const settings: Settings = {
    riskCap: typeof options.riskCap === 'number' && options.riskCap > 0 ? options.riskCap : 200,
    maxRisk: typeof options.maxRisk === 'number' && options.maxRisk >= 0 ? options.maxRisk : 300,
    symbol: typeof options.symbol === 'string' && options.symbol ? options.symbol : 'CME_MINI:MNQ1!',
  }

  on('session.start', async ($, e, next) => {
    await $.command.register({
      name: 't1',
      description: "Refresh and show today's MNQ v3 T1 setup (levels, lots, order state).",
    })
    refresh($, settings).catch(() => $.ui.status('MNQ T1 · TradingView unavailable'))
    $.clock.every(EVERY_MS, () => {
      tick($, settings).catch(() => $.ui.status('MNQ T1 · TradingView unavailable'))
    })
    return next(e)
  })

  on('command.run', { command: 't1' }, async $ => {
    try {
      const snap = await refresh($, settings)
      return { text: snap.detail }
    } catch {
      return { text: latest ? `TradingView unavailable; last read: ${latest.detail}` : 'TradingView unavailable.' }
    }
  })
}
