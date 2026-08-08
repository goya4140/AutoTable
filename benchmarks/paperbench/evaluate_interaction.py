#!/usr/bin/env python3
"""Verify that author answers are reflected in an interactive table submission."""
from __future__ import annotations

import json
from pathlib import Path

UNCERTAINTY_KEYS = ("sd", "se", "ci90", "ci95")


def metric_columns(spec):
    return {column["key"]: column for column in spec.get("columns", []) if column.get("kind") == "metric"}


def uncertainty_signature(spec, row_key):
    metrics = metric_columns(spec)
    signature = {}
    for row in spec.get("rows", []):
        for key in metrics:
            cell = row.get(key)
            if isinstance(cell, dict):
                kinds = [kind for kind in UNCERTAINTY_KEYS if kind in cell]
                if kinds:
                    signature[(row.get(row_key), key)] = (kinds, [cell[kind] for kind in kinds])
    return signature


def comparison_signature(spec, row_key):
    return {
        "emphasis": spec.get("emphasis", {}),
        "rows": {row.get(row_key): row.get("rank_eligible", True) for row in spec.get("rows", [])},
    }


def field_output_gate(field_id, expected, candidate, reference, case):
    row_key = case["semantic_contract"]["row_identity_key"]
    if field_id == "claim":
        return isinstance(candidate.get("caption"), str) and candidate["caption"].strip() == str(expected).strip()
    if field_id == "metric_directions":
        columns = metric_columns(candidate)
        return all(columns.get(key, {}).get("direction") == value for key, value in expected.items())
    if field_id == "metric_units":
        columns = metric_columns(candidate)
        return all(columns.get(key, {}).get("unit") == value for key, value in expected.items())
    if field_id == "uncertainty_kind":
        return uncertainty_signature(candidate, row_key) == uncertainty_signature(reference, row_key)
    if field_id == "independent_run_count":
        if not isinstance(expected, int):
            return True
        explanatory_text = " ".join([candidate.get("caption", ""), *candidate.get("notes", [])])
        return str(expected) in explanatory_text
    if field_id == "comparison_groups":
        return comparison_signature(candidate, row_key) == comparison_signature(reference, row_key)
    if field_id in {"target_width", "color_preference"}:
        return True
    return False


def evaluate_interaction(scenario, submission, reference, case):
    candidate = submission.get("candidate_spec")
    resolved = submission.get("resolved_fields")
    applied = set(submission.get("applied_answer_fields", []))
    answered = set(submission.get("answered_fields", []))
    assumed = set(submission.get("assumed_fields", []))
    if not isinstance(candidate, dict) or not isinstance(resolved, dict):
        return {"passed": False, "answer_application_rate": 0.0, "fields": [], "reason": "candidate_spec or resolved_fields missing"}
    results = []
    for field in scenario["hidden_fields"]:
        field_id = field["id"]
        if field.get("answer_status", "available") == "unavailable":
            safely_unresolved = field_id not in resolved and field_id not in applied and submission.get("final_status") != "verified"
            results.append({
                "field_id": field_id, "source": "unavailable",
                "resolution_match": field_id not in resolved,
                "application_declared": field_id not in applied,
                "output_recovered": None,
                "applicable": False,
                "passed": safely_unresolved,
            })
            continue
        used_answer = field_id in answered
        expected = field["value"] if used_answer else field.get("acceptable_default")
        resolution_match = field_id in resolved and resolved[field_id] == expected
        application_declared = field_id in applied if used_answer else field_id in assumed
        output_recovered = field_output_gate(field_id, expected, candidate, reference, case) if expected is not None else False
        passed = resolution_match and application_declared and output_recovered
        results.append({
            "field_id": field_id,
            "source": "author_answer" if used_answer else "declared_default",
            "resolution_match": resolution_match,
            "application_declared": application_declared,
            "output_recovered": output_recovered,
            "applicable": True,
            "passed": passed,
        })
    applicable = [result for result in results if result["applicable"]]
    passed_count = sum(result["passed"] for result in applicable)
    return {"passed": all(result["passed"] for result in results), "answer_application_rate": round(passed_count / len(applicable), 4) if applicable else None, "fields": results}


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("scenario", type=Path)
    parser.add_argument("submission", type=Path)
    parser.add_argument("reference", type=Path)
    parser.add_argument("case", type=Path)
    args = parser.parse_args()
    report = evaluate_interaction(
        json.loads(args.scenario.read_text()), json.loads(args.submission.read_text()),
        json.loads(args.reference.read_text()), json.loads(args.case.read_text()),
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
