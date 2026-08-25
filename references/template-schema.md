# Template and config schema

Templates are JSON objects in `assets/templates/`. User config is deep-merged over the selected template.

```json
{
  "template_id": "hierarchical-method-budget",
  "title": "Main results",
  "label": "tab:main",
  "claim": "The adaptation method improves quality at lower trainable-parameter cost.",
  "input": {"metric_columns": ["accuracy"]},
  "layout": {
    "orientation": "methods_rows",
    "row_fields": [
      {"key": "model", "label": "Model", "suppress_repeat": true, "separator": true},
      {"key": "method", "label": "Method"},
      {"key": "trainable_params", "label": "# Trainable"}
    ],
    "column_order": ["dataset", "metric"]
  },
  "metrics": {
    "accuracy": {"label": "Acc.", "direction": "max", "unit": "%", "precision": 1, "priority": 1}
  },
  "selection": {
    "methods": ["Full FT", "Adapter", "Ours"],
    "datasets": ["MNLI", "SST-2"],
    "metrics": ["accuracy"],
    "max_columns": 8
  },
  "notes": ["All methods use the same backbone and evaluation protocol."]
}
```

## Layout fields

- `orientation`: `methods_rows` or `datasets_rows`.
- `row_fields`: identity columns on the left. `suppress_repeat` blanks repeated labels; `separator` inserts whitespace when the value changes.
- `column_order`: `dataset, metric` or `metric, dataset` for methods-as-rows.
- `column_fields`: system label fields for datasets-as-rows.
- `column_group_field`: optional field such as `pretrain_data` rendered above system columns.

## Comparison scope

Use `comparison` to define which displayed systems participate in best/second-best ranking:

```json
{
  "comparison": {
    "rank_exclude_groups": ["Frontier Proprietary Models"],
    "rank_scope_label": "non-proprietary systems"
  }
}
```

`rank_include_groups`, `rank_include_methods`, and `rank_exclude_methods` are also supported. `rank_scope_label` is inserted into the generated caption; it should be a short human-readable description of the actual comparison universe.

## Visual hierarchy

```json
{
  "style": {
    "row_group_style": "band",
    "group_band_color": "EFEFEF",
    "highlight_methods": ["Ours"],
    "highlight_color": "E8F1FF",
    "fit_width": true,
    "font_size": "scriptsize",
    "tabcolsep": 2.5
  }
}
```

Colors are six-digit RGB hex values. `fit_width` uses `graphicx`; bands and row highlights use `xcolor` with the `table` option.

## Auxiliary deltas

Preserve the primary value while adding a parenthesized absolute or relative change:

```json
{
  "auxiliary": {
    "delta": {
      "baseline": {"method": "Strong Baseline"},
      "targets": [{"method": "Ours"}],
      "kind": "absolute",
      "precision": 1
    }
  }
}
```

Selectors may use any displayed identity field. The baseline must match exactly one row; ambiguity is an error. `kind` is `absolute` or `relative_percent`. The generated caption names the baseline and delta type.

The renderer treats the delta as a secondary subcell. It reserves that subcell across every row of each affected metric column, including blank slots for rows without deltas, so the primary measurements remain aligned.

## Selection and compression

Lists in `selection` filter and order the corresponding dimension. `max_columns` is optional; when used, metric `priority` chooses which columns stay in the main table. Every removed column is recorded in `manifest.json.omitted_columns`.
