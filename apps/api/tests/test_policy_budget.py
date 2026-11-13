from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
import psycopg

from app.adapters.postgres_policy import (
    PostgresAuthorizationPort as _PostgresAuthorizationPort,
    PostgresBudgetPort as _PostgresBudgetPort,
    PostgresContextPort,
)
from app.db import connect
from app.ports import BudgetRequest, ContextRequest, GenerationRequest
from app.security import digest


def PostgresBudgetPort(connection):
    return _PostgresBudgetPort(connection, clock=lambda supplied: supplied)


def PostgresAuthorizationPort(connection):
    return _PostgresAuthorizationPort(connection, clock=lambda supplied: supplied)


def _provider_model(conn, provider_id, alias, at):
    conn.execute(
        """INSERT INTO provider_models (
            provider_id,alias,gateway,routing_mode,status,last_verified_at,
            acquisition_mode,app_name,configured_model_id,model_family,capabilities,
            pricing_status,privacy_profile,pricing_version,identity_confidence
        ) VALUES (%s,%s,'fixture-api','direct','enabled',%s,'official_api',
                  'Fixture API','fixture-model','Fixture Family',ARRAY['text'],
                  'verified_priced','allowlisted','price-v1','provider_reported')""",
        (provider_id, alias, at - timedelta(days=1)),
    )


def _provider(conn, provider_id, alias, quota_account, at, *, call_cap=10):
    _provider_model(conn, provider_id, alias, at)
    conn.execute(
        """INSERT INTO provider_budget_policies (
            provider_id,alias,quota_account_id,policy_version,pricing_version,status,
            verified_at,expires_at,quota_timezone,fixed_cost_microusd,
            input_microusd_per_million,output_microusd_per_million,
            max_input_tokens,max_output_tokens,daily_call_cap,
            daily_input_token_cap,daily_output_token_cap
        ) VALUES (%s,%s,%s,'provider-policy-v1','price-v1','active',%s,%s,
                  'America/Los_Angeles',5,1000000,1000000,100000,100000,%s,
                  1000000,1000000)""",
        (provider_id, alias, quota_account, at - timedelta(days=1),
         at + timedelta(days=30), call_cap),
    )


def _official_run(client, thread, *, at=None, targets=1, call_cap=10,
                  provider_id=None, aliases=None, quota_account=None):
    at = at or datetime.now(timezone.utc)
    provider_id = provider_id or f"fixture-{uuid4()}"
    quota_account = quota_account or f"account-{uuid4()}"
    aliases = aliases or [f"alias-{index}" for index in range(targets)]
    source = client.post(
        f"/v1/conversations/{thread['conversation_id']}/messages",
        json={"content": "Private source context"},
    ).json()
    question = client.post(
        f"/v1/conversations/{thread['conversation_id']}/messages",
        json={"content": "What is the bounded answer?"},
    ).json()
    with connect() as conn:
        project = conn.execute(
            "SELECT owner_id FROM projects WHERE project_id=%s",
            (thread["project_id"],),
        ).fetchone()
        owner_id = project["owner_id"]
        conn.execute(
            """UPDATE owner_budget_policies SET policy_version='owner-policy-v1',
                run_cap_microusd=1000000,day_cap_microusd=1000000,
                month_cap_microusd=1000000,effective_at=%s,expires_at=%s
                WHERE owner_id=%s""",
            (at - timedelta(days=1), at + timedelta(days=30), owner_id),
        )
        for alias in aliases:
            _provider(conn, provider_id, alias, quota_account, at, call_cap=call_cap)
            conn.execute(
                """INSERT INTO project_provider_policies (
                    project_id,provider_id,alias,policy_version,status,consented_at,
                    verified_at,expires_at,max_input_tokens
                ) VALUES (%s,%s,%s,'context-policy-v1','allowed',%s,%s,%s,100000)""",
                (thread["project_id"], provider_id, alias, at - timedelta(hours=1),
                 at - timedelta(days=1), at + timedelta(days=30)),
            )
        run_id = conn.execute(
            """INSERT INTO runs (
                project_id,conversation_id,message_id,owner_id,request_key,request_hash,
                request_schema_version,deadline
            ) VALUES (%s,%s,%s,%s,%s,'fixture',0,%s) RETURNING run_id""",
            (thread["project_id"], thread["conversation_id"], question["message_id"],
             owner_id, str(uuid4()), at + timedelta(days=3)),
        ).fetchone()["run_id"]
        conn.execute(
            "INSERT INTO run_context_sources VALUES (%s,1,%s)",
            (run_id, source["message_id"]),
        )
        target_ids = []
        for index, alias in enumerate(aliases):
            model_id = "fixture-model" if index == 0 else f"fixture-model-{index}"
            target_ids.append(conn.execute(
                """INSERT INTO run_targets (
                    run_id,provider,alias,model_id,gateway,routing_mode
                ) VALUES (%s,%s,%s,%s,'ignored','ignored')
                RETURNING target_id""",
                (run_id, provider_id, alias, model_id),
            ).fetchone()["target_id"])
    return {
        "at": at,
        "owner_id": owner_id,
        "project_id": UUID(thread["project_id"]),
        "run_id": run_id,
        "target_ids": target_ids,
        "source_id": UUID(source["message_id"]),
        "question_id": UUID(question["message_id"]),
        "provider_id": provider_id,
        "aliases": aliases,
        "quota_account": quota_account,
    }


