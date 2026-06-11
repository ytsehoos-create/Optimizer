---
name: dashboard
description: Build a polished single-file HTML dashboard from edgeful market data — KPI cards, Chart.js charts, sortable tables, algo-analyzer dark-mode styling. Use when the user says "visualize", "dashboard", "chart this", "show me", "build a report for", or wants to turn report numbers into a shareable page.
---

## when to use this skill

trigger this skill when the user wants to turn edgeful market data into a visual, shareable artifact. natural-language signals include:

- "visualize this data"
- "build me a dashboard for {report}"
- "chart this"
- "show me a report on {ticker}"
- "make this into a page i can share"
- "turn this into a dashboard"

if the user is just asking for a number or a stat, do NOT trigger — that's the `edgeful-api` skill's job. this skill takes data and renders a page.

**data sources accepted:**
- a recent `edgeful-api` response in conversation context
- multiple `edgeful-api` responses (for multi-report dashboards)
- pasted JSON the user provides
- nothing — in which case ask the user how they want to source data (see workflow step 2)

---

## inputs and data sources

two paths to data:

1. **data already in context.** look back through the conversation for `edgeful-api` outputs — recognizable by `startDate`/`endDate`/`summary`/`detailed` keys. cache each by report name so you know what reports are available.
2. **no data in context.** ask the user the fork (workflow step 2). do not invent data, ever.

after you have data, **always offer enrichment**: ask if they want to pull additional related subreports to make the dashboard richer. examples per report family:
- IB → also pull `initial-balance-by-close`, `initial-balance-break-type`, `initial-balance-by-extension`, `opening-candle-color-continuation`
- ORB → also pull `opening-range-breakout-by-close`, `by-levels`, `by-retracement`, `by-size`
- gap fill → also pull `gap-fill-by-close`, `by-fill-time`, `by-prev-candle`, `by-size`

skip the offer if the user already specified a multi-report scope.

---

## the composition contract

every dashboard built by this skill follows the same hierarchy:

```
page
└── container (max-w-7xl)
    ├── header (title, ticker, session, date range, sample size, source-label)
    ├── zone 1
    │   ├── subsection (each labeled "from: {report-slug}")
    │   │   └── content block (KPI grid | chart | table | explainer)
    │   └── subsection ...
    ├── zone 2 (optional, for multi-report)
    └── footer (edgeful attribution + generated timestamp)
```

**rules:**

- **zones are always-on.** every dashboard has ≥1 zone. multi-report dashboards get one zone per source report. zones separated by `.section-divider`.
- **every subsection labels its source report.** in the header bar, under the title, in muted `text-xs`: `from: initial balance breakout by close`. this is non-negotiable — users need to know where each card's data came from. for single-report dashboards, label once in the page header and once per subsection. **render the report name with spaces, not hyphens** — convert the API slug (`initial-balance-breakout-by-close`) into a human-readable label for display. hyphenated slugs read as code; spaces match the rest of the dashboard's lowercase prose.
- **every source label is a clickable link to the live platform.** wrap the report name in `<a href="https://edgeful.com/reports/{market}/{TICKER}/{family}/{subreport}" target="_blank" rel="noopener">`. URL conversion rules, acronym special cases, and multi-ticker patterns live in `references/layout-patterns.md` section 10. base host is `edgeful.com`. tickers uppercase. plain-text source labels are a QA regression.
- a subsection holds **1–2 content blocks max**. more than that → split into a new subsection.

### chart-type picker

| your data shape | chart |
|---|---|
| 2–6 categories summing to 100% | doughnut |
| 7+ categories or non-summing counts (single series) | vertical bar |
| two outcomes per category (bullish/bearish split) | grouped bar (green + red) |
| distribution shares across one dimension | horizontal stacked bar |
| metric over time | line with fill |
| comparison of two scalars | KPI cards side-by-side (no chart) |

full configs in `references/chart-recipes.md`.

### density rules

