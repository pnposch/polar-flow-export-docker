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

