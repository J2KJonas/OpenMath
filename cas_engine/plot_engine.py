"""
Plotting computation engine for 2D mathematical function rendering.
Generates numeric arrays via SymPy lambdify and NumPy.
Supports standard y=f(x), multi-curve, parametric, polar, and implicit plots.
"""

import numpy as np
import sympy as sp


class CurveData:
    """Data for a single plotted curve."""
    def __init__(self, x_vals, y_vals, label: str = "", style: str = "-", color: str = None):
        self.x_vals = x_vals
        self.y_vals = y_vals
        self.label = label
        self.style = style
        self.color = color


class RegionData:
    """Data for a filled 2D polygon region or inequality area."""
    def __init__(self, x_vals, y_min_vals, y_max_vals, color: str = "#385a8a", alpha: float = 0.9, label: str = ""):
        self.x_vals = x_vals
        self.y_min_vals = y_min_vals
        self.y_max_vals = y_max_vals
        self.color = color
        self.alpha = alpha
        self.label = label


class PlotData:
    """Encapsulates all curves and visual configuration for a plot."""
    def __init__(self, curves: list, title: str = "", x_label: str = "x", y_label: str = "y",
                 x_lim=None, y_lim=None, is_polar: bool = False, is_implicit: bool = False,
                 grid: bool = True, legend: bool = True, regions: list = None,
                 is_3d: bool = False, x_grid=None, y_grid=None, z_grid=None,
                 aspect_equal: bool = False):
        self.curves = curves
        self.title = title
        self.x_label = x_label
        self.y_label = y_label
        self.x_lim = x_lim
        self.y_lim = y_lim
        self.is_polar = is_polar
        self.is_implicit = is_implicit
        self.grid = grid
        self.legend = legend
        self.regions = regions or []
        self.is_3d = is_3d
        self.x_grid = x_grid
        self.y_grid = y_grid
        self.z_grid = z_grid
        self.aspect_equal = aspect_equal


