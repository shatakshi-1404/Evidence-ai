from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.core.config import settings

_hasher = PasswordHasher()

# Verified against when a login uses an unknown email, so "unknown email" and
# "wrong password" take the same time and can't be told apart by timing.
DUMMY_HASH = _hasher.hash("not-a-real-password")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    try:
        return _hasher.verify(hashed_password, password)
    except (VerificationError, InvalidHashError):
        return False


def create_access_token(subject: str, expires_minutes: int | None = None) -> str:
    minutes = (
        settings.access_token_expire_minutes if expires_minutes is None else expires_minutes
    )
    now = datetime.now(timezone.utc)
    payload = {"sub": subject, "iat": now, "exp": now + timedelta(minutes=minutes)}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> str | None:
    """Return the user id inside a valid token, or None if invalid/expired/forged."""
    try:
        payload = jwt.decode(
            token, settings.secret_key, algorithms=[settings.jwt_algorithm]
        )
    except jwt.PyJWTError:
        return None
    subject = payload.get("sub")
    return subject if isinstance(subject, str) else None
