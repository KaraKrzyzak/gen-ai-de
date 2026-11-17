"""Where ingestion output goes. The backend is chosen by `STORAGE_BACKEND`.

Ingestion code only calls `storage.write_dataframe(...)` / `write_text(...)` with a
relative path such as "schedule/2026-11-14_040000/events.csv", so switching from
local files to a Databricks volume (or a database) never touches the parsers.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Protocol

import pandas as pd

from gen_ai_de.config import Settings, get_settings


class Storage(Protocol):
    def write_dataframe(self, frame: pd.DataFrame, relative_path: str) -> str: ...

    def write_text(self, text: str, relative_path: str) -> str: ...


class LocalStorage:
    """Plain files under `<DATA_DIR>/landing/`."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def _target(self, relative_path: str) -> Path:
        target = (self.root / relative_path).resolve()
        if self.root.resolve() not in target.parents:  # refuse "../" escapes
            raise ValueError(f"Path escapes the storage root: {relative_path}")
        target.parent.mkdir(parents=True, exist_ok=True)
        return target

    def write_dataframe(self, frame: pd.DataFrame, relative_path: str) -> str:
        target = self._target(relative_path)
        # Plain UTF-8 (no BOM): these files are read by machines (Spark / Auto Loader).
        frame.to_csv(target, index=False, encoding="utf-8")
        return str(target)

    def write_text(self, text: str, relative_path: str) -> str:
        target = self._target(relative_path)
        target.write_text(text, encoding="utf-8")
        return str(target)


_BACKENDS: dict[str, Callable[[Settings], Storage]] = {
    "local": lambda settings: LocalStorage(settings.data_dir / "landing"),
}


def get_storage(settings: Settings | None = None) -> Storage:
    settings = settings or get_settings()
    try:
        return _BACKENDS[settings.storage_backend](settings)
    except KeyError:
        known = ", ".join(sorted(_BACKENDS))
        raise ValueError(f"Unknown STORAGE_BACKEND '{settings.storage_backend}'. Available: {known}") from None
