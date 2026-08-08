#!/usr/bin/env python3
"""Build conservative weak labels for real-paper table discovery records."""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import re
from pathlib import Path

SCHEMA_VERSION = "1.0"
GENERATOR = "papertable-weak-structure-v1"
PURPOSES = {
    "ablation", "dataset_statistics", "efficiency", "experimental_configuration",
    "main_results", "method_taxonomy", "narrative_false_positive", "robustness",
    "sensitivity", "other",
}
FORMS = {
    "ablation_table", "comparison_table", "descriptive_table", "efficiency_table",
    "experimental_configuration_table", "sensitivity_table", "taxonomy_table", "exclude",
}
CAPTION_RE = re.compile(r"^Table\s+[A-Z]?\d+\s*:", re.I)
TABLE_MENTION_RE = re.compile(r"\bTable\s+([A-Z]?\d+)\b", re.I)
NUMBER_RE = re.compile(r"(?<![A-Za-z])[-+]?\d+(?:\.\d+)?%?")
CITATION_RE = re.compile(r"\[\d+(?:\s*[,;-]\s*\d+)*\]")
CONTINUATION_RE = re.compile(r"\b(?:a|an|and|at|for|in|of|on|the|to|under|using|with|different|various)$", re.I)

RULES = [
    ("ablation", ("ablation", "without ", "removing ", "removed ", "component contribution")),
    ("dataset_statistics", ("dataset statistics", "statistics of", "dataset descriptions", "number of nodes", "number of edges", "data statistics")),
    ("efficiency", ("runtime", "latency", "throughput", "memory", "flops", "computational cost", "training time", "inference time", "efficiency")),
    ("experimental_configuration", ("hyperparameter", "hyper-parameter", "parameter setting", "training details", "parameters for", "constraint settings")),
    ("sensitivity", ("sensitivity", "different temperatures", "different data sizes", "different pre-training", "number of prompt", "model scaling", "varying ", "different numbers")),
    ("robustness", ("robustness", "adversarial", "attack", "corruption", "noise", "out-of-domain", "ood ", "zero-shot transfer")),
    ("method_taxonomy", ("summary of", "list of", "key features", "baseline methods", "comparison of conditions", "prompt format", "notation")),
    ("main_results", ("performance", "results", "comparison", "benchmark", "accuracy", "f1", "mse", "mae", "evaluation")),
]
FORM_FOR_PURPOSE = {
    "ablation": "ablation_table",
    "dataset_statistics": "descriptive_table",
    "efficiency": "efficiency_table",
    "experimental_configuration": "experimental_configuration_table",
    "main_results": "comparison_table",
    "method_taxonomy": "taxonomy_table",
    "narrative_false_positive": "exclude",
    "robustness": "comparison_table",
    "sensitivity": "sensitivity_table",
    "other": "comparison_table",
}


def read_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def canonical_hash(record):
    payload = json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(payload).hexdigest()


def records_digest(records):
    payload = "".join(canonical_hash(record) + "\n" for record in records).encode()
    return hashlib.sha256(payload).hexdigest()


def cleaned(text):
    return re.sub(r"\s+", " ", str(text).replace("\u0002", "").replace("￾", "-")).strip()


def purpose_labels(caption, region, probable_caption):
    if not probable_caption:
        return "narrative_false_positive", [], ["caption.not_colon_delimited"], 0.97
    text = f"{caption} {region[:800]}".lower()
    tags, evidence = [], []
    for purpose, phrases in RULES:
        hits = [phrase.strip() for phrase in phrases if phrase in text]
        if hits:
            tags.append(purpose)
            evidence.append(f"purpose.{purpose}:{'|'.join(hits[:3])}")
    priority = ["ablation", "dataset_statistics", "efficiency", "experimental_configuration", "sensitivity", "robustness", "method_taxonomy", "main_results"]
    primary = next((label for label in priority if label in tags), "other")
    confidence = 0.92 if primary in {"ablation", "dataset_statistics", "experimental_configuration"} else 0.82 if primary != "other" else 0.45
    return primary, tags, evidence, confidence


