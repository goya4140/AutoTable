#!/usr/bin/env python3
"""Validate provenance, partitions, and claims of the weak discovery benchmark."""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load_annotator():
    spec = importlib.util.spec_from_file_location("neurips_table_annotator", HERE / "annotate.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate(source, annotations, legacy, summary=None, require_crops=False, audit_queue=None):
    annotator = load_annotator()
    errors = []
    if len(source) != len(annotations):
        errors.append(f"record count mismatch: source={len(source)} annotations={len(annotations)}")
    source_ids = [record.get("id") for record in source]
    annotation_ids = [record.get("id") for record in annotations]
    if source_ids != annotation_ids:
        errors.append("annotation IDs/order must exactly match source index")
    if len(source_ids) != len(set(source_ids)):
        errors.append("source IDs are not unique")
    legacy_papers = {record["paper_sha256"] for record in legacy}
    partition_papers = {}
    for index, (raw, annotation) in enumerate(zip(source, annotations)):
        prefix = f"{index}:{raw.get('id')}"
        if annotation.get("schema_version") != annotator.SCHEMA_VERSION:
            errors.append(f"{prefix} schema version mismatch")
        if annotation.get("source_record_sha256") != annotator.canonical_hash(raw):
            errors.append(f"{prefix} source record hash mismatch")
        if annotation.get("source_region_text_sha256") != raw.get("region_text_sha256") or annotation.get("source_crop_sha256") != raw.get("crop_sha256"):
            errors.append(f"{prefix} source artifact hash mismatch")
        expected_partition = "legacy_development" if raw.get("paper_sha256") in legacy_papers else "prospective_stress_test"
        if annotation.get("partition") != expected_partition:
            errors.append(f"{prefix} wrong prospective partition")
        partition_papers.setdefault(annotation.get("partition"), set()).add(raw.get("paper_sha256"))
        weak = annotation.get("annotation", {})
        if weak.get("tier") != "weak_rule_based" or weak.get("gold") is not False:
            errors.append(f"{prefix} weak annotations must explicitly set gold=false")
        if weak.get("purpose", {}).get("primary") not in annotator.PURPOSES:
            errors.append(f"{prefix} unknown purpose")
        if weak.get("recommended_form", {}).get("primary") not in annotator.FORMS:
            errors.append(f"{prefix} unknown form")
        eligibility = annotation.get("eligibility", {})
        if eligibility.get("numeric_reconstruction") or eligibility.get("paperbench_generation_pair") or eligibility.get("human_aesthetic_gold"):
            errors.append(f"{prefix} discovery record overclaims evaluation eligibility")
        if require_crops:
            crop = Path(raw.get("crop_path", ""))
            if not crop.exists():
                errors.append(f"{prefix} crop missing: {crop}")
    partitions = list(partition_papers)
    for index, left in enumerate(partitions):
        for right in partitions[index + 1:]:
            overlap = partition_papers[left] & partition_papers[right]
            if overlap:
                errors.append(f"paper leakage between {left} and {right}: {len(overlap)}")
    prospective_records = sum(record.get("partition") == "prospective_stress_test" for record in annotations)
    prospective_papers = len(partition_papers.get("prospective_stress_test", set()))
    if prospective_records < 50 or prospective_papers < 10:
        errors.append("prospective stress partition is too small")
    if summary is not None and summary != annotator.release_summary(annotations, source, legacy):
        errors.append("summary does not match annotations")
    if audit_queue is not None:
        source_by_id = {record["id"]: record for record in source}
        annotation_by_id = {record["id"]: record for record in annotations}
        queue_ids = [record.get("id") for record in audit_queue]
        if len(queue_ids) != len(set(queue_ids)):
            errors.append("audit queue IDs are not unique")
        if len(audit_queue) < 20:
            errors.append("audit queue is too small")
        for record in audit_queue:
            record_id = record.get("id"); raw = source_by_id.get(record_id); annotation = annotation_by_id.get(record_id)
            if not raw or not annotation:
                errors.append(f"audit queue references unknown ID: {record_id}"); continue
            if annotation["partition"] != "prospective_stress_test" or record.get("partition") != "prospective_stress_test":
                errors.append(f"audit queue must use prospective records: {record_id}")
            if record.get("crop_sha256") != raw.get("crop_sha256"):
                errors.append(f"audit crop hash mismatch: {record_id}")
            review = record.get("review", {})
            if review.get("status") != "pending" or any(review.get(key) is not None for key in ("is_table", "purpose", "recommended_form", "crop_clean", "notes", "reviewer", "reviewed_at")):
                errors.append(f"unreviewed audit queue must remain pending/null: {record_id}")
        if len({record.get("weak_purpose") for record in audit_queue}) < 6:
            errors.append("audit queue lacks purpose diversity")
        if not any(record.get("quality_flags") for record in audit_queue) or not any(not record.get("quality_flags") for record in audit_queue):
            errors.append("audit queue must cover both flagged and unflagged crops")
    return errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("annotations", type=Path)
    parser.add_argument("--legacy-development-index", type=Path, required=True)
    parser.add_argument("--summary", type=Path)
    parser.add_argument("--audit-queue", type=Path)
    parser.add_argument("--require-crops", action="store_true")
    args = parser.parse_args()
    annotator = load_annotator()
    source = annotator.read_jsonl(args.source)
    annotations = annotator.read_jsonl(args.annotations)
    legacy = annotator.read_jsonl(args.legacy_development_index)
    summary = json.loads(args.summary.read_text()) if args.summary else None
    audit_queue = annotator.read_jsonl(args.audit_queue) if args.audit_queue else None
    errors = validate(source, annotations, legacy, summary, args.require_crops, audit_queue)
    report = {"passed": not errors, "source_records": len(source), "annotations": len(annotations), "errors": errors}
    print(json.dumps(report, indent=2, ensure_ascii=False))
    raise SystemExit(0 if not errors else 1)


if __name__ == "__main__":
    main()
