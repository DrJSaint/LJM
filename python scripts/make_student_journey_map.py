#!/usr/bin/env python3
"""
make_student_journey_map.py

Wrapper script for the student-facing Learner Journey Map pipeline.

It runs the two-stage process:

1. Extract and validate student-facing journey data from a Word LJM.
2. Render the validated JSON data as a tall PNG poster, optionally with PDF output.

Expected companion scripts in the same folder:
    extract_student_journey_map_v2.py
    render_student_journey_map_png.py

Typical use:
    python make_student_journey_map.py

Useful toggles near the top:
    EXPORT_PDF = True / False
    ALLOW_WARNINGS = True / False
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


# ---------------------------
# User settings
# ---------------------------

INPUT_DOCX = Path("../input/DSC502_Learner_Journey_Map.docx")
OUTPUT_DIR = Path("../output")

WEEK_1_MONDAY = "2026-09-21"
EXPECTED_WEEKS = 12

EXPORT_PDF = True
ALLOW_WARNINGS = True

BASE_NAME = "student_journey_map"

EXTRACTOR_SCRIPT = "extract_student_journey_map_v2.py"
RENDERER_SCRIPT = "render_student_journey_map_png.py"


# ---------------------------
# Helpers
# ---------------------------

def info(message: str) -> None:
    print(f"[INFO] {message}")


def ok(message: str) -> None:
    print(f"[OK]   {message}")


def fail(message: str) -> None:
    print(f"[FAIL] {message}")


def run_command(cmd: list[str]) -> int:
    print("[CMD]  " + " ".join(f'"{x}"' if " " in x else x for x in cmd))
    result = subprocess.run(cmd, text=True)
    return result.returncode


# ---------------------------
# Main pipeline
# ---------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Run the full student journey map pipeline.")
    parser.add_argument("--input", default=str(INPUT_DOCX), help="Input Word Learner Journey Map .docx")
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR), help="Output folder")
    parser.add_argument("--week1", default=WEEK_1_MONDAY, help="Week 1 Monday as YYYY-MM-DD")
    parser.add_argument("--expected-weeks", type=int, default=EXPECTED_WEEKS, help="Expected number of teaching weeks")
    parser.add_argument("--base-name", default=BASE_NAME, help="Base filename for output files")
    parser.add_argument("--no-pdf", action="store_true", help="Do not create the PDF wrapper")
    parser.add_argument("--strict", action="store_true", help="Do not render PNG/PDF unless extraction status is APPROVED")
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    extractor_path = script_dir / EXTRACTOR_SCRIPT
    renderer_path = script_dir / RENDERER_SCRIPT

    input_docx = Path(args.input).resolve()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    review_path = output_dir / f"{args.base_name}_review.txt"
    json_path = output_dir / f"{args.base_name}_data.json"
    png_path = output_dir / f"{args.base_name}.png"
    pdf_path = output_dir / f"{args.base_name}.pdf"

    export_pdf = EXPORT_PDF and not args.no_pdf
    allow_warnings = ALLOW_WARNINGS and not args.strict

    info(f"Input DOCX     : {input_docx}")
    info(f"Output folder  : {output_dir}")
    info(f"Week 1 Monday  : {args.week1}")
    info(f"Expected weeks : {args.expected_weeks}")
    info(f"Export PDF     : {export_pdf}")
    info(f"Allow warnings : {allow_warnings}")

    if not input_docx.exists():
        fail(f"Input DOCX does not exist: {input_docx}")
        return 1

    if not extractor_path.exists():
        fail(f"Extractor script not found: {extractor_path}")
        return 1

    if not renderer_path.exists():
        fail(f"Renderer script not found: {renderer_path}")
        return 1

    print("\n[STEP 1] Extract and validate")
    extract_cmd = [
        sys.executable,
        str(extractor_path),
        "--input",
        str(input_docx),
        "--review",
        str(review_path),
        "--json",
        str(json_path),
        "--week1",
        args.week1,
        "--expected-weeks",
        str(args.expected_weeks),
    ]

    rc = run_command(extract_cmd)
    if rc != 0:
        fail("Extraction failed. PNG rendering skipped.")
        return rc

    print("\n[STEP 2] Render PNG")
    render_cmd = [
        sys.executable,
        str(renderer_path),
        "--input",
        str(json_path),
        "--output",
        str(png_path),
    ]

    if export_pdf:
        render_cmd.extend(["--pdf", str(pdf_path)])

    if allow_warnings:
        render_cmd.append("--allow-warnings")

    rc = run_command(render_cmd)
    if rc != 0:
        fail("PNG rendering failed.")
        return rc

    print("\n[DONE]")
    ok(f"Review TXT : {review_path}")
    ok(f"JSON data  : {json_path}")
    ok(f"PNG output : {png_path}")
    if export_pdf:
        ok(f"PDF output : {pdf_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