- **minimum dashboard:** 1 zone with header + 1 KPI strip (4 cards) + 1 chart + footer. ~150 lines of HTML.
- **typical:** 1–2 zones, each with explainer + KPI strip + 2–3 charts + 1 table. ~400–600 lines.
- **maximum:** 3 zones, ~8 charts total. beyond that, split into multiple dashboards.

### required components (every dashboard)

- header with title (lowercase), ticker, session, date range, total sample size, and source-label line
- at least one zone with at least one KPI strip OR explainer
- at least one Chart.js chart
- footer with edgeful attribution, date range, generated timestamp

### default-on conveniences

- **filter buttons** are default-on whenever a data table is present. active state uses primary blue `#0075FF`. never green (green is reserved for bullish outcomes).
- **sortable table headers** are default-on for every data table.

---

## workflow

execute these steps in order. copy the checklist into your response and check off as you go:

```
- [ ] 1. scan context for edgeful api data
- [ ] 2. if no data: ask the fork (api vs paste)
- [ ] 3. if api path: invoke edgeful-api skill, pull data
- [ ] 4. offer enrichment (additional subreports)
- [ ] 5. confirm scope if ambiguous
- [ ] 6. create output folder
- [ ] 7. assemble html (tokens → patterns → recipes)
- [ ] 8. write dashboard.html
- [ ] 9. distribute (open in cli, return artifact in web)
- [ ] 10. run qa checklist
```

**step details:**

1. **scan context.** look for edgeful api response shapes. cache hits per report key.
2. **if no data, ask the fork.** reply exactly: `I can pull from the edgeful API or you can paste data — which?` wait for the user's answer.
3. **if api path: invoke `edgeful-api`.** confirm ticker, market, session, date range, and which reports. pull. cache the response in context.
4. **offer enrichment.** if only one report's data is in context, ask: `want me to pull any related subreports to make this richer? for {report family} I can also pull: {list}.` skip if user gave a clear multi-report brief.
5. **confirm scope** only if ambiguous. one line: `I'll build {N} zones: {titles}. each will have {content summary}. ok?` skip if user is explicit.
6. **create output folder.** slug = kebab-case from dashboard title prefixed with today's date: `output/YYYY.MM.DD-{slug}/`. reuse if folder exists.
7. **assemble html.** read in this order: `references/design-tokens.md` → `references/layout-patterns.md` → `references/chart-recipes.md`. compose: page shell → header → zones (each with subsections, each labeled with its source report) → footer. inline all CSS and JS in one file.
8. **write `dashboard.html`** — single file, no external assets except CDNs.
9. **distribute:**
   - **claude code cli:** run `open output/YYYY.MM.DD-{slug}/dashboard.html` (macOS). the file opens in the default browser. report the absolute path.
   - **claude.ai web app or claude desktop:** return the HTML content as a downloadable artifact in the chat. tell the user to click the file to open it in their browser.
   - detect environment: if you have file-write tools AND the project has an `output/` folder, write to disk. otherwise return as artifact.
10. **run qa checklist** (next section). fix any failures before declaring done.

---

## output location and distribution

- **cli:** `output/YYYY.MM.DD-{slug}/dashboard.html` (matches the workspace output convention)
  - slug rules: lowercase, hyphens for spaces, no punctuation. examples: `ib-orb-joint-es-2024`, `gap-fill-spy-q4`, `nfp-performance-nq`
  - one folder per dashboard. reuse the folder if it already exists.
  - after write, run `open {path}` on macOS to launch the browser
- **claude.ai / claude desktop:** return HTML as artifact. user clicks → opens in browser. mention this explicitly so non-technical users know what to do.
- **all environments:** the HTML is fully self-contained. Tailwind, Chart.js, and Poppins load from public CDNs. no build step, no asset folder, no localhost dependencies. users can email the file, host it on any static service, or open it offline (with degraded styling — fonts and Tailwind need internet).

---

## reference files

read these on demand. do NOT load all three preemptively — only the ones you need for the current dashboard.

