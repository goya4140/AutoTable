import importlib.util
from pathlib import Path


ROOT = Path(__file__).parents[1]


def load_validator():
    path = ROOT / "benchmarks/inferencebench/validate.py"
    spec = importlib.util.spec_from_file_location("inferencebench_validator_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_real_tunetables_inference_case_and_safety_mutations_pass():
    validator = load_validator()
    errors, mutations = validator.validate_tunetables()
    assert errors == [] and mutations == 5


def test_clustered_estimand_reversal_and_safety_mutations_pass():
    validator = load_validator()
    errors, mutations = validator.validate_clustered()
    assert errors == [] and mutations == 6


def test_multimethod_omnibus_gating_and_safety_mutations_pass():
    validator = load_validator()
    errors, mutations = validator.validate_multimethod()
    assert errors == [] and mutations == 9
