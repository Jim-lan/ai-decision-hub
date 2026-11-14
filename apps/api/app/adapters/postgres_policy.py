"""PostgreSQL context-policy and conservative budget adapters."""

from datetime import datetime, timezone
import hashlib
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.ports import (
    AuthorizationPort,
    BudgetDecision,
    BudgetPort,
    BudgetRequest,
    BudgetReservation,
    ContextDecision,
    ContextPort,
    ContextProjection,
    ContextRequest,
    DispatchDecision,
    DispatchGrant,
    GenerationRequest,
)


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _audit(connection, action, trace_id, owner_id, project_id, resource_id, outcome):
    connection.execute(
        """INSERT INTO audit_events
            (action,trace_id,owner_id,project_id,resource_id,outcome)
            VALUES (%s,%s,%s,%s,%s,%s)""",
        (action, trace_id, owner_id, project_id, resource_id, outcome),
    )


def _token_bound(value: str) -> int:
    """UTF-8 bytes are a conservative provider-independent token upper bound."""
    return len(value.encode())


def _worst_cost(policy, input_bound, output_bound):
    amount = policy["fixed_cost_microusd"]
    amount += (input_bound * policy["input_microusd_per_million"] + 999_999) // 1_000_000
    amount += (output_bound * policy["output_microusd_per_million"] + 999_999) // 1_000_000
    return amount


def _render_context(question_row, source_ids, by_id, limit):
    question = question_row["content"]
    redactions = 0
    if question_row["decision"] == "redact":
        question = question_row["redacted_content"]
        redactions += 1
    model_input = f"Question:\n{question}"
    if _token_bound(model_input) > limit:
        return None
    included = []
    omissions = 0
    for position, source_id in enumerate(source_ids, start=1):
        row = by_id[source_id]
        content = row["content"]
        if row["decision"] == "redact":
            content = row["redacted_content"]
            redactions += 1
        addition = f"\n\nSelected context {position}:\n{content}"
        if _token_bound(model_input + addition) > limit:
            omissions += 1
            continue
        model_input += addition
        included.append(source_id)
    return model_input, included, redactions, omissions, _token_bound(model_input)


def _current_projection(connection, candidate, as_of):
    scope = connection.execute(
        """SELECT pp.policy_version,pp.status,pp.consented_at,pp.verified_at,
                  pp.expires_at,pp.max_input_tokens,pm.status AS registry_status,
                  pm.privacy_profile,q.content,qsr.decision,qsr.redacted_content,
                  qsr.policy_version AS question_policy_version
             FROM runs r
             JOIN messages q ON q.message_id=r.message_id
             JOIN run_targets t ON t.target_id=%s AND t.run_id=r.run_id
             JOIN provider_models pm
               ON pm.provider_id=t.provider AND pm.alias=t.alias
             JOIN project_provider_policies pp
               ON pp.project_id=r.project_id AND pp.provider_id=t.provider
              AND pp.alias=t.alias
             JOIN context_source_rules qsr
               ON qsr.project_id=r.project_id AND qsr.message_id=q.message_id
              AND qsr.provider_id=t.provider AND qsr.alias=t.alias
            WHERE r.run_id=%s AND r.project_id=%s
            FOR SHARE OF pp,pm,qsr""",
        (candidate["target_id"], candidate["run_id"], candidate["project_id"]),
    ).fetchone()
    if not scope or (
        scope["policy_version"] != candidate["policy_version"]
        or scope["status"] != "allowed"
        or scope["consented_at"] is None
        or as_of < scope["consented_at"]
        or as_of < scope["verified_at"]
        or as_of >= scope["expires_at"]
        or scope["registry_status"] != "enabled"
        or scope["privacy_profile"] != "allowlisted"
        or scope["question_policy_version"] != candidate["policy_version"]
        or scope["decision"] not in {"allow", "redact"}
        or scope["max_input_tokens"] < candidate["input_token_limit"]
    ):
        return None
    records = connection.execute(
        """SELECT m.message_id,m.content,csr.decision,csr.redacted_content,
                  csr.policy_version
             FROM run_context_sources selected
             JOIN messages m ON m.message_id=selected.message_id
             JOIN context_source_rules csr
               ON csr.message_id=m.message_id AND csr.project_id=%s
              AND csr.provider_id=%s AND csr.alias=%s
            WHERE selected.run_id=%s
              AND m.message_id=ANY(%s::uuid[])
            ORDER BY selected.position
            FOR SHARE OF csr""",
        (
            candidate["project_id"], candidate["provider_id"], candidate["alias"],
            candidate["run_id"], candidate["selected_source_message_ids"],
        ),
    ).fetchall()
    selected = tuple(candidate["selected_source_message_ids"])
    if tuple(row["message_id"] for row in records) != selected:
        return None
    if any(
        row["decision"] not in {"allow", "redact"}
        or row["policy_version"] != candidate["policy_version"]
        for row in records
    ):
        return None
    rendered = _render_context(
        scope, selected, {row["message_id"]: row for row in records},
        candidate["input_token_limit"],
    )
    if not rendered:
        return None
    model_input, included, redactions, omissions, input_bound = rendered
    if (
        model_input != candidate["model_visible_input"]
        or included != candidate["source_message_ids"]
        or redactions != candidate["redaction_count"]
        or omissions != candidate["omission_count"]
        or input_bound != candidate["input_token_bound"]
        or _digest(model_input) != candidate["request_hash"]
    ):
        return None
    return model_input


