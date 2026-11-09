#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
umask 077
dir=${1:-backups}
mkdir -p "$dir"
dest=$(mktemp "$dir/hub-$(date -u +%Y%m%dT%H%M%SZ)-XXXXXX")
trap 'unlink "$dest"' EXIT
docker compose exec -T db pg_dump --format=custom --no-owner -U hub aihub |
    gpg --batch --yes --pinentry-mode loopback --passphrase-file .secrets/backup_password \
        --symmetric --cipher-algo AES256 --output "$dest"
mv "$dest" "$dest.gpg"
trap - EXIT
echo "$dest.gpg"
