# LJM Renderer

Two pipelines live in this repo:

1. **LJM / MLO pipeline** — generate a student-facing learner journey map and module learning outcomes card from a Word `.docx` file.
2. **LTRS schedule pipeline** — generate branded conference schedule outputs (HTML + PDF) from an Excel workbook.

---

## LTRS Schedule Pipeline

### Quick start

```powershell
.\.venv\Scripts\python.exe "python scripts/make_ltrs2026_schedule.py"
```

Input: `input/LTRS2026 schedule.xlsx`, sheet `LTRS2026 (v1)`

Outputs written to `output/`:

| File | Description |
|------|-------------|
| `ltrs2026_single_page.html` | One-page continuous branded schedule |
| `ltrs2026_a4_two_side.html` + `.pdf` | Two-sided A4 duplex (front/back) |
| `ltrs2026_a4_fold_card.html` | Landscape fold card (Q4\|Q1 outer, Q2\|Q3 inner) |
| `ltrs2026_parsed.json` | Structured schedule data |
| `ltrs2026_parse_report.txt` | Human-readable parse summary |

The fold card's four quarters are split by actually rendering and measuring each candidate panel against the physical page size (`split_rows_by_fit()` in `render_ltrs2026_booklet.py`), not an abstract content-weight guess — so generating it takes a few seconds longer than the other two outputs while it launches headless Chromium to check the fit. See CLAUDE.md's "fold-card rebuild" session log for detail. Some further tweaks are expected in a future session; treat it as working, not finished.

### Quick style toggles

Near the top of `render_ltrs2026_booklet.py`, alongside the brand palette constants:

- `PAGE_FOOTER_LOGO` — which brand lockup (`assets/cp_gt.png` green text or `assets/cp_bt.png` black text) appears in the page footer on single-page and two-side.
- `SCHEDULE_HEADER_RADIUS` — `"0"` for the current square-cornered banner, or `"6px"` to restore the original rounded corners.

Change the value and rerun the pipeline; no other edits needed.

### Colors

Every color used in single-page and two-side is a single named constant at the top of
`render_ltrs2026_booklet.py` (`CREAM`, `DARK`, `GREEN`, `BLUE`, `LILAC`, `MAROON`, `WHITE`,
`BORDER_GREY`, `SCREEN_PREVIEW_BACKDROP`, `ROW_BREAK`) — nothing is hardcoded elsewhere in
those two outputs. Change a constant, rerun the pipeline, and it updates everywhere that color
is used. Fold-card keeps its own separate, independent set of color values for now.

### PDF printing tips

- Enable **Background graphics** in the print dialog (or use the pipeline's built-in Playwright export).
- Two-side PDF: duplex, flip on long edge.
- Fold card: duplex, landscape, flip on short edge; fold vertically down the centre.

### Scripts

| Script | Purpose |
|--------|---------|
| `parse_ltrs2026_v1.py` | Parse Excel workbook → JSON |
| `render_ltrs2026_booklet.py` | Render HTML outputs from JSON |
| `export_pdf.py` | Playwright HTML→PDF exporter |
| `make_ltrs2026_schedule.py` | Orchestrate full pipeline |

---

## LJM / MLO Pipeline

### Repo Layout

- `input/`: source Word documents
- `output/`: generated review text, JSON, PNG, and optional PDF
- `python scripts/`: extraction, rendering, and pipeline scripts
- `config/`: Easter Sunday lookup table used for automatic term-break insertion (see below)

## Requirements

- Python 3.10+
- `python-docx`, `Pillow` (LJM/MLO pipeline)
- `pandas`, `openpyxl`, `playwright` (LTRS pipeline)

Install dependencies:

```powershell
py -m pip install -r requirements.txt
```

If `python` is already on your PATH, `python -m pip install -r requirements.txt` also works.

The LTRS pipeline also needs Playwright's Chromium browser binary (separate from the pip
package):

```powershell
py -m playwright install chromium
```

On Streamlit Community Cloud this is handled automatically — `packages.txt` supplies the apt-level
system libraries Chromium needs, and `app.py` runs the Chromium install itself once per session
before the first LTRS upload (`ensure_playwright_browsers()`).

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
.\.venv\Scripts\python.exe -m streamlit run .\app.py
```

The demo has a single upload widget that accepts either a `.docx` (LJM/MLO pipeline) or an
`.xlsx` (LTRS schedule pipeline) and routes to the right pipeline based on the file extension —
no separate mode switch to pick.

**LJM/MLO mode** (`.docx` upload): runs the existing pipeline and always generates all assets
together: a combined PDF (MLO page first, then LJM), both PNGs, and the review text. The review
text is still generated and written to disk, but its download button is currently hidden (kept in
the code, not deleted — re-enable it in `app.py` if you want it back). Downloads are offered
individually — ZIP, PDF, MLO PNG, LJM PNG — plus a "Download all as ZIP" primary button.

**LTRS mode** (`.xlsx` upload): runs the LTRS orchestrator (`make_ltrs2026_schedule.py`) and
offers the two-side PDF, two-side HTML, and single-page HTML individually plus a "Download all as
ZIP" button. The fold card is generated behind the scenes but not exposed here — it's deliberately
excluded from the Streamlit flow for now. The sidebar's LJM-only controls (date picker, week
count, layout mode) are hidden for this mode since they don't apply.

Every generated LTRS HTML file is fully self-contained — fonts and images are embedded as base64
data URIs rather than linked as relative paths — so moving, emailing, or downloading the file from
Streamlit doesn't break its images or custom fonts (see CLAUDE.md's "asset embedding / portability
fix" note for why that wasn't always true).

Uploading a different file (or removing the current one) clears any previous run's download
buttons.

Each PNG's download button is followed by a suggested alt-text sentence (with a one-click copy icon) — paste it into Blackboard's own alt-text field when you embed the image there, since that's the only place alt text actually reaches a screen reader. It's a short summary by design, not a full transcript. The "Download all as ZIP" button also bundles a small `_alt_text.txt` file with both suggested sentences.

The sidebar has two sections: **Term Start Picker** (the Week 1 Monday date and a strict 10/12/Custom teaching-week-count control — see "Term Dates and the Easter Break" above) and **LJM height options** (the layout-mode radio). It is intended as a lightweight demo build; if the content is sensitive, use a private deployment instead of a public Streamlit Cloud app.

## Git Notes

Generated files under `output/` are ignored by Git. The folder stays in the repo via `output/.gitkeep`.
