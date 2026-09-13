"""
Tests for MathFormatter LaTeX generation and numeric evaluation.
"""

import unittest
import sympy as sp
from cas_engine import MathFormatter


class TestMathFormatter(unittest.TestCase):
    def test_latex_formatting(self):
        expr = sp.diff(sp.sin(sp.Symbol('x')) * sp.exp(sp.Symbol('x')), sp.Symbol('x'))
        latex_str = MathFormatter.to_latex(expr)
        self.assertIn("sin", latex_str)
        self.assertIn("cos", latex_str)
        self.assertIn("e^{x}", latex_str)

    def test_matrix_latex(self):
        M = sp.Matrix([[1, 2], [3, 4]])
        latex_str = MathFormatter.to_latex(M)
        self.assertIn(r"\begin{matrix}", latex_str)

    def test_numeric_evaluation(self):
        expr = sp.sqrt(2)
        res = MathFormatter.format_all(expr, precision=4)
        self.assertIn("2", res.exact_text)
        self.assertIn(r"\sqrt{2}", res.exact_latex)
        self.assertTrue("1,414" in str(res.numeric_text) or "1.414" in str(res.numeric_text))

    def test_decimal_separator_modes(self):
        # Test comma decimal
        MathFormatter.set_decimal_separator(',')
        self.assertEqual(MathFormatter.decimal_separator, ',')
        res_comma = MathFormatter.format_all(sp.Float('3.14159'), precision=3)
        self.assertIn("3,14", res_comma.numeric_text)
        self.assertIn("3{,}14", res_comma.numeric_latex)

        # Test period decimal
        MathFormatter.set_decimal_separator('.')
        self.assertEqual(MathFormatter.decimal_separator, '.')
        res_dot = MathFormatter.format_all(sp.Float('3.14159'), precision=3)
        self.assertIn("3.14", res_dot.numeric_text)
        self.assertIn("3.14", res_dot.numeric_latex)

        # Reset back to comma default
        MathFormatter.set_decimal_separator(',')


if __name__ == '__main__':
    unittest.main()