def annotate_record(record, legacy_papers):
    caption = cleaned(record.get("caption", ""))
    region = cleaned(record.get("region_text", ""))
    probable_caption = bool(CAPTION_RE.match(caption))
    mentions = TABLE_MENTION_RE.findall(region)
    unique_mentions = list(dict.fromkeys(item.upper() for item in mentions))
    primary, tags, evidence, confidence = purpose_labels(caption, region, probable_caption)
    quality_flags = []
    if not probable_caption:
        quality_flags.append("probable_narrative_mention")
    if CONTINUATION_RE.search(caption):
        quality_flags.append("caption_probably_truncated")
    if len(unique_mentions) > 1:
        quality_flags.append("region_contains_multiple_tables")
    if any(ord(char) < 32 and char not in "\n\r\t" for char in record.get("region_text", "")) or "￾" in record.get("region_text", ""):
        quality_flags.append("text_extraction_artifact")
    bbox = record.get("bbox_pdf_points", [0, 0, 0, 0])
    width = max(0.0, float(bbox[2]) - float(bbox[0])) if len(bbox) == 4 else 0.0
    height = max(0.0, float(bbox[3]) - float(bbox[1])) if len(bbox) == 4 else 0.0
    if height > 260:
        quality_flags.append("large_crop_may_include_context")
    numeric_tokens = NUMBER_RE.findall(region)
    if len(numeric_tokens) < 2:
        quality_flags.append("non_numeric_or_sparse_table")
    form = FORM_FOR_PURPOSE[primary]
    if probable_caption and primary == "other":
        evidence.append("form.conservative_comparison_default")
    if len(unique_mentions) > 1:
        confidence = max(0.2, confidence - 0.15)
    if "caption_probably_truncated" in quality_flags:
        confidence = max(0.2, confidence - 0.08)
    if "text_extraction_artifact" in quality_flags:
        confidence = max(0.2, confidence - 0.04)
    if "large_crop_may_include_context" in quality_flags:
        confidence = max(0.2, confidence - 0.08)
    partition = "legacy_development" if record.get("paper_sha256") in legacy_papers else "prospective_stress_test"
    metric_directions = []
    if "↑" in region:
        metric_directions.append("max")
    if "↓" in region:
        metric_directions.append("min")
    uncertainty = []
    for label, pattern in (("plus_minus", r"±"), ("standard_deviation", r"standard deviation|\bsd\b"), ("standard_error", r"standard error|\bse\b"), ("confidence_interval", r"confidence interval|\bci\b")):
        if re.search(pattern, region, re.I):
            uncertainty.append(label)
    eligible = probable_caption and primary != "narrative_false_positive"
    structure_eligible = eligible and not {"region_contains_multiple_tables", "large_crop_may_include_context"}.intersection(quality_flags)
    return {
        "schema_version": SCHEMA_VERSION,
        "id": record["id"],
        "source_record_sha256": canonical_hash(record),
        "source_region_text_sha256": record["region_text_sha256"],
        "source_crop_sha256": record["crop_sha256"],
        "venue": record.get("venue", "NeurIPS"),
        "year": record["year"],
        "paper_sha256": record["paper_sha256"],
        "partition": partition,
        "annotation": {
            "tier": "weak_rule_based",
            "generator": GENERATOR,
            "gold": False,
            "purpose": {"primary": primary, "tags": tags, "confidence": round(confidence, 2)},
            "recommended_form": {"primary": form, "confidence": round(confidence, 2)},
            "evidence": evidence,
        },
        "signals": {
            "probable_caption": probable_caption,
            "table_mentions": unique_mentions,
            "numeric_token_count": len(numeric_tokens),
            "percentage_token_count": sum(token.endswith("%") for token in numeric_tokens),
            "citation_token_count": len(CITATION_RE.findall(region)),
            "metric_directions": metric_directions,
            "uncertainty_markers": uncertainty,
            "region_line_count": len(record.get("region_text", "").splitlines()),
            "crop_width_pt": round(width, 2),
            "crop_height_pt": round(height, 2),
            "crop_aspect_ratio": round(width / height, 3) if height else None,
        },
        "quality_flags": quality_flags,
        "eligibility": {
            "caption_filter_diagnostic": True,
            "visual_structure_stress": structure_eligible,
            "form_routing_diagnostic": eligible and confidence >= 0.6,
            "numeric_reconstruction": False,
            "paperbench_generation_pair": False,
            "human_aesthetic_gold": False,
        },
        "limitations": [
            "caption and PDF text heuristics are weak labels, not human annotations",
            "no canonical experimental input x is linked",
            "the crop remains governed by source publication terms",
        ],
    }


