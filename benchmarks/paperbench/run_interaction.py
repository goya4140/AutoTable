#!/usr/bin/env python3
"""Run InquiryBench as a real ask-answer-submit interaction."""
from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_response(response, request_id):
    if not isinstance(response, dict) or response.get("request_id") != request_id:
        raise ValueError("adapter response has the wrong request_id")
    if response.get("action") not in {"ask", "submit"}:
        raise ValueError("adapter action must be ask or submit")
    if response["action"] == "ask":
        questions = response.get("questions")
        if not isinstance(questions, list) or not questions:
            raise ValueError("ask action requires at least one question")
        for question in questions:
            if not isinstance(question, dict) or not isinstance(question.get("field_id"), str) or not str(question.get("text", "")).strip():
                raise ValueError("every question requires field_id and non-empty natural-language text")
    else:
        if not isinstance(response.get("candidate_spec"), dict) or not isinstance(response.get("resolved_fields"), dict):
            raise ValueError("submit action requires candidate_spec and resolved_fields")
        for key in ("used_answer_fields", "assumed_fields", "applied_answer_fields"):
            if not isinstance(response.get(key), list) or not all(isinstance(value, str) for value in response[key]):
                raise ValueError(f"submit action requires string array {key}")
        if response.get("final_status") not in {"verified", "draft", "blocked"}:
            raise ValueError("submit action requires a valid final_status")


def author_answers(questions, scenario):
    hidden = {field["id"]: field for field in scenario["hidden_fields"]}
    answers = []
    for question in questions:
        field_id = question["field_id"]
        if field_id in hidden:
            field = hidden[field_id]
            if field.get("answer_status", "available") == "available":
                answers.append({"field_id": field_id, "status": "answered", "value": field["value"]})
            else:
                answers.append({"field_id": field_id, "status": "unavailable"})
        else:
            answers.append({"field_id": field_id, "status": "unavailable"})
    return answers


def run_episode(public_request, scenario, adapter, output_dir, max_rounds=3):
    request_id = public_request["request_id"]
    output_dir.mkdir(parents=True, exist_ok=False)
    transcript = []
    final_response = None
    for turn in range(1, max_rounds + 1):
        turn_request = {
            "protocol": "paperbench-interaction-v1", "request_id": request_id, "turn": turn,
            "public_request": public_request, "transcript": transcript,
            "instruction": "Ask a compact question batch or submit the final table. Never claim an answer that is absent from the transcript.",
        }
        response = adapter(turn_request, output_dir, turn)
        validate_response(response, request_id)
        if response["action"] == "submit":
            final_response = response
            break
        answers = author_answers(response["questions"], scenario)
        transcript.append({"turn": turn, "questions": response["questions"], "answers": answers})
    if final_response is None:
        raise ValueError(f"{request_id}: adapter did not submit within {max_rounds} rounds")
    asked_fields = [question["field_id"] for event in transcript for question in event["questions"]]
    answered_fields = list(dict.fromkeys(answer["field_id"] for event in transcript for answer in event["answers"] if answer["status"] == "answered"))
    submission = {
        "request_id": request_id,
        "asked_fields": asked_fields,
        "answered_fields": answered_fields,
        "used_answer_fields": final_response["used_answer_fields"],
        "assumed_fields": final_response["assumed_fields"],
        "applied_answer_fields": final_response["applied_answer_fields"],
        "resolved_fields": final_response["resolved_fields"],
        "candidate_spec": final_response["candidate_spec"],
        "stopped": True,
        "final_status": final_response["final_status"],
    }
    renderer = load_module(f"paperbench_interaction_render_{request_id}", HERE.parents[1] / "skills/paper-table/scripts/render_table.py")
    latex, html = renderer.render(submission["candidate_spec"])
    (output_dir / "table.tex").write_text(latex)
    (output_dir / "table.html").write_text(html)
    (output_dir / "submission.json").write_text(json.dumps(submission, indent=2, ensure_ascii=False) + "\n")
    (output_dir / "interaction.json").write_text(json.dumps({"request_id": request_id, "transcript": transcript}, indent=2, ensure_ascii=False) + "\n")
    return submission


def subprocess_adapter(command, timeout):
    def invoke(turn_request, output_dir, turn):
        request_path = output_dir / f"turn-{turn}-request.json"
        response_path = output_dir / f"turn-{turn}-response.json"
        request_path.write_text(json.dumps(turn_request, indent=2, ensure_ascii=False) + "\n")
        completed = subprocess.run(
            [*command, str(request_path), str(response_path)], cwd=output_dir,
            capture_output=True, text=True, timeout=timeout,
        )
        (output_dir / f"turn-{turn}-adapter.log").write_text(completed.stdout + completed.stderr)
        if completed.returncode != 0:
            raise ValueError(f"adapter failed on turn {turn} with exit code {completed.returncode}")
        if not response_path.is_file():
            raise ValueError(f"adapter did not write turn-{turn}-response.json")
        return json.loads(response_path.read_text())
    return invoke


def run_all(public_dir, private_dir, output_dir, adapter, max_rounds=3):
    blind = load_module("paperbench_interaction_blind", HERE / "blind_protocol.py")
    manifest = blind.validate_public(public_dir)
    if manifest["mode"] != "inquiry":
        raise ValueError("interaction runner requires an inquiry episode")
    private = json.loads((private_dir / "manifest.json").read_text())
    if private.get("protocol") != blind.PROTOCOL or private.get("mode") != "inquiry" or private.get("public_manifest_sha256") != blind.digest(public_dir / "manifest.json"):
        raise ValueError("private manifest does not match public inquiry episode")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError(f"refusing to overwrite non-empty output directory: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    scenarios = {row["id"]: row for line in (HERE / "inquiry/scenarios.jsonl").read_text().splitlines() if (row := json.loads(line))}
    request_paths = {row["request_id"]: public_dir / row["path"] for row in manifest["requests"]}
    mapping = private.get("request_map", [])
    mapped_ids = [item.get("request_id") for item in mapping]
    if len(mapped_ids) != len(set(mapped_ids)) or set(mapped_ids) != set(request_paths):
        raise ValueError("private request mapping does not match public inquiry requests")
    if any(item.get("scenario_id") not in scenarios for item in mapping):
        raise ValueError("private request mapping references an unknown scenario")
    for item in mapping:
        request = json.loads(request_paths[item["request_id"]].read_text())
        run_episode(request, scenarios[item["scenario_id"]], adapter, output_dir / item["request_id"], max_rounds)
    return {"requests": len(private["request_map"]), "output_dir": str(output_dir)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--public-dir", type=Path, required=True)
    parser.add_argument("--private-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--max-rounds", type=int, default=3)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--adapter", nargs="+", required=True, help="command; runner appends TURN_REQUEST.json TURN_RESPONSE.json")
    args = parser.parse_args()
    try:
        result = run_all(args.public_dir, args.private_dir, args.output_dir, subprocess_adapter(args.adapter, args.timeout), args.max_rounds)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except (OSError, ValueError, KeyError, json.JSONDecodeError, subprocess.TimeoutExpired) as error:
        raise SystemExit(f"interaction runner failed: {error}")


if __name__ == "__main__":
    main()
