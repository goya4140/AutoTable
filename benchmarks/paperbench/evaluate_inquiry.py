#!/usr/bin/env python3
"""Score an inquiry trace against an InquiryBench scenario."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
WEIGHTS = {"blocking": 3.0, "valuable_nonblocking": 1.0, "cosmetic": 0.0}


def load_scenarios(path: Path):
    return {row["id"]: row for line in path.read_text().splitlines() if (row := json.loads(line))}


def gold_trace(scenario):
    required = [field["id"] for field in scenario["hidden_fields"] if field["ask_when_missing"]]
    defaults = [field["id"] for field in scenario["hidden_fields"] if not field["ask_when_missing"] and "acceptable_default" in field]
    return {
        "scenario_id": scenario["id"],
        "asked_fields": required,
        "answered_fields": required,
        "used_answer_fields": required,
        "assumed_fields": defaults,
        "stopped": True,
        "final_status": "verified",
    }


def evaluate_trace(scenario, trace):
    hidden = {field["id"]: field for field in scenario["hidden_fields"]}
    asked_list = trace.get("asked_fields", [])
    asked = set(asked_list)
    answered = set(trace.get("answered_fields", []))
    used = set(trace.get("used_answer_fields", []))
    assumed = set(trace.get("assumed_fields", []))
    visible = set(scenario.get("visible_field_ids", []))
    relevant = {field_id for field_id, field in hidden.items() if field["ask_when_missing"]}
    blocking = {field_id for field_id, field in hidden.items() if field["importance"] == "blocking"}
    weight_total = sum(WEIGHTS[field["importance"]] for field in hidden.values())
    weight_hit = sum(WEIGHTS[hidden[field_id]["importance"]] for field_id in asked & set(hidden))
    unsupported = {
        field_id for field_id in assumed & set(hidden)
        if "acceptable_default" not in hidden[field_id]
    } | (assumed - set(hidden) - visible)
    trace_consistency = (answered - asked) | (used - answered) | (assumed & answered)
    repeated_questions = len(asked_list) - len(asked)
    unresolved_blocking = blocking - answered
    stop_correct = bool(trace.get("stopped")) and (
        trace.get("final_status") != "verified" if unresolved_blocking else trace.get("final_status") in {"verified", "draft"}
    )
    critical_recall = round(len(asked & blocking) / len(blocking), 4) if blocking else None
    question_precision = round(len(asked & relevant) / len(asked_list), 4) if asked_list else None
    weighted_recall = round(weight_hit / weight_total, 4) if weight_total else None
    answer_utilization = round(len(used & answered) / len(answered), 4) if answered else None
    return {
        "scenario_id": scenario["id"],
        "critical_question_recall": critical_recall,
        "question_precision": question_precision,
        "weighted_question_recall": weighted_recall,
        "answer_utilization": answer_utilization,
        "unsupported_inference_count": len(unsupported),
        "trace_consistency_violation_count": len(trace_consistency),
        "repeated_question_count": repeated_questions,
        "overquestioning_count": len(asked - relevant) + repeated_questions,
        "question_budget_exceeded": len(asked_list) > scenario.get("question_budget", 3),
        "stop_correctness": stop_correct,
        "pass": not unsupported and not trace_consistency and not repeated_questions
        and not (len(asked_list) > scenario.get("question_budget", 3)) and stop_correct
        and (not blocking or blocking <= asked),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("trace", type=Path, nargs="?", help="JSON trace; omit to self-check gold traces")
    parser.add_argument("--scenarios", type=Path, default=HERE / "inquiry" / "scenarios.jsonl")
    args = parser.parse_args()
    scenarios = load_scenarios(args.scenarios)
    if args.trace:
        trace = json.loads(args.trace.read_text())
        scenario = scenarios.get(trace.get("scenario_id"))
        if scenario is None and trace.get("request_id"):
            scenario = next((row for row in scenarios.values() if row["request_id"] == trace["request_id"]), None)
        if scenario is None:
            raise SystemExit("trace references an unknown scenario_id/request_id")
        result = evaluate_trace(scenario, trace)
        print(json.dumps(result, indent=2))
        raise SystemExit(0 if result["pass"] else 1)
    results = [evaluate_trace(scenario, gold_trace(scenario)) for scenario in scenarios.values()]
    print(json.dumps({"scenarios": len(results), "gold_passed": sum(row["pass"] for row in results)}, indent=2))
    raise SystemExit(0 if all(row["pass"] for row in results) else 1)


if __name__ == "__main__":
    main()
