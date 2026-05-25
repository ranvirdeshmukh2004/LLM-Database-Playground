#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# backup.sh — PostgreSQL backup script
# Run via cron: 0 3 * * * /opt/scripts/backup.sh
# ═══════════════════════════════════════════════════════════════

set -e

BACKUP_DIR="/opt/backups/postgres"
CONTAINER="supabase-db"
DB_NAME="${POSTGRES_DB:-postgres}"
DB_USER="${POSTGRES_USER:-postgres}"
KEEP_DAYS=7

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Generate timestamp
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/backup_${TIMESTAMP}.sql.gz"

echo "[$(date)] Starting PostgreSQL backup..."

# Dump and compress
docker exec "$CONTAINER" pg_dump -U "$DB_USER" "$DB_NAME" | gzip > "$BACKUP_FILE"

# Check if backup was created
if [ -f "$BACKUP_FILE" ]; then
    SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    echo "[$(date)] Backup created: $BACKUP_FILE ($SIZE)"
else
    echo "[$(date)] ERROR: Backup failed!"
    exit 1
fi

# Clean old backups
find "$BACKUP_DIR" -name "backup_*.sql.gz" -mtime +$KEEP_DAYS -delete
echo "[$(date)] Cleaned backups older than $KEEP_DAYS days"

# Optional: sync to S3
# aws s3 cp "$BACKUP_FILE" "s3://your-bucket/backups/"

echo "[$(date)] Backup complete."
