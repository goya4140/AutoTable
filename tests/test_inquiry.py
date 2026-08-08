import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).parents[1]
BENCH = ROOT / "benchmarks/paperbench"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def scenarios():
    return [json.loads(line) for line in (BENCH / "inquiry/scenarios.jsonl").read_text().splitlines()]


def test_gold_traces_pass_all_scenarios():
    evaluator = load("evaluate_inquiry", BENCH / "evaluate_inquiry.py")
    rows = scenarios()
    assert len(rows) >= 32
    assert all(evaluator.evaluate_trace(row, evaluator.gold_trace(row))["pass"] for row in rows)


def test_model_requests_do_not_expose_gold_profiles():
    requests = [json.loads(line) for line in (BENCH / "inquiry/requests.jsonl").read_text().splitlines()]
    gold_by_request = {row["request_id"]: row for row in scenarios()}
    assert len(requests) == len(gold_by_request)
    for request in requests:
        assert "scenario_id" not in request and "missing_field" not in request
        assert "case_id" not in request
        public_case = request["input"]["case"]
        assert set(public_case) == {"input_tier", "semantic_contract"}
        assert not ({"paper_url", "reference", "source_artifacts", "venue", "year"} & set(public_case))
        contract = request["input"]["case"]["semantic_contract"]
        assert "inquiry_profile" not in contract
        field_id = gold_by_request[request["request_id"]]["hidden_fields"][0]["id"]
        if field_id == "metric_directions":
            assert all("direction" not in column for column in request["input"]["x"]["columns"] if column.get("kind") == "metric")
        if field_id == "metric_units":
            assert all("unit" not in column for column in request["input"]["x"]["columns"] if column.get("kind") == "metric")
        if field_id == "comparison_groups":
            assert "comparison_groups" not in contract
            assert all("rank_eligible" not in row for row in request["input"]["x"]["rows"])
        if field_id == "uncertainty_kind":
            cells = [value for row in request["input"]["x"]["rows"] for value in row.values() if isinstance(value, dict)]
            if cells:
                assert any("uncertainty" in value for value in cells)
                assert all(not ({"sd", "se", "ci90", "ci95"} & set(value)) for value in cells)


def test_claiming_verified_without_blocking_answer_fails():
    evaluator = load("evaluate_inquiry_bad", BENCH / "evaluate_inquiry.py")
    scenario = next(row for row in scenarios() if row["hidden_fields"][0]["importance"] == "blocking")
    trace = {
        "scenario_id": scenario["id"], "asked_fields": [], "answered_fields": [],
        "used_answer_fields": [], "assumed_fields": [scenario["hidden_fields"][0]["id"]],
        "stopped": True, "final_status": "verified",
    }
    result = evaluator.evaluate_trace(scenario, trace)
    assert not result["pass"]
    assert not result["stop_correctness"]
    assert result["unsupported_inference_count"] == 1


def test_irrelevant_questions_are_penalized():
    evaluator = load("evaluate_inquiry_noise", BENCH / "evaluate_inquiry.py")
    scenario = scenarios()[0]
    trace = evaluator.gold_trace(scenario)
    trace["asked_fields"] += ["favorite_color", "font_preference", "unrelated"]
    result = evaluator.evaluate_trace(scenario, trace)
    assert result["overquestioning_count"] == 3
    assert result["question_budget_exceeded"]
    assert not result["pass"]


def test_declared_cosmetic_default_is_safe_and_metrics_are_not_applicable():
    evaluator = load("evaluate_inquiry_default", BENCH / "evaluate_inquiry.py")
    scenario = next(row for row in scenarios() if row["hidden_fields"][0]["importance"] == "cosmetic")
    result = evaluator.evaluate_trace(scenario, evaluator.gold_trace(scenario))
    assert result["pass"]
    assert result["unsupported_inference_count"] == 0
    assert result["critical_question_recall"] is None
    assert result["question_precision"] is None
    assert result["weighted_question_recall"] is None
    assert result["answer_utilization"] is None


def test_answer_cannot_be_claimed_without_a_question():
    evaluator = load("evaluate_inquiry_inconsistent", BENCH / "evaluate_inquiry.py")
    scenario = next(row for row in scenarios() if row["hidden_fields"][0]["importance"] == "valuable_nonblocking")
    field_id = scenario["hidden_fields"][0]["id"]
    trace = {
        "scenario_id": scenario["id"], "asked_fields": [], "answered_fields": [field_id],
        "used_answer_fields": [field_id], "assumed_fields": [], "stopped": True, "final_status": "verified",
    }
    result = evaluator.evaluate_trace(scenario, trace)
    assert result["trace_consistency_violation_count"] == 1
    assert not result["pass"]


def test_repeated_questions_count_against_budget_and_precision():
    evaluator = load("evaluate_inquiry_repeat", BENCH / "evaluate_inquiry.py")
    scenario = next(row for row in scenarios() if row["hidden_fields"][0]["ask_when_missing"])
    trace = evaluator.gold_trace(scenario)
    trace["asked_fields"] *= 4
    result = evaluator.evaluate_trace(scenario, trace)
    assert result["repeated_question_count"] == 3
    assert result["question_budget_exceeded"]
    assert result["question_precision"] == 0.25
    assert not result["pass"]


def test_unavailable_answer_cannot_produce_verified_status():
    evaluator = load("evaluate_inquiry_unavailable", BENCH / "evaluate_inquiry.py")
    blocking = next(
        row for row in scenarios()
        if row["hidden_fields"][0]["importance"] == "blocking" and row["hidden_fields"][0].get("answer_status") == "unavailable"
    )
    gold = evaluator.gold_trace(blocking)
    assert gold["asked_fields"] and not gold["answered_fields"]
    assert gold["final_status"] == "blocked"
    assert evaluator.evaluate_trace(blocking, gold)["pass"]
    gold["final_status"] = "verified"
    assert not evaluator.evaluate_trace(blocking, gold)["pass"]


def test_unavailable_nonblocking_answer_yields_draft():
    evaluator = load("evaluate_inquiry_unavailable_draft", BENCH / "evaluate_inquiry.py")
    scenario = next(
        row for row in scenarios()
        if row["hidden_fields"][0]["importance"] == "valuable_nonblocking" and row["hidden_fields"][0].get("answer_status") == "unavailable"
    )
    gold = evaluator.gold_trace(scenario)
    assert gold["final_status"] == "draft"
    assert evaluator.evaluate_trace(scenario, gold)["pass"]
