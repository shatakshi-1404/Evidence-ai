from datetime import datetime, timedelta, timezone

import jwt

from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_hash_is_not_plaintext_and_verifies():
    hashed = hash_password("my-secret-password")
    assert hashed != "my-secret-password"
    assert hashed.startswith("$argon2")
    assert verify_password("my-secret-password", hashed)


def test_wrong_password_fails():
    hashed = hash_password("my-secret-password")
    assert not verify_password("another-password", hashed)


def test_same_password_gives_different_hashes():
    assert hash_password("same-password") != hash_password("same-password")


def test_garbage_hash_returns_false():
    assert not verify_password("anything", "this-is-not-a-hash")


def test_token_round_trip():
    token = create_access_token("user-123")
    assert decode_access_token(token) == "user-123"


def test_expired_token_is_rejected():
    token = create_access_token("user-123", expires_minutes=-1)
    assert decode_access_token(token) is None


def test_token_signed_with_wrong_key_is_rejected():
    forged = jwt.encode(
        {"sub": "user-123", "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
        "a-completely-different-secret-key-0123456789",
        algorithm="HS256",
    )
    assert decode_access_token(forged) is None


def test_garbage_token_is_rejected():
    assert decode_access_token("not.a.token") is None
