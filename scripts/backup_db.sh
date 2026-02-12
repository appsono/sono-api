#!/bin/bash

#load environment variables
set -a
source .env
set +a

BACKUP_DIR="./backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/sono_db_$TIMESTAMP.sql.gz"

#create backup directory if it doesnt exist
mkdir -p $BACKUP_DIR

#create backup
echo "Creating backup: $BACKUP_FILE"
docker exec sono_postgres_db pg_dump -U $POSTGRES_USER $POSTGRES_DB | gzip > $BACKUP_FILE

#keep only last 7 days of backups
find $BACKUP_DIR -name "sono_db_*.sql.gz" -mtime +7 -delete

echo "Backup completed: $BACKUP_FILE"