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


def build_generation_submissions(public_dir, submissions_dir):
    renderer = load("blind_renderer", ROOT / "skills/paper-table/scripts/render_table.py")
    aggregators = {
        "paper-table-observations-v1": load("blind_observation_aggregator", ROOT / "skills/paper-table/scripts/aggregate_observations.py"),
        "paper-table-runs-v1": load("blind_run_aggregator", ROOT / "skills/paper-table/scripts/aggregate_runs.py"),
    }
    manifest = json.loads((public_dir / "manifest.json").read_text())
    for item in manifest["requests"]:
        request = json.loads((public_dir / item["path"]).read_text())
        request_id = request["request_id"]
        destination = submissions_dir / request_id
        destination.mkdir(parents=True)
        candidate = request["x"]
        if candidate.get("schema_version") in aggregators:
            candidate = aggregators[candidate["schema_version"]].aggregate(candidate)
        latex, html = renderer.render(candidate)
        (destination / "table.tex").write_text(latex)
        (destination / "table.html").write_text(html)
        (destination / "submission.json").write_text(json.dumps({"request_id": request_id, "candidate_spec": candidate}))


def test_generation_blind_protocol_freezes_and_detects_tampering(tmp_path):
    blind = load("blind_generation", BENCH / "blind_protocol.py")
    public_dir, private_dir = tmp_path / "public", tmp_path / "private"
    submissions_dir, frozen = tmp_path / "submissions", tmp_path / "frozen.json"
    result = blind.prepare("generation", public_dir, private_dir)
    expected = len(list((BENCH / "cases").glob("*/case.json")))
    assert result["requests"] == expected
    public_text = "".join(path.read_text() for path in (public_dir / "requests").glob("*.json"))
    assert '"reference"' not in public_text
    assert '"paper_url"' not in public_text
    assert '"inquiry_profile"' not in public_text
    requests = [json.loads(path.read_text()) for path in (public_dir / "requests").glob("*.json")]
    assert any(request["x"].get("schema_version") == "paper-table-observations-v1" for request in requests)
    assert any("rows" in request["x"] for request in requests)
    build_generation_submissions(public_dir, submissions_dir)
    blind.freeze(public_dir, submissions_dir, frozen)
    report = blind.score(public_dir, private_dir, submissions_dir, frozen)
    assert report["passed"]
    assert report["scientific_pass_rate"] == 1.0
    first = next(submissions_dir.glob("*/table.tex"))
    first.write_text(first.read_text() + "% changed after freeze\n")
    with pytest.raises(ValueError, match="changed after freeze"):
        blind.score(public_dir, private_dir, submissions_dir, frozen)


def test_inquiry_blind_protocol_keeps_gold_private(tmp_path):
    blind = load("blind_inquiry", BENCH / "blind_protocol.py")
    inquiry = load("blind_inquiry_eval", BENCH / "evaluate_inquiry.py")
    public_dir, private_dir = tmp_path / "public", tmp_path / "private"
    submissions_dir, frozen = tmp_path / "submissions", tmp_path / "frozen.json"
    result = blind.prepare("inquiry", public_dir, private_dir)
    expected = len((BENCH / "inquiry/scenarios.jsonl").read_text().splitlines())
    assert result["requests"] == expected
    assert "hidden_fields" not in "".join(path.read_text() for path in (public_dir / "requests").glob("*.json"))
    private = json.loads((private_dir / "manifest.json").read_text())
    scenarios = inquiry.load_scenarios(BENCH / "inquiry/scenarios.jsonl")
    for item in private["request_map"]:
        request_id = item["request_id"]
        destination = submissions_dir / request_id
        destination.mkdir(parents=True)
        trace = inquiry.gold_trace(scenarios[item["scenario_id"]])
        trace["request_id"] = request_id
        (destination / "submission.json").write_text(json.dumps(trace))
    blind.freeze(public_dir, submissions_dir, frozen)
    report = blind.score(public_dir, private_dir, submissions_dir, frozen)
    assert report["passed"]
    assert report["safe_pass_rate"] == 1.0
    assert report["unsupported_inference_total"] == 0


def test_blind_protocol_rejects_nested_public_private_dirs(tmp_path):
    blind = load("blind_paths", BENCH / "blind_protocol.py")
    with pytest.raises(ValueError, match="non-nested"):
        blind.prepare("generation", tmp_path / "episode", tmp_path / "episode/private")


def test_blind_protocol_rejects_unmanifested_public_file(tmp_path):
    blind = load("blind_public_contamination", BENCH / "blind_protocol.py")
    public_dir, private_dir = tmp_path / "public", tmp_path / "private"
    blind.prepare("generation", public_dir, private_dir)
    (public_dir / "unexpected.txt").write_text("possible leaked context")
    with pytest.raises(ValueError, match="differ from manifest"):
        blind.validate_public(public_dir)


def test_each_blind_episode_randomly_remaps_public_request_ids(tmp_path):
    blind = load("blind_random_ids", BENCH / "blind_protocol.py")
    public_a, private_a = tmp_path / "public-a", tmp_path / "private-a"
    public_b, private_b = tmp_path / "public-b", tmp_path / "private-b"
    blind.prepare("inquiry", public_a, private_a)
    blind.prepare("inquiry", public_b, private_b)
    ids_a = {row["request_id"] for row in json.loads((public_a / "manifest.json").read_text())["requests"]}
    ids_b = {row["request_id"] for row in json.loads((public_b / "manifest.json").read_text())["requests"]}
    static_ids = {json.loads(line)["request_id"] for line in (BENCH / "inquiry/requests.jsonl").read_text().splitlines()}
    assert ids_a.isdisjoint(ids_b)
    assert ids_a.isdisjoint(static_ids)
    assert ids_b.isdisjoint(static_ids)
