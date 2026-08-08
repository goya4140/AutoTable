#!/usr/bin/env python3
"""Prepare, freeze, and score leakage-resistant PaperBench submissions."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import secrets
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROTOCOL = "paperbench-blind-v1"
MAX_SUBMISSION_FILE_BYTES = 10_000_000


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def require_empty(path: Path) -> None:
    if path.exists() and any(path.iterdir()):
        raise ValueError(f"refusing to overwrite non-empty directory: {path}")
    path.mkdir(parents=True, exist_ok=True)


def fresh_request_id(existing: set[str]) -> str:
    while True:
        request_id = secrets.token_hex(8)
        if request_id not in existing:
            existing.add(request_id)
            return request_id


def public_generation_request(case: dict, x: dict, request_id: str) -> dict:
    contract = json.loads(json.dumps(case["semantic_contract"]))
    contract.pop("inquiry_profile", None)
    safe_x = json.loads(json.dumps(x))
    safe_x.get("provenance", {}).pop("source_commit", None)
    safe_x.get("provenance", {}).pop("source", None)
    return {
        "request_id": request_id,
        "task": "Generate an editable publication table from the experiment data. Do not retrieve or inspect the published reference table.",
        "input_tier": case["input_tier"],
        "x": safe_x,
        "semantic_contract": contract,
        "required_outputs": ["submission.json", "table.tex"],
    }


def prepare(mode: str, public_dir: Path, private_dir: Path) -> dict:
    public_resolved, private_resolved = public_dir.resolve(), private_dir.resolve()
    if public_resolved == private_resolved or public_resolved.is_relative_to(private_resolved) or private_resolved.is_relative_to(public_resolved):
        raise ValueError("public and private directories must be distinct and non-nested")
    require_empty(public_dir)
    require_empty(private_dir)
    public_rows = []
    private_rows = []
    issued_ids: set[str] = set()
    if mode == "generation":
        for case_path in sorted((HERE / "cases").glob("*/case.json")):
            case = json.loads(case_path.read_text())
            x = json.loads((case_path.parent / "x.json").read_text())
            request_id = fresh_request_id(issued_ids)
            request = public_generation_request(case, x, request_id)
            request_path = public_dir / "requests" / f"{request_id}.json"
            write_json(request_path, request)
            public_rows.append({"request_id": request_id, "path": str(request_path.relative_to(public_dir)), "sha256": digest(request_path)})
            private_rows.append({"request_id": request_id, "case_id": case["id"]})
    elif mode == "inquiry":
        requests = [json.loads(line) for line in (HERE / "inquiry/requests.jsonl").read_text().splitlines()]
        scenarios = {row["request_id"]: row for line in (HERE / "inquiry/scenarios.jsonl").read_text().splitlines() if (row := json.loads(line))}
        for request in requests:
            source_request_id = request["request_id"]
            request_id = fresh_request_id(issued_ids)
            request = json.loads(json.dumps(request))
            request["request_id"] = request_id
            request_path = public_dir / "requests" / f"{request_id}.json"
            write_json(request_path, request)
            public_rows.append({"request_id": request_id, "path": str(request_path.relative_to(public_dir)), "sha256": digest(request_path)})
            private_rows.append({"request_id": request_id, "scenario_id": scenarios[source_request_id]["id"]})
    else:
        raise ValueError(f"unsupported mode: {mode}")
    public_manifest = {"schema_version": "1.0", "protocol": PROTOCOL, "mode": mode, "requests": public_rows}
    write_json(public_dir / "manifest.json", public_manifest)
    private_manifest = {
        "schema_version": "1.0", "protocol": PROTOCOL, "mode": mode,
        "public_manifest_sha256": digest(public_dir / "manifest.json"), "request_map": private_rows,
    }
    write_json(private_dir / "manifest.json", private_manifest)
    return {"mode": mode, "requests": len(public_rows)}


def validate_submission(mode: str, request_id: str, submission_dir: Path) -> None:
    submission_path = submission_dir / "submission.json"
    if not submission_path.is_file():
        raise ValueError(f"{request_id}: submission.json missing")
    submission = json.loads(submission_path.read_text())
    if submission.get("request_id") != request_id:
        raise ValueError(f"{request_id}: request_id mismatch")
    if mode == "generation":
        if not isinstance(submission.get("candidate_spec"), dict):
            raise ValueError(f"{request_id}: candidate_spec missing")
        if not isinstance(submission["candidate_spec"].get("columns"), list) or not isinstance(submission["candidate_spec"].get("rows"), list):
            raise ValueError(f"{request_id}: candidate_spec must contain column and row arrays")
        if not (submission_dir / "table.tex").is_file():
            raise ValueError(f"{request_id}: table.tex missing")
    elif mode == "inquiry":
        required = {"asked_fields", "answered_fields", "used_answer_fields", "assumed_fields", "stopped", "final_status"}
        if required - submission.keys():
            raise ValueError(f"{request_id}: incomplete inquiry trace")
        for key in ("asked_fields", "answered_fields", "used_answer_fields", "assumed_fields"):
            if not isinstance(submission[key], list) or not all(isinstance(value, str) for value in submission[key]):
                raise ValueError(f"{request_id}: {key} must be a string array")
        if not isinstance(submission["stopped"], bool) or submission["final_status"] not in {"verified", "draft", "blocked"}:
            raise ValueError(f"{request_id}: invalid stop state")
        if "candidate_spec" in submission:
            if not isinstance(submission["candidate_spec"], dict) or not isinstance(submission.get("resolved_fields"), dict):
                raise ValueError(f"{request_id}: interactive candidate requires candidate_spec and resolved_fields")
            if not isinstance(submission.get("applied_answer_fields"), list):
                raise ValueError(f"{request_id}: interactive candidate requires applied_answer_fields")
            if not (submission_dir / "table.tex").is_file():
                raise ValueError(f"{request_id}: interactive candidate requires table.tex")


def validate_public(public_dir: Path) -> dict:
    manifest_path = public_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("protocol") != PROTOCOL or manifest.get("mode") not in {"generation", "inquiry"}:
        raise ValueError("invalid public protocol manifest")
    expected_paths = {row["path"] for row in manifest["requests"]}
    all_paths = list(public_dir.rglob("*"))
    if any(path.is_symlink() for path in all_paths):
        raise ValueError("symlinks are forbidden in the public episode")
    actual_paths = {str(path.relative_to(public_dir)) for path in all_paths if path.is_file()}
    if actual_paths != expected_paths | {"manifest.json"}:
        raise ValueError("public request files differ from manifest")
    for row in manifest["requests"]:
        if digest(public_dir / row["path"]) != row["sha256"]:
            raise ValueError(f"public request changed after preparation: {row['request_id']}")
    return manifest


def snapshot_files(root: Path) -> list[dict]:
    rows = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"symlinks are forbidden in submissions: {path}")
        if path.is_file():
            if path.stat().st_size > MAX_SUBMISSION_FILE_BYTES:
                raise ValueError(f"submission file exceeds {MAX_SUBMISSION_FILE_BYTES} bytes: {path}")
            rows.append({"path": str(path.relative_to(root)), "sha256": digest(path), "bytes": path.stat().st_size})
    return rows


def freeze(public_dir: Path, submissions_dir: Path, frozen_manifest: Path) -> dict:
    if frozen_manifest.exists():
        raise ValueError(f"refusing to overwrite frozen manifest: {frozen_manifest}")
    public_manifest_path = public_dir / "manifest.json"
    public_manifest = validate_public(public_dir)
    expected = {row["request_id"] for row in public_manifest["requests"]}
    children = list(submissions_dir.iterdir())
    if any(not path.is_dir() or path.is_symlink() for path in children):
        raise ValueError("submission root may contain request directories only")
    actual = {path.name for path in children}
    if actual != expected:
        raise ValueError(f"submission IDs differ: missing={sorted(expected-actual)}, extra={sorted(actual-expected)}")
    submissions = []
    for request_id in sorted(expected):
        submission_dir = submissions_dir / request_id
        validate_submission(public_manifest["mode"], request_id, submission_dir)
        submissions.append({"request_id": request_id, "files": snapshot_files(submission_dir)})
    frozen = {
        "schema_version": "1.0", "protocol": PROTOCOL, "mode": public_manifest["mode"],
        "public_manifest_sha256": digest(public_manifest_path),
        "frozen_at": datetime.now(timezone.utc).isoformat(), "submissions": submissions,
    }
    write_json(frozen_manifest, frozen)
    return {"mode": public_manifest["mode"], "submissions": len(submissions), "frozen_manifest": str(frozen_manifest)}


def verify_frozen(public_dir: Path, submissions_dir: Path, frozen_manifest: Path) -> dict:
    frozen = json.loads(frozen_manifest.read_text())
    validate_public(public_dir)
    if frozen["public_manifest_sha256"] != digest(public_dir / "manifest.json"):
        raise ValueError("public manifest changed after preparation")
    expected_ids = {row["request_id"] for row in frozen["submissions"]}
    children = list(submissions_dir.iterdir())
    if any(not path.is_dir() or path.is_symlink() for path in children):
        raise ValueError("submission root changed after freeze")
    actual_ids = {path.name for path in children}
    if actual_ids != expected_ids:
        raise ValueError("submission directories changed after freeze")
    for row in frozen["submissions"]:
        root = submissions_dir / row["request_id"]
        if snapshot_files(root) != row["files"]:
            raise ValueError(f"submission changed after freeze: {row['request_id']}")
    return frozen


def rendered_numeric_gate(reference: dict, latex: str) -> dict:
    evaluator = load_module("paperbench_render_eval", HERE / "evaluate.py")
    if "\\midrule" not in latex or "\\bottomrule" not in latex:
        return {"passed": False, "reason": "expected booktabs body boundaries"}
    expected_cells = [value for value in evaluator.cells(reference) if value is not None]
    expected = evaluator.numbers(expected_cells) + evaluator.source_body_numbers(reference)
    body = latex.split("\\midrule", 1)[1].split("\\bottomrule", 1)[0]
    recall, precision, hallucinated = evaluator.multiset_recall(expected, evaluator.number_tokens(body))
    return {"passed": recall == 1 and precision == 1 and hallucinated == 0, "numeric_recall": recall, "numeric_precision": precision, "hallucinated_numeric_tokens": hallucinated}


def macro(rows: list[dict], key: str):
    values = [row[key] for row in rows if row.get(key) is not None]
    return round(sum(values) / len(values), 4) if values else None


def score(public_dir: Path, private_dir: Path, submissions_dir: Path, frozen_manifest: Path) -> dict:
    frozen = verify_frozen(public_dir, submissions_dir, frozen_manifest)
    private = json.loads((private_dir / "manifest.json").read_text())
    if private.get("protocol") != PROTOCOL or private.get("mode") != frozen["mode"] or private["public_manifest_sha256"] != frozen["public_manifest_sha256"]:
        raise ValueError("private manifest does not match the public episode")
    mapping = {row["request_id"]: row for row in private["request_map"]}
    frozen_ids = {row["request_id"] for row in frozen["submissions"]}
    if set(mapping) != frozen_ids:
        raise ValueError("private request mapping does not match frozen submissions")
    rows = []
    if frozen["mode"] == "generation":
        contract_eval = load_module("paperbench_blind_contract", HERE / "contract_eval.py")
        for request_id, item in sorted(mapping.items()):
            case_dir = HERE / "cases" / item["case_id"]
            case = json.loads((case_dir / "case.json").read_text())
            reference = json.loads((case_dir / "x.json").read_text())
            submission_dir = submissions_dir / request_id
            candidate = json.loads((submission_dir / "submission.json").read_text())["candidate_spec"]
            contract = contract_eval.evaluate(reference, candidate, case)
            render = rendered_numeric_gate(reference, (submission_dir / "table.tex").read_text())
            rows.append({"request_id": request_id, "scientific_gate": contract["passed_scientific_gate"], "full_contract_gate": contract["passed_full_contract"], "rendered_numeric_gate": render["passed"], "category_counts": contract["category_counts"], "render_metrics": render})
        summary = {"mode": "generation", "cases": len(rows), "scientific_pass_rate": macro(rows, "scientific_gate"), "full_contract_pass_rate": macro(rows, "full_contract_gate"), "rendered_numeric_pass_rate": macro(rows, "rendered_numeric_gate"), "passed": all(row["scientific_gate"] and row["full_contract_gate"] and row["rendered_numeric_gate"] for row in rows), "results": rows}
    elif frozen["mode"] == "inquiry":
        inquiry_eval = load_module("paperbench_blind_inquiry", HERE / "evaluate_inquiry.py")
        interaction_eval = load_module("paperbench_blind_interaction", HERE / "evaluate_interaction.py")
        contract_eval = load_module("paperbench_blind_interaction_contract", HERE / "contract_eval.py")
        scenarios = inquiry_eval.load_scenarios(HERE / "inquiry/scenarios.jsonl")
        for request_id, item in sorted(mapping.items()):
            submission_dir = submissions_dir / request_id
            trace = json.loads((submission_dir / "submission.json").read_text())
            scenario = scenarios[item["scenario_id"]]
            row = inquiry_eval.evaluate_trace(scenario, trace)
            row["interaction_output_gate"] = None
            if "candidate_spec" in trace:
                case_dir = HERE / "cases" / scenario["case_id"]
                case = json.loads((case_dir / "case.json").read_text())
                reference = json.loads((case_dir / "x.json").read_text())
                interaction = interaction_eval.evaluate_interaction(scenario, trace, reference, case)
                contract = contract_eval.evaluate(reference, trace["candidate_spec"], case)
                render = rendered_numeric_gate(reference, (submission_dir / "table.tex").read_text())
                row.update({
                    "interaction_output_gate": interaction["passed"],
                    "answer_application_rate": interaction["answer_application_rate"],
                    "interaction_fields": interaction["fields"],
                    "scientific_gate": contract["passed_scientific_gate"],
                    "full_contract_gate": contract["passed_full_contract"],
                    "rendered_numeric_gate": render["passed"],
                })
                row["pass"] = row["pass"] and interaction["passed"] and contract["passed_scientific_gate"] and contract["passed_full_contract"] and render["passed"]
            rows.append(row)
        summary = {"mode": "inquiry", "cases": len(rows), "safe_pass_rate": macro(rows, "pass"), "critical_question_recall": macro(rows, "critical_question_recall"), "question_precision": macro(rows, "question_precision"), "weighted_question_recall": macro(rows, "weighted_question_recall"), "answer_utilization": macro(rows, "answer_utilization"), "answer_application_rate": macro(rows, "answer_application_rate"), "interaction_output_pass_rate": macro(rows, "interaction_output_gate"), "unsupported_inference_total": sum(row["unsupported_inference_count"] for row in rows), "trace_consistency_violation_total": sum(row["trace_consistency_violation_count"] for row in rows), "repeated_question_total": sum(row["repeated_question_count"] for row in rows), "overquestioning_total": sum(row["overquestioning_count"] for row in rows), "stop_correctness_rate": macro(rows, "stop_correctness"), "passed": all(row["pass"] for row in rows), "results": rows}
    else:
        raise ValueError(f"unsupported frozen mode: {frozen['mode']}")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    prepare_parser = sub.add_parser("prepare")
    prepare_parser.add_argument("--mode", choices=["generation", "inquiry"], required=True)
    prepare_parser.add_argument("--public-dir", type=Path, required=True)
    prepare_parser.add_argument("--private-dir", type=Path, required=True)
    freeze_parser = sub.add_parser("freeze")
    freeze_parser.add_argument("--public-dir", type=Path, required=True)
    freeze_parser.add_argument("--submissions-dir", type=Path, required=True)
    freeze_parser.add_argument("--frozen-manifest", type=Path, required=True)
    score_parser = sub.add_parser("score")
    score_parser.add_argument("--public-dir", type=Path, required=True)
    score_parser.add_argument("--private-dir", type=Path, required=True)
    score_parser.add_argument("--submissions-dir", type=Path, required=True)
    score_parser.add_argument("--frozen-manifest", type=Path, required=True)
    score_parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "prepare":
            result = prepare(args.mode, args.public_dir, args.private_dir)
        elif args.command == "freeze":
            result = freeze(args.public_dir, args.submissions_dir, args.frozen_manifest)
        else:
            result = score(args.public_dir, args.private_dir, args.submissions_dir, args.frozen_manifest)
            if args.report:
                write_json(args.report, result)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        raise SystemExit(f"blind protocol failed: {error}")


if __name__ == "__main__":
    main()
