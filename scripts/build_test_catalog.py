#!/usr/bin/env python3
"""Catalogue Excel de tous les cas de test, regroupés par couche, construit À PARTIR DES RAPPORTS RÉELS.

Comme scripts/build_traceability.py, rien n'est saisi à la main : chaque ligne provient d'un rapport
d'exécution (JUnit XML, JSON, CSV) ; une couche sans rapport apparaît « Non exécuté ».

Usage (après scripts/run_all_tests.sh) :
    uv run --no-project --with openpyxl python scripts/build_test_catalog.py
Sortie : reports/Catalogue_des_tests.xlsx (onglets « Synthèse », « Exécution par couche », « Cas de test »)
"""

import ast
import csv
import json
import re
import xml.etree.ElementTree as ET  # noqa: N817
from collections import Counter
from datetime import datetime
from pathlib import Path

from openpyxl import Workbook
from openpyxl.formatting.rule import FormulaRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

ROOT = Path(__file__).resolve().parents[1]
R = ROOT / "reports"
OUT = R / "Catalogue_des_tests.xlsx"
REQ_RE = re.compile(r"\b((?:EF|RG|WF)-\d{2}|EQ-[A-Z]{3,4}-\d{2})\b")
TAG_RE = re.compile(r"\[((?:EF|RG|WF)-\d{2}|EQ-[A-Z]{3,4}-\d{2})\]")
ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
PASS, FAIL, SKIP = "pass", "fail", "skip"

# clé, titre de section, outil(s), emplacement, préfixe des identifiants
SECTIONS = [
    ("unit_back", "Tests unitaires — backend", "pytest", "backend/tests/unit/", "UB"),
    ("unit_front", "Tests unitaires — frontend", "Vitest + Testing Library (jsdom)",
     "frontend/src/**/*.test.ts(x)", "UF"),
    ("integration", "Tests d'intégration (API ↔ base de données)",
     "pytest + TestClient (SQLite et PostgreSQL)", "backend/tests/integration/", "IT"),
    ("api", "Tests d'API (contrat)", "Postman / Newman", "tests/api/", "API"),
    ("e2e", "Tests de bout en bout (E2E) et compatibilité navigateurs",
     "Playwright (Chromium, Firefox, WebKit)", "frontend/e2e/", "E2E"),
    ("a11y", "Accessibilité (WCAG 2.1 AA)", "Playwright + axe-core",
     "frontend/e2e/usability.spec.ts", "ACC"),
    ("perf", "Performance (charge)", "Locust", "backend/tests/performance/", "PERF"),
    ("security", "Sécurité (tests applicatifs, SAST, SCA, DAST)",
     "pytest · Bandit · Ruff · ESLint · pip-audit · npm audit · OWASP ZAP",
     "backend/tests/*/test_security_*.py · scripts/run_all_tests.sh", "SEC"),
    ("reliability", "Fiabilité (code et infrastructure)", "pytest · Docker (chaos ciblé)",
     "backend/tests/reliability/ · scripts/chaos_test.py", "FIA"),
    ("quality", "Maintenabilité et qualité du code",
     "Ruff · Radon · tsc · ESLint · jscpd · coverage", "reports/quality/", "QUA"),
    ("portability", "Portabilité", "Docker Compose (clone Git vierge)",
     "scripts/portability_test.sh", "POR"),
]
ROWS: dict[str, list[dict]] = {key: [] for key, *_ in SECTIONS}


# ------------------------------------------------------------------ utilitaires
def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def stamp(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime).strftime("%d/%m/%Y %H:%M")


def reqs(*texts: str) -> str:
    return ", ".join(sorted({m for t in texts if t for m in REQ_RE.findall(t)}))


def clean(title: str) -> str:
    """Titre sans les étiquettes d'exigence (reportées dans la colonne « Exigences »)."""
    return re.sub(r"\s+", " ", TAG_RE.sub("", title)).strip()


def verdict(statuses: list[str]) -> str:
    if not statuses:
        return "Non exécuté"
    if FAIL in statuses:
        return "Échec"
    if all(s == SKIP for s in statuses):
        return "Ignoré"
    if SKIP in statuses:
        return "Réussi (partiel)"
    return "Réussi"


def symbol(status: str) -> str:
    return {PASS: "✔", FAIL: "✘", SKIP: "ignoré"}[status]


def passfail(ok: bool) -> str:
    return "Réussi" if ok else "Échec"


def add(section, group, case, *, result, req="", env="", duration=None, detail="", source=""):
    ROWS[section].append({"group": group, "case": case, "req": req, "env": env, "result": result,
                          "duration": duration, "detail": detail, "source": source})


def not_run(section, group, what, path: Path, req=""):
    add(section, group, what, req=req, result="Non exécuté",
        detail="Aucun rapport d'exécution trouvé.", source=rel(path))


def campaign_steps() -> dict[str, tuple[bool, int]]:
    path = R / "logs" / "bilan-campagne.txt"
    steps = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            m = re.match(r"(✅|❌) (.+?) \((\d+) s\)", line)
            if m:
                steps[m.group(2)] = (m.group(1) == "✅", int(m.group(3)))
    return steps


STEPS = campaign_steps()


# ------------------------------------------------------------------ JUnit
def junit_status(case: ET.Element) -> str:
    if case.find("failure") is not None or case.find("error") is not None:
        return FAIL
    if case.find("skipped") is not None:
        return SKIP
    return PASS


def failure_message(case: ET.Element) -> str:
    for tag in ("failure", "error"):
        el = case.find(tag)
        if el is not None:
            return ANSI_RE.sub("", el.get("message") or el.text or "").strip()[:300]
    return ""


# ------------------------------------------------------------------ pytest (unitaire, intégration, sécurité, fiabilité)
def _collect_docstrings(node, module, cls, docs):
    for child in node.body:
        if isinstance(child, ast.ClassDef):
            _collect_docstrings(child, module, child.name, docs)
        elif isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef) and child.name.startswith("test_"):
            doc = ast.get_docstring(child)
            if doc:
                docs[(module, cls, child.name)] = doc.strip().splitlines()[0]


