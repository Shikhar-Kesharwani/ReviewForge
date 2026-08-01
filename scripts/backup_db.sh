#!/usr/bin/env bash
# ==============================================================================
# Database Backup & Restore Automation Script for ReviewForge
# Supports both PostgreSQL (pg_dump) and SQLite (.db copy)
# ==============================================================================

set -e

BACKUP_DIR="./backups"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
mkdir -p "$BACKUP_DIR"

if [ -n "$DATABASE_URL" ]; then
    echo "📦 Backing up PostgreSQL Database..."
    pg_dump "$DATABASE_URL" | gzip > "$BACKUP_DIR/postgres_backup_$TIMESTAMP.sql.gz"
    echo "✅ Backup saved to $BACKUP_DIR/postgres_backup_$TIMESTAMP.sql.gz"
else
    echo "📦 Backing up SQLite Database..."
    if [ -f "./data/local.db" ]; then
        cp "./data/local.db" "$BACKUP_DIR/sqlite_backup_$TIMESTAMP.db"
        echo "✅ Backup saved to $BACKUP_DIR/sqlite_backup_$TIMESTAMP.db"
    else
        echo "⚠️ No local SQLite database found at ./data/local.db"
    fi
fi
