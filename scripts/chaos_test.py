"""Tests de fiabilité sur l'infrastructure réelle (ISO 25010 §6.5) — « chaos ciblé ».

Pré-requis : stack démarrée (`docker compose up -d`). Usage : python3 scripts/chaos_test.py
Scénarios :
  C1  Panne de PostgreSQL pendant le service → réponses 503 propres, pas de crash, reprise auto.
  C2  Aucune perte de données après redémarrage de la base.
  C3  Arrêt brutal (SIGKILL) d'un worker API → le service continue de répondre.
  C4  Redémarrage complet du backend → données intactes, maintenance idempotente.
Résultats : reports/reliability/chaos-summary.json + chaos-test.log
"""

import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE = "http://localhost:8080/api"
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "reliability"
OUT.mkdir(parents=True, exist_ok=True)
LOG = []
RESULTS = []


def log(msg: str) -> None:
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    LOG.append(line)


def _parse(raw):
    """JSON de l'API, ou texte brut (ex. page 502 de nginx pendant un redémarrage)."""
    try:
        return json.loads(raw or b"null")
    except ValueError:
        return {"raw": raw.decode(errors="replace")[:200]}


def http(method, path, token=None, body=None):
    req = urllib.request.Request(f"{BASE}{path}", method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    data = json.dumps(body).encode() if body is not None else None
    try:
        with urllib.request.urlopen(req, data=data, timeout=10) as r:  # noqa: S310 - URL locale fixe
            return r.status, _parse(r.read())
    except urllib.error.HTTPError as e:
        return e.code, _parse(e.read())
    except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
        return 0, {"error": str(e)}


def compose(*args: str) -> None:
    subprocess.run(["docker", "compose", *args], cwd=ROOT, check=True, capture_output=True)  # noqa: S603,S607


def wait_health(expected: int = 200, timeout: int = 90) -> float:
    start = time.time()
    while time.time() - start < timeout:
        if http("GET", "/health")[0] == expected:
            return time.time() - start
        time.sleep(0.5)
    raise TimeoutError(f"/health n'a pas retourné {expected} en {timeout}s")


def record(scenario, label, ok, detail=""):
    RESULTS.append({"scenario": scenario, "check": label, "passed": ok, "detail": detail})
    log(f"  [{'OK' if ok else 'ÉCHEC'}] {scenario} — {label} {detail}")


def login() -> str:
    status, body = http("POST", "/auth/login",
                        body={"email": "biblio@bibliotrack.example", "password": "Biblio1234"})
    assert status == 200, body
    return body["access_token"]


def setup_loan(token: str) -> int:
    """Crée un adhérent, un ouvrage, un exemplaire et un emprunt témoins."""
    suffix = str(int(time.time()))
    _, member = http("POST", "/auth/register", body={
        "email": f"chaos.{suffix}@bibliotrack.example", "full_name": "Chaos Test",
        "password": "Chaos1234"})
    _, cats = http("GET", "/categories", token)
    _, author = http("POST", "/authors", token, {"full_name": f"Auteur chaos {suffix}"})
    core = "979" + suffix[-9:].rjust(9, "0")
    key = (10 - sum(int(c) * (1 if i % 2 == 0 else 3) for i, c in enumerate(core)) % 10) % 10
    _, book = http("POST", "/books", token, {"isbn": core + str(key), "title": f"Chaos {suffix}",
                                             "category_id": cats[0]["id"],
                                             "author_ids": [author["id"]]})
    http("POST", f"/books/{book['id']}/copies", token, {"barcode": f"CHAOS-{suffix}"})
    status, loan = http("POST", "/loans", token, {"user_id": member["id"],
                                                 "barcode": f"CHAOS-{suffix}"})
    assert status == 201, loan
    return loan["id"]


def scenario_db_outage(token: str, loan_id: int) -> None:
    log("C1/C2 — arrêt de PostgreSQL pendant le service")
    compose("stop", "db")
    time.sleep(2)
    statuses = [http("GET", "/health")[0] for _ in range(5)]
    record("C1", "API répond 503 (et non crash/timeout) pendant la panne",
           all(s == 503 for s in statuses), f"statuts={statuses}")
    status, body = http("GET", "/books?size=1", token)
    record("C1", "Message d'erreur propre, sans fuite technique",
           status == 503 and "indisponible" in body.get("detail", "")
           and "psycopg" not in json.dumps(body).lower(), f"{status} {body}")
    compose("start", "db")
    recovered = wait_health()
    record("C1", "Reprise automatique après retour de la base (pool_pre_ping)", True,
           f"en {recovered:.1f}s")
    status, loans = http("GET", "/loans?size=100&status=EN_COURS", token)
    record("C2", "Aucune perte de données (emprunt témoin intact)",
           status == 200 and any(item["id"] == loan_id for item in loans["items"]))


def _worker_pids():
    script = ("import os\n"
              "for p in os.listdir('/proc'):\n"
              "    if p.isdigit() and p not in ('1', str(os.getpid())):\n"
              "        try: c = open(f'/proc/{p}/cmdline','rb').read()\n"
              "        except OSError: continue\n"
              "        if b'spawn_main' in c: print(p)\n")
    out = subprocess.run(["docker", "compose", "exec", "-T", "backend", "python", "-c", script],  # noqa: S603,S607
                         cwd=ROOT, check=True, capture_output=True, text=True).stdout
    return out.split()


def scenario_worker_kill(token: str) -> None:
    log("C3 — SIGKILL d'un worker uvicorn")
    pids = _worker_pids()
    if not pids:
        record("C3", "Workers détectés", False, "aucun worker trouvé")
        return
    kill = f"import os, signal; os.kill({int(pids[0])}, signal.SIGKILL)"
    subprocess.run(["docker", "compose", "exec", "-T", "backend", "python", "-c", kill],  # noqa: S603,S607
                   cwd=ROOT, check=True, capture_output=True)
    codes = [http("GET", "/books?size=1", token)[0] for _ in range(30)]
    ok = sum(c == 200 for c in codes)
    record("C3", "Service maintenu pendant la perte d'un worker", ok >= 28,
           f"{ok}/30 requêtes OK (worker {pids[0]} tué)")
    time.sleep(3)
    record("C3", "Worker remplacé par le superviseur uvicorn", len(_worker_pids()) == len(pids),
           f"{len(pids)} workers avant, {len(_worker_pids())} après")


def scenario_backend_restart(loan_id: int) -> None:
    log("C4 — redémarrage complet du backend")
    compose("restart", "backend")
    took = wait_health()
    token = login()
    status, loans = http("GET", "/loans?size=100&status=EN_COURS", token)
    record("C4", "Backend redémarré, données intactes",
           status == 200 and any(item["id"] == loan_id for item in loans["items"]),
           f"opérationnel en {took:.1f}s")
    first = http("POST", "/maintenance/run", token)[1]
    second = http("POST", "/maintenance/run", token)[1]
    record("C4", "Maintenance idempotente après reprise", second == {
        "loans_marked_overdue": 0, "reservations_expired": 0}, f"1er={first} 2e={second}")


def main() -> int:
    log("Démarrage des tests de chaos ciblés sur la stack Docker")
    wait_health()
    token = login()
    loan_id = setup_loan(token)
    log(f"Emprunt témoin créé : id={loan_id}")
    scenario_db_outage(token, loan_id)
    scenario_worker_kill(token)
    scenario_backend_restart(loan_id)
    passed = all(r["passed"] for r in RESULTS)
    summary = {"date": datetime.now(timezone.utc).isoformat(), "passed": passed,
               "checks": len(RESULTS), "failed": sum(not r["passed"] for r in RESULTS),
               "results": RESULTS}
    (OUT / "chaos-summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False),
                                            encoding="utf-8")
    (OUT / "chaos-test.log").write_text("\n".join(LOG), encoding="utf-8")
    log(f"BILAN : {len(RESULTS) - summary['failed']}/{len(RESULTS)} vérifications réussies")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
