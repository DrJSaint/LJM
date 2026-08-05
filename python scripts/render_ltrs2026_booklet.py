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
import json
from html import escape
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT_JSON = PROJECT_ROOT / "output" / "ltrs2026_parsed.json"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "output"
DEFAULT_BASE_NAME = "ltrs2026"

CREAM = "#F7F1E8"
DARK = "#171F20"
GREEN = "#195C4D"
BLUE = "#70ACE9"
LILAC = "#D8CBF1"
MAROON = "#710704"


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


def render_track_card(track: dict) -> str:
  talks_html = ""
  for talk in track.get("talks", []):
    presenter = str(talk.get("presenter", "")).strip()
    title = str(talk.get("title", "")).strip()
    title_html = f"<div class=\"talk-title\">{e(title)}</div>" if title else ""
    presenter_html = f"<div class=\"talk-presenter\">{e(presenter)}</div>" if presenter else ""
    talks_html += f"<li>{title_html}{presenter_html}</li>"

  chair_html = ""
  if track.get("chair"):
    chair_html = f"<div class=\"track-chair\">Chaired by: {e(track.get('chair', ''))}</div>"

  return f"""
  <section class="track-card">
    <h4>{e(track.get('title', 'Track'))}</h4>
    <div class="track-room">{e(track.get('room', ''))}</div>
    {chair_html}
    <ul class="talk-list">{talks_html}</ul>
  </section>
  """


def render_event_cell(row: dict) -> str:
    kind = row.get("kind")

    if kind == "parallel_workshops":
        return f"""
        <div class="event-shell">
          <h3>{e(row.get('title', ''))}</h3>
        </div>
        """

    if kind in {"parallel_sessions", "parallel_workshops"}:
        tracks = row.get("tracks", [])
        tracks_html = "".join(render_track_card(track) for track in tracks)
        return f"""
        <div class="event-shell">
          <h3>{e(row.get('title', ''))}</h3>
          <p class="event-note">Concurrent tracks run in this shared time slot.</p>
          <div class="track-grid">{tracks_html}</div>
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


def base_css() -> str:
    return f"""
    @font-face {{
      font-family: "Magnole";
      src: url("../assets/fonts/magnole-regular.otf") format("opentype");
    }}
    @font-face {{
      font-family: "AvenirLocal";
      src: url("../assets/fonts/AvenirNextLTPro-Regular.otf") format("opentype");
      font-weight: 400;
    }}
    @font-face {{
      font-family: "AvenirLocal";
      src: url("../assets/fonts/AvenirNextLTPro-Demi.otf") format("opentype");
      font-weight: 700;
    }}

    :root {{
      --cream: {CREAM};
      --dark: {DARK};
      --green: {GREEN};
      --blue: {BLUE};
      --lilac: {LILAC};
      --maroon: {MAROON};
      --row-event: var(--cream);
      --row-break: #edf6ef;
      --row-plenary: var(--lilac);
      --row-workshop: var(--lilac);
      --row-presentations: var(--lilac);
    }}

    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      color: var(--dark);
      background: var(--cream);
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


def render_single_page_html(parsed: dict, programme: list[dict]) -> str:
    rows = build_onepager_rows(programme)
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
              <td class="event-col">{render_event_cell(row)}</td>
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
              <td class="event-col event-col-wide" colspan="2">{render_event_cell(row)}</td>
            </tr>
            """
        else:
            rows_html += f"""
            <tr class="{row_class}">
              <th scope="row" class="time-col">{e(row.get('time', ''))}</th>
              <td class="event-col">{render_event_cell(row)}</td>
              <td class="location-col">{e(row.get('location', ''))}</td>
            </tr>
            """

    source_name = Path(parsed.get("source_file", "")).name or "LTRS2026 schedule.xlsx"

    return f"""<!doctype html>