def _context_request(data, target_index=0):
    return ContextRequest(
        trace_id=uuid4(), owner_id=data["owner_id"], project_id=data["project_id"],
        run_id=data["run_id"], target_id=data["target_ids"][target_index],
        provider_id=data["provider_id"], alias=data["aliases"][target_index],
        question="What is the bounded answer?", source_message_ids=(data["source_id"],),
        max_input_tokens=100000, as_of=data["at"],
    )


def _budget_request(data, projection, target_index=0, *, key=None, as_of=None):
    return BudgetRequest(
        trace_id=uuid4(), owner_id=data["owner_id"], project_id=data["project_id"],
        run_id=data["run_id"], target_id=data["target_ids"][target_index],
        provider_id=data["provider_id"], alias=data["aliases"][target_index],
        reservation_key=key or f"{data['run_id']}:{target_index}",
        input_token_bound=projection.input_token_bound, output_token_bound=50,
        requested_run_cap_microusd=data.get("max_cost_microusd"),
        as_of=as_of or data["at"],
    )


def _allow_source(conn, data, target_index=0, *, decision="allow", redacted=None):
    conn.execute(
        """INSERT INTO context_source_rules (
            project_id,message_id,provider_id,alias,decision,redacted_content,policy_version
        ) VALUES (%s,%s,%s,%s,'allow',NULL,'context-policy-v1')
        ON CONFLICT (message_id,provider_id,alias) DO NOTHING""",
        (data["project_id"], data["question_id"], data["provider_id"],
         data["aliases"][target_index]),
    )
    conn.execute(
        """INSERT INTO context_source_rules (
            project_id,message_id,provider_id,alias,decision,redacted_content,policy_version
        ) VALUES (%s,%s,%s,%s,%s,%s,'context-policy-v1')""",
        (data["project_id"], data["source_id"], data["provider_id"],
         data["aliases"][target_index], decision, redacted),
    )


