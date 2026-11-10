"""Primitives de sécurité : hachage bcrypt, jetons JWT, politique de mot de passe."""

import re
from datetime import timedelta

import bcrypt
import jwt

from app.core import clock
from app.core.config import get_settings

PASSWORD_POLICY = re.compile(r"^(?=.*[A-Za-z])(?=.*\d).{8,}$")
BCRYPT_MAX_BYTES = 72  # limite de l'algorithme bcrypt (au-delà : ValueError)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(
        password.encode("utf-8"), bcrypt.gensalt(rounds=get_settings().bcrypt_rounds)
    ).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


def password_is_strong(password: str) -> bool:
    """≥ 8 caractères, au moins une lettre et un chiffre, ≤ 72 octets UTF-8 (limite bcrypt)."""
    return (
        bool(PASSWORD_POLICY.match(password)) and len(password.encode("utf-8")) <= BCRYPT_MAX_BYTES
    )


def create_access_token(subject: str, role: str) -> str:
    settings = get_settings()
    issued = clock.now()
    payload = {
        "sub": subject,
        "role": role,
        "iat": int(issued.timestamp()),
        "exp": int((issued + timedelta(minutes=settings.access_token_minutes)).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    """Lève jwt.PyJWTError si le jeton est invalide, altéré ou expiré."""
    settings = get_settings()
    payload = jwt.decode(
        token,
        settings.jwt_secret,
        algorithms=[settings.jwt_algorithm],
        # exp/iat sont vérifiés ci-dessous avec l'horloge applicative (testable).
        options={
            "require": ["sub", "exp", "iat", "role"],
            "verify_exp": False,
            "verify_iat": False,
        },
    )
    now = int(clock.now().timestamp())
    if payload["exp"] <= now:
        raise jwt.ExpiredSignatureError("Signature has expired")
    if payload["iat"] > now + 30:  # 30 s de tolérance de dérive d'horloge
        raise jwt.ImmatureSignatureError("Token issued in the future")
    return payload
