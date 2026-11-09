import os
from uuid import uuid4

import pytest
import psycopg
from psycopg import sql
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from app.db import connection_args, read_secret
from app.main import app


@pytest.fixture(scope="session", autouse=True)
def test_database():
    # Only the randomly named test database is migrated or removed.
    name = "test_hub_" + uuid4().hex
    args = connection_args() | {"dbname":"postgres"}
    with psycopg.connect(**args, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        previous = os.environ.get("PGDATABASE")
        os.environ["PGDATABASE"] = name
        try:
            command.upgrade(Config("alembic.ini"), "head")
            command.upgrade(Config("alembic.ini"), "head")
            yield
        finally:
            if previous is None:
                os.environ.pop("PGDATABASE", None)
            else:
                os.environ["PGDATABASE"] = previous
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


@pytest.fixture
def client():
    with TestClient(app, headers={"Origin":os.environ["PUBLIC_BASE_URL"]}) as client:
        assert client.post("/v1/auth/login", json={"password":read_secret("OWNER_PASSWORD")}).status_code == 204
        yield client


@pytest.fixture
def thread(client):
    p = client.post("/v1/projects", json={"name":"Test project"}).json()
    return client.post("/v1/conversations", json={"project_id":p["project_id"], "title":"Initial discussion"}).json()
