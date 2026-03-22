#!/bin/bash
set -euo pipefail

# First month to consider. Override with: POLAR_START=2015-06 ./bulk.sh
start_month="${POLAR_START:-2014-01}"
end_month=$(date +%Y-%m)

if ! docker inspect -f '{{.State.Running}}' export 2>/dev/null | grep -q true; then
  echo "Error: container 'export' is not running. Run 'docker compose up -d' first." >&2
  exit 1
fi

echo "==> Bulk export: $start_month → $end_month (already-completed months will be skipped)"
docker exec export python3 polar-export.py --start "$start_month" --end "$end_month"
