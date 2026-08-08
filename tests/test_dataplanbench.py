import importlib.util
from pathlib import Path


ROOT = Path(__file__).parents[1]


def load_validator():
    path = ROOT / "benchmarks/dataplanbench/validate.py"
    spec = importlib.util.spec_from_file_location("dataplanbench_validator_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_data_acquisition_case_and_safety_mutations_pass():
    validator = load_validator()
    errors, mutations = validator.validate_case()
    assert errors == [] and mutations == 11
    errors, mutations = validator.validate_paired_difference_case()
    assert errors == [] and mutations == 12
