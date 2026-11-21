"""Construit la matrice de traçabilité exigence ↔ test ↔ outil ↔ résultat À PARTIR DES RAPPORTS RÉELS.

Aucune donnée n'est saisie à la main : chaque ligne provient d'un rapport produit par un outil
(JUnit XML de pytest/Vitest/Playwright/Newman, JSON de Locust/Bandit/pip-audit/npm/ZAP/Radon…).
Un rapport absent est signalé « non exécuté » (règle d'or du cahier des charges).

Usage : python3 scripts/build_traceability.py
Sorties : docs/MATRICE_TRACABILITE.md, reports/SYNTHESE.md, reports/traceability.json
"""

import json
import re
import sys
import xml.etree.ElementTree as ET  # noqa: N817
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from requirements_catalog import ISO, REQUIREMENTS  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
R = ROOT / "reports"
REQ_RE = re.compile(r"\b((?:EF|RG|WF)-\d{2}|EQ-[A-Z]{3,4}-\d{2})\b")

# requirement id -> list of evidence dicts
EVIDENCE: dict[str, list[dict]] = defaultdict(list)
SOURCES: list[dict] = []  # bilan par outil


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def add(req: str, layer: str, tool: str, name: str, passed: bool | None, proof: Path, detail=""):
    EVIDENCE[req].append({"layer": layer, "tool": tool, "name": name, "passed": passed,
                          "proof": rel(proof), "detail": detail})


def case_status(case: ET.Element) -> bool | None:
    if case.find("failure") is not None or case.find("error") is not None:
        return False
    if case.find("skipped") is not None:
        return None
    return True


# ------------------------------------------------------------------ JUnit
def parse_junit(path: Path, tool: str, layer_of) -> None:
    if not path.exists():
        SOURCES.append({"tool": tool, "report": rel(path), "status": "NON EXÉCUTÉ"})
        return
    root = ET.parse(path).getroot()
    total = passed = failed = skipped = 0
    for suite in root.iter("testsuite"):
        suite_name = suite.get("name", "")
        browser = suite.get("hostname", "")
        for case in suite.iter("testcase"):
            total += 1
            status = case_status(case)
            passed += status is True
            failed += status is False
            skipped += status is None
            props = {p.get("name"): p.get("value") for p in case.iter("property")}
            ids = set(filter(None, (props.get("req") or "").split(",")))
            text = f"{suite_name} {case.get('name', '')} {case.get('classname', '')}"
            ids |= set(REQ_RE.findall(text))
            if tool == "Playwright" and status is not None:
                ids.add("EQ-COMP-01")  # chaque parcours rejoué sur ce moteur prouve la compatibilité
            label = case.get("name", "")
            if tool == "Postman/Newman":
                label = f"{suite_name.split(' / ', 1)[-1]} › {label}"
            layer, tool_label = layer_of(case, browser)
            for req in ids:
                add(req, layer, tool_label, label, status, path)
    SOURCES.append({"tool": tool, "report": rel(path), "status": "EXÉCUTÉ", "total": total,
                    "passed": passed, "failed": failed, "skipped": skipped})


def pytest_layer(suffix=""):
    def layer_of(case, _browser):
        cls = case.get("classname", "")
        layer = ("Unitaire" if ".unit." in cls else "Fiabilité" if ".reliability." in cls
                 else "Intégration")
        return layer, f"pytest{suffix}"
    return layer_of


# ------------------------------------------------------------------ mesures (JSON)
def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def measure(req, layer, tool, name, passed, proof: Path, detail):
    add(req, layer, tool, name, passed, proof, detail)


def missing(tool: str, path: Path, reqs: list[str], layer: str) -> None:
    SOURCES.append({"tool": tool, "report": rel(path), "status": "NON EXÉCUTÉ"})
    for req in reqs:
        add(req, layer, tool, "Rapport absent : outil non exécuté", None, path, "procédure fournie")


