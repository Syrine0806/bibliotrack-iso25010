"""Vérifie les seuils de performance à partir du CSV produit par Locust (EQ-PERF-01).

Seuils : p95 global < 500 ms, taux d'erreur < 1 %. Code de sortie ≠ 0 si non respectés.
Écrit aussi un résumé JSON exploité par la matrice de traçabilité.
"""

import csv
import json
import sys
from pathlib import Path

P95_MAX_MS = 500
ERROR_RATE_MAX = 0.01


def main(stats_csv: str) -> int:
    with Path(stats_csv).open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    agg = next(r for r in rows if r["Name"] == "Aggregated")
    requests = int(agg["Request Count"])
    failures = int(agg["Failure Count"])
    p95 = float(agg["95%"])
    error_rate = failures / requests if requests else 1.0
    summary = {
        "requests": requests,
        "failures": failures,
        "error_rate": round(error_rate, 5),
        "rps": round(float(agg["Requests/s"]), 1),
        "median_ms": float(agg["50%"]),
        "p95_ms": p95,
        "p99_ms": float(agg["99%"]),
        "max_ms": float(agg["Max Response Time"]),
        "thresholds": {"p95_ms": P95_MAX_MS, "error_rate": ERROR_RATE_MAX},
        "per_endpoint_p95_ms": {
            r["Name"]: float(r["95%"]) for r in rows if r["Name"] != "Aggregated"
        },
    }
    summary["passed"] = p95 < P95_MAX_MS and error_rate < ERROR_RATE_MAX
    out = Path(stats_csv).with_name("performance-summary.json")
    out.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print("RÉSULTAT :", "CONFORME" if summary["passed"] else "NON CONFORME")
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "../reports/performance/locust_stats.csv"))
