import json
from pathlib import Path

import pytest

from papertable.ingest import load_inputs
from papertable.pipeline import generate


def test_wide_csv_end_to_end(tmp_path: Path) -> None:
    source = tmp_path / "results.csv"
    source.write_text(
        "group,method,dataset,seed,accuracy,latency_ms\n"
        "Base,A,D1,1,80,12\n"
        "Base,A,D1,2,82,10\n"
        "Ours,B,D1,1,84,9\n"
        "Ours,B,D1,2,86,7\n",
        encoding="utf-8",
    )
    config = {
        "input": {"metric_columns": ["accuracy", "latency_ms"]},
        "metrics": {
            "accuracy": {"direction": "max", "precision": 1},
            "latency_ms": {"direction": "min", "precision": 1},
        },
    }
    manifest = generate([source], tmp_path / "out", config)
    spec = json.loads((tmp_path / "out/table-spec.json").read_text())
    latex = (tmp_path / "out/table.tex").read_text()
    caption = (tmp_path / "out/caption.txt").read_text()

    assert manifest["observation_count"] == 8
    assert manifest["displayed_cell_count"] == 4
    assert spec["rows"][1]["cells"][0]["mean"] == 85
    assert spec["rows"][1]["cells"][1]["mean"] == 8
    assert r"\textbf{85.0 $\pm$ 1.4}" in latex
    assert r"\textbf{8.0 $\pm$ 1.4}" in latex
    assert "mean ± sample standard deviation" in caption


def test_nested_json(tmp_path: Path) -> None:
    source = tmp_path / "nested.json"
    source.write_text(json.dumps({
        "A": {"D1": {"score": [1, 3]}},
        "B": {"D1": {"score": [2, 4]}},
    }))
    observations = load_inputs([source])
    assert len(observations) == 4
    assert observations[1].run == "2"


def test_column_budget_records_omissions(tmp_path: Path) -> None:
    source = tmp_path / "results.csv"
    source.write_text("method,dataset,a,b,c\nM,D,1,2,3\n", encoding="utf-8")
    config = {
        "metrics": {"a": {"priority": 3}, "b": {"priority": 1}, "c": {"priority": 2}},
        "selection": {"max_columns": 2},
    }
    manifest = generate([source], tmp_path / "out", config)
    spec = json.loads((tmp_path / "out/table-spec.json").read_text())
    assert [column["metric"] for column in spec["columns"]] == ["b", "c"]
    assert manifest["omitted_columns"] == [{"dataset": "D", "setting": None, "metric": "a"}]


def test_selection_filters_instead_of_only_reordering(tmp_path: Path) -> None:
    source = tmp_path / "results.csv"
    source.write_text("method,dataset,a,b\nA,D1,1,2\nB,D2,3,4\n", encoding="utf-8")
    generate([source], tmp_path / "out", {
        "selection": {"methods": ["B"], "datasets": ["D2"], "metrics": ["b"]}
    })
    spec = json.loads((tmp_path / "out/table-spec.json").read_text())
    assert spec["methods"] == ["B"]
    assert spec["columns"] == [{"dataset": "D2", "setting": None, "metric": "b"}]
    assert spec["rows"][0]["cells"][0]["mean"] == 4


def test_score_is_a_valid_wide_metric(tmp_path: Path) -> None:
    source = tmp_path / "results.csv"
    source.write_text("method,dataset,score\nA,D,2\n", encoding="utf-8")
    observations = load_inputs([source])
    assert observations[0].metric == "score"


def test_duplicate_run_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "results.csv"
    source.write_text("method,dataset,seed,score\nA,D,1,2\nA,D,1,3\n", encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate run IDs"):
        generate([source], tmp_path / "out", {"input": {"metric_columns": ["score"]}})
