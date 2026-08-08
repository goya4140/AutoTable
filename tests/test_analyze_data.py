import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "skills/paper-table/scripts/analyze_data.py"


def test_analyzer_emits_bounded_structured_inquiry(tmp_path):
    data = tmp_path / "results.json"
    data.write_text(json.dumps([
        {"method": "A", "dataset": "D", "accuracy": 80.0},
        {"method": "B", "dataset": "D", "accuracy": 81.0},
    ]))
    result = subprocess.run([sys.executable, str(SCRIPT), str(data), "--json"], check=True, capture_output=True, text=True)
    report = json.loads(result.stdout)
    assert report["inquiry_state"] == "awaiting_author"
    assert 1 <= len(report["inquiry_plan"]) <= 3
    assert report["inquiry_plan"][0]["id"] == "metric_semantics"
    assert all({"id", "importance", "question", "reason"} <= set(item) for item in report["inquiry_plan"])
    assert report["design_proposal"]["primary_form"]
    assert report["visual_advice"]["actionable_changes"]


def test_context_suppresses_answered_question(tmp_path):
    data = tmp_path / "results.json"
    context = tmp_path / "context.json"
    data.write_text(json.dumps([{"method": "A", "score": 1}, {"method": "B", "score": 2}]))
    context.write_text(json.dumps({"metric_semantics": {"score": {"direction": "max", "unit": "%"}}}))
    result = subprocess.run([sys.executable, str(SCRIPT), str(data), "--json", "--context", str(context)], check=True, capture_output=True, text=True)
    report = json.loads(result.stdout)
    assert "metric_semantics" not in {item["id"] for item in report["inquiry_plan"]}


def test_detected_repeats_still_ask_uncertainty_semantics(tmp_path):
    data = tmp_path / "runs.json"
    data.write_text(json.dumps([
        {"method": "A", "seed": 0, "score": 1.0},
        {"method": "A", "seed": 1, "score": 1.2},
        {"method": "B", "seed": 0, "score": 2.0},
        {"method": "B", "seed": 1, "score": 2.2},
    ]))
    result = subprocess.run([sys.executable, str(SCRIPT), str(data), "--json"], check=True, capture_output=True, text=True)
    report = json.loads(result.stdout)
    assert "uncertainty_kind" in {item["id"] for item in report["inquiry_plan"]}
    assert report["visual_advice"]["questions"][0]["field_id"] == "uncertainty_source"
