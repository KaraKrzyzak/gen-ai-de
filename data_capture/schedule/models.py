"""Common data model shared by every source parser.
 
Every parser maps platform-specific data into ClassEvent (or into a DataFrame with
the same columns). Fields the source does not provide stay None.
 
Two kinds of schedules exist:
  * dated   (Fitssey, PerfectGym...) -> `start` is a real datetime
  * static  (weekly HTML timetable)  -> only `weekday` + `start_time` are known
"""
from __future__ import annotations
 
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Iterable, Optional
 
import pandas as pd
 
EVENT_COLUMNS = [
    "source", "title", "weekday", "start_time", "start", "end", "duration_min",
    "instructors", "spots_total", "spots_booked", "spots_free",
    "room", "category", "level", "price", "url",
]
 
 
@dataclass
class ClassEvent:
    source: str                              # filled in by the runner from the YAML name
    title: str
    weekday: Optional[int] = None            # 0 = Monday ... 6 = Sunday
    start_time: Optional[str] = None         # "HH:MM"
    start: Optional[datetime] = None
    end: Optional[datetime] = None
    duration_min: Optional[int] = None
    instructors: list[str] = field(default_factory=list)
    spots_total: Optional[int] = None
    spots_booked: Optional[int] = None
    spots_free: Optional[int] = None
    room: Optional[str] = None
    category: Optional[str] = None
    level: Optional[str] = None
    price: Optional[float] = None
    url: Optional[str] = None
    raw: Optional[dict[str, Any]] = None     # original record, kept for later re-parsing
 
    def __post_init__(self) -> None:
        # Derive values when the source gives only part of the information.
        if self.start is not None:
            if self.weekday is None:
                self.weekday = self.start.weekday()
            if self.start_time is None:
                self.start_time = self.start.strftime("%H:%M")
        if self.duration_min is None and self.start and self.end:
            self.duration_min = int((self.end - self.start).total_seconds() // 60)
        if (
            self.spots_free is None
            and self.spots_total is not None
            and self.spots_booked is not None
        ):
            self.spots_free = max(self.spots_total - self.spots_booked, 0)
 
    def to_dict(self, include_raw: bool = False) -> dict[str, Any]:
        data = asdict(self)
        if not include_raw:
            data.pop("raw", None)
        return data
 
 
def events_to_frame(events: Iterable[ClassEvent]) -> pd.DataFrame:
    """Convert events to a DataFrame with the standard column order."""
    rows = [e.to_dict() for e in events]
    return pd.DataFrame(rows, columns=EVENT_COLUMNS)
 