def docstrings() -> dict:
    docs: dict = {}
    for file in (ROOT / "backend" / "tests").rglob("test_*.py"):
        module = ".".join(file.relative_to(ROOT / "backend").with_suffix("").parts)
        _collect_docstrings(ast.parse(file.read_text(encoding="utf-8")), module, None, docs)
    return docs


def pytest_section(module: str) -> str:
    if module.rsplit(".", 1)[-1] in ("test_security_unit", "test_security_api"):
        return "security"
    if module.startswith("tests.unit."):
        return "unit_back"
    if module.startswith("tests.reliability."):
        return "reliability"
    return "integration"


def humanize(name: str) -> str:
    base, bracket, param = name.partition("[")
    text = base.removeprefix("test_").replace("_", " ").strip()
    text = text[:1].upper() + text[1:]
    return f"{text} [{param}" if bracket else text


def collect_pytest() -> None:
    envs = [("SQLite", R / "tests" / "junit-backend.xml"),
            ("PostgreSQL", R / "tests" / "junit-backend-postgres.xml")]
    cases: dict = {}
    for env, path in envs:
        if not path.exists():
            continue
        for case in ET.parse(path).getroot().iter("testcase"):
            entry = cases.setdefault((case.get("classname"), case.get("name")),
                                     {"status": {}, "time": 0.0, "req": "", "msg": ""})
            entry["status"][env] = junit_status(case)
            entry["time"] += float(case.get("time") or 0)
            for prop in case.iter("property"):
                if prop.get("name") == "req":
                    entry["req"] = prop.get("value", "").replace(",", ", ")
            entry["msg"] = entry["msg"] or failure_message(case)
    if not cases:
        for section in ("unit_back", "integration", "reliability"):
            not_run(section, "pytest", "Suite pytest", envs[0][1])
        return
    docs = docstrings()
    for (classname, name), e in cases.items():
        parts = classname.split(".")
        idx = next((i for i, p in enumerate(parts) if p.startswith("test_")), len(parts) - 1)
        module, cls = ".".join(parts[: idx + 1]), ".".join(parts[idx + 1:]) or None
        file = module.replace(".", "/") + ".py"
        env = " · ".join(f"{n} {symbol(e['status'][n])}" if n in e["status"] else f"{n} non exécuté"
                         for n, _ in envs)
        doc = docs.get((module, cls, name.split("[")[0]), "")
        detail = " ".join(x for x in (doc, f"Erreur : {e['msg']}" if e["msg"] else "") if x)
        add(pytest_section(module), Path(file).name + (f" › {cls}" if cls else ""), humanize(name),
            req=e["req"], env=env, result=verdict(list(e["status"].values())), duration=e["time"],
            detail=detail, source=f"backend/{file}::" + (f"{cls}::" if cls else "") + name)


# ------------------------------------------------------------------ Vitest
def collect_vitest() -> None:
    path = R / "tests" / "junit-frontend-unit.xml"
    if not path.exists():
        not_run("unit_front", "Vitest", "Suite Vitest", path)
        return
    for case in ET.parse(path).getroot().iter("testcase"):
        file = case.get("classname")
        *describe, title = case.get("name").split(" > ")
        status = junit_status(case)
        add("unit_front", " › ".join([Path(file).name, *describe]), clean(title),
            req=reqs(case.get("name")), env=f"jsdom {symbol(status)}", result=verdict([status]),
            duration=float(case.get("time") or 0), detail=failure_message(case),
            source=f"frontend/{file}")


# ------------------------------------------------------------------ Newman
def collect_newman() -> None:
    path = R / "api" / "junit-newman.xml"
    collection = load_json(ROOT / "tests" / "api" / "bibliotrack.postman_collection.json") or {}
    endpoints = {
        f"{folder['name']} / {item['name']}":
            f"{item['request']['method']} {item['request']['url']['raw'].replace('{{baseUrl}}', '')}"
        for folder in collection.get("item", []) for item in folder.get("item", [])
    }
    if not path.exists():
        not_run("api", "Newman", "Collection Postman", path)
        return
    for suite in ET.parse(path).getroot().iter("testsuite"):
        full = suite.get("name")
        folder, _, request = full.partition(" / ")
        cases = list(suite.iter("testcase"))
        statuses = [junit_status(c) for c in cases]
        detail = (f"{endpoints.get(full, '')} — {statuses.count(PASS)}/{len(cases)} assertions : "
                  + " ; ".join(f"{clean(c.get('name'))} {symbol(s)}" for c, s in zip(cases, statuses, strict=True)))
        errors = [failure_message(c) for c, s in zip(cases, statuses, strict=True) if s == FAIL]
        if errors:
            detail += " — Erreur : " + " | ".join(errors)
        add("api", folder, clean(request), req=reqs(full, *(c.get("name") for c in cases)),
            env=f"Stack Docker (nginx :8080) {symbol(FAIL if FAIL in statuses else PASS)}",
            result=verdict(statuses), duration=float(suite.get("time") or 0), detail=detail,
            source="tests/api/bibliotrack.postman_collection.json")


# ------------------------------------------------------------------ Playwright (E2E + accessibilité)
BROWSERS = {"chromium": "Chromium", "firefox": "Firefox", "webkit": "WebKit"}


def axe_summary(title: str) -> str:
    folder = R / "e2e" / "accessibility"
    for f in sorted(folder.glob("*.json")) if folder.exists() else []:
        hit = "connexion accessible" in title if f.stem == "connexion" else f"page {f.stem} " in f"{title} "
        if hit:
            d = load_json(f) or {}
            violations = d.get("violations", [])
            text = (f"axe-core (Chromium) : {d.get('passes', 0)} règles respectées, "
                    f"{len(violations)} violation(s)")
            if violations:
                text += " — " + ", ".join(f"{v['id']} ({v['impact']})" for v in violations)
            return text
    return ""


