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
    blocking = [field["id"] for field in scenario["hidden_fields"] if field["importance"] == "blocking"]
    return {
        "scenario_id": scenario["id"],
        "asked_fields": required,
        "answered_fields": required,
        "used_answer_fields": required,
        "assumed_fields": [],
        "stopped": True,
        "final_status": "verified" if set(blocking) <= set(required) else "draft",
    }


def evaluate_trace(scenario, trace):
    hidden = {field["id"]: field for field in scenario["hidden_fields"]}
    asked = set(trace.get("asked_fields", []))
    answered = set(trace.get("answered_fields", []))
    used = set(trace.get("used_answer_fields", []))
    assumed = set(trace.get("assumed_fields", []))
    relevant = {field_id for field_id, field in hidden.items() if field["ask_when_missing"]}
    blocking = {field_id for field_id, field in hidden.items() if field["importance"] == "blocking"}
    weight_total = sum(WEIGHTS[field["importance"]] for field in hidden.values())
    weight_hit = sum(WEIGHTS[hidden[field_id]["importance"]] for field_id in asked & set(hidden))
    unsupported = {
        field_id for field_id in assumed & set(hidden)
        if hidden[field_id]["importance"] != "cosmetic" and "default" not in hidden[field_id]
    }
    unresolved_blocking = blocking - answered
    stop_correct = bool(trace.get("stopped")) and (
        trace.get("final_status") != "verified" if unresolved_blocking else trace.get("final_status") in {"verified", "draft"}
    )
    precision_denominator = max(1, len(asked))
    return {
        "scenario_id": scenario["id"],
        "critical_question_recall": round(len(asked & blocking) / max(1, len(blocking)), 4),
        "question_precision": round(len(asked & relevant) / precision_denominator, 4),
        "weighted_question_recall": round(weight_hit / max(1.0, weight_total), 4),
        "answer_utilization": round(len(used & answered) / max(1, len(answered)), 4),
        "unsupported_inference_count": len(unsupported),
        "overquestioning_count": len(asked - relevant),
        "question_budget_exceeded": len(asked) > scenario.get("question_budget", 3),
        "stop_correctness": stop_correct,
        "pass": not unsupported and not (len(asked) > scenario.get("question_budget", 3)) and stop_correct
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
