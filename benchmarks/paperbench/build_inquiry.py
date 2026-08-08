#!/usr/bin/env python3
"""Build InquiryBench scenarios by hiding one author-provided field at a time."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASES = HERE / "cases"
OUT = HERE / "inquiry" / "scenarios.jsonl"
REQUESTS = HERE / "inquiry" / "requests.jsonl"


def delete_path(node, parts):
    if not parts:
        return
    head, *tail = parts
    if head == "*":
        children = node.values() if isinstance(node, dict) else node if isinstance(node, list) else []
        for child in list(children):
            delete_path(child, tail)
    elif isinstance(node, dict) and head in node:
        if tail:
            delete_path(node[head], tail)
        else:
            del node[head]


def neutralize_uncertainty(spec):
    for row in spec.get("rows", []):
        for value in row.values():
            if isinstance(value, dict):
                keys = [key for key in ("sd", "se", "ci90", "ci95") if key in value]
                if len(keys) == 1:
                    value["uncertainty"] = value.pop(keys[0])


def masked_request(case, x, field, request_id):
    contract = copy.deepcopy(case["semantic_contract"])
    contract.pop("inquiry_profile", None)
    safe_x = copy.deepcopy(x)
    safe_x.get("provenance", {}).pop("source", None)
    safe_x.get("provenance", {}).pop("source_commit", None)
    if field["id"] == "uncertainty_kind":
        neutralize_uncertainty(safe_x)
    payload = {"case": {"input_tier": case["input_tier"], "semantic_contract": contract}, "x": safe_x}
    for path in field.get("mask_paths", []):
        if field["id"] == "uncertainty_kind" and path.startswith("x.rows."):
            continue
        normalized = f"case.{path}" if path.startswith("semantic_contract.") else path
        delete_path(payload, normalized.split("."))
    return {
        "request_id": request_id,
        "task": "Inspect the experiment input, ask only scientifically necessary author questions, and then produce a verified table or a clearly labeled draft.",
        "question_budget": 3,
        "input": payload,
    }


def scenarios_and_requests():
    requests = []
    for case_dir in sorted(CASES.iterdir()):
        if not case_dir.is_dir():
            continue
        case = json.loads((case_dir / "case.json").read_text())
        x = json.loads((case_dir / "x.json").read_text())
        fields = case["semantic_contract"]["inquiry_profile"]["fields"]
        all_ids = [field["id"] for field in fields]
        for field in fields:
            scenario_id = f"{case['id']}--missing-{field['id']}"
            request_id = hashlib.sha256(scenario_id.encode()).hexdigest()[:16]
            scenario = {
                "id": scenario_id,
                "request_id": request_id,
                "case_id": case["id"],
                "hidden_fields": [field],
                "visible_field_ids": [field_id for field_id in all_ids if field_id != field["id"]],
                "question_budget": 3,
            }
            requests.append(masked_request(case, x, field, request_id))
            yield scenario, requests[-1]


def main():
    pairs = list(scenarios_and_requests())
    rows = [pair[0] for pair in pairs]
    requests = [pair[1] for pair in pairs]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows))
    REQUESTS.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in requests))
    print(f"wrote {len(rows)} gold scenarios to {OUT} and sanitized requests to {REQUESTS}")


if __name__ == "__main__":
    main()
