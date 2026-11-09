import os
from pathlib import Path

import psycopg
from psycopg.rows import dict_row
from sqlalchemy import URL


def read_secret(name: str) -> str:
    value = Path(os.environ[name + "_FILE"]).read_text().rstrip("\r\n")
    if not value:
        raise ValueError(f"{name} file is empty")
    return value


def connection_args() -> dict:
    return dict(host=os.getenv("PGHOST", "db"), port=int(os.getenv("PGPORT", "5432")),
                user=os.getenv("PGUSER", "hub"), dbname=os.getenv("PGDATABASE", "aihub"),
                password=read_secret("POSTGRES_PASSWORD"), connect_timeout=5)


def migration_url() -> URL:
    args = connection_args()
    return URL.create("postgresql+psycopg", username=args["user"], password=args["password"],
                      host=args["host"], port=args["port"], database=args["dbname"])


def connect():
    return psycopg.connect(**connection_args(), row_factory=dict_row)
