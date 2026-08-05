#!/usr/bin/env python3
"""
make_ltrs2026_schedule.py

Run the LTRS2026 pipeline:
1) Parse workbook -> JSON/report
2) Render three HTML outputs
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT_XLSX = PROJECT_ROOT / "input" / "LTRS2026 schedule.xlsx"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "output"
DEFAULT_SHEET = "LTRS2026 (v1)"
DEFAULT_BASE_NAME = "ltrs2026"


def run(cmd: list[str]) -> int:
    print("[CMD] " + " ".join(f'"{part}"' if " " in part else part for part in cmd))
    return subprocess.run(cmd, text=True).returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Run parse + render for LTRS2026 schedule outputs.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT_XLSX), help="Input schedule workbook (.xlsx)")
    parser.add_argument("--sheet", default=DEFAULT_SHEET, help="Workbook sheet name")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Output directory")
    parser.add_argument("--base-name", default=DEFAULT_BASE_NAME, help="Output filename prefix")
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    parse_script = script_dir / "parse_ltrs2026_v1.py"
    render_script = script_dir / "render_ltrs2026_booklet.py"
    pdf_script = script_dir / "export_pdf.py"

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    parsed_json = output_dir / f"{args.base_name}_parsed.json"
    parse_report = output_dir / f"{args.base_name}_parse_report.txt"

    parse_cmd = [
        sys.executable,
        str(parse_script),
        "--input",
        str(args.input),
        "--sheet",
        args.sheet,
        "--output-json",
        str(parsed_json),
        "--output-report",
        str(parse_report),
    ]
    if run(parse_cmd) != 0:
        print("[FAIL] Parse step failed")
        return 1

    render_cmd = [
        sys.executable,
        str(render_script),
        "--input-json",
        str(parsed_json),
        "--output-dir",
        str(output_dir),
        "--base-name",
        args.base_name,
    ]
    if run(render_cmd) != 0:
        print("[FAIL] Render step failed")
        return 1

    single_page_html = (output_dir / f"{args.base_name}_single_page.html").resolve()
    single_page_pdf = (output_dir / f"{args.base_name}_single_page.pdf").resolve()
    two_side_html = (output_dir / f"{args.base_name}_a4_two_side.html").resolve()
    two_side_pdf = (output_dir / f"{args.base_name}_a4_two_side.pdf").resolve()

    for html_path, pdf_path in [
        (two_side_html, two_side_pdf),
    ]:
        pdf_cmd = [
            sys.executable,
            str(pdf_script),
            "--input", str(html_path),
            "--output", str(pdf_path),
        ]
        if run(pdf_cmd) != 0:
            print(f"[WARN] PDF export failed for {html_path.name} — HTML output is still available")

    print("[DONE] LTRS outputs generated")
    print(f"[OK] Parsed JSON:     {parsed_json}")
    print(f"[OK] Parse report:    {parse_report}")
    print(f"[OK] Single page:     {single_page_html}")
    print(f"[OK] A4 two side:     {two_side_html}")
    print(f"[OK] A4 two side PDF: {two_side_pdf}")
    print(f"[OK] A4 fold card:    {output_dir / (args.base_name + '_a4_fold_card.html')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
