from datetime import datetime, timedelta

import jwt
import pytest

from app.core import clock
from app.core.config import get_settings
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    password_is_strong,
    verify_password,
)


@pytest.mark.req("EQ-SEC-01")
def test_mot_de_passe_hache_avec_sel_et_verifiable():
    h1, h2 = hash_password("Secret123"), hash_password("Secret123")
    assert h1 != h2 and h1.startswith("$2b$")
    assert "Secret123" not in h1
    assert verify_password("Secret123", h1)
    assert not verify_password("secret123", h1)


@pytest.mark.req("EQ-SEC-01")
def test_hash_corrompu_ne_leve_pas_d_exception():
    assert verify_password("x", "pas-un-hash-bcrypt") is False


@pytest.mark.req("EQ-SEC-01")
@pytest.mark.parametrize(
    ("password", "ok"),
    [
        ("Password1", True),
        ("abcdefg1", True),
        ("short1", False),
        ("onlyletters", False),
        ("12345678", False),
        ("", False),
    ],
)
def test_politique_de_mot_de_passe(password, ok):
    assert password_is_strong(password) is ok


@pytest.mark.req("EQ-SEC-02")
def test_jeton_valide_decode():
    payload = decode_access_token(create_access_token("42", "ADMIN"))
    assert payload["sub"] == "42" and payload["role"] == "ADMIN"


@pytest.mark.req("EQ-SEC-02")
def test_jeton_altere_rejete():
    token = create_access_token("42", "ADHERENT")
    header, payload, signature = token.split(".")
    forged = jwt.encode({"sub": "42", "role": "ADMIN", "exp": 9999999999}, "autre-secret-" * 4)
    with pytest.raises(jwt.PyJWTError):
        decode_access_token(forged)
    with pytest.raises(jwt.PyJWTError):
        decode_access_token(f"{header}.{payload}.{signature[::-1]}")


@pytest.mark.req("EQ-SEC-02")
def test_jeton_alg_none_rejete():
    unsigned = jwt.encode({"sub": "1", "role": "ADMIN", "exp": 9999999999}, None, algorithm="none")
    with pytest.raises(jwt.PyJWTError):
        decode_access_token(unsigned)


@pytest.mark.req("EQ-SEC-02")
def test_jeton_expire_rejete():
    clock.freeze(datetime(2026, 1, 1, 12, 0))
    token = create_access_token("42", "ADMIN")
    clock.freeze(
        datetime(2026, 1, 1, 12, 0) + timedelta(minutes=get_settings().access_token_minutes)
    )
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(token)


@pytest.mark.req("EQ-SEC-02")
def test_jeton_emis_dans_le_futur_rejete():
    clock.freeze(datetime(2026, 1, 1, 12, 0))
    token = create_access_token("42", "ADMIN")
    clock.freeze(datetime(2026, 1, 1, 11, 0))
    with pytest.raises(jwt.ImmatureSignatureError):
        decode_access_token(token)


@pytest.mark.req("EQ-SEC-01")
def test_politique_limite_a_72_octets_utf8():
    assert password_is_strong("a1" * 36)  # 72 octets : accepté
    assert not password_is_strong("a1" * 36 + "b")  # 73 octets
    assert not password_is_strong("é1" * 25)  # 50 caractères mais 75 octets
