"""Password, access-token, refresh-token and CSRF cryptographic helpers."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.core.config import Settings

ACCESS_TOKEN_SECONDS = 15 * 60
REFRESH_TOKEN_SECONDS = 7 * 24 * 60 * 60
JWT_ALGORITHM = "HS256"
PASSWORD_HASHER = PasswordHasher()
_DUMMY_PASSWORD_HASH = PASSWORD_HASHER.hash(secrets.token_urlsafe(32))


class InvalidAccessToken(Exception):
    """Raised for any token that fails strict access-token validation."""


def hash_password(password: str) -> str:
    return PASSWORD_HASHER.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return PASSWORD_HASHER.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def password_hash_needs_rehash(password_hash: str) -> bool:
    try:
        return PASSWORD_HASHER.check_needs_rehash(password_hash)
    except InvalidHashError:
        return True


def dummy_password_hash() -> str:
    return _DUMMY_PASSWORD_HASH


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def create_access_token(account_id: UUID, family_id: UUID, settings: Settings) -> str:
    now = datetime.now(timezone.utc)
    claims = {
        "sub": str(account_id),
        "sid": str(family_id),
        "jti": str(uuid4()),
        "iss": settings.auth_issuer,
        "aud": settings.auth_audience,
        "iat": now,
        "exp": now + timedelta(seconds=ACCESS_TOKEN_SECONDS),
        "token_type": "access",
    }
    return jwt.encode(claims, settings.jwt_signing_key.get_secret_value(), algorithm=JWT_ALGORITHM)


def decode_access_token(token: str, settings: Settings) -> dict[str, object]:
    try:
        claims = jwt.decode(
            token,
            settings.jwt_signing_key.get_secret_value(),
            algorithms=[JWT_ALGORITHM],
            issuer=settings.auth_issuer,
            audience=settings.auth_audience,
            options={
                "require": ["sub", "sid", "jti", "iss", "aud", "iat", "exp", "token_type"],
                "verify_signature": True,
                "verify_exp": True,
                "verify_iss": True,
                "verify_aud": True,
                "verify_iat": True,
            },
        )
    except jwt.PyJWTError as exc:
        raise InvalidAccessToken from exc
    if claims.get("token_type") != "access":
        raise InvalidAccessToken
    try:
        UUID(str(claims["sub"]))
        UUID(str(claims["sid"]))
        UUID(str(claims["jti"]))
    except (KeyError, ValueError, TypeError) as exc:
        raise InvalidAccessToken from exc
    return claims


def new_csrf_token(binding: str, settings: Settings) -> str:
    nonce = secrets.token_urlsafe(32)
    signed_value = f"{binding}:{nonce}".encode("utf-8")
    signature = hmac.new(
        settings.csrf_signing_key.get_secret_value().encode("utf-8"), signed_value, hashlib.sha256
    ).hexdigest()
    return f"{nonce}.{signature}"


def verify_csrf_token(token: str, binding: str, settings: Settings) -> bool:
    try:
        nonce, supplied_signature = token.rsplit(".", 1)
    except ValueError:
        return False
    if not nonce or len(supplied_signature) != 64:
        return False
    signed_value = f"{binding}:{nonce}".encode("utf-8")
    expected_signature = hmac.new(
        settings.csrf_signing_key.get_secret_value().encode("utf-8"), signed_value, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(supplied_signature, expected_signature)


def current_csrf_binding(refresh_token: str | None, access_token: str | None, settings: Settings) -> str:
    if access_token:
        try:
            claims = jwt.decode(
                access_token,
                options={"verify_signature": False, "verify_exp": False, "verify_aud": False},
                algorithms=[JWT_ALGORITHM],
            )
            jti = claims.get("jti")
            if isinstance(jti, str):
                UUID(jti)
                return f"access:{jti}"
        except (jwt.PyJWTError, ValueError, TypeError):
            pass
    if refresh_token:
        return f"refresh:{hash_refresh_token(refresh_token)}"
    return "anonymous"


def valid_csrf_pair(cookie_token: str | None, header_token: str | None, binding: str, settings: Settings) -> bool:
    return bool(
        cookie_token
        and header_token
        and hmac.compare_digest(cookie_token, header_token)
        and verify_csrf_token(cookie_token, binding, settings)
    )
