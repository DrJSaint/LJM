#!/usr/bin/env python3
"""
render_student_journey_map_png.py

Render a student-facing learner journey map poster from extracted JSON.

Input:
    student_journey_data.json from extract_student_journey_map_v2.py

Outputs:
    PNG poster, with optional PDF wrapper.
"""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from typing import List, Tuple

from PIL import Image, ImageDraw, ImageFont


DEFAULT_INPUT = "../output/student_journey_data.json"
DEFAULT_OUTPUT = "../output/student_journey_map.png"
DEFAULT_PDF = "../output/student_journey_map.pdf"
RENDER_SCALE = 3

STYLE = {
    "canvas": {
        "width": 1600,
        "background": "#F4E9D8",
        "top_padding": 210,
        "bottom_padding": 160,
        "side_margin": 110,
    },
    "palette": {
        "green": "#1E6556",
        "green_dark": "#16483F",
        "text": "#111111",
        "muted": "#575757",
        "cream": "#F4E9D8",
        "white": "#F3F5F2",
        "line": "#1E6556",
    },
    "timeline": {
        "x": 800,
        "line_width": 8,
        "circle_radius": 38,
        "circle_stroke": 0,
        "connector_width": 4,
        "week_gap": 245,
    },
    "text": {
        "title_size": 58,
        "subtitle_size": 34,
        "date_size": 26,
        "week_title_size": 30,
        "detail_size": 24,
        "pill_size": 22,
        "footer_size": 20,
        "line_spacing": 8,
    },
    "blocks": {
        "width": 520,
        "date_title_gap": 8,
        "title_detail_gap": 10,
        "pill_gap": 18,
    },
    "pill": {
        "padding_x": 20,
        "padding_y": 12,
        "radius": 26,
        "max_width": 470,
    },
}

def scale_style_values(obj, scale: int) -> None:
    for key, value in obj.items():
        if isinstance(value, dict):
            scale_style_values(value, scale)
        elif isinstance(value, (int, float)):
            obj[key] = int(round(value * scale))


scale_style_values(STYLE, RENDER_SCALE)

# ---------------------------
# Font helpers
# ---------------------------

