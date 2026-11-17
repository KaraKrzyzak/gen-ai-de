# Class schedule capture

Collects class timetables (dance, pole dance, stretching, pilates...) from many
studios and gyms into **one table** (`events.csv`, one row per class, with the
load time) plus a **clubs table** (`clubs.csv`, one row per studio, copied from
`list_schedule.yml`). Join them on `events.source == clubs.name`.

Location in the repo: `src/gen_ai_de/ingestion/schedule/` (package
`gen_ai_de.ingestion.schedule`). Shared pieces live one level up:
`src/gen_ai_de/config.py` (settings from environment variables),
`src/gen_ai_de/storage.py` (where output files go) and
`src/gen_ai_de/ingestion/run_all.py` (the automated entry point).

## 1. What each file does

| File | Purpose |
|---|---|
| `list_schedule.yml` | The list of sources. One entry per studio: `name`, `url`, `parser`, `schedule_type`, coordinates, Medicover / Multisport / OK System flags, plus parser-specific keys (`studio_id`, `club_id`, `timetable_id`). `enabled: false` skips an entry. |
| `loader.py` | Reads the YAML into a flat DataFrame (one row per studio). Nested flags become columns such as `medicover.dance`. Validates required keys and duplicate names. |
| `models.py` | The common data model: `ClassEvent` and the standard column list `EVENT_COLUMNS`. Every parser must return these columns. |
| `registry.py` | Maps the YAML `parser` value to a Python function (`@register("name")` / `get_parser`). |
| `register_parsers.py` | Imports every parser module so their `@register` decorators run. Add one name per new parser. |
| `aka.py` | Parser `aka` - Akademia Artystyczna, a static weekly HTML timetable (weekday + time only, no dates). |
| `fitssey.py` | Parser `fitssey` - studios on Fitssey (`app.fitssey.com/<studio>/frontoffice`). Calls the anonymous JSON endpoint the public page uses. Needs `studio_id`. |
| `perfectgym.py` | Parser `perfectgym` - clubs on PerfectGym Client Portal. Calls the public `WeeklyClasses` endpoint. Needs `club_id` (or it is read from the URL). |
| `wod_guru.py` | Parser `wod_guru` - studios on wod.guru (Esensai). JSON endpoint `<studio_id>.wod.guru/classes/get-data`. Needs `studio_id`. |
| `fitro.py` | Parser `fitro` - studios on Fitro (Lekko). Public JSON `api.fitro.pl/.../events`. Optional `studio_id` (defaults to the subdomain). |
| `activklub.py` | Parser `activklub` - Active Klub weekly timetable (static). Needs `timetable_id`; retries when rate-limited (HTTP 429). |
| `efitness.py` | Parser `efitness` - eFitness club sites. No API: scrapes the server-rendered weekly HTML table. Only the hour is known, not the minute. |
| `delta_sections.py` | Parser `delta_sections` - Delta Climb sign-up page (static weekly sections, JSON at `/api/sections`). |
| `discover.py` | Helper for writing a new parser: opens a browser, records every JSON response the page loads, so you can find the schedule endpoint. Needs the `browser` extra: `uv sync --extra browser` (then `uv run playwright install chromium`). |
| `run.py` | Scrapes every enabled source and returns `(events, clubs, errors)`. Run as a module it also writes human-friendly CSVs (UTF-8 with BOM, for Excel) to `<DATA_DIR>/schedule_output/`. |
| `../run_all.py` | The **automated** entry point (laptop, GitHub Actions, Docker): calls `run.py`, then writes one timestamped batch through the storage backend. |

### Output of `run_all` (local backend)

`<DATA_DIR>/landing/schedule/<yyyy-mm-dd_hhmmss>/` (UTC time, one folder per run):

| File | Content |
|---|---|
| `events.csv` | All classes from all sources (see columns below). |
| `clubs.csv` | The YAML as a table, one row per club (all clubs, also disabled ones): `name`, `url`, `parser`, `schedule_type`, `latitude`, `longitude`, `medicover.*`, `multisport.*`, `ok_system.*`, `studio_id`, `club_id`, `timetable_id`. |
| `errors.csv` | Only present if some source failed. |
| `manifest.json` | Batch id, `loaded_at`, row count, rows per source, failed sources. |

Files are plain UTF-8 (no BOM) because they are meant for machines (Spark / Auto Loader).
Each run adds a new folder; nothing is overwritten, so history is kept.

### Output columns (`events.csv`)

- `source` - the studio name from the YAML (key to join with `clubs.name`).
- `title`, `weekday` (0 = Mon), `start_time`, `start`, `end`, `duration_min`,
  `instructors`, `spots_total`, `spots_booked`, `spots_free`, `room`,
  `category`, `level`, `price`, `url` (link to the class if the source has one) -
  empty when the source does not provide the value. Static schedules
  (`schedule_type: static`) have only `weekday` + `start_time`, no `start`/`end`.
- Club metadata (URL, coordinates, Medicover / Multisport flags...) is **not**
  repeated here - it is in `clubs.csv`.
