"""Parser for Akademia Artystyczna (static weekly HTML timetable).

Registered as `parser: "aka"` in list_schedule.yml. It only returns the schedule
(standard ClassEvent columns); YAML metadata and load date are added by run.py.
"""
from __future__ import annotations

import pandas as pd
import requests
from bs4 import BeautifulSoup

from models import ClassEvent, events_to_frame
from registry import register

HEADERS = {"User-Agent": "Mozilla/5.0"}
TIMEOUT_S = 15

# h3 text is e.g. "PONIEDZIAŁEKSezon 2026/2027" -> keep the part before "Sezon".
WEEKDAYS = {
    "PONIEDZIAŁEK": 0, "WTOREK": 1, "ŚRODA": 2, "CZWARTEK": 3,
    "PIĄTEK": 4, "SOBOTA": 5, "NIEDZIELA": 6,
}


def parse_html(html: bytes | str) -> list[ClassEvent]:
    soup = BeautifulSoup(html, "html.parser")
    events: list[ClassEvent] = []
    for h3 in soup.find_all("h3"):
        day = h3.get_text(strip=True).split("Sezon")[0].strip().upper()
        table = h3.find_next("table")
        if day not in WEEKDAYS or table is None:
            continue
        for tr in table.find_all("tr"):
            td = tr.find_all("td")
            if len(td) < 3:
                continue
            age_classes = (td[3].span.get("class") or []) if len(td) > 3 and td[3].span else []
            age = next((c.removeprefix("age-") for c in age_classes if c.startswith("age-") and c != "age-indicator"), None)
            instructors = td[2].get_text(strip=True)
            events.append(ClassEvent(
                source="",  # filled in by run.py from the YAML name
                title=td[1].get_text(strip=True),
                weekday=WEEKDAYS[day],
                start_time=td[0].get_text(strip=True),
                instructors=[instructors] if instructors else [],
                level=age,  # kids / teens / adults
                url=td[1].a["href"] if td[1].a else None,
            ))
    return events


@register("aka")
def schedule_aka(config: dict) -> pd.DataFrame:
    response = requests.get(config["url"], headers=HEADERS, timeout=TIMEOUT_S)
    response.raise_for_status()
    # .content (bytes) lets BeautifulSoup detect UTF-8 instead of requests guessing.
    return events_to_frame(parse_html(response.content))
