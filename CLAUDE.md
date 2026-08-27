# Claude Handoff (LJM_Renderer)

## Project Purpose
This repo has two parallel pipelines:

### A) LJM / MLO pipeline
Generates learner journey artifacts from a Word `.docx`:
- LJM poster (PNG)
- MLO card (PNG, transparent header band)
- Combined PDF assembled from generated PNG pages in the Streamlit app

### B) LTRS schedule pipeline (added 2026-08-05)
Generates branded conference schedule outputs from an Excel workbook:
- `python scripts/parse_ltrs2026_v1.py` — parses workbook to JSON
- `python scripts/render_ltrs2026_booklet.py` — renders three HTML outputs
- `python scripts/export_pdf.py` — Playwright-based HTML→PDF exporter
- `python scripts/make_ltrs2026_schedule.py` — orchestrates all three steps

Outputs produced by the pipeline:
- `output/ltrs2026_single_page.html` — one-page continuous web/print layout
- `output/ltrs2026_a4_two_side.html` + `.pdf` — two-sided A4 duplex (front/back)
- `output/ltrs2026_a4_fold_card.html` — landscape fold card (Q4|Q1 outer, Q2|Q3 inner)

**Fold card rebuilt (2026-08-06 night session)** — the Parallel Presentation Sessions panel
regression noted below (2026-08-05 evening) is fixed, and the four-quarter content split now
uses real measured page-fit instead of a weight guess. See "Session Log (2026-08-06 night —
fold-card rebuild)" below. Some tweaks were explicitly parked for a future session — don't
assume it's fully finished, just no longer broken.

Brand lockup assets `assets/cp_bt.png` (black text) and `assets/cp_gt.png` (green text) were added
2026-08-06 for the page-footer branding — see "Session Log (2026-08-06 — branding footer, brand
green fix, uniform borders)" below.

**LTRS is now wired into the Streamlit app** (2026-08-06 late night session) — the same upload
widget accepts `.xlsx` and routes to this pipeline instead of the LJM one. See "Streamlit app"
section 5 below and "Session Log (2026-08-06 late night — Streamlit integration + asset
portability fix)".

Run the LTRS pipeline from repo root:
```powershell
.\.venv\Scripts\python.exe "python scripts/make_ltrs2026_schedule.py"
```

Input file expected at: `input/LTRS2026 schedule.xlsx`, sheet `LTRS2026 (v1)`.

## Current Priority State
This repo generates learner journey artifacts from a Word `.docx`:
- LJM poster (PNG)
- MLO card (PNG, transparent header band)
- Combined PDF assembled from generated PNG pages in the Streamlit app

## Current Priority State
The app UI is a mostly plain Streamlit layout after an earlier branding experiment was reverted.
The user prefers minimal UI customization — do not reintroduce heavy custom CSS unless explicitly asked.

As of this session, the app always generates all assets together (PDF, both PNGs, review text) —
there is no more PNG/PDF download-type choice. See "Streamlit app" below.

As of the 2026-07-22 follow-up 9 session, the review-text download button is hidden (kept in
code, not deleted) per user request — the review text is still generated and written to disk
internally, it's just not exposed via the UI or the ZIP right now. The ZIP includes a small
`_alt_text.txt` file (both suggested alt-text sentences) instead. See "Streamlit app" below.

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
- Upload one `.docx` (LJM/MLO pipeline) **or** one `.xlsx` (LTRS pipeline) — same uploader,
  routed by file extension. See the dedicated LTRS-integration note near the end of this
  section for how that branch works; everything else below describes the original LJM/MLO
  path, unchanged by that addition.
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
  render target implies), and the review text together (the review text is still generated and
  written to disk — see the hidden-controls note below for why it has no download button).
- Downloads are shown in this fixed order: **Download all as ZIP** (primary button), then PDF,
  then MLO PNG, then LJM PNG.
- Hidden (kept in code via `if False` blocks, not deleted):
  - Advanced MLO controls
  - Pipeline log expander
  - JSON download button
  - Reset workspace button
  - Review text download button (2026-07-22 follow-up 9 — user wants it back later; it used to
    sit after the LJM PNG button and in the ZIP as `_review.txt`, both now commented out rather
    than removed)
- Pipeline failures (subprocess non-zero exit, e.g. the Easter-year hard error below) now
  surface the actual last stderr line via `st.error(...)` instead of a bare exit code — see
  `run_pipeline()`. A leading `"[FAIL] "` tag (from the extractor's own `fail()` helper, see
  section 8) is stripped before display so the app doesn't show a doubled-up
  "Pipeline failed: [FAIL] ..." message — just the clean sentence itself. The full
  stdout/stderr is still captured into `last_message` but that expander stays hidden per the
  list above.
