# chart recipes

copy-paste Chart.js 4.4.1 configs pre-tuned with the edgeful palette. every recipe expects the design-tokens.md `<style>` block and the page shell (with Chart.js CDN loaded) from layout-patterns.md.

paste the **shared helpers** block once at the top of your chart init script. then use the recipes for each canvas.

---

## shared helpers (paste once per dashboard)

```html
<script>
  // edgeful palette — single source of truth for all chart colors
  const palette = {
    bullish:    '#22C55E',
    bearish:    '#D32D1F',
    warning:    '#D89700',
    primary:    '#0075FF',
    neutral:    '#555555',
    textSecondary: '#C7C7C7',
    textMuted:  '#555555',
    grid:       '#2A2A2A',
    surface:    '#121212',
    border:     '#2A2A2A',
  };

  // rgba helpers for fills (Chart.js expects rgba for translucent fills)
  const fill = {
    bullish: 'rgba(34, 197, 94, 0.7)',
    bearish: 'rgba(211, 45, 31, 0.7)',
    warning: 'rgba(216, 151, 0, 0.7)',
    primary: 'rgba(0, 117, 255, 0.7)',
    neutral: 'rgba(85, 85, 85, 0.4)',
    bullishLight: 'rgba(34, 197, 94, 0.15)',
    bearishLight: 'rgba(211, 45, 31, 0.15)',
  };

  // neutral series palette — for category comparisons where bars/slices don't carry win/loss meaning
  // (ticker A vs B, break-type counts, weekday counts). matches the live edgeful platform palette.
  const series = {
    primary:    '#0075FF',  // series 1, the headline category
    secondary:  '#3D4B5C',  // series 2, slate
    tertiary:   '#C7C7C7',  // series 3, light gray
    quaternary: '#202326',  // series 4, dark anchor — use only for small slices
  };
  const seriesFill = {
    primary:    'rgba(0, 117, 255, 0.85)',
    secondary:  'rgba(61, 75, 92, 0.85)',
    tertiary:   'rgba(199, 199, 199, 0.65)',
    quaternary: 'rgba(32, 35, 38, 0.95)',
  };

  // shared tooltip style — dark surface, secondary text, no shadow
  const baseTooltip = {
    backgroundColor: palette.surface,
    titleColor: '#FFFFFF',
    bodyColor: palette.textSecondary,
    borderColor: palette.border,
    borderWidth: 1,
    padding: 10,
    cornerRadius: 6,
    titleFont: { family: 'Poppins', size: 12, weight: '500' },
    bodyFont:  { family: 'Poppins', size: 12, weight: '400' },
  };

  // shared axis scales — gridlines #2A2A2A, ticks #C7C7C7
  const baseScales = {
    x: {
      ticks: { color: palette.textSecondary, font: { family: 'Poppins', size: 12 } },
      grid:  { color: palette.grid, drawBorder: false },
    },
    y: {
      ticks: { color: palette.textSecondary, font: { family: 'Poppins', size: 12 } },
      grid:  { color: palette.grid, drawBorder: false },
      beginAtZero: true,
    },
  };

  // shared base options — applied to every chart
  const baseOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { labels: { color: palette.textSecondary, font: { family: 'Poppins', size: 12 } } },
      tooltip: baseTooltip,
    },
  };
</script>
```

---

## chart-type picker

| your data shape | chart | recipe below |
|---|---|---|
| 2–6 categories summing to 100% | doughnut | recipe 4 |
| 7+ categories OR non-summing counts (single series) | vertical bar (single) | recipe 1 |
| two outcomes per category (bullish/bearish split) | vertical bar (grouped) | recipe 2 |
| distribution shares across one dimension | horizontal stacked bar | recipe 3 |
| metric over time | line with fill | recipe 5 |
| comparison of two scalars | KPI cards side-by-side (not a chart) | use layout-patterns.md §6 |

if your data doesn't fit any of these, default to recipe 1 (single bar) with categories on x-axis.

---

## semantic vs series — which color set to use

