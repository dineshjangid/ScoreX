"""SQLite persistence for Project state, plus users/sessions/audit log
for the shared-workspace multi-user model: every registered user can see
and edit every project; role is an attribution label on audit entries,
not an access restriction. Swapping to Postgres for a larger deployment
later means changing DATABASE_URL — the engine package is untouched.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DATA_DIR = os.environ.get("CREDITTOOL_DATA_DIR", os.path.expanduser("~/.credittool"))
UPLOADS_DIR = os.path.join(DATA_DIR, "uploads")
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(UPLOADS_DIR, exist_ok=True)
DATABASE_URL = f"sqlite:///{os.path.join(DATA_DIR, 'credittool.db')}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


class ProjectRecord(Base):
    __tablename__ = "projects"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    scorecard_type = Column(String, nullable=False)
    created_at = Column(String, nullable=False)
    updated_at = Column(String, nullable=False)
    # Serialized Project (step_status + artifacts) as JSON text.
    payload = Column(Text, nullable=False)
    # Path to the uploaded raw dataset for this project, once ingested.
    data_path = Column(String, nullable=True)
    # Path to the target/sample assignment (target + train/test/oot label
    # per row), once target definition + sampling have been run.
    splits_path = Column(String, nullable=True)
    # Path to the most recently uploaded batch-scoring file (applicants to
    # score with the finished scorecard, no target needed).
    batch_path = Column(String, nullable=True)


class ModelVersionRecord(Base):
    """A saved snapshot of one model build (binning through validation),
    for champion/challenger comparison across iterations. Independent of
    the project's current step_status/artifacts — saving a version never
    changes them, and re-running a step never touches saved versions.
    """

    __tablename__ = "model_versions"

    id = Column(String, primary_key=True)
    project_id = Column(String, nullable=False, index=True)
    version_number = Column(Integer, nullable=False)
    label = Column(String, nullable=True)
    is_champion = Column(Boolean, nullable=False, default=False)
    created_at = Column(String, nullable=False)
    # JSON: {target_definition, sampling, binning, variable_selection,
    # modeling, scaling, validation, ml_benchmark} as they were when saved.
    snapshot = Column(Text, nullable=False)


class UserRecord(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True)
    # For a local account, the chosen username; for an SSO account, the
    # IdP-asserted email (NameID) — either way, the unique login identity.
    username = Column(String, nullable=False, unique=True, index=True)
    # Null for SSO users, who never set a local password.
    password_hash = Column(String, nullable=True)
    role = Column(String, nullable=False)  # "analyst" | "validator" | "approver"
    created_at = Column(String, nullable=False)
    auth_source = Column(String, nullable=False, default="local")  # "local" | "saml"


class SessionRecord(Base):
    __tablename__ = "sessions"

    token = Column(String, primary_key=True)
    user_id = Column(String, nullable=False, index=True)
    created_at = Column(String, nullable=False)
    expires_at = Column(String, nullable=False)


class AuditLogRecord(Base):
    """One row per meaningful action for governance/audit purposes.
    Username/role are denormalized so history reads correctly even if a
    user is later renamed or their role changes.
    """

    __tablename__ = "audit_log"

    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False)
    username = Column(String, nullable=False)
    role = Column(String, nullable=False)
    project_id = Column(String, nullable=True, index=True)
    action = Column(String, nullable=False)
    detail = Column(String, nullable=True)
    created_at = Column(String, nullable=False, index=True)


def _add_missing_columns() -> None:
    """Best-effort dev-time migration: add any columns a model has that
    don't exist yet on an already-created table. Adequate for a local
    single-user SQLite file; swap for Alembic if/when this moves to
    Postgres for multi-user.
    """
    with engine.connect() as conn:
        for table in (ProjectRecord.__table__, UserRecord.__table__):
            existing = {row[1] for row in conn.exec_driver_sql(f"PRAGMA table_info({table.name})").fetchall()}
            for column in table.columns:
                if column.name not in existing:
                    default = "" if column.default is None else f" DEFAULT '{column.default.arg}'"
                    conn.exec_driver_sql(f"ALTER TABLE {table.name} ADD COLUMN {column.name} {column.type}{default}")
        conn.commit()


def init_db() -> None:
    Base.metadata.create_all(engine)
    _add_missing_columns()


def get_session() -> Session:
    return SessionLocal()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
