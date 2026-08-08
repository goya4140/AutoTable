#!/usr/bin/env python3
"""Build a raw per-instance PaperBench pair for SWT-Bench Table 4."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

from PIL import Image

from contracts import contract_for

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
CASE_ID = "neurips24-swtbench-models"
CASE_DIR = HERE / "cases" / CASE_ID
CODE_COMMIT = "dce4aeee1ea944c5de4f61e556dd2b94c118751d"
PAPER_URL = "https://proceedings.neurips.cc/paper_files/paper/2024/file/94f093b41fc2666376fb1f667fe282f3-Paper-Conference.pdf"
PAPER_SHA256 = "2a81c5bbcfa28e74448d8d10d0a3a455eca468f8ebf8c205694b4cf11515be9e"
FILTER_URL = f"https://raw.githubusercontent.com/logic-star-ai/swt-bench/{CODE_COMMIT}/dataset/filter_cases_lite.txt"
FILTER_SHA256 = "d88e9ecfc5ab4f68cb961cea90bf54ddcd7d8af58b77c15e7def8a5b2fd00f2b"
UTIL_URL = f"https://raw.githubusercontent.com/logic-star-ai/swt-bench/{CODE_COMMIT}/figures/util.py"
UTIL_SHA256 = "ac527c58095404c2875af1c400ffd69157b48d1a531ec79bb5a59dde55f4528f"
BASE_URL = "https://files.sri.inf.ethz.ch/swt-bench/run_instance_swt_logs/swt-lite"

ARTIFACTS = {
    "gold1.zip": ("validate-gold-1.zip", "04b358070eda134ea77c9c5f233b05a15a3a266c164eee6e1d5ac7c9e0d05ca7"),
    "mistral.zip": ("swea__mistral_large.zip", "62aa327b6b563c22d758798b5cfc2f4cbdb3ff3e24316e0b41f1e4ad5fba9a73"),
    "gpt4.zip": ("swea__gpt-4-1106-preview.zip", "6f66e5205314d8002c4115b1e3c82cbb0b7a71af57afad3a197a3f2a382bed26"),
    "sonnet.zip": ("swea__claude-3.5-sonnet.zip", "ce83c62d691b3ab1012342a3364c41397da0018fdf10d9f4844d3b69ab40b07c"),
    "gpt4omini.zip": ("swea__gpt-4o-mini-2024-07-18.zip", "f199cde36b870bae1c5adc5b74f3fce24b275c04243045ef31df9aa19a24c875"),
    "haiku.zip": ("swea__claude-3-haiku-20240307.zip", "3555bc8a9de875d8bcd107b49bc42df2dc8cee50a25fb2869041a86e07ca6cab"),
    "mixtral.zip": ("swea__together_mistralai_Mixtral-8x22B-Instruct-v0.1.zip", "7a96089027c39a05301b20c468651850cbb7ad18754dd31449cef45d6bace38e"),
}
MODELS = [
    ("Mistral Large 2", "mistral.zip"),
    ("GPT-4", "gpt4.zip"),
    ("Claude 3.5 Sonnet", "sonnet.zip"),
    ("GPT-4o mini", "gpt4omini.zip"),
    ("Claude 3.0 Haiku", "haiku.zip"),
    ("Mixtral 8x22B", "mixtral.zip"),
]


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fetch(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=120) as response:
        return response.read()


def materialize_artifact(directory: Path, local_name: str, remote_name: str, expected_sha256: str) -> Path:
    path = directory / local_name
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(fetch(f"{BASE_URL}/{remote_name}"))
    if digest(path.read_bytes()) != expected_sha256:
        raise ValueError(f"source artifact hash mismatch: {path}")
    return path


def read_reports(path: Path, excluded: set[str]) -> dict[str, dict]:
    reports = {}
    with zipfile.ZipFile(path) as archive:
        for member in archive.namelist():
            if not member.endswith("/report.json"):
                continue
            payload = json.loads(archive.read(member))
            if len(payload) != 1:
                raise ValueError(f"unexpected report shape in {member}")
            instance_id, report = next(iter(payload.items()))
            if instance_id in excluded:
                continue
            if instance_id in reports:
                raise ValueError(f"duplicate report for {instance_id} in {path}")
            reports[instance_id] = report
    return reports


def added(report: dict, category: str) -> set[str]:
    return set(report["tests_pred"][category]) - set(report["tests_base"][category])


def well_formed(report: dict | None) -> bool:
    if not report or "tests_pred" not in report:
        return False
    original = sum(len(tests) for tests in report["tests_base"].values())
    predicted = sum(len(tests) for tests in report["tests_pred"].values())
    return predicted >= 0.1 * original


def build_raw(artifact_dir: Path, filter_bytes: bytes) -> dict:
    excluded = set(filter_bytes.decode().splitlines())
    if len(excluded) != 24:
        raise ValueError("expected 24 paper-time SWT-Bench Lite exclusions")
    gold = read_reports(artifact_dir / "gold1.zip", excluded)
    universe = sorted(gold)
    coverage_eligible = sorted(
        instance_id for instance_id, report in gold.items()
        if report.get("coverage_delta_gold") is not None
    )
    if len(universe) != 276 or len(coverage_eligible) != 273:
        raise ValueError("unexpected SWT-Bench Lite or coverage denominator")

    observations = []
    for model, local_name in MODELS:
        reports = read_reports(artifact_dir / local_name, excluded)
        unknown = set(reports) - set(universe)
        if unknown:
            raise ValueError(f"{model} contains unknown instances: {sorted(unknown)[:3]}")
        for instance_id in universe:
            report = reports.get(instance_id)
            has_tests = bool(report and "tests_pred" in report)
            observations.append({
                "model": model,
                "instance_id": instance_id,
                "well_formed": well_formed(report),
                "success": bool(report and report.get("resolved")),
                "fail_to_any": bool(has_tests and (added(report, "FAIL_TO_PASS") | added(report, "FAIL_TO_FAIL"))),
                "coverage_delta": float(report.get("coverage_delta_pred") or 0.0) if report and instance_id in coverage_eligible else 0.0,
                "report_present": report is not None,
            })
    return {
        "schema_version": "paper-table-observations-v1",
        "unit_of_observation": "SWT-Bench Lite instance",
        "observation_id_key": "instance_id",
        "group_keys": [{"key": "model", "label": "Model"}],
        "denominators": {"all_instances": universe, "coverage_eligible_instances": coverage_eligible},
        "metrics": [
            {"key": "well_formed", "label": "Well-formed (W)", "field": "well_formed", "operation": "rate", "denominator": "all_instances", "scale": 100, "direction": "max", "unit": "%", "precision": 1},
            {"key": "success", "label": "Success (S)", "field": "success", "operation": "rate", "denominator": "all_instances", "scale": 100, "direction": "max", "unit": "%", "precision": 1},
            {"key": "fail_to_any", "label": "Fail-to-any (F→×)", "field": "fail_to_any", "operation": "rate", "denominator": "all_instances", "scale": 100, "direction": "max", "unit": "%", "precision": 1},
            {"key": "coverage", "label": "Change coverage (ΔC all)", "field": "coverage_delta", "operation": "sum_over_count", "denominator": "coverage_eligible_instances", "scale": 100, "direction": "max", "unit": "%", "precision": 1},
        ],
        "observations": observations,
        "title": "SWT-Bench model comparison",
        "label": "tab:swtbench-models",
        "caption": "SWE-Agent performance with different underlying language models on 276 SWT-Bench Lite instances.",
        "emphasis": {"best": "bold", "second": "none", "scope": "all"},
        "notes": [
            "W, S, and F→× use all 276 benchmark instances; change coverage uses the 273 instances with countable gold coverage.",
            "All values are percentages and are recomputed from the authors' per-instance evaluation reports; higher is better.",
        ],
        "provenance": {"source_commit": CODE_COMMIT, "aggregation_status": "raw_recomputed"},
    }


def render_reference(pdf_bytes: bytes, artifact_dir: Path, output: Path) -> None:
    pdf_path = artifact_dir / "paper.pdf"
    pdf_path.write_bytes(pdf_bytes)
    pdftoppm = os.environ.get("PAPERTABLE_PDFTOPPM") or shutil.which("pdftoppm")
    if not pdftoppm:
        raise RuntimeError("pdftoppm is required; set PAPERTABLE_PDFTOPPM to its path")
    prefix = artifact_dir / "paper-page8"
    subprocess.run([pdftoppm, "-f", "8", "-l", "8", "-singlefile", "-png", "-r", "180", str(pdf_path), str(prefix)], check=True)
    Image.open(prefix.with_suffix(".png")).crop((700, 1160, 1340, 1538)).save(output, optimize=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-dir", type=Path, default=ROOT / "tmp/paperbench/swtbench")
    args = parser.parse_args()
    args.artifact_dir.mkdir(parents=True, exist_ok=True)
    for local_name, (remote_name, expected_sha256) in ARTIFACTS.items():
        materialize_artifact(args.artifact_dir, local_name, remote_name, expected_sha256)
    filter_bytes = fetch(FILTER_URL)
    util_bytes = fetch(UTIL_URL)
    paper_bytes = fetch(PAPER_URL)
    if digest(filter_bytes) != FILTER_SHA256 or digest(util_bytes) != UTIL_SHA256:
        raise SystemExit("pinned SWT-Bench aggregation code changed")
    if digest(paper_bytes) != PAPER_SHA256:
        raise SystemExit("official SWT-Bench paper hash changed")

    raw = build_raw(args.artifact_dir, filter_bytes)
    raw_bytes = (json.dumps(raw, indent=2, ensure_ascii=False) + "\n").encode()
    sys.path.insert(0, str(ROOT / "skills/paper-table/scripts"))
    from aggregate_observations import aggregate

    spec = aggregate(raw)
    spec["provenance"]["raw_input_sha256"] = digest(raw_bytes)
    expected_rows = {
        "Mistral Large 2": [76.1, 16.3, 51.4, 23.0],
        "GPT-4": [87.3, 15.9, 48.2, 26.5],
        "Claude 3.5 Sonnet": [67.8, 12.3, 59.1, 30.3],
        "GPT-4o mini": [71.0, 9.8, 36.2, 20.9],
        "Claude 3.0 Haiku": [20.3, 2.5, 6.9, 3.0],
        "Mixtral 8x22B": [3.3, 0.7, 1.8, 0.9],
    }
    for row in spec["rows"]:
        actual = [row[key] for key in ("well_formed", "success", "fail_to_any", "coverage")]
        if actual != expected_rows[row["model"]]:
            raise ValueError(f"raw reports no longer reproduce Table 4 for {row['model']}: {actual}")

    CASE_DIR.mkdir(parents=True, exist_ok=True)
    (CASE_DIR / "raw_outcomes.json").write_bytes(raw_bytes)
    render_reference(paper_bytes, args.artifact_dir, CASE_DIR / "y_reference.png")
    source_artifacts = [
        {"role": "paper-time exclusion list", "url": FILTER_URL, "sha256": FILTER_SHA256, "commit": CODE_COMMIT, "redistributed": False},
        {"role": "paper-time aggregation definitions", "url": UTIL_URL, "sha256": UTIL_SHA256, "commit": CODE_COMMIT, "redistributed": False},
    ]
    for local_name, (remote_name, expected_sha256) in ARTIFACTS.items():
        source_artifacts.append({"role": "gold per-instance reports" if local_name == "gold1.zip" else "model per-instance reports", "url": f"{BASE_URL}/{remote_name}", "sha256": expected_sha256, "redistributed": False})
    source_artifacts.append({"role": "published paper", "url": PAPER_URL, "sha256": PAPER_SHA256})
    case = {
        "schema_version": "2.0",
        "id": CASE_ID,
        "task": "experimental-data-to-publication-table",
        "input_tier": "raw_runs",
        "venue": "NeurIPS",
        "year": 2024,
        "paper_url": PAPER_URL,
        "input": {"path": "raw_outcomes.json", "sha256": digest(raw_bytes), "schema": "paper-table-observations-v1"},
        "reference": {"page": 8, "table": "Table 4", "image": "y_reference.png", "sha256": digest((CASE_DIR / "y_reference.png").read_bytes())},
        "source_artifacts": source_artifacts,
        "transformation": {
            "selection": "Table 4: six SWE-Agent language-model backbones and four reported metrics",
            "aggregation": "W/S/F→× are per-instance rates over n=276; ΔC is the sum of per-instance coverage deltas divided by 273 countable gold-coverage instances",
            "rounding": "one decimal, matching the paper",
            "missing_reports": "a missing per-instance report contributes false/zero, exactly as the paper-time evaluator's fixed-denominator calculation",
        },
        "license": {"code_and_evaluation_artifacts": "MIT", "paper_excerpt": "source publication terms control", "source_terms_control": True},
        "semantic_contract": contract_for(CASE_ID),
        "limitations": [
            "The source ZIP archives are hash-pinned but not redistributed; the committed raw_outcomes.json contains only derived per-instance booleans and coverage deltas needed for Table 4.",
            "These are deterministic per-instance evaluations, not repeated stochastic seeds, so no run-to-run uncertainty is estimated.",
        ],
    }
    ratings = {"schema_version": "1.0", "status": "unrated", "required_raters": 3, "dimensions": ["typography", "visual_hierarchy", "readability", "claim_salience", "overall_aesthetics"], "ratings": []}
    (CASE_DIR / "case.json").write_text(json.dumps(case, indent=2, ensure_ascii=False) + "\n")
    (CASE_DIR / "x.json").write_text(json.dumps(spec, indent=2, ensure_ascii=False) + "\n")
    ratings_path = CASE_DIR / "ratings.json"
    if not ratings_path.exists():
        ratings_path.write_text(json.dumps(ratings, indent=2, ensure_ascii=False) + "\n")
    print(CASE_DIR)


if __name__ == "__main__":
    main()
