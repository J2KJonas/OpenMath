"""
Tests for MathParser shorthand syntax, assignments, calculus, and matrix commands.
"""

import unittest
import sympy as sp
from cas_engine import MathParser


class TestMathParser(unittest.TestCase):
    def test_shorthand_multiplication(self):
        res = MathParser.parse("2x + 3y")
        self.assertEqual(str(res.sympy_expr), "2*x + 3*y")

        res = MathParser.parse("4(x + 1)(x - 1)")
        x = sp.Symbol('x')
        self.assertEqual(sp.expand(res.sympy_expr), sp.expand(4*(x + 1)*(x - 1)))

    def test_powers_and_greek(self):
        res = MathParser.parse("x^3 + pi * r^2")
        self.assertTrue(sp.pi in res.sympy_expr.free_symbols or "pi" in str(res.sympy_expr))

    def test_unicode_symbols(self):
        res = MathParser.parse("√x + ∞")
        self.assertEqual(str(res.sympy_expr), "sqrt(x) + oo")

    def test_equation_parsing(self):
        res = MathParser.parse("x^2 + 5x + 6 = 0")
        self.assertTrue(isinstance(res.sympy_expr, sp.Eq))
        self.assertEqual(str(res.sympy_expr.lhs), "x**2 + 5*x + 6")
        self.assertEqual(res.sympy_expr.rhs, 0)

    def test_solve_nested_equation(self):
        res = MathParser.parse("solve(x^2 = 4, x)")
        self.assertIn(-2, res.sympy_expr)
        self.assertIn(2, res.sympy_expr)

    def test_decimal_comma_parsing(self):
        # Basic arithmetic with decimal commas
        res1 = MathParser.parse("1,5 + 2,5")
        self.assertEqual(float(res1.sympy_expr), 4.0)

        # Assignment with decimal comma and suppressed output
        res2 = MathParser.parse("U := 100,5:")
        self.assertTrue(res2.is_assignment)
        self.assertEqual(res2.assign_var, "U")
        self.assertAlmostEqual(float(res2.sympy_expr), 100.5)

        # Equation solving with decimal comma
        res3 = MathParser.parse("solve(x^2 - 2,25 = 0, x)")
        vals = [round(float(v), 2) for v in res3.sympy_expr]
        self.assertIn(-1.5, vals)
        self.assertIn(1.5, vals)

        # European list separation with semicolons and decimal commas
        res4 = MathParser.parse("[1,2; 3,4]")
        self.assertEqual(len(res4.sympy_expr), 2)
        self.assertAlmostEqual(float(res4.sympy_expr[0]), 1.2)
        self.assertAlmostEqual(float(res4.sympy_expr[1]), 3.4)

        # Number with space after comma (e.g. '30, 4') should be 30.4, not coordinate tuple
        res5 = MathParser.parse("30, 4")
        self.assertAlmostEqual(float(res5.sympy_expr), 30.4)
        self.assertFalse(isinstance(res5.sympy_expr, (tuple, list, sp.Tuple)))

        # Explicit coordinate with parentheses must still be a tuple
        res6 = MathParser.parse("(30, 4)")
        self.assertTrue(isinstance(res6.sympy_expr, (tuple, list, sp.Tuple)))


    def test_scientific_notation_parsing(self):
        # Test spaced scientific notation e.g. 4e - 06 or 1e + 03
        res1 = MathParser.parse("4e - 06")
        self.assertAlmostEqual(float(res1.sympy_expr), 4e-6)

        res2 = MathParser.parse("timer_calc(16 * 10^6, 64, 249) = {'tick_time_sec': 4e - 06}:")
        self.assertTrue(res2.suppress_output)

    def test_range_syntax(self):
        # Range with expressions and constants (Pi and π)
        prep1 = MathParser.preprocess_string("plot(sin(x), x = -2 · Pi..2 · Pi)")
        self.assertIn("(x, -2 * pi, 2 * pi)", prep1)

        prep2 = MathParser.preprocess_string("plot(sin(x), x = -2 · π .. 2 · π)")
        self.assertIn("(x, -2 * pi, 2 * pi)", prep2)

        prep3 = MathParser.preprocess_string("plot3d(sin(x) * cos(y), x = -π .. π, y = -π .. π)")
        self.assertIn("(x, -pi, pi)", prep3)
        self.assertIn("(y, -pi, pi)", prep3)

        prep4 = MathParser.preprocess_string("x = 1..10")
        self.assertEqual(prep4, "(x, 1, 10)")

        prep5 = MathParser.preprocess_string("1..10")
        self.assertEqual(prep5, "(1, 10)")


if __name__ == '__main__':
    unittest.main()
