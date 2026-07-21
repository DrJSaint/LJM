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
- No more download-type choice — every run always generates the PDF, both PNGs (whichever the
  render target implies), and the review text together.
- Downloads are shown in this fixed order: **Download all as ZIP** (primary button, bundles
  whichever of the four exist), then PDF, then MLO PNG, then LJM PNG, then review text.
- Hidden (kept in code via `if False` blocks, not deleted):
  - Advanced MLO controls
  - Pipeline log expander
  - JSON download button
  - Reset workspace button

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

## Suggested Next Step For Claude
1. Nothing outstanding from this session — all changes below are committed. Confirm with the user
   before starting new work.
2. If asked about vector output: this was discussed and explicitly deferred — don't start it
   unprompted.
3. Keep UI minimal unless user asks for targeted styling only.

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
