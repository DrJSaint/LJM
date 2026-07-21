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
import re
from pathlib import Path
from typing import List, Mapping, Tuple, cast

from PIL import Image, ImageChops, ImageDraw, ImageFont


DEFAULT_INPUT = "../output/student_journey_data.json"
DEFAULT_OUTPUT = "../output/student_journey_map.png"
DEFAULT_PDF = "../output/student_journey_map.pdf"
RENDER_SCALE = 6
PRINT_SCALE = 3  # multiplies the final delivered resolution beyond the 800px design width
FINAL_DOWNSCALE = RENDER_SCALE / PRINT_SCALE
PDF_BASE_RESOLUTION = 150.0
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CROP_TO_CONTENT = False
STANDARD_OUTPUT_HEIGHT = 2000
DEFAULT_LAYOUT_MODE = "flex-height"
LAYOUT_MODES = ("standard", "fit-fixed", "flex-height")
FIT_FIXED_MIN_DETAIL_SIZE = 12 * RENDER_SCALE
# Keep pills more visually stable in fixed mode; let detail absorb more pressure first.
FIT_FIXED_MIN_PILL_SIZE = 14 * RENDER_SCALE
FIT_FIXED_STEP = 1 * RENDER_SCALE
FLEX_HEADER_CLEARANCE = 40 * RENDER_SCALE
FLEX_BOTTOM_PADDING = 20 * RENDER_SCALE
FLEX_BOTTOM_EXTRA = 0

# A handful of pixel offsets below were tuned by eye at RENDER_SCALE=3 and aren't
# derived from STYLE, so they're re-based here to stay proportional if RENDER_SCALE changes.
_LEGACY_RENDER_SCALE = 3


def _legacy_scaled(value: float) -> int:
    return round(value * RENDER_SCALE / _LEGACY_RENDER_SCALE)


HEADER_CLEARANCE = _legacy_scaled(26)
LANE_CLEARANCE = _legacy_scaled(18)
TITLE_START_Y = _legacy_scaled(90)
TITLE_SUBTITLE_GAP = _legacy_scaled(16)
TIMELINE_TOP_OFFSET = _legacy_scaled(120)
MIN_BLOCK_WIDTH = _legacy_scaled(320)
BLOCK_WIDTH_DATE_PADDING = _legacy_scaled(34)
MIN_BLOCK_HEIGHT = _legacy_scaled(145)
TIMELINE_GAP_MIN = _legacy_scaled(72)
TIMELINE_GAP_REDUCTION = _legacy_scaled(40)
NODE_LABEL_Y_OFFSET = _legacy_scaled(20)
TEXT_BASELINE_NUDGE = _legacy_scaled(2)

