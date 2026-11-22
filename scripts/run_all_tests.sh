#!/usr/bin/env bash
# Campagne de tests complète : exécute chaque couche, archive les rapports dans reports/,
# puis génère la matrice de traçabilité (docs/MATRICE_TRACABILITE.md).
#
# Usage : scripts/run_all_tests.sh [--quick] [--with-portability]
#   --quick              : sans Docker (unitaires, intégration, statique, SCA, E2E locaux)
#   --with-portability   : ajoute le test d'installation depuis un clone vierge (~3 min)
# Pré-requis : uv, Node.js ≥ 20, Docker + Compose (sauf --quick).
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
R="$ROOT/reports"
LOGS="$R/logs"
QUICK=0; PORTABILITY=0
for arg in "$@"; do
  case "$arg" in --quick) QUICK=1 ;; --with-portability) PORTABILITY=1 ;; esac
done
mkdir -p "$LOGS" "$R"/{tests,quality,security/zap,api,e2e,performance,reliability,portability}
declare -a SUMMARY=()

run() {  # run "<étape>" <commande...>  — continue même en cas d'échec, journalise tout
  local name="$1"; shift
  printf '\n\033[1m▶ %s\033[0m\n' "$name"
  local start=$SECONDS
  if "$@" >"$LOGS/${name// /_}.log" 2>&1; then
    SUMMARY+=("✅ $name ($((SECONDS - start)) s)"); echo "  ✅ OK"
  else
    SUMMARY+=("❌ $name ($((SECONDS - start)) s) — voir reports/logs/${name// /_}.log"); echo "  ❌ ÉCHEC (voir $LOGS/${name// /_}.log)"
    tail -15 "$LOGS/${name// /_}.log" | sed 's/^/    /'
  fi
}

cd "$ROOT/backend"
uv sync --frozen -q
run "Ruff lint"            sh -c "uv run ruff check app tests --output-format json -o $R/quality/ruff.json; uv run ruff check app tests"
run "Ruff format"          uv run ruff format --check app tests
run "Radon complexite"     sh -c "uv run radon cc app -j > $R/quality/radon-cc.json && uv run radon cc app -s -a > $R/quality/radon-cc.txt && uv run radon mi app -s > $R/quality/radon-mi.txt"
run "Pytest SQLite"        uv run pytest --junitxml="$R/tests/junit-backend.xml" --cov \
                             --cov-report=xml:"$R/quality/backend-coverage.xml" \
                             --cov-report=html:"$R/quality/backend-coverage-html" --cov-report=term
run "Bandit SAST"          sh -c "uv run bandit -r app -c pyproject.toml -f json -o $R/security/bandit.json -q; uv run bandit -r app -c pyproject.toml -f screen -q > $R/security/bandit.txt; python3 -c \"import json,sys; t=json.load(open('$R/security/bandit.json'))['metrics']['_totals']; sys.exit(t['SEVERITY.HIGH']+t['SEVERITY.MEDIUM'])\""
run "pip-audit SCA"        sh -c "uv export --no-dev --frozen --no-hashes -q -o /tmp/biblio-req.txt && uv run pip-audit -r /tmp/biblio-req.txt -f json -o $R/security/pip-audit.json --progress-spinner off"

cd "$ROOT/frontend"
[ -d node_modules ] || npm ci --no-audit --no-fund >/dev/null
run "TypeScript strict"    sh -c "npx tsc --noEmit -p . > $R/quality/tsc.log 2>&1"
run "ESLint"               sh -c "npx eslint . -f json -o $R/quality/eslint.json; npx eslint . --max-warnings=0"
run "Vitest"               npx vitest run --coverage --reporter=default --reporter=junit --outputFile.junit="$R/tests/junit-frontend-unit.xml"
run "jscpd duplication"    npm run duplication
run "npm audit SCA"        sh -c "npm audit --omit=dev --json > $R/security/npm-audit-frontend-prod.json"

if [ "$QUICK" -eq 1 ]; then
  run "Build frontend"     npm run build
  run "Playwright E2E"     npx playwright test
else
  cd "$ROOT"
  run "Pytest PostgreSQL"  sh -c "docker rm -f biblio-pg-test >/dev/null 2>&1; docker run -d --rm --name biblio-pg-test -e POSTGRES_USER=biblio -e POSTGRES_PASSWORD=biblio -e POSTGRES_DB=biblio_test -p 55432:5432 postgres:16-alpine >/dev/null && for i in \$(seq 1 30); do docker exec biblio-pg-test pg_isready -U biblio -q && break; sleep 1; done && sleep 1 && cd backend && TEST_DATABASE_URL=postgresql+psycopg://biblio:biblio@localhost:55432/biblio_test uv run pytest -q --junitxml=$R/tests/junit-backend-postgres.xml; rc=\$?; docker stop biblio-pg-test >/dev/null; exit \$rc"
  run "Docker compose up"  sh -c "docker compose up -d --build && for i in \$(seq 1 120); do curl -sf localhost:8080/api/health && exit 0; sleep 1; done; exit 1"
  cd "$ROOT/tests/api"; [ -d node_modules ] || npm ci --no-audit --no-fund >/dev/null
  run "Newman API"         npx newman run bibliotrack.postman_collection.json -e local.postman_environment.json \
                             --env-var baseUrl=http://localhost:8080 --reporters cli,junit,htmlextra \
                             --reporter-junit-export "$R/api/junit-newman.xml" --reporter-htmlextra-export "$R/api/newman-report.html"
  cd "$ROOT/frontend"
  run "Playwright E2E"     env E2E_BASE_URL=http://localhost:8080 npx playwright test
  cd "$ROOT/backend"
  run "Locust performance" sh -c "uv run locust -f tests/performance/locustfile.py --host http://localhost:8080 --headless -u 20 -r 5 -t 2m --csv $R/performance/locust --html $R/performance/locust-report.html --only-summary && uv run python tests/performance/check_thresholds.py $R/performance/locust_stats.csv"
  cd "$ROOT"
  NET="$(docker compose ps -q frontend | xargs docker inspect -f '{{range $k, $v := .NetworkSettings.Networks}}{{$k}}{{end}}')"
  run "ZAP baseline DAST"  docker run --rm --network "$NET" -v "$R/security/zap:/zap/wrk:rw" zaproxy/zap-stable \
                             zap-baseline.py -t http://frontend:8080 -J zap-report.json -r zap-report.html -w zap-report.md -I
  run "ZAP API scan DAST"  docker run --rm --network "$NET" -v "$R/security/zap:/zap/wrk:rw" zaproxy/zap-stable \
                             zap-api-scan.py -t http://frontend:8080/api/openapi.json -f openapi -J zap-api-report.json -r zap-api-report.html -I
  run "Chaos fiabilite"    python3 scripts/chaos_test.py
  [ "$PORTABILITY" -eq 1 ] && run "Portabilite clone vierge" scripts/portability_test.sh
fi

cd "$ROOT"
run "Matrice tracabilite"  python3 scripts/build_traceability.py

printf '\n\033[1m═══ Bilan de la campagne ═══\033[0m\n'
printf '%s\n' "${SUMMARY[@]}" | tee "$R/logs/bilan-campagne.txt"
! printf '%s\n' "${SUMMARY[@]}" | grep -q "❌"
