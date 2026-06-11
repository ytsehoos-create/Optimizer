# layout patterns

copy-paste HTML scaffolding for every structural element of a dashboard. all patterns assume the design-tokens.md `<style>` block is already in the page `<head>`. all colors come from that token set — never inline new hex values.

structure mental model:

```
page
└── container (max-w-7xl)
    ├── header
    ├── zone 1
    │   ├── subsection (with from: source label)
    │   │   └── content block (KPI grid | chart | table | explainer)
    │   └── subsection ...
    ├── zone 2
    │   └── ...
    └── footer
```

zones are always-on. every dashboard has at least one. multi-report dashboards get one zone per source report.

---

## 1. page shell

the outermost scaffold. paste once per dashboard. **all CDNs and the design-tokens `<style>` block go in `<head>`.**

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{dashboard title} — {ticker} {session} {date-range short}</title>
<script src="https://cdn.tailwindcss.com"></script>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;500&display=swap" rel="stylesheet">
<!-- paste the full <style> block from design-tokens.md here -->
</head>
<body class="min-h-screen">
<div class="max-w-7xl mx-auto px-6 py-10">

  <!-- header goes here -->
  <!-- zones go here -->
  <!-- footer goes here -->

</div>
<!-- chart.js init scripts go here, after the canvases -->
</body>
</html>
```

---

## 2. header block

every dashboard starts with this. eyebrow label + lowercase H1 + subtitle line with ticker, session, date range, and total sample size.

```html
<header class="mb-8">
  <div class="text-xs uppercase tracking-wider text-neutral-500 mb-2">{eyebrow label}</div>
  <h1 class="text-3xl font-medium text-white mb-2 lowercase">{dashboard title}</h1>
  <p class="meta-line">
    <span>{TICKER} {report family}</span>
    <span class="meta-sep">|</span>
    <span>{MM/DD/YY} - {MM/DD/YY}</span>
    <span class="meta-sep">|</span>
    <span>{H:MM am} - {H:MM pm} (UTC{±N})</span>
    <span class="meta-sep">|</span>
    <a class="meta-link" href="https://edgeful.com" target="_blank" rel="noopener">edgeful.com</a>
  </p>
  <p class="source-label mt-2">from: <a href="{report-url}" target="_blank" rel="noopener">{primary report name}</a>{, <a href="{report-url-2}" target="_blank" rel="noopener">{additional report name}</a> ...}</p>
</header>
```

the `.meta-line` mirrors the live edgeful platform's section header subtitle. format rules and session presets are in section 5a.

**variants:** if multi-report, list every source in the `source-label` line (comma-separated), each wrapped in its own `<a>` tag. if single-report, just the one.

**report name formatting:** always render with spaces, not hyphens. convert the API slug `initial-balance-breakout-by-close` to the display label `initial balance breakout by close`. hyphenated slugs read as code; spaces match the rest of the dashboard's lowercase prose. applies to every `from:` label across the page header and every subsection.

**source label linking** (mandatory — see section 10 for the full rule and URL conversion).

---

## 3. explainer card (optional, top of page)

three-column "what / how / takeaway" card. use when the dashboard's setup or framing needs explanation before the data.

```html
<div class="card p-6 mb-8">
  <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
    <div>
      <div class="text-xs uppercase tracking-wider text-neutral-500 mb-2">what this shows</div>
      <p class="text-sm text-neutral-300 leading-relaxed lowercase">{1-3 sentences}</p>
    </div>
    <div>
      <div class="text-xs uppercase tracking-wider text-neutral-500 mb-2">how to read it</div>
      <p class="text-sm text-neutral-300 leading-relaxed lowercase">{1-3 sentences}</p>
    </div>
    <div>
      <div class="text-xs uppercase tracking-wider text-neutral-500 mb-2">takeaway</div>
      <p class="text-sm text-neutral-300 leading-relaxed lowercase">{1-3 sentences}</p>
    </div>
  </div>
</div>
```

**hard rule: no left accent border.** never add `border-l-4` or any colored side stripe to this card (or to any card). that pattern reads as generic AI dashboard output. card definition comes from the `#2A2A2A` outline only — no status stripes, no callout bars, no "accent borders" in any color.

---

## 4. zone container

a thematic top-level section. every dashboard has ≥1 zone. zones are separated by a section divider.

