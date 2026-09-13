"""
Main Computer Algebra System (CAS) Engine.
Integrates parser, SymPy evaluation, namespace management, and result formatting.
"""

import time
import warnings
import sympy as sp
import numpy as np
import re

from .parser import MathParser, ParseResult
from .formatter import MathFormatter, CASResult
from .plot_engine import PlotEngine, PlotData
from sympy.utilities.exceptions import SymPyDeprecationWarning


class CASEngine:
    """
    Stateful CAS evaluation engine.
    Maintains variables, symbols, execution history, and built-in math commands.
    """

    PACKAGES = {
        "LinearAlgebra": [
            "Add", "BackwardSubstitute", "BandMatrix", "Basis", "CharacteristicPolynomial",
            "Column", "ColumnDimension", "ColumnOperation", "ColumnSpace", "CompanionMatrix",
            "ConditionNumber", "ConstantMatrix", "ConstantVector", "CrossProduct", "DeleteColumn",
            "DeleteRow", "Determinant", "Diagonal", "DiagonalMatrix", "Dimension", "DotProduct",
            "Eigenvalues", "Eigenvectors", "Equal", "ForwardSubstitute", "GaussianElimination",
            "GramSchmidt", "HermitianTranspose", "Hessenberg", "HilbertMatrix", "IdentityMatrix",
            "IntersectionBasis", "IsDefinite", "IsOrthogonal", "IsSimilar", "IsUnitary",
            "JordanBlock", "JordanForm", "KroneckerProduct", "LeastSquares", "LinearSolve",
            "LUDecomposition", "MatrixAdd", "MatrixInverse", "MatrixMatrixMultiply",
            "MatrixPower", "MatrixScalarMultiply", "MatrixVectorMultiply", "MinimalPolynomial",
            "Minor", "Multiply", "Norm", "Normalize", "NullSpace", "OuterProductMatrix",
            "Permanent", "Pivot", "QRDecomposition", "RandomMatrix", "RandomVector", "Rank",
            "ReducedRowEchelonForm", "Row", "RowDimension", "RowOperation", "RowSpace",
            "ScalarMatrix", "ScalarMultiply", "ScalarVector", "SchurForm", "SingularValues",
            "SubMatrix", "SubVector", "SumBasis", "SylvesterMatrix", "ToeplitzMatrix", "Trace",
            "Transpose", "TridiagonalMatrix", "UnitVector", "VandermondeMatrix", "VectorAngle",
            "VectorNorm", "VectorSpaceBasis", "ZeroMatrix", "ZeroVector", "Zip"
        ],
        "VectorCalculus": [
            "ArcLength", "CrossProduct", "Curl", "Curvature", "Divergence", "DotProduct",
            "Gradient", "Hessian", "Jacobian", "Laplacian", "LineInt", "Norm", "Normalize",
            "PathInt", "PositionVector", "RadiusOfCurvature", "ScalarPotential", "SurfaceInt",
            "TangentVector", "Torsion", "VectorAngle", "VectorField"
        ],
        "Student[Calculus1]": [
            "AntiderivativePlot", "ApproximateInt", "ArcLength", "Asymptotes", "Clear",
            "CriticalPoints", "CurveAnalysisPlot", "DerivativePlot", "DiffPlot", "FunctionChart",
            "FunctionPlot", "InflectionPoints", "InversePlot", "LimitPlot", "MeanValueTheorem",
            "NewtonQuotient", "PointInterpolation", "RollesTheorem", "Roots", "Secant",
            "Show", "ShowSolution", "SurfaceOfRevolution", "Tangent", "TangentSecantPlot",
            "TaylorApproximation", "VolumeOfRevolution", "WhatProblem"
        ],
        "Student[LinearAlgebra]": [
            "ApplyLinearTransform", "CharacteristicPolynomial", "ColumnSpace", "CrossProduct",
            "Determinant", "Dimension", "DotProduct", "Eigenvalues", "Eigenvectors",
            "GaussianElimination", "GramSchmidt", "Inverse", "LeastSquares", "LinearSolve",
            "LUDecomposition", "MatrixAdd", "Norm", "NullSpace", "Plane", "Projection",
            "QRDecomposition", "Rank", "RowSpace", "Trace", "Transpose", "VectorAngle"
        ],
        "plots": [
            "animate", "animate3d", "animatecurve", "arrow", "changecoords", "complexplot",
            "complexplot3d", "conformal", "contourplot", "contourplot3d", "coordplot",
            "coordplot3d", "cylinderplot", "densityplot", "display", "fieldplot", "fieldplot3d",
            "gradplot", "gradplot3d", "implicitplot", "implicitplot3d", "inequal", "interactive",
            "interactiveparams", "intersectplot", "listcontplot", "listcontplot3d", "listdensityplot",
            "listplot", "listplot3d", "loglogplot", "logplot", "matrixplot", "odeplot", "pareto",
            "plotcompare", "pointplot", "pointplot3d", "polarplot", "polyhedraplot", "rootlocus",
            "semilogplot", "setcolors", "setoptions", "setoptions3d", "spacecurve", "sparsematrixplot",
            "surfdata", "textplot", "textplot3d", "tubeplot"
        ]
    }

    def __init__(self):
        self.namespace = {}
        self.history = {}           # execution_idx -> CASResult
        self.history_raw = {}       # execution_idx -> raw SymPy object
        self.execution_count = 0
        self._init_builtins()
        self._initial_namespace = dict(self.namespace)
        self._builtin_keys = set(self.namespace.keys())

    def load_package(self, pkg_name: str) -> list:
        """
        Load a package into the namespace and return its list of symbols.
        E.g. with(LinearAlgebra)
        """
        matched_pkg = None
        for k in self.PACKAGES:
            if k.lower() == pkg_name.lower():
                matched_pkg = k
                break
        if not matched_pkg:
            matched_pkg = pkg_name

        exports = self.PACKAGES.get(matched_pkg, [])
        if not exports:
            # Check if case insensitive match without brackets
            clean_name = pkg_name.replace('[', '_').replace(']', '').lower()
            for k in self.PACKAGES:
                if k.replace('[', '_').replace(']', '').lower() == clean_name:
                    exports = self.PACKAGES[k]
                    break

        # Register all exported symbols in namespace
        for sym_name in exports:
            if sym_name not in self.namespace:
                self.namespace[sym_name] = sp.Symbol(sym_name)

        return [sp.Symbol(sym) for sym in exports]

    def _init_builtins(self):
        """Initialize built-in SymPy functions, symbols, and CAS aliases."""
        self.namespace.clear()

        # SymPy common functions and symbols
        builtins_list = [
            # Standard functions
            sp.sin, sp.cos, sp.tan, sp.sec, sp.csc, sp.cot,
            sp.asin, sp.acos, sp.atan, sp.asec, sp.acsc, sp.acot,
            sp.sinh, sp.cosh, sp.tanh, sp.asinh, sp.acosh, sp.atanh,
            sp.exp, sp.log, sp.sqrt, sp.cbrt, sp.Abs, sp.sign,
            sp.factorial, sp.gamma, sp.erf, sp.zeta, sp.binomial,
            sp.Piecewise, sp.floor, sp.ceiling,

            # Calculus
            sp.diff, sp.integrate, sp.limit, sp.series, sp.dsolve,
            sp.Sum, sp.Product, sp.Derivative, sp.Integral,

            # Algebra
            sp.expand, sp.factor, sp.simplify, sp.collect, sp.cancel,
            sp.apart, sp.together, sp.solve, sp.solveset, sp.nsolve,
            sp.roots, sp.Poly, sp.trigsimp, sp.expand_trig,

            # Linear Algebra
            sp.Matrix, sp.eye, sp.zeros, sp.ones, sp.diag,

            # Logic & Equations
            sp.Eq, sp.Ne, sp.Lt, sp.Le, sp.Gt, sp.Ge,

            # Constants
            sp.pi, sp.E, sp.I, sp.oo, sp.nan,
        ]

        for item in builtins_list:
            if hasattr(item, '__name__'):
                self.namespace[item.__name__] = item

        # Aliases
        self.namespace['ln'] = sp.log
        self.namespace['abs'] = sp.Abs
        self.namespace['arcsin'] = sp.asin
        self.namespace['arccos'] = sp.acos
        self.namespace['arctan'] = sp.atan
        def _named_fn(name, fn):
            fn.__name__ = name
            fn.__qualname__ = name
            return fn

        self.namespace['det'] = _named_fn('det', lambda m: m.det() if hasattr(m, 'det') else sp.det(m))
        self.namespace['inv'] = _named_fn('inv', lambda m: m.inv() if hasattr(m, 'inv') else m**-1)
        self.namespace['transpose'] = _named_fn('transpose', lambda m: m.T if hasattr(m, 'T') else sp.transpose(m))
        self.namespace['eigenvals'] = _named_fn('eigenvals', lambda m: m.eigenvals() if hasattr(m, 'eigenvals') else sp.Matrix(m).eigenvals())
        self.namespace['eigenvects'] = _named_fn('eigenvects', lambda m: m.eigenvects() if hasattr(m, 'eigenvects') else sp.Matrix(m).eigenvects())
        self.namespace['rref'] = _named_fn('rref', lambda m: m.rref()[0] if hasattr(m, 'rref') else sp.Matrix(m).rref()[0])
        self.namespace['nullspace'] = _named_fn('nullspace', lambda m: m.nullspace() if hasattr(m, 'nullspace') else sp.Matrix(m).nullspace())
        self.namespace['rank'] = _named_fn('rank', lambda m: m.rank() if hasattr(m, 'rank') else sp.Matrix(m).rank())
        self.namespace['trace'] = _named_fn('trace', lambda m: m.trace() if hasattr(m, 'trace') else sp.trace(m))
        self.namespace['charpoly'] = _named_fn('charpoly', lambda m, *args: m.charpoly(*args) if hasattr(m, 'charpoly') else sp.Matrix(m).charpoly(*args))
        # Sets and Logic
        self.namespace['EmptySet'] = sp.S.EmptySet
        self.namespace['Complexes'] = sp.S.Complexes
        self.namespace['Reals'] = sp.S.Reals
        self.namespace['Naturals'] = sp.S.Naturals
        self.namespace['Integers'] = sp.S.Integers
        self.namespace['Rationals'] = sp.S.Rationals
        self.namespace['Contains'] = lambda x, s: sp.Contains(x, s) if isinstance(s, sp.Set) else sp.Function('Contains')(x, s)
        self.namespace['Subset'] = lambda *args: sp.Function('Subset')(*args)
        self.namespace['Superset'] = lambda *args: sp.Function('Superset')(*args)
        self.namespace['Intersection'] = lambda *args: sp.Intersection(*args) if all(isinstance(a, sp.Set) for a in args) else sp.Function('Intersection')(*args)
        self.namespace['Union'] = lambda *args: sp.Union(*args) if all(isinstance(a, sp.Set) for a in args) else sp.Function('Union')(*args)
        self.namespace['Implies'] = sp.Implies
        self.namespace['Equivalent'] = sp.Equivalent
        self.namespace['Not'] = sp.Not
        self.namespace['And'] = sp.And
        self.namespace['Or'] = sp.Or
        self.namespace['Exists'] = sp.Function('Exists')
        self.namespace['ForAll'] = sp.Function('ForAll')
        self.namespace['Q'] = sp.Symbol('Q')
        self.namespace['e'] = sp.E
        self.namespace['i'] = sp.I
        self.namespace['j'] = sp.I

        # Taylor expansion function
        def _taylor(f, var=sp.Symbol('x'), x0=0, n=6):
            if isinstance(var, sp.Eq):
                # e.g. taylor(f, x=0, 5)
                x0 = var.rhs
                var = var.lhs
            return sp.series(f, var, x0, n)

        self.namespace['taylor'] = _taylor
        self.namespace['series'] = _taylor

        # Limit evaluation function supporting x=c kwarg, Eq(x, c), and right/left direction strings
        def _safe_limit(e, *args, **kwargs):
            if len(args) >= 1:
                first = args[0]
                if isinstance(first, sp.Eq) or (hasattr(first, 'lhs') and hasattr(first, 'rhs')):
                    var = first.lhs
                    val = first.rhs
                    new_args = (var, val) + args[1:]
                    return _safe_limit(e, *new_args, **kwargs)
                elif isinstance(first, (tuple, list)) and len(first) == 2:
                    var, val = first
                    new_args = (var, val) + args[1:]
                    return _safe_limit(e, *new_args, **kwargs)
            if len(args) == 0:
                dir_val = kwargs.pop('dir', '+')
                if kwargs:
                    var_name, val = next(iter(kwargs.items()))
                    return _safe_limit(e, sp.Symbol(var_name), val, dir=dir_val)
            if 'dir' in kwargs:
                d = str(kwargs['dir'])
                if 'left' in d or '-' in d:
                    kwargs['dir'] = '-'
                elif 'right' in d or '+' in d:
                    kwargs['dir'] = '+'
            if len(args) >= 3:
                d = str(args[2])
                if 'left' in d or '-' in d:
                    args = args[:2] + ('-',) + args[3:]
                elif 'right' in d or '+' in d:
                    args = args[:2] + ('+',) + args[3:]
            return sp.limit(e, *args, **kwargs)

        self.namespace['limit'] = _safe_limit
        self.namespace['lim'] = _safe_limit

        # Common default symbols
        for sym_name in ['x', 'y', 'z', 't', 'u', 'v', 'w', 'a', 'b', 'c', 'k', 'n', 'm', 'theta', 'phi', 'lambda_sym']:
            clean_name = 'lambda' if sym_name == 'lambda_sym' else sym_name
            self.namespace[clean_name] = sp.Symbol(clean_name)

        # evalf / numerical approximation
        def _evalf(expr, n=10):
            try:
                return sp.N(expr, n)
            except Exception:
                return float(expr)

        self.namespace['evalf'] = _evalf
        self.namespace['N'] = _evalf

        # fsolve / numerical root finding
        def _fsolve(eq, var=None, *args):
            if isinstance(eq, sp.Eq):
                expr = eq.lhs - eq.rhs
            else:
                expr = sp.sympify(eq)
            if var is None:
                free = list(expr.free_symbols)
                var = free[0] if free else sp.Symbol('x')
            try:
                if args:
                    guess = args[0]
                    if isinstance(guess, (tuple, list)) and len(guess) == 2:
                        return sp.nsolve(expr, var, (guess[0], guess[1]))
                    return sp.nsolve(expr, var, guess)
                try:
                    return sp.nsolve(expr, var, 1.0)
                except Exception:
                    return sp.nsolve(expr, var, 0.0)
            except Exception:
                sols = sp.solve(expr, var)
                if sols:
                    return [s.evalf() for s in sols] if isinstance(sols, list) else sols.evalf()
                raise ValueError(f"fsolve could not find numerical root for {eq}")

        self.namespace['fsolve'] = _fsolve

        # LinearAlgebra Vector
        def _Vector(*args):
            if len(args) == 1 and isinstance(args[0], (list, tuple)):
                return sp.Matrix(args[0])
            return sp.Matrix(args)

        self.namespace['Vector'] = _Vector

        # piecewise function
        def _piecewise(*args):
            pairs = []
            i = 0
            while i < len(args) - 1:
                cond = args[i]
                val = args[i+1]
                pairs.append((val, cond))
                i += 2
            if i < len(args):
                pairs.append((args[i], True))
            return sp.Piecewise(*pairs)

        self.namespace['piecewise'] = _piecewise

        # sequence, add, mul commands
        def _seq(expr, *args):
            if not args:
                return [expr]
            if len(args) == 1 and isinstance(args[0], (tuple, list)):
                var, a, b = args[0]
            elif len(args) >= 3:
                var, a, b = args[0], args[1], args[2]
            else:
                var = sp.Symbol('i')
                a, b = 1, args[0]
            a_val = int(sp.sympify(a))
            b_val = int(sp.sympify(b))
            res = []
            for val in range(a_val, b_val + 1):
                cur = expr
                if hasattr(cur, 'subs'):
                    cur = cur.subs(var, val)
                    if str(var).lower() == 'i' and cur.has(sp.I):
                        cur = cur.subs(sp.I, val)
                res.append(cur)
            return res

        def _add(expr, *args):
            return sum(_seq(expr, *args))

        def _mul(expr, *args):
            items = _seq(expr, *args)
            prod = 1
            for it in items:
                prod *= it
            return prod

        self.namespace['seq'] = _seq
        self.namespace['add'] = _add
        self.namespace['mul'] = _mul

        # optimization commands
        def _maximize(f, var=sp.Symbol('x')):
            df = sp.diff(f, var)
            crit = sp.solve(df, var)
            vals = [f.subs(var, c) for c in crit]
            if vals:
                return max(vals, key=lambda v: float(sp.re(v.evalf())))
            return f

        def _minimize(f, var=sp.Symbol('x')):
            df = sp.diff(f, var)
            crit = sp.solve(df, var)
            vals = [f.subs(var, c) for c in crit]
            if vals:
                return min(vals, key=lambda v: float(sp.re(v.evalf())))
            return f

        self.namespace['maximize'] = _maximize
        self.namespace['minimize'] = _minimize

        # Capitalized LinearAlgebra synonyms
        self.namespace['Determinant'] = self.namespace['det']
        self.namespace['Inverse'] = self.namespace['inv']
        self.namespace['Transpose'] = self.namespace['transpose']
        self.namespace['Eigenvalues'] = self.namespace['eigenvals']
        self.namespace['Eigenvectors'] = self.namespace['eigenvects']
        self.namespace['Trace'] = self.namespace['trace']
        self.namespace['Rank'] = self.namespace['rank']
        self.namespace['NullSpace'] = self.namespace['nullspace']
        self.namespace['CharacteristicPolynomial'] = self.namespace['charpoly']

        # Plotting helper in namespace
        self.namespace['plot'] = self._cmd_plot
        self.namespace['plot3d'] = self._cmd_plot3d
        self.namespace['plot_parametric'] = self._cmd_plot_parametric
        self.namespace['plot_polar'] = self._cmd_plot_polar
        self.namespace['polygonOmråde'] = self._cmd_polygon_omraade
        self.namespace['polygonOmraade'] = self._cmd_polygon_omraade
        self.namespace['LPplot'] = self._cmd_lp_plot

        # Default linear inequalities from reference screenshot
        _x, _y = sp.Symbol('x'), sp.Symbol('y')
        self.namespace['Uligheder'] = [
            sp.Eq(10, 5 * _x + _y),
            sp.Eq(12, 2 * _x + 2 * _y),
            sp.Eq(12, _x + 4 * _y)
        ]

        # Common math constants
        self.namespace['Pi'] = sp.pi
        self.namespace['infinity'] = sp.oo

        # eval function: eval(expr, x = 2) or eval(expr, [x = 2, y = 3])
        def _cas_eval(expr, *args):
            if not args:
                return expr
            subs_dict = {}
            def _extract_subs(item):
                if isinstance(item, sp.Eq):
                    subs_dict[item.lhs] = item.rhs
                elif isinstance(item, (tuple, list, set)):
                    for sub_item in item:
                        _extract_subs(sub_item)
                elif isinstance(item, dict):
                    subs_dict.update(item)
            for arg in args:
                _extract_subs(arg)
            if hasattr(expr, 'subs') and subs_dict:
                return expr.subs(subs_dict)
            return expr

        # subs function: subs(x = 2, expr) or subs(x = 2, y = 3, expr) or subs(expr, x = 2)
        def _cas_subs(*args):
            if len(args) == 0:
                return None
            if len(args) == 1:
                return args[0]
            subs_dict = {}
            def _add_to_subs(item):
                if isinstance(item, sp.Eq):
                    subs_dict[item.lhs] = item.rhs
                elif isinstance(item, (tuple, list, set)):
                    for sub_item in item:
                        _add_to_subs(sub_item)
                elif isinstance(item, dict):
                    subs_dict.update(item)

            if isinstance(args[0], sp.Eq) or (isinstance(args[0], (list, tuple)) and args[0] and isinstance(args[0][0], sp.Eq)):
                # Multi-arg style: subs(eq1, eq2, ..., expr)
                target_expr = args[-1]
                for item in args[:-1]:
                    _add_to_subs(item)
                if hasattr(target_expr, 'subs') and subs_dict:
                    return target_expr.subs(subs_dict)
                return target_expr
            else:
                # Python/SymPy style: subs(expr, eq1, ...) or subs(expr, x, 2)
                target_expr = args[0]
                if len(args) == 3 and not isinstance(args[1], sp.Eq):
                    if hasattr(target_expr, 'subs'):
                        return target_expr.subs(args[1], args[2])
                    return target_expr
                for item in args[1:]:
                    _add_to_subs(item)
                if hasattr(target_expr, 'subs') and subs_dict:
                    return target_expr.subs(subs_dict)
                return target_expr

        self.namespace['eval'] = _cas_eval
        self.namespace['subs'] = _cas_subs

        # equation sides
        self.namespace['lhs'] = lambda eq: eq.lhs if hasattr(eq, 'lhs') else eq
        self.namespace['rhs'] = lambda eq: eq.rhs if hasattr(eq, 'rhs') else eq

        # normal rational simplification
        self.namespace['normal'] = lambda expr: sp.cancel(sp.together(expr)) if hasattr(expr, 'is_rational_function') or isinstance(expr, sp.Basic) else expr

        # coeff and degree
        def _coeff(p, var=None, n=1):
            try:
                p_expr = sp.sympify(p)
                if var is None:
                    free = list(p_expr.free_symbols)
                    var = free[0] if free else sp.Symbol('x')
                poly = sp.Poly(p_expr, var)
                deg = int(n) if n is not None else 1
                return poly.coeff_monomial(var**deg)
            except Exception:
                try:
                    return p.coeff(var, n)
                except Exception:
                    return sp.Integer(0)

        def _degree(p, var=None):
            try:
                p_expr = sp.sympify(p)
                if var is None:
                    free = list(p_expr.free_symbols)
                    var = free[0] if free else sp.Symbol('x')
                poly = sp.Poly(p_expr, var)
                return sp.Integer(poly.degree())
            except Exception:
                try:
                    return sp.degree(p, var)
                except Exception:
                    return sp.Integer(0)

        self.namespace['coeff'] = _coeff
        self.namespace['degree'] = _degree

        # convert command
        def _convert(expr, target_type, *args):
            target_str = str(target_type).lower().strip()
            if target_str in ('parfrac', 'apart', 'partialfraction'):
                var = args[0] if args else None
                return sp.apart(expr, var) if var is not None else sp.apart(expr)
            elif target_str in ('fraction', 'rational'):
                return sp.nsimplify(expr)
            elif target_str in ('sincos', 'trig'):
                return sp.trigsimp(expr)
            elif target_str in ('exp',):
                return expr.rewrite(sp.exp) if hasattr(expr, 'rewrite') else expr
            elif target_str in ('log', 'ln'):
                return expr.rewrite(sp.log) if hasattr(expr, 'rewrite') else expr
            elif target_str in ('degrees', 'deg'):
                return expr * 180 / sp.pi
            elif target_str in ('radians', 'rad'):
                return expr * sp.pi / 180
            elif target_str in ('list',):
                if isinstance(expr, (list, tuple, set)):
                    return list(expr)
                if hasattr(expr, 'args') and expr.args:
                    return list(expr.args)
                return [expr]
            elif target_str in ('set',):
                if isinstance(expr, (list, tuple, set)):
                    return set(expr)
                if hasattr(expr, 'args') and expr.args:
                    return set(expr.args)
                return {expr}
            elif target_str in ('string',):
                return str(expr)
            return expr

        self.namespace['convert'] = _convert

        # op and nops
        def _op(*args):
            if len(args) == 1:
                expr = args[0]
                if hasattr(expr, 'args') and expr.args:
                    return list(expr.args)
                return [expr]
            elif len(args) == 2:
                idx, expr = args[0], args[1]
                if idx == 0:
                    return expr.func if hasattr(expr, 'func') else type(expr)
                idx_int = int(idx)
                if hasattr(expr, 'args') and expr.args:
                    if idx_int > 0 and idx_int <= len(expr.args):
                        return expr.args[idx_int - 1]
                    elif idx_int < 0 and abs(idx_int) <= len(expr.args):
                        return expr.args[idx_int]
                raise IndexError(f"op index {idx} out of range for {expr}")
            raise ValueError("op expects 1 or 2 arguments")

        def _nops(expr):
            return len(expr.args) if hasattr(expr, 'args') else 0

        self.namespace['op'] = _op
        self.namespace['nops'] = _nops

        # map, select, remove
        def _map(fn, container, *args):
            if isinstance(container, (list, tuple)):
                return type(container)(fn(item, *args) for item in container)
            elif isinstance(container, set):
                return {fn(item, *args) for item in container}
            elif isinstance(container, sp.Matrix):
                return container.applyfunc(lambda x: fn(x, *args))
            elif hasattr(container, 'args') and container.args:
                new_args = [fn(a, *args) for a in container.args]
                return container.func(*new_args)
            return fn(container, *args)

        self.namespace['map'] = _map
        self.namespace['select'] = lambda pred, c: type(c)(x for x in c if pred(x)) if isinstance(c, (list, tuple)) else {x for x in c if pred(x)} if isinstance(c, set) else c
        self.namespace['remove'] = lambda pred, c: type(c)(x for x in c if not pred(x)) if isinstance(c, (list, tuple)) else {x for x in c if not pred(x)} if isinstance(c, set) else c

        # Inert Forms (Capitalized) and value evaluation
        self.namespace['Int'] = sp.Integral
        self.namespace['Diff'] = sp.Derivative
        self.namespace['Limit'] = sp.Limit
        self.namespace['Sum'] = sp.Sum
        self.namespace['Product'] = sp.Product
        self.namespace['value'] = lambda e: e.doit() if hasattr(e, 'doit') else e

        # LinearAlgebra commands
        self.namespace['DotProduct'] = lambda u, v: (sp.Matrix(u) if not isinstance(u, sp.Matrix) else u).dot(sp.Matrix(v) if not isinstance(v, sp.Matrix) else v)
        self.namespace['CrossProduct'] = lambda u, v: (sp.Matrix(u) if not isinstance(u, sp.Matrix) else u).cross(sp.Matrix(v) if not isinstance(v, sp.Matrix) else v)
        self.namespace['Norm'] = lambda v, p=2: (sp.Matrix(v) if not isinstance(v, sp.Matrix) else v).norm(p)
        self.namespace['VectorAngle'] = lambda u, v: sp.acos((sp.Matrix(u) if not isinstance(u, sp.Matrix) else u).dot(sp.Matrix(v) if not isinstance(v, sp.Matrix) else v) / ((sp.Matrix(u) if not isinstance(u, sp.Matrix) else u).norm() * (sp.Matrix(v) if not isinstance(v, sp.Matrix) else v).norm()))
        self.namespace['Row'] = lambda m, i: (sp.Matrix(m) if not isinstance(m, sp.Matrix) else m).row(int(i)-1 if int(i)>0 else int(i))
        self.namespace['Column'] = lambda m, j: (sp.Matrix(m) if not isinstance(m, sp.Matrix) else m).col(int(j)-1 if int(j)>0 else int(j))
        self.namespace['MatrixAdd'] = lambda A, B: (sp.Matrix(A) if not isinstance(A, sp.Matrix) else A) + (sp.Matrix(B) if not isinstance(B, sp.Matrix) else B)
        self.namespace['MatrixMatrixMultiply'] = lambda A, B: (sp.Matrix(A) if not isinstance(A, sp.Matrix) else A) * (sp.Matrix(B) if not isinstance(B, sp.Matrix) else B)
        self.namespace['LUDecomposition'] = lambda A: (sp.Matrix(A) if not isinstance(A, sp.Matrix) else A).LUdecomposition()
        self.namespace['QRDecomposition'] = lambda A: (sp.Matrix(A) if not isinstance(A, sp.Matrix) else A).QRdecomposition()
        self.namespace['GaussianElimination'] = lambda A: (sp.Matrix(A) if not isinstance(A, sp.Matrix) else A).rref()[0]
        self.namespace['IdentityMatrix'] = lambda n: sp.eye(int(n))
        self.namespace['ZeroMatrix'] = lambda m, n=None: sp.zeros(int(m), int(n) if n is not None else int(m))
        self.namespace['DiagonalMatrix'] = lambda *args: sp.diag(*(args[0] if len(args)==1 and isinstance(args[0], (list, tuple)) else args))

        # Statistics commands
        self.namespace['Mean'] = lambda data: sum(data) / len(data)
        self.namespace['Median'] = lambda data: sorted(data)[len(data)//2]
        self.namespace['Variance'] = lambda data: sum((x - sum(data)/len(data))**2 for x in data) / (len(data) - 1 if len(data) > 1 else 1)
        self.namespace['StandardDeviation'] = lambda data: sp.sqrt(sum((x - sum(data)/len(data))**2 for x in data) / (len(data) - 1 if len(data) > 1 else 1))

        # Transforms
        self.namespace['laplace'] = lambda f, t=sp.Symbol('t'), s=sp.Symbol('s'): sp.laplace_transform(f, t, s, noconds=True)
        self.namespace['invlaplace'] = lambda F, s=sp.Symbol('s'), t=sp.Symbol('t'): sp.inverse_laplace_transform(F, s, t)
        self.namespace['fourier'] = lambda f, t=sp.Symbol('t'), w=sp.Symbol('w'): sp.fourier_transform(f, t, w)
        self.namespace['invfourier'] = lambda F, w=sp.Symbol('w'), t=sp.Symbol('t'): sp.inverse_fourier_transform(F, w, t)

        # Number Theory
        self.namespace['ifactor'] = lambda n: sp.factorint(n)
        self.namespace['igcd'] = lambda *args: sp.gcd(*args)
        self.namespace['ilcm'] = lambda *args: sp.lcm(*args)
        self.namespace['nextprime'] = lambda n: sp.nextprime(n)
        self.namespace['prevprime'] = lambda n: sp.prevprime(n)
        self.namespace['ithprime'] = lambda i: sp.prime(i)
        self.namespace['divisors'] = lambda n: sp.divisors(n)
        self.namespace['euler_phi'] = lambda n: sp.totient(n)
        self.namespace['modp'] = lambda a, b: sp.Mod(a, b)
        self.namespace['Mod'] = sp.Mod

        # Embedded Systems & Hardware Engineering Builtins
        from .embedded import EmbeddedMath
        embedded_funcs = [
            'to_bin', 'to_hex', 'twos_comp', 'twos_comp_repr', 'two_comp', 'two_comp_repr',
            'bit_get', 'bit_set', 'bit_clear', 'bit_toggle', 'bit_mask', 'bit_field',
            'to_q', 'from_q', 'ieee754',
            'ubrr_calc', 'baud_rate', 'timer_calc', 'timer_arr', 'pwm_duty',
            'adc_raw', 'adc_volt', 'adc_resolution',
            'voltage_divider', 'voltage_divider_r1', 'led_resistor', 'rc_cutoff',
            'crc8', 'crc16'
        ]
        for fn_name in embedded_funcs:
            if hasattr(EmbeddedMath, fn_name):
                fn_obj = getattr(EmbeddedMath, fn_name)
                self.namespace[fn_name] = fn_obj
                alias = self._make_subscript_alias(fn_name)
                if alias:
                    self.namespace[alias] = fn_obj

        # Aliases for convenience
        self.namespace['to_qformat'] = EmbeddedMath.to_q
        self.namespace['from_qformat'] = EmbeddedMath.from_q
        self.namespace['uart_baud_div'] = EmbeddedMath.ubrr_calc
        self.namespace['uart_baud'] = EmbeddedMath.baud_rate

        # SI Units & Suffix Constants for Embedded Calculations
        self.namespace['V'] = 1.0
        self.namespace['mV'] = 1e-3
        self.namespace['uV'] = 1e-6
        self.namespace['μV'] = 1e-6
        self.namespace['kV'] = 1_000.0
        self.namespace['MV'] = 1_000_000.0
        self.namespace['MegaVolt'] = 1_000_000.0
        self.namespace['megavolt'] = 1_000_000.0
        self.namespace['Hz'] = 1.0
        self.namespace['kHz'] = 1_000.0
        self.namespace['MHz'] = 1_000_000.0
        self.namespace['GHz'] = 1_000_000_000.0
        self.namespace['MegaHz'] = 1_000_000.0
        self.namespace['megahertz'] = 1_000_000.0
        self.namespace['s'] = 1.0
        self.namespace['ms'] = 1e-3
        self.namespace['us'] = 1e-6
        self.namespace['μs'] = 1e-6
        self.namespace['ns'] = 1e-9
        self.namespace['ps'] = 1e-12
        self.namespace['Ohm'] = 1.0
        self.namespace['kOhm'] = 1_000.0
        self.namespace['MOhm'] = 1_000_000.0
        self.namespace['MegaOhm'] = 1_000_000.0
        self.namespace['megaohm'] = 1_000_000.0
        self.namespace['megohm'] = 1_000_000.0
        self.namespace['GOhm'] = 1_000_000_000.0
        self.namespace['GΩ'] = 1_000_000_000.0
        self.namespace['Ω'] = 1.0
        self.namespace['kΩ'] = 1_000.0
        self.namespace['MΩ'] = 1_000_000.0
        self.namespace['F'] = 1.0
        self.namespace['mF'] = 1e-3
        self.namespace['uF'] = 1e-6
        self.namespace['μF'] = 1e-6
        self.namespace['nF'] = 1e-9
        self.namespace['pF'] = 1e-12
        self.namespace['A'] = 1.0
        self.namespace['kA'] = 1_000.0
        self.namespace['MA'] = 1_000_000.0
        self.namespace['MegaAmp'] = 1_000_000.0
        self.namespace['megaamp'] = 1_000_000.0
        self.namespace['mA'] = 1e-3
        self.namespace['uA'] = 1e-6
        self.namespace['μA'] = 1e-6
        self.namespace['W'] = 1.0
        self.namespace['mW'] = 1e-3
        self.namespace['uW'] = 1e-6
        self.namespace['μW'] = 1e-6
        self.namespace['kW'] = 1_000.0
        self.namespace['MW'] = 1_000_000.0
        self.namespace['MegaWatt'] = 1_000_000.0
        self.namespace['megawatt'] = 1_000_000.0

    def _cmd_plot(self, *args, **kwargs):
        """Handle inline plot(expr, (x, min, max)) calls."""
        if not args:
            raise ValueError("plot() requires at least one expression or function.")

        expr = args[0]
        var = None
        x_min = -10.0
        x_max = 10.0
        title = kwargs.get('title', '')

        # Check if second arg is a tuple (x, min, max)
        if len(args) > 1 and isinstance(args[1], (tuple, list)):
            range_info = args[1]
            if len(range_info) >= 3:
                var = range_info[0]
                x_min = float(sp.sympify(range_info[1]).evalf())
                x_max = float(sp.sympify(range_info[2]).evalf())
            elif len(range_info) == 2:
                x_min = float(sp.sympify(range_info[0]).evalf())
                x_max = float(sp.sympify(range_info[1]).evalf())

        # Check if parametric: plot([x(t), y(t)], (t, min, max))
        if isinstance(expr, (list, tuple)) and len(expr) == 2 and str(var) == 't':
            return PlotEngine.generate_parametric_plot(expr[0], expr[1], t_symbol=var, t_min=x_min, t_max=x_max, title=title)

        # Check if polar: plot(r(theta), (theta, min, max))
        if str(var) in ('theta', 'θ') or kwargs.get('coords') == 'polar':
            return PlotEngine.generate_polar_plot(expr, theta_symbol=var, theta_min=x_min, theta_max=x_max, title=title)

        return PlotEngine.generate_plot(expr, var=var, x_min=x_min, x_max=x_max, title=title)

    def _cmd_plot_parametric(self, expr_x, expr_y, range_tuple=None, title=''):
        t_var = sp.Symbol('t')
        t_min = -10.0
        t_max = 10.0
        if range_tuple and isinstance(range_tuple, (tuple, list)) and len(range_tuple) >= 3:
            t_var = range_tuple[0]
            t_min = float(sp.sympify(range_tuple[1]).evalf())
            t_max = float(sp.sympify(range_tuple[2]).evalf())
        return PlotEngine.generate_parametric_plot(expr_x, expr_y, t_symbol=t_var, t_min=t_min, t_max=t_max, title=title)

    def _cmd_plot_polar(self, expr_r, range_tuple=None, title=''):
        th_var = sp.Symbol('theta')
        th_min = 0.0
        th_max = 2 * np.pi
        if range_tuple and isinstance(range_tuple, (tuple, list)) and len(range_tuple) >= 3:
            th_var = range_tuple[0]
            th_min = float(sp.sympify(range_tuple[1]).evalf())
            th_max = float(sp.sympify(range_tuple[2]).evalf())
        return PlotEngine.generate_polar_plot(expr_r, theta_symbol=th_var, theta_min=th_min, theta_max=th_max, title=title)

    def _cmd_plot3d(self, *args, **kwargs):
        """Handle plot3d(f(x, y), x=a..b, y=c..d) calls."""
        if not args:
            raise ValueError("plot3d() requires an expression or function of two variables.")
        expr = args[0]
        x_range = args[1] if len(args) > 1 else None
        y_range = args[2] if len(args) > 2 else None
        title = kwargs.get('title', '')
        return PlotEngine.generate_3d_plot(expr, x_range=x_range, y_range=y_range, title=title)

    def _cmd_polygon_omraade(self, *args, **kwargs):
        """
        polygonOmråde(Uligheder, x = a..b, y = c..d)
        Generates linear inequality feasible polygon plot.
        """
        ineqs = args[0] if args else self.namespace.get('Uligheder', [])
        x_min, x_max = -1.0, 13.0
        y_min, y_max = -1.0, 12.0
        x_var, y_var = 'x', 'y'

        for arg in args[1:]:
            if isinstance(arg, (tuple, list)):
                if len(arg) >= 3:
                    v_name = str(arg[0])
                    v_min = float(sp.sympify(arg[1]).evalf())
                    v_max = float(sp.sympify(arg[2]).evalf())
                    if v_name == 'y':
                        y_var = v_name
                        y_min, y_max = v_min, v_max
                    else:
                        x_var = v_name
                        x_min, x_max = v_min, v_max
                elif len(arg) == 2:
                    x_min = float(sp.sympify(arg[0]).evalf())
                    x_max = float(sp.sympify(arg[1]).evalf())

        return PlotEngine.generate_polygon_area_plot(
            inequalities=ineqs,
            x_min=x_min, x_max=x_max,
            y_min=y_min, y_max=y_max,
            x_var=x_var, y_var=y_var
        )

    def _cmd_lp_plot(self, *args, **kwargs):
        """
        LPplot(f(x, y), Uligheder, N)
        Plots objective function level curves over the feasible polygon region.
        """
        if not args:
            raise ValueError("LPplot requires an objective function.")
        obj = args[0]
        ineqs = args[1] if len(args) > 1 else self.namespace.get('Uligheder', [])
        levels = args[2] if len(args) > 2 else [0, 120, 300]
        return PlotEngine.generate_polygon_area_plot(
            inequalities=ineqs,
            x_min=-1.0, x_max=13.0,
            y_min=-1.0, y_max=12.0,
            objective=obj,
            level_curves=levels
        )

    def reset(self):
        """Reset workspace and variables to default state."""
        self._init_builtins()
        self._initial_namespace = dict(self.namespace)
        self._builtin_keys = set(self.namespace.keys())
        self.history.clear()
        self.history_raw.clear()
        self.execution_count = 0

    def get_variables(self) -> dict:
        """Return user-defined symbols and functions."""
        user_vars = {}
        for k, v in self.namespace.items():
            if k.startswith('_') or k.startswith('Out_') or k == 'ans':
                continue
            if k not in self._builtin_keys:
                user_vars[k] = v
            elif k in self._initial_namespace and v != self._initial_namespace[k]:
                user_vars[k] = v
        return user_vars

    @staticmethod
    def split_statements(text: str) -> list[str]:
        statements = []
        current = []
        depth = 0
        for ch in text:
            if ch in '([{':
                depth += 1
                current.append(ch)
            elif ch in ')]}':
                depth = max(0, depth - 1)
                current.append(ch)
            elif ch in ('\n', ';') and depth == 0:
                stmt = "".join(current).strip()
                if stmt:
                    statements.append(stmt)
                current = []
            else:
                current.append(ch)
        if current:
            stmt = "".join(current).strip()
            if stmt:
                statements.append(stmt)
        return statements

    @staticmethod
    def _make_subscript_alias(var_name: str) -> str:
        _SUB_MAP = {
            '0': '₀', '1': '₁', '2': '₂', '3': '₃', '4': '₄',
            '5': '₅', '6': '₆', '7': '₇', '8': '₈', '9': '₉',
            'a': 'ₐ', 'b': 'ᵦ', 'e': 'ₑ', 'h': 'ₕ', 'i': 'ᵢ', 'j': 'ⱼ',
            'k': 'ₖ', 'l': 'ₗ', 'm': 'ₘ', 'n': 'ₙ', 'o': 'ₒ',
            'p': 'ₚ', 'r': 'ᵣ', 'u': 'ᵤ', 'v': 'ᵥ', 'x': 'ₓ',
            's': 'ₛ', 't': 'ₜ',
        }
        _REV_SUB_MAP = {v: k for k, v in _SUB_MAP.items()}
        if '_' in var_name:
            parts = var_name.split('_', 1)
            if all(c in _SUB_MAP for c in parts[1]):
                return parts[0] + ''.join(_SUB_MAP[c] for c in parts[1])
        elif any(c in _REV_SUB_MAP for c in var_name):
            rev_chars = "".join(_REV_SUB_MAP.keys())
            return re.sub(rf'(?<=[a-zA-Z_])([{re.escape(rev_chars)}]+)',
                          lambda m: '_' + ''.join(_REV_SUB_MAP.get(c, c) for c in m.group(1)), var_name)
        return ""

    def evaluate(self, input_str: str, precision: int = 6) -> CASResult:
        """
        Evaluate a mathematical expression or CAS command.
        Returns a CASResult object.
        """
        statements = self.split_statements(input_str)
        if len(statements) > 1:
            last_res = None
            for stmt in statements:
                last_res = self.evaluate(stmt, precision=precision)
            return last_res

        start_time = time.perf_counter()
        self.execution_count += 1
        exec_idx = self.execution_count

        # Parse the input
        parse_res: ParseResult = MathParser.parse(input_str, local_dict=self.namespace)

        if parse_res.is_command:
            if parse_res.command_name == 'reset':
                self.reset()
                elapsed = (time.perf_counter() - start_time) * 1000
                res = MathFormatter.format_all("Workspace reset successfully.", elapsed, precision)
                return res
            elif parse_res.command_name == 'whos':
                uv = self.get_variables()
                var_desc = ", ".join(f"{k} = {v}" for k, v in uv.items()) if uv else "No user variables defined."
                elapsed = (time.perf_counter() - start_time) * 1000
                res = MathFormatter.format_all(var_desc, elapsed, precision)
                return res
            elif parse_res.command_name == 'help':
                topic = parse_res.command_args[0] if parse_res.command_args else ""
                help_texts = {
                    "polygonOmråde": "polygonOmråde(Uligheder, x = a .. b, y = c .. d)\nPlots the feasible polygon region bounded by linear inequalities with boundary equation labels.",
                    "polygonOmraade": "polygonOmråde(Uligheder, x = a .. b, y = c .. d)\nPlots the feasible polygon region bounded by linear inequalities with boundary equation labels.",
                    "LPplot": "LPplot(f(x, y), Uligheder, N)\nPlots objective function level curves over a linear inequality feasible region.",
                    "to_bin": "to_bin(val, bits=8)\nFormat integer as fixed-width binary nibbles (e.g. 0b0101 1010).",
                    "to_hex": "to_hex(val, bits=8)\nFormat integer as hexadecimal string (e.g. 0x5A).",
                    "twos_comp": "twos_comp(val, bits=8)\nCalculate signed value from two's complement or vice versa.",
                    "two_comp": "two_comp(val, bits=8)\nCalculate signed value from two's complement or vice versa.",
                    "twos_comp_repr": "twos_comp_repr(val, bits=8)\nCalculate two's complement signed/unsigned breakdown.",
                    "two_comp_repr": "two_comp_repr(val, bits=8)\nCalculate two's complement signed/unsigned breakdown.",
                    "bit_set": "bit_set(val, bit)\nSet specific bit index to 1.",
                    "bit_clear": "bit_clear(val, bit)\nClear specific bit index to 0.",
                    "bit_toggle": "bit_toggle(val, bit)\nToggle specific bit index."
                }
                desc = help_texts.get(topic, f"? {topic}\nHelp: Function '{topic}' is available in the CAS engine.")
                elapsed = (time.perf_counter() - start_time) * 1000
                res = MathFormatter.format_all(desc, elapsed, precision)
                return res
            elif parse_res.command_name == 'with':
                pkg_name = parse_res.command_args[0] if parse_res.command_args else ""
                pkg_funcs = self.load_package(pkg_name)
                elapsed = (time.perf_counter() - start_time) * 1000
                res = MathFormatter.format_all(pkg_funcs, elapsed, precision, suppress_output=parse_res.suppress_output)
                self._update_history(exec_idx, pkg_funcs, res)
                return res
            elif parse_res.command_name == 'unassign':
                unassigned = []
                for name in parse_res.command_args:
                    self.namespace[name] = sp.Symbol(name)
                    unassigned.append(name)
                    alias = self._make_subscript_alias(name)
                    if alias and alias in self.namespace:
                        self.namespace[alias] = sp.Symbol(alias)
                msg = f"Unassigned: {', '.join(unassigned)}" if unassigned else "unassign: specify variable(s)"
                elapsed = (time.perf_counter() - start_time) * 1000
                res = MathFormatter.format_all(msg, elapsed, precision, suppress_output=parse_res.suppress_output)
                return res

        # Handle PlotData directly if result is a plot
        if isinstance(parse_res.sympy_expr, PlotData):
            elapsed = (time.perf_counter() - start_time) * 1000
            res = CASResult(
                raw_result=parse_res.sympy_expr,
                exact_latex=r"\text{Plot Generated}",
                numeric_latex=r"\text{Plot Generated}",
                exact_text="[Plot Object]",
                numeric_text="[Plot Object]",
                python_code=input_str,
                is_numeric_available=False,
                is_plot=True,
                plot_data={'plot_obj': parse_res.sympy_expr},
                result_type="Plot",
                execution_time_ms=elapsed
            )
            self._update_history(exec_idx, parse_res.sympy_expr, res)
            return res

        raw_val = parse_res.sympy_expr

        # Handle Variable/Function Assignment
        if parse_res.is_assignment and parse_res.assign_var:
            var_name = parse_res.assign_var
            if parse_res.assign_args:
                # Function definition: f(x) := expr -> define lambda/function
                args_syms = [sp.Symbol(a) if isinstance(a, str) else a for a in parse_res.assign_args]
                func_expr = raw_val
                # Create callable function in namespace
                def _user_func(*f_args, _expr=func_expr, _syms=args_syms):
                    subs_dict = {sym: arg for sym, arg in zip(_syms, f_args)}
                    return _expr.subs(subs_dict)

                self.namespace[var_name] = _user_func
                raw_val = sp.Eq(sp.Function(var_name)(*args_syms), func_expr)
            else:
                self.namespace[var_name] = raw_val
                sub_alias = self._make_subscript_alias(var_name)
                if sub_alias:
                    self.namespace[sub_alias] = raw_val

        # Update History
        elapsed = (time.perf_counter() - start_time) * 1000
        # Suppress SymPyDeprecationWarning that can fire during sp.latex/simplify when
        # the expression contains non-Expr arguments (Mul/Pow with Tuple) — a known
        # SymPy edge case with implicit_multiplication_application transformer.
        with warnings.catch_warnings():
            warnings.filterwarnings('ignore', category=SymPyDeprecationWarning)
            warnings.filterwarnings('ignore', message='.*non-Expr.*')
            formatted_res = MathFormatter.format_all(raw_val, elapsed, precision, suppress_output=parse_res.suppress_output)

        # Check if the command was solve(...) or fsolve(...) to format the solution clearly (e.g. x = 4)
        clean_in = input_str.strip()
        if (clean_in.startswith('solve(') or clean_in.startswith('fsolve(')) and not parse_res.is_assignment:
            var_name = None
            var_match = re.search(r',\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\)$', clean_in)
            if var_match:
                var_name = var_match.group(1)
            else:
                inner_match = re.match(r'^(?:solve|fsolve)\s*\((.*)\)$', clean_in, re.DOTALL)
                if inner_match:
                    inner_txt = inner_match.group(1).split(',')[0].strip()
                    sym_matches = re.findall(r'\b([a-zA-Z_][a-zA-Z0-9_]*)\b', inner_txt)
                    reserved = {'sin', 'cos', 'tan', 'exp', 'log', 'ln', 'sqrt', 'pi', 'I', 'E', 'abs', 'diff', 'int'}
                    cand_syms = [s for s in sym_matches if s not in reserved and not s.isdigit()]
                    if cand_syms:
                        var_name = cand_syms[0]

            if var_name:
                if isinstance(raw_val, list):
                    if len(raw_val) == 1:
                        val_str = str(raw_val[0])
                        val_ltx = sp.latex(raw_val[0]) if isinstance(raw_val[0], sp.Basic) else str(raw_val[0])
                        formatted_res.exact_text = f"{var_name} = {val_str}"
                        formatted_res.exact_latex = f"{var_name} = {val_ltx}"
                        formatted_res.numeric_text = f"{var_name} = {val_str}"
                        formatted_res.numeric_latex = f"{var_name} = {val_ltx}"
                    elif len(raw_val) > 1:
                        items_txt = [f"{var_name} = {v}" for v in raw_val]
                        items_ltx = [f"{var_name} = {sp.latex(v) if isinstance(v, sp.Basic) else str(v)}" for v in raw_val]
                        formatted_res.exact_text = ", ".join(items_txt)
                        formatted_res.exact_latex = r"\left\{ " + ",~ ".join(items_ltx) + r" \right\}"
                elif isinstance(raw_val, (int, float, sp.Number)):
                    formatted_res.exact_text = f"{var_name} = {raw_val}"
                    formatted_res.exact_latex = f"{var_name} = {sp.latex(raw_val) if isinstance(raw_val, sp.Basic) else str(raw_val)}"
                elif isinstance(raw_val, dict):
                    items_txt = [f"{k} = {v}" for k, v in raw_val.items()]
                    items_ltx = [f"{sp.latex(k) if isinstance(k, sp.Basic) else str(k)} = {sp.latex(v) if isinstance(v, sp.Basic) else str(v)}" for k, v in raw_val.items()]
                    formatted_res.exact_text = "{" + ", ".join(items_txt) + "}"
                    formatted_res.exact_latex = r"\left\{ " + ",~ ".join(items_ltx) + r" \right\}"

        self._update_history(exec_idx, raw_val, formatted_res)
        return formatted_res

    def _update_history(self, idx: int, raw_val, res: CASResult):
        """Update history variables: ans, _, _1, Out[1], and ditto operators %, %%, %%%."""
        self.history[idx] = res
        self.history_raw[idx] = raw_val
        # Update ditto / ans history
        self.namespace['_ans_3'] = self.namespace.get('_ans_2', raw_val)
        self.namespace['_ans_2'] = self.namespace.get('ans', raw_val)
        self.namespace['ans'] = raw_val
        self.namespace['_'] = raw_val
        self.namespace[f'_{idx}'] = raw_val
        self.namespace[f'Out_{idx}'] = raw_val
