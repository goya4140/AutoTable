import importlib.util
from pathlib import Path

ROOT=Path(__file__).parents[1]

def load():
    path=ROOT/"benchmarks/paperbench/aggregate_runs.py"
    spec=importlib.util.spec_from_file_location("aggregate_runs",path)
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module

def payload(kind="sd"):
    return {
        "row_keys":[{"key":"method","label":"Method"}],
        "metrics":[{"key":"score","label":"Score","direction":"max","precision":3}],
        "uncertainty":kind,
        "runs":[
            {"method":"A","seed":0,"score":1},
            {"method":"A","seed":1,"score":2},
            {"method":"A","seed":2,"score":3}]}

def test_sample_standard_deviation_is_auditable():
    out=load().aggregate(payload())
    assert out["rows"][0]["score"]=={"mean":2.0,"sd":1.0}
    assert out["aggregation_audit"][0]["run_ids"]==[0,1,2]

def test_standard_error_uses_independent_run_count():
    out=load().aggregate(payload("se"))
    assert round(out["rows"][0]["score"]["se"],8)==round(1/(3**0.5),8)

def test_duplicate_seed_is_rejected():
    m=load(); data=payload(); data["runs"][1]["seed"]=0
    try: m.aggregate(data)
    except ValueError as error: assert "duplicate run id" in str(error)
    else: raise AssertionError("duplicate run id accepted")
