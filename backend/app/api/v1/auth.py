import re
import secrets
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.core.config import settings
from app.core.db import get_db
from app.core.deps import Principal, get_principal, require_role
from app.core.errors import AppError
from app.core.redis_client import r
from app.core.roles import ROLE_RANK, ROLES
from app.core.security import create_access_token, hash_password, verify_password
from app.models import Membership, Organization, User
from app.schemas import ForgotIn, InviteIn, LoginIn, OrgCreateIn, RegisterIn, ResetIn, SwitchOrgIn
from app.services.audit import audit
from app.services.bootstrap import seed_org_defaults

router = APIRouter(prefix="/auth", tags=["auth"])


def _slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:60] + "-" + secrets.token_hex(3)


def _token_out(user, org, role):
    return {**create_access_token(user.id, org.id),
            "user": {"id": user.id, "email": user.email, "full_name": user.full_name},
            "org": {"id": org.id, "name": org.name}, "role": role}


@router.post("/register")
def register(body: RegisterIn, db=Depends(get_db)):
    if db.scalar(select(User).where(User.email == body.email.lower())):
        raise AppError(409, "email_taken", "Email already registered")
    user = User(email=body.email.lower(), full_name=body.full_name, password_hash=hash_password(body.password))
    org = Organization(name=body.org_name, slug=_slug(body.org_name), settings={})
    db.add_all([user, org])
    db.flush()
    db.add(Membership(org_id=org.id, user_id=user.id, role="owner"))
    seed_org_defaults(db, org.id)
    audit(db, org.id, user.id, "org.created", "organization", org.id)
    db.commit()
    return _token_out(user, org, "owner")


@router.post("/login")
def login(body: LoginIn, db=Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if not user or not user.is_active or not verify_password(user.password_hash, body.password):
        raise AppError(401, "bad_credentials", "Invalid email or password")
    q = select(Membership, Organization).join(Organization, Organization.id == Membership.org_id) \
        .where(Membership.user_id == user.id)
    if body.org_id:
        q = q.where(Membership.org_id == body.org_id)
    row = db.execute(q.order_by(Membership.created_at)).first()
    if not row:
        raise AppError(403, "no_org", "No organization membership")
    audit(db, row[1].id, user.id, "auth.login", "user", user.id)
    db.commit()
    return _token_out(user, row[1], row[0].role)


@router.post("/logout")
def logout(p: Principal = Depends(get_principal)):
    r.setex(f"revoked:{p.jti}", settings.access_token_minutes * 60 + 60, "1")
    return {"ok": True}


@router.get("/me")
def me(p: Principal = Depends(get_principal), db=Depends(get_db)):
    user = db.get(User, p.user_id)
    orgs = db.execute(select(Organization.id, Organization.name, Membership.role)
                      .join(Membership, Membership.org_id == Organization.id)
                      .where(Membership.user_id == p.user_id)).all()
    return {"user": {"id": user.id, "email": user.email, "full_name": user.full_name},
            "org_id": p.org_id, "role": p.role,
            "organizations": [{"id": o.id, "name": o.name, "role": o.role} for o in orgs]}


@router.post("/orgs")
def create_org(body: OrgCreateIn, p: Principal = Depends(get_principal), db=Depends(get_db)):
    org = Organization(name=body.name, slug=_slug(body.name), settings={})
    db.add(org)
    db.flush()
    db.add(Membership(org_id=org.id, user_id=p.user_id, role="owner"))
    seed_org_defaults(db, org.id)
    audit(db, org.id, p.user_id, "org.created", "organization", org.id)
    db.commit()
    return _token_out(db.get(User, p.user_id), org, "owner")


@router.post("/switch-org")
def switch_org(body: SwitchOrgIn, p: Principal = Depends(get_principal), db=Depends(get_db)):
    m = db.scalar(select(Membership).where(Membership.user_id == p.user_id, Membership.org_id == body.org_id))
    if not m:
        raise AppError(403, "forbidden", "Not a member of that organization")
    return _token_out(db.get(User, p.user_id), db.get(Organization, body.org_id), m.role)


@router.post("/invite")
def invite(body: InviteIn, p: Principal = Depends(require_role("admin")), db=Depends(get_db)):
    if body.role not in ROLES or ROLE_RANK[body.role] > ROLE_RANK[p.role] or (body.role == "owner" and p.role != "owner"):
        raise AppError(403, "forbidden", "Cannot grant that role")
    user, temp = db.scalar(select(User).where(User.email == body.email.lower())), None
    if not user:
        temp = secrets.token_urlsafe(9)  # dev: returned; prod: email an invite link instead
        user = User(email=body.email.lower(), full_name=body.full_name, password_hash=hash_password(temp))
        db.add(user)
        db.flush()
    if db.scalar(select(Membership).where(Membership.org_id == p.org_id, Membership.user_id == user.id)):
        raise AppError(409, "already_member", "User already in organization")
    db.add(Membership(org_id=p.org_id, user_id=user.id, role=body.role))
    audit(db, p.org_id, p.user_id, "member.invited", "user", user.id, details={"role": body.role})
    db.commit()
    return {"user_id": user.id, "email": user.email, "role": body.role, "temporary_password": temp}


@router.post("/forgot-password", status_code=202)
def forgot(body: ForgotIn, db=Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if user:
        tok = secrets.token_urlsafe(24)
        r.setex(f"pwreset:{tok}", 3600, str(user.id))
        import logging
        logging.getLogger(__name__).info("DEV password reset token for %s: %s", user.email, tok)  # email it in prod
    return {"ok": True}  # same response whether or not the account exists


@router.post("/reset-password")
def reset(body: ResetIn, db=Depends(get_db)):
    uid = r.get(f"pwreset:{body.token}")
    if not uid:
        raise AppError(400, "invalid_token", "Reset token invalid or expired")
    user = db.get(User, uuid.UUID(uid))
    user.password_hash = hash_password(body.new_password)
    r.delete(f"pwreset:{body.token}")
    db.commit()
    return {"ok": True}
