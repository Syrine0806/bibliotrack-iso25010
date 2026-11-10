# 📚 BiblioTrack — gestion de médiathèque conforme ISO/IEC 25010

Projet de qualité logicielle (ING5) : une application métier complète (backend, frontend, base de données),
conçue dès le départ pour répondre aux 8 caractéristiques de qualité de la norme **ISO/IEC 25010**, avec une
stratégie de test multicouche automatisée et une **matrice de traçabilité générée à partir des rapports d'exécution réels**.

| | |
|---|---|
| **Domaine** | Bibliothèque / médiathèque : catalogue, exemplaires, prêts, réservations, pénalités |
| **Stack** | FastAPI (Python 3.12) · SQLAlchemy 2 · PostgreSQL 16 · React 18 + TypeScript · nginx · Docker Compose |
| **Périmètre** | 3 rôles · 8 entités (relations 1-N et N-N) · 3 workflows à statuts · 12 règles métier · tableau de bord · recherche sur 5 000 ouvrages · journal d'audit · intégration Open Library |
| **Tests** | pytest · Vitest · Postman/Newman · Playwright (Chromium, Firefox, WebKit) · axe-core · Locust · Bandit · pip-audit · npm audit · OWASP ZAP · Radon · Ruff · ESLint · jscpd · chaos Docker · portabilité |

## Démarrage en une commande

```bash
docker compose up -d --build
```

Ouvrir http://localhost:8080 et se connecter avec `admin@bibliotrack.example` / `Admin1234`
(autres comptes : `biblio@bibliotrack.example` / `Biblio1234`, `adherent@bibliotrack.example` / `Adherent1234`). API documentée : http://localhost:8080/api/docs.

## Rejouer toute la campagne de tests

```bash
scripts/run_all_tests.sh --with-portability
```

Le script exécute chaque couche, archive les rapports dans [`reports/`](reports/) et régénère
la matrice de traçabilité.

## Équipe

| Membre | GitHub |
|---|---|
| Syrine Guesmi | [@Syrine0806](https://github.com/Syrine0806) |
| Hedi Zouaoui | [@zhedi55-stack](https://github.com/zhedi55-stack) |
| Ferdaoues Belhedi | [@Ferdaoues](https://github.com/Ferdaoues) |
| Mohamed Aziz Jabri | [@AzizJabri](https://github.com/AzizJabri) |

## Organisation du dépôt

```
backend/     API FastAPI en couches (api → services → domain) + tests pytest
frontend/    SPA React/TypeScript + tests Vitest et Playwright
tests/api/   tests de contrat Postman/Newman
scripts/     campagne complète, chaos, portabilité, génération de la matrice
reports/     preuves d'exécution (JUnit, JSON, HTML, captures)
```