def test_context_requires_explicit_current_source_consent(client, thread):
    data = _official_run(client, thread)
    with connect() as conn:
        conn.execute(
            """INSERT INTO context_source_rules (
                project_id,message_id,provider_id,alias,decision,policy_version
            ) VALUES (%s,%s,%s,%s,'allow','context-policy-v1')""",
            (data["project_id"], data["question_id"], data["provider_id"],
             data["aliases"][0]),
        )
        denied = PostgresContextPort(conn).prepare(_context_request(data))
        assert denied.projection is None and denied.reason == "source_denied"
        _allow_source(conn, data, decision="redact", redacted="Approved redaction")
        allowed = PostgresContextPort(conn).prepare(_context_request(data))
        assert allowed.reason is None
        assert allowed.projection.source_message_ids == (data["source_id"],)
        assert "Approved redaction" in allowed.projection.model_visible_input
        assert "Private source context" not in allowed.projection.model_visible_input
        stored = conn.execute(
            "SELECT * FROM prepared_contexts WHERE candidate_id=%s",
            (allowed.projection.candidate_id,),
        ).fetchone()
        assert stored["request_hash"] == digest(allowed.projection.model_visible_input)
        assert stored["model_visible_input"] == allowed.projection.model_visible_input
        with pytest.raises(psycopg.errors.RaiseException):
            with conn.transaction():
                conn.execute(
                    "UPDATE prepared_contexts SET omission_count=1 WHERE candidate_id=%s",
                    (allowed.projection.candidate_id,),
                )


def test_reservation_grant_authorization_settlement_and_usage(client, thread):
    data = _official_run(client, thread)
    with connect() as conn:
        _allow_source(conn, data)
        projection = PostgresContextPort(conn).prepare(_context_request(data)).projection
        decision = PostgresBudgetPort(conn).reserve(_budget_request(data, projection))
        assert decision.reason is None and decision.reservation.state == "reserved"
        attempt_id = uuid4()
        grant = PostgresBudgetPort(conn).revalidate_dispatch(
            decision.reservation.reservation_id, projection.candidate_id,
            attempt_id, uuid4(), data["at"] + timedelta(seconds=1),
        ).grant
        request = GenerationRequest(
            attempt_id=attempt_id, grant_id=grant.grant_id,
            provider_id=data["provider_id"], requested_model_id="fixture-model",
            model_visible_input=projection.model_visible_input, timeout_ms=1000,
            max_output_tokens=50, allowed_model_ids=("fixture-model",),
        )
        assert PostgresAuthorizationPort(conn).validate_dispatch(
            request, data["at"] + timedelta(seconds=2),
        ).grant_id == grant.grant_id
        with pytest.raises(PermissionError, match="unavailable"):
            PostgresAuthorizationPort(conn).validate_dispatch(
                request, data["at"] + timedelta(seconds=2),
            )
        assert PostgresBudgetPort(conn).revalidate_dispatch(
            decision.reservation.reservation_id, projection.candidate_id,
            uuid4(), uuid4(), data["at"] + timedelta(seconds=3),
        ).reason == "reservation_unavailable"
        settled = PostgresBudgetPort(conn).reconcile(
            decision.reservation.reservation_id, uuid4(), outcome="settle",
            actual_cost_microusd=decision.reservation.amount_microusd,
            input_tokens=projection.input_token_bound, output_tokens=20,
        )
        assert settled.state == "settled"
        assert PostgresBudgetPort(conn).reconcile(
            decision.reservation.reservation_id, uuid4(), outcome="settle",
            actual_cost_microusd=decision.reservation.amount_microusd,
            input_tokens=projection.input_token_bound, output_tokens=20,
        ) == settled
        with pytest.raises(ValueError, match="changed usage"):
            PostgresBudgetPort(conn).reconcile(
                decision.reservation.reservation_id, uuid4(), outcome="settle",
                actual_cost_microusd=decision.reservation.amount_microusd - 1,
                input_tokens=projection.input_token_bound, output_tokens=20,
            )
    usage = client.get("/v1/usage", params={"run_id": str(data["run_id"])}).json()
    assert usage["currency"] == "USD"
    assert usage["run"]["settled_microusd"] == decision.reservation.amount_microusd
    assert usage["run"]["input_tokens"] == projection.input_token_bound