every recipe below is shown with the **semantic** palette (bullish green, bearish red, warning yellow). swap to the **series** palette (`series.primary` / `series.secondary` / `series.tertiary` / `series.quaternary`) whenever the data does NOT carry outcome polarity. quick decision rule:

| data is about... | palette | example |
|---|---|---|
| outcomes (filled/unfilled, won/lost, up/down, broke high/low) | semantic | gap up filled vs not filled, win rate per bucket |
| categories (ticker A vs B, weekday counts, break-type frequencies, IB-size buckets) | series | ES vs NQ comparison, mon/tue/wed counts, single-break vs double-break vs no-break |
| probability values colored by threshold (≥65/50-64/<50) | semantic | KPI value coloring, fill-rate per bucket |

mixing is fine within one dashboard. a doughnut showing filled vs not filled (semantic) and a grouped bar showing ES vs NQ counts (series) sit side-by-side without conflict — the colors tell two different kinds of story.

**how to swap a recipe:** replace `fill.bullish` → `seriesFill.primary`, `fill.bearish` → `seriesFill.secondary`, `palette.bullish` → `series.primary`, `palette.bearish` → `series.secondary`. for 3+ series add `series.tertiary` and (rarely) `series.quaternary`.

---

## recipe 1 — vertical bar (single series)

for raw counts or frequencies where no bullish/bearish split exists. uses neutral primary blue.

```html
<script>
  new Chart(document.getElementById('singleBarChart'), {
    type: 'bar',
    data: {
      labels: ['mon', 'tue', 'wed', 'thu', 'fri'],  // your categories
      datasets: [{
        label: 'sessions',
        data: [45, 52, 48, 50, 47],                 // your counts
        backgroundColor: fill.primary,
        borderColor: palette.primary,
        borderWidth: 1,
        borderRadius: 6,
      }],
    },
    options: {
      ...baseOptions,
      scales: baseScales,
      plugins: { ...baseOptions.plugins, legend: { display: false } },
    },
  });
</script>
```

**when to use:** single-metric counts, neutral frequencies, anything where outcome polarity doesn't apply.

---

## recipe 2 — vertical bar (grouped, bullish vs bearish)

two datasets per category — green and red side-by-side. use for outcome splits like "IB high break vs IB low break by weekday."

```html
<script>
  new Chart(document.getElementById('groupedBarChart'), {
    type: 'bar',
    data: {
      labels: ['mon', 'tue', 'wed', 'thu', 'fri'],
      datasets: [
        {
          label: 'bullish outcome',
          data: [12, 15, 11, 14, 13],
          backgroundColor: fill.bullish,
          borderColor: palette.bullish,
          borderWidth: 1,
          borderRadius: 6,
        },
        {
          label: 'bearish outcome',
          data: [8, 7, 10, 6, 9],
          backgroundColor: fill.bearish,
          borderColor: palette.bearish,
          borderWidth: 1,
          borderRadius: 6,
        },
      ],
    },
    options: {
      ...baseOptions,
      scales: baseScales,
    },
  });
</script>
```

**when to use:** two outcomes per category (up days vs down days, gap-up vs gap-down, breaks above vs below).

**neutral variant** — for two non-polar categories (ES vs NQ, weekday counts split by direction without win/loss meaning), swap colors to the series palette:

```js
datasets: [
  { label: 'ES', data: [...], backgroundColor: seriesFill.primary,   borderColor: series.primary,   borderWidth: 1, borderRadius: 6 },
  { label: 'NQ', data: [...], backgroundColor: seriesFill.secondary, borderColor: series.secondary, borderWidth: 1, borderRadius: 6 },
],
```

if you have 3 or 4 datasets, continue with `series.tertiary` and `series.quaternary` (skip quaternary if all bars are similarly sized — see the caveat in design-tokens.md).

---

## recipe 3 — horizontal stacked bar (100% distribution)

each row is one category, segments inside sum to 100%. for "what % of days in each bucket ended bullish vs bearish vs neutral."

