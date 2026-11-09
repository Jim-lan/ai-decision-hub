# Local implementation baseline

The first increment adopts ADR-001, ADR-002 and ADR-006 from the proposed baseline for implementation. FastAPI owns the HTTP interface, PostgreSQL owns durable history, Alembic versions the schema and Docker Compose supplies the local runtime. React uses the same origin as the API. Each message is an append-only source record.

The owner selected manual response import before official API integration. Gemini is the first candidate pending account-specific validation. ADR-003 through ADR-005 and ADR-007 through ADR-008 remain design targets for their respective increments. LangGraph execution state will be separate from canonical conversations. The first increment requires no provider key, paid inference or remote host.

The login uses a single owner and a revocable session. A local password file initializes the account on first startup. Subsequent starts retain the database identity. Off-host backup cadence, cloud region and a remote HTTPS configuration remain release work.
