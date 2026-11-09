#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
: "${COMPOSE_PROJECT_NAME:?Use a separate Compose project named aihub-drill-*}"
[[ "$COMPOSE_PROJECT_NAME" == aihub-drill-* ]] || { echo 'Use a separate drill project' >&2; exit 2; }
# The caller has already created synthetic browser data in this instance.
counts=$(docker compose exec -T db psql -U hub -d aihub -Atc 'SELECT count(*) FROM model_responses')
[[ "$counts" -gt 0 ]] || { echo 'Run the browser journey before this drill' >&2; exit 1; }
query="SELECT jsonb_build_array(p.project_id,c.conversation_id,m.message_id,m.content,m.source_hash,r.run_id,t.target_id,o.response_id,o.content,o.source_hash,v.version_num) FROM projects p JOIN conversations c USING(project_id) JOIN messages m USING(conversation_id) JOIN runs r USING(message_id) JOIN run_targets t USING(run_id) LEFT JOIN model_responses o USING(target_id) CROSS JOIN alembic_version v ORDER BY m.message_id,t.target_id"
snapshot() { docker compose exec -T db psql -U hub -d "$1" -Atc "$query"; }
before=$(snapshot aihub)
[[ -n "$before" ]]
archive=$(infra/scripts/backup.sh)
start=$SECONDS
restore="restore_$(date -u +%Y%m%d%H%M%S)_$$"
infra/scripts/restore.sh "$archive" "$restore"
[[ "$before" == "$(snapshot "$restore")" ]]
echo "Verified encrypted restore in $((SECONDS - start)) seconds."
docker compose restart db api web
docker compose up -d --wait web
[[ "$before" == "$(snapshot aihub)" ]]
curl --fail --silent --show-error "$PUBLIC_BASE_URL/v1/health"
echo ' Original project, conversation, run, message, revision and response records match after restart.'
