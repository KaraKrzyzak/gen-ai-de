"""Run every source from list_Schedule.yml and merge the results.
 
Usage:
    uv run python run.py
    uv run python run.py --only "Akademia Artystyczna"
"""
from __future__ import annotations
 
import argparse
import logging
from datetime import datetime
from pathlib import Path
 
import pandas as pd
 
import register_parsers  # noqa: F401  (registers all parsers)
from loader import DEFAULT_CONFIG_PATH, load_schedules
from registry import get_parser
 
log = logging.getLogger("schedules")
 
 
def clean_config(record: dict) -> dict:
    """Drop NaN values that pandas adds for keys missing in some YAML entries."""
    return {k: v for k, v in record.items() if not (isinstance(v, float) and pd.isna(v))}
 
 
def run(config_path: Path, only: str | None = None) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Return (events, clubs, errors). `clubs` is the full YAML table, one row per club."""
    clubs = load_schedules(config_path)
    sources = clubs
    if "enabled" in sources.columns:  # `enabled: false` in the YAML skips a source
        sources = sources[sources["enabled"].fillna(True).astype(bool)]
    if only:
        sources = sources[sources["name"] == only]
 
    frames: list[pd.DataFrame] = []
    errors: list[dict] = []
    for record in sources.to_dict("records"):
        config = clean_config(record)
        name = config["name"]
        try:
            frame = get_parser(config["parser"])(config).copy()
            frame["source"] = name          # the YAML name is the single source id
            frames.append(frame)
            log.info("%s: %d rows", name, len(frame))
        except Exception as exc:            # one broken source must not stop the others
            log.exception("%s failed", name)
            errors.append({"source": name, "error": repr(exc)})
 
    events = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
 
    if not events.empty:
        events["loaded_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
        events = events[["source"] + [c for c in events.columns if c != "source"]]
    # Club metadata is NOT repeated in events; join on events.source == clubs.name.
    return events, clubs.reset_index(drop=True), pd.DataFrame(errors)
 
 
def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    cli = argparse.ArgumentParser()
    cli.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    cli.add_argument("--only", help="run a single source by its YAML name")
    cli.add_argument("--out", type=Path, default=Path(__file__).resolve().parent / "output")
    args = cli.parse_args()
 
    events, clubs, errors = run(args.config, args.only)
    args.out.mkdir(parents=True, exist_ok=True)
    events.to_csv(args.out / "events.csv", index=False, encoding="utf-8-sig")
    clubs.to_csv(args.out / "clubs.csv", index=False, encoding="utf-8-sig")
    (args.out / "errors.csv").unlink(missing_ok=True)  # drop stale errors from earlier runs
    if not errors.empty:
        errors.to_csv(args.out / "errors.csv", index=False, encoding="utf-8-sig")
        log.warning("%d source(s) failed, see errors.csv", len(errors))
    print(events.head(10).to_string())
 
 
if __name__ == "__main__":
    main()