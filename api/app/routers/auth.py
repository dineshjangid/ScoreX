from __future__ import annotations

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy import select

from ..auth import (
    SESSION_COOKIE_NAME,
    VALID_ROLES,
    AuthUser,
    create_session,
    delete_session,
    get_current_user,
    hash_password,
    new_user_id,
    verify_password,
)
from ..db import UserRecord, get_session, now_iso

router = APIRouter(prefix="/api/auth", tags=["auth"])


class RegisterIn(BaseModel):
    username: str
    password: str
    role: str


class LoginIn(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    id: str
    username: str
    role: str


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 24 * 14,
        path="/",
    )


@router.post("/register", response_model=UserOut)
def register(body: RegisterIn, response: Response) -> UserOut:
    username = body.username.strip()
    if not username or len(body.password) < 6:
        raise HTTPException(status_code=400, detail="Username is required and password must be at least 6 characters")
    if body.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"role must be one of {sorted(VALID_ROLES)}")

    with get_session() as session:
        existing = session.execute(select(UserRecord).where(UserRecord.username == username)).scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=400, detail="Username is already taken")

        user = UserRecord(
            id=new_user_id(),
            username=username,
            password_hash=hash_password(body.password),
            role=body.role,
            created_at=now_iso(),
        )
        session.add(user)
        session.commit()
        user_id, user_role = user.id, user.role

    token, _ = create_session(user_id)
    _set_session_cookie(response, token)
    return UserOut(id=user_id, username=username, role=user_role)


@router.post("/login", response_model=UserOut)
def login(body: LoginIn, response: Response) -> UserOut:
    with get_session() as session:
        user = session.execute(
            select(UserRecord).where(UserRecord.username == body.username.strip())
        ).scalar_one_or_none()
        if not user or not verify_password(body.password, user.password_hash):
            raise HTTPException(status_code=401, detail="Invalid username or password")
        user_id, username, role = user.id, user.username, user.role

    token, _ = create_session(user_id)
    _set_session_cookie(response, token)
    return UserOut(id=user_id, username=username, role=role)


@router.post("/logout")
def logout(response: Response, session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME)) -> dict:
    if session_token:
        delete_session(session_token)
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")
    return {"status": "ok"}


@router.get("/me", response_model=UserOut)
def me(current_user: AuthUser = Depends(get_current_user)) -> UserOut:
    return UserOut(id=current_user.id, username=current_user.username, role=current_user.role)
