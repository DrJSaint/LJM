#!/usr/bin/env python3
"""
export_pdf.py

Export an HTML schedule file to PDF using Playwright's headless Chromium.
Respects the file's own @page CSS (size, margins, etc.) and forces
background graphics on so session colours are preserved.

Usage:
    python "python scripts/export_pdf.py" --input output/ltrs2026_single_page.html
    python "python scripts/export_pdf.py" --input output/ltrs2026_single_page.html --output output/ltrs2026_single_page.pdf
"""

from __future__ import annotations

import argparse
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "output"


def export(html_path: Path, pdf_path: Path) -> None:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1200, "height": 900})
        page.goto(html_path.as_uri(), wait_until="networkidle")
        page.pdf(
            path=str(pdf_path),
            print_background=True,   # preserve session row colours
            prefer_css_page_size=True,  # honour @page size/margin from HTML
        )
        browser.close()

    print(f"[OK] PDF written: {pdf_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Export an HTML schedule to PDF via Playwright.")
    parser.add_argument("--input", required=True, help="Path to input HTML file")
    parser.add_argument("--output", default=None, help="Path to output PDF (defaults to same name as input with .pdf)")
    args = parser.parse_args()

    html_path = Path(args.input).resolve()
    if not html_path.exists():
        print(f"[FAIL] HTML file not found: {html_path}")
        return 1

    pdf_path = Path(args.output).resolve() if args.output else html_path.with_suffix(".pdf")

    export(html_path, pdf_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