STYLE = {
    "canvas": {
        "width": 800,
        "background": "#F7F1E8",
        "top_padding": 200,
        "bottom_padding": 70,
        "side_margin": 110,
    },
    "palette": {
        "green": "#195C4D",
        "green_dark": "#195C4D",
        "text": "#171F20",
        "muted": "#171F20",
        "cream": "#F7F1E8",
        "white": "#F7F1E8",
        "line": "#D8CBF1",
        "node": "#D8CBF1",
        "accent": "#710704",
    },
    "timeline": {
        "x": 400,
        "line_width": 5,
        "circle_radius": 42,
        "circle_stroke": 0,
        "connector_width": 5,
        "week_gap": 150,
        "assessment_ring": 17,
    },
    "text": {
        "title_size": 30,
        "subtitle_size": 30,
        "date_size": 16,
        "week_title_size": 16,
        "detail_size": 16,
        "pill_size": 16,
        "circle_size": 26,
        "footer_size": 20,
        "line_spacing": 8,
    },
    "blocks": {
        "width": 540,
        "date_title_gap": 4,
        "title_detail_gap": 14,
        "pill_gap": 22,
        "timeline_gap": 90,
    },
    "pill": {
        "padding_x": 20,
        "padding_y": 18,
        "radius": 30,
        "max_width": 320,
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
AVENIR_OPTICAL_COMP_FINAL_PX = 5
AVENIR_OPTICAL_COMP = AVENIR_OPTICAL_COMP_FINAL_PX * RENDER_SCALE
MAGNOLE_OPTICAL_COMP_FINAL_PX = 1
MAGNOLE_OPTICAL_COMP = MAGNOLE_OPTICAL_COMP_FINAL_PX * RENDER_SCALE

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


def load_font(size: int, names: list[str], fallback: list[str] | None = None) -> ImageFont.ImageFont:
    path = find_font(names)
    if not path and fallback:
        path = find_font(fallback)
    if path:
        return cast(ImageFont.ImageFont, ImageFont.truetype(str(path), size=size))
    return cast(ImageFont.ImageFont, ImageFont.load_default())


def build_fonts(text_sizes: dict[str, int] | None = None) -> dict[str, ImageFont.ImageFont]:
    sizes = dict(STYLE["text"])
    if text_sizes:
        sizes.update(text_sizes)

    return {
        "title": load_font(
            sizes["title_size"] + MAGNOLE_OPTICAL_COMP,
            ["magnole-regular.otf"],
            ["georgia.ttf", "DejaVuSerif.ttf"],
        ),
        "subtitle": load_font(
            sizes["subtitle_size"] + MAGNOLE_OPTICAL_COMP,
            ["magnole-regular.otf"],
            ["georgia.ttf", "DejaVuSerif.ttf"],
        ),
        "date": load_font(
            sizes["date_size"] + AVENIR_OPTICAL_COMP,
            ["AvenirNextLTPro-Bold.otf", "AvenirNextLTPro-Demi.otf"],
            ["candarab.ttf", "calibrib.ttf", "verdanab.ttf", "arialbd.ttf"],
        ),
        "week_title": load_font(
            sizes["week_title_size"] + AVENIR_OPTICAL_COMP,
            ["AvenirNextLTPro-Bold.otf", "AvenirNextLTPro-Demi.otf"],
            ["candarab.ttf", "calibrib.ttf", "verdanab.ttf", "arialbd.ttf"],
        ),
        "detail": load_font(
            sizes["detail_size"] + AVENIR_OPTICAL_COMP,
            ["AvenirNextLTPro-Regular.otf", "AvenirNextLTPro-Mediumlt.otf"],
            ["candara.ttf", "calibri.ttf", "verdana.ttf", "arial.ttf"],
        ),
        "pill": load_font(
            sizes["pill_size"] + AVENIR_OPTICAL_COMP,
            ["AvenirNextLTPro-Bold.otf", "AvenirNextLTPro-Demi.otf"],
            ["candarab.ttf", "calibrib.ttf", "verdanab.ttf", "arialbd.ttf"],
        ),
        "circle": load_font(
            sizes["circle_size"],
            ["OpenSans_Condensed-Bold.ttf"],
            ["bahnschrift.ttf", "verdanab.ttf"],
        ),
        "footer": load_font(
            sizes["footer_size"] + AVENIR_OPTICAL_COMP,
            ["AvenirNextLTPro-Regular.otf"],
            ["candara.ttf", "calibri.ttf", "verdana.ttf", "arial.ttf"],
        ),
    }


FONTS = build_fonts()


# ---------------------------
# Drawing helpers
# ---------------------------

def text_size(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> Tuple[int, int]:
    if not text:
        return 0, 0
    bbox = draw.textbbox((0, 0), text, font=font)
    return int(bbox[2] - bbox[0]), int(bbox[3] - bbox[1])


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


def pill_size(draw: ImageDraw.ImageDraw, text: str, max_width: int, fonts: Mapping[str, ImageFont.ImageFont]) -> Tuple[List[str], int, int]:
    lines = wrap_text(draw, text, fonts["pill"], max_width - 2 * STYLE["pill"]["padding_x"])
    line_heights = [text_size(draw, line, fonts["pill"])[1] for line in lines] or [0]
    width = 0
    for line in lines:
        w, _ = text_size(draw, line, fonts["pill"])
        width = max(width, w)
    width += 2 * STYLE["pill"]["padding_x"]
    height = sum(line_heights) + (len(lines) - 1) * 5 + 2 * STYLE["pill"]["padding_y"]
    width = min(width, max_width)
    return lines, width, height


def centered_text_y(draw: ImageDraw.ImageDraw, center_y: int, text: str, font: ImageFont.ImageFont) -> int:
    bbox = draw.textbbox((0, 0), text, font=font)
    text_height = int(bbox[3] - bbox[1])
    return center_y - text_height // 2 - TEXT_BASELINE_NUDGE


def compute_block_width(draw: ImageDraw.ImageDraw, weeks: list[dict], fonts: Mapping[str, ImageFont.ImageFont]) -> int:
    widest_date = 0
    for week in weeks:
        label = week.get("date_label", "")
        w, _ = text_size(draw, label, fonts["date"])
        widest_date = max(widest_date, w)

    return max(MIN_BLOCK_WIDTH, widest_date + BLOCK_WIDTH_DATE_PADDING)


def draw_pill(draw: ImageDraw.ImageDraw, x: int, y: int, text: str, side: str, fonts: Mapping[str, ImageFont.ImageFont]) -> int:
    palette = STYLE["palette"]
    max_width = STYLE["pill"]["max_width"]
    lines, width, height = pill_size(draw, text, max_width, fonts)
    timeline_x = STYLE["timeline"]["x"]
    node_outer_radius = STYLE["timeline"]["circle_radius"]
    node_overlap = STYLE["pill"]["node_overlap"]

    if side == "left":
        rect_x = timeline_x - node_outer_radius + node_overlap - width
    else:
        rect_x = timeline_x + node_outer_radius - node_overlap

    rect = [rect_x, y, rect_x + width, y + height]
    draw.rounded_rectangle(rect, radius=STYLE["pill"]["radius"], fill=palette["green"])

    lines_heights = [text_size(draw, line, fonts["pill"])[1] for line in lines]
    total_text_height = sum(lines_heights) + max(0, len(lines) - 1) * 5
    text_y = y + max(0, (height - total_text_height) // 2) - TEXT_BASELINE_NUDGE
    text_x = rect_x + STYLE["pill"]["padding_x"]
    for line in lines:
        _, th = text_size(draw, line, fonts["pill"])
        draw.text((text_x, text_y), line, font=fonts["pill"], fill=palette["white"])
        text_y += th + 5

    return y + height


def opposite_side(side: str) -> str:
    return "right" if side == "left" else "left"


def measure_week_block(draw: ImageDraw.ImageDraw, week: dict, block_width: int, fonts: Mapping[str, ImageFont.ImageFont]) -> int:
    line_spacing = STYLE["text"]["line_spacing"]

    date_lines = wrap_text(draw, week["date_label"], fonts["date"], block_width)
    title_lines = wrap_text(draw, week["title"], fonts["week_title"], block_width)
    detail_lines = wrap_text(draw, week["detail"], fonts["detail"], block_width)

    height = 0
    for lines, font in [(date_lines, fonts["date"]), (title_lines, fonts["week_title"]), (detail_lines, fonts["detail"] )]:
        for line in lines:
            _, h = text_size(draw, line, font)
            height += h + line_spacing

    height += STYLE["blocks"]["date_title_gap"] + STYLE["blocks"]["title_detail_gap"]

    return max(height, MIN_BLOCK_HEIGHT)


def draw_week_block(draw: ImageDraw.ImageDraw, week: dict, center_y: int, side: str, block_width: int, fonts: Mapping[str, ImageFont.ImageFont]) -> None:
    palette = STYLE["palette"]
    timeline_x = STYLE["timeline"]["x"]
    gap_from_timeline = STYLE["blocks"]["timeline_gap"]
    left_gap_from_timeline = max(TIMELINE_GAP_MIN, gap_from_timeline - TIMELINE_GAP_REDUCTION)

    if side == "left":
        x = timeline_x - left_gap_from_timeline - block_width
        align = "left"
    else:
        x = timeline_x + gap_from_timeline
        align = "left"

    block_height = measure_week_block(draw, week, block_width, fonts)
    y = center_y - block_height // 2

    date_lines = wrap_text(draw, week["date_label"], fonts["date"], block_width)
    title_lines = wrap_text(draw, week["title"], fonts["week_title"], block_width)
    detail_lines = wrap_text(draw, week["detail"], fonts["detail"], block_width)

    current_y = y
    current_y = draw_wrapped_text(draw, x, current_y, date_lines, fonts["date"], palette["text"], STYLE["text"]["line_spacing"], align, block_width)
    current_y += STYLE["blocks"]["date_title_gap"]
    current_y = draw_wrapped_text(draw, x, current_y, title_lines, fonts["week_title"], palette["text"], STYLE["text"]["line_spacing"], align, block_width)
    current_y += STYLE["blocks"]["title_detail_gap"]
    current_y = draw_wrapped_text(draw, x, current_y, detail_lines, fonts["detail"], palette["text"], STYLE["text"]["line_spacing"], align, block_width)

    if week.get("render_pill") and week.get("assessment", "").strip():
        _, _, pill_height = pill_size(draw, week["assessment"], STYLE["pill"]["max_width"], fonts)
        pill_y = center_y - pill_height // 2 - TEXT_BASELINE_NUDGE
        draw_pill(draw, x, pill_y, week["assessment"], opposite_side(side), fonts)


def draw_week_node(draw: ImageDraw.ImageDraw, week_number: int, y: int, highlighted: bool = False, fonts: Mapping[str, ImageFont.ImageFont] | None = None) -> None:
    active_fonts = fonts or FONTS
    palette = STYLE["palette"]
    x = STYLE["timeline"]["x"]
    r = STYLE["timeline"]["circle_radius"]
    rect = [x - r, y - r, x + r, y + r]

    if highlighted:
        draw.ellipse(rect, fill=palette["green"])
        inner_r = max(10, r - STYLE["timeline"]["assessment_ring"])
        inner_rect = [x - inner_r, y - inner_r, x + inner_r, y + inner_r]
        draw.ellipse(inner_rect, fill=palette["node"])
    else:
        draw.ellipse(rect, fill=palette["node"])

    label = str(week_number)
    w, h = text_size(draw, label, active_fonts["circle"])
    label_fill = palette["accent"] if highlighted else palette["text"]
    draw.text((x - w // 2, y - h // 2 - NODE_LABEL_Y_OFFSET), label, font=active_fonts["circle"], fill=label_fill)


def measure_header_bottom(draw: ImageDraw.ImageDraw, data: dict, fonts: Mapping[str, ImageFont.ImageFont]) -> int:
    y = TITLE_START_Y
    y = draw_centered_text(draw, y, data["module_title"], fonts["title"], STYLE["palette"]["text"], STYLE["canvas"]["width"])
    y += TITLE_SUBTITLE_GAP
    y = draw_centered_text(draw, y, "Learner Journey Map", fonts["subtitle"], STYLE["palette"]["text"], STYLE["canvas"]["width"])
    return y


def week_side(index: int) -> str:
    return "left" if index % 2 == 0 else "right"


def measure_week_layout(draw: ImageDraw.ImageDraw, week: dict, block_width: int, side: str, fonts: Mapping[str, ImageFont.ImageFont]) -> dict:
    block_height = measure_week_block(draw, week, block_width, fonts)
    pill_height = 0
    pill_side = None
    if week.get("render_pill") and week.get("assessment", "").strip():
        pill_side = opposite_side(side)
        _, _, pill_height = pill_size(draw, week["assessment"], STYLE["pill"]["max_width"], fonts)

    lane_heights = {"left": 0, "right": 0}
    lane_types: dict[str, str | None] = {"left": None, "right": None}
    lane_heights[side] = block_height
    lane_types[side] = "block"
    if pill_side:
        lane_heights[pill_side] = pill_height
        lane_types[pill_side] = "pill"

    return {
        "side": side,
        "block_height": block_height,
        "pill_height": pill_height,
        "pill_side": pill_side,
        "lane_heights": lane_heights,
        "lane_types": lane_types,
    }


def compute_fixed_centers(count: int) -> list[int]:
    top = STYLE["canvas"]["top_padding"] + TIMELINE_TOP_OFFSET
    gap = STYLE["timeline"]["week_gap"]
    return [top + i * gap for i in range(count)]


def compute_flex_centers(layouts: list[dict], header_bottom: int) -> list[int]:
    if not layouts:
        return []

    gap = STYLE["timeline"]["week_gap"]
    top = STYLE["canvas"]["top_padding"] + TIMELINE_TOP_OFFSET
    first_half = max(
        STYLE["timeline"]["circle_radius"],
        layouts[0]["lane_heights"]["left"] // 2,
        layouts[0]["lane_heights"]["right"] // 2,
    )
    centers = [max(top, header_bottom + FLEX_HEADER_CLEARANCE + first_half)]

    for idx in range(1, len(layouts)):
        required_gap = gap
        for side in ("left", "right"):
            previous_height = layouts[idx - 1]["lane_heights"][side]
            current_height = layouts[idx]["lane_heights"][side]
            if previous_height and current_height:
                required_gap = max(required_gap, previous_height // 2 + current_height // 2 + LANE_CLEARANCE)
        centers.append(centers[-1] + required_gap)

    return centers


def compute_image_height(centers: list[int], layouts: list[dict], bottom_extra: int = 120, bottom_padding: int | None = None) -> int:
    if not centers:
        return STANDARD_OUTPUT_HEIGHT * RENDER_SCALE

    bottom = STYLE["canvas"]["bottom_padding"] if bottom_padding is None else bottom_padding
    node_radius = STYLE["timeline"]["circle_radius"]
    content_bottom = 0
    for center_y, layout in zip(centers, layouts):
        content_bottom = max(
            content_bottom,
            center_y + node_radius,
            center_y + layout["lane_heights"]["left"] // 2,
            center_y + layout["lane_heights"]["right"] // 2,
        )
    return content_bottom + bottom + bottom_extra


def compute_standard_image_height(count: int) -> int:
    if count <= 0:
        return STANDARD_OUTPUT_HEIGHT * RENDER_SCALE

    gap = STYLE["timeline"]["week_gap"]
    top = STYLE["canvas"]["top_padding"] + TIMELINE_TOP_OFFSET
    bottom = STYLE["canvas"]["bottom_padding"]
    return top + (count - 1) * gap + bottom + 120


def detect_fit_fixed_issues(layouts: list[dict], centers: list[int], header_bottom: int) -> list[dict]:
    issues: list[dict] = []
    if layouts and centers:
        for side in ("left", "right"):
            lane_height = layouts[0]["lane_heights"][side]
            lane_type = layouts[0]["lane_types"][side]
            if lane_height and centers[0] - lane_height // 2 < header_bottom + HEADER_CLEARANCE:
                issues.append({"week_index": 0, "side": side, "kind": "header", "target": lane_type})

    # Compare each side independently across all week positions. In alternating timelines,
    # the nearest collision risk is often two weeks apart on the same side.
    for side in ("left", "right"):
        side_indices = [idx for idx, layout in enumerate(layouts) if layout["lane_heights"][side] > 0]
        for prev_idx, curr_idx in zip(side_indices, side_indices[1:]):
            center_gap = centers[curr_idx] - centers[prev_idx]
            previous_height = layouts[prev_idx]["lane_heights"][side]
            current_height = layouts[curr_idx]["lane_heights"][side]
            minimum_gap = previous_height // 2 + current_height // 2 + LANE_CLEARANCE
            if center_gap < minimum_gap:
                issues.append({
                    "week_index": curr_idx,
                    "side": side,
                    "kind": "lane",
                    "prev_week_index": prev_idx,
                    "prev_target": layouts[prev_idx]["lane_types"][side],
                    "target": layouts[curr_idx]["lane_types"][side],
                })
    return issues


def fit_fixed_overrides(draw: ImageDraw.ImageDraw, weeks: list[dict], block_width: int, header_bottom: int) -> tuple[list[dict[str, int]], list[str]]:
    overrides = [{"detail_size": STYLE["text"]["detail_size"], "pill_size": STYLE["text"]["pill_size"]} for _ in weeks]
    centers = compute_fixed_centers(len(weeks))
    warnings: list[str] = []
    detail_shrinks = 0
    pill_shrinks = 0
    unresolved = False

    def try_shrink(week_index: int, target: str | None) -> bool:
        nonlocal detail_shrinks, pill_shrinks
        if target == "block" and overrides[week_index]["detail_size"] > FIT_FIXED_MIN_DETAIL_SIZE:
            overrides[week_index]["detail_size"] -= FIT_FIXED_STEP
            detail_shrinks += 1
            return True
        if target == "pill" and overrides[week_index]["pill_size"] > FIT_FIXED_MIN_PILL_SIZE:
            overrides[week_index]["pill_size"] -= FIT_FIXED_STEP
            pill_shrinks += 1
            return True
        return False

    for _ in range(500):
        layouts = [
            measure_week_layout(draw, week, block_width, week_side(idx), build_fonts(overrides[idx]))
            for idx, week in enumerate(weeks)
        ]
        issues = detect_fit_fixed_issues(layouts, centers, header_bottom)
        if not issues:
            break

        changed = False
        for issue in issues:
            candidates: list[tuple[int, str | None]] = []
            if issue["kind"] == "lane" and issue.get("prev_week_index") is not None:
                candidates.append((issue["prev_week_index"], issue.get("prev_target")))
            candidates.append((issue["week_index"], issue.get("target")))

            # Prefer shrinking detail blocks before pill text when resolving crowding.
            candidates.sort(key=lambda item: 0 if item[1] == "block" else 1)

            for week_index, target in candidates:
                if try_shrink(week_index, target):
                    changed = True
                    break
            if changed:
                break
        if not changed:
            unresolved = True
            break

    if detail_shrinks:
        warnings.append(f"detail text reduced {detail_shrinks} step(s) to preserve fixed canvas.")
    if pill_shrinks:
        warnings.append(f"pill text reduced {pill_shrinks} step(s) to preserve fixed canvas.")
    if unresolved:
        warnings.append("some content still risks crowding at minimum fixed-canvas text sizes.")

    return overrides, warnings


# ---------------------------
# Render
# ---------------------------

def render_journey_map(data: dict, output_png: Path, output_pdf: Path | None = None, layout_mode: str = DEFAULT_LAYOUT_MODE) -> list[str]:
    weeks = data["weeks"]
    width = STYLE["canvas"]["width"]
    warnings: list[str] = []

    # Measurement pass
    tmp = Image.new("RGB", (width, 1000), STYLE["canvas"]["background"])
    draw = ImageDraw.Draw(tmp)
    block_width = compute_block_width(draw, weeks, FONTS)
    header_bottom = measure_header_bottom(draw, data, FONTS)

    if layout_mode == "fit-fixed":
        week_overrides, fit_warnings = fit_fixed_overrides(draw, weeks, block_width, header_bottom)
        warnings.extend(fit_warnings)
        week_fonts = [build_fonts(overrides) for overrides in week_overrides]
    else:
        week_fonts = [FONTS for _ in weeks]

    layouts = [
        measure_week_layout(draw, week, block_width, week_side(idx), week_fonts[idx])
        for idx, week in enumerate(weeks)
    ]

    if layout_mode == "flex-height":
        ys = compute_flex_centers(layouts, header_bottom)
        height = compute_image_height(ys, layouts, FLEX_BOTTOM_EXTRA, FLEX_BOTTOM_PADDING)
    else:
        ys = compute_fixed_centers(len(weeks))
        height = compute_standard_image_height(len(weeks))

    image = Image.new("RGB", (width, height), STYLE["canvas"]["background"])
    draw = ImageDraw.Draw(image)
    palette = STYLE["palette"]

    y = TITLE_START_Y
    y = draw_centered_text(draw, y, data["module_title"], FONTS["title"], palette["text"], width)
    y += TITLE_SUBTITLE_GAP
    y = draw_centered_text(draw, y, "Learner Journey Map", FONTS["subtitle"], palette["text"], width)

    # Main timeline line
    if ys:
        draw.line(
            [(STYLE["timeline"]["x"], ys[0]), (STYLE["timeline"]["x"], ys[-1])],
            fill=palette["line"],
            width=STYLE["timeline"]["line_width"],
        )

    for idx, week in enumerate(weeks):
        side = week_side(idx)
        draw_week_block(draw, week, ys[idx], side, block_width, week_fonts[idx])
        draw_week_node(draw, int(week["week"]), ys[idx], bool(week.get("render_pill")), week_fonts[idx])

    output_png.parent.mkdir(parents=True, exist_ok=True)

    final_image = image.resize(
        (
            max(1, round(image.width / FINAL_DOWNSCALE)),
            max(1, round(image.height / FINAL_DOWNSCALE)),
        ),
        Image.Resampling.LANCZOS,
    )

    if CROP_TO_CONTENT:
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

    standard_height = STANDARD_OUTPUT_HEIGHT * PRINT_SCALE
    if layout_mode == "flex-height" and final_image.height > standard_height:
        warnings.append(
            f"layout mode flex-height expanded output height to {final_image.height}px from the standard {standard_height}px."
        )

    if output_pdf:
        rgb = final_image.convert("RGB")
        output_pdf.parent.mkdir(parents=True, exist_ok=True)
        rgb.save(output_pdf, "PDF", resolution=PDF_BASE_RESOLUTION * PRINT_SCALE)

    return warnings


# ---------------------------
# Main
# ---------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Render a student-facing Journey Map PNG from extracted JSON.")
    parser.add_argument("--input", default=DEFAULT_INPUT, help="Input JSON from extractor")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="Output PNG path")
    parser.add_argument("--pdf", default=None, help="Optional output PDF path")
    parser.add_argument("--allow-warnings", action="store_true", help="Render even if extraction status is not APPROVED")
    parser.add_argument("--layout-mode", default=DEFAULT_LAYOUT_MODE, choices=LAYOUT_MODES, help="Layout behavior: standard, fit-fixed, or flex-height")
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
    print(f"[INFO] Layout mode      : {args.layout_mode}")

    if output_pdf:
        print(f"[INFO] Output PDF       : {output_pdf}")

    if status != "APPROVED" and not args.allow_warnings:
        print("[ERROR] Extraction is not APPROVED. Review the TXT file or rerun with --allow-warnings.")
        for issue in data.get("issues", []):
            print(f"       - {issue}")
        return 2

    render_warnings = render_journey_map(data, output_png, output_pdf, args.layout_mode)
    print(f"[OK] Wrote PNG: {output_png.name}")
    if output_pdf:
        print(f"[OK] Wrote PDF: {output_pdf.name}")
    for warning in render_warnings:
        print(f"[WARN] {warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
