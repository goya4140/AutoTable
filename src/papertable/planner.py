from __future__ import annotations

from collections import defaultdict
from typing import Any

from .model import Aggregate

_LOWER_IS_BETTER = ("loss", "error", "wer", "perplex", "latency", "time", "memory", "flop", "param")


def _ordered(values: list[str], preferred: list[str] | None = None) -> list[str]:
    seen = list(dict.fromkeys(values))
    if not preferred:
        return seen
    return [x for x in preferred if x in seen] + [x for x in seen if x not in preferred]


def _select(values: list[str], requested: list[str] | None, name: str, warnings: list[str]) -> list[str]:
    available = list(dict.fromkeys(values))
    if requested is None:
        return available
    missing = [value for value in requested if value not in available]
    if missing:
        warnings.append(f"requested {name} not found: {', '.join(missing)}")
    return [value for value in requested if value in available]


def _metric_meta(metric: str, config: dict[str, Any], warnings: list[str]) -> dict[str, Any]:
    configured = config.get("metrics", {}).get(metric, {})
    direction = configured.get("direction")
    if direction not in {"max", "min"}:
        direction = "min" if any(token in metric.lower() for token in _LOWER_IS_BETTER) else "max"
        warnings.append(f"metric direction for {metric!r} was inferred as {direction!r}")
    return {
        "key": metric,
        "label": configured.get("label", metric.replace("_", " ").title()),
        "direction": direction,
        "precision": int(configured.get("precision", 2)),
        "unit": configured.get("unit"),
        "priority": int(configured.get("priority", 100)),
    }


def plan_main_table(aggregates: list[Aggregate], config: dict[str, Any] | None = None) -> dict[str, Any]:
    config = config or {}
    selection = config.get("selection", {})
    warnings: list[str] = []

    if selection.get("methods") is not None:
        methods = _select([x.method for x in aggregates], selection["methods"], "methods", warnings)
    else:
        methods = _ordered([x.method for x in aggregates], config.get("method_order"))
    datasets = _select([x.dataset for x in aggregates], selection.get("datasets"), "datasets", warnings)
    metrics = _select([x.metric for x in aggregates], selection.get("metrics"), "metrics", warnings)
    settings = _select(
        [x.setting for x in aggregates if x.setting is not None],
        selection.get("settings"), "settings", warnings,
    )
    metric_meta = {metric: _metric_meta(metric, config, warnings) for metric in metrics}

    available = {(x.dataset, x.setting, x.metric) for x in aggregates}
    columns: list[dict[str, Any]] = []
    setting_values: list[str | None] = settings if settings else [None]
    for dataset in datasets:
        for setting in setting_values:
            for metric in metrics:
                if (dataset, setting, metric) in available:
                    columns.append({"dataset": dataset, "setting": setting, "metric": metric})

    max_columns = selection.get("max_columns")
    omitted: list[dict[str, Any]] = []
    if max_columns is not None and len(columns) > int(max_columns):
        ranked = sorted(
            enumerate(columns),
            key=lambda pair: (metric_meta[pair[1]["metric"]]["priority"], pair[0]),
        )
        keep = {index for index, _ in ranked[: int(max_columns)]}
        omitted = [column for index, column in enumerate(columns) if index not in keep]
        columns = [column for index, column in enumerate(columns) if index in keep]
        warnings.append(f"{len(omitted)} columns were omitted by selection.max_columns")

    cells_by_key = {
        (x.method, x.dataset, x.setting, x.metric): x.to_dict() for x in aggregates
        if x.method in methods
    }
    rows = []
    for method in methods:
        matching = [x for x in aggregates if x.method == method]
        rows.append({
            "method": method,
            "group": next((x.group for x in matching if x.group), None),
            "cells": [cells_by_key.get((method, c["dataset"], c["setting"], c["metric"])) for c in columns],
        })

    return {
        "schema_version": "paper-table-spec-v1",
        "kind": "main",
        "title": config.get("title", "Main results"),
        "label": config.get("label", "tab:main-results"),
        "claim": config.get("claim"),
        "methods": methods,
        "metrics": metric_meta,
        "columns": columns,
        "rows": rows,
        "emphasis": config.get("emphasis", {"best": "bold", "second": "underline"}),
        "caption": config.get("caption"),
        "notes": list(config.get("notes", [])),
        "omitted_columns": omitted,
        "warnings": warnings,
    }


def emphasis_map(spec: dict[str, Any]) -> dict[tuple[int, int], str]:
    output: dict[tuple[int, int], str] = {}
    for column_index, column in enumerate(spec["columns"]):
        direction = spec["metrics"][column["metric"]]["direction"]
        values = [(row_index, row["cells"][column_index]["mean"])
                  for row_index, row in enumerate(spec["rows"])
                  if row["cells"][column_index] is not None]
        distinct = sorted({value for _, value in values}, reverse=direction == "max")
        if distinct and spec.get("emphasis", {}).get("best"):
            for row_index, value in values:
                if value == distinct[0]:
                    output[(row_index, column_index)] = spec["emphasis"]["best"]
        if len(distinct) > 1 and spec.get("emphasis", {}).get("second"):
            for row_index, value in values:
                if value == distinct[1]:
                    output[(row_index, column_index)] = spec["emphasis"]["second"]
    return output
