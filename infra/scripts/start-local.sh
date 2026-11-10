#!/bin/sh
set -eu
cd "$(dirname "$0")/../.."
for file in db_password owner_password; do
    if [ ! -r ".secrets/$file" ] || [ ! -s ".secrets/$file" ]; then
        echo 'Local bootstrap configuration is missing, unreadable or empty. Run infra/scripts/init-local.sh and retry. Existing secret files are never overwritten; repair empty files locally.' >&2
        exit 1
    fi
done
exec docker compose up -d --build --wait web
