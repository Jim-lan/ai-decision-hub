"""PostgreSQL adapter for owner-scoped runs and durable lifecycle state."""

from hashlib import sha256
from typing import Any, Mapping, cast
from uuid import UUID, uuid4

from app.ports import (
    BudgetPort,
    DispatchWork,
    GenerationRequest,
    ManualOriginalCommand,
    ManualOriginalResult,
    RepositoryConflict,
    RepositoryNotFound,
    WorkClaim,
)


TERMINAL_RUN_STATES = {"completed", "completed_partial", "failed", "cancelled"}
OPEN_TARGET_STATES = {"pending", "in_flight", "awaiting_manual"}


class PostgresRunRepository:
    def __init__(self, connection: Any, budget: BudgetPort) -> None:
        self.connection = connection
        self.budget = budget

    def get_run(self, run_id: UUID, owner_id: UUID) -> dict[str, Any]:
        row = self.connection.execute(
            """SELECT run_id, project_id, conversation_id, message_id, created_at,
                      deadline, state, revision, comparison_id, error_code
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

    def list_events(
        self, run_id: UUID, owner_id: UUID, after: int, limit: int
    ) -> list[Mapping[str, object]]:
        if not self.connection.execute(
            "SELECT 1 FROM runs WHERE run_id=%s AND owner_id=%s",
            (run_id, owner_id),
        ).fetchone():
            raise RepositoryNotFound
        rows = self.connection.execute(
            """SELECT * FROM run_events
               WHERE run_id=%s AND sequence>%s ORDER BY sequence LIMIT %s""",
            (run_id, after, limit),
        ).fetchall()
        return [self._event_record(row) for row in rows]

    @staticmethod
    def _event_record(row: Mapping[str, Any]) -> Mapping[str, object]:
        common: dict[str, object] = {
            "schema_version": row["schema_version"],
            "created_at": row["created_at"],
            "event_id": row["event_id"],
            "run_id": row["run_id"],
            "sequence": row["sequence"],
            "trace_id": row["trace_id"],
            "kind": row["kind"],
        }
        if row["kind"] == "run_state":
            return common | {
                "previous": row["previous_state"],
                "state": row["state"],
            }
        if row["kind"] == "target_state":
            return common | {
                "target_id": row["target_id"],
                "previous": row["previous_state"],
                "state": row["state"],
                "reason": row["reason"],
            }
        if row["kind"] == "original_saved":
            return common | {
                "target_id": row["target_id"],
                "response_id": row["response_id"],
            }
        return common | {
            "comparison_id": row["comparison_id"],
            "version": row["version"],
        }

    def _append_event(
        self,
        run_id: UUID,
        trace_id: UUID,
        kind: str,
        *,
        target_id: UUID | None = None,
        previous: str | None = None,
        state: str | None = None,
        reason: str | None = None,
        response_id: UUID | None = None,
        comparison_id: UUID | None = None,
        version: int | None = None,
    ) -> None:
        sequence = self.connection.execute(
            "SELECT COALESCE(max(sequence),0)+1 AS sequence FROM run_events WHERE run_id=%s",
            (run_id,),
        ).fetchone()["sequence"]
        self.connection.execute(
            """INSERT INTO run_events (
                   run_id,sequence,trace_id,kind,target_id,previous_state,state,
                   reason,response_id,comparison_id,version
               ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (
                run_id,
                sequence,
                trace_id,
                kind,
                target_id,
                previous,
                state,
                reason,
                response_id,
                comparison_id,
                version,
            ),
        )

    def _transition_run(
        self,
        run: dict[str, Any],
        state: str,
        trace_id: UUID,
        *,
        error_code: str | None = None,
    ) -> dict[str, Any]:
        previous = run["state"]
        if previous == state:
            return run
        terminal_at = "clock_timestamp()" if state in TERMINAL_RUN_STATES else "NULL"
        updated = self.connection.execute(
            f"""UPDATE runs SET state=%s,revision=revision+1,error_code=%s,
                       terminal_at={terminal_at}
                   WHERE run_id=%s AND revision=%s RETURNING *""",
            (state, error_code, run["run_id"], run["revision"]),
        ).fetchone()
        if not updated:
            raise RepositoryConflict
        self._append_event(
            run["run_id"], trace_id, "run_state", previous=previous, state=state
        )
        return cast(dict[str, Any], updated)

    def _transition_target(
        self,
        target: Mapping[str, Any],
        state: str,
        trace_id: UUID,
        *,
        error_code: str | None = None,
    ) -> Mapping[str, Any]:
        previous = target["state"]
        if previous == state:
            return target
        updated = self.connection.execute(
            """UPDATE run_targets SET state=%s,error_code=%s
               WHERE target_id=%s RETURNING *""",
            (state, error_code, target["target_id"]),
        ).fetchone()
        self._append_event(
            target["run_id"],
            trace_id,
            "target_state",
            target_id=target["target_id"],
            previous=previous,
            state=state,
            reason=error_code,
        )
        return cast(Mapping[str, Any], updated)

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

    def _finish_collection(
        self, run: dict[str, Any], trace_id: UUID
    ) -> dict[str, Any]:
        counts = self.connection.execute(
            """SELECT count(*) FILTER (WHERE state IN (
                         'pending','in_flight','awaiting_manual'
                     )) AS open_count,
                      count(*) FILTER (WHERE state='succeeded') AS success_count,
                      bool_or(state='delivery_unknown') AS has_unknown_delivery,
                      bool_or(state='timed_out') AS has_timeout,
                      (array_agg(error_code ORDER BY target_id)
                         FILTER (WHERE error_code IS NOT NULL))[1] AS first_error
               FROM run_targets WHERE run_id=%s""",
            (run["run_id"],),
        ).fetchone()
        if counts["open_count"]:
            return run
        if counts["success_count"]:
            if run["state"] == "queued":
                run = self._transition_run(run, "running", trace_id)
            if run["state"] in {"running", "awaiting_manual"}:
                run = self._transition_run(run, "synthesizing", trace_id)
        elif run["state"] in {"queued", "running", "awaiting_manual"}:
            error_code = (
                "delivery_unknown"
                if counts["has_unknown_delivery"]
                else "timeout"
                if counts["has_timeout"]
                else counts["first_error"] or "internal_error"
            )
            run = self._transition_run(run, "failed", trace_id, error_code=error_code)
        self.connection.execute(
            """UPDATE run_work SET state='finished',available_at=clock_timestamp(),
                       lease_token=NULL,lease_expires_at=NULL,worker_id=NULL,
                       updated_at=clock_timestamp()
               WHERE run_id=%s""",
            (run["run_id"],),
        )
        return run

    def import_manual_original(
        self, command: ManualOriginalCommand
    ) -> ManualOriginalResult:
        run = self.connection.execute(
            """SELECT * FROM runs
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

        if run["state"] not in {"queued", "running", "awaiting_manual"}:
            raise RepositoryConflict
        if target["state"] != "awaiting_manual":
            raise RepositoryConflict
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
        self._transition_target(target, "succeeded", command.trace_id)
        self._append_event(
            command.run_id,
            command.trace_id,
            "original_saved",
            target_id=command.target_id,
            response_id=response_id,
        )
        self._finish_collection(cast(dict[str, Any], run), command.trace_id)
        original = self._original_for_target(command.target_id)
        assert original is not None
        return ManualOriginalResult(
            original=original,
            project_id=run["project_id"],
            created=True,
        )

    def _release_unsent_reservation(self, target_id: UUID, trace_id: UUID) -> None:
        reservation = self.connection.execute(
            """SELECT reservation_id,state FROM budget_reservations
               WHERE target_id=%s FOR UPDATE""",
            (target_id,),
        ).fetchone()
        if reservation and reservation["state"] == "reserved":
            self.budget.reconcile(
                reservation["reservation_id"],
                trace_id,
                outcome="release",
                proven_unsent=True,
            )

    def settle_deadline(
        self, run_id: UUID, owner_id: UUID, trace_id: UUID
    ) -> Mapping[str, object]:
        run = self.connection.execute(
            "SELECT * FROM runs WHERE run_id=%s AND owner_id=%s FOR UPDATE",
            (run_id, owner_id),
        ).fetchone()
        if not run:
            raise RepositoryNotFound
        now = self.connection.execute(
            "SELECT clock_timestamp() AS now"
        ).fetchone()["now"]
        if now < run["deadline"] or run["state"] in TERMINAL_RUN_STATES | {"synthesizing"}:
            return cast(Mapping[str, object], run)
        targets = self.connection.execute(
            """SELECT * FROM run_targets WHERE run_id=%s
               ORDER BY target_id FOR UPDATE""",
            (run_id,),
        ).fetchall()
        for target in targets:
            if target["state"] in {"pending", "awaiting_manual"}:
                self._release_unsent_reservation(target["target_id"], trace_id)
                self._transition_target(target, "timed_out", trace_id, error_code="timeout")
            elif target["state"] == "in_flight":
                self._transition_target(
                    target,
                    "delivery_unknown",
                    trace_id,
                    error_code="delivery_unknown",
                )
        return self._finish_collection(cast(dict[str, Any], run), trace_id)

    def cancel_run(
        self, run_id: UUID, owner_id: UUID, trace_id: UUID
    ) -> Mapping[str, object]:
        run = self.connection.execute(
            "SELECT * FROM runs WHERE run_id=%s AND owner_id=%s FOR UPDATE",
            (run_id, owner_id),
        ).fetchone()
        if not run:
            raise RepositoryNotFound
        if run["state"] == "cancelled":
            return cast(Mapping[str, object], run)
        if run["state"] in TERMINAL_RUN_STATES:
            raise RepositoryConflict
        targets = self.connection.execute(
            """SELECT * FROM run_targets WHERE run_id=%s
               ORDER BY target_id FOR UPDATE""",
            (run_id,),
        ).fetchall()
        for target in targets:
            if target["state"] in OPEN_TARGET_STATES:
                if target["state"] != "in_flight":
                    self._release_unsent_reservation(target["target_id"], trace_id)
                self._transition_target(
                    target, "cancelled", trace_id, error_code="cancelled"
                )
        run = self._transition_run(
            cast(dict[str, Any], run), "cancelled", trace_id, error_code="cancelled"
        )
        self.connection.execute(
            """UPDATE run_work SET state='finished',available_at=clock_timestamp(),
                       lease_token=NULL,lease_expires_at=NULL,worker_id=NULL,
                       updated_at=clock_timestamp()
               WHERE run_id=%s""",
            (run_id,),
        )
        return cast(Mapping[str, object], run)

    def claim_work(
        self, worker_id: str, trace_id: UUID, lease_seconds: int
    ) -> WorkClaim | None:
        if not worker_id.strip() or len(worker_id) > 160:
            raise ValueError("Worker ID must be nonblank and bounded")
        if lease_seconds < 1 or lease_seconds > 300:
            raise ValueError("Lease duration must be between 1 and 300 seconds")
        candidate = self.connection.execute(
            """SELECT work.run_id
               FROM run_work work JOIN runs run USING (run_id)
               WHERE (
                   (work.state='available' AND work.available_at<=clock_timestamp()) OR
                   (work.state='waiting' AND work.available_at<=clock_timestamp()) OR
                   (work.state='leased' AND work.lease_expires_at<=clock_timestamp())
               ) AND run.state IN ('queued','running','awaiting_manual')
               ORDER BY work.available_at,work.run_id LIMIT 1"""
        ).fetchone()
        if not candidate:
            return None
        run = self.connection.execute(
            """SELECT * FROM runs WHERE run_id=%s
               AND state IN ('queued','running','awaiting_manual')
               FOR UPDATE SKIP LOCKED""",
            (candidate["run_id"],),
        ).fetchone()
        if not run:
            return None
        work = self.connection.execute(
            """SELECT * FROM run_work WHERE run_id=%s AND (
                   (state='available' AND available_at<=clock_timestamp()) OR
                   (state='waiting' AND available_at<=clock_timestamp()) OR
                   (state='leased' AND lease_expires_at<=clock_timestamp())
               ) FOR UPDATE""",
            (run["run_id"],),
        ).fetchone()
        if not work:
            return None
        now = self.connection.execute(
            "SELECT clock_timestamp() AS now"
        ).fetchone()["now"]
        if now >= run["deadline"]:
            self.settle_deadline(
                run["run_id"], run["owner_id"], trace_id
            )
            return None
        leased = self.connection.execute(
            """UPDATE run_work SET state='leased',lease_token=gen_random_uuid(),
                       lease_expires_at=%s+(%s*interval '1 second'),worker_id=%s,
                       fence=fence+1,updated_at=%s
               WHERE run_id=%s RETURNING *""",
            (now, lease_seconds, worker_id, now, run["run_id"]),
        ).fetchone()
        if run["state"] == "queued":
            run = self._transition_run(cast(dict[str, Any], run), "running", trace_id)
        return WorkClaim(
            run_id=run["run_id"],
            owner_id=run["owner_id"],
            project_id=run["project_id"],
            lease_token=leased["lease_token"],
            fence=leased["fence"],
            deadline=run["deadline"],
        )

    def park_manual_work(self, claim: WorkClaim, trace_id: UUID) -> bool:
        run = self.connection.execute(
            "SELECT * FROM runs WHERE run_id=%s FOR UPDATE", (claim.run_id,)
        ).fetchone()
        work = self.connection.execute(
            """SELECT * FROM run_work WHERE run_id=%s AND state='leased'
               AND lease_token=%s AND fence=%s FOR UPDATE""",
            (claim.run_id, claim.lease_token, claim.fence),
        ).fetchone()
        if not work:
            raise RepositoryConflict
        targets = self.connection.execute(
            "SELECT * FROM run_targets WHERE run_id=%s ORDER BY target_id FOR UPDATE",
            (claim.run_id,),
        ).fetchall()
        if any(
            target["state"] in {"pending", "in_flight"}
            and target["acquisition_mode"] == "official_api"
            for target in targets
        ):
            return False
        if any(target["state"] == "awaiting_manual" for target in targets):
            if run["state"] == "running":
                self._transition_run(
                    cast(dict[str, Any], run), "awaiting_manual", trace_id
                )
            self.connection.execute(
                """UPDATE run_work SET state='waiting',available_at=%s,
                           lease_token=NULL,lease_expires_at=NULL,worker_id=NULL,
                           updated_at=clock_timestamp() WHERE run_id=%s""",
                (run["deadline"], claim.run_id),
            )
            return True
        self._finish_collection(cast(dict[str, Any], run), trace_id)
        return True

    def prepare_next_dispatch(
        self, claim: WorkClaim, trace_id: UUID
    ) -> DispatchWork | None:
        run = self.connection.execute(
            "SELECT * FROM runs WHERE run_id=%s FOR UPDATE", (claim.run_id,)
        ).fetchone()
        work = self.connection.execute(
            """SELECT * FROM run_work WHERE run_id=%s AND state='leased'
               AND lease_token=%s AND fence=%s
               AND lease_expires_at>clock_timestamp() FOR UPDATE""",
            (claim.run_id, claim.lease_token, claim.fence),
        ).fetchone()
        if not run or not work or run["state"] != "running":
            raise RepositoryConflict
        target = self.connection.execute(
            """SELECT target.*,context.candidate_id,context.model_visible_input,
                      context.request_hash,reservation.reservation_id,
                      reservation.output_token_bound
                 FROM run_targets target
                 JOIN prepared_contexts context USING (target_id)
                 JOIN budget_reservations reservation USING (target_id)
                WHERE target.run_id=%s AND target.state='pending'
                  AND target.acquisition_mode='official_api'
                  AND reservation.state='reserved'
                ORDER BY target.target_id LIMIT 1 FOR UPDATE OF target""",
            (claim.run_id,),
        ).fetchone()
        if not target:
            return None
        now = self.connection.execute(
            "SELECT clock_timestamp() AS now"
        ).fetchone()["now"]
        attempt_id = uuid4()
        decision = self.budget.revalidate_dispatch(
            target["reservation_id"], target["candidate_id"], attempt_id,
            trace_id, now,
        )
        if decision.grant is None:
            reason = decision.reason
            code = {
                "registry_disabled": "disabled",
                "provider_quota": "quota_denied",
                "deadline": "timeout",
                "policy_expired": "policy_denied",
                "period_cap": "budget_denied",
            }.get(reason or "", "internal_error")
            self.budget.reconcile(
                target["reservation_id"], trace_id,
                outcome="release", proven_unsent=True,
            )
            state = "timed_out" if reason == "deadline" else "blocked"
            self._transition_target(target, state, trace_id, error_code=code)
            return None
        grant = decision.grant
        next_attempt = target["attempt_no"] + 1
        self.connection.execute(
            """INSERT INTO provider_attempts (
                   attempt_id,run_id,target_id,attempt_no,work_fence,state,
                   request_hash,grant_id
               ) VALUES (%s,%s,%s,%s,%s,'prepared',%s,%s)""",
            (
                attempt_id, claim.run_id, target["target_id"], next_attempt,
                claim.fence, target["request_hash"], grant.grant_id,
            ),
        )
        updated = self.connection.execute(
            """UPDATE run_targets SET state='in_flight',attempt_no=%s,
                       context_snapshot_id=%s,error_code=NULL
                   WHERE target_id=%s RETURNING *""",
            (next_attempt, target["candidate_id"], target["target_id"]),
        ).fetchone()
        self._append_event(
            claim.run_id, trace_id, "target_state",
            target_id=target["target_id"], previous=target["state"],
            state=updated["state"],
        )
        remaining_ms = max(1, round((claim.deadline - now).total_seconds() * 1000))
        return DispatchWork(
            run_id=claim.run_id,
            target_id=target["target_id"],
            reservation_id=target["reservation_id"],
            attempt_id=attempt_id,
            request=GenerationRequest(
                attempt_id=attempt_id,
                grant_id=grant.grant_id,
                provider_id=target["provider"],
                requested_model_id=target["model_id"],
                model_visible_input=target["model_visible_input"],
                timeout_ms=min(30_000, remaining_ms),
                max_output_tokens=target["output_token_bound"],
                allowed_model_ids=(target["model_id"],),
            ),
        )

    def recover_claimed_dispatches(
        self, claim: WorkClaim, trace_id: UUID
    ) -> int:
        """Freeze ambiguous claimed calls after a replacement worker takes the lease."""
        run = self.connection.execute(
            "SELECT * FROM runs WHERE run_id=%s FOR UPDATE", (claim.run_id,)
        ).fetchone()
        work = self.connection.execute(
            """SELECT * FROM run_work WHERE run_id=%s AND state='leased'
               AND lease_token=%s AND fence=%s
               AND lease_expires_at>clock_timestamp() FOR UPDATE""",
            (claim.run_id, claim.lease_token, claim.fence),
        ).fetchone()
        if not run or not work or run["state"] != "running":
            raise RepositoryConflict
        ambiguous = self.connection.execute(
            """SELECT attempt.*,claim.claimed_at
                 FROM provider_attempts attempt
                 JOIN dispatch_claims claim
                   ON claim.attempt_id=attempt.attempt_id
                  AND claim.grant_id=attempt.grant_id
                 JOIN run_targets target
                   ON target.target_id=attempt.target_id
                  AND target.run_id=attempt.run_id
                WHERE attempt.run_id=%s
                  AND attempt.state IN ('prepared','dispatch_claimed')
                  AND attempt.work_fence<%s
                  AND target.state='in_flight'
                  AND target.attempt_no=attempt.attempt_no
                ORDER BY attempt.target_id
                FOR UPDATE OF attempt,target""",
            (claim.run_id, claim.fence),
        ).fetchall()
        for attempt in ambiguous:
            self.connection.execute(
                """UPDATE provider_attempts
                      SET state='delivery_unknown',error_code='delivery_unknown',
                          dispatch_claimed_at=COALESCE(dispatch_claimed_at,%s),
                          finished_at=clock_timestamp()
                    WHERE attempt_id=%s""",
                (attempt["claimed_at"], attempt["attempt_id"]),
            )
            target = self.connection.execute(
                "SELECT * FROM run_targets WHERE target_id=%s",
                (attempt["target_id"],),
            ).fetchone()
            self._transition_target(
                target,
                "delivery_unknown",
                trace_id,
                error_code="delivery_unknown",
            )
        if not ambiguous:
            return 0

        run = self._finish_collection(cast(dict[str, Any], run), trace_id)
        if run["state"] in {"running", "awaiting_manual"}:
            open_counts = self.connection.execute(
                """SELECT count(*) FILTER (WHERE acquisition_mode='official_api'
                              AND state IN ('pending','in_flight')) AS official_open,
                          count(*) FILTER (WHERE state='awaiting_manual') AS manual_open
                     FROM run_targets WHERE run_id=%s""",
                (claim.run_id,),
            ).fetchone()
            if open_counts["official_open"]:
                self.connection.execute(
                    """UPDATE run_work SET state='available',
                               available_at=clock_timestamp(),lease_token=NULL,
                               lease_expires_at=NULL,worker_id=NULL,
                               updated_at=clock_timestamp() WHERE run_id=%s""",
                    (claim.run_id,),
                )
            elif open_counts["manual_open"]:
                if run["state"] == "running":
                    self._transition_run(run, "awaiting_manual", trace_id)
                self.connection.execute(
                    """UPDATE run_work SET state='waiting',available_at=%s,
                               lease_token=NULL,lease_expires_at=NULL,worker_id=NULL,
                               updated_at=clock_timestamp() WHERE run_id=%s""",
                    (run["deadline"], claim.run_id),
                )
        return len(ambiguous)
