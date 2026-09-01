import json
from pathlib import Path

import pytest

from papertable.ingest import load_inputs
from papertable.pipeline import generate
from papertable.templates import available_templates


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


def test_reported_summary_preserves_sd_n_and_source_without_inventing_runs(tmp_path: Path) -> None:
    source = tmp_path / "summary.csv"
    source.write_text(
        "method,dataset,metric,mean,sd,n\n"
        "A,D,accuracy,87.4,0.3,3\n"
        "B,D,accuracy,88.1,0.2,3\n",
        encoding="utf-8",
    )
    manifest = generate([source], tmp_path / "out", {
        "metrics": {"accuracy": {"direction": "max", "precision": 1}},
    })
    spec = json.loads((tmp_path / "out/table-spec.json").read_text())
    cell = spec["rows"][0]["cells"][0]

    assert manifest["observation_count"] == 0
    assert manifest["reported_summary_count"] == 2
    assert manifest["represented_run_count"] == 6
    assert cell["mean"] == pytest.approx(87.4)
    assert cell["sd"] == pytest.approx(0.3)
    assert cell["n"] == 3
    assert cell["values"] == []
    assert cell["run_ids"] == []
    assert cell["aggregation_source"] == "reported_summary"


def test_reported_summary_cannot_mix_with_raw_observation(tmp_path: Path) -> None:
    source = tmp_path / "mixed.csv"
    source.write_text(
        "method,dataset,metric,value,mean,sd,n\n"
        "A,D,score,1,,,\n"
        "A,D,score,,2,0.1,3\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="reported summary cannot be mixed"):
        generate([source], tmp_path / "out", {"metrics": {"score": {"direction": "max"}}})


def test_custom_missing_marker_renders_in_latex_and_html(tmp_path: Path) -> None:
    source = tmp_path / "missing.csv"
    source.write_text(
        "method,dataset,metric,value\nA,D1,score,1\nB,D2,score,2\n",
        encoding="utf-8",
    )
    generate([source], tmp_path / "out", {
        "metrics": {"score": {"direction": "max"}},
        "style": {"missing_marker": "N/A", "missing_note": "N/A is not applicable."},
    })
    assert "N/A" in (tmp_path / "out/table.tex").read_text()
    assert "N/A" in (tmp_path / "out/table.html").read_text()
    assert "N/A is not applicable" in (tmp_path / "out/caption.txt").read_text()


def test_descriptive_metric_can_hide_direction_arrow(tmp_path: Path) -> None:
    source = tmp_path / "descriptive.csv"
    source.write_text("method,dataset,metric,value\nSide effect,D,rate,41.6\n", encoding="utf-8")
    generate([source], tmp_path / "out", {
        "metrics": {"rate": {"direction": "max", "show_direction": False}},
        "emphasis": {},
    })
    latex = (tmp_path / "out/table.tex").read_text()
    html = (tmp_path / "out/table.html").read_text()
    assert r"Rate $\uparrow$" not in latex
    assert "Rate ↑" not in html


@pytest.mark.parametrize(
    ("stem", "record_count"),
    [
        ("core_evidence", 33),
        ("external_mll23", 18),
        ("ablations", 30),
        ("c2_diagnostic", 4),
        ("failure_taxonomy", 7),
    ],
)
def test_exp40_reported_tables_preserve_summary_lineage(
    tmp_path: Path, stem: str, record_count: int
) -> None:
    root = Path(__file__).parents[1]
    config = json.loads((root / f"examples/exp40/{stem}.json").read_text(encoding="utf-8"))
    manifest = generate(
        [root / f"examples/exp40/{stem}.csv"], tmp_path / stem, config
    )
    spec = json.loads((tmp_path / stem / "table-spec.json").read_text(encoding="utf-8"))

    assert manifest["verification"] == {"valid": True, "errors": []}
    assert manifest["warnings"] == []
    assert manifest["omitted_columns"] == []
    assert manifest["observation_count"] == 0
    assert manifest["reported_summary_count"] == record_count
    cells = [cell for row in spec["rows"] for cell in row["cells"] if cell is not None]
    assert len(cells) == record_count
    assert all(cell["aggregation_source"] == "reported_summary" for cell in cells)
    assert all(cell["values"] == [] and cell["run_ids"] == [] for cell in cells)

    if stem == "c2_diagnostic":
        assert spec["emphasis"] == {}
        assert "INCOMPLETE" in spec["caption"]
        assert "NOT EVALUABLE" in spec["caption"]
    if stem == "failure_taxonomy":
        assert spec["emphasis"] == {}
        assert all(not metric["show_direction"] for metric in spec["metrics"].values())


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
    assert spec["columns"] == [{
        "dataset": "D2", "setting": None, "metric": "b", "group_label": None, "label": "B"
    }]
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


def test_hierarchical_method_fields_are_separate_columns(tmp_path: Path) -> None:
    source = tmp_path / "results.csv"
    source.write_text(
        "model,method,trainable_params,dataset,seed,accuracy\n"
        "RoBERTa,Full FT,125M,MNLI,1,87\n"
        "RoBERTa,LoRA,0.3M,MNLI,1,88\n",
        encoding="utf-8",
    )
    generate([source], tmp_path / "out", {
        "template": "hierarchical-method-budget",
        "input": {"metric_columns": ["accuracy"]},
        "metrics": {"accuracy": {"direction": "max"}},
    })
    spec = json.loads((tmp_path / "out/table-spec.json").read_text())
    assert [field["key"] for field in spec["identity_columns"]] == ["model", "method", "trainable_params"]
    assert spec["rows"][1]["identity"] == {
        "model": "RoBERTa", "method": "LoRA", "trainable_params": "0.3M"
    }


def test_transposed_benchmark_ranks_across_method_columns(tmp_path: Path) -> None:
    source = tmp_path / "results.csv"
    source.write_text(
        "method,pretrain_data,dataset,accuracy\n"
        "ViT,JFT,ImageNet,88.5\n"
        "BiT,JFT,ImageNet,87.5\n"
        "ViT,JFT,CIFAR-10,99.5\n"
        "BiT,JFT,CIFAR-10,99.3\n",
        encoding="utf-8",
    )
    generate([source], tmp_path / "out", {
        "template": "transposed-benchmark",
        "input": {"metric_columns": ["accuracy"]},
        "metrics": {"accuracy": {"direction": "max", "precision": 1}},
    })
    spec = json.loads((tmp_path / "out/table-spec.json").read_text())
    latex = (tmp_path / "out/table.tex").read_text()
    assert spec["orientation"] == "datasets_rows"
    assert [column["method"] for column in spec["columns"]] == ["ViT", "BiT"]
    assert [row["dataset"] for row in spec["rows"]] == ["ImageNet", "CIFAR-10"]
    assert r"\textbf{88.5}" in latex
    assert "in each row" in (tmp_path / "out/caption.txt").read_text()


def test_transposed_columns_keep_groups_contiguous(tmp_path: Path) -> None:
    source = tmp_path / "results.csv"
    source.write_text(
        "method,pretrain_data,dataset,accuracy\n"
        "A,JFT,D,3\n"
        "A,ImageNet,D,2\n"
        "B,JFT,D,1\n",
        encoding="utf-8",
    )
    generate([source], tmp_path / "out", {
        "template": "transposed-benchmark",
        "input": {"metric_columns": ["accuracy"]},
    })
    spec = json.loads((tmp_path / "out/table-spec.json").read_text())
    assert [column["group_label"] for column in spec["columns"]] == ["JFT", "JFT", "ImageNet"]


@pytest.mark.parametrize(
    ("stem", "template_id"),
    [
        ("hierarchical", "hierarchical-method-budget"),
        ("transposed", "transposed-benchmark"),
        ("quality_efficiency", "quality-efficiency"),
        ("compact", "compact-regime-comparison"),
        ("scaled", "scaled-variants"),
        ("family_banded", "family-banded-benchmark"),
        ("statistical_delta", "benchmark-wide"),
    ],
)
def test_gallery_examples_generate_valid_specs(
    tmp_path: Path, stem: str, template_id: str
) -> None:
    gallery = Path(__file__).parents[1] / "examples" / "gallery"
    config = json.loads((gallery / f"{stem}.json").read_text(encoding="utf-8"))
    manifest = generate([gallery / f"{stem}.csv"], tmp_path / stem, config)

    assert manifest["template_id"] == template_id
    assert manifest["verification"] == {"valid": True, "errors": []}
    assert manifest["displayed_cell_count"] > 0


def test_readme_displays_every_gallery_image() -> None:
    root = Path(__file__).parents[1]
    readme = (root / "README.md").read_text(encoding="utf-8")

    for image in sorted((root / "docs/assets/gallery").glob("*.png")):
        relative_path = image.relative_to(root).as_posix()
        assert f"]({relative_path})" in readme, f"README does not display {relative_path}"


@pytest.mark.parametrize(
    ("stem", "expected_group_rules"),
    [("compact", 3), ("scaled", 2), ("hierarchical", 1)],
)
def test_semantic_group_templates_use_full_width_rules(
    tmp_path: Path, stem: str, expected_group_rules: int
) -> None:
    gallery = Path(__file__).parents[1] / "examples" / "gallery"
    config = json.loads((gallery / f"{stem}.json").read_text(encoding="utf-8"))
    generate([gallery / f"{stem}.csv"], tmp_path / stem, config)
    latex = (tmp_path / stem / "table.tex").read_text(encoding="utf-8")
    html = (tmp_path / stem / "table.html").read_text(encoding="utf-8")
    spec = json.loads((tmp_path / stem / "table-spec.json").read_text(encoding="utf-8"))

    assert latex.count("    \\midrule") == expected_group_rules + 1  # includes header rule
    assert "\\addlinespace" not in latex
    assert html.count('class="group-start rule"') == expected_group_rules
    separator_field = next(field["key"] for field in spec["identity_columns"] if field.get("separator"))
    group_values = [row["identity"].get(separator_field) for row in spec["rows"]]
    assert len(list(dict.fromkeys(group_values))) == expected_group_rules + 1


def test_all_research_backed_templates_are_discoverable() -> None:
    assert {item["id"] for item in available_templates()} == {
        "benchmark-wide",
        "compact-regime-comparison",
        "family-banded-benchmark",
        "hierarchical-method-budget",
        "quality-efficiency",
        "scaled-variants",
        "transposed-benchmark",
    }


def test_family_bands_scoped_ranking_and_focal_highlight(tmp_path: Path) -> None:
    gallery = Path(__file__).parents[1] / "examples" / "gallery"
    config = json.loads((gallery / "family_banded.json").read_text(encoding="utf-8"))
    manifest = generate(
        [gallery / "family_banded.csv"], tmp_path / "family-banded", config
    )
    latex = (tmp_path / "family-banded/table.tex").read_text(encoding="utf-8")
    html = (tmp_path / "family-banded/table.html").read_text(encoding="utf-8")
    caption = (tmp_path / "family-banded/caption.txt").read_text(encoding="utf-8")

    assert manifest["ranking_scope"] == "non-proprietary systems"
    assert latex.count(r"\rowcolor[HTML]{EFEFEF} \multicolumn") == 4
    assert r"Aurora-Pro & 0.91" in latex
    assert r"Aurora-Pro & \textbf{0.91}" not in latex
    assert r"\rowcolor[HTML]{E8F1FF} PaperTable-Agent & \textbf{0.88}" in latex
    assert "--" in latex
    assert 'class="group-band"' in html
    assert "among non-proprietary systems" in caption
    assert "Dashes denote unavailable results" in caption
    assert "Ties share the same marker" in caption


def test_auxiliary_delta_preserves_main_value_and_lineage(tmp_path: Path) -> None:
    gallery = Path(__file__).parents[1] / "examples" / "gallery"
    config = json.loads((gallery / "statistical_delta.json").read_text(encoding="utf-8"))
    manifest = generate(
        [gallery / "statistical_delta.csv"], tmp_path / "statistical-delta", config
    )
    spec = json.loads((tmp_path / "statistical-delta/table-spec.json").read_text())
    latex = (tmp_path / "statistical-delta/table.tex").read_text(encoding="utf-8")
    html = (tmp_path / "statistical-delta/table.html").read_text(encoding="utf-8")
    target = next(row for row in spec["rows"] if row["method"] == "PaperTable-Ours")

    assert manifest["auxiliary_display"] == ["delta"]
    assert target["cells"][0]["mean"] == pytest.approx(84.6)
    assert target["cells"][0]["auxiliary"]["value"] == pytest.approx(2.4)
    assert target["cells"][0]["n"] == 2
    assert r"r@{\hspace{0.25em}}l" in latex
    assert r"\multicolumn{2}{c}{Accuracy (\%) $\uparrow$}" in latex
    assert r"\textbf{84.6 $\pm$ 0.1} & {\scriptsize (+2.4)}" in latex
    assert r"\underline{17.8 $\pm$ 0.1} & {\scriptsize (-2.2)}" in latex
    baseline_line = next(line for line in latex.splitlines() if line.lstrip().startswith("Strong Baseline &"))
    target_line = next(line for line in latex.splitlines() if "PaperTable-Ours &" in line)
    assert baseline_line.count(" & ") == target_line.count(" & ") == 12
    assert html.count('class="cell-grid"') == 24


def test_auxiliary_delta_requires_unique_baseline(tmp_path: Path) -> None:
    source = tmp_path / "results.csv"
    source.write_text(
        "method,model,dataset,score\n"
        "Base,A,D,1\n"
        "Base,B,D,2\n"
        "Ours,C,D,3\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="baseline matched 2 rows"):
        generate([source], tmp_path / "out", {
            "input": {"metric_columns": ["score"]},
            "layout": {"row_fields": ["model", "method"]},
            "auxiliary": {
                "delta": {
                    "baseline": {"method": "Base"},
                    "targets": [{"method": "Ours"}],
                }
            },
        })


def test_empty_ranking_scope_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "results.csv"
    source.write_text("group,method,dataset,score\nBaseline,A,D,1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="ranking scope selects no displayed systems"):
        generate([source], tmp_path / "out", {
            "input": {"metric_columns": ["score"]},
            "comparison": {"rank_exclude_groups": ["Baseline"]},
        })


def test_unrepresented_identity_dimension_cannot_silently_collapse(tmp_path: Path) -> None:
    source = tmp_path / "results.csv"
    source.write_text(
        "method,protocol,dataset,accuracy\n"
        "A,zero-shot,D,80\n"
        "A,fine-tuned,D,90\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="collapse into one table cell"):
        generate([source], tmp_path / "out", {
            "input": {"metric_columns": ["accuracy"]},
        })