def _walk(suite, path):
    for spec in suite.get("specs", []):
        yield path, spec
    for sub in suite.get("suites", []):
        yield from _walk(sub, [*path, sub["title"]])


def collect_playwright() -> None:
    path = R / "e2e" / "results-e2e.json"
    data = load_json(path)
    if data is None:
        not_run("e2e", "Playwright", "Suite Playwright", path)
        not_run("a11y", "Playwright + axe-core", "Suite d'accessibilité", path)
        return
    for top in data["suites"]:
        for describe, spec in _walk(top, []):
            file = spec["file"]
            statuses, envs, notes, duration = [], [], [], 0.0
            for t in spec["tests"]:
                browser = BROWSERS.get(t["projectName"], t["projectName"])
                status = {"expected": PASS, "flaky": PASS, "skipped": SKIP}.get(t["status"], FAIL)
                statuses.append(status)
                envs.append(f"{browser} {symbol(status)}")
                duration += sum(r.get("duration", 0) for r in t["results"]) / 1000
                if t["status"] == "flaky":
                    notes.append(f"{browser} : réussi après un nouvel essai")
                notes += [f"{browser} ignoré : {a.get('description', '')}"
                          for a in t.get("annotations", []) if a.get("type") == "skip"]
                notes += [f"{browser} : " + ANSI_RE.sub("", r["error"].get("message", ""))[:200]
                          for r in t["results"] if r.get("status") in ("failed", "timedOut") and r.get("error")]
            section = "a11y" if file.endswith("usability.spec.ts") else "e2e"
            if section == "a11y" and (axe := axe_summary(clean(spec["title"]))):
                notes.insert(0, axe)
            add(section, " › ".join([file, *describe]), clean(spec["title"]), req=reqs(spec["title"]),
                env=" · ".join(envs), result=verdict(statuses), duration=duration,
                detail=" ; ".join(dict.fromkeys(notes)), source=f"frontend/e2e/{file}:{spec['line']}")


