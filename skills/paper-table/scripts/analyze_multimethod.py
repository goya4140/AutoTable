#!/usr/bin/env python3
"""Run a blocked rank-permutation omnibus and gated baseline post-hoc family."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import itertools
import json
import math
import random
import statistics
from collections import Counter
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "paper-table-multimethod-inference-v1"


def _load_paired():
    path = Path(__file__).with_name("analyze_paired.py")
    spec = importlib.util.spec_from_file_location("paper_table_multimethod_paired", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _finite(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _stable_key(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest(values: list[Any]) -> str:
    encoded = json.dumps(sorted(values, key=_stable_key), ensure_ascii=False, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def average_ranks(scores: list[float], direction: str) -> list[float]:
    """Return best-is-one within-block ranks with average ranks for exact ties."""
    order = sorted(range(len(scores)), key=lambda index: scores[index], reverse=direction == "max")
    ranks = [0.0] * len(scores)
    start = 0
    while start < len(order):
        end = start + 1
        while end < len(order) and scores[order[end]] == scores[order[start]]:
            end += 1
        average = ((start + 1) + end) / 2
        for position in range(start, end):
            ranks[order[position]] = average
        start = end
    return ranks


def friedman_statistic(rank_matrix: list[list[float]]) -> float:
    block_count = len(rank_matrix)
    method_count = len(rank_matrix[0])
    rank_sums = [math.fsum(row[index] for row in rank_matrix) for index in range(method_count)]
    statistic = 12 * math.fsum(value * value for value in rank_sums) / (block_count * method_count * (method_count + 1)) - 3 * block_count * (method_count + 1)
    return max(0.0, statistic)


def _unique_permutation_count(values: list[float]) -> int:
    result = math.factorial(len(values))
    for count in Counter(values).values():
        result //= math.factorial(count)
    return result


def permutation_omnibus(
    rank_matrix: list[list[float]],
    exact_max_configurations: int,
    monte_carlo_samples: int,
    seed: int,
) -> tuple[float, float, str, int, int]:
    """Permute method labels independently within complete blocks."""
    observed = friedman_statistic(rank_matrix)
    configuration_count = math.prod(_unique_permutation_count(row) for row in rank_matrix)
    tolerance = 1e-15
    if configuration_count <= exact_max_configurations:
        permutations = [sorted(set(itertools.permutations(row))) for row in rank_matrix]
        extreme = 0
        evaluated = 0
        for permuted in itertools.product(*permutations):
            evaluated += 1
            extreme += friedman_statistic([list(row) for row in permuted]) >= observed - tolerance
        if evaluated != configuration_count:
            raise RuntimeError("exact permutation configuration count mismatch")
        return observed, extreme / evaluated, "exact", evaluated, configuration_count
    rng = random.Random(seed)
    extreme = 0
    for _ in range(monte_carlo_samples):
        permuted = [rng.sample(row, len(row)) for row in rank_matrix]
        extreme += friedman_statistic(permuted) >= observed - tolerance
    return observed, (extreme + 1) / (monte_carlo_samples + 1), "monte_carlo_plus_one", monte_carlo_samples, configuration_count


def analyze(payload: dict) -> dict:
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"schema_version must be {SCHEMA_VERSION}")
    method_key = payload.get("method_key")
    block_key = payload.get("block_key")
    score_key = payload.get("score_key")
    methods = payload.get("methods", [])
    direction = payload.get("direction")
    records = payload.get("records", [])
    design = payload.get("design", {})
    omnibus = payload.get("omnibus", {})
    posthoc = payload.get("posthoc", {})
    if not all((method_key, block_key, score_key)) or not records:
        raise ValueError("method_key, block_key, score_key, and records are required")
    if len(methods) < 3 or len(methods) != len(set(methods)) or not all(isinstance(method, str) and method for method in methods):
        raise ValueError("methods must contain at least three unique nonempty strings")
    if direction not in {"min", "max"}:
        raise ValueError("direction must be min or max")
    if design.get("blocks") != "complete" or design.get("block_independence") != "independent":
        raise ValueError("design must declare complete, independent blocks")
    if not design.get("block_description") or not design.get("block_independence_evidence"):
        raise ValueError("block_description and block_independence_evidence are required")
    if omnibus.get("name") != "friedman_block_permutation":
        raise ValueError("omnibus.name must be friedman_block_permutation")
    if omnibus.get("rank_tie_policy") != "average":
        raise ValueError("rank_tie_policy must be average")
    if omnibus.get("exchangeability") != "method_labels_exchangeable_within_blocks_under_global_null" or not omnibus.get("exchangeability_rationale"):
        raise ValueError("omnibus requires a within-block method-label exchangeability declaration and rationale")
    omnibus_alpha = omnibus.get("alpha")
    exact_max = omnibus.get("exact_max_configurations", 100000)
    samples = omnibus.get("monte_carlo_samples")
    omnibus_seed = omnibus.get("seed")
    if not _finite(omnibus_alpha) or not 0 < float(omnibus_alpha) < 1:
        raise ValueError("omnibus.alpha must be between zero and one")
    if not isinstance(exact_max, int) or not 1 <= exact_max <= 1000000:
        raise ValueError("exact_max_configurations must be an integer from 1 to 1000000")
    if not isinstance(samples, int) or samples < 9999 or not isinstance(omnibus_seed, int):
        raise ValueError("omnibus requires an integer seed and at least 9999 Monte Carlo samples")

    baseline = posthoc.get("baseline")
    candidates = posthoc.get("candidates", [])
    if baseline not in methods or len(candidates) != len(set(candidates)) or set(candidates) != set(methods) - {baseline}:
        raise ValueError("posthoc must compare one declared baseline with every other method")
    if posthoc.get("baseline_selection_timing") != "predeclared_before_outcome_inspection":
        raise ValueError("posthoc baseline must be predeclared before outcome inspection")
    if posthoc.get("gatekeeping") != "require_omnibus_rejection":
        raise ValueError("posthoc must require omnibus rejection before significance markers")
    if posthoc.get("test") != "paired_sign_flip_mean" or posthoc.get("alternative") != "two-sided":
        raise ValueError("posthoc requires two-sided paired_sign_flip_mean tests")
    if posthoc.get("exchangeability") != "paired_signs_exchangeable_under_null" or not posthoc.get("exchangeability_rationale"):
        raise ValueError("posthoc sign-flip tests require an exchangeability declaration and rationale")
    exact_max_pairs = posthoc.get("exact_max_pairs", 18)
    posthoc_samples = posthoc.get("monte_carlo_samples")
    posthoc_seed = posthoc.get("seed")
    if not isinstance(exact_max_pairs, int) or not 1 <= exact_max_pairs <= 20:
        raise ValueError("posthoc.exact_max_pairs must be an integer from 1 to 20")
    if not isinstance(posthoc_samples, int) or posthoc_samples < 9999 or not isinstance(posthoc_seed, int):
        raise ValueError("posthoc test requires an integer seed and at least 9999 Monte Carlo samples")
    interval = posthoc.get("confidence_interval", {})
    if interval.get("name") != "paired_percentile_bootstrap_mean":
        raise ValueError("posthoc requires paired_percentile_bootstrap_mean intervals")
    confidence_level = interval.get("confidence_level")
    bootstrap_resamples = interval.get("resamples")
    bootstrap_seed = interval.get("seed")
    if not _finite(confidence_level) or not 0.8 <= float(confidence_level) <= 0.99:
        raise ValueError("posthoc confidence level must be from 0.8 to 0.99")
    if not isinstance(bootstrap_resamples, int) or bootstrap_resamples < 1000 or not isinstance(bootstrap_seed, int):
        raise ValueError("posthoc interval requires an integer seed and at least 1000 resamples")
    multiplicity = posthoc.get("multiplicity", {})
    family_id = multiplicity.get("family_id")
    correction = multiplicity.get("correction")
    posthoc_alpha = multiplicity.get("alpha")
    if not family_id or correction != "holm":
        raise ValueError("posthoc baseline family requires a family_id and Holm correction")
    if not _finite(posthoc_alpha) or float(posthoc_alpha) != float(omnibus_alpha):
        raise ValueError("omnibus and posthoc family must use the same alpha")

    method_set = set(methods)
    by_block: dict[str, dict[str, tuple[Any, float]]] = {}
    for record in records:
        try:
            method = record[method_key]
            block = record[block_key]
            score = record[score_key]
        except KeyError as error:
            raise ValueError(f"record lacks required field {error.args[0]!r}") from error
        if method not in method_set:
            raise ValueError(f"unexpected method {method!r}")
        if not _finite(score):
            raise ValueError(f"score must be finite for method {method!r}, block {block!r}")
        encoded_block = _stable_key(block)
        block_records = by_block.setdefault(encoded_block, {})
        if method in block_records:
            raise ValueError(f"duplicate method {method!r} in block {block!r}")
        block_records[method] = (block, float(score))
    if len(by_block) < 3:
        raise ValueError("at least three independent complete blocks are required")
    for encoded_block, block_records in by_block.items():
        if set(block_records) != method_set:
            label = next(iter(block_records.values()))[0]
            raise ValueError(f"block {label!r} is incomplete")
    ordered_blocks = sorted(by_block)
    score_matrix = [[by_block[block][method][1] for method in methods] for block in ordered_blocks]
    rank_matrix = [average_ranks(scores, direction) for scores in score_matrix]
    tie_blocks = sum(len(set(scores)) < len(scores) for scores in score_matrix)
    statistic, omnibus_p, omnibus_mode, evaluated, configurations = permutation_omnibus(
        rank_matrix, exact_max, samples, omnibus_seed
    )
    omnibus_reject = omnibus_p <= float(omnibus_alpha)
    average_rank_values = [statistics.fmean(row[index] for row in rank_matrix) for index in range(len(methods))]
    mean_scores = [statistics.fmean(row[index] for row in score_matrix) for index in range(len(methods))]

    paired = _load_paired()
    orientation = 1 if direction == "max" else -1
    raw_results = []
    pvalues = {}
    baseline_index = methods.index(baseline)
    for candidate in candidates:
        candidate_index = methods.index(candidate)
        raw_differences = [row[candidate_index] - row[baseline_index] for row in score_matrix]
        oriented = [orientation * value for value in raw_differences]
        pvalue, mode, pair_evaluated = paired.sign_flip_pvalue(
            oriented,
            exact_max_pairs,
            posthoc_samples,
            paired._derived_seed(posthoc_seed, candidate),
        )
        ci = paired.paired_bootstrap_ci(
            oriented,
            float(confidence_level),
            bootstrap_resamples,
            paired._derived_seed(bootstrap_seed, candidate),
        )
        pvalues[candidate] = pvalue
        raw_results.append({
            "method": candidate,
            "baseline": baseline,
            "n_blocks": len(ordered_blocks),
            "mean_delta_raw": statistics.fmean(raw_differences),
            "mean_improvement": statistics.fmean(oriented),
            "improvement_ci": ci,
            "confidence_level": float(confidence_level),
            "confidence_interval_method": "paired_percentile_bootstrap_mean",
            "bootstrap_resampling_unit": "complete_block",
            "bootstrap_resamples": bootstrap_resamples,
            "bootstrap_seed": paired._derived_seed(bootstrap_seed, candidate),
            "p_raw": pvalue,
            "test": "paired_sign_flip_mean",
            "pvalue_mode": mode,
            "permutations_or_samples": pair_evaluated,
            "test_seed": paired._derived_seed(posthoc_seed, candidate) if mode != "exact" else None,
        })
    adjusted = paired.holm_adjust(pvalues)
    for result in raw_results:
        result["p_adjusted"] = adjusted[result["method"]]
        result["omnibus_gate_passed"] = omnibus_reject
        result["reject_null"] = omnibus_reject and adjusted[result["method"]] <= float(posthoc_alpha)
        result["significance_marker_eligible"] = omnibus_reject

    block_labels = [by_block[block][methods[0]][0] for block in ordered_blocks]
    return {
        "schema_version": "paper-table-multimethod-inference-report-v1",
        "direction": direction,
        "design": {
            "blocks": "complete",
            "block_independence": "independent",
            "block_description": design["block_description"],
            "block_independence_evidence": design["block_independence_evidence"],
            "n_blocks": len(ordered_blocks),
            "n_methods": len(methods),
            "method_order": methods,
            "block_ids_sha256": _digest(block_labels),
        },
        "descriptive": [
            {"method": method, "mean_score": mean_scores[index], "average_rank": average_rank_values[index]}
            for index, method in enumerate(methods)
        ],
        "omnibus": {
            "name": "friedman_block_permutation",
            "statistic": statistic,
            "p_value": omnibus_p,
            "alpha": float(omnibus_alpha),
            "reject_global_null": omnibus_reject,
            "rank_tie_policy": "average",
            "blocks_with_ties": tie_blocks,
            "exchangeability": omnibus["exchangeability"],
            "exchangeability_rationale": omnibus["exchangeability_rationale"],
            "pvalue_mode": omnibus_mode,
            "evaluated_permutations_or_samples": evaluated,
            "total_label_configurations": configurations,
            "seed": omnibus_seed if omnibus_mode != "exact" else None,
        },
        "posthoc": {
            "baseline": baseline,
            "baseline_selection_timing": posthoc["baseline_selection_timing"],
            "gatekeeping": "require_omnibus_rejection",
            "family_id": family_id,
            "planned_comparisons": candidates,
            "correction": "holm",
            "alpha": float(posthoc_alpha),
            "results": raw_results,
        },
        "notes": [
            "Average rank one is best; exact score ties receive average within-block ranks.",
            "The global null permutes method labels independently within complete blocks and uses the observed tie pattern.",
            "Post-hoc effects and intervals use original scores, not ranks, and compare the predeclared baseline with every other method.",
            "Adjusted post-hoc p-values remain auditable when the omnibus gate fails, but no significance marker is eligible.",
        ],
        "provenance": payload.get("provenance", {}),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report = analyze(json.loads(args.input.read_text()))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(args.out)


if __name__ == "__main__":
    main()
