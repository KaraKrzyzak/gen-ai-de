"""Parser for studios on Fitro (<slug>.fitro.pl), e.g. Lekko Studio.

The public landing page loads its week view from an anonymous endpoint:
    GET https://api.fitro.pl/api/public/partners/<slug>/events?startDate=YYYY-MM-DD&endDate=YYYY-MM-DD
Response: {"content": [ {className, startDateTime (UTC), endDateTime, instructors,
                         capacity, occupied, spotsLeft, status, ...} ]}
(The /calendar page itself needs a login; this endpoint does not.)

YAML entry example:
  - name: "Lekko Studio"
    url: "https://lekko.fitro.pl/"
    parser: "fitro"
    studio_id: "lekko"        # optional, defaults to the subdomain of the url
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Optional
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import pandas as pd
import requests

from models import ClassEvent, events_to_frame
from registry import register

LOCAL_TZ = ZoneInfo("Europe/Warsaw")
WEEKS_AHEAD = 2
REQUEST_TIMEOUT_S = 20
HEADERS = {"User-Agent": "Mozilla/5.0 (schedule-scraper; personal project)"}
API = "https://api.fitro.pl/api/public/partners/{slug}/events"


def to_local(value: str) -> datetime:
    """'2026-11-11T18:05:00Z' (UTC) -> aware datetime in Europe/Warsaw."""
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(LOCAL_TZ)


def parse_payload(payload: dict[str, Any], link: Optional[str] = None) -> list[ClassEvent]:
    events: list[ClassEvent] = []
    for item in payload.get("content", []):
        if item.get("status") == "cancelled":
            continue
        people = [
            " ".join(filter(None, [i.get("firstName"), i.get("lastName")]))
            for i in item.get("instructors") or []
        ]
        location = item.get("location")
        events.append(ClassEvent(
            source="",  # filled in by run.py from the YAML name
            title=(item.get("className") or "").strip(),
            start=to_local(item["startDateTime"]),
            end=to_local(item["endDateTime"]),
            instructors=[p for p in people if p],
            spots_total=item.get("capacity"),
            spots_booked=item.get("occupied"),
            spots_free=item.get("spotsLeft"),
            room=location.get("name") if isinstance(location, dict) else location,
            price=item["priceMinor"] / 100 if item.get("priceMinor") else None,
            url=link,
            raw=item,
        ))
    return events


@register("fitro")
def schedule_fitro(config: dict) -> pd.DataFrame:
    slug = config.get("studio_id") or urlparse(config["url"]).hostname.split(".")[0]
    today = date.today()
    response = requests.get(
        API.format(slug=slug),
        params={"startDate": today.isoformat(), "endDate": (today + timedelta(weeks=WEEKS_AHEAD)).isoformat()},
        headers=HEADERS,
        timeout=REQUEST_TIMEOUT_S,
    )
    response.raise_for_status()
    return events_to_frame(parse_payload(response.json(), link=config["url"]))