- `loaded_at` - when the data was fetched (ISO timestamp with timezone).

## 2. How to run

Install dependencies once from the repository root:

```bash
uv sync
```

Run **from the repository root**:

```bash
# automated entry point: all enabled sources -> data/landing/schedule/<batch>/
uv run python -m gen_ai_de.ingestion.run_all

# a single source, by its YAML name
uv run python -m gen_ai_de.ingestion.run_all --only "Akademia Artystyczna"

# same scrape, but Excel-friendly CSVs in data/schedule_output/
uv run python -m gen_ai_de.ingestion.schedule.run

# in Docker (the daemon must be running); output goes to ./data
docker compose -f deploy/docker-compose.yml run --rm ingest
```

Settings come from environment variables or a local `.env` (copy `.env.example`):
`DATA_DIR` (default `data`), `STORAGE_BACKEND` (default `local`), `LOG_LEVEL`.
One broken source does not stop the others; failed sources are listed in `errors.csv`
and `manifest.json`. `run_all` exits with code 1 only if **no** source produced data.

Tests (no network; parsers run on saved samples in `tests/fixtures/`):

```bash
uv run pytest
uv run ruff check
```

### What happens when you run `run_all` (step by step)

1. **Start-up** (`run_all.main`). `config.get_settings()` reads the environment
   (and `.env`); logging is set up.
2. **Arguments.** `argparse` reads `--config` (default `list_schedule.yml`) and
   `--only` (optional club name).
3. **Import parsers** (`run.py`). It imports `register_parsers`, which imports every
   parser module (`aka`, `fitssey`, `perfectgym`, `wod_guru`, `fitro`, `activklub`,
   `efitness`, `delta_sections`). Each module runs its `@register("<type>")`
   decorator, which stores the parser function in the dictionary in `registry.py`.
4. **Load the YAML** (`loader.load_schedules`). The file is parsed with
   `yaml.safe_load`. Each entry is checked for the required keys (`name`, `url`,
   `parser`, `schedule_type`) and for duplicate names. Nested blocks are
   flattened, e.g. `medicover: {dance: true}` becomes the column
   `medicover.dance`. The result is the **clubs table**, one row per club.
5. **Select sources** (`run.run`). Rows with `enabled: false` are dropped. With
   `--only "<name>"` just that club stays. (The clubs table keeps all clubs.)
6. **Loop over the sources.** For each remaining club:
   1. The row is turned into a `config` dict (empty values are removed by
      `clean_config`).
   2. `registry.get_parser(config["parser"])` returns the parser function.
   3. The parser is called with `config`. It downloads the data (JSON endpoint or
      HTML), maps every class to a `ClassEvent` (`models.py`) and returns a
      DataFrame with the standard columns via `events_to_frame`.
   4. `run.py` writes the club name from the YAML into the `source` column.
   5. If the parser raises, the error is logged and stored for `errors.csv`;
      the loop continues with the next club.
7. **Merge** (`run.run`). The per-club DataFrames are concatenated into one table,
   `source` is moved to the first column and `loaded_at` (current time, ISO
   format with timezone) is added to every row.
8. **Write one batch** (`run_all.main` + `storage.py`). A batch folder name is built from
   the current UTC time. `get_storage()` picks the backend from `STORAGE_BACKEND`
   (today only `local`) and writes `events.csv`, `clubs.csv`, `errors.csv`
   (only if something failed) and `manifest.json`.
9. **Summary and exit code.** The log shows rows per run and failed sources; the
   process exits with 1 if no events were scraped at all (so a scheduler notices).

### Adding a new studio

1. Add an entry to `list_schedule.yml` with an existing `parser` value
   (for Fitssey: the `studio_id` from the URL; for PerfectGym: the `club_id`).
2. Run `uv run python -m gen_ai_de.ingestion.run_all --only "<name>"`.

### Adding a new parser type

1. Find the data endpoint:
   `uv sync --extra browser` once, then
   `uv run python -m gen_ai_de.ingestion.schedule.discover <page url> --out data/captures/<name>`
   (a browser opens; click through the schedule, then press Enter in the terminal).
   Look in `data/captures/<name>/index.json` for the request that returns the classes.
2. Create `<type>.py` here with a function `fn(config: dict) -> pandas.DataFrame`
   decorated with `@register("<type>")`. Build rows with `ClassEvent` and return
   `events_to_frame(events)`. Keep the response-to-events step in its own function
   (e.g. `parse_payload`) so it can be tested.
3. Add the module to the import list in `register_parsers.py`.
4. Save a trimmed real response in `tests/fixtures/` and add a test in
   `tests/test_schedule_parsers.py`.
5. Set `parser: "<type>"` (and remove `enabled: false`) in the YAML.

### Notes

- A source whose parser is not written yet should get `enabled: false` in the YAML.
- Dynamic sources return about two weeks ahead (`WEEKS_AHEAD` in each parser file).
  Lekko (Fitro) returns what the API gives for that range; Energy Club (eFitness)
  starts at the Monday of the current week.
- A new key in the YAML (e.g. `club_id`) only appears in `clubs.csv` as a new column.
