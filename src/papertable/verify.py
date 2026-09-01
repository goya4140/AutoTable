from __future__ import annotations

import math
from typing import Any


def verify_spec(spec: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    columns = spec.get("columns", [])
    rows = spec.get("rows", [])
    if not columns:
        errors.append("table has no columns")
    if not rows:
        errors.append("table has no rows")
    for row_index, row in enumerate(rows):
        cells = row.get("cells", [])
        if len(cells) != len(columns):
            errors.append(f"row {row_index} has {len(cells)} cells for {len(columns)} columns")
            continue
        for column_index, cell in enumerate(cells):
            if cell is None:
                continue
            if cell.get("n", 0) < 1:
                errors.append(f"cell {row_index},{column_index} has invalid n")
            for field in ("mean", "sd"):
                value = cell.get(field)
                if value is not None and (not isinstance(value, (int, float)) or not math.isfinite(value)):
                    errors.append(f"cell {row_index},{column_index} has non-finite {field}")
            aggregation_source = cell.get("aggregation_source", "observations")
            if aggregation_source == "observations":
                if len(cell.get("values", [])) != cell.get("n"):
                    errors.append(f"cell {row_index},{column_index} loses value lineage")
            elif aggregation_source == "reported_summary":
                if cell.get("values") or cell.get("run_ids") or not cell.get("sources"):
                    errors.append(f"cell {row_index},{column_index} has invalid summary lineage")
                if cell.get("sd") is not None and cell.get("n", 0) < 2:
                    errors.append(f"cell {row_index},{column_index} reports SD with n < 2")
            else:
                errors.append(f"cell {row_index},{column_index} has invalid aggregation source")
            auxiliary = cell.get("auxiliary")
            if auxiliary:
                if auxiliary.get("kind") not in {"absolute", "relative_percent"}:
                    errors.append(f"cell {row_index},{column_index} has invalid auxiliary kind")
                value = auxiliary.get("value")
                if not isinstance(value, (int, float)) or not math.isfinite(value):
                    errors.append(f"cell {row_index},{column_index} has invalid auxiliary value")
            column = columns[column_index]
            if spec.get("orientation") == "datasets_rows":
                matches = (
                    cell.get("method") == column.get("method")
                    and cell.get("metric") == row.get("metric")
                    and cell.get("dataset") == row.get("dataset")
                )
            else:
                matches = cell.get("method") == row.get("method") and cell.get("metric") == column.get("metric")
            if not matches:
                errors.append(f"cell {row_index},{column_index} does not match its row/column")
    return {"valid": not errors, "errors": errors}
