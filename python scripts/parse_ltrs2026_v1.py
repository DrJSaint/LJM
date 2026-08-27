#!/usr/bin/env python3
"""
parse_ltrs2026_v1.py

Quick parser for the revised LTRS2026 schedule workbook.

Expected project structure:

project_root/
  data/
    LTRS2026 schedule.xlsx
  output/
  python_scripts/
    parse_ltrs2026_v1.py

Run from anywhere:

  python python_scripts/parse_ltrs2026_v1.py

Outputs:

  output/ltrs2026_v1_parsed.json
  output/ltrs2026_v1_parse_report.txt

By default this script reads the first sheet in the workbook, whatever it's called. Pass
--sheet to target a specific sheet by name instead.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
import json
import re

try:
    import pandas as pd
    import openpyxl
except ImportError as exc:
    raise SystemExit(
        "Missing dependency: pandas. Install with: pip install pandas openpyxl"
    ) from exc


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT_FILE = PROJECT_ROOT / "input" / "LTRS2026 schedule.xlsx"
OUTPUT_DIR = PROJECT_ROOT / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_SHEET_NAME = None  # None = first sheet in the workbook, whatever it's called
DEFAULT_OUTPUT_JSON = OUTPUT_DIR / "ltrs2026_v1_parsed.json"
DEFAULT_OUTPUT_REPORT = OUTPUT_DIR / "ltrs2026_v1_parse_report.txt"


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

def clean(value: Any) -> str:
    """Return a tidy string, or empty string for missing values.

    Preserves intentional line breaks (e.g. Alt+Enter in Excel, used for a
    two-line event title) while still collapsing incidental horizontal
    whitespace within each line - a manual line break is meaningful content,
    not whitespace to be squashed away.
    """
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except TypeError:
        pass
    text = str(value).replace("\u00a0", " ")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def build_hyperlink_map(input_file: Path, sheet_name: str) -> Dict[int, Dict[str, str]]:
    """Map Excel row number -> {column_name: url} for every hyperlinked cell.

    pandas.read_excel() only ever gives cell values, never hyperlink metadata,
    so this is a separate direct read of the same file via openpyxl (which
    already exposes cell.hyperlink) purely to build this lookup. Keyed by
    the real Excel row number so it lines up with the source_row bookkeeping
    already used throughout this file (row 1 is the header, so data starts
    at row 2).
    """
    workbook = openpyxl.load_workbook(input_file, data_only=True)
    worksheet = workbook[sheet_name]
    headers = {cell.column: cell.value for cell in worksheet[1]}

    links: Dict[int, Dict[str, str]] = {}
    for row in worksheet.iter_rows(min_row=2):
        for cell in row:
            if cell.hyperlink is not None and cell.hyperlink.target:
                column_name = headers.get(cell.column)
                if column_name:
                    links.setdefault(cell.row, {})[column_name] = cell.hyperlink.target
    return links


def link_for(row: Dict[str, Any], column: str) -> Optional[str]:
    """The hyperlink URL (if any) attached to `row`'s cell in `column`."""
    return (row.get("_links") or {}).get(column) or None


def fmt_time(value: Any) -> str:
    """Convert Excel/pandas time values into HH:MM strings."""
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except TypeError:
        pass

    # pandas may give datetime.time, Timestamp, datetime, or plain string
    if hasattr(value, "strftime"):
        try:
            return value.strftime("%H:%M")
        except Exception:
            pass

    text = clean(value)
    if not text:
        return ""

    # Convert e.g. 09:00:00 to 09:00
    m = re.match(r"^(\d{1,2}):(\d{2})(?::\d{2})?$", text)
    if m:
        return f"{int(m.group(1)):02d}:{m.group(2)}"

    return text


def is_time_present(row: Dict[str, Any]) -> bool:
    return bool(fmt_time(row.get("Start")))


def is_block_header(row: Dict[str, Any]) -> bool:
    """A block header/event row has a Start time and an Event value."""
    return bool(fmt_time(row.get("Start")) and clean(row.get("Event")))


