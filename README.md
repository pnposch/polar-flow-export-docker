Polar Flow Exporter Docker
=========================

A tool for exporting training sessions from [Polar Flow](https://flow.polar.com) as TCX files.

## Updates
- Moved Selenium to Docker
- Adjusted login for new Polar Auth (July 2025)
- Refactored to single Selenium session across months (faster bulk exports)
- Added `--start` / `--end` / `--output-dir` CLI flags

## Installation

```bash
git clone https://github.com/pnposch/polar-flow-export.git
cp .env.example .env   # fill in your credentials
docker compose up -d
```

## Usage

Export the current month:
```bash
docker exec -it export python3 polar-export.py
```

Export a specific month:
```bash
docker exec -it export python3 polar-export.py <month> <year>
```

Export a date range:
```bash
docker exec -it export python3 polar-export.py --start 2025-01 --end 2026-03
```

TCX files are saved to the host directory mapped to `/data` inside the container (configured in `docker-compose.yml`).

### Bulk download

Edit `start_month` in `bulk.sh`, then:

```bash
./bulk.sh
```

`bulk.sh` runs a single export session from `start_month` to the current month — one login, no redundant reconnects.

### Automated monthly export (on first boot of each month)

Because the computer may not be on at a fixed time, `monthly-export.sh` uses a marker file (`~/.polar-monthly-export-last-run`) to run the previous month's export exactly once — on the first boot of each new month. Subsequent boots that month are silent no-ops.

The script also starts the Docker containers if they are not running, waits for the Selenium health check, and logs everything to `cron.log` in the repo directory.

**Setup — run once:**

```bash
# Make executable (already done if you cloned fresh)
chmod +x /path/to/polar-flow-export/monthly-export.sh

# Add to crontab (runs 60 s after every boot to let networking settle)
(crontab -l 2>/dev/null; echo "@reboot sleep 60 && /path/to/polar-flow-export/monthly-export.sh") | crontab -
```

Replace `/path/to/polar-flow-export` with the absolute path to this repo.

To verify it is registered:

```bash
crontab -l
```

Logs are written to `cron.log` in the repo directory.


