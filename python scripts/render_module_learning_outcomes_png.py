#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

DEFAULT_INPUT = "../output/student_journey_map_data.json"
DEFAULT_OUTPUT = "../output/module_learning_outcomes.png"
RESOLUTION_SCALE = 3  # multiplies the whole design beyond the original 1080px canvas for sharper zoom/print quality
CANVAS_SIZE = 1080 * RESOLUTION_SCALE
BASE_ROWS = 5
ROW_H = CANVAS_SIZE // BASE_ROWS
ROW_BOTTOM_PADDING = 18 * RESOLUTION_SCALE
CODE_BASELINE_NUDGE = 2 * RESOLUTION_SCALE
PROJECT_ROOT = Path(__file__).resolve().parent.parent

STYLE = {
    "palette": {
        "cream": "#F7F1E8",
        "dark": "#171F20",
        "lilac": "#D8CBF1",
        "green": "#195C4D",
        "mlo1": "#195C4D",
        "mlo2": "#70ACE9",
        "mlo3": "#710704",
        "mlo4": "#E7F95D",
    },
    "layout": {
        "code_x": 34,
        "text_x": 194,
        "right_pad": 40,
        "header_pad_top": 0,
        "header_line_gap": 0,
        "row_title_offset": 28,
        "row_desc_gap": 18,
    },
    "text": {
        "header_size": 52,
        "code_size": 52,
        "title_size": 37,
        "desc_size": 37,
        "line_spacing": 8,
    },
}


def scale_style_values(obj: dict, scale: int) -> None:
    for key, value in obj.items():
        if isinstance(value, dict):
            scale_style_values(value, scale)
        elif isinstance(value, (int, float)):
            obj[key] = int(round(value * scale))


scale_style_values(STYLE["layout"], RESOLUTION_SCALE)
scale_style_values(STYLE["text"], RESOLUTION_SCALE)


def hex_to_rgba(color: str, alpha: int = 255) -> tuple[int, int, int, int]:
    color = color.lstrip("#")
    return int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16), alpha


def find_font(names: str | list[str]) -> Path | None:
    if isinstance(names, str):
        names = [names]

    font_dirs = [
        PROJECT_ROOT / "assets" / "fonts",
        PROJECT_ROOT / "assets",
        Path("C:/Windows/Fonts"),
        Path.home() / "AppData" / "Local" / "Microsoft" / "Windows" / "Fonts",
    ]

    for font_dir in font_dirs:
        for name in names:
            candidate = font_dir / name
            if candidate.exists():
                return candidate
    return None


def load_font(size: int, names: list[str], fallback: list[str]) -> ImageFont.ImageFont:
    path = find_font(names) or find_font(fallback)
    if path:
        return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def build_fonts() -> dict[str, ImageFont.ImageFont]:
    return {
        "header": load_font(
            STYLE["text"]["header_size"],
            ["magnole-regular.otf"],
            ["georgia.ttf", "DejaVuSerif.ttf"],
        ),
        "code": load_font(
            STYLE["text"]["code_size"],
            ["magnole-regular.otf"],
            ["georgia.ttf", "DejaVuSerif.ttf"],
        ),
        "title": load_font(
            STYLE["text"]["title_size"],
            ["AvenirNextLTPro-Bold.otf", "AvenirNextLTPro-Demi.otf"],
            ["candarab.ttf", "calibrib.ttf", "arialbd.ttf"],
        ),
        "desc": load_font(
            STYLE["text"]["desc_size"],
            ["AvenirNextLTPro-Regular.otf", "AvenirNextLTPro-Mediumlt.otf"],
            ["candara.ttf", "calibri.ttf", "arial.ttf"],
        ),
    }


FONTS = build_fonts()