# ------------------------------------------------------------------ Locust
def _locust(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _metrics(r: dict) -> str:
    return (f"{int(r['Request Count'])} requêtes · {int(r['Failure Count'])} échec(s) · "
            f"médiane {float(r['50%']):.0f} ms · p95 {float(r['95%']):.0f} ms · "
            f"p99 {float(r['99%']):.0f} ms · max {float(r['Max Response Time']):.0f} ms · "
            f"{float(r['Requests/s']):.1f} req/s")


def collect_locust() -> None:
    stats = R / "performance" / "locust_stats.csv"
    summary = load_json(R / "performance" / "performance-summary.json")
    group = "Charge nominale — 20 utilisateurs, 2 min (profils adhérent 4 : bibliothécaire 1)"
    env = "Stack Docker (nginx + 4 workers + PostgreSQL, 5 000 ouvrages)"
    if not stats.exists() or summary is None:
        not_run("perf", group, "Test de charge Locust", stats, req="EQ-PERF-01")
    else:
        rows = _locust(stats)
        agg = next(r for r in rows if r["Name"] == "Aggregated")
        add("perf", group, "Seuil global : p95 < 500 ms et taux d'erreur < 1 %", req="EQ-PERF-01",
            env=env, result=passfail(summary["passed"]),
            detail=f"{_metrics(agg)} · taux d'erreur {summary['error_rate']:.2%} · exécuté le {stamp(stats)}",
            source=rel(R / "performance" / "performance-summary.json"))
        for r in rows:
            if r["Name"] != "Aggregated":
                add("perf", group, r["Name"], req="EQ-PERF-01", env=env, result="Mesure",
                    detail=_metrics(r), source=rel(stats))
    stress = R / "performance" / "stress100_stats.csv"
    if stress.exists():
        agg = next(r for r in _locust(stress) if r["Name"] == "Aggregated")
        add("perf", "Stress exploratoire — 100 utilisateurs (hors campagne automatisée)",
            "Comportement à 100 utilisateurs simultanés", env=env, result="Mesure",
            detail=f"{_metrics(agg)} · exécuté le {stamp(stress)}", source=rel(stress))


# ------------------------------------------------------------------ sécurité : SAST, SCA, DAST
RISK = {"High": "Élevé", "Medium": "Moyen", "Low": "Faible", "Informational": "Info"}


def collect_security_tools() -> None:
    sast, sca = "SAST — analyse statique de sécurité", "SCA — vulnérabilités connues des dépendances"

    path = R / "security" / "bandit.json"
    if (d := load_json(path)) is None:
        not_run("security", sast, "Bandit", path, req="EQ-SEC-06")
    else:
        t = d["metrics"]["_totals"]
        high, med, low = t["SEVERITY.HIGH"], t["SEVERITY.MEDIUM"], t["SEVERITY.LOW"]
        issues = " ; ".join(f"{i['test_id']} {i['issue_severity']} {i['filename']}:{i['line_number']}"
                            for i in d["results"])
        add("security", sast, "Bandit : aucune alerte de sévérité moyenne ou élevée", req="EQ-SEC-06",
            env="Code Python (app/)", result=passfail(high + med == 0),
            detail=f"{t['loc']} lignes analysées · {high} élevée · {med} moyenne · {low} faible"
                   + (f" — {issues}" if issues else ""), source=rel(path))

    path = R / "quality" / "ruff.json"
    if (d := load_json(path)) is None:
        not_run("security", sast, "Ruff — règles S", path, req="EQ-SEC-06")
    else:
        found = [x for x in d if str(x.get("code", "")).startswith("S")]
        add("security", sast, "Ruff : règles de sécurité S (flake8-bandit)", req="EQ-SEC-06",
            env="Code Python (app/, tests/)", result=passfail(not found),
            detail=f"{len(found)} alerte(s)" + "".join(f" ; {x['code']} {x['filename']}:{x['location']['row']}"
                                                       for x in found), source=rel(path))

    path = R / "quality" / "eslint.json"
    if (d := load_json(path)) is None:
        not_run("security", sast, "ESLint — eslint-plugin-security", path, req="EQ-SEC-06")
    else:
        found = [m for f in d for m in f["messages"] if str(m.get("ruleId") or "").startswith("security/")]
        add("security", sast, "ESLint : eslint-plugin-security (règles recommandées)", req="EQ-SEC-06",
            env="Code TypeScript (frontend)", result=passfail(not found),
            detail=f"{len(d)} fichiers analysés · {len(found)} alerte(s)", source=rel(path))

    path = R / "security" / "pip-audit.json"
    if (d := load_json(path)) is None:
        not_run("security", sca, "pip-audit", path, req="EQ-SEC-07")
    else:
        vulns = [f"{p['name']} {p['version']} ({v['id']})" for p in d["dependencies"] for v in p.get("vulns", [])]
        add("security", sca, "pip-audit : dépendances Python de production", req="EQ-SEC-07",
            env="uv.lock (sans dépendances de dev)", result=passfail(not vulns),
            detail=f"{len(d['dependencies'])} paquets analysés · {len(vulns)} vulnérabilité(s)"
                   + (f" — {', '.join(vulns)}" if vulns else ""), source=rel(path))

    path = R / "security" / "npm-audit-frontend-prod.json"
    if (d := load_json(path)) is None:
        not_run("security", sca, "npm audit", path, req="EQ-SEC-07")
    else:
        v, deps = d["metadata"]["vulnerabilities"], d["metadata"]["dependencies"]
        add("security", sca, "npm audit : dépendances JavaScript livrées (--omit=dev)", req="EQ-SEC-07",
            env="package-lock.json (frontend)", result=passfail(v["total"] == 0),
            detail=f"{deps['prod']} dépendances de production · critique {v['critical']} · élevée {v['high']}"
                   f" · modérée {v['moderate']} · faible {v['low']}", source=rel(path))

    for fname, group, target in (
        ("zap-report.json", "DAST — OWASP ZAP baseline (scan passif)", "http://frontend:8080"),
        ("zap-api-report.json", "DAST — OWASP ZAP API scan (actif, contrat OpenAPI)", "/api/openapi.json"),
    ):
        path = R / "security" / "zap" / fname
        if (z := load_json(path)) is None:
            not_run("security", group, "Scan OWASP ZAP", path, req="EQ-SEC-08")
            continue
        alerts = sorted((a for site in z["site"] for a in site["alerts"]),
                        key=lambda a: list(RISK).index(a["riskdesc"].split(" ")[0]))
        counts = Counter(a["riskdesc"].split(" ")[0] for a in alerts)
        env = f"Stack Docker — cible {target}"
        add("security", group, "Aucune alerte de risque élevé ou moyen", req="EQ-SEC-08", env=env,
            result=passfail(counts["High"] + counts["Medium"] == 0),
            detail=f"Rapport du {z['@generated']} · types d'alertes : "
                   + " · ".join(f"{label} {counts[k]}" for k, label in RISK.items()), source=rel(path))
        for a in alerts:
            risk, _, confidence = a["riskdesc"].partition(" ")
            add("security", group, f"Alerte : {a['name']}", req="EQ-SEC-08", env=env, result="Mesure",
                detail=f"Risque {RISK.get(risk, risk)} (confiance {confidence.strip('()')}) · "
                       f"{a['count']} occurrence(s) · règle ZAP {a['pluginid']}", source=rel(path))


# ------------------------------------------------------------------ fiabilité : chaos
CHAOS = {"C1": ("Panne de PostgreSQL pendant le service", "EQ-FIA-03"),
         "C2": ("Persistance des données après la panne", "EQ-FIA-03"),
         "C3": ("Arrêt brutal (SIGKILL) d'un worker API", "EQ-FIA-06"),
         "C4": ("Redémarrage complet du backend", "EQ-FIA-06")}


def collect_chaos() -> None:
    path = R / "reliability" / "chaos-summary.json"
    if (d := load_json(path)) is None:
        not_run("reliability", "Chaos ciblé sur la stack Docker", "Scénarios C1 à C4", path,
                req="EQ-FIA-03, EQ-FIA-06")
        return
    when = datetime.fromisoformat(d["date"]).astimezone().strftime("%d/%m/%Y %H:%M")
    for r in d["results"]:
        label, req = CHAOS.get(r["scenario"], ("", ""))
        add("reliability", f"Chaos ciblé (Docker) › {r['scenario']} — {label}", r["check"], req=req,
            env="Stack Docker Compose", result=passfail(r["passed"]),
            detail=" · ".join(x for x in (r["detail"], f"exécuté le {when}") if x), source=rel(path))


# ------------------------------------------------------------------ maintenabilité
def collect_quality() -> None:
    q = R / "quality"
    group_py, group_ts, group_cov = "Code Python (backend)", "Code TypeScript (frontend)", "Couverture de code"

    path = q / "ruff.json"
    if (d := load_json(path)) is None:
        not_run("quality", group_py, "Ruff — lint", path, req="EQ-MAI-03")
    else:
        add("quality", group_py, "Ruff : lint (pycodestyle, pyflakes, bugbear, pyupgrade, mccabe ≤ 8, S…)",
            req="EQ-MAI-03", env="app/ + tests/", result=passfail(not d),
            detail=f"{len(d)} problème(s)", source=rel(path))

    if (step := STEPS.get("Ruff format")) is not None:
        add("quality", group_py, "Ruff : formatage conforme (ruff format --check)", req="EQ-MAI-03",
            env="app/ + tests/", result=passfail(step[0]), detail="Code de sortie de l'étape de campagne",
            source="reports/logs/Ruff_format.log")

    path = q / "radon-cc.json"
    if (d := load_json(path)) is None:
        not_run("quality", group_py, "Radon — complexité cyclomatique", path, req="EQ-MAI-02")
    else:
        blocks = [(b["complexity"], b["rank"], b["name"], f) for f, bl in d.items() for b in bl]
        worst = max(blocks)
        add("quality", group_py, "Radon : complexité cyclomatique ≤ 10 par fonction", req="EQ-MAI-02",
            env="app/", result=passfail(worst[0] <= 10),
            detail=f"{len(blocks)} fonctions/classes analysées · maximum {worst[0]} (rang {worst[1]}) : "
                   f"{worst[2]} dans {worst[3]}", source=rel(path))

    path = q / "radon-mi.txt"
    if path.exists():
        mi = [re.match(r"(\S+) - ([A-F]) \(([\d.]+)\)", line) for line in path.read_text(encoding="utf-8").splitlines()]
        mi = [m for m in mi if m]
        lowest = min(mi, key=lambda m: float(m.group(3)))
        ranked_a = sum(m.group(2) == "A" for m in mi)
        add("quality", group_py, "Radon : indice de maintenabilité au rang A pour chaque module",
            req="EQ-MAI-02", env="app/", result=passfail(ranked_a == len(mi)),
            detail=f"{ranked_a}/{len(mi)} modules au rang A · minimum {lowest.group(3)} ({lowest.group(1)})",
            source=rel(path))

    path = q / "tsc.log"
    if path.exists():
        content = path.read_text(encoding="utf-8").strip()
        errors = len(re.findall(r"error TS\d+", content))
        add("quality", group_ts, "TypeScript : compilation en mode strict sans erreur", req="EQ-MAI-03",
            env="tsc --noEmit (strict)", result=passfail("error" not in content.lower()),
            detail=f"{errors} erreur(s)" + (f" — {content[:200]}" if content else ""), source=rel(path))

    path = q / "eslint.json"
    if (d := load_json(path)) is not None:
        errors = sum(f["errorCount"] for f in d)
        warnings = sum(f["warningCount"] for f in d)
        add("quality", group_ts, "ESLint : 0 avertissement (complexité ≤ 10, profondeur ≤ 3, hooks React)",
            req="EQ-MAI-03", env="frontend (src/ + e2e/)", result=passfail(errors + warnings == 0),
            detail=f"{len(d)} fichiers · {errors} erreur(s) · {warnings} avertissement(s)", source=rel(path))

    path = q / "jscpd" / "jscpd-report.json"
    if (d := load_json(path)) is None:
        not_run("quality", group_ts, "jscpd — duplication", path, req="EQ-MAI-04")
    else:
        t = d["statistics"]["total"]
        add("quality", group_ts, "jscpd : duplication du code < 3 %", req="EQ-MAI-04", env="frontend/src",
            result=passfail(t["percentage"] < 3),
            detail=f"{t['percentage']:.2f} % de lignes dupliquées · {t['clones']} clone(s) · "
                   f"{t['lines']} lignes dans {t['sources']} fichiers", source=rel(path))

    path = q / "backend-coverage.xml"
    if not path.exists():
        not_run("quality", group_cov, "Couverture backend", path, req="EQ-MAI-01")
    else:
        root = ET.parse(path).getroot()
        lines, branches = float(root.get("line-rate")) * 100, float(root.get("branch-rate")) * 100
        add("quality", group_cov, "Couverture backend ≥ 80 % (lignes et branches)", req="EQ-MAI-01",
            env="pytest-cov (SQLite)", result=passfail(lines >= 80 and branches >= 80),
            detail=f"lignes {lines:.1f} % · branches {branches:.1f} %", source=rel(path))

    path = q / "frontend-coverage" / "coverage-summary.json"
    if (d := load_json(path)) is not None:
        t = d["total"]
        add("quality", group_cov, "Couverture frontend (tests unitaires Vitest)", env="@vitest/coverage-v8",
            result="Mesure",
            detail=f"lignes {t['lines']['pct']} % · branches {t['branches']['pct']} % · "
                   f"fonctions {t['functions']['pct']} % — aucun seuil défini dans le plan de test",
            source=rel(path))


# ------------------------------------------------------------------ portabilité
def collect_portability() -> None:
    path = R / "portability" / "portability-summary.json"
    group = "Installation depuis un clone Git vierge (ports 18080/18000)"
    d = load_json(path)
    if d is None:
        not_run("portability", group, "Installation et persistance après redémarrage", path, req="EQ-POR-01")
        return
    when = datetime.fromisoformat(d["date"]).astimezone().strftime("%d/%m/%Y %H:%M")
    total = d["checks_passed"] + d["checks_failed"]
    summary = (f"{d['checks_passed']}/{total} vérifications réussies, opérationnel en "
               f"{d['ready_seconds_including_build']} s (build inclus)")
    if "Portabilite clone vierge" in STEPS:
        add("portability", group, "Installation et persistance après redémarrage", req="EQ-POR-01",
            env=d["host"], result=passfail(d["passed"]), detail=f"{summary} · exécuté le {when}",
            source=rel(path))
    else:
        add("portability", group, "Installation et persistance après redémarrage", req="EQ-POR-01",
            env=d["host"], result="Non exécuté",
            detail=f"Non lancé dans cette campagne (option --with-portability). Dernière exécution le "
                   f"{when} : {summary}.", source=rel(path))


# ------------------------------------------------------------------ classeur Excel
FONT = "Arial"
NAVY = "1F3864"
HEAD_FILL = PatternFill("solid", fgColor=NAVY)
SECTION_FILL = PatternFill("solid", fgColor="D9E1F2")
THIN = Side(style="thin", color="BFBFBF")
BORDER = Border(top=THIN, bottom=THIN, left=THIN, right=THIN)
RESULT_STYLES = [  # (formule, fond, texte)
    ('ISNUMBER(SEARCH("Réussi",{c}))', "C6EFCE", "006100"),
    ('{c}="Échec"', "FFC7CE", "9C0006"),
    ('OR({c}="Ignoré",{c}="Non exécuté")', "FFEB9C", "9C5700"),
    ('{c}="Mesure"', "DDEBF7", NAVY),
]
LEGEND = [
    ("Réussi", "Le test ou le seuil est satisfait dans tous les environnements où il a été exécuté."),
    ("Réussi (partiel)", "Réussi, mais ignoré dans au moins un environnement (raison dans « Détail »)."),
    ("Échec", "Au moins un environnement en échec, ou seuil non respecté."),
    ("Ignoré", "Ignoré dans tous les environnements."),
    ("Non exécuté", "Aucun rapport d'exécution pour cette campagne : aucun résultat n'est inventé."),
    ("Mesure", "Valeur relevée sans seuil propre (temps par endpoint, alerte ZAP informative, couverture frontend)."),
]
CASE_HEADERS = ["N°", "Section", "Groupe", "Cas de test", "Exigences", "Environnement(s) et résultat",
                "Résultat", "Durée cumulée (s)", "Détail", "Source (test ou rapport)"]
CASE_WIDTHS = [10, 24, 36, 58, 20, 36, 16, 11, 70, 50]


def font(size=10, **kw) -> Font:
    return Font(name=FONT, size=size, **kw)


def header_row(ws, row: int, values: list[str]) -> None:
    for col, value in enumerate(values, 1):
        c = ws.cell(row=row, column=col, value=value)
        c.font = font(bold=True, color="FFFFFF")
        c.fill = HEAD_FILL
        c.border = BORDER
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)


