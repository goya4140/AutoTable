from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Iterable

from .model import Observation

_IDENTITY_KEYS = {
    "method", "model", "system", "approach", "dataset", "benchmark", "task",
    "setting", "split", "seed", "run", "run_id", "fold", "group", "family",
    "metric", "value", "source", "epoch", "step", "n",
}
_METHOD_KEYS = ("method", "model", "system", "approach")
_DATASET_KEYS = ("dataset", "benchmark", "task")
_RUN_KEYS = ("run", "run_id", "seed", "fold")


class InputError(ValueError):
    pass


def _first(row: dict[str, Any], keys: Iterable[str], default: Any = None) -> Any:
    for key in keys:
        if key in row and row[key] not in (None, ""):
            return row[key]
    return default


def _number(value: Any, *, field: str) -> float:
    if isinstance(value, bool):
        raise InputError(f"{field} must be numeric, not boolean")
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise InputError(f"{field}={value!r} is not numeric") from exc


def _read(path: Path) -> Any:
    suffix = path.suffix.lower()
    if suffix in {".csv", ".tsv"}:
        with path.open(newline="", encoding="utf-8-sig") as handle:
            return list(csv.DictReader(handle, delimiter="\t" if suffix == ".tsv" else ","))
    if suffix == ".jsonl":
        with path.open(encoding="utf-8") as handle:
            return [json.loads(line) for line in handle if line.strip()]
    if suffix == ".json":
        with path.open(encoding="utf-8") as handle:
            return json.load(handle)
    raise InputError(f"unsupported input type: {path}; use CSV, TSV, JSON, or JSONL")


def _row_observations(
    rows: list[dict[str, Any]], source: str, metric_keys: list[str] | None
) -> list[Observation]:
    observations: list[Observation] = []
    for index, row in enumerate(rows, 1):
        if not isinstance(row, dict):
            raise InputError(f"{source}: row {index} is not an object")
        method = _first(row, _METHOD_KEYS)
        if method is None:
            raise InputError(f"{source}: row {index} has no method/model/system field")
        common = {
            "method": str(method),
            "dataset": str(_first(row, _DATASET_KEYS, "Overall")),
            "run": str(_first(row, _RUN_KEYS)) if _first(row, _RUN_KEYS) is not None else None,
            "setting": str(row["setting"]) if row.get("setting") not in (None, "") else None,
            "group": str(_first(row, ("group", "family"))) if _first(row, ("group", "family")) is not None else None,
            "source": source,
        }
        # Long format: one metric/value pair per row.
        if row.get("metric") not in (None, "") and _first(row, ("value", "score")) is not None:
            observations.append(Observation(
                metric=str(row["metric"]),
                value=_number(_first(row, ("value", "score")), field=f"{source}:{index}.value"),
                **common,
            ))
            continue

        # Wide format: every selected numeric column is a metric.
        candidates = metric_keys or [
            key for key, value in row.items()
            if key.lower() not in _IDENTITY_KEYS and value not in (None, "")
            and _looks_numeric(value)
        ]
        if not candidates:
            raise InputError(
                f"{source}: row {index} has no metric columns; set input.metric_columns in config"
            )
        for metric in candidates:
            if metric not in row or row[metric] in (None, ""):
                continue
            observations.append(Observation(
                metric=str(metric),
                value=_number(row[metric], field=f"{source}:{index}.{metric}"),
                **common,
            ))
    return observations


def _looks_numeric(value: Any) -> bool:
    try:
        float(value)
        return not isinstance(value, bool)
    except (TypeError, ValueError):
        return False


def _nested_observations(data: dict[str, Any], source: str) -> list[Observation]:
    """Parse method -> dataset -> metric -> scalar/list JSON."""
    observations: list[Observation] = []
    for method, datasets in data.items():
        if not isinstance(datasets, dict):
            raise InputError(f"{source}: expected object below method {method!r}")
        for dataset, metrics in datasets.items():
            if not isinstance(metrics, dict):
                raise InputError(f"{source}: expected object below dataset {dataset!r}")
            for metric, value in metrics.items():
                values = value if isinstance(value, list) else [value]
                for run_index, item in enumerate(values, 1):
                    observations.append(Observation(
                        method=str(method), dataset=str(dataset), metric=str(metric),
                        value=_number(item, field=f"{source}.{method}.{dataset}.{metric}"),
                        run=str(run_index) if isinstance(value, list) else None,
                        source=source,
                    ))
    return observations


def load_inputs(paths: list[str | Path], config: dict[str, Any] | None = None) -> list[Observation]:
    config = config or {}
    metric_keys = config.get("input", {}).get("metric_columns")
    all_observations: list[Observation] = []
    for raw_path in paths:
        path = Path(raw_path)
        if not path.is_file():
            raise InputError(f"input does not exist: {path}")
        data = _read(path)
        source = str(path)
        if isinstance(data, dict) and isinstance(data.get("results"), list):
            data = data["results"]
        if isinstance(data, list):
            all_observations.extend(_row_observations(data, source, metric_keys))
        elif isinstance(data, dict):
            all_observations.extend(_nested_observations(data, source))
        else:
            raise InputError(f"{source}: root must be an array or object")
    if not all_observations:
        raise InputError("no observations found")
    return all_observations