```html
<script>
  new Chart(document.getElementById('horizontalStackedChart'), {
    type: 'bar',
    data: {
      labels: ['small IB', 'medium IB', 'large IB'],
      datasets: [
        { label: 'bullish', data: [45, 52, 38], backgroundColor: fill.bullish, borderColor: palette.bullish, borderWidth: 1 },
        { label: 'neutral', data: [10, 8, 12], backgroundColor: fill.neutral, borderColor: palette.neutral, borderWidth: 1 },
        { label: 'bearish', data: [45, 40, 50], backgroundColor: fill.bearish, borderColor: palette.bearish, borderWidth: 1 },
      ],
    },
    options: {
      ...baseOptions,
      indexAxis: 'y',
      scales: {
        x: { ...baseScales.x, stacked: true, max: 100, ticks: { ...baseScales.x.ticks, callback: (v) => v + '%' } },
        y: { ...baseScales.y, stacked: true },
      },
    },
  });
</script>
```

**when to use:** distribution shares across a single dimension where segments sum to 100%.

---

## recipe 4 — doughnut

small categorical distribution (4–6 slices max). show the total in the center via a small subtitle below the canvas (Chart.js plugin-free approach).

**before using:** every slice MUST have a unique color. if two slices share a color, the legend is doing all the visual work and the chart reads as "green-green-red-red." this is the most common doughnut failure mode.

if your data is **direction × outcome** (e.g., gap up filled / gap up unfilled / gap down filled / gap down unfilled), do NOT collapse both dimensions into one doughnut. **default: split into 2 doughnuts side-by-side, one per direction.** escape hatch: if the across-direction comparison matters more than the share view, switch to recipe 2 (grouped bar) with direction on x and outcome as the two datasets.

```html
<script>
  new Chart(document.getElementById('doughnutChart'), {
    type: 'doughnut',
    data: {
      labels: ['IB high break', 'IB low break', 'double break', 'no break'],
      datasets: [{
        data: [42, 28, 18, 12],
        backgroundColor: [fill.bullish, fill.bearish, fill.warning, fill.neutral],
        borderColor:     [palette.bullish, palette.bearish, palette.warning, palette.neutral],
        borderWidth: 1,
      }],
    },
    options: {
      ...baseOptions,
      cutout: '60%',
      plugins: {
        ...baseOptions.plugins,
        legend: { position: 'right', labels: { color: palette.textSecondary, font: { family: 'Poppins', size: 12 }, padding: 12 } },
      },
    },
  });
</script>
```

**when to use:** 2–6 mutually exclusive categories. for >6 categories, switch to a vertical bar instead.

**color mapping rules for doughnut slices:**
- if slices have outcome polarity (bullish/bearish/neutral): use semantic colors `[palette.bullish, palette.bearish, palette.warning, palette.neutral]`
- if slices are neutral categories (break-type counts, instrument counts, IB-size buckets): use the **series palette** in order — `[series.primary, series.tertiary, series.quaternary, series.secondary]`. matches the live edgeful platform doughnut. note the order: tertiary (`#C7C7C7`) comes before quaternary (`#202326`) so the dark anchor lands on the smallest slice; if all slices are similar size, drop quaternary and use only the first 3 tones

---

## recipe 5 — line with fill (cumulative or rolling)

metric over time. fill under line in matching color at 15% opacity. use bullish green if trend is up, bearish red if down, primary blue if neutral.

```html
<script>
  new Chart(document.getElementById('lineChart'), {
    type: 'line',
    data: {
      labels: ['0.5x', '1.0x', '1.5x', '2.0x', '2.5x', '3.0x'],  // x-axis points
      datasets: [{
        label: '% of days reaching',
        data: [92, 78, 61, 45, 28, 14],
        borderColor: palette.bullish,
        backgroundColor: fill.bullishLight,
        fill: true,
        tension: 0.3,
        pointBackgroundColor: palette.bullish,
        pointBorderColor: palette.bullish,
        pointRadius: 4,
        pointHoverRadius: 6,
      }],
    },
    options: {
      ...baseOptions,
      scales: {
        x: baseScales.x,
        y: { ...baseScales.y, max: 100, ticks: { ...baseScales.y.ticks, callback: (v) => v + '%', stepSize: 20 } },
      },
    },
  });
</script>
```

**when to use:** cumulative hit rate, rolling win rate, any metric tracked across a continuous dimension.