<html lang="en-GB">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>LTRS 2026 Schedule - Single Page</title>
  <style>
{base_css()}
  @page {{ size: A4 portrait; margin: 8mm; }}
  .single-page {{
    width: 210mm;
    min-height: 297mm;
    margin: 0 auto;
    background: var(--cream);
    padding: 8mm;
  }}
  .schedule-header {{
    background: var(--green);
    color: var(--cream);
    border-radius: 6px;
    padding: 8px 10px;
    margin-bottom: 8px;
    text-align: center;
  }}
  .schedule-header h1 {{
    font-size: 48px;
    color: var(--cream);
    margin: 0;
  }}
  .schedule-header p {{
    margin-top: 4px;
    font-size: 14px;
    line-height: 1.2;
  }}
  .source-line {{
    font-size: 11px;
    margin-top: 6px;
    opacity: 0.88;
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
  .schedule-table {{
    width: 100%;
    border-collapse: collapse;
    table-layout: fixed;
    border: 1px solid rgba(23, 31, 32, 0.42);
    background: #fff;
  }}
  .col-time {{ width: 5.2em; }}
  .col-location {{ width: 7.6em; }}
  .schedule-table thead.sr-only th {{
    padding: 0;
    border: 0;
  }}
  .time-col {{
    background: #216d5c;
    color: var(--cream);
    font-size: 13px;
    font-weight: 700;
    line-height: 1.05;
    padding: 4px 5px;
    border: 1px solid rgba(23, 31, 32, 0.42);
    text-align: left;
    vertical-align: top;
  }}
  .event-col {{
    border: 1px solid rgba(23, 31, 32, 0.42);
    padding: 3px 6px;
    vertical-align: top;
    background: var(--cream);
  }}
  .location-col {{
    width: 18%;
    border: 1px solid rgba(23, 31, 32, 0.42);
    padding: 4px 5px;
    vertical-align: top;
    text-align: center;
    font-size: 12px;
    font-weight: 700;
    background: var(--cream);
  }}
  .event-shell h3 {{
    font-family: "Magnole", Georgia, serif;
    font-weight: 400;
    font-size: 18px;
    line-height: 1.05;
    margin: 0;
  }}
  .detail-lines {{
    margin: 2px 0 0;
    font-size: 11px;
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
    border-bottom: 1px solid rgba(23, 31, 32, 0.52);
    padding-bottom: 2px;
    margin-bottom: 2px;
  }}
  .track-grid {{
    margin-top: 3px;
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
    gap: 3px;
  }}
  .row-workshops-header .event-col {{
    padding-bottom: 1px;
  }}
  .workshop-location-hint {{
    text-transform: uppercase;
    letter-spacing: 0.03em;
    font-size: 11px;
  }}
  .row-workshop-item .event-col {{
    padding-top: 2px;
    padding-bottom: 2px;
  }}
  .row-workshop-item .talk-presenter {{
    margin-top: 1px;
  }}
  .row-workshop-item .talk-title {{
    margin-top: 0;
  }}
  .track-card {{
    border: 1px solid rgba(23, 31, 32, 0.22);
    background: #f8f5ec;
    padding: 2px 4px;
  }}
  .row-parallel_sessions .track-card,
  .row-parallel_workshops .track-card {{
    background: #d8cbf1;
  }}
  .track-card h4 {{
    font-size: 13px;
    line-height: 1.08;
    margin: 0;
  }}
  .track-room {{
    font-size: 12px;
    font-weight: 700;
    margin-top: 1px;
  }}
  .track-chair {{
    display: block;
    margin-left: -4px;
    margin-right: -4px;
    padding-left: 4px;
    padding-right: 4px;
    font-size: 11px;
    font-style: italic;
    margin-top: 1px;
    border-bottom: 1px solid rgba(23, 31, 32, 0.52);
    padding-bottom: 2px;
    margin-bottom: 2px;
  }}
  .talk-list {{
    margin: 2px 0 0;
    padding: 0;
    list-style: none;
  }}
  .talk-list li {{
    margin-top: 2px;
    padding-top: 2px;
    border-top: 1px dotted rgba(23, 31, 32, 0.45);
  }}
  .talk-list li:first-child {{
    border-top: 0;
    margin-top: 0;
    padding-top: 0;
  }}
  .talk-presenter {{
    font-size: 11px;
    font-weight: 400;
    line-height: 1.1;
  }}
  .talk-title {{
    font-size: 11px;
    font-weight: 700;
    line-height: 1.12;
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
  .footer-line {{
    margin-top: 8px;
    text-align: center;
    font-family: "Magnole", Georgia, serif;
    color: var(--green);
    font-size: 24px;
    line-height: 1.0;
  }}
  .footer-sub {{
    text-align: center;
    margin-top: 1px;
    font-size: 13px;
    color: var(--dark);
  }}
  @media (max-width: 900px) {{
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
    body {{ background: #fff; }}
    .single-page {{ margin: 0; padding: 0; }}
  }}
  </style>
</head>
<body>
  <main class="single-page">
    <header class="schedule-header" role="banner">
      <h1>LTRS 2026</h1>
      <p>The Future of Learning in Higher Ed</p>
      <p>Learning, Teaching, Research and Scholarship Conference</p>
      <p class="source-line">Source: {e(source_name)}</p>
    </header>

    <table class="schedule-table" aria-describedby="schedule-caption">
      <caption id="schedule-caption" class="sr-only">LTRS 2026 conference schedule with columns for time, event details, and location.</caption>
      <colgroup>
        <col class="col-time">
        <col class="col-event">
        <col class="col-location">
      </colgroup>
      <thead class="sr-only">
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

    <div class="footer-line">Cultivating Possibility</div>
    <div class="footer-sub">Regent's University London</div>
  </main>
</body>
</html>
"""


def render_two_side_a4_html(cards: list[dict]) -> str:
    pages = split_balanced(cards, 2)

    page_html = []
    for idx, page_cards in enumerate(pages, start=1):
        cards_html = "\n".join(render_card(card) for card in page_cards)
        page_html.append(
            f"""
    <section class="a4-page">
      <div class="panel-label">A4 Side {idx}</div>
      <div class="cards">{cards_html}</div>
    </section>
    """
        )

    return f"""<!doctype html>
<html lang="en-GB">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>LTRS 2026 Schedule - A4 Two Side</title>
  <style>
{base_css()}
  @page {{ size: A4 portrait; margin: 10mm; }}
  h1 {{ font-size: 54px; }}
  .a4-page {{
    width: 190mm;
    min-height: 277mm;
    padding: 10mm;
    margin: 0 auto;
    page-break-after: always;
    background: var(--cream);
  }}
  .a4-page:last-child {{ page-break-after: auto; }}
  .cards {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
  @media screen {{
    body {{ background: #d9d9d9; padding: 10px; }}
    .a4-page {{ box-shadow: 0 8px 30px rgba(0, 0, 0, 0.18); margin-bottom: 12px; }}
  }}
  </style>
</head>
<body>
  <header class="a4-page">
    <div class="title-block">
      <div class="eyebrow">Learning, Teaching, Research and Scholarship Conference</div>
      <h1>LTRS 2026</h1>
      <p class="subtitle">Print layout: 2 A4 sides</p>
    </div>
    <p style="font-size:13px; margin-bottom:10px;">Use double-sided printing (flip on long edge).</p>
    <div class="cards"></div>
  </header>
  {''.join(page_html)}
</body>
</html>
"""


def render_fold_card_a4_html(parsed: dict, programme: list[dict], cards: list[dict]) -> str:
    deck = [cover_card(parsed, programme, cards)] + cards
    panels = split_balanced(deck, 4)

    # Imposition for folded A4 booklet:
    # Outer sheet: left=back panel (4), right=front panel (1)
    # Inner sheet: left=inside-left panel (2), right=inside-right panel (3)
    front = panels[0]
    inside_left = panels[1]
    inside_right = panels[2]
    back = panels[3]

    def panel_html(label: str, panel_cards: list[dict]) -> str:
        cards_html = "\n".join(render_card(card) for card in panel_cards)
        return f"""
        <section class="panel">
          <div class="panel-label">{e(label)}</div>
          <div class="cards">{cards_html}</div>
        </section>
        """

    outer = panel_html("Back (Panel 4)", back) + panel_html("Front (Panel 1)", front)
    inner = panel_html("Inside Left (Panel 2)", inside_left) + panel_html("Inside Right (Panel 3)", inside_right)

    return f"""<!doctype html>
<html lang="en-GB">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>LTRS 2026 Schedule - A4 Fold Card</title>
  <style>
{base_css()}
  @page {{ size: A4 landscape; margin: 8mm; }}
  h1 {{ font-size: 54px; }}
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
    padding: 6mm;
    overflow: hidden;
  }}
  .cards {{
    grid-template-columns: 1fr;
    gap: 7px;
  }}
  .card h3 {{ font-size: 14px; }}
  .card-subtitle {{ font-size: 12px; }}
  .card ul {{ font-size: 12px; }}
  .instructions {{
    width: 281mm;
    margin: 0 auto;
    padding: 8mm;
    page-break-after: always;
    background: var(--cream);
  }}
  @media screen {{
    body {{ background: #d9d9d9; padding: 10px; }}
    .instructions, .sheet {{ box-shadow: 0 8px 30px rgba(0, 0, 0, 0.18); margin-bottom: 12px; }}
  }}
  </style>
</head>
<body>
  <section class="instructions">
    <header class="title-block">
      <div class="eyebrow">Learning, Teaching, Research and Scholarship Conference</div>
      <h1>LTRS 2026</h1>
      <p class="subtitle">Print layout: 4 panels on folded A4</p>
    </header>
    <ol style="margin-top:0; padding-left:18px; font-size:13px;">
      <li>Print double-sided on A4, landscape, flip on short edge.</li>
      <li>First printed side is the outer sheet: back panel on the left, front panel on the right.</li>
      <li>Second printed side is the inner sheet with panels 2 and 3.</li>
      <li>Fold vertically down the middle.</li>
    </ol>
  </section>

  <section class="sheet">
    {outer}
  </section>

  <section class="sheet">
    {inner}
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
    fold_html = output_dir / f"{args.base_name}_a4_fold_card.html"

    single_html.write_text(render_single_page_html(parsed, programme), encoding="utf-8")
    two_side_html.write_text(render_two_side_a4_html(cards), encoding="utf-8")
    fold_html.write_text(render_fold_card_a4_html(parsed, programme, cards), encoding="utf-8")

    print(f"Wrote HTML: {single_html}")
    print(f"Wrote HTML: {two_side_html}")
    print(f"Wrote HTML: {fold_html}")


if __name__ == "__main__":
    main()
