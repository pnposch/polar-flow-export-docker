# Copilot Instructions

## Overview

This is a Dockerized tool that exports training sessions from [Polar Flow](https://flow.polar.com) as TCX files. It uses Selenium (remote Chrome) to log in via SSO and scrape exercise IDs from the monthly diary view, then downloads each session via the Polar export API using transferred session cookies.

## Architecture

- **`polar-export.py`** — single-file Python script; all export logic lives here
- **`docker-compose.yml`** — two services: `selenium` (standalone Chrome) and `app` (export runner, container name `export`)
- **`bulk.sh`** — single `docker exec` call with `--start` / `--end` flags covering the full date range
- **`.env`** — credentials loaded into the `app` container at runtime (see `.env.example`)
- Output TCX files and `ids.txt` are written to the host volume mapped to `/data` inside the container

### Key flow

1. `validate_env()` checks all required env vars before touching Selenium
2. `build_driver()` connects to the remote Chrome service
3. `login()` handles SSO; a 5 s sleep follows to let the redirect settle
4. For each month in the requested range, `get_exercise_ids()` scrapes exercise IDs via Selenium
5. Before downloading each month's batch, cookies are refreshed from the live WebDriver into a `requests.Session` — this ensures the download session stays fresh across a long multi-month run
6. `download_exercises()` skips IDs already in `ids.txt` (idempotent reruns) and catches per-exercise errors without aborting the whole run
7. `save_ids()` persists the updated ID set after each month

## Running the tool

```bash
# Start services
docker compose up -d

# Export current month
docker exec -it export python3 polar-export.py

# Export a specific month (legacy positional args)
docker exec -it export python3 polar-export.py <month> <year>

# Export a date range
docker exec -it export python3 polar-export.py --start 2025-01 --end 2026-03

# Bulk export (edit start_month in bulk.sh first, then:)
./bulk.sh
```

## Environment variables (required)

| Variable        | Purpose                          |
|-----------------|----------------------------------|
| `POLAR_USER`    | Polar Flow username or email     |
| `POLAR_PASS`    | Polar Flow password              |
| `SELENIUM_HOST` | Hostname of the Selenium service |
| `SELENIUM_PORT` | Port of the Selenium service     |

Set `POLAR_USER` and `POLAR_PASS` in `.env` (see `.env.example`); the others are set by `docker-compose.yml`.

## Key conventions

- **ID deduplication**: `ids.txt` in the output dir is a persistent sorted set of downloaded exercise IDs. It is read once at startup and written after each month's batch. New IDs are union-merged; existing ones are skipped.
- **Cookie refresh per month**: a new `requests.Session` is built from `driver.get_cookies()` before each month's downloads to handle long-running sessions.
- **Output path**: defaults to `/data` inside the container — change the volume mount in `docker-compose.yml` to redirect output, or pass `--output-dir`.
- **Selenium wait**: `WebDriverWait` (10 s timeout) is used after diary navigation. Months with no exercises raise `TimeoutException`, which is caught and treated as an empty month.
- **Container name**: the `app` service is named `export` — `bulk.sh` and manual `docker exec` commands rely on this name.
- **Legacy positional args**: `polar-export.py <month> <year>` still works for single-month invocations.

## Dependency management

Dependencies are declared in both `pyproject.toml` (for `uv`) and `requirements.txt` (used by the Dockerfile). After any dependency change, regenerate `requirements.txt`:

```bash
uv export -o requirements.txt --no-hashes
```

Local dev:

```bash
uv sync
uv run python polar-export.py --start 2026-01 --end 2026-03
```
