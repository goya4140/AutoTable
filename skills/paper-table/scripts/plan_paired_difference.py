#!/usr/bin/env python3
"""Audit fixed paired runs and plan precision for baseline-vs-candidate mean differences."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import statistics
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "paper-table-paired-difference-plan-v1"


def _load_mean_planner():
    path = Path(__file__).with_name("plan_more_data.py")
    spec = importlib.util.spec_from_file_location("paper_table_mean_precision_helpers", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


_MEAN = _load_mean_planner()


def _finite(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _stable_key(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest(values: list[Any]) -> str:
    encoded = json.dumps(sorted(values, key=_stable_key), ensure_ascii=False, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def plan(payload: dict) -> dict:
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"schema_version must be {SCHEMA_VERSION}")
    method_key = payload.get("method_key")
    context_keys = payload.get("context_keys", [])
    metrics = payload.get("metrics", [])
    runs = payload.get("runs", [])
    run_id_key = payload.get("run_id_key")
    repeat_unit = payload.get("repeat_unit")
    pairing = payload.get("pairing", {})
    planning = payload.get("planning", {})
    if not method_key or not context_keys or not metrics or not runs or not run_id_key or not repeat_unit:
        raise ValueError("method_key, context_keys, metrics, runs, run_id_key, and repeat_unit are required")
    if payload.get("independence") != "independent":
        raise ValueError("independence must be explicitly declared as independent")
    if method_key in context_keys or len(context_keys) != len(set(context_keys)):
        raise ValueError("context_keys must be unique and must not include method_key")

    metric_names = [metric.get("key") for metric in metrics]
    if any(not name for name in metric_names) or len(metric_names) != len(set(metric_names)):
        raise ValueError("metric keys must be unique and nonempty")
    for metric in metrics:
        if "unit" not in metric or metric.get("direction") not in {"min", "max"}:
            raise ValueError(f"metric {metric.get('key')!r} requires unit and direction")

    baseline = pairing.get("baseline")
    candidates = pairing.get("candidates")
    expected_context_items = pairing.get("expected_contexts")
    expected_id_items = pairing.get("expected_run_ids")
    if pairing.get("mode") != "baseline_vs_all_fixed_ids":
        raise ValueError("pairing.mode must be baseline_vs_all_fixed_ids")
    if baseline is None or not isinstance(candidates, list) or not candidates:
        raise ValueError("pairing requires one baseline and a nonempty candidates list")
    if len({_stable_key(value) for value in [baseline, *candidates]}) != len(candidates) + 1:
        raise ValueError("baseline and candidates must be distinct and candidates unique")
    if not isinstance(expected_context_items, list) or not expected_context_items:
        raise ValueError("pairing.expected_contexts must be a nonempty declared list")
    if not isinstance(expected_id_items, list) or not expected_id_items:
        raise ValueError("pairing.expected_run_ids must be a nonempty declared list")
    if len({_stable_key(value) for value in expected_id_items}) != len(expected_id_items):
        raise ValueError("expected_run_ids contains a duplicate")

    contexts: dict[str, dict] = {}
    for item in expected_context_items:
        if not isinstance(item, dict) or set(item) != set(context_keys):
            raise ValueError("each expected context must contain exactly the declared context_keys")
        encoded = _stable_key(item)
        if encoded in contexts:
            raise ValueError("expected_contexts contains a duplicate")
        contexts[encoded] = item
    expected_contexts = sorted(contexts)
    expected_ids = {_stable_key(value): value for value in expected_id_items}
    methods = [baseline, *candidates]
    method_ids = {_stable_key(value): value for value in methods}

    confidence = planning.get("confidence_level")
    targets = planning.get("target_half_widths", {})
    minimum_pilot = planning.get("minimum_pilot_pairs")
    maximum_total = planning.get("maximum_total_pairs")
    if planning.get("estimand") != "paired_mean_difference":
        raise ValueError("planning.estimand must be paired_mean_difference")
    if not _finite(confidence) or not 0.8 <= float(confidence) <= 0.99:
        raise ValueError("planning.confidence_level must be from 0.8 to 0.99")
    if set(targets) != set(metric_names) or not all(_finite(value) and float(value) > 0 for value in targets.values()):
        raise ValueError("target_half_widths must provide one positive finite target for every metric")
    if not isinstance(minimum_pilot, int) or minimum_pilot < 3:
        raise ValueError("minimum_pilot_pairs must be an integer of at least three")
    if not isinstance(maximum_total, int) or maximum_total < minimum_pilot:
        raise ValueError("maximum_total_pairs must be an integer no smaller than minimum_pilot_pairs")
    if planning.get("variance_assumption") != "pilot_paired_difference_sd_stable_for_planning_only":
        raise ValueError("variance_assumption must acknowledge pilot_paired_difference_sd_stable_for_planning_only")
    if planning.get("interval_assumption") != "t_interval_appropriate_for_paired_difference_distribution":
        raise ValueError("interval_assumption must acknowledge t_interval_appropriate_for_paired_difference_distribution")

    observed: dict[str, dict[str, dict[str, dict]]] = {}
    for run in runs:
        try:
            context = {key: run[key] for key in context_keys}
            method = run[method_key]
            run_id = run[run_id_key]
        except KeyError as error:
            raise ValueError(f"run lacks required field {error.args[0]!r}") from error
        context_id = _stable_key(context)
        method_id = _stable_key(method)
        run_id_id = _stable_key(run_id)
        if context_id not in contexts:
            raise ValueError("observed runs contain a context outside expected_contexts")
        if method_id not in method_ids:
            raise ValueError("observed runs contain a method outside baseline and candidates")
        if run_id_id not in expected_ids:
            raise ValueError("observed run id falls outside expected_run_ids")
        by_id = observed.setdefault(context_id, {}).setdefault(method_id, {})
        if run_id_id in by_id:
            raise ValueError(f"duplicate run id {run_id!r} for context {context!r} and method {method!r}")
        by_id[run_id_id] = run

    repair_requests = []
    invalid_metric_requests = []
    for context_id in expected_contexts:
        for method in methods:
            method_id = _stable_key(method)
            by_id = observed.get(context_id, {}).get(method_id, {})
            for run_id_id, run_id in expected_ids.items():
                record = by_id.get(run_id_id)
                if record is None:
                    repair_requests.append({
                        "context": contexts[context_id], "method": method, "run_id": run_id,
                        "request": "complete_existing_paired_run", "metrics": metric_names,
                    })
                    continue
                for metric in metrics:
                    field = metric.get("field", metric["key"])
                    if not _finite(record.get(field)):
                        invalid_metric_requests.append({
                            "context": contexts[context_id], "method": method, "run_id": run_id,
                            "metric": metric["key"], "request": "rerun_or_recover_missing_metric",
                        })

    cells = []
    for context_id in expected_contexts:
        baseline_runs = observed.get(context_id, {}).get(_stable_key(baseline), {})
        for candidate in candidates:
            candidate_runs = observed.get(context_id, {}).get(_stable_key(candidate), {})
            for metric in metrics:
                field = metric.get("field", metric["key"])
                differences = []
                paired_ids = []
                for run_id_id, run_id in expected_ids.items():
                    base = baseline_runs.get(run_id_id, {}).get(field)
                    cand = candidate_runs.get(run_id_id, {}).get(field)
                    if _finite(base) and _finite(cand):
                        raw = float(cand) - float(base)
                        differences.append(raw if metric["direction"] == "max" else -raw)
                        paired_ids.append(run_id)
                pair_count = len(differences)
                target = float(targets[metric["key"]])
                cell = {
                    "context": contexts[context_id], "baseline": baseline, "candidate": candidate,
                    "metric": metric["key"], "unit": metric["unit"],
                    "difference_orientation": "positive_favors_candidate",
                    "complete_pairs": pair_count, "paired_run_ids": paired_ids,
                    "paired_run_ids_sha256": _digest(paired_ids),
                    "mean_improvement": statistics.mean(differences) if differences else None,
                    "target_ci_half_width": target, "confidence_level": float(confidence),
                    "planning_assumption": "pilot_paired_difference_sd_stable_for_planning_only",
                    "interval_assumption": "t_interval_appropriate_for_paired_difference_distribution",
                }
                if pair_count < minimum_pilot:
                    sample_sd = statistics.stdev(differences) if pair_count >= 2 else None
                    cell.update({
                        "paired_difference_sd": sample_sd,
                        "current_ci_half_width": _MEAN.ci_half_width(sample_sd, pair_count, float(confidence)) if sample_sd is not None else None,
                        "required_total_pairs": minimum_pilot,
                        "additional_pairs": minimum_pilot - pair_count,
                        "status": "collect_minimum_pilot_then_replan", "target_met": False,
                    })
                else:
                    sample_sd = statistics.stdev(differences)
                    current_width = _MEAN.ci_half_width(sample_sd, pair_count, float(confidence))
                    if sample_sd == 0:
                        cell.update({
                            "paired_difference_sd": 0.0, "current_ci_half_width": 0.0,
                            "required_total_pairs": None, "additional_pairs": None,
                            "status": "zero_pilot_difference_variance_requires_review", "target_met": False,
                        })
                    else:
                        required = _MEAN.required_total_runs(sample_sd, pair_count, target, float(confidence), maximum_total)
                        cell.update({
                            "paired_difference_sd": sample_sd, "current_ci_half_width": current_width,
                            "required_total_pairs": required,
                            "additional_pairs": None if required is None else max(0, required - pair_count),
                            "status": "target_not_reached_within_cap" if required is None else ("target_met" if required <= pair_count else "additional_pairs_provisionally_required"),
                            "target_met": required is not None and required <= pair_count,
                        })
                cells.append(cell)

    known_requirements = [cell["required_total_pairs"] for cell in cells if cell["required_total_pairs"] is not None]
    unresolved = [cell for cell in cells if cell["required_total_pairs"] is None]
    common_total = max([len(expected_ids), *known_requirements])
    questions = []
    if repair_requests or invalid_metric_requests:
        questions.append("Can you rerun or recover the listed existing paired cells first, then return the repaired data so paired-difference precision can be recomputed?")
    if unresolved:
        questions.append("Some paired-difference targets are unresolved because pilot difference variance is zero or the pair cap is too low; should the author collect a fresh paired pilot, raise the cap, or revise the target width?")

    return {
        "schema_version": "paper-table-paired-difference-plan-report-v1",
        "repeat_unit": repeat_unit,
        "independence": "independent",
        "pairing": {
            "mode": "baseline_vs_all_fixed_ids", "method_key": method_key,
            "baseline": baseline, "candidates": candidates,
            "expected_contexts": [contexts[key] for key in expected_contexts],
            "expected_run_ids": list(expected_ids.values()),
            "expected_run_ids_sha256": _digest(list(expected_ids.values())),
        },
        "completeness": {
            "repair_requests": repair_requests, "invalid_metric_requests": invalid_metric_requests,
            "repair_count": len(repair_requests) + len(invalid_metric_requests),
            "requires_replan_after_repair": bool(repair_requests or invalid_metric_requests),
        },
        "precision": {
            "confidence_level": float(confidence), "estimand": "paired_mean_difference",
            "minimum_pilot_pairs": minimum_pilot, "maximum_total_pairs": maximum_total,
            "variance_assumption": "pilot_paired_difference_sd_stable_for_planning_only",
            "interval_assumption": "t_interval_appropriate_for_paired_difference_distribution",
            "cells": cells,
            "request": {
                "mode": "add_new_run_ids_for_baseline_and_every_candidate_in_every_context",
                "provisional_common_total_pairs": common_total,
                "additional_common_run_ids": max(0, common_total - len(expected_ids)),
                "contexts": [contexts[key] for key in expected_contexts], "methods": methods,
            },
            "unresolved_cells": len(unresolved), "provisional": True,
        },
        "questions_for_author": questions,
        "notes": [
            "This report requests observations; it never simulates or imputes experimental outcomes.",
            "The estimand is the mean within-run candidate improvement over the baseline, not either method's group mean.",
            "Positive differences always favor the candidate; lower-is-better metrics are sign-reversed before planning.",
            "Precision projections use the observed paired-difference sample SD in a two-sided Student-t interval and must be recomputed after new pairs arrive.",
            "Complete existing paired run IDs before starting new paired IDs for every baseline, candidate, and context.",
            "A zero pilot paired-difference SD is not accepted as proof of zero future variance.",
        ],
        "provenance": payload.get("provenance", {}),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report = plan(json.loads(args.input.read_text()))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(args.out)


if __name__ == "__main__":
    main()
