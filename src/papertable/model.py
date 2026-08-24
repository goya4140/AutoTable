from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class Observation:
    method: str
    metric: str
    value: float
    dataset: str = "Overall"
    run: str | None = None
    setting: str | None = None
    group: str | None = None
    source: str | None = None
    dimensions: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Aggregate:
    method: str
    metric: str
    dataset: str
    setting: str | None
    group: str | None
    mean: float
    sd: float | None
    n: int
    values: tuple[float, ...]
    run_ids: tuple[str, ...]
    sources: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["values"] = list(self.values)
        data["run_ids"] = list(self.run_ids)
        data["sources"] = list(self.sources)
        return data

