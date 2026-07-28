#!/usr/bin/env bash
# Copy gptimage production databases to rust gateway data dir (read-only snapshot).
# Run ON panda. Does not modify chatgpt2api-local :8012 data.
#
# Usage:
#   bash scripts/panda_sync_gptimage_db.sh
#   SOURCE_CONTAINER=chatgpt2api-local bash scripts/panda_sync_gptimage_db.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE_CONTAINER="${SOURCE_CONTAINER:-chatgpt2api-local}"
STAMP="$(date -u +%Y%m%d-%H%M%S)"
DEST="$ROOT/data/gptimage"
BACKUP="$ROOT/data/gptimage-backup/$STAMP"

mkdir -p "$DEST" "$BACKUP"

for db in accounts.db image_tasks.db image_reference_assets.db; do
  if docker exec "$SOURCE_CONTAINER" test -f "/app/data/$db" 2>/dev/null; then
    echo "==> copy $db"
    docker cp "$SOURCE_CONTAINER:/app/data/$db" "$BACKUP/$db"
    cp -a "$BACKUP/$db" "$DEST/$db"
    chmod 600 "$DEST/$db"
  else
    echo "skip: $db not in $SOURCE_CONTAINER"
  fi
done

echo "SYNC_OK backup=$BACKUP dest=$DEST"
ls -la "$DEST"
