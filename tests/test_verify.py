import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).parents[1]

def test_boolean_metadata_is_not_a_numeric_observation():
    path=ROOT/"skills/paper-table/scripts/verify_table.py"
    spec=importlib.util.spec_from_file_location("verify",path)
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    assert list(module.walk({"score":1.5,"rank_eligible":False}))==[1.5]


def test_confidence_interval_bounds_are_verified():
    path=ROOT/"skills/paper-table/scripts/verify_table.py"
    spec=importlib.util.spec_from_file_location("verify_ci",path)
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    assert list(module.walk({"score":{"mean":1.0,"ci95":[0.8,1.2]},"precision":2}))==[1.0,0.8,1.2]


def test_cli_fails_when_confidence_bound_is_missing(tmp_path):
    script=ROOT/"skills/paper-table/scripts/verify_table.py"
    spec_path=tmp_path/"spec.json"; rendered=tmp_path/"table.tex"
    spec_path.write_text(json.dumps({"rows":[{"score":{"mean":1.0,"ci95":[0.8,1.2]}}]}))
    rendered.write_text("1.0 [0.8]")
    result=subprocess.run([sys.executable,str(script),str(spec_path),str(rendered)],capture_output=True,text=True)
    report=json.loads(result.stdout)
    assert result.returncode==1 and report["missing_numeric_values"]==[1.2]
