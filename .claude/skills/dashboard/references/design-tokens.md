# design tokens

every hex, type rule, and CSS class used by the dashboard skill. lifted from the edgeful web app's algo-analyzer feature. these are the only colors and typographic primitives allowed — do not introduce new ones.

---

## color palette

| role | hex | use it for |
|---|---|---|
| page background | `#09090B` | `<body>` background. never use `#0a0a0a`, `#000`, or any other near-black |
| card surface | `#09090B` | every card body, subsection body, chart canvas area, KPI cell. **same as page** — the card is defined by its border, not by a fill contrast |
| header bar | `#121212` | subsection header strip (the only fill that's lighter than the page, gives the card its top edge), tooltip background, sticky table header |
| border | `#2A2A2A` | card borders, gridlines, dividers, table row separators |
| text primary | `#FFFFFF` | KPI values, headlines, chart titles |
| text secondary | `#C7C7C7` | body copy, chart axis labels, table cell text |
| text muted | `#555555` | timestamps, footnotes, "from:" source labels |
| bullish | `#22C55E` | positive outcomes, win rates ≥65%, "up" / "green" data, success states |
| bearish | `#D32D1F` | negative outcomes, "down" / "red" data, loss states |
| warning | `#D89700` | neutral/middling metrics (50–64% probability), threshold notices |
| primary blue | `#0075FF` | active filter buttons, interactive elements, neutral single-color charts |

**chart overlay rgba values** (with opacity, for Chart.js fills):

- bullish fill: `rgba(34, 197, 94, 0.7)` (body), border `#22C55E`
- bearish fill: `rgba(211, 45, 31, 0.7)` (body), border `#D32D1F`
- warning fill: `rgba(216, 151, 0, 0.7)` (body), border `#D89700`
- primary fill: `rgba(0, 117, 255, 0.7)` (body), border `#0075FF`
- neutral fill (gridlines/quiet bars): `rgba(85, 85, 85, 0.4)`, border `#555555`

---

## chart series palette (neutral)

for charts where categories DON'T carry win/loss meaning — ticker A vs B, break-type counts, weekday session counts, IB-size buckets — use this 4-tone neutral palette. it matches the live edgeful platform's chart palette and avoids implying outcome polarity where none exists.

| role | hex | use it for |
|---|---|---|
| series 1 (primary) | `#0075FF` | the most-emphasized category (first dataset, the headline series) |
| series 2 (secondary) | `#3D4B5C` | second dataset, mid-tone slate |
| series 3 (tertiary) | `#C7C7C7` | third dataset, light gray |
| series 4 (quaternary) | `#202326` | fourth/last dataset, near-page dark anchor — best for small slices only (see note) |

**chart overlay rgba values for series palette:**

- series 1 fill: `rgba(0, 117, 255, 0.85)`, border `#0075FF`
- series 2 fill: `rgba(61, 75, 92, 0.85)`, border `#3D4B5C`
- series 3 fill: `rgba(199, 199, 199, 0.65)`, border `#C7C7C7`
- series 4 fill: `rgba(32, 35, 38, 0.95)`, border `#3D4B5C` (use slate as visible border; raw `#202326` border disappears against the card)

**when to use series vs semantic:**

- use **series** for category counts, comparisons between tickers/instruments, frequency distributions across buckets, anything where slices/bars don't carry an intrinsic up/down or win/loss meaning
- use **semantic** (bullish/bearish/warning) when the data IS the outcome — filled vs not filled, gap up vs gap down, broke high vs broke low, win vs loss
- mixing is fine within one dashboard: doughnut showing filled vs not filled → semantic; grouped bar showing ES vs NQ counts → series

**caveat on series 4 `#202326`:** very close to the subsection header `#121212`. if the slice is large, it visually merges with the chart background. use it only for the smallest slice in a doughnut, or skip it entirely and stick to 3 tones (series 1, 2, 3) when all categories are similarly sized.

---

## semantic color rules

these are the only acceptable color assignments. enforce them:

1. **bullish outcomes always `#22C55E`.** green is reserved exclusively for positive/up/win data. never use Tailwind `green-400`, `emerald-*`, `lime-*`, or any other green.
2. **bearish outcomes always `#D32D1F`.** red is reserved exclusively for negative/down/loss data. never use `red-500`, `rose-*`, or any other red.
3. **warning always `#D89700`.** for middling probability (50–64%), caution states, or "approach with care" framing.
4. **primary blue `#0075FF` is the first series color and the interactivity color.** active filter buttons, hyperlinks, and the headline series in any neutral chart (it's `series.primary` in the series palette above). never use blue for bullish or bearish data — that overloads the meaning.
5. **neutral text uses white or `#C7C7C7`.** never style neutral text in blue, green, or red.

---

## threshold rules (the 65% rule applied to viz)

mirror algo-analyzer's `winRateColor()` and `pnlColor()` utilities. when a percentage represents probability, win rate, or hit rate:

| value | color | meaning |
|---|---|---|
| ≥ 65% | `#22C55E` bullish | strong historical edge — eligible for "setup" framing |
| 50–64% | `#D89700` warning | exists but not actionable on its own |
| < 50% | `#D32D1F` bearish | weak or contrary — present as context only |

apply this to KPI card values, chip badges, and chart bar colors that represent probabilities. do NOT apply to raw counts or non-probability metrics (those use the neutral primary or text-primary color).

---

## typography

font: **Poppins** only. system sans-serif fallback if it fails to load.

**weights allowed: 400 and 500 only.** medium (500) is the thickest weight. everything else is regular (400). never use `font-light` (300), `font-semibold` (600), or `font-bold` (700). this is a hard design system rule — the platform itself uses only these two weights and the dashboards must match.

**minimum font size: 12px.** nothing in the dashboard renders smaller than 12px — not chips, not badges, not chart axis ticks, not legends, not table cells. the smallest Tailwind class allowed is `text-xs` (12px). do not use `text-[10px]` or `text-[11px]` arbitrary classes, and do not inline `font-size: 10px` / `11px` in any CSS rule. anything that needs to feel "small" stays at 12px and uses muted color (`text-neutral-500`) or uppercase tracking to read as secondary.

| element | tailwind | absolute |
|---|---|---|
| H1 (page title) | `text-3xl font-medium` | 30px / 500 |
| H2 (zone title) | `text-2xl font-medium` | 24px / 500 |
| H3 (subsection title) | `text-lg font-medium` | 18px / 500 |
| stat number (KPI value) | `text-4xl font-medium tabular-nums` | 36px / 500 with `font-feature-settings: "tnum"` |
| stat number small | `text-3xl font-medium tabular-nums` | 30px / 500 |
| body | `text-sm font-normal` | 14px / 400 |
| caption / footnote | `text-xs font-normal text-neutral-400` | 12px / 400 |
| label (small caps) | `text-xs uppercase tracking-wider font-normal text-neutral-500` | 12px / 400 / `letter-spacing: 0.05em` |
| source label ("from: report name") | `text-xs font-normal text-neutral-500 lowercase` | 12px / 400 (spaces, no hyphens in the report name) |
| meta line (pipe subtitle) | `.meta-line` class | 12px / 400 / white, with `.meta-sep` (muted gray) for pipes and `.meta-link` (primary blue) for the edgeful.com link |

**all headlines and body text must be lowercase.** exceptions only for ticker symbols (ES, NQ, SPY), acronyms (IB, ORB, FVG, VWAP, NY, ET), and proper nouns.

---

## spacing & radius

| element | tailwind |
|---|---|
| page container | `max-w-7xl mx-auto px-6 py-10` |
| card padding | `p-6` (24px all sides) |
| KPI cell padding | `p-5` or `p-6` |
| gap between cards in a grid | `gap-4` |
| gap between sections | `mb-8` |
| card radius | `rounded-xl` (12px) |
| button / chip radius | `rounded-lg` (8px) |
| pill / badge radius | `rounded-full` |
| section divider | `border-top: 1px solid #2A2A2A; margin: 3rem 0 2rem;` |

---

## font loading snippet

paste this in `<head>` exactly:

```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;500&display=swap" rel="stylesheet">
```

---

## the `<style>` block (paste in `<head>`)

drop this whole block into every dashboard. it defines all reusable component classes referenced by layout-patterns.md and chart-recipes.md. do not modify the hex values.

```html
<style>
  body { font-family: 'Poppins', sans-serif; background: #09090B; color: #C7C7C7; }
  .card { background: #09090B; border: 1px solid #2A2A2A; border-radius: 12px; }
  .stat-num { font-weight: 500; font-feature-settings: "tnum"; }
  table { font-feature-settings: "tnum"; }

  /* subsection header bar — the only surface lighter than the page, gives the card its visible top edge */
  .subsection-header { background: #121212; border-bottom: 1px solid #2A2A2A; padding: 12px 24px; border-top-left-radius: 12px; border-top-right-radius: 12px; }
  .source-label { font-size: 12px; color: #555555; text-transform: lowercase; }
  /* source label links — every report name links to the live edgeful platform */
  .source-label a { color: #555555; text-decoration: none; border-bottom: 1px dashed rgba(85, 85, 85, 0.5); transition: color 0.15s, border-color 0.15s; }
  .source-label a:hover { color: #C7C7C7; border-bottom-color: rgba(199, 199, 199, 0.6); }
  /* ticker chips for multi-ticker dashboards (use instead of plain text when a subsection covers >1 ticker) */
  .source-ticker { color: #60A5FA; text-decoration: none; border-bottom: 1px dashed rgba(96, 165, 250, 0.4); margin-left: 4px; transition: color 0.15s, border-color 0.15s; }
  .source-ticker:hover { color: #93C5FD; border-bottom-color: rgba(147, 197, 253, 0.7); }
  /* meta line — pipe-separated subtitle that mirrors the live edgeful platform header */
  .meta-line { font-size: 12px; color: #FFFFFF; display: flex; flex-wrap: wrap; align-items: center; gap: 4px 8px; }
  .meta-sep { color: #555555; }
  .meta-line a.meta-link { color: #0075FF; text-decoration: none; transition: color 0.15s; }
  .meta-line a.meta-link:hover { color: #60A5FA; }

  /* table row tinting */
  .row-bullish { background: rgba(34, 197, 94, 0.06); }
  .row-bullish:hover { background: rgba(34, 197, 94, 0.12); }
  .row-bearish { background: rgba(211, 45, 31, 0.06); }
  .row-bearish:hover { background: rgba(211, 45, 31, 0.12); }
  tr:hover { background: rgba(255, 255, 255, 0.03); }
  th { cursor: pointer; user-select: none; color: #C7C7C7; }
  th:hover { color: #FFFFFF; }

  /* chips */
  .chip { display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: 12px; }
  .chip-bullish { background: rgba(34, 197, 94, 0.15); color: #4ADE80; }
  .chip-bearish { background: rgba(211, 45, 31, 0.15); color: #F87171; }
  .chip-warning { background: rgba(216, 151, 0, 0.15); color: #FACC15; }
  .chip-neutral { background: rgba(85, 85, 85, 0.2); color: #C7C7C7; }

  /* badges (more prominent than chips, used for zone labels) */
  .badge { display: inline-block; padding: 3px 10px; border-radius: 6px; font-size: 12px; font-weight: 500; letter-spacing: 0.5px; }
  .badge-bullish { background: rgba(34, 197, 94, 0.15); color: #4ADE80; border: 1px solid rgba(34, 197, 94, 0.3); }
  .badge-bearish { background: rgba(211, 45, 31, 0.15); color: #F87171; border: 1px solid rgba(211, 45, 31, 0.3); }
  .badge-neutral { background: rgba(0, 117, 255, 0.15); color: #60A5FA; border: 1px solid rgba(0, 117, 255, 0.3); }

  /* filter buttons (default-on for tables) */
  .filter-btn { padding: 6px 12px; border-radius: 8px; border: 1px solid #2A2A2A; background: #121212; color: #C7C7C7; transition: all 0.15s; font-size: 13px; cursor: pointer; }
  .filter-btn:hover { border-color: #404040; color: #FFFFFF; }
  .filter-btn.active { background: #0075FF; color: #FFFFFF; border-color: #0075FF; font-weight: 500; }

  /* section divider between zones */
  .section-divider { border-top: 1px solid #2A2A2A; margin: 3rem 0 2rem; }
</style>
```

---

## what to reference next

- structural HTML patterns (page shell, zone, subsection, KPI grid, table) → `layout-patterns.md`
- Chart.js configs that consume these tokens → `chart-recipes.md`