def test_last_budget_unit_is_atomic_across_competing_targets(client, thread):
    data = _official_run(client, thread, targets=2)
    projections = []
    with connect() as conn:
        for index in range(2):
            _allow_source(conn, data, index)
            projections.append(PostgresContextPort(conn).prepare(
                _context_request(data, index),
            ).projection)
        amount = projections[0].input_token_bound + 50 + 5
        exposure = PostgresBudgetPort(conn)._exposure(
            data["owner_id"], data["run_id"], data["at"].date(),
            data["at"].date().replace(day=1),
        )
        conn.execute(
            """UPDATE owner_budget_policies SET run_cap_microusd=%s,
                day_cap_microusd=%s,month_cap_microusd=%s WHERE owner_id=%s""",
            (amount, exposure["day_total"] + amount,
             exposure["month_total"] + amount, data["owner_id"]),
        )

    def reserve(index):
        with connect() as conn:
            return PostgresBudgetPort(conn).reserve(
                _budget_request(data, projections[index], index),
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        decisions = list(pool.map(reserve, range(2)))
    assert sum(item.reservation is not None for item in decisions) == 1
    assert {item.reason for item in decisions if item.reason} == {"run_cap"}


def test_reserve_resamples_authoritative_time_after_waiting_for_lock(client, thread):
    data = _official_run(client, thread)
    with connect() as conn:
        _allow_source(conn, data)
        projection = PostgresContextPort(conn).prepare(_context_request(data)).projection
    current = {"value": data["at"]}

    def reserve_after_lock():
        with connect() as conn:
            port = _PostgresBudgetPort(conn, clock=lambda supplied: current["value"])
            return port.reserve(_budget_request(data, projection))

    holder = connect()
    try:
        holder.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
            (f"budget-owner:{data['owner_id']}",),
        )
        with ThreadPoolExecutor(max_workers=1) as pool:
            pending = pool.submit(reserve_after_lock)
            current["value"] = data["at"] + timedelta(days=4)
            holder.commit()
            denied = pending.result(timeout=5)
    finally:
        holder.close()
    assert denied.reservation is None and denied.reason == "policy_expired"


def test_aggregate_admission_rolls_back_all_targets_on_denial(client, thread):
    data = _official_run(client, thread, targets=2)
    with connect() as conn:
        projections = []
        for index in range(2):
            _allow_source(conn, data, index)
            projections.append(PostgresContextPort(conn).prepare(
                _context_request(data, index),
            ).projection)
        amount = projections[0].input_token_bound + 50 + 5
        data["max_cost_microusd"] = amount
        conn.execute(
            "UPDATE runs SET max_cost_microusd=%s WHERE run_id=%s",
            (amount, data["run_id"]),
        )
        conn.execute(
            """UPDATE owner_budget_policies SET run_cap_microusd=%s,
                day_cap_microusd=%s,month_cap_microusd=%s WHERE owner_id=%s""",
            (1000000, 1000000, 1000000, data["owner_id"]),
        )
        first = PostgresBudgetPort(conn).reserve(_budget_request(data, projections[0], 0))
        second = PostgresBudgetPort(conn).reserve(_budget_request(data, projections[1], 1))
        assert first.reservation is not None and second.reason == "request_cap"
        conn.rollback()
    with connect() as conn:
        assert conn.execute(
            "SELECT count(*) AS count FROM budget_reservations WHERE run_id=%s",
            (data["run_id"],),
        ).fetchone()["count"] == 0


def test_dispatch_revalidation_moves_period_and_rechecks_cap(client, thread):
    before_reset = datetime(2026, 7, 1, 23, 59, tzinfo=timezone.utc)
    first = _official_run(client, thread, at=before_reset)
    with connect() as conn:
        _allow_source(conn, first)
        first_projection = PostgresContextPort(conn).prepare(_context_request(first)).projection
        first_reservation = PostgresBudgetPort(conn).reserve(
            _budget_request(first, first_projection),
        ).reservation
        first_attempt = uuid4()
        first_grant = PostgresBudgetPort(conn).revalidate_dispatch(
            first_reservation.reservation_id, first_projection.candidate_id,
            first_attempt, uuid4(), before_reset + timedelta(seconds=1),
        )
        assert first_grant.grant is not None

    second_project = client.post("/v1/projects", json={"name": "New UTC period"}).json()
    second_thread = client.post("/v1/conversations", json={
        "project_id": second_project["project_id"], "title": "Period movement",
    }).json()
    after_reset = before_reset + timedelta(minutes=2)
    second = _official_run(client, second_thread, at=after_reset)
    with connect() as conn:
        _allow_source(conn, second)
        second_projection = PostgresContextPort(conn).prepare(_context_request(second)).projection
        second_reservation = PostgresBudgetPort(conn).reserve(
            _budget_request(second, second_projection),
        ).reservation
        conn.execute(
            """UPDATE owner_budget_policies SET day_cap_microusd=%s
                WHERE owner_id=%s""",
            (second_reservation.amount_microusd, first["owner_id"]),
        )
        denied = PostgresBudgetPort(conn).revalidate_dispatch(
            first_reservation.reservation_id, first_projection.candidate_id,
            first_attempt, uuid4(), after_reset,
        )
        assert denied.grant is None and denied.reason == "period_cap"


