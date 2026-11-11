"""Parser for Active Klub (activklub.pl) weekly timetables - a static, recurring schedule.

The harmonogram page loads its data from
    POST https://www.activklub.pl/timetable/<timetable_id>      (form body with empty filters)
Response: {"events": {"HH:MM": {"<day idx>": [event, ...]}}, "days": {...}}.
The server rate-limits (HTTP 429), so requests are retried with a pause.

YAML entry example:
  - name: "Active Fialkowo"
    url: "https://www.activklub.pl/fikakowo-harmonogram"
    parser: "activklub"
    schedule_type: "static"
    timetable_id: 7
"""
from __future__ import annotations

import time
from typing import Any, Optional

import pandas as pd
import requests

from models import ClassEvent, events_to_frame
from registry import register

ENDPOINT = "https://www.activklub.pl/timetable/{timetable_id}"
WEEKDAYS = {"Monday": 0, "Tuesday": 1, "Wednesday": 2, "Thursday": 3,
            "Friday": 4, "Saturday": 5, "Sunday": 6}
REQUEST_TIMEOUT_S = 20
RETRIES = 4
HEADERS = {"User-Agent": "Mozilla/5.0 (schedule-scraper; personal project)"}
FORM = {"filters[gym_events.gym_event_type_id]": "", "filters[gym_events.gym_room_id]": ""}


def parse_payload(payload: dict[str, Any], link: Optional[str] = None) -> list[ClassEvent]:
    events: list[ClassEvent] = []
    for by_day in payload.get("events", {}).values():
        for items in by_day.values():
            if isinstance(items, dict):  # PHP arrays with gaps arrive as {"0": event, "2": event}
                items = list(items.values())
            for item in items:
                events.append(ClassEvent(
                    source="",  # filled in by run.py from the YAML name
                    title=((item.get("gym_event_type") or {}).get("name") or "").strip(),
                    weekday=WEEKDAYS.get(item.get("day_of_week")),
                    start_time=(item.get("starts_at") or "")[:5] or None,
                    duration_min=item.get("minutes_length"),
                    instructors=[item["info"].strip()] if (item.get("info") or "").strip() else [],
                    room=(item.get("gym_room") or {}).get("name"),
                    url=item.get("url") or link,
                    raw=item,
                ))
    return events


def fetch_payload(timetable_id: int) -> dict[str, Any]:
    for attempt in range(RETRIES):
        response = requests.post(
            ENDPOINT.format(timetable_id=timetable_id), data=FORM,
            headers=HEADERS, timeout=REQUEST_TIMEOUT_S,
        )
        if response.status_code != 429:
            response.raise_for_status()
            return response.json()
        time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"activklub timetable {timetable_id}: still rate-limited after {RETRIES} tries")


@register("activklub")
def schedule_activklub(config: dict) -> pd.DataFrame:
    return events_to_frame(parse_payload(fetch_payload(int(config["timetable_id"])), link=config["url"]))