def _reservation(row) -> BudgetReservation:
    return BudgetReservation(
        reservation_id=row["reservation_id"],
        amount_microusd=row["amount_microusd"],
        input_token_bound=row["input_token_bound"],
        output_token_bound=row["output_token_bound"],
        pricing_version=row["pricing_version"],
        owner_day=row["owner_day"].isoformat(),
        owner_month=row["owner_month"].isoformat(),
        provider_day=row["provider_day"].isoformat(),
        state=row["state"],
    )


def _grant(row) -> DispatchGrant:
    return DispatchGrant(
        grant_id=row["grant_id"],
        reservation_id=row["reservation_id"],
        candidate_id=row["candidate_id"],
        attempt_id=row["attempt_id"],
        owner_id=row["owner_id"],
        project_id=row["project_id"],
        run_id=row["run_id"],
        target_id=row["target_id"],
        provider_id=row["provider_id"],
        alias=row["alias"],
        requested_model_id=row["requested_model_id"],
        input_digest=row["input_digest"],
        input_token_bound=row["input_token_bound"],
        output_token_bound=row["output_token_bound"],
        deadline=row["deadline"],
        validated_at=row["validated_at"],
    )


class PostgresContextPort(ContextPort):
    def __init__(self, connection):
        self.connection = connection

    def _deny(self, request: ContextRequest, reason: str) -> ContextDecision:
        _audit(
            self.connection, "context_denied", request.trace_id, request.owner_id,
            request.project_id, request.target_id, "denied",
        )
        return ContextDecision(projection=None, reason=reason)

    def prepare(self, request: ContextRequest) -> ContextDecision:
        if (
            request.as_of.tzinfo is None
            or request.max_input_tokens <= 0
            or len(request.source_message_ids) > 32
            or len(set(request.source_message_ids)) != len(request.source_message_ids)
        ):
            return self._deny(request, "source_out_of_scope")

        scope = self.connection.execute(
            """SELECT pp.policy_version,pp.status,pp.consented_at,pp.verified_at,
                      pp.expires_at,pp.max_input_tokens,pm.status AS registry_status,
                      pm.privacy_profile,q.content,qsr.decision,qsr.redacted_content,
                      qsr.policy_version AS question_policy_version
                 FROM runs r
                 JOIN messages q ON q.message_id=r.message_id
                 JOIN run_targets t ON t.run_id=r.run_id
                 JOIN provider_models pm
                   ON pm.provider_id=t.provider AND pm.alias=t.alias
            LEFT JOIN project_provider_policies pp
                   ON pp.project_id=r.project_id AND pp.provider_id=t.provider
                  AND pp.alias=t.alias
            LEFT JOIN context_source_rules qsr
                   ON qsr.project_id=r.project_id AND qsr.message_id=q.message_id
                  AND qsr.provider_id=t.provider AND qsr.alias=t.alias
                WHERE r.run_id=%s AND t.target_id=%s AND r.owner_id=%s
                  AND r.project_id=%s AND t.provider=%s AND t.alias=%s""",
            (
                request.run_id, request.target_id, request.owner_id,
                request.project_id, request.provider_id, request.alias,
            ),
        ).fetchone()
        if not scope:
            return self._deny(request, "source_out_of_scope")
        if scope["policy_version"] is None or scope["consented_at"] is None:
            return self._deny(request, "consent_missing")
        if (
            request.question != scope["content"]
            or request.as_of < scope["verified_at"]
            or request.as_of < scope["consented_at"]
            or request.as_of >= scope["expires_at"]
        ):
            return self._deny(request, "policy_expired")
        if (
            scope["status"] != "allowed"
            or scope["registry_status"] != "enabled"
            or scope["privacy_profile"] != "allowlisted"
            or scope["question_policy_version"] != scope["policy_version"]
            or scope["decision"] not in {"allow", "redact"}
        ):
            return self._deny(request, "recipient_blocked")

        selected = self.connection.execute(
            """SELECT message_id FROM run_context_sources WHERE run_id=%s
                ORDER BY position""", (request.run_id,),
        ).fetchall()
        if tuple(row["message_id"] for row in selected) != request.source_message_ids:
            return self._deny(request, "source_out_of_scope")

        records = self.connection.execute(
            """SELECT m.message_id,m.content,csr.decision,csr.redacted_content,
                      csr.policy_version
                 FROM messages m
                 JOIN conversations c USING (conversation_id)
                 JOIN projects p USING (project_id)
                 JOIN run_context_sources selected
                   ON selected.message_id=m.message_id AND selected.run_id=%s
            LEFT JOIN context_source_rules csr
                   ON csr.message_id=m.message_id AND csr.project_id=c.project_id
                  AND csr.provider_id=%s AND csr.alias=%s
                WHERE p.owner_id=%s AND c.project_id=%s
                  AND m.message_id=ANY(%s::uuid[])""",
            (
                request.run_id, request.provider_id, request.alias, request.owner_id,
                request.project_id, list(request.source_message_ids),
            ),
        ).fetchall()
        by_id = {row["message_id"]: row for row in records}
        if len(by_id) != len(request.source_message_ids):
            return self._deny(request, "source_out_of_scope")
        if any(
            by_id[source]["decision"] not in {"allow", "redact"}
            or by_id[source]["policy_version"] != scope["policy_version"]
            for source in request.source_message_ids
        ):
            return self._deny(request, "source_denied")

        limit = min(request.max_input_tokens, scope["max_input_tokens"])
        rendered = _render_context(scope, request.source_message_ids, by_id, limit)
        if not rendered:
            return self._deny(request, "question_too_large")
        model_input, included, redactions, omissions, input_bound = rendered
        request_hash = _digest(model_input)
        inserted = self.connection.execute(
            """INSERT INTO prepared_contexts (
                    run_id,target_id,project_id,policy_version,
                    selected_source_message_ids,source_message_ids,model_visible_input,
                    request_hash,redaction_count,omission_count,input_token_limit,
                    input_token_bound
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (target_id) DO NOTHING RETURNING candidate_id""",
            (
                request.run_id, request.target_id, request.project_id,
                scope["policy_version"], list(request.source_message_ids), included,
                model_input, request_hash, redactions, omissions, limit, input_bound,
            ),
        ).fetchone()
        if inserted:
            candidate_id = inserted["candidate_id"]
        else:
            existing = self.connection.execute(
                """SELECT * FROM prepared_contexts WHERE target_id=%s""",
                (request.target_id,),
            ).fetchone()
            expected = (
                request.run_id, request.project_id, scope["policy_version"],
                list(request.source_message_ids), included, model_input, request_hash,
                redactions, omissions, limit, input_bound,
            )
            actual = (
                existing["run_id"], existing["project_id"], existing["policy_version"],
                existing["selected_source_message_ids"], existing["source_message_ids"],
                existing["model_visible_input"], existing["request_hash"],
                existing["redaction_count"], existing["omission_count"],
                existing["input_token_limit"], existing["input_token_bound"],
            )
            if actual != expected:
                return self._deny(request, "candidate_conflict")
            candidate_id = existing["candidate_id"]

        _audit(
            self.connection, "context_allowed", request.trace_id, request.owner_id,
            request.project_id, request.target_id, "accepted",
        )
        return ContextDecision(
            projection=ContextProjection(
                candidate_id=candidate_id,
                policy_version=scope["policy_version"],
                source_message_ids=tuple(included),
                model_visible_input=model_input,
                request_hash=request_hash,
                redaction_count=redactions,
                omission_count=omissions,
                input_token_bound=input_bound,
            ),
            reason=None,
        )