- `references/design-tokens.md` — the palette (every hex), typography scale, spacing/radius, font loading, and the CSS `<style>` block that defines every component class. **read this first, every time.** it's the foundation.
- `references/layout-patterns.md` — copy-paste HTML scaffolding for the page shell, header, zones, subsections, KPI grids, chart containers, data tables (with filter buttons), chips, and footer. read this when assembling structure.
- `references/chart-recipes.md` — Chart.js 4.4.1 configs pre-tuned with the edgeful palette: shared helpers (palette, baseTooltip, baseScales), 5 chart recipes, chart-type picker, and one worked example. read this when adding charts.

---

## qa checklist (run before declaring done)

inspect the rendered HTML against every item. fix any failures:

```
- [ ] page background is exactly #09090B (not #0a0a0a, not black)
- [ ] card body fill is exactly #09090B (same as page bg — the card is defined by its #2A2A2A border, not by a contrast surface)
- [ ] subsection header bar is exactly #121212 (slightly lighter than page, gives the card its visible top edge)
- [ ] only two font weights are used: `font-medium` (500) for headings/KPIs/badges, `font-normal` (400) for everything else. no `font-light` (300), `font-semibold` (600), or `font-bold` (700) anywhere. Google Fonts URL loads only `wght@400;500`
- [ ] minimum font size is 12px everywhere. no `font-size: 10px` / `11px` in CSS, no `text-[10px]` / `text-[11px]` arbitrary classes, no Chart.js `size: 10` / `11` in tick or legend configs. smallest Tailwind class allowed is `text-xs` (12px)
- [ ] every headline and body line is lowercase (exceptions: tickers, acronyms, proper nouns)
- [ ] no em dashes (—) in chart labels, axis labels, or KPI labels (em dashes only allowed in optional prose paragraphs)
- [ ] poppins font loaded via google fonts <link> tags
- [ ] chart axis ticks use #C7C7C7, chart gridlines use #2A2A2A
- [ ] outcome-polarity chart data uses semantic colors: bullish #22C55E, bearish #D32D1F, warning #D89700. neutral-category chart data uses the series palette: #0075FF, #3D4B5C, #C7C7C7, #202326. no off-palette colors (no Tailwind green-400, emerald-*, rose-*, etc.)
- [ ] filter buttons present whenever a data table is present (default-on rule)
- [ ] sortable headers present on every data table
- [ ] no `border-l-*` or other colored side accents on any card (status stripes are banned — they read as generic AI dashboard output)
- [ ] every subsection card has a `from: {report name with spaces}` source label in its header (no hyphens — convert `by-close` to `by close`)
- [ ] every `from:` source label has the report name wrapped in an `<a href="https://edgeful.com/reports/{market}/{TICKER}/{family}/{subreport}" target="_blank" rel="noopener">` link, ticker uppercase, pointing to the correct subreport. multi-ticker dashboards use the `.source-ticker` chip pattern from `references/layout-patterns.md` section 10
- [ ] every page header has a `.meta-line` paragraph below the H1 with exactly 4 pipe-separated segments (ticker+report, date range, time range, edgeful.com link)
- [ ] every subsection card's `.subsection-header` has a `.meta-line` paragraph as its second row, using that subsection's specific report family
- [ ] date format is `MM/DD/YY` with a plain hyphen separator (not en-dash, not em-dash). time format is `H:MM am - H:MM pm (UTC±N)` (lowercase am/pm, no leading zero on hour). format rules in `references/layout-patterns.md` section 5a
- [ ] header includes title, ticker, session, date range, sample size, and source-label
- [ ] any highlighted "setup" or "edge" has ≥65% historical probability (compliance rule)
- [ ] footer present with edgeful attribution + date range + generated timestamp
- [ ] file is self-contained: no localhost refs, no external image refs, no missing assets
```

quick verification commands (cli):

