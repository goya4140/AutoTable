import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).parents[1]
BENCH = ROOT / "benchmarks/paperbench"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def first_case():
    path = sorted((BENCH / "cases").glob("*/case.json"))[0]
    return json.loads(path.read_text()), json.loads((path.parent / "x.json").read_text())


def test_reference_passes_semantic_contract():
    evaluator = load("contract_eval", BENCH / "contract_eval.py")
    case, table = first_case()
    result = evaluator.evaluate(table, table, case)
    assert result["passed_scientific_gate"]
    assert result["passed_full_contract"]


def test_controlled_mutations_hit_expected_categories():
    evaluator = load("contract_eval_mutations", BENCH / "contract_eval.py")
    controlled = load("build_controlled", BENCH / "build_controlled.py")
    descriptors = [json.loads(line) for line in (BENCH / "controlled/cases.jsonl").read_text().splitlines()]
    assert len(descriptors) >= 24
    for descriptor in descriptors:
        case_path = BENCH / "cases" / descriptor["base_case_id"] / "case.json"
        case = json.loads(case_path.read_text())
        table = json.loads((case_path.parent / "x.json").read_text())
        candidate = controlled.apply_mutation(table, descriptor["mutation"])
        result = evaluator.evaluate(table, candidate, case)
        assert descriptor["expected_violation_category"] in result["category_counts"]
