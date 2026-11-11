"""Parser for eFitness club websites (<club>.cms.efitness.com.pl/kalendarz-zajec).

There is no JSON API: the calendar is server-rendered HTML (table "calendar_table
week", one row per hour, one column per day). Week navigation: ?day=YYYY-MM-DD.
Only the hour row is known (not the exact minute), so `start` is that full hour.
Classes marked as cancelled in the room cell ("ODWOŁANE") are skipped.

YAML entry example:
  - name: "Energy Club"
    url: "https://energyclub-gdynia2.cms.efitness.com.pl/kalendarz-zajec"
    parser: "efitness"
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

import pandas as pd
import requests
from bs4 import BeautifulSoup

from models import ClassEvent, events_to_frame
from registry import register

LOCAL_TZ = ZoneInfo("Europe/Warsaw")
WEEKS_AHEAD = 2
REQUEST_TIMEOUT_S = 20
HEADERS = {"User-Agent": "Mozilla/5.0 (schedule-scraper; personal project)"}


def text_of(node, selector: str) -> Optional[str]:
    found = node.select_one(selector)
    return found.get_text(" ", strip=True) if found else None


def parse_html(html: bytes | str, link: Optional[str] = None) -> list[ClassEvent]:
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("table.calendar_table")
    if table is None:
        return []
    # Column index -> date, from the header links <a class="scheduler-go-to-day" meta:date=...>
    days = [
        date.fromisoformat(a["meta:date"]) if a and a.has_attr("meta:date") else None
        for a in (td.select_one("a.scheduler-go-to-day") for td in table.select("thead td"))
    ]
    events: list[ClassEvent] = []
    for tr in table.select("tbody tr"):
        cells = tr.find_all("td", recursive=False)
        if not cells or not re.fullmatch(r"\d{1,2}:\d{2}", cells[0].get_text(strip=True)):
            continue
        hour, minute = map(int, cells[0].get_text(strip=True).split(":"))
        for index, cell in enumerate(cells[1:], start=1):
            if index >= len(days) or days[index] is None:
                continue
            for div in cell.select("div.event"):
                room = text_of(div, "p.room") or ""
                if "ODWOŁAN" in room.upper():
                    continue
                length = re.search(r"\d+", text_of(div, "span.eventlength") or "")
                free = text_of(div, "span.availability-number")
                start = datetime(days[index].year, days[index].month, days[index].day, hour, minute, tzinfo=LOCAL_TZ)
                events.append(ClassEvent(
                    source="",  # filled in by run.py from the YAML name
                    title=text_of(div, "p.event_name") or "",
                    start=start,
                    end=start + timedelta(minutes=int(length.group())) if length else None,
                    instructors=[i] if (i := text_of(div, "p.instructor")) else [],
                    spots_free=max(int(free), 0) if free and re.fullmatch(r"-?\d+", free) else None,
                    room=room or None,
                    url=link,
                ))
    return events


@register("efitness")
def schedule_efitness(config: dict) -> pd.DataFrame:
    today = date.today()
    events: list[ClassEvent] = []
    for week in range(WEEKS_AHEAD):
        response = requests.get(
            config["url"],
            params={"view": "WeekByHour", "day": (today + timedelta(weeks=week)).isoformat()},
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT_S,
        )
        response.raise_for_status()
        events.extend(parse_html(response.content, link=config["url"]))
    frame = events_to_frame(events)
    # Consecutive weeks can overlap on the boundary day; drop exact duplicates.
    return frame.drop_duplicates(["title", "start", "room"]).reset_index(drop=True)
