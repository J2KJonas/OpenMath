import pytest
import sys
import os

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from web.py.cas_bridge import evaluate_expression, get_system_info

def test_basic_algebra():
    res = evaluate_expression("expand((x+1)^3)", precision=6)
    assert res["error"] is None
    assert "x^{3}" in res["exact_latex"] or "x**3" in res["exact_text"]

def test_calculus():
    res = evaluate_expression("diff(sin(x)*cos(x), x)", precision=6)
    assert res["error"] is None
    assert "cos" in res["exact_latex"] or "cos" in res["exact_text"]

def test_syntax_error_handling():
    res = evaluate_expression("integrate(sin(x", precision=6)
    assert res["error"] is not None
    assert "syntax" in res["error"].lower() or "bracket" in res["error"].lower() or "error" in res["error"].lower()

def test_embedded_math():
    res = evaluate_expression("to_bin(42, 8)", precision=6)
    assert res["error"] is None
    assert "00101010" in res["exact_text"] or "0b" in res["exact_text"]

def test_plot_generation():
    res = evaluate_expression("plot(sin(x), (x, -5, 5))", precision=6)
    assert res["error"] is None
    assert res["is_plot"] is True
    assert "curves" in res["plot_data"]
    assert len(res["plot_data"]["curves"]) > 0

def test_matrix_operations():
    res = evaluate_expression("det(Matrix([[1, 2], [3, 4]]))", precision=6)
    assert res["error"] is None
    assert "-2" in res["exact_text"]

def test_parse_mw_document():
    from web.py.cas_bridge import parse_worksheet_document
    sample_mw = """<?xml version="1.0" encoding="UTF-8"?>
<Worksheet>
<View-Properties presentation="false"/>
<Section collapsed="false">
<Title><Text-field>Exercise 1: Derivatives</Text-field></Title>
<Group>
<Input><Text-field><Equation input-equation="diff(sin(x), x)" display="diff(sin(x), x)">diff(sin(x), x)</Equation></Text-field></Input>
</Group>
</Section>
</Worksheet>"""
    doc = parse_worksheet_document(sample_mw)
    assert doc["error"] is None
    assert len(doc["cells"]) >= 2
    inputs = [c["input"] for c in doc["cells"]]
    assert any("Exercise 1" in inp for inp in inputs)
    assert any("diff(sin(x), x)" in inp for inp in inputs)

def test_parse_json_document():
    from web.py.cas_bridge import parse_worksheet_document
    sample_json = '[{"input": "expand((x+1)^2)", "mode": "math"}]'
    doc = parse_worksheet_document(sample_json)
    assert doc["error"] is None
    assert len(doc["cells"]) == 1
    assert doc["cells"][0]["input"] == "expand((x+1)^2)"

