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
            if len(cell.get("values", [])) != cell.get("n"):
                errors.append(f"cell {row_index},{column_index} loses value lineage")
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