def summarize(records):
    counter = lambda values: dict(sorted(collections.Counter(values).items()))
    papers = collections.defaultdict(set)
    for record in records:
        papers[record["partition"]].add(record["paper_sha256"])
    return {
        "schema_version": SCHEMA_VERSION,
        "annotation_tier": "weak_rule_based",
        "gold": False,
        "records": len(records),
        "papers": len({record["paper_sha256"] for record in records}),
        "partitions": counter(record["partition"] for record in records),
        "papers_by_partition": {key: len(value) for key, value in sorted(papers.items())},
        "purposes": counter(record["annotation"]["purpose"]["primary"] for record in records),
        "recommended_forms": counter(record["annotation"]["recommended_form"]["primary"] for record in records),
        "quality_flags": counter(flag for record in records for flag in record["quality_flags"]),
        "eligible_caption_filter_diagnostic": sum(record["eligibility"]["caption_filter_diagnostic"] for record in records),
        "eligible_visual_structure_stress": sum(record["eligibility"]["visual_structure_stress"] for record in records),
        "eligible_form_routing_diagnostic": sum(record["eligibility"]["form_routing_diagnostic"] for record in records),
        "paperbench_generation_pairs": 0,
    }


def release_summary(records, source, legacy):
    summary = summarize(records)
    summary["generator"] = GENERATOR
    summary["source_manifest"] = {
        "records": len(source),
        "papers": len({record["paper_sha256"] for record in source}),
        "record_set_sha256": records_digest(source),
    }
    summary["legacy_development_manifest"] = {
        "records": len(legacy),
        "papers": len({record["paper_sha256"] for record in legacy}),
        "record_set_sha256": records_digest(legacy),
    }
    return summary


def build_audit_queue(source, annotations, limit=40):
    source_by_id = {record["id"]: record for record in source}
    buckets = collections.defaultdict(list)
    for annotation in annotations:
        if annotation["partition"] != "prospective_stress_test":
            continue
        stratum = "flagged" if annotation["quality_flags"] else "unflagged"
        buckets[(annotation["annotation"]["purpose"]["primary"], stratum)].append(annotation)
    for values in buckets.values():
        values.sort(key=lambda record: (record["paper_sha256"], record["id"]))
    selected, selected_ids = [], set()
    paper_counts = collections.Counter()
    while len(selected) < limit:
        progressed = False
        for bucket in sorted(buckets):
            choices = [record for record in buckets[bucket] if record["id"] not in selected_ids]
            if not choices:
                continue
            record = min(choices, key=lambda item: (paper_counts[item["paper_sha256"]], item["id"]))
            selected.append(record); selected_ids.add(record["id"]); paper_counts[record["paper_sha256"]] += 1; progressed = True
            if len(selected) >= limit:
                break
        if not progressed:
            break
    queue = []
    for annotation in selected:
        raw = source_by_id[annotation["id"]]
        queue.append({
            "schema_version": "1.0",
            "id": annotation["id"],
            "partition": annotation["partition"],
            "paper_sha256": annotation["paper_sha256"],
            "page": raw["page"],
            "caption": raw["caption"],
            "crop_path": raw["crop_path"],
            "crop_sha256": raw["crop_sha256"],
            "weak_purpose": annotation["annotation"]["purpose"]["primary"],
            "weak_recommended_form": annotation["annotation"]["recommended_form"]["primary"],
            "quality_flags": annotation["quality_flags"],
            "review": {
                "status": "pending",
                "is_table": None,
                "purpose": None,
                "recommended_form": None,
                "crop_clean": None,
                "notes": None,
                "reviewer": None,
                "reviewed_at": None,
            },
        })
    return queue


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("--legacy-development-index", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--audit-queue", type=Path)
    parser.add_argument("--audit-size", type=int, default=40)
    args = parser.parse_args()
    source = read_jsonl(args.source)
    legacy_source = read_jsonl(args.legacy_development_index)
    legacy = {record["paper_sha256"] for record in legacy_source}
    records = [annotate_record(record, legacy) for record in source]
    summary = release_summary(records, source, legacy_source)
    args.out.write_text("".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records))
    args.summary.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
    if args.audit_queue:
        queue = build_audit_queue(source, records, args.audit_size)
        args.audit_queue.write_text("".join(json.dumps(record, ensure_ascii=False) + "\n" for record in queue))
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
