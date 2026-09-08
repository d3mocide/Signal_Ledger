import hashlib
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import HTTPException, Request
from sqlalchemy import select
from .models import LoginSession, User

ROLE_ORDER = {"viewer": 1, "auditor": 2, "analyst": 3, "admin": 4}
ROLES = set(ROLE_ORDER)
SESSION_COOKIE = "signal_ledger_session"
hasher = PasswordHasher()

@dataclass(frozen=True)
class Principal:
    user_id: int
    actor: str
    role: str

def password_hash(password: str) -> str:
    return hasher.hash(password)

def password_valid(password: str, encoded: str) -> bool:
    try:
        return hasher.verify(encoded, password)
    except VerifyMismatchError:
        return False

def session_token() -> str:
    return secrets.token_urlsafe(32)

def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()

def expires_at() -> datetime:
    return datetime.utcnow() + timedelta(days=int(os.getenv("SESSION_DAYS", "7")))

def authenticate(request: Request) -> Principal:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(401, "Sign in required")
    db = request.state.db
    session = db.scalar(select(LoginSession).where(LoginSession.token_hash == token_hash(token), LoginSession.expires_at > datetime.utcnow()))
    if not session:
        raise HTTPException(401, "Session expired; sign in again")
    user = db.get(User, session.user_id)
    if not user or user.disabled:
        raise HTTPException(403, "User account is disabled")
    return Principal(user_id=user.id, actor=user.username, role=user.role)