def result_formatting(ws, ref: str, first_cell: str) -> None:
    for formula, fill, color in RESULT_STYLES:
        ws.conditional_formatting.add(ref, FormulaRule(
            formula=[formula.format(c=first_cell)], fill=PatternFill("solid", fgColor=fill),
            font=Font(name=FONT, color=color, bold=True)))


def write_cases(ws) -> int:
    ws.title = "Cas de test"
    header_row(ws, 1, CASE_HEADERS)
    ws.row_dimensions[1].height = 30
    ws.sheet_properties.outlinePr.summaryBelow = False
    row = 2
    for n, (key, title, tool, location, prefix) in enumerate(SECTIONS, 1):
        rows = ROWS[key]
        ws.cell(row=row, column=1, value=f"{n}. {title} — {len(rows)} ligne(s) · {tool} · {location}")
        for col in range(1, len(CASE_HEADERS) + 1):
            c = ws.cell(row=row, column=col)
            c.fill, c.font, c.border = SECTION_FILL, font(11, bold=True, color=NAVY), BORDER
        ws.row_dimensions[row].height = 20
        row += 1
        start = row
        for i, r in enumerate(rows, 1):
            values = [f"{prefix}-{i:03d}", title, r["group"], r["case"], r["req"], r["env"], r["result"],
                      r["duration"], r["detail"], r["source"]]
            for col, value in enumerate(values, 1):
                c = ws.cell(row=row, column=col, value=value)
                c.font, c.border = font(), BORDER
                c.alignment = Alignment(vertical="top", wrap_text=col in (3, 4, 5, 6, 9, 10))
            ws.cell(row=row, column=8).number_format = "0.00"
            row += 1
        if rows:
            ws.row_dimensions.group(start, row - 1, outline_level=1, hidden=False)
    last = row - 1
    for col, width in enumerate(CASE_WIDTHS, 1):
        ws.column_dimensions[get_column_letter(col)].width = width
    ws.freeze_panes = "E2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(CASE_HEADERS))}{last}"
    result_formatting(ws, f"G2:G{last}", "$G2")
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth, ws.page_setup.fitToHeight = 1, 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.print_title_rows = "1:1"
    return last