---

## worked example — gap-fill summary → finished chart

input data shape (from `edgeful-api report gap-fill-standard ...`):

```json
{
  "startDate": "2024-01-02",
  "endDate": "2024-12-31",
  "summary": [
    { "category": "gap up",              "frequency": 128, "percentage": 50.8 },
    { "category": "gap up filled",       "frequency": 87,  "percentage": 68.0 },
    { "category": "gap up not filled",   "frequency": 41,  "percentage": 32.0 },
    { "category": "gap down",            "frequency": 124, "percentage": 49.2 },
    { "category": "gap down filled",     "frequency": 79,  "percentage": 63.7 },
    { "category": "gap down not filled", "frequency": 45,  "percentage": 36.3 }
  ]
}
```

this data has a direction × outcome structure (gap up vs gap down, then filled vs not filled inside each). per the doughnut rule above, **split into 2 doughnuts** — one per direction. each chart then has only 2 slices (filled green, not filled red), and every visual element is uniquely identifiable without depending on the legend.

```html
<!-- in the zone body, side-by-side grid -->
<div class="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
  <div class="card">
    <div class="subsection-header">
      <div class="flex items-baseline justify-between">
        <h3 class="text-lg font-medium text-white lowercase">gap up outcomes</h3>
        <span class="source-label">from: gap fill standard</span>
      </div>
    </div>
    <div class="p-6">
      <p class="text-sm text-neutral-400 mb-4 lowercase">128 gap ups, 68% closed back to the prior close.</p>
      <div class="h-64"><canvas id="gapUpChart"></canvas></div>
      <p class="text-xs text-neutral-500 mt-3 lowercase">sample: 128 gap up sessions</p>
    </div>
  </div>
  <div class="card">
    <div class="subsection-header">
      <div class="flex items-baseline justify-between">
        <h3 class="text-lg font-medium text-white lowercase">gap down outcomes</h3>
        <span class="source-label">from: gap fill standard</span>
      </div>
    </div>
    <div class="p-6">
      <p class="text-sm text-neutral-400 mb-4 lowercase">124 gap downs, 64% closed back to the prior close.</p>
      <div class="h-64"><canvas id="gapDownChart"></canvas></div>
      <p class="text-xs text-neutral-500 mt-3 lowercase">sample: 124 gap down sessions</p>
    </div>
  </div>
</div>

<script>
  const doughnutOptions = (total) => ({
    ...baseOptions,
    cutout: '60%',
    plugins: {
      ...baseOptions.plugins,
      legend: { position: 'right', labels: { color: palette.textSecondary, font: { family: 'Poppins', size: 12 }, padding: 12 } },
      tooltip: { ...baseTooltip, callbacks: { label: (ctx) => `${ctx.label}: ${ctx.parsed} sessions (${Math.round(ctx.parsed/total*100)}%)` } },
    },
  });
  new Chart(document.getElementById('gapUpChart'), {
    type: 'doughnut',
    data: {
      labels: ['filled', 'not filled'],
      datasets: [{
        data: [87, 41],
        backgroundColor: [fill.bullish, fill.bearish],
        borderColor:     [palette.bullish, palette.bearish],
        borderWidth: 1,
      }],
    },
    options: doughnutOptions(128),
  });
  new Chart(document.getElementById('gapDownChart'), {
    type: 'doughnut',
    data: {
      labels: ['filled', 'not filled'],
      datasets: [{
        data: [79, 45],
        backgroundColor: [fill.bullish, fill.bearish],
        borderColor:     [palette.bullish, palette.bearish],
        borderWidth: 1,
      }],
    },
    options: doughnutOptions(124),
  });
</script>
```

**why not one 4-slice doughnut:** if you color it bullish/bearish/bullish/bearish (filled=green, unfilled=red), the chart reads as "green green red red" — two pairs of identical slices distinguishable only by the legend text. the 2-doughnut split makes the share view scannable inside each direction, and the difference between directions readable by glancing across the two charts.

---

## what to reference next

- structural HTML (where these canvases live) → `layout-patterns.md`
- color and typography rules these recipes consume → `design-tokens.md`
