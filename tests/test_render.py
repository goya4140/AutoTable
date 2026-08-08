import importlib.util, json
from pathlib import Path
ROOT=Path(__file__).parents[1]
def load(name,path):
    s=importlib.util.spec_from_file_location(name,path); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
def test_render_is_faithful():
    m=load("render",ROOT/"skills/paper-table/scripts/render_table.py")
    spec=json.loads((ROOT/"examples/main-results.json").read_text())
    tex,html=m.render(spec)
    assert "85.6" in tex and "83.4" in html and "\\textbf{85.6" in tex
    assert "\\toprule" in tex and "<table>" in html

def test_render_supports_nested_column_groups():
    m=load("render_grouped",ROOT/"skills/paper-table/scripts/render_table.py")
    spec={
        "caption":"Grouped","column_supergroup":"Dataset","columns":[
            {"key":"method","label":"Method","kind":"text"},
            {"key":"a","label":"Accuracy","kind":"metric","direction":"max","group":"Split A"},
            {"key":"b","label":"Accuracy","kind":"metric","direction":"max","group":"Split B"}],
        "rows":[{"method":"M","a":1,"b":2}]}
    tex,html=m.render(spec)
    assert "\\multicolumn{2}{c}{Dataset}" in tex
    assert "\\multicolumn{1}{c}{Split A}" in tex
    assert 'colspan="2">Dataset' in html
