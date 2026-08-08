#!/usr/bin/env python3
"""Deterministic protocol baseline for the interactive InquiryBench runner."""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

QUESTIONS = {
    "claim": "What single scientific claim should the table communicate?",
    "metric_directions": "For each metric, is higher or lower better?",
    "metric_units": "What unit should be displayed for each metric?",
    "uncertainty_kind": "Are the reported uncertainty values SD, SE, or confidence intervals?",
    "independent_run_count": "How many independent runs contributed to each reported result?",
    "comparison_groups": "Which rows are scientifically comparable, and which rows must be excluded from ranking?",
    "target_width": "Should the table fit a single column, full text width, or page width?",
}


def metrics(x):
    return [column for column in x.get("columns", []) if column.get("kind") == "metric"]


def detect_missing(public_request):
    payload = public_request["input"]
    contract = payload["case"]["semantic_contract"]
    x = payload["x"]
    if "claim" not in contract:
        return "claim"
    if any("direction" not in column for column in metrics(x)):
        return "metric_directions"
    if any("unit" not in column for column in metrics(x)):
        return "metric_units"
    if "uncertainty_kind" not in contract.get("statistics", {}):
        return "uncertainty_kind"
    if "independent_run_count" not in contract.get("statistics", {}):
        return "independent_run_count"
    if "comparison_groups" not in contract:
        return "comparison_groups"
    if "target_width" not in contract.get("rendering_constraints", {}):
        return "target_width"
    if "color_mode" not in contract.get("rendering_constraints", {}):
        return "color_preference"
    return None


def restore(candidate, field_id, value):
    if field_id == "claim":
        candidate["caption"] = value
    elif field_id in {"metric_directions", "metric_units"}:
        key = "direction" if field_id == "metric_directions" else "unit"
        for column in metrics(candidate):
            column[key] = value[column["key"]]
    elif field_id == "uncertainty_kind":
        kind = value if value in {"sd", "se", "ci90", "ci95"} else None
        for row in candidate.get("rows", []):
            for cell in row.values():
                if isinstance(cell, dict) and "uncertainty" in cell:
                    uncertainty = cell.pop("uncertainty")
                    if kind:
                        cell[kind] = uncertainty
    elif field_id == "independent_run_count" and isinstance(value, int):
        candidate.setdefault("notes", []).append(f"Results summarize {value} independent runs.")
    elif field_id == "comparison_groups":
        excluded = {row for group in value for row in group.get("excluded_row_values", [])}
        for row in candidate.get("rows", []):
            row.pop("rank_eligible", None)
            if row.get("method") in excluded:
                row["rank_eligible"] = False


def submit(turn_request, answers=None, default_field=None):
    public_request = turn_request["public_request"]
    candidate = copy.deepcopy(public_request["input"]["x"])
    resolved = {}
    used = []
    assumed = []
    applied = []
    unavailable = False
    for answer in answers or []:
        if answer.get("status") != "answered":
            unavailable = True
            continue
        field_id, value = answer["field_id"], answer["value"]
        resolved[field_id] = value
        used.append(field_id)
        applied.append(field_id)
        restore(candidate, field_id, value)
    if default_field == "color_preference":
        resolved[default_field] = "grayscale_safe"
        assumed.append(default_field)
    uncertainty_kind = public_request["input"]["case"]["semantic_contract"].get("statistics", {}).get("uncertainty_kind")
    unavailable_status = "draft" if uncertainty_kind in {"none", None} else "blocked"
    return {
        "request_id": turn_request["request_id"], "action": "submit",
        "candidate_spec": candidate, "resolved_fields": resolved,
        "used_answer_fields": used, "assumed_fields": assumed,
        "applied_answer_fields": applied, "final_status": unavailable_status if unavailable else "verified",
    }


def respond(turn_request):
    transcript = turn_request["transcript"]
    if transcript:
        answers = [answer for event in transcript for answer in event["answers"]]
        return submit(turn_request, answers=answers)
    field_id = detect_missing(turn_request["public_request"])
    if field_id == "color_preference":
        return submit(turn_request, default_field=field_id)
    if field_id:
        return {
            "request_id": turn_request["request_id"], "action": "ask",
            "questions": [{"field_id": field_id, "text": QUESTIONS[field_id]}],
        }
    return submit(turn_request)


def main():
    if len(sys.argv) != 3:
        raise SystemExit("usage: rule_inquiry_adapter.py TURN_REQUEST.json TURN_RESPONSE.json")
    request_path, response_path = map(Path, sys.argv[1:])
    response_path.write_text(json.dumps(respond(json.loads(request_path.read_text())), indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
