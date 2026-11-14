"""PostgreSQL adapter for owner-scoped runs and immutable originals."""

from hashlib import sha256
from typing import Any, Mapping, cast
from uuid import UUID

from app.ports import (
    ManualOriginalCommand,
    ManualOriginalResult,
    RepositoryConflict,
    RepositoryNotFound,
)


class PostgresRunRepository:
    def __init__(self, connection: Any) -> None:
        self.connection = connection

    def get_run(self, run_id: UUID, owner_id: UUID) -> dict[str, Any]:
        row = self.connection.execute(
            """SELECT run_id, project_id, conversation_id, message_id, created_at, deadline
               FROM runs WHERE run_id=%s AND owner_id=%s""",
            (run_id, owner_id),
        ).fetchone()
        if not row:
            raise RepositoryNotFound
        return cast(dict[str, Any], row)

    def list_originals(
        self, run_id: UUID, owner_id: UUID
    ) -> list[Mapping[str, object]]:
        rows = self.connection.execute(
            """SELECT m.*, t.run_id, t.provider,
                      t.model_id AS requested_model_id, t.gateway, t.routing_mode
               FROM model_responses m
               JOIN run_targets t USING (target_id)
               JOIN runs r USING (run_id)
               WHERE r.run_id=%s AND r.owner_id=%s
               ORDER BY m.created_at, m.response_id""",
            (run_id, owner_id),
        ).fetchall()
        return cast(list[Mapping[str, object]], rows)

    def _original_for_target(self, target_id: UUID) -> dict[str, Any] | None:
        row = self.connection.execute(
            """SELECT m.*, t.run_id, t.provider,
                      t.model_id AS requested_model_id, t.gateway, t.routing_mode
               FROM model_responses m
               JOIN run_targets t USING (target_id)
               WHERE m.target_id=%s""",
            (target_id,),
        ).fetchone()
        return cast(dict[str, Any] | None, row)

    @staticmethod
    def _is_exact_replay(
        existing: Mapping[str, Any],
        command: ManualOriginalCommand,
        declared_model_id: str,
    ) -> bool:
        # Before C-008, an omitted declaration was represented only by the
        # legacy display identity. Treat that value as the compatibility default.
        existing_declared_model = (
            existing["declared_model_id"] or existing["actual_model_id"]
        )
        return (
            existing["content"],
            existing["model_family"],
            existing["declared_app"],
            existing_declared_model,
        ) == (
            command.content,
            command.model_family,
            command.declared_app,
            declared_model_id,
        )

    def import_manual_original(
        self, command: ManualOriginalCommand
    ) -> ManualOriginalResult:
        # The frozen lock order is run then target. It serializes concurrent
        # pastes and future lifecycle transitions without a network transaction.
        run = self.connection.execute(
            """SELECT run_id, project_id, deadline FROM runs
               WHERE run_id=%s AND owner_id=%s FOR UPDATE""",
            (command.run_id, command.owner_id),
        ).fetchone()
        if not run:
            raise RepositoryNotFound
        target = self.connection.execute(
            """SELECT * FROM run_targets
               WHERE run_id=%s AND target_id=%s FOR UPDATE""",
            (command.run_id, command.target_id),
        ).fetchone()
        if not target:
            raise RepositoryNotFound

        declared_model_id = command.declared_model_id or target["model_id"]
        if (
            target["provider"] != "manual"
            or target["gateway"] != "manual"
            or target["acquisition_mode"] != "manual"
            or "manual_import" not in target["capabilities"]
        ):
            raise RepositoryConflict

        existing = self._original_for_target(command.target_id)
        if existing:
            if not self._is_exact_replay(existing, command, declared_model_id):
                raise RepositoryConflict
            return ManualOriginalResult(
                original=existing,
                project_id=run["project_id"],
                created=False,
            )

        checked_at = self.connection.execute(
            "SELECT clock_timestamp() AS checked_at"
        ).fetchone()["checked_at"]
        if checked_at >= run["deadline"]:
            raise RepositoryConflict

        response_id = self.connection.execute(
            """INSERT INTO model_responses (
                   target_id, actual_model_id, model_family, identity_confidence,
                   acquisition_mode, content, source_hash, declared_app,
                   declared_model_id
               ) VALUES (%s,%s,%s,'user_declared','manual',%s,%s,%s,%s)
               RETURNING response_id""",
            (
                command.target_id,
                declared_model_id,
                command.model_family,
                command.content,
                sha256(command.content.encode()).hexdigest(),
                command.declared_app,
                declared_model_id,
            ),
        ).fetchone()["response_id"]
        original = self.connection.execute(
            """SELECT m.*, t.run_id, t.provider,
                      t.model_id AS requested_model_id, t.gateway, t.routing_mode
               FROM model_responses m
               JOIN run_targets t USING (target_id)
               WHERE m.response_id=%s""",
            (response_id,),
        ).fetchone()
        return ManualOriginalResult(
            original=original,
            project_id=run["project_id"],
            created=True,
        )
