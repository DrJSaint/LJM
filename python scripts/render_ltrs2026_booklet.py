#!/usr/bin/env python3
"""
render_ltrs2026_booklet.py

Render LTRS schedule HTML outputs from parsed JSON.

Outputs:
- single-page HTML (continuous web layout)
- A4 two-side print layout (2 pages)
- A4 fold-card print layout (4 panels imposed on 2 sheets)
"""

from __future__ import annotations

import argparse
import base64
import json
from functools import lru_cache
from html import escape
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT_JSON = PROJECT_ROOT / "output" / "ltrs2026_parsed.json"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "output"
DEFAULT_BASE_NAME = "ltrs2026"

_ASSET_MIME_TYPES = {
    ".png": "image/png",
    ".otf": "font/otf",
    ".ttf": "font/ttf",
}


@lru_cache(maxsize=None)
def asset_data_uri(filename: str) -> str:
    # Embeds the asset directly in the HTML as a base64 data URI, so the file has
    # no dependency on a sibling assets/ folder — it stays correct if the HTML is
    # moved, emailed, or downloaded as a single file from the Streamlit app.
    # lru_cache avoids re-reading/re-encoding the same font file for every call site.
    path = PROJECT_ROOT / "assets" / filename
    mime = _ASSET_MIME_TYPES.get(path.suffix.lower(), "application/octet-stream")
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"

CREAM = "#F7F1E8"
DARK = "#171F20"
GREEN = "#195C4D"
BLUE = "#70ACE9"
LILAC = "#D8CBF1"
MAROON = "#710704"
WHITE = "#FFFFFF"
BORDER_GREY = "#999994"  # uniform border color, computed to match how the old translucent border looked over cream
SCREEN_PREVIEW_BACKDROP = "#D9D9D9"  # browser-only page-boundary backdrop, never printed
ROW_BREAK = "#EDF6EF"  # pale mint background for Refreshments Break rows

# Quick single-page/two-side toggles — change the value, regenerate, done.
PAGE_FOOTER_LOGO = "cp_gt.png"  # or "cp_bt.png" for the black-text variant
SCHEDULE_HEADER_RADIUS = "0"  # square corners; was "6px" for the original rounded banner


def e(value: object) -> str:
    if value is None:
        return ""
    return escape(str(value), quote=True)


def time_range(block: dict) -> str:
    start = block.get("start", "")
    end = block.get("end", "")
    if start and end:
        return f"{start}-{end}"
    return start or end or ""


def format_time_label(value: str) -> str:
    if not value:
        return ""
    parts = value.split(":")
    if len(parts) != 2:
        return value
    hour = int(parts[0])
    minute = parts[1]
    suffix = "am" if hour < 12 else "pm"
    hour12 = hour % 12
    if hour12 == 0:
        hour12 = 12
    return f"{hour12}:{minute}{suffix}"


def format_time_range_label(block: dict) -> str:
    start = block.get("start", "")
    end = block.get("end", "")
    if start and end:
        return f"{format_time_label(start)} - {format_time_label(end)}"
    return format_time_label(start or end)


