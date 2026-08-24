from __future__ import annotations

from collections import defaultdict
from statistics import fmean, stdev

from .model import Aggregate, Observation


def aggregate(observations: list[Observation]) -> list[Aggregate]:
    buckets: dict[tuple[str, str, str, str | None, str | None], list[Observation]] = defaultdict(list)
    for item in observations:
        key = (item.method, item.dataset, item.metric, item.setting, item.group)
        buckets[key].append(item)

    output: list[Aggregate] = []
    for (method, dataset, metric, setting, group), items in buckets.items():
        values = tuple(item.value for item in items)
        run_ids = tuple(item.run for item in items if item.run is not None)
        if run_ids and len(set(run_ids)) != len(run_ids):
            raise ValueError(
                f"duplicate run IDs for method={method}, dataset={dataset}, metric={metric}, setting={setting}"
            )
        output.append(Aggregate(
            method=method,
            dataset=dataset,
            metric=metric,
            setting=setting,
            group=group,
            mean=fmean(values),
            sd=stdev(values) if len(values) > 1 else None,
            n=len(values),
            values=values,
            run_ids=run_ids,
            sources=tuple(sorted({item.source for item in items if item.source})),
        ))
    return output

