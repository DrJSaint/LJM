# LJM Renderer

Generate a student-facing learner journey map from a Word `.docx` file.

## Repo Layout

- `input/`: source Word documents
- `output/`: generated review text, JSON, PNG, and optional PDF
- `python scripts/`: extraction, rendering, and pipeline scripts
- `config/`: Easter Sunday lookup table used for automatic term-break insertion (see below)

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

The wrapper script's default `--input` path is:

```text
input/DSC502_Learner_Journey_Map.docx
```

`input/` is gitignored (it may contain real course content), so this file won't exist in a fresh
clone — place your own `.docx` there, or pass `--input` explicitly:

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

## Term Dates and the Easter Break

`--week1` and `--expected-weeks` define the term as a plain sequence of Monday–Friday
teaching weeks. If that date range overlaps Easter (22 Mar–25 Apr in the relevant year),
a 2-week Easter break is inserted automatically — the Mon–Fri weeks immediately either
side of Easter weekend — and every week after it shifts forward by 14 days. Teaching week
numbering is untouched; the break renders as one extra timeline node with a bunny icon.

Easter Sunday dates are looked up from `config/easter_sunday_dates_2027_2036.csv`. If a
term's date range reaches a year that's missing from that file, extraction fails with a
clear error rather than silently skipping the break — add the missing year's Easter Sunday
date to the CSV to resolve it. The lookup file location can be overridden:

```powershell
py ".\python scripts\extract_student_journey_map_v2.py" --input ".\input\your_file.docx" --review ".\output\review.txt" --json ".\output\data.json" --easter-config ".\config\easter_sunday_dates_2027_2036.csv"
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

Render Module Learning Outcomes PNG from extracted JSON (3240px wide, dynamic height):

```powershell
py ".\python scripts\render_module_learning_outcomes_png.py" --input ".\output\student_journey_map_data.json" --output ".\output\student_journey_map_mlos.png"
```

## Streamlit Demo

Run the web demo locally:

```powershell
streamlit run .\app.py
```

The demo uploads a Word document, runs the existing pipeline, and always generates all assets together: a combined PDF (MLO page first, then LJM), both PNGs, and the review text. Downloads are offered individually in that order, plus a "Download all as ZIP" button. Uploading a different file (or removing the current one) clears any previous run's download buttons.

Each PNG's download button is followed by a suggested alt-text sentence (with a one-click copy icon) — paste it into Blackboard's own alt-text field when you embed the image there, since that's the only place alt text actually reaches a screen reader. The same text is also written into the review `.txt`. It's a short summary rather than a full transcript by design — the review `.txt` itself is the accompanying full-text equivalent for anyone using assistive technology.

The sidebar has two sections: **Term Start Picker** (the Week 1 Monday date and a strict 10/12/Custom teaching-week-count control — see "Term Dates and the Easter Break" above) and **LJM height options** (the layout-mode radio). It is intended as a lightweight demo build; if the content is sensitive, use a private deployment instead of a public Streamlit Cloud app.

## Git Notes

Generated files under `output/` are ignored by Git. The folder stays in the repo via `output/.gitkeep`.
