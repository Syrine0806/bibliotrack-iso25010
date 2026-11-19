"""Reprise au démarrage : le conteneur attend la base au lieu d'échouer (EQ-FIA-06)."""

import pytest
from sqlalchemy.exc import OperationalError

from app import prestart


class FlakyEngine:
    """Moteur simulé : indisponible pendant `failures` tentatives, puis joignable."""

    def __init__(self, failures: int) -> None:
        self.failures = failures
        self.calls = 0

    def connect(self):
        self.calls += 1
        if self.calls <= self.failures:
            raise OperationalError("SELECT 1", {}, Exception("connection refused"))
        return _Conn()


class _Conn:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, _stmt):
        return None


@pytest.mark.req("EQ-FIA-06", "EQ-POR-01")
def test_attend_la_base_puis_reussit(monkeypatch):
    engine = FlakyEngine(failures=3)
    monkeypatch.setattr(prestart, "engine", engine)
    monkeypatch.setattr(prestart.time, "sleep", lambda _s: None)
    prestart.wait_for_database(attempts=10)
    assert engine.calls == 4


@pytest.mark.req("EQ-FIA-06")
def test_abandon_propre_si_base_definitivement_absente(monkeypatch):
    engine = FlakyEngine(failures=99)
    monkeypatch.setattr(prestart, "engine", engine)
    monkeypatch.setattr(prestart.time, "sleep", lambda _s: None)
    with pytest.raises(SystemExit) as exc:
        prestart.wait_for_database(attempts=5)
    assert exc.value.code == 1 and engine.calls == 5


@pytest.mark.req("EQ-POR-01")
def test_initialisation_idempotente(db):
    from app.main import init_database

    init_database()
    init_database()  # second démarrage : aucune erreur, aucun doublon
