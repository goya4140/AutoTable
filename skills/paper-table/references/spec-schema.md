# Table specification

Use JSON with this shape:

```json
{
  "title": "Main results",
  "label": "tab:main",
  "caption": "Test performance. Higher is better.",
  "column_supergroup": "Benchmark",
  "columns": [
    {"key": "method", "label": "Method", "kind": "text"},
    {"key": "accuracy", "label": "Accuracy", "kind": "metric", "direction": "max", "precision": 1, "group": "Test split"}
  ],
  "rows": [
    {"group": "Prior work", "method": "Baseline", "accuracy": 82.1},
    {"group": "Ours", "method": "Proposed", "accuracy": {"mean": 85.4, "sd": 0.3}}
  ],
  "emphasis": {"best": "bold", "second": "underline", "scope": "group"},
  "notes": ["Mean ± SD over 5 seeds."],
  "provenance": {"observed": true, "source": "results.csv"}
}
```

Required keys are `columns` and `rows`. Column `kind` is `text` or `metric`. Metric cells may be numbers, strings, null, or objects containing `mean` and one of `sd`, `se`, `ci95`, or `values`. Consecutive metric columns with the same optional `group` receive a shared header; `column_supergroup` adds one level above all metric columns. Use `scope: all` to rank across all rows, or `group` to rank within each row group. Set `rank_eligible: false` on an upper bound or oracle row that must not participate in emphasis. Set `observed: false` and add simulation assumptions whenever values are synthetic.
