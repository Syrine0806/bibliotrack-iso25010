"""Horloge injectable : permet de tester les règles temporelles (retards, expirations)."""

from datetime import UTC, date, datetime

_frozen: datetime | None = None


def now() -> datetime:
    """Instant courant en UTC (naïf, stocké tel quel en base)."""
    if _frozen is not None:
        return _frozen
    return datetime.now(UTC).replace(tzinfo=None)


def today() -> date:
    return now().date()


def freeze(at: datetime | None) -> None:
    """Fige l'horloge (tests uniquement). `None` rétablit l'horloge réelle."""
    global _frozen
    _frozen = at
