"""
Unit tests for the CAS Engine, Parser, and Formatter.
"""

import unittest
import sympy as sp
from cas_engine import CASEngine, MathParser, MathFormatter, PlotEngine


class TestCASEngine(unittest.TestCase):
    def setUp(self):
        self.engine = CASEngine()

    def test_basic_arithmetic_and_symbols(self):
        res = self.engine.evaluate("2 + 3 * 4")
        self.assertEqual(res.raw_result, 14)

        res = self.engine.evaluate("x^2 + 2x + 1")
        self.assertEqual(str(res.raw_result), "x**2 + 2*x + 1")

    def test_algebra(self):
        res = self.engine.evaluate("expand((x + y)^3)")
        self.assertEqual(str(res.raw_result), "x**3 + 3*x**2*y + 3*x*y**2 + y**3")

        res = self.engine.evaluate("factor(x^3 - 8)")
        self.assertEqual(str(res.raw_result), "(x - 2)*(x**2 + 2*x + 4)")

        res = self.engine.evaluate("solve(x^2 - 5x + 6 = 0, x)")
        self.assertEqual(set(res.raw_result), {2, 3})

    def test_calculus(self):
        res = self.engine.evaluate("diff(sin(x)*exp(x), x)")
        expected = sp.diff(sp.sin(sp.Symbol('x')) * sp.exp(sp.Symbol('x')), sp.Symbol('x'))
        self.assertEqual(res.raw_result, expected)

        res = self.engine.evaluate("integrate(x^2, x)")
        self.assertEqual(res.raw_result, sp.Symbol('x')**3 / 3)

        res = self.engine.evaluate("limit(sin(x)/x, x, 0)")
        self.assertEqual(res.raw_result, 1)

        res = self.engine.evaluate("taylor(exp(x), x, 0, 4)")
        # 1 + x + x^2/2 + x^3/6 + O(x^4)
        self.assertTrue("x**3/6" in str(res.raw_result))

    def test_linear_algebra(self):
        res = self.engine.evaluate("A := Matrix([[1, 2], [3, 4]])")
        self.assertEqual(res.raw_result, sp.Matrix([[1, 2], [3, 4]]))

        res = self.engine.evaluate("det(A)")
        self.assertEqual(res.raw_result, -2)

        res = self.engine.evaluate("inv(A)")
        self.assertEqual(res.raw_result, sp.Matrix([[-2, 1], [sp.Rational(3, 2), -sp.Rational(1, 2)]]))

    def test_assignments_and_history(self):
        self.engine.evaluate("f(x) := x^2 + 1")
        res = self.engine.evaluate("f(3)")
        self.assertEqual(res.raw_result, 10)

        self.engine.evaluate("a := 15")
        res = self.engine.evaluate("a * 2")
        self.assertEqual(res.raw_result, 30)

        res = self.engine.evaluate("ans + 5")
        self.assertEqual(res.raw_result, 35)

    def test_plot_command(self):
        res = self.engine.evaluate("plot(sin(x), (x, -2*pi, 2*pi))")
        self.assertTrue(res.is_plot)
        self.assertIsNotNone(res.plot_data.get('plot_obj'))

        # Test with mathematical π and range syntax
        res_pi_unicode = self.engine.evaluate("plot(sin(x), x = -2 · π .. 2 · π)")
        self.assertTrue(res_pi_unicode.is_plot)
        self.assertIsNotNone(res_pi_unicode.plot_data.get('plot_obj'))

        # Test with Pi keyword and range syntax
        res_pi_str = self.engine.evaluate("plot(sin(x), x = -2 · Pi..2 · Pi)")
        self.assertTrue(res_pi_str.is_plot)
        self.assertIsNotNone(res_pi_str.plot_data.get('plot_obj'))

        # Test parametric circle
        res_param = self.engine.evaluate("plot([cos(t), sin(t)], t = 0 .. 2 · π)")
        self.assertTrue(res_param.is_plot)

        # Test 3D plot with ranges
        res_3d = self.engine.evaluate("plot3d(sin(x) · cos(y), x = -π .. π, y = -π .. π)")
        self.assertTrue(res_3d.is_plot)
        self.assertTrue(res_3d.plot_data['plot_obj'].is_3d)

    def test_cas_eval_and_subs(self):
        res = self.engine.evaluate("eval(x^2 + 1, x = 2)")
        self.assertEqual(res.raw_result, 5)

        res = self.engine.evaluate("subs(x = 3, x^2 + 1)")
        self.assertEqual(res.raw_result, 10)

        res = self.engine.evaluate("subs(x^2 + 1, x = 4)")
        self.assertEqual(res.raw_result, 17)

    def test_cas_equations_and_normal(self):
        res = self.engine.evaluate("lhs(x = 5)")
        self.assertEqual(res.raw_result, sp.Symbol('x'))

        res = self.engine.evaluate("rhs(x = 5)")
        self.assertEqual(res.raw_result, 5)

        res = self.engine.evaluate("normal((x^2 - 1)/(x - 1))")
        self.assertEqual(res.raw_result, sp.Symbol('x') + 1)

    def test_cas_coeff_degree_convert(self):
        res = self.engine.evaluate("coeff(3*x^2 + 2*x + 1, x, 2)")
        self.assertEqual(res.raw_result, 3)

        res = self.engine.evaluate("degree(3*x^2 + 2*x + 1, x)")
        self.assertEqual(res.raw_result, 2)

        res = self.engine.evaluate("convert(1/(x^2 - 1), parfrac, x)")
        x = sp.Symbol('x')
        self.assertEqual(res.raw_result, sp.apart(1/(x**2 - 1), x))

    def test_cas_op_nops(self):
        res = self.engine.evaluate("nops(x + y + z)")
        self.assertEqual(res.raw_result, 3)

        res = self.engine.evaluate("op(1, x + y)")
        self.assertTrue(res.raw_result in (sp.Symbol('x'), sp.Symbol('y')))

    def test_cas_inert_forms_and_value(self):
        res1 = self.engine.evaluate("Diff(x^3, x)")
        self.assertTrue(isinstance(res1.raw_result, sp.Derivative))

        res2 = self.engine.evaluate("value(%)")
        self.assertEqual(res2.raw_result, 3 * sp.Symbol('x')**2)

        res3 = self.engine.evaluate("Int(x^2, x)")
        self.assertTrue(isinstance(res3.raw_result, sp.Integral))

        res4 = self.engine.evaluate("value(%)")
        self.assertEqual(res4.raw_result, sp.Symbol('x')**3 / 3)

    def test_cas_ditto_operators(self):
        self.engine.evaluate("10")
        self.engine.evaluate("20")
        self.engine.evaluate("30")

        # After evaluating 10, 20, 30:
        # % is 30
        res_ditto1 = self.engine.evaluate("%")
        self.assertEqual(res_ditto1.raw_result, 30)

        # Fresh sequence to verify %% and %%%
        self.engine.evaluate("100")
        self.engine.evaluate("200")
        self.engine.evaluate("300")

        res_ditto2 = self.engine.evaluate("%%")
        self.assertEqual(res_ditto2.raw_result, 200)

    def test_cas_packages(self):
        res = self.engine.evaluate("with(LinearAlgebra)")
        self.assertTrue(isinstance(res.raw_result, list))
        self.assertTrue(sp.Symbol('DotProduct') in res.raw_result)

        res_vec = self.engine.evaluate("DotProduct([1, 2, 3], [4, 5, 6])")
        self.assertEqual(res_vec.raw_result, 32)

    def test_cas_modulo_and_suppression(self):
        res_mod = self.engine.evaluate("17 mod 5")
        self.assertEqual(res_mod.raw_result, 2)

        res_supp = self.engine.evaluate("a := 42:")
        self.assertTrue(res_supp.suppress_output)
        self.assertEqual(self.engine.namespace['a'], 42)

    def test_limit_evaluations(self):
        res1 = self.engine.evaluate("limit(f(x), x = 0)")
        self.assertIsNotNone(res1.exact_text)

        res2 = self.engine.evaluate("limit(sin(x)/x, x = 0)")
        self.assertEqual(res2.exact_text, "1")

        res3 = self.engine.evaluate("limit(1/x, x = 0, dir='+')")
        self.assertEqual(res3.exact_text, "∞")

        res4 = self.engine.evaluate("limit(1/x, x = 0, right)")
        self.assertEqual(res4.exact_text, "∞")

        res5 = self.engine.evaluate("lim(sin(x)/x, x = 0)")
        self.assertEqual(res5.exact_text, "1")


if __name__ == '__main__':
    unittest.main()
