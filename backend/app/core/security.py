import base64
import hashlib
import time
import uuid

import jwt
from argon2 import PasswordHasher
from cryptography.fernet import Fernet

from app.core.config import settings
from app.core.errors import AppError

_ph = PasswordHasher()
_fernet = Fernet(base64.urlsafe_b64encode(hashlib.sha256(settings.jwt_secret.encode()).digest()))


def hash_password(p: str) -> str:
    return _ph.hash(p)


def verify_password(h: str, p: str) -> bool:
    try:
        return _ph.verify(h, p)
    except Exception:
        return False


def create_access_token(user_id, org_id) -> dict:
    jti = uuid.uuid4().hex
    exp = int(time.time()) + settings.access_token_minutes * 60
    token = jwt.encode({"sub": str(user_id), "org": str(org_id), "jti": jti, "exp": exp},
                       settings.jwt_secret, algorithm=settings.jwt_alg)
    return {"access_token": token, "token_type": "bearer", "expires_in": settings.access_token_minutes * 60}


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_alg])
    except jwt.PyJWTError:
        raise AppError(401, "invalid_token", "Invalid or expired token")


def encrypt_secret(s: str) -> str:
    return _fernet.encrypt(s.encode()).decode()


def decrypt_secret(s: str) -> str:
    return _fernet.decrypt(s.encode()).decode()
