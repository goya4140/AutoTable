#!/usr/bin/env python3
"""Audit repeated-run completeness and plan precision-driven data acquisition."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "paper-table-more-data-plan-v1"


def _finite(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _stable_key(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest(values: list[Any]) -> str:
    encoded = json.dumps(sorted(values, key=_stable_key), ensure_ascii=False, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _beta_continued_fraction(a: float, b: float, x: float) -> float:
    maximum_iterations = 300
    epsilon = 3e-14
    floor = 1e-300
    qab = a + b
    qap = a + 1
    qam = a - 1
    c = 1.0
    d = 1 - qab * x / qap
    if abs(d) < floor:
        d = floor
    d = 1 / d
    result = d
    for iteration in range(1, maximum_iterations + 1):
        twice = 2 * iteration
        coefficient = iteration * (b - iteration) * x / ((qam + twice) * (a + twice))
        d = 1 + coefficient * d
        if abs(d) < floor:
            d = floor
        c = 1 + coefficient / c
        if abs(c) < floor:
            c = floor
        d = 1 / d
        result *= d * c
        coefficient = -(a + iteration) * (qab + iteration) * x / ((a + twice) * (qap + twice))
        d = 1 + coefficient * d
        if abs(d) < floor:
            d = floor
        c = 1 + coefficient / c
        if abs(c) < floor:
            c = floor
        d = 1 / d
        delta = d * c
        result *= delta
        if abs(delta - 1) < epsilon:
            return result
    raise RuntimeError("incomplete-beta continued fraction did not converge")


def regularized_incomplete_beta(x: float, a: float, b: float) -> float:
    if not 0 <= x <= 1 or a <= 0 or b <= 0:
        raise ValueError("invalid regularized incomplete beta arguments")
    if x == 0:
        return 0.0
    if x == 1:
        return 1.0
    factor = math.exp(math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log1p(-x))
    if x < (a + 1) / (a + b + 2):
        return factor * _beta_continued_fraction(a, b, x) / a
    return 1 - factor * _beta_continued_fraction(b, a, 1 - x) / b


def student_t_cdf(value: float, degrees_of_freedom: int) -> float:
    if not isinstance(degrees_of_freedom, int) or degrees_of_freedom < 1:
        raise ValueError("degrees_of_freedom must be a positive integer")
    if value == 0:
        return 0.5
    x = degrees_of_freedom / (degrees_of_freedom + value * value)
    tail = 0.5 * regularized_incomplete_beta(x, degrees_of_freedom / 2, 0.5)
    return 1 - tail if value > 0 else tail


def student_t_quantile(probability: float, degrees_of_freedom: int) -> float:
    if not 0 < probability < 1:
        raise ValueError("probability must be between zero and one")
    if probability < 0.5:
        return -student_t_quantile(1 - probability, degrees_of_freedom)
    if probability == 0.5:
        return 0.0
    lower = 0.0
    upper = 1.0
    while student_t_cdf(upper, degrees_of_freedom) < probability:
        upper *= 2
    for _ in range(100):
        middle = (lower + upper) / 2
        if student_t_cdf(middle, degrees_of_freedom) < probability:
            lower = middle
        else:
            upper = middle
    return (lower + upper) / 2


def ci_half_width(sample_sd: float, sample_size: int, confidence_level: float) -> float:
    critical = student_t_quantile(1 - (1 - confidence_level) / 2, sample_size - 1)
    return critical * sample_sd / math.sqrt(sample_size)


def required_total_runs(
    sample_sd: float,
    current_runs: int,
    target_half_width: float,
    confidence_level: float,
    maximum_total_runs: int,
) -> int | None:
    for total in range(max(2, current_runs), maximum_total_runs + 1):
        if ci_half_width(sample_sd, total, confidence_level) <= target_half_width:
            return total
    return None


def plan(payload: dict) -> dict:
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"schema_version must be {SCHEMA_VERSION}")
    group_keys = payload.get("group_keys", [])
    metrics = payload.get("metrics", [])
    runs = payload.get("runs", [])
    run_id_key = payload.get("run_id_key")
    repeat_unit = payload.get("repeat_unit")
    independence = payload.get("independence")
    pairing = payload.get("pairing", {})
    planning = payload.get("planning", {})
    if not group_keys or not metrics or not runs or not run_id_key or not repeat_unit:
        raise ValueError("group_keys, metrics, runs, run_id_key, and repeat_unit are required")
    if independence != "independent":
        raise ValueError("independence must be explicitly declared as independent")
    group_names = [item.get("key") for item in group_keys]
    metric_names = [item.get("key") for item in metrics]
    if any(not name for name in [*group_names, *metric_names]) or len(group_names) != len(set(group_names)) or len(metric_names) != len(set(metric_names)):
        raise ValueError("group and metric keys must be unique and nonempty")
    for metric in metrics:
        if "unit" not in metric or metric.get("direction") not in {"min", "max"}:
            raise ValueError(f"metric {metric.get('key')!r} requires unit and direction")
    pairing_mode = pairing.get("mode")
    if pairing_mode not in {"fixed_across_groups", "group_specific"}:
        raise ValueError("pairing.mode must be fixed_across_groups or group_specific")
    confidence_level = planning.get("confidence_level")
    targets = planning.get("target_half_widths", {})
    minimum_pilot = planning.get("minimum_pilot_runs")
    maximum_total = planning.get("maximum_total_runs")
    if not _finite(confidence_level) or not 0.8 <= float(confidence_level) <= 0.99:
        raise ValueError("planning.confidence_level must be from 0.8 to 0.99")
    if set(targets) != set(metric_names) or not all(_finite(value) and float(value) > 0 for value in targets.values()):
        raise ValueError("target_half_widths must provide one positive finite target for every metric")
    if not isinstance(minimum_pilot, int) or minimum_pilot < 3:
        raise ValueError("minimum_pilot_runs must be an integer of at least three")
    if not isinstance(maximum_total, int) or maximum_total < minimum_pilot:
        raise ValueError("maximum_total_runs must be an integer no smaller than minimum_pilot_runs")
    if planning.get("variance_assumption") != "pilot_sd_stable_for_planning_only":
        raise ValueError("variance_assumption must acknowledge pilot_sd_stable_for_planning_only")
    if planning.get("interval_assumption") != "t_interval_appropriate_for_repeat_distribution":
        raise ValueError("interval_assumption must acknowledge t_interval_appropriate_for_repeat_distribution")
    if planning.get("estimand") != "group_mean":
        raise ValueError("planning.estimand must be group_mean; paired-difference precision requires a separate plan")

    observed: dict[str, dict[str, Any]] = {}
    group_labels: dict[str, dict] = {}
    for run in runs:
        try:
            group = {name: run[name] for name in group_names}
            run_id = run[run_id_key]
        except KeyError as error:
            raise ValueError(f"run lacks required field {error.args[0]!r}") from error
        encoded_group = _stable_key(group)
        encoded_run = _stable_key(run_id)
        group_labels[encoded_group] = group
        by_id = observed.setdefault(encoded_group, {})
        if encoded_run in by_id:
            raise ValueError(f"duplicate run id {run_id!r} in group {group!r}")
        by_id[encoded_run] = {"id": run_id, "record": run}

    expected_group_items = pairing.get("expected_groups")
    if expected_group_items is None:
        expected_groups = sorted(observed)
        expected_group_source = "observed_groups"
    else:
        expected_groups = []
        for item in expected_group_items:
            if not isinstance(item, dict) or set(item) != set(group_names):
                raise ValueError("each expected group must contain exactly the declared group keys")
            encoded = _stable_key(item)
            if encoded in expected_groups:
                raise ValueError("expected_groups contains a duplicate")
            expected_groups.append(encoded)
            group_labels[encoded] = item
        expected_groups.sort()
        expected_group_source = "declared_expected_groups"
        unexpected = set(observed) - set(expected_groups)
        if unexpected:
            raise ValueError("observed runs contain a group outside expected_groups")

    observed_run_ids = {
        encoded: entry["id"]
        for by_id in observed.values()
        for encoded, entry in by_id.items()
    }
    declared_ids = pairing.get("expected_run_ids")
    if declared_ids is None:
        expected_run_ids = sorted(observed_run_ids)
        expected_run_id_source = "union_of_observed_run_ids"
    else:
        if len(declared_ids) != len({_stable_key(value) for value in declared_ids}):
            raise ValueError("expected_run_ids contains a duplicate")
        expected_run_ids = sorted((_stable_key(value) for value in declared_ids))
        expected_run_id_source = "declared_expected_run_ids"
        if set(observed_run_ids) - set(expected_run_ids):
            raise ValueError("observed run id falls outside expected_run_ids")
        for value in declared_ids:
            observed_run_ids.setdefault(_stable_key(value), value)

    repair_requests = []
    invalid_metric_requests = []
    for encoded_group in expected_groups:
        group = group_labels[encoded_group]
        by_id = observed.get(encoded_group, {})
        if pairing_mode == "fixed_across_groups":
            for encoded_run in expected_run_ids:
                if encoded_run not in by_id:
                    repair_requests.append({
                        "group": group,
                        "run_id": observed_run_ids[encoded_run],
                        "request": "complete_existing_paired_run",
                        "metrics": metric_names,
                    })
        for encoded_run, entry in by_id.items():
            for metric in metrics:
                field = metric.get("field", metric["key"])
                if not _finite(entry["record"].get(field)):
                    invalid_metric_requests.append({
                        "group": group,
                        "run_id": entry["id"],
                        "metric": metric["key"],
                        "request": "rerun_or_recover_missing_metric",
                    })

    precision_cells = []
    for encoded_group in expected_groups:
        group = group_labels[encoded_group]
        by_id = observed.get(encoded_group, {})
        for metric in metrics:
            field = metric.get("field", metric["key"])
            values = [float(entry["record"][field]) for entry in by_id.values() if _finite(entry["record"].get(field))]
            current_runs = len(values)
            target = float(targets[metric["key"]])
            cell = {
                "group": group,
                "metric": metric["key"],
                "unit": metric["unit"],
                "current_valid_runs": current_runs,
                "target_ci_half_width": target,
                "confidence_level": float(confidence_level),
                "planning_assumption": "pilot_sd_stable_for_planning_only",
                "interval_assumption": "t_interval_appropriate_for_repeat_distribution",
            }
            if current_runs < minimum_pilot:
                cell.update({
                    "sample_sd": statistics.stdev(values) if current_runs >= 2 else None,
                    "current_ci_half_width": ci_half_width(statistics.stdev(values), current_runs, float(confidence_level)) if current_runs >= 2 else None,
                    "required_total_runs": minimum_pilot,
                    "additional_runs": minimum_pilot - current_runs,
                    "status": "collect_minimum_pilot_then_replan",
                    "target_met": False,
                })
            else:
                sample_sd = statistics.stdev(values)
                current_half_width = ci_half_width(sample_sd, current_runs, float(confidence_level))
                if sample_sd == 0:
                    cell.update({
                        "sample_sd": 0.0,
                        "current_ci_half_width": 0.0,
                        "required_total_runs": None,
                        "additional_runs": None,
                        "status": "zero_pilot_variance_requires_review",
                        "target_met": False,
                    })
                else:
                    required = required_total_runs(sample_sd, current_runs, target, float(confidence_level), maximum_total)
                    if required is None:
                        status = "target_not_reached_within_cap"
                        additional = None
                        target_met = False
                    else:
                        status = "target_met" if required <= current_runs else "additional_runs_provisionally_required"
                        additional = max(0, required - current_runs)
                        target_met = required <= current_runs
                    cell.update({
                        "sample_sd": sample_sd,
                        "current_ci_half_width": current_half_width,
                        "required_total_runs": required,
                        "additional_runs": additional,
                        "status": status,
                        "target_met": target_met,
                    })
            precision_cells.append(cell)

    known_requirements = [cell["required_total_runs"] for cell in precision_cells if cell["required_total_runs"] is not None]
    unresolved = [cell for cell in precision_cells if cell["required_total_runs"] is None]
    if pairing_mode == "fixed_across_groups":
        common_total = max([len(expected_run_ids), *known_requirements])
        precision_request = {
            "mode": "add_new_run_ids_across_every_expected_group",
            "provisional_common_total_runs": common_total,
            "additional_common_run_ids": max(0, common_total - len(expected_run_ids)),
            "groups": [group_labels[group] for group in expected_groups],
        }
    else:
        precision_request = {
            "mode": "add_runs_per_group",
            "groups": [
                {
                    "group": group_labels[group],
                    "provisional_total_runs": max(
                        (cell["required_total_runs"] or len(observed.get(group, {})))
                        for cell in precision_cells
                        if _stable_key(cell["group"]) == group
                    ),
                }
                for group in expected_groups
            ],
        }
    questions = []
    if repair_requests or invalid_metric_requests:
        questions.append("Can you rerun or recover the listed existing run cells first, then return the repaired data so the precision plan can be recomputed?")
    if unresolved:
        questions.append("Some precision targets are unresolved because pilot variance is zero or the run cap is too low; should the author raise the cap, collect a fresh pilot, or revise the target width?")

    return {
        "schema_version": "paper-table-more-data-plan-report-v1",
        "repeat_unit": repeat_unit,
        "independence": independence,
        "pairing": {
            "mode": pairing_mode,
            "expected_group_source": expected_group_source,
            "expected_run_id_source": expected_run_id_source,
            "expected_groups": [group_labels[group] for group in expected_groups],
            "expected_run_ids": [observed_run_ids[run_id] for run_id in expected_run_ids],
            "expected_run_ids_sha256": _digest([observed_run_ids[run_id] for run_id in expected_run_ids]),
        },
        "completeness": {
            "repair_requests": repair_requests,
            "invalid_metric_requests": invalid_metric_requests,
            "repair_count": len(repair_requests) + len(invalid_metric_requests),
            "requires_replan_after_repair": bool(repair_requests or invalid_metric_requests),
        },
        "precision": {
            "confidence_level": float(confidence_level),
            "estimand": "group_mean",
            "minimum_pilot_runs": minimum_pilot,
            "maximum_total_runs": maximum_total,
            "variance_assumption": "pilot_sd_stable_for_planning_only",
            "interval_assumption": "t_interval_appropriate_for_repeat_distribution",
            "cells": precision_cells,
            "request": precision_request,
            "unresolved_cells": len(unresolved),
            "provisional": True,
        },
        "questions_for_author": questions,
        "notes": [
            "This report requests observations; it never simulates or imputes experimental outcomes.",
            "The target estimand is each group mean, not a paired method difference.",
            "Precision projections use the observed pilot sample SD in a two-sided Student-t mean interval and must be recomputed after new runs arrive.",
            "The author must judge the Student-t mean interval appropriate for the repeat distribution; small, strongly skewed, or heavy-tailed pilots need another plan.",
            "Complete existing paired run IDs before starting new paired IDs.",
            "A zero pilot SD is not accepted as proof of zero future variance.",
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
