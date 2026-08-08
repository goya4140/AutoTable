"""Curated semantic contracts for the bundled PaperBench cases."""
from __future__ import annotations

import copy


COMMON_ALLOWED = [
    "equivalent_latex_or_html",
    "consistent_precision_formatting",
    "whitespace_and_rule_adjustment",
    "row_reordering_within_comparison_group",
    "split_metric_columns_into_semantic_panels_with_repeated_identity",
]
COMMON_FORBIDDEN = [
    "change_observed_values",
    "invent_runs_or_sample_counts",
    "reinterpret_uncertainty_without_evidence",
    "compare_rows_outside_declared_groups",
    "mark_significance_without_a_declared_test",
]


def inquiry_fields(
    *,
    claim: str,
    directions: dict,
    units: dict,
    uncertainty: str,
    uncertainty_blocking: bool,
    run_count: int | None,
    comparisons: str,
    target_width: str = "full_width",
) -> list[dict]:
    uncertainty_importance = "blocking" if uncertainty_blocking else "valuable_nonblocking"
    fields = [
        {
            "id": "claim",
            "importance": "valuable_nonblocking",
            "ask_when_missing": True,
            "value": claim,
            "acceptable_default": "produce a conservative lookup-first table",
            "rationale": "The intended claim changes hierarchy and emphasis, but a conservative draft remains possible.",
            "mask_paths": ["semantic_contract.claim", "x.caption"],
        },
        {
            "id": "metric_directions",
            "importance": "blocking",
            "ask_when_missing": True,
            "value": directions,
            "rationale": "Best-value emphasis is invalid without the optimization direction.",
            "mask_paths": ["x.columns.*.direction"],
        },
        {
            "id": "metric_units",
            "importance": "blocking",
            "ask_when_missing": True,
            "value": units,
            "rationale": "A numerically correct token can still make a false claim under the wrong unit.",
            "mask_paths": ["x.columns.*.unit"],
        },
        {
            "id": "uncertainty_kind",
            "importance": uncertainty_importance,
            "ask_when_missing": True,
            "value": uncertainty,
            "rationale": "SD, SE, and confidence intervals are not interchangeable.",
            "mask_paths": ["semantic_contract.statistics.uncertainty_kind", "x.rows.*.*.sd", "x.rows.*.*.se", "x.rows.*.*.ci90", "x.rows.*.*.ci95", "x.caption", "x.notes", "x.provenance"],
        },
        {
            "id": "independent_run_count",
            "importance": uncertainty_importance,
            "ask_when_missing": True,
            "value": run_count if run_count is not None else "unavailable",
            "answer_status": "available" if run_count is not None else "unavailable",
            "rationale": "The run count is needed to interpret uncertainty and must never be guessed.",
            "mask_paths": ["semantic_contract.statistics.independent_run_count", "x.provenance.seeds", "x.caption", "x.notes"],
        },
        {
            "id": "comparison_groups",
            "importance": "blocking",
            "ask_when_missing": True,
            "value": comparisons,
            "rationale": "Ranking or bolding across incompatible settings is scientifically misleading.",
            "mask_paths": ["semantic_contract.comparison_groups", "x.rows.*.rank_eligible"],
        },
        {
            "id": "target_width",
            "importance": "valuable_nonblocking",
            "ask_when_missing": True,
            "value": target_width,
            "acceptable_default": "full_width",
            "rationale": "The target width affects column hierarchy and legibility, but a documented default is safe.",
            "mask_paths": ["semantic_contract.rendering_constraints.target_width", "semantic_contract.rendering_constraints.max_width_pt"],
        },
        {
            "id": "color_preference",
            "importance": "cosmetic",
            "ask_when_missing": False,
            "value": "no author preference; use restrained grayscale-safe styling",
            "acceptable_default": "grayscale_safe",
            "rationale": "Personal color preference should not block a scientifically valid draft.",
            "mask_paths": ["semantic_contract.rendering_constraints.color_mode"],
        },
    ]
    for field in fields:
        field.setdefault("answer_status", "available")
    return fields


