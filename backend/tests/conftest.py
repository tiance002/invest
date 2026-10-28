import os
import uuid
from pathlib import Path

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from alembic import command
from app.infrastructure.config import Settings
from app.main import create_app
from app.orchestration.store import TaskStore


@pytest.fixture
def settings():
    return Settings(_env_file=None, model_timeout_seconds=0.2, lease_seconds=3)


@pytest.fixture
def sessions():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL to run real-PostgreSQL integration tests")
    if not url.startswith("postgresql"):
        pytest.fail("Integration tests require PostgreSQL; SQLite is not a verification substitute")
    schema = "arena_test_" + uuid.uuid4().hex
    admin = create_engine(url, connect_args={"connect_timeout": 3})
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(url, connect_args={"options": f"-csearch_path={schema}", "connect_timeout": 3})
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    try:
        with engine.begin() as connection:
            config.attributes["connection"] = connection
            config.attributes["schema"] = schema
            command.upgrade(config, "head")
        yield sessionmaker(engine, expire_on_commit=False)
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


class NoRedis:
    def __init__(self):
        self.calls = []

    def notify(self, task_id):
        self.calls.append(task_id)
        return False

    def healthy(self):
        return False


@pytest.fixture
def notifications():
    return NoRedis()


@pytest.fixture
def store(sessions, settings):
    return TaskStore(sessions, settings)


@pytest.fixture
def client(sessions, settings, notifications):
    with TestClient(create_app(settings, sessions, notifications)) as test_client:
        yield test_client


@pytest.fixture
def payload():
    return {
        "symbol": "600519",
        "market": "CN_A",
        "horizon_days": 3,
        "research_question": "验证模拟证据与反方质询流程",
        "scenario": "normal",
    }