- Uploading a different file (or removing the current one) immediately clears the previous
  run's `last_results`/`last_message`/download buttons, rather than leaving them showing
  stale downloads until the user clicks Generate again. Tracked via the upload widget's own
  `uploaded_file.file_id` (unique per upload event — Streamlit's `UploadedFile` class) stored
  in `st.session_state["last_uploaded_file_id"]`; a mismatch on rerun triggers the clear.
- Each generated PNG download button is followed by a `st.code(...)` block showing suggested
  alt text (see section 9), read out of the generated JSON's `"alt_text"` field and cached in
  `st.session_state["last_alt_text"]`. `st.code` gives a built-in copy icon, which is the
  actual UX need here — there's no in-app image preview (no `st.image` anywhere) since the
  app is download-only, and PNG file metadata isn't read as alt text by Blackboard or any
  other embedding target, so this had to be copy-paste text rather than baked into the file.
  - **Made compact (2026-07-22 follow-up 9):** Streamlit's default `st.code` padding/font-size/
    line-height and inter-element spacing are sized for multi-line code, not one line of copy
    text — the block read as oversized and only loosely associated with the download button it
    describes. Fixed with scoped CSS in the same `st.markdown(..., unsafe_allow_html=True)`
    style block (only `st.code` usage in the app, so the broad selectors are safe): code font
    forced to 11px with `line-height: 1.25`, `pre` padding cut to `0.15rem 0.6rem`, and the
    caption's own container gets negative top/bottom margins so it sits almost flush against
    the download button above it and the code block below it. The caption is targeted via
    `div[data-testid="stElementContainer"]:has(+ div[data-testid="stElementContainer"] >
    div[data-testid="stCode"])` — "whatever precedes an `st.code` block" — rather than a text
    match, since Streamlit gives no unique per-instance class to key off. Deliberately left
    normal spacing between the code block and the *next* download button, so each PNG's
    button+caption+code still reads as one attached group distinct from the next PNG's group.
    Took three iterative rounds (padding alone, then padding+line-height, then font-size+tighter
    margins) — the first two looked like real fixes in isolated measurement but still read as
    "oversized" to the user until the line-height and inter-element gaps were both addressed.

**LTRS integration (added 2026-08-06 late night session):**

- Detection is by uploaded filename extension only (`uploaded_file.name.lower().endswith(".xlsx")`)
  — no content sniffing, no user-facing mode switch. Computed once per rerun as `is_ltrs` right
  after the (now type-agnostic) `st.file_uploader(..., type=["docx", "xlsx"])` call.
- The uploader call was moved to *before* the `with st.sidebar:` block in the code (Streamlit
  doesn't care about call order between sidebar and main-area — layout position is controlled by
  the `st.sidebar` context manager, not code position) specifically so `is_ltrs` is known before
  the sidebar renders, letting the LJM-only controls (Term Start Picker, LJM height options) be
  wrapped in `if not is_ltrs: ... else: st.caption(...)` instead of showing irrelevant controls
  for an Excel upload.
- `run_ltrs_pipeline()` shells out to `make_ltrs2026_schedule.py` as a single subprocess (same
  pattern as the existing `run_pipeline()` → `make_student_journey_map.py`), not to the three
  underlying scripts individually — reuses the existing orchestrator rather than duplicating its
  logic in `app.py`. The orchestrator still generates the fold card too (cheap, part of the same
  run); `results` just never picks up that file, so it's never surfaced or zipped. If fold-card
  ever needs exposing later, that's a one-line addition to the `results` dict, not a pipeline
  change.
- Button label and download section both branch on `is_ltrs` (stored as
  `st.session_state["last_is_ltrs"]` at generation time, not recomputed from the *current*
  uploader state on every rerun — same reasoning as `last_input_name` already being cached: a
  download button click triggers a rerun, and the uploader could theoretically have changed by
  then). Downloads: ZIP, Two-Side PDF, Two-Side HTML, Single-Page HTML — no fold-card, no
  alt-text/JSON extras (those are LJM-specific concepts that don't apply here).
- Verified end-to-end via a real Playwright browser session: uploaded the actual
  `LTRS2026 schedule.xlsx`, generated, downloaded the ZIP, confirmed exactly the three expected
  files with no fold-card, and additionally extracted the ZIP to a folder with no `assets/`
  sibling anywhere nearby to confirm the downloaded HTML is genuinely self-contained (see the
  asset-embedding note below — this only works *because* of that fix, landing in the same
  session for exactly that reason).

**Asset embedding / portability fix (same session, `render_ltrs2026_booklet.py`):** prompted by
user noticing images go missing when an LTRS HTML file is moved to a different folder. Root
cause was actually two separate things:

1. Every `<img src="../assets/...">` and `@font-face src: url("../assets/...")` was a *relative*
   path, which only resolves correctly if the HTML stays at `output/` with `assets/` as a sibling
   directory — move the file anywhere else (email it, download it from Streamlit, drop it in a
   different folder) and the path breaks.
2. Found while fixing #1: the `@font-face` paths all pointed at `../assets/fonts/...`, but
   `assets/fonts/` has never existed as a directory — every font file actually lives directly in
   `assets/`. The Pillow-based LJM/MLO renderers have their own `find_font()` search list that
   tries `assets/fonts/` *then* `assets/`, so they silently succeeded via the second path; the
   LTRS pipeline's CSS had only the one (wrong) hardcoded path with no fallback. This means the
   custom Magnole/Avenir Next fonts have likely never actually loaded in *any* LTRS HTML/PDF
   output produced this session — every render was silently falling back to Georgia/Arial via the
   CSS font-stack, and nobody (including this session, until now) noticed because the fallback
   still looked like a reasonable serif/sans pairing.

- Fix for both: new `asset_data_uri(filename)` helper (`functools.lru_cache`d — the same three
  font files get requested many times across the three HTML outputs, no reason to re-read/re-encode
  each one repeatedly) reads the file from the *correct* `assets/` location and returns a full
  `data:{mime};base64,{...}` URI. Every `@font-face` and `<img src="...">` in `base_css()` and the
  three `render_*_html()` functions now uses this instead of a relative path — genuinely fixes
  both the wrong-path bug and the portability complaint in one change, since the embedded font is
  necessarily read from the real file location.
- One near-miss worth remembering: the fold card's own header block
  (`panel_html()`'s `header_block` string) was a **plain triple-quoted string, not an f-string** —
  the first pass at this edit inserted `{asset_data_uri(...)}` into it and it would have silently
  rendered as literal broken text in the output rather than an image, with no Python error at all
  (valid syntax, just not interpolated). Caught by grepping the generated HTML for literal
  `asset_data_uri(` text after regenerating, rather than assuming the edit worked — worth doing
  that grep again if any *other* string in this file gets a similar edit in the future.
- HTML file size grew by roughly 250-300KB per output (3 embedded fonts ≈ 170KB raw / ~230KB
  base64, plus one logo image) — confirmed acceptable, not worth optimizing further; a
  fully self-contained single-file download matters more here than shaving 300KB.

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

### 7) Public deployment hardening (2026-07-22, prompted by app going live)
The app is now deployed publicly on Streamlit Community Cloud (user shares the link with
colleagues, but it's reachable by anyone with the URL — no auth). That prompted a fact-check
of some generic security reassurance the user got elsewhere, which undersold what actually
happens in this codebase. Two real gaps, both fixed in `app.py`:
- **Uploaded/generated files aren't ephemeral-in-memory — they're written to disk.**
  `run_pipeline()` writes the uploaded `.docx` and every generated PNG/PDF into a real temp
  directory (`tempfile.mkdtemp(prefix="ljm_streamlit_")`), and the only code that ever
  removed it was the "Reset workspace" button — which is hidden behind `if False` (see
  section 5's hidden-controls list). So on a public deployment, uploads accumulated on disk
  indefinitely. Fixed with `cleanup_stale_work_dirs()`: on each new session's first
  `init_state()` call, sweep any `ljm_streamlit_*` temp dir untouched for more than
  `STALE_WORK_DIR_MAX_AGE_SECONDS` (2 hours), skipping the current session's own dir. Gated
  by `st.session_state["stale_cleanup_done"]` so it's a cheap once-per-visitor glob, not a
  per-rerun scan.
- **Unsanitized upload filename.** `save_uploaded_file()` used to build the save path as
  `input_dir / uploaded_file.name` with no sanitization — `uploaded_file.name` is
  attacker-controllable if someone hits the upload endpoint directly rather than through the
  browser file picker (classic path-traversal-via-filename). Fixed by joining
  `Path(uploaded_file.name).name` instead, which strips any directory components before the
  file is ever written.
- Verified via Playwright against the running app (upload/generate still works after both
  changes) and a standalone script confirming the stale-dir sweep only removes genuinely old
  dirs and that the sanitized join can no longer escape the intended folder.

### 8) Friendly extraction error messages (2026-07-22, user feedback on raw error text)
User uploaded a `.docx` with no table (just the word "Hello") and got the readable-but-techy
`Pipeline failed: ValueError: Could not find week table`; uploaded a genuinely empty/invalid
`.docx` and got a much more confusing `Pipeline failed: zipfile.BadZipFile: File is not a zip
file`. Investigated both in `extract_student_journey_map_v2.py`:
- **The `BadZipFile` one was a real bug, not just bad wording.** `python-docx`'s
  `PhysPkgReader.__new__` only runs its own safe "is this actually a zip" check
  (`zipfile.is_zipfile()`) when given a plain `str` path — passed a `pathlib.Path` instead,
  it skips that check and opens the file as a raw `ZipFile`, letting an unwrapped
  `zipfile.BadZipFile` escape instead of python-docx's own `PackageNotFoundError`.
  `extract_weeks()` was calling `Document(docx_path)` with a `Path` object. Fixed by calling
  `Document(str(docx_path))` instead — now any invalid/corrupt/empty file consistently raises
  `PackageNotFoundError`, a single exception type to handle instead of two.
- `main()` now wraps the risky calls (date parsing, `extract_weeks()`, `compute_week_dates()`)
  in `try`/`except`, catching `PackageNotFoundError` and the "no week table" `ValueError`
  specifically and calling a new `fail(message)` helper — prints `[FAIL] {message}` to
  **stderr** (matters: `app.py` only inspects `completed.stderr`, not stdout) and exits 1,
  with no Python traceback or exception-class name in the message. The pre-existing
  Easter-year-missing `ValueError` (section 6) already had a good human message, so it's
  routed through the same `fail()` path for consistent formatting rather than reworded.
  Unrecognized exceptions still propagate as a full traceback — only these specific,
  known/expected cases get the friendly one-liner treatment.
- Verified end-to-end through the running app for all three cases (no table, corrupt file,
  0-byte file) plus a regression check that the happy path and the Easter hard error still
  work — see the `run_pipeline()` note in "Streamlit app" above for the matching app.py-side
  cleanup (stripping the leading `[FAIL]` tag so the app doesn't show it doubled).

### 9) Suggested alt text for the PNGs (2026-07-22, accessibility request)
User asked for "alt text" on the generated PNGs. Clarified with the user first since a PNG
file has no standard field an LMS reads as alt text, and the app has no in-app image preview
(`st.image`) to attach one to either — alt text only takes effect where an image gets
*embedded* (e.g. Blackboard's own alt-text field when inserting an image), so the only
generally useful thing to build was **copy-pasteable suggested text**, not file metadata.
User confirmed that's what they wanted.
- `extract_student_journey_map_v2.py`: `build_ljm_alt_text()` and `build_mlo_alt_text()`
  generate one descriptive sentence per image from data already extracted — module title,
  teaching-week count and date range, which weeks carry assessment pills, whether an Easter
  break is present (LJM); module title and each MLO code/title (MLO card). Deliberately kept
  short rather than a full transcript — the review `.txt` already serves as a complete text
  equivalent, so the alt text explicitly points to it ("See the accompanying review text for
  full week-by-week detail") rather than duplicating it. This is the standard accessibility
  pattern for complex images: short alt text + an adjacent full-text alternative.
  Both strings are computed once in `main()`, added to the JSON payload as `"alt_text":
  {"ljm": ..., "mlo": ...}`, and also printed into the review `.txt` under a new "Suggested
  alt text" heading near the top.
  - **Updated (2026-07-22 follow-up 9):** removed the trailing "See the accompanying review
    text for full week-by-week detail" sentence from `build_ljm_alt_text()`. The review-text
    download was hidden from the app in the same session (see "Streamlit app" above), so that
    sentence would have pointed users at a file they could no longer get to from the app.
    Confirmed with the user via AskUserQuestion rather than guessing whether to reword it
    instead (e.g. to point at the new zipped `_alt_text.txt`) — they chose to drop it outright,
    to be restored verbatim if/when the review-text download comes back. `build_mlo_alt_text()`
    never had this trailing sentence, so it needed no change. Also fielded a question here on
    whether ~40-word alt text is normal: yes — WCAG's "keep it short" guidance targets simple
    images, while complex images (timelines, charts) are expected to pair a short(er) alt text
    with a pointer to a fuller text equivalent, which is this app's existing pattern.
- `app.py`: `run_pipeline()` re-reads the just-written JSON and caches
  `payload["alt_text"]` into `st.session_state["last_alt_text"]` (cheap — the JSON is small
  and already on disk; avoids threading a new return value through `run_pipeline`'s existing
  `dict[str, Path]` return type). Cleared on new upload same as `last_results`. Each PNG's
  download button is immediately followed by a `st.caption` + `st.code(text, language=None)`
  showing that image's suggested alt text — `st.code` was chosen specifically because it
  gives a built-in copy icon for free, which is the actual interaction a user needs here
  (copy → paste into Blackboard's alt-text field), without any custom CSS/JS.
- Verified via Playwright: generated a poster+MLO card, confirmed exactly two `st.code`
  blocks render with the expected wording (module title, week count/date range, assessment
  weeks, Easter break mention, MLO codes/titles).

## Important PDF Logic
In `app.py`:
- Combined PDF is assembled from generated PNGs (`build_multipage_pdf`)
- Transparency handling: alpha images are composited onto **white** `PDF_PAGE_BG = (255, 255, 255)`
  before RGB conversion. This was changed from cream `(247, 241, 232)` this session — cream matched
  the MLO card's row-1 background exactly, so the transparent header band was visually merging into
  row 1 in the PDF instead of staying distinct (see the LJM poster's own background, which is cream —
  the MLO header itself is meant to read as white/blank space above the colored rows).
- Page order: 1. MLO first, 2. LJM second (when both exist)
- `build_zip(results, base_name, alt_text)` bundles whichever of PDF / MLO PNG / LJM PNG exist
  into an in-memory zip (`io.BytesIO` + `zipfile`) for the "Download all as ZIP" button, plus a
  generated `_alt_text.txt` (both suggested alt-text sentences, LJM then MLO, matching the
  review `.txt`'s own label order) written straight into the zip via `archive.writestr(...)`
  rather than read from disk. Review text is no longer bundled (2026-07-22 follow-up 9 — see
  "Streamlit app" above); the `names` dict's `"review"` entry is commented out, not deleted.

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
4. Fold card has known further tweaks parked by the user ("there are tweaks to do, but let's park
   that for now") — unspecified, don't start guessing at them unprompted.
5. Fold card is deliberately NOT wired into the Streamlit app ("Let's leave the card fold out of
   this now") — don't add it without being asked.

## Session Log (2026-08-20, cont'd — bold/italic/underline carried through from Excel)
Same session, right after hyperlinks. User asked to detect basic character-level formatting too
(bold/italic/underline), including formatting applied to only *part* of a cell's text — explicitly
not colour or font, since "we have our strict colour and font rules." First corrected a
misunderstanding: the existing italic on "Chaired by:" lines isn't detected from the source at
all — it's a fixed CSS style baked into the template regardless of what's in the cell.

- **Confirmed feasibility before committing to it**, since this is a materially bigger change
  than the hyperlink feature (a different data model — per-character-run spans, not one
  attribute per cell) rather than assuming it would just work. Tested `openpyxl.load_workbook(...,
  rich_text=True)` (openpyxl 3.1.5, already the installed version) against synthetic cells: a
  cell with *mixed* formatting (e.g. "Dr Jane Smith" italic + "Prof John Doe" bold+underline in
  the same cell) comes back as a `CellRichText` — a sequence of plain strings and `TextBlock`
  objects, each with its own `InlineFont` (`.b`, `.i`, `.u` — deliberately never reading `.color`
  or `.rFont`). A cell with *uniform* whole-cell formatting comes back as a plain string instead,
  with the formatting on the cell's own `.font.bold`/`.italic`/`.underline` — a genuinely
  different code path that needed handling separately, confirmed by testing both cases explicitly
  rather than assuming one code path would cover both.
- **`parse_ltrs2026_v1.py`:** `build_hyperlink_map()` became `build_cell_metadata_map()` — one
  `openpyxl.load_workbook(rich_text=True)` read now covers both hyperlinks and formatting (not a
  third separate file read). New `extract_runs(cell)` returns `[(text_segment, {"bold",
  "italic", "underline"}), ...]` for either representation, normalising whitespace per-segment the
  same way `clean()` does but *without* stripping each segment's edges — stripping every segment
  individually would eat the space between two adjacent runs (e.g. "Chaired by: " next to "Dr Jane
  Smith" would collide into "Chaired by:Dr Jane Smith"). Only the very first segment's leading
  whitespace and the very last segment's trailing whitespace are stripped, matching what a single
  `clean()` call on the joined text would do. `row_to_dict()`'s `_links` field became the more
  general `_meta` (`{"url", "runs"}` per column); new `runs_for(row, column)` returns `None`
  whenever a cell has no actual bold/italic/underline (the vast majority), so nothing downstream
  needs to special-case the common case. Every block-building function gained a matching
  `<field>_runs` key alongside each existing `<field>_url` key, with the same Chair-or-Presenter
  fallback logic already used for `_url` applied consistently to `_runs` too.
- **`render_ltrs2026_booklet.py`:** `link_text()` gained an optional `runs` parameter — when
  present, builds the HTML by wrapping each run's escaped text in `<strong>`/`<em>`/`<u>` per its
  flags (nested, e.g. `<u><strong>text</strong></u>` for bold+underline together), *then* wraps
  the whole result in `<a href>` if the cell also had a link — composing correctly when a cell
  happens to carry both. Threaded `runs=...` through every one of the ~20 `link_text()` call sites
  touched for the hyperlink feature just before this, plus `build_onepager_rows()` carrying the
  new `_runs` fields alongside `_url` the same way. No new CSS needed — `<strong>`/`<em>`/`<u>`
  render via plain browser defaults, which is exactly right here since colour/font are explicitly
  out of scope.
- **Verified with synthetic and real data.** Built test cells covering mixed-run formatting
  (italic + bold+underline in one cell) and whole-cell formatting, confirmed both extract with the
  correct flags in the parsed JSON, then rendered a full pipeline test to PDF and visually
  confirmed each renders correctly (italic, bold, bold+underline nested correctly) with zero
  colour/font drift. Re-ran against the real `input/LTRS2026 schedule.xlsx` (which had changed
  again since the hyperlink work — the user had been actively editing it) and confirmed real bold
  section headers and a real italic note rendered correctly alongside the existing hyperlink,
  including a cell that has *both* a link and underline formatting at once, composing correctly
  with no visual regression anywhere else in the document.

## Session Log (2026-08-20, cont'd — Excel hyperlinks carry through to rendered output)
Same session. User had added real hyperlinks to their workbook (a YouTube link on a workshop
title and on its presenter name) and asked whether links could be detected "anywhere" rather than
needing to specify which columns in advance.

- **Investigated the real file first, not a synthetic guess.** `pandas.read_excel()` only ever
  returns cell *values* — hyperlink metadata isn't exposed through it at all, regardless of engine.
  Confirmed by opening the actual `input/LTRS2026 schedule.xlsx` directly via `openpyxl` and
  scanning every cell for `cell.hyperlink`: exactly 2 hyperlinked cells existed, both the same
  YouTube URL — one on a workshop item's Event (title) cell, one on its Presenter cell. This also
  incidentally caught that the user had renamed the sheet to `LTRS2026 Schedule` since the
  first-sheet-by-default fix — confirming that change was worth doing when it was.
- **`parse_ltrs2026_v1.py`:** new `build_hyperlink_map(input_file, sheet_name)` does a second,
  separate `openpyxl.load_workbook()` read of the same file purely to build a
  `{excel_row: {column_name: url}}` lookup (pandas's own read is left untouched). `row_to_dict()`
  now carries this as a `_links` dict alongside the usual field values, and a new `link_for(row,
  column)` helper reads from it. Every block-building function (`parse_standard_event`,
  `parse_workshop_block`, `parse_plenary_block`, `parse_presentation_sessions`) now attaches a
  matching `<field>_url` key (`title_url`, `location_url`, `presenter_url`, `chair_url`, `room_url`,
  `theme_url`, `presenters_url`) wherever that field's source column had a link — always present,
  defaulting to `None`, so downstream code has one consistent shape to check rather than needing
  to know which fields ever carry a URL. Where a display field already has a fallback (e.g. `chair
  = Chair or Presenter`), the URL fallback mirrors it — whichever column actually supplied the
  text is the one whose link gets used.
- **`render_ltrs2026_booklet.py`:** new `link_text(value, url)` — the `e()`-escaped text, wrapped
  in `<a href="..." target="_blank" rel="noopener">` when a URL is given, unwrapped otherwise.
  Threaded through every place a linkable field gets rendered: `build_onepager_rows()` (carries
  `_url` fields into the row/track/talk dicts it builds — this also required changing `details`
  from a flat `list[str]` to `list[{"text", "url"}]`, since a "Chair: ..." detail line needed to
  carry its own URL), `render_talk_cell()`, `render_track_grid()`, `render_track_stack()`,
  `render_event_cell()` (all four branches), and — the one that actually mattered for the user's
  real example — the workshop-item-row path inside `render_schedule_rows()`. That last one is a
  **separate, direct rendering path from `render_track_grid()`/`render_talk_cell()`** (each
  workshop item becomes its own `<tr>`, not a nested track-grid cell — the `.row-workshop-item`
  CSS class was the tell), so the first pass at this feature built full parse+render plumbing but
  the actual link never showed up anywhere, because this one code path still called `e()` directly.
  Found via `grep -c 'href="https://youtu.be'` returning `0` on all three outputs immediately
  after the first "complete" pass — didn't just trust the code, checked the actual output.
- **Styling:** added `.event-shell a, .track-cell a, .event-col a, .location-col a { color:
  inherit; text-decoration: underline; }` to `schedule_table_css()` (plus `.track-stack-item a`
  in `fold_card_css()`, since fold-card renders through the same shared functions) — link text
  inherits whatever color it would have had anyway (important since some of it sits on dark
  green/lilac backgrounds where default link-blue would clash badly) and is marked out only by an
  underline.
- **Verified thoroughly:** `grep -c "<a "` confirmed exactly 2 anchor tags across the whole
  two-side document (matching the 2 real hyperlinks, no stray wrapping on ordinary titles);
  Playwright confirmed the rendered `<a>` has the correct `href` and a real clickable bounding box;
  a raw byte scan of the exported PDF confirmed genuine `/Subtype /Link` + `/URI` annotations (2 of
  them) — Playwright's PDF export carries real clickable links through from `<a href>` in the
  source HTML, not just visually-styled text, so this works in the PDF too, not only the HTML.
  Rendered the full page to a PNG and visually confirmed only the two real links are underlined,
  everything else is unaffected.

## Session Log (2026-08-20, cont'd — extracted shared single-page/two-side CSS)
Same session. User asked about something mentioned in passing earlier ("three identical
structures") — explained that `render_ltrs2026_booklet.py`'s single-page, two-side, and fold-card
outputs each keep their own hand-duplicated copy of the schedule-table/track-grid CSS, and that
this had already caused a real bug once (the fold-card Parallel Sessions panel regression, see
the 2026-08-05 evening session log) plus ongoing double-editing pain (e.g. today's font-size and
line-break changes both needed applying twice). Asked "So do we have needless duplication?" then
"Can we fix it?" — confirmed yes for single-page/two-side specifically (fold-card has genuinely
different layout constraints — landscape, narrower panels — so some of its divergence is real,
not just copy-paste debt).

- **Compared both CSS blocks property-by-property** before touching anything, to separate what's
  truly identical from what's a legitimate, deliberate difference. Genuinely identical: the whole
  `.schedule-header`/banner block, `.schedule-table`/`.col-time`/`.col-location`/thead styling,
  `.sr-only`, `.time-col`, `.event-shell h3`, `.detail-lines`/`.detail-line`/`.event-note`/
  `.chair-note`, the entire `.track-grid`/`.track-cell`/`.talk-list` block, and the row-type color
  mapping. Genuinely different: the page container itself (`.a4-page` vs `.single-page` — two-side
  is flex-column with `page-break-after`, single-page isn't), `.page-footer` (two-side centers via
  flex auto-margins in the leftover page space, single-page just sits in normal flow), two-side's
  extra `.a4-page.continuation .schedule-table thead` rule and `@media print`/`@media screen`
  blocks, single-page's own separate `@media screen and (max-width: 900px)` responsive query and
  `@media print` rule — and the `--cream` vs `--cream-bg` distinction from the beige-paper work,
  since single-page never got that feature.
- **New `schedule_table_css(background_var: str = "var(--cream)") -> str`** holds everything in
  the "genuinely identical" list above. `.event-col`/`.location-col`/`.track-cell` — the three
  rules that need to differ for the beige-paper PDF — take `background_var` as a parameter instead
  of hardcoding a color, so two-side calls `schedule_table_css(background_var="var(--cream-bg)")`
  and single-page calls it with the default `var(--cream)`. Everything else in the function is
  identical text for both callers. fold-card is untouched — it still has its own separate
  `fold_card_css()`, deliberately not merged into this, since unifying it would fight its real
  layout differences rather than remove actual duplication.
- **Verified the refactor was a pure no-op**, not just assumed from reading the diff: backed up
  the four generated HTML files, regenerated the full pipeline, and diffed old vs new byte-for-
  byte. Fold-card came back byte-identical. Single-page and two-side differed only in *where*
  a few rules sit in the CSS (e.g. `.sr-only` moved position, `.a4-page.continuation .schedule-
  table thead` moved position, a stray blank line and a code comment shifted) — no property
  values, selectors, or content changed anywhere. Then rendered the regenerated two-side PDF to a
  PNG and visually confirmed no regression (colors, borders, fonts, layout all intact).

## Session Log (2026-08-20, cont'd — manual line breaks in event titles)
Same session. User showed a screenshot of an Excel cell where they'd used Alt+Enter to put an
event title on two lines ("Keynote" / "Navigating Without a Compass: ..."), and asked whether
that line break can carry through to the rendered output.

- **Root cause, `parse_ltrs2026_v1.py`'s `clean()`:** `re.sub(r"\s+", " ", text)` collapsed *all*
  whitespace, newlines included, into a single space — so a manual line break in Excel was
  silently flattened before it ever reached the renderer. Fixed by preserving line breaks while
  still collapsing incidental horizontal whitespace *within* each line: split on `splitlines()`
  (normalises `\r\n`/`\r`/`\n` alike), collapse runs of spaces/tabs and strip each line
  individually, drop lines that end up empty, then rejoin with `\n`. Applies to every field parsed
  through `clean()` (not just Event), but only Event/title text is realistically ever multi-line
  in practice, and the structural marker comparisons (`event == "Plenary (VC Funding)"` etc.)
  still match correctly since those literal strings never contain manual breaks.
- **`render_ltrs2026_booklet.py`:** added `white-space: pre-line;` to `.event-shell h3` (the title
  element every event/workshop/plenary/session-block title renders through, via the shared
  `render_event_cell()`) in all three CSS scopes — single-page, two-side, fold-card. `e()` already
  HTML-escapes without touching `\n` (only `& < > " '`), so the preserved newline just needed a
  CSS rule that actually renders it as a visual break rather than collapsing it back down (the
  browser/print default for a literal `\n` in HTML text).
- **Verified by rendering, not just reasoning from CSS:** built a synthetic workbook with an Event
  cell containing the exact same two-line text from the user's screenshot, ran the full pipeline,
  confirmed the `\n` survived into the parsed JSON, then rendered the exported PDF's first page to
  a PNG and visually confirmed "Keynote" now sits on its own line above the long subtitle, matching
  the source Excel formatting. Re-ran against the real workbook afterward to confirm ordinary
  single-line titles are unaffected (no accidental wrapping/regression).

## Session Log (2026-08-20, cont'd — friendly errors for a dodgy/empty sheet)
Same session, right after the first-sheet-by-default change above, which prompted the user to
notice the flip side: "It would be useful if it provided an error warning if you uploaded a dodgy
sheet, say with no data, or a non LTRS sheet. Currently it still renders a blank schedule."

- **Root-caused why it went silently blank, in `parse_ltrs2026_v1.py`'s `parse_v1()`.** The
  column-normalisation step (`for col in expected: if col not in df.columns: df[col] = ""`)
  backfills every missing expected column with blanks *unconditionally* — so a completely
  unrelated sheet (wrong columns entirely) doesn't error, it just gets treated as a sheet full of
  blank cells. Every row then fails the `is_block_header` check (needs a Start time and an Event
  value) and the "skip fully blank rows" check catches it, so `programme` ends up `[]` with no
  exception raised anywhere — the render step then dutifully builds a technically-valid but empty
  schedule. A subtler variant: a sheet with *some* matching columns but rows that don't look like
  real schedule entries doesn't produce an empty `programme` either — it produces a list of
  `"unparsed_row"` placeholder entries, which the renderer doesn't know how to draw, so it *still*
  comes out blank-looking despite `programme` being non-empty.
- **Added two validation checks in `parse_v1()`**, both raising `ValueError` with a specific,
  actionable message rather than continuing to a blank render:
  1. Right after reading the sheet, checked *before* the backfill step (so it sees the sheet's
     real original columns): if none of the 7 expected columns (`Start`, `Duration`, `End`,
     `Event`, `Location`, `Presenter`, `Chair`) are present at all, fail immediately and name
     which columns *were* found — catches "wrong sheet/file entirely" (e.g. a notes tab, a
     completely different workbook).
  2. After building `programme`, checked whether *any* block has a real recognised `type` (not
     just `"unparsed_row"`) — catches both a genuinely empty sheet (zero data rows) and a sheet
     with the right columns but rows that don't parse into anything meaningful.
- **Wired through the same `[FAIL]`/`fail()` convention already used by the LJM/MLO extractor**
  (see section 8, "Friendly extraction error messages") — added an identical `fail(message)`
  helper (`print(f"[FAIL] {message}", file=sys.stderr); sys.exit(1)`) and wrapped `main()`'s call
  to `parse_v1()` in `try/except (FileNotFoundError, ValueError)`, routing both through `fail()`.
  This also incidentally gives the pre-existing "input file doesn't exist" case (previously an
  unhandled raw traceback) the same friendly treatment for free.
- **Confirmed the friendly message survives the full subprocess chain unmodified**, not just
  assumed it would: `make_ltrs2026_schedule.py`'s `run()` helper doesn't capture the child
  process's output (`subprocess.run(cmd, text=True)`, no `capture_output`), so
  `parse_ltrs2026_v1.py`'s stderr passes straight through to the orchestrator's own stderr; then
  simulated exactly what `app.py`'s `run_ltrs_pipeline()` does
  (`subprocess.run(orchestrator_cmd, capture_output=True, text=True)`) and confirmed the last
  line of `completed.stderr` is precisely the specific `[FAIL] Sheet '...' doesn't look like an
  LTRS schedule...` message — i.e. this will genuinely reach `st.error(...)` in the Streamlit UI
  worded exactly as written, not just a generic "pipeline failed" fallback.
- **Verified with real dodgy inputs, not just code reading:** built one workbook with entirely
  unrelated columns (`Name`, `Score`) and one with the correct 7 columns but zero data rows,
  confirmed both fail cleanly with exit code 1, the specific messages above, and — checked
  explicitly — no partial/blank JSON or report file gets written on either failure path. Also
  re-ran the full pipeline against the real `input/LTRS2026 schedule.xlsx` afterwards to confirm
  no false-positive regression on valid data.

## Session Log (2026-08-20, cont'd — default to first sheet regardless of name)
Same session, after the beige-paper PDF work above. User asked (having first asked about
multi-sheet workbooks earlier — see the "quick question" note above): "Is it possible for the
script to take the first sheet in the workbook, by default, whatever it's called?"

- **`parse_ltrs2026_v1.py`:** `DEFAULT_SHEET_NAME` changed from the literal `"LTRS2026 (v1)"` to
  `None`. In `parse_v1()`, when `sheet_name is None`, it's resolved up front via
  `pd.ExcelFile(input_file, engine="openpyxl").sheet_names[0]` — the workbook's first sheet by
  position — *before* the actual read, specifically so the parse report/JSON's `"sheet"` field
  still shows the real resolved name (e.g. "RandomFirstSheetName") rather than an opaque `0`.
  `--sheet` still accepts an explicit name to override this. Docstring and `--help` text updated
  to match.
- **`make_ltrs2026_schedule.py`:** `DEFAULT_SHEET` also changed to `None`; the `--sheet` flag is
  only appended to the `parse_ltrs2026_v1.py` subprocess call when explicitly given, so the
  no-flag case falls through to that script's own first-sheet default rather than duplicating the
  "first sheet" logic in two places.
- `app.py`'s `run_ltrs_pipeline()` was already not passing `--sheet` at all, so it picks this up
  for free with no changes needed there.
- **Verified, not just reasoned through:** confirmed the real `input/LTRS2026 schedule.xlsx`
  already has `LTRS2026 (v1)` as its first of six sheets (`['LTRS2026 (v1)', 'LTRS2026 (v2)',
  'LTRS2026 (prev)', 'LTRS2025', 'Sheet1', 'LTRS2026 (prev 1)']`), so the existing default local
  workflow is unaffected — then built a synthetic two-sheet workbook with an oddly-named first
  sheet (`RandomFirstSheetName`) and a second sheet literally named `LTRS2026 (v1)` containing
  different content, ran the parser against it with no `--sheet` flag, and confirmed it picked
  the first sheet by position (`RandomFirstSheetName`'s row, not the named sheet's) — proving
  this is genuinely position-based, not falling back to name-matching under the hood.

## Session Log (2026-08-20, cont'd — beige-paper PDF variant)
Same session, after the border/font fixes below. User reminded me of an earlier flagged
possibility ([[project-multi-tool-workflow]]-adjacent note from the color-centralization
session: "there is a chance we may source some beige paper... I may ask to change our beige to
no-fill in the future") and asked to actually build it: two versions of the two-side PDF, one
for digital/white-paper printing (current behaviour) and one for pre-printed beige paper where
"all currently beige coloured stuff (background, text) would be no-fill." User also said this
only applies to the PDF artifact, not the HTML outputs.

- **Asked a clarifying question before building anything**, since a wrong guess here means
  literally invisible text on a printed conference schedule, not just a cosmetic miss. Checked
  where `var(--cream)` is actually used in the CSS and found it's not just backgrounds — it's
  also the *text* color for the green header banner's lettering, the schedule-table header row,
  and the Time column (cream-on-green, for contrast). Removing fill from a cream *background*
  makes sense on beige paper (the paper already supplies that color, no need to print it) — but
  cream *text* sitting on printed green ink isn't "matching the paper," it's providing contrast
  against the green, and would just vanish if made no-fill regardless of paper color. Asked via
  `AskUserQuestion`; user confirmed **backgrounds only**, text stays as real cream ink. Also
  confirmed the exact desired filenames: `LTRS_A4_PDF_BeigePaperPrint.pdf` and
  `LTRS_A4_PDF_Digital_or_WhitePaperPrint.pdf`, replacing the old `{base_name}_a4_two_side.pdf`
  naming for these two specific files (not templated by base_name).
- **Implementation, `render_ltrs2026_booklet.py`:** `base_css()` gained a `beige_paper: bool =
  False` parameter and a new `--cream-bg` CSS variable — `var(--cream)` when `False` (identical
  output to before, zero behaviour change for single-page/fold-card, which never pass this),
  `transparent` when `True`. Every *background-only* cream usage in the two-side scope
  (`.a4-page`, `.event-col`, `.location-col`, default `.track-cell`, `--row-event`, `body`) was
  repointed from `var(--cream)` to `var(--cream-bg)`; every *text*-color cream usage
  (`.schedule-header`, its `h1`, `.schedule-table thead th`, `.time-col`,
  `.row-parallel_sessions/workshops .track-row-header .track-cell`, the `@media print`
  `!important` overrides) was deliberately left alone. `render_two_side_a4_html()` gained the
  same `beige_paper: bool = False` parameter, threaded straight through to `base_css()`. `main()`
  now writes a second HTML file, `{base_name}_a4_two_side_beige.html` — an internal render
  step/export source, not an app-facing deliverable in its own right (only its exported PDF is,
  per the user's "PDF artifact, not HTML" framing).
- **Implementation, `make_ltrs2026_schedule.py`:** the PDF-export loop now runs twice — once per
  two-side HTML variant — writing to the two fixed filenames above instead of the old
  `{base_name}_a4_two_side.pdf`. `pdf_ok`/exit-code reporting (see the border/font-size session
  above) now covers both exports.
- **Implementation, `app.py`:** `run_ltrs_pipeline()` looks up both fixed PDF filenames (renamed
  result keys `ltrs_two_side_pdf_digital` / `ltrs_two_side_pdf_beige`, replacing the old single
  `ltrs_two_side_pdf` key); `build_ltrs_zip()` bundles both under their real filenames; the
  downloads section now shows two separate buttons, "Download Two-Side PDF (Digital / White
  Paper)" and "Download Two-Side PDF (Beige Paper)".
- **Verified by rendering, not just reasoning from CSS** (per [[feedback-visual-verification]]):
  regenerated the full pipeline, rendered both exported PDFs' first pages to PNG (`pypdfium2`,
  the same one-off local verification tool from the border-fix earlier this session), and
  visually confirmed the beige variant's previously-cream rows are genuinely blank/no-fill (would
  show the physical beige paper) while the green/lilac fills and the banner's cream lettering are
  completely unaffected — and separately re-confirmed the digital variant is byte-for-byte
  unchanged in appearance (still cream backgrounds, no border regression, no font-size
  regression) despite the shared `base_css()` refactor underneath it.

## Session Log (2026-08-20 — printed two-pager: white PDF border, presenter text size)
User printed the two-side PDF for the first time and flagged two things from the physical
printout, both in `render_ltrs2026_booklet.py` (two-side and single-page CSS; fold-card untouched
— it already had the correct pattern, see below):

- **Presenter/detail text bumped from 11px to 12px**, to match `.location-col`'s 12px — user felt
  "Professor Fary Cachelin"-style detail lines under each event title read too small next to the
  location column beside them. Applied to both single-page and two-side (`.detail-lines`), left
  `.event-note`/`.chair-note` (the italic "Chaired by:" line) alone since that wasn't what was
  flagged.
- **Fixed a real double-margin bug causing a white border on the exported PDF only** (not the
  HTML view — `@page` CSS rules only apply to print/PDF rendering, which is exactly why the user
  saw it in the printed PDF but not when just opening the HTML file). Root cause: `.a4-page` /
  `.single-page` are already sized to the *full* physical A4 sheet (`210mm × 297mm`) with their
  own `padding: 8mm` providing the inset — but the accompanying `@page { margin: 8mm }` rule adds
  a *second*, independent 8mm margin on top when Chromium's `page.pdf()` honours it (triggered by
  `export_pdf.py`'s `prefer_css_page_size=True`), shrinking the printable area and letterboxing
  the whole already-inset page inside it. Fixed by setting both `@page` rules' `margin` to `0`,
  leaving `.a4-page`/`.single-page`'s own padding as the sole source of inset — matches how the
  fold card already does it correctly (`.sheet` is pre-shrunk to `281mm` — the landscape page
  width already minus its own 8mm-each-side margin — rather than full page + padding), which is
  why fold-card never had this bug and needed no change here. Single-page's PDF export is still
  disabled in the pipeline, so this was a latent identical bug there too, fixed for consistency
  even though it wasn't yet visibly hit.
- Verified by regenerating the pipeline and rendering the actual exported PDF's first page to a
  PNG (`pypdfium2`, one-off local verification tool, not added to `requirements.txt` since the
  pipeline itself never needs to rasterize a PDF) rather than trusting the CSS reasoning alone —
  confirmed the cream page now fills to the sheet edge with no white margin, and the presenter
  text visibly matches the location column's size.

## Session Log (2026-08-06 late night, cont'd — Streamlit Cloud deployment fixes)
Same night, after the Streamlit-integration work below was pushed. User tested the deployed app
on Streamlit Community Cloud and hit `ImportError: Import openpyxl failed` uploading an `.xlsx`.

- **Root cause:** `requirements.txt` only ever listed `python-docx`, `Pillow`, `streamlit` — the
  entire LTRS pipeline's dependencies (`pandas`, `openpyxl`, `playwright`) were installed directly
  into the local `.venv` at some point (likely during the original Copilot build session) but
  never added to the file Streamlit Cloud actually installs from. Worked locally the whole time
  for exactly that reason; never actually exercised via a fresh install until this test. Fixed by
  adding all three to `requirements.txt`.
- **Anticipated the next blocker rather than waiting for it to surface separately:** `pip install
  playwright` only installs the Python package, not the Chromium binary it drives — both the
  fold-card measurement pass (`split_rows_by_fit()`) and `export_pdf.py`'s PDF export launch
  Chromium via `sync_playwright()`, and the fold card is generated unconditionally as part of
  every LTRS orchestrator run (see "LTRS integration" above), so this would have broken even
  HTML-only output, not just the PDF. Streamlit Community Cloud has no post-install hook to run
  `playwright install chromium` automatically. Fixed with two additions:
  - `packages.txt` (new file, repo root): the apt-level shared libraries Chromium needs on
    Streamlit Cloud's Debian-based image (`libnss3`, `libatk-bridge2.0-0`, `libgbm1`, etc.) —
    Streamlit Cloud reads this file at build time and apt-installs its contents automatically.
  - `ensure_playwright_browsers()` in `app.py`: runs `python -m playwright install chromium` once
    per session before `run_ltrs_pipeline()`'s subprocess call, gated by
    `st.session_state["playwright_browsers_ready"]` — same pattern as the existing
    `stale_cleanup_done` flag. `playwright install` is itself idempotent (no-ops if the browser is
    already downloaded in the container), so the session-state gate only saves a redundant no-op
    subprocess call within one browser session, not a real reinstall each time.
- **Confirmed working by the user against the live deployment** the same night: the `openpyxl`
  error is gone and the anticipated Chromium-binary issue was indeed the next thing hit, cleared
  automatically by `ensure_playwright_browsers()` — user noted a short delay on first LTRS
  generation per (re)deployed container while Chromium downloads, then normal speed after. That
  one-time delay is expected and not a bug — see `ensure_playwright_browsers()`'s own comment for
  why the session-state gate doesn't (and can't) eliminate it, only avoid repeating it needlessly.

## Session Log (2026-08-06 late night — Streamlit integration + asset portability fix)
Fourth session of the same day. User asked to add the LTRS pipeline to the Streamlit front end
("the next step is to add it to the streamlit front end... one uplaod area, and the response
depends on if it is a word doc or excel doc") after noticing a real problem while testing the
fold-card output manually: moving an LTRS HTML file to a different folder breaks its images.
Touched `app.py` and `render_ltrs2026_booklet.py`.

- **Root-caused the portability complaint properly before touching code.** Every image/font in
  the LTRS HTML output was a relative path (`../assets/...`), which only resolves if the HTML
  stays next to its original `output/`/`assets/` folder pair — exactly what breaks when a file is
  moved, emailed, or downloaded from Streamlit (a browser download has no sibling `assets/`
  folder at all). While fixing this, found a second, previously invisible bug: the `@font-face`
  rules pointed at `../assets/fonts/...`, but `assets/fonts/` has never existed as a directory —
  every font file actually lives directly in `assets/`. The Pillow-based LJM/MLO renderers have
  always had a `find_font()` fallback search list that tries `assets/fonts/` then `assets/`, so
  they never surfaced this; the LTRS CSS had only the one wrong hardcoded path with no fallback.
  Practical implication: the custom Magnole/Avenir Next fonts have likely never actually rendered
  in any LTRS output — every render silently fell back to Georgia/Arial via the CSS font-stack,
  unnoticed because the fallback still looked like a plausible serif/sans pairing.
- **Fixed both with one change:** a new `asset_data_uri(filename)` helper in
  `render_ltrs2026_booklet.py` (`functools.lru_cache`d, since the same three font files get
  requested repeatedly across the three HTML outputs) reads a file from the correct `assets/`
  location and returns a `data:{mime};base64,{...}` URI. Every `@font-face` and `<img src="...">`
  across `base_css()` and all three `render_*_html()` functions (single-page, two-side ×2,
  fold-card, plus both `PAGE_FOOTER_LOGO` footer occurrences — 6 image references total) now uses
  this instead of a relative path, so every output HTML file is now fully self-contained with zero
  external file dependencies.
- **Caught a real near-miss while doing the conversion:** the fold card's own primary header
  block was built from a plain triple-quoted string, not an f-string. The first pass at inserting
  `{asset_data_uri(...)}` into it would have silently written that literal text into the output
  HTML instead of an image — valid Python, no error, just a broken render. Caught by reading the
  surrounding code before assuming the edit worked (not by running it and seeing a failure), fixed
  by adding the `f` prefix, then double-checked globally by grepping all three generated HTML
  outputs for the literal string `asset_data_uri(` — confirmed zero matches in all three, meaning
  every occurrence was genuinely interpolated.
- **Wired LTRS into `app.py`** as a second mode of the existing single-upload flow, exactly as the
  user asked for ("Haha, so we could have one upload area, and the response depends on if it is a
  word doc or excel doc. It is not scalable but I like it! Let's do it!"):
  - `st.file_uploader(..., type=["docx", "xlsx"])` now accepts both; `is_ltrs` is computed from
    the uploaded filename's extension right after upload, before the sidebar renders, so the
    sidebar can conditionally hide the LJM-only controls (Term Start Picker, LJM height options)
    behind `if not is_ltrs: ... else: st.caption("No extra options needed for LTRS schedules —
    just upload and generate.")`.
  - New `run_ltrs_pipeline()` shells out to the existing `make_ltrs2026_schedule.py` orchestrator
    as one subprocess — same pattern as the existing `run_pipeline()` →
    `make_student_journey_map.py` — rather than re-implementing the three-step pipeline inline.
    The orchestrator still generates the fold card as part of that run (cheap, already happening),
    but `results` never picks it up, so it's never surfaced in the UI or the ZIP — fold card stays
    deliberately excluded per the user's explicit "leave the card fold out of this."
  - New `build_ltrs_zip()` bundles the two-side PDF, two-side HTML, and single-page HTML.
  - Button label (`"Generate Schedule"` vs `"Generate PDF and PNGs"`) and the downloads section
    both branch on `is_ltrs`, cached at generation time as `st.session_state["last_is_ltrs"]`
    (same reasoning as the pre-existing `last_input_name` caching — a download button click
    triggers a rerun, and the uploader could have changed by then, so branch on what was actually
    generated, not on the current uploader state).
- **Verified thoroughly, not just by reading the code:**
  - `ast.parse` syntax check on `app.py`.
  - Full Playwright end-to-end run: uploaded the real `input/LTRS2026 schedule.xlsx`, confirmed
    the sidebar caption, button label, and all four expected download buttons, downloaded the ZIP
    and confirmed its exact contents (`LTRS2026 schedule_a4_two_side.pdf`,
    `LTRS2026 schedule_a4_two_side.html`, `LTRS2026 schedule_single_page.html` — no fold card).
  - True portability check: extracted the downloaded ZIP into an isolated folder with no
    `assets/` directory anywhere nearby, opened the HTML directly, and confirmed via
    `img.naturalWidth === 161` (not `0`) and `img.src.startsWith('data:') === true` that the logo
    genuinely rendered from its embedded data URI rather than a broken relative link.
- Output file size grew by roughly 250-300KB per HTML output (three embedded fonts plus one logo
  image) — judged an acceptable tradeoff for zero external dependencies, not worth optimizing
  further.

## Session Log (2026-08-06 night — fold-card rebuild)
Third session of the same day, tackling the fold card rebuild that had been explicitly deferred
twice already (see the two session logs below). All changes in `render_ltrs2026_booklet.py`.

- **Fixed the Parallel Presentation Sessions panel regression** flagged in the 2026-08-05 evening
  session. Gave fold-card its own dedicated `render_track_stack()` renderer instead of sharing
  `render_track_grid()` with the two-pager — deliberately *not* reusing that function, since
  sharing it is exactly what caused the original regression (a two-pager markup change silently
  broke fold-card's stale CSS). fold-card's panels are too narrow for three side-by-side columns
  the way the two-pager does it (long talk titles would wrap into a very tall, narrow column), so
  tracks stack one under another instead — each track its own bordered block (title + room on one
  line, chair below with a divider, talks in a simple list) — matching the *original* pre-refactor
  fold-card design intent, just rebuilt on top of the new data flow. Threaded a `compact: bool`
  flag through `render_event_cell()`/`render_schedule_rows()` (default `False`, zero behaviour
  change for single-page/two-side) so fold-card's own call site can opt into
  `render_track_stack()` instead of `render_track_grid()`.

- **Found and fixed a real bug in `split_rows_balanced()`** while investigating why Q4 (the back
  cover) rendered completely empty. The function uses a fixed global `target = total_weight /
  parts` to decide where to split, but once a heavy block (Parallel Presentation Sessions, weight
  5) pushes a group over that target early, the *remaining* rows no longer contain enough total
  weight to trigger another split under the same fixed target before the row loop runs out — so
  the function silently produces fewer real groups than requested and pads the rest with `[]`.
  Fixed by recomputing `target` from *remaining* weight ÷ *remaining* groups at each step (a
  standard adaptive-target balancing fix) — confirmed by hand-tracing the exact 13-row dataset
  before touching the code, then verifying the regenerated output matched the trace precisely.

- **User pushback that mattered: "you're just shrinking the content."** First pass at "fix the
  panel" kept the original 8-9px font sizes — technically correct now, but genuinely too small to
  read comfortably (roughly 2-2.5mm cap height). User's reframing: the fold card uses the same
  total paper as the two-pager (2 sheets of A4, just landscape and quartered instead of portrait
  and halved), so content should redistribute to fit that space at a readable size, not shrink to
  fit wherever the split happened to land. This was the right diagnosis and reframed the actual
  task from "fix the CSS" to "fix the pagination."

- **Bumped fold-card's detail text to genuinely readable sizes** (13px times/thead, 15px event
  titles — Magnole, left untouched per user's explicit ask — 12px talk/track text, up from
  8-9px), deliberately as a diagnostic step first ("show me how bad the overflow looks") before
  building anything to fix it, rather than assuming.

- **Discovered `.panel` had no enforced height at all** — `overflow: hidden` was set, but with no
  explicit `height`, there was nothing for it to clip against; the panel (and the whole `.sheet`
  grid row) just silently grows to fit content. The old weight-based split happened to keep
  content small enough that this never became visible. Computed the real physical budget:
  `FOLD_CARD_PANEL_BUDGET_PX = round((194 - 16) * 96 / 25.4)` ≈ 673px (sheet min-height minus its
  own padding, converted to CSS px) — this is the number every subsequent fit check is measured
  against.

- **Caught my own measurement bug via user question, not luck.** First overflow readings (via
  `panel.scrollHeight`) showed Q1 and Q3 exactly matching their overloaded sibling's height
  pixel-for-pixel — which should have been an immediate red flag but initially wasn't caught.
  When the user asked "is this doable?", re-checking the numbers before answering surfaced why:
  `.panel` is a CSS Grid item, and grid items default to `align-items: stretch`, so the shorter
  panel in each row was being measured *after* being stretched to match its taller sibling, not
  at its own true content height. Re-measured with `align-items: start` forced via an injected
  style tag to get real numbers — corrected picture was Q1=536px/Q3=267px (both with huge slack),
  Q2=1129px (456px over budget), versus the initial wrongly-uniform reading. Worth remembering:
  don't trust a "coincidentally identical" measurement between two elements that shouldn't be
  identical — that's usually a sign the measurement itself is wrong, not the content.

- **Built `split_rows_by_fit()`**: a real measure-and-pack splitter, replacing the weight-based
  guess for fold-card specifically (`split_rows_balanced()` is kept as-is and still used as its
  own fallback/degenerate-input case, and is untouched for its original purpose). Extracted the
  fold-card CSS block out of `render_fold_card_a4_html()`'s inline f-string into its own
  `fold_card_css()` function specifically so the *measurement* pass and the *real* render use
  byte-identical styles — measuring against different CSS than what actually ships would make the
  whole exercise pointless. The splitter launches one headless Chromium instance (via Playwright,
  already a project dependency through `export_pdf.py`) and, for each of the first `parts - 1`
  panels, greedily adds rows one at a time — rendering and checking `scrollHeight` via
  `page.set_content()` reuse (not a fresh browser per candidate, for speed) — stopping as soon as
  the next row would exceed `FOLD_CARD_PANEL_BUDGET_PX`, with a guard reserving at least one row
  per remaining panel so an early panel can't greedily consume everything. The last panel always
  gets whatever remains (no split point needed for it). Runtime cost: ~30-40 render/measure calls
  for this 13-row schedule, well under a second in practice — the whole pipeline run stayed under
  4 seconds end to end.
  - Result, verified with the same unstretched-measurement technique: Q4=304px, Q1=570px,
    Q2=513px, Q3=675px (2px over budget — ~0.5mm, print-invisible, not worth chasing further)
    — down from the pre-fix reading of Q2 alone at 1129px (456px/68% over). All four panels now
    carry genuinely readable, sensibly distributed content.
  - User's own framing of the fix, worth keeping for next time this needs revisiting: "same
    paper, rearranged" — the two-pager and fold-card use the same total physical paper (2 A4
    sheets), so pagination should be solved as a real physical-fit problem, not an abstract
    weight heuristic, whenever there's a hard page-size constraint like this one.

- **Explicitly parked for a future session** (user's own words: "there are tweaks to do, but
  let's park that for now") — not itemized in detail, just noted that this is a working, solid
  state, not a finished/polished one. Don't assume fold-card needs nothing further.

## Session Log (2026-08-06 follow-up — border-width bug, pipeline reporting bug, full color centralization)
Same evening, continued from the branding/border-color session below. All changes in
`render_ltrs2026_booklet.py` (single-page/two-side scope only, fold-card untouched) plus one
fix in `make_ltrs2026_schedule.py`.

- **Fixed a genuine double-width border bug**, found by actually measuring rendered pixels
  rather than trusting the CSS. User zoomed into two spots (top of page 1's table, top of
  page 2's table) and asked "can you see it?" — verified empirically via Playwright pixel
  sampling (not guesswork): every border in the schedule table renders at 4 device-px except
  two specific seams, which rendered at a genuine 8 device-px (exactly double), confirming the
  visual perception was correct, not an illusion.
  - **Page 1 seam** (header row → first data row): the `<thead>` cell's own border and the
    first `<tbody>` row's own border weren't collapsing cleanly — a known `border-collapse`
    quirk specifically at `thead`/`tbody` boundaries (works fine for row-to-row collapses
    *within* the same section). Fixed by setting `border-bottom: 0` on
    `.schedule-table thead th`, leaving the first body row's own top border as the sole line.
  - **Page 2 seam** (very top of the table): two-side hides its `<thead>` entirely
    (`display: none`), so the exposed seam there was the `<table>` element's own `border`
    property colliding with the first visible row's border — a different pairing than page 1's
    case, same root mechanism (two competing border declarations not merging). Fixed by
    removing `.schedule-table`'s own `border` declaration outright — every outer cell already
    has a full border on all four sides, so the table's own border was pure redundancy that
    happened to double up at exactly this one edge.
  - Verification method worth remembering for next time: `getBoundingClientRect()` comparisons
    were misleading here (found a spurious 0.5px "gap" that had nothing to do with the actual
    bug and persisted even after removing the table border) — actually sampling rendered pixel
    colors down a vertical strip (`Image.open(screenshot).getpixel(...)`) was what nailed the
    exact width and location. Re-tested by genuinely locking the PDF file open
    (`msvcrt.locking`) and confirming the real `PermissionError` — don't trust a passing test
    that didn't actually reproduce the failure condition (a first attempt using plain
    `open(path, "r+b")` did *not* trigger Windows file locking and gave a false pass).

- **Fixed `make_ltrs2026_schedule.py`'s misleading success report**, prompted by user noticing
  the two-side PDF hadn't actually regenerated (stale file timestamp) despite the pipeline's
  final summary claiming `[OK]`. Root cause: the final summary's `print(f"[OK] A4 two side
  PDF: ...")` line was unconditional — it printed regardless of whether the `export_pdf.py`
  subprocess actually succeeded, even though an inline `[WARN]` was correctly printed earlier
  when it failed (that warning was just easy to miss among the rest of the output, and the
  script's exit code stayed `0` either way). Added a `pdf_ok` flag driven by the same
  `run(pdf_cmd) != 0` check already in place; the summary now prints `[FAIL] ...` when export
  failed, and `main()` returns `1` instead of always `0`. Also removed an unused
  `single_page_pdf` variable found while reading through the file (single-page PDF export is
  intentionally disabled — see the pipeline overview above — so this was dead code, not a
  planned-but-unwired feature). User explicitly said not to worry about the underlying source
  `.xlsx` changing content between runs mid-session — that's the intended workflow, not
  something to flag as unexpected.

- **Full color centralization**, prompted by "is our beige stored in one place too?" after the
  brand-green fix earlier the same evening. Audited every hardcoded hex color in the
  single-page/two-side scope (previously: `#999994` border grey × 29, `#f8f5ec` × 2, `#d8cbf1`
  × 2, `#fff` × 3, `#d9d9d9` × 1, plus `--row-break: #edf6ef` already living directly in `:root`
  with no matching Python constant) and gave every one of them a single source of truth:
  - `#f8f5ec` was a near-duplicate of `CREAM` (only 1–4 points off per RGB channel — the kind
    of accidental drift that's invisible until you go looking) → now `var(--cream)`.
  - `#d8cbf1` was an *exact* duplicate of `LILAC`, just never wired to the variable → now
    `var(--lilac)`.
  - Added proper named constants for values that were fine as colors but still "stray" in the
    sense of having no single source: `WHITE`, `BORDER_GREY` (the uniform grey from the earlier
    border-color session), `SCREEN_PREVIEW_BACKDROP` (the browser-only page-boundary grey,
    never printed), and `ROW_BREAK` (previously a bare hex directly in the `--row-break`
    `:root` line). All four now follow the same `CONSTANT = "#hex"` → `:root { --x: {CONSTANT}
    }` → `var(--x)` pattern as the original six palette colors.
  - Implementation was a line-range-scoped `sed` (function boundaries re-checked fresh
    immediately before running it, since line numbers shift after every edit) rather than
    `replace_all`, same reasoning as the earlier border-color pass: several of these exact hex
    values also appear in fold-card's own independent copy and must not be touched there.
  - Verified with a fresh PDF render and a direct visual comparison against the prior render —
    intentionally identical in appearance, since this was a pure "same colors, now properly
    sourced" refactor, not a design change.

## Session Log (2026-08-06 — branding footer, brand green fix, uniform borders)
Follow-up to the previous evening's two-pager polish session, same scope discipline: everything
below touches `render_ltrs2026_booklet.py` only, and only the single-page/two-side code paths —
fold-card's separate CSS block was deliberately left alone again, still pending its own rebuild
(see the "Known issue" note above the LTRS scripts list).

- **Page-footer branding added to both single-page and two-side.** User provided two brand
  lockup variants — `assets/cp_bt.png` (black text) and `assets/cp_gt.png` (green text), both
  the full "REGENT'S UNIVERSITY LONDON / CULTIVATING POSSIBILITY" wordmark, distinct from the
  small rosette-only `r_logo.png` already used in the page header. User asked to literally try
  one, look at it, then try the other, rather than have both rendered side-by-side for
  comparison — so the whole exercise was done via a single `PAGE_FOOTER_LOGO` module-level
  constant (grouped with the palette constants near the top of the file) that gets toggled and
  the pipeline rerun each time, not a one-off comparison harness.
  - Two-side page 2 previously ended with dead blank space below the table; `.a4-page` was
    changed to `display: flex; flex-direction: column` so a `<footer class="page-footer">`
    (holding just the logo `<img>`) can use `margin-top: auto` to sit flush at the page bottom.
    First pass looked too small and too close to the very bottom edge — user wanted it bigger
    and more centered in the blank space, not pinned to the edge. Fixed by widening the image
    (150px → 260px) and adding `margin-bottom: auto` alongside the existing `margin-top: auto`,
    which centers the footer in whatever space is left after the header+table rather than
    pushing it to the bottom — a pure CSS flex trick, no JS/measurement needed.
  - Single-page had its own separate, older footer — plain text "Cultivating Possibility" /
    "Regent's University London" in Magnole serif (`.footer-line`/`.footer-sub` classes, no
    image). User asked to replace that with the same logo treatment for consistency. Single-page
    isn't a fixed-height flex page like two-side (`.single-page` is a plain block container that
    just grows with content), so its footer doesn't need the flex-centering trick — it simply
    sits in normal document flow right after the table, sized slightly smaller (200px) since
    there's no blank space to visually balance against. `.footer-line`/`.footer-sub` CSS and
    both call sites were removed outright (confirmed via grep they had no other callers), not
    left as dead code.

- **Fixed a real hardcoded-color bug: `#216d5c` vs the actual brand green `#195C4D`.** User
  zoomed into the table header and asked "what's our official brand green" — turned out the
  schedule table's header row background and the Time column background were using a
  *different*, separately hardcoded green (`#216d5c`) that had never been tied to the `GREEN`
  constant / `var(--green)` used everywhere else (the schedule-header banner, track headers,
  etc.). Replaced all 8 occurrences — across single-page, two-side, *and* fold-card, since this
  one was a correctness fix worth making everywhere regardless of fold-card's pending rebuild,
  not a design choice specific to the two-pager — with `var(--green)`, so there's now exactly
  one place (`GREEN = "#195C4D"` at the top of the file) that defines the brand green.

- **Unified all border colors/weights to one solid, understated grey.** User zoomed into the
  table and asked to review line colors/weighting/alpha "throughout" — the grid lines looked
  inconsistent (near-black over cream rows, nearly invisible over the dark green header/Time
  column). Investigated properly before touching anything: pulled live computed styles via
  Playwright and confirmed every border declaration was already textually identical
  (`rgba(23, 31, 32, 0.42)`, 1px) — so it wasn't a CSS mismatch, it was the nature of a
  *semi-transparent* border compositing differently depending on what's behind it. Also surveyed
  the full alpha hierarchy in use (0.42 main grid, 0.52 track-header divider, 0.22 track-cell
  box, 0.16 talk-to-talk divider) and flagged that 0.52 was technically *stronger* than the
  0.42 main grid — a sub-component's internal line outweighing the page's own top-level
  structure, inherited from the original pre-refactor design, not something introduced this
  week. User's call: uniform and understated, i.e. collapse all four tiers into one solid color.
  Computed what `rgba(23, 31, 32, 0.42)` already looks like composited over the cream background
  (`(23×0.42 + 247×0.58, 31×0.42 + 241×0.58, 32×0.42 + 232×0.58)` ≈ `#999994`) and used that
  exact value as a single opaque replacement everywhere in single-page/two-side (26 occurrences,
  via a line-range-scoped `sed` rather than `replace_all`, specifically to avoid touching
  fold-card's own separate border declarations, several of which happen to share the same 0.42
  value by coincidence). Picking the "already how it looks over cream" value meant the light
  rows are visually unchanged; only the dark-green areas' lines became visible/consistent rather
  than nearly disappearing.

- **More breathing room between the green header banner and the table.** User's own aesthetic
  call (asked for an opinion first, then asked for the change): `.schedule-header`'s
  `margin-bottom` went from 8px to 20px in single-page and two-side, so the banner and the
  table's own (same-colored) header row read as two distinct elements instead of one merged
  green block. Confirmed the two-side page 2 footer (see above, centered via `margin-top: auto`
  / `margin-bottom: auto`) re-centered itself correctly in the now-slightly-smaller remaining
  space with no extra work — that's the point of using auto-margins for centering instead of a
  fixed offset.

- **Squared off the header banner's corners**, user's own suggestion after speculating about two
  options (round the table's corners to match the banner, vs. square the banner to match the
  table) and asking for a recommendation. Recommended squaring — cheaper, zero risk to the
  border-collapse mechanics the uniform-border fix above depends on, and rounding a real
  `<table>` with collapsed borders is a known CSS pain point (needs `border-collapse: separate`
  plus per-corner-cell radii, which would also risk reintroducing the border inconsistency just
  fixed). Implemented as a `SCHEDULE_HEADER_RADIUS = "0"` toggle constant (comment notes the
  original was `"6px"`) rather than deleting the rounded-corner value outright, per user's
  explicit ask to keep it easily reversible — same pattern as `PAGE_FOOTER_LOGO`.

## Session Log (2026-08-05 evening — two-pager polish + fold-card regression)
User had exhausted their GitHub Copilot credits for the day and switched to Claude Code
mid-project — the LTRS pipeline itself (see the session log below) was built entirely by a
Copilot session earlier the same day; this session's starting point was "familiarize yourself
with what Copilot built," not a from-scratch build. All changes below are in
`render_ltrs2026_booklet.py` only — the other three LTRS scripts were untouched.

- **Two-side page 2 header now matches page 1 exactly.** It previously showed a smaller
  "LTRS 2026 / Programme Continued / {date}" banner (smaller `h1`, tighter padding, via
  `.a4-page.continuation .schedule-header`/`.schedule-header h1` overrides). User wanted it
  visually identical to page 1's full banner (title + Magnole theme line + conference line +
  date) — removed those two continuation-specific overrides and copied page 1's exact header
  markup onto page 2. The `.a4-page.continuation .schedule-table thead { display: none; }`
  rule was deliberately left alone (that's about not repeating the Time/Event/Location column
  headers on page 2's table, a separate and still-reasonable choice from the banner question).

- **Parallel Presentation Sessions: talks now align row-by-row across all three tracks, not
  just as an overall equal-height box.** User's ask was specific: "Elif Toker has the tallest
  cell [...] can we pad out Chris and Fatimah so the bottom of the cells matches Elif's" — i.e.
  talk *N* of every track should be the same height as talk *N* of every other track, not just
  the tracks' overall bottoms lining up. This needed a real restructure, not a CSS tweak:
  - Removed `render_track_card()` (rendered each track as an independent
    `<section class="track-card"><ul class="talk-list">...</ul></section>`, no relationship
    between one track's Nth talk and another's).
  - Added `render_talk_cell()` + `render_track_grid()`: computes `max_talks` across all tracks
    in the block, then builds one `<div class="track-row">` per talk-index, pulling that
    index's talk from each track (or an empty matching-styled cell if a shorter track has run
    out) — plus one header row for title/room/chair. `display: table-row` on `.track-row` /
    `display: table-cell` on `.track-cell` gets a genuine per-row equal-height guarantee
    (the same mechanism plain HTML tables have always had) — far more reliable than relying on
    CSS Grid's implicit `align-items: normal` (which computes to `stretch`, and did measure as
    already-equal in a quick Playwright/Chromium check *before* this rewrite, but the user's
    own browser view kept showing genuinely uneven heights regardless — never fully root-caused
    which engine/context was diverging, so the row-table structure was built specifically to be
    the most cross-engine-robust option rather than trusting Grid stretch further).
  - This also incidentally fixed the earlier "make the whole box equal height" ask from the
    same evening (previously done with `display: table`/`table-cell` on `.track-grid` itself
    directly wrapping each `<section class="track-card">` as a whole-track cell) — that
    intermediate version is fully superseded by the row-based one, not layered on top of it.

- **Track headers (e.g. "Compassion and Support / Darwin - D208 / Chaired by: TBC") given a
  dark green band with cream text**, on user's observation that header text and talk text were
  the same visual weight and blended together. Reused the existing green/cream pairing already
  established elsewhere (banner, Time column) rather than introducing a new colour — scoped via
  `.row-parallel_sessions .track-row-header .track-cell` (higher specificity than the general
  `.row-parallel_sessions .track-cell` lilac rule, so it reliably overrides regardless of
  source order).

- **Divider style consistency pass**, prompted by user noticing dotted talk-separator lines
  next to solid structural borders ("someone could argue..."). Two rounds:
  1. Changed all dotted `border-top` separators (both the new track-grid talk rows *and* the
     pre-existing Plenary `.talk-list li` separators, which had been missed in the first pass —
     caught when user asked "did you do plenary?") to a thin solid line at low opacity
     (`rgba(23, 31, 32, 0.16)`), so only line *weight/opacity* varies, not style.
  2. User then flagged that the track-grid's talk separators bled edge-to-edge (touching the
     column borders) while Plenary's separators sit inset within their own padding — asked to
     make Plenary full-width to match (i.e. bring track-grid *up* to Plenary's boldness). Went
     the other way by mistake (made track-grid inset to match Plenary) — user actually preferred
     the accidental result, so kept it. Implementation: added a `.talk-body` inner wrapper div
     around each talk's content (`render_talk_cell()`), moved the separator border onto that
     wrapper instead of the outer `.talk-cell`, since a table-cell's own border always spans its
     full box edge-to-edge with no way to inset it directly — an inner element sitting inside
     the cell's own padding was the only way to get an inset line. The strong divider under each
     track's green header deliberately stays full-width/edge-to-edge (`.track-row-header
     .track-cell`'s own border) — that's a major structural boundary, not a repeating separator,
     mirroring how the *original* pre-refactor design already distinguished the two (the old
     `.track-chair` used a negative-margin trick specifically to bleed that one line full-width
     while leaving `.talk-list li` separators naturally inset).
  - Landed on a found design rule worth keeping for future additions: full-width/bold dividers
    mark *parallel* boundaries (concurrent tracks, concurrent workshops in different rooms);
    inset/light dividers mark *sequential* items within one place (talks one after another in
    the same track or the same Plenary session). Not designed in from the start, but held up
    when checked against every section, including ones not touched this session
    (Parallel Workshops' full-width row borders are the master schedule-table's own row
    boundaries, not a nested separator — genuinely a different structural level, not an
    inconsistency, despite looking like one at a glance).

- **Location column: header and cells now both left-aligned** (previously header inherited a
  blanket `text-align: left` from `.schedule-table thead th` while `.location-col` cells were
  explicitly centered — a real mismatch). Tried centering the header to match first; user then
  asked to try the opposite (left-align the cells to match the header) and preferred that one
  — "once an Excel guy, always an Excel guy."

- **End-of-session code review** (user's request, prompted by "when you tweak as much as we
  have, things can get messy and Frankensteiny"): found and confirmed via a live screenshot
  that the fold card's Parallel Presentation Sessions panel is now broken — see the "Known
  issue" note above the LTRS scripts list. Root cause: `render_fold_card_a4_html()` shares
  `render_schedule_rows()` → `render_event_cell()` → `render_track_grid()` with single-page and
  two-side, but fold-card keeps its own separate, compact CSS block (~line 1690s) that still
  targets the pre-refactor class names (`.track-card`, `.talk-list li`) — none of the new
  `.track-row`/`.track-cell`/`.track-header-cell`/`.talk-body` classes have any rule there.
  User already knew fold-card needed work and wants a fresh rebuild of that panel rather than a
  patch — explicitly deferred, not fixed this session. Two smaller/non-urgent findings from the
  same review, also not acted on: `build_onepager_rows()` sets a `"location": "See tracks"`
  value for workshop_block/presentation_session_block rows that's computed but never actually
  rendered anywhere (harmless dead data); and single-page/two-side/fold-card each hand-duplicate
  their own copy of the schedule-table/track-grid CSS with no shared source, which is exactly
  the gap that let the fold-card regression happen silently — worth extracting into a shared
  CSS-building function next time any of the shared `render_*` functions' markup changes.

- **Deferred to a future session (both explicitly "tomorrow," not tonight):**
  1. Fresh rebuild of the fold card's Parallel Presentation Sessions panel.
  2. Some kind of branding treatment for the bare space at the bottom of two-side page 2 —
     user hasn't specified what yet, just flagged the space looks empty.

## Session Log (2026-08-05 — LTRS schedule pipeline)
- Built the full LTRS 2026 conference schedule pipeline from scratch:
  - `parse_ltrs2026_v1.py`: parses Excel workbook → structured JSON + parse report.
  - `render_ltrs2026_booklet.py`: renders three branded HTML outputs from JSON.
  - `export_pdf.py`: Playwright headless Chromium HTML→PDF exporter.
  - `make_ltrs2026_schedule.py`: orchestrates all three steps end-to-end.
- Three HTML/PDF outputs:
  - **Single page** (`_single_page.html`): continuous branded schedule, HTML only (PDF deliberately disabled — HTML is the deliverable here).
  - **A4 two-side** (`_a4_two_side.html` + `.pdf`): true duplex front/back pages, schedule rows split by content weight. PDF export via Playwright with `print_background=True` and `@media screen and (max-width: 900px)` scoping to preserve 3-column layout in PDF.
  - **Fold card** (`_a4_fold_card.html`): landscape fold imposition — sheet 1 is Q4|Q1 (outer), sheet 2 is Q2|Q3 (inner), ready for duplex landscape print + fold.
- Visual design built on brand palette (cream, dark green, lilac, maroon) with Magnole serif and Avenir Next body fonts.
- Named CSS variables for session row colours (`--row-event`, `--row-break`, `--row-plenary`, `--row-workshop`, `--row-presentations`) — easy to tweak.
- Header block: logo + LTRS 2026 lockup, Magnole-styled theme line, conference line, date.
- `print-color-adjust: exact` and `@media print` background rules ensure colours survive PDF export.
- `render_schedule_rows()` extracted as shared helper used by all three outputs.
- `split_rows_balanced()` weights rows by content density for fair page splitting.
- Spacing pass applied: workshops, plenary, and presentation rows have more breathing room (padding, line-height, talk-list gaps).
- Key known note: if the PDF file is open in a viewer when the pipeline runs, it will fail with a permission error. Close the PDF first.

## Session Log (2026-07-22 follow-up 9)
- User asked whether ~40-word alt text (the LJM poster's) is "normal." Answered inline: WCAG's
  short-alt guidance targets simple images; complex images like this timeline poster are
  expected to use a short(er) alt text paired with a fuller text equivalent elsewhere, which is
  this app's existing design — no change needed for length itself.
- User asked to make the alt-text `st.code` blocks tighter, three rounds in a row (padding →
  padding+line-height → font-size+tighter caption-to-button margins) before it read as properly
  compact. See "Streamlit app" above for the final CSS.
- User asked to hide the review-text download for now (kept in code via `if False`, not
  deleted; still generated internally) and drop it from the ZIP, replacing it with a small
  `_alt_text.txt` bundling both suggested alt-text sentences. That broke the LJM alt text's own
  trailing reference to "the accompanying review text" — resolved via AskUserQuestion; user
  chose to drop that sentence rather than reword it or leave it dangling. See "Suggested alt
  text for the PNGs" and "Important PDF Logic" above.
- Verified via Playwright: review-text button no longer renders, the generated ZIP contains no
  `_review.txt` but does contain `_alt_text.txt` with both sentences correctly, and the LJM alt
  text no longer mentions the review text.

## Session Log (2026-07-22 follow-up 8)
- User asked for alt text on the PNGs for accessibility. Clarified via AskUserQuestion first
  since "alt text on a PNG" is ambiguous (no in-app image preview, and file metadata isn't
  read by Blackboard) — user confirmed they wanted copy-pasteable suggested text, not
  embedded file metadata. Added generated alt-text sentences to the JSON/review-text output
  and a copy-friendly `st.code` display next to each PNG's download button in the app. See
  "Suggested alt text for the PNGs" above.

## Session Log (2026-07-22 follow-up 7)
- User noticed that uploading a second/third `.docx` in the same session left the previous
  run's download buttons showing until they clicked Generate again. Fixed in `app.py` by
  tracking the upload widget's `file_id` and clearing `last_results`/`last_message` as soon
  as a different file is selected (or the file is removed) — see "Streamlit app" above.

## Session Log (2026-07-22 follow-up 6)
- User reported two confusing error messages from bad test uploads (no table; empty/corrupt
  file) and asked for friendlier wording. Found the corrupt-file case was an actual bug (see
  "Friendly extraction error messages" above) — python-docx skips its own file-type check
  when passed a `Path` instead of `str`, letting a raw `zipfile.BadZipFile` leak through
  instead of the library's own clearer exception. Fixed that plus added targeted
  try/except handling in the extractor for the known cases, and cleaned up app.py so it
  doesn't double the `[FAIL]` tag on display.

## Session Log (2026-07-22 follow-up 5)
- User mentioned the app is now live and public on Streamlit Community Cloud, and shared a
  separate conversation where a different Claude session had reassured them about the risk
  (no data storage, "briefly in memory" at most). Fact-checked that against the actual code
  and found it was imprecise/incomplete — see "Public deployment hardening" above for the two
  real fixes made as a result (stale temp-dir cleanup, upload filename sanitization).

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