def test_context_revocation_and_same_window_cap_tightening_block_dispatch(client, thread):
    data = _official_run(client, thread)
    with connect() as conn:
        _allow_source(conn, data)
        projection = PostgresContextPort(conn).prepare(_context_request(data)).projection
        reservation = PostgresBudgetPort(conn).reserve(
            _budget_request(data, projection),
        ).reservation
        attempt = uuid4()
        grant = PostgresBudgetPort(conn).revalidate_dispatch(
            reservation.reservation_id, projection.candidate_id,
            attempt, uuid4(), data["at"] + timedelta(seconds=1),
        )
        assert grant.grant is not None
        conn.execute(
            """UPDATE context_source_rules SET decision='redact',
                redacted_content='More restrictive current text'
                WHERE message_id=%s AND provider_id=%s AND alias=%s""",
            (data["source_id"], data["provider_id"], data["aliases"][0]),
        )
        revoked = PostgresBudgetPort(conn).revalidate_dispatch(
            reservation.reservation_id, projection.candidate_id,
            attempt, uuid4(), data["at"] + timedelta(seconds=2),
        )
        assert revoked.grant is None and revoked.reason == "policy_expired"
        conn.execute(
            """UPDATE context_source_rules SET decision='allow',redacted_content=NULL
                WHERE message_id=%s AND provider_id=%s AND alias=%s""",
            (data["source_id"], data["provider_id"], data["aliases"][0]),
        )
        conn.execute(
            """UPDATE provider_budget_policies SET fixed_cost_microusd=%s
                WHERE provider_id=%s AND alias=%s""",
            (reservation.amount_microusd + 1, data["provider_id"], data["aliases"][0]),
        )
        repriced = PostgresBudgetPort(conn).revalidate_dispatch(
            reservation.reservation_id, projection.candidate_id,
            attempt, uuid4(), data["at"] + timedelta(seconds=3),
        )
        assert repriced.grant is None and repriced.reason == "policy_expired"
        conn.execute(
            """UPDATE provider_budget_policies SET fixed_cost_microusd=5
                WHERE provider_id=%s AND alias=%s""",
            (data["provider_id"], data["aliases"][0]),
        )
        conn.execute(
            """UPDATE owner_budget_policies SET run_cap_microusd=0,
                day_cap_microusd=0,month_cap_microusd=0 WHERE owner_id=%s""",
            (data["owner_id"],),
        )
        request = GenerationRequest(
            attempt_id=attempt, grant_id=grant.grant.grant_id,
            provider_id=data["provider_id"], requested_model_id="fixture-model",
            model_visible_input=projection.model_visible_input, timeout_ms=1000,
            max_output_tokens=50, allowed_model_ids=("fixture-model",),
        )
        with pytest.raises(PermissionError, match="budget"):
            PostgresAuthorizationPort(conn).validate_dispatch(
                request, data["at"] + timedelta(seconds=4),
            )


