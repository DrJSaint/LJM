# Claude Handoff (LJM_Renderer)

## Project Purpose
This repo generates learner journey artifacts from a Word `.docx`:
- LJM poster (PNG)
- MLO card (PNG, transparent header band)
- Optional combined PDF assembled from generated PNG pages in the Streamlit app

## Current Priority State
The app UI was intentionally reverted back to a mostly plain Streamlit layout after a branding experiment.
The user preferred minimal UI customization.

## What Is Implemented

### 1) Core CLI pipeline (existing scripts)
- Extract: `python scripts/extract_student_journey_map_v2.py`
- LJM render: `python scripts/render_student_journey_map_png.py`
- MLO render: `python scripts/render_module_learning_outcomes_png.py`
- Wrapper: `python scripts/make_student_journey_map.py`

### 2) MLO renderer behavior
In `python scripts/render_module_learning_outcomes_png.py`:
- Dynamic height by outcome count/content (no forced clipping)
- Fixed width (1080)
- Header row transparent in PNG (`RGBA`)
- Header text in dark palette color
- Defaults currently tuned to:
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

### 4) Streamlit app
In `app.py`:
- Upload one `.docx`
- Render target: `ljm | mlo | both`
- Layout mode: `flex-height | standard | fit-fixed`
- Download type: `png | pdf`
- Hidden (kept in code via `if False` blocks, not deleted):
  - Advanced MLO controls
  - Pipeline log expander
  - JSON download button
  - Reset workspace button

## Important PDF Logic (recent fixes)
In `app.py`:
- Combined PDF is assembled from generated PNGs (`build_multipage_pdf`)
- Transparency handling fix: alpha images are composited onto cream background `(247, 241, 232)` before RGB conversion to avoid black transparent areas in PDF
- Page order currently set to:
  1. MLO first
  2. LJM second
  (when both exist)

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

## Git State At Last Check
- Modified: `README.md`
- Modified: `requirements.txt`
- Untracked: `app.py`
- Untracked input doc example: `input/Blurb for Claude.docx`

## Commit / Tag Context
- `77c8cc6` on `main` (also tagged `mlo-final-tuning`)
- Streamlit work in `app.py` is currently local/uncommitted.

## Suggested Next Step For Claude
1. Confirm app behavior in UI for both download modes.
2. Commit pending app/repo changes when user confirms final state.
3. Keep UI minimal unless user asks for targeted styling only.