class PostgresBudgetPort(BudgetPort):
    def __init__(self, connection, clock=None):
        self.connection = connection
        self.clock = clock

    def _current_time(self, supplied):
        if self.clock:
            return self.clock(supplied)
        return self.connection.execute(
            "SELECT clock_timestamp() AS current_time"
        ).fetchone()["current_time"]

    def _deny(self, request: BudgetRequest, reason: str) -> BudgetDecision:
        _audit(
            self.connection, "budget_denied", request.trace_id, request.owner_id,
            request.project_id, request.run_id, "denied",
        )
        return BudgetDecision(reservation=None, reason=reason)

    @staticmethod
    def _periods(as_of: datetime, quota_timezone: str):
        if as_of.tzinfo is None:
            raise ValueError("Budget instants require a timezone")
        utc = as_of.astimezone(timezone.utc)
        provider = as_of.astimezone(ZoneInfo(quota_timezone))
        return utc.date(), utc.date().replace(day=1), provider.date()

    def _scope(self, request: BudgetRequest):
        return self.connection.execute(
            """SELECT r.deadline,r.max_cost_microusd,t.model_id,
                      pm.status AS registry_status,
                      pm.acquisition_mode,pm.pricing_status,pm.pricing_version
                 FROM runs r JOIN run_targets t ON t.run_id=r.run_id
                 JOIN provider_models pm
                   ON pm.provider_id=t.provider AND pm.alias=t.alias
                WHERE r.run_id=%s AND t.target_id=%s AND r.owner_id=%s
                  AND r.project_id=%s AND t.provider=%s AND t.alias=%s""",
            (
                request.run_id, request.target_id, request.owner_id,
                request.project_id, request.provider_id, request.alias,
            ),
        ).fetchone()

    def _policies(self, owner_id, provider_id, alias):
        owner = self.connection.execute(
            "SELECT * FROM owner_budget_policies WHERE owner_id=%s FOR SHARE",
            (owner_id,),
        ).fetchone()
        provider = self.connection.execute(
            """SELECT * FROM provider_budget_policies
                WHERE provider_id=%s AND alias=%s FOR SHARE""",
            (provider_id, alias),
        ).fetchone()
        return owner, provider

    def _exposure(self, owner_id, run_id, owner_day, owner_month, exclude=None):
        return self.connection.execute(
            """SELECT
                COALESCE(sum(CASE WHEN state='settled' THEN actual_cost_microusd
                                  ELSE greatest(amount_microusd,coalesce(actual_cost_microusd,0)) END)
                         FILTER (WHERE run_id=%s AND state<>'released'),0) AS run_total,
                COALESCE(sum(CASE WHEN state='settled' THEN actual_cost_microusd
                                  ELSE greatest(amount_microusd,coalesce(actual_cost_microusd,0)) END)
                         FILTER (WHERE state='held' OR owner_day=%s),0) AS day_total,
                COALESCE(sum(CASE WHEN state='settled' THEN actual_cost_microusd
                                  ELSE greatest(amount_microusd,coalesce(actual_cost_microusd,0)) END)
                         FILTER (WHERE state='held' OR owner_month=%s),0) AS month_total
                FROM budget_reservations WHERE owner_id=%s AND state<>'released'
                  AND (%s::uuid IS NULL OR reservation_id<>%s)""",
            (run_id, owner_day, owner_month, owner_id, exclude, exclude),
        ).fetchone()

    def _quota(self, provider_id, quota_account_id, provider_day, exclude=None):
        return self.connection.execute(
            """SELECT
                count(*) FILTER (WHERE state='held' OR provider_day=%s) AS calls,
                COALESCE(sum(CASE WHEN state='settled'
                                  THEN coalesce(input_tokens,input_token_bound)
                                  ELSE input_token_bound END)
                         FILTER (WHERE state='held' OR provider_day=%s),0) AS input_tokens,
                COALESCE(sum(CASE WHEN state='settled'
                                  THEN coalesce(output_tokens,output_token_bound)
                                  ELSE output_token_bound END)
                         FILTER (WHERE state='held' OR provider_day=%s),0) AS output_tokens
                FROM budget_reservations
                WHERE provider_id=%s AND quota_account_id=%s AND state<>'released'
                  AND (%s::uuid IS NULL OR reservation_id<>%s)""",
            (
                provider_day, provider_day, provider_day, provider_id,
                quota_account_id, exclude, exclude,
            ),
        ).fetchone()

    def reserve(self, request: BudgetRequest) -> BudgetDecision:
        if (
            request.as_of.tzinfo is None
            or request.input_token_bound < 0
            or request.output_token_bound <= 0
            or not request.reservation_key.strip()
        ):
            return self._deny(request, "invalid_bound")
        self.connection.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
            (f"budget-owner:{request.owner_id}",),
        )
        existing = self.connection.execute(
            """SELECT * FROM budget_reservations
                WHERE owner_id=%s AND reservation_key=%s""",
            (request.owner_id, request.reservation_key),
        ).fetchone()
        if existing:
            if (
                existing["target_id"] != request.target_id
                or existing["input_token_bound"] != request.input_token_bound
                or existing["output_token_bound"] != request.output_token_bound
                or existing["requested_run_cap_microusd"]
                != request.requested_run_cap_microusd
            ):
                return self._deny(request, "idempotency_conflict")
            return BudgetDecision(reservation=_reservation(existing), reason=None)

        scope = self._scope(request)
        if (
            not scope
            or scope["registry_status"] != "enabled"
            or scope["acquisition_mode"] != "official_api"
        ):
            return self._deny(request, "registry_disabled")
        if request.as_of >= scope["deadline"]:
            return self._deny(request, "policy_expired")
        if request.requested_run_cap_microusd != scope["max_cost_microusd"]:
            return self._deny(request, "idempotency_conflict")
        owner_policy, provider_policy = self._policies(
            request.owner_id, request.provider_id, request.alias,
        )
        if not owner_policy or not provider_policy or provider_policy["status"] != "active":
            return self._deny(request, "policy_missing")
        if (
            request.as_of < owner_policy["effective_at"]
            or (owner_policy["expires_at"] and request.as_of >= owner_policy["expires_at"])
            or request.as_of < provider_policy["verified_at"]
            or request.as_of >= provider_policy["expires_at"]
        ):
            return self._deny(request, "policy_expired")
        if (
            scope["pricing_status"] not in {"verified_free", "verified_priced"}
            or scope["pricing_version"] != provider_policy["pricing_version"]
        ):
            return self._deny(request, "price_unknown")
        if (
            request.input_token_bound > provider_policy["max_input_tokens"]
            or request.output_token_bound > provider_policy["max_output_tokens"]
        ):
            return self._deny(request, "invalid_bound")
        try:
            owner_day, owner_month, provider_day = self._periods(
                request.as_of, provider_policy["quota_timezone"],
            )
        except ZoneInfoNotFoundError:
            return self._deny(request, "policy_missing")
        self.connection.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
            (f"budget-provider:{request.provider_id}:{provider_policy['quota_account_id']}",),
        )
        as_of = self._current_time(request.as_of)
        if (
            as_of >= scope["deadline"]
            or as_of < owner_policy["effective_at"]
            or (owner_policy["expires_at"] and as_of >= owner_policy["expires_at"])
            or as_of < provider_policy["verified_at"]
            or as_of >= provider_policy["expires_at"]
        ):
            return self._deny(request, "policy_expired")
        try:
            owner_day, owner_month, provider_day = self._periods(
                as_of, provider_policy["quota_timezone"],
            )
        except ZoneInfoNotFoundError:
            return self._deny(request, "policy_missing")

        amount = _worst_cost(
            provider_policy, request.input_token_bound, request.output_token_bound,
        )
        exposure = self._exposure(
            request.owner_id, request.run_id, owner_day, owner_month,
        )
        if (
            request.requested_run_cap_microusd is not None
            and exposure["run_total"] + amount > request.requested_run_cap_microusd
        ):
            return self._deny(request, "request_cap")
        for current, cap, reason in (
            (exposure["run_total"], owner_policy["run_cap_microusd"], "run_cap"),
            (exposure["day_total"], owner_policy["day_cap_microusd"], "day_cap"),
            (exposure["month_total"], owner_policy["month_cap_microusd"], "month_cap"),
        ):
            if current + amount > cap:
                return self._deny(request, reason)
        quota = self._quota(
            request.provider_id, provider_policy["quota_account_id"], provider_day,
        )
        if quota["calls"] + 1 > provider_policy["daily_call_cap"]:
            return self._deny(request, "provider_call_quota")
        if quota["input_tokens"] + request.input_token_bound > provider_policy["daily_input_token_cap"]:
            return self._deny(request, "provider_input_quota")
        if quota["output_tokens"] + request.output_token_bound > provider_policy["daily_output_token_cap"]:
            return self._deny(request, "provider_output_quota")

        row = self.connection.execute(
            """INSERT INTO budget_reservations (
                    owner_id,project_id,run_id,target_id,provider_id,alias,
                    quota_account_id,reservation_key,owner_policy_version,
                    provider_policy_version,pricing_version,owner_day,owner_month,
                    provider_day,amount_microusd,input_token_bound,output_token_bound,
                    requested_run_cap_microusd,state
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'reserved')
                RETURNING *""",
            (
                request.owner_id, request.project_id, request.run_id, request.target_id,
                request.provider_id, request.alias, provider_policy["quota_account_id"],
                request.reservation_key, owner_policy["policy_version"],
                provider_policy["policy_version"], provider_policy["pricing_version"],
                owner_day, owner_month, provider_day, amount, request.input_token_bound,
                request.output_token_bound, request.requested_run_cap_microusd,
            ),
        ).fetchone()
        self.connection.execute(
            """INSERT INTO usage_events
                (reservation_id,run_id,target_id,kind,amount_microusd)
                VALUES (%s,%s,%s,'reserve',%s)""",
            (row["reservation_id"], request.run_id, request.target_id, amount),
        )
        _audit(
            self.connection, "budget_reserved", request.trace_id, request.owner_id,
            request.project_id, row["reservation_id"], "accepted",
        )
        return BudgetDecision(reservation=_reservation(row), reason=None)

    def revalidate_dispatch(
        self, reservation_id, candidate_id, attempt_id, trace_id, as_of,
    ) -> DispatchDecision:
        row = self.connection.execute(
            "SELECT * FROM budget_reservations WHERE reservation_id=%s FOR UPDATE",
            (reservation_id,),
        ).fetchone()
        if not row or row["state"] != "reserved":
            return DispatchDecision(grant=None, reason="reservation_unavailable")
        candidate = self.connection.execute(
            """SELECT c.*,r.deadline,t.model_id,t.provider AS provider_id,t.alias
                FROM prepared_contexts c
                JOIN runs r USING (run_id) JOIN run_targets t USING (target_id)
                WHERE c.candidate_id=%s AND c.run_id=%s AND c.target_id=%s""",
            (candidate_id, row["run_id"], row["target_id"]),
        ).fetchone()
        if not candidate or candidate["input_token_bound"] != row["input_token_bound"]:
            return DispatchDecision(grant=None, reason="candidate_mismatch")
        if as_of.tzinfo is None or as_of >= candidate["deadline"]:
            return DispatchDecision(grant=None, reason="deadline")
        if _current_projection(self.connection, candidate, as_of) is None:
            return DispatchDecision(grant=None, reason="policy_expired")

        owner_policy, provider_policy = self._policies(
            row["owner_id"], row["provider_id"], row["alias"],
        )
        registry = self.connection.execute(
            """SELECT status,pricing_version,privacy_profile FROM provider_models
                WHERE provider_id=%s AND alias=%s FOR SHARE""",
            (row["provider_id"], row["alias"]),
        ).fetchone()
        if (
            not registry
            or registry["status"] != "enabled"
            or registry["privacy_profile"] != "allowlisted"
        ):
            return DispatchDecision(grant=None, reason="registry_disabled")
        if (
            not owner_policy or not provider_policy or provider_policy["status"] != "active"
            or owner_policy["policy_version"] != row["owner_policy_version"]
            or provider_policy["policy_version"] != row["provider_policy_version"]
            or provider_policy["pricing_version"] != row["pricing_version"]
            or registry["pricing_version"] != row["pricing_version"]
            or as_of < owner_policy["effective_at"]
            or (owner_policy["expires_at"] and as_of >= owner_policy["expires_at"])
            or as_of < provider_policy["verified_at"]
            or as_of >= provider_policy["expires_at"]
        ):
            return DispatchDecision(grant=None, reason="policy_expired")
        try:
            owner_day, owner_month, provider_day = self._periods(
                as_of, provider_policy["quota_timezone"],
            )
        except ZoneInfoNotFoundError:
            return DispatchDecision(grant=None, reason="policy_expired")
        self.connection.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
            (f"budget-owner:{row['owner_id']}",),
        )
        self.connection.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
            (f"budget-provider:{row['provider_id']}:{row['quota_account_id']}",),
        )
        as_of = self._current_time(as_of)
        if as_of.tzinfo is None or as_of >= candidate["deadline"]:
            return DispatchDecision(grant=None, reason="deadline")
        if _current_projection(self.connection, candidate, as_of) is None:
            return DispatchDecision(grant=None, reason="policy_expired")
        if (
            as_of < owner_policy["effective_at"]
            or (owner_policy["expires_at"] and as_of >= owner_policy["expires_at"])
            or as_of < provider_policy["verified_at"]
            or as_of >= provider_policy["expires_at"]
        ):
            return DispatchDecision(grant=None, reason="policy_expired")
        try:
            owner_day, owner_month, provider_day = self._periods(
                as_of, provider_policy["quota_timezone"],
            )
        except ZoneInfoNotFoundError:
            return DispatchDecision(grant=None, reason="policy_expired")
        if provider_policy["quota_account_id"] != row["quota_account_id"]:
            return DispatchDecision(grant=None, reason="policy_expired")
        if _worst_cost(
            provider_policy, row["input_token_bound"], row["output_token_bound"],
        ) > row["amount_microusd"]:
            return DispatchDecision(grant=None, reason="policy_expired")
        exposure = self._exposure(
            row["owner_id"], row["run_id"], owner_day, owner_month, reservation_id,
        )
        if (
            exposure["run_total"] + row["amount_microusd"] > owner_policy["run_cap_microusd"]
            or exposure["day_total"] + row["amount_microusd"] > owner_policy["day_cap_microusd"]
            or exposure["month_total"] + row["amount_microusd"] > owner_policy["month_cap_microusd"]
            or (
                row["requested_run_cap_microusd"] is not None
                and exposure["run_total"] + row["amount_microusd"]
                > row["requested_run_cap_microusd"]
            )
        ):
            return DispatchDecision(grant=None, reason="period_cap")
        quota = self._quota(
            row["provider_id"], row["quota_account_id"], provider_day, reservation_id,
        )
        if (
            quota["calls"] + 1 > provider_policy["daily_call_cap"]
            or quota["input_tokens"] + row["input_token_bound"]
            > provider_policy["daily_input_token_cap"]
            or quota["output_tokens"] + row["output_token_bound"]
            > provider_policy["daily_output_token_cap"]
        ):
            return DispatchDecision(grant=None, reason="provider_quota")
        self.connection.execute(
            """UPDATE budget_reservations
                SET owner_day=%s,owner_month=%s,provider_day=%s,dispatch_validated_at=%s
                WHERE reservation_id=%s""",
            (owner_day, owner_month, provider_day, as_of, reservation_id),
        )
        replay = self.connection.execute(
            "SELECT * FROM dispatch_grants WHERE attempt_id=%s",
            (attempt_id,),
        ).fetchone()
        if replay:
            if replay["reservation_id"] != reservation_id or replay["candidate_id"] != candidate_id:
                return DispatchDecision(grant=None, reason="candidate_mismatch")
            return DispatchDecision(grant=_grant(replay), reason=None)
        if self.connection.execute(
            """SELECT 1 FROM dispatch_claims claim
               WHERE claim.reservation_id=%s""",
            (reservation_id,),
        ).fetchone():
            return DispatchDecision(grant=None, reason="reservation_unavailable")
        grant = self.connection.execute(
            """INSERT INTO dispatch_grants (
                    reservation_id,candidate_id,attempt_id,owner_id,project_id,run_id,
                    target_id,provider_id,alias,requested_model_id,input_digest,
                    input_token_bound,output_token_bound,deadline,validated_at
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                RETURNING *""",
            (
                reservation_id, candidate_id, attempt_id, row["owner_id"],
                row["project_id"], row["run_id"], row["target_id"],
                row["provider_id"], row["alias"], candidate["model_id"],
                candidate["request_hash"], row["input_token_bound"],
                row["output_token_bound"], candidate["deadline"], as_of,
            ),
        ).fetchone()
        return DispatchDecision(grant=_grant(grant), reason=None)

    def reconcile(
        self, reservation_id, trace_id, *, outcome, proven_unsent=False,
        actual_cost_microusd=None, input_tokens=None, output_tokens=None,
    ) -> BudgetReservation:
        row = self.connection.execute(
            "SELECT * FROM budget_reservations WHERE reservation_id=%s FOR UPDATE",
            (reservation_id,),
        ).fetchone()
        if not row:
            raise ValueError("Unknown reservation")
        if any(value is not None and value < 0 for value in (
            actual_cost_microusd, input_tokens, output_tokens,
        )):
            raise ValueError("Usage cannot be negative")
        if outcome == "release":
            if row["state"] == "released":
                return _reservation(row)
            if (
                not proven_unsent
                or row["state"] == "settled"
                or row["actual_cost_microusd"] is not None
            ):
                raise ValueError("Release requires trusted proof of non-delivery")
            state = "released"
            event_amount = 0
            actual_cost_microusd = input_tokens = output_tokens = None
        elif outcome == "hold":
            if row["state"] == "held":
                return _reservation(row)
            if row["state"] != "reserved":
                raise ValueError("Only an unresolved reservation can be held")
            if any(value is not None for value in (
                actual_cost_microusd, input_tokens, output_tokens,
            )):
                raise ValueError("Known usage must be settled, not held")
            state = "held"
            event_amount = max(row["amount_microusd"], actual_cost_microusd or 0)
        elif outcome == "settle":
            if row["actual_cost_microusd"] is not None:
                if (
                    row["actual_cost_microusd"] != actual_cost_microusd
                    or row["input_tokens"] != input_tokens
                    or row["output_tokens"] != output_tokens
                ):
                    raise ValueError("Settlement replay changed usage")
                return _reservation(row)
            if row["state"] not in {"reserved", "held"} or actual_cost_microusd is None:
                raise ValueError("Settlement requires trusted actual cost")
            if actual_cost_microusd > row["amount_microusd"]:
                state = "held"
                event_amount = actual_cost_microusd
                self.connection.execute(
                    """UPDATE provider_models SET status='disabled'
                        WHERE provider_id=%s AND alias=%s""",
                    (row["provider_id"], row["alias"]),
                )
                self.connection.execute(
                    """UPDATE provider_budget_policies SET status='disabled'
                        WHERE provider_id=%s AND alias=%s""",
                    (row["provider_id"], row["alias"]),
                )
            else:
                state = "settled"
                event_amount = actual_cost_microusd
        else:
            raise ValueError("Unsupported reconciliation outcome")

        updated = self.connection.execute(
            """UPDATE budget_reservations
                SET state=%s,actual_cost_microusd=%s,input_tokens=%s,output_tokens=%s
                WHERE reservation_id=%s RETURNING *""",
            (
                state, actual_cost_microusd, input_tokens, output_tokens,
                reservation_id,
            ),
        ).fetchone()
        self.connection.execute(
            """INSERT INTO usage_events (
                    reservation_id,run_id,target_id,kind,amount_microusd,
                    input_tokens,output_tokens
                ) VALUES (%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (reservation_id,kind) DO NOTHING""",
            (
                reservation_id, row["run_id"], row["target_id"], outcome,
                event_amount, input_tokens, output_tokens,
            ),
        )
        _audit(
            self.connection, "usage_reconciled", trace_id, row["owner_id"],
            row["project_id"], reservation_id, "accepted",
        )
        return _reservation(updated)


