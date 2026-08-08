#!/usr/bin/env python3
"""Run PaperTable-Controlled mutations through the semantic contract evaluator."""
from __future__ import annotations

import json
from pathlib import Path

from build_controlled import OUTPUT, apply_mutation
from contract_eval import evaluate

HERE = Path(__file__).resolve().parent


def main() -> None:
    if not OUTPUT.exists():
        raise SystemExit("run build_controlled.py first")
    results = []
    for line in OUTPUT.read_text().splitlines():
        descriptor = json.loads(line)
        case_dir = HERE / "cases" / descriptor["base_case_id"]
        case = json.loads((case_dir / "case.json").read_text())
        reference = json.loads((case_dir / "x.json").read_text())
        candidate = apply_mutation(reference, descriptor["mutation"])
        report = evaluate(reference, candidate, case)
        detected = descriptor["expected_violation_category"] in report["category_counts"]
        results.append({**descriptor, "detected": detected, "category_counts": report["category_counts"]})
    passed = sum(result["detected"] for result in results)
    summary = {"passed": passed == len(results), "detected": passed, "total": len(results), "results": results}
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