def dedupe_non_blank(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = value.strip()
        if not text:
            continue
        if text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def build_onepager_rows(programme: list[dict]) -> list[dict]:
    rows: list[dict] = []

    for block in programme:
        block_type = block.get("type")
        time_text = format_time_range_label(block)

        if block_type == "event":
            title = block.get("title", "")
            lower = title.lower()
            label = "Event"
            row_kind = "event"
            if "break" in lower:
                label = "Break"
                row_kind = "break"
            elif "keynote" in lower:
              label = "Keynote"
              row_kind = "keynote"
            details: list[str] = []
            if block.get("presenter"):
                details.append(str(block["presenter"]))
            if block.get("chair"):
                details.append(f"Chair: {block['chair']}")

            rows.append({
                "kind": row_kind,
                "label": label,
                "time": time_text,
                "title": title,
                "details": details,
                "location": block.get("location", ""),
            })

        elif block_type == "workshop_block":
            workshops = block.get("items", [])
            rows.append({
                "kind": "parallel_workshops",
                "label": "Parallel workshops",
                "time": time_text,
                "title": block.get("title", "Parallel Workshops"),
            "location": "See tracks",
                "chair": block.get("chair", ""),
                "tracks": [
                    {
                        "title": item.get("title", "Workshop"),
                        "room": item.get("room", ""),
                        "chair": "",
                        "talks": [
                            {
                                "presenter": item.get("presenter", ""),
                                "title": "",
                            }
                        ],
                    }
                    for item in workshops
                ],
            })

        elif block_type == "plenary_block":
            talks = []
            for item in block.get("items", []):
                talks.append({
                    "presenter": item.get("presenters", ""),
                    "title": item.get("title", ""),
                })
            rows.append({
                "kind": "plenary",
                "label": "Plenary",
                "time": time_text,
                "title": block.get("title", "Plenary Session"),
                "location": block.get("location", ""),
                "chair": block.get("chair", ""),
                "talks": talks,
            })

        elif block_type == "presentation_session_block":
            sessions = block.get("sessions", [])
            rows.append({
                "kind": "parallel_sessions",
                "label": "Parallel sessions",
                "time": time_text,
                "title": block.get("title", "Parallel Presentation Sessions"),
            "location": "See tracks",
                "tracks": [
                    {
                        "title": session.get("theme", "Session"),
                        "room": session.get("room", ""),
                        "chair": session.get("chair", ""),
                        "talks": [
                            {
                                "presenter": talk.get("presenter", ""),
                                "title": talk.get("title", ""),
                            }
                            for talk in session.get("talks", [])
                        ],
                    }
                    for session in sessions
                ],
            })

    return rows


def render_talk_cell(talk: dict | None) -> str:
  if not talk:
    return '<div class="track-cell talk-cell"><div class="talk-body"></div></div>'

  presenter = str(talk.get("presenter", "")).strip()
  title = str(talk.get("title", "")).strip()
  title_html = f"<div class=\"talk-title\">{e(title)}</div>" if title else ""
  presenter_html = f"<div class=\"talk-presenter\">{e(presenter)}</div>" if presenter else ""
  return f'<div class="track-cell talk-cell"><div class="talk-body">{title_html}{presenter_html}</div></div>'


def render_track_grid(tracks: list[dict]) -> str:
  if not tracks:
    return ""

  max_talks = max((len(track.get("talks", [])) for track in tracks), default=0)

  header_cells = ""
  for track in tracks:
    chair_html = ""
    if track.get("chair"):
      chair_html = f"<div class=\"track-chair\">Chaired by: {e(track.get('chair', ''))}</div>"
    header_cells += f"""
    <div class="track-cell track-header-cell">
      <h4>{e(track.get('title', 'Track'))}</h4>
      <div class="track-room">{e(track.get('room', ''))}</div>
      {chair_html}
    </div>
    """

  talk_rows_html = ""
  for i in range(max_talks):
    row_cells = ""
    for track in tracks:
      talks = track.get("talks", [])
      row_cells += render_talk_cell(talks[i] if i < len(talks) else None)
    talk_rows_html += f'<div class="track-row">{row_cells}</div>'

  return f"""
  <div class="track-grid">
    <div class="track-row track-row-header">{header_cells}</div>
    {talk_rows_html}
  </div>
  """


def render_track_stack(tracks: list[dict]) -> str:
  # Fold-card's own dedicated track renderer — panels are too narrow for three
  # side-by-side columns, so tracks stack one under another instead. Deliberately
  # separate from render_track_grid() so a future two-pager change can't silently
  # break this panel again the way it did before this rebuild.
  if not tracks:
    return ""

  items_html = ""
  for track in tracks:
    chair_html = ""
    if track.get("chair"):
      chair_html = f"<div class=\"track-stack-chair\">Chaired by: {e(track.get('chair', ''))}</div>"

    talks_html = ""
    for talk in track.get("talks", []):
      presenter = str(talk.get("presenter", "")).strip()
      title = str(talk.get("title", "")).strip()
      title_html = f"<div class=\"talk-title\">{e(title)}</div>" if title else ""
      presenter_html = f"<div class=\"talk-presenter\">{e(presenter)}</div>" if presenter else ""
      talks_html += f"<li>{title_html}{presenter_html}</li>"

    items_html += f"""
    <div class="track-stack-item">
      <div class="track-stack-head">
        <span class="track-stack-title">{e(track.get('title', 'Track'))}</span>
        <span class="track-stack-room">{e(track.get('room', ''))}</span>
      </div>
      {chair_html}
      <ul class="track-stack-talks">{talks_html}</ul>
    </div>
    """

  return f'<div class="track-stack">{items_html}</div>'


def render_event_cell(row: dict, compact: bool = False) -> str:
    kind = row.get("kind")

    if kind == "parallel_workshops":
        return f"""
        <div class="event-shell">
          <h3>{e(row.get('title', ''))}</h3>
        </div>
        """

    if kind == "parallel_sessions":
        tracks = row.get("tracks", [])
        grid_html = render_track_stack(tracks) if compact else render_track_grid(tracks)
        return f"""
        <div class="event-shell">
          <h3>{e(row.get('title', ''))}</h3>
          <p class="event-note">Concurrent tracks run in this shared time slot.</p>
          {grid_html}
        </div>
        """

    if kind == "plenary":
      talks_html = ""
      for talk in row.get("talks", []):
        presenter = str(talk.get("presenter", "")).strip()
        title = str(talk.get("title", "")).strip()
        title_html = f"<div class=\"talk-title\">{e(title)}</div>" if title else ""
        presenter_html = f"<div class=\"talk-presenter\">{e(presenter)}</div>" if presenter else ""
        talks_html += f"<li>{title_html}{presenter_html}</li>"

      chair_html = ""
      if row.get("chair"):
        chair_html = f"<p class=\"event-note chair-note\">Chaired by: {e(row.get('chair', ''))}</p>"

      return f"""
      <div class="event-shell">
        <h3>{e(row.get('title', ''))}</h3>
        {chair_html}
        <ul class="talk-list plenary-list">{talks_html}</ul>
      </div>
      """

    details = row.get("details", [])
    detail_html = "".join(f"<div class=\"detail-line\">{e(detail)}</div>" for detail in details)
    detail_list = f"<div class=\"detail-lines\">{detail_html}</div>" if details else ""
    return f"""
    <div class="event-shell">
      <h3>{e(row.get('title', ''))}</h3>
      {detail_list}
    </div>
    """


def render_schedule_rows(rows: list[dict], compact: bool = False) -> str:
    rows_html = ""
    for row in rows:
        row_class = f"schedule-row row-{row.get('kind', 'event')}"
        if row.get("kind") == "parallel_workshops":
            tracks = row.get("tracks", [])

            def room_sort_key(track: dict) -> tuple[int, str]:
                room = str(track.get("room", "")).strip()
                for token in room.split():
                    if len(token) == 1 and token.isalpha():
                        return (0, token.upper())
                return (1, room.upper())

            tracks_sorted = sorted(tracks, key=room_sort_key)
            total_rows = max(1, len(tracks_sorted)) + 1

            rows_html += f"""
            <tr class="{row_class} row-workshops-header">
              <th scope="row" class="time-col" rowspan="{total_rows}">{e(row.get('time', ''))}</th>
              <td class="event-col">{render_event_cell(row, compact)}</td>
              <td class="location-col workshop-location-hint"></td>
            </tr>
            """

            for track in tracks_sorted:
                talks = track.get("talks", [])
                presenter = ""
                if talks:
                    presenter = str(talks[0].get("presenter", "")).strip()
                title_html = f"<div class=\"talk-title\">{e(track.get('title', 'Workshop'))}</div>"
                presenter_html = f"<div class=\"talk-presenter\">{e(presenter)}</div>" if presenter else ""

                rows_html += f"""
                <tr class="{row_class} row-workshop-item">
                  <td class="event-col">
                    {title_html}
                    {presenter_html}
                  </td>
                  <td class="location-col">{e(track.get('room', ''))}</td>
                </tr>
                """

        elif row.get("kind") == "parallel_sessions":
            rows_html += f"""
            <tr class="{row_class}">
              <th scope="row" class="time-col">{e(row.get('time', ''))}</th>
              <td class="event-col event-col-wide" colspan="2">{render_event_cell(row, compact)}</td>
            </tr>
            """
        else:
            rows_html += f"""
            <tr class="{row_class}">
              <th scope="row" class="time-col">{e(row.get('time', ''))}</th>
              <td class="event-col">{render_event_cell(row, compact)}</td>
              <td class="location-col">{e(row.get('location', ''))}</td>
            </tr>
            """

    return rows_html


def row_layout_weight(row: dict) -> int:
    kind = str(row.get("kind", "event"))
    if kind == "parallel_sessions":
        return 5
    if kind == "plenary":
        return 3
    if kind == "parallel_workshops":
        return 3
    return 1


def split_rows_two_sides(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    if len(rows) <= 1:
        return rows, []

    weights = [row_layout_weight(row) for row in rows]
    total = sum(weights)
    running = 0
    split_idx = max(1, len(rows) // 2)

    for idx, weight in enumerate(weights, start=1):
        running += weight
        if running >= total / 2:
            split_idx = idx
            break

    min_side_rows = 3
    split_idx = max(min_side_rows, split_idx)
    split_idx = min(len(rows) - min_side_rows, split_idx)
    split_idx = max(1, min(len(rows) - 1, split_idx))
    return rows[:split_idx], rows[split_idx:]


def split_rows_balanced(rows: list[dict], parts: int) -> list[list[dict]]:
    if parts <= 1:
        return [rows]
    if not rows:
        return [[] for _ in range(parts)]

    weights = [row_layout_weight(row) for row in rows]
    total = sum(weights)

    groups: list[list[dict]] = []
    current: list[dict] = []
    running = 0
    consumed = 0  # weight already finalized into `groups`

    for idx, row in enumerate(rows):
        remaining_rows = len(rows) - idx
        remaining_groups = parts - len(groups)
        # Recompute the target from what's actually left, not a fixed total/parts —
        # a fixed target under-splits once earlier groups run over it (e.g. a single
        # heavy block), silently leaving later groups empty instead of rebalancing.
        target = (total - consumed) / remaining_groups if remaining_groups else total

        if (
            current
            and remaining_groups > 1
            and running >= target
            and remaining_rows >= remaining_groups
        ):
            groups.append(current)
            consumed += running
            current = []
            running = 0

        current.append(row)
        running += row_layout_weight(row)

    if current:
        groups.append(current)

    while len(groups) < parts:
        groups.append([])

    while len(groups) > parts:
        groups[-2].extend(groups[-1])
        groups.pop()

    return groups


def card_weight(card: dict) -> int:
    text_blob = " ".join(card.get("lines", []))
    return max(1, 1 + len(text_blob) // 120)


def to_card(title: str, subtitle: str, lines: list[str], accent: str) -> dict:
    return {
        "title": title,
        "subtitle": subtitle,
        "lines": [line for line in lines if line],
        "accent": accent,
    }


def programme_to_cards(programme: list[dict]) -> list[dict]:
    cards: list[dict] = []

    for block in programme:
        block_type = block.get("type")
        when = time_range(block)

        if block_type == "event":
            lines = []
            if block.get("location"):
                lines.append(f"Location: {block['location']}")
            if block.get("presenter"):
                lines.append(f"Presenter: {block['presenter']}")
            if block.get("chair"):
                lines.append(f"Chair: {block['chair']}")
            cards.append(to_card(block.get("title", "Event"), when, lines, GREEN))

        elif block_type == "workshop_block":
            lines = []
            for item in block.get("items", []):
                title = item.get("title", "")
                room = item.get("room", "")
                presenter = item.get("presenter", "")
                line = title
                if room:
                    line += f" ({room})"
                if presenter:
                    line += f" - {presenter}"
                lines.append(line)
            if block.get("chair"):
                lines.insert(0, f"Chair: {block['chair']}")
            cards.append(to_card(block.get("title", "Parallel Workshops"), when, lines, BLUE))

        elif block_type == "plenary_block":
            lines = []
            if block.get("location"):
                lines.append(f"Location: {block['location']}")
            if block.get("chair"):
                lines.append(f"Chair: {block['chair']}")
            for item in block.get("items", []):
                title = item.get("title", "")
                presenters = item.get("presenters", "")
                line = title
                if presenters:
                    line += f" - {presenters}"
                lines.append(line)
            cards.append(to_card(block.get("title", "Plenary"), when, lines, MAROON))

        elif block_type == "presentation_session_block":
            for session in block.get("sessions", []):
                lines = []
                if session.get("chair"):
                    lines.append(f"Chair: {session['chair']}")
                if session.get("room"):
                    lines.append(f"Room: {session['room']}")
                for talk in session.get("talks", []):
                    title = talk.get("title", "")
                    presenter = talk.get("presenter", "")
                    line = title
                    if presenter:
                        line += f" - {presenter}"
                    lines.append(line)
                cards.append(to_card(session.get("theme", "Presentation Session"), when, lines, LILAC))

    return cards


def split_balanced(cards: list[dict], parts: int) -> list[list[dict]]:
    if parts <= 1:
        return [cards]

    if not cards:
        return [[] for _ in range(parts)]

    weighted = [card_weight(card) for card in cards]
    total = sum(weighted)
    target = max(1, total / parts)

    groups: list[list[dict]] = []
    current: list[dict] = []
    running = 0

    for idx, card in enumerate(cards):
        remaining_cards = len(cards) - idx
        remaining_groups = parts - len(groups)

        if (
            current
            and remaining_groups > 1
            and running >= target
            and remaining_cards >= remaining_groups
        ):
            groups.append(current)
            current = []
            running = 0

        current.append(card)
        running += card_weight(card)

    if current:
      groups.append(current)

    while len(groups) < parts:
      groups.append([])

    while len(groups) > parts:
      groups[-2].extend(groups[-1])
      groups.pop()

    return groups


def render_card(card: dict) -> str:
    lines_html = "".join(f"<li>{e(line)}</li>" for line in card.get("lines", []))
    subtitle = f"<div class=\"card-subtitle\">{e(card['subtitle'])}</div>" if card.get("subtitle") else ""
    return f"""
    <article class="card" style="--accent:{card['accent']};">
      <h3>{e(card['title'])}</h3>
      {subtitle}
      <ul>{lines_html}</ul>
    </article>
    """


def render_single_row(card: dict) -> str:
    lines_html = "".join(f"<li>{e(line)}</li>" for line in card.get("lines", []))
    subtitle = card.get("subtitle", "")
    return f"""
    <article class="single-row" style="--accent:{card['accent']};">
      <div class="single-row-time">{e(subtitle)}</div>
      <div class="single-row-content">
        <h3>{e(card['title'])}</h3>
        <ul>{lines_html}</ul>
      </div>
    </article>
    """


def cover_card(parsed: dict, programme: list[dict], cards: list[dict]) -> dict:
    starts = [block.get("start", "") for block in programme if block.get("start")]
    ends = [block.get("end", "") for block in programme if block.get("end")]
    first_time = starts[0] if starts else ""
    last_time = ends[-1] if ends else ""

    workshops = sum(1 for block in programme if block.get("type") == "workshop_block")
    sessions = sum(
        len(block.get("sessions", []))
        for block in programme
        if block.get("type") == "presentation_session_block"
    )

    lines = []
    if first_time or last_time:
        lines.append(f"Day schedule: {first_time}-{last_time}" if first_time and last_time else f"Day schedule: {first_time or last_time}")
    lines.append(f"Programme blocks: {len(programme)}")
    if workshops:
        lines.append(f"Parallel workshop blocks: {workshops}")
    if sessions:
        lines.append(f"Presentation tracks: {sessions}")
    if cards:
      lines.append(f"First programme item: {cards[0].get('title', '')}")
    lines.append("Fold-print layout: outer sheet (Back + Front), inner sheet (Inside Left + Inside Right)")

    source_name = Path(parsed.get("source_file", "")).name or "LTRS2026 schedule"
    return to_card("LTRS 2026", source_name, lines, GREEN)


def base_css(beige_paper: bool = False) -> str:
    # beige_paper=True is used only by the two-side "beige paper" PDF variant: every
    # background that's currently painted cream becomes no-fill (transparent), so a
    # pre-printed beige sheet shows through instead of the printer laying down cream
    # ink/toner on top of it. Text that happens to be cream-coloured (e.g. the green
    # banner's lettering) is unaffected — that's providing contrast against printed
    # green ink, not matching the paper, so it must keep printing normally regardless
    # of paper colour. --cream-bg is the single point where that distinction lives;
    # everywhere else keeps using --cream directly for real cream-coloured content.
    cream_bg = "transparent" if beige_paper else "var(--cream)"
    return f"""
    @font-face {{
      font-family: "Magnole";
      src: url("{asset_data_uri('magnole-regular.otf')}") format("opentype");
    }}
    @font-face {{
      font-family: "AvenirLocal";
      src: url("{asset_data_uri('AvenirNextLTPro-Regular.otf')}") format("opentype");
      font-weight: 400;
    }}
    @font-face {{
      font-family: "AvenirLocal";
      src: url("{asset_data_uri('AvenirNextLTPro-Demi.otf')}") format("opentype");
      font-weight: 700;
    }}

    :root {{
      --cream: {CREAM};
      --dark: {DARK};
      --green: {GREEN};
      --blue: {BLUE};
      --lilac: {LILAC};
      --maroon: {MAROON};
      --white: {WHITE};
      --border-grey: {BORDER_GREY};
      --screen-preview-backdrop: {SCREEN_PREVIEW_BACKDROP};
      --cream-bg: {cream_bg};
      --row-event: var(--cream-bg);
      --row-break: {ROW_BREAK};
      --row-plenary: var(--lilac);
      --row-workshop: var(--lilac);
      --row-presentations: var(--lilac);
    }}

    * {{
      box-sizing: border-box;
      -webkit-print-color-adjust: exact;
      print-color-adjust: exact;
    }}
    body {{
      margin: 0;
      color: var(--dark);
      background: var(--cream-bg);
      font-family: "AvenirLocal", "Avenir Next", Arial, sans-serif;
      line-height: 1.25;
    }}
    h1, h2, h3, p {{ margin: 0; }}
    .title-block {{
      border-bottom: 2px solid var(--green);
      margin-bottom: 12px;
      padding-bottom: 8px;
    }}
    .eyebrow {{
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: var(--maroon);
      margin-bottom: 6px;
    }}
    h1 {{
      font-family: "Magnole", Georgia, serif;
      color: var(--green);
      font-weight: 400;
      line-height: 0.95;
    }}
    .subtitle {{
      margin-top: 6px;
      font-size: 14px;
    }}
    .cards {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
      gap: 10px;
    }}
    .card {{
      background: rgba(255, 255, 255, 0.7);
      border: 1px solid rgba(23, 31, 32, 0.14);
      border-left: 5px solid var(--accent);
      border-radius: 10px;
      padding: 10px 11px;
      break-inside: avoid;
    }}
    .card h3 {{
      color: var(--dark);
      font-size: 16px;
      line-height: 1.1;
      margin-bottom: 4px;
    }}
    .card-subtitle {{
      color: var(--green);
      font-size: 13px;
      font-weight: 700;
      margin-bottom: 6px;
    }}
    .card ul {{
      margin: 0;
      padding-left: 16px;
      font-size: 13px;
    }}
    .card li {{
      margin: 2px 0;
    }}
    .panel-label {{
      font-size: 11px;
      color: rgba(23, 31, 32, 0.72);
      margin-bottom: 6px;
      font-weight: 700;
      letter-spacing: 0.04em;
      text-transform: uppercase;
    }}
    """


def schedule_table_css(background_var: str = "var(--cream)") -> str:
    # Shared by single-page and two-side, which are otherwise near-identical A4
    # portrait layouts — extracted so a change to the schedule table/track-grid
    # styling only needs to happen once instead of being hand-mirrored into both
    # (see the 2026-08-05 session log on how that duplication let a real bug slip
    # through on fold-card once already). fold-card is NOT built on this — it has
    # a genuinely different layout (landscape, narrower panels) and keeps its own
    # `fold_card_css()`, so this only ever needs to serve these two.
    # background_var lets two-side's beige-paper PDF variant swap in --cream-bg
    # (no-fill) while single-page always keeps the literal --cream fill.
    return f"""
  .schedule-header {{
    background: var(--green);
    color: var(--cream);
    border-radius: {SCHEDULE_HEADER_RADIUS};
    padding: 8px 10px;
    margin-bottom: 20px;
    text-align: center;
  }}
  .schedule-header-top {{
    display: flex;
    align-items: center;
    gap: 12px;
    justify-content: center;
    margin-bottom: 6px;
  }}
  .schedule-header-logo {{
    width: 56px;
    height: 56px;
    flex-shrink: 0;
    object-fit: contain;
    display: block;
  }}
  .schedule-header h1 {{
    font-size: 48px;
    color: var(--cream);
    margin: 0;
    font-family: "Magnole", Georgia, serif;
    font-weight: 400;
    line-height: 0.95;
  }}
  .schedule-header .subtitle-line {{
    margin-top: 4px;
    font-size: 14px;
    line-height: 1.2;
  }}
  .schedule-header .subtitle-line.magnole {{
    font-family: "Magnole", Georgia, serif;
    font-weight: 400;
    font-size: 18px;
    line-height: 1.15;
    letter-spacing: 0;
    white-space: nowrap;
  }}
  .source-line {{
    font-size: 14px;
    line-height: 1.2;
    margin-top: 2px;
  }}
  .schedule-table {{
    width: 100%;
    border-collapse: collapse;
    table-layout: fixed;
    background: var(--white);
  }}
  .col-time {{ width: 5.2em; }}
  .col-location {{ width: 7.6em; }}
  .schedule-table thead th {{
    border: 1px solid var(--border-grey);
    border-bottom: 0;
    padding: 4px 6px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    text-align: left;
    color: var(--cream);
    background: var(--green);
  }}
  .sr-only {{
    position: absolute;
    width: 1px;
    height: 1px;
    padding: 0;
    margin: -1px;
    overflow: hidden;
    clip: rect(0, 0, 0, 0);
    white-space: nowrap;
    border: 0;
  }}
  .time-col {{
    background: var(--green);
    color: var(--cream);
    font-size: 13px;
    font-weight: 700;
    line-height: 1.05;
    padding: 4px 5px;
    border: 1px solid var(--border-grey);
    text-align: left;
    vertical-align: top;
  }}
  .event-col {{
    border: 1px solid var(--border-grey);
    padding: 3px 6px;
    vertical-align: top;
    background: {background_var};
  }}
  .location-col {{
    width: 18%;
    border: 1px solid var(--border-grey);
    padding: 4px 5px;
    vertical-align: top;
    text-align: left;
    font-size: 12px;
    font-weight: 700;
    background: {background_var};
  }}
  .event-shell h3 {{
    font-family: "Magnole", Georgia, serif;
    font-weight: 400;
    font-size: 18px;
    line-height: 1.05;
    margin: 0;
    white-space: pre-line;
  }}
  .detail-lines {{
    margin: 2px 0 0;
    font-size: 12px;
  }}
  .detail-line {{ margin: 1px 0; }}
  .event-note {{
    margin: 2px 0 0;
    font-size: 11px;
    font-style: italic;
  }}
  .chair-note {{
    display: block;
    margin-left: -6px;
    margin-right: -6px;
    padding-left: 6px;
    padding-right: 6px;
    border-bottom: 1px solid var(--border-grey);
    padding-bottom: 2px;
    margin-bottom: 2px;
  }}
  .track-grid {{
    margin-top: 3px;
    display: table;
    table-layout: fixed;
    width: 100%;
    border-spacing: 3px 0;
  }}
  .row-workshops-header .event-col {{
    padding-bottom: 4px;
  }}
  .workshop-location-hint {{
    text-transform: uppercase;
    letter-spacing: 0.03em;
    font-size: 11px;
  }}
  .row-workshop-item .event-col {{
    padding-top: 5px;
    padding-bottom: 5px;
  }}
  .row-workshop-item .talk-presenter {{
    margin-top: 2px;
  }}
  .row-workshop-item .talk-title {{
    margin-top: 0;
  }}
  .track-row {{
    display: table-row;
  }}
  .track-cell {{
    display: table-cell;
    vertical-align: top;
    border-left: 1px solid var(--border-grey);
    border-right: 1px solid var(--border-grey);
    background: {background_var};
    padding: 5px 6px;
  }}
  .track-row-header .track-cell {{
    border-top: 1px solid var(--border-grey);
    border-bottom: 1px solid var(--border-grey);
  }}
  .track-row:last-child .track-cell {{
    border-bottom: 1px solid var(--border-grey);
  }}
  .row-parallel_sessions .track-cell,
  .row-parallel_workshops .track-cell {{
    background: var(--lilac);
  }}
  .row-parallel_sessions .track-row-header .track-cell,
  .row-parallel_workshops .track-row-header .track-cell {{
    background: var(--green);
    color: var(--cream);
  }}
  .track-header-cell h4 {{
    font-size: 13px;
    line-height: 1.08;
    margin: 0;
  }}
  .track-room {{
    font-size: 12px;
    font-weight: 700;
    margin-top: 2px;
  }}
  .track-chair {{
    display: block;
    font-size: 11px;
    font-style: italic;
    margin-top: 3px;
  }}
  .talk-body {{
    border-top: 1px solid var(--border-grey);
  }}
  .track-row-header + .track-row .talk-body {{
    border-top: 0;
  }}
  .talk-list {{
    margin: 4px 0 0;
    padding: 0;
    list-style: none;
  }}
  .talk-list li {{
    margin-top: 4px;
    padding-top: 4px;
    border-top: 1px solid var(--border-grey);
  }}
  .talk-list li:first-child {{
    border-top: 0;
    margin-top: 0;
    padding-top: 0;
  }}
  .talk-presenter {{
    font-size: 11px;
    font-weight: 400;
    line-height: 1.25;
  }}
  .talk-title {{
    font-size: 11px;
    font-weight: 700;
    line-height: 1.25;
  }}
  .plenary-list .talk-title {{
    font-size: 11px;
  }}
  /* Row type color mapping */
  .row-event .event-col,
  .row-event .location-col,
  .row-keynote .event-col,
  .row-keynote .location-col {{
    background: var(--row-event);
  }}
  .row-break .event-col,
  .row-break .location-col {{
    background: var(--row-break);
  }}
  .row-plenary .event-col,
  .row-plenary .location-col {{
    background: var(--row-plenary);
  }}
  .row-parallel_workshops .event-col,
  .row-parallel_workshops .location-col {{
    background: var(--row-workshop);
  }}
  .row-parallel_sessions .event-col,
  .row-parallel_sessions .location-col {{
    background: var(--row-presentations);
  }}
"""


def render_single_page_html(parsed: dict, programme: list[dict]) -> str:
    rows = build_onepager_rows(programme)
    rows_html = render_schedule_rows(rows)

    source_name = Path(parsed.get("source_file", "")).name or "LTRS2026 schedule.xlsx"

    return f"""<!doctype html>
<html lang="en-GB">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>LTRS 2026 Schedule - Single Page</title>
  <style>
{base_css()}
  @page {{ size: A4 portrait; margin: 0; }}
  .single-page {{
    width: 210mm;
    min-height: 297mm;
    margin: 0 auto;
    background: var(--cream);
    padding: 8mm;
  }}
{schedule_table_css()}
  .page-footer {{
    margin-top: 20px;
    text-align: center;
  }}
  .page-footer img {{
    width: 200px;
    height: auto;
    display: inline-block;
  }}
  @media screen and (max-width: 900px) {{
    .single-page {{ width: auto; min-height: auto; padding: 10px; }}
    .schedule-header h1 {{ font-size: 36px; }}
    .schedule-table,
    .schedule-table thead,
    .schedule-table tbody,
    .schedule-table tr,
    .schedule-table th,
    .schedule-table td {{
      display: block;
      width: 100%;
    }}
    .schedule-table thead {{
      display: none;
    }}
    .time-col,
    .event-col,
    .location-col {{
      border-width: 1px;
    }}
    .time-col {{ border-bottom: 0; }}
    .event-col {{ border-top: 0; border-bottom: 0; }}
    .location-col {{ border-top: 0; text-align: left; }}
  }}
  @media print {{
    body {{ background: var(--white); }}
    .single-page {{ margin: 0; padding: 0; }}
  }}
  </style>
</head>
<body>
  <main class="single-page">
    <header class="schedule-header" role="banner">
      <div class="schedule-header-top">
        <img class="schedule-header-logo" src="{asset_data_uri('r_logo.png')}" alt="Regent's University London logo">
        <h1>LTRS 2026</h1>
      </div>
      <p class="subtitle-line magnole">Care, Collaboration, and Community: Building Belonging in Higher Education</p>
      <p class="subtitle-line">Learning, Teaching, Research and Scholarship Conference</p>
      <p class="source-line">September 10th, 2026</p>
    </header>

    <table class="schedule-table" aria-describedby="schedule-caption">
      <caption id="schedule-caption" class="sr-only">LTRS 2026 conference schedule with columns for time, event details, and location.</caption>
      <colgroup>
        <col class="col-time">
        <col class="col-event">
        <col class="col-location">
      </colgroup>
      <thead>
        <tr>
          <th scope="col">Time</th>
          <th scope="col">Event</th>
          <th scope="col">Location</th>
        </tr>
      </thead>
      <tbody>
        {rows_html}
      </tbody>
    </table>

    <footer class="page-footer">
      <img src="{asset_data_uri(PAGE_FOOTER_LOGO)}" alt="Regent's University London — Cultivating Possibility">
    </footer>
  </main>
</body>
</html>
"""


def render_two_side_a4_html(parsed: dict, programme: list[dict], beige_paper: bool = False) -> str:
    rows = build_onepager_rows(programme)
    front_rows, back_rows = split_rows_two_sides(rows)
    front_rows_html = render_schedule_rows(front_rows)
    back_rows_html = render_schedule_rows(back_rows)

    return f"""<!doctype html>
<html lang="en-GB">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>LTRS 2026 Schedule - A4 Two Side</title>
  <style>
{base_css(beige_paper=beige_paper)}
  @page {{ size: A4 portrait; margin: 0; }}
  .a4-page {{
    width: 210mm;
    min-height: 297mm;
    padding: 8mm;
    margin: 0 auto;
    page-break-after: always;
    background: var(--cream-bg);
    display: flex;
    flex-direction: column;
  }}
  .a4-page:last-child {{ page-break-after: auto; }}
  .page-footer {{
    margin-top: auto;
    margin-bottom: auto;
    text-align: center;
  }}
  .page-footer img {{
    width: 260px;
    height: auto;
    display: inline-block;
  }}
  .a4-page.continuation .schedule-table thead {{
    display: none;
  }}
{schedule_table_css(background_var="var(--cream-bg)")}
  @media print {{
    .schedule-header {{
      background: var(--green) !important;
      color: var(--cream) !important;
    }}
    .schedule-header h1,
    .schedule-header .subtitle-line,
    .schedule-header .source-line {{
      color: var(--cream) !important;
    }}
    .time-col {{
      background: var(--green) !important;
      color: var(--cream) !important;
    }}
    .row-event .event-col,
    .row-event .location-col,
    .row-keynote .event-col,
    .row-keynote .location-col {{
      background: var(--row-event) !important;
    }}
    .row-break .event-col,
    .row-break .location-col {{
      background: var(--row-break) !important;
    }}
    .row-plenary .event-col,
    .row-plenary .location-col {{
      background: var(--row-plenary) !important;
    }}
    .row-parallel_workshops .event-col,
    .row-parallel_workshops .location-col {{
      background: var(--row-workshop) !important;
    }}
    .row-parallel_sessions .event-col,
    .row-parallel_sessions .location-col {{
      background: var(--row-presentations) !important;
    }}
  }}
  @media screen {{
    body {{ background: var(--screen-preview-backdrop); padding: 10px; }}
    .a4-page {{ box-shadow: 0 8px 30px rgba(0, 0, 0, 0.18); margin-bottom: 12px; }}
  }}
  </style>
</head>
<body>
  <main class="a4-page">
    <header class="schedule-header" role="banner">
      <div class="schedule-header-top">
        <img class="schedule-header-logo" src="{asset_data_uri('r_logo.png')}" alt="Regent's University London logo">
        <h1>LTRS 2026</h1>
      </div>
      <p class="subtitle-line magnole">Care, Collaboration, and Community: Building Belonging in Higher Education</p>
      <p class="subtitle-line">Learning, Teaching, Research and Scholarship Conference</p>
      <p class="source-line">September 10th, 2026</p>
    </header>
    <table class="schedule-table" aria-describedby="schedule-caption-front">
      <caption id="schedule-caption-front" class="sr-only">LTRS 2026 conference schedule side 1 with columns for time, event details, and location.</caption>
      <colgroup>
        <col class="col-time">
        <col class="col-event">
        <col class="col-location">
      </colgroup>
      <thead>
        <tr>
          <th scope="col">Time</th>
          <th scope="col">Event</th>
          <th scope="col">Location</th>
        </tr>
      </thead>
      <tbody>
        {front_rows_html}
      </tbody>
    </table>
  </main>

  <main class="a4-page continuation">
    <header class="schedule-header" role="banner">
      <div class="schedule-header-top">
        <img class="schedule-header-logo" src="{asset_data_uri('r_logo.png')}" alt="Regent's University London logo">
        <h1>LTRS 2026</h1>
      </div>
      <p class="subtitle-line magnole">Care, Collaboration, and Community: Building Belonging in Higher Education</p>
      <p class="subtitle-line">Learning, Teaching, Research and Scholarship Conference</p>
      <p class="source-line">September 10th, 2026</p>
    </header>
    <table class="schedule-table" aria-describedby="schedule-caption-back">
      <caption id="schedule-caption-back" class="sr-only">LTRS 2026 conference schedule side 2 with columns for time, event details, and location.</caption>
      <colgroup>
        <col class="col-time">
        <col class="col-event">
        <col class="col-location">
      </colgroup>
      <thead>
        <tr>
          <th scope="col">Time</th>
          <th scope="col">Event</th>
          <th scope="col">Location</th>
        </tr>
      </thead>
      <tbody>
        {back_rows_html}
      </tbody>
    </table>
    <footer class="page-footer">
      <img src="{asset_data_uri(PAGE_FOOTER_LOGO)}" alt="Regent's University London — Cultivating Possibility">
    </footer>
  </main>
</body>
</html>
"""


def fold_card_css() -> str:
    # Extracted so the measured-fit splitter (split_rows_by_fit) can render candidate
    # panels with the exact same styles as the real output — no risk of measuring
    # against one set of rules and rendering with another.
    return f"""
  @page {{ size: A4 landscape; margin: 8mm; }}
  .sheet {{
    width: 281mm;
    min-height: 194mm;
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8mm;
    margin: 0 auto;
    padding: 8mm;
    page-break-after: always;
    background: var(--cream);
  }}
  .sheet:last-child {{ page-break-after: auto; }}
  .panel {{
    border: 1px dashed rgba(23, 31, 32, 0.25);
    border-radius: 10px;
    padding: 4mm;
    overflow: hidden;
    background: #fff;
  }}
  .schedule-header {{
    background: var(--green);
    color: var(--cream);
    border-radius: 6px;
    padding: 6px 8px;
    margin-bottom: 6px;
    text-align: center;
  }}
  .schedule-header-top {{
    display: flex;
    align-items: center;
    gap: 8px;
    justify-content: center;
    margin-bottom: 4px;
  }}
  .schedule-header-logo {{
    width: 40px;
    height: 40px;
    object-fit: contain;
    display: block;
  }}
  .schedule-header h1 {{
    font-size: 30px;
    color: var(--cream);
    margin: 0;
    font-family: "Magnole", Georgia, serif;
    font-weight: 400;
    line-height: 0.95;
  }}
  .schedule-header .subtitle-line {{
    margin-top: 2px;
    font-size: 11px;
    line-height: 1.15;
  }}
  .schedule-header .subtitle-line.magnole {{
    font-family: "Magnole", Georgia, serif;
    font-size: 14px;
  }}
  .schedule-header .source-line {{
    margin-top: 2px;
    font-size: 10px;
    line-height: 1.1;
  }}
  .panel-header {{
    border-bottom: 1px solid rgba(23, 31, 32, 0.28);
    margin-bottom: 4px;
    padding-bottom: 2px;
  }}
  .panel-header h2 {{
    margin: 0;
    font-size: 16px;
    font-family: "Magnole", Georgia, serif;
    color: var(--green);
    font-weight: 400;
  }}
  .schedule-table {{
    width: 100%;
    border-collapse: collapse;
    table-layout: fixed;
    border: 1px solid rgba(23, 31, 32, 0.42);
    background: #fff;
  }}
  .col-time {{ width: 4.7em; }}
  .col-location {{ width: 6.4em; }}
  .schedule-table thead th {{
    border: 1px solid rgba(23, 31, 32, 0.42);
    padding: 3px 4px;
    font-size: 13px;
    font-weight: 700;
    letter-spacing: 0.03em;
    text-transform: uppercase;
    text-align: left;
    color: var(--cream);
    background: var(--green);
  }}
  .time-col {{
    background: var(--green);
    color: var(--cream);
    font-size: 13px;
    font-weight: 700;
    line-height: 1.05;
    padding: 3px 4px;
    border: 1px solid rgba(23, 31, 32, 0.42);
    text-align: left;
    vertical-align: top;
  }}
  .event-col {{
    border: 1px solid rgba(23, 31, 32, 0.42);
    padding: 2px 4px;
    vertical-align: top;
    background: var(--cream);
  }}
  .location-col {{
    border: 1px solid rgba(23, 31, 32, 0.42);
    padding: 2px 4px;
    vertical-align: top;
    text-align: center;
    font-size: 13px;
    font-weight: 700;
    background: var(--cream);
  }}
  .event-shell h3 {{
    font-family: "Magnole", Georgia, serif;
    font-weight: 400;
    font-size: 15px;
    line-height: 1.04;
    margin: 0;
    white-space: pre-line;
  }}
  .detail-lines {{ margin: 1px 0 0; font-size: 12px; }}
  .detail-line {{ margin: 0; }}
  .event-note {{ margin: 1px 0 0; font-size: 12px; font-style: italic; }}
  .chair-note {{
    display: block;
    margin-left: -4px;
    margin-right: -4px;
    padding-left: 4px;
    padding-right: 4px;
    border-bottom: 1px solid rgba(23, 31, 32, 0.45);
    padding-bottom: 1px;
    margin-bottom: 1px;
  }}
  .row-workshops-header .event-col {{ padding-bottom: 1px; }}
  .workshop-location-hint {{ text-transform: uppercase; letter-spacing: 0.02em; font-size: 10px; }}
  .row-workshop-item .event-col {{ padding-top: 1px; padding-bottom: 1px; }}
  .track-stack {{ margin-top: 2px; display: flex; flex-direction: column; gap: 2px; }}
  .track-stack-item {{ border: 1px solid rgba(23, 31, 32, 0.2); background: var(--cream); padding: 1px 3px; }}
  .row-parallel_sessions .track-stack-item,
  .row-parallel_workshops .track-stack-item {{ background: var(--lilac); }}
  .track-stack-head {{ display: flex; justify-content: space-between; align-items: baseline; gap: 4px; }}
  .track-stack-title {{ font-size: 13px; font-weight: 700; line-height: 1.05; }}
  .track-stack-room {{ font-size: 12px; font-weight: 700; white-space: nowrap; }}
  .track-stack-chair {{
    display: block;
    margin-left: -3px;
    margin-right: -3px;
    padding-left: 3px;
    padding-right: 3px;
    font-size: 12px;
    font-style: italic;
    margin-top: 1px;
    border-bottom: 1px solid rgba(23, 31, 32, 0.45);
    padding-bottom: 1px;
    margin-bottom: 1px;
  }}
  .track-stack-talks {{ margin: 1px 0 0; padding: 0; list-style: none; }}
  .track-stack-talks li {{ margin-top: 1px; padding-top: 1px; border-top: 1px dotted rgba(23, 31, 32, 0.35); }}
  .track-stack-talks li:first-child {{ border-top: 0; margin-top: 0; padding-top: 0; }}
  .talk-list {{ margin: 1px 0 0; padding: 0; list-style: none; }}
  .talk-list li {{ margin-top: 1px; padding-top: 1px; border-top: 1px dotted rgba(23, 31, 32, 0.35); }}
  .talk-list li:first-child {{ border-top: 0; margin-top: 0; padding-top: 0; }}
  .talk-presenter {{ font-size: 12px; font-weight: 400; line-height: 1.08; }}
  .talk-title {{ font-size: 12px; font-weight: 700; line-height: 1.08; }}
  .row-event .event-col,
  .row-event .location-col,
  .row-keynote .event-col,
  .row-keynote .location-col {{ background: var(--row-event); }}
  .row-break .event-col,
  .row-break .location-col {{ background: var(--row-break); }}
  .row-plenary .event-col,
  .row-plenary .location-col {{ background: var(--row-plenary); }}
  .row-parallel_workshops .event-col,
  .row-parallel_workshops .location-col {{ background: var(--row-workshop); }}
  .row-parallel_sessions .event-col,
  .row-parallel_sessions .location-col {{ background: var(--row-presentations); }}
  @media print {{
    .schedule-header {{
      background: var(--green) !important;
      color: var(--cream) !important;
    }}
    .schedule-header h1,
    .schedule-header .subtitle-line,
    .schedule-header .source-line {{ color: var(--cream) !important; }}
    .time-col {{ background: var(--green) !important; color: var(--cream) !important; }}
    .row-event .event-col,
    .row-event .location-col,
    .row-keynote .event-col,
    .row-keynote .location-col {{ background: var(--row-event) !important; }}
    .row-break .event-col,
    .row-break .location-col {{ background: var(--row-break) !important; }}
    .row-plenary .event-col,
    .row-plenary .location-col {{ background: var(--row-plenary) !important; }}
    .row-parallel_workshops .event-col,
    .row-parallel_workshops .location-col {{ background: var(--row-workshop) !important; }}
    .row-parallel_sessions .event-col,
    .row-parallel_sessions .location-col {{ background: var(--row-presentations) !important; }}
  }}
  @media screen {{
    body {{ background: #d9d9d9; padding: 10px; }}
    .sheet {{ box-shadow: 0 8px 30px rgba(0, 0, 0, 0.18); margin-bottom: 12px; }}
  }}
  """


# Physical usable height per fold-card panel: sheet min-height (194mm) minus the
# sheet's own top+bottom padding (8mm x2), converted to CSS px at 96dpi. Panels
# whose real rendered content exceeds this will not fit on one printed A4 sheet.
FOLD_CARD_PANEL_BUDGET_PX = round((194 - 16) * 96 / 25.4)


def measure_panel_height(rows_for_panel: list[dict]) -> int:
    """Render a candidate panel's actual table markup in headless Chromium and
    return its true content height in px — used by split_rows_by_fit() so panel
    boundaries are chosen from real measurements, not an abstract weight guess."""
    from playwright.sync_api import sync_playwright

    html = f"""<!doctype html>
<html><head><style>
{base_css()}
{fold_card_css()}
</style></head>
<body>
<div class="panel" style="width: 128.5mm; display: inline-block;">
  <table class="schedule-table">
    <colgroup><col class="col-time"><col class="col-event"><col class="col-location"></colgroup>
    <tbody>{render_schedule_rows(rows_for_panel, compact=True)}</tbody>
  </table>
</div>
</body></html>"""

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 700, "height": 3000})
        page.set_content(html)
        height = page.locator(".panel").first.evaluate("el => el.scrollHeight")
        browser.close()
    return height


def split_rows_by_fit(rows: list[dict], parts: int, budget_px: int) -> list[list[dict]]:
    """Pack rows into `parts` groups by actually rendering and measuring each
    candidate panel, adding rows until the next one would overflow budget_px —
    a real 'does it fit' check rather than the abstract weight heuristic in
    split_rows_balanced(). Falls back to that heuristic for degenerate inputs."""
    if parts <= 1 or not rows:
        return split_rows_balanced(rows, parts)

    from playwright.sync_api import sync_playwright

    def panel_html(rows_for_panel: list[dict]) -> str:
        return f"""<!doctype html>
<html><head><style>
{base_css()}
{fold_card_css()}
</style></head>
<body>
<div class="panel" style="width: 128.5mm; display: inline-block;">
  <table class="schedule-table">
    <colgroup><col class="col-time"><col class="col-event"><col class="col-location"></colgroup>
    <tbody>{render_schedule_rows(rows_for_panel, compact=True)}</tbody>
  </table>
</div>
</body></html>"""

    groups: list[list[dict]] = []
    remaining = list(rows)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 700, "height": 3000})

        for panel_index in range(parts):
            panels_left_after = parts - panel_index - 1

            if panels_left_after == 0:
                # Last panel: whatever's left, no further split point to find.
                groups.append(remaining)
                remaining = []
                break

            current: list[dict] = []
            for row in list(remaining):
                candidate = current + [row]
                # Always leave at least one row per remaining panel.
                if len(remaining) - len(candidate) < panels_left_after and current:
                    break
                page.set_content(panel_html(candidate))
                height = page.locator(".panel").first.evaluate("el => el.scrollHeight")
                if height > budget_px and current:
                    break
                current.append(row)

            if not current and remaining:
                # A single row already exceeds budget on its own — take it anyway;
                # there's nothing smaller to split it into at this level.
                current = [remaining[0]]

            groups.append(current)
            remaining = remaining[len(current):]

        browser.close()

    while len(groups) < parts:
        groups.append([])

    return groups


