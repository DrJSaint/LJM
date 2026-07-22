# Claude Handoff (LJM_Renderer)

## Project Purpose
This repo generates learner journey artifacts from a Word `.docx`:
- LJM poster (PNG)
- MLO card (PNG, transparent header band)
- Combined PDF assembled from generated PNG pages in the Streamlit app

## Current Priority State
The app UI is a mostly plain Streamlit layout after an earlier branding experiment was reverted.
The user prefers minimal UI customization — do not reintroduce heavy custom CSS unless explicitly asked.

As of this session, the app always generates all assets together (PDF, both PNGs, review text) —
there is no more PNG/PDF download-type choice. See "Streamlit app" below.

## What Is Implemented

### 1) Core CLI pipeline (existing scripts)
- Extract: `python scripts/extract_student_journey_map_v2.py`
- LJM render: `python scripts/render_student_journey_map_png.py`
- MLO render: `python scripts/render_module_learning_outcomes_png.py`
- Wrapper: `python scripts/make_student_journey_map.py`

### 2) MLO renderer behavior
In `python scripts/render_module_learning_outcomes_png.py`:
- Dynamic height by outcome count/content (no forced clipping)
- Header row transparent in PNG (`RGBA`)
- Header text in dark palette color, reads `Learning\nOutcomes\nfor {code}` (lowercase "for")
- Defaults currently tuned to (pre-scale, "nominal" units — see resolution note below):
  - header size: 52
  - code size: 52
  - title size: 37
  - desc size: 37
  - line spacing: 8
  - header line gap: 0

### 3) Wrapper flags for MLO typography
In `python scripts/make_student_journey_map.py`:
- `--mlo-header-size`
- `--mlo-code-size`
- `--mlo-title-size`
- `--mlo-desc-size`
- `--mlo-line-spacing`
- `--mlo-header-line-gap`

These values are specified in nominal ("1x") units — the renderer scales them internally (see below).

### 4) Render resolution / print quality
Both renderers deliver 3x their original design resolution now (bumped from 1x, then 2x, then 3x
during this session, based on user feedback that output looked soft when zoomed/printed):
- `render_student_journey_map_png.py`: `RENDER_SCALE = 6` (supersampling used only to antialias
  circles/lines/pill corners — Pillow doesn't antialias shapes at draw time) and `PRINT_SCALE = 3`
  (multiplies the final delivered resolution beyond the original 800px design width). Final PNG is
  ~2400px wide. The embedded PDF DPI (`PDF_BASE_RESOLUTION * PRINT_SCALE` = 450) scales with it so
  the physical PDF page size is unchanged, just denser.
  - A handful of hardcoded pixel offsets (title start y, node-label nudge, block-width padding, etc.)
    were re-based as named constants (`_legacy_scaled(...)`) so they stay proportional if `RENDER_SCALE`
    changes again — they were tuned by eye at the old `RENDER_SCALE = 3` and would otherwise drift.
  - **Fixed (follow-up session, 2026-07-22):** that rebase missed one spot. `compute_standard_image_height()`
    (used by `standard` and `fit-fixed` layout modes only — `flex-height` was unaffected) had the literal
    `120` appear twice in its original bottom-padding formula: once building `top` (correctly rebased to
    `TIMELINE_TOP_OFFSET`) and once tacked onto the final `return` (missed, left as bare `120`). Fixed by
    reusing `TIMELINE_TOP_OFFSET` for the second occurrence too, since both instances were the same source
    value. Low-impact (a few dozen px of bottom padding drift at current scale) but would have kept
    drifting further out of proportion on any future `RENDER_SCALE` change.
- `render_module_learning_outcomes_png.py`: `RESOLUTION_SCALE = 3` scales the whole design (canvas,
  layout offsets, font sizes) together. Final PNG is ~3240px wide. The CLI override path
  (`--mlo-header-size` etc.) also multiplies by `RESOLUTION_SCALE`, since the Streamlit app always
  passes those flags — without that, overrides would silently reset sizes back to nominal/unscaled.
- This is still raster (Pillow `ImageDraw`), not vector — discussed switching to a vector backend
  (`reportlab`/`pycairo`/SVG) for true infinite-zoom sharpness, but that's a separate, larger rewrite
  the user opted not to pursue for now. Revisit only if asked.

### 5) Streamlit app
In `app.py`:
- Upload one `.docx`
- Render target: `ljm | mlo | both`
- Layout mode: `flex-height | standard | fit-fixed`
- Sidebar has no top-level "Options" header (removed per user feedback — redundant once the
  sidebar has its own subheaded sections). It's split into two subheaded sections separated
  by `st.divider()`: **"Term Start Picker"** (date picker, week-count control, Easter
  caption) above **"LJM height options"** (the layout-mode radio) below — deliberately in
  that order since date/week-count feed the extractor while layout mode only affects the LJM
  renderer. A small scoped CSS rule (`section[data-testid="stSidebar"] hr { margin-bottom:
  0.25rem; }`, in the existing `st.markdown(..., unsafe_allow_html=True)` style block) pulls
  "LJM height options" up closer to the divider above it, per user feedback that the default
  gap looked too loose — kept intentionally narrow/scoped rather than a general stylesheet,
  consistent with "minimal UI, no heavy custom CSS unless explicitly asked."
- Term start (Week 1 Monday) date picker, and a "number of teaching weeks" control:
  strict `10 weeks` / `12 weeks` radio, plus a `Custom` option that reveals a bounded
  number input. Picking a non-Monday snaps forward/back to that week's Monday
  (`resolve_week1()`), shown via a caption rather than a hard validation error.
- No more download-type choice — every run always generates the PDF, both PNGs (whichever the
  render target implies), and the review text together.
- Downloads are shown in this fixed order: **Download all as ZIP** (primary button, bundles
  whichever of the four exist), then PDF, then MLO PNG, then LJM PNG, then review text.
- Hidden (kept in code via `if False` blocks, not deleted):
  - Advanced MLO controls
  - Pipeline log expander
  - JSON download button
  - Reset workspace button
- Pipeline failures (subprocess non-zero exit, e.g. the Easter-year hard error below) now
  surface the actual last stderr line via `st.error(...)` instead of a bare exit code — see
  `run_pipeline()`. The full stdout/stderr is still captured into `last_message` but that
  expander stays hidden per the list above.

### 6) Term dates and Easter break (added 2026-07-22 follow-up)
`extract_student_journey_map_v2.py` no longer computes week dates as pure sequential
Monday–Friday with zero break awareness:
- `config/easter_sunday_dates_2027_2036.csv` (git-tracked; one `Easter Sunday` date per
  row, `DD/MM/YYYY`) is the lookup table, loaded by `load_easter_sundays()`. Plain stdlib
  `csv`, no new dependency (rejected pandas/openpyxl for reading 10 rows).
- `compute_week_dates()` walks the extracted teaching weeks once. If the term's naive date
  range overlaps a year's Easter window (22 Mar–25 Apr, calculated without needing the
  exact date — see `EASTER_WINDOW_EARLIEST`/`LATEST`), it requires that year's Easter Sunday
  to be in the CSV; missing coverage is a **hard error** (raises `ValueError`, pipeline exits
  non-zero) rather than silently skipping the break — confirmed with the user rather than
  guessing. A term that never gets near spring (e.g. Sept–Dec) needs no CSV coverage at all
  for that year.
