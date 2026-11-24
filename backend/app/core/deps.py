import time
import uuid
from dataclasses import dataclass

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.core.errors import AppError
from app.core.redis_client import r
from app.core.roles import ROLE_RANK
from app.core.security import decode_token
from app.models import Membership, User

bearer = HTTPBearer(auto_error=False)


@dataclass
class Principal:
    user_id: uuid.UUID
    org_id: uuid.UUID
    role: str
    jti: str
    email: str


def rate_limit(request: Request):
    ident = request.client.host if request.client else "anon"
    key = f"rl:{ident}:{int(time.time() // 60)}"
    try:
        n = r.incr(key)
        if n == 1:
            r.expire(key, 70)
    except Exception:
        return  # fail-open if redis is down
    if n > settings.rate_limit_per_minute:
        raise AppError(429, "rate_limited", "Too many requests")


def principal_from_token(token: str, db: Session) -> Principal:
    claims = decode_token(token)
    try:
        if r.exists(f"revoked:{claims['jti']}"):
            raise AppError(401, "revoked", "Token revoked")
    except AppError:
        raise
    except Exception:
        pass
    row = db.execute(
        select(Membership.role, User.email, User.is_active)
        .join(User, User.id == Membership.user_id)
        .where(Membership.user_id == uuid.UUID(claims["sub"]), Membership.org_id == uuid.UUID(claims["org"]))
    ).first()
    if not row or not row.is_active:
        raise AppError(401, "invalid_token", "Membership no longer valid")
    # role is read from DB on every request, so role changes apply immediately
    return Principal(uuid.UUID(claims["sub"]), uuid.UUID(claims["org"]), row.role, claims["jti"], row.email)


def get_principal(creds: HTTPAuthorizationCredentials = Depends(bearer), db: Session = Depends(get_db)) -> Principal:
    if not creds:
        raise AppError(401, "unauthenticated", "Missing bearer token")
    return principal_from_token(creds.credentials, db)


def require_role(min_role: str):
    def dep(p: Principal = Depends(get_principal)) -> Principal:
        if ROLE_RANK[p.role] < ROLE_RANK[min_role]:
            raise AppError(403, "forbidden", f"Requires {min_role} role")
        return p
    return dep
