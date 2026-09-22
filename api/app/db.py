"""SQLite persistence for Project state (local, single-user for now).

Swapping to Postgres for multi-user later means changing DATABASE_URL and
adding auth/ownership columns here — the engine package is untouched.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from sqlalchemy import Column, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DATA_DIR = os.environ.get("CREDITTOOL_DATA_DIR", os.path.expanduser("~/.credittool"))
os.makedirs(DATA_DIR, exist_ok=True)
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


def init_db() -> None:
    Base.metadata.create_all(engine)


def get_session() -> Session:
    return SessionLocal()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
