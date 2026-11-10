# Personal AI Decision Hub

A single-owner workspace for keeping questions and original model responses together across conversations. This first increment implements authenticated local projects, append-only history and manual comparisons. A run preserves the exact pasted answer, its hash, acquisition mode and user-declared model identity. A target can remain pending while other answers are available.

[GitHub Project](https://github.com/users/Jim-lan/projects/1/views/1) · [Frozen design](docs/architecture/baseline-v2.0.md) · [P0 implementation tasks](tasks/README.md) · [Target HTTP contract](docs/api/openapi.yaml)

## Start on your Mac

Use Docker Desktop with Compose, Bash and OpenSSL. From the repository root:

```sh
infra/scripts/init-local.sh
infra/scripts/start-local.sh
```

Open **http://localhost:8080** and enter the password from the local file **.secrets/owner_password**. The initializer generates it once. The account and password hash persist in PostgreSQL. Use the same hostname in your browser and in PUBLIC_BASE_URL so the origin check succeeds. For a different port, copy .env.example to .env and change both values.

Choose **New project**, give it a name, then choose **New conversation**. Enter a question. To compare originals, enter comma-separated manual model names and choose **Start comparison**. Open a target, paste its answer and select **Save original**. A refresh restores the selected conversation and the saved text. Leave the model field empty to record a standalone question. Manual targets have a 24-hour deadline.

The default Compose stack publishes only the web port on loopback. It makes no model calls. Gemini eligibility, pricing, budgets, queued execution, synthesis, reviewed memory and versioned decisions are tracked in the backlog.

## Development checks

```sh
docker compose run --build --rm tests
docker compose exec -T api python -m app.openapi > /tmp/hub-openapi.json
diff contracts/openapi.json /tmp/hub-openapi.json
```

Integration tests create and remove a uniquely named PostgreSQL database. CI also builds the React bundle and exercises login, project creation, concurrent history writes, run replay, manual import and restoration. The CI workflow includes a separate browser/recovery rehearsal with synthetic content.

Run the foundation preflight tests without Docker:

```sh
python3 -m unittest infra/tests/test_local_bootstrap.py
```

## Backup and restore

Install GnuPG for the backup commands. Store a separate recovery copy of **.secrets/backup_password**. Keep encrypted archives outside the laptop for recovery from disk loss.

```sh
infra/scripts/backup.sh
infra/scripts/restore.sh backups/example.gpg restore_check
```

Use the archive path printed by the backup command. The restore command requires a fresh database name beginning with restore_. It rejects existing databases. The full archive includes owner credentials in hashed form and session records. Treat the recovery key as a secret. The local drill compares original IDs, exact text, content hashes and Alembic revision after restore and after container restart. Automated off-host scheduling and the full release recovery objective remain in Sprint 4.

Use `docker compose stop` to pause the application and keep its database volume.
