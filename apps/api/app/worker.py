"""Durable P0 run worker entry point."""

import logging
import socket
import time
from uuid import uuid4

from app.adapters.postgres_policy import PostgresBudgetPort
from app.adapters.postgres_runs import PostgresRunRepository
from app.db import connect


logger = logging.getLogger("ai_decision_hub.worker")


class RunWorker:
    def __init__(self, worker_id: str, lease_seconds: int = 30) -> None:
        self.worker_id = worker_id
        self.lease_seconds = lease_seconds

    def run_once(self) -> bool:
        trace_id = uuid4()
        with connect() as connection:
            repository = PostgresRunRepository(connection, PostgresBudgetPort(connection))
            claim = repository.claim_work(
                self.worker_id, trace_id, self.lease_seconds
            )
            if claim is None:
                return False
            if repository.recover_claimed_dispatches(claim, trace_id):
                return True
            if not repository.park_manual_work(claim, trace_id):
                raise RuntimeError("No qualified provider executor for claimed run")
            return True

    def run_forever(self, idle_seconds: float = 1.0) -> None:
        while True:
            try:
                worked = self.run_once()
            except Exception:
                logger.exception("Run worker transaction failed")
                worked = False
            if not worked:
                time.sleep(idle_seconds)


def main() -> None:
    RunWorker(f"local-{socket.gethostname()}").run_forever()


if __name__ == "__main__":
    main()