CONTRACTS = {
    "neurips24-captaincook-taskgraph": {
        "claim": {
            "text": "DO achieves the strongest task-graph precision, recall, and F1 on CaptainCook4D.",
            "priority_metric_keys": ["precision", "recall", "f1"],
        },
        "row_identity_key": "method",
        "comparison_groups": [{
            "id": "all_methods",
            "row_values": ["MSGI [39]", "LLM", "Count-Based [3]", "MSG² [20]", "TGT-text (Ours)", "DO (Ours)"],
            "metric_keys": ["precision", "recall", "f1"],
        }],
        "statistics": {
            "aggregation_status": "publication_only",
            "uncertainty_kind": "ci90",
            "independent_run_count": None,
            "source": "Published cells report 90% confidence-interval half-widths; raw samples are unavailable.",
        },
        "allowed_transformations": COMMON_ALLOWED,
        "forbidden_inferences": COMMON_FORBIDDEN,
        "rendering_constraints": {"target_width": "full_width", "max_width_pt": 469, "color_mode": "grayscale_safe", "editable": True, "outputs": ["latex", "html"]},
        "inquiry_profile": {"fields": inquiry_fields(
            claim="DO achieves the strongest task-graph precision, recall, and F1 on CaptainCook4D.",
            directions={"precision": "max", "recall": "max", "f1": "max"},
            units={"precision": "%", "recall": "%", "f1": "%"},
            uncertainty="ci90",
            uncertainty_blocking=True,
            run_count=None,
            comparisons="All six methods are mutually comparable for all three metrics.",
        )},
    },
    "neurips24-restoreagent-data-size": {
        "claim": {
            "text": "The 23k-data RestoreAgent variant is best on most perceptual and ranking-oriented metrics, while the 7k variant has the highest PSNR.",
            "priority_metric_keys": ["balanced", "ranking", "lpips", "dists", "psnr"],
        },
        "row_identity_key": "method",
        "comparison_groups": [{
            "id": "all_data_sizes_and_baselines",
            "row_values": ["Random", "Human Expert", "7k", "14k", "23k"],
            "metric_keys": ["psnr", "ssim", "lpips", "dists", "balanced", "ranking"],
        }],
        "statistics": {
            "aggregation_status": "publication_only",
            "uncertainty_kind": "none",
            "independent_run_count": None,
            "source": "The publication table exposes point estimates only.",
        },
        "allowed_transformations": COMMON_ALLOWED,
        "forbidden_inferences": COMMON_FORBIDDEN,
        "rendering_constraints": {"target_width": "full_width", "max_width_pt": 469, "color_mode": "grayscale_safe", "editable": True, "outputs": ["latex", "html"]},
        "inquiry_profile": {"fields": inquiry_fields(
            claim="The 23k-data RestoreAgent variant is best on most perceptual and ranking-oriented metrics, while the 7k variant has the highest PSNR.",
            directions={"psnr": "max", "ssim": "max", "lpips": "min", "dists": "min", "balanced": "max", "ranking": "min"},
            units={"psnr": "dB", "ssim": "dimensionless", "lpips": "dimensionless", "dists": "dimensionless", "balanced": "score", "ranking": "%"},
            uncertainty="none reported",
            uncertainty_blocking=False,
            run_count=None,
            comparisons="All baselines and RestoreAgent data-size variants are compared in one group.",
        )},
    },
    "neurips24-rl-action-masking": {
        "claim": {
            "text": "No action-masking strategy dominates every environment; Generator leads Seeker, Ray leads Walker2D, and Distributional is strongest on 2D Quad.",
            "priority_metric_keys": ["seeker", "quad2d", "quad3d", "walker2d"],
        },
        "row_identity_key": "method",
        "comparison_groups": [{
            "id": "all_masking_strategies",
            "row_values": ["Baseline", "Replacement", "Ray", "Generator", "Distributional"],
            "metric_keys": ["seeker", "quad2d", "quad3d", "walker2d"],
        }],
        "statistics": {
            "aggregation_status": "publication_only",
            "uncertainty_kind": "sd",
            "independent_run_count": 10,
            "source": "Published table reports mean ± SD over ten runs per trained model.",
        },
        "allowed_transformations": COMMON_ALLOWED,
        "forbidden_inferences": COMMON_FORBIDDEN,
        "rendering_constraints": {"target_width": "full_width", "max_width_pt": 469, "color_mode": "grayscale_safe", "editable": True, "outputs": ["latex", "html"]},
        "inquiry_profile": {"fields": inquiry_fields(
            claim="No action-masking strategy dominates every environment; emphasize per-environment winners rather than one global winner.",
            directions={"seeker": "max", "quad2d": "max", "quad3d": "max", "walker2d": "max"},
            units={"seeker": "episode return", "quad2d": "episode return", "quad3d": "episode return", "walker2d": "episode return"},
            uncertainty="sd",
            uncertainty_blocking=True,
            run_count=10,
            comparisons="All five masking strategies are comparable within each environment; missing Walker2D is not imputed.",
        )},
    },
    "neurips24-rankup-utkface": {
        "claim": {
            "text": "RankUp + RDA is strongest among comparable semi-supervised methods for both label budgets and all reported metrics.",
            "priority_metric_keys": ["mae_50", "r2_50", "srcc_50", "mae_250", "r2_250", "srcc_250"],
        },
        "row_identity_key": "method",
        "comparison_groups": [{
            "id": "semi_supervised_methods",
            "row_values": ["Supervised", "Π-Model", "Mean Teacher", "CLSS", "UCVME", "MixMatch", "RankUp (Ours)", "RankUp + RDA (Ours)"],
            "excluded_row_values": ["Fully-Supervised"],
            "metric_keys": ["mae_50", "r2_50", "srcc_50", "mae_250", "r2_250", "srcc_250"],
        }],
        "statistics": {
            "aggregation_status": "author_aggregate",
            "uncertainty_kind": "sd",
            "independent_run_count": 3,
            "source": "Pinned author log reports mean ± SD over seeds 0, 1, and 2; individual runs are not released.",
        },
        "allowed_transformations": COMMON_ALLOWED,
        "forbidden_inferences": COMMON_FORBIDDEN,
        "rendering_constraints": {"target_width": "full_width", "max_width_pt": 469, "color_mode": "grayscale_safe", "editable": True, "outputs": ["latex", "html"]},
        "inquiry_profile": {"fields": inquiry_fields(
            claim="RankUp + RDA is strongest among comparable semi-supervised methods for both label budgets and all reported metrics.",
            directions={"mae_50": "min", "r2_50": "max", "srcc_50": "max", "mae_250": "min", "r2_250": "max", "srcc_250": "max"},
            units={"mae_50": "years", "r2_50": "dimensionless", "srcc_50": "dimensionless", "mae_250": "years", "r2_250": "dimensionless", "srcc_250": "dimensionless"},
            uncertainty="sd",
            uncertainty_blocking=True,
            run_count=3,
            comparisons="Fully-Supervised is an upper bound and must not participate in best-value emphasis.",
        )},
    },
    "neurips24-agentboard-proprietary": {
        "claim": {
            "text": "GPT-4 has higher progress and success rates than Claude2 in every reported AgentBoard environment and in the nine-environment average.",
            "priority_metric_keys": ["progress_avg", "success_avg"],
        },
        "row_identity_key": "model",
        "comparison_groups": [{
            "id": "proprietary_models",
            "row_values": ["GPT-4", "Claude2"],
            "metric_keys": [
                f"{metric}_{task}"
                for task in ("alf", "sw", "ba", "jc", "pl", "ws", "wa", "tq", "to", "avg")
                for metric in ("progress", "success")
            ],
        }],
        "statistics": {
            "aggregation_status": "author_aggregate",
            "uncertainty_kind": "none",
            "independent_run_count": None,
            "source": "Pinned author-site JSON exposes the published point estimates; confidence intervals are outside this Table 3 excerpt.",
        },
        "allowed_transformations": COMMON_ALLOWED,
        "forbidden_inferences": COMMON_FORBIDDEN,
        "rendering_constraints": {"target_width": "full_width", "max_width_pt": 469, "color_mode": "grayscale_safe", "editable": True, "outputs": ["latex", "html"]},
        "inquiry_profile": {"fields": inquiry_fields(
            claim="GPT-4 has higher progress and success rates than Claude2 in every reported AgentBoard environment and in the nine-environment average.",
            directions={
                f"{metric}_{task}": "max"
                for task in ("alf", "sw", "ba", "jc", "pl", "ws", "wa", "tq", "to", "avg")
                for metric in ("progress", "success")
            },
            units={
                f"{metric}_{task}": "%"
                for task in ("alf", "sw", "ba", "jc", "pl", "ws", "wa", "tq", "to", "avg")
                for metric in ("progress", "success")
            },
            uncertainty="none reported in the excerpt",
            uncertainty_blocking=False,
            run_count=None,
            comparisons="GPT-4 and Claude2 use the same AgentBoard task definitions and are comparable within every metric column in this excerpt.",
        )},
    },
    "neurips24-swtbench-models": {
        "claim": {
            "text": "No single SWE-Agent backbone dominates every metric: GPT-4 is most often well-formed, Mistral Large 2 has the highest success rate, and Claude 3.5 Sonnet leads fail-to-any and change coverage.",
            "priority_metric_keys": ["well_formed", "success", "fail_to_any", "coverage"],
        },
        "row_identity_key": "model",
        "comparison_groups": [{
            "id": "swe_agent_backbones",
            "row_values": ["Mistral Large 2", "GPT-4", "Claude 3.5 Sonnet", "GPT-4o mini", "Claude 3.0 Haiku", "Mixtral 8x22B"],
            "metric_keys": ["well_formed", "success", "fail_to_any", "coverage"],
        }],
        "statistics": {
            "aggregation_status": "raw_recomputed",
            "uncertainty_kind": "none",
            "independent_run_count": None,
            "observation_count": 276,
            "source": "Author-released per-instance reports are recomputed using the paper-time evaluator: rates use 276 instances and change coverage uses 273 countable gold-coverage instances.",
        },
        "allowed_transformations": COMMON_ALLOWED,
        "forbidden_inferences": COMMON_FORBIDDEN,
        "rendering_constraints": {"target_width": "single_column", "max_width_pt": 234.5, "color_mode": "grayscale_safe", "editable": True, "outputs": ["latex", "html"]},
        "inquiry_profile": {"fields": inquiry_fields(
            claim="No single SWE-Agent backbone dominates every metric; retain per-metric emphasis rather than declaring one overall winner.",
            directions={"well_formed": "max", "success": "max", "fail_to_any": "max", "coverage": "max"},
            units={"well_formed": "%", "success": "%", "fail_to_any": "%", "coverage": "%"},
            uncertainty="none; deterministic per-instance aggregation",
            uncertainty_blocking=False,
            run_count=None,
            comparisons="All six language-model backbones use the same SWE-Agent setup and SWT-Bench Lite denominator and are comparable within every metric.",
            target_width="single_column",
        )},
    },
}


