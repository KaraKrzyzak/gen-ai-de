"""All configuration comes from environment variables (optionally from a local `.env`).

No paths, hosts or tokens are hard-coded anywhere else, so the same code runs
unchanged on a laptop, in GitHub Actions and in a Docker container on a VM.
See `.env.example` for the full list of keys.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()  # reads .env from the working directory if it exists; real env vars win


@dataclass(frozen=True)
class Settings:
    data_dir: Path  # local working area (landing files, caches); gitignored
    storage_backend: str  # where ingestion writes its output: "local" | (later) "databricks_volume"
    log_level: str


def get_settings() -> Settings:
    return Settings(
        data_dir=Path(os.getenv("DATA_DIR", "data")),
        storage_backend=os.getenv("STORAGE_BACKEND", "local").strip().lower(),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
    )
