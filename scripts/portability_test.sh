#!/usr/bin/env bash
# Test de portabilité (ISO 25010 §6.8 — EQ-POR-01) :
#   clone Git VIERGE du dépôt dans un dossier temporaire → docker compose up → tests de fumée.
# Prouve que l'installation ne dépend d'aucun fichier local non versionné.
# Usage : scripts/portability_test.sh   (Docker + Docker Compose requis)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/reports/portability"
mkdir -p "$OUT"
LOG="$OUT/portability-test.log"
WORK="$(mktemp -d)"
PROJECT="bibliotrack-portability"
export FRONTEND_PORT=18080 BACKEND_PORT=18000
BASE="http://localhost:${FRONTEND_PORT}"
PASS=0; FAIL=0

exec > >(tee "$LOG") 2>&1
step() { printf '\n== %s\n' "$*"; }
check() {  # check "<libellé>" <commande...>
  local label="$1"; shift
  if "$@" >/dev/null 2>&1; then echo "  [OK]   $label"; PASS=$((PASS+1)); else echo "  [ÉCHEC] $label"; FAIL=$((FAIL+1)); fi
}
cleanup() { (cd "$WORK/repo" 2>/dev/null && docker compose -p "$PROJECT" down -v --remove-orphans >/dev/null 2>&1) || true; rm -rf "$WORK"; }
trap cleanup EXIT

step "Environnement d'exécution"
echo "Date        : $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "Système     : $(uname -srm)"
echo "Docker      : $(docker version --format '{{.Server.Version}}')"
echo "Compose     : $(docker compose version --short)"
echo "Commit      : $(git -C "$ROOT" rev-parse --short HEAD)"

step "1. Clone vierge du dépôt (seuls les fichiers versionnés)"
git clone --quiet "$ROOT" "$WORK/repo"
cd "$WORK/repo"
echo "Fichiers versionnés : $(git ls-files | wc -l | tr -d ' ')"

step "2. Construction des images et démarrage (projet isolé, ports ${FRONTEND_PORT}/${BACKEND_PORT})"
START=$(date +%s)
docker compose -p "$PROJECT" up -d --build --quiet-pull 2>&1 | tail -5
for _ in $(seq 1 180); do
  curl -sf "$BASE/api/health" >/dev/null 2>&1 && break
  sleep 1
done
READY=$(( $(date +%s) - START ))
echo "Application opérationnelle en ${READY} s (construction incluse)"
docker compose -p "$PROJECT" ps --format 'table {{.Service}}\t{{.Status}}'

step "3. Tests de fumée"
check "Sonde de santé /api/health = 200" curl -sf "$BASE/api/health"
check "SPA servie par nginx (index.html)" sh -c "curl -sf $BASE/ | grep -q '<div id=\"root\">'"
check "Routage SPA (deep link /catalogue)" sh -c "curl -sf $BASE/catalogue | grep -q 'id=\"root\"'"
TOKEN=$(curl -sf "$BASE/api/auth/login" -H 'Content-Type: application/json' \
  -d '{"email":"biblio@bibliotrack.example","password":"Biblio1234"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])' || true)
check "Authentification JWT" test -n "$TOKEN"
check "Données de démo chargées (5000 ouvrages)" sh -c "curl -sf -H 'Authorization: Bearer $TOKEN' '$BASE/api/books?size=1' | grep -q '\"total\":5000'"
check "Tableau de bord sur PostgreSQL" curl -sf -H "Authorization: Bearer $TOKEN" "$BASE/api/dashboard"
check "En-tête CSP posé par nginx" sh -c "curl -sI $BASE/ | grep -qi 'content-security-policy'"
check "Version nginx masquée" sh -c "! curl -sI $BASE/ | grep -qi 'server: nginx/'"
check "Conteneur backend non-root" sh -c "[ \"\$(docker compose -p $PROJECT exec -T backend id -u)\" != '0' ]"
check "Persistance : volume PostgreSQL nommé" sh -c "docker volume ls | grep -q ${PROJECT}_pgdata"

step "4. Redémarrage complet (down/up sans -v) : les données persistent"
curl -sf -X POST "$BASE/api/categories" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"name":"Catégorie portabilité"}' >/dev/null
docker compose -p "$PROJECT" down >/dev/null 2>&1
docker compose -p "$PROJECT" up -d >/dev/null 2>&1
for _ in $(seq 1 90); do curl -sf "$BASE/api/health" >/dev/null 2>&1 && break; sleep 1; done
TOKEN=$(curl -sf "$BASE/api/auth/login" -H 'Content-Type: application/json' \
  -d '{"email":"biblio@bibliotrack.example","password":"Biblio1234"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])' || true)
check "Donnée créée avant redémarrage retrouvée" sh -c "curl -sf -H 'Authorization: Bearer $TOKEN' $BASE/api/categories | grep -q 'Catégorie portabilité'"
check "Pas de double chargement des données de démo" sh -c "curl -sf -H 'Authorization: Bearer $TOKEN' '$BASE/api/books?size=1' | grep -q '\"total\":5000'"

step "Images produites"
docker images --format '{{.Repository}}:{{.Tag}}  {{.Size}}' | grep "$PROJECT" || true

step "Bilan"
echo "Vérifications réussies : $PASS / $((PASS+FAIL))"
python3 - "$OUT/portability-summary.json" "$PASS" "$FAIL" "$READY" <<'EOF'
import json, sys, platform, datetime
path, ok, ko, ready = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
json.dump({"date": datetime.datetime.now(datetime.timezone.utc).isoformat(), "host": platform.platform(),
           "checks_passed": ok, "checks_failed": ko, "ready_seconds_including_build": ready,
           "passed": ko == 0}, open(path, "w"), indent=2)
EOF
[ "$FAIL" -eq 0 ]
