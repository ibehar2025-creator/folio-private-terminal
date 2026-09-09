import hashlib
import secrets
from datetime import timedelta, timezone
from typing import Annotated
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select, delete, func
from sqlalchemy.orm import Session as DBSession
from .db import get_db
from .models import User, Session, LoginAttempt, now
from .config import get_settings

router = APIRouter(prefix="/api/auth", tags=["authentication"])
hasher = PasswordHasher()
DUMMY_HASH = hasher.hash(secrets.token_urlsafe(32))
DB = Annotated[DBSession, Depends(get_db)]


def digest(value: str):
    return hashlib.sha256(value.encode()).hexdigest()


def utc(value):
    return (
        value.replace(tzinfo=timezone.utc)
        if value.tzinfo is None
        else value.astimezone(timezone.utc)
    )


def session_for(request: Request, db: DBSession):
    token = request.cookies.get("folio_session", "")
    session = db.get(Session, digest(token)) if token else None
    if not session or utc(session.expires_at) <= now():
        raise HTTPException(401, "Please sign in to your private workspace")
    return session


def current_user(request: Request, db: DB):
    session = session_for(request, db)
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        if not secrets.compare_digest(
            request.headers.get("X-CSRF-Token", ""), session.csrf
        ):
            raise HTTPException(403, "Invalid CSRF token; refresh and try again")
    user = db.get(User, session.user_id)
    if not user:
        raise HTTPException(401, "Session no longer valid")
    return user


CurrentUser = Annotated[User, Depends(current_user)]


class Login(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=1024)


@router.post("/login")
def login(body: Login, request: Request, response: Response, db: DB):
    cutoff = now() - timedelta(minutes=15)
    ip_key = digest("ip:" + (request.client.host if request.client else "unknown"))
    name_key = digest("user:" + body.username.strip().lower())
    db.execute(delete(LoginAttempt).where(LoginAttempt.created_at < cutoff))
    for key, limit in [(ip_key, 20), (name_key, 8)]:
        if (
            db.scalar(
                select(func.count())
                .select_from(LoginAttempt)
                .where(LoginAttempt.key == key, LoginAttempt.created_at >= cutoff)
            )
            >= limit
        ):
            raise HTTPException(
                429, "Too many sign-in attempts. Try again in 15 minutes."
            )
    db.add_all([LoginAttempt(key=ip_key), LoginAttempt(key=name_key)])
    db.commit()
    user = db.scalar(select(User).where(User.username == body.username.strip().lower()))
    try:
        valid = hasher.verify(user.password_hash if user else DUMMY_HASH, body.password)
    except (VerifyMismatchError, InvalidHashError):
        valid = False
    if not user or not valid:
        raise HTTPException(401, "Incorrect username or password")
    old = request.cookies.get("folio_session")
    if old:
        db.execute(delete(Session).where(Session.token_hash == digest(old)))
    db.execute(delete(Session).where(Session.expires_at < now()))
    token, csrf = secrets.token_urlsafe(48), secrets.token_hex(32)
    lifetime = get_settings().session_hours * 3600
    db.add(
        Session(
            token_hash=digest(token),
            user_id=user.id,
            csrf=csrf,
            expires_at=now() + timedelta(seconds=lifetime),
        )
    )
    db.execute(delete(LoginAttempt).where(LoginAttempt.key == name_key))
    db.commit()
    response.set_cookie(
        "folio_session",
        token,
        httponly=True,
        secure=get_settings().secure_cookies,
        samesite="strict",
        max_age=lifetime,
        path="/",
    )
    return {"username": user.username, "csrf": csrf, "demo": get_settings().demo_mode}


@router.get("/me")
def me(request: Request, user: CurrentUser, db: DB):
    return {
        "username": user.username,
        "csrf": session_for(request, db).csrf,
        "demo": get_settings().demo_mode,
    }


@router.post("/logout")
def logout(request: Request, response: Response, user: CurrentUser, db: DB):
    db.execute(
        delete(Session).where(
            Session.token_hash == digest(request.cookies.get("folio_session", ""))
        )
    )
    db.commit()
    response.delete_cookie("folio_session", path="/")
    return {"ok": True}


class PasswordChange(BaseModel):
    current_password: str = Field(max_length=1024)
    new_password: str = Field(min_length=14, max_length=1024)


@router.post("/password")
def password_change(
    body: PasswordChange, user: CurrentUser, db: DB, response: Response
):
    try:
        hasher.verify(user.password_hash, body.current_password)
    except VerifyMismatchError:
        raise HTTPException(400, "Current password is incorrect")
    user.password_hash = hasher.hash(body.new_password)
    db.execute(delete(Session).where(Session.user_id == user.id))
    db.commit()
    response.delete_cookie("folio_session", path="/")
    return {"ok": True}