def text_size(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> tuple[int, int]:
    if not text:
        return 0, 0
    bbox = draw.textbbox((0, 0), text, font=font)
    return int(bbox[2] - bbox[0]), int(bbox[3] - bbox[1])


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
    text = re.sub(r"\s+", " ", text.strip())
    if not text:
        return []

    words = text.split(" ")
    lines: list[str] = []
    current: list[str] = []

    for word in words:
        trial = " ".join(current + [word]).strip()
        width, _ = text_size(draw, trial, font)
        if width <= max_width or not current:
            current.append(word)
        else:
            lines.append(" ".join(current))
            current = [word]

    if current:
        lines.append(" ".join(current))

    return lines


def fit_lines(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int, max_lines: int) -> list[str]:
    lines = wrap_text(draw, text, font, max_width)
    if len(lines) <= max_lines:
        return lines

    clipped = lines[:max_lines]
    last = clipped[-1]
    while last:
        candidate = last.rstrip(" .,") + "..."
        if text_size(draw, candidate, font)[0] <= max_width:
            clipped[-1] = candidate
            break
        last = last[:-1]
    if not last:
        clipped[-1] = "..."
    return clipped


def module_code(module_title: str) -> str:
    if ":" in module_title:
        return module_title.split(":", 1)[0].strip()
    first = module_title.split()
    return first[0] if first else "MODULE"


def mlo_rows(mlos: list[dict]) -> list[dict]:
    items = []
    for mlo in mlos:
        items.append(
            {
                "code": str(mlo.get("code", "")).upper() or "MLO?",
                "title": str(mlo.get("title", "")).strip() or "Learning Outcome Title",
                "description": str(mlo.get("description", "")).strip() or "Learning Outcome description",
            }
        )
    return items


def render_mlos(data: dict, output_png: Path) -> list[str]:
    warnings: list[str] = []
    mlos = data.get("mlos", [])
    if not mlos:
        warnings.append("No MLOs found in extracted data; rendering a placeholder outcome row.")
        mlos = [{"code": "MLO1", "title": "Learning Outcome Title", "description": "Learning Outcome description"}]

    rows = mlo_rows(mlos)
    outcome_rows = len(rows)

    # Measure row content first so text is never clipped by fixed row height.
    measure_image = Image.new("RGB", (CANVAS_SIZE, ROW_H), STYLE["palette"]["cream"])
    measure_draw = ImageDraw.Draw(measure_image)
    max_text_w = CANVAS_SIZE - STYLE["layout"]["text_x"] - STYLE["layout"]["right_pad"]

    prepared_rows: list[dict] = []
    row_heights: list[int] = []
    for i, mlo in enumerate(rows):
        title = str(mlo.get("title", "Learning Outcome Title")).strip() or "Learning Outcome Title"
        desc = str(mlo.get("description", "Learning Outcome description")).strip() or "Learning Outcome description"

        desc_lines = wrap_text(measure_draw, desc, FONTS["desc"], max_text_w)
        if not desc_lines:
            desc_lines = [""]

        _, title_h = text_size(measure_draw, title, FONTS["title"])
        line_heights = [text_size(measure_draw, line, FONTS["desc"])[1] for line in desc_lines]
        desc_h = sum(line_heights) + max(0, len(desc_lines) - 1) * STYLE["text"]["line_spacing"]

        content_h = (
            STYLE["layout"]["row_title_offset"]
            + title_h
            + STYLE["layout"]["row_desc_gap"]
            + desc_h
            + ROW_BOTTOM_PADDING
        )
        row_h = max(ROW_H, content_h)

        prepared_rows.append(
            {
                "mlo": mlo,
                "title": title,
                "desc_lines": desc_lines,
            }
        )
        row_heights.append(row_h)

    canvas_h = ROW_H + sum(row_heights)

    if outcome_rows > 5 or any(h > ROW_H for h in row_heights):
        warnings.append(f"Output height expanded to {canvas_h}px to preserve all MLO text.")

    image = Image.new("RGBA", (CANVAS_SIZE, canvas_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    # Row backgrounds: header + outcome bands (cycled for variable count)
    row_bg = [STYLE["palette"]["dark"]]
    outcome_bg_cycle = [
        STYLE["palette"]["cream"],
        STYLE["palette"]["dark"],
        STYLE["palette"]["lilac"],
        STYLE["palette"]["green"],
    ]
    for idx in range(outcome_rows):
        row_bg.append(outcome_bg_cycle[idx % len(outcome_bg_cycle)])

    # Header band stays transparent to match template export style.
    draw.rectangle([0, 0, CANVAS_SIZE, ROW_H], fill=(0, 0, 0, 0))
    y_cursor = ROW_H
    for i, color in enumerate(row_bg[1:]):
        row_h = row_heights[i]
        draw.rectangle([0, y_cursor, CANVAS_SIZE, y_cursor + row_h], fill=hex_to_rgba(color))
        y_cursor += row_h

    code = module_code(data.get("module_title", "MODULE"))
    header_text = f"Learning\nOutcomes\nfor {code}"
    lines = header_text.split("\n")
    # Use font metrics for consistent line advance across mixed glyphs.
    ascent, descent = FONTS["header"].getmetrics()
    line_advance = ascent + descent
    line_heights = [line_advance for _ in lines]
    header_line_gap = STYLE["layout"]["header_line_gap"]
    total_h = sum(line_heights) + (len(lines) - 1) * header_line_gap
    y = (ROW_H - total_h) // 2 + STYLE["layout"]["header_pad_top"]

    for line, lh in zip(lines, line_heights):
        lw, _ = text_size(draw, line, FONTS["header"])
        draw.text(((CANVAS_SIZE - lw) // 2, y), line, font=FONTS["header"], fill=STYLE["palette"]["dark"])
        y += lh + header_line_gap

    code_colors = [STYLE["palette"]["mlo1"], STYLE["palette"]["mlo2"], STYLE["palette"]["mlo3"], STYLE["palette"]["mlo4"]]
    title_colors = [STYLE["palette"]["dark"], STYLE["palette"]["cream"], STYLE["palette"]["dark"], STYLE["palette"]["cream"]]
    desc_colors = [STYLE["palette"]["dark"], STYLE["palette"]["cream"], STYLE["palette"]["dark"], STYLE["palette"]["cream"]]

    row_y = ROW_H
    for i, prepared in enumerate(prepared_rows):
        mlo = prepared["mlo"]
        title = prepared["title"]
        desc_lines = prepared["desc_lines"]
        row_h = row_heights[i]
        row_center = row_y + row_h // 2

        code_text = str(mlo.get("code", f"MLO{i+1}")).upper()
        cw, ch = text_size(draw, code_text, FONTS["code"])
        code_x = STYLE["layout"]["code_x"]
        code_y = row_center - ch // 2 - CODE_BASELINE_NUDGE
        draw.text((code_x, code_y), code_text, font=FONTS["code"], fill=code_colors[i % len(code_colors)])

        text_x = STYLE["layout"]["text_x"]
        title_y = row_y + STYLE["layout"]["row_title_offset"]
        draw.text((text_x, title_y), title, font=FONTS["title"], fill=title_colors[i % len(title_colors)])

        _, title_h = text_size(draw, title, FONTS["title"])
        desc_y = title_y + title_h + STYLE["layout"]["row_desc_gap"]

        cy = desc_y
        for line in desc_lines:
            draw.text((text_x, cy), line, font=FONTS["desc"], fill=desc_colors[i % len(desc_colors)])
            _, lh = text_size(draw, line, FONTS["desc"])
            cy += lh + STYLE["text"]["line_spacing"]

        row_y += row_h

    output_png.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_png, "PNG")
    return warnings


def main() -> int:
    parser = argparse.ArgumentParser(description="Render fixed-width Module Learning Outcomes PNG from extracted JSON.")
    parser.add_argument("--input", default=DEFAULT_INPUT, help="Input JSON from extractor")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="Output PNG path")
    parser.add_argument("--allow-warnings", action="store_true", help="Render even if extraction status is not APPROVED")
    parser.add_argument("--header-size", type=int, default=None, help="Override header font size")
    parser.add_argument("--code-size", type=int, default=None, help="Override MLO code font size")
    parser.add_argument("--title-size", type=int, default=None, help="Override outcome title font size")
    parser.add_argument("--desc-size", type=int, default=None, help="Override outcome description font size")
    parser.add_argument("--line-spacing", type=int, default=None, help="Override description line spacing")
    parser.add_argument("--header-line-gap", type=int, default=None, help="Override header line gap")
    args = parser.parse_args()

    global FONTS
    if args.header_size is not None:
        STYLE["text"]["header_size"] = max(8, args.header_size) * RESOLUTION_SCALE
    if args.code_size is not None:
        STYLE["text"]["code_size"] = max(8, args.code_size) * RESOLUTION_SCALE
    if args.title_size is not None:
        STYLE["text"]["title_size"] = max(8, args.title_size) * RESOLUTION_SCALE
    if args.desc_size is not None:
        STYLE["text"]["desc_size"] = max(8, args.desc_size) * RESOLUTION_SCALE
    if args.line_spacing is not None:
        STYLE["text"]["line_spacing"] = max(0, args.line_spacing) * RESOLUTION_SCALE
    if args.header_line_gap is not None:
        STYLE["layout"]["header_line_gap"] = max(0, args.header_line_gap) * RESOLUTION_SCALE

    FONTS = build_fonts()

    input_path = Path(args.input).resolve()
    output_png = Path(args.output).resolve()

    if not input_path.exists():
        print(f"[ERROR] Input JSON does not exist: {input_path}")
        return 1

    data = json.loads(input_path.read_text(encoding="utf-8"))
    status = data.get("extraction_status", "UNKNOWN")

    print(f"[INFO] Input JSON       : {input_path}")
    print(f"[INFO] Extraction status: {status}")
    print(f"[INFO] Output PNG       : {output_png}")

    if status != "APPROVED" and not args.allow_warnings:
        print("[ERROR] Extraction is not APPROVED. Review the TXT file or rerun with --allow-warnings.")
        for issue in data.get("issues", []):
            print(f"       - {issue}")
        return 2

    warnings = render_mlos(data, output_png)
    print(f"[OK] Wrote PNG: {output_png.name}")
    for warning in warnings:
        print(f"[WARN] {warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
