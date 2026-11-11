"""Parser for studios on wod.guru (e.g. Esensai Pole Dance Studio).

The studio page embeds https://wod.guru/schedule/<slug>; the embedded widget loads
    POST https://<slug>.wod.guru/classes/get-data   {"start_date": "YYYY-MM-DD", "period": 6}
Response: {"classes": [[day 0 classes], [day 1 classes], ...]} where day i = start_date + i.
Times are minutes from midnight (1020 = 17:00). Cancelled classes are skipped.

YAML entry example:
  - name: "Esensai Pole Dance Studio"
    url: "https://esensai.pl/grafik/"
    parser: "wod_guru"
    studio_id: "esensaipoledancestudio"   # slug of <slug>.wod.guru
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any, Optional
from zoneinfo import ZoneInfo

import pandas as pd
import requests

from models import ClassEvent, events_to_frame
from registry import register

LOCAL_TZ = ZoneInfo("Europe/Warsaw")
PERIOD_DAYS = 6          # the endpoint returns this many days per request
WEEKS_AHEAD = 2
REQUEST_TIMEOUT_S = 20
HEADERS = {"User-Agent": "Mozilla/5.0 (schedule-scraper; personal project)"}


def at_minutes(day: date, minutes: int) -> datetime:
    return datetime.combine(day, time(), tzinfo=LOCAL_TZ) + timedelta(minutes=minutes)


def parse_payload(payload: dict[str, Any], start: date, link: Optional[str] = None) -> list[ClassEvent]:
    events: list[ClassEvent] = []
    for offset, day_classes in enumerate(payload.get("classes", [])):
        day = start + timedelta(days=offset)
        for item in day_classes:
            if item.get("cancelled") or item.get("removed") or not item.get("active", 1):
                continue
            limit = item.get("class_limit")
            booked = item.get("number_of_signed_members")
            coaches = [
                " ".join(filter(None, [c.get("first_name"), c.get("last_name")]))
                for c in (cc.get("public_coach") or {} for cc in item.get("classes_coaches", []))
            ]
            events.append(ClassEvent(
                source="",  # filled in by run.py from the YAML name
                title=((item.get("plan") or {}).get("name") or "").strip(),
                start=at_minutes(day, item["start_time"]),
                end=at_minutes(day, item["end_time"]),
                instructors=[c for c in coaches if c],
                spots_total=limit,
                spots_booked=booked,
                room=(item.get("classroom") or {}).get("name"),
                url=link,
                raw=item,
            ))
    return events


@register("wod_guru")
def schedule_wod_guru(config: dict) -> pd.DataFrame:
    endpoint = f"https://{config['studio_id']}.wod.guru/classes/get-data"
    today = date.today()
    last_day = today + timedelta(weeks=WEEKS_AHEAD)
    events: list[ClassEvent] = []
    page_start = today
    while page_start <= last_day:
        response = requests.post(
            endpoint,
            json={"start_date": page_start.isoformat(), "period": PERIOD_DAYS},
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT_S,
        )
        response.raise_for_status()
        events.extend(parse_payload(response.json(), page_start, link=config.get("url")))
        page_start += timedelta(days=PERIOD_DAYS)
    return events_to_frame(events)