```bash
grep -E "font-(bold|semibold|light)" output/YYYY.MM.DD-{slug}/dashboard.html  # should return nothing
grep "wght@" output/YYYY.MM.DD-{slug}/dashboard.html  # should show only wght@400;500 — no 300, 600, or 700
grep -E "font-size: ?(8|9|10|11)px|size: ?(8|9|10|11)[^0-9]|text-\[(8|9|10|11)px\]" output/YYYY.MM.DD-{slug}/dashboard.html  # should be empty: nothing under 12px anywhere
grep -c "meta-line" output/YYYY.MM.DD-{slug}/dashboard.html  # must be >= 1 + number of subsection cards (page header + 1 per subsection)
grep -E "(emerald|rose|lime|sky|amber)-" output/YYYY.MM.DD-{slug}/dashboard.html  # should return nothing
grep "from:" output/YYYY.MM.DD-{slug}/dashboard.html  # should return one match per subsection
grep "source-label.*from:.*<a " output/YYYY.MM.DD-{slug}/dashboard.html  # every from: label should have an <a> tag — count must match the above
grep -E "app\.edgeful\.com|edgeful\.com/reports/[a-z]+/[a-z]" output/YYYY.MM.DD-{slug}/dashboard.html  # should be empty: no app.edgeful.com host, no lowercase tickers in URLs
```

---

## common pitfalls

avoid these — they appear in past one-off dashboards and break brand consistency:

1. **mixed palettes.** the only correct palette is the live edgeful report UI: page bg and card body both `#09090B`, subsection header strip `#121212`, border `#2A2A2A`. do NOT use `#212327` for card body, `#1A1B1F` for header, `#141414`, `#0a0a0a`, or any other near-black variant — they all read as "almost right but not the product."
2. **missing source labels.** subsection cards without a `from:` line. users lose context about which report each metric came from. always include it. write the report name with spaces (`from: initial balance breakout by close`), not the API slug with hyphens (`from: initial-balance-breakout-by-close`).
2a. **unlinked source labels.** every `from:` label must wrap its report name in an `<a href="https://edgeful.com/reports/{market}/{TICKER}/{family}/{subreport}" target="_blank" rel="noopener">` tag so readers can click through to the live platform. plain text source labels are a regression. base host is `edgeful.com` (NOT `app.edgeful.com` — that's the image CDN). tickers always uppercase. full URL conversion rules in `references/layout-patterns.md` section 10.
3. **font-bold creep / font-light creep.** Tailwind defaults and copied snippets often use `font-bold` on headlines or `font-light` on body text. strip both. only `font-normal` (400) and `font-medium` (500) are allowed. medium is the absolute thickest weight in this design system. the Google Fonts URL must load only `wght@400;500` — never include 300, 600, or 700.
4. **em dashes in chart labels.** autocorrect or paste-from-doc often inserts em dashes into axis labels and KPI labels. they break the clean look. use commas or periods in labels; em dashes only in optional prose paragraphs (and even there, prefer commas).
5. **green for non-bullish data.** green is reserved exclusively for positive/up/win outcomes. never use green for "active filter" (that's primary blue), neutral counts, or category comparisons (those use the series palette `#0075FF` / `#3D4B5C` / `#C7C7C7` / `#202326`).
5a. **semantic colors on category data.** if a chart compares ES vs NQ, single-break vs double-break, or weekday counts, the bars don't have outcome polarity — using green/red implies a meaning the data doesn't carry. use the series palette instead (see `references/design-tokens.md` and `references/chart-recipes.md`).
6. **doughnut with >6 slices.** they become unreadable. switch to a vertical bar instead.
7. **promoting setups below 65%.** the 65% rule applies to dashboards too. if a stat is highlighted as actionable ("strong edge", "setup", "tradeable"), it must be ≥65%. lower probabilities present as context only.
8. **left accent borders / status stripes.** never put a colored vertical bar on the side of a card (`border-l-4` with a green/red/yellow color). this pattern reads as generic AI dashboard output. cards are defined by the `#2A2A2A` outline only — no side accents, no callout stripes, no "tone indicators" in any color.
