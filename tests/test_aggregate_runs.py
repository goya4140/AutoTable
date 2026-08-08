import importlib.util
from pathlib import Path

import pytest

ROOT=Path(__file__).parents[1]

def load():
    path=ROOT/"benchmarks/paperbench/aggregate_runs.py"
    spec=importlib.util.spec_from_file_location("aggregate_runs",path)
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module

def payload(kind="sd"):
    return {
        "schema_version":"paper-table-runs-v1",
        "group_keys":[{"key":"method","label":"Method"}],
        "run_id_key":"seed",
        "repeat_unit":"training seed",
        "independence":"independent",
        "reported_uncertainty":kind,
        "pairing":{"mode":"fixed_across_groups","missing_policy":"error"},
        "metrics":[{"key":"score","label":"Score","direction":"max","unit":"points","precision":3}],
        "runs":[
            {"method":"A","seed":0,"score":1},
            {"method":"A","seed":1,"score":2},
            {"method":"A","seed":2,"score":3}]}

def test_sample_standard_deviation_is_auditable():
    out=load().aggregate(payload())
    assert out["rows"][0]["score"]=={"mean":2.0,"sd":1.0}
    assert out["aggregation_audit"][0]["run_ids"]==[0,1,2]
    assert len(out["aggregation_audit"][0]["run_ids_sha256"])==64

def test_standard_error_uses_independent_run_count():
    out=load().aggregate(payload("se"))
    assert out["rows"][0]["score"]["se"]==0.577
    assert round(out["aggregation_audit"][0]["se"],8)==round(1/(3**0.5),8)

def test_duplicate_seed_is_rejected():
    m=load(); data=payload(); data["runs"][1]["seed"]=0
    with pytest.raises(ValueError,match="duplicate run id"):
        m.aggregate(data)


def test_fixed_pairing_rejects_missing_seed():
    m=load(); data=payload()
    data["runs"] += [
        {"method":"B","seed":0,"score":4},
        {"method":"B","seed":1,"score":5},
    ]
    with pytest.raises(ValueError,match="fixed_across_groups"):
        m.aggregate(data)


def test_nonfinite_values_are_rejected():
    m=load(); data=payload(); data["runs"][1]["score"]=float("nan")
    with pytest.raises(ValueError,match="finite value"):
        m.aggregate(data)


def test_independence_must_be_explicit():
    m=load(); data=payload(); data["independence"]="unknown"
    with pytest.raises(ValueError,match="explicitly declared"):
        m.aggregate(data)


def test_mean_only_keeps_uncertainty_in_audit():
    out=load().aggregate(payload("none"))
    assert out["rows"][0]["score"]==2.0
    assert out["aggregation_audit"][0]["sample_sd"]==1.0
    assert out["aggregation_audit"][0]["reported_uncertainty"]=="none"
