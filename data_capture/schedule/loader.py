"""Load list_Schedule.yml into a flat DataFrame (one row per source)."""
from __future__ import annotations
 
from pathlib import Path
from typing import Any
 
import pandas as pd
import yaml
 
# Resolved relative to this file, so it works from any working directory.
DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent / "list_schedule.yml"
REQUIRED_KEYS = ("name", "url", "parser", "schedule_type")
 
 
def _as_flag_dict(value: Any) -> dict[str, Any] | None:
    """Return a dict for dict / list-of-single-key-dicts values, else None.
 
    YAML like
        medicover:
          - dance: true
          - stretch: false
    loads as a list of dicts; this merges it into {"dance": True, "stretch": False}.
    """
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, list) and value and all(isinstance(i, dict) for i in value):
        merged: dict[str, Any] = {}
        for item in value:
            merged.update(item)
        return merged
    return None
 
 
def load_schedules(path: str | Path = DEFAULT_CONFIG_PATH) -> pd.DataFrame:
    path = Path(path).resolve()
    with open(path, encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
 
    rows: list[dict[str, Any]] = []
    seen_names: set[str] = set()
    for index, entry in enumerate(data.get("schedules", [])):
        missing = [key for key in REQUIRED_KEYS if key not in entry]
        if missing:
            raise ValueError(
                f"Entry #{index} ({entry.get('name')}) in {path} is missing: {missing}. "
                f"Keys found: {sorted(entry)}"
            )
        if entry["name"] in seen_names:
            raise ValueError(f"Duplicate source name: {entry['name']}")
        seen_names.add(entry["name"])
 
        row: dict[str, Any] = {}
        for key, value in entry.items():
            flags = _as_flag_dict(value)
            if flags is None:
                row[key] = value
            else:  # medicover: {dance: true} -> medicover.dance = True
                for flag_name, flag_value in flags.items():
                    row[f"{key}.{flag_name}"] = flag_value
        rows.append(row)
 
    return pd.DataFrame(rows)