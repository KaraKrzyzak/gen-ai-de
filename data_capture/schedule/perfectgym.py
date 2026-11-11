"""Parser for clubs on PerfectGym Client Portal (<host>/ClientPortal2/#/Classes/<club>/Calendar).

The public calendar page loads its data from an anonymous JSON endpoint (found with
discover.py / network capture):
    POST <host>/ClientPortal2/Classes/ClassCalendar/WeeklyClasses
    {"clubId": 76, "categoryId": null, "timeTableId": null, "trainerId": null,
     "daysInWeek": 6, "date": "YYYY-MM-DD"}
One response covers 6 days; PagerData.NextDate is the start of the next page.

YAML entry example:
  - name: "Well Fitness Osowa"
    url: "https://wellfitness.perfectgym.com/ClientPortal2/#/Classes/76/Calendar"
    parser: "perfectgym"
    club_id: 76            # optional, otherwise taken from the url
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Any, Optional
from zoneinfo import ZoneInfo

import pandas as pd
import requests

from models import ClassEvent, events_to_frame
from registry import register

LOCAL_TZ = ZoneInfo("Europe/Warsaw")
WEEKS_AHEAD = 2
REQUEST_TIMEOUT_S = 20
HEADERS = {"User-Agent": "Mozilla/5.0 (schedule-scraper; personal project)"}
MAX_PAGES = 6  # safety net against an endless NextDate loop


def club_id_from_url(url: str) -> int:
    match = re.search(r"/Classes/(\d+)", url)
    if not match:
        raise ValueError(f"No club id in url {url!r}; set `club_id` in the YAML")
    return int(match.group(1))


def base_url(url: str) -> str:
    """'https://x.perfectgym.com/ClientPortal2/#/...' -> 'https://x.perfectgym.com/ClientPortal2'."""
    return url.split("/ClientPortal2", 1)[0] + "/ClientPortal2"


def parse_duration_min(value: Optional[str]) -> Optional[int]:
    """PerfectGym sends odd values such as 'PT1H-5M' (= 55 min)."""
    match = re.fullmatch(r"PT(?:(-?\d+)H)?(?:(-?\d+)M)?", value or "")
    if not match or not any(match.groups()):
        return None
    return int(match.group(1) or 0) * 60 + int(match.group(2) or 0)


def parse_payload(payload: dict[str, Any], link: Optional[str] = None) -> list[ClassEvent]:
    events: list[ClassEvent] = []
    for zone in payload.get("CalendarData", []):
        for hour in zone.get("ClassesPerHour", []):
            for day in hour.get("ClassesPerDay", []):
                for item in day:
                    start = datetime.fromisoformat(item["StartTime"]).replace(tzinfo=LOCAL_TZ)
                    minutes = parse_duration_min(item.get("Duration"))
                    booking = item.get("BookingIndicator") or {}
                    events.append(ClassEvent(
                        source="",  # filled in by run.py from the YAML name
                        title=(item.get("Name") or "").strip(),
                        start=start,
                        end=start + timedelta(minutes=minutes) if minutes else None,
                        duration_min=minutes,
                        instructors=[item["Trainer"]] if item.get("Trainer") else [],
                        spots_total=booking.get("Limit"),
                        spots_free=booking.get("Available"),
                        room=zone.get("ZoneName"),
                        category=item.get("Status"),  # Bookable / FullBooked / Awaitable
                        url=link,
                        raw=item,
                    ))
    return events


def fetch_page(base: str, club_id: int, start: date) -> dict[str, Any]:
    response = requests.post(
        f"{base}/Classes/ClassCalendar/WeeklyClasses",
        json={
            "clubId": club_id, "categoryId": None, "timeTableId": None,
            "trainerId": None, "daysInWeek": 6, "date": start.isoformat(),
        },
        headers=HEADERS,
        timeout=REQUEST_TIMEOUT_S,
    )
    response.raise_for_status()
    return response.json()


@register("perfectgym")
def schedule_perfectgym(config: dict) -> pd.DataFrame:
    base = base_url(config["url"])
    club_id = int(config.get("club_id") or club_id_from_url(config["url"]))
    today = date.today()
    last_day = today + timedelta(weeks=WEEKS_AHEAD)

    events: list[ClassEvent] = []
    page_start = today
    for _ in range(MAX_PAGES):
        payload = fetch_page(base, club_id, page_start)
        events.extend(parse_payload(payload, link=config["url"]))
        next_date = (payload.get("PagerData") or {}).get("NextDate")
        if not next_date or date.fromisoformat(next_date) > last_day:
            break
        page_start = date.fromisoformat(next_date)
    return events_to_frame(events)
