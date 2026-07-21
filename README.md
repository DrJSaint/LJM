# LJM Renderer

Generate a student-facing learner journey map from a Word `.docx` file.

## Repo Layout

- `input/`: source Word documents
- `output/`: generated review text, JSON, PNG, and optional PDF
- `python scripts/`: extraction, rendering, and pipeline scripts

## Requirements

- Python 3.10+
- `python-docx`
- `Pillow`

Install dependencies:

```powershell
py -m pip install -r requirements.txt
```

If `python` is already on your PATH, `python -m pip install -r requirements.txt` also works.

## Quick Start

From the repo root:

```powershell
Set-Location "c:\Projects\LJM_Renderer"
py ".\python scripts\make_student_journey_map.py"
```

This runs the full pipeline:

1. Extracts and validates week data from the input `.docx`
2. Writes review text and JSON into `output/`
3. Renders a PNG poster
4. Optionally writes a PDF wrapper

## Default Input

The wrapper script expects this file by default:

```text
input/DSC502_Learner_Journey_Map.docx
```

If you want to use a different file:

```powershell
py ".\python scripts\make_student_journey_map.py" --input ".\input\your_file.docx"
```

## Common Commands

Run the full pipeline without PDF:

```powershell
py ".\python scripts\make_student_journey_map.py" --no-pdf
```

Run in strict mode so rendering stops on validation warnings:

```powershell
py ".\python scripts\make_student_journey_map.py" --strict
```

Choose a layout mode:

```powershell
py ".\python scripts\make_student_journey_map.py" --layout-mode flex-height
```

Choose what to render:

```powershell
py ".\python scripts\make_student_journey_map.py" --render-target both
```

Tune MLO text sizing from the wrapper command:

```powershell
py ".\python scripts\make_student_journey_map.py" --render-target mlo --mlo-header-size 40 --mlo-code-size 42 --mlo-title-size 31 --mlo-desc-size 31 --mlo-line-spacing 8
```

Add more space between header lines:

```powershell
py ".\python scripts\make_student_journey_map.py" --render-target mlo --mlo-header-line-gap 12
```

Current best-known MLO typography preset:

```powershell
py ".\python scripts\make_student_journey_map.py" --render-target mlo --mlo-header-size 52 --mlo-code-size 52 --mlo-title-size 37 --mlo-desc-size 37 --mlo-line-spacing 8 --mlo-header-line-gap 0
```

Render targets:

1. `ljm`: learner journey map poster only
2. `mlo`: module learning outcomes square only
3. `both`: render both assets from the same extracted JSON

Available layout modes:

1. `flex-height`: default mode; preserves typography and expands poster height when content is dense
2. `standard`: keeps the current poster geometry without adaptive text fitting
3. `fit-fixed`: keeps the fixed poster canvas and selectively reduces detail or pill text when dense content would crowd the layout

Change the expected teaching week count:

```powershell
py ".\python scripts\make_student_journey_map.py" --expected-weeks 12
```

Change the Week 1 Monday date:

```powershell
py ".\python scripts\make_student_journey_map.py" --week1 2026-09-21
```

## Direct Scripts

Extract review text and JSON only:

```powershell
py ".\python scripts\extract_student_journey_map_v2.py" --input ".\input\DSC502_Learner_Journey_Map.docx" --review ".\output\student_journey_map_review.txt" --json ".\output\student_journey_map_data.json"
```

Render PNG and PDF from extracted JSON:

```powershell
py ".\python scripts\render_student_journey_map_png.py" --input ".\output\student_journey_map_data.json" --output ".\output\student_journey_map.png" --pdf ".\output\student_journey_map.pdf" --layout-mode flex-height
```

Render 1080x1080 Module Learning Outcomes PNG from extracted JSON:

```powershell
py ".\python scripts\render_module_learning_outcomes_png.py" --input ".\output\student_journey_map_data.json" --output ".\output\student_journey_map_mlos.png"
```

## Git Notes

Generated files under `output/` are ignored by Git. The folder stays in the repo via `output/.gitkeep`.
