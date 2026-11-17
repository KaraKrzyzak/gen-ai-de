# Image for the daily ingestion (and later the API / bot). Only the core dependencies are
# installed (no torch / playwright): see [project.dependencies] in pyproject.toml.

# ---- stage 1: build the virtualenv -----------------------------------------------------
FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
# UV_NO_CACHE: do not keep downloaded wheels (they would be stored twice).
ENV UV_NO_CACHE=1 UV_LINK_MODE=copy UV_COMPILE_BYTECODE=1

COPY pyproject.toml uv.lock README.md ./
COPY src ./src
# Core dependencies + the project itself, installed (not editable) into /app/.venv.
RUN uv sync --frozen --no-dev --no-editable

# ---- stage 2: small runtime image ------------------------------------------------------
FROM python:3.12-slim

WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 DATA_DIR=/data
VOLUME /data

# Same entry point as on a laptop and in GitHub Actions.
CMD ["python", "-m", "gen_ai_de.ingestion.run_all"]
