"""Single entry point for the daily ingestion (laptop, GitHub Actions, Docker on a VM).

    uv run python -m gen_ai_de.ingestion.run_all
    uv run python -m gen_ai_de.ingestion.run_all --only "Akademia Artystyczna"

Steps: scrape every enabled club -> write one timestamped batch through the configured
storage backend (STORAGE_BACKEND), as events.csv + clubs.csv (+ errors.csv, manifest.json).
Exit code 1 if no source produced data, so a scheduler notices a fully broken run.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone

from gen_ai_de.config import get_settings
from gen_ai_de.ingestion.schedule.loader import DEFAULT_CONFIG_PATH
from gen_ai_de.ingestion.schedule.run import run
from gen_ai_de.storage import get_storage

log = logging.getLogger("ingestion")


def main(argv: list[str] | None = None) -> int:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level, format="%(levelname)s %(name)s: %(message)s")

    cli = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    cli.add_argument("--config", default=DEFAULT_CONFIG_PATH, help="clubs YAML")
    cli.add_argument("--only", help="run a single club by its YAML name")
    args = cli.parse_args(argv)

    events, clubs, errors = run(args.config, args.only)

    storage = get_storage(settings)
    batch = f"schedule/{datetime.now(timezone.utc).strftime('%Y-%m-%d_%H%M%S')}"
    written = [
        storage.write_dataframe(events, f"{batch}/events.csv"),
        storage.write_dataframe(clubs, f"{batch}/clubs.csv"),
    ]
    if not errors.empty:
        written.append(storage.write_dataframe(errors, f"{batch}/errors.csv"))
    manifest = {
        "batch": batch,
        "loaded_at": None if events.empty else str(events["loaded_at"].iloc[0]),
        "rows": 0 if events.empty else len(events),
        "rows_per_source": {} if events.empty else events["source"].value_counts().to_dict(),
        "failed_sources": [] if errors.empty else errors["source"].tolist(),
    }
    written.append(storage.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), f"{batch}/manifest.json"))

    log.info(
        "%d rows from %d source(s), %d failed",
        manifest["rows"],
        len(manifest["rows_per_source"]),
        len(manifest["failed_sources"]),
    )
    for path in written:
        log.info("wrote %s", path)
    return 1 if events.empty else 0


if __name__ == "__main__":
    sys.exit(main())
