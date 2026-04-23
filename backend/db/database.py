import os

from dotenv import load_dotenv
from sqlalchemy import text
from sqlmodel import Session, SQLModel, create_engine

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL is not set in .env file")

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
)


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
        # 2026-04-23: Data Isolation columns
        "ALTER TABLE employee ADD COLUMN IF NOT EXISTS session_id VARCHAR DEFAULT 'global'",
        "ALTER TABLE simulation_job ADD COLUMN IF NOT EXISTS session_id VARCHAR DEFAULT 'global'",
        "ALTER TABLE orchestrate_job ADD COLUMN IF NOT EXISTS session_id VARCHAR DEFAULT 'global'",
        "ALTER TABLE policy_generation_log ADD COLUMN IF NOT EXISTS session_id VARCHAR DEFAULT 'global'",
        "ALTER TABLE ml_artifact ADD COLUMN IF NOT EXISTS session_id VARCHAR DEFAULT 'global'",
        # Drop old PK and add composite PK for ml_artifact
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'ml_artifact_pkey'
                AND pg_get_constraintdef(oid) NOT LIKE '%session_id%'
            ) THEN
                ALTER TABLE ml_artifact DROP CONSTRAINT ml_artifact_pkey;
                ALTER TABLE ml_artifact ADD PRIMARY KEY (name, session_id);
            END IF;
        END $$;
        """,
        # 2026-04-23: Drop sole employee_id PK and add composite (employee_id, session_id)
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'employee_pkey'
                AND pg_get_constraintdef(oid) NOT LIKE '%session_id%'
            ) THEN
                ALTER TABLE employee DROP CONSTRAINT employee_pkey;
                ALTER TABLE employee ADD PRIMARY KEY (employee_id, session_id);
            END IF;
        END $$;
        """,
    ]
    with engine.connect() as conn:
        for stmt in migrations:
            conn.execute(text(stmt))
        conn.commit()


def init_db():
    SQLModel.metadata.create_all(engine)
    _run_migrations()


def get_session():
    with Session(engine) as session:
        yield session
