from sqlmodel import SQLModel, create_engine, Session
from dotenv import load_dotenv
from sqlalchemy import text
import os

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL is not set in .env file")

engine = create_engine(DATABASE_URL,
    pool_pre_ping=True,
    connect_args={"check_same_thread":False} if "sqlite" in DATABASE_URL else {})


def _run_migrations():
    """
    Idempotent schema migrations — runs on every startup.
    Safe to add new columns here; IF NOT EXISTS means no-op on existing DBs.
    Add a new line here whenever a column is added to a model after initial deployment
    instead of running manual ALTER TABLE commands.
    """
    migrations = [
        # 2026-03-28: added data_issues to SimulationJob
        "ALTER TABLE simulation_job ADD COLUMN IF NOT EXISTS data_issues TEXT",
        # 2026-03-28: added seed to SimulationJob for reproducible runs
        "ALTER TABLE simulation_job ADD COLUMN IF NOT EXISTS seed INTEGER",
        # 2026-04-04: added policy_config to link exact params to results
        "ALTER TABLE simulation_job ADD COLUMN IF NOT EXISTS policy_config TEXT",
        # 2026-04-04: added executive_summary for future CEO reasoning output
        "ALTER TABLE simulation_job ADD COLUMN IF NOT EXISTS executive_summary TEXT",
        # 2026-04-05: added policy_log_id to link job to LLM generation log
        "ALTER TABLE simulation_job ADD COLUMN IF NOT EXISTS policy_log_id TEXT",
    ]
    with engine.connect() as conn:
        for stmt in migrations:
            conn.execute(text(stmt))
        conn.commit()


def init_db():
    SQLModel.metadata.create_all(engine)
    _run_migrations()
    # Restore any ML artifacts that are missing from disk but present in the DB.
    # This makes the DB the source of truth and disk a local cache.
    from backend.storage.storage import restore_artifacts_from_db
    restore_artifacts_from_db()


def get_session():
    with Session(engine) as session:
        yield session
