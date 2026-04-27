import os
from unittest.mock import patch

import pytest

# Set environment variables for testing before any backend imports
os.environ["DATABASE_URL"] = "sqlite:///./test.db"
os.environ["ENVIRONMENT"] = "test"

# Mock out any legacy background task imports if they still exist or try to run

from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with patch("backend.main.init_db"):
        from backend.main import app

        with TestClient(app) as client:
            yield client


@pytest.fixture(autouse=True)
def setup_db():
    from backend.db.database import SQLModel, engine

    with patch("backend.db.database._run_migrations"):
        SQLModel.metadata.create_all(engine)
        yield
        SQLModel.metadata.drop_all(engine)