def test_claimed_unknown_delivery_carries_across_utc_reset(client, thread):
    before_reset = datetime(2026, 8, 1, 23, 59, tzinfo=timezone.utc)
    first = _official_run(client, thread, at=before_reset)
    with connect() as conn:
        _allow_source(conn, first)
        projection = PostgresContextPort(conn).prepare(_context_request(first)).projection
        reservation = PostgresBudgetPort(conn).reserve(
            _budget_request(first, projection),
        ).reservation
        attempt = uuid4()
        grant = PostgresBudgetPort(conn).revalidate_dispatch(
            reservation.reservation_id, projection.candidate_id,
            attempt, uuid4(), before_reset + timedelta(seconds=1),
        ).grant
        request = GenerationRequest(
            attempt_id=attempt, grant_id=grant.grant_id,
            provider_id=first["provider_id"], requested_model_id="fixture-model",
            model_visible_input=projection.model_visible_input, timeout_ms=1000,
            max_output_tokens=50, allowed_model_ids=("fixture-model",),
        )
        PostgresAuthorizationPort(conn).validate_dispatch(
            request, before_reset + timedelta(seconds=2),
        )
    with connect() as conn:
        assert conn.execute(
            "SELECT state FROM budget_reservations WHERE reservation_id=%s",
            (reservation.reservation_id,),
        ).fetchone()["state"] == "held"

    project = client.post("/v1/projects", json={"name": "Post-reset admission"}).json()
    next_thread = client.post("/v1/conversations", json={
        "project_id": project["project_id"], "title": "After reset",
    }).json()
    after_reset = before_reset + timedelta(minutes=2)
    second = _official_run(client, next_thread, at=after_reset)
    with connect() as conn:
        _allow_source(conn, second)
        projection = PostgresContextPort(conn).prepare(_context_request(second)).projection
        conn.execute(
            """UPDATE owner_budget_policies SET day_cap_microusd=%s
                WHERE owner_id=%s""",
            (reservation.amount_microusd, first["owner_id"]),
        )
        denied = PostgresBudgetPort(conn).reserve(
            _budget_request(second, projection),
        )
        assert denied.reservation is None and denied.reason == "day_cap"


def test_shared_provider_quota_uses_pacific_window_across_projects(client, thread):
    first_at = datetime(2026, 7, 1, 7, 30, tzinfo=timezone.utc)
    provider = f"shared-{uuid4()}"
    account = f"shared-account-{uuid4()}"
    first = _official_run(
        client, thread, at=first_at, call_cap=1, provider_id=provider,
        quota_account=account, aliases=["first"],
    )
    other_project = client.post("/v1/projects", json={"name": "Second quota project"}).json()
    other_thread = client.post("/v1/conversations", json={
        "project_id": other_project["project_id"], "title": "Quota scope",
    }).json()
    second = _official_run(
        client, other_thread, at=first_at, call_cap=1, provider_id=provider,
        quota_account=account, aliases=["second"],
    )
    with connect() as conn:
        with pytest.raises(psycopg.errors.RaiseException, match="one quota policy"):
            with conn.transaction():
                _provider(
                    conn, provider, "inconsistent", account, first_at, call_cap=2,
                )
    projections = []
    for data in (first, second):
        with connect() as conn:
            _allow_source(conn, data)
            projections.append(PostgresContextPort(conn).prepare(_context_request(data)).projection)
    with connect() as conn:
        assert PostgresBudgetPort(conn).reserve(
            _budget_request(first, projections[0], key="first-key"),
        ).reservation
    with connect() as conn:
        before_pacific_reset = first_at + timedelta(hours=23)
        denied = PostgresBudgetPort(conn).reserve(
            _budget_request(
                second, projections[1], key="second-key", as_of=before_pacific_reset,
            ),
        )
        assert denied.reason == "provider_call_quota"
    with connect() as conn:
        after_pacific_reset = first_at + timedelta(days=1)
        allowed = PostgresBudgetPort(conn).reserve(
            _budget_request(
                second, projections[1], key="second-key", as_of=after_pacific_reset,
            ),
        )
        assert allowed.reservation is not None