def find_font(name: str = "DejaVuSans.ttf") -> Path | None:
    candidates = [
        Path("/usr/share/fonts/truetype/dejavu") / name,
        Path("/usr/share/fonts/truetype/liberation2") / name,
        Path("/usr/share/fonts/truetype/freefont") / name,
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    font_name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    path = find_font(font_name)
    if path:
        return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


FONTS = {
    "title": load_font(STYLE["text"]["title_size"], bold=True),
    "subtitle": load_font(STYLE["text"]["subtitle_size"], bold=True),
    "date": load_font(STYLE["text"]["date_size"], bold=True),
    "week_title": load_font(STYLE["text"]["week_title_size"], bold=True),
    "detail": load_font(STYLE["text"]["detail_size"], bold=False),
    "pill": load_font(STYLE["text"]["pill_size"], bold=True),
    "circle": load_font(32, bold=True),
    "footer": load_font(STYLE["text"]["footer_size"], bold=False),
}


# ---------------------------
# Drawing helpers
# ---------------------------

def text_size(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> Tuple[int, int]:
    if not text:
        return 0, 0
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> List[str]:
    text = re.sub(r"\s+", " ", text.strip())
    if not text:
        return []

    words = text.split(" ")
    lines: List[str] = []
    current: List[str] = []

    for word in words:
        trial = " ".join(current + [word]).strip()
        w, _ = text_size(draw, trial, font)
        if w <= max_width or not current:
            current.append(word)
        else:
            lines.append(" ".join(current))
            current = [word]

    if current:
        lines.append(" ".join(current))

    return lines


def draw_wrapped_text(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    lines: List[str],
    font: ImageFont.ImageFont,
    fill: str,
    line_spacing: int,
    align: str = "left",
    max_width: int | None = None,
) -> int:
    current_y = y
    for line in lines:
        w, h = text_size(draw, line, font)
        draw_x = x
        if align == "right" and max_width is not None:
            draw_x = x + max_width - w
        elif align == "center" and max_width is not None:
            draw_x = x + (max_width - w) // 2
        draw.text((draw_x, current_y), line, font=font, fill=fill)
        current_y += h + line_spacing
    return current_y


def draw_centered_text(draw: ImageDraw.ImageDraw, y: int, text: str, font: ImageFont.ImageFont, fill: str, canvas_width: int) -> int:
    w, h = text_size(draw, text, font)
    draw.text(((canvas_width - w) // 2, y), text, font=font, fill=fill)
    return y + h


def pill_size(draw: ImageDraw.ImageDraw, text: str, max_width: int) -> Tuple[List[str], int, int]:
    lines = wrap_text(draw, text, FONTS["pill"], max_width - 2 * STYLE["pill"]["padding_x"])
    line_heights = [text_size(draw, line, FONTS["pill"])[1] for line in lines] or [0]
    width = 0
    for line in lines:
        w, _ = text_size(draw, line, FONTS["pill"])
        width = max(width, w)
    width += 2 * STYLE["pill"]["padding_x"]
    height = sum(line_heights) + (len(lines) - 1) * 5 + 2 * STYLE["pill"]["padding_y"]
    width = min(width, max_width)
    return lines, width, height


def draw_pill(draw: ImageDraw.ImageDraw, x: int, y: int, text: str, side: str) -> int:
    palette = STYLE["palette"]
    max_width = STYLE["pill"]["max_width"]
    lines, width, height = pill_size(draw, text, max_width)

    if side == "left":
        rect_x = x + STYLE["blocks"]["width"] - width
    else:
        rect_x = x

    rect = [rect_x, y, rect_x + width, y + height]
    draw.rounded_rectangle(rect, radius=STYLE["pill"]["radius"], fill=palette["green"])

    text_y = y + STYLE["pill"]["padding_y"]
    for line in lines:
        tw, th = text_size(draw, line, FONTS["pill"])
        draw.text((rect_x + (width - tw) // 2, text_y), line, font=FONTS["pill"], fill=palette["white"])
        text_y += th + 5

    return y + height


def measure_week_block(draw: ImageDraw.ImageDraw, week: dict) -> int:
    block_width = STYLE["blocks"]["width"]
    line_spacing = STYLE["text"]["line_spacing"]

    date_lines = wrap_text(draw, week["date_label"], FONTS["date"], block_width)
    title_lines = wrap_text(draw, week["title"], FONTS["week_title"], block_width)
    detail_lines = wrap_text(draw, week["detail"], FONTS["detail"], block_width)

    height = 0
    for lines, font in [(date_lines, FONTS["date"]), (title_lines, FONTS["week_title"]), (detail_lines, FONTS["detail"] )]:
        for line in lines:
            _, h = text_size(draw, line, font)
            height += h + line_spacing

    height += STYLE["blocks"]["date_title_gap"] + STYLE["blocks"]["title_detail_gap"]

    if week.get("render_pill") and week.get("assessment", "").strip():
        lines, _, pill_h = pill_size(draw, week["assessment"], STYLE["pill"]["max_width"])
        height += STYLE["blocks"]["pill_gap"] + pill_h

    return max(height, 145)


def draw_week_block(draw: ImageDraw.ImageDraw, week: dict, center_y: int, side: str) -> None:
    palette = STYLE["palette"]
    block_width = STYLE["blocks"]["width"]
    timeline_x = STYLE["timeline"]["x"]
    gap_from_timeline = 105

    if side == "left":
        x = timeline_x - gap_from_timeline - block_width
        align = "right"
        connector_start = x + block_width + 10
        connector_end = timeline_x - STYLE["timeline"]["circle_radius"] - 8
    else:
        x = timeline_x + gap_from_timeline
        align = "left"
        connector_start = timeline_x + STYLE["timeline"]["circle_radius"] + 8
        connector_end = x - 10

    block_height = measure_week_block(draw, week)
    y = center_y - block_height // 2

    # Connector line
    draw.line(
        [(connector_start, center_y), (connector_end, center_y)],
        fill=palette["green"],
        width=STYLE["timeline"]["connector_width"],
    )

    date_lines = wrap_text(draw, week["date_label"], FONTS["date"], block_width)
    title_lines = wrap_text(draw, week["title"], FONTS["week_title"], block_width)
    detail_lines = wrap_text(draw, week["detail"], FONTS["detail"], block_width)

    current_y = y
    current_y = draw_wrapped_text(draw, x, current_y, date_lines, FONTS["date"], palette["green"], STYLE["text"]["line_spacing"], align, block_width)
    current_y += STYLE["blocks"]["date_title_gap"]
    current_y = draw_wrapped_text(draw, x, current_y, title_lines, FONTS["week_title"], palette["text"], STYLE["text"]["line_spacing"], align, block_width)
    current_y += STYLE["blocks"]["title_detail_gap"]
    current_y = draw_wrapped_text(draw, x, current_y, detail_lines, FONTS["detail"], palette["text"], STYLE["text"]["line_spacing"], align, block_width)

    if week.get("render_pill") and week.get("assessment", "").strip():
        current_y += STYLE["blocks"]["pill_gap"]
        draw_pill(draw, x, current_y, week["assessment"], side)


def draw_week_node(draw: ImageDraw.ImageDraw, week_number: int, y: int) -> None:
    palette = STYLE["palette"]
    x = STYLE["timeline"]["x"]
    r = STYLE["timeline"]["circle_radius"]
    rect = [x - r, y - r, x + r, y + r]
    draw.ellipse(rect, fill=palette["green"])

    label = str(week_number)
    w, h = text_size(draw, label, FONTS["circle"])
    draw.text((x - w // 2, y - h // 2 - 2), label, font=FONTS["circle"], fill=palette["white"])


# ---------------------------
# Render
# ---------------------------

def render_journey_map(data: dict, output_png: Path, output_pdf: Path | None = None) -> None:
    weeks = data["weeks"]
    width = STYLE["canvas"]["width"]

    # Measurement pass
    tmp = Image.new("RGB", (width, 1000), STYLE["canvas"]["background"])
    draw = ImageDraw.Draw(tmp)

    gap = STYLE["timeline"]["week_gap"]
    top = STYLE["canvas"]["top_padding"] + 120
    bottom = STYLE["canvas"]["bottom_padding"]
    height = top + (len(weeks) - 1) * gap + bottom + 120

    image = Image.new("RGB", (width, height), STYLE["canvas"]["background"])
    draw = ImageDraw.Draw(image)
    palette = STYLE["palette"]

    y = 70
    y = draw_centered_text(draw, y, data["module_title"], FONTS["title"], palette["green"], width)
    y += 16
    y = draw_centered_text(draw, y, "Learner Journey Map", FONTS["subtitle"], palette["text"], width)

    ys = [top + i * gap for i in range(len(weeks))]

    # Main timeline line
    if ys:
        draw.line(
            [(STYLE["timeline"]["x"], ys[0]), (STYLE["timeline"]["x"], ys[-1])],
            fill=palette["line"],
            width=STYLE["timeline"]["line_width"],
        )

    for idx, week in enumerate(weeks):
        side = "left" if idx % 2 == 0 else "right"
        draw_week_block(draw, week, ys[idx], side)
        draw_week_node(draw, int(week["week"]), ys[idx])

    footer = data.get("module_title", "")
    if footer:
        foot = f"{footer}"
        fw, fh = text_size(draw, foot, FONTS["footer"])
        draw.text(((width - fw) // 2, height - bottom // 2), foot, font=FONTS["footer"], fill=palette["muted"])

    output_png.parent.mkdir(parents=True, exist_ok=True)

    final_image = image.resize(
        (
            image.width // RENDER_SCALE,
            image.height // RENDER_SCALE,
        ),
        Image.Resampling.LANCZOS,
    )

    final_image.save(output_png, "PNG")

    if output_pdf:
        rgb = final_image.convert("RGB")
        output_pdf.parent.mkdir(parents=True, exist_ok=True)
        rgb.save(output_pdf, "PDF", resolution=150.0)


# ---------------------------
# Main
# ---------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Render a student-facing Journey Map PNG from extracted JSON.")
    parser.add_argument("--input", default=DEFAULT_INPUT, help="Input JSON from extractor")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="Output PNG path")
    parser.add_argument("--pdf", default=None, help="Optional output PDF path")
    parser.add_argument("--allow-warnings", action="store_true", help="Render even if extraction status is not APPROVED")
    args = parser.parse_args()

    input_path = Path(args.input).resolve()
    output_png = Path(args.output).resolve()
    output_pdf = Path(args.pdf).resolve() if args.pdf else None

    if not input_path.exists():
        print(f"[ERROR] Input JSON does not exist: {input_path}")
        return 1

    data = json.loads(input_path.read_text(encoding="utf-8"))
    status = data.get("extraction_status", "UNKNOWN")

    print(f"[INFO] Input JSON       : {input_path}")
    print(f"[INFO] Extraction status: {status}")
    print(f"[INFO] Output PNG       : {output_png}")

    if output_pdf:
        print(f"[INFO] Output PDF       : {output_pdf}")

    if status != "APPROVED" and not args.allow_warnings:
        print("[ERROR] Extraction is not APPROVED. Review the TXT file or rerun with --allow-warnings.")
        for issue in data.get("issues", []):
            print(f"       - {issue}")
        return 2

    render_journey_map(data, output_png, output_pdf)
    print(f"[OK] Wrote PNG: {output_png.name}")
    if output_pdf:
        print(f"[OK] Wrote PDF: {output_pdf.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
