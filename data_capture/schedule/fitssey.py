"""Parser for studios hosted on Fitssey (app.fitssey.com/<studio>/frontoffice).

The public FrontOffice page loads its schedule from an anonymous JSON endpoint:
    POST https://app.fitssey.com/<studio>/api/v4/private/frontoffice/schedule
    {"startDate": "YYYY-MM-DD", "endDate": "YYYY-MM-DD", "view": "agendaView", ...}
(found with discover.py). Response: {"schedule": [{"date", "scheduleEvents": [...]}]}.

YAML entry example:
  - name: "Czulosfera"
    url: "https://app.fitssey.com/czulosfera/frontoffice"
    parser: "fitssey"
    studio_id: "czulosfera"
    sample_file: "captures/czulosfera/schedule.json"   # optional, offline testing
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Optional

import pandas as pd
import requests

from models import ClassEvent, events_to_frame
from registry import register

SCHEDULE_URL = "https://app.fitssey.com/{studio}/api/v4/private/frontoffice/schedule"
WEEKS_AHEAD = 2
REQUEST_TIMEOUT_S = 20
HEADERS = {"User-Agent": "Mozilla/5.0 (schedule-scraper; personal project)"}


def _get(obj: Any, *path: str) -> Any:
    for key in path:
        if not isinstance(obj, dict):
            return None
        obj = obj.get(key)
    return obj


def parse_event(event: dict[str, Any], link: Optional[str]) -> ClassEvent:
    total = event.get("totalCapacity")
    free = event.get("remainCapacity")
    instructors = [
        name for m in (event.get("members") or [])
        if (name := _get(m, "user", "fullName") or m.get("qualifiedName"))
    ] or [n for n in [_get(event, "member", "user", "fullName")] if n]
    return ClassEvent(
        source="",  # filled in by run.py from the YAML name
        title=(_get(event, "scheduleMeta", "classService", "name") or "").strip(),
        # startsAt carries the studio's own UTC offset, e.g. 2026-11-09T09:00:00+01:00
        start=datetime.fromisoformat(event["startsAt"]),
        end=datetime.fromisoformat(event["endsAt"]),
        instructors=instructors,
        spots_total=total,
        spots_free=free,
        spots_booked=total - free if total is not None and free is not None else None,
        room=_get(event, "room", "name"),
        category=event.get("serviceType") if isinstance(event.get("serviceType"), str) else None,
        url=link,
        raw=event,
    )


def parse_payload(payload: dict[str, Any], link: Optional[str] = None) -> pd.DataFrame:
    events = [
        parse_event(e, link)
        for day in payload.get("schedule", [])
        for e in day.get("scheduleEvents", [])
        if not e.get("isCancelled") and not e.get("isHidden")
    ]
    return events_to_frame(events)


def fetch_payload(studio_id: str, start: date, end: date) -> dict[str, Any]:
    response = requests.post(
        SCHEDULE_URL.format(studio=studio_id),
        json={
            "category": None, "filters": None, "view": "agendaView", "loadFilters": False,
            "startDate": start.isoformat(), "endDate": end.isoformat(),
        },
        headers=HEADERS,
        timeout=REQUEST_TIMEOUT_S,
    )
    response.raise_for_status()
    return response.json()


@register("fitssey")
def schedule_fitssey(config: dict) -> pd.DataFrame:
    """Registry entry point. Uses `sample_file` from the YAML if present (offline test)."""
    if config.get("sample_file"):
        payload = json.loads(Path(config["sample_file"]).read_text(encoding="utf-8"))
    else:
        today = date.today()
        payload = fetch_payload(config["studio_id"], today, today + timedelta(weeks=WEEKS_AHEAD))
    return parse_payload(payload, link=config.get("url"))
