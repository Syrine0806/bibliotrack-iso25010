# Preuves d'exécution

Tous les fichiers de ce dossier sont **produits par les outils** lors de `scripts/run_all_tests.sh --with-portability`
(campagne de référence du 24/11/2026 : 21 étapes sur 21 réussies, voir `logs/bilan-campagne.txt`). Aucun n'est rédigé à la main.

| Dossier / fichier | Outil | Contenu à ouvrir en priorité |
|---|---|---|
| `SYNTHESE.md`, `traceability.json` | build_traceability.py | Bilan par outil ; données brutes de la matrice |
| `tests/` | pytest, Vitest | `junit-backend.xml`, `junit-backend-postgres.xml`, `junit-frontend-unit.xml` |
| `api/` | Newman | `newman-report.html` |
| `e2e/` | Playwright + axe-core | `html/index.html` (rapport interactif), `junit-e2e.xml`, `accessibility/*.json`, `screenshots/` |
| `performance/` | Locust | `locust-report.html`, `performance-summary.json` (contrôle des seuils), `stress100-report.html` |
| `reliability/` | Script de chaos (Docker) | `chaos-summary.json`, `chaos-test.log` |
| `security/` | Bandit, pip-audit, npm audit, OWASP ZAP | `bandit.json` (+ `bandit-AVANT-revue.txt`), `pip-audit.json`, `npm-audit-*.json` (+ `npm-audit-AVANT-correction.json`), `zap/zap-report.html`, `zap/zap-api-report.html` (+ `zap-report-AVANT-correction.html`) |
| `quality/` | coverage.py, Radon, Ruff, ESLint, tsc, jscpd, Vitest | `backend-coverage-html/index.html`, `radon-cc.json`, `radon-mi.txt`, `eslint.json`, `ruff.json`, `jscpd/`, `frontend-coverage/` |
| `portability/` | Script de clone vierge | `portability-test.log`, `portability-summary.json` |
| `logs/` | run_all_tests.sh | Sortie complète de chaque étape |

Les fichiers suffixés `-AVANT-…` conservent l'état **avant correction** des anomalies détectées, pour en garder la preuve.