```html
<div class="section-divider"></div>
<section class="mb-12">
  <div class="flex items-center gap-3 mb-3">
    <span class="badge badge-neutral">zone {N}</span>
    <h2 class="text-2xl font-medium text-white lowercase">{zone title}</h2>
  </div>
  <p class="text-sm text-neutral-400 mb-6 lowercase max-w-3xl">{1-2 sentence zone description — what this section answers}</p>

  <!-- subsections go here -->

</section>
```

**variants:**
- single-zone dashboard: skip the `section-divider` div before the first (and only) zone.
- multi-report zone: use the report-relevant badge color (`badge-bullish` for a bullish-leaning report, `badge-bearish` for bearish, `badge-neutral` for purely descriptive).
- omit the badge entirely if the zone is just "overview" and badging adds no info.

---

## 5. subsection card

a titled card inside a zone. each subsection answers exactly one question and holds 1–2 content blocks. **every subsection labels its source report** in the header.

```html
<div class="card mb-6">
  <div class="subsection-header">
    <div class="flex items-baseline justify-between">
      <h3 class="text-lg font-medium text-white lowercase">{subsection title}</h3>
      <span class="source-label">from: <a href="{report-url}" target="_blank" rel="noopener">{report name with spaces}</a></span>
    </div>
    <p class="meta-line mt-1">
      <span>{TICKER} {report family}</span>
      <span class="meta-sep">|</span>
      <span>{MM/DD/YY} - {MM/DD/YY}</span>
      <span class="meta-sep">|</span>
      <span>{H:MM am} - {H:MM pm} (UTC{±N})</span>
      <span class="meta-sep">|</span>
      <a class="meta-link" href="https://edgeful.com" target="_blank" rel="noopener">edgeful.com</a>
    </p>
  </div>
  <div class="p-6">
    <!-- content block goes here: KPI grid, chart, table, or explainer text -->
  </div>
</div>
```

**variants:**
- if subsection holds a chart, the chart container HTML goes inside `<div class="p-6">`.
- if subsection holds a KPI grid, replace `<div class="p-6">` with the KPI grid wrapper (which has its own padding).
- for compact single-stat subsections, swap `p-6` for `p-5`.
- if the subsection covers more than one ticker (a comparison dashboard), use the multi-ticker variant in section 10.
- the `.meta-line` second row repeats the dashboard's date/time intentionally — it makes each card self-contained for screenshots. its first segment uses the report-family name relevant to that specific subsection (not the full dashboard's primary report).

---

## 5a. meta-line format rules

every `.meta-line` (page header and every subsection-header) has exactly four pipe-separated segments. format each one this way:

| segment | format | example | notes |
|---|---|---|---|
| ticker + report family | `{TICKER} {report family with spaces}` | `NQ gap fill` | multi-ticker comparison: `ES, NQ initial balance breakout`. report-family is the same human-readable name used in the `from:` source-label, minus the variant suffix (`standard`, `by weekday`, etc.) |
| date range | `MM/DD/YY - MM/DD/YY` | `11/26/25 - 05/25/26` | convert from `YYYY-MM-DD` (API format): take last 2 chars of year, output `MM/DD/YY`. range separator is a plain hyphen — never an en-dash or em-dash |
| time range with UTC offset | `H:MM am - H:MM pm (UTC±N)` | `9:30 am - 4:00 pm (UTC-4)` | lowercase am/pm. strip leading zero on the hour (`9:30` not `09:30`). offset uses the session preset (table below) — pick DST vs standard time based on the data window's majority |
| edgeful.com | clickable link | `edgeful.com` | always present, always `https://edgeful.com`, always opens in a new tab (`target="_blank" rel="noopener"`) |

**session preset → time range cheat sheet:**

| session | time range | DST | standard |
|---|---|---|---|
| NY (futures, stock, crypto) | `9:30 am - 4:00 pm` | `(UTC-4)` Mar→Nov | `(UTC-5)` Nov→Mar |
| LONDON (futures, forex, crypto) | `8:00 am - 4:00 pm` | `(UTC+1)` Mar→Oct | `(UTC+0)` Oct→Mar |
| ASIA / tokyo (futures, crypto) | `8:00 am - 5:00 pm` | year-round `(UTC+9)` | — |
| forex NY | `8:00 am - 5:00 pm` | `(UTC-4)` DST | `(UTC-5)` |

