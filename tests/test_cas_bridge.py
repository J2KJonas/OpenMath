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
