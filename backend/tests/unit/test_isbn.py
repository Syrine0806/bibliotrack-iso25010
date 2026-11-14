import pytest

from app.domain.isbn import is_valid_isbn, normalize_isbn, to_isbn13

pytestmark = pytest.mark.req("RG-01")


@pytest.mark.parametrize(
    "isbn",
    [
        "9782070368228",
        "978-2-07-036822-8",
        "207036822X",
        "0-306-40615-2",
        "080442957X",
        "9791032305690",
    ],
)
def test_isbn_valides(isbn):
    assert is_valid_isbn(isbn)


@pytest.mark.parametrize(
    "isbn",
    ["9782070368229", "2070368229", "123", "", "abcdefghij", "9772070368228", "97820703682281"],
)
def test_isbn_invalides(isbn):
    assert not is_valid_isbn(isbn)


def test_normalisation_supprime_separateurs_et_met_en_majuscule():
    assert normalize_isbn(" 080-442-957x ") == "080442957X"


def test_conversion_isbn10_vers_isbn13():
    assert to_isbn13("207036822X") == "9782070368228"
    assert to_isbn13("978-2-07-036822-8") == "9782070368228"


def test_conversion_refuse_isbn_invalide():
    with pytest.raises(ValueError):
        to_isbn13("2070368229")
