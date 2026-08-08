#!/usr/bin/env python3
"""Compare a reconstructed table with a publication snapshot at display precision."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "paper-table-snapshot-comparison-v1"
UNCERTAINTY_KEYS = ("sd", "se", "ci90", "ci95")


def _finite(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _display_value(value: float, precision: int) -> float | int:
    return int(round(value)) if precision == 0 else float(f"{value:.{precision}f}")


def _components(cell: Any) -> dict[str, Any]:
    if _finite(cell):
        return {"value": cell}
    if isinstance(cell, dict) and _finite(cell.get("mean")):
        result = {"mean": cell["mean"]}
        for key in UNCERTAINTY_KEYS:
            if key in cell:
                result[key] = cell[key]
        return result
    return {"unsupported": cell}


def _column_map(spec: dict) -> dict[str, dict]:
    return {column["key"]: column for column in spec.get("columns", []) if isinstance(column, dict) and column.get("key")}


def _row_map(spec: dict, row_key: str) -> tuple[dict[Any, dict], list[Any]]:
    rows = {}
    duplicates = []
    for row in spec.get("rows", []):
        identity = row.get(row_key)
        if identity in rows:
            duplicates.append(identity)
        rows[identity] = row
    return rows, duplicates


def compare(current: dict, published: dict, row_key: str) -> dict:
    current_columns = _column_map(current)
    published_columns = _column_map(published)
    metric_keys = [column["key"] for column in published.get("columns", []) if column.get("kind") == "metric"]
    structural = []
    if row_key not in published_columns or row_key not in current_columns:
        structural.append({"path": f"columns.{row_key}", "message": "row identity column missing"})
    for key in metric_keys:
        if key not in current_columns:
            structural.append({"path": f"columns.{key}", "message": "published metric missing from reconstruction"})
            continue
        for field in ("direction", "unit"):
            if current_columns[key].get(field) != published_columns[key].get(field):
                structural.append({
                    "path": f"columns.{key}.{field}",
                    "message": "metric semantics changed",
                    "published": published_columns[key].get(field),
                    "snapshot": current_columns[key].get(field),
                })
    current_rows, current_duplicates = _row_map(current, row_key)
    published_rows, published_duplicates = _row_map(published, row_key)
    for identity in current_duplicates:
        structural.append({"path": f"rows.{identity}", "message": "duplicate reconstruction row identity"})
    for identity in published_duplicates:
        structural.append({"path": f"rows.{identity}", "message": "duplicate published row identity"})
    for identity in sorted(published_rows.keys() - current_rows.keys(), key=str):
        structural.append({"path": f"rows.{identity}", "message": "published row missing from reconstruction"})
    for identity in sorted(current_rows.keys() - published_rows.keys(), key=str):
        structural.append({"path": f"rows.{identity}", "message": "unexpected reconstruction row"})

    mismatches = []
    exact = 0
    cells = 0
    per_metric = {}
    for metric in metric_keys:
        if metric not in current_columns:
            continue
        precision = published_columns[metric].get("precision")
        if not isinstance(precision, int) or not 0 <= precision <= 12:
            structural.append({"path": f"columns.{metric}.precision", "message": "published metric requires display precision"})
            continue
        metric_exact = 0
        differences = []
        metric_cells = 0
        for identity in published_rows:
            if identity not in current_rows:
                continue
            expected_components = _components(published_rows[identity].get(metric))
            observed_components = _components(current_rows[identity].get(metric))
            if set(expected_components) != set(observed_components) or "unsupported" in expected_components:
                structural.append({
                    "path": f"rows.{identity}.{metric}",
                    "message": "cell structure changed or is unsupported",
                    "published": expected_components,
                    "snapshot": observed_components,
                })
                continue
            cell_exact = True
            for component, expected_raw in expected_components.items():
                metric_cells += 1
                cells += 1
                observed_raw = observed_components[component]
                if isinstance(expected_raw, list) or isinstance(observed_raw, list):
                    structural.append({"path": f"rows.{identity}.{metric}.{component}", "message": "interval arrays require explicit endpoint precision"})
                    cell_exact = False
                    continue
                expected = _display_value(float(expected_raw), precision)
                observed = _display_value(float(observed_raw), precision)
                difference = float(observed) - float(expected)
                differences.append(abs(difference))
                if observed == expected:
                    exact += 1
                    metric_exact += 1
                else:
                    cell_exact = False
                    mismatches.append({
                        "row": identity,
                        "metric": metric,
                        "component": component,
                        "precision": precision,
                        "published": expected,
                        "snapshot": observed,
                        "difference": difference,
                    })
            if not cell_exact:
                continue
        per_metric[metric] = {
            "exact_components": metric_exact,
            "components": metric_cells,
            "mean_absolute_drift": sum(differences) / len(differences) if differences else None,
            "max_absolute_drift": max(differences) if differences else None,
        }
    eligible = not structural and not mismatches and cells > 0
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "exact_published_reconstruction" if eligible else "source_snapshot_drift_detected",
        "published_exact_gold": eligible,
        "row_identity_key": row_key,
        "exact_components": exact,
        "components": cells,
        "exact_component_rate": exact / cells if cells else None,
        "mismatched_components": len(mismatches),
        "structural_mismatches": structural,
        "per_metric": per_metric,
        "mismatches": mismatches,
        "required_action": (
            "Eligible for exact published-cell evaluation."
            if eligible
            else "Do not declare verified against the publication; request the paper-time snapshot or label the output as a current-snapshot reconstruction."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("current", type=Path)
    parser.add_argument("published", type=Path)
    parser.add_argument("--row-key", required=True)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    report = compare(json.loads(args.current.read_text()), json.loads(args.published.read_text()), args.row_key)
    rendered = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered)
        print(args.out)
    else:
        print(rendered, end="")
    raise SystemExit(0 if report["published_exact_gold"] else 2)


if __name__ == "__main__":
    main()
