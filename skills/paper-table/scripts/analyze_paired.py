#!/usr/bin/env python3
"""Run audited unit- or cluster-level sign-flip comparisons and bootstrap CIs."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any


SCHEMA_V1 = "paper-table-paired-inference-v1"
SCHEMA_V2 = "paper-table-paired-inference-v2"
SCHEMA_VERSION = SCHEMA_V1  # Backward-compatible import for existing v1 callers.


def _finite(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _stable_key(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest(values: list[Any]) -> str:
    encoded = json.dumps(sorted(values, key=_stable_key), ensure_ascii=False, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _derived_seed(seed: int, label: str) -> int:
    material = f"{seed}:{label}".encode()
    return int.from_bytes(hashlib.sha256(material).digest()[:8], "big")


def _quantile(sorted_values: list[float], probability: float) -> float:
    if not sorted_values:
        raise ValueError("quantile requires at least one value")
    position = (len(sorted_values) - 1) * probability
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return sorted_values[lower]
    fraction = position - lower
    return sorted_values[lower] * (1 - fraction) + sorted_values[upper] * fraction


def sign_flip_pvalue(differences: list[float], exact_max_pairs: int, samples: int, seed: int) -> tuple[float, str, int]:
    observed = abs(statistics.fmean(differences))
    tolerance = 1e-15
    n = len(differences)
    if n <= exact_max_pairs:
        total = 1 << n
        extreme = 0
        for mask in range(total):
            statistic = math.fsum(value if mask & (1 << index) else -value for index, value in enumerate(differences)) / n
            extreme += abs(statistic) >= observed - tolerance
        return extreme / total, "exact", total
    rng = random.Random(seed)
    extreme = 0
    for _ in range(samples):
        statistic = math.fsum(value if rng.getrandbits(1) else -value for value in differences) / n
        extreme += abs(statistic) >= observed - tolerance
    return (extreme + 1) / (samples + 1), "monte_carlo_plus_one", samples


def paired_bootstrap_ci(differences: list[float], confidence_level: float, resamples: int, seed: int) -> list[float]:
    rng = random.Random(seed)
    n = len(differences)
    means = []
    for _ in range(resamples):
        means.append(math.fsum(differences[rng.randrange(n)] for _ in range(n)) / n)
    means.sort()
    alpha = 1 - confidence_level
    return [_quantile(means, alpha / 2), _quantile(means, 1 - alpha / 2)]


def cluster_bootstrap_ci(
    cluster_differences: list[list[float]],
    estimand: str,
    confidence_level: float,
    resamples: int,
    seed: int,
) -> list[float]:
    """Resample intact clusters and recompute the declared mean estimand."""
    rng = random.Random(seed)
    cluster_count = len(cluster_differences)
    means = []
    for _ in range(resamples):
        sampled = [cluster_differences[rng.randrange(cluster_count)] for _ in range(cluster_count)]
        if estimand == "equal_cluster_mean":
            means.append(statistics.fmean(statistics.fmean(cluster) for cluster in sampled))
        else:
            count = sum(len(cluster) for cluster in sampled)
            means.append(math.fsum(value for cluster in sampled for value in cluster) / count)
    means.sort()
    alpha = 1 - confidence_level
    return [_quantile(means, alpha / 2), _quantile(means, 1 - alpha / 2)]


def holm_adjust(pvalues: dict[str, float]) -> dict[str, float]:
    ordered = sorted(pvalues.items(), key=lambda item: (item[1], item[0]))
    adjusted = {}
    running = 0.0
    count = len(ordered)
    for index, (label, pvalue) in enumerate(ordered):
        running = max(running, min(1.0, (count - index) * pvalue))
        adjusted[label] = running
    return adjusted


def _analyze_v1(payload: dict) -> dict:
    method_key = payload.get("method_key")
    unit_key = payload.get("unit_key")
    score_key = payload.get("score_key")
    baseline = payload.get("baseline")
    candidates = payload.get("candidates", [])
    direction = payload.get("direction")
    records = payload.get("records", [])
    design = payload.get("design", {})
    test = payload.get("test", {})
    interval = payload.get("confidence_interval", {})
    multiplicity = payload.get("multiplicity", {})
    if not all((method_key, unit_key, score_key, baseline)) or not candidates or not records:
        raise ValueError("method_key, unit_key, score_key, baseline, candidates, and records are required")
    if len(candidates) != len(set(candidates)) or baseline in candidates:
        raise ValueError("candidates must be unique and must not include the baseline")
    if direction not in {"min", "max"}:
        raise ValueError("direction must be min or max")
    if design.get("pairing") != "complete" or design.get("unit_independence") != "independent":
        raise ValueError("design must declare complete pairing and independent paired units")
    if not design.get("unit_description") or not design.get("unit_independence_evidence"):
        raise ValueError("design.unit_description and unit_independence_evidence are required")
    cluster_key = design.get("cluster_key")
    if test.get("name") != "paired_sign_flip_mean" or test.get("alternative") != "two-sided":
        raise ValueError("v1 requires a two-sided paired_sign_flip_mean test")
    if test.get("exchangeability") != "paired_signs_exchangeable_under_null" or not test.get("exchangeability_rationale"):
        raise ValueError("the sign-flip test requires an explicit paired-sign exchangeability declaration and rationale")
    exact_max = test.get("exact_max_pairs", 18)
    samples = test.get("monte_carlo_samples")
    test_seed = test.get("seed")
    if not isinstance(exact_max, int) or not 1 <= exact_max <= 20:
        raise ValueError("test.exact_max_pairs must be an integer from 1 to 20")
    if not isinstance(samples, int) or samples < 9999 or not isinstance(test_seed, int):
        raise ValueError("test requires an integer seed and at least 9999 Monte Carlo samples")
    if interval.get("name") != "paired_percentile_bootstrap_mean":
        raise ValueError("v1 requires paired_percentile_bootstrap_mean confidence intervals")
    confidence_level = interval.get("confidence_level")
    bootstrap_resamples = interval.get("resamples")
    bootstrap_seed = interval.get("seed")
    if not _finite(confidence_level) or not 0.8 <= float(confidence_level) <= 0.99:
        raise ValueError("confidence_interval.confidence_level must be from 0.8 to 0.99")
    if not isinstance(bootstrap_resamples, int) or bootstrap_resamples < 1000 or not isinstance(bootstrap_seed, int):
        raise ValueError("confidence interval requires an integer seed and at least 1000 resamples")
    alpha = multiplicity.get("alpha")
    correction = multiplicity.get("correction")
    family_id = multiplicity.get("family_id")
    if not _finite(alpha) or not 0 < float(alpha) < 1 or not family_id:
        raise ValueError("multiplicity requires alpha and family_id")
    if len(candidates) > 1 and correction != "holm":
        raise ValueError("multiple comparisons require Holm correction in v1")
    if len(candidates) == 1 and correction not in {"none", "holm"}:
        raise ValueError("single comparisons require correction none or holm")

    allowed_methods = {baseline, *candidates}
    by_method: dict[str, dict[str, tuple[Any, float]]] = defaultdict(dict)
    unit_to_cluster = {}
    for record in records:
        try:
            method = record[method_key]
            unit = record[unit_key]
            score = record[score_key]
        except KeyError as error:
            raise ValueError(f"record lacks required field {error.args[0]!r}") from error
        if method not in allowed_methods:
            raise ValueError(f"unexpected method {method!r} outside the declared comparison family")
        if not _finite(score):
            raise ValueError(f"score must be finite for method {method!r}, unit {unit!r}")
        encoded_unit = _stable_key(unit)
        if cluster_key:
            if cluster_key not in record:
                raise ValueError(f"record lacks declared cluster field {cluster_key!r}")
            encoded_cluster = _stable_key(record[cluster_key])
            if encoded_unit in unit_to_cluster and unit_to_cluster[encoded_unit] != encoded_cluster:
                raise ValueError(f"paired unit {unit!r} maps to multiple clusters")
            unit_to_cluster[encoded_unit] = encoded_cluster
        if encoded_unit in by_method[method]:
            raise ValueError(f"duplicate paired unit {unit!r} for method {method!r}")
        by_method[method][encoded_unit] = (unit, float(score))
    if cluster_key:
        cluster_units: dict[str, set[str]] = defaultdict(set)
        for unit, cluster in unit_to_cluster.items():
            cluster_units[cluster].add(unit)
        repeated = [cluster for cluster, units in cluster_units.items() if len(units) > 1]
        if repeated:
            raise ValueError("correlated units are nested within clusters; aggregate to one independent unit per cluster or use a declared clustered method")
    if set(by_method) != allowed_methods:
        raise ValueError("every declared method must have records")
    baseline_units = set(by_method[baseline])
    if len(baseline_units) < 2:
        raise ValueError("at least two independent paired units are required")
    for method in candidates:
        if set(by_method[method]) != baseline_units:
            raise ValueError(f"method {method!r} does not share the complete baseline unit set")
    ordered_units = sorted(baseline_units)

    raw_results = []
    pvalues = {}
    orientation = 1 if direction == "max" else -1
    for method in candidates:
        raw_differences = [by_method[method][unit][1] - by_method[baseline][unit][1] for unit in ordered_units]
        oriented = [orientation * value for value in raw_differences]
        pvalue, mode, evaluated = sign_flip_pvalue(
            oriented,
            exact_max,
            samples,
            _derived_seed(test_seed, method),
        )
        ci = paired_bootstrap_ci(
            oriented,
            float(confidence_level),
            bootstrap_resamples,
            _derived_seed(bootstrap_seed, method),
        )
        pvalues[method] = pvalue
        raw_results.append({
            "method": method,
            "baseline": baseline,
            "n_pairs": len(oriented),
            "mean_delta_raw": statistics.fmean(raw_differences),
            "mean_improvement": statistics.fmean(oriented),
            "improvement_ci": ci,
            "confidence_level": float(confidence_level),
            "confidence_interval_method": "paired_percentile_bootstrap_mean",
            "bootstrap_resamples": bootstrap_resamples,
            "bootstrap_seed": _derived_seed(bootstrap_seed, method),
            "p_raw": pvalue,
            "test": "paired_sign_flip_mean",
            "alternative": "two-sided",
            "pvalue_mode": mode,
            "permutations_or_samples": evaluated,
            "test_seed": _derived_seed(test_seed, method) if mode != "exact" else None,
            "paired_unit_ids_sha256": _digest([by_method[baseline][unit][0] for unit in ordered_units]),
        })
    adjusted = holm_adjust(pvalues) if correction == "holm" else dict(pvalues)
    for result in raw_results:
        result["p_adjusted"] = adjusted[result["method"]]
        result["reject_null"] = adjusted[result["method"]] <= float(alpha)
        result["significance_marker_eligible"] = True

    return {
        "schema_version": "paper-table-paired-inference-report-v1",
        "baseline": baseline,
        "direction": direction,
        "design": {
            "pairing": "complete",
            "unit_independence": "independent",
            "unit_description": design["unit_description"],
            "unit_independence_evidence": design["unit_independence_evidence"],
            "cluster_key": cluster_key,
            "n_units": len(ordered_units),
            "unit_ids_sha256": _digest([by_method[baseline][unit][0] for unit in ordered_units]),
        },
        "multiplicity": {
            "family_id": family_id,
            "planned_comparisons": candidates,
            "correction": correction,
            "alpha": float(alpha),
        },
        "test": {
            "name": "paired_sign_flip_mean",
            "alternative": "two-sided",
            "exchangeability": test["exchangeability"],
            "exchangeability_rationale": test["exchangeability_rationale"],
            "exact_max_pairs": exact_max,
            "monte_carlo_samples": samples,
            "seed": test_seed,
        },
        "results": raw_results,
        "notes": [
            "Positive mean improvement favors the candidate after applying the declared metric direction.",
            "The percentile bootstrap interval resamples complete paired units; it is an approximate interval and its seed/resample count are recorded.",
            "Significance markers are eligible only for this complete, independent, explicitly corrected comparison family.",
        ],
        "provenance": payload.get("provenance", {}),
    }


def _analyze_v2_clustered(payload: dict) -> dict:
    method_key = payload.get("method_key")
    unit_key = payload.get("unit_key")
    score_key = payload.get("score_key")
    baseline = payload.get("baseline")
    candidates = payload.get("candidates", [])
    direction = payload.get("direction")
    records = payload.get("records", [])
    design = payload.get("design", {})
    test = payload.get("test", {})
    interval = payload.get("confidence_interval", {})
    multiplicity = payload.get("multiplicity", {})
    if not all((method_key, unit_key, score_key, baseline)) or not candidates or not records:
        raise ValueError("method_key, unit_key, score_key, baseline, candidates, and records are required")
    if len(candidates) != len(set(candidates)) or baseline in candidates:
        raise ValueError("candidates must be unique and must not include the baseline")
    if direction not in {"min", "max"}:
        raise ValueError("direction must be min or max")
    if design.get("pairing") != "complete":
        raise ValueError("clustered inference requires complete pairing")
    if design.get("unit_independence") != "nested_within_independent_clusters":
        raise ValueError("v2 clustered inference requires unit_independence nested_within_independent_clusters")
    if not design.get("unit_description"):
        raise ValueError("design.unit_description is required")
    cluster_key = design.get("cluster_key")
    if not cluster_key or design.get("cluster_independence") != "independent":
        raise ValueError("v2 clustered inference requires cluster_key and independent clusters")
    if not design.get("cluster_description") or not design.get("cluster_independence_evidence"):
        raise ValueError("cluster_description and cluster_independence_evidence are required")
    estimand = design.get("cluster_estimand")
    if estimand not in {"equal_cluster_mean", "unit_weighted_mean"}:
        raise ValueError("cluster_estimand must be equal_cluster_mean or unit_weighted_mean")
    if test.get("name") != "cluster_sign_flip_mean" or test.get("alternative") != "two-sided":
        raise ValueError("v2 clustered inference requires a two-sided cluster_sign_flip_mean test")
    if test.get("exchangeability") != "cluster_signs_exchangeable_under_null" or not test.get("exchangeability_rationale"):
        raise ValueError("the cluster sign-flip test requires an explicit cluster-sign exchangeability declaration and rationale")
    exact_max = test.get("exact_max_clusters", 18)
    samples = test.get("monte_carlo_samples")
    test_seed = test.get("seed")
    if not isinstance(exact_max, int) or not 1 <= exact_max <= 20:
        raise ValueError("test.exact_max_clusters must be an integer from 1 to 20")
    if not isinstance(samples, int) or samples < 9999 or not isinstance(test_seed, int):
        raise ValueError("test requires an integer seed and at least 9999 Monte Carlo samples")
    if interval.get("name") != "cluster_percentile_bootstrap_mean":
        raise ValueError("v2 clustered inference requires cluster_percentile_bootstrap_mean confidence intervals")
    confidence_level = interval.get("confidence_level")
    bootstrap_resamples = interval.get("resamples")
    bootstrap_seed = interval.get("seed")
    if not _finite(confidence_level) or not 0.8 <= float(confidence_level) <= 0.99:
        raise ValueError("confidence_interval.confidence_level must be from 0.8 to 0.99")
    if not isinstance(bootstrap_resamples, int) or bootstrap_resamples < 1000 or not isinstance(bootstrap_seed, int):
        raise ValueError("confidence interval requires an integer seed and at least 1000 resamples")
    alpha = multiplicity.get("alpha")
    correction = multiplicity.get("correction")
    family_id = multiplicity.get("family_id")
    if not _finite(alpha) or not 0 < float(alpha) < 1 or not family_id:
        raise ValueError("multiplicity requires alpha and family_id")
    if len(candidates) > 1 and correction != "holm":
        raise ValueError("multiple comparisons require Holm correction in v2")
    if len(candidates) == 1 and correction not in {"none", "holm"}:
        raise ValueError("single comparisons require correction none or holm")

    allowed_methods = {baseline, *candidates}
    by_method: dict[str, dict[str, tuple[Any, float]]] = defaultdict(dict)
    unit_to_cluster: dict[str, tuple[Any, str]] = {}
    for record in records:
        try:
            method = record[method_key]
            unit = record[unit_key]
            cluster = record[cluster_key]
            score = record[score_key]
        except KeyError as error:
            raise ValueError(f"record lacks required field {error.args[0]!r}") from error
        if method not in allowed_methods:
            raise ValueError(f"unexpected method {method!r} outside the declared comparison family")
        if not _finite(score):
            raise ValueError(f"score must be finite for method {method!r}, unit {unit!r}")
        encoded_unit = _stable_key(unit)
        encoded_cluster = _stable_key(cluster)
        if encoded_unit in unit_to_cluster and unit_to_cluster[encoded_unit][1] != encoded_cluster:
            raise ValueError(f"paired unit {unit!r} maps to multiple clusters")
        unit_to_cluster[encoded_unit] = (cluster, encoded_cluster)
        if encoded_unit in by_method[method]:
            raise ValueError(f"duplicate paired unit {unit!r} for method {method!r}")
        by_method[method][encoded_unit] = (unit, float(score))
    if set(by_method) != allowed_methods:
        raise ValueError("every declared method must have records")
    baseline_units = set(by_method[baseline])
    if len(baseline_units) < 2:
        raise ValueError("at least two paired units are required")
    for method in candidates:
        if set(by_method[method]) != baseline_units:
            raise ValueError(f"method {method!r} does not share the complete baseline unit set")
    ordered_units = sorted(baseline_units)
    ordered_clusters = sorted({value[1] for value in unit_to_cluster.values()})
    if len(ordered_clusters) < 4:
        raise ValueError("clustered inference requires at least four independent clusters")
    cluster_labels = {encoded: label for label, encoded in unit_to_cluster.values()}
    cluster_sizes = [sum(unit_to_cluster[unit][1] == cluster for unit in ordered_units) for cluster in ordered_clusters]

    raw_results = []
    pvalues = {}
    orientation = 1 if direction == "max" else -1
    for method in candidates:
        raw_by_cluster: dict[str, list[float]] = defaultdict(list)
        for unit in ordered_units:
            difference = by_method[method][unit][1] - by_method[baseline][unit][1]
            raw_by_cluster[unit_to_cluster[unit][1]].append(difference)
        oriented_by_cluster = [
            [orientation * value for value in raw_by_cluster[cluster]]
            for cluster in ordered_clusters
        ]
        if estimand == "equal_cluster_mean":
            raw_contributions = [statistics.fmean(raw_by_cluster[cluster]) for cluster in ordered_clusters]
            oriented_contributions = [statistics.fmean(cluster) for cluster in oriented_by_cluster]
        else:
            raw_contributions = [math.fsum(raw_by_cluster[cluster]) for cluster in ordered_clusters]
            oriented_contributions = [math.fsum(cluster) for cluster in oriented_by_cluster]
        pvalue, mode, evaluated = sign_flip_pvalue(
            oriented_contributions,
            exact_max,
            samples,
            _derived_seed(test_seed, method),
        )
        ci = cluster_bootstrap_ci(
            oriented_by_cluster,
            estimand,
            float(confidence_level),
            bootstrap_resamples,
            _derived_seed(bootstrap_seed, method),
        )
        if estimand == "equal_cluster_mean":
            raw_effect = statistics.fmean(raw_contributions)
            oriented_effect = statistics.fmean(oriented_contributions)
        else:
            raw_effect = math.fsum(raw_contributions) / len(ordered_units)
            oriented_effect = math.fsum(oriented_contributions) / len(ordered_units)
        pvalues[method] = pvalue
        raw_results.append({
            "method": method,
            "baseline": baseline,
            "n_pairs": len(ordered_units),
            "n_clusters": len(ordered_clusters),
            "cluster_estimand": estimand,
            "mean_delta_raw": raw_effect,
            "mean_improvement": oriented_effect,
            "improvement_ci": ci,
            "confidence_level": float(confidence_level),
            "confidence_interval_method": "cluster_percentile_bootstrap_mean",
            "bootstrap_resampling_unit": "cluster",
            "bootstrap_resamples": bootstrap_resamples,
            "bootstrap_seed": _derived_seed(bootstrap_seed, method),
            "p_raw": pvalue,
            "test": "cluster_sign_flip_mean",
            "randomization_unit": "cluster",
            "alternative": "two-sided",
            "pvalue_mode": mode,
            "permutations_or_samples": evaluated,
            "test_seed": _derived_seed(test_seed, method) if mode != "exact" else None,
            "paired_unit_ids_sha256": _digest([by_method[baseline][unit][0] for unit in ordered_units]),
            "cluster_ids_sha256": _digest([cluster_labels[cluster] for cluster in ordered_clusters]),
            "cluster_sizes": [len(raw_by_cluster[cluster]) for cluster in ordered_clusters],
        })
    adjusted = holm_adjust(pvalues) if correction == "holm" else dict(pvalues)
    for result in raw_results:
        result["p_adjusted"] = adjusted[result["method"]]
        result["reject_null"] = adjusted[result["method"]] <= float(alpha)
        result["significance_marker_eligible"] = True

    return {
        "schema_version": "paper-table-paired-inference-report-v2",
        "baseline": baseline,
        "direction": direction,
        "design": {
            "pairing": "complete",
            "unit_independence": "nested_within_independent_clusters",
            "unit_description": design["unit_description"],
            "cluster_key": cluster_key,
            "cluster_description": design["cluster_description"],
            "cluster_independence": "independent",
            "cluster_independence_evidence": design["cluster_independence_evidence"],
            "cluster_estimand": estimand,
            "n_units": len(ordered_units),
            "n_clusters": len(ordered_clusters),
            "cluster_size_summary": {
                "minimum": min(cluster_sizes),
                "maximum": max(cluster_sizes),
                "unequal": len(set(cluster_sizes)) > 1,
            },
            "unit_ids_sha256": _digest([by_method[baseline][unit][0] for unit in ordered_units]),
            "cluster_ids_sha256": _digest([cluster_labels[cluster] for cluster in ordered_clusters]),
        },
        "multiplicity": {
            "family_id": family_id,
            "planned_comparisons": candidates,
            "correction": correction,
            "alpha": float(alpha),
        },
        "test": {
            "name": "cluster_sign_flip_mean",
            "alternative": "two-sided",
            "exchangeability": test["exchangeability"],
            "exchangeability_rationale": test["exchangeability_rationale"],
            "randomization_unit": "cluster",
            "exact_max_clusters": exact_max,
            "monte_carlo_samples": samples,
            "seed": test_seed,
        },
        "diagnostics": {
            "few_clusters_warning": len(ordered_clusters) < 10,
            "exact_sign_configurations": (1 << len(ordered_clusters)) if len(ordered_clusters) <= exact_max else None,
            "best_case_two_sided_exact_p_resolution": (2 / (1 << len(ordered_clusters))) if len(ordered_clusters) <= exact_max else None,
        },
        "results": raw_results,
        "notes": [
            "Positive mean improvement favors the candidate after applying the declared metric direction.",
            "Sign flips and percentile-bootstrap resampling operate on intact independent clusters, never on nested units.",
            "The declared cluster estimand determines whether clusters or nested units receive equal weight.",
            *(["Fewer than ten independent clusters are available; interval coverage may be unstable, and extra resamples do not create independent information."] if len(ordered_clusters) < 10 else []),
            "Significance markers are eligible only for this complete, explicitly clustered and corrected comparison family.",
        ],
        "provenance": payload.get("provenance", {}),
    }


def analyze(payload: dict) -> dict:
    schema_version = payload.get("schema_version")
    if schema_version == SCHEMA_V1:
        return _analyze_v1(payload)
    if schema_version == SCHEMA_V2:
        return _analyze_v2_clustered(payload)
    raise ValueError(f"schema_version must be {SCHEMA_V1} or {SCHEMA_V2}")


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
