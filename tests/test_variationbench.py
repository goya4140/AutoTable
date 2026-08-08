import importlib.util
from pathlib import Path


ROOT = Path(__file__).parents[1]


def load_validator():
    path = ROOT / "benchmarks/variationbench/validate.py"
    spec = importlib.util.spec_from_file_location("variationbench_validator_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_variationbench_case_and_safety_mutations_pass():
    errors, mutations = load_validator().validate_case()
    assert errors == [] and mutations == 16
