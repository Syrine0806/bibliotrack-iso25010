"""RG-01 : validation des ISBN-10 / ISBN-13 (clé de contrôle)."""

import re

_SEPARATORS = re.compile(r"[\s-]")


def normalize_isbn(raw: str) -> str:
    return _SEPARATORS.sub("", raw or "").upper()


def _valid_isbn10(isbn: str) -> bool:
    if not re.fullmatch(r"\d{9}[\dX]", isbn):
        return False
    total = sum((10 - i) * (10 if c == "X" else int(c)) for i, c in enumerate(isbn))
    return total % 11 == 0


def _valid_isbn13(isbn: str) -> bool:
    if not re.fullmatch(r"97[89]\d{10}", isbn):
        return False
    total = sum(int(c) * (1 if i % 2 == 0 else 3) for i, c in enumerate(isbn[:12]))
    return (10 - total % 10) % 10 == int(isbn[12])


def is_valid_isbn(raw: str) -> bool:
    isbn = normalize_isbn(raw)
    if len(isbn) == 10:
        return _valid_isbn10(isbn)
    if len(isbn) == 13:
        return _valid_isbn13(isbn)
    return False


def to_isbn13(raw: str) -> str:
    """Convertit un ISBN valide en ISBN-13 canonique (forme stockée en base)."""
    isbn = normalize_isbn(raw)
    if not is_valid_isbn(isbn):
        raise ValueError(f"ISBN invalide : {raw!r}")
    if len(isbn) == 13:
        return isbn
    core = "978" + isbn[:9]
    total = sum(int(c) * (1 if i % 2 == 0 else 3) for i, c in enumerate(core))
    return core + str((10 - total % 10) % 10)
