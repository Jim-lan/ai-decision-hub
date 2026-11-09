#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
archive=${1:?Pass an encrypted backup file}
target=${2:?Pass a new database name starting with restore_}
[[ "$target" =~ ^restore_[a-z0-9_]{1,50}$ ]] || { echo 'Invalid restore database name' >&2; exit 2; }
test -r "$archive"
# createdb fails for existing names. A failed restore never changes the live DB.
docker compose exec -T db createdb -U hub "$target"
gpg --batch --pinentry-mode loopback --passphrase-file .secrets/backup_password --decrypt "$archive" |
    docker compose exec -T db pg_restore -U hub -d "$target" --no-owner --exit-on-error --single-transaction
docker compose exec -T db psql -U hub -d "$target" -Atc 'SELECT version_num FROM alembic_version'
