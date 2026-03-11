#!/usr/bin/env bash
# deployment/scripts/backup_campaign.sh
set -e

cd "$(dirname "$0")/../.."

BACKUP_DIR="archive"
mkdir -p "$BACKUP_DIR"
DATE_STR=$(date +"%Y_%m_%d_%H%M%S")
BACKUP_ARCHIVE="${BACKUP_DIR}/backup_${DATE_STR}.tar.gz"

echo "=============================================="
echo " Campaign In A Box — Backup System"
echo "=============================================="

# Define directories to back up
# We deliberately exclude data/voters and data/campaign_runtime to prevent
# accidental distribution of sensitive info in routine backups.
TARGETS="config derived reports data/elections data/intelligence/public"

# Filter to only targets that actually exist
EXISTING_TARGETS=""
for T in $TARGETS; do
    if [ -d "$T" ] || [ -f "$T" ]; then
        EXISTING_TARGETS="$EXISTING_TARGETS $T"
    fi
done

echo "Creating secure tarball of campaign config and outputs..."
tar -czf "$BACKUP_ARCHIVE" $EXISTING_TARGETS

echo "✓ Backup created successfully at: $BACKUP_ARCHIVE"
echo "=============================================="
