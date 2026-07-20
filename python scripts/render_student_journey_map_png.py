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

from PIL import Image, ImageChops, ImageDraw, ImageFont


DEFAULT_INPUT = "../output/student_journey_data.json"
DEFAULT_OUTPUT = "../output/student_journey_map.png"
DEFAULT_PDF = "../output/student_journey_map.pdf"
RENDER_SCALE = 3
PROJECT_ROOT = Path(__file__).resolve().parent.parent

STYLE = {
    "canvas": {
        "width": 1600,
        "background": "#F4E9D8",
        "top_padding": 235,
        "bottom_padding": 160,
        "side_margin": 110,
    },
    "palette": {
        "green": "#1E6556",
        "green_dark": "#16483F",
        "text": "#1A1A1A",
        "muted": "#575757",
        "cream": "#F4E9D8",
        "white": "#F3F5F2",
        "line": "#D9C9F2",
        "node": "#D9C9F2",
        "accent": "#8A2F24",
    },
    "timeline": {
        "x": 800,
        "line_width": 10,
        "circle_radius": 56,
        "circle_stroke": 0,
        "connector_width": 5,
        "week_gap": 245,
        "assessment_ring": 28,
    },
    "text": {
        "title_size": 58,
        "subtitle_size": 34,
        "date_size": 30,
        "week_title_size": 30,
        "detail_size": 24,
        "pill_size": 30,
        "circle_size": 34,
        "footer_size": 20,
        "line_spacing": 8,
    },
    "blocks": {
        "width": 540,
        "date_title_gap": 10,
        "title_detail_gap": 14,
        "pill_gap": 22,
        "timeline_gap": 115,
    },
    "pill": {
        "padding_x": 28,
        "padding_y": 18,
        "radius": 30,
        "max_width": 520,
        "node_overlap": 10,
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

def find_font(names: str | list[str]) -> Path | None:
    if isinstance(names, str):
        names = [names]

    font_dirs = [
        PROJECT_ROOT / "assets" / "fonts",
        PROJECT_ROOT / "assets",
        Path("C:/Windows/Fonts"),
        Path.home() / "AppData" / "Local" / "Microsoft" / "Windows" / "Fonts",
        Path.home() / "AppData" / "Local" / "Adobe",
        Path.home() / "AppData" / "Roaming" / "Adobe",
        Path("C:/Program Files/Adobe"),
        Path("C:/Program Files/Common Files/Adobe"),
        Path("/usr/share/fonts/truetype/dejavu"),
        Path("/usr/share/fonts/truetype/liberation2"),
        Path("/usr/share/fonts/truetype/freefont"),
    ]

    for font_dir in font_dirs:
        for name in names:
            candidate = font_dir / name
            if candidate.exists():
                return candidate
    return None


def load_font(size: int, names: list[str], fallback: list[str] | None = None) -> ImageFont.FreeTypeFont:
    path = find_font(names)
    if not path and fallback:
        path = find_font(fallback)
    if path:
        return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


FONTS = {
    "title": load_font(
        STYLE["text"]["title_size"],
        ["magnole-regular.otf"],
        ["georgia.ttf", "DejaVuSerif.ttf"],
    ),
    "subtitle": load_font(
        STYLE["text"]["subtitle_size"],
        ["magnole-regular.otf"],
        ["georgia.ttf", "DejaVuSerif.ttf"],
    ),
    "date": load_font(
        STYLE["text"]["date_size"],
        ["AvenirNextLTPro-Bold.otf", "AvenirNextLTPro-Demi.otf"],
        ["candarab.ttf", "calibrib.ttf", "verdanab.ttf", "arialbd.ttf"],
    ),
    "week_title": load_font(
        STYLE["text"]["week_title_size"],
        ["AvenirNextLTPro-Bold.otf", "AvenirNextLTPro-Demi.otf"],
        ["candarab.ttf", "calibrib.ttf", "verdanab.ttf", "arialbd.ttf"],
    ),
    "detail": load_font(
        STYLE["text"]["detail_size"],
        ["AvenirNextLTPro-Regular.otf", "AvenirNextLTPro-Mediumlt.otf"],
        ["candara.ttf", "calibri.ttf", "verdana.ttf", "arial.ttf"],
    ),
    "pill": load_font(
        STYLE["text"]["pill_size"],
        ["AvenirNextLTPro-Bold.otf", "AvenirNextLTPro-Demi.otf"],
        ["candarab.ttf", "calibrib.ttf", "verdanab.ttf", "arialbd.ttf"],
    ),
    "circle": load_font(
        STYLE["text"]["circle_size"],
        ["OpenSans_Condensed-Bold.ttf"],
        ["bahnschrift.ttf", "verdanab.ttf"],
    ),
    "footer": load_font(
        STYLE["text"]["footer_size"],
        ["AvenirNextLTPro-Regular.otf"],
        ["candara.ttf", "calibri.ttf", "verdana.ttf", "arial.ttf"],
    ),
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


def centered_text_y(draw: ImageDraw.ImageDraw, center_y: int, text: str, font: ImageFont.ImageFont) -> int:
    bbox = draw.textbbox((0, 0), text, font=font)
    text_height = bbox[3] - bbox[1]
    return center_y - text_height // 2 - 2


def compute_block_width(draw: ImageDraw.ImageDraw, weeks: list[dict]) -> int:
    widest_date = 0
    for week in weeks:
        label = week.get("date_label", "")
        w, _ = text_size(draw, label, FONTS["date"])
        widest_date = max(widest_date, w)

    return max(320, widest_date + 34)


def draw_pill(draw: ImageDraw.ImageDraw, x: int, y: int, text: str, side: str) -> int:
    palette = STYLE["palette"]
    max_width = STYLE["pill"]["max_width"]
    lines, width, height = pill_size(draw, text, max_width)
    timeline_x = STYLE["timeline"]["x"]
    node_outer_radius = STYLE["timeline"]["circle_radius"] + STYLE["timeline"]["assessment_ring"]
    node_overlap = STYLE["pill"]["node_overlap"]

    if side == "left":
        rect_x = timeline_x - node_outer_radius + node_overlap - width
    else:
        rect_x = timeline_x + node_outer_radius - node_overlap

    rect = [rect_x, y, rect_x + width, y + height]
    draw.rounded_rectangle(rect, radius=STYLE["pill"]["radius"], fill=palette["green"])

    lines_heights = [text_size(draw, line, FONTS["pill"])[1] for line in lines]
    total_text_height = sum(lines_heights) + max(0, len(lines) - 1) * 5
    text_y = y + max(0, (height - total_text_height) // 2) - 14
    for line in lines:
        tw, th = text_size(draw, line, FONTS["pill"])
        draw.text((rect_x + (width - tw) // 2, text_y), line, font=FONTS["pill"], fill=palette["white"])
        text_y += th + 5

    return y + height


def opposite_side(side: str) -> str:
    return "right" if side == "left" else "left"


def measure_week_block(draw: ImageDraw.ImageDraw, week: dict, block_width: int) -> int:
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

    return max(height, 145)


def draw_week_block(draw: ImageDraw.ImageDraw, week: dict, center_y: int, side: str, block_width: int) -> None:
    palette = STYLE["palette"]
    timeline_x = STYLE["timeline"]["x"]
    gap_from_timeline = STYLE["blocks"]["timeline_gap"]
    left_gap_from_timeline = max(72, gap_from_timeline - 40)

    if side == "left":
        x = timeline_x - left_gap_from_timeline - block_width
        align = "right"
    else:
        x = timeline_x + gap_from_timeline
        align = "left"

    block_height = measure_week_block(draw, week, block_width)
    y = center_y - block_height // 2

    date_lines = wrap_text(draw, week["date_label"], FONTS["date"], block_width)
    title_lines = wrap_text(draw, week["title"], FONTS["week_title"], block_width)
    detail_lines = wrap_text(draw, week["detail"], FONTS["detail"], block_width)

    current_y = y
    current_y = draw_wrapped_text(draw, x, current_y, date_lines, FONTS["date"], palette["text"], STYLE["text"]["line_spacing"], "left", block_width)
    current_y += STYLE["blocks"]["date_title_gap"]
    current_y = draw_wrapped_text(draw, x, current_y, title_lines, FONTS["week_title"], palette["text"], STYLE["text"]["line_spacing"], "left", block_width)
    current_y += STYLE["blocks"]["title_detail_gap"]
    current_y = draw_wrapped_text(draw, x, current_y, detail_lines, FONTS["detail"], palette["text"], STYLE["text"]["line_spacing"], "left", block_width)

    if week.get("render_pill") and week.get("assessment", "").strip():
        _, _, pill_height = pill_size(draw, week["assessment"], STYLE["pill"]["max_width"])
        pill_y = center_y - pill_height // 2 - 2
        draw_pill(draw, x, pill_y, week["assessment"], opposite_side(side))


def draw_week_node(draw: ImageDraw.ImageDraw, week_number: int, y: int, highlighted: bool = False) -> None:
    palette = STYLE["palette"]
    x = STYLE["timeline"]["x"]
    r = STYLE["timeline"]["circle_radius"]
    rect = [x - r, y - r, x + r, y + r]

    if highlighted:
        outer_r = r + STYLE["timeline"]["assessment_ring"]
        outer_rect = [x - outer_r, y - outer_r, x + outer_r, y + outer_r]
        draw.ellipse(outer_rect, fill=palette["green"])

    draw.ellipse(rect, fill=palette["node"])

    label = str(week_number)
    w, h = text_size(draw, label, FONTS["circle"])
    label_fill = palette["accent"] if highlighted else palette["text"]
    draw.text((x - w // 2, y - h // 2 - 8), label, font=FONTS["circle"], fill=label_fill)


# ---------------------------
# Render
# ---------------------------

def render_journey_map(data: dict, output_png: Path, output_pdf: Path | None = None) -> None:
    weeks = data["weeks"]
    width = STYLE["canvas"]["width"]

    # Measurement pass
    tmp = Image.new("RGB", (width, 1000), STYLE["canvas"]["background"])
    draw = ImageDraw.Draw(tmp)
    block_width = compute_block_width(draw, weeks)

    gap = STYLE["timeline"]["week_gap"]
    top = STYLE["canvas"]["top_padding"] + 120
    bottom = STYLE["canvas"]["bottom_padding"]
    height = top + (len(weeks) - 1) * gap + bottom + 120

    image = Image.new("RGB", (width, height), STYLE["canvas"]["background"])
    draw = ImageDraw.Draw(image)
    palette = STYLE["palette"]

    y = 70
    y = draw_centered_text(draw, y, data["module_title"], FONTS["title"], palette["text"], width)
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
        draw_week_block(draw, week, ys[idx], side, block_width)
        draw_week_node(draw, int(week["week"]), ys[idx], bool(week.get("render_pill")))

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

    background = Image.new(final_image.mode, final_image.size, STYLE["canvas"]["background"])
    diff = ImageChops.difference(final_image, background)
    bbox = diff.getbbox()
    if bbox:
        left, top_crop, right, bottom_crop = bbox
        pad = 24
        left = max(0, left - pad)
        top_crop = max(0, top_crop - pad)
        right = min(final_image.width, right + pad)
        bottom_crop = min(final_image.height, bottom_crop + pad)
        final_image = final_image.crop((left, top_crop, right, bottom_crop))

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
