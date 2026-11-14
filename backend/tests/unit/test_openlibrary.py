"""Intégration tierce Open Library : contrat de réponse et repli en cas de panne (respx)."""

import httpx
import pytest
import respx

from app.integrations.openlibrary import lookup_isbn

URL = "https://openlibrary.test/api/books"
ISBN = "9782070368228"
PAYLOAD = {
    f"ISBN:{ISBN}": {
        "title": "L'Étranger",
        "publishers": [{"name": "Gallimard"}],
        "publish_date": "Mar 1972",
        "authors": [{"name": "Albert Camus"}],
    }
}


@pytest.mark.req("EF-14", "EQ-COMP-02")
@respx.mock
def test_isbn_trouve_est_mappe():
    route = respx.get(URL).mock(return_value=httpx.Response(200, json=PAYLOAD))
    result = lookup_isbn("207036822X")  # ISBN-10 converti en ISBN-13 avant l'appel
    assert route.called
    assert route.calls.last.request.url.params["bibkeys"] == f"ISBN:{ISBN}"
    assert result.found and result.source == "openlibrary"
    assert result.title == "L'Étranger" and result.publisher == "Gallimard"
    assert result.publication_year == 1972 and result.authors == ["Albert Camus"]


@pytest.mark.req("EF-14")
@respx.mock
def test_isbn_inconnu():
    respx.get(URL).mock(return_value=httpx.Response(200, json={}))
    result = lookup_isbn(ISBN)
    assert not result.found and result.source == "openlibrary"


@pytest.mark.req("EQ-FIA-04", "EQ-COMP-02")
@respx.mock
@pytest.mark.parametrize(
    "failure",
    [httpx.ConnectTimeout("timeout"), httpx.ConnectError("dns"), httpx.ReadTimeout("slow")],
)
def test_panne_reseau_repli_sans_exception(failure):
    respx.get(URL).mock(side_effect=failure)
    result = lookup_isbn(ISBN)
    assert result.found is False and result.source == "fallback"
    assert "indisponible" in result.message


@pytest.mark.req("EQ-FIA-04")
@respx.mock
@pytest.mark.parametrize("status", [500, 502, 503, 429])
def test_erreur_http_tiers_repli(status):
    respx.get(URL).mock(return_value=httpx.Response(status))
    assert lookup_isbn(ISBN).source == "fallback"


@pytest.mark.req("EQ-FIA-04")
@respx.mock
def test_reponse_non_json_repli():
    respx.get(URL).mock(return_value=httpx.Response(200, text="<html>maintenance</html>"))
    assert lookup_isbn(ISBN).source == "fallback"
