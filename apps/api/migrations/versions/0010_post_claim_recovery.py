"""Permit fenced terminal recovery of an already claimed provider attempt."""

from alembic import op


revision = "0010_post_claim_recovery"
down_revision = "0009_attempt_fencing"


def upgrade():
    op.execute(
        """
        CREATE OR REPLACE FUNCTION validate_provider_attempt_fence()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            -- The grant/fence relationship is immutable after insert.  A later
            -- worker must still be able to terminalize a claimed attempt after
            -- taking a higher work fence; it must never be able to send it again.
            IF TG_OP='INSERT' AND NEW.grant_id IS NOT NULL AND NOT EXISTS (
                SELECT 1
                  FROM dispatch_grants g
                  JOIN run_work work ON work.run_id=g.run_id
                 WHERE g.grant_id=NEW.grant_id
                   AND g.attempt_id=NEW.attempt_id
                   AND g.run_id=NEW.run_id
                   AND g.target_id=NEW.target_id
                   AND work.fence=NEW.work_fence
            ) THEN
                RAISE EXCEPTION 'Provider attempt must match its grant and work fence';
            END IF;
            IF TG_OP='UPDATE' AND OLD.state='prepared'
               AND NEW.state='dispatch_claimed' AND NOT EXISTS (
                SELECT 1
                  FROM dispatch_claims claim
                  JOIN dispatch_grants g ON g.grant_id=claim.grant_id
                  JOIN run_work work ON work.run_id=g.run_id
                 WHERE claim.grant_id=NEW.grant_id
                   AND claim.attempt_id=NEW.attempt_id
                   AND claim.reservation_id=g.reservation_id
                   AND work.state='leased'
                   AND work.fence=NEW.work_fence
                   AND work.lease_expires_at>clock_timestamp()
            ) THEN
                RAISE EXCEPTION 'Dispatch claim must hold the current work fence';
            END IF;
            RETURN NEW;
        END; $$;

        CREATE OR REPLACE FUNCTION protect_provider_attempt()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP='DELETE' THEN
                RAISE EXCEPTION 'Provider attempt evidence is immutable';
            END IF;
            IF ROW(
                NEW.attempt_id,NEW.run_id,NEW.target_id,NEW.attempt_no,
                NEW.work_fence,NEW.request_hash,NEW.grant_id,NEW.created_at
            ) IS DISTINCT FROM ROW(
                OLD.attempt_id,OLD.run_id,OLD.target_id,OLD.attempt_no,
                OLD.work_fence,OLD.request_hash,OLD.grant_id,OLD.created_at
            ) THEN
                RAISE EXCEPTION 'Provider attempt identity is immutable';
            END IF;
            IF NEW.state<>OLD.state AND NOT (
                (OLD.state='prepared' AND NEW.state IN (
                    'dispatch_claimed','failed','timed_out','cancelled'
                )) OR
                (OLD.state='prepared' AND NEW.state='delivery_unknown' AND EXISTS (
                    SELECT 1 FROM dispatch_claims claim
                    WHERE claim.attempt_id=OLD.attempt_id
                      AND claim.grant_id=OLD.grant_id
                )) OR
                (OLD.state='dispatch_claimed' AND NEW.state IN (
                    'succeeded','failed','delivery_unknown','timed_out','cancelled'
                ))
            ) THEN
                RAISE EXCEPTION 'Invalid provider attempt transition % -> %', OLD.state, NEW.state;
            END IF;
            IF OLD.state IN ('succeeded','failed','delivery_unknown','timed_out','cancelled')
               AND NEW IS DISTINCT FROM OLD THEN
                RAISE EXCEPTION 'Terminal provider attempt is immutable';
            END IF;
            RETURN NEW;
        END; $$;
        """
    )


def downgrade():
    raise RuntimeError("Restore the verified pre-migration backup to roll back.")
