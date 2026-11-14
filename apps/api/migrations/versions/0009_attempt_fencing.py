"""Fence provider attempts and permit safe pre-claim grant recovery."""

from alembic import op


revision = "0009_attempt_fencing"
down_revision = "0008_run_lifecycle"


def upgrade():
    op.execute(
        """
        ALTER TABLE dispatch_claims ADD COLUMN reservation_id UUID;
        UPDATE dispatch_claims claim
           SET reservation_id=g.reservation_id
          FROM dispatch_grants g
         WHERE g.grant_id=claim.grant_id;
        ALTER TABLE dispatch_claims
            ALTER COLUMN reservation_id SET NOT NULL,
            ADD CONSTRAINT dispatch_claims_reservation_fk
                FOREIGN KEY (reservation_id)
                REFERENCES budget_reservations(reservation_id),
            ADD CONSTRAINT dispatch_claims_one_send_per_reservation
                UNIQUE (reservation_id);

        ALTER TABLE dispatch_grants
            DROP CONSTRAINT dispatch_grants_reservation_id_key;

        ALTER TABLE provider_attempts
            ADD CONSTRAINT provider_attempts_grant_shape CHECK (
                state NOT IN ('prepared','dispatch_claimed','succeeded','delivery_unknown')
                OR grant_id IS NOT NULL
            );

        CREATE FUNCTION validate_provider_attempt_fence()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF NEW.grant_id IS NOT NULL AND NOT EXISTS (
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
        CREATE TRIGGER provider_attempts_fence
            BEFORE INSERT OR UPDATE ON provider_attempts
            FOR EACH ROW EXECUTE FUNCTION validate_provider_attempt_fence();

        CREATE OR REPLACE FUNCTION validate_dispatch_claim()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM dispatch_grants g
                WHERE g.grant_id=NEW.grant_id
                  AND g.attempt_id=NEW.attempt_id
                  AND g.reservation_id=NEW.reservation_id
                  AND NEW.claimed_at>=g.validated_at
                  AND NEW.claimed_at<g.deadline
            ) THEN
                RAISE EXCEPTION 'Dispatch claim must match a current grant';
            END IF;
            RETURN NEW;
        END; $$;
        """
    )


def downgrade():
    raise RuntimeError("Restore the verified pre-migration backup to roll back.")