UNITS = {
    "neurips24-captaincook-taskgraph": {"precision": "%", "recall": "%", "f1": "%"},
    "neurips24-restoreagent-data-size": {"psnr": "dB", "ssim": "dimensionless", "lpips": "dimensionless", "dists": "dimensionless", "balanced": "score", "ranking": "%"},
    "neurips24-rl-action-masking": {"seeker": "episode return", "quad2d": "episode return", "quad3d": "episode return", "walker2d": "episode return"},
    "neurips24-rankup-utkface": {"mae_50": "years", "r2_50": "dimensionless", "srcc_50": "dimensionless", "mae_250": "years", "r2_250": "dimensionless", "srcc_250": "dimensionless"},
    "neurips24-agentboard-proprietary": {
        f"{metric}_{task}": "%"
        for task in ("alf", "sw", "ba", "jc", "pl", "ws", "wa", "tq", "to", "avg")
        for metric in ("progress", "success")
    },
    "neurips24-swtbench-models": {"well_formed": "%", "success": "%", "fail_to_any": "%", "coverage": "%"},
}


def contract_for(case_id: str) -> dict:
    contract = copy.deepcopy(CONTRACTS[case_id])
    for field in contract["inquiry_profile"]["fields"]:
        if field["id"] == "comparison_groups":
            field["value"] = copy.deepcopy(contract["comparison_groups"])
    return contract


def enrich_spec(case_id: str, spec: dict) -> dict:
    result = copy.deepcopy(spec)
    units = UNITS[case_id]
    for column in result["columns"]:
        if column.get("kind") == "metric":
            column["unit"] = units[column["key"]]
    return result
