#!/usr/bin/env python3
"""Recommend an evidence-backed visual strategy for an academic table spec."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

ABLATION_HINTS = {"ablation", "component", "configuration", "module", "setting", "variant"}
CHANGE_HINTS = {"change", "delta", "difference", "gain", "improvement", "increase", "decrease"}


def scalar(cell):
    if isinstance(cell, (int, float)) and not isinstance(cell, bool) and math.isfinite(cell):
        return float(cell)
    if isinstance(cell, dict) and isinstance(cell.get("mean"), (int, float)) and math.isfinite(cell["mean"]):
        return float(cell["mean"])
    if isinstance(cell, str):
        try:
            value = float(cell)
            return value if math.isfinite(value) else None
        except ValueError:
            return None
    return None


def uncertainty_kinds(spec):
    kinds = set()
    for row in spec.get("rows", []):
        for value in row.values():
            if not isinstance(value, dict):
                continue
            kinds.update(key for key in ("sd", "se", "ci90", "ci95", "values") if value.get(key) is not None)
    return sorted(kinds)


def claim_text(spec, case):
    claim = spec.get("claim")
    if isinstance(claim, str):
        return claim
    contract = (case or {}).get("semantic_contract", {})
    claim = contract.get("claim", {})
    return claim.get("text", "") if isinstance(claim, dict) else str(claim or "")


def target_width(spec, case, explicit):
    if explicit is not None:
        return explicit
    constraints = (case or {}).get("semantic_contract", {}).get("rendering_constraints", {})
    value = constraints.get("max_width_pt")
    return float(value) if isinstance(value, (int, float)) else None


def metric_groups(metrics):
    groups = []
    for column in metrics:
        group = column.get("group")
        if group and group not in groups:
            groups.append(group)
    return groups


def comparable_groups(case):
    return (case or {}).get("semantic_contract", {}).get("comparison_groups", [])


def priority_metrics(spec, case, metric_keys):
    claim = (case or {}).get("semantic_contract", {}).get("claim", {})
    requested = claim.get("priority_metric_keys", []) if isinstance(claim, dict) else []
    return [key for key in requested if key in metric_keys]


def choose_form(spec, case=None, width=None):
    columns = spec.get("columns", [])
    metrics = [column for column in columns if column.get("kind") == "metric"]
    texts = [column for column in columns if column.get("kind") != "metric"]
    rows = spec.get("rows", [])
    groups = metric_groups(metrics)
    claim = claim_text(spec, case).lower()
    values = [scalar(row.get(metrics[0]["key"])) for row in rows] if len(metrics) == 1 else []
    values = [value for value in values if value is not None]
    signed = bool(values) and min(values) < 0 < max(values)
    change_claim = any(token in claim for token in CHANGE_HINTS)
    ablation = any(
        any(token in f"{column.get('key', '')} {column.get('label', '')}".lower() for token in ABLATION_HINTS)
        for column in texts
    )
    if len(metrics) == 1 and 2 <= len(rows) <= 16 and (signed or change_claim):
        return ("diverging_table_chart" if signed else "ranked_table_chart"), [
            "one outcome metric supports a position encoding",
            "the rows remain few enough for exact value labels",
            "signed values require a visible zero baseline" if signed else "the stated claim concerns change or improvement",
        ]
    if ablation and metrics:
        return "ablation_table", ["the input exposes an explicit variant/component dimension", "exact cells matter for attributing component effects"]
    if len(metrics) >= 6 and len(groups) >= 2 and width is not None and width <= 360:
        return "semantic_panel_table", [f"{len(metrics)} metrics form {len(groups)} named families", f"the {width:g} pt target is narrow for one comparison surface"]
    if len(rows) >= 6 and 1 <= len(metrics) <= 3 and claim:
        return "compact_leaderboard_table", ["many methods share a small metric set", "a supplied claim makes ranking salience useful"]
    return "comparison_table", [
        "multiple exact values must remain directly retrievable" if len(metrics) > 1 else "no supplied evidence makes a chart encoding necessary",
        "a conventional table is the conservative, editable default",
    ]


def advise(spec, case=None, target_width_pt=None):
    columns = spec.get("columns", [])
    metrics = [column for column in columns if column.get("kind") == "metric"]
    texts = [column for column in columns if column.get("kind") != "metric"]
    rows = spec.get("rows", [])
    keys = [column.get("key") for column in metrics]
    groups = metric_groups(metrics)
    kinds = uncertainty_kinds(spec)
    claim = claim_text(spec, case)
    width = target_width(spec, case, target_width_pt)
    form, reasons = choose_form(spec, case, width)
    missing_direction = [column.get("key") for column in metrics if column.get("direction") not in {"min", "max"}]
    missing_unit = [column.get("key") for column in metrics if not column.get("unit")]
    priorities = priority_metrics(spec, case, keys)
    run_identifiers = [column.get("key") for column in texts if str(column.get("key", "")).lower() in {"seed", "run", "trial"}]
    warnings = []
    questions = []
    if run_identifiers:
        warnings.append("Per-run identifiers are still present; aggregate only after confirming independence and the requested uncertainty statistic.")
        questions.append({"field_id": "uncertainty_source", "importance": "blocking", "text": f"Are {', '.join(run_identifiers)} independent repeats, and should the final table report SD, SE, or a confidence interval?"})
    if missing_direction:
        warnings.append("Do not rank or emphasize metrics whose optimization direction is unresolved.")
        questions.append({"field_id": "metric_directions", "importance": "blocking", "text": f"Is higher or lower better for: {', '.join(missing_direction)}?"})
    if missing_unit:
        warnings.append("Add units, including `dimensionless`, before publication.")
        questions.append({"field_id": "metric_units", "importance": "blocking", "text": f"What unit should be shown for: {', '.join(missing_unit)}?"})
    if len(kinds) > 1:
        warnings.append(f"Mixed uncertainty encodings ({', '.join(kinds)}) must be explained separately; do not collapse them into one ± label.")
    if not claim:
        questions.append({"field_id": "claim", "importance": "valuable_nonblocking", "text": "What single scientific claim should this visual make easiest to verify?"})
    if metrics and not comparable_groups(case):
        warnings.append("Comparison groups are not author-confirmed; keep emphasis conservative until comparable rows are known.")
    if form == "diverging_table_chart":
        hierarchy = "Place row labels beside a shared zero baseline; print exact signed values at bar ends."
        color = "Use two grayscale-distinguishable hues plus explicit +/− signs; never encode sign by color alone."
    elif form == "ranked_table_chart":
        hierarchy = "Sort only when row order has no scientific meaning; retain exact values beside horizontal bars."
        color = "Use neutral bars and one restrained accent for the claim-relevant row."
    elif form == "semantic_panel_table":
        hierarchy = "Split only at metric-family boundaries and repeat identity columns in every panel."
        color = "Use typography and whitespace first; reserve one grayscale-safe accent for the proposed method."
    elif form == "ablation_table":
        hierarchy = "Order rows from reference configuration to cumulative or isolated changes; keep the primary outcome nearest the variant label."
        color = "Avoid heatmaps for small effects; use bold only for valid within-block optima."
    else:
        hierarchy = "Keep identities left, put priority metrics nearest them, and group remaining outcomes by dataset or metric family."
        color = "Use typography and whitespace first; reserve one grayscale-safe accent for the proposed method."
    uncertainty = (
        "Show mean ± SD inline." if kinds == ["sd"] else
        "Show mean ± SE inline and define SE in the caption." if kinds == ["se"] else
        "Show the confidence interval and its level explicitly." if any(kind.startswith("ci") for kind in kinds) else
        "Keep each declared uncertainty type explicit." if kinds else
        "Do not add error bars or ± values without repeated runs, sample-level predictions, or supplied intervals."
    )
    actions = [hierarchy]
    if priorities:
        actions.append(f"Make the claim-priority metrics easiest to scan without changing canonical data order: {', '.join(priorities)}.")
    if groups:
        actions.append(f"Use grouped headers for: {', '.join(groups)}.")
    actions.extend([
        uncertainty,
        "Use consistent precision within each metric and preserve all observed values exactly.",
        color,
    ])
    alternatives = []
    if form.endswith("table_chart"):
        alternatives.append({"form": "comparison_table", "use_when": "exact multi-column lookup is more important than magnitude"})
    else:
        alternatives.append({"form": "table_chart", "use_when": "the author confirms one dominant metric or delta as the primary message"})
    if len(groups) >= 2:
        alternatives.append({"form": "semantic_panel_table", "use_when": "measured width cannot preserve readable typography in one panel"})
    return {
        "primary_form": form,
        "decision_basis": reasons,
        "input_facts": {
            "rows": len(rows), "text_columns": len(texts), "metric_columns": len(metrics),
            "metric_groups": groups, "uncertainty_kinds": kinds, "target_width_pt": width,
            "claim_supplied": bool(claim), "comparison_groups_supplied": bool(comparable_groups(case)),
            "run_identifier_columns": run_identifiers,
        },
        "proposal": {
            "hierarchy": hierarchy, "emphasis": "best/second-best only within author-confirmed comparison groups and resolved metric directions",
            "uncertainty": uncertainty, "color": color,
            "caption_checklist": ["evaluation split", "metric direction and unit", "repeat count", "uncertainty meaning", "comparison exclusions"],
        },
        "actionable_changes": actions,
        "alternatives": alternatives,
        "warnings": warnings,
        "questions": questions[:3],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("spec", type=Path)
    parser.add_argument("--case", type=Path, help="optional PaperBench case.json with semantic contract")
    parser.add_argument("--target-width-pt", type=float)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    spec = json.loads(args.spec.read_text())
    case = json.loads(args.case.read_text()) if args.case else None
    report = advise(spec, case, args.target_width_pt)
    text = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text)
    else:
        print(text, end="")


if __name__ == "__main__":
    main()
