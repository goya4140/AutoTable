#!/usr/bin/env python3
"""Score discovery routing predictions against public weak labels as diagnostics."""
from __future__ import annotations

import argparse
import collections
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load_annotator():
    spec = importlib.util.spec_from_file_location("neurips_discovery_eval_annotator", HERE / "annotate.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def safe_div(numerator, denominator):
    return numerator / denominator if denominator else None


def binary_metrics(gold, predicted):
    tp = sum(expected and actual for expected, actual in zip(gold, predicted))
    fp = sum(not expected and actual for expected, actual in zip(gold, predicted))
    fn = sum(expected and not actual for expected, actual in zip(gold, predicted))
    precision = safe_div(tp, tp + fp); recall = safe_div(tp, tp + fn)
    f1 = safe_div(2 * precision * recall, precision + recall) if precision is not None and recall is not None else None
    return {"precision": precision, "recall": recall, "f1": f1, "tp": tp, "fp": fp, "fn": fn}


def multiclass_metrics(gold, predicted):
    labels = sorted(set(gold))
    per_class = {}
    for label in labels:
        metrics = binary_metrics([value == label for value in gold], [value == label for value in predicted])
        per_class[label] = metrics
    f1_values = [metrics["f1"] for metrics in per_class.values() if metrics["f1"] is not None]
    return {
        "accuracy": safe_div(sum(expected == actual for expected, actual in zip(gold, predicted)), len(gold)),
        "macro_f1": safe_div(sum(f1_values), len(f1_values)),
        "per_class": per_class,
    }


def score(annotations, predictions):
    targets = [record for record in annotations if record["partition"] == "prospective_stress_test"]
    prediction_map = {}; protocol_errors = []
    for prediction in predictions:
        record_id = prediction.get("id")
        if record_id in prediction_map:
            protocol_errors.append(f"duplicate prediction ID: {record_id}")
        prediction_map[record_id] = prediction
    target_ids = {record["id"] for record in targets}
    extras = sorted(set(prediction_map) - target_ids)
    if extras:
        protocol_errors.append(f"unexpected prediction IDs: {len(extras)}")
    missing = sorted(target_ids - set(prediction_map))
    filter_gold = [record["annotation"]["recommended_form"]["primary"] == "exclude" for record in targets]
    filter_predicted = [prediction_map.get(record["id"], {}).get("action") == "exclude" for record in targets]
    routing_targets = [record for record in targets if record["eligibility"]["form_routing_diagnostic"]]
    purpose_gold = [record["annotation"]["purpose"]["primary"] for record in routing_targets]
    purpose_predicted = [prediction_map.get(record["id"], {}).get("purpose", "__missing__") for record in routing_targets]
    form_gold = [record["annotation"]["recommended_form"]["primary"] for record in routing_targets]
    form_predicted = [prediction_map.get(record["id"], {}).get("recommended_form", "__missing__") for record in routing_targets]
    quality_universe = sorted({flag for record in targets for flag in record["quality_flags"]})
    quality_gold = []; quality_predicted = []
    for record in targets:
        actual = set(prediction_map.get(record["id"], {}).get("quality_flags", []))
        expected = set(record["quality_flags"])
        for flag in quality_universe:
            quality_gold.append(flag in expected); quality_predicted.append(flag in actual)
    return {
        "diagnostic_only": True,
        "annotation_tier": "weak_rule_based",
        "gold": False,
        "public_labels": True,
        "leaderboard_eligible": False,
        "protocol_errors": protocol_errors,
        "prospective_records": len(targets),
        "submitted_records": len(target_ids & set(prediction_map)),
        "coverage": safe_div(len(target_ids & set(prediction_map)), len(targets)),
        "missing_prediction_ids": missing,
        "narrative_filter": binary_metrics(filter_gold, filter_predicted),
        "purpose_routing": {"records": len(routing_targets), **multiclass_metrics(purpose_gold, purpose_predicted)},
        "form_routing": {"records": len(routing_targets), **multiclass_metrics(form_gold, form_predicted)},
        "quality_flag_detection": {"flags": quality_universe, **binary_metrics(quality_gold, quality_predicted)},
        "limitations": [
            "labels are deterministic public heuristics and can be tuned against",
            "metrics measure regression agreement, not human design quality",
            "no structured experimental input is available for numeric fidelity scoring",
        ],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("annotations", type=Path)
    parser.add_argument("predictions", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    annotator = load_annotator()
    report = score(annotator.read_jsonl(args.annotations), annotator.read_jsonl(args.predictions))
    text = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.out:
        args.out.write_text(text)
    else:
        print(text, end="")
    raise SystemExit(0 if not report["protocol_errors"] else 1)


if __name__ == "__main__":
    main()