- When Easter Sunday falls inside the naive range, a single break entry is inserted between
  the two affected teaching weeks (`break_start = easter_sunday - 6 days` (Monday),
  `break_end = easter_sunday + 5 days` (Friday) — the Mon–Fri weeks immediately either side
  of the Easter weekend), and every week from that point on shifts forward 14 calendar days.
  Teaching week numbering/count is untouched; the break is a render-only extra entry.
- JSON schema: each entry in `"weeks"` now has `"kind": "week" | "break"`; a break entry
  reuses existing field names rather than inventing new ones — `week`: `null`, `date_label`:
  the bracketed range e.g. `(22nd Mar - 2nd Apr)` (via `format_break_range()`, same
  ordinal/month helpers as normal weeks but no "Week" prefix), `assessment`: two lines
  joined with `\n` — `"Easter Break\n(22nd Mar - 2nd Apr)"` — since that field is what
  becomes the pill text. Top-level JSON also gets `"easter_break": {"start": iso, "end":
  iso} | None` for transparency/debugging, and the review `.txt` gets an `Easter break` line.
- `render_student_journey_map_png.py` draws the break as **one** timeline node: a small
  sitting-bunny silhouette (`draw_break_icon` — body + head + two ears, plain
  `ImageDraw.ellipse` shapes, deliberately not a font glyph since the project fonts have no
  guaranteed dingbat coverage) in `palette["node"]` (lilac) sat inside a node circle filled
  with `palette["accent"]` (dark maroon) — i.e. the node background matches the pill
  background, with the icon in the *node's* usual lilac instead. Paired with a two-line
  "Easter Break" / date-range pill, also in `palette["accent"]`. No title/detail block for a
  break entry. `wrap_text()` now treats `\n` as a hard line break (splits into paragraphs
  before word-wrapping each) specifically so this two-line pill text renders as intended —
  harmless for every other caller since no other text in this pipeline contains a literal
  newline. This all rides on the existing fact that node spacing is purely by list index
  (`compute_fixed_centers`/`compute_flex_centers`), not by calendar date — so
  `flex-height`/`standard`/`fit-fixed` and `RENDER_SCALE` needed zero changes to accommodate
  the extra node.
- CSV only covers 2027–2036. The very next academic year default (`2026-09-21`) works fine
  today only because that particular term doesn't reach spring 2026/2027's Easter window at
  all in a 10–12 week span — but a spring-term default would need the table extended.
  Revisit/extend the CSV once 2036 approaches, or if someone schedules a spring term in a
  year outside that range.

