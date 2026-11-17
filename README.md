# gen-ai-de

A small data platform about fitness / dance classes in the Tri-City area: scrape class
schedules every day, keep the history, enrich it (activity types, calories, distances,
weather) and finally ask questions from a phone ("what is within 5 km, what is worth
going to if I want to get tired").

**Status:** step 1 of 7 is done (daily-capable ingestion, config, storage, Docker files, tests).
Databricks, enrichment, ML, the app and RAG are still to do - see [Roadmap](#roadmap).

Target architecture (all free tiers):

```
 ingest (GitHub Actions cron / laptop / Docker on a VM)
   -> files in a landing area (local folder now, Databricks volume next)
   -> Databricks medallion: bronze -> silver -> gold, small ML
   -> serving store (Postgres + pgvector or DuckDB) -> API / Telegram bot -> phone
```

## 1. What is where

```
gen-ai-de/
├─ src/gen_ai_de/                 the Python package (all real code lives here)
│  ├─ config.py                   settings from environment variables / .env
│  ├─ storage.py                  where ingestion output goes (backend = STORAGE_BACKEND)
│  └─ ingestion/
│     ├─ run_all.py               THE entry point for the automated daily run
│     ├─ schedule/                class schedules from 11 clubs (details: schedule/README.md)
│     │  ├─ list_schedule.yml     the list of clubs + which parser reads each one
│     │  ├─ run.py, loader.py, models.py, registry.py, register_parsers.py
│     │  └─ aka.py fitssey.py perfectgym.py wod_guru.py fitro.py activklub.py efitness.py delta_sections.py
│     └─ reference/               static reference data for later enrichment
│        ├─ met.csv               MET values (Compendium of Physical Activities): 1111 activities
│        └─ calories.py           downloads Kaggle datasets (calories per kg, gym check-ins)
├─ tests/                         pytest; parsers are tested on saved samples in tests/fixtures/
├─ deploy/                        Dockerfile + docker-compose.yml (service `ingest`)
├─ data/                          local working area (gitignored): landing files, downloads
├─ auto/                          separate experiment, ignored by this README and by pytest/ruff
├─ pyproject.toml, uv.lock        dependencies (uv) and pytest / ruff settings
├─ .env.example                   all settings with comments (copy to .env)
└─ code.md                        short cheat sheet of dev commands
```

### Clubs currently scraped (11)

| Club | Parser | Kind |
|---|---|---|
| Akademia Artystyczna | `aka` | static weekly timetable |
| Czulosfera, WCR Pilates, Dance Atelier | `fitssey` | dated, with free spots |
| Well Fitness Osowa, Well Fitness Gdynia | `perfectgym` | dated, with free spots |
| Esensai Pole Dance Studio | `wod_guru` | dated, with free spots |
| Lekko Studio | `fitro` | dated |
| Active Fikakowo | `activklub` | static weekly timetable |
| Energy Club Wielkopolska | `efitness` | dated (hour only), free spots |
| Delta Climb | `delta_sections` | static weekly sections |

Two tables come out of every run: `events.csv` (one row per class + `loaded_at`) and
`clubs.csv` (the YAML, one row per club). Join with `events.source == clubs.name`.
Column list and step-by-step description of a run: `src/gen_ai_de/ingestion/schedule/README.md`.

## 2. How to run

Everything is run **from the repository root**.

```bash
uv sync                                              # core dependencies (once)
# uv sync --extra nlp --extra browser                # optional heavy extras (see below)
cp .env.example .env                                 # optional: change settings

# daily ingestion: scrape all clubs -> data/landing/schedule/<yyyy-mm-dd_hhmmss>/
uv run python -m gen_ai_de.ingestion.run_all
uv run python -m gen_ai_de.ingestion.run_all --only "Akademia Artystyczna"   # one club

# same scrape, Excel-friendly CSVs (UTF-8 with BOM) in data/schedule_output/
uv run python -m gen_ai_de.ingestion.schedule.run

# reference data from Kaggle -> data/reference/ (may ask for Kaggle credentials)
uv run python -m gen_ai_de.ingestion.reference.calories

# tests and code quality
uv run pytest
uv run ruff check
uv run ruff format

# Docker (Docker Desktop must be running); output goes to ./data
docker compose -f deploy/docker-compose.yml build           # build the image (~420 MB)
docker compose -f deploy/docker-compose.yml run --rm ingest # run the scrape in the container
```

A run writes into one new folder and never overwrites older ones, so history accumulates:
`events.csv`, `clubs.csv`, `manifest.json` (counts per club) and `errors.csv` (only if a club failed).
The exit code is 1 only when **no** club produced data.

Settings (environment variables or `.env`, read by `src/gen_ai_de/config.py`):

| Variable | Default | Meaning |
|---|---|---|
| `DATA_DIR` | `data` | local working area |
| `STORAGE_BACKEND` | `local` | where ingestion writes (`local` today) |
| `LOG_LEVEL` | `INFO` | logging level |

Dependencies are split so the Docker image stays small:
- **core** (`uv sync`): pandas, requests, beautifulsoup4, pyyaml, kagglehub... everything the daily
  ingestion needs.
- **`nlp`** extra: `torch`, `transformers`, `sentence-transformers` (embeddings / text similarity).
  On x86 Linux `torch` pulls GBs of CUDA wheels, so it is **not** in the Docker image.
- **`browser`** extra: `playwright`, only for `discover.py` (finding a new club's data endpoint).

Tips:
- Plain `uv run ...` is enough. Do not add `--active`: it installs into whatever environment is
  currently active (e.g. a conda env) instead of the project's `.venv`.
- To add a club: add an entry to `list_schedule.yml` and run with `--only "<name>"`. To add a new
  platform: write a parser (guide in `schedule/README.md`).

## 3. Design rules (so a VM can be added later without rewriting)

1. Configuration only through environment variables (`config.py`), no hard-coded paths or hosts.
2. One entry point for every environment: `python -m gen_ai_de.ingestion.run_all`.
3. Docker from the start; `docker-compose.yml` will grow (`db`, `api`, `bot`) when a VM is added.
4. Storage is a switchable backend (`STORAGE_BACKEND`); parsers never know where files end up.
5. No state inside containers or the repo; secrets in `.env` or GitHub Secrets, never in the image.
6. Nothing outside `medallion/` and the upload code should depend on Databricks.

## 4. Roadmap

Plan: daily ingest in GitHub Actions (free), processing in Databricks Free Edition, a VM
(e.g. Oracle Always Free) only when the app needs an always-on service.

| # | Step | State |
|---|---|---|
| 1 | Foundation: package layout, env config, storage backend, Docker files, parser tests, ruff | **done** |
| 2 | Automatic ingest: GitHub Actions workflow (daily cron + manual run), upload to a Databricks volume, weather (Open-Meteo) | to do |
| 3 | Databricks medallion: bronze / silver / gold, stable `class_series` and `instructor` ids, job as a Databricks Asset Bundle | to do |
| 4 | Enrichment: title -> `activity_type` mapping (rules, embeddings, agent; cached in `title_mapping`), MET / calories, distances, text similarity | to do |
| 5 | Small ML: predict how full a class will be (needs a few weeks of daily snapshots) | to do |
| 6 | Serving + app: Postgres / pgvector on a VM, API, Telegram bot, reviews and opinions | to do |
| 7 | RAG over articles and reviews, with guardrails | to do |

### Loose ends from step 1

- **Docker image:** built and tested (420 MB; a run in the container returns the same 912 rows).
  The first version was ~15 GB because `torch`'s CUDA dependencies were still installed; fixed by moving
  `torch` / `transformers` / `sentence-transformers` / `playwright` to optional extras and by a
  multi-stage Dockerfile without the uv cache. When embeddings are needed on a VM, build a separate
  image with `--extra nlp` (on ARM `torch` has no CUDA packages; on x86 use the CPU index).
- **Club coordinates:** most `latitude` / `longitude` in `list_schedule.yml` are still `null`.
  They are needed for "within 5 km" - fill them by geocoding addresses (step 4).
- **`calories.py`** still runs its code at import time and uses the deprecated `kagglehub.load_dataset`
  (renamed to `dataset_load`). It should become a function that writes to `data/reference/`.
- **Medicover / Multisport / OK System flags** are `null` for all clubs except Akademia Artystyczna.
- **Data checks:** Delta Climb is hosted on a `*.chatgpt.site` address (verify it is the club's real page);
  the club name "Energy Club Wielkopolska" has the URL `energyclub-gdynia2` (verify which club it is);
  Lekko Studio is at ul. Wielkopolska 395 in Gdynia, so the two names may have been mixed up.
- **Empty folders** `data_capture/health` and `data_capture/schedule` remain (Windows locked them while
  an IDE had them open). Delete `data_capture/` by hand.

### Open questions (decide before steps 2-7)

- Does the Databricks Free workspace allow outbound internet (could the scraper run there instead of
  GitHub Actions), and does it offer Vector Search, Foundation Model API and `databricks bundle deploy`?
- Where do reviews and opinions come from: only typed in by you, or also collected from other sites?
- Which LLM to use on a free tier (Databricks Foundation Model API, Groq, Gemini, a small local model)?
- Is a Telegram bot an acceptable phone interface, or should it be a web app (PWA)?

## 5. Data model (target, from step 3 on)

- `dim_club`, `dim_class_series` (stable id: club + normalised title + weekday + time),
  `dim_instructor`, `dim_activity_type` (+ MET).
- `fact_class_event`, `fact_availability_snapshot` (free spots over time), `fact_review`
  (written by the user, so it needs a small operational store, not Databricks Free),
  `fact_weather_forecast`, `document` / `chunk` with embeddings.
- Medallion layers: bronze = raw files appended with `loaded_at`; silver = typed and deduplicated;
  gold = ready for questions and ML (events + clubs + activity type + calories).