def test_conflicting_shared_quota_policies_serialize(client):
    at = datetime(2026, 9, 1, 12, tzinfo=timezone.utc)
    provider = f"quota-race-{uuid4()}"
    account = f"quota-account-{uuid4()}"
    aliases = ("race-a", "race-b")
    with connect() as conn:
        for alias in aliases:
            _provider_model(conn, provider, alias, at)

    def insert_policy(item):
        alias, cap = item
        try:
            with connect() as conn:
                conn.execute(
                    """INSERT INTO provider_budget_policies (
                        provider_id,alias,quota_account_id,policy_version,pricing_version,
                        status,verified_at,expires_at,quota_timezone,fixed_cost_microusd,
                        input_microusd_per_million,output_microusd_per_million,
                        max_input_tokens,max_output_tokens,daily_call_cap,
                        daily_input_token_cap,daily_output_token_cap
                    ) VALUES (%s,%s,%s,'race-v1','price-v1','active',%s,%s,
                        'America/Los_Angeles',0,0,0,1000,1000,%s,1000,1000)""",
                    (provider, alias, account, at - timedelta(days=1),
                     at + timedelta(days=30), cap),
                )
            return True
        except psycopg.errors.RaiseException:
            return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(insert_policy, zip(aliases, (1, 2), strict=True)))
    assert sorted(outcomes) == [False, True]


def test_unknown_delivery_holds_and_overrun_quarantines_provider(client, thread):
    data = _official_run(client, thread, targets=2)
    reservations = []
    with connect() as conn:
        for index in range(2):
            _allow_source(conn, data, index)
            projection = PostgresContextPort(conn).prepare(
                _context_request(data, index),
            ).projection
            reservations.append(PostgresBudgetPort(conn).reserve(
                _budget_request(data, projection, index),
            ).reservation)
        with pytest.raises(ValueError, match="proof"):
            PostgresBudgetPort(conn).reconcile(
                reservations[0].reservation_id, uuid4(), outcome="release",
            )
        held = PostgresBudgetPort(conn).reconcile(
            reservations[0].reservation_id, uuid4(), outcome="hold",
        )
        assert held.state == "held"
        released = PostgresBudgetPort(conn).reconcile(
            reservations[0].reservation_id, uuid4(), outcome="release", proven_unsent=True,
        )
        assert released.state == "released"
        overrun = PostgresBudgetPort(conn).reconcile(
            reservations[1].reservation_id, uuid4(), outcome="settle",
            actual_cost_microusd=reservations[1].amount_microusd + 1,
            input_tokens=1, output_tokens=1,
        )
        assert overrun.state == "held"
        with pytest.raises(ValueError, match="changed usage"):
            PostgresBudgetPort(conn).reconcile(
                reservations[1].reservation_id, uuid4(), outcome="settle",
                actual_cost_microusd=reservations[1].amount_microusd,
                input_tokens=1, output_tokens=1,
            )
        with pytest.raises(ValueError, match="proof"):
            PostgresBudgetPort(conn).reconcile(
                reservations[1].reservation_id, uuid4(), outcome="release",
                proven_unsent=True,
            )
        states = conn.execute(
            """SELECT pm.status AS registry,pb.status AS budget
                FROM provider_models pm JOIN provider_budget_policies pb USING (provider_id,alias)
                WHERE pm.provider_id=%s AND pm.alias=%s""",
            (data["provider_id"], data["aliases"][1]),
        ).fetchone()
        assert states == {"registry": "disabled", "budget": "disabled"}
        assert conn.execute(
            """SELECT kind,amount_microusd FROM usage_events
                WHERE reservation_id=%s AND kind='settle'""",
            (reservations[1].reservation_id,),
        ).fetchone()["amount_microusd"] == reservations[1].amount_microusd + 1
        carried = PostgresBudgetPort(conn)._exposure(
            data["owner_id"], data["run_id"],
            (data["at"] + timedelta(days=40)).date(),
            (data["at"] + timedelta(days=40)).date().replace(day=1),
        )
        assert carried["day_total"] >= reservations[1].amount_microusd + 1
        assert carried["month_total"] >= reservations[1].amount_microusd + 1