**multi-report header variant:** if a single-ticker dashboard pulls 2 or 3 reports, list them comma-separated in the first segment of the page-header meta-line (e.g., `NQ opening candle continuation, initial balance breakout`). subsections still use only their specific report family. for 4+ reports, drop the report list and use just the ticker + market (e.g., `NQ futures`) — the `from:` source-label below carries the full list.

---

## 6. KPI grid

responsive grid of stat cards. picks columns based on count. labels on top, value below, optional footnote.

**4-card row (most common):**

```html
<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
  <div class="card p-6">
    <div class="text-xs uppercase tracking-wider text-neutral-500 mb-2">{label}</div>
    <div class="stat-num text-4xl text-white">{value}</div>
    <div class="text-sm text-neutral-400 mt-1 lowercase">{footnote}</div>
  </div>
  <!-- repeat 3 more times -->
</div>
```

**column count rules:**
- 2 stats → `md:grid-cols-2`
- 3 stats → `md:grid-cols-3`
- 4 stats → `md:grid-cols-2 lg:grid-cols-4`
- 5–6 stats → `md:grid-cols-3 lg:grid-cols-6`

**colored value variant** (for stats representing probabilities — apply threshold rule):

```html
<div class="stat-num text-4xl" style="color: #22C55E;">72.3%</div>  <!-- bullish ≥65% -->
<div class="stat-num text-4xl" style="color: #D89700;">58.1%</div>  <!-- warning 50–64% -->
<div class="stat-num text-4xl" style="color: #D32D1F;">42.0%</div>  <!-- bearish <50% -->
```

**compact variant** for dense secondary stats (use `p-5` and `text-3xl`):

```html
<div class="card p-5">
  <div class="text-xs uppercase tracking-wider text-neutral-500 mb-1">{label}</div>
  <div class="stat-num text-3xl text-white">{value}</div>
  <div class="text-xs text-neutral-500 mt-1">{footnote}</div>
</div>
```

---

## 7. chart container

a `<canvas>` wrapped in a card with title, subtitle, and sample-size footnote. the canvas height is fixed to keep aspect ratios consistent. paired with a Chart.js init script (see chart-recipes.md).

```html
<div class="card mb-6">
  <div class="subsection-header">
    <div class="flex items-baseline justify-between">
      <h3 class="text-lg font-medium text-white lowercase">{chart title}</h3>
      <span class="source-label">from: <a href="{report-url}" target="_blank" rel="noopener">{report name with spaces}</a></span>
    </div>
    <p class="meta-line mt-1">
      <span>{TICKER} {report family}</span>
      <span class="meta-sep">|</span>
      <span>{MM/DD/YY} - {MM/DD/YY}</span>
      <span class="meta-sep">|</span>
      <span>{H:MM am} - {H:MM pm} (UTC{±N})</span>
      <span class="meta-sep">|</span>
      <a class="meta-link" href="https://edgeful.com" target="_blank" rel="noopener">edgeful.com</a>
    </p>
  </div>
  <div class="p-6">
    <p class="text-sm text-neutral-400 mb-4 lowercase">{1-line description of what this chart shows}</p>
    <div class="h-72">
      <canvas id="{chartId}"></canvas>
    </div>
    <p class="text-xs text-neutral-500 mt-3 lowercase">sample: {N} sessions · {date-range}</p>
  </div>
</div>
```

**height variants:**
- `h-72` (288px) — default, most charts
- `h-96` (384px) — line charts with long x-axis or distribution charts with many categories
- `h-64` (256px) — compact secondary charts

**side-by-side charts in one zone:**

```html
<div class="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
  <!-- two chart cards -->
</div>
```

---

## 8. data table (with filter buttons)

sortable table with row tinting and filter buttons above. **filter buttons are default-on whenever a data table is present** (per skill rule). row tinting uses `.row-bullish` / `.row-bearish` for outcome-based rows.

