import importlib.util
from pathlib import Path


ROOT = Path(__file__).parents[1]


def load_validator():
    path = ROOT / "benchmarks/statbench/validate.py"
    spec = importlib.util.spec_from_file_location("statbench_validator_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_diamond_raw_runs_reproduce_all_published_cells():
    validator = load_validator()
    case_dir = ROOT / "benchmarks/statbench/cases/neurips24-diamond-atari"
    assert validator.validate_diamond(case_dir) == []


def test_tunetables_detects_snapshot_drift_without_admitting_false_gold():
    validator = load_validator()
    case_dir = ROOT / "benchmarks/statbench/cases/neurips24-tunetables-tabzilla"
    assert validator.validate_tunetables(case_dir) == []