def write_summary(ws, last: int) -> None:
    ws.title = "Synthèse"
    bilan = R / "logs" / "bilan-campagne.txt"
    ws["A1"] = "Catalogue des tests — BiblioTrack"
    ws["A1"].font = font(16, bold=True, color=NAVY)
    ws["A2"] = (f"Généré le {datetime.now():%d/%m/%Y %H:%M} par scripts/build_test_catalog.py à partir des "
                f"rapports d'exécution de reports/"
                + (f" (campagne terminée le {stamp(bilan)})." if bilan.exists() else "."))
    ws["A2"].font = font(italic=True, color="595959")

    headers = ["Section", "Outil(s)", "Emplacement", "Lignes", "Réussis", "Échecs",
               "Ignorés / non exécutés", "Mesures (sans seuil)", "Taux de réussite"]
    header_row(ws, 4, headers)
    ws.row_dimensions[4].height = 30
    sec, res = f"'Cas de test'!$B$2:$B${last}", f"'Cas de test'!$G$2:$G${last}"
    first = 5
    for i, (_key, title, tool, location, _prefix) in enumerate(SECTIONS):
        r = first + i
        count = f"COUNTIFS({sec},$A{r},{res},"
        values = [title, tool, location, f"=COUNTIFS({sec},$A{r})", f'={count}"Réussi*")',
                  f'={count}"Échec")', f'={count}"Ignoré")+{count}"Non exécuté")', f'={count}"Mesure")',
                  f'=IF(E{r}+F{r}=0,"-",E{r}/(E{r}+F{r}))']
        for col, value in enumerate(values, 1):
            c = ws.cell(row=r, column=col, value=value)
            c.font, c.border = font(), BORDER
            c.alignment = Alignment(vertical="top", wrap_text=col <= 3,
                                    horizontal="center" if col >= 4 else None)
        ws.cell(row=r, column=9).number_format = "0.0%"
    total = first + len(SECTIONS)
    ws.cell(row=total, column=1, value="Total")
    for col in range(4, 9):
        letter = get_column_letter(col)
        ws.cell(row=total, column=col, value=f"=SUM({letter}{first}:{letter}{total - 1})")
    ws.cell(row=total, column=9, value=f'=IF(E{total}+F{total}=0,"-",E{total}/(E{total}+F{total}))')
    ws.cell(row=total, column=9).number_format = "0.0%"
    for col in range(1, 10):
        c = ws.cell(row=total, column=col)
        c.font, c.border, c.fill = font(bold=True), BORDER, SECTION_FILL
        c.alignment = Alignment(horizontal="center" if col >= 4 else None)

    note = total + 1
    ws.cell(row=note, column=1, value=(
        "Une ligne pytest = un cas exécuté sur SQLite et sur PostgreSQL ; une ligne E2E = un scénario exécuté "
        "sur Chromium, Firefox et WebKit ; une ligne Newman = une requête et toutes ses assertions. "
        "Le taux de réussite exclut les lignes « Mesure » et « Ignoré / non exécuté ».")).font = font(9, italic=True, color="595959")

    row = note + 2
    ws.cell(row=row, column=1, value="Légende de la colonne « Résultat »").font = font(12, bold=True, color=NAVY)
    for label, meaning in LEGEND:
        row += 1
        ws.cell(row=row, column=1, value=label).font = font(bold=True)
        ws.cell(row=row, column=2, value=meaning).font = font()
    result_formatting(ws, f"A{row - len(LEGEND) + 1}:A{row}", f"$A{row - len(LEGEND) + 1}")

    row += 2
    ws.cell(row=row, column=1, value="Étapes de la campagne (reports/logs/bilan-campagne.txt)").font = font(
        12, bold=True, color=NAVY)
    row += 1
    header_row(ws, row, ["Étape", "Résultat", "Journal", "Durée (s)"])
    start = row + 1
    for name, (ok, seconds) in STEPS.items():
        row += 1
        for col, value in enumerate([name, passfail(ok), f"reports/logs/{name.replace(' ', '_')}.log", seconds], 1):
            c = ws.cell(row=row, column=col, value=value)
            c.font, c.border = font(), BORDER
    if STEPS:
        result_formatting(ws, f"B{start}:B{row}", f"$B{start}")

    for col, width in enumerate([48, 44, 44, 11, 11, 11, 14, 14, 13], 1):
        ws.column_dimensions[get_column_letter(col)].width = width
    ws.freeze_panes = "A5"


