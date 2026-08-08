#!/usr/bin/env python3
"""Distribution-light pilot diagnostics for precision acquisition planning."""
from __future__ import annotations

import hashlib
import json
import math
import statistics
from typing import Any, Callable


MINIMUM_LOO_RUNS = 5
MODIFIED_Z_LABEL_THRESHOLD = 3.5


def adjusted_fisher_pearson_skewness(values: list[float]) -> float | None:
    """Return adjusted Fisher-Pearson skewness, or None for zero variance / n < 3."""
    n = len(values)
    if n < 3:
        return None
    mean = statistics.mean(values)
    second = sum((value - mean) ** 2 for value in values) / n
    if second == 0:
        return None
    third = sum((value - mean) ** 3 for value in values) / n
    unadjusted = third / (second ** 1.5)
    return math.sqrt(n * (n - 1)) / (n - 2) * unadjusted


def diagnose(
    values: list[float],
    run_ids: list[Any],
    target_half_width: float,
    confidence_level: float,
    maximum_total: int,
    ci_half_width_fn: Callable[[float, int, float], float],
    required_total_fn: Callable[[float, int, float, float, int], int | None],
) -> dict:
    """Describe skew, potential extremes, and leave-one-run-out planning sensitivity.

    This is a sensitivity audit, not a normality test and not permission to delete runs.
    """
    if len(values) != len(run_ids):
        raise ValueError("values and run_ids must have equal length")
    if not values:
        return {
            "method": "descriptive_plus_leave_one_run_out_v1",
            "status": "insufficient_runs_for_stability_diagnostics",
            "diagnostic_runs": 0,
            "minimum_runs_for_leave_one_out": MINIMUM_LOO_RUNS,
            "review_reasons": ["no_valid_runs"],
        }

    numeric = [float(value) for value in values]
    n = len(numeric)
    median = statistics.median(numeric)
    deviations = [abs(value - median) for value in numeric]
    mad = statistics.median(deviations)
    if mad == 0:
        modified_z = [None] * n
        potential_indices: list[int] = []
        modified_z_status = "unavailable_zero_mad"
    else:
        modified_z = [0.6745 * (value - median) / mad for value in numeric]
        potential_indices = [index for index, value in enumerate(modified_z) if abs(value) > MODIFIED_Z_LABEL_THRESHOLD]
        modified_z_status = "computed"

    result = {
        "method": "descriptive_plus_leave_one_run_out_v1",
        "status": "insufficient_runs_for_stability_diagnostics" if n < MINIMUM_LOO_RUNS else "no_automatic_flag",
        "diagnostic_runs": n,
        "minimum_runs_for_leave_one_out": MINIMUM_LOO_RUNS,
        "adjusted_fisher_pearson_skewness": adjusted_fisher_pearson_skewness(numeric),
        "median": median,
        "median_absolute_deviation": mad,
        "modified_z_status": modified_z_status,
        "modified_z_label_threshold": MODIFIED_Z_LABEL_THRESHOLD,
        "potential_extreme_run_ids": [run_ids[index] for index in potential_indices],
        "potential_extreme_count": len(potential_indices),
        "review_reasons": [],
        "interpretation": "Sensitivity evidence only; do not delete or relabel an observed run without investigating its provenance.",
    }
    if n < MINIMUM_LOO_RUNS:
        result["review_reasons"].append("fewer_than_five_valid_runs")
        return result

    full_sd = statistics.stdev(numeric)
    if full_sd == 0:
        result["status"] = "review_required"
        result["review_reasons"].append("zero_full_sample_variance")

    omissions = []
    for omitted in range(n):
        subset = numeric[:omitted] + numeric[omitted + 1:]
        subset_sd = statistics.stdev(subset)
        if subset_sd == 0:
            required = None
            width = 0.0
        else:
            width = ci_half_width_fn(subset_sd, n - 1, confidence_level)
            required = required_total_fn(subset_sd, n - 1, target_half_width, confidence_level, maximum_total)
        omissions.append({
            "omitted_run_id": run_ids[omitted],
            "remaining_mean": statistics.mean(subset),
            "remaining_sd": subset_sd,
            "remaining_ci_half_width": width,
            "required_total_under_remaining_sd": required,
            "target_met_in_remaining_subset": subset_sd != 0 and width <= target_half_width,
        })

    means = [item["remaining_mean"] for item in omissions]
    sds = [item["remaining_sd"] for item in omissions]
    requirements = [item["required_total_under_remaining_sd"] for item in omissions if item["required_total_under_remaining_sd"] is not None]
    zero_sd_ids = [item["omitted_run_id"] for item in omissions if item["remaining_sd"] == 0]
    cap_ids = [
        item["omitted_run_id"] for item in omissions
        if item["remaining_sd"] != 0 and item["required_total_under_remaining_sd"] is None
    ]
    target_states = {item["target_met_in_remaining_subset"] for item in omissions}
    minimum_sd = min(sds)
    maximum_sd = max(sds)
    minimum_requirement = min(requirements) if requirements else None
    maximum_requirement = max(requirements) if requirements else None
    omission_audit = json.dumps(omissions, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    result["leave_one_run_out"] = {
        "mean_range": [min(means), max(means)],
        "maximum_absolute_mean_shift": max(abs(value - statistics.mean(numeric)) for value in means),
        "sd_range": [minimum_sd, maximum_sd],
        "minimum_sd_omitted_run_ids": [item["omitted_run_id"] for item in omissions if item["remaining_sd"] == minimum_sd],
        "maximum_sd_omitted_run_ids": [item["omitted_run_id"] for item in omissions if item["remaining_sd"] == maximum_sd],
        "required_total_range": [minimum_requirement, maximum_requirement] if requirements else None,
        "minimum_required_total_omitted_run_ids": [
            item["omitted_run_id"] for item in omissions
            if minimum_requirement is not None and item["required_total_under_remaining_sd"] == minimum_requirement
        ],
        "maximum_required_total_omitted_run_ids": [
            item["omitted_run_id"] for item in omissions
            if maximum_requirement is not None and item["required_total_under_remaining_sd"] == maximum_requirement
        ],
        "zero_variance_after_omitting_run_ids": zero_sd_ids,
        "cap_exceeded_after_omitting_run_ids": cap_ids,
        "target_attainment_changes_across_omissions": len(target_states) > 1,
        "omission_count": len(omissions),
        "omission_audit_sha256": hashlib.sha256(omission_audit).hexdigest(),
    }
    if potential_indices:
        result["review_reasons"].append("modified_z_labels_potential_extreme_run")
    if full_sd > 0 and zero_sd_ids:
        result["review_reasons"].append("all_observed_variance_depends_on_one_run")
    if cap_ids:
        result["review_reasons"].append("projected_requirement_exceeds_cap_for_some_omissions")
    if len(target_states) > 1:
        result["review_reasons"].append("target_attainment_changes_across_omissions")
    if result["review_reasons"]:
        result["status"] = "review_required"
    return result