def row_to_dict(row: Any, links: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    base = {k: row.get(k, "") for k in ["Start", "Duration", "End", "Event", "Location", "Presenter", "Chair"]}
    base["_links"] = links or {}
    return base


def get_theme_from_session_title(title: str) -> str:
    if ":" in title:
        return title.split(":", 1)[1].strip()
    return title.strip()


# -----------------------------------------------------------------------------
# Parser
# -----------------------------------------------------------------------------

def parse_standard_event(rows: List[Dict[str, Any]], i: int) -> tuple[Dict[str, Any], int]:
    row = rows[i]
    item = {
        "type": "event",
        "start": fmt_time(row.get("Start")),
        "end": fmt_time(row.get("End")),
        "duration_minutes": clean(row.get("Duration")),
        "title": clean(row.get("Event")),
        "title_url": link_for(row, "Event"),
        "location": clean(row.get("Location")),
        "location_url": link_for(row, "Location"),
        "presenter": clean(row.get("Presenter")),
        "presenter_url": link_for(row, "Presenter"),
        "chair": clean(row.get("Chair")),
        "chair_url": link_for(row, "Chair"),
        "source_row": i + 2,  # Excel row number, assuming header row is row 1
    }
    return item, i + 1


def parse_workshop_block(rows: List[Dict[str, Any]], i: int) -> tuple[Dict[str, Any], int]:
    header = rows[i]
    header_chair = clean(header.get("Chair"))
    block = {
        "type": "workshop_block",
        "start": fmt_time(header.get("Start")),
        "end": fmt_time(header.get("End")),
        "duration_minutes": clean(header.get("Duration")),
        "title": clean(header.get("Event")),
        "title_url": link_for(header, "Event"),
        "chair": header_chair or clean(header.get("Presenter")),
        "chair_url": link_for(header, "Chair") if header_chair else link_for(header, "Presenter"),
        "items": [],
        "source_row": i + 2,
    }

    i += 1
    while i < len(rows) and not is_block_header(rows[i]):
        row = rows[i]
        title = clean(row.get("Event"))
        room = clean(row.get("Location"))
        presenter = clean(row.get("Presenter"))

        if title or room or presenter:
            block["items"].append({
                "title": title,
                "title_url": link_for(row, "Event"),
                "room": room,
                "room_url": link_for(row, "Location"),
                "presenter": presenter,
                "presenter_url": link_for(row, "Presenter"),
                "source_row": i + 2,
            })
        i += 1

    return block, i


def parse_plenary_block(rows: List[Dict[str, Any]], i: int) -> tuple[Dict[str, Any], int]:
    header = rows[i]
    header_chair = clean(header.get("Chair"))
    block = {
        "type": "plenary_block",
        "start": fmt_time(header.get("Start")),
        "end": fmt_time(header.get("End")),
        "duration_minutes": clean(header.get("Duration")),
        "title": clean(header.get("Event")),
        "title_url": link_for(header, "Event"),
        "location": clean(header.get("Location")),
        "location_url": link_for(header, "Location"),
        "chair": header_chair or clean(header.get("Presenter")),
        "chair_url": link_for(header, "Chair") if header_chair else link_for(header, "Presenter"),
        "items": [],
        "source_row": i + 2,
    }

    i += 1
    while i < len(rows) and not is_block_header(rows[i]):
        row = rows[i]
        title = clean(row.get("Event"))
        presenters = clean(row.get("Presenter"))

        if title or presenters:
            block["items"].append({
                "title": title,
                "title_url": link_for(row, "Event"),
                "presenters": presenters,
                "presenters_url": link_for(row, "Presenter"),
                "source_row": i + 2,
            })
        i += 1

    return block, i


def parse_presentation_sessions(rows: List[Dict[str, Any]], i: int) -> tuple[Dict[str, Any], int]:
    """
    Parse the 14:00 parallel presentation section.

    In the revised v1 sheet, the first session row has the timed header:
      Start=14:00, Event='Parallel Presentation Session 1: ...', Location=Room A, Chair=...

    Subsequent sessions are untimed subheaders before the next timed block:
      Event='Parallel Presentation Session 2: ...', Location=Room B, Chair=...
      Event='Parallel Presentation Session 3: ...', Location=Room C, Chair=...
    """
    header = rows[i]
    parent = {
        "type": "presentation_session_block",
        "start": fmt_time(header.get("Start")),
        "end": fmt_time(header.get("End")),
        "duration_minutes": clean(header.get("Duration")),
        "title": "Parallel Presentation Sessions",
        "sessions": [],
        "source_row": i + 2,
    }

    current_session: Optional[Dict[str, Any]] = None

    while i < len(rows):
        row = rows[i]

        # Stop when the next timed block begins, but allow the first timed row.
        if i != parent["source_row"] - 2 and is_block_header(row):
            break

        event_text = clean(row.get("Event"))
        location = clean(row.get("Location"))
        presenter = clean(row.get("Presenter"))
        chair = clean(row.get("Chair"))

        if event_text.startswith("Parallel Presentation Session"):
            if current_session:
                parent["sessions"].append(current_session)

            current_session = {
                "session_title": event_text,
                "theme": get_theme_from_session_title(event_text),
                "theme_url": link_for(row, "Event"),
                "room": location,
                "room_url": link_for(row, "Location"),
                "chair": chair or presenter,
                "chair_url": link_for(row, "Chair") if chair else link_for(row, "Presenter"),
                "talks": [],
                "source_row": i + 2,
            }
        else:
            if current_session and (event_text or presenter):
                current_session["talks"].append({
                    "title": event_text,
                    "title_url": link_for(row, "Event"),
                    "presenter": presenter,
                    "presenter_url": link_for(row, "Presenter"),
                    "source_row": i + 2,
                })

        i += 1

    if current_session:
        parent["sessions"].append(current_session)

    return parent, i


def parse_v1(input_file: Path, sheet_name: Optional[str]) -> Dict[str, Any]:
    if not input_file.exists():
        raise FileNotFoundError(f"Cannot find input file: {input_file}")

    if sheet_name is None:
        # No sheet name given — take whichever sheet is first in the workbook,
        # regardless of what it's called. Resolved to a real name up front (rather
        # than passing pandas a positional index) so the parse report/JSON can show
        # the actual sheet that got read, not just "0".
        sheet_name = pd.ExcelFile(input_file, engine="openpyxl").sheet_names[0]

    df = pd.read_excel(input_file, sheet_name=sheet_name, engine="openpyxl")

    # Keep only the expected columns and normalise missing columns.
    expected = ["Start", "Duration", "End", "Event", "Location", "Presenter", "Chair"]

    # Checked against the sheet's real columns, before any are backfilled below —
    # a sheet with none of these is almost certainly the wrong sheet/file entirely
    # (e.g. a non-LTRS workbook, or a summary/notes tab), not just missing a
    # column or two. Catching this here gives a specific, actionable message
    # instead of silently producing an empty schedule.
    original_columns = {str(c).strip() for c in df.columns}
    if not original_columns & set(expected):
        found = ", ".join(str(c) for c in df.columns) or "(no columns)"
        raise ValueError(
            f"Sheet '{sheet_name}' doesn't look like an LTRS schedule — none of the expected "
            f"columns (Start, Duration, End, Event, Location, Presenter, Chair) were found. "
            f"Found: {found}."
        )

    for col in expected:
        if col not in df.columns:
            df[col] = ""
    df = df[expected]

    hyperlinks = build_hyperlink_map(input_file, sheet_name)
    # Row 1 is the header, so the first data row (DataFrame index 0) is Excel row 2 —
    # the same convention every source_row already uses throughout this file.
    rows = [
        row_to_dict(r, hyperlinks.get(idx + 2))
        for idx, (_, r) in enumerate(df.iterrows())
    ]

    programme: List[Dict[str, Any]] = []
    i = 0

    while i < len(rows):
        row = rows[i]
        event = clean(row.get("Event"))

        # Skip fully blank rows.
        if not any(clean(row.get(c)) for c in expected):
            i += 1
            continue

        if is_block_header(row):
            if event == "Parallel Workshops":
                block, i = parse_workshop_block(rows, i)
                programme.append(block)
            elif event == "Plenary (VC Funding)":
                block, i = parse_plenary_block(rows, i)
                programme.append(block)
            elif event.startswith("Parallel Presentation Session"):
                block, i = parse_presentation_sessions(rows, i)
                programme.append(block)
            else:
                block, i = parse_standard_event(rows, i)
                programme.append(block)
        else:
            # Any unanchored row outside a recognised block gets preserved for debugging.
            programme.append({
                "type": "unparsed_row",
                "event": clean(row.get("Event")),
                "location": clean(row.get("Location")),
                "presenter": clean(row.get("Presenter")),
                "chair": clean(row.get("Chair")),
                "source_row": i + 2,
            })
            i += 1

    # A sheet that has the right columns but no rows shaped like real schedule
    # entries (each needs a Start time and an Event) produces only "unparsed_row"
    # placeholders rather than raising outright — catch that here so it surfaces
    # as an error instead of rendering a blank-looking schedule.
    real_blocks = [block for block in programme if block.get("type") != "unparsed_row"]
    if not real_blocks:
        raise ValueError(
            f"No usable schedule rows were found on sheet '{sheet_name}' — it may be empty, "
            f"or the data isn't in the expected format (each event needs a Start time and an "
            f"Event value in the row directly below the header row)."
        )

    return {
        "source_file": str(input_file),
        "sheet": sheet_name,
        "programme": programme,
    }


def build_report(parsed: Dict[str, Any]) -> str:
    lines = []
    lines.append(f"Source: {parsed['source_file']}")
    lines.append(f"Sheet: {parsed['sheet']}")
    lines.append("")

    programme = parsed["programme"]
    lines.append(f"Top-level blocks parsed: {len(programme)}")
    lines.append("")

    for idx, block in enumerate(programme, start=1):
        btype = block.get("type")
        title = block.get("title") or block.get("session_title") or block.get("event")
        start = block.get("start", "")
        end = block.get("end", "")
        src = block.get("source_row", "?")

        if btype == "event":
            lines.append(f"{idx:02d}. EVENT [{start}-{end}] {title} | row {src}")
        elif btype == "workshop_block":
            lines.append(f"{idx:02d}. WORKSHOP BLOCK [{start}-{end}] {len(block['items'])} workshops | chair: {block.get('chair')} | row {src}")
        elif btype == "plenary_block":
            lines.append(f"{idx:02d}. PLENARY [{start}-{end}] {len(block['items'])} items | chair: {block.get('chair')} | row {src}")
        elif btype == "presentation_session_block":
            session_count = len(block.get("sessions", []))
            talk_count = sum(len(s.get("talks", [])) for s in block.get("sessions", []))
            lines.append(f"{idx:02d}. PRESENTATION BLOCK [{start}-{end}] {session_count} sessions, {talk_count} talks | row {src}")
            for session in block.get("sessions", []):
                lines.append(f"    - {session.get('theme')} | {session.get('room')} | chair: {session.get('chair')} | {len(session.get('talks', []))} talks")
        else:
            lines.append(f"{idx:02d}. {btype.upper()} {title} | row {src}")

    return "\n".join(lines) + "\n"


def fail(message: str) -> None:
    print(f"[FAIL] {message}", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Parse LTRS schedule workbook into JSON.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT_FILE), help="Input .xlsx workbook path")
    parser.add_argument(
        "--sheet",
        default=DEFAULT_SHEET_NAME,
        help="Worksheet name to parse (default: first sheet in the workbook, whatever it's called)",
    )
    parser.add_argument("--output-json", default=str(DEFAULT_OUTPUT_JSON), help="Output parsed JSON path")
    parser.add_argument("--output-report", default=str(DEFAULT_OUTPUT_REPORT), help="Output parse report path")
    args = parser.parse_args()

    input_file = Path(args.input)
    output_json = Path(args.output_json)
    output_report = Path(args.output_report)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_report.parent.mkdir(parents=True, exist_ok=True)

    try:
        parsed = parse_v1(input_file=input_file, sheet_name=args.sheet)
    except (FileNotFoundError, ValueError) as exc:
        fail(str(exc))

    output_json.write_text(
        json.dumps(parsed, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    report = build_report(parsed)
    output_report.write_text(report, encoding="utf-8")

    print(report)
    print(f"Wrote JSON:   {output_json}")
    print(f"Wrote report: {output_report}")


if __name__ == "__main__":
    main()
