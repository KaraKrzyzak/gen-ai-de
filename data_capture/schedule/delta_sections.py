"""Parser for the Delta Climb sign-up page (weekly sections) - a static schedule.

The page loads its sections from <site>/api/sections:
    {"sections": [{name, kind, coach, schedule: "Poniedziałek · 17:00–18:00",
                   capacity, available, sessions: [{schedule, capacity, available}]}]}
`capacity` / `available` are the places for the current sign-up round.

YAML entry example:
  - name: "Delta Climb"
    url: "https://<host>/zapisy"
    parser: "delta_sections"
    schedule_type: "static"
"""
from __future__ import annotations

import re
from typing import Any, Optional
from urllib.parse import urlparse

import pandas as pd
import requests

from models import ClassEvent, events_to_frame
from registry import register

WEEKDAYS = {"poniedziałek": 0, "wtorek": 1, "środa": 2, "czwartek": 3,
            "piątek": 4, "sobota": 5, "niedziela": 6}
REQUEST_TIMEOUT_S = 20
HEADERS = {"User-Agent": "Mozilla/5.0 (schedule-scraper; personal project)"}
SCHEDULE_RE = re.compile(r"(?P<day>\S+)\s*·\s*(?P<h1>\d{1,2}):(?P<m1>\d{2})\s*[–-]\s*(?P<h2>\d{1,2}):(?P<m2>\d{2})")


def parse_schedule(text: str) -> Optional[dict[str, Any]]:
    """'Poniedziałek · 17:00–18:00' -> weekday, start_time, duration_min."""
    match = SCHEDULE_RE.search(text or "")
    if not match or match["day"].lower() not in WEEKDAYS:
        return None
    start = int(match["h1"]) * 60 + int(match["m1"])
    end = int(match["h2"]) * 60 + int(match["m2"])
    return {
        "weekday": WEEKDAYS[match["day"].lower()],
        "start_time": f"{match['h1'].zfill(2)}:{match['m1']}",
        "duration_min": end - start,
    }


def parse_payload(payload: dict[str, Any], link: Optional[str] = None) -> list[ClassEvent]:
    events: list[ClassEvent] = []
    for section in payload.get("sections", []):
        for session in section.get("sessions") or [section]:
            when = parse_schedule(session.get("schedule") or section.get("schedule"))
            if when is None:
                continue
            events.append(ClassEvent(
                source="",  # filled in by run.py from the YAML name
                title=(section.get("name") or "").strip(),
                instructors=[section["coach"]] if section.get("coach") else [],
                spots_total=session.get("capacity"),
                spots_free=session.get("available"),
                level=section.get("kind"),
                url=link,
                raw=section,
                **when,
            ))
    return events


@register("delta_sections")
def schedule_delta(config: dict) -> pd.DataFrame:
    parts = urlparse(config["url"])
    response = requests.get(f"{parts.scheme}://{parts.netloc}/api/sections", headers=HEADERS, timeout=REQUEST_TIMEOUT_S)
    response.raise_for_status()
    return events_to_frame(parse_payload(response.json(), link=config["url"]))