def render_fold_card_a4_html(parsed: dict, programme: list[dict], cards: list[dict]) -> str:
    _ = cards  # Kept for function signature compatibility.
    rows = build_onepager_rows(programme)
    quarters = split_rows_by_fit(rows, 4, FOLD_CARD_PANEL_BUDGET_PX)

    # Imposition order for folding:
    # Sheet 1 (outer): Q4 on left, Q1 on right
    # Sheet 2 (inner): Q2 on left, Q3 on right
    q1, q2, q3, q4 = quarters

    def panel_html(rows_for_panel: list[dict], panel_title: str, show_primary_header: bool = False) -> str:
        thead_html = """
          <thead>
            <tr>
              <th scope=\"col\">Time</th>
              <th scope=\"col\">Event</th>
              <th scope=\"col\">Location</th>
            </tr>
          </thead>
        """ if show_primary_header else ""

        header_block = ""
        if show_primary_header:
            header_block = f"""
          <header class=\"schedule-header\" role=\"banner\">
            <div class=\"schedule-header-top\">
              <img class=\"schedule-header-logo\" src=\"{asset_data_uri('r_logo.png')}\" alt=\"Regent's University London logo\">
              <h1>LTRS 2026</h1>
            </div>
            <p class=\"subtitle-line magnole\">Care, Collaboration, and Community: Building Belonging in Higher Education</p>
            <p class=\"subtitle-line\">Learning, Teaching, Research and Scholarship Conference</p>
            <p class=\"source-line\">September 10th, 2026</p>
          </header>
            """
        else:
            header_block = f"""
          <header class=\"panel-header\">
            <h2>{e(panel_title)}</h2>
          </header>
            """

        return f"""
        <section class=\"panel\">
          {header_block}
          <table class=\"schedule-table\" aria-label=\"{e(panel_title)}\">
            <colgroup>
              <col class=\"col-time\">
              <col class=\"col-event\">
              <col class=\"col-location\">
            </colgroup>
            {thead_html}
            <tbody>
              {render_schedule_rows(rows_for_panel, compact=True)}
            </tbody>
          </table>
        </section>
        """

    outer_sheet = (
        panel_html(q4, "Programme - Quarter 4")
        + panel_html(q1, "Programme - Quarter 1", show_primary_header=True)
    )
    inner_sheet = (
        panel_html(q2, "Programme - Quarter 2")
        + panel_html(q3, "Programme - Quarter 3")
    )

    return f"""<!doctype html>
<html lang="en-GB">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>LTRS 2026 Schedule - A4 Fold Card</title>
  <style>
{base_css()}
{fold_card_css()}
  </style>
</head>
<body>
  <section class="sheet">
    {outer_sheet}
  </section>
  <section class="sheet">
    {inner_sheet}
  </section>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Render LTRS schedule into multiple branded HTML outputs.")
    parser.add_argument("--input-json", default=str(DEFAULT_INPUT_JSON), help="Parsed JSON input path")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Output directory")
    parser.add_argument("--base-name", default=DEFAULT_BASE_NAME, help="Base output filename prefix")
    args = parser.parse_args()

    input_json = Path(args.input_json)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if not input_json.exists():
        raise FileNotFoundError(f"Cannot find parsed JSON: {input_json}. Run parse_ltrs2026_v1.py first.")

    parsed = json.loads(input_json.read_text(encoding="utf-8"))
    programme = parsed.get("programme", [])
    cards = programme_to_cards(programme)

    single_html = output_dir / f"{args.base_name}_single_page.html"
    two_side_html = output_dir / f"{args.base_name}_a4_two_side.html"
    two_side_html_beige = output_dir / f"{args.base_name}_a4_two_side_beige.html"
    fold_html = output_dir / f"{args.base_name}_a4_fold_card.html"

    single_html.write_text(render_single_page_html(parsed, programme), encoding="utf-8")
    two_side_html.write_text(render_two_side_a4_html(parsed, programme), encoding="utf-8")
    # Beige-paper variant: same content, cream backgrounds set to no-fill so a
    # pre-printed beige sheet shows through instead of the printer laying down cream
    # ink on top of it. Print/PDF-only distinction (@page CSS never applies to a
    # plain browser view) — not surfaced as its own app-facing deliverable, only its
    # exported PDF is (see make_ltrs2026_schedule.py / app.py).
    two_side_html_beige.write_text(
        render_two_side_a4_html(parsed, programme, beige_paper=True), encoding="utf-8"
    )
    fold_html.write_text(render_fold_card_a4_html(parsed, programme, cards), encoding="utf-8")

    print(f"Wrote HTML: {single_html}")
    print(f"Wrote HTML: {two_side_html}")
    print(f"Wrote HTML: {two_side_html_beige}")
    print(f"Wrote HTML: {fold_html}")


if __name__ == "__main__":
    main()