def parse_measures() -> None:  # noqa: C901 - simple suite de lecteurs indépendants
    perf = R / "performance" / "performance-summary.json"
    if (d := load(perf)) is not None:
        measure("EQ-PERF-01", "Performance", "Locust", "Charge 20 utilisateurs / 2 min",
                d["passed"], perf, f"{d['requests']} requêtes, p95 = {d['p95_ms']:.0f} ms, "
                f"p99 = {d['p99_ms']:.0f} ms, erreurs = {d['error_rate'] * 100:.2f} %")
        SOURCES.append({"tool": "Locust", "report": rel(perf), "status": "EXÉCUTÉ",
                        "detail": f"p95 {d['p95_ms']:.0f} ms"})
    else:
        missing("Locust", perf, ["EQ-PERF-01"], "Performance")

    bandit = R / "security" / "bandit.json"
    if (d := load(bandit)) is not None:
        t = d["metrics"]["_totals"]
        bad = t["SEVERITY.MEDIUM"] + t["SEVERITY.HIGH"]
        measure("EQ-SEC-06", "SAST", "Bandit", "Analyse statique du code Python", bad == 0, bandit,
                f"élevé={t['SEVERITY.HIGH']}, moyen={t['SEVERITY.MEDIUM']}, "
                f"faible={t['SEVERITY.LOW']}, revus/exclus={t.get('skipped_tests', 0)}")
        SOURCES.append({"tool": "Bandit (SAST)", "report": rel(bandit), "status": "EXÉCUTÉ"})
    else:
        missing("Bandit", bandit, ["EQ-SEC-06"], "SAST")

    eslint = R / "quality" / "eslint.json"
    if (d := load(eslint)) is not None:
        errors = sum(f["errorCount"] for f in d)
        warnings = sum(f["warningCount"] for f in d)
        for req in ("EQ-SEC-06", "EQ-MAI-03"):
            measure(req, "SAST / qualité", "ESLint (+ plugin security)", f"{len(d)} fichiers TS",
                    errors == 0 and warnings == 0, eslint, f"erreurs={errors}, avertissements={warnings}")
        SOURCES.append({"tool": "ESLint", "report": rel(eslint), "status": "EXÉCUTÉ"})

    pipa = R / "security" / "pip-audit.json"
    if (d := load(pipa)) is not None:
        vulns = [x["name"] for x in d["dependencies"] if x.get("vulns")]
        measure("EQ-SEC-07", "SCA", "pip-audit", "Dépendances Python de production", not vulns,
                pipa, f"{len(d['dependencies'])} paquets, vulnérables : {vulns or 'aucun'}")
        SOURCES.append({"tool": "pip-audit (SCA)", "report": rel(pipa), "status": "EXÉCUTÉ"})
    else:
        missing("pip-audit", pipa, ["EQ-SEC-07"], "SCA")

    npm = R / "security" / "npm-audit-frontend-prod.json"
    if (d := load(npm)) is not None:
        v = d["metadata"]["vulnerabilities"]
        measure("EQ-SEC-07", "SCA", "npm audit", "Dépendances JavaScript livrées", v["total"] == 0,
                npm, f"{d['metadata']['dependencies']['total']} paquets, vulnérabilités={v['total']}")
        SOURCES.append({"tool": "npm audit (SCA)", "report": rel(npm), "status": "EXÉCUTÉ"})

    for fname, label in (("zap-report.json", "Scan baseline (passif) de l'application déployée"),
                         ("zap-api-report.json", "Scan actif de l'API à partir du contrat OpenAPI")):
        zap = R / "security" / "zap" / fname
        if (d := load(zap)) is None:
            missing("OWASP ZAP", zap, ["EQ-SEC-08"], "DAST")
            continue
        risk = defaultdict(int)
        for a in (a for site in d.get("site", []) for a in site.get("alerts", [])):
            risk[a["riskdesc"].split(" ")[0]] += 1
        measure("EQ-SEC-08", "DAST", "OWASP ZAP", label, risk["High"] == 0 and risk["Medium"] == 0,
                zap, ", ".join(f"{k}={v}" for k, v in sorted(risk.items())) or "aucune alerte")
        SOURCES.append({"tool": f"OWASP ZAP ({fname})", "report": rel(zap), "status": "EXÉCUTÉ"})

    cov = R / "quality" / "backend-coverage.xml"
    if cov.exists():
        root = ET.parse(cov).getroot()
        lines, branches = float(root.get("line-rate")) * 100, float(root.get("branch-rate")) * 100
        measure("EQ-MAI-01", "Qualité", "coverage.py (pytest-cov)", "Couverture backend",
                lines >= 80 and branches >= 80, cov, f"lignes {lines:.1f} %, branches {branches:.1f} %")
        SOURCES.append({"tool": "coverage.py", "report": rel(cov), "status": "EXÉCUTÉ"})
    else:
        missing("coverage.py", cov, ["EQ-MAI-01"], "Qualité")

    radon = R / "quality" / "radon-cc.json"
    if (d := load(radon)) is not None:
        blocks = [b for items in d.values() for b in items if isinstance(b, dict)]
        worst = max(blocks, key=lambda b: b["complexity"])
        mi = (R / "quality" / "radon-mi.txt").read_text(encoding="utf-8").splitlines()
        mi_a = sum(" - A " in line for line in mi)
        measure("EQ-MAI-02", "Qualité", "Radon + Ruff (mccabe)", "Complexité / maintenabilité",
                worst["complexity"] <= 10 and mi_a == len(mi), radon,
                f"{len(blocks)} blocs, max = {worst['complexity']} ({worst['name']}), "
                f"moyenne = {sum(b['complexity'] for b in blocks) / len(blocks):.2f}, "
                f"indice MI rang A : {mi_a}/{len(mi)} fichiers")
        SOURCES.append({"tool": "Radon", "report": rel(radon), "status": "EXÉCUTÉ"})

    ruff = R / "quality" / "ruff.json"
    if (d := load(ruff)) is not None:
        measure("EQ-MAI-03", "Qualité", "Ruff", "Lint Python (pycodestyle, bugbear, bandit, mccabe…)",
                len(d) == 0, ruff, f"{len(d)} problème(s)")
        SOURCES.append({"tool": "Ruff", "report": rel(ruff), "status": "EXÉCUTÉ"})

    tsc = R / "quality" / "tsc.log"
    if tsc.exists():
        content = tsc.read_text(encoding="utf-8").strip()
        measure("EQ-MAI-03", "Qualité", "TypeScript (strict)", "Vérification de types",
                "error" not in content.lower(), tsc, content or "0 erreur")

    jscpd = R / "quality" / "jscpd" / "jscpd-report.json"
    if (d := load(jscpd)) is not None:
        pct = d["statistics"]["total"]["percentage"]
        measure("EQ-MAI-04", "Qualité", "jscpd", "Duplication du code frontend", pct < 3, jscpd,
                f"{pct:.2f} % de lignes dupliquées ({d['statistics']['total']['clones']} clones)")
        SOURCES.append({"tool": "jscpd", "report": rel(jscpd), "status": "EXÉCUTÉ"})

    chaos = R / "reliability" / "chaos-summary.json"
    if (d := load(chaos)) is not None:
        mapping = {"C1": "EQ-FIA-03", "C2": "EQ-FIA-03", "C3": "EQ-FIA-06", "C4": "EQ-FIA-06"}
        for r in d["results"]:
            measure(mapping[r["scenario"]], "Fiabilité (chaos)", "Docker + script chaos",
                    f"{r['scenario']} — {r['check']}", r["passed"], chaos, r["detail"])
        SOURCES.append({"tool": "Chaos ciblé (Docker)", "report": rel(chaos), "status": "EXÉCUTÉ"})
    else:
        missing("Chaos ciblé", chaos, ["EQ-FIA-03", "EQ-FIA-06"], "Fiabilité (chaos)")

    port = R / "portability" / "portability-summary.json"
    if (d := load(port)) is not None:
        measure("EQ-POR-01", "Portabilité", "Docker Compose (clone vierge)",
                "Installation depuis un clone Git vierge", d["passed"], port,
                f"{d['checks_passed']}/{d['checks_passed'] + d['checks_failed']} vérifications, "
                f"opérationnel en {d['ready_seconds_including_build']} s (build inclus)")
        SOURCES.append({"tool": "Test de portabilité", "report": rel(port), "status": "EXÉCUTÉ"})
    else:
        missing("Test de portabilité", port, ["EQ-POR-01"], "Portabilité")


