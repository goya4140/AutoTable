import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
BENCH = ROOT / "benchmarks/paperbench"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_rule_adapter_completes_all_interactive_scenarios(tmp_path):
    blind = load("interaction_blind", BENCH / "blind_protocol.py")
    runner = load("interaction_runner", BENCH / "run_interaction.py")
    baseline = load("interaction_baseline", BENCH / "baselines/rule_inquiry_adapter.py")
    public_dir, private_dir = tmp_path / "public", tmp_path / "private"
    submissions, frozen = tmp_path / "submissions", tmp_path / "frozen.json"
    blind.prepare("inquiry", public_dir, private_dir)
    adapter = lambda request, _output, _turn: baseline.respond(request)
    runner.run_all(public_dir, private_dir, submissions, adapter)
    blind.freeze(public_dir, submissions, frozen)
    report = blind.score(public_dir, private_dir, submissions, frozen)
    assert report["passed"]
    assert report["cases"] == 32
    assert report["critical_question_recall"] == 1.0
    assert report["question_precision"] == 1.0
    assert report["answer_application_rate"] == 1.0
    assert report["interaction_output_pass_rate"] == 1.0


def test_declaring_answer_usage_without_changing_table_fails(tmp_path):
    runner = load("interaction_runner_bad", BENCH / "run_interaction.py")
    evaluator = load("interaction_evaluator_bad", BENCH / "evaluate_interaction.py")
    requests = [json.loads(line) for line in (BENCH / "inquiry/requests.jsonl").read_text().splitlines()]
    scenarios = [json.loads(line) for line in (BENCH / "inquiry/scenarios.jsonl").read_text().splitlines()]
    scenario = next(row for row in scenarios if row["hidden_fields"][0]["id"] == "metric_directions")
    request = next(row for row in requests if row["request_id"] == scenario["request_id"])
    field_id = scenario["hidden_fields"][0]["id"]

    def dishonest_adapter(turn_request, _output, _turn):
        if not turn_request["transcript"]:
            return {"request_id": request["request_id"], "action": "ask", "questions": [{"field_id": field_id, "text": "Is each metric higher- or lower-is-better?"}]}
        value = turn_request["transcript"][0]["answers"][0]["value"]
        return {
            "request_id": request["request_id"], "action": "submit",
            "candidate_spec": request["input"]["x"], "resolved_fields": {field_id: value},
            "used_answer_fields": [field_id], "assumed_fields": [],
            "applied_answer_fields": [field_id], "final_status": "verified",
        }

    submission = runner.run_episode(request, scenario, dishonest_adapter, tmp_path / "dishonest")
    case_dir = BENCH / "cases" / scenario["case_id"]
    report = evaluator.evaluate_interaction(
        scenario, submission, json.loads((case_dir / "x.json").read_text()), json.loads((case_dir / "case.json").read_text())
    )
    assert not report["passed"]
    assert not report["fields"][0]["output_recovered"]


def test_adapter_question_requires_natural_language():
    runner = load("interaction_runner_validation", BENCH / "run_interaction.py")
    with pytest.raises(ValueError, match="natural-language"):
        runner.validate_response({"request_id": "r", "action": "ask", "questions": [{"field_id": "claim", "text": ""}]}, "r")


def test_simulated_author_does_not_answer_irrelevant_field():
    runner = load("interaction_runner_author", BENCH / "run_interaction.py")
    scenario = json.loads((BENCH / "inquiry/scenarios.jsonl").read_text().splitlines()[0])
    answers = runner.author_answers([{"field_id": "unrelated", "text": "What is your favorite font?"}], scenario)
    assert answers == [{"field_id": "unrelated", "status": "unavailable"}]
