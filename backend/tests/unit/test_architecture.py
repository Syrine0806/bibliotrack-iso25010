"""Garde-fou d'architecture en couches (maintenabilité, EQ-MAI-04).

  api  →  services  →  domain
             ↓
           models / core
Le domaine reste pur (testable sans base ni framework web) ; les services ignorent HTTP.
"""

import ast
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[2] / "app"


def imports_of(package: str) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for file in (APP / package).rglob("*.py"):
        modules: set[str] = set()
        for node in ast.walk(ast.parse(file.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                modules |= {alias.name for alias in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules.add(node.module)
        result[str(file.relative_to(APP))] = modules
    return result


def violations(package: str, forbidden: tuple[str, ...]) -> list[str]:
    return [
        f"{file} importe {module}"
        for file, modules in imports_of(package).items()
        for module in modules
        if module.startswith(forbidden)
    ]


@pytest.mark.req("EQ-MAI-04")
def test_domaine_pur_sans_framework_ni_persistance():
    assert (
        violations(
            "domain", ("fastapi", "sqlalchemy", "app.services", "app.api", "app.models", "httpx")
        )
        == []
    )


@pytest.mark.req("EQ-MAI-04")
def test_services_independants_du_protocole_http():
    assert violations("services", ("fastapi", "starlette", "app.api")) == []


@pytest.mark.req("EQ-MAI-04")
def test_modeles_independants_des_couches_superieures():
    assert violations("models", ("app.services", "app.api", "fastapi")) == []


@pytest.mark.req("EQ-MAI-04")
def test_api_ne_contient_pas_de_sql():
    """Les routeurs délèguent aux services : pas de requêtes SQLAlchemy dans la couche API."""
    offenders = [
        f"{file} importe sqlalchemy.{{select|func|insert|update|delete}}"
        for file, modules in imports_of("api").items()
        if file != "api/admin.py"  # seule exception : `SELECT 1` de la sonde de santé
        and "sqlalchemy" in modules
    ]
    assert offenders == []
