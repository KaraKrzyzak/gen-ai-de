"""Config, YAML, registry, storage and the run_all entry point (no network)."""

import json
from pathlib import Path

import pandas as pd
import pytest

from gen_ai_de.config import get_settings
from gen_ai_de.ingestion import run_all
from gen_ai_de.ingestion.schedule import register_parsers  # noqa: F401
from gen_ai_de.ingestion.schedule.loader import load_schedules
from gen_ai_de.ingestion.schedule.models import EVENT_COLUMNS, ClassEvent, events_to_frame
from gen_ai_de.ingestion.schedule.registry import get_parser
from gen_ai_de.storage import LocalStorage, get_storage


def test_settings_come_from_env(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("STORAGE_BACKEND", " Local ")
    settings = get_settings()
    assert settings.data_dir == tmp_path
    assert settings.storage_backend == "local"


def test_every_club_in_yaml_has_a_registered_parser():
    clubs = load_schedules()
    assert clubs["name"].is_unique
    for parser in clubs["parser"].unique():
        assert callable(get_parser(parser)), parser


def test_unknown_parser_lists_registered_ones():
    with pytest.raises(KeyError, match="Registered"):
        get_parser("does_not_exist")


def test_local_storage_writes_and_blocks_path_escape(tmp_path):
    storage = LocalStorage(tmp_path / "landing")
    path = storage.write_dataframe(pd.DataFrame({"a": [1]}), "schedule/x/events.csv")
    assert Path(path).read_text(encoding="utf-8").startswith("a\n")  # no BOM
    with pytest.raises(ValueError):
        storage.write_text("x", "../outside.txt")


def test_unknown_storage_backend_is_a_clear_error(monkeypatch):
    monkeypatch.setenv("STORAGE_BACKEND", "nope")
    with pytest.raises(ValueError, match="Available: local"):
        get_storage()


def test_run_all_writes_one_batch(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    events = events_to_frame([ClassEvent(source="", title="Yoga", weekday=1, start_time="18:00")])
    events["source"] = "Club A"
    events["loaded_at"] = "2026-11-14T04:00:00+01:00"
    clubs = pd.DataFrame({"name": ["Club A"], "url": ["https://a"]})
    errors = pd.DataFrame({"source": ["Club B"], "error": ["boom"]})
    monkeypatch.setattr(run_all, "run", lambda config, only: (events, clubs, errors))

    assert run_all.main([]) == 0

    (batch,) = list((tmp_path / "landing" / "schedule").iterdir())
    assert {p.name for p in batch.iterdir()} == {"events.csv", "clubs.csv", "errors.csv", "manifest.json"}
    manifest = json.loads((batch / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["rows"] == 1 and manifest["failed_sources"] == ["Club B"]
    written = pd.read_csv(batch / "events.csv")
    assert set(EVENT_COLUMNS) <= set(written.columns) and "loaded_at" in written.columns
    assert written.loc[0, "source"] == "Club A"


def test_run_all_fails_when_nothing_was_scraped(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setattr(
        run_all,
        "run",
        lambda config, only: (
            pd.DataFrame(),
            pd.DataFrame({"name": ["A"]}),
            pd.DataFrame({"source": ["A"], "error": ["x"]}),
        ),
    )
    assert run_all.main([]) == 1