class PostgresAuthorizationPort(AuthorizationPort):
    def __init__(self, connection, clock=None):
        self.connection = connection
        self.clock = clock

    def validate_dispatch(self, request: GenerationRequest, as_of: datetime) -> DispatchGrant:
        if as_of.tzinfo is None or request.requested_model_id not in request.allowed_model_ids:
            raise PermissionError("Dispatch grant is unavailable or does not match the request")
        grant = self.connection.execute(
            """SELECT g.* FROM dispatch_grants g
                JOIN provider_attempts attempt
                  ON attempt.attempt_id=g.attempt_id
                 AND attempt.grant_id=g.grant_id
                JOIN run_work work ON work.run_id=g.run_id
                WHERE g.grant_id=%s AND g.attempt_id=%s
                AND g.provider_id=%s AND g.requested_model_id=%s
                AND g.input_digest=%s AND g.output_token_bound=%s
                AND g.validated_at<=%s AND g.deadline>%s
                AND attempt.state='prepared'
                AND attempt.work_fence=work.fence
                AND work.state='leased' AND work.lease_expires_at>%s""",
            (
                request.grant_id, request.attempt_id, request.provider_id,
                request.requested_model_id, _digest(request.model_visible_input),
                request.max_output_tokens, as_of, as_of, as_of,
            ),
        ).fetchone()
        if not grant:
            raise PermissionError("Dispatch grant is unavailable or does not match the request")
        reservation = self.connection.execute(
            "SELECT * FROM budget_reservations WHERE reservation_id=%s FOR UPDATE",
            (grant["reservation_id"],),
        ).fetchone()
        candidate = self.connection.execute(
            """SELECT c.*,t.provider AS provider_id,t.alias FROM prepared_contexts c
                JOIN run_targets t USING (target_id) WHERE c.candidate_id=%s""",
            (grant["candidate_id"],),
        ).fetchone()
        budget = PostgresBudgetPort(self.connection, clock=self.clock)
        owner_policy, provider_policy = budget._policies(
            grant["owner_id"], grant["provider_id"], grant["alias"],
        )
        registry = self.connection.execute(
            """SELECT status,pricing_version,privacy_profile FROM provider_models
                WHERE provider_id=%s AND alias=%s FOR SHARE""",
            (grant["provider_id"], grant["alias"]),
        ).fetchone()
        if (
            not reservation or reservation["state"] != "reserved"
            or reservation["dispatch_validated_at"] is None
            or not candidate or _current_projection(self.connection, candidate, as_of) is None
            or not owner_policy or not provider_policy or not registry
            or registry["status"] != "enabled"
            or registry["privacy_profile"] != "allowlisted"
            or registry["pricing_version"] != reservation["pricing_version"]
            or provider_policy["status"] != "active"
            or owner_policy["policy_version"] != reservation["owner_policy_version"]
            or provider_policy["policy_version"] != reservation["provider_policy_version"]
            or provider_policy["pricing_version"] != reservation["pricing_version"]
            or provider_policy["quota_account_id"] != reservation["quota_account_id"]
            or _worst_cost(
                provider_policy, reservation["input_token_bound"],
                reservation["output_token_bound"],
            ) > reservation["amount_microusd"]
            or as_of < owner_policy["effective_at"]
            or (owner_policy["expires_at"] and as_of >= owner_policy["expires_at"])
            or as_of < provider_policy["verified_at"]
            or as_of >= provider_policy["expires_at"]
        ):
            raise PermissionError("Dispatch grant is unavailable or does not match the request")
        try:
            owner_day, owner_month, provider_day = budget._periods(
                as_of, provider_policy["quota_timezone"],
            )
        except ZoneInfoNotFoundError as error:
            raise PermissionError(
                "Dispatch grant is unavailable or does not match the request"
            ) from error
        if (
            owner_day != reservation["owner_day"]
            or owner_month != reservation["owner_month"]
            or provider_day != reservation["provider_day"]
        ):
            raise PermissionError("Dispatch grant requires current-period revalidation")
        self.connection.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
            (f"budget-owner:{grant['owner_id']}",),
        )
        self.connection.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
            (f"budget-provider:{grant['provider_id']}:{reservation['quota_account_id']}",),
        )
        as_of = budget._current_time(as_of)
        if (
            as_of >= grant["deadline"]
            or _current_projection(self.connection, candidate, as_of) is None
            or as_of < owner_policy["effective_at"]
            or (owner_policy["expires_at"] and as_of >= owner_policy["expires_at"])
            or as_of < provider_policy["verified_at"]
            or as_of >= provider_policy["expires_at"]
        ):
            raise PermissionError("Dispatch grant expired while waiting for admission locks")
        try:
            owner_day, owner_month, provider_day = budget._periods(
                as_of, provider_policy["quota_timezone"],
            )
        except ZoneInfoNotFoundError as error:
            raise PermissionError(
                "Dispatch grant is unavailable or does not match the request"
            ) from error
        if (
            owner_day != reservation["owner_day"]
            or owner_month != reservation["owner_month"]
            or provider_day != reservation["provider_day"]
        ):
            raise PermissionError("Dispatch grant requires current-period revalidation")
        exposure = budget._exposure(
            grant["owner_id"], grant["run_id"], owner_day, owner_month,
            reservation["reservation_id"],
        )
        amount = reservation["amount_microusd"]
        if (
            exposure["run_total"] + amount > owner_policy["run_cap_microusd"]
            or exposure["day_total"] + amount > owner_policy["day_cap_microusd"]
            or exposure["month_total"] + amount > owner_policy["month_cap_microusd"]
            or (
                reservation["requested_run_cap_microusd"] is not None
                and exposure["run_total"] + amount
                > reservation["requested_run_cap_microusd"]
            )
        ):
            raise PermissionError("Dispatch grant exceeds the current owner budget")
        quota = budget._quota(
            grant["provider_id"], reservation["quota_account_id"], provider_day,
            reservation["reservation_id"],
        )
        if (
            quota["calls"] + 1 > provider_policy["daily_call_cap"]
            or quota["input_tokens"] + reservation["input_token_bound"]
            > provider_policy["daily_input_token_cap"]
            or quota["output_tokens"] + reservation["output_token_bound"]
            > provider_policy["daily_output_token_cap"]
        ):
            raise PermissionError("Dispatch grant exceeds the current provider quota")
        claimed = self.connection.execute(
            """INSERT INTO dispatch_claims (
                    grant_id,reservation_id,attempt_id,claimed_at
                ) VALUES (%s,%s,%s,%s)
                ON CONFLICT DO NOTHING RETURNING claim_id""",
            (
                grant["grant_id"], grant["reservation_id"],
                grant["attempt_id"], as_of,
            ),
        ).fetchone()
        if not claimed:
            raise PermissionError("Dispatch grant has already been claimed")
        self.connection.execute(
            """UPDATE budget_reservations SET state='held'
                WHERE reservation_id=%s AND state='reserved'""",
            (reservation["reservation_id"],),
        )
        self.connection.execute(
            """INSERT INTO usage_events (
                    reservation_id,run_id,target_id,attempt_id,kind,amount_microusd
                ) VALUES (%s,%s,%s,%s,'hold',%s)""",
            (
                reservation["reservation_id"], reservation["run_id"],
                reservation["target_id"], grant["attempt_id"],
                reservation["amount_microusd"],
            ),
        )
        return _grant(grant)