# ------------------------------------------------------------------ rendu
def icon(passed) -> str:
    return {True: "✅", False: "❌", None: "⚪"}[passed]


def verdict(items: list[dict]) -> tuple[str, bool | None]:
    if not items:
        return "⚠️ NON COUVERT", None
    executed = [i for i in items if i["passed"] is not None]
    ko = [i for i in executed if i["passed"] is False]
    if ko:
        return f"❌ {len(executed) - len(ko)}/{len(executed)}", False
    if not executed:
        return "⚪ non exécuté", None
    return f"✅ {len(executed)}/{len(executed)}", True


def render() -> str:
    now = datetime.now(timezone.utc).astimezone().strftime("%d/%m/%Y %H:%M")
    out = [
        "# Matrice de traçabilité — exigence ↔ test ↔ outil ↔ résultat",
        "",
        f"> **Document généré automatiquement** le {now} par `scripts/build_traceability.py` "
        "à partir des rapports d'exécution réels présents dans `reports/`. "
        "Ne pas modifier à la main : relancer `scripts/run_all_tests.sh`.",
        "",
        "Légende : ✅ réussi · ❌ échec · ⚪ non exécuté (outil indisponible, procédure fournie) · "
        "⚠️ exigence sans test. Le nombre `n/m` compte les cas de test (ou mesures) rattachés "
        "à l'exigence, toutes couches confondues.",
        "",
        "## 1. Vue d'ensemble",
        "",
        "| ID | Exigence | Caractéristique ISO 25010 | Couches de test | Outils | Résultat | Preuve(s) |",
        "|---|---|---|---|---|---|---|",
    ]
    stats = defaultdict(lambda: [0, 0])
    for rid, iso, text in REQUIREMENTS:
        items = EVIDENCE.get(rid, [])
        label, ok = verdict(items)
        stats[ISO[iso]][0] += 1
        stats[ISO[iso]][1] += ok is True
        layers = ", ".join(sorted({i["layer"] for i in items})) or "—"
        tools = ", ".join(sorted({re.sub(r" \(.*\)$", "", i["tool"]) for i in items})) or "—"
        proofs = "<br>".join(f"`{p}`" for p in sorted({i["proof"] for i in items})) or "—"
        out.append(f"| **{rid}** | {text} | {ISO[iso]} | {layers} | {tools} | {label} | {proofs} |")

    out += ["", "## 2. Synthèse par caractéristique ISO/IEC 25010", "",
            "| Caractéristique | Exigences | Exigences vérifiées ✅ |", "|---|---|---|"]
    for iso_label in ISO.values():
        total, ok = stats[iso_label]
        out.append(f"| {iso_label} | {total} | {ok}/{total} |")

    out += ["", "## 3. Exécutions par outil", "",
            "| Outil | Rapport | Statut | Total | Réussis | Échecs | Ignorés |", "|---|---|---|---|---|---|---|"]
    for s in SOURCES:
        out.append(f"| {s['tool']} | `{s['report']}` | {s['status']} | {s.get('total', '—')} | "
                   f"{s.get('passed', '—')} | {s.get('failed', '—')} | {s.get('skipped', '—')} |")

    out += ["", "## 4. Détail des tests par exigence", ""]
    for rid, iso, text in REQUIREMENTS:
        items = EVIDENCE.get(rid, [])
        label, _ = verdict(items)
        out += [f"<details><summary><b>{rid}</b> — {text} : {label}</summary>", "",
                "| | Couche | Outil | Test / mesure | Détail |", "|---|---|---|---|---|"]
        merged: dict[tuple, list] = {}
        for i in items:  # regroupe les variantes paramétrées / navigateurs d'un même test
            base = re.sub(r"\[\d+\]$|\[[^\]]*\]$", "", i["name"]) if i["tool"].startswith("pytest") else i["name"]
            merged.setdefault((i["layer"], i["tool"], base, i["detail"]), []).append(i["passed"])
        for (layer, tool, name, detail), results in sorted(merged.items()):
            agg = False if False in results else (None if all(r is None for r in results) else True)
            count = f" (×{len(results)})" if len(results) > 1 else ""
            safe = name.replace("|", "\\|")
            out.append(f"| {icon(agg)} | {layer} | {tool} | {safe}{count} | {detail} |")
        out += ["", "</details>", ""]
    return "\n".join(out)


