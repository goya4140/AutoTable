import importlib.util, json
from pathlib import Path
ROOT=Path(__file__).parents[1]
def load(name,path):
    s=importlib.util.spec_from_file_location(name,path); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
def test_seed_cases_are_true_pairs():
    cases=list((ROOT/"benchmarks/paperbench/cases").glob("*/case.json"))
    assert len(cases)>=3
    for path in cases:
        case=json.loads(path.read_text()); folder=path.parent; x=json.loads((folder/"x.json").read_text())
        assert case["schema_version"] == "2.0"
        assert case["task"] == "experimental-data-to-publication-table"
        assert case["semantic_contract"]["comparison_groups"]
        assert case["semantic_contract"]["inquiry_profile"]["fields"]
        assert case["input_tier"] in {"raw_runs","canonical_table","recovered_table"}
        assert (folder/case["reference"]["image"]).exists()
        assert x["columns"] and x["rows"] and case["reference"]["sha256"] != "PENDING"
        assert all("unit" in column and "direction" in column for column in x["columns"] if column.get("kind")=="metric")
        if case["input_tier"]=="raw_runs":
            descriptor=case.get("input")
            assert descriptor and (folder/descriptor["path"]).is_file()
            assert x.get("aggregation_audit")
        if case["input_tier"]=="canonical_table":
            assert case.get("source_artifacts")
            assert case.get("transformation")
def test_numeric_multiset_normalizes_precision():
    m=load("evaluate",ROOT/"benchmarks/paperbench/evaluate.py")
    recall,precision,hall=m.multiset_recall(["-0.8","12"],["-0.80","12.0"])
    assert (recall,precision,hall)==(1.0,1.0,0)


def test_all_cases_pass_repository_validation():
    validator=load("validate_cases",ROOT/"benchmarks/paperbench/validate_cases.py")
    for case_dir in (ROOT/"benchmarks/paperbench/cases").iterdir():
        if case_dir.is_dir():
            assert validator.validate_case(case_dir)==[]