STACK = "Stack Docker démarrée (étape 0)"
PG_URL = "postgresql+psycopg://biblio:biblio@localhost:55432/biblio_test"
ZAP = ('docker run --rm --network bibliotrack_default -v "$PWD/reports/security/zap:/zap/wrk:rw" '
       "zaproxy/zap-stable")
# (n° de section, couche, prérequis, commandes depuis la racine du dépôt, rapports, étapes de campagne)
HOW_TO = [
    ("0", "Prérequis et stack Docker",
     "uv, Node.js ≥ 20, Docker (colima start sur macOS)",
     "cd backend && uv sync --frozen && cd ..\n"
     "cd frontend && npm ci && npx playwright install && cd ..\n"
     "cd tests/api && npm ci && cd ..\n"
     "docker compose up -d --build\n"
     "curl -sf localhost:8080/api/health        # → {\"status\":\"ok\",\"database\":\"ok\"}",
     "http://localhost:8080 (API : /api/docs)", ["Docker compose up"]),
    ("1", "Tests unitaires — backend", "Aucun (SQLite temporaire)",
     "cd backend && uv run pytest tests/unit",
     "terminal (ajouter --junitxml=../reports/tests/junit-unit.xml)", []),
    ("2", "Tests unitaires — frontend", "Aucun",
     "cd frontend && npm test\n"
     "cd frontend && npm run test:coverage        # avec couverture",
     "terminal · reports/quality/frontend-coverage/", ["Vitest"]),
    ("3", "Tests d'intégration — SQLite", "Aucun",
     "cd backend && uv run pytest tests/integration",
     "terminal", ["Pytest SQLite"]),
    ("3", "Tests d'intégration — PostgreSQL", "Docker",
     "docker run -d --rm --name biblio-pg-test -e POSTGRES_USER=biblio -e POSTGRES_PASSWORD=biblio "
     "-e POSTGRES_DB=biblio_test -p 55432:5432 postgres:16-alpine\n"
     f"cd backend && TEST_DATABASE_URL={PG_URL} uv run pytest\n"
     "docker stop biblio-pg-test",
     "reports/tests/junit-backend-postgres.xml (avec --junitxml)", ["Pytest PostgreSQL"]),
    ("4", "Tests d'API (contrat) — Newman", STACK,
     "cd tests/api && npx newman run bibliotrack.postman_collection.json -e local.postman_environment.json "
     "--env-var baseUrl=http://localhost:8080 --reporters cli,htmlextra "
     "--reporter-htmlextra-export ../../reports/api/newman-report.html",
     "reports/api/newman-report.html", ["Newman API"]),
    ("5", "Tests E2E — autonome", "Aucun (démarre une API SQLite et le front automatiquement)",
     "cd frontend && npm run build && npx playwright test auth catalog circulation admin\n"
     "cd frontend && npx playwright test --project=chromium        # un seul navigateur",
     "reports/e2e/html/index.html", []),
    ("5", "Tests E2E — contre la stack Docker", STACK,
     "cd frontend && E2E_BASE_URL=http://localhost:8080 npx playwright test auth catalog circulation admin",
     "reports/e2e/html/index.html", ["Playwright E2E"]),
    ("6", "Accessibilité (axe-core)", "Aucun (démarre l'API et le front ; E2E_BASE_URL pour viser la stack)",
     "cd frontend && npm run build && npx playwright test usability",
     "reports/e2e/accessibility/*.json", []),
    ("7", "Performance (Locust)", STACK,
     "cd backend && uv run locust -f tests/performance/locustfile.py --host http://localhost:8080 --headless "
     "-u 20 -r 5 -t 2m --csv ../reports/performance/locust --html ../reports/performance/locust-report.html "
     "--only-summary\n"
     "cd backend && uv run python tests/performance/check_thresholds.py ../reports/performance/locust_stats.csv",
     "reports/performance/locust-report.html · performance-summary.json", ["Locust performance"]),
    ("8", "Sécurité — tests applicatifs (pytest)", "Aucun",
     "cd backend && uv run pytest tests/unit/test_security_unit.py tests/integration/test_security_api.py",
     "terminal", []),
    ("8", "Sécurité — SAST", "Aucun",
     "cd backend && uv run bandit -r app -c pyproject.toml\n"
     "cd backend && uv run ruff check app tests --select S\n"
     "cd frontend && npx eslint .",
     "terminal (bandit : -f json -o ../reports/security/bandit.json)", ["Bandit SAST"]),
    ("8", "Sécurité — SCA", "Accès Internet (bases de vulnérabilités)",
     "cd backend && uv export --no-dev --frozen --no-hashes -q -o /tmp/biblio-req.txt "
     "&& uv run pip-audit -r /tmp/biblio-req.txt\n"
     "cd frontend && npm audit --omit=dev",
     "terminal", ["pip-audit SCA", "npm audit SCA"]),
    ("8", "Sécurité — DAST (OWASP ZAP)", STACK,
     f"{ZAP} zap-baseline.py -t http://frontend:8080 -J zap-report.json -r zap-report.html -I\n"
     f"{ZAP} zap-api-scan.py -t http://frontend:8080/api/openapi.json -f openapi -J zap-api-report.json "
     "-r zap-api-report.html -I",
     "reports/security/zap/zap-report.html · zap-api-report.html", ["ZAP baseline DAST", "ZAP API scan DAST"]),
    ("9", "Fiabilité — code (pytest)", "Aucun",
     "cd backend && uv run pytest tests/reliability", "terminal", []),
    ("9", "Fiabilité — chaos sur l'infrastructure", f"{STACK} — arrête puis relance des conteneurs",
     "python3 scripts/chaos_test.py",
     "reports/reliability/chaos-summary.json · chaos-test.log", ["Chaos fiabilite"]),
    ("10", "Maintenabilité — Python", "Aucun",
     "cd backend && uv run ruff check app tests && uv run ruff format --check app tests\n"
     "cd backend && uv run radon cc app -s -a && uv run radon mi app -s\n"
     "cd backend && uv run pytest --cov --cov-report=term        # couverture",
     "terminal", ["Ruff lint", "Ruff format", "Radon complexite"]),
    ("10", "Maintenabilité — TypeScript", "Aucun",
     "cd frontend && npx tsc --noEmit -p .\n"
     "cd frontend && npm run lint\n"
     "cd frontend && npm run duplication",
     "reports/quality/jscpd/", ["TypeScript strict", "ESLint", "jscpd duplication"]),
    ("11", "Portabilité (clone Git vierge)", "Docker, ports 18080/18000 libres",
     "scripts/portability_test.sh", "reports/portability/portability-summary.json",
     ["Portabilite clone vierge"]),
    ("—", "Campagne complète", "Comme l'étape 0",
     "scripts/run_all_tests.sh                       # toutes les couches (~25 min)\n"
     "scripts/run_all_tests.sh --with-portability    # + portabilité\n"
     "scripts/run_all_tests.sh --quick               # sans Docker",
     "reports/logs/bilan-campagne.txt", []),
    ("—", "Matrice de traçabilité et ce catalogue", "Rapports présents dans reports/",
     "python3 scripts/build_traceability.py\n"
     "uv run --no-project --with openpyxl python scripts/build_test_catalog.py",
     "docs/MATRICE_TRACABILITE.md · reports/Catalogue_des_tests.xlsx", ["Matrice tracabilite"]),
]


