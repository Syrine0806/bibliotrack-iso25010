"""Coexistence avec un système tiers : API publique Open Library (recherche par ISBN).

Fiabilité : délai d'attente borné, aucune exception propagée — en cas de panne du
service tiers, l'application continue de fonctionner (saisie manuelle).
"""

import logging
import re

import httpx

from app.core.config import get_settings
from app.domain.isbn import to_isbn13
from app.schemas import IsbnLookupOut

log = logging.getLogger("biblio.openlibrary")


def _year(raw: str | None) -> int | None:
    match = re.search(r"\b(1[4-9]\d\d|20\d\d)\b", raw or "")
    return int(match.group(1)) if match else None


def lookup_isbn(isbn: str, client: httpx.Client | None = None) -> IsbnLookupOut:
    settings = get_settings()
    canonical = to_isbn13(isbn)
    url = f"{settings.openlibrary_base_url}/api/books"
    params = {"bibkeys": f"ISBN:{canonical}", "format": "json", "jscmd": "data"}
    owns_client = client is None
    client = client or httpx.Client(timeout=settings.openlibrary_timeout_seconds)
    try:
        response = client.get(url, params=params)
        response.raise_for_status()
        data = response.json().get(f"ISBN:{canonical}")
    except (httpx.HTTPError, ValueError) as exc:
        log.warning("Open Library indisponible (%s) : repli sur saisie manuelle", exc)
        return IsbnLookupOut(
            isbn=canonical,
            found=False,
            source="fallback",
            message="Service Open Library indisponible : saisie manuelle requise.",
        )
    finally:
        if owns_client:
            client.close()
    if not data:
        return IsbnLookupOut(
            isbn=canonical,
            found=False,
            source="openlibrary",
            message="ISBN inconnu d'Open Library.",
        )
    publishers = data.get("publishers") or [{}]
    return IsbnLookupOut(
        isbn=canonical,
        found=True,
        source="openlibrary",
        title=data.get("title"),
        publisher=publishers[0].get("name"),
        publication_year=_year(data.get("publish_date")),
        authors=[a.get("name", "") for a in data.get("authors", []) if a.get("name")],
    )
