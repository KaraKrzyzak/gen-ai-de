"""Parsers are tested on saved (trimmed) real responses in tests/fixtures: no network needed."""

import json
from datetime import date
from pathlib import Path

import pytest

from gen_ai_de.ingestion.schedule import (
    activklub,
    aka,
    delta_sections,
    efitness,
    fitro,
    fitssey,
    perfectgym,
    wod_guru,
)
from gen_ai_de.ingestion.schedule.models import EVENT_COLUMNS

FIXTURES = Path(__file__).parent / "fixtures"


def load_json(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_aka_static_weekly_timetable():
    events = aka.parse_html((FIXTURES / "aka.html").read_bytes())
    assert len(events) == 8
    first = events[0]
    assert first.title == "Akrobatyka Brzdące 3-5 lat"  # UTF-8 read correctly
    assert (first.weekday, first.start_time, first.level) == (0, "17:00", "kids")
    assert first.start is None  # static schedule: no calendar date
    assert first.url.startswith("https://akademiaartystyczna.com/")


def test_fitssey_dated_events_and_spots():
    frame = fitssey.parse_payload(load_json("fitssey.json"), link="https://app.fitssey.com/x")
    assert list(frame.columns) == EVENT_COLUMNS
    row = frame.iloc[0]
    assert row["title"].startswith("ABT")
    assert row["duration_min"] == 55
    assert (row["spots_total"], row["spots_free"], row["spots_booked"]) == (9, 6, 3)
    assert row["start"].utcoffset().total_seconds() == 3600  # keeps the studio's +01:00


def test_perfectgym_parsing_and_helpers():
    events = perfectgym.parse_payload(load_json("perfectgym.json"), link="x")
    assert len(events) == 6
    first = events[0]
    assert first.title.startswith("TBW")
    assert first.duration_min == 55  # "PT1H-5M"
    assert (first.spots_total, first.spots_free) == (30, 3)
    assert first.start.hour == 8 and first.start.minute == 30
    assert perfectgym.parse_duration_min("PT1H") == 60
    assert perfectgym.parse_duration_min(None) is None
    assert perfectgym.club_id_from_url("https://x.perfectgym.com/ClientPortal2/#/Classes/76/Calendar") == 76
    assert (
        perfectgym.base_url("https://x.perfectgym.com/ClientPortal2/#/Classes/76/Calendar")
        == "https://x.perfectgym.com/ClientPortal2"
    )
    with pytest.raises(ValueError):
        perfectgym.club_id_from_url("https://x.perfectgym.com/ClientPortal2/")


def test_wod_guru_minutes_to_datetime_and_cancelled_skipped():
    payload = load_json("wod_guru.json")
    events = wod_guru.parse_payload(payload, date(2026, 11, 11), link="x")
    assert events and all(e.start.hour * 60 + e.start.minute > 0 for e in events)
    total = sum(len(day) for day in payload["classes"])
    cancelled = sum(1 for day in payload["classes"] for c in day if c.get("cancelled"))
    assert len(events) == total - cancelled
    # day i of the response = start_date + i
    first_day_index = next(i for i, day in enumerate(payload["classes"]) if any(not c["cancelled"] for c in day))
    assert events[0].start.date() == date(2026, 11, 11 + first_day_index)


def test_fitro_utc_converted_to_warsaw():
    events = fitro.parse_payload(load_json("fitro.json"), link="x")
    assert len(events) == 4
    raw_utc = events[0].raw["startDateTime"]  # e.g. 2026-11-11T14:00:00Z
    assert events[0].start.utcoffset().total_seconds() == 3600  # CET in November
    assert events[0].start.hour == int(raw_utc[11:13]) + 1


def test_activklub_weekday_from_day_of_week():
    events = activklub.parse_payload(load_json("activklub.json"), link="x")
    assert len(events) == 13
    first = events[0]
    assert (first.title, first.weekday, first.start_time, first.duration_min) == ("BODY SHAPE", 0, "08:30", 60)
    assert first.room == "Sala 1"


def test_efitness_html_calendar():
    events = efitness.parse_html((FIXTURES / "efitness.html").read_bytes(), link="x")
    assert len(events) == 16
    first = events[0]
    assert first.title == "TBC total body conditioning"
    assert (first.start.hour, first.duration_min, first.spots_free) == (9, 55, 16)
    assert all(e.spots_free is None or e.spots_free >= 0 for e in events)  # "-1" clamped
    assert not any("ODWOŁAN" in (e.room or "").upper() for e in events)


def test_delta_sections_schedule_text():
    assert delta_sections.parse_schedule("Poniedziałek · 17:00–18:00") == {
        "weekday": 0,
        "start_time": "17:00",
        "duration_min": 60,
    }
    assert delta_sections.parse_schedule("Czwartek · 16:30–17:30")["weekday"] == 3
    assert delta_sections.parse_schedule("coś innego") is None
    events = delta_sections.parse_payload(load_json("delta_sections.json"), link="x")
    assert len(events) == 4 and events[0].level == "child"
    assert (events[0].spots_total, events[0].spots_free) == (8, 1)
