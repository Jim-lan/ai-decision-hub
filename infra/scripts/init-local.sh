#!/bin/sh
set -eu
cd "$(dirname "$0")/../.."
umask 077
mkdir -p .secrets
for file in db_password owner_password backup_password; do
    if [ ! -e ".secrets/$file" ]; then
        tmp=$(mktemp ".secrets/$file.XXXXXX")
        openssl rand -hex 24 > "$tmp"
        # Atomic no-overwrite publication, including concurrent initialization.
        ln "$tmp" ".secrets/$file" 2>/dev/null || test -s ".secrets/$file"
        unlink "$tmp"
    fi
    test -s ".secrets/$file"
done
echo 'Local secret files are ready in .secrets/.'
