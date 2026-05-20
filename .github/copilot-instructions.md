# Copilot Instructions

This repository is a small Dockerized Python tool that exports Polar Flow workouts as TCX files. The implementation is intentionally concentrated in `polar-export.py`; most useful Copilot help here comes from understanding the runtime flow and the persistence files in the output directory.

## Build, test, and lint commands

```bash
# Start the Selenium + app containers used by the normal workflow
docker compose up -d

# Export the current month from the running app container
docker exec export python3 polar-export.py

# Export a specific range
docker exec export python3 polar-export.py --start 2025-01 --end 2026-03

# Legacy single-month invocation still supported
docker exec export python3 polar-export.py 3 2026

# Bulk export from POLAR_START (or the default in bulk.sh) through the current month
./bulk.sh

# Local dependency setup for non-Docker development
uv sync

# Regenerate Docker requirements after dependency changes
uv export -o requirements.txt --no-hashes
```

There is currently **no repository-defined automated test suite or lint command**. Do not invent `pytest`, `ruff`, or similar targets in instructions unless the repo adds them later, so there is also no single-test command today.

## High-level architecture

- **`docker-compose.yml`** defines the real runtime topology: a remote `selenium/standalone-chrome` service plus an `app` container named **`export`**. Most documented commands assume that container name.
- **`polar-export.py`** owns the entire export pipeline:
  1. `validate_env()` fails fast if Polar or Selenium env vars are missing.
  2. `build_driver()` connects to the remote Selenium service rather than starting a local browser.
  3. `login()` performs Polar SSO in Selenium and waits until the redirect leaves the `flowSso` domain.
  4. `get_exercise_ids()` visits each monthly diary page and scrapes workout links from the calendar view.
  5. For each month, the script copies live Selenium cookies into a fresh `requests.Session`, mirrors browser headers, and downloads TCX files from the Polar export API.
  6. Download state is persisted in the output directory so reruns can skip work.
- **`bulk.sh`** is not a separate implementation path; it just wraps one long `docker exec export python3 polar-export.py --start ... --end ...` run so Selenium login and cookie state are reused across the whole date range.
- The host directory mounted to **`/data`** is part of the app's state model, not just an output folder: TCX files, `ids.txt`, and `completed_months.txt` all live there.

## Key conventions

- **Single-file core logic:** keep workflow changes in `polar-export.py` unless there is a strong reason to split it. Architecture, CLI parsing, Selenium scraping, and download behavior currently live together.
- **Persistent skip state lives in output files:** `ids.txt` is the sorted set of already-downloaded exercise IDs, and `completed_months.txt` tracks months that finished successfully. Changes to rerun behavior usually need both files considered together.
- **Current month is special:** completed-month skipping does **not** apply to the current month, because new workouts can still appear there.
- **Month completion is conservative:** empty months are marked complete immediately, but months with any download failure are **not** marked complete, so future runs retry them.
- **Cookie refresh happens per month:** the `requests.Session` is rebuilt from `driver.get_cookies()` before each monthly batch. Preserve that pattern for long-running exports instead of reusing one stale session for the entire run.
- **Date handling is month-based:** CLI dates are `YYYY-MM`, internally normalized to the first day of the month, and `--end` is capped to the current month.
- **Docker and local dependency metadata both matter:** dependencies are declared in `pyproject.toml` for `uv`, but the Docker image installs from `requirements.txt`, so dependency updates are incomplete unless both stay in sync.
- **Runtime prerequisites come from env + compose:** `POLAR_USER` and `POLAR_PASS` belong in `.env`; `SELENIUM_HOST` and `SELENIUM_PORT` are injected by Compose. Copilot should preserve that split instead of hardcoding values in scripts.
