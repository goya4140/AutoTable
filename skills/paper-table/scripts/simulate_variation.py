#!/usr/bin/env python3
"""Generate explicitly assumed, non-inferential variation scenarios for paper tables."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import statistics
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "paper-table-simulated-variation-v1"
REPORT_VERSION = "paper-table-simulated-variation-report-v1"


def _finite(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _stable(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _cell_seed(seed: int, identity: dict, metric: str) -> int:
    encoded = f"{seed}|{_stable(identity)}|{metric}".encode()
    return int.from_bytes(hashlib.sha256(encoded).digest()[:8], "big")


def _standard_normal(rng: random.Random) -> float:
    # Explicit Box-Muller transform keeps the generator contract independent of random.gauss caches.
    first = rng.random()
    while first == 0:
        first = rng.random()
    second = rng.random()
    return math.sqrt(-2 * math.log(first)) * math.cos(2 * math.pi * second)


def _single_run_draw(rng: random.Random, family: str, location: float, scale: float, lower: float | None, upper: float | None) -> float:
    if family == "normal":
        return location + scale * _standard_normal(rng)
    for _ in range(100_000):
        value = location + scale * _standard_normal(rng)
        if lower <= value <= upper:
            return value
    raise RuntimeError("truncated-normal rejection sampler failed after 100000 attempts")


def _quantile(sorted_values: list[float], probability: float) -> float:
    position = probability * (len(sorted_values) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return sorted_values[lower]
    fraction = position - lower
    return sorted_values[lower] * (1 - fraction) + sorted_values[upper] * fraction


def _reject_conflicting_provenance(value: Any, path: str = "provenance") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            current = f"{path}.{key}"
            if key in {"observed", "verified", "eligible_for_inference", "eligible_for_ranking", "eligible_for_significance_markers"} and item is True:
                raise ValueError(f"{current} cannot be true for a simulated scenario")
            if key == "status" and isinstance(item, str) and item.lower() in {"observed", "verified", "exact_gold"}:
                raise ValueError(f"{current} conflicts with simulated_scenario_only status")
            _reject_conflicting_provenance(item, current)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _reject_conflicting_provenance(item, f"{path}[{index}]")


def simulate(payload: dict) -> dict:
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"schema_version must be {SCHEMA_VERSION}")
    scenario = payload.get("scenario", {})
    cells = payload.get("cells", [])
    provenance = payload.get("provenance", {})
    label = scenario.get("label")
    draws = scenario.get("draws")
    seed = scenario.get("seed")
    interval_mass = scenario.get("interval_mass")
    if not isinstance(label, str) or not label.strip():
        raise ValueError("scenario.label is required")
    if scenario.get("request_source") != "author_requested":
        raise ValueError("scenario.request_source must be author_requested")
    if scenario.get("purpose") != "illustrative_possible_variation_only":
        raise ValueError("scenario.purpose must be illustrative_possible_variation_only")
    if not isinstance(draws, int) or isinstance(draws, bool) or not 1_000 <= draws <= 100_000:
        raise ValueError("scenario.draws must be an integer from 1000 to 100000")
    if not isinstance(seed, int) or isinstance(seed, bool) or not 0 <= seed < 2**63:
        raise ValueError("scenario.seed must be an integer from 0 to 2^63-1")
    if not _finite(interval_mass) or not 0.5 <= float(interval_mass) <= 0.99:
        raise ValueError("scenario.interval_mass must be from 0.5 to 0.99")
    if not isinstance(cells, list) or not cells:
        raise ValueError("cells must be a nonempty list")
    if not isinstance(provenance, dict):
        raise ValueError("provenance must be an object")
    _reject_conflicting_provenance(provenance)

    seen = set()
    results = []
    for cell in cells:
        identity = cell.get("identity")
        metric = cell.get("metric")
        observed = cell.get("observed_value")
        direction = cell.get("direction")
        unit = cell.get("unit")
        model = cell.get("model", {})
        if not isinstance(identity, dict) or not identity:
            raise ValueError("each cell requires a nonempty identity object")
        if not isinstance(metric, str) or not metric:
            raise ValueError("each cell requires a metric")
        key = _stable({"identity": identity, "metric": metric})
        if key in seen:
            raise ValueError("duplicate identity and metric cell")
        seen.add(key)
        if not _finite(observed):
            raise ValueError("observed_value must be finite and remains an anchor, not a simulated observation")
        if direction not in {"min", "max"} or not isinstance(unit, str) or not unit:
            raise ValueError("each cell requires metric direction and unit")

        family = model.get("family")
        scale = model.get("scale_parameter")
        scale_parameterization = model.get("scale_parameterization")
        target = model.get("future_target")
        future_count = model.get("future_run_count")
        source = model.get("scale_source")
        source_detail = model.get("scale_source_detail")
        if family not in {"normal", "truncated_normal"}:
            raise ValueError("model.family must be normal or truncated_normal")
        if not _finite(scale) or float(scale) <= 0:
            raise ValueError("model.scale_parameter must be positive and finite")
        expected_parameterization = "distribution_sd" if family == "normal" else "parent_normal_sd_before_truncation"
        if scale_parameterization != expected_parameterization:
            raise ValueError(f"model.scale_parameterization must be {expected_parameterization} for {family}")
        if source not in {"author_assumption", "external_domain_evidence"} or not isinstance(source_detail, str) or not source_detail.strip():
            raise ValueError("model scale requires an allowed scale_source and nonempty scale_source_detail")
        if target not in {"future_single_run", "future_mean_of_independent_runs"}:
            raise ValueError("model.future_target must be future_single_run or future_mean_of_independent_runs")
        if target == "future_single_run":
            if future_count != 1:
                raise ValueError("future_single_run requires future_run_count equal to one")
        elif not isinstance(future_count, int) or isinstance(future_count, bool) or not 2 <= future_count <= 100:
            raise ValueError("future_mean_of_independent_runs requires future_run_count from 2 to 100")

        lower = model.get("lower_bound")
        upper = model.get("upper_bound")
        if family == "normal":
            if lower is not None or upper is not None:
                raise ValueError("normal models cannot declare bounds; use truncated_normal")
            lower_value = upper_value = None
        else:
            if not _finite(lower) or not _finite(upper) or float(lower) >= float(upper):
                raise ValueError("truncated_normal requires finite lower_bound smaller than upper_bound")
            lower_value, upper_value = float(lower), float(upper)
            normal = statistics.NormalDist(float(observed), float(scale))
            acceptance = normal.cdf(upper_value) - normal.cdf(lower_value)
            if acceptance < 1e-4:
                raise ValueError("truncated_normal bounds have less than 0.0001 parent-normal probability")
            expected_attempts = draws * future_count / acceptance
            if expected_attempts > 50_000_000:
                raise ValueError("truncated_normal expected rejection-sampling work exceeds 50000000 attempts")

        rng = random.Random(_cell_seed(seed, identity, metric))
        simulated = []
        for _ in range(draws):
            total = sum(
                _single_run_draw(rng, family, float(observed), float(scale), lower_value, upper_value)
                for _ in range(future_count)
            )
            simulated.append(total / future_count)
        ordered = sorted(simulated)
        tail = (1 - float(interval_mass)) / 2
        sample_sd = statistics.stdev(simulated)
        draw_hash = hashlib.sha256("|".join(value.hex() for value in simulated).encode()).hexdigest()
        results.append({
            "identity": identity,
            "metric": metric,
            "direction": direction,
            "unit": unit,
            "observed_anchor": float(observed),
            "simulation_model": {
                "family": family,
                "location": float(observed),
                "location_source": "observed_point_estimate_anchor",
                "scale_parameter": float(scale),
                "scale_parameterization": scale_parameterization,
                "scale_source": source,
                "scale_source_detail": source_detail,
                "lower_bound": lower_value,
                "upper_bound": upper_value,
                "future_target": target,
                "future_run_count": future_count,
            },
            "simulated_summary": {
                "draws": draws,
                "mean": statistics.mean(simulated),
                "sd": sample_sd,
                "interval_mass": float(interval_mass),
                "lower_quantile_probability": tail,
                "upper_quantile_probability": 1 - tail,
                "lower": _quantile(ordered, tail),
                "median": _quantile(ordered, 0.5),
                "upper": _quantile(ordered, 1 - tail),
                "monte_carlo_se_of_simulated_mean": sample_sd / math.sqrt(draws),
                "draw_order_sha256": draw_hash,
            },
            "observed": False,
            "status": "simulated_scenario_only",
            "eligible_for_verified_table": False,
            "eligible_for_inference": False,
            "eligible_for_ranking": False,
        })

    results.sort(key=lambda item: _stable({"identity": item["identity"], "metric": item["metric"]}))
    return {
        "schema_version": REPORT_VERSION,
        "scenario": {
            "label": f"SIMULATED SCENARIO — {label}",
            "request_source": "author_requested",
            "purpose": "illustrative_possible_variation_only",
            "draws": draws,
            "seed": seed,
            "interval_mass": float(interval_mass),
        },
        "cells": results,
        "global_contract": {
            "observed": False,
            "status": "simulated_scenario_only",
            "eligible_for_verified_table": False,
            "eligible_for_inference": False,
            "eligible_for_significance_markers": False,
            "eligible_for_best_second_emphasis": False,
            "must_remain_separate_from_observed_results": True,
        },
        "notes": [
            "All ranges are generated from author-requested assumptions, not repeated experimental observations.",
            "The observed point value is only the scenario location anchor and does not make simulated draws observed data.",
            "Do not use these scenarios for p-values, confidence claims, significance markers, rankings, or verified paper results.",
            "Prefer collecting real independent repeats; replace this scenario rather than blending it with later observations.",
        ],
        "provenance": provenance | {
            "simulation_status": "assumption_only",
            "observed": False,
            "verified": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report = simulate(json.loads(args.input.read_text()))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(args.out)


if __name__ == "__main__":
    main()
