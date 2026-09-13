"""
High-quality mathematical LaTeX rendering widget using Matplotlib's MathText engine.
Produces crisp, retina-ready QPixmaps with theme awareness and caching.
"""

import io
from functools import lru_cache
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QScrollArea, QSizePolicy
from PyQt6.QtGui import QPixmap, QImage, QPainter, QColor, QFont
from PyQt6.QtCore import Qt, QSize, pyqtSignal

from .theme import Theme


_PIXMAP_CACHE = {}


def expr_to_preview_latex(text: str) -> str:
    """
    Convert raw user input or template string into a crisp LaTeX string for live 2D Math preview.
    Handles placeholders ⟦var⟧, calculus commands (diff, integrate, limit, Sum, Product),
    assignments (:=), functions, equations, fractions, and general mathematical notation.
    """
    import re
    import sympy as sp
    from cas_engine.parser import MathParser
    from cas_engine.formatter import MathFormatter

    s = text.strip()
    if not s:
        return ""

    # 1. Clean placeholders ⟦var⟧ -> var
    s_clean = re.sub(r'⟦(.*?)⟧', r'\1', s)

    # 2. Handle assignments :=
    assign_prefix = ""
    if ':=' in s_clean:
        parts = s_clean.split(':=', 1)
        lhs_raw = parts[0].strip()
        _SUB_MAP = {
            '₀': '0', '₁': '1', '₂': '2', '₃': '3', '₄': '4',
            '₅': '5', '₆': '6', '₇': '7', '₈': '8', '₉': '9',
            'ₐ': 'a', 'ᵦ': 'b', 'ₑ': 'e', 'ₕ': 'h', 'ᵢ': 'i', 'ⱼ': 'j',
            'ₖ': 'k', 'ₗ': 'l', 'ₘ': 'm', 'ₙ': 'n', 'ₒ': 'o',
            'ₚ': 'p', 'ᵣ': 'r', 'ᵤ': 'u', 'ᵥ': 'v', 'ₓ': 'x',
            'ₛ': 's', 'ₜ': 't',
        }
        all_sub_chars = ''.join(_SUB_MAP.keys())
        lhs_converted = re.sub(rf'(?<=[a-zA-Z_])([{re.escape(all_sub_chars)}]+)',
                               lambda m: '_' + ''.join(_SUB_MAP.get(c, c) for c in m.group(1)), lhs_raw)
        m_sub = re.match(r'^([a-zA-Z_]+)_([0-9a-zA-Z]+)$', lhs_converted)
        if m_sub:
            lhs_fmt = f"{m_sub.group(1)}_{{{m_sub.group(2)}}}"
        else:
            lhs_fmt = lhs_raw
        assign_prefix = lhs_fmt + r" := "
        s_clean = parts[1].strip()

    # Preprocess decimal comma in expression for template parsing
    if getattr(MathParser, 'decimal_separator', ',') == ',':
        s_clean = re.sub(r'(^|(?<=[\s+\-*/=([<{]))\s*,\s*(\d+)', r'\g<1>0.\2', s_clean)
        s_clean = re.sub(r'(?<=\d),(?=\d)', '.', s_clean)
        chars = []
        depth = 0
        i = 0
        n = len(s_clean)
        while i < n:
            ch = s_clean[i]
            if ch in '([{':
                depth += 1
                chars.append(ch)
                i += 1
            elif ch in ')]}':
                depth = max(0, depth - 1)
                chars.append(ch)
                i += 1
            elif depth == 0 and ch == ',' and i > 0 and s_clean[i - 1].isdigit():
                m = re.match(r'^\s*(\d+)', s_clean[i + 1:])
                if m:
                    chars.append('.' + m.group(1))
                    i += 1 + len(m.group(0))
                else:
                    chars.append(ch)
                    i += 1
            else:
                chars.append(ch)
                i += 1
        s_clean = ''.join(chars)
        s_clean = re.sub(r';\s*(?!\s*$)', ', ', s_clean)

    def _finish(res_latex: str) -> str:
        if getattr(MathFormatter, 'decimal_separator', ',') == ',':
            # Format decimal dots as LaTeX decimal commas {,}
            res_latex = re.sub(r'(?<=\d)\.(?=\d)', '{,}', res_latex)
            res_latex = re.sub(r'(?<=\d),(?=\d)', '{,}', res_latex)
        return assign_prefix + res_latex

    # 3. Handle arrow mappings like (x) -> y or x -> y
    if '->' in s_clean:
        parts = s_clean.split('->', 1)
        lhs = parts[0].strip().strip('()')
        rhs_latex = expr_to_preview_latex(parts[1])
        return _finish(f"{lhs} \\to {rhs_latex}")

    # If text has multiple lines, render each line independently so equations do not cross newlines
    if '\n' in s_clean:
        lines = [ln.strip() for ln in s_clean.split('\n') if ln.strip()]
        if len(lines) > 1:
            rendered = [expr_to_preview_latex(ln) for ln in lines]
            return _finish(r" \\ ".join(rendered))
        elif len(lines) == 1:
            s_clean = lines[0]

    # 4. Handle equation with single = at top-level (and not <=, >=, !=, ==)
    eq_pos = -1
    if '=' in s_clean and not any(op in s_clean for op in ('<=', '>=', '!=', '==')):
        b_depth = 0
        for idx, c in enumerate(s_clean):
            if c in '([{':
                b_depth += 1
            elif c in ')]}':
                b_depth = max(0, b_depth - 1)
            elif c == '=' and b_depth == 0:
                eq_pos = idx
                break

    if eq_pos != -1:
        left_ltx = expr_to_preview_latex(s_clean[:eq_pos])
        right_ltx = expr_to_preview_latex(s_clean[eq_pos + 1:])
        if left_ltx == right_ltx:
            return _finish(right_ltx)
        return _finish(f"{left_ltx} = {right_ltx}")

    # 5. Handle unevaluated calculus forms so preview shows proper LaTeX templates
    # First derivative or higher order
    m_diff = re.match(r'^diff\((.*)\)$', s_clean)
    if m_diff:
        args = [a.strip() for a in m_diff.group(1).split(',')]
        if len(args) == 2:
            return _finish(f"\\frac{{d}}{{d {args[1]}}} \\left({args[0]}\\right)")
        elif len(args) == 3:
            return _finish(f"\\frac{{d^{{{args[2]}}}}}{{d {args[1]}^{{{args[2]}}}}} \\left({args[0]}\\right)")

    # Integral (indefinite or definite)
    m_int = re.match(r'^integrate\((.*)\)$', s_clean)
    if m_int:
        inner = m_int.group(1).strip()
        m_def = re.match(r'^(.*?),\s*\((.*?),\s*(.*?),\s*(.*?)\)$', inner)
        if m_def:
            f, x, a, b = m_def.group(1), m_def.group(2), m_def.group(3), m_def.group(4)
            return _finish(f"\\int_{{{a}}}^{{{b}}} {f}\\, d{x}")
        args = [a.strip() for a in inner.split(',')]
        if len(args) == 2:
            return _finish(f"\\int {args[0]}\\, d{args[1]}")

    # Limit
    m_lim = re.match(r'^limit\((.*)\)$', s_clean)
    if m_lim:
        args = [a.strip() for a in m_lim.group(1).split(',')]
        if len(args) == 3:
            return _finish(f"\\lim_{{{args[1]} \\to {args[2]}}} \\left({args[0]}\\right)")

    # Summation & Product
    m_sum = re.match(r'^Sum\((.*?),\s*\((.*?),\s*(.*?),\s*(.*?)\)\)$', s_clean)
    if m_sum:
        f, i, k, n = m_sum.group(1), m_sum.group(2), m_sum.group(3), m_sum.group(4)
        return _finish(f"\\sum_{{{i}={k}}}^{{{n}}} {f}")

    m_prod = re.match(r'^Product\((.*?),\s*\((.*?),\s*(.*?),\s*(.*?)\)\)$', s_clean)
    if m_prod:
        f, i, k, n = m_prod.group(1), m_prod.group(2), m_prod.group(3), m_prod.group(4)
        return _finish(f"\\prod_{{{i}={k}}}^{{{n}}} {f}")

    # 6. Parse with SymPy / MathParser for standard expressions (fractions, powers, roots, trig, etc.)
    try:
        import warnings
        from sympy.utilities.exceptions import SymPyDeprecationWarning
        with warnings.catch_warnings():
            # Suppress SymPyDeprecationWarning that fires when implicit_multiplication_application
            # transformer constructs Pow(Symbol, Tuple) or Mul(Symbol, Tuple) for multi-arg function calls
            warnings.filterwarnings('ignore', category=SymPyDeprecationWarning)
            warnings.filterwarnings('ignore', category=DeprecationWarning)
            warnings.filterwarnings('ignore', message='.*non-Expr.*')
            warnings.filterwarnings('ignore', message='.*Tuple.*')
            parse_res = MathParser.parse(s_clean)
            if parse_res.sympy_expr is not None:
                return _finish(sp.latex(parse_res.sympy_expr))
    except Exception:
        pass

    # 7. Fallback: simple replacements
    fb = s_clean
    fb = re.sub(r'\((.*?)\)/\((.*?)\)', r'\\frac{\1}{\2}', fb)
    return _finish(fb)


