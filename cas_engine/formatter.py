"""
Result formatter for CAS Engine.
Converts SymPy objects and calculations into:
- Standard typeset LaTeX (for Matplotlib mathtext / rendering)
- Evaluated numeric floats (with precision control)
- Pretty plain text
- Copyable Python / CAS expressions
"""

import re
import sympy as sp
import numpy as np


class CASResult:
    """Encapsulates the result of a CAS calculation."""
    def __init__(self, raw_result, exact_latex: str, numeric_latex: str,
                 exact_text: str, numeric_text: str, python_code: str,
                 is_numeric_available: bool = True, is_plot: bool = False,
                 plot_data: dict = None, result_type: str = "Symbolic",
                 execution_time_ms: float = 0.0, suppress_output: bool = False):
        self.raw_result = raw_result
        self.exact_latex = exact_latex
        self.numeric_latex = numeric_latex
        self.exact_text = exact_text
        self.numeric_text = numeric_text
        self.python_code = python_code
        self.is_numeric_available = is_numeric_available
        self.is_plot = is_plot
        self.plot_data = plot_data or {}
        self.result_type = result_type
        self.execution_time_ms = execution_time_ms
        self.suppress_output = suppress_output


class MathFormatter:
    """
    Handles formatting of SymPy expressions into LaTeX, text, and numeric representations.
    Supports customizable decimal separator (comma ',' by default per user request, or period '.').
    """

    decimal_separator: str = ','

    @classmethod
    def set_decimal_separator(cls, sep: str):
        """Set the active decimal separator (',' or '.')."""
        if sep in (',', '.'):
            cls.decimal_separator = sep

    @classmethod
    def format_decimal(cls, text: str, sep: str = None) -> str:
        """Replace decimal points in plain text with the active decimal separator."""
        if sep is None:
            sep = cls.decimal_separator
        if sep == ',':
            return re.sub(r'(?<=\d)\.(?=\d)', ',', text)
        elif sep == '.':
            return re.sub(r'(?<=\d),(?=\d)', '.', text)
        return text

    @classmethod
    def format_latex_decimal(cls, latex_str: str, sep: str = None) -> str:
        """
        Format decimal numbers in LaTeX.
        In LaTeX math mode, a decimal comma must be written as {,} to avoid unwanted punctuation spacing.
        """
        if sep is None:
            sep = cls.decimal_separator
        if sep == ',':
            return re.sub(r'(?<=\d)\.(?=\d)', '{,}', latex_str)
        elif sep == '.':
            # Remove LaTeX decimal comma grouping if switching back to period
            return re.sub(r'(?<=\d)\{,\}(?=\d)', '.', latex_str)
        return latex_str

    @classmethod
    def clean_latex_for_mathtext(cls, latex_str: str) -> str:
        r"""
        Adjust SymPy LaTeX output to be 100% compatible with Matplotlib mathtext engine.
        For instance, convert \begin{bmatrix} -> \left[\begin{matrix}...\end{matrix}\right],
        remove unsupported \displaystyle, and ensure spacing/font commands are mathtext safe.
        """
        s = latex_str.strip()
        # Remove \displaystyle which is not supported in mathtext
        s = s.replace(r'\displaystyle', '')
        # Mathtext supports \begin{matrix} with \left[ and \right]
        s = s.replace(r'\begin{bmatrix}', r'\left[\begin{matrix}')
        s = s.replace(r'\end{bmatrix}', r'\end{matrix}\right]')
        s = s.replace(r'\begin{pmatrix}', r'\left(\begin{matrix}')
        s = s.replace(r'\end{pmatrix}', r'\end{matrix}\right)')
        s = s.replace(r'\begin{vmatrix}', r'\left|\begin{matrix}')
        s = s.replace(r'\end{vmatrix}', r'\end{matrix}\right|')
        s = s.replace(r'\operatorname{', r'\mathrm{')
        s = s.replace(r'\text{', r'\mathrm{')
        # Convert custom set and logic functions in LaTeX
        s = re.sub(r'\\(?:mathrm|operatorname)\{Intersection\}\s*\{?\s*(?:\\left\(|\()\s*(.*?)\s*,\s*(.*?)\s*(?:\\right\)|\))\s*\}?', lambda m: f'{m.group(1)} \\cap {m.group(2)}', s)
        s = re.sub(r'\\(?:mathrm|operatorname)\{Union\}\s*\{?\s*(?:\\left\(|\()\s*(.*?)\s*,\s*(.*?)\s*(?:\\right\)|\))\s*\}?', lambda m: f'{m.group(1)} \\cup {m.group(2)}', s)
        s = re.sub(r'\\(?:mathrm|operatorname)\{Subset\}\s*\{?\s*(?:\\left\(|\()\s*(.*?)\s*,\s*(.*?)\s*(?:\\right\)|\))\s*\}?', lambda m: f'{m.group(1)} \\subset {m.group(2)}', s)
        s = re.sub(r'\\(?:mathrm|operatorname)\{Superset\}\s*\{?\s*(?:\\left\(|\()\s*(.*?)\s*,\s*(.*?)\s*(?:\\right\)|\))\s*\}?', lambda m: f'{m.group(1)} \\supset {m.group(2)}', s)
        s = re.sub(r'\\(?:mathrm|operatorname)\{Contains\}\s*\{?\s*(?:\\left\(|\()\s*(.*?)\s*,\s*(.*?)\s*(?:\\right\)|\))\s*\}?', lambda m: f'{m.group(1)} \\in {m.group(2)}', s)
        s = re.sub(r'\\(?:mathrm|operatorname)\{Exists\}\s*\{?\s*(?:\\left\(|\()\s*(.*?)\s*,\s*(.*?)\s*(?:\\right\)|\))\s*\}?', lambda m: f'\\exists {m.group(1)} : {m.group(2)}', s)
        s = re.sub(r'\\(?:mathrm|operatorname)\{ForAll\}\s*\{?\s*(?:\\left\(|\()\s*(.*?)\s*,\s*(.*?)\s*(?:\\right\)|\))\s*\}?', lambda m: f'\\forall {m.group(1)} : {m.group(2)}', s)
        return s.strip()

    @classmethod
    def to_latex(cls, expr) -> str:
        """Generate formatted LaTeX string from SymPy expression or Python structure."""
        if expr is None:
            return ""
        try:
            if isinstance(expr, (list, tuple)):
                items = [sp.latex(item) if hasattr(item, 'is_symbol') or isinstance(item, (sp.Basic, sp.MatrixBase, sp.Eq)) else str(item) for item in expr]
                raw_latex = r"\left[ " + ",~ ".join(items) + r" \right]"
                res = cls.clean_latex_for_mathtext(raw_latex)
            elif isinstance(expr, dict):
                res = cls.format_dict(expr, is_latex=True)
            elif isinstance(expr, set):
                items = [cls.to_latex(item) for item in expr]
                raw_latex = r"\left\{ " + ",~ ".join(items) + r" \right\}"
                res = cls.clean_latex_for_mathtext(raw_latex)
            elif hasattr(expr, '_repr_latex_'):
                raw_latex = expr._repr_latex_().strip('$')
                res = cls.clean_latex_for_mathtext(raw_latex)
            elif isinstance(expr, (sp.Basic, sp.MatrixBase, sp.Eq)):
                raw_latex = sp.latex(expr)
                res = cls.clean_latex_for_mathtext(raw_latex)
            elif isinstance(expr, (int, float, complex, np.number)):
                res = str(expr)
            elif isinstance(expr, str):
                if re.match(r'^0b[01\s]+$', expr):
                    res = expr.replace(' ', r'\ ')
                elif re.match(r'^0x[0-9a-fA-F\s]+$', expr):
                    res = expr.replace(' ', r'\ ')
                else:
                    try:
                        res = sp.latex(sp.sympify(expr))
                    except Exception:
                        res = str(expr)
            else:
                res = sp.latex(sp.sympify(expr))
        except Exception:
            res = str(expr)
        return cls.format_latex_decimal(res)

    @classmethod
    def to_numeric(cls, expr, precision: int = 6):
        """
        Evaluate expression numerically (to float / complex float / numeric matrix).
        """
        if expr is None:
            return None
        try:
            if isinstance(expr, (int, float, complex, np.number)):
                if isinstance(expr, float):
                    return round(expr, precision)
                return expr
            elif isinstance(expr, sp.MatrixBase):
                return expr.evalf(precision)
            elif isinstance(expr, (list, tuple)):
                return [cls.to_numeric(x, precision) for x in expr]
            elif isinstance(expr, dict):
                return {cls.to_numeric(k, precision): cls.to_numeric(v, precision) for k, v in expr.items()}
            elif isinstance(expr, sp.Eq):
                return sp.Eq(cls.to_numeric(expr.lhs, precision), cls.to_numeric(expr.rhs, precision))
            elif isinstance(expr, (sp.Basic, sp.Expr)):
                evaluated = expr.evalf(precision)
                return evaluated
            else:
                sym_expr = sp.sympify(expr)
                return sym_expr.evalf(precision)
        except Exception:
            return expr

    @classmethod
    def to_numeric_str(cls, expr, precision: int = 6) -> str:
        """Generate numeric string for display."""
        num_val = cls.to_numeric(expr, precision)
        if num_val is None:
            return ""
        if isinstance(num_val, sp.MatrixBase):
            s = str(num_val)
        else:
            s = str(num_val)
        return cls.format_decimal(s)

    @classmethod
    def get_result_type(cls, expr) -> str:
        """Determine human-readable result type."""
        if expr is None:
            return "None"
        if isinstance(expr, sp.MatrixBase):
            return f"Matrix ({expr.rows}×{expr.cols})"
        if isinstance(expr, sp.Eq):
            return "Equation"
        if isinstance(expr, dict):
            return "Embedded Record" if any('hex' in str(k) or 'baud' in str(k) or 'timer' in str(k) or 'adc' in str(k) or 'q_' in str(k) or 'ieee' in str(k) or 'cutoff' in str(k) or 'crc' in str(k) or 'comp' in str(k) for k in expr.keys()) else f"Record ({len(expr)} fields)"
        if isinstance(expr, (list, tuple, set)):
            return f"List / Set ({len(expr)} items)"
        if isinstance(expr, (int, float, sp.Integer, sp.Float, sp.Rational)):
            return "Number"
        if isinstance(expr, sp.Derivative):
            return "Derivative"
        if isinstance(expr, sp.Integral):
            return "Integral"
        from sympy.core.relational import Relational
        if isinstance(expr, Relational):
            return "Inequality"
        if isinstance(expr, sp.Symbol):
            return "Symbol"
        if isinstance(expr, sp.Expr):
            return "Expression"
        return type(expr).__name__

    @classmethod
    def format_dict(cls, d: dict, is_latex: bool = False, precision: int = 4) -> str:
        """Format dictionary / embedded record cleanly with engineering units and rounded numbers."""
        if not d:
            return r"\left[ \right]" if is_latex else "[]"

        sep = cls.decimal_separator

        # 1. Specialized cleaner for rc_cutoff
        if "cutoff_frequency_hz" in d and ("time_constant_tau_ms" in d or "time_constant_tau_sec" in d):
            fc = float(d.get("cutoff_frequency_hz", 0.0))
            tau_sec = float(d.get("time_constant_tau_sec", 0.0))
            if tau_sec == 0.0 and "time_constant_tau_ms" in d:
                tau_sec = float(d.get("time_constant_tau_ms", 0.0)) / 1000.0

            # Auto SI units for fc
            if fc >= 1e9:
                fc_val, fc_unit = f"{fc/1e9:.3g}", "GHz"
            elif fc >= 1e6:
                fc_val, fc_unit = f"{fc/1e6:.3g}", "MHz"
            elif fc >= 1e3:
                fc_val, fc_unit = f"{fc/1e3:.3g}", "kHz"
            else:
                fc_val, fc_unit = f"{fc:.2f}".rstrip("0").rstrip("."), "Hz"

            # Auto SI units for tau
            if tau_sec >= 1.0:
                tau_val, tau_unit = f"{tau_sec:.3g}", "s"
            elif tau_sec >= 1e-3:
                tau_val, tau_unit = f"{tau_sec*1e3:.3g}", "ms"
            elif tau_sec >= 1e-6:
                tau_val, tau_unit = f"{tau_sec*1e6:.3g}", "µs"
            else:
                tau_val, tau_unit = f"{tau_sec*1e9:.3g}", "ns"

            # Settle time (5*tau)
            settle_sec = tau_sec * 5.0
            if settle_sec >= 1.0:
                set_val, set_unit = f"{settle_sec:.3g}", "s"
            elif settle_sec >= 1e-3:
                set_val, set_unit = f"{settle_sec*1e3:.3g}", "ms"
            elif settle_sec >= 1e-6:
                set_val, set_unit = f"{settle_sec*1e6:.3g}", "µs"
            else:
                set_val, set_unit = f"{settle_sec*1e9:.3g}", "ns"

            fc_val = cls.format_decimal(fc_val, sep)
            tau_val = cls.format_decimal(tau_val, sep)
            set_val = cls.format_decimal(set_val, sep)

            if is_latex:
                return (
                    rf"\left[\begin{{matrix}} "
                    rf"\mathbf{{Cutoff~Frequency}}: & {fc_val}~\mathrm{{{fc_unit}}} \\ "
                    rf"\mathbf{{Time~Constant~(\tau)}}: & {tau_val}~\mathrm{{{tau_unit}}} \\ "
                    rf"\mathbf{{Settle~Time~(99\%)}}: & {set_val}~\mathrm{{{set_unit}}} "
                    rf"\end{{matrix}}\right]"
                )
            else:
                return f"[Cutoff = {fc_val} {fc_unit}, Tau (τ) = {tau_val} {tau_unit}, Settle (99%) = {set_val} {set_unit}]"

        # 2. General dictionary formatting
        UNIT_SUFFIXES = {
            "_hz": "Hz", "_khz": "kHz", "_mhz": "MHz", "_ghz": "GHz",
            "_sec": "s", "_s": "s", "_ms": "ms", "_us": "µs", "_ns": "ns",
            "_ohms": "Ω", "_ohm": "Ω", "_kohms": "kΩ", "_kohm": "kΩ", "_mohms": "MΩ", "_mohm": "MΩ",
            "_v": "V", "_mv": "mV", "_kv": "kV",
            "_a": "A", "_ma": "mA", "_ua": "µA",
            "_w": "W", "_mw": "mW",
            "_pct": "%", "_percent": "%",
            "_db": "dB",
            "_bytes": "bytes", "_bits": "bits"
        }

        entries = []
        latex_rows = []
        for k, v in d.items():
            k_str = str(k)
            unit = ""
            for sfx, u in UNIT_SUFFIXES.items():
                if k_str.lower().endswith(sfx):
                    unit = u
                    k_str = k_str[:-len(sfx)]
                    break

            clean_k = k_str.replace("_", " ").strip().title()
            if not clean_k:
                clean_k = str(k)

            if isinstance(v, float):
                if abs(v - round(v)) < 1e-9:
                    v_str = str(int(round(v)))
                elif abs(v) >= 1e4 or (abs(v) < 1e-3 and abs(v) > 0):
                    v_str = f"{v:.4g}"
                else:
                    v_str = f"{v:.4f}".rstrip("0").rstrip(".")
                v_str = cls.format_decimal(v_str, sep)
                val_disp = f"{v_str} {unit}".strip() if unit else v_str
            elif isinstance(v, int):
                val_disp = f"{v} {unit}".strip() if unit else str(v)
            else:
                val_disp = str(v)

            entries.append(f"{clean_k} = {val_disp}")
            if is_latex:
                k_latex = clean_k.replace(" ", "~")
                val_latex = cls.format_latex_decimal(val_disp, sep)
                latex_rows.append(rf"\mathbf{{{k_latex}}}: & \mathrm{{{val_latex}}}")

        if is_latex:
            return r"\left[\begin{matrix} " + r" \\ ".join(latex_rows) + r" \end{matrix}\right]"
        else:
            return "[" + ",  ".join(entries) + "]"

    @classmethod
    def format_all(cls, raw_result, execution_time_ms: float = 0.0, precision: int = 6, suppress_output: bool = False) -> CASResult:
        """
        Produce a full CASResult bundle containing exact and numeric LaTeX/text representations.
        """
        if isinstance(raw_result, dict):
            exact_latex = cls.format_dict(raw_result, is_latex=True, precision=precision)
            exact_text = cls.format_dict(raw_result, is_latex=False, precision=precision)
            numeric_latex = exact_latex
            numeric_text = exact_text
            is_numeric_available = True
        else:
            # Exact LaTeX & Text
            exact_latex = cls.format_latex_decimal(cls.to_latex(raw_result))
            exact_text = sp.pretty(raw_result) if isinstance(raw_result, (sp.Basic, sp.MatrixBase)) else str(raw_result)
            exact_text = re.sub(r'\bIntersection\((.*?), (.*?)\)', r'\1 ∩ \2', exact_text)
            exact_text = re.sub(r'\bUnion\((.*?), (.*?)\)', r'\1 ∪ \2', exact_text)
            exact_text = re.sub(r'\bSubset\((.*?), (.*?)\)', r'\1 ⊂ \2', exact_text)
            exact_text = re.sub(r'\bSuperset\((.*?), (.*?)\)', r'\1 ⊃ \2', exact_text)
            exact_text = re.sub(r'\bContains\((.*?), (.*?)\)', r'\1 ∈ \2', exact_text)
            exact_text = cls.format_decimal(exact_text)

            # Numeric Evaluation
            try:
                numeric_obj = cls.to_numeric(raw_result, precision)
                numeric_latex = cls.format_latex_decimal(cls.to_latex(numeric_obj))
                numeric_text = sp.pretty(numeric_obj) if isinstance(numeric_obj, (sp.Basic, sp.MatrixBase)) else str(numeric_obj)
                numeric_text = cls.format_decimal(numeric_text)
                is_numeric_available = True
            except Exception:
                numeric_latex = exact_latex
                numeric_text = exact_text
                is_numeric_available = False

        # Python Code
        try:
            if isinstance(raw_result, (sp.Basic, sp.MatrixBase)):
                python_code = str(raw_result)
            else:
                python_code = repr(raw_result)
        except Exception:
            python_code = str(raw_result)

        result_type = cls.get_result_type(raw_result)

        return CASResult(
            raw_result=raw_result,
            exact_latex=exact_latex,
            numeric_latex=numeric_latex,
            exact_text=exact_text,
            numeric_text=numeric_text,
            python_code=python_code,
            is_numeric_available=is_numeric_available,
            is_plot=False,
            result_type=result_type,
            execution_time_ms=execution_time_ms,
            suppress_output=suppress_output
        )
