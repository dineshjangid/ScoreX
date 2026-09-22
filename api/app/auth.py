"""Lightweight auth for a shared internal team workspace: username +
password with hashed passwords and server-side sessions delivered via an
HttpOnly cookie. No password reset/email verification/lockout — this is
proportionate for a trusted internal tool, not a public-facing service.

Every registered user can see and edit every project (shared
workspace); role is purely an attribution label recorded on audit log
entries, not an access restriction.
"""
from __future__ import annotations

import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import Cookie, HTTPException, status

from .db import SessionRecord, UserRecord, get_session, now_iso

SESSION_COOKIE_NAME = "session_token"
SESSION_LIFETIME = timedelta(days=14)
VALID_ROLES = {"analyst", "validator", "approver"}


@dataclass
class AuthUser:
    id: str
    username: str
    role: str


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def create_session(user_id: str) -> tuple[str, str]:
    """Create a session row, returning (token, expires_at_iso)."""
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + SESSION_LIFETIME
    with get_session() as session:
        session.add(
            SessionRecord(
                token=token,
                user_id=user_id,
                created_at=now_iso(),
                expires_at=expires_at.isoformat(),
            )
        )
        session.commit()
    return token, expires_at.isoformat()


def delete_session(token: str) -> None:
    with get_session() as session:
        record = session.get(SessionRecord, token)
        if record:
            session.delete(record)
            session.commit()


def new_user_id() -> str:
    return str(uuid.uuid4())


def get_current_user(session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME)) -> AuthUser:
    if not session_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    with get_session() as session:
        session_record = session.get(SessionRecord, session_token)
        if session_record is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired or invalid")

        expires_at = datetime.fromisoformat(session_record.expires_at)
        if expires_at < datetime.now(timezone.utc):
            session.delete(session_record)
            session.commit()
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")

        user = session.get(UserRecord, session_record.user_id)
        if user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

        return AuthUser(id=user.id, username=user.username, role=user.role)