## Important PDF Logic
In `app.py`:
- Combined PDF is assembled from generated PNGs (`build_multipage_pdf`)
- Transparency handling: alpha images are composited onto **white** `PDF_PAGE_BG = (255, 255, 255)`
  before RGB conversion. This was changed from cream `(247, 241, 232)` this session — cream matched
  the MLO card's row-1 background exactly, so the transparent header band was visually merging into
  row 1 in the PDF instead of staying distinct (see the LJM poster's own background, which is cream —
  the MLO header itself is meant to read as white/blank space above the colored rows).
- Page order: 1. MLO first, 2. LJM second (when both exist)
- `build_zip(results, base_name)` bundles whichever of PDF / MLO PNG / LJM PNG / review text exist
  into an in-memory zip (`io.BytesIO` + `zipfile`) for the "Download all as ZIP" button.

## Local Run
From repo root:

```powershell
.\.venv\Scripts\python.exe -m streamlit run .\app.py
```

If Streamlit is missing in venv:

```powershell
.\.venv\Scripts\python.exe -m pip install streamlit
```

## Known Notes
- Browser may remember collapsed sidebar state; controls are still present in sidebar.
- Combined PDF is app-side composition from PNG outputs.
- User requested minimal UI styling; do not reintroduce heavy custom CSS unless explicitly asked.
- **Not a bug (confirmed by user):** Week 6 of `DSC502_Learner_Journey_Map.docx` has the same
  assessment sentence repeated 3x in the source table cell. This was the user deliberately
  stress-testing text handling by copy-pasting it, not an extraction defect — `extract_assessment()`
  is correctly reading exactly what's in the source. It does still overflow `fit-fixed` mode's minimum
  font size and overlap the timeline under that much text, which is a legitimate layout limit worth
  knowing about, but there's nothing to fix in extraction.
- **Not a bug:** `input/.gitkeep` is intentionally the one tracked file in an otherwise fully
  gitignored `input/` (`input/*` then `!input/.gitkeep` in `.gitignore`). Git can't track an
  empty directory, so `.gitkeep` is a placeholder that keeps the folder present on clone while
  actual uploaded/sample `.docx` files (may contain real course content) stay untracked. Same
  pattern as `output/.gitkeep`.

## Suggested Next Step For Claude
1. Nothing outstanding from this session — all changes below are committed. Confirm with the user
   before starting new work.
2. If asked about vector output: this was discussed and explicitly deferred — don't start it
   unprompted.
3. Keep UI minimal unless user asks for targeted styling only.

## Session Log (2026-07-22 follow-up 4)
- Further sidebar feedback: removed the top-level "Options" header, and added a small scoped
  CSS rule to tighten the gap between the divider and the "LJM height options" subheader
  below it. See "Streamlit app" above.
- Answered a question about `input/.gitkeep` (intentional, not a bug) — see "Known Notes".
  No code change, documented for future reference only.

## Session Log (2026-07-22 follow-up 3)
- User feedback on the first Easter-break pass: switched the break pill from a single
  "Easter Break" line to two lines (label + bracketed date range); swapped the break node's
  colours so the circle background matches the pill's dark maroon and the icon is lilac
  (previously the reverse); replaced the flower icon with a sitting-bunny silhouette; and
  reordered the Streamlit sidebar so the term-start/week-count controls sit above the
  layout-mode control, each under its own subheader ("Term Start Picker" / "LJM height
  options") separated by `st.divider()`. See "Term dates and Easter break" and "Streamlit
  app" above for the resulting detail.

## Session Log (2026-07-22 follow-up 2)
- Added configurable term start date + teaching week count (strict 10/12 + custom escape
  hatch) to the Streamlit sidebar, and automatic Easter break insertion when a term's date
  range covers it. See "Term dates and Easter break" above for full detail. Touched
  `extract_student_journey_map_v2.py` (date math + break insertion + hard error on missing
  CSV year), `render_student_journey_map_png.py` (break node/pill drawing), `app.py` (UI +
  surfacing pipeline error detail instead of a bare exit code), and added
  `config/easter_sunday_dates_2027_2036.csv` (git-tracked; previously an untracked `.xlsx`
  in the gitignored `input/` folder).
- Verified via CLI (Easter-crossing term, non-crossing term, missing-year hard error) and
  via a real browser session (Playwright + Chromium) driving the actual Streamlit app —
  upload, date pick, generate, downloads — for both the happy path and the error path.

## Session Log (2026-07-22 follow-up)
- Fixed a leftover unscaled literal in `compute_standard_image_height()` (`render_student_journey_map_png.py`)
  found while checking whether `standard`/`fit-fixed` layout modes still scale correctly post-3x. See
  "Render resolution / print quality" above for detail.

## Session Log (previous session)
- Cleaned up dead code (unused imports/vars) across all four Python scripts.
- Fixed PDF header-transparency-blending-into-cream-row bug (`PDF_PAGE_BG` → white).
- Changed MLO header text to lowercase "for".
- Increased render resolution 3x on both renderers (see "Render resolution / print quality" above),
  including a compatibility fix to hardcoded pixel offsets in the poster renderer.
- Reworked the Streamlit app: removed the PNG/PDF download-type radio, app now always generates all
  assets, downloads shown in a fixed order, added a "Download all as ZIP" button.
