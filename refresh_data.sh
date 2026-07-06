#!/usr/bin/env bash
# Monthly cron script: refresh cold storage data, refit SARIMA models, restart the app.
# Runs relative to the repo checkout it lives in. Example crontab (6am on the 25th —
# NASS releases the Cold Storage report in the third or fourth week of the month):
#   0 6 25 * * /path/to/repo/refresh_data.sh >> /var/log/cold-storage-viz-refresh.log 2>&1
#
# Podman users: local images are fully qualified — invoke as
#   COLD_STORAGE_IMAGE=localhost/cold-storage-viz:latest ./refresh_data.sh

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMAGE="${COLD_STORAGE_IMAGE:-cold-storage-viz:latest}"

echo "[$(date -Iseconds)] Starting cold storage data refresh"

# API key (from .env) is only needed for the fetch step
docker run --rm \
    --env-file "$REPO_DIR/.env" \
    -v "$REPO_DIR/data:/app/data:rw" \
    "$IMAGE" \
    python fetch_data.py

echo "[$(date -Iseconds)] Data fetched, fitting SARIMA forecasts (~50 min)..."

docker run --rm \
    -v "$REPO_DIR/data:/app/data:rw" \
    "$IMAGE" \
    python fit_forecasts.py

echo "[$(date -Iseconds)] Refresh complete, restarting app"

# Requires passwordless sudo for this command, or run the script as root
sudo systemctl restart cold-storage-viz
