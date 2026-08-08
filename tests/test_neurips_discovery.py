import copy
import hashlib
import importlib.util
import json
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).parents[1]
BENCH = ROOT / "benchmarks/neurips-tables"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def test_next_caption_bounds_previous_table_crop():
    collector = load("neurips_collector", BENCH / "collect.py")
    found = [
        ("Table 1: Main results.", (20, 600, 200, 620)),
        ("Table 2: Ablation.", (20, 350, 200, 370)),
    ]
    first, second = collector.bounded_table_regions(found, 612, 792)
    assert first[1] >= 374 and first[3] == 625
    assert second[1] == 50 and second[3] == 375


def test_weak_annotation_separates_caption_from_narrative():
    annotator = load("neurips_annotator", BENCH / "annotate.py")
    base = {
        "id": "x", "year": 2024, "paper_sha256": "paper", "page": 1,
        "bbox_pdf_points": [0, 100, 612, 300], "region_text_sha256": "region",
        "crop_sha256": "crop", "region_text": "Table 1: Ablation. Base 1 Ours 2",
    }
    caption = annotator.annotate_record({**base, "caption": "Table 1: Ablation on the encoder."}, set())
    narrative = annotator.annotate_record({**base, "caption": "Table 1 shows that the encoder helps."}, set())
    assert caption["annotation"]["purpose"]["primary"] == "ablation"
    assert caption["eligibility"]["visual_structure_stress"]
    assert narrative["annotation"]["purpose"]["primary"] == "narrative_false_positive"
    assert not narrative["eligibility"]["visual_structure_stress"]


def test_committed_discovery_annotations_are_provenance_safe():
    annotator = load("neurips_annotation_data", BENCH / "annotate.py")
    validator = load("neurips_annotation_validator", BENCH / "validate_annotations.py")
    source = read_jsonl(BENCH / "index-diverse-2024.jsonl")
    annotations = read_jsonl(BENCH / "annotations-diverse-2024.jsonl")
    legacy = read_jsonl(BENCH / "index.jsonl")
    summary = json.loads((BENCH / "annotations-summary-2024.json").read_text())
    queue = read_jsonl(BENCH / "audit-queue-2024.jsonl")
    assert validator.validate(source, annotations, legacy, summary, False, queue) == []
    assert len(source) == 200 and len({record["paper_sha256"] for record in source}) == 30
    assert max(__import__("collections").Counter(record["paper_sha256"] for record in source).values()) == 8
    assert summary["partitions"]["prospective_stress_test"] == 121
    assert summary["paperbench_generation_pairs"] == 0
    assert all(not record["annotation"]["gold"] for record in annotations)
    assert len(queue) == 40 and all(record["review"]["status"] == "pending" for record in queue)


def test_validator_rejects_discovery_record_promoted_to_gold():
    validator = load("neurips_annotation_overclaim", BENCH / "validate_annotations.py")
    source = read_jsonl(BENCH / "index-diverse-2024.jsonl")
    annotations = read_jsonl(BENCH / "annotations-diverse-2024.jsonl")
    legacy = read_jsonl(BENCH / "index.jsonl")
    corrupted = copy.deepcopy(annotations)
    corrupted[0]["annotation"]["gold"] = True
    corrupted[0]["eligibility"]["paperbench_generation_pair"] = True
    errors = validator.validate(source, corrupted, legacy)
    assert any("gold=false" in error for error in errors)
    assert any("overclaims" in error for error in errors)


def test_discovery_evaluator_keeps_weak_metrics_diagnostic_only():
    evaluator = load("neurips_discovery_evaluator", BENCH / "evaluate_annotations.py")
    annotations = read_jsonl(BENCH / "annotations-diverse-2024.jsonl")
    predictions = []
    for record in annotations:
        if record["partition"] != "prospective_stress_test":
            continue
        form = record["annotation"]["recommended_form"]["primary"]
        predictions.append({
            "id": record["id"],
            "action": "exclude" if form == "exclude" else "route",
            "purpose": record["annotation"]["purpose"]["primary"],
            "recommended_form": form,
            "quality_flags": record["quality_flags"],
        })
    report = evaluator.score(annotations, predictions)
    assert report["coverage"] == 1.0
    assert report["form_routing"]["macro_f1"] == 1.0
    assert report["narrative_filter"]["f1"] == 1.0
    assert report["diagnostic_only"] and not report["gold"] and not report["leaderboard_eligible"]


def test_discovery_evaluator_penalizes_missing_predictions():
    evaluator = load("neurips_discovery_evaluator_missing", BENCH / "evaluate_annotations.py")
    annotations = read_jsonl(BENCH / "annotations-diverse-2024.jsonl")
    report = evaluator.score(annotations, [])
    assert report["coverage"] == 0.0
    assert report["form_routing"]["accuracy"] == 0.0
    assert len(report["missing_prediction_ids"]) == 121


def test_audit_sheet_checks_crop_hashes(tmp_path):
    renderer = load("neurips_audit_renderer", BENCH / "render_audit_sheet.py")
    crop = tmp_path / "crop.png"; Image.new("RGB", (120, 80), "white").save(crop)
    digest = hashlib.sha256(crop.read_bytes()).hexdigest()
    queue = [{
        "id": "case", "crop_path": "crop.png", "crop_sha256": digest,
        "weak_purpose": "main_results", "quality_flags": [],
    }]
    report = renderer.render(queue, tmp_path, tmp_path / "sheet.png", quality="unflagged", columns=1)
    assert report["records"] == 1 and (tmp_path / "sheet.png").exists()
    import pytest
    broken = copy.deepcopy(queue); broken[0]["crop_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="hash mismatch"):
        renderer.render(broken, tmp_path, tmp_path / "broken.png", quality="unflagged", columns=1)