def write_how_to(ws) -> None:
    ws.title = "Exécution par couche"
    ws["A1"] = "Exécuter chaque couche de test indépendamment"
    ws["A1"].font = font(16, bold=True, color=NAVY)
    ws["A2"] = ("Toutes les commandes se lancent depuis la racine du dépôt. « Stack Docker » = étape 0 "
                "(docker compose up -d --build). Les commandes sont celles de scripts/run_all_tests.sh.")
    ws["A2"].font = font(italic=True, color="595959")
    headers = ["Section", "Couche", "Prérequis", "Commande(s)", "Rapport / résultat",
               "Durée (s), dernière campagne"]
    header_row(ws, 4, headers)
    ws.row_dimensions[4].height = 30
    mono = Font(name="Courier New", size=9)
    for i, (num, layer, prereq, commands, report, steps) in enumerate(HOW_TO, 5):
        durations = [STEPS[s][1] for s in steps if s in STEPS]
        values = [num, layer, prereq, commands, report, sum(durations) if durations else "—"]
        for col, value in enumerate(values, 1):
            c = ws.cell(row=i, column=col, value=value)
            c.font = mono if col == 4 else font(bold=col == 2)
            c.border = BORDER
            c.alignment = Alignment(vertical="top", wrap_text=True,
                                    horizontal="center" if col in (1, 6) else None)
            if num in ("0", "—"):
                c.fill = SECTION_FILL
        ws.row_dimensions[i].height = 15 * (commands.count("\n") + 1) + 8 * (len(commands) // 110) + 6
    for col, width in enumerate([9, 34, 32, 110, 40, 14], 1):
        ws.column_dimensions[get_column_letter(col)].width = width
    ws.freeze_panes = "C5"
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth, ws.page_setup.fitToHeight = 1, 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True


def main() -> None:
    collect_pytest()
    collect_vitest()
    collect_newman()
    collect_playwright()
    collect_locust()
    collect_security_tools()
    collect_chaos()
    collect_quality()
    collect_portability()

    wb = Workbook()
    summary = wb.active
    last = write_cases(wb.create_sheet())
    write_summary(summary, last)
    write_how_to(wb.create_sheet(index=1))
    wb.properties.title = "Catalogue des tests — BiblioTrack"
    wb.properties.creator = "scripts/build_test_catalog.py"
    wb.save(OUT)
    print(f"{rel(OUT)} : {sum(len(v) for v in ROWS.values())} lignes")
    for key, title, *_ in SECTIONS:
        print(f"  {title:<60} {len(ROWS[key]):>4}  {dict(Counter(r['result'] for r in ROWS[key]))}")


if __name__ == "__main__":
    main()
