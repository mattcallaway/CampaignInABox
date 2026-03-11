#!/usr/bin/env bash
# deployment/scripts/restore_campaign.sh
set -e

cd "$(dirname "$0")/../.."

if [ -z "$1" ]; then
    echo "Usage: ./restore_campaign.sh <path_to_backup.tar.gz>"
    echo "Available backups in archive/:"
    ls -l archive/*.tar.gz || echo "No backups found."
    exit 1
fi

BACKUP_FILE="$1"

if [ ! -f "$BACKUP_FILE" ]; then
    echo "Error: Backup file $BACKUP_FILE not found."
    exit 1
fi

echo "=============================================="
echo " Campaign In A Box — Restore System"
echo "=============================================="
echo "WARNING: Restoring will overwrite current config and derived data."
read -p "Are you sure you want to proceed? (y/n): " confirm
if [ "$confirm" != "y" ]; then
    echo "Restore aborted."
    exit 0
fi

echo "Extracting backup..."
tar -xzf "$BACKUP_FILE"

echo "✓ Restore complete from $BACKUP_FILE"
echo "=============================================="