def main() -> int:
    parse_junit(R / "tests" / "junit-backend.xml", "pytest", pytest_layer())
    parse_junit(R / "tests" / "junit-backend-postgres.xml", "pytest (PostgreSQL)",
                pytest_layer(" (PostgreSQL)"))
    parse_junit(R / "tests" / "junit-frontend-unit.xml", "Vitest",
                lambda c, b: ("Unitaire (frontend)", "Vitest"))
    parse_junit(R / "api" / "junit-newman.xml", "Postman/Newman",
                lambda c, b: ("API (contrat)", "Postman/Newman"))
    parse_junit(R / "e2e" / "junit-e2e.xml", "Playwright",
                lambda c, b: ("E2E / compatibilité", f"Playwright ({b or 'navigateur'})"))
    parse_measures()

    md = render()
    (ROOT / "docs").mkdir(exist_ok=True)
    (ROOT / "docs" / "MATRICE_TRACABILITE.md").write_text(md, encoding="utf-8")
    (R / "traceability.json").write_text(json.dumps(
        {"generated": datetime.now(timezone.utc).isoformat(), "sources": SOURCES,
         "requirements": {rid: EVIDENCE.get(rid, []) for rid, _, _ in REQUIREMENTS}},
        indent=2, ensure_ascii=False), encoding="utf-8")

    uncovered = [rid for rid, _, _ in REQUIREMENTS if not EVIDENCE.get(rid)]
    failed = [rid for rid, _, _ in REQUIREMENTS if verdict(EVIDENCE.get(rid, []))[1] is False]
    synth = ["# Synthèse des exécutions", "", f"Générée le {datetime.now().strftime('%d/%m/%Y %H:%M')}.", "",
             "| Outil | Statut | Total | Réussis | Échecs | Ignorés |", "|---|---|---|---|---|---|"]
    synth += [f"| {s['tool']} | {s['status']} | {s.get('total', '—')} | {s.get('passed', '—')} | "
              f"{s.get('failed', '—')} | {s.get('skipped', '—')} |" for s in SOURCES]
    synth += ["", f"- Exigences : {len(REQUIREMENTS)}",
              f"- Exigences sans test : {', '.join(uncovered) or 'aucune'}",
              f"- Exigences en échec : {', '.join(failed) or 'aucune'}"]
    (R / "SYNTHESE.md").write_text("\n".join(synth) + "\n", encoding="utf-8")
    print("\n".join(synth))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
