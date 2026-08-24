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

## Selection and compression

Lists in `selection` filter and order the corresponding dimension. `max_columns` is optional; when used, metric `priority` chooses which columns stay in the main table. Every removed column is recorded in `manifest.json.omitted_columns`.

