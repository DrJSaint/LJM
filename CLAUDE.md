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
