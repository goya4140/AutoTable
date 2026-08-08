import importlib.util
from pathlib import Path

ROOT=Path(__file__).parents[1]

def test_boolean_metadata_is_not_a_numeric_observation():
    path=ROOT/"skills/paper-table/scripts/verify_table.py"
    spec=importlib.util.spec_from_file_location("verify",path)
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    assert list(module.walk({"score":1.5,"rank_eligible":False}))==[1.5]