class PlotEngine:
    """Computes numerical coordinates for functions and expressions."""

    @classmethod
    def clean_discontinuities(cls, y_arr, max_diff=100.0, max_val=1e5):
        """
        Detect and mask vertical asymptote lines (e.g. tan(x), 1/x).
        """
        y_clean = np.copy(y_arr)
        # Mask huge values
        y_clean[np.abs(y_clean) > max_val] = np.nan
        # Mask rapid jumps between consecutive points
        diffs = np.abs(np.diff(y_clean, prepend=y_clean[0]))
        y_clean[diffs > max_diff] = np.nan
        return y_clean

    @classmethod
    def evaluate_1d_function(cls, expr, var_symbol=None, x_min=-10.0, x_max=10.0, num_points=1000):
        """
        Evaluate y = f(x) over [x_min, x_max].
        """
        if isinstance(expr, str):
            expr = sp.sympify(expr)

        symbols = list(expr.free_symbols)
        if var_symbol is None:
            if symbols:
                var_symbol = symbols[0]
            else:
                var_symbol = sp.Symbol('x')
        elif isinstance(var_symbol, str):
            var_symbol = sp.Symbol(var_symbol)

        x_vals = np.linspace(float(x_min), float(x_max), num_points)

        try:
            # Try numpy lambdify
            f_num = sp.lambdify(var_symbol, expr, modules=['numpy', 'scipy', {'sin': np.sin, 'cos': np.cos}])
            y_vals = f_num(x_vals)
            # If constant function
            if np.isscalar(y_vals) or y_vals.shape == ():
                y_vals = np.full_like(x_vals, float(y_vals))
            else:
                y_vals = np.asarray(y_vals, dtype=float)
        except Exception:
            # Fallback: point by point with SymPy evalf
            y_vals = []
            for x in x_vals:
                try:
                    val = float(expr.subs(var_symbol, x).evalf())
                except Exception:
                    val = np.nan
                y_vals.append(val)
            y_vals = np.array(y_vals, dtype=float)

        y_vals = cls.clean_discontinuities(y_vals)
        return x_vals, y_vals

    @classmethod
    def generate_plot(cls, exprs, var=None, x_min=-10.0, x_max=10.0, num_points=1000, title="", labels=None):
        """
        Generate PlotData for one or more expressions.
        exprs: single SymPy expr or list of exprs
        """
        if not isinstance(exprs, (list, tuple)):
            expr_list = [exprs]
        else:
            expr_list = exprs

        curves = []
        for i, exp in enumerate(expr_list):
            lbl = labels[i] if labels and i < len(labels) else f"$f_{{{i+1}}}(x) = {sp.latex(exp)}$"
            x_vals, y_vals = cls.evaluate_1d_function(exp, var_symbol=var, x_min=x_min, x_max=x_max, num_points=num_points)
            curves.append(CurveData(x_vals, y_vals, label=lbl))

        var_name = str(var) if var else "x"
        return PlotData(
            curves=curves,
            title=title or "",
            x_label=var_name,
            y_label=f"f({var_name})",
            x_lim=(x_min, x_max),
            grid=True,
            legend=len(curves) > 1 or bool(labels)
        )

    @classmethod
    def generate_parametric_plot(cls, expr_x, expr_y, t_symbol=None, t_min=-10.0, t_max=10.0, num_points=1000, title=""):
        """
        Generate PlotData for parametric curve (x(t), y(t)).
        """
        if t_symbol is None:
            t_symbol = sp.Symbol('t')
        elif isinstance(t_symbol, str):
            t_symbol = sp.Symbol(t_symbol)

        t_vals = np.linspace(float(t_min), float(t_max), num_points)
        fx = sp.lambdify(t_symbol, expr_x, modules=['numpy', 'math'])
        fy = sp.lambdify(t_symbol, expr_y, modules=['numpy', 'math'])

        try:
            x_vals = np.asarray(fx(t_vals), dtype=float)
            y_vals = np.asarray(fy(t_vals), dtype=float)
            if x_vals.shape == ():
                x_vals = np.full_like(t_vals, float(x_vals))
            if y_vals.shape == ():
                y_vals = np.full_like(t_vals, float(y_vals))
        except Exception:
            x_vals = [float(expr_x.subs(t_symbol, t).evalf()) for t in t_vals]
            y_vals = [float(expr_y.subs(t_symbol, t).evalf()) for t in t_vals]
            x_vals = np.array(x_vals)
            y_vals = np.array(y_vals)

        curves = [CurveData(x_vals, y_vals, label=f"$({sp.latex(expr_x)}, {sp.latex(expr_y)})$")]
        return PlotData(
            curves=curves,
            title=title or "",
            x_label=f"x({t_symbol})",
            y_label=f"y({t_symbol})",
            grid=True,
            legend=True,
            aspect_equal=True
        )

    @classmethod
    def generate_polar_plot(cls, expr_r, theta_symbol=None, theta_min=0.0, theta_max=2*np.pi, num_points=1000, title=""):
        """
        Generate PlotData for polar curve r(theta).
        """
        if theta_symbol is None:
            theta_symbol = sp.Symbol('theta')
        elif isinstance(theta_symbol, str):
            theta_symbol = sp.Symbol(theta_symbol)

        theta_vals = np.linspace(float(theta_min), float(theta_max), num_points)
        fr = sp.lambdify(theta_symbol, expr_r, modules=['numpy', 'math'])
        try:
            r_vals = np.asarray(fr(theta_vals), dtype=float)
            if r_vals.shape == ():
                r_vals = np.full_like(theta_vals, float(r_vals))
        except Exception:
            r_vals = np.array([float(expr_r.subs(theta_symbol, th).evalf()) for th in theta_vals])

        # Convert to cartesian for 2D plotter
        x_vals = r_vals * np.cos(theta_vals)
        y_vals = r_vals * np.sin(theta_vals)

        curves = [CurveData(x_vals, y_vals, label=f"$r({sp.latex(theta_symbol)}) = {sp.latex(expr_r)}$")]
        return PlotData(
            curves=curves,
            title=title or "",
            x_label="x = r cos(θ)",
            y_label="y = r sin(θ)",
            grid=True,
            legend=True,
            is_polar=True,
            aspect_equal=True
        )

    @classmethod
    def generate_polygon_area_plot(cls, inequalities, x_min=-1.0, x_max=13.0, y_min=-1.0, y_max=12.0,
                                   title="", x_var='x', y_var='y', objective=None, level_curves=None):
        """
        Generate PlotData for polygonOmråde / LPplot linear programming feasible polygon regions.
        Shades the feasible region satisfying inequalities and plots boundary lines with labels.
        """
        x_sym = sp.Symbol(str(x_var))
        y_sym = sp.Symbol(str(y_var))

        if not isinstance(inequalities, (list, tuple)):
            inequalities = [inequalities]

        # Standard palette colors: red-brown, blue, olive green, etc.
        line_colors = ["#8B2500", "#1E3F8B", "#6B8E23", "#9932CC", "#FF8C00", "#008B8B"]
        curves = []
        parsed_ineqs = []

        num_points = 500
        x_vals = np.linspace(float(x_min), float(x_max), num_points)

        for i, ineq in enumerate(inequalities):
            # Parse equation/inequality: e.g. 10 = 5*x + y or 5*x + y >= 10
            lbl = str(ineq)
            color = line_colors[i % len(line_colors)]
            try:
                # Solve for y in terms of x
                if hasattr(ineq, 'lhs') and hasattr(ineq, 'rhs'):
                    eq_expr = sp.Eq(ineq.lhs, ineq.rhs)
                    # Pretty label like "10 = 5x + y"
                    lbl = f"${sp.latex(ineq.lhs)} = {sp.latex(ineq.rhs)}$"
                else:
                    eq_expr = sp.Eq(sp.sympify(ineq), 0)
                    lbl = f"${sp.latex(ineq)} = 0$"

                sol = sp.solve(eq_expr, y_sym)
                if sol:
                    y_expr = sol[0]
                    f_num = sp.lambdify(x_sym, y_expr, modules=['numpy', 'math'])
                    y_vals = np.asarray(f_num(x_vals), dtype=float)
                    if y_vals.shape == ():
                        y_vals = np.full_like(x_vals, float(y_vals))
                    curves.append(CurveData(x_vals, y_vals, label=lbl, color=color))
                    parsed_ineqs.append(y_expr)
                else:
                    # Vertical line x = c
                    sol_x = sp.solve(eq_expr, x_sym)
                    if sol_x:
                        c_val = float(sol_x[0].evalf())
                        curves.append(CurveData(np.full(num_points, c_val), np.linspace(y_min, y_max, num_points),
                                                label=lbl, color=color))
            except Exception:
                continue

        # Plot objective function level curves if LPplot
        if objective is not None and level_curves is not None:
            if not isinstance(level_curves, (list, tuple)):
                level_curves = [level_curves]
            for val in level_curves:
                try:
                    obj_eq = sp.Eq(objective, val)
                    sol = sp.solve(obj_eq, y_sym)
                    if sol:
                        y_expr = sol[0]
                        f_num = sp.lambdify(x_sym, y_expr, modules=['numpy', 'math'])
                        y_vals = np.asarray(f_num(x_vals), dtype=float)
                        if y_vals.shape == ():
                            y_vals = np.full_like(x_vals, float(y_vals))
                        curves.append(CurveData(x_vals, y_vals, label=f"N = {val}", style="--", color="#e11d48"))
                except Exception:
                    pass

        # Compute feasible region envelope (y >= max(lines))
        regions = []
        if parsed_ineqs:
            try:
                # Compute upper envelope for region above boundary lines
                y_stack = []
                for y_expr in parsed_ineqs:
                    f_num = sp.lambdify(x_sym, y_expr, modules=['numpy', 'math'])
                    yv = np.asarray(f_num(x_vals), dtype=float)
                    if yv.shape == ():
                        yv = np.full_like(x_vals, float(yv))
                    y_stack.append(yv)

                y_stack = np.array(y_stack)
                y_lower_envelope = np.maximum.reduce(y_stack)
                y_upper_bound = np.full_like(x_vals, float(y_max))
                # Clip lower to y_min
                y_lower_envelope = np.clip(y_lower_envelope, float(y_min), float(y_max))
                regions.append(RegionData(x_vals, y_lower_envelope, y_upper_bound, color="#385a8a", alpha=0.9, label="polygonOmråde"))
            except Exception:
                pass

        return PlotData(
            curves=curves,
            title=title,
            x_label=str(x_var),
            y_label=str(y_var),
            x_lim=(float(x_min), float(x_max)),
            y_lim=(float(y_min), float(y_max)),
            grid=True,
            legend=True,
            regions=regions
        )

    @classmethod
    def generate_3d_plot(cls, expr, x_range=None, y_range=None, title=""):
        """Generate 3D surface plot data for plot3d(f(x, y), x=a..b, y=c..d)."""
        x_sym = sp.Symbol('x')
        y_sym = sp.Symbol('y')
        x_min, x_max = -5.0, 5.0
        y_min, y_max = -5.0, 5.0

        if x_range and isinstance(x_range, (tuple, list)) and len(x_range) >= 3:
            x_sym = x_range[0]
            x_min = float(sp.sympify(x_range[1]).evalf())
            x_max = float(sp.sympify(x_range[2]).evalf())
        elif x_range and isinstance(x_range, (tuple, list)) and len(x_range) == 2:
            x_min = float(sp.sympify(x_range[0]).evalf())
            x_max = float(sp.sympify(x_range[1]).evalf())

        if y_range and isinstance(y_range, (tuple, list)) and len(y_range) >= 3:
            y_sym = y_range[0]
            y_min = float(sp.sympify(y_range[1]).evalf())
            y_max = float(sp.sympify(y_range[2]).evalf())
        elif y_range and isinstance(y_range, (tuple, list)) and len(y_range) == 2:
            y_min = float(sp.sympify(y_range[0]).evalf())
            y_max = float(sp.sympify(y_range[1]).evalf())

        X = np.linspace(x_min, x_max, 40)
        Y = np.linspace(y_min, y_max, 40)
        X_grid, Y_grid = np.meshgrid(X, Y)
        f_num = sp.lambdify((x_sym, y_sym), expr, modules=['numpy', 'math'])
        try:
            Z_grid = np.asarray(f_num(X_grid, Y_grid), dtype=float)
            if Z_grid.shape == ():
                Z_grid = np.full_like(X_grid, float(Z_grid))
        except Exception:
            Z_grid = np.zeros_like(X_grid)

        return PlotData(
            curves=[],
            title=title or f"z = {expr}",
            x_label=str(x_sym),
            y_label=str(y_sym),
            is_3d=True,
            x_grid=X_grid,
            y_grid=Y_grid,
            z_grid=Z_grid
        )