```html
<div class="card mb-6">
  <div class="subsection-header">
    <div class="flex items-baseline justify-between">
      <h3 class="text-lg font-medium text-white lowercase">{table title}</h3>
      <span class="source-label">from: <a href="{report-url}" target="_blank" rel="noopener">{report name with spaces}</a></span>
    </div>
    <p class="meta-line mt-1">
      <span>{TICKER} {report family}</span>
      <span class="meta-sep">|</span>
      <span>{MM/DD/YY} - {MM/DD/YY}</span>
      <span class="meta-sep">|</span>
      <span>{H:MM am} - {H:MM pm} (UTC{±N})</span>
      <span class="meta-sep">|</span>
      <a class="meta-link" href="https://edgeful.com" target="_blank" rel="noopener">edgeful.com</a>
    </p>
  </div>
  <div class="p-6">

    <!-- filter buttons -->
    <div class="flex flex-wrap gap-2 mb-4">
      <button class="filter-btn active" data-filter="all">all ({totalCount})</button>
      <button class="filter-btn" data-filter="bullish">bullish ({bullishCount})</button>
      <button class="filter-btn" data-filter="bearish">bearish ({bearishCount})</button>
      <!-- add more buckets as relevant to the data -->
    </div>

    <!-- table -->
    <div class="overflow-x-auto">
      <table class="w-full text-sm">
        <thead class="border-b border-neutral-700">
          <tr class="text-left text-xs uppercase tracking-wider text-neutral-500">
            <th class="px-3 py-2 lowercase" data-sort="date">date</th>
            <th class="px-3 py-2 text-right lowercase" data-sort="num">value 1</th>
            <th class="px-3 py-2 text-right lowercase" data-sort="num">value 2</th>
            <th class="px-3 py-2 lowercase" data-sort="text">outcome</th>
          </tr>
        </thead>
        <tbody>
          <!-- repeat per row, set class="row-bullish" or "row-bearish" based on outcome, data-category for filter -->
          <tr class="row-bullish" data-category="bullish">
            <td class="px-3 py-2 text-neutral-300">{date}</td>
            <td class="px-3 py-2 text-right tabular-nums text-white">{value}</td>
            <td class="px-3 py-2 text-right tabular-nums text-white">{value}</td>
            <td class="px-3 py-2"><span class="chip chip-bullish">bullish</span></td>
          </tr>
        </tbody>
      </table>
    </div>

  </div>
</div>

<!-- table interaction script — paste once per dashboard, after all tables -->
<script>
  // filter buttons
  document.querySelectorAll('.filter-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      const group = e.target.closest('.card');
      group.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
      e.target.classList.add('active');
      const filter = e.target.dataset.filter;
      group.querySelectorAll('tbody tr').forEach(row => {
        row.style.display = (filter === 'all' || row.dataset.category === filter) ? '' : 'none';
      });
    });
  });

  // sortable headers (numeric or text)
  document.querySelectorAll('th[data-sort]').forEach(th => {
    th.addEventListener('click', () => {
      const table = th.closest('table');
      const tbody = table.querySelector('tbody');
      const idx = Array.from(th.parentNode.children).indexOf(th);
      const type = th.dataset.sort;
      const rows = Array.from(tbody.querySelectorAll('tr'));
      const dir = th.dataset.dir === 'asc' ? 'desc' : 'asc';
      th.dataset.dir = dir;
      rows.sort((a, b) => {
        const av = a.children[idx].textContent.trim();
        const bv = b.children[idx].textContent.trim();
        if (type === 'num') return (parseFloat(av) - parseFloat(bv)) * (dir === 'asc' ? 1 : -1);
        return av.localeCompare(bv) * (dir === 'asc' ? 1 : -1);
      });
      rows.forEach(r => tbody.appendChild(r));
    });
  });
</script>
```

---

## 9. chips and badges (inline state markers)

use chips for inline labels inside table cells or paragraphs. use badges for more prominent labeling (zone headers, important callouts).

```html
<span class="chip chip-bullish">bullish</span>
<span class="chip chip-bearish">bearish</span>
<span class="chip chip-warning">caution</span>
<span class="chip chip-neutral">neutral</span>

<span class="badge badge-bullish">strong edge</span>
<span class="badge badge-bearish">weak setup</span>
<span class="badge badge-neutral">descriptive</span>
```

---

## 10. source linking (mandatory)

every `from:` label across the dashboard (header, subsections, chart cards, table cards) MUST wrap the report name in an `<a>` tag that points to the same report on the live edgeful platform. this lets readers click any data block and see the source report with their own settings, drill-downs, and date range.

### base URL and route pattern

```
https://edgeful.com/reports/{market}/{TICKER}/{report-family}/{subreport}
```

