#!/usr/bin/env bash
# Monthly cron script: refresh cold storage data and refit SARIMA models.
# Suggested cron (3am on the 20th of each month — NASS releases around mid-month):
#   0 3 20 * * /var/lib/cold-storage-viz/refresh_data.sh >> /var/log/cold-storage-viz-refresh.log 2>&1

set -euo pipefail

DATA_DIR="/var/lib/cold-storage-viz/data"
IMAGE="cold-storage-viz:latest"

echo "[$(date -Iseconds)] Starting cold storage data refresh"

docker run --rm \
    --env-file /etc/cold-storage-viz.env \
    -v "$DATA_DIR:/app/data:rw" \
    "$IMAGE" \
    python fetch_data.py

echo "[$(date -Iseconds)] Data fetched, fitting SARIMA forecasts..."

docker run --rm \
    -v "$DATA_DIR:/app/data:rw" \
    "$IMAGE" \
    python fit_forecasts.py

echo "[$(date -Iseconds)] Refresh complete"

# Restart the app so it picks up the new parquet file
systemctl restart cold-storage-viz