class MathRendererWidget(QWidget):
    """
    Widget that displays rendered LaTeX mathematical formulas crisply.
    Supports scaling, theme switching, and copy/export.
    """
    doubleClicked = pyqtSignal()

    def __init__(self, latex_str: str = "", font_size: int = 14, theme_mode: str = "dark", parent=None):
        super().__init__(parent)
        self.latex_str = latex_str
        self.font_size = font_size
        self.theme_mode = theme_mode
        self.zoom_factor = 1.0

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(4, 4, 4, 4)
        self.layout.setSpacing(0)

        self.label = QLabel(self)
        self.label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.layout.addWidget(self.label)

        self.update_render()

    def set_latex(self, latex_str: str):
        """Update the rendered formula."""
        self.latex_str = latex_str
        self.update_render()

    def set_theme_mode(self, mode: str):
        """Update theme mode (dark / light) and re-render."""
        self.theme_mode = mode
        self.update_render()

    def set_font_size(self, size: int):
        """Update font size."""
        self.font_size = size
        self.update_render()

    def set_zoom_factor(self, factor: float):
        """Update zoom factor and re-render."""
        factor = max(0.2, min(5.0, factor))
        if abs(self.zoom_factor - factor) > 0.001:
            self.zoom_factor = factor
            self.update_render()

    def mouseDoubleClickEvent(self, event):
        self.doubleClicked.emit()
        super().mouseDoubleClickEvent(event)

    def update_render(self):
        """Render the LaTeX string into a crisp QPixmap and set to label."""
        if not self.latex_str:
            self.label.clear()
            self.label.setText("")
            return

        from PyQt6.QtWidgets import QApplication
        screen = self.screen() or QApplication.primaryScreen()
        screen_dpr = float(screen.devicePixelRatio()) if screen else 1.0
        dpr = max(1.0, float(self.devicePixelRatio()), screen_dpr)

        pixmap = self.render_latex_to_pixmap(
            self.latex_str,
            font_size=int(self.font_size * self.zoom_factor),
            theme_mode=self.theme_mode,
            dpi_scale=dpr
        )

        if pixmap and not pixmap.isNull():
            # For high-DPI displays (Retina)
            pixmap.setDevicePixelRatio(dpr)
            self.label.setPixmap(pixmap)
        else:
            # Fallback to plain text
            self.label.setText(self.latex_str)
            text_color = Theme.DARK_TEXT_PRIMARY if self.theme_mode == Theme.DARK else Theme.LIGHT_TEXT_PRIMARY
            self.label.setStyleSheet(f"color: {text_color}; font-size: {self.font_size}px; font-family: monospace;")

    @classmethod
    def render_latex_to_pixmap(cls, latex_str: str, font_size: int = 14, theme_mode: str = "dark", dpi_scale: float = 1.0, color: str = None) -> QPixmap:
        """
        Renders a LaTeX expression to a QPixmap using Matplotlib.
        Results are cached in memory for instant high-speed retrieval.
        """
        raw_latex = latex_str.strip()
        if not raw_latex:
            return QPixmap()

        cache_key = (raw_latex, font_size, theme_mode, round(dpi_scale, 2), color)
        if cache_key in _PIXMAP_CACHE:
            return QPixmap(_PIXMAP_CACHE[cache_key])

        # Wrap in math mode if not already
        if not (raw_latex.startswith('$') and raw_latex.endswith('$')):
            math_text = f"${raw_latex}$"
        else:
            math_text = raw_latex

        # Text and background colors (signature royal blue #0000aa for math output)
        if color:
            text_color = color
        elif theme_mode == Theme.LIGHT:
            text_color = "#0000aa"
        else:
            text_color = "#93c5fd"

        dpi = int(144 * max(1.0, dpi_scale))

        try:
            import re
            from matplotlib.backends.backend_agg import FigureCanvasAgg

            # Check if this is a matrix or multi-row table structure
            matrix_match = re.search(r"\\begin\{(matrix|pmatrix|bmatrix|cases)\}(.*?)\\end\{\1\}", raw_latex, re.DOTALL)
            if matrix_match:
                inner = matrix_match.group(2).strip()
                raw_rows = [r.strip() for r in inner.replace(r'\cr', r'\\').split(r'\\') if r.strip()]
                rows = []
                for r in raw_rows:
                    cols = [c.strip() for c in r.split('&')]
                    if any(cols):
                        rows.append(cols)

                if rows:
                    num_rows = len(rows)
                    num_cols = max(len(r) for r in rows)
                    is_record = any(r'\mathbf' in c for r in rows for c in r)

                    prefix = raw_latex[:matrix_match.start()].strip()
                    prefix = re.sub(r'\\left\[\s*$', '', prefix).strip()
                    prefix = re.sub(r'\[\s*$', '', prefix).strip()
                    prefix_w = max(0.5, len(prefix) * 0.14) if prefix else 0.0

                    if is_record:
                        fig_w = max(2.0, prefix_w + num_cols * 1.5)
                        fig_h = max(0.8, num_rows * 0.35 + 0.3)
                    else:
                        fig_w = max(1.1, prefix_w + num_cols * 0.75 + 0.35)
                        fig_h = max(0.8, num_rows * 0.36 + 0.25)

                    fig = Figure(figsize=(fig_w, fig_h), dpi=dpi)
                    fig.patch.set_alpha(0.0)
                    canvas = FigureCanvasAgg(fig)
                    ax = fig.add_axes([0.02, 0.02, 0.96, 0.96])
                    ax.set_axis_off()
                    ax.patch.set_alpha(0.0)

                    p_frac = prefix_w / fig_w if prefix else 0.0
                    if prefix:
                        p_color = Theme.DARK_TEXT_PRIMARY if theme_mode == Theme.DARK else Theme.LIGHT_TEXT_PRIMARY
                        prefix_math = prefix if (prefix.startswith('$') and prefix.endswith('$')) else f"${prefix}$"
                        ax.text(p_frac * 0.45, 0.5, prefix_math, fontsize=font_size, color=p_color, ha='center', va='center')

                    mat_left = p_frac + (0.04 if prefix else 0.0)
                    mat_right = 0.98

                    y_coords = [0.82 - 0.64 * (r / max(1, num_rows - 1)) if num_rows > 1 else 0.5 for r in range(num_rows)]

                    if is_record:
                        for r_idx, row in enumerate(rows):
                            k = row[0] if len(row) > 0 else ''
                            v = row[1] if len(row) > 1 else ''
                            if not k.startswith('$'): k = f"${k}$"
                            if not v.startswith('$'): v = f"${v}$"
                            ax.text(mat_left + 0.05, y_coords[r_idx], k, fontsize=font_size, color=text_color, ha='left', va='center')
                            ax.text(mat_left + 0.52, y_coords[r_idx], v, fontsize=font_size, color=text_color, ha='left', va='center')
                    else:
                        has_curly = r'\left\{' in raw_latex or 'cases' in raw_latex
                        has_parens = r'\left(' in raw_latex or 'pmatrix' in raw_latex

                        col_span = mat_right - mat_left
                        if has_curly:
                            col_xs = [mat_left + col_span * 0.35 + (col_span * 0.55) * (c / max(1, num_cols - 1)) if num_cols > 1 else mat_left + col_span * 0.5 for c in range(num_cols)]
                        else:
                            col_xs = [mat_left + col_span * 0.12 + (col_span * 0.76) * (c / max(1, num_cols - 1)) if num_cols > 1 else mat_left + col_span * 0.5 for c in range(num_cols)]

                        for r_idx, row in enumerate(rows):
                            for c_idx, val in enumerate(row):
                                v_math = val if (val.startswith('$') and val.endswith('$')) else f"${val}$"
                                ax.text(col_xs[c_idx], y_coords[r_idx], v_math, fontsize=font_size, color=text_color, ha='center', va='center')

                        # Draw brackets / braces
                        if has_curly:
                            ax.text(mat_left + col_span * 0.12, 0.5, r'$\{$', fontsize=font_size * 2.5, color=text_color, ha='center', va='center')
                        elif has_parens:
                            ax.text(mat_left + col_span * 0.05, 0.5, r'$($', fontsize=font_size * 2.2, color=text_color, ha='center', va='center')
                            ax.text(mat_right - col_span * 0.05, 0.5, r'$)$', fontsize=font_size * 2.2, color=text_color, ha='center', va='center')
                        else:
                            # Square brackets
                            b_left = mat_left + col_span * 0.03
                            b_right = mat_right - col_span * 0.03
                            bracket_arm = min(0.06, col_span * 0.05)
                            ax.plot([b_left + bracket_arm, b_left, b_left, b_left + bracket_arm], [0.93, 0.93, 0.07, 0.07], color=text_color, linewidth=1.6)
                            ax.plot([b_right - bracket_arm, b_right, b_right, b_right - bracket_arm], [0.93, 0.93, 0.07, 0.07], color=text_color, linewidth=1.6)

                        canvas.draw()
                        buf = io.BytesIO()
                        fig.savefig(buf, format='png', dpi=dpi, transparent=True, bbox_inches='tight', pad_inches=0.04)
                        plt.close(fig)

                        buf.seek(0)
                        pixmap = QPixmap()
                        pixmap.loadFromData(buf.read(), 'PNG')
                        if dpi_scale > 1.0:
                            pixmap.setDevicePixelRatio(dpi_scale)
                        _PIXMAP_CACHE[cache_key] = pixmap
                        return pixmap

            # Standard formula rendering
            fig = Figure(figsize=(0.01, 0.01), dpi=dpi)
            fig.patch.set_alpha(0.0)  # Transparent figure background
            canvas = FigureCanvasAgg(fig)

            ax = fig.add_axes([0, 0, 1, 1])
            ax.set_axis_off()
            ax.patch.set_alpha(0.0)

            # Render text
            text_obj = ax.text(
                0.5, 0.5, math_text,
                fontsize=font_size,
                color=text_color,
                ha='center', va='center',
                usetex=False
            )

            # Calculate tight bounding box
            canvas.draw()
            renderer = canvas.get_renderer()
            bbox = text_obj.get_window_extent(renderer)
            w_in = max(0.1, (bbox.width + 16) / dpi)
            h_in = max(0.1, (bbox.height + 12) / dpi)

            fig.set_size_inches(w_in, h_in)

            # Render to buffer
            buf = io.BytesIO()
            fig.savefig(buf, format='png', dpi=dpi, transparent=True, bbox_inches='tight', pad_inches=0.04)
            plt.close(fig)

            buf.seek(0)
            img_bytes = buf.read()
            pixmap = QPixmap()
            pixmap.loadFromData(img_bytes, 'PNG')
            if dpi_scale > 1.0:
                pixmap.setDevicePixelRatio(dpi_scale)
            _PIXMAP_CACHE[cache_key] = pixmap
            return pixmap

        except Exception:
            # If mathtext fails to parse complex latex, return empty QPixmap
            try:
                plt.close('all')
            except Exception:
                pass
            return QPixmap()
