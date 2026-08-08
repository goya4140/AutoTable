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
    {"key": "accuracy", "label": "Accuracy", "kind": "metric", "direction": "max", "unit": "%", "precision": 1, "group": "Test split"}
  ],
  "rows": [
    {"group": "Prior work", "method": "Baseline", "accuracy": 82.1},
    {"group": "Ours", "method": "Proposed", "accuracy": {"mean": 85.4, "sd": 0.3}}
  ],
  "emphasis": {"best": "bold", "second": "underline", "scope": "group"},
  "layout": {"font_size": "small", "column_padding_pt": 5, "row_stretch": 1.0},
  "notes": ["Mean ± SD over 5 seeds."],
  "provenance": {"observed": true, "source": "results.csv"}
}
```

Required keys are `columns` and `rows`. Column `kind` is `text` or `metric`; every metric should declare `direction` and `unit`, including `dimensionless` when appropriate. Metric cells may be numbers, strings, null, or objects containing `mean` and one of `sd`, `se`, `ci95`, or `values`. Consecutive metric columns with the same optional `group` receive a shared header; `column_supergroup` adds one level above all metric columns. Use `scope: all` to rank across all rows, or `group` to rank within each row group. Set `rank_eligible: false` on an upper bound or oracle row that must not participate in emphasis. Set `observed: false` and add simulation assumptions whenever values are synthetic.

The optional `layout` object accepts `font_size` (`small`, `footnotesize`, or `scriptsize`), `column_padding_pt` from 1.5 to 10, `row_stretch` from 0.8 to 1.5, and an optional `text_column_width_pt` from 45 to 160 for lossless wrapping. Let `optimize_layout.py` choose these values unless the venue template fixes them.

For a semantic panel split, add `panels`, for example `[{"label":"(a) Dataset A","metric_keys":["acc_a","f1_a"]},{"label":"(b) Dataset B","metric_keys":["acc_b","f1_b"]}]`. Panel keys must cover every metric exactly once and in original column order. Do not mix different nonempty metric groups within one panel. Identity columns repeat automatically; the underlying `columns` and `rows` remain canonical and unchanged.

Keep the broader claim, comparison-group membership, statistics source, run count, allowed transformations, forbidden inferences, and rendering constraints in a semantic-contract sidecar as described in `semantic-contract.md`. The table spec controls rendering; the sidecar controls what the renderer is scientifically allowed to imply.

`render_table_chart.py` uses the same canonical spec but accepts exactly one metric column and 2–16 rows. The metric must declare `direction`, `unit`, and preferably `precision`; cells may be scalar means or objects containing `mean` with one consistent uncertainty kind. The renderer refuses a multi-metric lookup table, unresolved direction/unit, mixed uncertainty kinds, and inputs for which `design_advisor.py` recommends a conventional table. It emits `table-chart.svg`, `table-chart.pdf`, `table-chart.png`, and a source-backed `chart-spec.json` containing the plotted rows, palette contract, non-color distinction, provenance, and design advice.