- **base**: `https://edgeful.com` (NOT `app.edgeful.com` — that's the image storage CDN, not the page host)
- **{market}**: `futures` | `stock` | `forex` | `crypto`
- **{TICKER}**: uppercase (`ES`, `NQ`, `SPY`, `BTC`)
- **{report-family}**: the parent slug, e.g. `opening-candle-continuation`, `initial-balance-breakout`, `gap-fill`
- **{subreport}**: `standard` | `by-weekday` | `by-size` | `by-rejection` | etc.

### API slug → URL conversion

most API report slugs map mechanically:

| API slug | URL path |
|---|---|
| `gap-fill-standard` | `/gap-fill/standard` |
| `gap-fill-by-fill-time` | `/gap-fill/by-fill-time` |
| `initial-balance-breakout-by-rejection` | `/initial-balance-breakout/by-rejection` |
| `opening-candle-continuation-by-weekday` | `/opening-candle-continuation/by-weekday` |

**conversion rule:** strip the trailing `-standard`, or split on the last `-by-` to separate the family from the subreport.

### acronym-prefix special cases

these families keep an acronym prefix in the URL that is NOT in the API slug. use the URL form for the route:

| API family slug | URL family slug |
|---|---|
| `adr-average-daily-range` | `ADR-average-daily-range` |
| `atr-average-true-range` | `ATR-average-true-range` |
| `opening-range-breakout` | `ORB-opening-range-breakout` |
| `cpi-performance` | `CPI-performance` |
| `fomc-performance` | `FOMC-performance` |
| `nfp-performance` | `NFP-performance` |
| `sma-performance` | `SMA-performance` |
| `ict-opening-retracement` | `ICT-opening-retracement` |

### single-ticker dashboards (the common case)

every `<a>` href uses that one ticker. example for a gap fill dashboard on NQ:

```html
<span class="source-label">
  from: <a href="https://edgeful.com/reports/futures/NQ/gap-fill/by-size" target="_blank" rel="noopener">gap fill by size</a>
</span>
```

### multi-ticker comparison dashboards

a comparison dashboard (e.g., ES vs NQ side-by-side in the same chart) needs both tickers reachable from one label. use the `source-ticker` chip pattern: keep the family/variant name as the primary link (defaulting to the first ticker), then add a small clickable chip per ticker:

```html
<span class="source-label">
  from: <a href="https://edgeful.com/reports/futures/ES/initial-balance-breakout/by-rejection" target="_blank" rel="noopener">initial balance breakout by rejection</a>
  <a class="source-ticker" href="https://edgeful.com/reports/futures/ES/initial-balance-breakout/by-rejection" target="_blank" rel="noopener">ES</a>
  <a class="source-ticker" href="https://edgeful.com/reports/futures/NQ/initial-balance-breakout/by-rejection" target="_blank" rel="noopener">NQ</a>
</span>
```

the `source-ticker` class renders the ticker as a small blue chip with a dashed underline (defined in `design-tokens.md`'s `<style>` block).

### multi-report header variant

if the header lists many subreports (5+), don't link every name inline. summarize and add ticker links at the end:

```html
<p class="source-label mt-2">
  from: initial balance breakout (11 variants: standard, by breakout, by close, by weekday, ...). view in app:
  <a class="source-ticker" href="https://edgeful.com/reports/futures/ES/initial-balance-breakout/standard" target="_blank" rel="noopener">ES</a>
  <a class="source-ticker" href="https://edgeful.com/reports/futures/NQ/initial-balance-breakout/standard" target="_blank" rel="noopener">NQ</a>
</p>
```

### implementation tips

- always set `target="_blank" rel="noopener"` so links open in a new tab without exposing window.opener
- never link the literal word "from:" — only the report name(s) after it
- if a ticker is non-standard (futures contract month code like `NQH6`), use the root symbol (`NQ`) for the URL — the platform handles contract selection internally
- ticker case: always uppercase in URLs. the platform may accept lowercase but uppercase is canonical

---

## 11. footer

every dashboard ends with attribution and a generated timestamp.

```html
<footer class="mt-16 pt-6 border-t border-neutral-800 text-xs text-neutral-500 lowercase">
  <p>data from <a href="https://edgeful.com" class="text-neutral-400 hover:text-white">edgeful.com</a> · {date-range} · {N} sessions</p>
  <p class="mt-1">generated {YYYY-MM-DD} · for educational purposes only · historical performance is not a prediction of future results</p>
</footer>
```

---

## what to reference next

- Chart.js configs that drop into the canvases above → `chart-recipes.md`
- color rules and the `<style>` block these patterns depend on → `design-tokens.md`
