"""
OpenMath Execution Group & Worksheet Cell.
Provides authentic visual appearance and interaction:
- Left execution group bracket indicator `[`
- Prompt `> ` in classic dark red/black
- 2-D Math mode (Times New Roman italic), 1-D Math mode (Courier/Consolas), and Text mode
- F5 mode toggle shortcut
- Tab navigation between template placeholders ⟦...⟧
- Command autocompletion on Esc / Ctrl+Space
- Output displayed in signature royal blue (#0000aa)
- Right-aligned equation labels (1), (2), (3)...
- Direct embedded Matplotlib plots inside the worksheet flow
"""

import os
import uuid
import re
import base64
from typing import Optional, List, Dict, Any, Tuple, Union
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QTextEdit,
    QPushButton, QFrame, QSizePolicy, QApplication, QMenu,
    QCompleter, QDialog, QLineEdit, QDialogButtonBox, QFileDialog
)
from PyQt6.QtGui import (
    QFont, QFontMetrics, QColor, QKeyEvent, QPainter, QPainterPath, QPen,
    QTextCursor, QWheelEvent, QTextCharFormat, QTextBlockFormat, QTextFormat, QTextImageFormat,
    QTextDocument, QPixmap, QImage, QSyntaxHighlighter, QPolygonF, QKeySequence, QBrush, QPalette,
    QTextOption
)
from PyQt6.QtCore import Qt, pyqtSignal, QRect, QRectF, QSize, QTimer, QStringListModel, QEvent, QUrl, QPoint, QPointF, QBuffer, QIODevice, QMimeData
try:
    from PyQt6 import sip
except ImportError:
    import sip

_GLOBAL_IMAGE_CACHE: Dict[str, Tuple[QImage, str]] = {}

PROP_MODE = int(QTextFormat.Property.UserProperty) + 1
PROP_FRAC_ID = int(QTextFormat.Property.UserProperty) + 10
PROP_MATH_EXPR = int(QTextFormat.Property.UserProperty) + 11
PROP_IS_EXPONENT = int(QTextFormat.Property.UserProperty) + 12
PROP_TALL_PAREN = int(QTextFormat.Property.UserProperty) + 20
PROP_SUBSCRIPT_LEVEL = int(QTextFormat.Property.UserProperty) + 21

from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
import matplotlib.offsetbox as mob

from cas_engine import CASResult, PlotData, MathParser
from .math_renderer import MathRendererWidget, expr_to_preview_latex
from .syntax_highlighter import MathSyntaxHighlighter
from .theme import Theme

SUPER_MAP = {
    '0': '⁰', '1': '¹', '2': '²', '3': '³', '4': '⁴',
    '5': '⁵', '6': '⁶', '7': '⁷', '8': '⁸', '9': '⁹',
    '+': '⁺', '-': '⁻', '=': '⁼', '(': '⁽', ')': '⁾',
    'a': 'ᵃ', 'b': 'ᵇ', 'c': 'ᶜ', 'd': 'ᵈ', 'e': 'ᵉ',
    'f': 'ᶠ', 'g': 'ᵍ', 'h': 'ʰ', 'i': 'ⁱ', 'j': 'ʲ',
    'k': 'ᵏ', 'l': 'ˡ', 'm': 'ᵐ', 'n': 'ⁿ', 'o': 'ᵒ',
    'p': 'ᵖ', 'r': 'ʳ', 's': 'ˢ', 't': 'ᵗ', 'u': 'ᵘ',
    'v': 'ᵛ', 'w': 'ʷ', 'x': 'ˣ', 'y': 'ʸ', 'z': 'ᶻ',
    '*': '·', '·': '·'
}

INV_SUPER_MAP = {v: k for k, v in SUPER_MAP.items() if k != '·'}
INV_SUPER_MAP['·'] = '*'
INV_SUPER_MAP['⋅'] = '*'

SUB_MAP = {
    '0': '₀', '1': '₁', '2': '₂', '3': '₃', '4': '₄',
    '5': '₅', '6': '₆', '7': '₇', '8': '₈', '9': '₉',
    '+': '₊', '-': '₋', '=': '₌', '(': '₍', ')': '₎',
    'a': 'ₐ', 'b': 'ᵦ', 'e': 'ₑ', 'h': 'ₕ', 'i': 'ᵢ', 'j': 'ⱼ',
    'k': 'ₖ', 'l': 'ₗ', 'm': 'ₘ', 'n': 'ₙ', 'o': 'ₒ',
    'p': 'ₚ', 'r': 'ᵣ', 's': 'ₛ', 't': 'ₜ', 'u': 'ᵤ',
    'v': 'ᵥ', 'x': 'ₓ'
}

INV_SUB_MAP = {v: k for k, v in SUB_MAP.items()}


def format_subscripts_and_superscripts(text: str) -> str:
    """Convert _1, _{12}, ^2, ^{abc} to authentic Unicode subscript and superscript characters."""
    if not text or ('_' not in text and '^' not in text):
        return text
    sub_keys = ''.join(SUB_MAP.keys())
    sub_id_keys = ''.join(c for c in SUB_MAP.keys() if c.isalnum())
    sup_keys = ''.join(SUPER_MAP.keys())
    sup_id_keys = ''.join(c for c in SUPER_MAP.keys() if c.isalnum())
    formatted = text
    # Superscripts: ^{...} or ^token (alphanumeric, avoids capturing trailing closing parenthesis)
    formatted = re.sub(f'\\^{{([{re.escape(sup_keys)}]+)}}', lambda m: ''.join(SUPER_MAP.get(c, c) for c in m.group(1)), formatted)
    formatted = re.sub(f'\\^([{re.escape(sup_id_keys)}]+)', lambda m: ''.join(SUPER_MAP.get(c, c) for c in m.group(1)), formatted)
    # Subscripts: _{...} or _token (alphanumeric, avoids capturing trailing closing parenthesis)
    # Protect stepped identifiers (multi-underscore like two_comp_repr or word identifiers like bit_toggle,
    # where the subscript chain is not a simple 1-2 char unicode subscript in SUB_MAP)
    tokens = set(re.findall(r'\b[a-zA-Z][a-zA-Z0-9]*(?:_[a-zA-Z0-9_]+)+\b', formatted))
    stepped_tokens = set()
    for tok in tokens:
        sub_chain = tok.split('_')[1:]
        if not (len(sub_chain) == 1 and len(sub_chain[0]) <= 2 and all(c in SUB_MAP for c in sub_chain[0])):
            stepped_tokens.add(tok)

    placeholders = {}
    for i, tok in enumerate(sorted(stepped_tokens, key=len, reverse=True)):
        ph = f"OMPPROTECTEDSTEPPEDTOKEN{i}X"
        placeholders[ph] = tok
        formatted = formatted.replace(tok, ph)

    formatted = re.sub(r'(?<=[a-zA-Z0-9_\)\]\}])_+{' + f'([{re.escape(sub_keys)}]+)' + r'}', lambda m: ''.join(SUB_MAP.get(c, c) for c in m.group(1)), formatted)
    formatted = re.sub(r'(?<=[a-zA-Z0-9_\)\]\}])_+' + f'([{re.escape(sub_id_keys)}]+)(?![a-zA-Z0-9])', lambda m: ''.join(SUB_MAP.get(c, c) for c in m.group(1)), formatted)

    for ph, tok in placeholders.items():
        formatted = formatted.replace(ph, tok)

    return formatted


class Math2DHighlighter(QSyntaxHighlighter):
    """
    Ensures authentic mathematical typography in 2D Math mode:
    Numbers (0-9), subscript digits (₀-₉), and operators (:=, +, -, =, etc.)
    are displayed in upright roman font, while variable symbols remain elegant
    italic Times New Roman.
    """
    def __init__(self, parent_edit: 'CellInputEdit'):
        super().__init__(parent_edit.document())
        self.parent_edit = parent_edit
        self.fmt_upright = QTextCharFormat()
        self.fmt_upright.setFontItalic(False)
        self.fmt_colon = QTextCharFormat()
        self.fmt_colon.setFontItalic(False)
        self.fmt_colon.setFontWeight(QFont.Weight.Bold)
        self._pattern = re.compile(r'[0-9₀₁₂₃₄₅₆₇₈₉:=+\-*/()·\u00b7\u2212]+')
        self._colon_pattern = re.compile(r':')

    def highlightBlock(self, text: str):
        if not text or not self.parent_edit:
            return
        parent_cell = getattr(self.parent_edit, 'parent_cell', None)
        mode_2d = getattr(parent_cell, 'MODE_2D_MATH', '2d_math')
        mode_nonexec = getattr(parent_cell, 'MODE_NONEXEC_MATH', 'nonexec_math')
        current_mode = self.parent_edit.get_mode_at_cursor()
        if current_mode not in (mode_2d, mode_nonexec):
            return

        for m in self._pattern.finditer(text):
            self.setFormat(m.start(), m.end() - m.start(), self.fmt_upright)

        for m in self._colon_pattern.finditer(text):
            self.setFormat(m.start(), 1, self.fmt_colon)


MATH_COMPLETIONS = [
    # CAS & Algebra
    "factor", "expand", "simplify", "solve", "fsolve", "evalf", "roots", "collect",
    "apart", "together", "normal", "trigsimp", "expand_trig", "piecewise",
    "seq", "add", "mul", "maximize", "minimize", "unassign", "restart",
    # Calculus
    "diff", "integrate", "limit", "taylor", "series", "dsolve",
    "Sum", "Product", "Derivative", "Integral",
    # Linear Algebra
    "Matrix", "Vector", "det", "inv", "transpose", "eigenvals", "eigenvects",
    "rref", "nullspace", "rank", "trace", "charpoly", "eye", "zeros",
    "Determinant", "Inverse", "Transpose", "Eigenvalues", "Eigenvectors",
    "Trace", "Rank", "NullSpace", "CharacteristicPolynomial",
    # Functions
    "sin", "cos", "tan", "sec", "csc", "cot",
    "asin", "acos", "atan", "sinh", "cosh", "tanh",
    "exp", "ln", "log", "sqrt", "Abs", "factorial", "binomial", "Piecewise",
    # Plots & Reference Functions
    "plot", "plot3d", "plot_parametric", "plot_polar", "polygonOmråde", "LPplot",
    "Uligheder",
    # Embedded Systems Calculations
    "to_bin", "to_hex", "toᵦᵢₙ", "toₕₑₓ", "twos_comp", "twos_comp_repr", "two_comp", "two_comp_repr", "bit_get", "bit_set",
    "bit_clear", "bit_toggle", "bit_mask", "bit_field", "to_q", "from_q",
    "ieee754", "ubrr_calc", "timer_calc", "timer_arr", "pwm_duty",
    "adc_raw", "adc_volt", "adc_resolution", "voltage_divider",
    "led_resistor", "rc_cutoff", "crc8", "crc16"
]


def _extract_preceding_numerator_token(text: str):
    """
    Extract token/expression immediately preceding cursor to be used as fraction numerator.
    Returns (string_to_delete, numerator_expression, is_exponent).
    """
    if not text:
        return "", "", False

    sup_vals = set(SUPER_MAP.values())
    sup_vals.add('·')

    # Case A: text ends with ^
    if text.endswith('^'):
        return "^", "a", True

    # Case B: text ends with superscript characters, e.g. 10¹ or 10⁽¹⁾ or 10⁽¹
    if text[-1] in sup_vals or text[-1] == '⁾':
        if text.endswith('⁾'):
            depth = 0
            for i in range(len(text) - 1, -1, -1):
                if text[i] == '⁾':
                    depth += 1
                elif text[i] == '⁽':
                    depth -= 1
                    if depth == 0:
                        to_del = text[i:]
                        expr = text[i+1:-1]
                        if i > 0 and text[i-1] == '^':
                            to_del = "^" + to_del
                        num = "".join(INV_SUPER_MAP.get(c, c) for c in expr)
                        return to_del, num if num else "a", True
        m = re.search(rf'(\^?⁽?[{re.escape("".join(sup_vals))}]+)$', text)
        if m:
            to_del = m.group(1)
            raw = to_del.lstrip('^⁽')
            num = "".join(INV_SUPER_MAP.get(c, c) for c in raw)
            return to_del, num if num else "a", True

    # Case C: parenthesized ASCII expression: (num)
    if text.endswith(")"):
        depth = 0
        for i in range(len(text) - 1, -1, -1):
            if text[i] == ")":
                depth += 1
            elif text[i] == "(":
                depth -= 1
                if depth == 0:
                    prefix = text[:i]
                    if prefix.endswith('^'):
                        return prefix[-1:] + text[i:], text[i+1:-1].strip(), True
                    fn_match = re.search(r"([a-zA-Z0-9_]+)$", prefix)
                    if fn_match:
                        full_del = fn_match.group(1) + text[i:]
                        return full_del, full_del, False
                    expr = text[i + 1:-1].strip()
                    return text[i:], expr, False
        return "", "", False

    # Case D: ^token, e.g. 10^1 or 10^x
    m_pow = re.search(r"\^([a-zA-Z0-9_\.]+)$", text)
    if m_pow:
        return m_pow.group(0), m_pow.group(1), True

    # Case E: standard token: 10 or x
    m = re.search(r"([a-zA-Z0-9_\.]+)$", text)
    if m:
        return m.group(1), m.group(1), False
    return "", "", False


def decimal_to_fraction(dec_str: str):
    """
    Convert a decimal string (e.g. '30,3333333333' or '1,25' or '3.3333333333')
    into an exact Rational fraction (e.g. 91/3, 5/4, 10/3).
    Handles both terminating decimals and recurring decimal approximations.
    """
    if not dec_str:
        return None
    clean = str(dec_str).replace(',', '.').strip()
    try:
        from fractions import Fraction
        f = Fraction(clean).limit_denominator(1000000)
        flt_val = float(clean)
        if abs(float(f) - flt_val) < 1e-6:
            import sympy as sp
            return sp.Rational(f.numerator, f.denominator)
    except Exception:
        pass

    try:
        import sympy as sp
        val = sp.sympify(clean)
        rat = sp.nsimplify(val, tolerance=1e-6, rational=True)
        return rat
    except Exception:
        pass

    return None


def _parse_fraction_str(val: str):
    """
    Parse a string representation of a fraction into (num, den).
    Supports:
      - LaTeX: \frac{num}{den}
      - Chained/nested parenthesized: (num)/(den)
      - Simple token division: num/den
    """
    if not val:
        return None
    val = val.strip()
    if not val:
        return None

    # 1. LaTeX \frac{num}{den}
    if val.startswith(r'\frac') or val.startswith('frac'):
        prefix = r'\frac' if val.startswith(r'\frac') else 'frac'
        rest = val[len(prefix):].strip()
        if rest.startswith('{'):
            depth = 0
            split_idx = -1
            for i, c in enumerate(rest):
                if c == '{': depth += 1
                elif c == '}': depth -= 1
                if depth == 0:
                    split_idx = i
                    break
            if split_idx != -1:
                num = rest[1:split_idx]
                rem = rest[split_idx+1:].strip()
                if rem.startswith('{') and rem.endswith('}'):
                    den = rem[1:-1]
                    return num.strip(), den.strip()

    # 2. (num)/(den) with balanced parentheses
    if val.startswith('(') and ')/(' in val and val.endswith(')'):
        depth = 0
        split_idx = -1
        for i, c in enumerate(val):
            if c == '(': depth += 1
            elif c == ')': depth -= 1
            if depth == 0:
                if val[i:i+3] == ')/(':
                    split_idx = i
                    break
        if split_idx != -1:
            num = val[1:split_idx]
            den = val[split_idx+3:-1]
            return num.strip(), den.strip()

    # 3. (num)/den or num/(den)
    if val.startswith('(') and ')/' in val:
        depth = 0
        split_idx = -1
        for i, c in enumerate(val):
            if c == '(': depth += 1
            elif c == ')': depth -= 1
            if depth == 0:
                if val[i:i+2] == ')/':
                    split_idx = i
                    break
        if split_idx != -1:
            num = val[1:split_idx]
            den = val[split_idx+2:].strip()
            if den.startswith('(') and den.endswith(')'):
                den = den[1:-1]
            return num.strip(), den.strip()

    if '/(' in val and val.endswith(')'):
        idx = val.find('/(')
        num = val[:idx].strip()
        den = val[idx+2:-1].strip()
        if not any(op in num for op in ['+', '=', ':=', '<', '>', ';']):
            return num, den

    # 4. Simple num/den without outer operators
    if '/' in val and not any(op in val for op in ['+', '=', ':=', '<', '>', '*', ';', '^', '(', ')']):
        parts = val.split('/', 1)
        if parts[0].strip() and parts[1].strip():
            return parts[0].strip(), parts[1].strip()

    return None


def parse_matrix_string(text: str):
    """
    Parse a Matrix(...) string or list of lists into a 2D list of strings.
    E.g. "Matrix([[1, 2, 4], [-1, 0, 5], [1, 8, 5]])" -> [["1", "2", "4"], ["-1", "0", "5"], ["1", "8", "5"]]
    """
    if not text:
        return None
    s = text.strip()
    if s.startswith("Matrix(") and s.endswith(")"):
        s = s[7:-1].strip()

    import ast
    try:
        start = s.find('[')
        end = s.rfind(']')
        if start != -1 and end != -1:
            raw = ast.literal_eval(s[start:end + 1])
            if isinstance(raw, list) and all(isinstance(r, list) for r in raw):
                return [[str(elem).strip() for elem in row] for row in raw]
    except Exception:
        pass

    try:
        import sympy as sp
        expr = sp.sympify(text)
        if isinstance(expr, sp.MatrixBase):
            rows, cols = expr.shape
            return [[sp.sstr(expr[r, c]) for c in range(cols)] for r in range(rows)]
    except Exception:
        pass

    import re
    m_ltx = re.search(r'\\begin\{(?:matrix|pmatrix|bmatrix)\}(.*?)\\end\{(?:matrix|pmatrix|bmatrix)\}', s, re.DOTALL)
    if not m_ltx:
        m_ltx = re.search(r'\\\\begin\{(?:matrix|pmatrix|bmatrix)\}(.*?)\\\\end\{(?:matrix|pmatrix|bmatrix)\}', s, re.DOTALL)
    if m_ltx:
        inner = m_ltx.group(1).strip()
        raw_rows = [r.strip() for r in inner.replace(r'\cr', r'\\').split(r'\\') if r.strip()]
        res = []
        for r in raw_rows:
            cols = [c.strip() for c in r.split('&')]
            if any(cols):
                res.append(cols)
        if res:
            return res

    return None


def parse_math_tokens(text: str) -> list:
    """
    Parses a math string into a list of ('text', str), ('fraction', num_str, den_str),
    and ('radical', radicand_str, degree_str).
    Used when loading worksheets and embedding child math structures so saved fraction
    expressions, radicals, and nested structures are restored as true visual 2D widgets.
    """
    tokens = []
    i = 0
    n = len(text)
    sup_digits = {
        '⁰': '0', '¹': '1', '²': '2', '³': '3', '⁴': '4',
        '⁵': '5', '⁶': '6', '⁷': '7', '⁸': '8', '⁹': '9',
        'ⁿ': 'n', 'ⁱ': 'i'
    }
    while i < n:
        # Check for Matrix([...])
        if text.startswith('Matrix([', i):
            depth = 1
            j = i + 7
            while j < n and depth > 0:
                if text[j] == '(': depth += 1
                elif text[j] == ')': depth -= 1
                j += 1
            if depth == 0:
                mat_str = text[i:j]
                m_data = parse_matrix_string(mat_str)
                if m_data:
                    tokens.append(('matrix', m_data))
                    i = j
                    continue

        # Check for LaTeX \frac{...}{...}
        if text.startswith(r'\frac{', i):
            depth = 1
            j = i + 6
            while j < n and depth > 0:
                if text[j] == '{': depth += 1
                elif text[j] == '}': depth -= 1
                j += 1
            if depth == 0:
                num_content = text[i+6:j-1]
                w = j
                while w < n and text[w].isspace(): w += 1
                if w < n and text[w] == '{':
                    k = w + 1
                    depth = 1
                    while k < n and depth > 0:
                        if text[k] == '{': depth += 1
                        elif text[k] == '}': depth -= 1
                        k += 1
                    if depth == 0:
                        den_content = text[w+1:k-1]
                        tokens.append(('fraction', num_content, den_content))
                        i = k
                        continue

        # Check for radical (LaTeX \sqrt, root(...), sqrt(...), or unicode √)
        matched_rad = None
        if text.startswith(r'\sqrt', i):
            p = i + 5
            deg = None
            if p < n and text[p] == '[':
                depth = 1
                q = p + 1
                while q < n and depth > 0:
                    if text[q] == '[': depth += 1
                    elif text[q] == ']': depth -= 1
                    q += 1
                if depth == 0:
                    deg = text[p+1:q-1]
                    p = q
            while p < n and text[p].isspace():
                p += 1
            if p < n and text[p] == '{':
                depth = 1
                q = p + 1
                while q < n and depth > 0:
                    if text[q] == '{': depth += 1
                    elif text[q] == '}': depth -= 1
                    q += 1
                if depth == 0:
                    matched_rad = (text[p+1:q-1], deg, q)

        elif (i == 0 or not (text[i-1].isalnum() or text[i-1] == '_')) and text.startswith('root(', i):
            depth = 1
            j = i + 5
            comma_idx = -1
            bracket_d = 0
            brace_d = 0
            while j < n and depth > 0:
                ch = text[j]
                if ch == '(':
                    depth += 1
                elif ch == ')':
                    depth -= 1
                    if depth == 0:
                        break
                elif ch == '[':
                    bracket_d += 1
                elif ch == ']':
                    bracket_d -= 1
                elif ch == '{':
                    brace_d += 1
                elif ch == '}':
                    brace_d -= 1
                elif ch == ',' and depth == 1 and bracket_d == 0 and brace_d == 0:
                    comma_idx = j
                j += 1
            if depth == 0 and comma_idx != -1:
                matched_rad = (text[i+5:comma_idx].strip(), text[comma_idx+1:j].strip(), j + 1)

        elif (i == 0 or not (text[i-1].isalnum() or text[i-1] == '_')) and text.startswith('sqrt(', i):
            depth = 1
            j = i + 5
            while j < n and depth > 0:
                if text[j] == '(': depth += 1
                elif text[j] == ')': depth -= 1
                j += 1
            if depth == 0:
                matched_rad = (text[i+5:j-1].strip(), None, j)

        else:
            deg_str = ""
            p = i
            while p < n and text[p] in sup_digits:
                deg_str += sup_digits[text[p]]
                p += 1
            if p < n and text[p] == '√':
                rad_start = p + 1
                if rad_start < n and text[rad_start] == '(':
                    depth = 1
                    j = rad_start + 1
                    while j < n and depth > 0:
                        if text[j] == '(': depth += 1
                        elif text[j] == ')': depth -= 1
                        j += 1
                    if depth == 0:
                        matched_rad = (text[rad_start+1:j-1].strip(), deg_str if deg_str else None, j)
                else:
                    m = re.match(r'^([a-zA-Z0-9_.]+)', text[rad_start:])
                    if m:
                        matched_rad = (m.group(1), deg_str if deg_str else None, rad_start + len(m.group(1)))

        if matched_rad is not None:
            rad_content, deg_content, end_pos = matched_rad
            w = end_pos
            while w < n and text[w] == ' ': w += 1
            if w < n and text[w] == '/':
                w += 1
                while w < n and text[w] == ' ': w += 1
                den_content = None
                den_end = w
                if w < n and text[w] == '(':
                    depth = 1
                    k = w + 1
                    while k < n and depth > 0:
                        if text[k] == '(': depth += 1
                        elif text[k] == ')': depth -= 1
                        k += 1
                    if depth == 0:
                        den_content = text[w+1:k-1].strip()
                        den_end = k
                else:
                    m = re.match(r'^([a-zA-Z0-9_.]+)', text[w:])
                    if m:
                        den_content = m.group(1).strip()
                        den_end = w + len(m.group(0))

                if den_content:
                    rad_rep = f"root({rad_content}, {deg_content})" if deg_content else f"sqrt({rad_content})"
                    if tokens and tokens[-1][0] == 'text':
                        m_coeff = re.search(r'([a-zA-Z0-9_.]+\s*[*·]\s*)$', tokens[-1][1])
                        if m_coeff:
                            coeff_str = m_coeff.group(1)
                            tokens[-1] = ('text', tokens[-1][1][:-len(coeff_str)])
                            if not tokens[-1][1]: tokens.pop()
                            rad_rep = f"{coeff_str}{rad_rep}"
                    tokens.append(('fraction', rad_rep, den_content))
                    i = den_end
                    continue

            tokens.append(('radical', rad_content, deg_content))
            i = end_pos
            continue

        # Check for unicode superscript fraction: ⁽num/den⁾
        if text[i] == '⁽':
            depth = 1
            j = i + 1
            while j < n and depth > 0:
                if text[j] == '⁽': depth += 1
                elif text[j] == '⁾': depth -= 1
                j += 1
            if depth == 0:
                inner = text[i+1:j-1]
                if '/' in inner:
                    parts = inner.split('/', 1)
                    num_c = "".join(INV_SUPER_MAP.get(c, c) for c in parts[0].strip())
                    den_c = "".join(INV_SUPER_MAP.get(c, c) for c in parts[1].strip())
                    if num_c and den_c:
                        if tokens and tokens[-1][0] == 'text' and tokens[-1][1].endswith('^'):
                            tokens[-1] = ('text', tokens[-1][1][:-1])
                            if not tokens[-1][1]: tokens.pop()
                        tokens.append(('fraction', num_c, den_c, True))
                        i = j
                        continue

        # Check for (num)/(den) pattern or (num/den) pattern
        is_preceded_by_caret = bool(tokens and tokens[-1][0] == 'text' and tokens[-1][1].endswith('^'))
        if text[i] == '(':
            depth = 1
            j = i + 1
            while j < n and depth > 0:
                if text[j] == '(': depth += 1
                elif text[j] == ')': depth -= 1
                j += 1
            if depth == 0:
                inner = text[i+1:j-1]
                w = j
                while w < n and text[w] == ' ': w += 1
                if w < n and text[w] == '/':
                    w += 1
                    while w < n and text[w] == ' ': w += 1
                    if w < n and text[w] == '(':
                        k = w + 1
                        depth = 1
                        while k < n and depth > 0:
                            if text[k] == '(': depth += 1
                            elif text[k] == ')': depth -= 1
                            k += 1
                        if depth == 0:
                            num_content = inner
                            den_content = text[w+1:k-1]
                            if is_preceded_by_caret:
                                tokens[-1] = ('text', tokens[-1][1][:-1])
                                if not tokens[-1][1]: tokens.pop()
                                tokens.append(('fraction', num_content, den_content, True))
                            else:
                                tokens.append(('fraction', num_content, den_content))
                            i = k
                            continue
                    else:
                        m = re.match(r'^([a-zA-Z0-9_.]+(?:\/[a-zA-Z0-9_.]+)?)\b', text[w:])
                        if m:
                            num_content = inner
                            den_content = m.group(1)
                            if is_preceded_by_caret:
                                tokens[-1] = ('text', tokens[-1][1][:-1])
                                if not tokens[-1][1]: tokens.pop()
                                tokens.append(('fraction', num_content, den_content, True))
                            else:
                                tokens.append(('fraction', num_content, den_content))
                            i = w + len(den_content)
                            continue
                elif '/' in inner and not any(op in inner for op in ['+', '=', ':=', '<', '>', '*', ';', '^']):
                    parts = inner.split('/', 1)
                    if parts[0].strip() and parts[1].strip():
                        if is_preceded_by_caret:
                            tokens[-1] = ('text', tokens[-1][1][:-1])
                            if not tokens[-1][1]: tokens.pop()
                            tokens.append(('fraction', parts[0].strip(), parts[1].strip(), True))
                        else:
                            tokens.append(('fraction', parts[0].strip(), parts[1].strip()))
                        i = j
                        continue

        # Check for simple num/den token: e.g. 1/30 or 5/sqrt(33)
        m_num = re.match(r'^([a-zA-Z0-9_.]+)\s*/\s*', text[i:])
        if m_num:
            den_start = i + len(m_num.group(0))
            if text.startswith('sqrt(', den_start):
                depth = 1
                j = den_start + 5
                while j < n and depth > 0:
                    if text[j] == '(': depth += 1
                    elif text[j] == ')': depth -= 1
                    j += 1
                if depth == 0:
                    tokens.append(('fraction', m_num.group(1), text[den_start:j]))
                    i = j
                    continue
            elif text.startswith('√', den_start):
                m_rad = re.match(r'^√(?:\(([^\)]+)\)|([a-zA-Z0-9_.]+))', text[den_start:])
                if m_rad:
                    rad_in = m_rad.group(1) or m_rad.group(2)
                    tokens.append(('fraction', m_num.group(1), f"sqrt({rad_in})"))
                    i = den_start + len(m_rad.group(0))
                    continue
            elif is_preceded_by_caret:
                m_den = re.match(r'^([a-zA-Z0-9_.]+)\b', text[den_start:])
                if m_den:
                    tokens[-1] = ('text', tokens[-1][1][:-1])
                    if not tokens[-1][1]: tokens.pop()
                    tokens.append(('fraction', m_num.group(1), m_den.group(1), True))
                    i = den_start + len(m_den.group(0))
                    continue
            else:
                m_den = re.match(r'^([a-zA-Z0-9_.]+)\b', text[den_start:])
                if m_den:
                    tokens.append(('fraction', m_num.group(1), m_den.group(1)))
                    i = den_start + len(m_den.group(0))
                    continue

        # Plain text
        if tokens and tokens[-1][0] == 'text':
            tokens[-1] = ('text', tokens[-1][1] + text[i])
        else:
            tokens.append(('text', text[i]))
        i += 1
    return tokens


class MathSlotEdit(QTextEdit):
    """
    Seamless multi-line capable math slot text editor.
    Used inside math templates (RadicalWidget, FractionSlot, DefiniteIntegralWidget)
    to allow formulas that exceed the window/editor width to naturally wrap down onto
    multiple lines instead of disappearing off the right edge.
    Maintains a 100% QLineEdit-compatible API for backwards compatibility.
    """
    textEdited = pyqtSignal(str)
    returnPressed = pyqtSignal()

    def __init__(self, text: str = "", parent=None):
        super().__init__(parent)
        self._alignment = Qt.AlignmentFlag.AlignLeft
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        self.document().setDocumentMargin(1)
        self.setContentsMargins(0, 0, 0, 0)
        self.setStyleSheet("background: transparent; border: none; padding: 0px;")
        if text:
            self.setPlainText(text)
        self.textChanged.connect(self._on_text_changed_internal)

    def _on_text_changed_internal(self):
        self.textEdited.emit(self.toPlainText())

    def text(self) -> str:
        return self.toPlainText()

    def setText(self, text: str):
        self.blockSignals(True)
        self.setPlainText(text)
        if hasattr(self, '_alignment') and self._alignment != Qt.AlignmentFlag.AlignLeft:
            self.setAlignment(self._alignment)
        if self.width() > 0 and self.document():
            self.document().setTextWidth(self.width())
        self.blockSignals(False)
        self.textChanged.emit()

    def insert(self, text: str):
        self.insertPlainText(text)

    def cursorPosition(self) -> int:
        return self.textCursor().position()

    def setCursorPosition(self, pos: int):
        cur = self.textCursor()
        cur.setPosition(max(0, min(pos, len(self.toPlainText()))))
        self.setTextCursor(cur)

    def selectedText(self) -> str:
        return self.textCursor().selectedText()

    def hasSelectedText(self) -> bool:
        return self.textCursor().hasSelection()

    def deselect(self):
        cur = self.textCursor()
        cur.clearSelection()
        self.setTextCursor(cur)

    def setAlignment(self, alignment: Qt.AlignmentFlag):
        self._alignment = alignment
        super().setAlignment(alignment)
        doc = self.document()
        if doc:
            already_aligned = True
            blk = doc.begin()
            while blk.isValid():
                if blk.blockFormat().alignment() != alignment:
                    already_aligned = False
                    break
                blk = blk.next()
            if not already_aligned:
                self.blockSignals(True)
                blk = doc.begin()
                while blk.isValid():
                    cur = QTextCursor(blk)
                    fmt = cur.blockFormat()
                    fmt.setAlignment(alignment)
                    cur.setBlockFormat(fmt)
                    blk = blk.next()
                self.blockSignals(False)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        w = event.size().width()
        if w > 0 and self.document() and self.document().textWidth() != w:
            self.document().setTextWidth(w)
            if hasattr(self, '_alignment') and self._alignment != Qt.AlignmentFlag.AlignLeft:
                if self.alignment() != self._alignment:
                    self.setAlignment(self._alignment)


def _is_cursor_on_first_line(edit: MathSlotEdit) -> bool:
    if not isinstance(edit, QTextEdit):
        return True
    cur = edit.textCursor()
    block = cur.block()
    if block.blockNumber() > 0:
        return False
    layout = block.layout()
    if layout and layout.lineCount() > 1:
        pos_in_block = cur.positionInBlock()
        first_line = layout.lineAt(0)
        return pos_in_block <= first_line.textLength()
    return True


def _is_cursor_on_last_line(edit: MathSlotEdit) -> bool:
    if not isinstance(edit, QTextEdit):
        return True
    cur = edit.textCursor()
    doc = edit.document()
    block = cur.block()
    if block.blockNumber() < doc.blockCount() - 1:
        return False
    layout = block.layout()
    if layout and layout.lineCount() > 1:
        pos_in_block = cur.positionInBlock()
        last_line = layout.lineAt(layout.lineCount() - 1)
        return pos_in_block >= last_line.textStart()
    return True


class FractionSlot(QWidget):
    """
    A slot inside a FractionWidget (either numerator or denominator).
    Contains an inline sequence of items (QLineEdit for text, FractionWidget for nested fractions).
    Supports multiple child fractions next to each other (e.g. 1/30 + 1/30), interactive typing,
    seamless arrow navigation between all elements, auto-sizing, and centering.
    """
    def __init__(self, initial_value="", is_num: bool = True, parent_frac=None, is_result: bool = False):
        super().__init__(parent_frac)
        self.is_num = is_num
        self.parent_frac = parent_frac
        self.is_result = is_result or (parent_frac and getattr(parent_frac, 'is_result', False))
        self.items = []
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("background: transparent;")

        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(1)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._init_from_value(initial_value)

    def _init_from_value(self, value):
        self._clear_items()
        if isinstance(value, FractionWidget):
            ed0 = self._create_edit("")
            self._add_item(ed0)
            value.setParent(self)
            value.parent_slot = self
            self._add_item(value)
            ed1 = self._create_edit("")
            self._add_item(ed1)
            return

        if isinstance(value, RadicalWidget):
            ed0 = self._create_edit("")
            self._add_item(ed0)
            value.setParent(self)
            value.parent_slot = self
            self._add_item(value)
            ed1 = self._create_edit("")
            self._add_item(ed1)
            return

        val_str = str(value).strip() if value is not None else ""
        if not val_str:
            default_txt = "a" if self.is_num else "b"
            self._add_item(self._create_edit(default_txt))
            return

        tokens = parse_math_tokens(val_str)
        if len(tokens) == 1 and tokens[0][0] == 'text':
            frac_parts = _parse_fraction_str(tokens[0][1])
            if frac_parts:
                tokens = [('fraction', frac_parts[0], frac_parts[1])]

        has_compound = any(t[0] in ('fraction', 'radical') for t in tokens)
        if not has_compound:
            raw_text = "".join(t[1] for t in tokens)
            self._add_item(self._create_edit(raw_text))
        else:
            fid = getattr(self.parent_frac, 'fid', 1) if self.parent_frac else 1
            parent_edit = getattr(self.parent_frac, 'parent_edit', None) if self.parent_frac else None
            text_buf = ""
            for tok in tokens:
                if tok[0] == 'text':
                    text_buf += tok[1]
                elif tok[0] == 'fraction':
                    self._add_item(self._create_edit(text_buf))
                    text_buf = ""
                    fw = FractionWidget(num=tok[1], den=tok[2], fid=fid, parent_edit=parent_edit, parent_slot=self, is_result=self.is_result)
                    self._add_item(fw)
                elif tok[0] == 'radical':
                    self._add_item(self._create_edit(text_buf))
                    text_buf = ""
                    rw = RadicalWidget(radicand=tok[1], degree=tok[2], fid=fid, parent_edit=parent_edit, parent_slot=self, is_result=self.is_result, read_only=self.is_result)
                    self._add_item(rw)
            self._add_item(self._create_edit(text_buf))

    def _clear_items(self):
        for it in list(self.items):
            self.layout.removeWidget(it)
            it.deleteLater()
        self.items.clear()

    def _add_item(self, item):
        self.items.append(item)
        self.layout.addWidget(item)

    def _create_edit(self, text: str = "") -> MathSlotEdit:
        text = format_subscripts_and_superscripts(text)
        ed = MathSlotEdit(text, self)
        ed.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        ed.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if getattr(self, 'is_result', False):
            ed.setReadOnly(True)
            ed.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        ed.textChanged.connect(self._on_text_changed)

        font = getattr(self.parent_frac, '_math_font', None)
        if not isinstance(font, QFont):
            font = QFont("Times New Roman", 13)
            font.setItalic(True)
        ed.setFont(font)
        if hasattr(self.parent_frac, 'edit_style'):
            ed.setStyleSheet(self.parent_frac.edit_style)

        if self.parent_frac:
            orig_press = self.parent_frac._make_click_handler(ed)
            def _on_press(event):
                top = self.parent_frac.get_top_fraction() if self.parent_frac else None
                if top and top.parent_edit:
                    top.parent_edit._active_fraction_slot = self
                orig_press(event)
            ed.mousePressEvent = _on_press

            def _on_focus_in(event):
                try:
                    top = self.parent_frac.get_top_fraction() if self.parent_frac else None
                    if top:
                        if top.parent_edit:
                            top.parent_edit._active_fraction_slot = self
                        top.update()
                    if len(self.items) > 1 and not ed.text():
                        ed.setFixedWidth(12)
                        self._adjust_size()
                        if self.parent_frac:
                            self.parent_frac._adjust_size()
                except (RuntimeError, AttributeError):
                    pass
                try:
                    super(MathSlotEdit, ed).focusInEvent(event)
                except (RuntimeError, TypeError):
                    pass
            ed.focusInEvent = _on_focus_in

            def _on_focus_out(event):
                try:
                    top = self.parent_frac.get_top_fraction() if self.parent_frac else None
                    if top:
                        QTimer.singleShot(50, top.update)
                    if len(self.items) > 1 and not ed.text():
                        ed.setFixedWidth(0)
                        self._adjust_size()
                        if self.parent_frac:
                            self.parent_frac._adjust_size()
                except (RuntimeError, AttributeError):
                    pass
                try:
                    super(MathSlotEdit, ed).focusOutEvent(event)
                except (RuntimeError, TypeError):
                    pass
            ed.focusOutEvent = _on_focus_out

            ed.keyPressEvent = self.parent_frac._make_key_handler(ed, is_num=self.is_num, slot=self)
            ed.contextMenuEvent = self.parent_frac._make_context_menu_handler(ed)
        return ed

    def insert_fraction_at(self, edit_w: QLineEdit, num: str = "a", den: str = "b") -> 'FractionWidget':
        if edit_w not in self.items:
            return self.convert_to_fraction(num, den)

        idx = self.items.index(edit_w)
        if len(self.items) == 1 and (edit_w.text().strip() in ("", "a", "b")):
            return self.convert_to_fraction(num, den)

        sel = edit_w.selectedText().strip()
        if sel:
            pos_start = edit_w.selectionStart()
            pos_end = pos_start + len(edit_w.selectedText())
            prefix = edit_w.text()[:pos_start]
            suffix = edit_w.text()[pos_end:]
            num_val = sel
        else:
            pos = edit_w.cursorPosition()
            text_before = edit_w.text()[:pos]
            suffix = edit_w.text()[pos:]
            m = re.search(r'([a-zA-Z0-9_.]+)$', text_before.strip())
            if m:
                num_val = m.group(1)
                idx_m = text_before.rfind(num_val)
                prefix = text_before[:idx_m]
            elif pos == 0 and edit_w.text().strip() and edit_w.text().strip() not in ("a", "b"):
                num_val = edit_w.text().strip()
                prefix = ""
                suffix = ""
            else:
                num_val = num
                prefix = text_before

        edit_w.setText(prefix)
        fid = getattr(self.parent_frac, 'fid', 1) if self.parent_frac else 1
        parent_edit = getattr(self.parent_frac, 'parent_edit', None) if self.parent_frac else None
        fw = FractionWidget(num=num_val, den=den, fid=fid, parent_edit=parent_edit, parent_slot=self)
        ed_after = self._create_edit(suffix)

        self.items.insert(idx + 1, fw)
        self.layout.insertWidget(idx + 1, fw)
        self.items.insert(idx + 2, ed_after)
        self.layout.insertWidget(idx + 2, ed_after)

        fw.show()
        ed_after.show()

        if self.parent_frac:
            self.parent_frac._adjust_size()
            top = self.parent_frac.get_top_fraction()
            if top.parent_edit:
                top.parent_edit._active_fraction_slot = fw.den_slot
                top.parent_edit._on_frac_size_changed(top)

        fw.den_slot.first_edit().setFocus()
        fw.den_slot.first_edit().selectAll()
        return fw

    def convert_to_fraction(self, num: str = "a", den: str = "b") -> 'FractionWidget':
        self._clear_items()
        ed0 = self._create_edit("")
        self._add_item(ed0)
        fid = getattr(self.parent_frac, 'fid', 1) if self.parent_frac else 1
        parent_edit = getattr(self.parent_frac, 'parent_edit', None) if self.parent_frac else None
        fw = FractionWidget(num=num, den=den, fid=fid, parent_edit=parent_edit, parent_slot=self)
        self._add_item(fw)
        ed1 = self._create_edit("")
        self._add_item(ed1)
        if self.parent_frac:
            self.parent_frac._adjust_size()
            top = self.parent_frac.get_top_fraction()
            if top.parent_edit:
                top.parent_edit._active_fraction_slot = fw.den_slot
                top.parent_edit._on_frac_size_changed(top)
        return fw

    def convert_to_text(self, text: str = "") -> QLineEdit:
        self._clear_items()
        ed = self._create_edit(text)
        self._add_item(ed)
        if self.parent_frac:
            self.parent_frac._adjust_size()
            top = self.parent_frac.get_top_fraction()
            if top.parent_edit:
                top.parent_edit._on_frac_size_changed(top)
        return ed

    def remove_fraction_child(self, child_frac: 'FractionWidget'):
        if child_frac not in self.items:
            return
        idx = self.items.index(child_frac)
        prev_edit = self.items[idx - 1] if idx - 1 >= 0 and isinstance(self.items[idx - 1], (QLineEdit, QTextEdit)) else None
        next_edit = self.items[idx + 1] if idx + 1 < len(self.items) and isinstance(self.items[idx + 1], (QLineEdit, QTextEdit)) else None

        self.layout.removeWidget(child_frac)
        self.items.remove(child_frac)
        child_frac.deleteLater()

        if prev_edit and next_edit:
            cursor_pos = len(prev_edit.text())
            prev_edit.setText(prev_edit.text() + next_edit.text())
            self.layout.removeWidget(next_edit)
            self.items.remove(next_edit)
            next_edit.deleteLater()
            prev_edit.setFocus()
            prev_edit.setCursorPosition(cursor_pos)
        elif prev_edit:
            prev_edit.setFocus()
            prev_edit.setCursorPosition(len(prev_edit.text()))
        elif next_edit:
            next_edit.setFocus()
            next_edit.setCursorPosition(0)
        elif not self.items:
            self._add_item(self._create_edit("a" if self.is_num else "b"))

        if self.parent_frac:
            self.parent_frac._adjust_size()
            top = self.parent_frac.get_top_fraction()
            if top and top.parent_edit:
                top.parent_edit._on_frac_size_changed(top)

    def insert_radical_at(self, edit_w: QLineEdit, radicand: str = "a", degree: Optional[str] = None) -> 'RadicalWidget':
        if edit_w not in self.items or (len(self.items) == 1 and edit_w.text().strip() in ("", "a", "b")):
            self._clear_items()
            ed0 = self._create_edit("")
            self._add_item(ed0)
            fid = getattr(self.parent_frac, 'fid', 1) if self.parent_frac else 1
            parent_edit = getattr(self.parent_frac, 'parent_edit', None) if self.parent_frac else None
            rw = RadicalWidget(radicand=radicand, degree=degree, fid=fid, parent_edit=parent_edit, parent_slot=self)
            self._add_item(rw)
            ed1 = self._create_edit("")
            self._add_item(ed1)
            rw.show()
            self._adjust_size()
            if self.parent_frac:
                self.parent_frac._adjust_size()
                top = self.parent_frac.get_top_fraction()
                if top and top.parent_edit:
                    top.parent_edit._active_fraction_slot = self
                    top.parent_edit._on_frac_size_changed(top)
            if degree and rw.deg_edit:
                rw.deg_edit.setFocus()
                rw.deg_edit.selectAll()
            else:
                rw.rad_edit.setFocus()
                rw.rad_edit.selectAll()
            return rw

        idx = self.items.index(edit_w)
        sel = edit_w.selectedText().strip()
        if sel:
            pos_start = edit_w.selectionStart()
            pos_end = pos_start + len(edit_w.selectedText())
            prefix = edit_w.text()[:pos_start]
            suffix = edit_w.text()[pos_end:]
            rad_val = sel
        else:
            pos = edit_w.cursorPosition()
            text_before = edit_w.text()[:pos]
            suffix = edit_w.text()[pos:]
            m = re.search(r'([a-zA-Z0-9_.]+)$', text_before.strip())
            if m:
                rad_val = m.group(1)
                idx_m = text_before.rfind(rad_val)
                prefix = text_before[:idx_m]
            else:
                rad_val = radicand
                prefix = text_before

        edit_w.setText(prefix)
        fid = getattr(self.parent_frac, 'fid', 1) if self.parent_frac else 1
        parent_edit = getattr(self.parent_frac, 'parent_edit', None) if self.parent_frac else None
        rw = RadicalWidget(radicand=rad_val, degree=degree, fid=fid, parent_edit=parent_edit, parent_slot=self)
        ed_after = self._create_edit(suffix)

        self.items.insert(idx + 1, rw)
        self.layout.insertWidget(idx + 1, rw)
        self.items.insert(idx + 2, ed_after)
        self.layout.insertWidget(idx + 2, ed_after)

        rw.show()
        ed_after.show()

        if self.parent_frac:
            self.parent_frac._adjust_size()
            top = self.parent_frac.get_top_fraction()
            if top and top.parent_edit:
                top.parent_edit._active_fraction_slot = self
                top.parent_edit._on_frac_size_changed(top)

        if degree and rw.deg_edit:
            rw.deg_edit.setFocus()
            rw.deg_edit.selectAll()
        else:
            rw.rad_edit.setFocus()
            rw.rad_edit.selectAll()
        return rw

    def remove_radical_child(self, child_rad: 'RadicalWidget'):
        if child_rad not in self.items:
            return
        idx = self.items.index(child_rad)
        prev_edit = self.items[idx - 1] if idx - 1 >= 0 and isinstance(self.items[idx - 1], (QLineEdit, QTextEdit)) else None
        next_edit = self.items[idx + 1] if idx + 1 < len(self.items) and isinstance(self.items[idx + 1], (QLineEdit, QTextEdit)) else None

        self.layout.removeWidget(child_rad)
        self.items.remove(child_rad)
        child_rad.deleteLater()

        if prev_edit and next_edit:
            cursor_pos = len(prev_edit.text())
            prev_edit.setText(prev_edit.text() + next_edit.text())
            self.layout.removeWidget(next_edit)
            self.items.remove(next_edit)
            next_edit.deleteLater()
            prev_edit.setFocus()
            prev_edit.setCursorPosition(cursor_pos)
        elif prev_edit:
            prev_edit.setFocus()
            prev_edit.setCursorPosition(len(prev_edit.text()))
        elif next_edit:
            next_edit.setFocus()
            next_edit.setCursorPosition(0)
        elif not self.items:
            self._add_item(self._create_edit("a" if self.is_num else "b"))

        if self.parent_frac:
            self.parent_frac._adjust_size()
            top = self.parent_frac.get_top_fraction()
            if top and top.parent_edit:
                top.parent_edit._on_frac_size_changed(top)

    @property
    def child_frac(self):
        for it in self.items:
            if isinstance(it, FractionWidget):
                return it
        return None

    @child_frac.setter
    def child_frac(self, val):
        pass

    @property
    def child_fracs(self):
        return [it for it in self.items if isinstance(it, FractionWidget)]

    @property
    def child_rad(self):
        for it in self.items:
            if isinstance(it, RadicalWidget):
                return it
        return None

    @property
    def child_rads(self):
        return [it for it in self.items if isinstance(it, RadicalWidget)]

    @property
    def edit(self):
        for it in self.items:
            if isinstance(it, (QLineEdit, QTextEdit)):
                return it
        return None

    @edit.setter
    def edit(self, val):
        pass

    @property
    def edits(self):
        res = []
        for it in list(self.items):
            try:
                if isinstance(it, (QLineEdit, QTextEdit)) and not sip.isdeleted(it):
                    res.append(it)
            except Exception:
                pass
        return res

    def is_fraction(self) -> bool:
        for it in list(self.items):
            try:
                if isinstance(it, FractionWidget) and not sip.isdeleted(it):
                    return True
            except Exception:
                pass
        return False

    def is_radical(self) -> bool:
        for it in list(self.items):
            try:
                if isinstance(it, RadicalWidget) and not sip.isdeleted(it):
                    return True
            except Exception:
                pass
        return False

    def first_edit(self) -> Optional[QLineEdit]:
        for it in list(self.items):
            try:
                if sip.isdeleted(it):
                    continue
                if isinstance(it, (FractionWidget, RadicalWidget)):
                    fe = it.first_edit()
                    if fe is not None and not sip.isdeleted(fe):
                        return fe
                elif isinstance(it, (QLineEdit, QTextEdit)):
                    idx = self.items.index(it)
                    if not it.text() and idx + 1 < len(self.items):
                        nxt = self.items[idx + 1]
                        if isinstance(nxt, (FractionWidget, RadicalWidget)) and not sip.isdeleted(nxt):
                            fe = nxt.first_edit()
                            if fe is not None and not sip.isdeleted(fe):
                                return fe
                    return it
            except Exception:
                continue
        try:
            if hasattr(self, 'edit') and self.edit and not sip.isdeleted(self.edit):
                return self.edit
        except Exception:
            pass
        return None

    def last_edit(self) -> Optional[QLineEdit]:
        for it in reversed(list(self.items)):
            try:
                if sip.isdeleted(it):
                    continue
                if isinstance(it, (FractionWidget, RadicalWidget)):
                    le = it.last_edit()
                    if le is not None and not sip.isdeleted(le):
                        return le
                elif isinstance(it, (QLineEdit, QTextEdit)):
                    idx = self.items.index(it)
                    if not it.text() and idx - 1 >= 0:
                        prv = self.items[idx - 1]
                        if isinstance(prv, (FractionWidget, RadicalWidget)) and not sip.isdeleted(prv):
                            le = prv.last_edit()
                            if le is not None and not sip.isdeleted(le):
                                return le
                    return it
            except Exception:
                continue
        try:
            if hasattr(self, 'edit') and self.edit and not sip.isdeleted(self.edit):
                return self.edit
        except Exception:
            pass
        return None

    def navigate_after_child(self, child) -> bool:
        if child in self.items:
            idx = self.items.index(child)
            if idx + 1 < len(self.items):
                nxt = self.items[idx + 1]
                if isinstance(nxt, (QLineEdit, QTextEdit)):
                    nxt.setFocus()
                    nxt.setCursorPosition(0)
                    return True
                elif isinstance(nxt, (FractionWidget, RadicalWidget)):
                    fe = nxt.first_edit()
                    if fe:
                        fe.setFocus()
                        fe.setCursorPosition(0)
                        return True
        return False

    def navigate_before_child(self, child) -> bool:
        if child in self.items:
            idx = self.items.index(child)
            if idx - 1 >= 0:
                prev = self.items[idx - 1]
                if isinstance(prev, (QLineEdit, QTextEdit)):
                    prev.setFocus()
                    prev.setCursorPosition(len(prev.text()))
                    return True
                elif isinstance(prev, (FractionWidget, RadicalWidget)):
                    le = prev.last_edit()
                    if le:
                        le.setFocus()
                        le.setCursorPosition(len(le.text()))
                        return True
        return False

    def navigate_after_edit(self, edit_w) -> bool:
        if edit_w in self.items:
            idx = self.items.index(edit_w)
            if idx + 1 < len(self.items):
                nxt = self.items[idx + 1]
                if isinstance(nxt, (FractionWidget, RadicalWidget)):
                    fe = nxt.first_edit()
                    if fe:
                        fe.setFocus()
                        fe.setCursorPosition(0)
                        return True
                elif isinstance(nxt, (QLineEdit, QTextEdit)):
                    nxt.setFocus()
                    nxt.setCursorPosition(0)
                    return True
        return False

    def navigate_before_edit(self, edit_w) -> bool:
        if edit_w in self.items:
            idx = self.items.index(edit_w)
            if idx - 1 >= 0:
                prev = self.items[idx - 1]
                if isinstance(prev, (FractionWidget, RadicalWidget)):
                    le = prev.last_edit()
                    if le:
                        le.setFocus()
                        le.setCursorPosition(len(le.text()))
                        return True
                elif isinstance(prev, (QLineEdit, QTextEdit)):
                    prev.setFocus()
                    prev.setCursorPosition(len(prev.text()))
                    return True
        return False

    def text(self) -> str:
        parts = []
        for it in list(self.items):
            try:
                if sip.isdeleted(it):
                    continue
                if isinstance(it, (QLineEdit, QTextEdit)):
                    parts.append(it.text())
                elif isinstance(it, (FractionWidget, RadicalWidget)):
                    parts.append(it.text_expression())
            except Exception:
                continue
        return "".join(parts).strip()

    def _on_text_changed(self):
        for it in list(self.items):
            try:
                if sip.isdeleted(it):
                    continue
                if isinstance(it, (QLineEdit, QTextEdit)):
                    cur_text = it.text()
                    if '_' in cur_text or '^' in cur_text:
                        formatted = format_subscripts_and_superscripts(cur_text)
                        if formatted != cur_text:
                            cpos = it.cursorPosition()
                            it.setText(formatted)
                            it.setCursorPosition(min(cpos, len(formatted)))
                            self._just_subscripted = True
            except Exception:
                continue
        self._adjust_size()
        if self.parent_frac and not sip.isdeleted(self.parent_frac):
            self.parent_frac._on_text_changed()

    def content_size(self) -> tuple[int, int]:
        font = getattr(self.parent_frac, '_math_font', None)
        if isinstance(font, QFont):
            fm = QFontMetrics(font)
        else:
            fm = self.fontMetrics()

        valid_items = []
        for it in list(self.items):
            try:
                if not sip.isdeleted(it):
                    valid_items.append(it)
            except Exception:
                pass

        if not valid_items:
            return 14, max(16, fm.height() + 2)
        if len(valid_items) == 1 and isinstance(valid_items[0], (QLineEdit, QTextEdit)):
            ed = valid_items[0]
            txt = ed.text()
            w = max(14, fm.horizontalAdvance(txt if txt else ("a" if self.is_num else "b")) + 8)
            h = max(16, fm.height() + 2)
            if isinstance(ed, QTextEdit) and hasattr(ed, 'document') and ed.document().lineCount() > 1:
                doc_h = ed.document().documentLayout().documentSize().height()
                h = max(h, int(doc_h) + 2)
            return w, h

        total_w = 0
        max_h = max(16, fm.height() + 2)
        for it in valid_items:
            if isinstance(it, (FractionWidget, RadicalWidget)):
                w_i, h_i = it.width(), it.height()
                total_w += w_i
                if h_i > max_h:
                    max_h = h_i
            elif isinstance(it, (QLineEdit, QTextEdit)):
                txt = it.text()
                if txt:
                    w_i = fm.horizontalAdvance(txt) + 8
                elif it.hasFocus():
                    w_i = 12
                else:
                    w_i = 0
                h_i = max(16, fm.height() + 2)
                if isinstance(it, QTextEdit) and hasattr(it, 'document') and it.document().lineCount() > 1:
                    doc_h = it.document().documentLayout().documentSize().height()
                    h_i = max(h_i, int(doc_h) + 2)
                it.setFixedSize(w_i, h_i)
                total_w += w_i
                if h_i > max_h:
                    max_h = h_i

        spacing = self.layout.spacing() * max(0, len([it for it in valid_items if it.width() > 0]) - 1)
        total_w += spacing
        return max(total_w, 14), max(max_h, 16)

    def _adjust_size(self):
        if self.parent_frac and not sip.isdeleted(self.parent_frac):
            if not getattr(self.parent_frac, '_is_adjusting_size', False):
                self.parent_frac._adjust_size()
            return
        w, h = self.content_size()
        self.setFixedSize(w, h)
        self.updateGeometry()

    def update_style(self):
        font = getattr(self.parent_frac, '_math_font', None)
        if not isinstance(font, QFont):
            font = QFont("Times New Roman", 13)
            font.setItalic(True)
        for it in self.items:
            if isinstance(it, (FractionWidget, RadicalWidget)):
                it.update_style()
            elif isinstance(it, (QLineEdit, QTextEdit)):
                it.setFont(font)
                it.setAlignment(Qt.AlignmentFlag.AlignCenter)
                if hasattr(self.parent_frac, 'edit_style'):
                    it.setStyleSheet(self.parent_frac.edit_style)


class FractionWidget(QWidget):
    """
    Seamless inline 2D fraction widget embedded directly in CellInputEdit viewport.
    Displays numerator on top, horizontal fraction bar, and denominator on bottom.
    Supports arbitrarily nested fractions (fractions within fractions), smooth navigation,
    interactive conversion on typing '/', and full CAS evaluation.
    """
    def __init__(self, num: str = "a", den: str = "b", fid: int = 1, parent_edit=None, parent_slot=None, is_exponent: bool = False, is_result: bool = False):
        if parent_slot is not None:
            super().__init__(parent_slot)
        elif parent_edit is not None:
            super().__init__(parent_edit.viewport())
        else:
            super().__init__()
        self.fid = fid
        self.parent_edit = parent_edit
        self.parent_slot = parent_slot
        self.is_exponent = is_exponent
        self.is_result = is_result or (parent_slot and getattr(parent_slot, 'is_result', False))
        self.num_slot = None
        self.den_slot = None
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("background: transparent;")

        self._init_style_properties()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(1)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.num_slot = FractionSlot(initial_value=num, is_num=True, parent_frac=self, is_result=self.is_result)
        self.line = QFrame(self)
        self.line.setFrameShape(QFrame.Shape.HLine)
        self.line.setFixedHeight(1)
        self.line.setStyleSheet(f"background-color: {getattr(self, '_line_color', '#000000')}; border: none;")
        self.den_slot = FractionSlot(initial_value=den, is_num=False, parent_frac=self, is_result=self.is_result)

        layout.addWidget(self.num_slot, 0, Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.line)
        layout.addWidget(self.den_slot, 0, Qt.AlignmentFlag.AlignCenter)

        self.update_style()
        self._adjust_size()

    def paintEvent(self, event):
        super().paintEvent(event)
        top = self.get_top_fraction()
        if self == top and not getattr(self, 'is_result', False):
            fw = QApplication.focusWidget()
            has_child_focus = bool(fw and (self == fw or self.isAncestorOf(fw)))
            if has_child_focus:
                painter = QPainter(self)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                pen = QPen(QColor("#93c5fd"), 1, Qt.PenStyle.DashLine)
                painter.setPen(pen)
                painter.setBrush(QColor(239, 246, 255, 130))
                r = self.rect().adjusted(0, 0, -1, -1)
                painter.drawRoundedRect(r, 2.0, 2.0)

    def mousePressEvent(self, event):
        top = self.get_top_fraction()
        if top:
            top.update()
        if hasattr(self, 'line') and self.line:
            if event.pos().y() < self.line.y():
                self.num_slot.first_edit().setFocus()
            else:
                self.den_slot.first_edit().setFocus()
        super().mousePressEvent(event)

    @property
    def num_edit(self) -> Optional[QLineEdit]:
        """Backward compatibility: returns first editable line edit in numerator."""
        if self.num_slot and not sip.isdeleted(self.num_slot):
            return self.num_slot.first_edit()
        return None

    @property
    def den_edit(self) -> Optional[QLineEdit]:
        """Backward compatibility: returns first editable line edit in denominator."""
        if self.den_slot and not sip.isdeleted(self.den_slot):
            return self.den_slot.first_edit()
        return None

    def first_edit(self) -> Optional[QLineEdit]:
        if self.num_slot and not sip.isdeleted(self.num_slot):
            return self.num_slot.first_edit()
        return None

    def last_edit(self) -> Optional[QLineEdit]:
        if self.den_slot and not sip.isdeleted(self.den_slot):
            return self.den_slot.last_edit()
        return None

    def num_text(self) -> str:
        if self.num_slot and not sip.isdeleted(self.num_slot):
            return self.num_slot.text().strip() or "a"
        return "a"

    def den_text(self) -> str:
        if self.den_slot and not sip.isdeleted(self.den_slot):
            return self.den_slot.text().strip() or "b"
        return "b"

    def get_top_fraction(self) -> 'FractionWidget':
        cur = self
        while cur.parent_slot and not sip.isdeleted(cur.parent_slot) and cur.parent_slot.parent_frac and not sip.isdeleted(cur.parent_slot.parent_frac):
            cur = cur.parent_slot.parent_frac
        return cur

    def _make_click_handler(self, edit_widget):
        orig_press = edit_widget.mousePressEvent
        def handler(event):
            had_focus = edit_widget.hasFocus()
            orig_press(event)
            top = self.get_top_fraction()
            if top:
                top.update()
            if not had_focus and edit_widget.text().strip() in ("a", "b"):
                edit_widget.selectAll()
        return handler

    def _make_key_handler(self, edit_widget, is_num: bool, slot: FractionSlot):
        orig_key = edit_widget.keyPressEvent
        def handler(event):
            if edit_widget.isReadOnly():
                if event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier):
                    if event.key() in (Qt.Key.Key_Plus, Qt.Key.Key_Equal, Qt.Key.Key_Minus, Qt.Key.Key_Underscore, Qt.Key.Key_0):
                        top = self.get_top_fraction()
                        if top and top.parent_edit:
                            top.parent_edit.keyPressEvent(event)
                            return
                orig_key(event)
                return

            key = event.key()
            if key != Qt.Key.Key_Right:
                slot._just_subscripted = False

            # Typing '*' converts to middle dot '·'
            if event.text() in ('*', '·'):
                edit_widget.insert('·')
                event.accept()
                return

            # Typing '^' for superscript
            if event.text() == '^':
                slot._superscript_active = True
                event.accept()
                return
            if getattr(slot, '_superscript_active', False):
                ch = event.text()
                if ch in (' ', '\t') or key == Qt.Key.Key_Space:
                    slot._superscript_active = False
                    edit_widget.insert(' ')
                    event.accept()
                    return
                elif ch in SUPER_MAP or ch.lower() in SUPER_MAP:
                    edit_widget.insert(SUPER_MAP.get(ch, SUPER_MAP.get(ch.lower(), ch)))
                    slot._superscript_active = True
                    event.accept()
                    return
                elif ch in ('*', '·'):
                    edit_widget.insert('·')
                    slot._superscript_active = True
                    event.accept()
                    return
                elif ch:
                    slot._superscript_active = False

            # Enter / Return or inline evaluation shortcuts
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                top = self.get_top_fraction()
                if top and top.parent_edit:
                    if event.modifiers() & (Qt.KeyboardModifier.ShiftModifier | Qt.KeyboardModifier.AltModifier):
                        top.parent_edit._handle_inline_evaluation()
                    elif event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier):
                        top.parent_edit.executeRequested.emit()
                    else:
                        top.parent_edit.keyPressEvent(event)
                event.accept()
                return

            if key == Qt.Key.Key_Equal and (
                (event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier | Qt.KeyboardModifier.MetaModifier)) or
                ((event.modifiers() & Qt.KeyboardModifier.ShiftModifier) and event.text() != '+')
            ):
                top = self.get_top_fraction()
                if top and top.parent_edit:
                    top.parent_edit._handle_inline_evaluation()
                event.accept()
                return

            # Slash '/' creates nested fraction in denominator, or jumps to denominator from numerator
            if event.text() == '/' and not (event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier)):
                if not is_num:
                    # Typing / in denominator creates a nested fraction at current edit
                    slot.insert_fraction_at(edit_widget)
                    event.accept()
                    return
                else:
                    # In numerator: if text is selected, create nested fraction in numerator
                    sel = edit_widget.selectedText().strip()
                    if sel:
                        slot.insert_fraction_at(edit_widget, num=sel, den="b")
                        event.accept()
                        return
                    else:
                        # Otherwise jump to denominator
                        self.den_slot.first_edit().setFocus()
                        self.den_slot.first_edit().selectAll()
                        event.accept()
                        return

            # Tab / Backtab navigation
            if key == Qt.Key.Key_Tab:
                if is_num:
                    self.den_slot.first_edit().setFocus()
                    self.den_slot.first_edit().selectAll()
                    event.accept()
                    return
                else:
                    if slot.navigate_after_edit(edit_widget):
                        event.accept()
                        return
                    self.navigate_after()
                    event.accept()
                    return

            if key == Qt.Key.Key_Backtab:
                if not is_num:
                    if slot.navigate_before_edit(edit_widget):
                        event.accept()
                        return
                    self.num_slot.last_edit().setFocus()
                    self.num_slot.last_edit().selectAll()
                    event.accept()
                    return
                else:
                    if slot.navigate_before_edit(edit_widget):
                        event.accept()
                        return
                    self.navigate_before()
                    event.accept()
                    return

            # Down arrow: move from numerator down into denominator, or exit if already at bottom
            if key == Qt.Key.Key_Down:
                if isinstance(edit_widget, QTextEdit) and not _is_cursor_on_last_line(edit_widget):
                    orig_key(event)
                    return
                if is_num:
                    cpos = edit_widget.cursorPosition()
                    target = self.den_slot.first_edit()
                    target.setFocus()
                    target.setCursorPosition(min(cpos, len(target.text())))
                    top = self.get_top_fraction()
                    if top:
                        top.update()
                    event.accept()
                    return
                else:
                    if self.parent_slot and self.parent_slot.is_num:
                        target = self.parent_slot.parent_frac.den_slot.first_edit()
                        cpos = edit_widget.cursorPosition()
                        target.setFocus()
                        target.setCursorPosition(min(cpos, len(target.text())))
                        top = self.get_top_fraction()
                        if top:
                            top.update()
                        event.accept()
                        return
                    else:
                        self.navigate_after()
                        event.accept()
                        return

            # Up arrow: move from denominator up into numerator, or exit if already at top
            if key == Qt.Key.Key_Up:
                if isinstance(edit_widget, QTextEdit) and not _is_cursor_on_first_line(edit_widget):
                    orig_key(event)
                    return
                if not is_num:
                    cpos = edit_widget.cursorPosition()
                    target = self.num_slot.first_edit()
                    target.setFocus()
                    target.setCursorPosition(min(cpos, len(target.text())))
                    top = self.get_top_fraction()
                    if top:
                        top.update()
                    event.accept()
                    return
                else:
                    if self.parent_slot and not self.parent_slot.is_num:
                        target = self.parent_slot.parent_frac.num_slot.first_edit()
                        cpos = edit_widget.cursorPosition()
                        target.setFocus()
                        target.setCursorPosition(min(cpos, len(target.text())))
                        top = self.get_top_fraction()
                        if top:
                            top.update()
                        event.accept()
                        return
                    else:
                        self.navigate_before()
                        event.accept()
                        return

            is_sup_char = lambda c: c in SUPER_MAP.values() or c in ('·', '⋅')

            # Right arrow navigation
            if key == Qt.Key.Key_Right:
                cpos = edit_widget.cursorPosition()
                txt = edit_widget.text()
                if getattr(slot, '_superscript_active', False):
                    if cpos == len(txt):
                        slot._superscript_active = False
                        event.accept()
                        return
                    else:
                        new_pos = cpos + 1
                        edit_widget.setCursorPosition(new_pos)
                        char_left = txt[new_pos - 1] if new_pos > 0 else ""
                        if not is_sup_char(char_left):
                            slot._superscript_active = False
                        event.accept()
                        return
                else:
                    if cpos == len(txt):
                        if getattr(slot, '_just_subscripted', False):
                            slot._just_subscripted = False
                            event.accept()
                            return
                        if txt.count('(') > txt.count(')') or txt.count('[') > txt.count(']'):
                            event.accept()
                            return
                        if slot.navigate_after_edit(edit_widget):
                            event.accept()
                            return
                        self.navigate_after()
                        event.accept()
                        return
                    else:
                        new_pos = cpos + 1
                        edit_widget.setCursorPosition(new_pos)
                        char_left = txt[new_pos - 1] if new_pos > 0 else ""
                        char_right = txt[new_pos] if new_pos < len(txt) else ""
                        if is_sup_char(char_left) and is_sup_char(char_right):
                            slot._superscript_active = True
                        else:
                            slot._superscript_active = False
                        event.accept()
                        return

            # Left arrow navigation
            if key == Qt.Key.Key_Left:
                cpos = edit_widget.cursorPosition()
                txt = edit_widget.text()
                if cpos == 0:
                    slot._superscript_active = False
                    if slot.navigate_before_edit(edit_widget):
                        event.accept()
                        return
                    self.navigate_before()
                    event.accept()
                    return
                else:
                    new_pos = cpos - 1
                    edit_widget.setCursorPosition(new_pos)
                    char_left = txt[new_pos - 1] if new_pos > 0 else ""
                    if is_sup_char(char_left):
                        slot._superscript_active = True
                    else:
                        slot._superscript_active = False
                    event.accept()
                    return

            # Backspace handling
            if key == Qt.Key.Key_Backspace:
                cpos = edit_widget.cursorPosition()
                txt = edit_widget.text()
                if not txt:
                    slot._superscript_active = False
                    if self.parent_slot:
                        self.parent_slot.remove_fraction_child(self)
                    else:
                        top = self.get_top_fraction()
                        if top.parent_edit:
                            top.parent_edit.remove_fraction(top.fid)
                    event.accept()
                    return
                elif cpos > 0 and not edit_widget.hasSelectedText():
                    orig_key(event)
                    new_pos = edit_widget.cursorPosition()
                    new_txt = edit_widget.text()
                    char_left = new_txt[new_pos - 1] if new_pos > 0 else ""
                    if is_sup_char(char_left):
                        slot._superscript_active = True
                    else:
                        slot._superscript_active = False
                    return

            orig_key(event)
        return handler

    def navigate_after(self):
        if self.parent_slot and self.parent_slot.parent_frac:
            if self.parent_slot.navigate_after_child(self):
                return
            self.parent_slot.parent_frac.navigate_after()
        elif self.parent_edit:
            self.parent_edit.move_cursor_after_fraction(self.fid)

    def navigate_before(self):
        if self.parent_slot and self.parent_slot.parent_frac:
            if self.parent_slot.navigate_before_child(self):
                return
            self.parent_slot.parent_frac.navigate_before()
        elif self.parent_edit:
            self.parent_edit.move_cursor_before_fraction(self.fid)

    def _on_text_changed(self):
        self._adjust_size()
        top = self.get_top_fraction()
        if top.parent_edit:
            top.parent_edit._on_frac_size_changed(top)

    def _init_style_properties(self):
        sz = 13
        fam = "Times New Roman"
        is_dark = False
        top = self.get_top_fraction()
        parent_edit = top.parent_edit if top else self.parent_edit
        if parent_edit and parent_edit.parent_cell:
            cell = parent_edit.parent_cell
            sz = getattr(cell, 'current_font_size', 13)
            fam = getattr(cell, 'current_font_family', "Times New Roman")
            factor = getattr(cell, 'zoom_factor', 1.0)
            sz = max(8, round(sz * factor))
            is_dark = (getattr(cell, 'theme_mode', 'light') == 'dark')

        # Scaling for nesting level
        level = 0
        p = self.parent_slot
        while p:
            level += 1
            if p.parent_frac:
                p = getattr(p.parent_frac, 'parent_slot', None)
            else:
                break
        exp_scale = 0.72 if getattr(self, 'is_exponent', False) else 1.0
        scaled_sz = max(7, round(sz * exp_scale * (0.85 ** level)))

        if getattr(self, 'is_result', False):
            from .theme import Theme
            color = Theme.DARK_MATH_BLUE if is_dark else Theme.OPENMATH_MATH_BLUE
            line_color = color
        else:
            color = "#f8fafc" if is_dark else "#000000"
            line_color = "#94a3b8" if is_dark else "#000000"

        is_italic = True
        if self.parent_edit:
            cell = getattr(self.parent_edit, 'parent_cell', None)
            mode_nonexec = getattr(cell, 'MODE_NONEXEC_MATH', 'nonexec_math')
            mode_text = getattr(cell, 'MODE_TEXT', 'text')
            cur_mode = self.parent_edit.get_mode_at_cursor()
            cell_mode = getattr(cell, 'input_mode', None)
            if cell_mode in (mode_nonexec, mode_text) or cur_mode in (mode_nonexec, mode_text):
                is_italic = False

        font = QFont(fam, scaled_sz)
        font.setItalic(is_italic)
        self._math_font = font

        self.edit_style = f"""
            QLineEdit, QTextEdit {{
                background: transparent;
                border: none;
                padding: 0px;
                margin: 0px;
                color: {color};
                font-family: "{fam}";
                font-size: {scaled_sz}pt;
                font-style: {'italic' if is_italic else 'normal'};
                selection-background-color: #2563eb;
                selection-color: #ffffff;
            }}
        """
        self._line_color = line_color

    def update_style(self):
        self._init_style_properties()
        if hasattr(self, 'line') and self.line:
            self.line.setStyleSheet(f"background-color: {getattr(self, '_line_color', '#000000')}; border: none;")
        if getattr(self, 'num_slot', None) is not None:
            self.num_slot.update_style()
        if getattr(self, 'den_slot', None) is not None:
            self.den_slot.update_style()
        self._adjust_size()

    def _get_available_width(self) -> int:
        top = self.get_top_fraction()
        parent_edit = top.parent_edit if top else self.parent_edit
        if parent_edit and hasattr(parent_edit, 'viewport'):
            vw = parent_edit.viewport().width()
            if vw > 100:
                curr_x = top.x() if top.x() > 0 else 0
                avail = vw - curr_x - 16
                if avail < 120:
                    avail = max(120, vw - 36)
                return avail
        return 800

    def _adjust_size(self):
        if getattr(self, 'num_slot', None) is None or getattr(self, 'den_slot', None) is None:
            return
        if getattr(self, '_is_adjusting_size', False):
            return
        self._is_adjusting_size = True
        try:
            avail_w = self._get_available_width()
            pad = 4 if getattr(self, 'is_exponent', False) else 8
            min_w = 14 if getattr(self, 'is_exponent', False) else 20
            max_slot_w = max(40, avail_w - pad)

            w_num, h_num = self.num_slot.content_size()
            if w_num > max_slot_w and len(self.num_slot.items) == 1 and isinstance(self.num_slot.items[0], (QLineEdit, QTextEdit)):
                ed = self.num_slot.items[0]
                if hasattr(ed, 'document'):
                    ed.document().setTextWidth(max_slot_w)
                    doc_h = ed.document().documentLayout().documentSize().height()
                    h_num = max(16, int(doc_h) + 2)
                    w_num = max_slot_w
            elif len(self.num_slot.items) == 1 and isinstance(self.num_slot.items[0], QTextEdit):
                self.num_slot.items[0].document().setTextWidth(-1)

            w_den, h_den = self.den_slot.content_size()
            if w_den > max_slot_w and len(self.den_slot.items) == 1 and isinstance(self.den_slot.items[0], (QLineEdit, QTextEdit)):
                ed = self.den_slot.items[0]
                if hasattr(ed, 'document'):
                    ed.document().setTextWidth(max_slot_w)
                    doc_h = ed.document().documentLayout().documentSize().height()
                    h_den = max(16, int(doc_h) + 2)
                    w_den = max_slot_w
            elif len(self.den_slot.items) == 1 and isinstance(self.den_slot.items[0], QTextEdit):
                self.den_slot.items[0].document().setTextWidth(-1)

            raw_w = max(min_w, max(w_num, w_den) + pad)
            w = min(raw_w, avail_w)
            total_h = h_num + h_den + 3

            # Match numerator and denominator slot widths to full fraction bar width for perfect horizontal centering
            self.num_slot.setFixedSize(w, h_num)
            self.den_slot.setFixedSize(w, h_den)

            if len(self.num_slot.items) == 1 and isinstance(self.num_slot.items[0], (QLineEdit, QTextEdit)):
                self.num_slot.items[0].setFixedSize(w, h_num)
                if hasattr(self.num_slot.items[0], 'document'):
                    self.num_slot.items[0].document().setTextWidth(w)
                    self.num_slot.items[0].setAlignment(Qt.AlignmentFlag.AlignCenter)
            if len(self.den_slot.items) == 1 and isinstance(self.den_slot.items[0], (QLineEdit, QTextEdit)):
                self.den_slot.items[0].setFixedSize(w, h_den)
                if hasattr(self.den_slot.items[0], 'document'):
                    self.den_slot.items[0].document().setTextWidth(w)
                    self.den_slot.items[0].setAlignment(Qt.AlignmentFlag.AlignCenter)

            self.line.setFixedSize(w, 1)
            self.setFixedSize(w, total_h)
            self.updateGeometry()

            if self.parent_slot and self.parent_slot.parent_frac:
                self.parent_slot._adjust_size()
                self.parent_slot.parent_frac._adjust_size()
            else:
                top = self.get_top_fraction()
                if top and top.parent_edit:
                    top.parent_edit._on_frac_size_changed(top)
        finally:
            self._is_adjusting_size = False

    def get_focused_slot(self) -> Optional['FractionSlot']:
        for slot in (getattr(self, 'num_slot', None), getattr(self, 'den_slot', None)):
            if slot is None:
                continue
            try:
                if sip.isdeleted(slot):
                    continue
                for it in list(slot.items):
                    try:
                        if sip.isdeleted(it):
                            continue
                        if isinstance(it, FractionWidget):
                            sub = it.get_focused_slot()
                            if sub is not None and not sip.isdeleted(sub):
                                return sub
                        elif isinstance(it, RadicalWidget):
                            if (it.rad_edit and it.rad_edit.hasFocus()) or (it.deg_edit and it.deg_edit.hasFocus()):
                                return slot
                        elif isinstance(it, (QLineEdit, QTextEdit)) and it.hasFocus():
                            return slot
                    except Exception:
                        continue
            except Exception:
                continue
        return None

    def text_expression(self) -> str:
        num = self.num_text()
        den = self.den_text()
        if getattr(self, 'is_exponent', False):
            return f"^(({num})/({den}))"
        return f"({num})/({den})"

    def contextMenuEvent(self, event):
        self.show_context_menu(event.globalPos(), None)
        event.accept()

    def _make_context_menu_handler(self, edit_widget):
        def handler(event):
            self.show_context_menu(event.globalPos(), edit_widget)
            event.accept()
        return handler

    def show_context_menu(self, global_pos, source_edit=None):
        menu = QMenu(self)
        Theme.apply_menu_style(menu, getattr(self, 'theme_mode', 'light'))

        # 1. Convert to Decimal
        can_convert_dec = False
        dec_str = ""
        try:
            import sympy as sp
            val = sp.sympify(self.text_expression())
            flt = float(val)
            if flt.is_integer():
                raw_dec = str(int(flt))
            else:
                raw_dec = f"{flt:.10f}".rstrip("0").rstrip(".")
            from cas_engine.formatter import MathFormatter
            dec_str = MathFormatter.format_decimal(raw_dec)
            can_convert_dec = True
        except Exception:
            try:
                import sympy as sp
                val = sp.sympify(self.text_expression())
                n_val = sp.N(val, 10)
                from cas_engine.formatter import MathFormatter
                dec_str = MathFormatter.format_decimal(sp.sstr(n_val))
                can_convert_dec = True
            except Exception:
                can_convert_dec = False

        if can_convert_dec:
            act_dec = menu.addAction(f"Convert to Decimal ({dec_str})")
            act_dec.triggered.connect(lambda: self.convert_to_decimal(dec_str))
        else:
            act_dec = menu.addAction("Convert to Decimal")
            act_dec.setEnabled(False)

        # 2. Simplify
        can_simplify = False
        simplified_n = ""
        simplified_d = ""
        is_whole = False
        try:
            import sympy as sp
            cur_expr = sp.sympify(self.text_expression())
            sim_expr = sp.simplify(cur_expr)
            n, d = sp.fraction(sim_expr)
            s_n = sp.sstr(n)
            s_d = sp.sstr(d)
            cur_n = self.num_text()
            cur_d = self.den_text()

            if d == 1 or d == -1:
                res_whole = s_n if d == 1 else sp.sstr(-n)
                if cur_d != "1" or cur_n != res_whole:
                    can_simplify = True
                    is_whole = True
                    simplified_n = res_whole
            else:
                if s_n != cur_n or s_d != cur_d:
                    can_simplify = True
                    simplified_n = s_n
                    simplified_d = s_d
        except Exception:
            can_simplify = False

        if can_simplify:
            label = f"Simplify ({simplified_n})" if is_whole else f"Simplify ({simplified_n}/{simplified_d})"
            act_simp = menu.addAction(label)
            act_simp.triggered.connect(lambda: self.simplify(is_whole, simplified_n, simplified_d))
        else:
            act_simp = menu.addAction("Simplify (Already in simplest form)")
            act_simp.setEnabled(False)

        menu.addSeparator()

        # Invert Fraction
        act_inv = menu.addAction("Invert Fraction")
        act_inv.triggered.connect(self.invert_fraction)

        menu.addSeparator()

        if source_edit:
            act_cut = menu.addAction("Cut")
            act_cut.setEnabled(source_edit.hasSelectedText())
            act_cut.triggered.connect(source_edit.cut)

            act_copy = menu.addAction("Copy")
            act_copy.setEnabled(source_edit.hasSelectedText())
            act_copy.triggered.connect(source_edit.copy)

            act_paste = menu.addAction("Paste")
            act_paste.triggered.connect(source_edit.paste)

            act_sel = menu.addAction("Select All")
            act_sel.triggered.connect(source_edit.selectAll)

            menu.addSeparator()

        act_del = menu.addAction("Delete Fraction")
        def _delete_frac():
            if self.parent_slot:
                self.parent_slot.convert_to_text("")
            else:
                top = self.get_top_fraction()
                if top.parent_edit:
                    top.parent_edit.remove_fraction(top.fid)
        act_del.triggered.connect(_delete_frac)

        menu.exec(global_pos)

    def convert_to_decimal(self, dec_str: str = ""):
        num = self.num_text() or "1"
        den = self.den_text() or "1"
        if not dec_str:
            try:
                import sympy as sp
                val = sp.sympify(self.text_expression())
                flt = float(val)
                raw_dec = str(int(flt)) if flt.is_integer() else f"{flt:.10f}".rstrip("0").rstrip(".")
                from cas_engine.formatter import MathFormatter
                dec_str = MathFormatter.format_decimal(raw_dec)
            except Exception:
                return
        if self.parent_slot:
            self.parent_slot.convert_to_text(dec_str)
        else:
            top = self.get_top_fraction()
            if top.parent_edit:
                if not hasattr(top.parent_edit, '_frac_history'):
                    top.parent_edit._frac_history = {}
                top.parent_edit._frac_history[dec_str] = (num, den)
                top.parent_edit._frac_history[dec_str.replace(',', '.')] = (num, den)
                top.parent_edit._frac_history[dec_str.replace('.', ',')] = (num, den)
                top.parent_edit.replace_fraction_with_text(top.fid, dec_str)

    def simplify(self, is_whole: bool = False, sim_n: str = "", sim_d: str = ""):
        if not sim_n:
            try:
                import sympy as sp
                cur_expr = sp.sympify(self.text_expression())
                sim_expr = sp.simplify(cur_expr)
                n, d = sp.fraction(sim_expr)
                if d == 1 or d == -1:
                    is_whole = True
                    sim_n = sp.sstr(n if d == 1 else -n)
                else:
                    is_whole = False
                    sim_n = sp.sstr(n)
                    sim_d = sp.sstr(d)
            except Exception:
                return

        if is_whole:
            if self.parent_slot:
                self.parent_slot.convert_to_text(sim_n)
            else:
                top = self.get_top_fraction()
                if top.parent_edit:
                    top.parent_edit.replace_fraction_with_text(top.fid, sim_n)
        else:
            self.num_slot.convert_to_text(sim_n)
            self.den_slot.convert_to_text(sim_d)
            self._adjust_size()
            top = self.get_top_fraction()
            if top.parent_edit:
                top.parent_edit._on_frac_size_changed(top)

    def invert_fraction(self):
        n_is_frac = self.num_slot.is_fraction()
        d_is_frac = self.den_slot.is_fraction()
        n_text = self.num_slot.text()
        d_text = self.den_slot.text()

        if d_is_frac:
            self.num_slot.convert_to_fraction(self.den_slot.child_frac.num_text(), self.den_slot.child_frac.den_text())
        else:
            self.num_slot.convert_to_text(d_text)

        if n_is_frac:
            self.den_slot.convert_to_fraction(self.num_slot.child_frac.num_text(), self.num_slot.child_frac.den_text())
        else:
            self.den_slot.convert_to_text(n_text)

        self._adjust_size()
        top = self.get_top_fraction()
        if top.parent_edit:
            top.parent_edit._on_frac_size_changed(top)


class DefiniteIntegralWidget(QWidget):
    """
    Seamless inline 2D definite integral widget embedded directly in CellInputEdit viewport.
    Displays tall integral sign ∫, stacked limits (b on top, a on bottom), and integrand f
    (with optional differential dx).
    All fields (a, b, f) are editable QLineEdits that smoothly resize and support Tab/Arrow
    navigation and CAS evaluation.
    """
    def __init__(self, a: str = "a", b: str = "b", f: str = "f", var: str = "x",
                 show_differential: bool = False, fid: int = 1, parent_edit=None):
        super().__init__(parent_edit.viewport() if parent_edit else None)
        self.fid = fid
        self.parent_edit = parent_edit
        self.show_differential = show_differential
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("background: transparent;")

        h_layout = QHBoxLayout(self)
        h_layout.setContentsMargins(2, 0, 2, 0)
        h_layout.setSpacing(2)

        # 1. Integral Symbol ∫
        self.lbl_int = QLabel("∫", self)
        self.lbl_int.setAlignment(Qt.AlignmentFlag.AlignCenter)
        h_layout.addWidget(self.lbl_int)

        # 2. Limits stacked vertically: b on top, a on bottom
        self.limits_w = QWidget(self)
        limits_layout = QVBoxLayout(self.limits_w)
        limits_layout.setContentsMargins(0, 0, 0, 0)
        limits_layout.setSpacing(1)

        self.b_edit = QLineEdit(b, self)
        self.a_edit = QLineEdit(a, self)
        limits_layout.addWidget(self.b_edit)
        limits_layout.addWidget(self.a_edit)
        h_layout.addWidget(self.limits_w)

        # 3. Integrand f
        self.f_edit = MathSlotEdit(f, self)
        h_layout.addWidget(self.f_edit)

        # 4. Optional differential dx
        self.lbl_d = QLabel(" d", self)
        self.lbl_d.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.x_edit = QLineEdit(var, self)
        h_layout.addWidget(self.lbl_d)
        h_layout.addWidget(self.x_edit)
        if not self.show_differential:
            self.lbl_d.setVisible(False)
            self.x_edit.setVisible(False)

        # Signals
        self.b_edit.textChanged.connect(self._on_text_changed)
        self.a_edit.textChanged.connect(self._on_text_changed)
        self.f_edit.textChanged.connect(self._on_text_changed)
        self.x_edit.textChanged.connect(self._on_text_changed)

        # Click handlers
        self.b_edit.mousePressEvent = self._make_click_handler(self.b_edit)
        self.a_edit.mousePressEvent = self._make_click_handler(self.a_edit)
        self.f_edit.mousePressEvent = self._make_click_handler(self.f_edit)
        self.x_edit.mousePressEvent = self._make_click_handler(self.x_edit)

        # Key handlers
        self.b_edit.keyPressEvent = self._make_key_handler(self.b_edit, role="b")
        self.a_edit.keyPressEvent = self._make_key_handler(self.a_edit, role="a")
        self.f_edit.keyPressEvent = self._make_key_handler(self.f_edit, role="f")
        self.x_edit.keyPressEvent = self._make_key_handler(self.x_edit, role="x")

        # Context menu
        self.b_edit.contextMenuEvent = self._make_context_menu_handler(self.b_edit)
        self.a_edit.contextMenuEvent = self._make_context_menu_handler(self.a_edit)
        self.f_edit.contextMenuEvent = self._make_context_menu_handler(self.f_edit)
        self.x_edit.contextMenuEvent = self._make_context_menu_handler(self.x_edit)

        self.update_style()
        self._adjust_size()

    def _make_click_handler(self, edit_widget):
        orig_press = edit_widget.mousePressEvent
        def handler(event):
            had_focus = edit_widget.hasFocus()
            orig_press(event)
            self.update()
            if not had_focus and edit_widget.text().strip() in ("a", "b", "f", "x"):
                edit_widget.selectAll()
        return handler

    def _make_key_handler(self, edit_widget, role):
        orig_key = edit_widget.keyPressEvent
        def handler(event):
            if edit_widget.isReadOnly():
                if event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier):
                    if event.key() in (Qt.Key.Key_Plus, Qt.Key.Key_Equal, Qt.Key.Key_Minus, Qt.Key.Key_Underscore, Qt.Key.Key_0):
                        if self.parent_edit:
                            self.parent_edit.keyPressEvent(event)
                            return
                orig_key(event)
                return

            key = event.key()

            # Enter / Return or inline evaluation shortcuts
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if self.parent_edit:
                    if event.modifiers() & (Qt.KeyboardModifier.ShiftModifier | Qt.KeyboardModifier.AltModifier):
                        self.parent_edit._handle_inline_evaluation()
                    elif event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier):
                        self.parent_edit.executeRequested.emit()
                    else:
                        self.parent_edit.keyPressEvent(event)
                event.accept()
                return

            if key == Qt.Key.Key_Equal and (
                (event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier | Qt.KeyboardModifier.MetaModifier)) or
                ((event.modifiers() & Qt.KeyboardModifier.ShiftModifier) and event.text() != '+')
            ):
                if self.parent_edit:
                    self.parent_edit._handle_inline_evaluation()
                event.accept()
                return

            # Tab navigation: a -> b -> f -> (x) -> after widget
            if key == Qt.Key.Key_Tab:
                if role == "a":
                    self.b_edit.setFocus()
                    self.b_edit.selectAll()
                elif role == "b":
                    self.f_edit.setFocus()
                    self.f_edit.selectAll()
                elif role == "f":
                    if self.show_differential:
                        self.x_edit.setFocus()
                        self.x_edit.selectAll()
                    else:
                        if self.parent_edit:
                            self.parent_edit.move_cursor_after_fraction(self.fid)
                elif role == "x":
                    if self.parent_edit:
                        self.parent_edit.move_cursor_after_fraction(self.fid)
                event.accept()
                return

            # Backtab (Shift+Tab) navigation: (x) -> f -> b -> a -> before widget
            if key == Qt.Key.Key_Backtab:
                if role == "x":
                    self.f_edit.setFocus()
                    self.f_edit.selectAll()
                elif role == "f":
                    self.b_edit.setFocus()
                    self.b_edit.selectAll()
                elif role == "b":
                    self.a_edit.setFocus()
                    self.a_edit.selectAll()
                elif role == "a":
                    if self.parent_edit:
                        self.parent_edit.move_cursor_before_fraction(self.fid)
                event.accept()
                return

            # Up / Down arrows:
            if key == Qt.Key.Key_Up:
                if role == "f" and isinstance(edit_widget, QTextEdit):
                    if not _is_cursor_on_first_line(edit_widget):
                        orig_key(event)
                        return
                if role == "a":
                    cpos = edit_widget.cursorPosition()
                    self.b_edit.setFocus()
                    self.b_edit.setCursorPosition(min(cpos, len(self.b_edit.text())))
                    self.update()
                    event.accept()
                    return
                elif role in ("f", "x"):
                    cpos = edit_widget.cursorPosition()
                    self.b_edit.setFocus()
                    self.b_edit.setCursorPosition(min(cpos, len(self.b_edit.text())))
                    self.update()
                    event.accept()
                    return
            if key == Qt.Key.Key_Down:
                if role == "f" and isinstance(edit_widget, QTextEdit):
                    if not _is_cursor_on_last_line(edit_widget):
                        orig_key(event)
                        return
                if role == "b":
                    cpos = edit_widget.cursorPosition()
                    self.a_edit.setFocus()
                    self.a_edit.setCursorPosition(min(cpos, len(self.a_edit.text())))
                    self.update()
                    event.accept()
                    return
                elif role in ("f", "x"):
                    cpos = edit_widget.cursorPosition()
                    self.a_edit.setFocus()
                    self.a_edit.setCursorPosition(min(cpos, len(self.a_edit.text())))
                    self.update()
                    event.accept()
                    return

            # Right arrow at end of text:
            if key == Qt.Key.Key_Right and edit_widget.cursorPosition() == len(edit_widget.text()):
                if role in ("a", "b"):
                    self.f_edit.setFocus()
                    self.f_edit.setCursorPosition(0)
                elif role == "f":
                    if self.show_differential:
                        self.x_edit.setFocus()
                        self.x_edit.setCursorPosition(0)
                    else:
                        if self.parent_edit:
                            self.parent_edit.move_cursor_after_fraction(self.fid)
                elif role == "x":
                    if self.parent_edit:
                        self.parent_edit.move_cursor_after_fraction(self.fid)
                event.accept()
                return

            # Left arrow at start of text:
            if key == Qt.Key.Key_Left and edit_widget.cursorPosition() == 0:
                if role in ("a", "b"):
                    if self.parent_edit:
                        self.parent_edit.move_cursor_before_fraction(self.fid)
                elif role == "f":
                    self.b_edit.setFocus()
                    self.b_edit.setCursorPosition(len(self.b_edit.text()))
                elif role == "x":
                    self.f_edit.setFocus()
                    self.f_edit.setCursorPosition(len(self.f_edit.text()))
                event.accept()
                return

            # Backspace on empty text: delete integral widget
            if key == Qt.Key.Key_Backspace and not edit_widget.text():
                if self.parent_edit:
                    self.parent_edit.remove_fraction(self.fid)
                event.accept()
                return

            orig_key(event)
        return handler

    def paintEvent(self, event):
        super().paintEvent(event)
        fw = QApplication.focusWidget()
        has_child_focus = bool(fw and (self == fw or self.isAncestorOf(fw)))
        if has_child_focus:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            pen = QPen(QColor("#93c5fd"), 1, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.setBrush(QColor(239, 246, 255, 130))
            r = self.rect().adjusted(0, 0, -1, -1)
            painter.drawRoundedRect(r, 2.0, 2.0)

    def contextMenuEvent(self, event):
        self.show_context_menu(event.globalPos(), None)
        event.accept()

    def _make_context_menu_handler(self, edit_widget):
        def handler(event):
            self.show_context_menu(event.globalPos(), edit_widget)
            event.accept()
        return handler

    def show_context_menu(self, global_pos, source_edit=None):
        menu = QMenu(self)
        theme_mode = 'light'
        if self.parent_edit and self.parent_edit.parent_cell:
            theme_mode = getattr(self.parent_edit.parent_cell, 'theme_mode', 'light')
        Theme.apply_menu_style(menu, theme_mode)

        act_diff = menu.addAction("Hide Differential (dx)" if self.show_differential else "Show Differential (dx)")
        act_diff.triggered.connect(self.toggle_differential)

        menu.addSeparator()
        act_del = menu.addAction("Delete Integral")
        act_del.triggered.connect(lambda: self.parent_edit.remove_fraction(self.fid) if self.parent_edit else None)

        menu.exec(global_pos)

    def toggle_differential(self):
        self.show_differential = not self.show_differential
        self.lbl_d.setVisible(self.show_differential)
        self.x_edit.setVisible(self.show_differential)
        self._on_text_changed()

    def _on_text_changed(self):
        self._adjust_size()
        if self.parent_edit:
            self.parent_edit._on_frac_size_changed(self)

    def update_style(self):
        sz = 13
        fam = "Times New Roman"
        is_dark = False
        if self.parent_edit and self.parent_edit.parent_cell:
            cell = self.parent_edit.parent_cell
            sz = getattr(cell, 'current_font_size', 13)
            fam = getattr(cell, 'current_font_family', "Times New Roman")
            factor = getattr(cell, 'zoom_factor', 1.0)
            sz = max(8, round(sz * factor))
            is_dark = (getattr(cell, 'theme_mode', 'light') == 'dark')

        color = "#f8fafc" if is_dark else "#000000"
        border_col = "#475569" if is_dark else "#cbd5e1"
        focus_bg = "#1e293b" if is_dark else "#eff6ff"
        focus_border = "#60a5fa" if is_dark else "#2563eb"

        int_sz = max(16, int(sz * 2.2))
        font_int = QFont(fam, int_sz)
        self.lbl_int.setFont(font_int)
        self.lbl_int.setStyleSheet(f"color: {color}; background: transparent; border: none; font-size: {int_sz}pt; font-family: \"{fam}\";")

        is_italic = True
        if self.parent_edit:
            cell = getattr(self.parent_edit, 'parent_cell', None)
            mode_nonexec = getattr(cell, 'MODE_NONEXEC_MATH', 'nonexec_math')
            mode_text = getattr(cell, 'MODE_TEXT', 'text')
            cur_mode = self.parent_edit.get_mode_at_cursor()
            cell_mode = getattr(cell, 'input_mode', None)
            if cell_mode in (mode_nonexec, mode_text) or cur_mode in (mode_nonexec, mode_text):
                is_italic = False

        lim_sz = max(8, int(sz * 0.75))
        font_lim = QFont(fam, lim_sz)
        font_lim.setItalic(is_italic)

        lim_style = f"""
            QLineEdit {{
                background: transparent;
                border: 1px dashed {border_col};
                border-radius: 2px;
                padding: 1px 4px;
                color: {color};
                font-family: \"{fam}\";
                font-size: {lim_sz}pt;
                font-style: {'italic' if is_italic else 'normal'};
            }}
            QLineEdit:focus {{
                border: 1.5px solid {focus_border};
                background: {focus_bg};
            }}
        """
        self.b_edit.setFont(font_lim)
        self.b_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.b_edit.setStyleSheet(lim_style)

        self.a_edit.setFont(font_lim)
        self.a_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.a_edit.setStyleSheet(lim_style)

        font_body = QFont(fam, sz)
        font_body.setItalic(is_italic)
        body_style = f"""
            QLineEdit, QTextEdit {{
                background: transparent;
                border: 1px dashed {border_col};
                border-radius: 2px;
                padding: 1px 4px;
                color: {color};
                font-family: \"{fam}\";
                font-size: {sz}pt;
                font-style: {'italic' if is_italic else 'normal'};
            }}
            QLineEdit:focus, QTextEdit:focus {{
                border: 1.5px solid {focus_border};
                background: {focus_bg};
            }}
        """
        self.f_edit.setFont(font_body)
        self.f_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.f_edit.setStyleSheet(body_style)

        font_d = QFont(fam, sz)
        self.lbl_d.setFont(font_d)
        self.lbl_d.setStyleSheet(f"color: {color}; background: transparent; border: none; font-family: \"{fam}\"; font-size: {sz}pt;")

        self.x_edit.setFont(font_body)
        self.x_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.x_edit.setStyleSheet(body_style)

        self._adjust_size()

    def _get_available_width(self) -> int:
        if self.parent_edit and hasattr(self.parent_edit, 'viewport'):
            vw = self.parent_edit.viewport().width()
            if vw > 100:
                curr_x = self.x() if self.x() > 0 else 0
                avail = vw - curr_x - 16
                if avail < 120:
                    avail = max(120, vw - 36)
                return avail
        return 800

    def _adjust_size(self):
        fm_int = self.lbl_int.fontMetrics()
        fm_lim = self.b_edit.fontMetrics()
        fm_body = self.f_edit.fontMetrics()

        int_w = max(fm_int.horizontalAdvance("∫") + 8, int(fm_int.height() * 0.45))
        self.lbl_int.setFixedWidth(int_w)

        b_txt = self.b_edit.text()
        a_txt = self.a_edit.text()
        lim_w = max(22, max(fm_lim.horizontalAdvance(b_txt or "b"), fm_lim.horizontalAdvance(a_txt or "a")) + 18)
        lim_h = max(16, fm_lim.height() + 4)
        self.b_edit.setFixedSize(lim_w, lim_h)
        self.a_edit.setFixedSize(lim_w, lim_h)
        self.limits_w.setFixedSize(lim_w, lim_h * 2 + 2)

        if getattr(self, 'show_differential', False) and hasattr(self, 'x_edit'):
            d_w = fm_body.horizontalAdvance(" d") + 2
            self.lbl_d.setFixedWidth(d_w)
            x_txt = self.x_edit.text()
            x_w = max(20, fm_body.horizontalAdvance(x_txt or "x") + 16)
            self.x_edit.setFixedSize(x_w, max(20, fm_body.height() + 4))
            diff_w = d_w + x_w + 4
        else:
            diff_w = 0

        avail_w = self._get_available_width()
        max_f_w = max(40, avail_w - int_w - lim_w - diff_w - 20)

        f_txt = self.f_edit.text()
        single_line_w = max(22, fm_body.horizontalAdvance(f_txt or "f") + 16)
        if single_line_w <= max_f_w:
            f_w = single_line_w
            if hasattr(self.f_edit, 'document'):
                self.f_edit.document().setTextWidth(-1)
            f_h = max(20, fm_body.height() + 4)
        else:
            f_w = max_f_w
            if hasattr(self.f_edit, 'document'):
                self.f_edit.document().setTextWidth(max_f_w - 4)
                doc_h = self.f_edit.document().documentLayout().documentSize().height()
                f_h = max(20, int(doc_h) + 4)
            else:
                f_h = max(20, fm_body.height() + 4)

        self.f_edit.setFixedSize(f_w, f_h)

        tot_w = int_w + lim_w + f_w + diff_w + 10
        tot_h = max(fm_int.height() + 4, max(lim_h * 2 + 4, f_h + 4))
        self.setFixedSize(tot_w, tot_h)
        self.updateGeometry()

    def text_expression(self) -> str:
        a_txt = self.a_edit.text().strip() or "a"
        b_txt = self.b_edit.text().strip() or "b"
        f_txt = self.f_edit.text().strip() or "f"

        if getattr(self, 'show_differential', False) and hasattr(self, 'x_edit'):
            var = self.x_edit.text().strip() or "x"
            return f"integrate({f_txt}, ({var}, {a_txt}, {b_txt}))"

        # Check if f_txt ends with d<var>, e.g. "x^2 dx" or "* dx"
        m = re.search(r'(?:[\s*]+|\b)d([a-zA-Z])\s*$', f_txt)
        if m:
            var = m.group(1)
            f_clean = f_txt[:m.start()].strip()
            return f"integrate({f_clean}, ({var}, {a_txt}, {b_txt}))"

        # Extract variable from f_txt:
        candidates = re.findall(r'\b([a-zA-Z])\b', f_txt)
        candidates = [c for c in candidates if c not in (a_txt, b_txt, 'e', 'd')]
        if 'x' in candidates:
            var = 'x'
        elif candidates and candidates[0] != 'f':
            var = candidates[0]
        else:
            var = 'x'

        return f"integrate({f_txt}, ({var}, {a_txt}, {b_txt}))"

    def lower_text(self) -> str:
        return self.a_edit.text()

    def upper_text(self) -> str:
        return self.b_edit.text()

    def integrand_text(self) -> str:
        return self.f_edit.text()


class BigOperatorWidget(QWidget):
    """
    Seamless inline 2D big operator widget (Summation ∑ and Product ∏)
    embedded directly in CellInputEdit viewport.
    Displays operator symbol with upper limit above (e.g. n), lower limit below (e.g. k = 1),
    and summand/factor f to the right.
    All fields (top, bottom, body) are editable that smoothly resize and support Tab/Arrow
    navigation and CAS evaluation.
    """
    def __init__(self, op_symbol: str = "∑", top: str = "n", bottom: str = "k = 1",
                 body: str = "f", fid: int = 1, parent_edit=None):
        super().__init__(parent_edit.viewport() if parent_edit else None)
        self.fid = fid
        self.parent_edit = parent_edit
        self.op_symbol = op_symbol
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("background: transparent;")

        h_layout = QHBoxLayout(self)
        h_layout.setContentsMargins(2, 0, 2, 0)
        h_layout.setSpacing(4)

        # 1. Operator column: top limit, symbol, bottom limit
        self.col_op = QWidget(self)
        v_layout = QVBoxLayout(self.col_op)
        v_layout.setContentsMargins(0, 0, 0, 0)
        v_layout.setSpacing(1)

        self.top_edit = QLineEdit(top, self.col_op)
        self.lbl_op = QLabel(op_symbol, self.col_op)
        self.bot_edit = QLineEdit(bottom, self.col_op)

        v_layout.addWidget(self.top_edit)
        v_layout.addWidget(self.lbl_op)
        v_layout.addWidget(self.bot_edit)
        h_layout.addWidget(self.col_op)

        # 2. Body / summand / factor f
        self.body_edit = MathSlotEdit(body, self)
        h_layout.addWidget(self.body_edit)

        # Signals
        self.top_edit.textChanged.connect(self._on_text_changed)
        self.bot_edit.textChanged.connect(self._on_text_changed)
        self.body_edit.textChanged.connect(self._on_text_changed)

        # Click handlers
        self.top_edit.mousePressEvent = self._make_click_handler(self.top_edit)
        self.bot_edit.mousePressEvent = self._make_click_handler(self.bot_edit)
        self.body_edit.mousePressEvent = self._make_click_handler(self.body_edit)

        # Key handlers
        self.top_edit.keyPressEvent = self._make_key_handler(self.top_edit, role="top")
        self.bot_edit.keyPressEvent = self._make_key_handler(self.bot_edit, role="bot")
        self.body_edit.keyPressEvent = self._make_key_handler(self.body_edit, role="body")

        # Context menu
        self.top_edit.contextMenuEvent = self._make_context_menu_handler(self.top_edit)
        self.bot_edit.contextMenuEvent = self._make_context_menu_handler(self.bot_edit)
        self.body_edit.contextMenuEvent = self._make_context_menu_handler(self.body_edit)

        self.update_style()
        self._adjust_size()

    def _make_click_handler(self, edit_widget):
        orig_press = edit_widget.mousePressEvent
        def handler(event):
            had_focus = edit_widget.hasFocus()
            orig_press(event)
            self.update()
            if not had_focus and edit_widget.text().strip() in ("n", "k = 1", "k=1", "f", "a", "b"):
                edit_widget.selectAll()
        return handler

    def _make_key_handler(self, edit_widget, role):
        orig_key = edit_widget.keyPressEvent
        def handler(event):
            if edit_widget.isReadOnly():
                if event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier):
                    if event.key() in (Qt.Key.Key_Plus, Qt.Key.Key_Equal, Qt.Key.Key_Minus, Qt.Key.Key_Underscore, Qt.Key.Key_0):
                        if self.parent_edit:
                            self.parent_edit.keyPressEvent(event)
                            return
                orig_key(event)
                return

            key = event.key()

            # Enter / Return
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if self.parent_edit:
                    if event.modifiers() & (Qt.KeyboardModifier.ShiftModifier | Qt.KeyboardModifier.AltModifier):
                        self.parent_edit._handle_inline_evaluation()
                    elif event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier):
                        self.parent_edit.executeRequested.emit()
                    else:
                        self.parent_edit.keyPressEvent(event)
                event.accept()
                return

            # Tab navigation: bot -> top -> body -> after widget
            if key == Qt.Key.Key_Tab:
                if role == "bot":
                    self.top_edit.setFocus()
                    self.top_edit.selectAll()
                elif role == "top":
                    self.body_edit.setFocus()
                    self.body_edit.selectAll()
                elif role == "body":
                    if self.parent_edit:
                        self.parent_edit.move_cursor_after_fraction(self.fid)
                event.accept()
                return

            # Backtab navigation: body -> top -> bot -> before widget
            if key == Qt.Key.Key_Backtab:
                if role == "body":
                    self.top_edit.setFocus()
                    self.top_edit.selectAll()
                elif role == "top":
                    self.bot_edit.setFocus()
                    self.bot_edit.selectAll()
                elif role == "bot":
                    if self.parent_edit:
                        self.parent_edit.move_cursor_before_fraction(self.fid)
                event.accept()
                return

            # Up / Down arrows:
            if key == Qt.Key.Key_Up:
                if role == "bot":
                    cpos = edit_widget.cursorPosition()
                    self.top_edit.setFocus()
                    self.top_edit.setCursorPosition(min(cpos, len(self.top_edit.text())))
                    self.update()
                    event.accept()
                    return
                elif role == "body" and isinstance(edit_widget, QTextEdit):
                    if not _is_cursor_on_first_line(edit_widget):
                        orig_key(event)
                        return
                    self.top_edit.setFocus()
                    self.top_edit.selectAll()
                    self.update()
                    event.accept()
                    return
            if key == Qt.Key.Key_Down:
                if role == "top":
                    cpos = edit_widget.cursorPosition()
                    self.bot_edit.setFocus()
                    self.bot_edit.setCursorPosition(min(cpos, len(self.bot_edit.text())))
                    self.update()
                    event.accept()
                    return
                elif role == "body" and isinstance(edit_widget, QTextEdit):
                    if not _is_cursor_on_last_line(edit_widget):
                        orig_key(event)
                        return
                    self.bot_edit.setFocus()
                    self.bot_edit.selectAll()
                    self.update()
                    event.accept()
                    return

            # Right arrow at end of text:
            if key == Qt.Key.Key_Right and edit_widget.cursorPosition() == len(edit_widget.text()):
                if role in ("bot", "top"):
                    self.body_edit.setFocus()
                    self.body_edit.setCursorPosition(0)
                elif role == "body":
                    if self.parent_edit:
                        self.parent_edit.move_cursor_after_fraction(self.fid)
                event.accept()
                return

            # Left arrow at start of text:
            if key == Qt.Key.Key_Left and edit_widget.cursorPosition() == 0:
                if role in ("bot", "top"):
                    if self.parent_edit:
                        self.parent_edit.move_cursor_before_fraction(self.fid)
                elif role == "body":
                    self.top_edit.setFocus()
                    self.top_edit.setCursorPosition(len(self.top_edit.text()))
                event.accept()
                return

            # Backspace on empty text: delete widget
            if key == Qt.Key.Key_Backspace and not edit_widget.text():
                if self.parent_edit:
                    self.parent_edit.remove_fraction(self.fid)
                event.accept()
                return

            orig_key(event)
        return handler

    def paintEvent(self, event):
        super().paintEvent(event)
        fw = QApplication.focusWidget()
        has_child_focus = bool(fw and (self == fw or self.isAncestorOf(fw)))
        if has_child_focus:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            pen = QPen(QColor("#93c5fd"), 1, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.setBrush(QColor(239, 246, 255, 130))
            r = self.rect().adjusted(0, 0, -1, -1)
            painter.drawRoundedRect(r, 2.0, 2.0)

    def contextMenuEvent(self, event):
        self.show_context_menu(event.globalPos(), None)
        event.accept()

    def _make_context_menu_handler(self, edit_widget):
        def handler(event):
            self.show_context_menu(event.globalPos(), edit_widget)
            event.accept()
        return handler

    def show_context_menu(self, global_pos, source_edit=None):
        menu = QMenu(self)
        theme_mode = 'light'
        if self.parent_edit and self.parent_edit.parent_cell:
            theme_mode = getattr(self.parent_edit.parent_cell, 'theme_mode', 'light')
        Theme.apply_menu_style(menu, theme_mode)

        act_del = menu.addAction(f"Delete {'Summation' if self.op_symbol == '∑' else 'Product'}")
        act_del.triggered.connect(lambda: self.parent_edit.remove_fraction(self.fid) if self.parent_edit else None)
        menu.exec(global_pos)

    def _on_text_changed(self):
        self._adjust_size()
        if self.parent_edit:
            self.parent_edit._on_frac_size_changed(self)

    def update_style(self):
        sz = 13
        fam = "Times New Roman"
        is_dark = False
        if self.parent_edit and self.parent_edit.parent_cell:
            cell = self.parent_edit.parent_cell
            sz = getattr(cell, 'current_font_size', 13)
            fam = getattr(cell, 'current_font_family', "Times New Roman")
            factor = getattr(cell, 'zoom_factor', 1.0)
            sz = max(8, round(sz * factor))
            is_dark = (getattr(cell, 'theme_mode', 'light') == 'dark')

        color = "#f8fafc" if is_dark else "#000000"
        border_col = "#475569" if is_dark else "#cbd5e1"
        focus_bg = "#1e293b" if is_dark else "#eff6ff"
        focus_border = "#60a5fa" if is_dark else "#2563eb"

        op_sz = max(18, int(sz * 2.2))
        font_op = QFont(fam, op_sz)
        self.lbl_op.setFont(font_op)
        self.lbl_op.setStyleSheet(f"color: {color}; background: transparent; border: none; font-size: {op_sz}pt; font-family: \"{fam}\";")

        is_italic = True
        if self.parent_edit:
            cell = getattr(self.parent_edit, 'parent_cell', None)
            mode_nonexec = getattr(cell, 'MODE_NONEXEC_MATH', 'nonexec_math')
            mode_text = getattr(cell, 'MODE_TEXT', 'text')
            cur_mode = self.parent_edit.get_mode_at_cursor()
            cell_mode = getattr(cell, 'input_mode', None)
            if cell_mode in (mode_nonexec, mode_text) or cur_mode in (mode_nonexec, mode_text):
                is_italic = False

        lim_sz = max(8, int(sz * 0.75))
        font_lim = QFont(fam, lim_sz)
        font_lim.setItalic(is_italic)

        lim_style = f"""
            QLineEdit {{
                background: transparent;
                border: 1px dashed {border_col};
                border-radius: 2px;
                padding: 1px 4px;
                color: {color};
                font-family: \"{fam}\";
                font-size: {lim_sz}pt;
                font-style: {'italic' if is_italic else 'normal'};
            }}
            QLineEdit:focus {{
                border: 1.5px solid {focus_border};
                background: {focus_bg};
            }}
        """
        self.top_edit.setFont(font_lim)
        self.top_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.top_edit.setStyleSheet(lim_style)

        self.bot_edit.setFont(font_lim)
        self.bot_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.bot_edit.setStyleSheet(lim_style)

        font_body = QFont(fam, sz)
        font_body.setItalic(is_italic)
        body_style = f"""
            QLineEdit, QTextEdit {{
                background: transparent;
                border: 1px dashed {border_col};
                border-radius: 2px;
                padding: 1px 4px;
                color: {color};
                font-family: \"{fam}\";
                font-size: {sz}pt;
                font-style: {'italic' if is_italic else 'normal'};
            }}
            QLineEdit:focus, QTextEdit:focus {{
                border: 1.5px solid {focus_border};
                background: {focus_bg};
            }}
        """
        self.body_edit.setFont(font_body)
        self.body_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.body_edit.setStyleSheet(body_style)

        self._adjust_size()

    def _get_available_width(self) -> int:
        if self.parent_edit and hasattr(self.parent_edit, 'viewport'):
            vw = self.parent_edit.viewport().width()
            if vw > 100:
                curr_x = self.x() if self.x() > 0 else 0
                avail = vw - curr_x - 16
                if avail < 120:
                    avail = max(120, vw - 36)
                return avail
        return 800

    def _adjust_size(self):
        fm_op = self.lbl_op.fontMetrics()
        fm_lim = self.top_edit.fontMetrics()
        fm_body = self.body_edit.fontMetrics()

        top_txt = self.top_edit.text()
        bot_txt = self.bot_edit.text()
        top_w = max(22, fm_lim.horizontalAdvance(top_txt or "n") + 18)
        bot_w = max(28, fm_lim.horizontalAdvance(bot_txt or "k = 1") + 18)
        sym_w = fm_op.horizontalAdvance(self.op_symbol) + 8
        op_col_w = max(top_w, bot_w, sym_w)

        lim_h = max(16, fm_lim.height() + 4)
        op_h = max(20, fm_op.height())

        self.top_edit.setFixedSize(op_col_w, lim_h)
        self.lbl_op.setFixedSize(op_col_w, op_h)
        self.bot_edit.setFixedSize(op_col_w, lim_h)
        self.col_op.setFixedSize(op_col_w, lim_h * 2 + op_h + 2)

        avail_w = self._get_available_width()
        max_b_w = max(40, avail_w - op_col_w - 20)

        body_txt = self.body_edit.text()
        single_line_w = max(22, fm_body.horizontalAdvance(body_txt or "f") + 16)
        if single_line_w <= max_b_w:
            b_w = single_line_w
            if hasattr(self.body_edit, 'document'):
                self.body_edit.document().setTextWidth(-1)
            b_h = max(20, fm_body.height() + 4)
        else:
            b_w = max_b_w
            if hasattr(self.body_edit, 'document'):
                self.body_edit.document().setTextWidth(max_b_w - 4)
                doc_h = self.body_edit.document().documentLayout().documentSize().height()
                b_h = max(20, int(doc_h) + 4)
            else:
                b_h = max(20, fm_body.height() + 4)

        self.body_edit.setFixedSize(b_w, b_h)

        tot_w = op_col_w + b_w + 12
        tot_h = max(lim_h * 2 + op_h + 4, b_h + 4)
        self.setFixedSize(tot_w, tot_h)
        self.updateGeometry()

    def text_expression(self) -> str:
        top_txt = self.top_edit.text().strip() or "n"
        bot_txt = self.bot_edit.text().strip() or "k = 1"
        body_txt = self.body_edit.text().strip() or "f"

        var = "k"
        start = "1"
        if "=" in bot_txt:
            parts = bot_txt.split("=", 1)
            var = parts[0].strip() or "k"
            start = parts[1].strip() or "1"
        else:
            start = bot_txt

        if self.op_symbol == "∏":
            return f"∏({body_txt}, {var} = {start}..{top_txt})"
        return f"∑({body_txt}, {var} = {start}..{top_txt})"

    def top_text(self) -> str:
        return self.top_edit.text()

    def bottom_text(self) -> str:
        return self.bot_edit.text()

    def body_text(self) -> str:
        return self.body_edit.text()


class RadicalWidget(QWidget):
    """
    Seamless inline 2D radical (square root / nth root) widget embedded directly in CellInputEdit viewport.
    Displays radical symbol with continuous horizontal overbar (vinculum) that dynamically extends
    above whatever is written inside the root (radicand).
    Supports optional degree for nth root (\\sqrt[n]{a}), smooth cursor navigation,
    subscripts/superscripts, and full CAS evaluation.
    """
    def __init__(self, radicand: str = "a", degree: Optional[str] = None, fid: int = 1, parent_edit=None, parent_slot=None, is_result: bool = False, read_only: bool = False):
        if parent_slot is not None:
            super().__init__(parent_slot)
        elif parent_edit is not None:
            super().__init__(parent_edit.viewport())
        else:
            super().__init__()
        self.fid = fid
        self.parent_edit = parent_edit
        self.parent_slot = parent_slot
        self.degree_str = degree
        self.show_degree = degree is not None
        self.is_result = is_result
        self.read_only = read_only or is_result
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("background: transparent;")

        # Optional degree edit for nth root
        if self.show_degree:
            self.deg_edit = QLineEdit(degree if degree else "n", self)
            self.deg_edit.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            self.deg_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
            if self.read_only:
                self.deg_edit.setReadOnly(True)
            self.deg_edit.textChanged.connect(self._on_text_changed)
            self.deg_edit.mousePressEvent = self._make_click_handler(self.deg_edit)
            self.deg_edit.keyPressEvent = self._make_key_handler(self.deg_edit, role="deg")
            self.deg_edit.contextMenuEvent = self._make_context_menu_handler(self.deg_edit)
        else:
            self.deg_edit = None

        # Main radicand edit (inside the square root)
        self.rad_edit = MathSlotEdit(radicand, self)
        self.rad_edit.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.rad_edit.setAlignment(Qt.AlignmentFlag.AlignLeft)
        if self.read_only:
            self.rad_edit.setReadOnly(True)
        self.rad_edit.textChanged.connect(self._on_text_changed)
        self.rad_edit.mousePressEvent = self._make_click_handler(self.rad_edit)
        self.rad_edit.keyPressEvent = self._make_key_handler(self.rad_edit, role="rad")
        self.rad_edit.contextMenuEvent = self._make_context_menu_handler(self.rad_edit)

        self.update_style()
        self._adjust_size()

    def first_edit(self) -> Optional[QLineEdit]:
        if self.show_degree and self.deg_edit and not sip.isdeleted(self.deg_edit):
            return self.deg_edit
        if self.rad_edit and not sip.isdeleted(self.rad_edit):
            return self.rad_edit
        return None

    def last_edit(self) -> Optional[QLineEdit]:
        if self.rad_edit and not sip.isdeleted(self.rad_edit):
            return self.rad_edit
        if self.show_degree and self.deg_edit and not sip.isdeleted(self.deg_edit):
            return self.deg_edit
        return None

    def radicand_text(self) -> str:
        if self.rad_edit and not sip.isdeleted(self.rad_edit):
            return self.rad_edit.text().strip() or "a"
        return "a"

    def degree_text(self) -> Optional[str]:
        if self.show_degree and self.deg_edit and not sip.isdeleted(self.deg_edit):
            return self.deg_edit.text().strip() or "n"
        return None

    def text_expression(self) -> str:
        rad = self.radicand_text()
        deg = self.degree_text()
        if deg:
            return f"root({rad}, {deg})"
        return f"sqrt({rad})"

    def _make_click_handler(self, edit_widget):
        orig_press = edit_widget.mousePressEvent
        is_sup_char = lambda c: c in SUPER_MAP.values() or c in ('·', '⋅')
        def handler(event):
            had_focus = edit_widget.hasFocus()
            orig_press(event)
            if self.parent_slot:
                top = self.parent_slot.parent_frac.get_top_fraction() if self.parent_slot.parent_frac else None
                if top:
                    if top.parent_edit:
                        top.parent_edit._active_fraction_slot = self.parent_slot
                    top.update()
            self.update()
            if not had_focus and edit_widget.text().strip() in ("a", "n"):
                edit_widget.selectAll()
            else:
                cpos = edit_widget.cursorPosition()
                txt = edit_widget.text()
                char_left = txt[cpos - 1] if cpos > 0 else ""
                char_right = txt[cpos] if cpos < len(txt) else ""
                if is_sup_char(char_left) and is_sup_char(char_right):
                    edit_widget._superscript_active = True
                elif cpos == len(txt) and getattr(edit_widget, '_superscript_active', False):
                    pass
                else:
                    edit_widget._superscript_active = False
        return handler

    def _make_key_handler(self, edit_widget, role: str):
        orig_key = edit_widget.keyPressEvent
        is_sup_char = lambda c: c in SUPER_MAP.values() or c in ('·', '⋅')

        def handler(event):
            if edit_widget.isReadOnly():
                orig_key(event)
                return

            key = event.key()

            # Superscripts: typing '^' enters continuous power mode
            if event.text() == '^':
                edit_widget._superscript_active = True
                event.accept()
                return

            # Active superscript typing
            if getattr(edit_widget, '_superscript_active', False):
                ch = event.text()
                if ch in (' ', '\t') or key == Qt.Key.Key_Space:
                    edit_widget._superscript_active = False
                    edit_widget.insert(' ')
                    event.accept()
                    return
                elif ch in SUPER_MAP or ch.lower() in SUPER_MAP:
                    edit_widget.insert(SUPER_MAP.get(ch, SUPER_MAP.get(ch.lower(), ch)))
                    edit_widget._superscript_active = True
                    event.accept()
                    return
                elif ch in ('*', '·'):
                    edit_widget.insert('·')
                    edit_widget._superscript_active = True
                    event.accept()
                    return
                elif ch:
                    edit_widget._superscript_active = False
                    # fall through to normal baseline typing

            # Typing '*' converts to middle dot '·'
            if event.text() in ('*', '·'):
                edit_widget.insert('·')
                event.accept()
                return

            # Enter / Return execution shortcuts
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                top_edit = None
                if self.parent_slot and self.parent_slot.parent_frac:
                    top = self.parent_slot.parent_frac.get_top_fraction()
                    top_edit = top.parent_edit if top else None
                elif self.parent_edit:
                    top_edit = self.parent_edit

                if top_edit:
                    if event.modifiers() & (Qt.KeyboardModifier.ShiftModifier | Qt.KeyboardModifier.AltModifier):
                        top_edit._handle_inline_evaluation()
                    elif event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier):
                        top_edit.executeRequested.emit()
                    else:
                        top_edit.keyPressEvent(event)
                event.accept()
                return

            # Up / Down arrows inside a fraction slot or multiline edit
            if key == Qt.Key.Key_Down:
                if isinstance(edit_widget, QTextEdit) and not _is_cursor_on_last_line(edit_widget):
                    orig_key(event)
                    return
                if self.parent_slot and self.parent_slot.parent_frac and self.parent_slot.is_num:
                    target = self.parent_slot.parent_frac.den_slot.first_edit()
                    if target:
                        target.setFocus()
                        top = self.parent_slot.parent_frac.get_top_fraction()
                        if top: top.update()
                        event.accept()
                        return
            if key == Qt.Key.Key_Up:
                if isinstance(edit_widget, QTextEdit) and not _is_cursor_on_first_line(edit_widget):
                    orig_key(event)
                    return
                if self.parent_slot and self.parent_slot.parent_frac and not self.parent_slot.is_num:
                    target = self.parent_slot.parent_frac.num_slot.first_edit()
                    if target:
                        target.setFocus()
                        top = self.parent_slot.parent_frac.get_top_fraction()
                        if top: top.update()
                        event.accept()
                        return

            # Tab navigation
            if key == Qt.Key.Key_Tab:
                if role == "deg" and self.rad_edit:
                    self.rad_edit.setFocus()
                    self.rad_edit.selectAll()
                else:
                    if self.parent_slot:
                        self.parent_slot.navigate_after_child(self)
                    elif self.parent_edit:
                        self.parent_edit.move_cursor_after_fraction(self.fid)
                event.accept()
                return

            # Backtab (Shift+Tab) navigation
            if key == Qt.Key.Key_Backtab:
                if role == "rad" and self.show_degree and self.deg_edit:
                    self.deg_edit.setFocus()
                    self.deg_edit.selectAll()
                else:
                    if self.parent_slot:
                        self.parent_slot.navigate_before_child(self)
                    elif self.parent_edit:
                        self.parent_edit.move_cursor_before_fraction(self.fid)
                event.accept()
                return

            # Arrow navigation
            if key == Qt.Key.Key_Right:
                cpos = edit_widget.cursorPosition()
                txt = edit_widget.text()
                if getattr(edit_widget, '_superscript_active', False):
                    if cpos == len(txt):
                        # At end of power/text: exit power mode to baseline without leaving the root
                        edit_widget._superscript_active = False
                        event.accept()
                        return
                    else:
                        new_pos = cpos + 1
                        edit_widget.setCursorPosition(new_pos)
                        char_left = txt[new_pos - 1] if new_pos > 0 else ""
                        if not is_sup_char(char_left):
                            edit_widget._superscript_active = False
                        event.accept()
                        return
                else:
                    if cpos == len(txt):
                        if role == "deg" and self.rad_edit:
                            self.rad_edit.setFocus()
                            self.rad_edit.setCursorPosition(0)
                            event.accept()
                            return
                        elif self.parent_slot:
                            if self.parent_slot.navigate_after_child(self):
                                event.accept()
                                return
                            else:
                                top = self.parent_slot.parent_frac.get_top_fraction()
                                if top:
                                    top.navigate_after()
                                    event.accept()
                                    return
                        elif self.parent_edit:
                            self.parent_edit.move_cursor_after_fraction(self.fid)
                            event.accept()
                            return
                    else:
                        new_pos = cpos + 1
                        edit_widget.setCursorPosition(new_pos)
                        char_left = txt[new_pos - 1] if new_pos > 0 else ""
                        char_right = txt[new_pos] if new_pos < len(txt) else ""
                        if is_sup_char(char_left) and is_sup_char(char_right):
                            edit_widget._superscript_active = True
                        else:
                            edit_widget._superscript_active = False
                        event.accept()
                        return

            if key == Qt.Key.Key_Left:
                cpos = edit_widget.cursorPosition()
                txt = edit_widget.text()
                if cpos == 0:
                    edit_widget._superscript_active = False
                    if role == "rad" and self.show_degree and self.deg_edit:
                        self.deg_edit.setFocus()
                        self.deg_edit.setCursorPosition(len(self.deg_edit.text()))
                        event.accept()
                        return
                    elif self.parent_slot:
                        if self.parent_slot.navigate_before_child(self):
                            event.accept()
                            return
                        else:
                            top = self.parent_slot.parent_frac.get_top_fraction()
                            if top:
                                top.navigate_before()
                                event.accept()
                                return
                    elif self.parent_edit:
                        self.parent_edit.move_cursor_before_fraction(self.fid)
                        event.accept()
                        return
                else:
                    new_pos = cpos - 1
                    edit_widget.setCursorPosition(new_pos)
                    char_left = txt[new_pos - 1] if new_pos > 0 else ""
                    if is_sup_char(char_left):
                        edit_widget._superscript_active = True
                    else:
                        edit_widget._superscript_active = False
                    event.accept()
                    return

            # Backspace handling
            if key == Qt.Key.Key_Backspace:
                cpos = edit_widget.cursorPosition()
                txt = edit_widget.text()
                if not txt:
                    edit_widget._superscript_active = False
                    if self.parent_slot:
                        self.parent_slot.remove_radical_child(self)
                    elif self.parent_edit:
                        self.parent_edit.remove_fraction(self.fid)
                    event.accept()
                    return
                elif cpos > 0 and not edit_widget.hasSelectedText():
                    orig_key(event)
                    new_pos = edit_widget.cursorPosition()
                    new_txt = edit_widget.text()
                    char_left = new_txt[new_pos - 1] if new_pos > 0 else ""
                    if is_sup_char(char_left):
                        edit_widget._superscript_active = True
                    else:
                        edit_widget._superscript_active = False
                    return

            orig_key(event)
        return handler

    def _on_text_changed(self):
        for edit in (self.rad_edit, self.deg_edit):
            if edit and not sip.isdeleted(edit):
                cur_text = edit.text()
                if '_' in cur_text or '^' in cur_text:
                    formatted = format_subscripts_and_superscripts(cur_text)
                    if formatted != cur_text:
                        cpos = edit.cursorPosition()
                        edit.setText(formatted)
                        edit.setCursorPosition(min(cpos, len(formatted)))
        self._adjust_size()
        if self.parent_slot and not sip.isdeleted(self.parent_slot):
            self.parent_slot._adjust_size()
            if self.parent_slot.parent_frac and not sip.isdeleted(self.parent_slot.parent_frac):
                self.parent_slot.parent_frac._adjust_size()
                top = self.parent_slot.parent_frac.get_top_fraction()
                if top and top.parent_edit:
                    top.parent_edit._on_frac_size_changed(top)
        elif self.parent_edit:
            self.parent_edit._on_frac_size_changed(self)

    def update_style(self):
        sz = 13
        fam = "Times New Roman"
        is_dark = False
        factor = 1.0
        cell = None
        p_edit = None
        if self.parent_slot and self.parent_slot.parent_frac:
            top = self.parent_slot.parent_frac.get_top_fraction()
            p_edit = top.parent_edit if top else self.parent_slot.parent_frac.parent_edit
        elif self.parent_edit:
            p_edit = self.parent_edit

        if p_edit and p_edit.parent_cell:
            cell = p_edit.parent_cell
            sz = getattr(cell, 'current_font_size', 13)
            fam = getattr(cell, 'current_font_family', "Times New Roman")
            factor = getattr(cell, 'zoom_factor', 1.0)
            sz = max(8, round(sz * factor))
            is_dark = (getattr(cell, 'theme_mode', 'light') == 'dark')

        if self.parent_slot:
            level = 0
            p = self.parent_slot
            while p:
                level += 1
                if p.parent_frac:
                    p = getattr(p.parent_frac, 'parent_slot', None)
                else:
                    break
            sz = max(7, round(sz * (0.85 ** level)))

        from .theme import Theme
        if getattr(self, 'is_result', False):
            color = Theme.DARK_MATH_BLUE if is_dark else Theme.OPENMATH_MATH_BLUE
        else:
            color = "#f8fafc" if is_dark else "#000000"

        is_italic = True
        if p_edit:
            cell = getattr(p_edit, 'parent_cell', None)
            mode_nonexec = getattr(cell, 'MODE_NONEXEC_MATH', 'nonexec_math')
            mode_text = getattr(cell, 'MODE_TEXT', 'text')
            cur_mode = p_edit.get_mode_at_cursor()
            cell_mode = getattr(cell, 'input_mode', None)
            if cell_mode in (mode_nonexec, mode_text) or cur_mode in (mode_nonexec, mode_text):
                is_italic = False

        font_rad = QFont(fam, sz)
        font_rad.setItalic(is_italic)
        self.rad_edit.setFont(font_rad)
        self._font_rad = font_rad

        rad_style = f"""
            QLineEdit, QTextEdit {{
                background: transparent;
                border: none;
                padding: 0px 3px;
                margin: 0px;
                color: {color};
                font-family: "{fam}";
                font-size: {sz}pt;
                font-style: {'italic' if is_italic else 'normal'};
                selection-background-color: #2563eb;
                selection-color: #ffffff;
            }}
        """
        self.rad_edit.setStyleSheet(rad_style)

        if self.deg_edit:
            deg_sz = max(7, int(sz * 0.68))
            font_deg = QFont(fam, deg_sz)
            font_deg.setItalic(is_italic)
            self.deg_edit.setFont(font_deg)
            self._font_deg = font_deg
            deg_style = f"""
                QLineEdit, QTextEdit {{
                    background: transparent;
                    border: none;
                    padding: 0px 1px;
                    margin: 0px;
                    color: {color};
                    font-family: "{fam}";
                    font-size: {deg_sz}pt;
                    font-style: {'italic' if is_italic else 'normal'};
                    selection-background-color: #2563eb;
                    selection-color: #ffffff;
                }}
            """
            self.deg_edit.setStyleSheet(deg_style)

        self._adjust_size()

    def _get_available_width(self) -> int:
        top_edit = None
        if self.parent_slot and self.parent_slot.parent_frac:
            top = self.parent_slot.parent_frac.get_top_fraction()
            top_edit = top.parent_edit if top else None
        elif self.parent_edit:
            top_edit = self.parent_edit
        if top_edit and hasattr(top_edit, 'viewport'):
            vw = top_edit.viewport().width()
            if vw > 100:
                curr_x = self.x() if self.x() > 0 else 0
                avail = vw - curr_x - 16
                if avail < 120:
                    avail = max(120, vw - 36)
                return avail
        return 800

    def _adjust_size(self):
        font_rad = getattr(self, '_font_rad', None) or self.rad_edit.font()
        fm_rad = QFontMetrics(font_rad)
        factor = 1.0
        p_edit = None
        if self.parent_slot and self.parent_slot.parent_frac:
            top = self.parent_slot.parent_frac.get_top_fraction()
            p_edit = top.parent_edit if top else self.parent_slot.parent_frac.parent_edit
        elif self.parent_edit:
            p_edit = self.parent_edit
        if p_edit and p_edit.parent_cell:
            factor = getattr(p_edit.parent_cell, 'zoom_factor', 1.0)

        if self.show_degree and self.deg_edit:
            font_deg = getattr(self, '_font_deg', None) or self.deg_edit.font()
            fm_deg = QFontMetrics(font_deg)
            d_txt = self.deg_edit.text()
            w_deg = max(10, fm_deg.horizontalAdvance(d_txt if d_txt else "n") + 4)
            h_deg = max(12, fm_deg.height())
            self.deg_edit.setFixedSize(w_deg, h_deg)
            self.deg_edit.move(1, 0)
            hook_x_start = w_deg + 2
        else:
            hook_x_start = 2

        hook_w = max(10, int(11 * factor))
        bar_top_margin = max(2, int(3 * factor))

        rad_x = hook_x_start + hook_w + max(2, int(3 * factor))
        rad_y = bar_top_margin

        avail_w = self._get_available_width()
        right_pad = max(4, int(5 * factor))
        max_rad_w = max(60, avail_w - rad_x - right_pad)

        txt = self.rad_edit.text()
        w_text = fm_rad.horizontalAdvance(txt if txt else "a")
        single_line_w = max(18, w_text + 8)

        if single_line_w <= max_rad_w:
            w_rad = single_line_w
            if hasattr(self.rad_edit, 'document'):
                self.rad_edit.document().setTextWidth(-1)
            h_rad = max(18, fm_rad.height() + 2)
        else:
            w_rad = max_rad_w
            if hasattr(self.rad_edit, 'document'):
                self.rad_edit.document().setTextWidth(w_rad)
                doc_h = self.rad_edit.document().documentLayout().documentSize().height()
                h_rad = max(18, int(doc_h) + 2)
            else:
                h_rad = max(18, fm_rad.height() + 2)

        self.rad_edit.setFixedSize(w_rad, h_rad)
        self.rad_edit.move(rad_x, rad_y)

        tot_w = rad_x + w_rad + right_pad
        tot_h = rad_y + h_rad + max(2, int(3 * factor))

        self.setFixedSize(tot_w, tot_h)
        self.updateGeometry()
        self.update()

        if self.parent_slot and self.parent_slot.parent_frac:
            self.parent_slot._adjust_size()
            self.parent_slot.parent_frac._adjust_size()
        elif self.parent_edit:
            self.parent_edit._on_frac_size_changed(self)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        factor = 1.0
        p_edit = None
        if self.parent_slot and self.parent_slot.parent_frac:
            top = self.parent_slot.parent_frac.get_top_fraction()
            p_edit = top.parent_edit if top else self.parent_slot.parent_frac.parent_edit
        elif self.parent_edit:
            p_edit = self.parent_edit

        is_dark = False
        if p_edit and p_edit.parent_cell:
            factor = getattr(p_edit.parent_cell, 'zoom_factor', 1.0)
            is_dark = (getattr(p_edit.parent_cell, 'theme_mode', 'light') == 'dark')

        if not getattr(self, 'is_result', False) and self.parent_slot is None:
            fw = QApplication.focusWidget()
            has_child_focus = bool(fw and (self == fw or self.isAncestorOf(fw)))
            if has_child_focus:
                focus_pen = QPen(QColor("#93c5fd"), 1, Qt.PenStyle.DashLine)
                painter.setPen(focus_pen)
                painter.setBrush(QColor(239, 246, 255, 120) if not is_dark else QColor(30, 41, 59, 120))
                r = self.rect().adjusted(0, 0, -1, -1)
                painter.drawRoundedRect(r, 2.0, 2.0)
                painter.setBrush(Qt.BrushStyle.NoBrush)

        from .theme import Theme
        if getattr(self, 'is_result', False):
            line_color = QColor(Theme.DARK_MATH_BLUE if is_dark else Theme.OPENMATH_MATH_BLUE)
        else:
            line_color = QColor("#f8fafc" if is_dark else "#000000")
        line_w = max(1.1, 1.35 * factor)
        pen = QPen(line_color, line_w, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.MiterJoin)
        painter.setPen(pen)

        rad_rect = self.rad_edit.geometry()
        hook_x_start = 2
        if self.show_degree and self.deg_edit:
            hook_x_start = self.deg_edit.geometry().right() + 2

        hook_w = max(6, rad_rect.x() - hook_x_start)
        y_top = rad_rect.y() - 1
        y_bot = rad_rect.y() + rad_rect.height() - max(2, int(3 * factor))
        y_mid = y_top + (y_bot - y_top) * 0.58

        path = QPainterPath()
        p0 = QPointF(hook_x_start, y_mid)
        p1 = QPointF(hook_x_start + hook_w * 0.28, y_top + (y_bot - y_top) * 0.70)
        p2 = QPointF(hook_x_start + hook_w * 0.52, y_bot)
        p3 = QPointF(rad_rect.x() - 1, y_top)
        x_bar_end = rad_rect.x() + rad_rect.width() + 1
        p4 = QPointF(x_bar_end, y_top)
        p5 = QPointF(x_bar_end, y_top + max(2.0, 2.5 * factor))

        path.moveTo(p0)
        path.lineTo(p1)
        path.lineTo(p2)
        path.lineTo(p3)
        path.lineTo(p4)
        path.lineTo(p5)

        painter.drawPath(path)

    def contextMenuEvent(self, event):
        self.show_context_menu(event.globalPos(), None)
        event.accept()

    def _make_context_menu_handler(self, edit_widget):
        def handler(event):
            self.show_context_menu(event.globalPos(), edit_widget)
            event.accept()
        return handler

    def show_context_menu(self, global_pos, source_edit=None):
        menu = QMenu(self)
        theme_mode = 'light'
        if self.parent_edit and self.parent_edit.parent_cell:
            theme_mode = getattr(self.parent_edit.parent_cell, 'theme_mode', 'light')
        Theme.apply_menu_style(menu, theme_mode)

        act_del = menu.addAction("Delete Radical (√)")
        act_del.triggered.connect(lambda: self.parent_edit.remove_fraction(self.fid) if self.parent_edit else None)
        menu.exec(global_pos)


class EvalBarWidget(QWidget):
    """
    Seamless inline 2D evaluation-at-point (eval bar) widget: f|_{x=a}
    Displays expression f, followed by a tall vertical bar |, and subscript condition x=a.
    Both fields (f, condition) are editable and support Tab/Arrow navigation and CAS evaluation.
    """
    def __init__(self, f: str = "f", cond: str = "x = a", fid: int = 1, parent_edit=None):
        super().__init__(parent_edit.viewport() if parent_edit else None)
        self.fid = fid
        self.parent_edit = parent_edit
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("background: transparent;")

        h_layout = QHBoxLayout(self)
        h_layout.setContentsMargins(2, 0, 2, 0)
        h_layout.setSpacing(3)

        self.f_edit = MathSlotEdit(f, self)
        h_layout.addWidget(self.f_edit)

        self.lbl_bar = QLabel("|", self)
        self.lbl_bar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        h_layout.addWidget(self.lbl_bar)

        self.cond_container = QWidget(self)
        v_sub = QVBoxLayout(self.cond_container)
        v_sub.setContentsMargins(0, 0, 0, 0)
        v_sub.setSpacing(0)
        self.sub_spacer = QWidget(self.cond_container)
        v_sub.addWidget(self.sub_spacer)
        self.cond_edit = QLineEdit(cond, self.cond_container)
        v_sub.addWidget(self.cond_edit)
        h_layout.addWidget(self.cond_container)

        self.f_edit.textChanged.connect(self._on_text_changed)
        self.cond_edit.textChanged.connect(self._on_text_changed)

        self.f_edit.mousePressEvent = self._make_click_handler(self.f_edit)
        self.cond_edit.mousePressEvent = self._make_click_handler(self.cond_edit)

        self.f_edit.keyPressEvent = self._make_key_handler(self.f_edit, role="f")
        self.cond_edit.keyPressEvent = self._make_key_handler(self.cond_edit, role="cond")

        self.update_style()
        self._adjust_size()

    def _make_click_handler(self, edit_widget):
        orig_press = edit_widget.mousePressEvent
        def handler(event):
            had_focus = edit_widget.hasFocus()
            orig_press(event)
            self.update()
            if not had_focus and edit_widget.text().strip() in ("f", "x = a", "x=a"):
                edit_widget.selectAll()
        return handler

    def _make_key_handler(self, edit_widget, role):
        orig_key = edit_widget.keyPressEvent
        def handler(event):
            if edit_widget.isReadOnly():
                orig_key(event)
                return
            key = event.key()
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if self.parent_edit:
                    if event.modifiers() & (Qt.KeyboardModifier.ShiftModifier | Qt.KeyboardModifier.AltModifier):
                        self.parent_edit._handle_inline_evaluation()
                    elif event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier):
                        self.parent_edit.executeRequested.emit()
                    else:
                        self.parent_edit.keyPressEvent(event)
                event.accept()
                return
            if key == Qt.Key.Key_Tab:
                if role == "f":
                    self.cond_edit.setFocus()
                    self.cond_edit.selectAll()
                elif role == "cond" and self.parent_edit:
                    self.parent_edit.move_cursor_after_fraction(self.fid)
                event.accept()
                return
            if key == Qt.Key.Key_Backtab:
                if role == "cond":
                    self.f_edit.setFocus()
                    self.f_edit.selectAll()
                elif role == "f" and self.parent_edit:
                    self.parent_edit.move_cursor_before_fraction(self.fid)
                event.accept()
                return
            if key == Qt.Key.Key_Right and edit_widget.cursorPosition() == len(edit_widget.text()):
                if role == "f":
                    self.cond_edit.setFocus()
                    self.cond_edit.setCursorPosition(0)
                elif role == "cond" and self.parent_edit:
                    self.parent_edit.move_cursor_after_fraction(self.fid)
                event.accept()
                return
            if key == Qt.Key.Key_Left and edit_widget.cursorPosition() == 0:
                if role == "cond":
                    self.f_edit.setFocus()
                    self.f_edit.setCursorPosition(len(self.f_edit.text()))
                elif role == "f" and self.parent_edit:
                    self.parent_edit.move_cursor_before_fraction(self.fid)
                event.accept()
                return
            orig_key(event)
            self._adjust_size()
            if self.parent_edit:
                self.parent_edit._on_frac_size_changed(self)
        return handler

    def _on_text_changed(self):
        self._adjust_size()
        if self.parent_edit:
            self.parent_edit._on_frac_size_changed(self)

    def paintEvent(self, event):
        super().paintEvent(event)
        fw = QApplication.focusWidget()
        if fw and (self == fw or self.isAncestorOf(fw)):
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            pen = QPen(QColor("#93c5fd"), 1, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.setBrush(QColor(239, 246, 255, 130))
            r = self.rect().adjusted(0, 0, -1, -1)
            painter.drawRoundedRect(r, 2.0, 2.0)

    def update_style(self):
        sz = 13
        fam = "Times New Roman"
        is_dark = False
        if self.parent_edit and self.parent_edit.parent_cell:
            cell = self.parent_edit.parent_cell
            sz = getattr(cell, 'current_font_size', 13)
            fam = getattr(cell, 'current_font_family', "Times New Roman")
            factor = getattr(cell, 'zoom_factor', 1.0)
            sz = max(8, round(sz * factor))
            is_dark = (getattr(cell, 'theme_mode', 'light') == 'dark')

        color = "#f8fafc" if is_dark else "#000000"
        border_col = "#475569" if is_dark else "#cbd5e1"
        focus_bg = "#1e293b" if is_dark else "#eff6ff"
        focus_border = "#60a5fa" if is_dark else "#2563eb"

        bar_sz = max(16, int(sz * 1.8))
        font_bar = QFont(fam, bar_sz)
        self.lbl_bar.setFont(font_bar)
        self.lbl_bar.setStyleSheet(f"color: {color}; background: transparent; border: none; font-size: {bar_sz}pt; font-family: \"{fam}\";")

        font_f = QFont(fam, sz)
        font_f.setItalic(True)
        f_style = f"""
            QLineEdit, QTextEdit {{
                background: transparent;
                border: 1px dashed {border_col};
                border-radius: 2px;
                padding: 1px 4px;
                color: {color};
                font-family: \"{fam}\";
                font-size: {sz}pt;
                font-style: italic;
            }}
            QLineEdit:focus, QTextEdit:focus {{
                border: 1.5px solid {focus_border};
                background: {focus_bg};
            }}
        """
        self.f_edit.setFont(font_f)
        self.f_edit.setStyleSheet(f_style)

        sub_sz = max(8, int(sz * 0.75))
        font_cond = QFont(fam, sub_sz)
        font_cond.setItalic(True)
        cond_style = f"""
            QLineEdit {{
                background: transparent;
                border: 1px dashed {border_col};
                border-radius: 2px;
                padding: 1px 4px;
                color: {color};
                font-family: \"{fam}\";
                font-size: {sub_sz}pt;
                font-style: italic;
            }}
            QLineEdit:focus {{
                border: 1.5px solid {focus_border};
                background: {focus_bg};
            }}
        """
        self.cond_edit.setFont(font_cond)
        self.cond_edit.setStyleSheet(cond_style)

    def _adjust_size(self):
        fm_f = self.f_edit.fontMetrics()
        fm_cond = self.cond_edit.fontMetrics()
        fm_bar = self.lbl_bar.fontMetrics()

        f_txt = self.f_edit.text() or "f"
        cond_txt = self.cond_edit.text() or "x = a"

        f_w = max(28, fm_f.horizontalAdvance(f_txt) + 22)
        f_h = max(24, fm_f.height() + 6)
        self.f_edit.setFixedSize(f_w, f_h)

        cond_w = max(32, fm_cond.horizontalAdvance(cond_txt) + 18)
        cond_h = max(18, fm_cond.height() + 4)
        self.cond_edit.setFixedSize(cond_w, cond_h)

        bar_w = max(8, fm_bar.horizontalAdvance("|") + 4)
        tot_h = max(f_h + cond_h // 2, 30)
        self.lbl_bar.setFixedSize(bar_w, tot_h)

        spacer_h = max(0, tot_h - cond_h - 2)
        self.sub_spacer.setFixedHeight(spacer_h)
        self.cond_container.setFixedSize(cond_w, tot_h)

        tot_w = f_w + bar_w + cond_w + 16
        self.setFixedSize(tot_w, tot_h)
        self.updateGeometry()

    def text_expression(self) -> str:
        f_txt = self.f_edit.text().strip() or "f"
        cond_txt = self.cond_edit.text().strip() or "x = a"
        return f"eval({f_txt}, {cond_txt})"


class BinomialWidget(QWidget):
    """
    Seamless inline 2D binomial coefficient widget: (n choose k)
    Displays tall parentheses with n stacked directly above k.
    """
    def __init__(self, top: str = "n", bot: str = "k", fid: int = 1, parent_edit=None):
        super().__init__(parent_edit.viewport() if parent_edit else None)
        self.fid = fid
        self.parent_edit = parent_edit
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("background: transparent;")

        h_layout = QHBoxLayout(self)
        h_layout.setContentsMargins(1, 0, 1, 0)
        h_layout.setSpacing(2)

        self.lbl_lparen = QLabel("(", self)
        self.lbl_lparen.setAlignment(Qt.AlignmentFlag.AlignCenter)
        h_layout.addWidget(self.lbl_lparen)

        self.col_mid = QWidget(self)
        v_mid = QVBoxLayout(self.col_mid)
        v_mid.setContentsMargins(0, 0, 0, 0)
        v_mid.setSpacing(2)

        self.top_edit = QLineEdit(top, self.col_mid)
        self.top_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.bot_edit = QLineEdit(bot, self.col_mid)
        self.bot_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v_mid.addWidget(self.top_edit)
        v_mid.addWidget(self.bot_edit)
        h_layout.addWidget(self.col_mid)

        self.lbl_rparen = QLabel(")", self)
        self.lbl_rparen.setAlignment(Qt.AlignmentFlag.AlignCenter)
        h_layout.addWidget(self.lbl_rparen)

        self.top_edit.textChanged.connect(self._on_text_changed)
        self.bot_edit.textChanged.connect(self._on_text_changed)

        self.top_edit.mousePressEvent = self._make_click_handler(self.top_edit)
        self.bot_edit.mousePressEvent = self._make_click_handler(self.bot_edit)

        self.top_edit.keyPressEvent = self._make_key_handler(self.top_edit, role="top")
        self.bot_edit.keyPressEvent = self._make_key_handler(self.bot_edit, role="bot")

        self.update_style()
        self._adjust_size()

    def _make_click_handler(self, edit_widget):
        orig_press = edit_widget.mousePressEvent
        def handler(event):
            had_focus = edit_widget.hasFocus()
            orig_press(event)
            self.update()
            if not had_focus and edit_widget.text().strip() in ("n", "k"):
                edit_widget.selectAll()
        return handler

    def _make_key_handler(self, edit_widget, role):
        orig_key = edit_widget.keyPressEvent
        def handler(event):
            if edit_widget.isReadOnly():
                orig_key(event)
                return
            key = event.key()
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if self.parent_edit:
                    if event.modifiers() & (Qt.KeyboardModifier.ShiftModifier | Qt.KeyboardModifier.AltModifier):
                        self.parent_edit._handle_inline_evaluation()
                    elif event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier):
                        self.parent_edit.executeRequested.emit()
                    else:
                        self.parent_edit.keyPressEvent(event)
                event.accept()
                return
            if key == Qt.Key.Key_Tab:
                if role == "top":
                    self.bot_edit.setFocus()
                    self.bot_edit.selectAll()
                elif role == "bot" and self.parent_edit:
                    self.parent_edit.move_cursor_after_fraction(self.fid)
                event.accept()
                return
            if key == Qt.Key.Key_Backtab:
                if role == "bot":
                    self.top_edit.setFocus()
                    self.top_edit.selectAll()
                elif role == "top" and self.parent_edit:
                    self.parent_edit.move_cursor_before_fraction(self.fid)
                event.accept()
                return
            if key == Qt.Key.Key_Down and role == "top":
                self.bot_edit.setFocus()
                self.bot_edit.selectAll()
                event.accept()
                return
            if key == Qt.Key.Key_Up and role == "bot":
                self.top_edit.setFocus()
                self.top_edit.selectAll()
                event.accept()
                return
            if key == Qt.Key.Key_Right and edit_widget.cursorPosition() == len(edit_widget.text()):
                if role == "top":
                    self.bot_edit.setFocus()
                    self.bot_edit.setCursorPosition(0)
                elif role == "bot" and self.parent_edit:
                    self.parent_edit.move_cursor_after_fraction(self.fid)
                event.accept()
                return
            if key == Qt.Key.Key_Left and edit_widget.cursorPosition() == 0:
                if role == "bot":
                    self.top_edit.setFocus()
                    self.top_edit.setCursorPosition(len(self.top_edit.text()))
                elif role == "top" and self.parent_edit:
                    self.parent_edit.move_cursor_before_fraction(self.fid)
                event.accept()
                return
            orig_key(event)
            self._adjust_size()
            if self.parent_edit:
                self.parent_edit._on_frac_size_changed(self)
        return handler

    def _on_text_changed(self):
        self._adjust_size()
        if self.parent_edit:
            self.parent_edit._on_frac_size_changed(self)

    def paintEvent(self, event):
        super().paintEvent(event)
        fw = QApplication.focusWidget()
        if fw and (self == fw or self.isAncestorOf(fw)):
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            pen = QPen(QColor("#93c5fd"), 1, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.setBrush(QColor(239, 246, 255, 130))
            r = self.rect().adjusted(0, 0, -1, -1)
            painter.drawRoundedRect(r, 2.0, 2.0)

    def update_style(self):
        sz = 13
        fam = "Times New Roman"
        is_dark = False
        if self.parent_edit and self.parent_edit.parent_cell:
            cell = self.parent_edit.parent_cell
            sz = getattr(cell, 'current_font_size', 13)
            fam = getattr(cell, 'current_font_family', "Times New Roman")
            factor = getattr(cell, 'zoom_factor', 1.0)
            sz = max(8, round(sz * factor))
            is_dark = (getattr(cell, 'theme_mode', 'light') == 'dark')

        color = "#f8fafc" if is_dark else "#000000"
        border_col = "#475569" if is_dark else "#cbd5e1"
        focus_bg = "#1e293b" if is_dark else "#eff6ff"
        focus_border = "#60a5fa" if is_dark else "#2563eb"

        paren_sz = max(18, int(sz * 2.2))
        font_paren = QFont(fam, paren_sz)
        self.lbl_lparen.setFont(font_paren)
        self.lbl_lparen.setStyleSheet(f"color: {color}; background: transparent; border: none; font-size: {paren_sz}pt; font-family: \"{fam}\";")
        self.lbl_rparen.setFont(font_paren)
        self.lbl_rparen.setStyleSheet(f"color: {color}; background: transparent; border: none; font-size: {paren_sz}pt; font-family: \"{fam}\";")

        font_slot = QFont(fam, sz)
        font_slot.setItalic(True)
        slot_style = f"""
            QLineEdit {{
                background: transparent;
                border: 1px dashed {border_col};
                border-radius: 2px;
                padding: 1px 4px;
                color: {color};
                font-family: \"{fam}\";
                font-size: {sz}pt;
                font-style: italic;
            }}
            QLineEdit:focus {{
                border: 1.5px solid {focus_border};
                background: {focus_bg};
            }}
        """
        self.top_edit.setFont(font_slot)
        self.top_edit.setStyleSheet(slot_style)
        self.bot_edit.setFont(font_slot)
        self.bot_edit.setStyleSheet(slot_style)

    def _adjust_size(self):
        fm = self.top_edit.fontMetrics()
        fm_paren = self.lbl_lparen.fontMetrics()

        top_txt = self.top_edit.text() or "n"
        bot_txt = self.bot_edit.text() or "k"

        w_mid = max(22, max(fm.horizontalAdvance(top_txt), fm.horizontalAdvance(bot_txt)) + 18)
        h_slot = max(18, fm.height() + 4)

        self.top_edit.setFixedSize(w_mid, h_slot)
        self.bot_edit.setFixedSize(w_mid, h_slot)
        tot_h = h_slot * 2 + 6
        self.col_mid.setFixedSize(w_mid, tot_h)

        paren_w = max(8, fm_paren.horizontalAdvance("(") + 3)
        self.lbl_lparen.setFixedSize(paren_w, tot_h)
        self.lbl_rparen.setFixedSize(paren_w, tot_h)

        tot_w = paren_w * 2 + w_mid + 10
        self.setFixedSize(tot_w, tot_h)
        self.updateGeometry()

    def text_expression(self) -> str:
        top_txt = self.top_edit.text().strip() or "n"
        bot_txt = self.bot_edit.text().strip() or "k"
        return f"binomial({top_txt}, {bot_txt})"


class LimitWidget(QWidget):
    """
    Seamless inline 2D limit widget: lim_(x -> a) f, lim_(x -> a⁻) f, lim_(x -> a⁺) f
    Displays operator 'lim' with variable/target underneath, followed by body expression f.
    Both fields (target, body) are editable and support Tab/Arrow navigation and CAS evaluation.
    """
    def __init__(self, target: str = "x → a", body: str = "f", direction: str = "",
                 fid: int = 1, parent_edit=None):
        super().__init__(parent_edit.viewport() if parent_edit else None)
        self.fid = fid
        self.parent_edit = parent_edit
        self.direction = direction  # '', '-', or '+'
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("background: transparent;")

        h_layout = QHBoxLayout(self)
        h_layout.setContentsMargins(2, 0, 2, 0)
        h_layout.setSpacing(3)

        self.col_lim = QWidget(self)
        v_lim = QVBoxLayout(self.col_lim)
        v_lim.setContentsMargins(0, 0, 0, 0)
        v_lim.setSpacing(1)

        self.lbl_lim = QLabel("lim", self.col_lim)
        self.lbl_lim.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v_lim.addWidget(self.lbl_lim)

        self.target_edit = QLineEdit(target, self.col_lim)
        self.target_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v_lim.addWidget(self.target_edit)
        h_layout.addWidget(self.col_lim)

        self.body_edit = MathSlotEdit(body, self)
        h_layout.addWidget(self.body_edit)

        self.target_edit.textChanged.connect(self._on_text_changed)
        self.body_edit.textChanged.connect(self._on_text_changed)

        self.target_edit.mousePressEvent = self._make_click_handler(self.target_edit)
        self.body_edit.mousePressEvent = self._make_click_handler(self.body_edit)

        self.target_edit.keyPressEvent = self._make_key_handler(self.target_edit, role="target")
        self.body_edit.keyPressEvent = self._make_key_handler(self.body_edit, role="body")

        self.update_style()
        self._adjust_size()

    def _make_click_handler(self, edit_widget):
        orig_press = edit_widget.mousePressEvent
        def handler(event):
            had_focus = edit_widget.hasFocus()
            orig_press(event)
            self.update()
            if not had_focus and edit_widget.text().strip() in ("f", "x → a", "x → a⁻", "x → a⁺", "x -> a", "x = a"):
                edit_widget.selectAll()
        return handler

    def _make_key_handler(self, edit_widget, role):
        orig_key = edit_widget.keyPressEvent
        def handler(event):
            if edit_widget.isReadOnly():
                orig_key(event)
                return
            key = event.key()
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if self.parent_edit:
                    if event.modifiers() & (Qt.KeyboardModifier.ShiftModifier | Qt.KeyboardModifier.AltModifier):
                        self.parent_edit._handle_inline_evaluation()
                    elif event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier):
                        self.parent_edit.executeRequested.emit()
                    else:
                        self.parent_edit.keyPressEvent(event)
                event.accept()
                return
            if key == Qt.Key.Key_Tab:
                if role == "target":
                    self.body_edit.setFocus()
                    self.body_edit.selectAll()
                elif role == "body" and self.parent_edit:
                    self.parent_edit.move_cursor_after_fraction(self.fid)
                event.accept()
                return
            if key == Qt.Key.Key_Backtab:
                if role == "body":
                    self.target_edit.setFocus()
                    self.target_edit.selectAll()
                elif role == "target" and self.parent_edit:
                    self.parent_edit.move_cursor_before_fraction(self.fid)
                event.accept()
                return
            if key == Qt.Key.Key_Right and edit_widget.cursorPosition() == len(edit_widget.text()):
                if role == "target":
                    self.body_edit.setFocus()
                    self.body_edit.setCursorPosition(0)
                elif role == "body" and self.parent_edit:
                    self.parent_edit.move_cursor_after_fraction(self.fid)
                event.accept()
                return
            if key == Qt.Key.Key_Left and edit_widget.cursorPosition() == 0:
                if role == "body":
                    self.target_edit.setFocus()
                    self.target_edit.setCursorPosition(len(self.target_edit.text()))
                elif role == "target" and self.parent_edit:
                    self.parent_edit.move_cursor_before_fraction(self.fid)
                event.accept()
                return
            orig_key(event)
            self._adjust_size()
            if self.parent_edit:
                self.parent_edit._on_frac_size_changed(self)
        return handler

    def _on_text_changed(self):
        self._adjust_size()
        if self.parent_edit:
            self.parent_edit._on_frac_size_changed(self)

    def paintEvent(self, event):
        super().paintEvent(event)
        fw = QApplication.focusWidget()
        if fw and (self == fw or self.isAncestorOf(fw)):
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            pen = QPen(QColor("#93c5fd"), 1, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.setBrush(QColor(239, 246, 255, 130))
            r = self.rect().adjusted(0, 0, -1, -1)
            painter.drawRoundedRect(r, 2.0, 2.0)

    def update_style(self):
        sz = 13
        fam = "Times New Roman"
        is_dark = False
        if self.parent_edit and self.parent_edit.parent_cell:
            cell = self.parent_edit.parent_cell
            sz = getattr(cell, 'current_font_size', 13)
            fam = getattr(cell, 'current_font_family', "Times New Roman")
            factor = getattr(cell, 'zoom_factor', 1.0)
            sz = max(8, round(sz * factor))
            is_dark = (getattr(cell, 'theme_mode', 'light') == 'dark')

        color = "#f8fafc" if is_dark else "#000000"
        border_col = "#475569" if is_dark else "#cbd5e1"
        focus_bg = "#1e293b" if is_dark else "#eff6ff"
        focus_border = "#60a5fa" if is_dark else "#2563eb"

        lim_font_sz = max(11, sz)
        font_lbl = QFont(fam, lim_font_sz)
        self.lbl_lim.setFont(font_lbl)
        self.lbl_lim.setStyleSheet(f"color: {color}; background: transparent; border: none; font-size: {lim_font_sz}pt; font-family: \"{fam}\"; font-weight: bold;")

        sub_sz = max(8, int(sz * 0.75))
        font_sub = QFont(fam, sub_sz)
        font_sub.setItalic(True)
        sub_style = f"""
            QLineEdit {{
                background: transparent;
                border: 1px dashed {border_col};
                border-radius: 2px;
                padding: 1px 3px;
                color: {color};
                font-family: \"{fam}\";
                font-size: {sub_sz}pt;
                font-style: italic;
            }}
            QLineEdit:focus {{
                border: 1.5px solid {focus_border};
                background: {focus_bg};
            }}
        """
        self.target_edit.setFont(font_sub)
        self.target_edit.setStyleSheet(sub_style)

        font_body = QFont(fam, sz)
        font_body.setItalic(True)
        body_style = f"""
            QLineEdit, QTextEdit {{
                background: transparent;
                border: 1px dashed {border_col};
                border-radius: 2px;
                padding: 1px 4px;
                color: {color};
                font-family: \"{fam}\";
                font-size: {sz}pt;
                font-style: italic;
            }}
            QLineEdit:focus, QTextEdit:focus {{
                border: 1.5px solid {focus_border};
                background: {focus_bg};
            }}
        """
        self.body_edit.setFont(font_body)
        self.body_edit.setStyleSheet(body_style)

    def _adjust_size(self):
        fm_lim = self.lbl_lim.fontMetrics()
        fm_sub = self.target_edit.fontMetrics()
        fm_body = self.body_edit.fontMetrics()

        tgt_txt = self.target_edit.text() or "x → a"
        body_txt = self.body_edit.text() or "f"

        lbl_w = fm_lim.horizontalAdvance("lim") + 6
        sub_w = max(32, fm_sub.horizontalAdvance(tgt_txt) + 18)
        col_w = max(lbl_w, sub_w)

        lbl_h = max(15, fm_lim.height())
        sub_h = max(16, fm_sub.height() + 4)
        self.lbl_lim.setFixedSize(col_w, lbl_h)
        self.target_edit.setFixedSize(col_w, sub_h)
        self.col_lim.setFixedSize(col_w, lbl_h + sub_h + 2)

        body_w = max(28, fm_body.horizontalAdvance(body_txt) + 22)
        body_h = max(24, fm_body.height() + 6)
        self.body_edit.setFixedSize(body_w, body_h)

        tot_w = col_w + body_w + 10
        tot_h = max(lbl_h + sub_h + 4, body_h + 4)
        self.setFixedSize(tot_w, tot_h)
        self.updateGeometry()

    def text_expression(self) -> str:
        body = self.body_edit.text().strip() or "f"
        target_str = self.target_edit.text().strip() or "x = a"
        dir_val = self.direction
        if "⁻" in target_str or target_str.endswith("^-") or target_str.endswith("-"):
            dir_val = "-"
            target_str = target_str.replace("⁻", "").replace("^-", "").rstrip("-").strip()
        elif "⁺" in target_str or target_str.endswith("^+") or target_str.endswith("+"):
            dir_val = "+"
            target_str = target_str.replace("⁺", "").replace("^+", "").rstrip("+").strip()

        var = "x"
        val = "a"
        for sep in ("->", "→", r"\to", "="):
            if sep in target_str:
                parts = target_str.split(sep, 1)
                var = parts[0].strip() or "x"
                val = parts[1].strip() or "a"
                break
        else:
            if target_str:
                val = target_str

        if dir_val in ("-", "'-'", "left"):
            return f"limit({body}, {var}, {val}, '-')"
        elif dir_val in ("+", "'+'", "right"):
            return f"limit({body}, {var}, {val}, '+')"
        else:
            return f"limit({body}, {var}, {val})"


class PiecewiseWidget(QWidget):
    """
    Seamless inline 2D piecewise function widget:
    { -x, x < 0
    {  x, otherwise
    Displays tall curly brace { with stacked case rows.
    """
    def __init__(self, expr1: str = "-x", cond1: str = "x < 0",
                 expr2: str = "x", cond2: str = "otherwise",
                 fid: int = 1, parent_edit=None):
        super().__init__(parent_edit.viewport() if parent_edit else None)
        self.fid = fid
        self.parent_edit = parent_edit
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("background: transparent;")

        h_layout = QHBoxLayout(self)
        h_layout.setContentsMargins(1, 0, 1, 0)
        h_layout.setSpacing(2)

        self.lbl_brace = QLabel("{", self)
        self.lbl_brace.setAlignment(Qt.AlignmentFlag.AlignCenter)
        h_layout.addWidget(self.lbl_brace)

        self.cases_col = QWidget(self)
        v_cases = QVBoxLayout(self.cases_col)
        v_cases.setContentsMargins(0, 0, 0, 0)
        v_cases.setSpacing(2)

        r1 = QWidget(self.cases_col)
        h_r1 = QHBoxLayout(r1)
        h_r1.setContentsMargins(0, 0, 0, 0)
        h_r1.setSpacing(3)
        self.expr1_edit = QLineEdit(expr1, r1)
        self.lbl_comma1 = QLabel(",", r1)
        self.cond1_edit = QLineEdit(cond1, r1)
        h_r1.addWidget(self.expr1_edit)
        h_r1.addWidget(self.lbl_comma1)
        h_r1.addWidget(self.cond1_edit)
        v_cases.addWidget(r1)

        r2 = QWidget(self.cases_col)
        h_r2 = QHBoxLayout(r2)
        h_r2.setContentsMargins(0, 0, 0, 0)
        h_r2.setSpacing(3)
        self.expr2_edit = QLineEdit(expr2, r2)
        self.lbl_comma2 = QLabel(",", r2)
        self.cond2_edit = QLineEdit(cond2, r2)
        h_r2.addWidget(self.expr2_edit)
        h_r2.addWidget(self.lbl_comma2)
        h_r2.addWidget(self.cond2_edit)
        v_cases.addWidget(r2)

        h_layout.addWidget(self.cases_col)

        self.expr1_edit.textChanged.connect(self._on_text_changed)
        self.cond1_edit.textChanged.connect(self._on_text_changed)
        self.expr2_edit.textChanged.connect(self._on_text_changed)
        self.cond2_edit.textChanged.connect(self._on_text_changed)

        for ed, role in [
            (self.expr1_edit, "e1"), (self.cond1_edit, "c1"),
            (self.expr2_edit, "e2"), (self.cond2_edit, "c2")
        ]:
            ed.mousePressEvent = self._make_click_handler(ed)
            ed.keyPressEvent = self._make_key_handler(ed, role=role)

        self.update_style()
        self._adjust_size()

    def _make_click_handler(self, edit_widget):
        orig_press = edit_widget.mousePressEvent
        def handler(event):
            had_focus = edit_widget.hasFocus()
            orig_press(event)
            self.update()
            if not had_focus and edit_widget.text().strip() in ("-x", "x < 0", "x", "otherwise"):
                edit_widget.selectAll()
        return handler

    def _make_key_handler(self, edit_widget, role):
        orig_key = edit_widget.keyPressEvent
        def handler(event):
            if edit_widget.isReadOnly():
                orig_key(event)
                return
            key = event.key()
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if self.parent_edit:
                    if event.modifiers() & (Qt.KeyboardModifier.ShiftModifier | Qt.KeyboardModifier.AltModifier):
                        self.parent_edit._handle_inline_evaluation()
                    elif event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier):
                        self.parent_edit.executeRequested.emit()
                    else:
                        self.parent_edit.keyPressEvent(event)
                event.accept()
                return
            if key == Qt.Key.Key_Tab:
                if role == "e1":
                    self.cond1_edit.setFocus()
                    self.cond1_edit.selectAll()
                elif role == "c1":
                    self.expr2_edit.setFocus()
                    self.expr2_edit.selectAll()
                elif role == "e2":
                    self.cond2_edit.setFocus()
                    self.cond2_edit.selectAll()
                elif role == "c2" and self.parent_edit:
                    self.parent_edit.move_cursor_after_fraction(self.fid)
                event.accept()
                return
            if key == Qt.Key.Key_Backtab:
                if role == "c2":
                    self.expr2_edit.setFocus()
                    self.expr2_edit.selectAll()
                elif role == "e2":
                    self.cond1_edit.setFocus()
                    self.cond1_edit.selectAll()
                elif role == "c1":
                    self.expr1_edit.setFocus()
                    self.expr1_edit.selectAll()
                elif role == "e1" and self.parent_edit:
                    self.parent_edit.move_cursor_before_fraction(self.fid)
                event.accept()
                return
            if key == Qt.Key.Key_Down and role in ("e1", "c1"):
                target = self.expr2_edit if role == "e1" else self.cond2_edit
                target.setFocus()
                target.selectAll()
                event.accept()
                return
            if key == Qt.Key.Key_Up and role in ("e2", "c2"):
                target = self.expr1_edit if role == "e2" else self.cond1_edit
                target.setFocus()
                target.selectAll()
                event.accept()
                return
            orig_key(event)
            self._adjust_size()
            if self.parent_edit:
                self.parent_edit._on_frac_size_changed(self)
        return handler

    def _on_text_changed(self):
        self._adjust_size()
        if self.parent_edit:
            self.parent_edit._on_frac_size_changed(self)

    def paintEvent(self, event):
        super().paintEvent(event)
        fw = QApplication.focusWidget()
        if fw and (self == fw or self.isAncestorOf(fw)):
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            pen = QPen(QColor("#93c5fd"), 1, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.setBrush(QColor(239, 246, 255, 130))
            r = self.rect().adjusted(0, 0, -1, -1)
            painter.drawRoundedRect(r, 2.0, 2.0)

    def update_style(self):
        sz = 13
        fam = "Times New Roman"
        is_dark = False
        if self.parent_edit and self.parent_edit.parent_cell:
            cell = self.parent_edit.parent_cell
            sz = getattr(cell, 'current_font_size', 13)
            fam = getattr(cell, 'current_font_family', "Times New Roman")
            factor = getattr(cell, 'zoom_factor', 1.0)
            sz = max(8, round(sz * factor))
            is_dark = (getattr(cell, 'theme_mode', 'light') == 'dark')

        color = "#f8fafc" if is_dark else "#000000"
        border_col = "#475569" if is_dark else "#cbd5e1"
        focus_bg = "#1e293b" if is_dark else "#eff6ff"
        focus_border = "#60a5fa" if is_dark else "#2563eb"

        brace_sz = max(20, int(sz * 2.4))
        font_brace = QFont(fam, brace_sz)
        self.lbl_brace.setFont(font_brace)
        self.lbl_brace.setStyleSheet(f"color: {color}; background: transparent; border: none; font-size: {brace_sz}pt; font-family: \"{fam}\";")

        font_slot = QFont(fam, sz)
        font_slot.setItalic(True)
        slot_style = f"""
            QLineEdit {{
                background: transparent;
                border: 1px dashed {border_col};
                border-radius: 2px;
                padding: 1px 3px;
                color: {color};
                font-family: \"{fam}\";
                font-size: {sz}pt;
                font-style: italic;
            }}
            QLineEdit:focus {{
                border: 1.5px solid {focus_border};
                background: {focus_bg};
            }}
        """
        for ed in (self.expr1_edit, self.cond1_edit, self.expr2_edit, self.cond2_edit):
            ed.setFont(font_slot)
            ed.setStyleSheet(slot_style)
        self.lbl_comma1.setStyleSheet(f"color: {color}; background: transparent; font-size: {sz}pt;")
        self.lbl_comma2.setStyleSheet(f"color: {color}; background: transparent; font-size: {sz}pt;")

    def _adjust_size(self):
        fm = self.expr1_edit.fontMetrics()
        fm_brace = self.lbl_brace.fontMetrics()

        e1_w = max(22, fm.horizontalAdvance(self.expr1_edit.text() or "-x") + 16)
        c1_w = max(28, fm.horizontalAdvance(self.cond1_edit.text() or "x < 0") + 16)
        e2_w = max(22, fm.horizontalAdvance(self.expr2_edit.text() or "x") + 16)
        c2_w = max(28, fm.horizontalAdvance(self.cond2_edit.text() or "otherwise") + 16)

        max_e_w = max(e1_w, e2_w)
        max_c_w = max(c1_w, c2_w)
        h_slot = max(18, fm.height() + 4)

        self.expr1_edit.setFixedSize(max_e_w, h_slot)
        self.expr2_edit.setFixedSize(max_e_w, h_slot)
        self.cond1_edit.setFixedSize(max_c_w, h_slot)
        self.cond2_edit.setFixedSize(max_c_w, h_slot)

        comma_w = max(6, fm.horizontalAdvance(",") + 2)
        self.lbl_comma1.setFixedSize(comma_w, h_slot)
        self.lbl_comma2.setFixedSize(comma_w, h_slot)

        row_w = max_e_w + comma_w + max_c_w + 6
        tot_h = h_slot * 2 + 6
        self.cases_col.setFixedSize(row_w, tot_h)

        brace_w = max(10, fm_brace.horizontalAdvance("{") + 4)
        self.lbl_brace.setFixedSize(brace_w, tot_h)

        tot_w = brace_w + row_w + 8
        self.setFixedSize(tot_w, tot_h)
        self.updateGeometry()

    def text_expression(self) -> str:
        e1 = self.expr1_edit.text().strip() or "-x"
        c1 = self.cond1_edit.text().strip() or "x < 0"
        e2 = self.expr2_edit.text().strip() or "x"
        c2 = self.cond2_edit.text().strip() or "otherwise"
        if c2.lower() in ("otherwise", "true", "else", "*"):
            return f"piecewise({c1}, {e1}, {e2})"
        return f"piecewise({c1}, {e1}, {c2}, {e2})"


class VectorWidget(QWidget):
    """
    Seamless inline 2D column vector widget:
    [ a ]
    [ b ]
    Displays brackets around stacked vector components.
    """
    def __init__(self, r1: str = "a", r2: str = "b", fid: int = 1, parent_edit=None):
        super().__init__(parent_edit.viewport() if parent_edit else None)
        self.fid = fid
        self.parent_edit = parent_edit
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("background: transparent;")

        h_layout = QHBoxLayout(self)
        h_layout.setContentsMargins(1, 0, 1, 0)
        h_layout.setSpacing(2)

        self.lbl_lbracket = QLabel("[", self)
        self.lbl_lbracket.setAlignment(Qt.AlignmentFlag.AlignCenter)
        h_layout.addWidget(self.lbl_lbracket)

        self.col_mid = QWidget(self)
        v_mid = QVBoxLayout(self.col_mid)
        v_mid.setContentsMargins(0, 0, 0, 0)
        v_mid.setSpacing(2)

        self.r1_edit = QLineEdit(r1, self.col_mid)
        self.r1_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.r2_edit = QLineEdit(r2, self.col_mid)
        self.r2_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v_mid.addWidget(self.r1_edit)
        v_mid.addWidget(self.r2_edit)
        h_layout.addWidget(self.col_mid)

        self.lbl_rbracket = QLabel("]", self)
        self.lbl_rbracket.setAlignment(Qt.AlignmentFlag.AlignCenter)
        h_layout.addWidget(self.lbl_rbracket)

        self.r1_edit.textChanged.connect(self._on_text_changed)
        self.r2_edit.textChanged.connect(self._on_text_changed)

        self.r1_edit.mousePressEvent = self._make_click_handler(self.r1_edit)
        self.r2_edit.mousePressEvent = self._make_click_handler(self.r2_edit)

        self.r1_edit.keyPressEvent = self._make_key_handler(self.r1_edit, role="r1")
        self.r2_edit.keyPressEvent = self._make_key_handler(self.r2_edit, role="r2")

        self.update_style()
        self._adjust_size()

    def _make_click_handler(self, edit_widget):
        orig_press = edit_widget.mousePressEvent
        def handler(event):
            had_focus = edit_widget.hasFocus()
            orig_press(event)
            self.update()
            if not had_focus and edit_widget.text().strip() in ("a", "b"):
                edit_widget.selectAll()
        return handler

    def _make_key_handler(self, edit_widget, role):
        orig_key = edit_widget.keyPressEvent
        def handler(event):
            if edit_widget.isReadOnly():
                orig_key(event)
                return
            key = event.key()
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if self.parent_edit:
                    if event.modifiers() & (Qt.KeyboardModifier.ShiftModifier | Qt.KeyboardModifier.AltModifier):
                        self.parent_edit._handle_inline_evaluation()
                    elif event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier):
                        self.parent_edit.executeRequested.emit()
                    else:
                        self.parent_edit.keyPressEvent(event)
                event.accept()
                return
            if key == Qt.Key.Key_Tab:
                if role == "r1":
                    self.r2_edit.setFocus()
                    self.r2_edit.selectAll()
                elif role == "r2" and self.parent_edit:
                    self.parent_edit.move_cursor_after_fraction(self.fid)
                event.accept()
                return
            if key == Qt.Key.Key_Backtab:
                if role == "r2":
                    self.r1_edit.setFocus()
                    self.r1_edit.selectAll()
                elif role == "r1" and self.parent_edit:
                    self.parent_edit.move_cursor_before_fraction(self.fid)
                event.accept()
                return
            if key == Qt.Key.Key_Down and role == "r1":
                self.r2_edit.setFocus()
                self.r2_edit.selectAll()
                event.accept()
                return
            if key == Qt.Key.Key_Up and role == "r2":
                self.r1_edit.setFocus()
                self.r1_edit.selectAll()
                event.accept()
                return
            if key == Qt.Key.Key_Right and edit_widget.cursorPosition() == len(edit_widget.text()):
                if role == "r1":
                    self.r2_edit.setFocus()
                    self.r2_edit.setCursorPosition(0)
                elif role == "r2" and self.parent_edit:
                    self.parent_edit.move_cursor_after_fraction(self.fid)
                event.accept()
                return
            if key == Qt.Key.Key_Left and edit_widget.cursorPosition() == 0:
                if role == "r2":
                    self.r1_edit.setFocus()
                    self.r1_edit.setCursorPosition(len(self.r1_edit.text()))
                elif role == "r1" and self.parent_edit:
                    self.parent_edit.move_cursor_before_fraction(self.fid)
                event.accept()
                return
            orig_key(event)
            self._adjust_size()
            if self.parent_edit:
                self.parent_edit._on_frac_size_changed(self)
        return handler

    def _on_text_changed(self):
        self._adjust_size()
        if self.parent_edit:
            self.parent_edit._on_frac_size_changed(self)

    def paintEvent(self, event):
        super().paintEvent(event)
        fw = QApplication.focusWidget()
        if fw and (self == fw or self.isAncestorOf(fw)):
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            pen = QPen(QColor("#93c5fd"), 1, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.setBrush(QColor(239, 246, 255, 130))
            r = self.rect().adjusted(0, 0, -1, -1)
            painter.drawRoundedRect(r, 2.0, 2.0)

    def update_style(self):
        sz = 13
        fam = "Times New Roman"
        is_dark = False
        if self.parent_edit and self.parent_edit.parent_cell:
            cell = self.parent_edit.parent_cell
            sz = getattr(cell, 'current_font_size', 13)
            fam = getattr(cell, 'current_font_family', "Times New Roman")
            factor = getattr(cell, 'zoom_factor', 1.0)
            sz = max(8, round(sz * factor))
            is_dark = (getattr(cell, 'theme_mode', 'light') == 'dark')

        color = "#f8fafc" if is_dark else "#000000"
        border_col = "#475569" if is_dark else "#cbd5e1"
        focus_bg = "#1e293b" if is_dark else "#eff6ff"
        focus_border = "#60a5fa" if is_dark else "#2563eb"

        bracket_sz = max(18, int(sz * 2.2))
        font_b = QFont(fam, bracket_sz)
        self.lbl_lbracket.setFont(font_b)
        self.lbl_lbracket.setStyleSheet(f"color: {color}; background: transparent; border: none; font-size: {bracket_sz}pt; font-family: \"{fam}\";")
        self.lbl_rbracket.setFont(font_b)
        self.lbl_rbracket.setStyleSheet(f"color: {color}; background: transparent; border: none; font-size: {bracket_sz}pt; font-family: \"{fam}\";")

        font_slot = QFont(fam, sz)
        font_slot.setItalic(True)
        slot_style = f"""
            QLineEdit {{
                background: transparent;
                border: 1px dashed {border_col};
                border-radius: 2px;
                padding: 1px 3px;
                color: {color};
                font-family: \"{fam}\";
                font-size: {sz}pt;
                font-style: italic;
            }}
            QLineEdit:focus {{
                border: 1.5px solid {focus_border};
                background: {focus_bg};
            }}
        """
        self.r1_edit.setFont(font_slot)
        self.r1_edit.setStyleSheet(slot_style)
        self.r2_edit.setFont(font_slot)
        self.r2_edit.setStyleSheet(slot_style)

    def _adjust_size(self):
        fm = self.r1_edit.fontMetrics()
        fm_b = self.lbl_lbracket.fontMetrics()

        r1_txt = self.r1_edit.text() or "a"
        r2_txt = self.r2_edit.text() or "b"

        w_mid = max(22, max(fm.horizontalAdvance(r1_txt), fm.horizontalAdvance(r2_txt)) + 18)
        h_slot = max(18, fm.height() + 4)

        self.r1_edit.setFixedSize(w_mid, h_slot)
        self.r2_edit.setFixedSize(w_mid, h_slot)
        tot_h = h_slot * 2 + 6
        self.col_mid.setFixedSize(w_mid, tot_h)

        b_w = max(8, fm_b.horizontalAdvance("[") + 3)
        self.lbl_lbracket.setFixedSize(b_w, tot_h)
        self.lbl_rbracket.setFixedSize(b_w, tot_h)

        tot_w = b_w * 2 + w_mid + 10
        self.setFixedSize(tot_w, tot_h)
        self.updateGeometry()

    def text_expression(self) -> str:
        r1_txt = self.r1_edit.text().strip() or "a"
        r2_txt = self.r2_edit.text().strip() or "b"
        return f"Vector([{r1_txt}, {r2_txt}])"


class MatrixWidget(QWidget):
    """
    Seamless inline 2D matrix widget (M x N):
    [ a11  a12  ... ]
    [ a21  a22  ... ]
    Displays authentic mathematical square brackets around a grid of matrix cells.
    """
    def __init__(self, rows: int = 2, cols: int = 2, data: list = None, fid: int = 1, parent_edit=None, is_result: bool = False, read_only: bool = False):
        super().__init__(parent_edit.viewport() if parent_edit else None)
        self.fid = fid
        self.parent_edit = parent_edit
        self.is_result = is_result
        self.read_only = read_only or is_result

        # Normalize data matrix
        if data is not None and isinstance(data, list) and len(data) > 0:
            self.num_rows = len(data)
            self.num_cols = max(len(r) if isinstance(r, list) else 1 for r in data)
            self._initial_data = []
            for r in range(self.num_rows):
                row_list = []
                r_src = data[r] if isinstance(data[r], list) else [data[r]]
                for c in range(self.num_cols):
                    val = str(r_src[c]) if c < len(r_src) else "0"
                    row_list.append(val)
                self._initial_data.append(row_list)
        else:
            self.num_rows = max(1, rows)
            self.num_cols = max(1, cols)
            self._initial_data = [["0" for _ in range(self.num_cols)] for _ in range(self.num_rows)]

        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("background: transparent;")

        h_layout = QHBoxLayout(self)
        h_layout.setContentsMargins(10, 4, 10, 4)
        h_layout.setSpacing(0)

        self.grid_widget = QWidget(self)
        self.grid_layout = QGridLayout(self.grid_widget)
        self.grid_layout.setContentsMargins(0, 0, 0, 0)
        self.grid_layout.setSpacing(4)
        h_layout.addWidget(self.grid_widget)

        self.cells = []
        for r in range(self.num_rows):
            row_cells = []
            for c in range(self.num_cols):
                val_txt = self._initial_data[r][c]
                edit = QLineEdit(val_txt, self.grid_widget)
                edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
                if self.read_only:
                    edit.setReadOnly(True)
                edit.textChanged.connect(self._on_text_changed)
                edit.mousePressEvent = self._make_click_handler(edit)
                edit.keyPressEvent = self._make_key_handler(edit, r, c)
                self.grid_layout.addWidget(edit, r, c)
                row_cells.append(edit)
            self.cells.append(row_cells)

        self.bracket_color_str = "#000000"
        self.update_style()
        self._adjust_size()

    def _make_click_handler(self, edit_widget):
        orig_press = edit_widget.mousePressEvent
        def handler(event):
            had_focus = edit_widget.hasFocus()
            orig_press(event)
            self.update()
            if not had_focus and not self.read_only:
                edit_widget.selectAll()
        return handler

    def _make_key_handler(self, edit_widget, r: int, c: int):
        orig_key = edit_widget.keyPressEvent
        def handler(event):
            if edit_widget.isReadOnly():
                orig_key(event)
                return
            key = event.key()
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if self.parent_edit:
                    if event.modifiers() & (Qt.KeyboardModifier.ShiftModifier | Qt.KeyboardModifier.AltModifier):
                        self.parent_edit._handle_inline_evaluation()
                    elif event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier):
                        self.parent_edit.executeRequested.emit()
                    else:
                        self.parent_edit.keyPressEvent(event)
                event.accept()
                return

            if key == Qt.Key.Key_Tab:
                if c + 1 < self.num_cols:
                    nxt = self.cells[r][c + 1]
                    nxt.setFocus()
                    nxt.selectAll()
                elif r + 1 < self.num_rows:
                    nxt = self.cells[r + 1][0]
                    nxt.setFocus()
                    nxt.selectAll()
                elif self.parent_edit:
                    self.parent_edit.move_cursor_after_fraction(self.fid)
                event.accept()
                return

            if key == Qt.Key.Key_Backtab:
                if c > 0:
                    prv = self.cells[r][c - 1]
                    prv.setFocus()
                    prv.selectAll()
                elif r > 0:
                    prv = self.cells[r - 1][self.num_cols - 1]
                    prv.setFocus()
                    prv.selectAll()
                elif self.parent_edit:
                    self.parent_edit.move_cursor_before_fraction(self.fid)
                event.accept()
                return

            if key == Qt.Key.Key_Down and r + 1 < self.num_rows:
                nxt = self.cells[r + 1][c]
                nxt.setFocus()
                nxt.selectAll()
                event.accept()
                return

            if key == Qt.Key.Key_Up and r > 0:
                nxt = self.cells[r - 1][c]
                nxt.setFocus()
                nxt.selectAll()
                event.accept()
                return

            if key == Qt.Key.Key_Right and edit_widget.cursorPosition() == len(edit_widget.text()):
                if c + 1 < self.num_cols:
                    nxt = self.cells[r][c + 1]
                    nxt.setFocus()
                    nxt.setCursorPosition(0)
                elif r + 1 < self.num_rows:
                    nxt = self.cells[r + 1][0]
                    nxt.setFocus()
                    nxt.setCursorPosition(0)
                elif self.parent_edit:
                    self.parent_edit.move_cursor_after_fraction(self.fid)
                event.accept()
                return

            if key == Qt.Key.Key_Left and edit_widget.cursorPosition() == 0:
                if c > 0:
                    prv = self.cells[r][c - 1]
                    prv.setFocus()
                    prv.setCursorPosition(len(prv.text()))
                elif r > 0:
                    prv = self.cells[r - 1][self.num_cols - 1]
                    prv.setFocus()
                    prv.setCursorPosition(len(prv.text()))
                elif self.parent_edit:
                    self.parent_edit.move_cursor_before_fraction(self.fid)
                event.accept()
                return

            orig_key(event)
            self._adjust_size()
            if self.parent_edit:
                self.parent_edit._on_frac_size_changed(self)
        return handler

    def _on_text_changed(self):
        self._adjust_size()
        if self.parent_edit:
            self.parent_edit._on_frac_size_changed(self)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        fw = QApplication.focusWidget()
        if fw and (self == fw or self.isAncestorOf(fw)):
            pen_f = QPen(QColor("#93c5fd"), 1, Qt.PenStyle.DashLine)
            painter.setPen(pen_f)
            painter.setBrush(QColor(239, 246, 255, 90))
            r = self.rect().adjusted(1, 1, -2, -2)
            painter.drawRoundedRect(r, 2.0, 2.0)

        bracket_color = QColor(self.bracket_color_str)
        pen_b = QPen(bracket_color, 1.8)
        pen_b.setCapStyle(Qt.PenCapStyle.SquareCap)
        pen_b.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
        painter.setPen(pen_b)

        # Left bracket: [
        b_left = 3
        y_top = 2
        y_bot = self.height() - 3
        arm = 6
        painter.drawLine(b_left + arm, y_top, b_left, y_top)
        painter.drawLine(b_left, y_top, b_left, y_bot)
        painter.drawLine(b_left, y_bot, b_left + arm, y_bot)

        # Right bracket: ]
        b_right = self.width() - 4
        painter.drawLine(b_right - arm, y_top, b_right, y_top)
        painter.drawLine(b_right, y_top, b_right, y_bot)
        painter.drawLine(b_right, y_bot, b_right - arm, y_bot)

    def update_style(self):
        from .theme import Theme
        sz = 13
        fam = "Times New Roman"
        is_dark = False
        if self.parent_edit and self.parent_edit.parent_cell:
            cell = self.parent_edit.parent_cell
            sz = getattr(cell, 'current_font_size', 13)
            fam = getattr(cell, 'current_font_family', "Times New Roman")
            factor = getattr(cell, 'zoom_factor', 1.0)
            sz = max(8, round(sz * factor))
            is_dark = (getattr(cell, 'theme_mode', 'light') == 'dark')

        if self.is_result:
            color = Theme.DARK_MATH_BLUE if is_dark else Theme.OPENMATH_MATH_BLUE
            self.bracket_color_str = color
            border_col = "transparent"
        else:
            color = "#f8fafc" if is_dark else "#000000"
            self.bracket_color_str = color
            border_col = "#475569" if is_dark else "#cbd5e1"

        focus_bg = "#1e293b" if is_dark else "#eff6ff"
        focus_border = "#60a5fa" if is_dark else "#2563eb"

        font_slot = QFont(fam, sz)
        font_slot.setItalic(False)

        slot_style = f"""
            QLineEdit {{
                background: transparent;
                border: 1px dashed {border_col};
                border-radius: 2px;
                padding: 1px 3px;
                color: {color};
                font-family: "{fam}";
                font-size: {sz}pt;
            }}
            QLineEdit:focus {{
                border: 1.5px solid {focus_border};
                background: {focus_bg};
            }}
        """
        for row in self.cells:
            for edit in row:
                edit.setFont(font_slot)
                edit.setStyleSheet(slot_style)

    def _adjust_size(self):
        if not self.cells:
            return
        fm = self.cells[0][0].fontMetrics()
        col_widths = []
        for c in range(self.num_cols):
            max_adv = 0
            for r in range(self.num_rows):
                txt = self.cells[r][c].text() or "0"
                adv = fm.horizontalAdvance(txt)
                if adv > max_adv:
                    max_adv = adv
            col_w = max(22, max_adv + 14)
            col_widths.append(col_w)

        row_h = max(20, fm.height() + 4)
        spacing = 4
        for r in range(self.num_rows):
            for c in range(self.num_cols):
                self.cells[r][c].setFixedSize(col_widths[c], row_h)

        grid_w = sum(col_widths) + max(0, self.num_cols - 1) * spacing
        grid_h = self.num_rows * row_h + max(0, self.num_rows - 1) * spacing
        self.grid_widget.setFixedSize(grid_w, grid_h)

        tot_w = grid_w + 20
        tot_h = grid_h + 8
        self.setFixedSize(tot_w, tot_h)
        self.updateGeometry()

    def text_expression(self) -> str:
        rows = []
        for r in range(self.num_rows):
            row_items = []
            for c in range(self.num_cols):
                t = self.cells[r][c].text().strip() or "0"
                row_items.append(t)
            rows.append("[" + ", ".join(row_items) + "]")
        return f"Matrix([{', '.join(rows)}])"


class CellInputEdit(QTextEdit):
    """
    Input editor supporting 2-D Math, 1-D Math, Nonexecutable Math, and Text modes.
    Handles Enter (evaluate), Shift+Enter (newline), Tab (placeholder navigation),
    F5 (mode toggle), and Esc / Ctrl+Space (command completion).
    Preserves text type (Text vs Nonexecutable Math vs Math) per character/span.
    """
    executeRequested = pyqtSignal()
    modeToggleRequested = pyqtSignal()
    navigateUp = pyqtSignal()
    navigateDown = pyqtSignal()

    def __init__(self, parent=None, parent_cell=None):
        super().__init__(parent)
        self.parent_cell = parent_cell
        self.current_typing_mode = getattr(parent_cell, 'input_mode', '2d_math') if parent_cell else '2d_math'
        self._pending_mode = None
        self._last_cursor_pos = -1
        self._is_bold = False
        self._is_italic = None
        self._is_underline = False
        self.frac_widgets = {}
        self._fraction_id_counter = 0
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursorWidth(2)
        self.setTabChangesFocus(False)
        self.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setStyleSheet("background: transparent; border: none; padding: 0px; selection-background-color: #2563eb; selection-color: #ffffff;")

        # Autocompleter
        self.completer = QCompleter(MATH_COMPLETIONS, self)
        self.completer.setWidget(self)
        self.completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.completer.activated.connect(self._insert_completion)

        self.document().contentsChanged.connect(self._adjust_height)
        self.document().contentsChanged.connect(self._reposition_fractions)
        self.document().contentsChanged.connect(self._update_tall_parentheses)
        self.textChanged.connect(self._on_text_changed_clear_error)
        self.cursorPositionChanged.connect(self._on_cursor_position_changed)
        self._just_evaluated_inline = False
        self._subscript_active = False
        self._superscript_active = False
        self._active_text_color = None
        self._active_highlight_color = None
        self.setFixedHeight(26)
        self._is_cross_cell_drag = False
        self._drag_start_global_pos = None

        pal = self.palette()
        pal.setColor(QPalette.ColorGroup.Inactive, QPalette.ColorRole.Highlight, QColor("#2563eb"))
        pal.setColor(QPalette.ColorGroup.Inactive, QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
        self.setPalette(pal)

        # Image selection & interactive resizing state
        self.setMouseTracking(True)
        self.viewport().setMouseTracking(True)
        self._selected_image_pos = None
        self._hovered_image_pos = None
        self._resizing_image = False
        self._resize_corner = None
        self._resize_image_pos = None
        self._resize_start_mouse = None
        self._resize_start_w = 100.0
        self._resize_start_h = 100.0
        self._resize_ratio = 1.0

        init_fmt = self._get_char_format_for_mode(self.current_typing_mode)
        self.setCurrentCharFormat(init_fmt)
        self.math_highlighter = Math2DHighlighter(self)

    def set_editable(self, editable: bool):
        self.setReadOnly(not editable)
        for le in self.findChildren(QLineEdit):
            le.setReadOnly(not editable)

    def _get_char_format_for_mode(self, mode: str) -> QTextCharFormat:
        sz = getattr(self.parent_cell, 'current_font_size', 12) if self.parent_cell else 12
        if not isinstance(sz, int) or sz <= 0:
            sz = 12
        fam = getattr(self.parent_cell, 'current_font_family', "Times New Roman") or "Times New Roman" if self.parent_cell else "Times New Roman"
        factor = getattr(self.parent_cell, 'zoom_factor', 1.0) if self.parent_cell else 1.0
        display_sz = max(4, round(sz * factor))

        fmt = QTextCharFormat()
        fmt.setFontPointSize(display_sz)
        fmt.setProperty(PROP_MODE, mode)

        if getattr(self, '_is_bold', False):
            fmt.setFontWeight(QFont.Weight.Bold)
        else:
            fmt.setFontWeight(QFont.Weight.Normal)

        if getattr(self, '_is_underline', False):
            fmt.setFontUnderline(True)
        else:
            fmt.setFontUnderline(False)

        is_dark = (getattr(self.parent_cell, 'theme_mode', 'light') == 'dark') if self.parent_cell else False
        if mode == getattr(self.parent_cell, 'MODE_2D_MATH', '2d_math'):
            fmt.setFontFamily(fam)
            fmt.setFontItalic(True if getattr(self, '_is_italic', None) is None else self._is_italic)
            fmt.setForeground(QColor("#f8fafc" if is_dark else "#000000"))
        elif mode == getattr(self.parent_cell, 'MODE_NONEXEC_MATH', 'nonexec_math'):
            fmt.setFontFamily(fam)
            fmt.setFontItalic(False if getattr(self, '_is_italic', None) is None else self._is_italic)  # Nonexecutable math is upright
            fmt.setForeground(QColor("#f8fafc" if is_dark else "#1e293b"))
        elif mode == getattr(self.parent_cell, 'MODE_1D_MATH', '1d_math'):
            c_fam = "Courier New" if "Courier" in fam or "Consolas" in fam else fam
            fmt.setFontFamily(c_fam)
            fmt.setFontItalic(False if getattr(self, '_is_italic', None) is None else self._is_italic)
            fmt.setForeground(QColor("#fb7185" if is_dark else "#b22222"))
        else:  # Text mode
            fmt.setFontFamily(fam)
            fmt.setFontItalic(False if getattr(self, '_is_italic', None) is None else self._is_italic)  # Normal text (NOT italic)
            fmt.setForeground(QColor("#f8fafc" if is_dark else "#1e293b"))

        return fmt

    def update_theme(self, mode: str):
        """Update editor colors, cursor, palette, and existing document spans for active theme."""
        is_dark = (mode == 'dark')
        pal = self.palette()
        sel_bg = QColor("#0284c7" if is_dark else "#2563eb")
        pal.setColor(QPalette.ColorRole.Highlight, sel_bg)
        pal.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
        pal.setColor(QPalette.ColorGroup.Inactive, QPalette.ColorRole.Highlight, sel_bg)
        pal.setColor(QPalette.ColorGroup.Inactive, QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
        self.setPalette(pal)

        cursor = QTextCursor(self.document())
        cursor.beginEditBlock()
        while not cursor.atEnd():
            cursor.movePosition(QTextCursor.MoveOperation.NextCharacter, QTextCursor.MoveMode.KeepAnchor)
            fmt = cursor.charFormat()
            char_mode = fmt.property(PROP_MODE) or self.current_typing_mode
            if char_mode == '1d_math':
                fmt.setForeground(QColor("#fb7185" if is_dark else "#b22222"))
            elif char_mode == '2d_math':
                fmt.setForeground(QColor("#f8fafc" if is_dark else "#000000"))
            else:
                fmt.setForeground(QColor("#f8fafc" if is_dark else "#1e293b"))
            cursor.setCharFormat(fmt)
            cursor.clearSelection()
        cursor.endEditBlock()

        curr_fmt = self._get_char_format_for_mode(self.current_typing_mode)
        self.setCurrentCharFormat(curr_fmt)

        for le in self.findChildren(QLineEdit):
            le.setStyleSheet(f"""
                QLineEdit {{
                    background-color: {'#18202e' if is_dark else '#ffffff'};
                    color: {'#f8fafc' if is_dark else '#000000'};
                    border: 1px solid {'#2b384c' if is_dark else '#cbd5e1'};
                    border-radius: 2px;
                }}
            """)

    def _get_subscript_format(self, level: int = 0) -> QTextCharFormat:
        """
        Return QTextCharFormat for the given subscript depth:
        level 0: baseline font size, 0.0 offset
        level 1: 80% font size, lowered baseline (-28% base size)
        level 2: 70% font size, lowered further (-50% base size)
        level 3+: 65% font size, lowered further (-68% base size)
        """
        base_fmt = self._get_char_format_for_mode(self.current_typing_mode)
        fmt = QTextCharFormat(base_fmt)
        sz = base_fmt.fontPointSize()
        if sz <= 0:
            sz = 12.0

        if level == 1:
            fmt.setFontPointSize(round(sz * 0.80, 1))
            fmt.setBaselineOffset(round(-sz * 0.28, 1))
            fmt.setProperty(PROP_SUBSCRIPT_LEVEL, 1)
        elif level == 2:
            fmt.setFontPointSize(round(sz * 0.70, 1))
            fmt.setBaselineOffset(round(-sz * 0.50, 1))
            fmt.setProperty(PROP_SUBSCRIPT_LEVEL, 2)
        elif level >= 3:
            fmt.setFontPointSize(round(sz * 0.65, 1))
            fmt.setBaselineOffset(round(-sz * 0.68, 1))
            fmt.setProperty(PROP_SUBSCRIPT_LEVEL, level)
        else:
            fmt.setFontPointSize(sz)
            fmt.setBaselineOffset(0.0)
            fmt.setProperty(PROP_SUBSCRIPT_LEVEL, 0)

        if getattr(self, '_active_text_color', None):
            fmt.setForeground(self._active_text_color)
        if getattr(self, '_active_highlight_color', None):
            fmt.setBackground(self._active_highlight_color)

        return fmt

    def _insert_chunk_with_punctuation(self, cursor: QTextCursor, text: str, fmt_base: QTextCharFormat, fmt_upright: QTextCharFormat):
        if not text:
            return
        punc_pat = re.compile(r'([0-9.,:;=+\-*/()\[\]{}·\s]+)')
        for part in punc_pat.split(text):
            if not part:
                continue
            if punc_pat.fullmatch(part):
                cursor.insertText(part, fmt_upright)
            else:
                cursor.insertText(part, fmt_base)

    def insert_stepped_math_text(self, text: str, cursor: Optional[QTextCursor] = None):
        """
        Insert math text with stepped lowered subscripts for identifiers with underscores,
        e.g. 'two_comp_repr(-5, 8)' -> 'two' (baseline), 'comp' (lower), 'repr' (lowered), '(-5, 8)' (baseline).
        """
        if cursor is None:
            cursor = self.textCursor()

        fmt_base = self._get_subscript_format(0)
        fmt_upright = QTextCharFormat(fmt_base)
        fmt_upright.setFontItalic(False)

        pattern = re.compile(r'\b([a-zA-Z][a-zA-Z0-9]*)(_[a-zA-Z0-9_]+)\b')
        last_idx = 0
        for m in pattern.finditer(text):
            start, end = m.span()
            if start > last_idx:
                non_match = text[last_idx:start]
                self._insert_chunk_with_punctuation(cursor, non_match, fmt_base, fmt_upright)
            base_name = m.group(1)
            sub_chain = m.group(2).split('_')[1:]

            if len(sub_chain) == 1 and all(c in SUB_MAP for c in sub_chain[0]) and len(sub_chain[0]) <= 2:
                unicode_sub = ''.join(SUB_MAP[c] for c in sub_chain[0])
                cursor.insertText(base_name + unicode_sub, fmt_base)
            else:
                cursor.insertText(base_name, fmt_base)
                for lvl, sub_part in enumerate(sub_chain, start=1):
                    cursor.insertText(sub_part, self._get_subscript_format(lvl))
            last_idx = end

        if last_idx < len(text):
            rem = text[last_idx:]
            self._insert_chunk_with_punctuation(cursor, rem, fmt_base, fmt_upright)

        self.setCurrentCharFormat(self._get_subscript_format(0))
        self.setTextCursor(cursor)

    def set_stepped_math_text(self, text: str):
        self.setPlainText("")
        cursor = self.textCursor()
        self.insert_stepped_math_text(text, cursor)

    def set_mode(self, mode: str):
        self.current_typing_mode = mode
        self._pending_mode = mode
        fmt = self._get_char_format_for_mode(mode)
        if getattr(self, '_active_text_color', None):
            fmt.setForeground(self._active_text_color)
        if getattr(self, '_active_highlight_color', None):
            fmt.setBackground(self._active_highlight_color)
        cursor = self.textCursor()
        if cursor.hasSelection():
            cursor.mergeCharFormat(fmt)
        else:
            self.setCurrentCharFormat(fmt)
        self.viewport().update()

    def get_mode_at_cursor(self) -> str:
        if getattr(self, '_pending_mode', None):
            return self._pending_mode
        cursor = self.textCursor()
        pos = cursor.position()
        doc = self.document()
        if pos > 0:
            c = self.textCursor()
            c.setPosition(pos - 1)
            c.setPosition(pos, QTextCursor.MoveMode.KeepAnchor)
            fmt = c.charFormat()
            mode = fmt.property(PROP_MODE)
            if mode:
                return mode
        elif doc.characterCount() > 1:
            c = self.textCursor()
            c.setPosition(0)
            c.setPosition(1, QTextCursor.MoveMode.KeepAnchor)
            fmt = c.charFormat()
            mode = fmt.property(PROP_MODE)
            if mode:
                return mode
        return getattr(self, 'current_typing_mode', getattr(self.parent_cell, 'input_mode', '2d_math'))

    def _on_cursor_position_changed(self):
        pos = self.textCursor().position()
        if pos != getattr(self, '_last_cursor_pos', -1):
            self._last_cursor_pos = pos
            self._pending_mode = None
            mode = self.get_mode_at_cursor()
            self.current_typing_mode = mode
            fmt = self._get_char_format_for_mode(mode)
            if not self.textCursor().hasSelection():
                cf = self.textCursor().charFormat()
                if cf.hasProperty(QTextCharFormat.Property.FontPointSize):
                    cur_pt = cf.fontPointSize()
                    if cur_pt > 0:
                        fmt.setFontPointSize(cur_pt)
                if cf.hasProperty(QTextCharFormat.Property.FontFamilies):
                    fams = cf.fontFamilies()
                    cur_fam = fams[0] if (isinstance(fams, list) and fams) else (fams if isinstance(fams, str) and fams else None)
                    if cur_fam:
                        fmt.setFontFamilies([cur_fam])
                
                # Maintain active typing text foreground and background highlight color
                if getattr(self, '_active_text_color', None):
                    fmt.setForeground(self._active_text_color)
                elif cf.hasProperty(QTextFormat.Property.ForegroundBrush):
                    brush = cf.foreground()
                    if brush.style() != Qt.BrushStyle.NoBrush and brush.color().isValid():
                        fmt.setForeground(brush.color())

                if getattr(self, '_active_highlight_color', None):
                    fmt.setBackground(self._active_highlight_color)
                elif cf.hasProperty(QTextFormat.Property.BackgroundBrush):
                    brush = cf.background()
                    if brush.style() != Qt.BrushStyle.NoBrush and brush.color().isValid() and brush.color().alpha() > 0:
                        fmt.setBackground(brush)

                if cf.hasProperty(PROP_SUBSCRIPT_LEVEL):
                    lvl = cf.property(PROP_SUBSCRIPT_LEVEL)
                    if lvl:
                        fmt.setProperty(PROP_SUBSCRIPT_LEVEL, lvl)
                        fmt.setBaselineOffset(cf.baselineOffset())

                self.setCurrentCharFormat(fmt)
            if self.parent_cell:
                if self.parent_cell.input_mode != mode:
                    self.parent_cell.input_mode = mode
                    self.parent_cell._apply_prompt_styling(mode)
                self.parent_cell._on_cursor_changed()
            self.viewport().update()

    def setPlainText(self, text: str):
        self._clear_fractions()
        mode = getattr(self.parent_cell, 'input_mode', getattr(self, 'current_typing_mode', '2d_math'))
        self.current_typing_mode = mode
        fmt = self._get_char_format_for_mode(mode)
        self.blockSignals(True)
        super().setPlainText(text)
        cursor = QTextCursor(self.document())
        cursor.select(QTextCursor.SelectionType.Document)
        cursor.setCharFormat(fmt)
        self.setCurrentCharFormat(fmt)
        self.blockSignals(False)
        self._adjust_height()

    def insert_image_object(self, qimg: QImage, max_width: int = None):
        """Insert a QImage into the document cursor, register it as a resource, and store base64."""
        if not qimg or qimg.isNull():
            return
        buf = QBuffer()
        buf.open(QIODevice.OpenModeFlag.WriteOnly)
        qimg.save(buf, "PNG")
        b64_png = base64.b64encode(buf.data().data()).decode('ascii')
        buf.close()

        img_id = f"img_{uuid.uuid4().hex[:8]}"
        if not hasattr(self, 'embedded_images'):
            self.embedded_images = {}
        self.embedded_images[img_id] = b64_png
        _GLOBAL_IMAGE_CACHE[img_id] = (qimg, b64_png)

        self.document().addResource(QTextDocument.ResourceType.ImageResource, QUrl(img_id), qimg)
        cursor = self.textCursor()
        fmt = QTextImageFormat()
        fmt.setName(img_id)

        target_max_w = max_width or max(700, self.viewport().width() - 40)
        if qimg.width() > target_max_w:
            scaled_h = max(20, int(qimg.height() * (target_max_w / qimg.width())))
            fmt.setWidth(target_max_w)
            fmt.setHeight(scaled_h)
        else:
            fmt.setWidth(qimg.width())
            fmt.setHeight(qimg.height())

        cursor.insertImage(fmt)
        self._adjust_height()

        # Switch cell to Text mode so the image is not in a cell / math box
        parent_cell = getattr(self, 'parent_cell', None)
        if parent_cell:
            if hasattr(parent_cell, 'set_input_mode') and hasattr(parent_cell, 'MODE_TEXT'):
                parent_cell.set_input_mode(parent_cell.MODE_TEXT)
            if hasattr(parent_cell, 'lbl_prompt'):
                parent_cell.lbl_prompt.setVisible(False)
            if hasattr(parent_cell, 'bracket_bar'):
                parent_cell.bracket_bar.setVisible(False)
            ws = self._get_worksheet_view() or (parent_cell._get_worksheet_view() if parent_cell else None)
            if ws:
                ws.active_cell = parent_cell
                ws.activeCellChanged.emit(parent_cell)

    def _create_or_focus_math_cell_below(self):
        """Create or focus a 2D Math execution block below when Enter is pressed in an image cell."""
        parent_cell = getattr(self, 'parent_cell', None)
        if not parent_cell:
            return None

        ws = self._get_worksheet_view() or (parent_cell._get_worksheet_view() if parent_cell else None)
        if not ws or not hasattr(ws, 'insert_cell_below'):
            return None

        # Trailing text handling: if cursor was before trailing text, move that text down
        cursor = self.textCursor()
        trailing_text = ""
        if cursor.position() < self.document().characterCount() - 1:
            trailing_cursor = QTextCursor(self.document())
            trailing_cursor.setPosition(cursor.position())
            trailing_cursor.movePosition(QTextCursor.MoveOperation.End, QTextCursor.MoveMode.KeepAnchor)
            raw_trailing = trailing_cursor.selectedText().replace('\ufffc', '').strip()
            if raw_trailing:
                trailing_text = raw_trailing
                trailing_cursor.removeSelectedText()

        # If next cell exists and is an empty non-section cell, reuse it
        idx = ws._get_cell_index_by_id(parent_cell.cell_id) if hasattr(ws, '_get_cell_index_by_id') else -1
        if idx != -1 and idx + 1 < len(ws.cells):
            next_c = ws.cells[idx + 1]
            if not getattr(next_c, 'is_section_header', False) and not next_c.get_input_text().strip():
                math_mode = getattr(next_c, 'MODE_2D_MATH', '2d_math')
                next_c.set_input_mode(math_mode)
                next_c.set_worksheet_mode(ws.is_worksheet_mode)
                if trailing_text:
                    next_c.set_input_text(trailing_text)
                    if hasattr(next_c, 'input_edit'):
                        next_c.input_edit.moveCursor(QTextCursor.MoveOperation.Start)
                ws.clear_cell_selection()
                ws.active_cell = next_c
                ws.activeCellChanged.emit(next_c)
                next_c.set_cell_focus()
                return next_c

        # Otherwise insert a fresh math execution block directly below parent_cell
        new_cell = ws.insert_cell_below(parent_cell.cell_id)
        if new_cell:
            math_mode = getattr(new_cell, 'MODE_2D_MATH', '2d_math')
            new_cell.set_input_mode(math_mode)
            new_cell.set_worksheet_mode(ws.is_worksheet_mode)
            if trailing_text:
                new_cell.set_input_text(trailing_text)
                if hasattr(new_cell, 'input_edit'):
                    new_cell.input_edit.moveCursor(QTextCursor.MoveOperation.Start)
            new_cell.set_cell_selected(False)
            ws.clear_cell_selection()
            ws.active_cell = new_cell
            ws.activeCellChanged.emit(new_cell)
            new_cell.set_cell_focus()

            def _focus_new():
                try:
                    if new_cell and hasattr(new_cell, 'set_cell_focus'):
                        new_cell.set_cell_focus()
                except Exception:
                    pass

            QTimer.singleShot(10, _focus_new)
            QTimer.singleShot(50, _focus_new)
            return new_cell

        return None

    def _resolve_image_src(self, src: str) -> Optional[QImage]:
        """Resolve an image src (data URI, local img_id, resource, or file path) into a QImage."""
        if not src:
            return None
        # 1. Base64 data URI
        if src.startswith("data:image/"):
            m = re.match(r'data:image/[^;]+;base64,(.+)', src, re.DOTALL)
            if m:
                try:
                    raw = base64.b64decode(m.group(1).strip())
                    qimg = QImage()
                    if qimg.loadFromData(raw):
                        return qimg
                except Exception:
                    pass
        # 2. Check global clipboard image cache
        if src in _GLOBAL_IMAGE_CACHE:
            cached_img, _ = _GLOBAL_IMAGE_CACHE[src]
            if cached_img and not cached_img.isNull():
                return cached_img
        # 3. Check current document resources
        res = self.document().resource(QTextDocument.ResourceType.ImageResource, QUrl(src))
        if res and not res.isNull():
            if isinstance(res, QImage):
                return res
            if isinstance(res, QPixmap):
                return res.toImage()
            if hasattr(res, 'toImage'):
                return res.toImage()
        # 4. Check embedded_images dictionary of this cell
        if hasattr(self, 'embedded_images') and src in self.embedded_images:
            try:
                raw = base64.b64decode(self.embedded_images[src])
                qimg = QImage()
                if qimg.loadFromData(raw):
                    return qimg
            except Exception:
                pass
        # 5. Check all cells across worksheet
        ws = self._get_worksheet_view()
        if ws and hasattr(ws, 'cells'):
            for c in ws.cells:
                if hasattr(c, 'input_edit') and hasattr(c.input_edit, 'embedded_images'):
                    if src in c.input_edit.embedded_images:
                        try:
                            raw = base64.b64decode(c.input_edit.embedded_images[src])
                            qimg = QImage()
                            if qimg.loadFromData(raw):
                                return qimg
                        except Exception:
                            pass
        # 6. Check local file path or file URL
        fpath = QUrl(src).toLocalFile() if src.startswith("file:") else src
        if fpath and os.path.isfile(fpath):
            qimg = QImage(fpath)
            if not qimg.isNull():
                return qimg
        return None

    def createMimeDataFromSelection(self) -> QMimeData:
        mime = super().createMimeDataFromSelection()
        cursor = self.textCursor()
        if not cursor.hasSelection():
            return mime

        start = min(cursor.selectionStart(), cursor.selectionEnd())
        end = max(cursor.selectionStart(), cursor.selectionEnd())

        found_images: List[Tuple[str, QImage, Optional[str]]] = []
        it = QTextCursor(self.document())
        it.setPosition(start)
        while it.position() < end:
            it.movePosition(QTextCursor.MoveOperation.NextCharacter, QTextCursor.MoveMode.KeepAnchor)
            fmt = it.charFormat()
            if fmt.isImageFormat():
                img_name = fmt.toImageFormat().name()
                qimg: Optional[QImage] = None
                b64_str: Optional[str] = None
                res = self.document().resource(QTextDocument.ResourceType.ImageResource, QUrl(img_name))
                if res and not res.isNull():
                    if isinstance(res, QImage):
                        qimg = res
                    elif isinstance(res, QPixmap):
                        qimg = res.toImage()
                    elif hasattr(res, 'toImage'):
                        qimg = res.toImage()
                if hasattr(self, 'embedded_images') and img_name in self.embedded_images:
                    b64_str = self.embedded_images[img_name]
                    if qimg is None or qimg.isNull():
                        try:
                            raw = base64.b64decode(b64_str)
                            qimg = QImage()
                            qimg.loadFromData(raw)
                        except Exception:
                            pass
                elif qimg and not qimg.isNull():
                    buf = QBuffer()
                    buf.open(QIODevice.OpenModeFlag.WriteOnly)
                    qimg.save(buf, "PNG")
                    b64_str = base64.b64encode(buf.data().data()).decode('ascii')
                    buf.close()

                if (qimg is None or qimg.isNull()) and img_name in _GLOBAL_IMAGE_CACHE:
                    qimg, b64_str = _GLOBAL_IMAGE_CACHE[img_name]

                if qimg and not qimg.isNull():
                    found_images.append((img_name, qimg, b64_str))
                    if b64_str:
                        _GLOBAL_IMAGE_CACHE[img_name] = (qimg, b64_str)

            it.setPosition(it.position())

        if found_images:
            sel_text = cursor.selectedText().replace('\ufffc', '').strip()
            # If the selection is ONLY image(s) or has images, set image data on clipboard
            if not sel_text or len(found_images) == 1:
                mime.setImageData(found_images[0][1])

            if mime.hasHtml():
                h = mime.html()
                for iname, iq, ib64 in found_images:
                    if ib64:
                        h = re.sub(
                            r'src=[\'"]' + re.escape(iname) + r'[\'"]',
                            f'src="data:image/png;base64,{ib64}"',
                            h
                        )
                mime.setHtml(h)

        return mime

    def _on_insert_image_dialog(self):
        """Open file dialog to insert an image file into the worksheet cell."""
        fpath, _ = QFileDialog.getOpenFileName(
            self, "Insert Image", "",
            "Images (*.png *.jpg *.jpeg *.bmp *.gif *.svg);;All Files (*.*)"
        )
        if fpath and os.path.exists(fpath):
            qimg = QImage(fpath)
            if not qimg.isNull():
                self.insert_image_object(qimg)

    def insertFromMimeData(self, source):
        # 1. Handle image paste from clipboard (e.g. screenshot or copied image)
        if source.hasImage():
            img_data = source.imageData()
            if img_data:
                if isinstance(img_data, QPixmap):
                    qimg = img_data.toImage()
                elif isinstance(img_data, QImage):
                    qimg = img_data
                elif hasattr(img_data, 'toImage'):
                    qimg = img_data.toImage()
                else:
                    qimg = img_data
                clean_txt = source.text().replace('\ufffc', '').strip() if source.hasText() else ""
                if not clean_txt:
                    if qimg and not qimg.isNull():
                        self.insert_image_object(qimg)
                        return

        # 2. Handle image files from clipboard
        if source.hasUrls():
            urls = source.urls()
            inserted_any = False
            for u in urls:
                if u.isLocalFile():
                    lp = u.toLocalFile()
                    if os.path.isfile(lp) and lp.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif', '.webp')):
                        qimg = QImage(lp)
                        if not qimg.isNull():
                            self.insert_image_object(qimg)
                            inserted_any = True
            if inserted_any:
                return

        # 3. Handle HTML containing embedded images
        if source.hasHtml():
            html = source.html()
            if "<img" in html.lower():
                plain = source.text() if source.hasText() else ""
                clean_plain = plain.replace('\ufffc', '').strip()
                img_srcs = re.findall(r'<img[^>]+src=[\'"]([^\'"]+)[\'"]', html, re.IGNORECASE)
                if img_srcs and not clean_plain:
                    inserted = False
                    for src in img_srcs:
                        qimg = self._resolve_image_src(src)
                        if qimg and not qimg.isNull():
                            self.insert_image_object(qimg)
                            inserted = True
                    if inserted:
                        return
                elif img_srcs:
                    for src in img_srcs:
                        qimg = self._resolve_image_src(src)
                        if qimg and not qimg.isNull():
                            buf = QBuffer()
                            buf.open(QIODevice.OpenModeFlag.WriteOnly)
                            qimg.save(buf, "PNG")
                            b64_png = base64.b64encode(buf.data().data()).decode('ascii')
                            buf.close()
                            img_id = f"img_{uuid.uuid4().hex[:8]}"
                            if not hasattr(self, 'embedded_images'):
                                self.embedded_images = {}
                            self.embedded_images[img_id] = b64_png
                            self.document().addResource(QTextDocument.ResourceType.ImageResource, QUrl(img_id), qimg)
                            _GLOBAL_IMAGE_CACHE[img_id] = (qimg, b64_png)
                            html = html.replace(src, img_id)
                    self.insertHtml(html)
                    self._adjust_height()
                    parent_cell = getattr(self, 'parent_cell', None)
                    if parent_cell:
                        if hasattr(parent_cell, 'set_input_mode') and hasattr(parent_cell, 'MODE_TEXT'):
                            parent_cell.set_input_mode(parent_cell.MODE_TEXT)
                        if hasattr(parent_cell, 'lbl_prompt'):
                            parent_cell.lbl_prompt.setVisible(False)
                        if hasattr(parent_cell, 'bracket_bar'):
                            parent_cell.bracket_bar.setVisible(False)
                        ws = self._get_worksheet_view() or (parent_cell._get_worksheet_view() if parent_cell else None)
                        if ws:
                            ws.active_cell = parent_cell
                            ws.activeCellChanged.emit(parent_cell)
                    return

        if source.hasText():
            txt = source.text()
            if txt == '\ufffc':
                return
            if self.get_mode_at_cursor() == getattr(self.parent_cell, 'MODE_2D_MATH', '2d_math'):
                sup_keys = ''.join(SUPER_MAP.keys())
                sup_id_keys = ''.join(c for c in SUPER_MAP.keys() if c.isalnum())
                txt = re.sub(f'\\^{{([{re.escape(sup_keys)}]+)}}', lambda m: ''.join(SUPER_MAP.get(c, c) for c in m.group(1)), txt)
                txt = re.sub(f'\\^([{re.escape(sup_id_keys)}]+)', lambda m: ''.join(SUPER_MAP.get(c, c) for c in m.group(1)), txt)
                sub_keys = ''.join(SUB_MAP.keys())
                sub_letters = ''.join(c for c in SUB_MAP.keys() if c.isalpha())
                txt = re.sub(r'(?<=[a-zA-Z0-9_\)\]\}])_+{' + f'([{re.escape(sub_keys)}]+)' + r'}', lambda m: ''.join(SUB_MAP.get(c, c) for c in m.group(1)), txt)
                txt = re.sub(rf'(?<=[a-zA-Z0-9_\)\]\}}])_+([0-9]+|[{re.escape(sub_letters)}])(?![a-zA-Z0-9])', lambda m: ''.join(SUB_MAP.get(c, c) for c in m.group(1)), txt)
                txt = re.sub(r'(?<=[a-zA-Z0-9_\)\]\}])\s*(?<!\*)\*(?!\*)\s*(?=[a-zA-Z0-9_\(\[\{])', ' · ', txt)
                txt = txt.replace(' * ', ' · ')
            self.insertPlainText(txt)
        else:
            super().insertFromMimeData(source)

    def update_font_scaling(self):
        sz = getattr(self.parent_cell, 'current_font_size', 12) if self.parent_cell else 12
        if not isinstance(sz, int) or sz <= 0:
            sz = 12
        fam = getattr(self.parent_cell, 'current_font_family', "Times New Roman") or "Times New Roman" if self.parent_cell else "Times New Roman"
        factor = getattr(self.parent_cell, 'zoom_factor', 1.0) if self.parent_cell else 1.0
        display_sz = max(4, round(sz * factor))

        wf = QFont(fam, display_sz)
        self.setFont(wf)

        if self.document().characterCount() > 1:
            cursor = QTextCursor(self.document())
            cursor.beginEditBlock()
            cursor.select(QTextCursor.SelectionType.Document)
            fmt = QTextCharFormat()
            fmt.setFontPointSize(display_sz)
            cursor.mergeCharFormat(fmt)
            cursor.endEditBlock()

        cur_fmt = self.currentCharFormat()
        cur_fmt.setFontPointSize(display_sz)
        self.setCurrentCharFormat(cur_fmt)

        if hasattr(self, 'frac_widgets'):
            for frac in list(self.frac_widgets.values()):
                frac.update_style()
                self._on_frac_size_changed(frac)

        self._adjust_height()
        self._update_tall_parentheses()
        self.viewport().update()

    def get_spans(self) -> list:
        spans = []
        doc = self.document()
        block = doc.begin()
        while block.isValid():
            it = block.begin()
            while not it.atEnd():
                frag = it.fragment()
                if frag.isValid():
                    fmt = frag.charFormat()
                    mode = fmt.property(PROP_MODE) or getattr(self.parent_cell, 'input_mode', '2d_math')
                    if fmt.isImageFormat():
                        fid = fmt.property(PROP_FRAC_ID)
                        if fid and hasattr(self, 'frac_widgets') and fid in self.frac_widgets:
                            w = self.frac_widgets[fid]
                            if isinstance(w, FractionWidget):
                                spans.append({
                                    'type': 'fraction',
                                    'num': w.num_text(),
                                    'den': w.den_text(),
                                    'text': w.text_expression(),
                                    'is_exponent': getattr(w, 'is_exponent', False),
                                    'is_result': getattr(w, 'is_result', False),
                                    'mode': mode
                                })
                                it += 1
                                continue
                            elif isinstance(w, DefiniteIntegralWidget):
                                spans.append({
                                    'type': 'definite_integral',
                                    'a': w.lower_text(),
                                    'b': w.upper_text(),
                                    'f': w.integrand_text(),
                                    'var': getattr(w, 'var_name', 'x'),
                                    'show_diff': getattr(w, 'show_differential', False),
                                    'text': w.text_expression(),
                                    'mode': mode
                                })
                                it += 1
                                continue
                            elif isinstance(w, RadicalWidget):
                                spans.append({
                                    'type': 'radical',
                                    'radicand': w.radicand_text(),
                                    'degree': w.degree_text(),
                                    'text': w.text_expression(),
                                    'is_result': getattr(w, 'is_result', False),
                                    'mode': mode
                                })
                                it += 1
                                continue
                            elif isinstance(w, BigOperatorWidget):
                                spans.append({
                                    'type': 'big_operator',
                                    'op_symbol': w.op_symbol,
                                    'top': w.top_text(),
                                    'bottom': w.bottom_text(),
                                    'body': w.body_text(),
                                    'text': w.text_expression(),
                                    'mode': mode
                                })
                                it += 1
                                continue
                            elif isinstance(w, MatrixWidget):
                                spans.append({
                                    'type': 'matrix',
                                    'data': [[cell.text() for cell in row] for row in w.cells],
                                    'text': w.text_expression(),
                                    'is_result': getattr(w, 'is_result', False),
                                    'mode': mode
                                })
                                it += 1
                                continue
                            else:
                                text = w.text_expression()
                        else:
                            expr = fmt.property(PROP_MATH_EXPR)
                            text = str(expr) if expr else frag.text()
                    else:
                        text = frag.text()

                    if text:
                        if spans and spans[-1].get('type', 'text') == 'text' and spans[-1].get('mode') == mode:
                            spans[-1]['text'] += text
                        else:
                            spans.append({'type': 'text', 'text': text, 'mode': mode})
                it += 1
            block = block.next()
            if block.isValid() and spans:
                if spans[-1].get('type', 'text') == 'text':
                    spans[-1]['text'] += '\n'
                else:
                    spans.append({'type': 'text', 'text': '\n', 'mode': spans[-1].get('mode', '2d_math')})
        return spans

    def set_spans(self, spans: list):
        self._is_formatting_math = True
        try:
            self.clear()
            if hasattr(self, 'frac_widgets'):
                for w in list(self.frac_widgets.values()):
                    w.deleteLater()
                self.frac_widgets.clear()

            for span in spans:
                stype = span.get('type')
                mode = span.get('mode', '2d_math')
                fmt = self._get_char_format_for_mode(mode)
                if 'color' in span:
                    fmt.setForeground(QColor(span['color']))
                if 'bg_color' in span or 'background' in span:
                    bg = span.get('bg_color') or span.get('background')
                    fmt.setBackground(QColor(bg))
                if span.get('font_weight') == 'bold':
                    fmt.setFontWeight(QFont.Weight.Bold)
                if span.get('is_italic') or span.get('italic'):
                    fmt.setFontItalic(True)

                if stype == 'fraction':
                    num = span.get('num', 'a')
                    den = span.get('den', 'b')
                    is_exp = span.get('is_exponent', False)
                    is_res = span.get('is_result', False)
                    self.insert_fraction_widget(num=num, den=den, focus_target=None, is_exponent=is_exp, is_result=is_res)
                elif stype == 'definite_integral':
                    a = span.get('a', 'a')
                    b = span.get('b', 'b')
                    f = span.get('f', 'f')
                    var = span.get('var', 'x')
                    show_diff = span.get('show_diff', False)
                    self.insert_definite_integral_widget(a=a, b=b, f=f, var=var, show_differential=show_diff, focus_target=None)
                elif stype == 'radical':
                    radicand = span.get('radicand', 'a')
                    degree = span.get('degree', None)
                    is_res = span.get('is_result', False)
                    self.insert_radical_widget(radicand=radicand, degree=degree, focus_target=None, is_result=is_res)
                elif stype == 'big_operator':
                    op_symbol = span.get('op_symbol', '∑')
                    top = span.get('top', 'n')
                    bottom = span.get('bottom', 'k = 1')
                    body = span.get('body', 'f')
                    self.insert_big_operator_widget(op_symbol=op_symbol, top=top, bottom=bottom, body=body, focus_target=None)
                elif stype == 'matrix':
                    mat_data = span.get('data')
                    is_res = span.get('is_result', False)
                    self.insert_matrix_widget(data=mat_data, focus_target=None, is_result=is_res)
                else:
                    text = span.get('text', '')
                    if not text:
                        continue
                    if mode == getattr(self.parent_cell, 'MODE_2D_MATH', '2d_math') and not ('color' in span or 'bg_color' in span or 'background' in span):
                        # Parse math tokens so legacy saved fractions e.g. (1)/(R) or 3/20 are restored as 2D fractions
                        tokens = parse_math_tokens(text)
                        for tok_type, *tok_args in tokens:
                            if tok_type == 'fraction':
                                num = tok_args[0]
                                den = tok_args[1]
                                is_exp = tok_args[2] if len(tok_args) > 2 else False
                                self.insert_fraction_widget(num=num, den=den, focus_target=None, is_exponent=is_exp)
                            elif tok_type == 'radical':
                                radicand, degree = tok_args
                                self.insert_radical_widget(radicand=radicand, degree=degree, focus_target=None)
                            elif tok_type == 'matrix':
                                self.insert_matrix_widget(data=tok_args[0], focus_target=None)
                            else:
                                cur = self.textCursor()
                                cur.insertText(tok_args[0], fmt)
                                self.setTextCursor(cur)
                    else:
                        cur = self.textCursor()
                        cur.insertText(text, fmt)
                        self.setTextCursor(cur)

        finally:
            self._is_formatting_math = False
        self._adjust_height()
        QTimer.singleShot(0, self._reposition_fractions)

    def inputMethodEvent(self, event):
        super().inputMethodEvent(event)
        self._dynamically_format_math()

    def _dynamically_format_math(self):
        """Dynamically converts ^power and **power to superscripts (e.g. a^2 -> a², a**2 -> a²) while writing."""
        if getattr(self, '_is_formatting_math', False):
            return
        if self.get_mode_at_cursor() != getattr(self.parent_cell, 'MODE_2D_MATH', '2d_math'):
            return

        text = super().toPlainText()
        if not text:
            return

        sup_keys = ''.join(SUPER_MAP.keys())
        sup_vals = ''.join(SUPER_MAP.values())
        sup_id_keys = ''.join(c for c in SUPER_MAP.keys() if c.isalnum())
        sub_keys = ''.join(SUB_MAP.keys())
        sub_vals = ''.join(SUB_MAP.values())
        sub_letters = ''.join(c for c in SUB_MAP.keys() if c.isalpha())
        pow_pattern = re.compile(rf'(\*\*|\^)\s*([{re.escape(sup_id_keys)}]+)')
        cont_pattern = re.compile(rf'([{re.escape(sup_vals)}]+)([{re.escape(sup_id_keys)}]+)')
        exp_frac_pattern = re.compile(
            r'(\*\*|\^)\s*\(\s*([0-9a-zA-Z_.]+)\s*/\s*([0-9a-zA-Z_.]+)\s*\)|'
            rf'⁽\s*([{re.escape("".join(SUPER_MAP.values()))}0-9a-zA-Z_.]+)\s*/\s*([{re.escape("".join(SUPER_MAP.values()))}0-9a-zA-Z_.]+)\s*⁾'
        )
        sub_brace_pattern = re.compile(r'(?<=[a-zA-Z0-9_\)\]\}])_+{' + f'([{re.escape(sub_keys)}]+)' + r'}')
        sub_pattern = re.compile(rf'(?<=[a-zA-Z0-9_\)\]\}}])_+([0-9]+|[{re.escape(sub_letters)}])(?![a-zA-Z0-9])')
        sub_cont_pattern = re.compile(rf'([{re.escape(sub_vals)}]+)([0-9]+)')
        mul_pattern = re.compile(r'(?<=[a-zA-Z0-9_\)\]\}])\s*(?<!\*)\*(?!\*)\s*(?=[a-zA-Z0-9_\(\[\{])')

        kw_patterns = [
            (re.compile(r'\\sqrt\s*\{([^}]*)\}'), lambda m: f"√({m.group(1)})"),
            (re.compile(r'\bsqrt\s*\('), "√("),
            (re.compile(r'\blog10\s*\('), "log₁₀("),
            (re.compile(r'\blog_10\s*\('), "log₁₀("),
            (re.compile(r'\blog2\s*\('), "log₂("),
            (re.compile(r'\blog_2\s*\('), "log₂("),
            (re.compile(r'\b(?:Sum|sum)\s*\('), "∑("),
            (re.compile(r'\b(?:Product|product|prod)\s*\('), "∏("),
            (re.compile(r'\b(?:integrate|int)\s*\('), "∫("),
        ]

        has_exp_frac = bool(exp_frac_pattern.search(text))
        has_pow = bool(pow_pattern.search(text))
        has_cont = getattr(self, '_superscript_active', False) and bool(cont_pattern.search(text))
        has_sub = bool(sub_pattern.search(text)) or bool(sub_brace_pattern.search(text))
        has_sub_cont = getattr(self, '_subscript_active', False) and bool(sub_cont_pattern.search(text))
        has_mul = bool(mul_pattern.search(text))
        has_kw = any(bool(p.search(text)) for p, _ in kw_patterns)
        has_completed_rad = bool(re.search(r'√\s*\([^()]+\)|\broot\s*\([^,()]+\s*,\s*[^()]+\)|\\sqrt\s*\{[^}]+\}', text))

        if not has_exp_frac and not has_pow and not has_cont and not has_sub and not has_sub_cont and not has_mul and not has_kw and not has_completed_rad:
            return

        self._is_formatting_math = True
        try:
            cursor = self.textCursor()
            cpos = cursor.position()
            new_cpos = cpos

            cursor.beginEditBlock()

            # 0. Format exponent fractions ^(num/den) or ⁽num/den⁾ into 2D elevated fraction widgets
            if has_exp_frac:
                for m in reversed(list(exp_frac_pattern.finditer(text))):
                    if m.group(1):
                        num = m.group(2)
                        den = m.group(3)
                    else:
                        num = "".join(INV_SUPER_MAP.get(c, c) for c in m.group(4))
                        den = "".join(INV_SUPER_MAP.get(c, c) for c in m.group(5))
                    start, end = m.span()
                    cur = QTextCursor(self.document())
                    cur.setPosition(start)
                    cur.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
                    cur.removeSelectedText()
                    self.setTextCursor(cur)
                    self.insert_fraction_widget(num=num, den=den, focus_target=None, is_exponent=True)
                    delta = (end - start) - 1
                    if cpos >= end:
                        new_cpos -= delta
                    elif cpos > start:
                        new_cpos = start + 1
                text = super().toPlainText()

            # 1. Format single multiplication * between terms to · (skip if part of **)
            if has_mul:
                for m in reversed(list(mul_pattern.finditer(text))):
                    start, end = m.span()
                    rep = " · "
                    cur = QTextCursor(self.document())
                    cur.setPosition(start)
                    cur.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
                    cur.insertText(rep)
                    delta = (end - start) - len(rep)
                    if cpos >= end:
                        new_cpos -= delta
                    elif cpos > start:
                        new_cpos = start + len(rep)
                text = super().toPlainText()

            # 2. Format ^power and **power into superscripts
            pow_matches = list(pow_pattern.finditer(text))
            if pow_matches:
                for m in reversed(pow_matches):
                    start, end = m.span()
                    power_str = m.group(2)
                    sup = ''.join(SUPER_MAP.get(c, c) for c in power_str)
                    cur = QTextCursor(self.document())
                    cur.setPosition(start)
                    cur.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
                    cur.insertText(sup)
                    delta = (end - start) - len(sup)
                    if cpos >= end:
                        new_cpos -= delta
                    elif cpos > start:
                        new_cpos = start + len(sup)
                text = super().toPlainText()

            # 3. Format continuation digits immediately following existing superscripts
            cont_matches = list(cont_pattern.finditer(text))
            if cont_matches:
                for m in reversed(cont_matches):
                    digits = m.group(2)
                    start = m.start(2)
                    end = m.end(2)
                    sup = ''.join(SUPER_MAP.get(c, c) for c in digits)
                    cur = QTextCursor(self.document())
                    cur.setPosition(start)
                    cur.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
                    cur.insertText(sup)
                    delta = (end - start) - len(sup)
                    if cpos >= end:
                        new_cpos -= delta
                    elif cpos > start:
                        new_cpos = start + len(sup)

            # 3b. Format _sub and _{sub} into subscripts
            if has_sub:
                sub_matches = list(sub_brace_pattern.finditer(text)) + list(sub_pattern.finditer(text))
                sub_matches.sort(key=lambda m: m.start(), reverse=True)
                for m in sub_matches:
                    start, end = m.span()
                    sub_str = m.group(1)
                    sub = ''.join(SUB_MAP.get(c, c) for c in sub_str)
                    cur = QTextCursor(self.document())
                    cur.setPosition(start)
                    cur.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
                    cur.insertText(sub)
                    delta = (end - start) - len(sub)
                    if cpos >= end:
                        new_cpos -= delta
                    elif cpos > start:
                        new_cpos = start + len(sub)
                text = super().toPlainText()

            # 3c. Format continuation digits immediately following existing subscripts
            if has_sub_cont:
                sub_cont_matches = list(sub_cont_pattern.finditer(text))
                if sub_cont_matches:
                    for m in reversed(sub_cont_matches):
                        digits = m.group(2)
                        start = m.start(2)
                        end = m.end(2)
                        sub = ''.join(SUB_MAP.get(c, c) for c in digits)
                        cur = QTextCursor(self.document())
                        cur.setPosition(start)
                        cur.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
                        cur.insertText(sub)
                        delta = (end - start) - len(sub)
                        if cpos >= end:
                            new_cpos -= delta
                        elif cpos > start:
                            new_cpos = start + len(sub)
                    text = super().toPlainText()

            # 4. Format math keywords to clean symbols: sqrt( -> √(, log10( -> log₁₀(, sum( -> ∑(, prod( -> ∏(, int( -> ∫(
            if has_kw:
                for pat, rep in kw_patterns:
                    matches = list(pat.finditer(text))
                    if matches:
                        for m in reversed(matches):
                            start, end = m.span()
                            replacement_str = rep(m) if callable(rep) else rep
                            cur = QTextCursor(self.document())
                            cur.setPosition(start)
                            cur.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
                            cur.insertText(replacement_str)
                            delta = (end - start) - len(replacement_str)
                            if cpos >= end:
                                new_cpos -= delta
                            elif cpos > start:
                                new_cpos = start + len(replacement_str)
                        text = super().toPlainText()

            # 5. Format completed radicals into 2D RadicalWidget instances
            has_completed_rad = bool(re.search(r'√\s*\([^()]+\)|\broot\s*\([^,()]+\s*,\s*[^()]+\)|\\sqrt\s*\{[^}]+\}', text))
            if has_completed_rad:
                rad_matches = []
                for m in re.finditer(r'\broot\s*\(([^,()]+),\s*([^()]+)\)', text):
                    rad_matches.append((m.start(), m.end(), m.group(1).strip(), m.group(2).strip()))
                for m in re.finditer(r'√\s*\(([^()]+)\)', text):
                    rad_matches.append((m.start(), m.end(), m.group(1).strip(), None))
                for m in re.finditer(r'\\sqrt\s*\{([^}]+)\}', text):
                    rad_matches.append((m.start(), m.end(), m.group(1).strip(), None))

                if rad_matches:
                    rad_matches.sort(key=lambda x: x[0], reverse=True)
                    for start, end, rad_val, deg_val in rad_matches:
                        cur = QTextCursor(self.document())
                        cur.setPosition(start)
                        cur.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
                        cur.removeSelectedText()
                        self.setTextCursor(cur)
                        self.insert_radical_widget(radicand=rad_val, degree=deg_val, focus_target="radicand")
                        delta = (end - start) - 1
                        if cpos >= end:
                            new_cpos -= delta
                        elif cpos > start:
                            new_cpos = start + 1
                    text = super().toPlainText()

            cursor.endEditBlock()

            final_cur = self.textCursor()
            final_cur.setPosition(min(max(0, new_cpos), max(0, self.document().characterCount() - 1)))
            self.setTextCursor(final_cur)
        finally:
            self._is_formatting_math = False

    def _on_text_changed_clear_error(self):
        self._dynamically_format_math()
        if self.parent_cell and hasattr(self.parent_cell, 'error_box') and self.parent_cell.error_box.isVisible():
            self.parent_cell.clear_error()

    def focusInEvent(self, event):
        super().focusInEvent(event)
        if self.parent_cell:
            self.parent_cell._on_cursor_changed()

    def _cleanup_orphaned_fractions(self) -> bool:
        """Find and remove any frac_widgets whose image placeholder is no longer in the document."""
        if not hasattr(self, 'frac_widgets') or not self.frac_widgets:
            return False
        doc = self.document()
        present_fids = set()
        it = doc.begin()
        while it.isValid():
            fit = it.begin()
            while not fit.atEnd():
                frag = fit.fragment()
                if frag.isValid():
                    fmt = frag.charFormat()
                    if fmt.isImageFormat() and fmt.property(PROP_FRAC_ID):
                        present_fids.add(fmt.property(PROP_FRAC_ID))
                fit += 1
            it = it.next()

        removed = False
        for fid in list(self.frac_widgets.keys()):
            if fid not in present_fids:
                w = self.frac_widgets.pop(fid)
                if hasattr(self, '_active_fraction_slot') and self._active_fraction_slot:
                    try:
                        if sip.isdeleted(self._active_fraction_slot) or (w and not sip.isdeleted(w) and (w == self._active_fraction_slot or w.isAncestorOf(self._active_fraction_slot))):
                            self._active_fraction_slot = None
                    except Exception:
                        self._active_fraction_slot = None
                if w and not sip.isdeleted(w):
                    w.hide()
                    w.deleteLater()
                removed = True
        return removed

    def _adjust_height(self):
        self._cleanup_orphaned_fractions()
        fm = self.fontMetrics()
        line_height = max(14, fm.lineSpacing())
        blocks = max(1, self.document().blockCount())
        doc_layout = self.document().documentLayout()
        doc_h = doc_layout.documentSize().height() if doc_layout else 0
        tl = self.document().begin().layout() if self.document().begin().isValid() else None
        is_multiline = (tl is not None and tl.lineCount() > 1) or blocks > 1

        if not is_multiline and not (hasattr(self, 'frac_widgets') and self.frac_widgets) and not (hasattr(self, 'embedded_images') and self.embedded_images):
            calc_h = line_height + 10
        else:
            calc_h = int(doc_h) + 4 if doc_h > 0 else blocks * line_height + 8
            if hasattr(self, 'frac_widgets') and self.frac_widgets:
                max_frac_h = max(f.height() for f in self.frac_widgets.values())
                calc_h = max(calc_h, max_frac_h + 8)

            # Embedded images height check
            if hasattr(self, 'embedded_images') and self.embedded_images:
                img_h_sum = 0
                for ch_pos in range(self.document().characterCount() - 1):
                    c = QTextCursor(self.document())
                    c.setPosition(ch_pos)
                    c.setPosition(ch_pos + 1, QTextCursor.MoveMode.KeepAnchor)
                    if c.charFormat().isImageFormat():
                        fh = c.charFormat().toImageFormat().height()
                        if fh > 0:
                            img_h_sum += int(fh)
                if img_h_sum > 0:
                    calc_h = max(calc_h, img_h_sum + 16)
                else:
                    for img_id in self.embedded_images:
                        res = self.document().resource(QTextDocument.ResourceType.ImageResource, QUrl(img_id))
                        if res and not res.isNull():
                            img_h_sum += res.size().height()
                    if img_h_sum > 0:
                        calc_h = max(calc_h, img_h_sum + 16)

        new_h = max(line_height + 6, min(4000, calc_h))
        if self.height() != new_h:
            self.setFixedHeight(new_h)
            self.updateGeometry()
            if self.parent_cell:
                if hasattr(self.parent_cell, 'input_row'):
                    self.parent_cell.input_row.updateGeometry()
                if hasattr(self.parent_cell, 'content_container'):
                    if self.parent_cell.content_container.layout():
                        self.parent_cell.content_container.layout().invalidate()
                    self.parent_cell.content_container.updateGeometry()
                if self.parent_cell.layout():
                    self.parent_cell.layout().invalidate()
                self.parent_cell.updateGeometry()
                ws = self.parent_cell._get_worksheet_view()
                if ws and hasattr(ws, 'cells_layout'):
                    ws.cells_layout.activate()

    def showEvent(self, event):
        super().showEvent(event)
        self._adjust_height()

    def _get_worksheet_view(self):
        p = self.parent()
        while p:
            if hasattr(p, 'set_zoom') and hasattr(p, 'zoom_in'):
                return p
            p = p.parent()
        return None

    def wheelEvent(self, event: QWheelEvent):
        if event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier):
            ws = self._get_worksheet_view()
            if ws and ws.handle_wheel_zoom(event):
                event.accept()
                return
        ws = self._get_worksheet_view()
        if ws and hasattr(ws, 'scroll_area'):
            ws.scroll_area.wheelEvent(event)
            event.accept()
            return
        super().wheelEvent(event)

    def event(self, event: QEvent):
        if event.type() == QEvent.Type.NativeGesture:
            ws = self._get_worksheet_view()
            if ws and ws.handle_native_gesture_zoom(event):
                event.accept()
                return True
        return super().event(event)

    def set_font_size(self, size: int):
        try:
            val = int(size)
            if val <= 0:
                val = 12
        except (ValueError, TypeError):
            val = 12
        val = max(1, val)  # Guard: Qt requires point size > 0
        factor = getattr(self.parent_cell, 'zoom_factor', 1.0) if self.parent_cell else 1.0
        display_sz = max(4, round(val * factor))

        cursor = self.textCursor()
        fmt = QTextCharFormat()
        fmt.setFontPointSize(display_sz)

        if cursor.hasSelection():
            # Apply ONLY to the selected text
            cursor.mergeCharFormat(fmt)
            self.setTextCursor(cursor)
        else:
            # When NO text is selected: do NOT alter existing text in the document!
            # Only set format for what the user is about to type next at the cursor
            self.mergeCurrentCharFormat(fmt)
            if self.document().characterCount() <= 1:
                # If document is empty, also update default cell font size and base font
                if self.parent_cell:
                    self.parent_cell.current_font_size = val
                fam = getattr(self.parent_cell, 'current_font_family', "Times New Roman") or "Times New Roman" if self.parent_cell else "Times New Roman"
                self.setFont(QFont(fam, display_sz))
        self._adjust_height()

    def set_line_spacing(self, spacing: float):
        """
        Set line spacing (1.0 = single, 1.15, 1.25, 1.5, 2.0 = double, etc.).
        If text is selected: applies ONLY to the blocks within the selection.
        If NO text is selected: applies ONLY to the current block/cursor and future typing,
        without altering the rest of the document.
        """
        try:
            val = float(spacing)
            if val <= 0.1:
                val = 1.0
        except (ValueError, TypeError):
            val = 1.0

        self.current_line_spacing = val
        if self.parent_cell:
            self.parent_cell.current_line_spacing = val

        bfmt = QTextBlockFormat()
        # 1 corresponds to QTextBlockFormat.LineHeightTypes.ProportionalHeight
        bfmt.setLineHeight(val * 100.0, 1)

        cursor = self.textCursor()
        if cursor.hasSelection():
            cursor.beginEditBlock()
            cursor.mergeBlockFormat(bfmt)
            cursor.endEditBlock()
            self.setTextCursor(cursor)
        else:
            cursor.mergeBlockFormat(bfmt)
            self.setTextCursor(cursor)

        self._adjust_height()

    def set_font_family(self, family: str):
        if not family:
            return
        cursor = self.textCursor()
        fmt = QTextCharFormat()
        fmt.setFontFamily(family)
        if cursor.hasSelection():
            cursor.mergeCharFormat(fmt)
            self.setTextCursor(cursor)
        else:
            self.mergeCurrentCharFormat(fmt)
            if self.document().characterCount() <= 1:
                if self.parent_cell:
                    self.parent_cell.current_font_family = family
                self.setFont(QFont(family, self.font().pointSize()))
        self._adjust_height()

    def set_bold(self, bold: bool):
        self._is_bold = bold
        cursor = self.textCursor()
        fmt = QTextCharFormat()
        fmt.setFontWeight(QFont.Weight.Bold if bold else QFont.Weight.Normal)
        if cursor.hasSelection():
            cursor.mergeCharFormat(fmt)
        else:
            self.mergeCurrentCharFormat(fmt)

    def set_italic(self, italic: bool):
        self._is_italic = italic
        cursor = self.textCursor()
        fmt = QTextCharFormat()
        fmt.setFontItalic(italic)
        if cursor.hasSelection():
            cursor.mergeCharFormat(fmt)
        else:
            self.mergeCurrentCharFormat(fmt)

    def set_underline(self, underline: bool):
        self._is_underline = underline
        cursor = self.textCursor()
        fmt = QTextCharFormat()
        fmt.setFontUnderline(underline)
        if cursor.hasSelection():
            cursor.mergeCharFormat(fmt)
        else:
            self.mergeCurrentCharFormat(fmt)

    def set_text_color(self, color: QColor):
        """Apply foreground text color to selection (or future typing if no selection)."""
        if not color.isValid():
            return
        self._active_text_color = color
        cursor = self.textCursor()
        fmt = QTextCharFormat()
        fmt.setForeground(color)
        if cursor.hasSelection():
            cursor.mergeCharFormat(fmt)
            cursor.clearSelection()
            self.setTextCursor(cursor)
        else:
            self.mergeCurrentCharFormat(fmt)

    def set_highlight_color(self, color: QColor):
        """Apply background highlight color to selection (or clear if transparent/invalid)."""
        cursor = self.textCursor()
        fmt = QTextCharFormat()
        if color.isValid() and color.alpha() > 0:
            self._active_highlight_color = color
            fmt.setBackground(color)
        else:
            self._active_highlight_color = None
            fmt.setBackground(QBrush(Qt.BrushStyle.NoBrush))
        if cursor.hasSelection():
            cursor.mergeCharFormat(fmt)
            cursor.clearSelection()
            self.setTextCursor(cursor)
        else:
            self.mergeCurrentCharFormat(fmt)

    def clear_text_color(self):
        """Reset foreground color to default."""
        self._active_text_color = None
        cursor = self.textCursor()
        mode = self.get_mode_at_cursor()
        base_fmt = self._get_char_format_for_mode(mode)
        fmt = QTextCharFormat()
        fmt.setForeground(base_fmt.foreground())
        if cursor.hasSelection():
            cursor.mergeCharFormat(fmt)
            cursor.clearSelection()
            self.setTextCursor(cursor)
        else:
            self.mergeCurrentCharFormat(fmt)

    def clear_highlight_color(self):
        """Remove background highlight."""
        self._active_highlight_color = None
        cursor = self.textCursor()
        fmt = QTextCharFormat()
        fmt.setBackground(QBrush(Qt.BrushStyle.NoBrush))
        if cursor.hasSelection():
            cursor.mergeCharFormat(fmt)
            cursor.clearSelection()
            self.setTextCursor(cursor)
        else:
            self.mergeCurrentCharFormat(fmt)

    def setAlignment(self, align: Qt.AlignmentFlag):
        cursor = self.textCursor()
        block_format = cursor.blockFormat()
        block_format.setAlignment(align)
        cursor.setBlockFormat(block_format)
        self.setTextCursor(cursor)

    def _insert_completion(self, completion: str):
        tc = self.textCursor()
        tc.select(QTextCursor.SelectionType.WordUnderCursor)
        tc.removeSelectedText()
        if "_" in completion:
            self.insert_stepped_math_text(completion + "()", tc)
        else:
            tc.insertText(completion + "()")
        # Move inside parentheses
        tc.movePosition(QTextCursor.MoveOperation.Left)
        self.setTextCursor(tc)

    def _under_cursor_word(self) -> str:
        tc = self.textCursor()
        tc.select(QTextCursor.SelectionType.WordUnderCursor)
        return tc.selectedText()

    def _select_next_placeholder(self) -> bool:
        """Find next ⟦...⟧ placeholder and select it for immediate typing."""
        text = self.toPlainText()
        pos = self.textCursor().position()

        # Search forward from current position
        match = re.search(r'⟦(.*?)⟧', text[pos:])
        if match:
            start = pos + match.start()
            end = pos + match.end()
        else:
            # Wrap around to beginning
            match = re.search(r'⟦(.*?)⟧', text)
            if match:
                start = match.start()
                end = match.end()
            else:
                return False

        cursor = self.textCursor()
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
        self.setTextCursor(cursor)
        return True

    def insert_fraction_widget(self, num: str = "a", den: str = "b", focus_target: str = "num", is_exponent: bool = False, is_result: bool = False):
        """Insert a 2D vertical fraction widget with horizontal line directly inline in math text."""
        if not hasattr(self, 'frac_widgets'):
            self.frac_widgets = {}
        self._fraction_id_counter = getattr(self, '_fraction_id_counter', 0) + 1
        fid = self._fraction_id_counter

        frac = FractionWidget(num=num, den=den, fid=fid, parent_edit=self, is_exponent=is_exponent, is_result=is_result)
        self.frac_widgets[fid] = frac
        frac.show()

        # Transparent placeholder image to reserve space in QTextDocument
        pm = QPixmap(max(1, frac.width()), max(1, frac.height()))
        pm.fill(Qt.GlobalColor.transparent)
        url_str = f"frac://cell_{id(self)}_{fid}"
        url = QUrl(url_str)
        self.document().addResource(QTextDocument.ResourceType.ImageResource, url, pm)

        img_fmt = QTextImageFormat()
        img_fmt.setName(url_str)
        img_fmt.setWidth(frac.width())
        img_fmt.setHeight(frac.height())
        if is_exponent:
            img_fmt.setVerticalAlignment(QTextImageFormat.VerticalAlignment.AlignSuperScript)
            img_fmt.setProperty(PROP_IS_EXPONENT, True)
        else:
            img_fmt.setVerticalAlignment(QTextImageFormat.VerticalAlignment.AlignMiddle)
            img_fmt.setProperty(PROP_IS_EXPONENT, False)
        img_fmt.setProperty(PROP_FRAC_ID, fid)
        img_fmt.setProperty(PROP_MODE, self.current_typing_mode)

        cursor = self.textCursor()
        cursor.insertImage(img_fmt)
        norm_fmt = self._get_char_format_for_mode(self.current_typing_mode)
        cursor.setCharFormat(norm_fmt)
        self.setCurrentCharFormat(norm_fmt)
        self.setTextCursor(cursor)

        self._adjust_height()
        self._update_tall_parentheses()
        QTimer.singleShot(0, self._reposition_fractions)
        QTimer.singleShot(0, self.viewport().update)

        if not is_result:
            if focus_target == "den":
                frac.den_edit.setFocus()
                frac.den_edit.selectAll()
                self._active_fraction_slot = frac.den_slot
            elif focus_target == "num":
                frac.num_edit.setFocus()
                frac.num_edit.selectAll()
                self._active_fraction_slot = frac.num_slot
            else:
                self.setFocus()
        else:
            self.setFocus()

    def insert_fraction(self, num: str = "a", den: str = "b"):
        self.insert_fraction_widget(num=num, den=den, focus_target="num")

    def insert_definite_integral_widget(self, a: str = "a", b: str = "b", f: str = "f",
                                       var: str = "x", show_differential: bool = False,
                                       focus_target: str = "f"):
        """Insert a 2D vertical definite integral widget directly inline in math text."""
        if not hasattr(self, 'frac_widgets'):
            self.frac_widgets = {}
        self._fraction_id_counter = getattr(self, '_fraction_id_counter', 0) + 1
        fid = self._fraction_id_counter

        widget = DefiniteIntegralWidget(a=a, b=b, f=f, var=var,
                                        show_differential=show_differential,
                                        fid=fid, parent_edit=self)
        self.frac_widgets[fid] = widget
        widget.show()

        # Transparent placeholder image to reserve space in QTextDocument
        pm = QPixmap(max(1, widget.width()), max(1, widget.height()))
        pm.fill(Qt.GlobalColor.transparent)
        url_str = f"frac://cell_{id(self)}_{fid}"
        url = QUrl(url_str)
        self.document().addResource(QTextDocument.ResourceType.ImageResource, url, pm)

        img_fmt = QTextImageFormat()
        img_fmt.setName(url_str)
        img_fmt.setWidth(widget.width())
        img_fmt.setHeight(widget.height())
        img_fmt.setVerticalAlignment(QTextImageFormat.VerticalAlignment.AlignMiddle)
        img_fmt.setProperty(PROP_FRAC_ID, fid)
        img_fmt.setProperty(PROP_MODE, self.current_typing_mode)

        cursor = self.textCursor()
        cursor.insertImage(img_fmt)
        norm_fmt = self._get_char_format_for_mode(self.current_typing_mode)
        cursor.setCharFormat(norm_fmt)
        self.setCurrentCharFormat(norm_fmt)
        self.setTextCursor(cursor)

        self._adjust_height()
        self._update_tall_parentheses()
        QTimer.singleShot(0, self._reposition_fractions)
        QTimer.singleShot(0, self.viewport().update)

        if focus_target == "a":
            widget.a_edit.setFocus()
            widget.a_edit.selectAll()
        elif focus_target == "b":
            widget.b_edit.setFocus()
            widget.b_edit.selectAll()
        elif focus_target == "x" and show_differential:
            widget.x_edit.setFocus()
            widget.x_edit.selectAll()
        elif focus_target == "f":
            widget.f_edit.setFocus()
            widget.f_edit.selectAll()
        else:
            self.setFocus()

    def insert_big_operator_widget(self, op_symbol: str = "∑", top: str = "n",
                                   bottom: str = "k = 1", body: str = "f",
                                   focus_target: str = "body"):
        """Insert a 2D vertical big operator (∑ or ∏) widget directly inline in math text."""
        if not hasattr(self, 'frac_widgets'):
            self.frac_widgets = {}
        self._fraction_id_counter = getattr(self, '_fraction_id_counter', 0) + 1
        fid = self._fraction_id_counter

        widget = BigOperatorWidget(op_symbol=op_symbol, top=top, bottom=bottom,
                                   body=body, fid=fid, parent_edit=self)
        self.frac_widgets[fid] = widget
        widget.show()

        # Transparent placeholder image to reserve space in QTextDocument
        pm = QPixmap(max(1, widget.width()), max(1, widget.height()))
        pm.fill(Qt.GlobalColor.transparent)
        url_str = f"frac://cell_{id(self)}_{fid}"
        url = QUrl(url_str)
        self.document().addResource(QTextDocument.ResourceType.ImageResource, url, pm)

        img_fmt = QTextImageFormat()
        img_fmt.setName(url_str)
        img_fmt.setWidth(widget.width())
        img_fmt.setHeight(widget.height())
        img_fmt.setVerticalAlignment(QTextImageFormat.VerticalAlignment.AlignMiddle)
        img_fmt.setProperty(PROP_FRAC_ID, fid)
        img_fmt.setProperty(PROP_MODE, self.current_typing_mode)

        cursor = self.textCursor()
        cursor.insertImage(img_fmt)
        norm_fmt = self._get_char_format_for_mode(self.current_typing_mode)
        cursor.setCharFormat(norm_fmt)
        self.setCurrentCharFormat(norm_fmt)
        self.setTextCursor(cursor)

        self._adjust_height()
        self._update_tall_parentheses()
        QTimer.singleShot(0, self._reposition_fractions)
        QTimer.singleShot(0, self.viewport().update)

        if focus_target == "bottom":
            widget.bot_edit.setFocus()
            widget.bot_edit.selectAll()
        elif focus_target == "top":
            widget.top_edit.setFocus()
            widget.top_edit.selectAll()
        elif focus_target == "body":
            widget.body_edit.setFocus()
            widget.body_edit.selectAll()
        else:
            self.setFocus()

    def insert_radical_widget(self, radicand: str = "a", degree: str = None, focus_target: str = "radicand", is_result: bool = False):
        """Insert a 2D radical (square root or nth root) widget directly inline in math text."""
        if not hasattr(self, 'frac_widgets'):
            self.frac_widgets = {}
        self._fraction_id_counter = getattr(self, '_fraction_id_counter', 0) + 1
        fid = self._fraction_id_counter

        rad = RadicalWidget(radicand=radicand, degree=degree, fid=fid, parent_edit=self, is_result=is_result, read_only=is_result)
        self.frac_widgets[fid] = rad
        rad.show()

        # Transparent placeholder image to reserve space in QTextDocument
        pm = QPixmap(max(1, rad.width()), max(1, rad.height()))
        pm.fill(Qt.GlobalColor.transparent)
        url_str = f"frac://cell_{id(self)}_{fid}"
        url = QUrl(url_str)
        self.document().addResource(QTextDocument.ResourceType.ImageResource, url, pm)

        img_fmt = QTextImageFormat()
        img_fmt.setName(url_str)
        img_fmt.setWidth(rad.width())
        img_fmt.setHeight(rad.height())
        img_fmt.setVerticalAlignment(QTextImageFormat.VerticalAlignment.AlignMiddle)
        img_fmt.setProperty(PROP_FRAC_ID, fid)
        img_fmt.setProperty(PROP_MODE, self.current_typing_mode)

        cursor = self.textCursor()
        cursor.insertImage(img_fmt)
        norm_fmt = self._get_char_format_for_mode(self.current_typing_mode)
        cursor.setCharFormat(norm_fmt)
        self.setCurrentCharFormat(norm_fmt)
        self.setTextCursor(cursor)

        self._adjust_height()
        self._update_tall_parentheses()
        QTimer.singleShot(0, self._reposition_fractions)
        QTimer.singleShot(0, self.viewport().update)

        if not is_result:
            if focus_target == "deg" and hasattr(rad, 'deg_edit') and rad.deg_edit:
                rad.deg_edit.setFocus()
                rad.deg_edit.selectAll()
            elif focus_target in ("rad", "radicand") and hasattr(rad, 'rad_edit') and rad.rad_edit:
                rad.rad_edit.setFocus()
                rad.rad_edit.selectAll()
            elif focus_target == "degree" and rad.deg_slot and rad.deg_slot.first_edit():
                fe = rad.deg_slot.first_edit()
                fe.setFocus()
                fe.selectAll()
                self._active_fraction_slot = rad.deg_slot
            elif hasattr(rad, 'rad_slot') and rad.rad_slot and rad.rad_slot.first_edit():
                fe = rad.rad_slot.first_edit()
                fe.setFocus()
                fe.selectAll()
                self._active_fraction_slot = rad.rad_slot
            else:
                self.setFocus()
        else:
            self.setFocus()
        return rad

    def insert_eval_bar_widget(self, f: str = "f", cond: str = "x = a", focus_target: str = "cond"):
        """Insert a 2D evaluation-at-point (eval bar) widget directly inline in math text: f|_{x=a}"""
        if not hasattr(self, 'frac_widgets'):
            self.frac_widgets = {}
        self._fraction_id_counter = getattr(self, '_fraction_id_counter', 0) + 1
        fid = self._fraction_id_counter

        widget = EvalBarWidget(f=f, cond=cond, fid=fid, parent_edit=self)
        self.frac_widgets[fid] = widget
        widget.show()

        pm = QPixmap(max(1, widget.width()), max(1, widget.height()))
        pm.fill(Qt.GlobalColor.transparent)
        url_str = f"frac://cell_{id(self)}_{fid}"
        url = QUrl(url_str)
        self.document().addResource(QTextDocument.ResourceType.ImageResource, url, pm)

        img_fmt = QTextImageFormat()
        img_fmt.setName(url_str)
        img_fmt.setWidth(widget.width())
        img_fmt.setHeight(widget.height())
        img_fmt.setVerticalAlignment(QTextImageFormat.VerticalAlignment.AlignMiddle)
        img_fmt.setProperty(PROP_FRAC_ID, fid)
        img_fmt.setProperty(PROP_MODE, self.current_typing_mode)

        cursor = self.textCursor()
        cursor.insertImage(img_fmt)
        norm_fmt = self._get_char_format_for_mode(self.current_typing_mode)
        cursor.setCharFormat(norm_fmt)
        self.setCurrentCharFormat(norm_fmt)
        self.setTextCursor(cursor)

        self._adjust_height()
        self._update_tall_parentheses()
        QTimer.singleShot(0, self._reposition_fractions)
        QTimer.singleShot(0, self.viewport().update)

        if focus_target == "f":
            widget.f_edit.setFocus()
            widget.f_edit.selectAll()
        elif focus_target == "cond":
            widget.cond_edit.setFocus()
            widget.cond_edit.selectAll()
        else:
            self.setFocus()
        return widget

    def insert_binomial_widget(self, top: str = "n", bot: str = "k", focus_target: str = "bot"):
        """Insert a 2D binomial coefficient widget directly inline in math text: (n choose k)"""
        if not hasattr(self, 'frac_widgets'):
            self.frac_widgets = {}
        self._fraction_id_counter = getattr(self, '_fraction_id_counter', 0) + 1
        fid = self._fraction_id_counter

        widget = BinomialWidget(top=top, bot=bot, fid=fid, parent_edit=self)
        self.frac_widgets[fid] = widget
        widget.show()

        pm = QPixmap(max(1, widget.width()), max(1, widget.height()))
        pm.fill(Qt.GlobalColor.transparent)
        url_str = f"frac://cell_{id(self)}_{fid}"
        url = QUrl(url_str)
        self.document().addResource(QTextDocument.ResourceType.ImageResource, url, pm)

        img_fmt = QTextImageFormat()
        img_fmt.setName(url_str)
        img_fmt.setWidth(widget.width())
        img_fmt.setHeight(widget.height())
        img_fmt.setVerticalAlignment(QTextImageFormat.VerticalAlignment.AlignMiddle)
        img_fmt.setProperty(PROP_FRAC_ID, fid)
        img_fmt.setProperty(PROP_MODE, self.current_typing_mode)

        cursor = self.textCursor()
        cursor.insertImage(img_fmt)
        norm_fmt = self._get_char_format_for_mode(self.current_typing_mode)
        cursor.setCharFormat(norm_fmt)
        self.setCurrentCharFormat(norm_fmt)
        self.setTextCursor(cursor)

        self._adjust_height()
        self._update_tall_parentheses()
        QTimer.singleShot(0, self._reposition_fractions)
        QTimer.singleShot(0, self.viewport().update)

        if focus_target == "top":
            widget.top_edit.setFocus()
            widget.top_edit.selectAll()
        elif focus_target == "bot":
            widget.bot_edit.setFocus()
            widget.bot_edit.selectAll()
        else:
            self.setFocus()
        return widget

    def insert_limit_widget(self, target: str = "x → a", body: str = "f", direction: str = "", focus_target: str = "body"):
        """Insert a 2D limit widget directly inline in math text: lim_(x->a) f"""
        if not hasattr(self, 'frac_widgets'):
            self.frac_widgets = {}
        self._fraction_id_counter = getattr(self, '_fraction_id_counter', 0) + 1
        fid = self._fraction_id_counter

        widget = LimitWidget(target=target, body=body, direction=direction, fid=fid, parent_edit=self)
        self.frac_widgets[fid] = widget
        widget.show()

        pm = QPixmap(max(1, widget.width()), max(1, widget.height()))
        pm.fill(Qt.GlobalColor.transparent)
        url_str = f"frac://cell_{id(self)}_{fid}"
        url = QUrl(url_str)
        self.document().addResource(QTextDocument.ResourceType.ImageResource, url, pm)

        img_fmt = QTextImageFormat()
        img_fmt.setName(url_str)
        img_fmt.setWidth(widget.width())
        img_fmt.setHeight(widget.height())
        img_fmt.setVerticalAlignment(QTextImageFormat.VerticalAlignment.AlignMiddle)
        img_fmt.setProperty(PROP_FRAC_ID, fid)
        img_fmt.setProperty(PROP_MODE, self.current_typing_mode)

        cursor = self.textCursor()
        cursor.insertImage(img_fmt)
        norm_fmt = self._get_char_format_for_mode(self.current_typing_mode)
        cursor.setCharFormat(norm_fmt)
        self.setCurrentCharFormat(norm_fmt)
        self.setTextCursor(cursor)

        self._adjust_height()
        self._update_tall_parentheses()
        QTimer.singleShot(0, self._reposition_fractions)
        QTimer.singleShot(0, self.viewport().update)

        if focus_target == "target":
            widget.target_edit.setFocus()
            widget.target_edit.selectAll()
        elif focus_target == "body":
            widget.body_edit.setFocus()
            widget.body_edit.selectAll()
        else:
            self.setFocus()
        return widget

    def insert_piecewise_widget(self, expr1: str = "-x", cond1: str = "x < 0",
                                expr2: str = "x", cond2: str = "otherwise",
                                focus_target: str = "expr1"):
        """Insert a 2D piecewise function widget directly inline in math text."""
        if not hasattr(self, 'frac_widgets'):
            self.frac_widgets = {}
        self._fraction_id_counter = getattr(self, '_fraction_id_counter', 0) + 1
        fid = self._fraction_id_counter

        widget = PiecewiseWidget(expr1=expr1, cond1=cond1, expr2=expr2, cond2=cond2, fid=fid, parent_edit=self)
        self.frac_widgets[fid] = widget
        widget.show()

        pm = QPixmap(max(1, widget.width()), max(1, widget.height()))
        pm.fill(Qt.GlobalColor.transparent)
        url_str = f"frac://cell_{id(self)}_{fid}"
        url = QUrl(url_str)
        self.document().addResource(QTextDocument.ResourceType.ImageResource, url, pm)

        img_fmt = QTextImageFormat()
        img_fmt.setName(url_str)
        img_fmt.setWidth(widget.width())
        img_fmt.setHeight(widget.height())
        img_fmt.setVerticalAlignment(QTextImageFormat.VerticalAlignment.AlignMiddle)
        img_fmt.setProperty(PROP_FRAC_ID, fid)
        img_fmt.setProperty(PROP_MODE, self.current_typing_mode)

        cursor = self.textCursor()
        cursor.insertImage(img_fmt)
        norm_fmt = self._get_char_format_for_mode(self.current_typing_mode)
        cursor.setCharFormat(norm_fmt)
        self.setCurrentCharFormat(norm_fmt)
        self.setTextCursor(cursor)

        self._adjust_height()
        self._update_tall_parentheses()
        QTimer.singleShot(0, self._reposition_fractions)
        QTimer.singleShot(0, self.viewport().update)

        if focus_target == "expr1":
            widget.expr1_edit.setFocus()
            widget.expr1_edit.selectAll()
        elif focus_target == "cond1":
            widget.cond1_edit.setFocus()
            widget.cond1_edit.selectAll()
        elif focus_target == "expr2":
            widget.expr2_edit.setFocus()
            widget.expr2_edit.selectAll()
        elif focus_target == "cond2":
            widget.cond2_edit.setFocus()
            widget.cond2_edit.selectAll()
        else:
            self.setFocus()
        return widget

    def insert_vector_widget(self, r1: str = "a", r2: str = "b", focus_target: str = "r1"):
        """Insert a 2D column vector widget directly inline in math text: [ a / b ]"""
        if not hasattr(self, 'frac_widgets'):
            self.frac_widgets = {}
        self._fraction_id_counter = getattr(self, '_fraction_id_counter', 0) + 1
        fid = self._fraction_id_counter

        widget = VectorWidget(r1=r1, r2=r2, fid=fid, parent_edit=self)
        self.frac_widgets[fid] = widget
        widget.show()

        pm = QPixmap(max(1, widget.width()), max(1, widget.height()))
        pm.fill(Qt.GlobalColor.transparent)
        url_str = f"frac://cell_{id(self)}_{fid}"
        url = QUrl(url_str)
        self.document().addResource(QTextDocument.ResourceType.ImageResource, url, pm)

        img_fmt = QTextImageFormat()
        img_fmt.setName(url_str)
        img_fmt.setWidth(widget.width())
        img_fmt.setHeight(widget.height())
        img_fmt.setVerticalAlignment(QTextImageFormat.VerticalAlignment.AlignMiddle)
        img_fmt.setProperty(PROP_FRAC_ID, fid)
        img_fmt.setProperty(PROP_MODE, self.current_typing_mode)

        cursor = self.textCursor()
        cursor.insertImage(img_fmt)
        norm_fmt = self._get_char_format_for_mode(self.current_typing_mode)
        cursor.setCharFormat(norm_fmt)
        self.setCurrentCharFormat(norm_fmt)
        self.setTextCursor(cursor)

        self._adjust_height()
        self._update_tall_parentheses()
        QTimer.singleShot(0, self._reposition_fractions)
        QTimer.singleShot(0, self.viewport().update)

        if focus_target == "r1":
            widget.r1_edit.setFocus()
            widget.r1_edit.selectAll()
        elif focus_target == "r2":
            widget.r2_edit.setFocus()
            widget.r2_edit.selectAll()
        else:
            self.setFocus()
        return widget

    def insert_matrix_widget(self, data: list = None, rows: int = 2, cols: int = 2, focus_target: str = "first", is_result: bool = False):
        """Insert an authentic 2D matrix widget directly inline in math text with square brackets."""
        if not hasattr(self, 'frac_widgets'):
            self.frac_widgets = {}
        self._fraction_id_counter = getattr(self, '_fraction_id_counter', 0) + 1
        fid = self._fraction_id_counter

        widget = MatrixWidget(rows=rows, cols=cols, data=data, fid=fid, parent_edit=self, is_result=is_result)
        self.frac_widgets[fid] = widget
        widget.show()

        pm = QPixmap(max(1, widget.width()), max(1, widget.height()))
        pm.fill(Qt.GlobalColor.transparent)
        url_str = f"frac://cell_{id(self)}_{fid}"
        url = QUrl(url_str)
        self.document().addResource(QTextDocument.ResourceType.ImageResource, url, pm)

        img_fmt = QTextImageFormat()
        img_fmt.setName(url_str)
        img_fmt.setWidth(widget.width())
        img_fmt.setHeight(widget.height())
        img_fmt.setVerticalAlignment(QTextImageFormat.VerticalAlignment.AlignMiddle)
        img_fmt.setProperty(PROP_FRAC_ID, fid)
        img_fmt.setProperty(PROP_MODE, self.current_typing_mode)

        cursor = self.textCursor()
        cursor.insertImage(img_fmt)
        norm_fmt = self._get_char_format_for_mode(self.current_typing_mode)
        cursor.setCharFormat(norm_fmt)
        self.setCurrentCharFormat(norm_fmt)
        self.setTextCursor(cursor)

        self._adjust_height()
        self._update_tall_parentheses()
        QTimer.singleShot(0, self._reposition_fractions)
        QTimer.singleShot(0, self.viewport().update)

        if focus_target == "first" and not is_result and widget.cells:
            widget.cells[0][0].setFocus()
            widget.cells[0][0].selectAll()
        elif focus_target == "last" and not is_result and widget.cells:
            widget.cells[-1][-1].setFocus()
            widget.cells[-1][-1].selectAll()
        else:
            self.setFocus()
        return widget

    def _on_frac_size_changed(self, frac):
        doc = self.document()
        it = doc.begin()
        while it.isValid():
            fit = it.begin()
            while not fit.atEnd():
                frag = fit.fragment()
                if frag.isValid():
                    fmt = frag.charFormat()
                    if fmt.isImageFormat() and fmt.property(PROP_FRAC_ID) == frac.fid:
                        img_fmt = fmt.toImageFormat()
                        if img_fmt.width() != frac.width() or img_fmt.height() != frac.height():
                            img_fmt.setWidth(frac.width())
                            img_fmt.setHeight(frac.height())
                            cur = QTextCursor(doc)
                            cur.setPosition(frag.position())
                            cur.setPosition(frag.position() + frag.length(), QTextCursor.MoveMode.KeepAnchor)
                            cur.setCharFormat(img_fmt)
                        break
                fit += 1
            it = it.next()
        self._adjust_height()
        self._reposition_fractions()
        self._update_tall_parentheses()
        self.viewport().update()

    def _reposition_fractions(self):
        if not hasattr(self, 'frac_widgets') or not self.frac_widgets:
            return
        doc = self.document()
        present_fids = set()
        it = doc.begin()
        while it.isValid():
            fit = it.begin()
            while not fit.atEnd():
                frag = fit.fragment()
                if frag.isValid():
                    fmt = frag.charFormat()
                    if fmt.isImageFormat() and fmt.property(PROP_FRAC_ID):
                        fid = fmt.property(PROP_FRAC_ID)
                        present_fids.add(fid)
                        if fid in self.frac_widgets:
                            cur = QTextCursor(doc)
                            cur.setPosition(frag.position())
                            rect = self.cursorRect(cur)
                            frac = self.frac_widgets[fid]
                            is_exp = fmt.property(PROP_IS_EXPONENT) or getattr(frac, 'is_exponent', False)
                            if is_exp:
                                y = max(2, rect.y() + 2)
                            else:
                                y = max(2, rect.y() + (rect.height() - frac.height()) // 2)
                            frac.move(rect.x(), y)
                            frac.show()
                fit += 1
            it = it.next()

        if self._cleanup_orphaned_fractions():
            self._adjust_height()

    def _find_fraction_fragment_pos(self, fid: int):
        doc = self.document()
        it = doc.begin()
        while it.isValid():
            fit = it.begin()
            while not fit.atEnd():
                frag = fit.fragment()
                if frag.isValid():
                    fmt = frag.charFormat()
                    if fmt.isImageFormat() and fmt.property(PROP_FRAC_ID) == fid:
                        return frag.position(), frag.length()
                fit += 1
            it = it.next()
        return None, 0

    def move_cursor_after_fraction(self, fid: int):
        pos, length = self._find_fraction_fragment_pos(fid)
        if pos is not None:
            cur = self.textCursor()
            cur.setPosition(pos + length)
            norm_fmt = self._get_char_format_for_mode(self.current_typing_mode)
            cur.setCharFormat(norm_fmt)
            self.setCurrentCharFormat(norm_fmt)
            self.setTextCursor(cur)
            self.setFocus()
            self.viewport().update()

    def move_cursor_before_fraction(self, fid: int):
        pos, length = self._find_fraction_fragment_pos(fid)
        if pos is not None:
            cur = self.textCursor()
            cur.setPosition(pos)
            norm_fmt = self._get_char_format_for_mode(self.current_typing_mode)
            cur.setCharFormat(norm_fmt)
            self.setCurrentCharFormat(norm_fmt)
            self.setTextCursor(cur)
            self.setFocus()
            self.viewport().update()

    def remove_fraction(self, fid: int):
        pos, length = self._find_fraction_fragment_pos(fid)
        if hasattr(self, 'frac_widgets') and fid in self.frac_widgets:
            w = self.frac_widgets.pop(fid)
            if hasattr(self, '_active_fraction_slot') and self._active_fraction_slot:
                try:
                    if sip.isdeleted(self._active_fraction_slot) or (w and not sip.isdeleted(w) and (w == self._active_fraction_slot or w.isAncestorOf(self._active_fraction_slot))):
                        self._active_fraction_slot = None
                except Exception:
                    self._active_fraction_slot = None
            w.deleteLater()
        if pos is not None:
            cur = self.textCursor()
            cur.setPosition(pos)
            cur.setPosition(pos + length, QTextCursor.MoveMode.KeepAnchor)
            cur.removeSelectedText()
            self.setTextCursor(cur)
        self.setFocus()
        self._adjust_height()
        self._reposition_fractions()
        self._update_tall_parentheses()
        self.viewport().update()

    def replace_fraction_with_text(self, fid: int, new_text: str):
        pos, length = self._find_fraction_fragment_pos(fid)
        if hasattr(self, 'frac_widgets') and fid in self.frac_widgets:
            w = self.frac_widgets.pop(fid)
            if hasattr(self, '_active_fraction_slot') and self._active_fraction_slot:
                try:
                    if sip.isdeleted(self._active_fraction_slot) or (w and not sip.isdeleted(w) and (w == self._active_fraction_slot or w.isAncestorOf(self._active_fraction_slot))):
                        self._active_fraction_slot = None
                except Exception:
                    self._active_fraction_slot = None
            w.deleteLater()
        if pos is not None:
            cur = self.textCursor()
            cur.setPosition(pos)
            cur.setPosition(pos + length, QTextCursor.MoveMode.KeepAnchor)
            mode = self.get_mode_at_cursor()
            fmt = self._get_char_format_for_mode(mode)
            cur.insertText(new_text, fmt)
            self.setTextCursor(cur)
        self.setFocus()
        self._adjust_height()
        self._reposition_fractions()
        self._update_tall_parentheses()
        self.viewport().update()

    def _clear_fractions(self):
        self._active_fraction_slot = None
        if hasattr(self, 'frac_widgets'):
            for frac in list(self.frac_widgets.values()):
                frac.deleteLater()
            self.frac_widgets.clear()

    def clear(self):
        self._active_fraction_slot = None
        self._clear_fractions()
        super().clear()

    def _get_selected_math_text(self, cursor=None) -> str:
        """Extract plain or mathematical text representing the current text selection,
        including any embedded fractions."""
        if cursor is None:
            cursor = self.textCursor()
        if not cursor.hasSelection():
            return ""
        start = cursor.selectionStart()
        end = cursor.selectionEnd()
        doc = self.document()
        parts = []
        block = doc.begin()
        prev_level = 0
        while block.isValid():
            it = block.begin()
            while not it.atEnd():
                frag = it.fragment()
                if frag.isValid():
                    frag_pos = frag.position()
                    frag_len = frag.length()
                    if frag_pos + frag_len > start and frag_pos < end:
                        fmt = frag.charFormat()
                        if fmt.isImageFormat():
                            fid = fmt.property(PROP_FRAC_ID)
                            if fid and hasattr(self, 'frac_widgets') and fid in self.frac_widgets:
                                parts.append(self.frac_widgets[fid].text_expression())
                            else:
                                expr = fmt.property(PROP_MATH_EXPR)
                                parts.append(str(expr) if expr else frag.text())
                            prev_level = 0
                        else:
                            level = fmt.property(PROP_SUBSCRIPT_LEVEL) or 0
                            sub_start = max(0, start - frag_pos)
                            sub_end = min(frag_len, end - frag_pos)
                            text = frag.text()[sub_start:sub_end]
                            if level > 0 and level > prev_level:
                                for _ in range(level - prev_level):
                                    parts.append("_")
                            parts.append(text)
                            prev_level = level
                it += 1
            block = block.next()
        return "".join(parts).strip()

    def _find_tall_parenthesis_pairs(self) -> list:
        """Find matching parenthesis pairs '(' and ')' that enclose at least one tall widget
        (FractionWidget or DefiniteIntegralWidget) in the same line."""
        doc = self.document()
        widget_positions = []
        it = doc.begin()
        while it.isValid():
            fit = it.begin()
            while not fit.atEnd():
                frag = fit.fragment()
                if frag.isValid():
                    fmt = frag.charFormat()
                    if fmt.isImageFormat() and fmt.property(PROP_FRAC_ID):
                        fid = fmt.property(PROP_FRAC_ID)
                        if hasattr(self, 'frac_widgets') and fid in self.frac_widgets:
                            w = self.frac_widgets[fid]
                            widget_positions.append((frag.position(), w))
                fit += 1
            it = it.next()

        if not widget_positions:
            return []

        raw_text = doc.toPlainText()
        stack = []
        pairs = []
        for idx, ch in enumerate(raw_text):
            if ch == '(':
                stack.append(idx)
            elif ch == ')':
                if stack:
                    open_idx = stack.pop()
                    enclosed = [w for pos, w in widget_positions if open_idx < pos < idx]
                    if enclosed:
                        c_open = QTextCursor(doc)
                        c_open.setPosition(open_idx)
                        c_close = QTextCursor(doc)
                        c_close.setPosition(idx)
                        if c_open.blockNumber() == c_close.blockNumber():
                            pairs.append({
                                'open_pos': open_idx,
                                'close_pos': idx,
                                'widgets': enclosed
                            })
        return pairs

    def _update_tall_parentheses(self):
        """Format parenthesis characters enclosing tall widgets with transparent color
        and adequate advance spacing so drawn Bézier brackets fit naturally."""
        if getattr(self, '_updating_tall_parens', False):
            return
        self._updating_tall_parens = True
        doc = self.document()
        prev_blocked = doc.signalsBlocked()
        doc.blockSignals(True)
        try:
            sz = getattr(self.parent_cell, 'current_font_size', 12) if self.parent_cell else 12
            if not isinstance(sz, int) or sz <= 0:
                sz = 12
            factor = getattr(self.parent_cell, 'zoom_factor', 1.0) if self.parent_cell else 1.0
            display_sz = max(4, round(sz * factor))

            pairs = self._find_tall_parenthesis_pairs()
            tall_positions = {}
            for p in pairs:
                max_h = max((w.height() for w in p['widgets']), default=display_sz)
                paren_sz = max(14, round(display_sz * 1.35), int(max_h * 0.38))
                tall_positions[p['open_pos']] = paren_sz
                tall_positions[p['close_pos']] = paren_sz

            # Revert any previously tall parens that are no longer in tall_positions
            it = doc.begin()
            while it.isValid():
                fit = it.begin()
                while not fit.atEnd():
                    frag = fit.fragment()
                    if frag.isValid():
                        fmt = frag.charFormat()
                        if fmt.property(PROP_TALL_PAREN) and frag.position() not in tall_positions:
                            mode = fmt.property(PROP_MODE) or self.current_typing_mode
                            norm_fmt = self._get_char_format_for_mode(mode)
                            cur = QTextCursor(doc)
                            cur.setPosition(frag.position())
                            cur.setPosition(frag.position() + frag.length(), QTextCursor.MoveMode.KeepAnchor)
                            cur.setCharFormat(norm_fmt)
                    fit += 1
                it = it.next()

            # Apply transparent formatting with adequate spacing for tall parens
            for pos, psz in tall_positions.items():
                cur = QTextCursor(doc)
                cur.setPosition(pos)
                cur.setPosition(pos + 1, QTextCursor.MoveMode.KeepAnchor)
                fmt_tall = QTextCharFormat()
                fmt_tall.setFontPointSize(psz)
                fmt_tall.setForeground(Qt.GlobalColor.transparent)
                fmt_tall.setProperty(PROP_TALL_PAREN, True)
                cur.mergeCharFormat(fmt_tall)
        finally:
            doc.blockSignals(prev_blocked)
            self._updating_tall_parens = False

    def _draw_tall_parentheses(self):
        """Draw smooth antialiased Bézier math parentheses matching fraction height."""
        pairs = self._find_tall_parenthesis_pairs()
        if not pairs:
            return

        doc = self.document()
        is_dark = (getattr(self.parent_cell, 'theme_mode', 'light') == 'dark') if self.parent_cell else False
        normal_paren_color = QColor('#f8fafc') if is_dark else QColor('#000000')
        sel_color = QColor('#ffffff')
        factor = getattr(self.parent_cell, 'zoom_factor', 1.0) if self.parent_cell else 1.0
        stroke_w = max(1.4, 1.8 * factor)

        cur_tc = self.textCursor()
        has_sel = cur_tc.hasSelection()
        sel_start = cur_tc.selectionStart() if has_sel else -1
        sel_end = cur_tc.selectionEnd() if has_sel else -1

        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        for pair in pairs:
            open_pos = pair['open_pos']
            close_pos = pair['close_pos']
            widgets = pair['widgets']

            # Visible fraction bounds
            min_y = min((w.y() for w in widgets if w.isVisible()), default=0)
            max_bottom = max((w.y() + w.height() for w in widgets if w.isVisible()), default=0)

            # Left paren (
            cur_open = QTextCursor(doc)
            cur_open.setPosition(open_pos)
            r_open = self.cursorRect(cur_open)
            cur_open.setPosition(open_pos + 1)
            r_open_end = self.cursorRect(cur_open)

            if min_y == 0 and max_bottom == 0:
                min_y = r_open.y()
                max_bottom = r_open.y() + r_open.height()
            else:
                min_y = min(min_y, r_open.y())
                max_bottom = max(max_bottom, r_open.y() + r_open.height())

            fy = min_y - 2
            fh = max(16, (max_bottom - min_y) + 4)

            open_is_sel = has_sel and (sel_start <= open_pos < sel_end)
            pen_open = QPen(sel_color if open_is_sel else normal_paren_color, stroke_w)
            pen_open.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen_open)

            pw_l = max(6, r_open_end.x() - r_open.x() - 2)
            lx = r_open.x() + 1
            path_l = QPainterPath()
            path_l.moveTo(lx + pw_l, fy)
            path_l.cubicTo(lx, fy + fh * 0.2, lx, fy + fh * 0.8, lx + pw_l, fy + fh)
            painter.drawPath(path_l)

            # Right paren )
            cur_close = QTextCursor(doc)
            cur_close.setPosition(close_pos)
            r_close = self.cursorRect(cur_close)
            cur_close.setPosition(close_pos + 1)
            r_close_end = self.cursorRect(cur_close)

            close_is_sel = has_sel and (sel_start <= close_pos < sel_end)
            pen_close = QPen(sel_color if close_is_sel else normal_paren_color, stroke_w)
            pen_close.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen_close)

            pw_r = max(6, r_close_end.x() - r_close.x() - 2)
            rx = r_close.x() + 1
            path_r = QPainterPath()
            path_r.moveTo(rx, fy)
            path_r.cubicTo(rx + pw_r, fy + fh * 0.2, rx + pw_r, fy + fh * 0.8, rx, fy + fh)
            painter.drawPath(path_r)

        painter.end()

    def paintEvent(self, event):
        is_math_focus = False
        ws = self._get_worksheet_view()
        has_multi_cells = bool(ws and getattr(ws, 'selected_cells', None) and len(ws.selected_cells) > 1)
        if self.hasFocus() and not has_multi_cells:
            mode = self.get_mode_at_cursor()
            if mode in (
                getattr(self.parent_cell, 'MODE_2D_MATH', '2d_math'),
                getattr(self.parent_cell, 'MODE_NONEXEC_MATH', 'nonexec_math'),
                '2d_math',
                'nonexec_math'
            ):
                is_math_focus = True

        if is_math_focus:
            p = QPainter(self.viewport())
            p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            is_dark = bool(self.parent_cell and getattr(self.parent_cell, 'theme_mode', 'light') == 'dark')
            border_color = QColor("#60a5fa") if is_dark else QColor("#93c5fd")
            bg_color = QColor(30, 41, 59, 130) if is_dark else QColor(239, 246, 255, 130)
            pen = QPen(border_color, 1, Qt.PenStyle.DashLine)
            p.setPen(pen)
            p.setBrush(bg_color)

            margin = int(self.document().documentMargin())
            ideal_w = self.document().idealWidth()
            tl = self.document().begin().layout() if self.document().begin().isValid() else None
            is_multiline = (tl is not None and tl.lineCount() > 1) or self.document().blockCount() > 1

            if is_multiline:
                box_w = self.viewport().width() - 2
                box_h = max(18, self.viewport().height() - 4)
                box_y = 1.0
            else:
                box_w = min(max(28, int(ideal_w) + margin * 2 + 8), self.viewport().width() - 2)
                content_h = max(14, self.fontMetrics().lineSpacing())
                if hasattr(self, 'frac_widgets') and self.frac_widgets:
                    content_h = max(content_h, max(f.height() for f in self.frac_widgets.values()))
                box_h = min(content_h + 6, self.viewport().height() - 2)
                box_h = max(18, box_h)
                box_y = max(1.0, float((self.viewport().height() - box_h) / 2))

            rect = QRectF(1.0, float(box_y), float(box_w), float(box_h))
            p.drawRoundedRect(rect, 2.0, 2.0)
            p.end()

        super().paintEvent(event)
        self._reposition_fractions()
        self._draw_tall_parentheses()
        self._draw_image_resize_handles()

    def focusInEvent(self, event):
        super().focusInEvent(event)
        self.viewport().update()

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self.viewport().update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'frac_widgets') and self.frac_widgets:
            for frac in list(self.frac_widgets.values()):
                if hasattr(frac, '_adjust_size'):
                    frac._adjust_size()
                    self._on_frac_size_changed(frac)
        self._adjust_height()
        self._reposition_fractions()
        self._update_tall_parentheses()

    def toPlainText(self) -> str:
        return self.get_plain_or_math_text()

    def get_plain_or_math_text(self) -> str:
        doc = self.document()
        parts = []
        block = doc.begin()
        while block.isValid():
            it = block.begin()
            prev_level = 0
            while not it.atEnd():
                frag = it.fragment()
                if frag.isValid():
                    fmt = frag.charFormat()
                    if fmt.isImageFormat():
                        fid = fmt.property(PROP_FRAC_ID)
                        if fid and hasattr(self, 'frac_widgets') and fid in self.frac_widgets:
                            parts.append(self.frac_widgets[fid].text_expression())
                        else:
                            expr = fmt.property(PROP_MATH_EXPR)
                            if expr:
                                parts.append(str(expr))
                            else:
                                parts.append(frag.text())
                        prev_level = 0
                    else:
                        level = fmt.property(PROP_SUBSCRIPT_LEVEL) or 0
                        text = frag.text()
                        if level > 0 and level > prev_level:
                            for _ in range(level - prev_level):
                                parts.append("_")
                        parts.append(text)
                        prev_level = level
                it += 1
            if block != doc.lastBlock():
                parts.append("\n")
            block = block.next()
        return "".join(parts)


    def _get_engine(self):
        if self.parent_cell and hasattr(self.parent_cell, 'engine') and self.parent_cell.engine:
            return self.parent_cell.engine
        p = self.parent()
        while p:
            if hasattr(p, 'engine') and p.engine:
                return p.engine
            p = p.parent()
        from cas_engine import CASEngine
        if not hasattr(CellInputEdit, '_shared_engine'):
            CellInputEdit._shared_engine = CASEngine()
        return CellInputEdit._shared_engine

    @staticmethod
    def _find_top_level_equal(text: str) -> int:
        depth = 0
        for idx, ch in enumerate(text):
            if ch in '([{':
                depth += 1
            elif ch in ')]}':
                depth = max(0, depth - 1)
            elif ch == '=' and depth == 0:
                prev_c = text[idx - 1] if idx > 0 else ''
                next_c = text[idx + 1] if idx + 1 < len(text) else ''
                if prev_c not in ('=', '<', '>', '!', ':') and next_c not in ('=',):
                    return idx
        return -1

    @staticmethod
    def clean_operator_spacing(text: str) -> str:
        s = text
        # Multi-character operators
        s = re.sub(r'(?<=[a-zA-Z0-9_\)\]\}])\s*:=\s*', ' := ', s)
        s = re.sub(r'(?<=[a-zA-Z0-9_\)\]\}])\s*<=\s*', ' <= ', s)
        s = re.sub(r'(?<=[a-zA-Z0-9_\)\]\}])\s*>=\s*', ' >= ', s)
        s = re.sub(r'(?<=[a-zA-Z0-9_\)\]\}])\s*!=\s*', ' != ', s)
        s = re.sub(r'(?<=[a-zA-Z0-9_\)\]\}])\s*==\s*', ' == ', s)
        s = re.sub(r'(?<=[a-zA-Z0-9_\)\]\}])\s*->\s*', ' -> ', s)
        # Relational and set/logic symbols
        for op in ['≥', '≤', '≠', '≡', '∈', '∉', '⊂', '⊃', '∩', '∪', '⇒', '∧', '∨']:
            s = re.sub(rf'\s*{re.escape(op)}\s*', f' {op} ', s)
        s = re.sub(r'\s*¬\s*', '¬', s)
        # Statement-ending colon / output suppression delimiter (e.g. "potato :")
        s = re.sub(r'(?<=[^\s:])\s*:(?=\s+|$)', ' :', s)
        # Binary =
        s = re.sub(r'(?<=[a-zA-Z0-9_\)\]\}])\s*=\s*(?=[a-zA-Z0-9_\(\[\{\-])', ' = ', s)
        # Normalize scientific notation e.g. 4e - 06 -> 4e-6, avoiding spaced exponents
        def _norm_sci(m):
            return f"{m.group(1)}e{m.group(2)}{int(m.group(3))}"
        s = re.sub(r'\b(\d+(?:\.\d+)?)[eE]\s*([+-])\s*(\d+)\b', _norm_sci, s)
        # Binary + (exclude scientific notation exponent like 1e+03)
        s = re.sub(r'(?<!\d[eE])(?<=[a-zA-Z0-9_\)\]\}])\s*\+\s*(?=[a-zA-Z0-9_\(\[\{])', ' + ', s)
        # Binary - (exclude scientific notation exponent like 4e-06)
        s = re.sub(r'(?<!\d[eE])(?<=[a-zA-Z0-9_\)\]\}])\s*-\s*(?=[a-zA-Z0-9_\(\[\{])', ' - ', s)
        # Multiplication operators: do before subscripts so word boundary matches ASCII
        s = re.sub(r'\*\*', '^', s)
        s = re.sub(r'(?<=[a-zA-Z0-9_\)\]\}])\s*(?<!\*)\*(?!\*)\s*(?=[a-zA-Z0-9_\(\[\{])', ' · ', s)
        s = re.sub(r'(?<=[a-zA-Z0-9_\)\]\}])\s*[·⋅]\s*(?=[a-zA-Z0-9_\(\[\{])', ' · ', s)
        s = re.sub(r'\s*\^\s*', '^', s)
        # Subscripts and superscripts
        s = format_subscripts_and_superscripts(s)
        # Commas: preserve decimal commas between digits without spaces (e.g. 30,4 must remain 30,4)
        # while argument/item commas (with spaces or around non-digits) are formatted with a single trailing space.
        s = re.sub(r'(?<=\d)\s*,\s+(\d)', r', \1', s)
        s = re.sub(r'(?<!\d)\s*,\s*', ', ', s)
        s = re.sub(r'(?<=\D),\s*(?!\s)', ', ', s)
        return s

    def _handle_operator_spacing(self, event: QKeyEvent) -> bool:
        """Auto-space operators like +, -, =, := so 'x+1=3+2' formats to 'x + 1 = 3 + 2' as typed."""
        if self.get_mode_at_cursor() == getattr(self.parent_cell, 'MODE_TEXT', 'text'):
            return False

        ch = event.text()
        if not ch or (event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier)):
            return False

        cursor = self.textCursor()
        pos = cursor.position()
        raw_text = super().toPlainText()
        text_before = raw_text[:pos]
        last_char = text_before[-1] if text_before else ''

        def _done(res=True):
            if res:
                self.setTextCursor(cursor)
            return res

        # Avoid redundant consecutive spaces in math mode (e.g. after auto-spaced operators)
        if ch == ' ':
            self._subscript_active = False
            self._superscript_active = False
            if text_before.endswith(' '):
                return True
            return False

        # Delimiters: parentheses, brackets, braces - always on baseline, never subscript or superscript
        if ch in ('(', ')', '[', ']', '{', '}'):
            self._subscript_active = False
            self._superscript_active = False
            fmt0 = self._get_subscript_format(0)
            self.setCurrentCharFormat(fmt0)
            cursor.setCharFormat(fmt0)
            if text_before.endswith('_'):
                cursor.deletePreviousChar()
            elif text_before.endswith('^'):
                cursor.deletePreviousChar()
            cursor.insertText(ch, fmt0)
            return _done(True)

        # Handle composite dead-key events like '^2' from European/macOS keyboards
        if ch.startswith('^') and len(ch) > 1:
            rest = ch[1:]
            sup = ''.join(SUPER_MAP.get(c, c) for c in rest)
            cursor.insertText(sup)
            self._superscript_active = True
            self._subscript_active = False
            return _done(True)

        # Handle composite dead-key events like '_1'
        if ch.startswith('_') and len(ch) > 1:
            rest = ch[1:]
            sub = ''.join(SUB_MAP.get(c, c) for c in rest)
            cursor.insertText(sub)
            self._subscript_active = True
            self._superscript_active = False
            return _done(True)

        # Entering superscript mode with '^'
        if ch == '^':
            self._superscript_active = True
            self._subscript_active = False
            return False

        cur_lvl = self.currentCharFormat().property(PROP_SUBSCRIPT_LEVEL) or cursor.charFormat().property(PROP_SUBSCRIPT_LEVEL) or 0

        # Entering subscript mode with '_'
        if ch == '_':
            if cur_lvl > 0:
                # Step down to next subscript level (e.g. comp -> repr)
                new_lvl = cur_lvl + 1
                fmt = self._get_subscript_format(new_lvl)
                self.setCurrentCharFormat(fmt)
                self._subscript_active = True
                self._superscript_active = False
                return True
            else:
                self._subscript_active = True
                self._superscript_active = False
                cursor.insertText('_')
                return _done(True)

        if (text_before.endswith('^') or text_before.endswith('^ ')) and (ch in SUPER_MAP or any(c in SUPER_MAP for c in ch)):
            if text_before.endswith('^ '):
                cursor.deletePreviousChar()
                cursor.deletePreviousChar()
            else:
                cursor.deletePreviousChar()
            sup = ''.join(SUPER_MAP.get(c, c) for c in ch)
            cursor.insertText(sup)
            self._superscript_active = True
            self._subscript_active = False
            return _done(True)
        elif getattr(self, '_superscript_active', False) and (last_char in SUPER_MAP.values() or last_char in ('^', '·', '⋅')) and (ch in SUPER_MAP or ch.lower() in SUPER_MAP):
            sup = SUPER_MAP.get(ch, SUPER_MAP.get(ch.lower(), ch))
            cursor.insertText(sup)
            self._superscript_active = True
            return _done(True)

        # Subscript handling: typing after '_' or '__' or existing subscripts
        if text_before.endswith('__') or text_before.endswith('_') or text_before.endswith('_ '):
            if text_before.endswith('__'):
                cursor.deletePreviousChar()
                cursor.deletePreviousChar()
            elif text_before.endswith('_ '):
                cursor.deletePreviousChar()
                cursor.deletePreviousChar()
            else:
                cursor.deletePreviousChar()

            if (ch in SUB_MAP or any(c in SUB_MAP for c in ch)) and ch.isdigit():
                sub = ''.join(SUB_MAP.get(c, c) for c in ch)
                cursor.insertText(sub)
                self._subscript_active = True
                self._superscript_active = False
                return _done(True)
            elif ch.isalnum():
                fmt = self._get_subscript_format(1)
                cursor.insertText(ch, fmt)
                self.setCurrentCharFormat(fmt)
                self._subscript_active = True
                self._superscript_active = False
                return _done(True)
        elif getattr(self, '_subscript_active', False) and cur_lvl > 0 and ch.isalnum():
            fmt = self._get_subscript_format(cur_lvl)
            cursor.insertText(ch, fmt)
            self._subscript_active = True
            return _done(True)
        elif getattr(self, '_subscript_active', False) and last_char in SUB_MAP.values() and ch.isalnum() and ch in SUB_MAP:
            cursor.insertText(SUB_MAP.get(ch, ch))
            self._subscript_active = True
            return _done(True)

        # Operators and punctuation exit subscript/superscript mode
        fmt0 = self._get_subscript_format(0)
        if cur_lvl > 0:
            self.setCurrentCharFormat(fmt0)
            cursor.setCharFormat(fmt0)
        self._subscript_active = False
        self._superscript_active = False

        if ch == '+':
            if last_char == ' ':
                cursor.insertText("+ ", fmt0)
            elif last_char and (last_char.isalnum() or last_char in ')]}'):
                cursor.insertText(" + ", fmt0)
            else:
                cursor.insertText("+", fmt0)
            return _done(True)

        elif ch == '-':
            if last_char == ' ':
                prev2 = text_before[:-1].rstrip()
                if prev2 and (prev2[-1].isalnum() or prev2[-1] in ')]}'):
                    cursor.insertText("- ", fmt0)
                else:
                    cursor.insertText("-", fmt0)
            elif last_char and (last_char.isalnum() or last_char in ')]}'):
                cursor.insertText(" - ", fmt0)
            else:
                cursor.insertText("-", fmt0)
            return _done(True)

        elif ch == '=':
            if text_before.endswith(' :'):
                cursor.deletePreviousChar()
                cursor.deletePreviousChar()
                pos2 = cursor.position()
                tb2 = super().toPlainText()[:pos2]
                prefix = " " if (tb2 and tb2[-1] != ' ') else ""
                cursor.insertText(prefix + ":= ", fmt0)
                return _done(True)
            elif text_before.endswith(':'):
                cursor.deletePreviousChar()
                pos2 = cursor.position()
                tb2 = super().toPlainText()[:pos2]
                prefix = " " if (tb2 and tb2[-1] != ' ') else ""
                cursor.insertText(prefix + ":= ", fmt0)
                return _done(True)
            elif text_before.endswith(' < ') or text_before.endswith('< ') or text_before.endswith('<'):
                while cursor.position() > 0 and super().toPlainText()[cursor.position() - 1] in ('<', ' '):
                    cursor.deletePreviousChar()
                pos2 = cursor.position()
                tb2 = super().toPlainText()[:pos2]
                prefix = " " if (tb2 and tb2[-1] != ' ') else ""
                cursor.insertText(prefix + "<= ", fmt0)
                return _done(True)
            elif text_before.endswith(' > ') or text_before.endswith('> ') or text_before.endswith('>'):
                while cursor.position() > 0 and super().toPlainText()[cursor.position() - 1] in ('>', ' '):
                    cursor.deletePreviousChar()
                pos2 = cursor.position()
                tb2 = super().toPlainText()[:pos2]
                prefix = " " if (tb2 and tb2[-1] != ' ') else ""
                cursor.insertText(prefix + ">= ", fmt0)
                return _done(True)
            elif text_before.endswith('!'):
                cursor.deletePreviousChar()
                pos2 = cursor.position()
                tb2 = super().toPlainText()[:pos2]
                prefix = " " if (tb2 and tb2[-1] != ' ') else ""
                cursor.insertText(prefix + "!= ", fmt0)
                return _done(True)
            elif text_before.endswith(' = ') or text_before.endswith('= ') or text_before.endswith('='):
                while cursor.position() > 0 and super().toPlainText()[cursor.position() - 1] in ('=', ' '):
                    cursor.deletePreviousChar()
                pos2 = cursor.position()
                tb2 = super().toPlainText()[:pos2]
                prefix = " " if (tb2 and tb2[-1] != ' ') else ""
                cursor.insertText(prefix + "== ", fmt0)
                return _done(True)
            elif last_char == ' ':
                cursor.insertText("= ", fmt0)
            elif last_char and (last_char.isalnum() or last_char in ')]}'):
                cursor.insertText(" = ", fmt0)
            else:
                cursor.insertText("=", fmt0)
            return _done(True)

        elif ch == '<':
            if last_char == ' ':
                cursor.insertText("< ", fmt0)
            elif last_char and (last_char.isalnum() or last_char in ')]}'):
                cursor.insertText(" < ", fmt0)
            else:
                cursor.insertText("<", fmt0)
            return _done(True)

        elif ch == '>':
            if text_before.endswith(' - ') or text_before.endswith('- ') or text_before.endswith('-'):
                while cursor.position() > 0 and super().toPlainText()[cursor.position() - 1] in ('-', ' '):
                    cursor.deletePreviousChar()
                pos2 = cursor.position()
                tb2 = super().toPlainText()[:pos2]
                prefix = " " if (tb2 and tb2[-1] != ' ') else ""
                cursor.insertText(prefix + "-> ", fmt0)
                return _done(True)
            elif last_char == ' ':
                cursor.insertText("> ", fmt0)
            elif last_char and (last_char.isalnum() or last_char in ')]}'):
                cursor.insertText(" > ", fmt0)
            else:
                cursor.insertText(">", fmt0)
            return _done(True)

        elif ch in ('*', '·', '⋅'):
            dot_sym = "·"
            if text_before.endswith(' · '):
                # Double asterisk '**' -> exponentiation '^'
                for _ in range(3):
                    cursor.deletePreviousChar()
                cursor.insertText("^", fmt0)
                return _done(True)
            elif text_before.endswith('*') or text_before.endswith('·') or text_before.endswith('⋅'):
                cursor.insertText(dot_sym, fmt0)
            elif last_char == ' ':
                cursor.insertText(f"{dot_sym} ", fmt0)
            elif last_char and (last_char.isalnum() or last_char in ')]}'):
                cursor.insertText(f" {dot_sym} ", fmt0)
            else:
                cursor.insertText(dot_sym, fmt0)
            return _done(True)

        elif ch == '^':
            if text_before.endswith(' '):
                cursor.deletePreviousChar()
            if cursor.hasSelection():
                sel = cursor.selectedText()
                cursor.insertText(f"{sel}ᵇ", fmt0)
                pos_after = cursor.position()
                cursor.setPosition(pos_after - 1)
                cursor.setPosition(pos_after, QTextCursor.MoveMode.KeepAnchor)
                return _done(True)
            else:
                cursor.insertText("^", fmt0)
                return _done(True)

        elif ch == '_':
            if text_before.endswith(' '):
                cursor.deletePreviousChar()
            if cursor.hasSelection():
                sel = cursor.selectedText()
                cursor.insertText(f"{sel}₁", fmt0)
                pos_after = cursor.position()
                cursor.setPosition(pos_after - 1)
                cursor.setPosition(pos_after, QTextCursor.MoveMode.KeepAnchor)
                return _done(True)
            else:
                cursor.insertText("_", fmt0)
                return _done(True)

        elif ch == ',':
            from cas_engine.formatter import MathFormatter
            # In decimal comma mode or after a digit, do NOT insert a space!
            if getattr(MathFormatter, 'decimal_separator', ',') == ',' or (last_char and last_char.isdigit()):
                if text_before.endswith(' '):
                    cursor.deletePreviousChar()
                cursor.insertText(",", fmt0)
                return _done(True)
            if text_before.endswith(' '):
                cursor.deletePreviousChar()
            cursor.insertText(", ", fmt0)
            return _done(True)

        elif ch == ':':
            if text_before.endswith(':'):
                # Double colon '::' for type assertions - keep together
                cursor.insertText(":", fmt0)
            elif text_before.endswith(' '):
                # Ensure only a single space precedes ':'
                while cursor.position() > 0 and super().toPlainText()[:cursor.position()].endswith('  '):
                    cursor.deletePreviousChar()
                cursor.insertText(":", fmt0)
            elif last_char and last_char not in ('\n', '\t'):
                cursor.insertText(" :", fmt0)
            else:
                cursor.insertText(":", fmt0)
            return _done(True)

        return False

    def _insert_result_tokens(self, result_str: str, fmt_res: QTextCharFormat):
        """
        Inserts an evaluation result into the cell. Radicals (sqrt, nth-root, unicode √)
        are inserted as authentic 2D RadicalWidget instances with result styling (math blue, read-only).
        Matrices (Matrix([...])) are inserted as MatrixWidget instances.
        Fractions are inserted as FractionWidget instances with result styling.
        Other text is inserted with fmt_res.
        """
        if not result_str:
            return

        tokens = parse_math_tokens(result_str)
        for tok in tokens:
            tok_type = tok[0]
            if tok_type == 'fraction':
                num, den = tok[1], tok[2]
                is_exp = tok[3] if len(tok) > 3 else False
                self.insert_fraction_widget(num=num, den=den, focus_target=None, is_exponent=is_exp, is_result=True)
            elif tok_type == 'radical':
                radicand, degree = tok[1], tok[2]
                self.insert_radical_widget(radicand=radicand, degree=degree, focus_target=None, is_result=True)
            elif tok_type == 'matrix':
                self.insert_matrix_widget(data=tok[1], focus_target=None, is_result=True)
            else:
                cur = self.textCursor()
                cur.insertText(tok[1], fmt_res)
                self.setTextCursor(cur)

    def _handle_inline_evaluation(self, target_block=None) -> bool:
        """
        Evaluate expression inline and append/update '= result' (e.g. '1+2' -> '1+2 = 3').
        """
        if target_block is not None:
            cursor = QTextCursor(target_block)
            cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock)
        else:
            cursor = self.textCursor()

        if self.get_mode_at_cursor() in (
            getattr(self.parent_cell, 'MODE_TEXT', 'text'),
            getattr(self.parent_cell, 'MODE_NONEXEC_MATH', 'nonexec_math')
        ):
            return False

        # Check if text is selected
        selected_text = self._get_selected_math_text(cursor) if (target_block is None and cursor.hasSelection()) else ""
        if selected_text:
            eq_pos = self._find_top_level_equal(selected_text)
            if eq_pos != -1:
                expr_str = selected_text[:eq_pos].strip()
            else:
                expr_str = selected_text
            is_selection = True
        else:
            is_selection = False
            block = target_block if target_block is not None else cursor.block()
            block_parts = []
            it = block.begin()
            prev_level = 0
            while not it.atEnd():
                frag = it.fragment()
                if frag.isValid():
                    fmt = frag.charFormat()
                    if fmt.isImageFormat():
                        fid = fmt.property(PROP_FRAC_ID)
                        if fid and hasattr(self, 'frac_widgets') and fid in self.frac_widgets:
                            block_parts.append(self.frac_widgets[fid].text_expression())
                        else:
                            expr = fmt.property(PROP_MATH_EXPR)
                            block_parts.append(str(expr) if expr else frag.text())
                        prev_level = 0
                    else:
                        level = fmt.property(PROP_SUBSCRIPT_LEVEL) or 0
                        text = frag.text()
                        if level > 0 and level > prev_level:
                            for _ in range(level - prev_level):
                                block_parts.append("_")
                        block_parts.append(text)
                        prev_level = level
                it += 1
            line_text = "".join(block_parts).strip()
            if not line_text:
                return False
            eq_pos = self._find_top_level_equal(line_text)
            if eq_pos != -1:
                expr_str = line_text[:eq_pos].strip()
            else:
                expr_str = line_text

        if not expr_str:
            return False

        if "= [Plot Object]" in expr_str:
            expr_str = expr_str.replace("= [Plot Object]", "").strip()

        engine = self._get_engine()
        if not engine:
            return False

        try:
            res = engine.evaluate(expr_str)
            if self.parent_cell:
                self.parent_cell.clear_error()

            # If result is a Plot, render directly and never display '= [Plot Object]' text
            if getattr(res, 'is_plot', False) or isinstance(getattr(res, 'raw_result', None), PlotData):
                full_raw = self.toPlainText()
                if "= [Plot Object]" in full_raw or full_raw.rstrip().endswith('='):
                    cleaned_txt = full_raw.replace("= [Plot Object]", "").rstrip()
                    if cleaned_txt.endswith('='):
                        cleaned_txt = cleaned_txt[:-1].rstrip()
                    self.setPlainText(cleaned_txt)
                    cur = self.textCursor()
                    cur.movePosition(QTextCursor.MoveOperation.End)
                    self.setTextCursor(cur)
                if self.parent_cell:
                    if hasattr(self.parent_cell, 'preview_row'):
                        self.parent_cell.preview_row.setVisible(False)
                    self.parent_cell.set_result(res)
                return True

            # Format the evaluated result nicely
            result_str = ""
            if res.exact_text:
                result_str = res.exact_text.strip()
            elif res.numeric_text:
                result_str = res.numeric_text.strip()
            elif hasattr(res, 'raw_result'):
                result_str = str(res.raw_result).strip()

            # Flatten multiline ASCII matrices / fractions / results to clean inline representation
            if '\n' in result_str:
                if hasattr(res, 'raw_result'):
                    import sympy as sp
                    try:
                        result_str = sp.sstr(res.raw_result)
                    except Exception:
                        pass
                result_str = re.sub(r'\s*\n\s*', ' ', result_str)

            if not result_str:
                return False

            # Automatically infer and append units if applicable (e.g. voltage_divider -> V)
            from cas_engine.units import infer_unit_from_expression
            inferred_unit = infer_unit_from_expression(expr_str)
            if inferred_unit and result_str:
                if not re.search(r'\b' + re.escape(inferred_unit) + r'\b', result_str):
                    if re.match(r'^[+-]?\d+(?:[.,]\d+)?(?:[eE][+-]?\d+)?$', result_str.strip()):
                        result_str = f"{result_str} {inferred_unit}"

            # Check if the result is a radical (square root or nth root)
            is_rad = False
            rad_val = ""
            deg_val = None
            rad_coeff_str = ""
            rad_approx_str = ""
            if hasattr(res, 'raw_result') and res.raw_result is not None:
                try:
                    import sympy as sp
                    from cas_engine.formatter import MathFormatter
                    coeff, root_part = res.raw_result.as_coeff_Mul() if hasattr(res.raw_result, 'as_coeff_Mul') else (1, res.raw_result)
                    if (hasattr(root_part, 'is_Pow') and root_part.is_Pow and
                        isinstance(root_part.exp, sp.Rational) and root_part.exp.numerator == 1 and root_part.exp.denominator > 1):
                        coeff_den = getattr(coeff, 'denominator', getattr(coeff, 'q', 1))
                        if coeff_den == 1:
                            is_rad = True
                            rad_val = sp.sstr(root_part.base)
                            deg_val = None if root_part.exp.denominator == 2 else sp.sstr(root_part.exp.denominator)
                            if coeff == -1:
                                rad_coeff_str = "-"
                            elif coeff != 1:
                                rad_coeff_str = f"{sp.sstr(coeff)} · "
                            else:
                                rad_coeff_str = ""

                        # Calculate full precision decimal approximation if no free symbols
                        if not getattr(res.raw_result, 'free_symbols', None):
                            try:
                                approx_num = sp.sstr(res.raw_result.evalf())
                                approx_dec = MathFormatter.format_decimal(approx_num)
                                rad_approx_str = f" ≈ {approx_dec}"
                            except Exception:
                                rad_approx_str = ""
                except Exception:
                    pass

            # Check if the result is a fraction
            is_frac = False
            num_val, den_val = "", ""
            if not is_rad and hasattr(res, 'raw_result') and res.raw_result is not None:
                try:
                    import sympy as sp
                    if isinstance(res.raw_result, (sp.Rational, sp.Expr)):
                        has_tuple = any(isinstance(a, (tuple, list, sp.Tuple)) for a in getattr(res.raw_result, 'args', ()))
                        if not has_tuple:
                            n, d = sp.fraction(res.raw_result)
                            if d != 1 and d != -1:
                                is_frac = True
                                num_val = sp.sstr(n)
                                den_val = sp.sstr(d)
                except Exception:
                    pass
            if not is_rad and not is_frac:
                m = re.match(r'^([+-]?[0-9a-zA-Z_.]+)\s*/\s*([0-9a-zA-Z_.]+)$', result_str.strip())
                if m:
                    is_frac = True
                    num_val = m.group(1)
                    den_val = m.group(2)

            # Check if the result is a Matrix or 2D vector
            is_mat = False
            mat_data = []
            if not is_rad and not is_frac and hasattr(res, 'raw_result') and res.raw_result is not None:
                try:
                    import sympy as sp
                    if isinstance(res.raw_result, sp.MatrixBase):
                        is_mat = True
                        for r in range(res.raw_result.rows):
                            row_items = []
                            for c in range(res.raw_result.cols):
                                row_items.append(sp.sstr(res.raw_result[r, c]))
                            mat_data.append(row_items)
                except Exception:
                    pass

            is_2d_math = (self.get_mode_at_cursor() == getattr(self.parent_cell, 'MODE_2D_MATH', '2d_math'))
            if is_2d_math:
                if is_rad:
                    rad_val = self.clean_operator_spacing(rad_val)
                    if rad_coeff_str:
                        rad_coeff_str = self.clean_operator_spacing(rad_coeff_str)
                elif is_frac:
                    num_val = self.clean_operator_spacing(num_val)
                    den_val = self.clean_operator_spacing(den_val)
                elif is_mat:
                    for r in range(len(mat_data)):
                        for c in range(len(mat_data[r])):
                            mat_data[r][c] = self.clean_operator_spacing(mat_data[r][c])
                else:
                    result_str = self.clean_operator_spacing(result_str)
            else:
                if is_rad:
                    rad_term = f"root({rad_val}, {deg_val})" if deg_val else f"sqrt({rad_val})"
                    result_str = f"{rad_coeff_str}{rad_term}{rad_approx_str}"

            from .theme import Theme
            ws_theme = getattr(self, 'theme_mode', 'light')
            output_blue = Theme.OPENMATH_MATH_BLUE if ws_theme != 'dark' else Theme.DARK_MATH_BLUE

            if is_selection:
                orig = cursor.selectedText()
                fmt = cursor.charFormat()
                fmt_eq = QTextCharFormat(fmt)
                fmt_eq.setForeground(QColor("#000000"))
                fmt_res = QTextCharFormat(fmt)
                fmt_res.setForeground(QColor(output_blue))

                if ':=' in orig:
                    assign_lhs = orig.split(':=', 1)[0].strip()
                    prefix = f"{assign_lhs} := "
                else:
                    eq_pos = self._find_top_level_equal(orig)
                    if eq_pos != -1:
                        lhs_part = self.clean_operator_spacing(orig[:eq_pos].rstrip())
                        prefix = f"{lhs_part} = "
                    else:
                        lhs_part = self.clean_operator_spacing(orig.rstrip())
                if re.search(r'\b[a-zA-Z][a-zA-Z0-9]*(?:_[a-zA-Z0-9_]+)+\b', prefix):
                    self.insert_stepped_math_text(prefix, cursor)
                else:
                    cursor.insertText(prefix, fmt_eq)
                self.setTextCursor(cursor)
                if is_rad and is_2d_math:
                    if rad_coeff_str:
                        cur = self.textCursor()
                        cur.insertText(rad_coeff_str, fmt_res)
                        self.setTextCursor(cur)
                    self.insert_radical_widget(radicand=rad_val, degree=deg_val, focus_target=None, is_result=True)
                    if rad_approx_str:
                        cur = self.textCursor()
                        cur.insertText(rad_approx_str, fmt_res)
                        self.setTextCursor(cur)
                elif is_frac and is_2d_math:
                    self.insert_fraction_widget(num=num_val, den=den_val, focus_target=None, is_result=True)
                elif is_mat and is_2d_math:
                    self.insert_matrix_widget(data=mat_data, focus_target=None, is_result=True)
                else:
                    if is_2d_math:
                        self._insert_result_tokens(result_str, fmt_res)
                    else:
                        cur = self.textCursor()
                        cur.insertText(result_str, fmt_res)
                        self.setTextCursor(cur)
            else:
                block = target_block if target_block is not None else cursor.block()
                block_raw_text = block.text()
                eq_idx = self._find_top_level_equal(block_raw_text)

                cursor.beginEditBlock()
                if eq_idx != -1:
                    start_cut = eq_idx
                    while start_cut > 0 and block_raw_text[start_cut - 1] in (' ', '\t'):
                        start_cut -= 1
                    cursor.setPosition(block.position() + start_cut)
                    cursor.setPosition(block.position() + len(block_raw_text), QTextCursor.MoveMode.KeepAnchor)
                    cursor.removeSelectedText()
                else:
                    cursor.setPosition(block.position() + len(block_raw_text))

                fmt = self._get_char_format_for_mode(self.get_mode_at_cursor())
                fmt_eq = QTextCharFormat(fmt)
                fmt_eq.setForeground(QColor("#000000"))
                cursor.insertText(" = ", fmt_eq)
                self.setTextCursor(cursor)
                cursor.endEditBlock()

                fmt_res = QTextCharFormat(fmt)
                fmt_res.setForeground(QColor(output_blue))

                if is_rad and is_2d_math:
                    if rad_coeff_str:
                        cur = self.textCursor()
                        cur.insertText(rad_coeff_str, fmt_res)
                        self.setTextCursor(cur)
                    self.insert_radical_widget(radicand=rad_val, degree=deg_val, focus_target=None, is_result=True)
                    if rad_approx_str:
                        cur = self.textCursor()
                        cur.insertText(rad_approx_str, fmt_res)
                        self.setTextCursor(cur)
                elif is_frac and is_2d_math:
                    self.insert_fraction_widget(num=num_val, den=den_val, focus_target=None, is_result=True)
                elif is_mat and is_2d_math:
                    self.insert_matrix_widget(data=mat_data, focus_target=None, is_result=True)
                else:
                    if is_2d_math:
                        self._insert_result_tokens(result_str, fmt_res)
                    else:
                        cur = self.textCursor()
                        cur.insertText(result_str, fmt_res)
                        self.setTextCursor(cur)

            self._just_evaluated_inline = True
            if self.parent_cell:
                self.parent_cell._last_inline_text = None
                self.parent_cell._last_inline_result_latex = None
                if hasattr(self.parent_cell, 'preview_row') and self.parent_cell.preview_row:
                    self.parent_cell.preview_row.setVisible(False)
                if hasattr(self.parent_cell, 'output_row') and self.parent_cell.output_row:
                    self.parent_cell.output_row.setVisible(False)
            self._reposition_fractions()
            self._adjust_height()
            return True

        except Exception as err:
            if self.parent_cell:
                self.parent_cell.set_error("Inline Evaluation", str(err), input_expr=expr_str)
            return True

    def keyPressEvent(self, event: QKeyEvent):
        if self.isReadOnly():
            if event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier):
                if event.key() in (Qt.Key.Key_Plus, Qt.Key.Key_Equal, Qt.Key.Key_Minus, Qt.Key.Key_Underscore, Qt.Key.Key_0):
                    ws = self._get_worksheet_view()
                    if ws:
                        if event.key() in (Qt.Key.Key_Plus, Qt.Key.Key_Equal):
                            ws.zoom_in()
                        elif event.key() in (Qt.Key.Key_Minus, Qt.Key.Key_Underscore):
                            ws.zoom_out()
                        elif event.key() == Qt.Key.Key_0:
                            ws.zoom_reset()
                        event.accept()
                        return
            if event.matches(QKeySequence.StandardKey.Copy) or \
               event.matches(QKeySequence.StandardKey.SelectAll) or \
               event.key() in (Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Up, Qt.Key.Key_Down,
                               Qt.Key.Key_Home, Qt.Key.Key_End, Qt.Key.Key_PageUp, Qt.Key.Key_PageDown):
                super().keyPressEvent(event)
                return
            if event.text():
                ws = self._get_worksheet_view()
                if ws and hasattr(ws, 'statusMessage'):
                    ws.statusMessage.emit("Document is in View Mode. Click 'Enable Editing' to make changes.", 2500)
            event.accept()
            return

        ws = self._get_worksheet_view()
        has_multi_cells = bool(ws and getattr(ws, 'selected_cells', None) and len(ws.selected_cells) > 1 and self.parent_cell in ws.selected_cells)

        # Delete / Backspace across multiple statements
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace) and has_multi_cells:
            ws.delete_selected_cells()
            event.accept()
            return

        # Copy across multiple statements
        if ((event.key() == Qt.Key.Key_C and (event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier))) or event.matches(QKeySequence.StandardKey.Copy)) and has_multi_cells:
            ws.copy_selected_cells()
            event.accept()
            return

        # Cut across multiple statements
        if ((event.key() == Qt.Key.Key_X and (event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier))) or event.matches(QKeySequence.StandardKey.Cut)) and has_multi_cells:
            ws.cut_selected_cells()
            event.accept()
            return

        # Paste across multiple statements or rich cells
        if (event.key() == Qt.Key.Key_V and (event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier))) or event.matches(QKeySequence.StandardKey.Paste):
            if ws:
                clipboard = QApplication.clipboard()
                md = clipboard.mimeData() if clipboard else None
                if md and (md.hasFormat("application/x-openmath-cells") or has_multi_cells):
                    if ws.paste_cells():
                        event.accept()
                        return

        # Select All (Ctrl+A / Cmd+A)
        if (event.key() == Qt.Key.Key_A and (event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier))) or event.matches(QKeySequence.StandardKey.SelectAll):
            cursor = self.textCursor()
            doc_len = len(self.toPlainText())
            is_fully_selected = cursor.hasSelection() and abs(cursor.selectionEnd() - cursor.selectionStart()) >= doc_len
            if is_fully_selected or doc_len == 0 or has_multi_cells:
                if ws and len(ws.cells) > 1:
                    ws.select_all_cells()
                    event.accept()
                    return

        # Completer popup handling
        if self.completer.popup().isVisible():
            if event.key() in (Qt.Key.Key_Enter, Qt.Key.Key_Return, Qt.Key.Key_Tab):
                completion = self.completer.currentCompletion()
                if not completion and self.completer.popup().currentIndex().isValid():
                    completion = self.completer.popup().currentIndex().data()
                if not completion:
                    matching = [c for c in MATH_COMPLETIONS if c.lower().startswith(self.completer.completionPrefix().lower())]
                    if matching:
                        completion = matching[0]
                if completion:
                    self._insert_completion(completion)
                self.completer.popup().hide()
                event.accept()
                return
            elif event.key() in (Qt.Key.Key_Escape, Qt.Key.Key_Backtab):
                self.completer.popup().hide()
                event.accept()
                return

        # F5: Toggle Math / Text mode
        if event.key() == Qt.Key.Key_F5:
            self.modeToggleRequested.emit()
            event.accept()
            return

        # Esc or Ctrl+Space / Cmd+Space: Trigger Command Completion
        if (event.key() == Qt.Key.Key_Space and (event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier))) or event.key() == Qt.Key.Key_Escape:
            word = self._under_cursor_word()
            if word:
                self.completer.setCompletionPrefix(word)
                cr = self.cursorRect()
                cr.setWidth(self.completer.popup().sizeHintForColumn(0) + self.completer.popup().verticalScrollBar().sizeHint().width())
                self.completer.complete(cr)
            event.accept()

        # Slash '/' in 2D Math mode inserts an inline FractionWidget
        if event.text() == '/' and not (event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier | Qt.KeyboardModifier.AltModifier)):
            if self.get_mode_at_cursor() == getattr(self.parent_cell, 'MODE_2D_MATH', '2d_math'):
                cursor = self.textCursor()
                if cursor.hasSelection():
                    sel = self._get_selected_math_text(cursor)
                    cursor.removeSelectedText()
                    self.setTextCursor(cursor)
                    is_exp = getattr(self, '_superscript_active', False) or any(c in SUPER_MAP.values() for c in (sel or ''))
                    if is_exp and sel:
                        sel = "".join(INV_SUPER_MAP.get(c, c) for c in sel)
                    self.insert_fraction_widget(num=sel if sel else "a", den="b", focus_target="den", is_exponent=is_exp)
                    self._superscript_active = False
                    event.accept()
                    return
                else:
                    pos = cursor.position()
                    line_text_before = cursor.block().text()[:pos - cursor.block().position()]
                    if line_text_before.endswith('\ufffc'):
                        cur_prev = QTextCursor(cursor)
                        cur_prev.setPosition(pos - 1)
                        cur_prev.setPosition(pos, QTextCursor.MoveMode.KeepAnchor)
                        pre_text = self._get_selected_math_text(cur_prev)
                        if pre_text:
                            cur_prev.removeSelectedText()
                            self.setTextCursor(cur_prev)
                            self.insert_fraction_widget(num=pre_text, den="b", focus_target="den")
                            event.accept()
                            return
                    to_del, num, is_exp = _extract_preceding_numerator_token(line_text_before)
                    if to_del:
                        for _ in range(len(to_del)):
                            cursor.deletePreviousChar()
                        self.setTextCursor(cursor)
                        target = "num" if to_del == "^" else "den"
                        self.insert_fraction_widget(num=num, den="b", focus_target=target, is_exponent=is_exp)
                    else:
                        is_exp = getattr(self, '_superscript_active', False)
                        self.insert_fraction_widget(num="a", den="b", focus_target="num", is_exponent=is_exp)
                    self._superscript_active = False
                    event.accept()
                    return

        # Typing '(' or ')' with selection wraps selection in parentheses
        if event.text() in ('(', ')') and not (event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier | Qt.KeyboardModifier.AltModifier)):
            cursor = self.textCursor()
            if cursor.hasSelection():
                start = cursor.selectionStart()
                end = cursor.selectionEnd()
                cursor.beginEditBlock()
                cursor.setPosition(end)
                cursor.insertText(")")
                cursor.setPosition(start)
                cursor.insertText("(")
                cursor.setPosition(start + 1)
                cursor.setPosition(end + 1, QTextCursor.MoveMode.KeepAnchor)
                cursor.endEditBlock()
                self.setTextCursor(cursor)
                self._update_tall_parentheses()
                self._adjust_height()
                self._reposition_fractions()
                self.viewport().update()
                event.accept()
                return

        # Operator auto-spacing (+, -, =, :=, etc.)
        if self._handle_operator_spacing(event):
            event.accept()
            return

        # Paste shortcut Ctrl+V / Cmd+V with full image / document support
        if (event.key() == Qt.Key.Key_V and (event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier))):
            clipboard = QApplication.clipboard()
            md = clipboard.mimeData()
            if md:
                self.insertFromMimeData(md)
                event.accept()
                return

        # Zoom shortcuts: Ctrl/Cmd + Plus/Equal, Ctrl/Cmd + Minus, Ctrl/Cmd + 0
        if event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier):
            if event.key() in (Qt.Key.Key_Plus, Qt.Key.Key_Equal):
                ws = self._get_worksheet_view()
                if ws:
                    ws.zoom_in()
                    event.accept()
                    return
            elif event.key() in (Qt.Key.Key_Minus, Qt.Key.Key_Underscore):
                ws = self._get_worksheet_view()
                if ws:
                    ws.zoom_out()
                    event.accept()
                    return
            elif event.key() == Qt.Key.Key_0:
                ws = self._get_worksheet_view()
                if ws:
                    ws.zoom_reset()
                    event.accept()
                    return

        # Shift+Enter, Alt+Enter, Alt+=, or Shift+= (unless typing '+'): Inline Evaluation (e.g. "1+2" -> "1+2 = 3")
        is_inline_eval_trigger = (
            (event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and (event.modifiers() & (Qt.KeyboardModifier.ShiftModifier | Qt.KeyboardModifier.AltModifier))) or
            (event.key() == Qt.Key.Key_Equal and (event.modifiers() & Qt.KeyboardModifier.AltModifier)) or
            (event.key() == Qt.Key.Key_Equal and (event.modifiers() & Qt.KeyboardModifier.ShiftModifier) and event.text() != '+')
        )
        if is_inline_eval_trigger:
            if hasattr(self, 'embedded_images') and self.embedded_images:
                res = self._create_or_focus_math_cell_below()
                if res:
                    event.accept()
                    return
            if self.get_mode_at_cursor() in (
                getattr(self.parent_cell, 'MODE_TEXT', 'text'),
                getattr(self.parent_cell, 'MODE_NONEXEC_MATH', 'nonexec_math')
            ):
                super().keyPressEvent(event)
                return
            if self._handle_inline_evaluation():
                event.accept()
                return
            super().keyPressEvent(event)
            return

        # Ctrl+Enter / Cmd+Enter: Execute cell (block execution)
        if (event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)) and (event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier)):
            self.executeRequested.emit()
            event.accept()
            return

        # Plain Enter / Return:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._just_evaluated_inline = False
            cursor = self.textCursor()
            mode = self.get_mode_at_cursor()
            parent_mode = getattr(self.parent_cell, 'input_mode', None) if self.parent_cell else None
            is_nonexec_math = (
                mode in (getattr(self.parent_cell, 'MODE_NONEXEC_MATH', 'nonexec_math'), 'nonexec_math') or
                parent_mode in (getattr(self.parent_cell, 'MODE_NONEXEC_MATH', 'nonexec_math'), 'nonexec_math')
            )
            is_text_mode = (
                mode in (getattr(self.parent_cell, 'MODE_TEXT', 'text'), 'text') or
                parent_mode in (getattr(self.parent_cell, 'MODE_TEXT', 'text'), 'text')
            )

            # In Nonexecutable Math mode, ending a statement with ':' or ';' and pressing Enter
            # suppresses output and advances/creates a separate cell below (matching Math mode).
            if is_nonexec_math:
                line_text = cursor.block().text()
                pos_in_block = cursor.positionInBlock()
                text_before_cursor = line_text[:pos_in_block].rstrip()
                text_after_cursor = line_text[pos_in_block:].strip()
                cell_text = self.toPlainText().rstrip()

                ends_with_colon = (
                    (not text_after_cursor and (text_before_cursor.endswith(':') or text_before_cursor.endswith(';'))) or
                    cell_text.endswith(':') or cell_text.endswith(';')
                )

                if ends_with_colon:
                    if self.parent_cell:
                        if hasattr(self.parent_cell, 'output_row'):
                            self.parent_cell.output_row.setVisible(False)
                        if hasattr(self.parent_cell, 'plot_container'):
                            self.parent_cell.plot_container.setVisible(False)
                        if hasattr(self.parent_cell, 'lbl_error'):
                            self.parent_cell.lbl_error.setVisible(False)
                        if hasattr(self.parent_cell, 'preview_row'):
                            self.parent_cell.preview_row.setVisible(False)
                        if hasattr(self.parent_cell, '_preview_timer'):
                            self.parent_cell._preview_timer.stop()

                    ws = self._get_worksheet_view()
                    if ws and self.parent_cell:
                        ws._focus_next_cell(self.parent_cell.cell_id)
                    event.accept()
                    return

                # Non-colon terminated nonexecutable math: insert block in same cell
                cursor.beginEditBlock()
                if cursor.hasSelection():
                    cursor.removeSelectedText()
                cursor.insertBlock()
                cursor.endEditBlock()
                self.setTextCursor(cursor)
                self.ensureCursorVisible()
                event.accept()
                return

            if is_text_mode:
                if hasattr(self, 'embedded_images') and self.embedded_images:
                    res = self._create_or_focus_math_cell_below()
                    if res:
                        event.accept()
                        return
                cursor.beginEditBlock()
                if cursor.hasSelection():
                    cursor.removeSelectedText()
                cursor.insertBlock()
                cursor.endEditBlock()
                self.setTextCursor(cursor)
                self.ensureCursorVisible()
                event.accept()
                return

            # If the cell has an embedded image, pressing Enter creates/advances to a new math box below
            if hasattr(self, 'embedded_images') and self.embedded_images:
                res = self._create_or_focus_math_cell_below()
                if res:
                    event.accept()
                    return

            # Clean up '= [Plot Object]' if user presses Enter
            if "= [Plot Object]" in self.toPlainText():
                cleaned = self.toPlainText().replace("= [Plot Object]", "").strip()
                self.setPlainText(cleaned)
                cur = self.textCursor()
                cur.movePosition(QTextCursor.MoveOperation.End)
                self.setTextCursor(cur)

            cur_text = self.parent_cell.get_executable_text() if self.parent_cell else self.toPlainText().strip()
            cur_text_trimmed = cur_text.rstrip() if cur_text else ""
            
            # Plot commands or worksheet mode with text execute immediately upon Enter
            is_plot_cmd = any(cur_text.lstrip().startswith(cmd) for cmd in (
                'plot(', 'plot3d(', 'implicitplot(', 'LPplot(', 'polygonOmråde(', 'polygonOmraade('
            ))
            if is_plot_cmd or (cur_text and self.parent_cell and getattr(self.parent_cell, 'is_worksheet_mode', False)):
                self.executeRequested.emit()
                event.accept()
                return

            # If statement ends with colon (suppress output) or semicolon,
            # or is a variable assignment (':='), execute and assign immediately upon Enter
            if cur_text and (cur_text_trimmed.endswith(':') or cur_text_trimmed.endswith(';') or (':=' in cur_text and '\n' not in cur_text)):
                self.executeRequested.emit()
                event.accept()
                return

            if cur_text and (cur_text.endswith('=') or cur_text.rstrip().endswith('=')):
                if self._handle_inline_evaluation():
                    event.accept()
                    return

            cursor = self.textCursor()
            cursor.beginEditBlock()
            if cursor.hasSelection():
                cursor.removeSelectedText()
            cursor.insertBlock()
            cursor.endEditBlock()
            self.setTextCursor(cursor)
            self.ensureCursorVisible()
            event.accept()
            return

        # Shift+Tab (Backtab): Outdent cell out of subsection or section
        if event.key() == Qt.Key.Key_Backtab or (event.key() == Qt.Key.Key_Tab and (event.modifiers() & Qt.KeyboardModifier.ShiftModifier)):
            ws = self._get_worksheet_view()
            if ws and hasattr(ws, 'outdent_active_cell'):
                ws.outdent_active_cell()
                event.accept()
                return

        # Backspace on an empty cell inside a section outdents it outside the section,
        # unless it is the only cell in that section (section must keep at least one empty line).
        if event.key() == Qt.Key.Key_Backspace and not (event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier)):
            if not self.toPlainText() and not getattr(self, 'frac_widgets', None):
                ws = self._get_worksheet_view()
                if ws and getattr(self.parent_cell, 'is_inside_section', False):
                    if hasattr(ws, 'is_only_content_in_section') and ws.is_only_content_in_section(self.parent_cell):
                        event.accept()
                        return
                    ws.outdent_active_cell()
                    event.accept()
                    return

        # Tab: Autocomplete or Navigate Placeholders or Indent
        if event.key() == Qt.Key.Key_Tab:
            if self._select_next_placeholder():
                event.accept()
                return
            else:
                word = self._under_cursor_word()
                if word:
                    matching = [c for c in MATH_COMPLETIONS if c.lower().startswith(word.lower())]
                    if len(matching) == 1:
                        self._insert_completion(matching[0])
                        event.accept()
                        return
                    elif len(matching) > 1:
                        self.completer.setCompletionPrefix(word)
                        cr = self.cursorRect()
                        cr.setWidth(160)
                        self.completer.complete(cr)
                        event.accept()
                        return
                # Indent / standard tab
                self.insertPlainText("  ")
                event.accept()
                return

        # Arrow navigation into embedded fraction/integral widgets
        if event.key() in (Qt.Key.Key_Right, Qt.Key.Key_Left, Qt.Key.Key_Down, Qt.Key.Key_Up) and not (event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier)):
            cursor = self.textCursor()
            if not cursor.hasSelection():
                pos = cursor.position()
                doc = self.document()

                def _get_frac_at(p):
                    if not hasattr(self, 'frac_widgets') or not self.frac_widgets:
                        return None
                    if 0 <= p < doc.characterCount() - 1:
                        c = QTextCursor(doc)
                        c.setPosition(p)
                        c.setPosition(p + 1, QTextCursor.MoveMode.KeepAnchor)
                        fmt = c.charFormat()
                        if fmt.isImageFormat():
                            fid = fmt.property(PROP_FRAC_ID)
                            if fid and fid in self.frac_widgets:
                                return self.frac_widgets[fid]
                    return None

                frac_right = _get_frac_at(pos)
                frac_left = _get_frac_at(pos - 1)

                if event.key() == Qt.Key.Key_Right and frac_right is not None:
                    if isinstance(frac_right, FractionWidget):
                        target = frac_right.num_slot.first_edit()
                        target.setFocus()
                        target.setCursorPosition(0)
                        if target.text().strip() in ("a", "b"):
                            target.selectAll()
                        top = frac_right.get_top_fraction()
                        if top:
                            top.update()
                        self.viewport().update()
                        event.accept()
                        return
                    elif isinstance(frac_right, DefiniteIntegralWidget):
                        target = frac_right.a_edit
                        target.setFocus()
                        target.setCursorPosition(0)
                        if target.text().strip() in ("a", "b", "f", "x"):
                            target.selectAll()
                        frac_right.update()
                        self.viewport().update()
                        event.accept()
                        return
                    elif isinstance(frac_right, BigOperatorWidget):
                        target = frac_right.bot_edit
                        target.setFocus()
                        target.setCursorPosition(0)
                        if target.text().strip() in ("n", "k = 1", "k=1", "f", "a", "b"):
                            target.selectAll()
                        frac_right.update()
                        self.viewport().update()
                        event.accept()
                        return

                elif event.key() == Qt.Key.Key_Left and frac_left is not None:
                    if isinstance(frac_left, FractionWidget):
                        target = frac_left.num_slot.last_edit()
                        target.setFocus()
                        target.setCursorPosition(len(target.text()))
                        if target.text().strip() in ("a", "b"):
                            target.selectAll()
                        top = frac_left.get_top_fraction()
                        if top:
                            top.update()
                        self.viewport().update()
                        event.accept()
                        return
                    elif isinstance(frac_left, DefiniteIntegralWidget):
                        target = frac_left.x_edit if frac_left.show_differential else frac_left.f_edit
                        target.setFocus()
                        target.setCursorPosition(len(target.text()))
                        if target.text().strip() in ("a", "b", "f", "x"):
                            target.selectAll()
                        frac_left.update()
                        self.viewport().update()
                        event.accept()
                        return
                    elif isinstance(frac_left, BigOperatorWidget):
                        target = frac_left.body_edit
                        target.setFocus()
                        target.setCursorPosition(len(target.text()))
                        if target.text().strip() in ("n", "k = 1", "k=1", "f", "a", "b"):
                            target.selectAll()
                        frac_left.update()
                        self.viewport().update()
                        event.accept()
                        return

                elif event.key() == Qt.Key.Key_Down:
                    target_frac = frac_right or frac_left
                    if target_frac is not None:
                        if isinstance(target_frac, FractionWidget):
                            target = target_frac.den_slot.first_edit()
                            target.setFocus()
                            target.setCursorPosition(0 if target_frac == frac_right else len(target.text()))
                            if target.text().strip() in ("a", "b"):
                                target.selectAll()
                            top = target_frac.get_top_fraction()
                            if top:
                                top.update()
                            self.viewport().update()
                            event.accept()
                            return
                        elif isinstance(target_frac, DefiniteIntegralWidget):
                            target = target_frac.a_edit
                            target.setFocus()
                            target.setCursorPosition(0 if target_frac == frac_right else len(target.text()))
                            target_frac.update()
                            self.viewport().update()
                            event.accept()
                            return
                        elif isinstance(target_frac, BigOperatorWidget):
                            target = target_frac.bot_edit
                            target.setFocus()
                            target.setCursorPosition(0 if target_frac == frac_right else len(target.text()))
                            target_frac.update()
                            self.viewport().update()
                            event.accept()
                            return

                elif event.key() == Qt.Key.Key_Up:
                    target_frac = frac_right or frac_left
                    if target_frac is not None:
                        if isinstance(target_frac, FractionWidget):
                            target = target_frac.num_slot.first_edit()
                            target.setFocus()
                            target.setCursorPosition(0 if target_frac == frac_right else len(target.text()))
                            if target.text().strip() in ("a", "b"):
                                target.selectAll()
                            top = target_frac.get_top_fraction()
                            if top:
                                top.update()
                            self.viewport().update()
                            event.accept()
                            return
                        elif isinstance(target_frac, DefiniteIntegralWidget):
                            target = target_frac.b_edit
                            target.setFocus()
                            target.setCursorPosition(0 if target_frac == frac_right else len(target.text()))
                            target_frac.update()
                            self.viewport().update()
                            event.accept()
                            return
                        elif isinstance(target_frac, BigOperatorWidget):
                            target = target_frac.top_edit
                            target.setFocus()
                            target.setCursorPosition(0 if target_frac == frac_right else len(target.text()))
                            target_frac.update()
                            self.viewport().update()
                            event.accept()
                            return

        # Arrow navigation between cells
        if event.key() == Qt.Key.Key_Up:
            cursor = self.textCursor()
            if cursor.blockNumber() == 0:
                self.navigateUp.emit()
                event.accept()
                return
        elif event.key() == Qt.Key.Key_Down:
            cursor = self.textCursor()
            if cursor.blockNumber() == self.document().blockCount() - 1:
                self.navigateDown.emit()
                event.accept()
                return

        # Right arrow exits subscript/superscript mode to baseline
        if event.key() == Qt.Key.Key_Right:
            if getattr(self, '_subscript_active', False) or getattr(self, '_superscript_active', False) or (self.currentCharFormat().property(PROP_SUBSCRIPT_LEVEL) or 0) > 0:
                self._subscript_active = False
                self._superscript_active = False
                self.setCurrentCharFormat(self._get_subscript_format(0))
                cursor = self.textCursor()
                if cursor.atEnd():
                    event.accept()
                    return

        # Multi-cell keyboard range selection with Shift+Down / Shift+Up
        if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            ws = self._get_worksheet_view()
            if ws and len(ws.cells) > 1:
                cursor = self.textCursor()
                if event.key() == Qt.Key.Key_Down:
                    is_at_bottom = (cursor.block() == self.document().lastBlock())
                    has_multi = len(getattr(ws, 'selected_cells', [])) > 1
                    if is_at_bottom or has_multi:
                        curr_c = ws.selected_cells[-1] if has_multi else self.parent_cell
                        if curr_c in ws.cells:
                            idx = ws.cells.index(curr_c)
                            if idx + 1 < len(ws.cells):
                                next_c = ws.cells[idx + 1]
                                if not has_multi:
                                    ws.select_range(self.parent_cell, next_c)
                                else:
                                    first_c = ws.selected_cells[0]
                                    ws.select_range(first_c, next_c)
                                event.accept()
                                return
                elif event.key() == Qt.Key.Key_Up:
                    is_at_top = (cursor.block() == self.document().firstBlock())
                    has_multi = len(getattr(ws, 'selected_cells', [])) > 1
                    if is_at_top or has_multi:
                        curr_c = ws.selected_cells[0] if has_multi else self.parent_cell
                        if curr_c in ws.cells:
                            idx = ws.cells.index(curr_c)
                            if idx > 0:
                                prev_c = ws.cells[idx - 1]
                                if not has_multi:
                                    ws.select_range(self.parent_cell, prev_c)
                                else:
                                    last_c = ws.selected_cells[-1]
                                    ws.select_range(last_c, prev_c)
                                event.accept()
                                return

        if event.key() in (Qt.Key.Key_Left, Qt.Key.Key_Up, Qt.Key.Key_Down, Qt.Key.Key_Home, Qt.Key.Key_End, Qt.Key.Key_PageUp, Qt.Key.Key_PageDown, Qt.Key.Key_Escape):
            self._subscript_active = False
            self._superscript_active = False

        super().keyPressEvent(event)

        # Auto-popup / filter completion when typing words >= 3 chars
        word = self._under_cursor_word()
        if len(word) >= 3:
            matching = [c for c in MATH_COMPLETIONS if c.lower().startswith(word.lower())]
            if matching:
                self.completer.setCompletionPrefix(word)
                cr = self.cursorRect()
                cr.setWidth(160)
                if not self.completer.popup().isVisible():
                    self.completer.complete(cr)
            else:
                if self.completer.popup().isVisible():
                    self.completer.popup().hide()
        else:
            if self.completer.popup().isVisible():
                self.completer.popup().hide()

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        theme_mode = getattr(self, 'theme_mode', 'light')
        Theme.apply_menu_style(menu, theme_mode)

        cursor = self.cursorForPosition(event.pos())
        doc_pos = cursor.position()
        block = cursor.block()
        block_text = block.text()
        pos_in_block = doc_pos - block.position()
        selected = self.textCursor().selectedText().strip()

        # -----------------------------------------------------------------
        # 1. Function Suggestions & Examples (at top of right-click menu)
        # -----------------------------------------------------------------
        from cas_engine.function_guide import find_function_in_text, get_categories_dict

        fn_name, fn_info, fn_span = "", None, (0, 0)
        if selected:
            fn_name, fn_info, fn_span = find_function_in_text(selected)
        if not fn_info:
            fn_name, fn_info, fn_span = find_function_in_text(block_text, pos_in_block)
        if not fn_info and block_text.strip():
            fn_name, fn_info, fn_span = find_function_in_text(block_text.strip())

        def _do_insert_example(code: str, span_range=None, b_pos=block.position()):
            if span_range and span_range[1] > span_range[0]:
                tc = QTextCursor(self.document())
                tc.setPosition(b_pos + span_range[0])
                tc.setPosition(b_pos + span_range[1], QTextCursor.MoveMode.KeepAnchor)
                tc.insertText(code)
                self.setTextCursor(tc)
            elif self.textCursor().hasSelection():
                self.textCursor().insertText(code)
            else:
                self.textCursor().insertText(code)
            self.setFocus()
            if self.parent_cell and hasattr(self.parent_cell, 'clear_error'):
                self.parent_cell.clear_error()

        # If an error is currently visible on the parent cell, offer quick fix
        if self.parent_cell and hasattr(self.parent_cell, 'error_box') and self.parent_cell.error_box.isVisible():
            err_sugg = getattr(self.parent_cell.error_box, '_current_suggestion', '')
            if err_sugg:
                act_fix = menu.addAction(f"💡 Fix Error:  {err_sugg}")
                act_fix.triggered.connect(lambda checked=False, s=err_sugg: self.parent_cell._on_suggestion_applied(s))
                menu.addSeparator()

        if fn_info:
            act_prim = menu.addAction(f"💡 Insert Example:  {fn_info.primary_example}")
            act_prim.triggered.connect(lambda checked=False, c=fn_info.primary_example, sp=fn_span: _do_insert_example(c, span_range=sp))

            if len(fn_info.examples) > 1:
                menu_ex = menu.addMenu(f"💡 Examples for '{fn_info.name}'")
                Theme.apply_menu_style(menu_ex, theme_mode)
                for ex in fn_info.examples:
                    act_ex = menu_ex.addAction(f"{ex.label}:  {ex.code}")
                    act_ex.triggered.connect(lambda checked=False, c=ex.code, sp=fn_span: _do_insert_example(c, span_range=sp))

            act_hint = menu.addAction(f"ℹ️  {fn_info.syntax} — {fn_info.description}")
            act_hint.setEnabled(False)
            menu.addSeparator()

        menu_catalog = menu.addMenu("💡 Math Function Examples")
        Theme.apply_menu_style(menu_catalog, theme_mode)
        cats = get_categories_dict()
        for cat_name, items in cats.items():
            cat_menu = menu_catalog.addMenu(cat_name)
            Theme.apply_menu_style(cat_menu, theme_mode)
            for itm in items:
                act_itm = cat_menu.addAction(f"{itm.name} — {itm.primary_example}")
                act_itm.triggered.connect(lambda checked=False, c=itm.primary_example: _do_insert_example(c, span_range=(0, 0)))
        menu.addSeparator()

        # Check if cursor or selection contains a decimal or expression
        num_str = ""
        replace_cursor = None

        if selected:
            clean = selected.replace(',', '.')
            try:
                flt = float(clean)
                num_str = selected
                replace_cursor = self.textCursor()
            except Exception:
                pass
        else:
            doc_pos = cursor.position()
            block = cursor.block()
            block_text = block.text()
            pos_in_block = doc_pos - block.position()
            for m in re.finditer(r'([+-]?\d+[\.,]\d+)', block_text):
                if m.start() <= pos_in_block <= m.end():
                    num_str = m.group(1)
                    replace_cursor = QTextCursor(self.document())
                    replace_cursor.setPosition(block.position() + m.start())
                    replace_cursor.setPosition(block.position() + m.end(), QTextCursor.MoveMode.KeepAnchor)
                    break

        if num_str and replace_cursor:
            clean = num_str.replace(',', '.')
            orig_n, orig_d = None, None
            if hasattr(self, '_frac_history'):
                if num_str in self._frac_history:
                    orig_n, orig_d = self._frac_history[num_str]
                elif clean in self._frac_history:
                    orig_n, orig_d = self._frac_history[clean]
            if not orig_n:
                rat = decimal_to_fraction(clean)
                if rat is not None:
                    import sympy as sp
                    n_sym, d_sym = sp.fraction(rat)
                    if d_sym != 1 and d_sym != -1:
                        orig_n, orig_d = str(n_sym), str(d_sym)

            if orig_n and orig_d:
                n, d = orig_n, orig_d
                act_frac = menu.addAction(f"Convert to Fraction ({n}/{d})")
                def _do_conv():
                    self.setTextCursor(replace_cursor)
                    replace_cursor.removeSelectedText()
                    self.insert_fraction_widget(num=str(n), den=str(d), focus_target=None)
                act_frac.triggered.connect(_do_conv)
                menu.addSeparator()

        # Unit conversion detection on right-click
        from cas_engine.units import (
            UNIT_LOOKUP, get_unit_conversions, infer_unit_from_expression
        )
        unit_target_val = None
        unit_target_unit = None
        unit_replace_cursor = None
        is_answer_part = False

        doc_pos = cursor.position()
        block = cursor.block()
        block_text = block.text()
        pos_in_block = doc_pos - block.position()
        eq_idx = self._find_top_level_equal(block_text)

        # Case A: Right-click is on the answer (on or after '=' sign)
        if eq_idx != -1 and pos_in_block >= eq_idx:
            lhs_text = block_text[:eq_idx].strip()
            rhs_text = block_text[eq_idx + 1:]
            m_ans = re.search(r'([+-]?\d+(?:[.,]\d+)?(?:[eE][+-]?\d+)?)\s*([a-zA-ZΩμµ]+)?', rhs_text)
            if m_ans:
                val_raw = m_ans.group(1).replace(',', '.')
                unit_candidate = m_ans.group(2)
                if not unit_candidate:
                    unit_candidate = infer_unit_from_expression(lhs_text)
                if unit_candidate and unit_candidate in UNIT_LOOKUP:
                    try:
                        unit_target_val = float(val_raw)
                        unit_target_unit = unit_candidate
                        start_pos = block.position() + eq_idx + 1 + m_ans.start()
                        end_pos = block.position() + eq_idx + 1 + m_ans.end()
                        unit_replace_cursor = QTextCursor(self.document())
                        unit_replace_cursor.setPosition(start_pos)
                        unit_replace_cursor.setPosition(end_pos, QTextCursor.MoveMode.KeepAnchor)
                        is_answer_part = True
                    except Exception:
                        pass

        # Case B: Right-click on a specific number-with-unit token anywhere in block (e.g. "10 kOhm")
        if unit_target_val is None:
            for m in re.finditer(r'\b([+-]?\d+(?:[.,]\d+)?(?:[eE][+-]?\d+)?)\s*([a-zA-ZΩμµ]+)\b', block_text):
                if m.start() <= pos_in_block <= m.end():
                    cand_unit = m.group(2)
                    if cand_unit in UNIT_LOOKUP:
                        try:
                            unit_target_val = float(m.group(1).replace(',', '.'))
                            unit_target_unit = cand_unit
                            unit_replace_cursor = QTextCursor(self.document())
                            unit_replace_cursor.setPosition(block.position() + m.start())
                            unit_replace_cursor.setPosition(block.position() + m.end(), QTextCursor.MoveMode.KeepAnchor)
                            is_answer_part = (eq_idx != -1 and m.start() > eq_idx)
                            break
                        except Exception:
                            pass

        if unit_target_val is not None and unit_target_unit and unit_replace_cursor:
            sep = getattr(MathParser, 'decimal_separator', ',')
            convs = get_unit_conversions(unit_target_val, unit_target_unit, decimal_separator=sep)
            if convs:
                unit_menu = menu.addMenu(f"Convert Unit ({unit_target_unit})")
                for opt in convs:
                    disp = opt['display_text']
                    code_val = opt['code_text']
                    if opt['is_current']:
                        act = unit_menu.addAction(f"✓ {disp}")
                        act.setEnabled(False)
                    else:
                        act = unit_menu.addAction(disp)
                        def _do_unit_conv(checked=False, txt=code_val, rep_cur=unit_replace_cursor, is_ans=is_answer_part):
                            self.setTextCursor(rep_cur)
                            rep_cur.removeSelectedText()
                            ws_theme = getattr(self, 'theme_mode', 'light')
                            output_blue = Theme.OPENMATH_MATH_BLUE if ws_theme != 'dark' else Theme.DARK_MATH_BLUE
                            fmt = self._get_char_format_for_mode(self.get_mode_at_cursor())
                            fmt_res = QTextCharFormat(fmt)
                            if is_ans:
                                fmt_res.setForeground(QColor(output_blue))
                            rep_cur.insertText(txt, fmt_res)
                            self.setTextCursor(rep_cur)
                        act.triggered.connect(_do_unit_conv)
                menu.addSeparator()

        # Check if right-click is on an image; if so and no selection, select the image
        if not self.textCursor().hasSelection():
            p = cursor.position()
            for test_p in [p, p - 1]:
                if 0 <= test_p < self.document().characterCount() - 1:
                    c_test = QTextCursor(self.document())
                    c_test.setPosition(test_p)
                    c_test.setPosition(test_p + 1, QTextCursor.MoveMode.KeepAnchor)
                    if c_test.charFormat().isImageFormat():
                        self.setTextCursor(c_test)
                        break

        # Standard editing actions matching clean style
        act_undo = menu.addAction("Undo")
        act_undo.setEnabled(self.document().isUndoAvailable())
        act_undo.triggered.connect(self.undo)

        act_redo = menu.addAction("Redo")
        act_redo.setEnabled(self.document().isRedoAvailable())
        act_redo.triggered.connect(self.redo)

        menu.addSeparator()

        ws = self._get_worksheet_view()
        is_multi = bool(ws and getattr(ws, 'selected_cells', None) and len(ws.selected_cells) > 1 and self.parent_cell in ws.selected_cells)
        selected_count = len(ws.selected_cells) if is_multi else 0

        has_sel = self.textCursor().hasSelection()
        act_cut = menu.addAction(f"Cut {selected_count} Statements" if is_multi else "Cut")
        act_cut.setEnabled(has_sel or is_multi)
        if is_multi:
            act_cut.triggered.connect(ws.cut_selected_cells)
        else:
            act_cut.triggered.connect(self.cut)

        act_copy = menu.addAction(f"Copy {selected_count} Statements" if is_multi else "Copy")
        act_copy.setEnabled(has_sel or is_multi)
        if is_multi:
            act_copy.triggered.connect(ws.copy_selected_cells)
        else:
            act_copy.triggered.connect(self.copy)

        cb = QApplication.clipboard()
        cb_mime = cb.mimeData() if cb else None
        has_cb_cells = bool(cb_mime and cb_mime.hasFormat("application/x-openmath-cells"))
        has_cb_img = bool(cb_mime and (
            cb_mime.hasImage() or 
            (cb_mime.hasHtml() and '<img' in cb_mime.html().lower()) or
            (cb_mime.hasUrls() and any(u.isLocalFile() and u.toLocalFile().lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif', '.webp')) for u in cb_mime.urls()))
        ))

        act_paste = menu.addAction("Paste")
        act_paste.setEnabled(self.canPaste() or has_cb_img or has_cb_cells or is_multi)
        if has_cb_cells or is_multi:
            act_paste.triggered.connect(lambda: ws.paste_cells() if ws else self.paste())
        elif has_cb_img and not self.canPaste():
            act_paste.triggered.connect(lambda: self.insertFromMimeData(cb_mime))
        else:
            act_paste.triggered.connect(self.paste)

        if has_cb_img:
            act_paste_img = menu.addAction("Paste Image")
            act_paste_img.triggered.connect(lambda: self.insertFromMimeData(cb_mime))

        # If selection contains an image, add "Copy Image"
        if has_sel and '\ufffc' in self.textCursor().selectedText():
            act_copy_img = menu.addAction("Copy Image")
            act_copy_img.triggered.connect(self.copy)

        act_insert_img = menu.addAction("Insert Image from File...")
        act_insert_img.triggered.connect(self._on_insert_image_dialog)

        act_del = menu.addAction(f"Delete {selected_count} Statements" if is_multi else "Delete")
        act_del.setEnabled(has_sel or is_multi)
        if is_multi:
            act_del.triggered.connect(ws.delete_selected_cells)
        else:
            def _do_delete():
                if self.textCursor().hasSelection():
                    self.textCursor().removeSelectedText()
            act_del.triggered.connect(_do_delete)

        menu.addSeparator()

        act_select_all = menu.addAction("Select All")
        act_select_all.triggered.connect(self.selectAll)
        if ws and len(ws.cells) > 1:
            act_select_all_doc = menu.addAction("Select All Statements in Document")
            act_select_all_doc.triggered.connect(ws.select_all_cells)

        menu.addSeparator()

        act_eval = menu.addAction("Inline Evaluation (Shift+Enter)")
        act_eval.triggered.connect(self._handle_inline_evaluation)

        act_exec = menu.addAction("Execute Cell (Ctrl+Enter)")
        act_exec.triggered.connect(self.executeRequested.emit)

        menu.exec(event.globalPos())

    def _get_image_rect(self, ch_pos: int, img_fmt: QTextImageFormat) -> Optional[QRectF]:
        """Compute the bounding QRectF of an image in viewport coordinates."""
        doc = self.document()
        if ch_pos < 0 or ch_pos >= doc.characterCount() - 1:
            return None
        c_start = QTextCursor(doc)
        c_start.setPosition(ch_pos)
        c_end = QTextCursor(doc)
        c_end.setPosition(ch_pos + 1)

        r_start = self.cursorRect(c_start)
        r_end = self.cursorRect(c_end)

        x = min(r_start.x(), r_end.x())
        y = min(r_start.y(), r_end.y())

        w = img_fmt.width() if img_fmt.width() > 0 else abs(r_end.x() - r_start.x())
        h = img_fmt.height() if img_fmt.height() > 0 else max(r_start.height(), r_end.height())

        if w <= 0 or h <= 0:
            return None

        return QRectF(float(x), float(y), float(w), float(h))

    def _hit_test_corners(self, pos: QPoint, rect: QRectF, radius: float = 12.0) -> Optional[str]:
        """Test if pos is within radius of any of the 4 corners of rect."""
        x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()
        corners = {
            'tl': (x, y),
            'tr': (x + w, y),
            'bl': (x, y + h),
            'br': (x + w, y + h),
        }
        r2 = radius * radius
        px, py = float(pos.x()), float(pos.y())
        for name, (cx, cy) in corners.items():
            dx = px - cx
            dy = py - cy
            if dx * dx + dy * dy <= r2:
                return name
        return None

    def _find_image_at_pos(self, pos: QPoint) -> Optional[Tuple[int, QTextImageFormat, QRectF]]:
        """Find the image character at viewport pos, returning (char_pos, format, rect)."""
        doc = self.document()
        if not doc or doc.characterCount() <= 1:
            return None

        cursor = self.cursorForPosition(pos)
        p = cursor.position()
        test_positions = [p, p - 1, p + 1]

        for test_p in test_positions:
            if 0 <= test_p < doc.characterCount() - 1:
                c = QTextCursor(doc)
                c.setPosition(test_p)
                c.setPosition(test_p + 1, QTextCursor.MoveMode.KeepAnchor)
                fmt = c.charFormat()
                if fmt.isImageFormat():
                    img_rect = self._get_image_rect(test_p, fmt.toImageFormat())
                    if img_rect and img_rect.adjusted(-6, -6, 6, 6).contains(float(pos.x()), float(pos.y())):
                        return (test_p, fmt.toImageFormat(), img_rect)

        if hasattr(self, 'embedded_images') and self.embedded_images:
            for ch_pos in range(doc.characterCount() - 1):
                c = QTextCursor(doc)
                c.setPosition(ch_pos)
                c.setPosition(ch_pos + 1, QTextCursor.MoveMode.KeepAnchor)
                fmt = c.charFormat()
                if fmt.isImageFormat():
                    img_rect = self._get_image_rect(ch_pos, fmt.toImageFormat())
                    if img_rect and img_rect.adjusted(-6, -6, 6, 6).contains(float(pos.x()), float(pos.y())):
                        return (ch_pos, fmt.toImageFormat(), img_rect)
        return None

    def _draw_image_resize_handles(self):
        """Draw bounding box and 4 corner resize handles for active/selected/hovered image."""
        active_pos = getattr(self, '_selected_image_pos', None)
        if active_pos is None:
            active_pos = getattr(self, '_hovered_image_pos', None)
        if active_pos is None:
            return

        doc = self.document()
        if not (0 <= active_pos < doc.characterCount() - 1):
            return

        c = QTextCursor(doc)
        c.setPosition(active_pos)
        c.setPosition(active_pos + 1, QTextCursor.MoveMode.KeepAnchor)
        fmt = c.charFormat()
        if not fmt.isImageFormat():
            return

        img_rect = self._get_image_rect(active_pos, fmt.toImageFormat())
        if not img_rect:
            return

        p = QPainter(self.viewport())
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        is_dark = bool(self.parent_cell and getattr(self.parent_cell, 'theme_mode', 'light') == 'dark')
        border_col = QColor("#2563eb") if not is_dark else QColor("#60a5fa")

        # 1. Selection border outline
        pen = QPen(border_col, 1.5, Qt.PenStyle.SolidLine)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(img_rect)

        # 2. 4 corner handles
        handle_size = 9.0
        half = handle_size / 2.0
        x = img_rect.x()
        y = img_rect.y()
        w = img_rect.width()
        h = img_rect.height()

        corners = [
            (x, y),          # Top-Left
            (x + w, y),      # Top-Right
            (x, y + h),      # Bottom-Left
            (x + w, y + h),  # Bottom-Right
        ]

        handle_pen = QPen(border_col, 1.5, Qt.PenStyle.SolidLine)
        handle_fill = QBrush(QColor("#ffffff") if not is_dark else QColor("#1e293b"))
        p.setPen(handle_pen)
        p.setBrush(handle_fill)

        for cx, cy in corners:
            h_rect = QRectF(cx - half, cy - half, handle_size, handle_size)
            p.drawRoundedRect(h_rect, 2.0, 2.0)

        p.end()

    def leaveEvent(self, event):
        super().leaveEvent(event)
        if getattr(self, '_hovered_image_pos', None) is not None and getattr(self, '_selected_image_pos', None) is None:
            self._hovered_image_pos = None
            self.viewport().unsetCursor()
            self.viewport().update()

    def mousePressEvent(self, event):
        self._subscript_active = False
        self._superscript_active = False
        self._drag_start_global_pos = event.globalPosition().toPoint() if hasattr(event, 'globalPosition') else event.globalPos()
        self._is_cross_cell_drag = False

        # 1. Check if clicking on an image corner resize handle
        if event.button() == Qt.MouseButton.LeftButton:
            active_pos = getattr(self, '_selected_image_pos', None)
            if active_pos is None:
                active_pos = getattr(self, '_hovered_image_pos', None)
            if active_pos is None:
                found = self._find_image_at_pos(event.pos())
                if found:
                    active_pos = found[0]

            if active_pos is not None and (0 <= active_pos < self.document().characterCount() - 1):
                c = QTextCursor(self.document())
                c.setPosition(active_pos)
                c.setPosition(active_pos + 1, QTextCursor.MoveMode.KeepAnchor)
                fmt = c.charFormat()
                if fmt.isImageFormat():
                    img_fmt = fmt.toImageFormat()
                    img_rect = self._get_image_rect(active_pos, img_fmt)
                    if img_rect:
                        corner = self._hit_test_corners(event.pos(), img_rect)
                        if corner:
                            self._resizing_image = True
                            self._resize_corner = corner
                            self._resize_image_pos = active_pos
                            self._resize_start_mouse = event.pos()
                            self._resize_start_w = img_fmt.width() if img_fmt.width() > 0 else img_rect.width()
                            self._resize_start_h = img_fmt.height() if img_fmt.height() > 0 else img_rect.height()

                            # Determine intrinsic aspect ratio from QImage resource or start size
                            src_name = img_fmt.name()
                            res = self.document().resource(QTextDocument.ResourceType.ImageResource, QUrl(src_name))
                            if res and not res.isNull() and res.size().width() > 0 and res.size().height() > 0:
                                self._resize_ratio = float(res.size().width()) / float(res.size().height())
                            elif self._resize_start_h > 0:
                                self._resize_ratio = float(self._resize_start_w) / float(self._resize_start_h)
                            else:
                                self._resize_ratio = 1.0

                            self._selected_image_pos = active_pos
                            self.viewport().update()
                            event.accept()
                            return

        ws = self._get_worksheet_view()
        if event.button() == Qt.MouseButton.LeftButton and ws:
            mods = event.modifiers()
            if mods & Qt.KeyboardModifier.ShiftModifier:
                if ws.active_cell and ws.active_cell != self.parent_cell:
                    ws.select_cell(self.parent_cell, range_select=True)
                    event.accept()
                    return
            elif mods & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier):
                ws.select_cell(self.parent_cell, additive=True)
                event.accept()
                return
            else:
                if getattr(ws, 'selected_cells', None) and len(ws.selected_cells) > 0:
                    ws.clear_cell_selection()

        super().mousePressEvent(event)

        if event.button() == Qt.MouseButton.LeftButton:
            # Check if clicked on an image directly
            found = self._find_image_at_pos(event.pos())
            if found:
                img_pos, img_fmt, img_rect = found
                self._selected_image_pos = img_pos
                c_test = QTextCursor(self.document())
                c_test.setPosition(img_pos)
                c_test.setPosition(img_pos + 1, QTextCursor.MoveMode.KeepAnchor)
                self.setTextCursor(c_test)
                self.viewport().update()
            else:
                if getattr(self, '_selected_image_pos', None) is not None:
                    self._selected_image_pos = None
                    self.viewport().update()

    def mouseMoveEvent(self, event):
        # 1. Handle active image resizing from any corner without stretching
        if getattr(self, '_resizing_image', False):
            corner = getattr(self, '_resize_corner', 'br')
            dx = event.pos().x() - self._resize_start_mouse.x()
            dy = event.pos().y() - self._resize_start_mouse.y()
            ratio = getattr(self, '_resize_ratio', 1.0)
            start_w = getattr(self, '_resize_start_w', 100.0)

            # Symmetrical displacement for all 4 corners
            if corner == 'br':
                delta_x = dx
                delta_y = dy * ratio
            elif corner == 'tr':
                delta_x = dx
                delta_y = -dy * ratio
            elif corner == 'bl':
                delta_x = -dx
                delta_y = dy * ratio
            elif corner == 'tl':
                delta_x = -dx
                delta_y = -dy * ratio
            else:
                delta_x = dx
                delta_y = dy * ratio

            delta = delta_x if abs(delta_x) >= abs(delta_y) else delta_y
            max_w = max(700, self.viewport().width() - 40)
            new_w = max(40.0, min(float(max_w), start_w + delta))
            new_h = max(20.0, new_w / ratio)

            # Update format in document
            pos = getattr(self, '_resize_image_pos', None)
            if pos is not None and 0 <= pos < self.document().characterCount() - 1:
                c = QTextCursor(self.document())
                c.setPosition(pos)
                c.setPosition(pos + 1, QTextCursor.MoveMode.KeepAnchor)
                fmt = c.charFormat()
                if fmt.isImageFormat():
                    img_fmt = fmt.toImageFormat()
                    img_fmt.setWidth(new_w)
                    img_fmt.setHeight(new_h)
                    c.setCharFormat(img_fmt)
                    self._adjust_height()
                    self.viewport().update()

            event.accept()
            return

        # 2. Hover detection and cursor shape update for corner handles
        if not (event.buttons() & Qt.MouseButton.LeftButton):
            active_pos = getattr(self, '_selected_image_pos', None)
            if active_pos is None:
                found = self._find_image_at_pos(event.pos())
                if found:
                    active_pos = found[0]
                    if getattr(self, '_hovered_image_pos', None) != active_pos:
                        self._hovered_image_pos = active_pos
                        self.viewport().update()
                else:
                    if getattr(self, '_hovered_image_pos', None) is not None:
                        self._hovered_image_pos = None
                        self.viewport().update()

            if active_pos is not None and (0 <= active_pos < self.document().characterCount() - 1):
                c = QTextCursor(self.document())
                c.setPosition(active_pos)
                c.setPosition(active_pos + 1, QTextCursor.MoveMode.KeepAnchor)
                fmt = c.charFormat()
                if fmt.isImageFormat():
                    img_rect = self._get_image_rect(active_pos, fmt.toImageFormat())
                    if img_rect:
                        corner = self._hit_test_corners(event.pos(), img_rect)
                        if corner in ('tl', 'br'):
                            self.viewport().setCursor(Qt.CursorShape.SizeFDiagCursor)
                        elif corner in ('tr', 'bl'):
                            self.viewport().setCursor(Qt.CursorShape.SizeBDiagCursor)
                        elif img_rect.contains(float(event.pos().x()), float(event.pos().y())):
                            self.viewport().setCursor(Qt.CursorShape.ArrowCursor)
                        else:
                            self.viewport().unsetCursor()
                    else:
                        self.viewport().unsetCursor()
                else:
                    self.viewport().unsetCursor()
            else:
                self.viewport().unsetCursor()

        # 3. Cross-cell drag selection
        if (event.buttons() & Qt.MouseButton.LeftButton) and hasattr(self, '_drag_start_global_pos') and self._drag_start_global_pos is not None:
            ws = self._get_worksheet_view()
            if ws and hasattr(ws, 'container') and ws.container and hasattr(self, 'parent_cell') and self.parent_cell in ws.cells:
                g_pos = event.globalPosition().toPoint() if hasattr(event, 'globalPosition') else event.globalPos()
                c_pos = ws.container.mapFromGlobal(g_pos)
                cur_y = c_pos.y()
                parent_geo = self.parent_cell.geometry()
                top_b = parent_geo.top()
                bot_b = parent_geo.bottom()

                if cur_y < top_b - 6 or cur_y > bot_b + 6 or getattr(self, '_is_cross_cell_drag', False):
                    self._is_cross_cell_drag = True
                    target_cell = None
                    for c in ws.cells:
                        geo = c.geometry()
                        if geo.top() <= cur_y <= geo.bottom():
                            target_cell = c
                            break
                    if not target_cell and ws.cells:
                        if cur_y < ws.cells[0].geometry().top():
                            target_cell = ws.cells[0]
                        elif cur_y > ws.cells[-1].geometry().bottom():
                            target_cell = ws.cells[-1]

                    if target_cell:
                        ws.select_range(self.parent_cell, target_cell)
                        if hasattr(ws, 'scroll_area') and ws.scroll_area:
                            ws.scroll_area.ensureVisible(c_pos.x(), c_pos.y(), 20, 20)
                        event.accept()
                        return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if getattr(self, '_resizing_image', False):
            self._resizing_image = False
            self.viewport().unsetCursor()
            self._adjust_height()
            self.viewport().update()
            event.accept()
            return
        if getattr(self, '_is_cross_cell_drag', False):
            self._is_cross_cell_drag = False
            event.accept()
            return
        super().mouseReleaseEvent(event)


class SelectableErrorLabel(QLabel):
    """
    Selectable error label that notifies when Delete or Backspace is pressed.
    """
    deletePressed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWordWrap(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse |
            Qt.TextInteractionFlag.TextSelectableByKeyboard
        )

    def minimumSizeHint(self) -> QSize:
        return QSize(50, 18)

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self.deletePressed.emit()
            event.accept()
            return
        super().keyPressEvent(event)

    def contextMenuEvent(self, event):
        p = self.parent()
        while p and not hasattr(p, '_show_error_context_menu'):
            p = p.parent()
        if p and hasattr(p, '_show_error_context_menu'):
            p._show_error_context_menu(event.globalPos())
            event.accept()
        else:
            super().contextMenuEvent(event)


class SelectableSuggestionLabel(QLabel):
    """
    Suggestion label with word wrap and small minimumSizeHint so it wraps down into multiple lines
    instead of forcing the cell or window beyond the screen boundary.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWordWrap(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

    def minimumSizeHint(self) -> QSize:
        return QSize(50, 18)

    def contextMenuEvent(self, event):
        p = self.parent()
        while p and not hasattr(p, '_show_error_context_menu'):
            p = p.parent()
        if p and hasattr(p, '_show_error_context_menu'):
            p._show_error_context_menu(event.globalPos())
            event.accept()
        else:
            super().contextMenuEvent(event)


class CellErrorBox(QFrame):
    """
    Selectable Error Box with intelligent fix suggestions.
    Allows user to mark/select the error with mouse or keyboard,
    view 'Did you mean: ...' suggestions, click 'Apply Fix' or press Delete/Backspace to dismiss.
    """
    dismissRequested = pyqtSignal()
    suggestionApplied = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("cellErrorBox")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(20, 3, 8, 3)
        main_layout.setSpacing(6)

        # Content column (Error label + Suggestion row)
        content_col = QVBoxLayout()
        content_col.setContentsMargins(0, 0, 0, 0)
        content_col.setSpacing(4)

        # Selectable error label
        self.lbl_text = SelectableErrorLabel(self)
        self.lbl_text.setFont(QFont("Consolas", 11, QFont.Weight.Bold))
        self.lbl_text.setStyleSheet("color: #b91c1c; background: transparent; font-weight: bold;")
        self.lbl_text.deletePressed.connect(self.dismissRequested.emit)
        content_col.addWidget(self.lbl_text)

        # Suggestion container
        self.suggestion_widget = QWidget(self)
        self.suggestion_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        sugg_layout = QHBoxLayout(self.suggestion_widget)
        sugg_layout.setContentsMargins(0, 0, 0, 0)
        sugg_layout.setSpacing(8)

        self.lbl_suggestion = SelectableSuggestionLabel(self.suggestion_widget)
        self.lbl_suggestion.setFont(QFont("Segoe UI", 10))
        self.lbl_suggestion.setStyleSheet("color: #0369a1; background: transparent;")
        sugg_layout.addWidget(self.lbl_suggestion, 1)

        self.btn_apply = QPushButton("Apply Fix", self.suggestion_widget)
        self.btn_apply.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_apply.setStyleSheet("""
            QPushButton {
                background: #0284c7;
                color: #ffffff;
                font-weight: bold;
                font-size: 10px;
                border: none;
                border-radius: 3px;
                padding: 2px 8px;
            }
            QPushButton:hover {
                background: #0369a1;
            }
            QPushButton:pressed {
                background: #075985;
            }
        """)
        self.btn_apply.clicked.connect(self._on_apply_clicked)
        sugg_layout.addWidget(self.btn_apply, 0, Qt.AlignmentFlag.AlignTop)

        self.suggestion_widget.setVisible(False)
        content_col.addWidget(self.suggestion_widget)

        main_layout.addLayout(content_col, 1)

    def minimumSizeHint(self) -> QSize:
        return QSize(60, super().minimumSizeHint().height())

        # Quick remove button '✕'
        self.btn_remove = QPushButton("✕", self)
        self.btn_remove.setFixedSize(20, 20)
        self.btn_remove.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_remove.setToolTip("Remove Error (Delete / Backspace)")
        self.btn_remove.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #b91c1c;
                border: 1px solid transparent;
                border-radius: 10px;
                font-size: 11px;
                font-weight: bold;
                padding: 0px;
            }
            QPushButton:hover {
                background: #fee2e2;
                border: 1px solid #fca5a5;
                color: #991b1b;
            }
            QPushButton:pressed {
                background: #fecaca;
            }
        """)
        self.btn_remove.clicked.connect(self.dismissRequested.emit)
        main_layout.addWidget(self.btn_remove, 0, Qt.AlignmentFlag.AlignTop)

        self._current_suggestion = ""
        self._is_selected = False
        self._update_style()

    def set_error_and_suggestion(self, error_text: str, suggestion: str = ""):
        self.lbl_text.setText(error_text)
        self._current_suggestion = suggestion or ""
        if suggestion:
            self.lbl_suggestion.setText(f"Did you mean:  {suggestion}")
            self.suggestion_widget.setVisible(True)
        else:
            self.suggestion_widget.setVisible(False)

    def _on_apply_clicked(self):
        if self._current_suggestion:
            self.suggestionApplied.emit(self._current_suggestion)

    def setText(self, text: str):
        self.set_error_and_suggestion(text, "")

    def text(self) -> str:
        return self.lbl_text.text()

    def set_selected(self, selected: bool):
        self._is_selected = selected
        self._update_style()

    def _update_style(self):
        if self._is_selected:
            self.setStyleSheet("""
                #cellErrorBox {
                    background-color: #fef2f2;
                    border: 1.5px dashed #f87171;
                    border-radius: 4px;
                }
            """)
        else:
            self.setStyleSheet("""
                #cellErrorBox {
                    background-color: transparent;
                    border: 1px solid transparent;
                    border-radius: 4px;
                }
            """)

    def mousePressEvent(self, event):
        self.setFocus()
        self.set_selected(True)
        super().mousePressEvent(event)

    def focusInEvent(self, event):
        self.set_selected(True)
        super().focusInEvent(event)

    def focusOutEvent(self, event):
        self.set_selected(False)
        super().focusOutEvent(event)

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self.dismissRequested.emit()
            event.accept()
            return
        super().keyPressEvent(event)

    def _show_error_context_menu(self, global_pos):
        menu = QMenu(self)
        theme_mode = getattr(self, 'theme_mode', 'light')
        parent_cell = getattr(self, 'parent_cell', None)
        if not parent_cell:
            p = self.parent()
            while p:
                if hasattr(p, 'input_edit'):
                    parent_cell = p
                    break
                p = p.parent()
        if parent_cell:
            theme_mode = getattr(parent_cell, 'theme_mode', theme_mode)

        Theme.apply_menu_style(menu, theme_mode)

        # 1. Direct fix suggestion if available
        if self._current_suggestion:
            sugg_text = self._current_suggestion
            act_sugg = menu.addAction(f"💡 Apply Fix:  {sugg_text}")
            act_sugg.triggered.connect(lambda checked=False, s=sugg_text: self.suggestionApplied.emit(s))

        # 2. Check for relevant function in cell input or error message
        input_text = parent_cell.get_input_text().strip() if parent_cell else ""
        from cas_engine.function_guide import find_function_in_text, get_categories_dict
        fn_name, fn_info, span = find_function_in_text(input_text)
        if not fn_info:
            fn_name, fn_info, span = find_function_in_text(self.text())

        if fn_info:
            if fn_info.primary_example != self._current_suggestion:
                act_ex = menu.addAction(f"💡 Insert Example:  {fn_info.primary_example}")
                act_ex.triggered.connect(lambda checked=False, c=fn_info.primary_example: self.suggestionApplied.emit(c))

            if len(fn_info.examples) > 1:
                menu_exs = menu.addMenu(f"💡 Examples for '{fn_info.name}'")
                Theme.apply_menu_style(menu_exs, theme_mode)
                for ex in fn_info.examples:
                    act_item = menu_exs.addAction(f"{ex.label}:  {ex.code}")
                    act_item.triggered.connect(lambda checked=False, c=ex.code: self.suggestionApplied.emit(c))

            act_hint = menu.addAction(f"ℹ️  {fn_info.syntax} — {fn_info.description}")
            act_hint.setEnabled(False)

        menu.addSeparator()

        # 3. Categorized examples browser submenu
        menu_catalog = menu.addMenu("💡 Browse Math Function Examples")
        Theme.apply_menu_style(menu_catalog, theme_mode)
        cats = get_categories_dict()
        for cat_name, items in cats.items():
            cat_menu = menu_catalog.addMenu(cat_name)
            Theme.apply_menu_style(cat_menu, theme_mode)
            for itm in items:
                act_itm = cat_menu.addAction(f"{itm.name} — {itm.primary_example}")
                act_itm.triggered.connect(lambda checked=False, c=itm.primary_example: self.suggestionApplied.emit(c))

        menu.addSeparator()

        # 4. Copy actions
        if hasattr(self, 'lbl_text') and self.lbl_text.hasSelectedText():
            sel = self.lbl_text.selectedText()
            act_copy_sel = menu.addAction("Copy Selected Text")
            act_copy_sel.triggered.connect(lambda: QApplication.clipboard().setText(sel))

        act_copy = menu.addAction("Copy Error Message")
        clean_err = self.text().strip()
        act_copy.triggered.connect(lambda: QApplication.clipboard().setText(clean_err))

        # 5. Dismiss action
        act_remove = menu.addAction("✕ Dismiss Error (Delete)")
        act_remove.triggered.connect(self.dismissRequested.emit)

        menu.exec(global_pos)

    def contextMenuEvent(self, event):
        self._show_error_context_menu(event.globalPos())


class CellOutputBox(QFrame):
    """
    Cell output container that can be marked and removed via Delete/Backspace or ✕ button.
    """
    dismissRequested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("cellOutputBox")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        self._is_selected = False
        self._update_style()

    def set_selected(self, selected: bool):
        self._is_selected = selected
        self._update_style()

    def _update_style(self):
        if self._is_selected:
            self.setStyleSheet("""
                #cellOutputBox {
                    background-color: #f8fafc;
                    border: 1.5px dashed #94a3b8;
                    border-radius: 4px;
                }
            """)
        else:
            self.setStyleSheet("""
                #cellOutputBox {
                    background-color: transparent;
                    border: 1px solid transparent;
                    border-radius: 4px;
                }
            """)

    def mousePressEvent(self, event):
        self.setFocus()
        self.set_selected(True)
        super().mousePressEvent(event)

    def focusInEvent(self, event):
        self.set_selected(True)
        super().focusInEvent(event)

    def focusOutEvent(self, event):
        self.set_selected(False)
        super().focusOutEvent(event)

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self.dismissRequested.emit()
            event.accept()
            return
        super().keyPressEvent(event)

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        Theme.apply_menu_style(menu, getattr(self, 'theme_mode', 'light'))
        parent_cell = getattr(self, 'parent_cell', None)
        if not parent_cell:
            p = self.parent()
            while p:
                if hasattr(p, 'current_result') and hasattr(p, 'math_renderer'):
                    parent_cell = p
                    break
                p = p.parent()

        if parent_cell and parent_cell.current_result and parent_cell.current_result.raw_result is not None:
            raw = parent_cell.current_result.raw_result
            import sympy as sp
            from cas_engine.formatter import MathFormatter

            # 1. Convert to Decimal
            try:
                flt = float(raw)
                if flt.is_integer():
                    raw_dec = str(int(flt))
                else:
                    raw_dec = f"{flt:.10f}".rstrip("0").rstrip(".")
                dec_str = MathFormatter.format_decimal(raw_dec)
                act_dec = menu.addAction(f"Convert to Decimal ({dec_str})")
                def _do_dec():
                    parent_cell.math_renderer.set_latex(MathFormatter.format_latex_decimal(dec_str))
                act_dec.triggered.connect(_do_dec)
            except Exception:
                pass

            # 2. Convert to Fraction
            try:
                rat = decimal_to_fraction(str(raw))
                if rat is not None:
                    n, d = sp.fraction(rat)
                    if d != 1 and d != -1:
                        act_frac = menu.addAction(f"Convert to Fraction ({n}/{d})")
                        def _do_frac():
                            parent_cell.math_renderer.set_latex(MathFormatter.to_latex(rat))
                        act_frac.triggered.connect(_do_frac)
            except Exception:
                pass

            # 3. Simplify
            try:
                sim = sp.simplify(raw)
                if sp.sstr(sim) != sp.sstr(raw):
                    act_simp = menu.addAction(f"Simplify ({sim})")
                    def _do_simp():
                        parent_cell.math_renderer.set_latex(MathFormatter.to_latex(sim))
                    act_simp.triggered.connect(_do_simp)
            except Exception:
                pass

            # 4. Unit Conversion
            from cas_engine.units import infer_unit_from_expression, get_unit_conversions, UNIT_LOOKUP
            math_text = parent_cell.get_executable_text() if hasattr(parent_cell, 'get_executable_text') else ""
            inferred_u = infer_unit_from_expression(math_text)
            if inferred_u and inferred_u in UNIT_LOOKUP:
                try:
                    flt_val = float(raw)
                    sep = getattr(MathParser, 'decimal_separator', ',')
                    convs = get_unit_conversions(flt_val, inferred_u, decimal_separator=sep)
                    if convs:
                        u_menu = menu.addMenu(f"Convert Unit ({inferred_u})")
                        for opt in convs:
                            disp = opt['display_text']
                            code_u = opt['code_unit']
                            c_val = opt['value']
                            if opt['is_current']:
                                act = u_menu.addAction(f"✓ {disp}")
                                act.setEnabled(False)
                            else:
                                act = u_menu.addAction(disp)
                                def _do_out_conv(checked=False, val_float=c_val, u_lbl=code_u):
                                    dec = MathFormatter.format_decimal(f"{val_float:.6g}" if 'e' in f"{val_float:.6g}".lower() else f"{val_float:.6f}".rstrip('0').rstrip('.'))
                                    parent_cell.math_renderer.set_latex(f"{MathFormatter.format_latex_decimal(dec)}\\text{{ {u_lbl}}}")
                                act.triggered.connect(_do_out_conv)
                except Exception:
                    pass

            menu.addSeparator()

        act_remove = menu.addAction("Remove Output (Delete)")
        act_remove.triggered.connect(self.dismissRequested.emit)
        menu.exec(event.globalPos())


class CellBracketBar(QWidget):
    """
    Execution Group left bracket '[' widget.
    Draws the classic vertical bracket line grouping input and output together.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(10)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event):
        parent_cell = self.parent()
        while parent_cell and not hasattr(parent_cell, 'deleteRequested'):
            parent_cell = parent_cell.parent()
        if parent_cell and hasattr(parent_cell, '_get_worksheet_view'):
            ws = parent_cell._get_worksheet_view()
            if ws:
                mods = event.modifiers()
                if mods & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier):
                    ws.select_cell(parent_cell, additive=True)
                elif mods & Qt.KeyboardModifier.ShiftModifier:
                    ws.select_cell(parent_cell, range_select=True)
                else:
                    ws.select_cell(parent_cell, additive=False)
                event.accept()
                return
        super().mousePressEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        pen = QPen(QColor("#7c8798"), 1)
        painter.setPen(pen)
        w = self.width()
        h = self.height()
        # Draw bracket '[': top tick, vertical line, bottom tick
        painter.drawLine(w - 2, 2, w - 8, 2)
        painter.drawLine(w - 8, 2, w - 8, h - 3)
        painter.drawLine(w - 8, h - 3, w - 2, h - 3)


class DraggableAxisLabel(mob.DraggableBase):
    """
    Allows dragging an axis label (e.g. 'x' or 'f(x)') directly with the mouse.
    """
    def __init__(self, axis, use_blit=False):
        self.axis = axis
        self.text = axis.label
        self.ax = axis.axes
        self.text.set_picker(True)
        super().__init__(self.text, use_blit=use_blit)

    def save_offset(self):
        fig = self.text.get_figure(root=True)
        r = fig.canvas.get_renderer()
        bbox = self.text.get_window_extent(r)
        self.orig_center_x = (bbox.x0 + bbox.x1) / 2
        self.orig_center_y = (bbox.y0 + bbox.y1) / 2

    def update_offset(self, dx, dy):
        fig = self.text.get_figure(root=True)
        margin = 8.0
        new_disp_x = max(margin, min(self.orig_center_x + dx, fig.bbox.width - margin))
        new_disp_y = max(margin, min(self.orig_center_y + dy, fig.bbox.height - margin))
        axes_pos = self.ax.transAxes.inverted().transform((new_disp_x, new_disp_y))
        self.axis.set_label_coords(axes_pos[0], axes_pos[1], transform=self.ax.transAxes)


class SectionDisclosureWidget(QWidget):
    """
    Crisp vector-rendered collapsible section disclosure arrow matching worksheet reference.
    Draws an equilateral filled triangle:
    - Collapsed: pointing right (▶)
    - Expanded: pointing down (▼)
    """
    clicked = pyqtSignal()

    def __init__(self, is_collapsed: bool = False, parent=None):
        super().__init__(parent)
        self._is_collapsed = is_collapsed
        self._hovered = False
        self.setFixedSize(16, 16)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)

    def is_collapsed(self) -> bool:
        return self._is_collapsed

    def set_collapsed(self, collapsed: bool):
        if self._is_collapsed != collapsed:
            self._is_collapsed = collapsed
            self.update()

    def setText(self, text: str):
        """Backward compatibility for callers setting '▼' or '►'."""
        self.set_collapsed("►" in text or "▶" in text)

    def text(self) -> str:
        """Backward compatibility: returns '►' if collapsed else '▼'."""
        return "►" if self._is_collapsed else "▼"

    def enterEvent(self, event):
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            parent_cell = getattr(self.parent(), 'parent_cell', None)
            if not parent_cell:
                p = self.parent()
                while p:
                    if hasattr(p, 'deleteRequested'):
                        parent_cell = p
                        break
                    p = p.parent()
            mods = event.modifiers()
            if mods & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier):
                if parent_cell:
                    ws = parent_cell._get_worksheet_view()
                    if ws:
                        ws.select_cell(parent_cell, additive=True)
                        event.accept()
                        return
            elif mods & Qt.KeyboardModifier.ShiftModifier:
                if parent_cell:
                    ws = parent_cell._get_worksheet_view()
                    if ws:
                        ws.select_cell(parent_cell, range_select=True)
                        event.accept()
                        return
            self.clicked.emit()
        super().mousePressEvent(event)

    def contextMenuEvent(self, event):
        parent_cell = getattr(self.parent(), 'parent_cell', None)
        if not parent_cell:
            p = self.parent()
            while p:
                if hasattr(p, 'deleteRequested'):
                    parent_cell = p
                    break
                p = p.parent()

        menu = QMenu(self)
        theme_mode = getattr(parent_cell, 'theme_mode', 'light') if parent_cell else 'light'
        Theme.apply_menu_style(menu, theme_mode)

        act_toggle = menu.addAction("Expand Section" if self._is_collapsed else "Collapse Section")
        act_toggle.triggered.connect(self.clicked.emit)

        menu.addSeparator()

        ws = parent_cell._get_worksheet_view() if parent_cell else None
        selected_count = len(getattr(ws, 'selected_cells', [])) if ws else 0
        if selected_count > 1 and ws and parent_cell in ws.selected_cells:
            act_del_all = menu.addAction(f"Delete {selected_count} Selected Elements")
            act_del_all.triggered.connect(ws.delete_selected_cells)
        else:
            is_sub = getattr(parent_cell, 'section_level', 0) > 0 if parent_cell else False
            del_label = "Delete Subsection" if is_sub else "Delete Section"
            act_del = menu.addAction(del_label)
            if parent_cell:
                act_del.triggered.connect(lambda: parent_cell.deleteRequested.emit(parent_cell.cell_id))

        if parent_cell:
            act_indent = menu.addAction("Indent Section (Tab)")
            act_indent.triggered.connect(parent_cell.indent_section)
            if getattr(parent_cell, 'section_level', 0) > 0:
                act_outdent = menu.addAction("Outdent Section (Shift+Tab)")
                act_outdent.triggered.connect(parent_cell.outdent_section)

        menu.exec(event.globalPos())
        event.accept()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        color = QColor("#1e293b" if self._hovered else "#737373")
        painter.setBrush(color)
        painter.setPen(Qt.PenStyle.NoPen)

        w = self.width()
        h = self.height()
        cx = w / 2.0
        cy = h / 2.0

        if self._is_collapsed:
            poly = QPolygonF([
                QPointF(cx - 3.5, cy - 5.5),
                QPointF(cx + 4.5, cy),
                QPointF(cx - 3.5, cy + 5.5)
            ])
        else:
            poly = QPolygonF([
                QPointF(cx - 5.5, cy - 3.5),
                QPointF(cx + 5.5, cy - 3.5),
                QPointF(cx, cy + 4.5)
            ])
        painter.drawPolygon(poly)


def _parse_worksheet_color(val: Any) -> Optional[str]:
    """Parse a worksheet color representation ([r, g, b] or #rrggbb or rgb(...)) to standard css rgb/hex."""
    if not val:
        return None
    s = str(val).strip()
    m_rgb = re.search(r'\[(\d+),\s*(\d+),\s*(\d+)\]', s)
    if m_rgb:
        r, g, b = m_rgb.groups()
        return f"rgb({r},{g},{b})"
    if s.startswith('#') or s.startswith('rgb'):
        return s
    return None


class SectionTitleEdit(QTextEdit):
    """
    Editable single-line rich title for section headers.
    Supports character formatting (font color, background highlight color,
    bold, italic, underline), partial text selection formatting, typing, editing,
    and Tab (indent) / Shift+Tab (outdent).
    Dynamically sizes its width and height to naturally fit its text contents.
    """
    focusNextRequested = pyqtSignal()
    focusPrevRequested = pyqtSignal()

    def __init__(self, parent_cell, parent=None):
        super().__init__(parent)
        self.parent_cell = parent_cell
        self.setPlaceholderText("")
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.document().setDocumentMargin(2)
        self.setContentsMargins(0, 0, 0, 0)
        self.textChanged.connect(self._on_text_changed)
        self.selectionChanged.connect(self._on_selection_changed)
        self._update_style()

    def text(self) -> str:
        return self.toPlainText()

    def setText(self, text: str):
        self.blockSignals(True)
        if not text:
            self.setPlainText("")
        elif "<" in text and ">" in text and any(tag in text.lower() for tag in ("<span", "<b", "<i", "<p", "<div", "<font", "<html")):
            self.setHtml(text)
        else:
            self.setPlainText(text)
        self.blockSignals(False)
        self._adjust_size()

    def hasSelectedText(self) -> bool:
        return self.textCursor().hasSelection()

    def selectedText(self) -> str:
        return self.textCursor().selectedText()

    def deselect(self):
        cur = self.textCursor()
        cur.clearSelection()
        self.setTextCursor(cur)

    def cursorPosition(self) -> int:
        return self.textCursor().position()

    def backspace(self):
        self.textCursor().deletePreviousChar()

    def insertFromMimeData(self, source: QMimeData):
        if source.hasText():
            clean = source.text().replace("\r\n", " ").replace("\n", " ").replace("\r", " ")
            self.insertPlainText(clean)
        else:
            super().insertFromMimeData(source)

    def _on_selection_changed(self):
        if self.parent_cell:
            ws = self.parent_cell._get_worksheet_view()
            if ws:
                ws.active_cell = self.parent_cell

    def _on_text_changed(self):
        txt = self.toPlainText()
        if self.parent_cell:
            self.parent_cell.section_title = txt
            self.parent_cell.section_html = self.toHtml()
        self._adjust_size()

    def _adjust_size(self):
        fm = self.fontMetrics()
        base_w = fm.horizontalAdvance("0" * 7) + 20
        doc = self.document()
        avail_w = 99999
        if self.parent_cell:
            cell_w = self.parent_cell.width()
            if cell_w > 100:
                avail_w = max(120, cell_w - 80)

        doc.setTextWidth(-1)
        doc.adjustSize()
        ideal_w = int(doc.idealWidth()) + 24
        if ideal_w > avail_w:
            w = avail_w
            doc.setTextWidth(avail_w - 10)
        else:
            w = max(base_w, ideal_w)
        h = max(28, int(doc.size().height()) + 4)
        self.setFixedSize(w, h)

    def _update_style(self):
        if not self.parent_cell:
            return
        lvl = getattr(self.parent_cell, 'section_level', 0)
        base_pt = 16 if lvl == 0 else (14 if lvl == 1 else 12)
        zoom = getattr(self.parent_cell, 'zoom_factor', 1.0)
        scaled_pt = max(10, round(base_pt * zoom))
        is_dark = getattr(self.parent_cell, 'theme_mode', 'light') == 'dark'

        font = QFont("Segoe UI", scaled_pt, QFont.Weight.Bold)
        font.setStyleHint(QFont.StyleHint.SansSerif)
        self.setFont(font)
        color = '#f8fafc' if is_dark else '#0f172a'

        self.setStyleSheet(f"""
            QTextEdit {{
                background-color: transparent;
                border: none;
                padding: 0px;
                margin: 0px;
                color: {color};
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
                font-size: {scaled_pt}pt;
                font-weight: bold;
                selection-background-color: #2563eb;
                selection-color: #ffffff;
            }}
        """)
        pal = self.palette()
        pal.setColor(QPalette.ColorGroup.Inactive, QPalette.ColorRole.Highlight, QColor("#2563eb"))
        pal.setColor(QPalette.ColorGroup.Inactive, QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
        self.setPalette(pal)

    def set_text_color(self, color: QColor):
        """Apply text foreground color to selection (or all text if no selection)."""
        if not color.isValid():
            return
        cursor = self.textCursor()
        fmt = QTextCharFormat()
        fmt.setForeground(color)
        if cursor.hasSelection():
            cursor.mergeCharFormat(fmt)
            cursor.clearSelection()
            self.setTextCursor(cursor)
        else:
            cur = self.textCursor()
            cur.select(QTextCursor.SelectionType.Document)
            cur.mergeCharFormat(fmt)
            cur.clearSelection()
            self.setTextCursor(cur)
            self.mergeCurrentCharFormat(fmt)
        if self.parent_cell:
            self.parent_cell.section_html = self.toHtml()
        self._adjust_size()

    def set_highlight_color(self, color: QColor):
        """Apply background highlight color to selection (or all text if no selection)."""
        cursor = self.textCursor()
        fmt = QTextCharFormat()
        if color.isValid() and color.alpha() > 0:
            fmt.setBackground(color)
        else:
            fmt.setBackground(QBrush(Qt.BrushStyle.NoBrush))
        if cursor.hasSelection():
            cursor.mergeCharFormat(fmt)
            cursor.clearSelection()
            self.setTextCursor(cursor)
        else:
            cur = self.textCursor()
            cur.select(QTextCursor.SelectionType.Document)
            cur.mergeCharFormat(fmt)
            cur.clearSelection()
            self.setTextCursor(cur)
            self.mergeCurrentCharFormat(fmt)
        if self.parent_cell:
            self.parent_cell.section_html = self.toHtml()
        self._adjust_size()

    def clear_text_color(self):
        """Reset text color to default theme color."""
        is_dark = getattr(self.parent_cell, 'theme_mode', 'light') == 'dark' if self.parent_cell else False
        default_fg = QColor('#f8fafc' if is_dark else '#0f172a')
        fmt = QTextCharFormat()
        fmt.setForeground(default_fg)
        cursor = self.textCursor()
        if cursor.hasSelection():
            cursor.mergeCharFormat(fmt)
            cursor.clearSelection()
            self.setTextCursor(cursor)
        else:
            cur = self.textCursor()
            cur.select(QTextCursor.SelectionType.Document)
            cur.mergeCharFormat(fmt)
            cur.clearSelection()
            self.setTextCursor(cur)
            self.mergeCurrentCharFormat(fmt)
        if self.parent_cell:
            self.parent_cell.section_html = self.toHtml()
        self._adjust_size()

    def clear_highlight_color(self):
        """Remove background highlight color."""
        fmt = QTextCharFormat()
        fmt.setBackground(QBrush(Qt.BrushStyle.NoBrush))
        cursor = self.textCursor()
        if cursor.hasSelection():
            cursor.mergeCharFormat(fmt)
            cursor.clearSelection()
            self.setTextCursor(cursor)
        else:
            cur = self.textCursor()
            cur.select(QTextCursor.SelectionType.Document)
            cur.mergeCharFormat(fmt)
            cur.clearSelection()
            self.setTextCursor(cur)
            self.mergeCurrentCharFormat(fmt)
        if self.parent_cell:
            self.parent_cell.section_html = self.toHtml()
        self._adjust_size()

    def set_bold(self, bold: bool):
        cursor = self.textCursor()
        fmt = QTextCharFormat()
        fmt.setFontWeight(QFont.Weight.Bold if bold else QFont.Weight.Normal)
        if cursor.hasSelection():
            cursor.mergeCharFormat(fmt)
            self.setTextCursor(cursor)
        else:
            cur = self.textCursor()
            cur.select(QTextCursor.SelectionType.Document)
            cur.mergeCharFormat(fmt)
            self.mergeCurrentCharFormat(fmt)
        if self.parent_cell:
            self.parent_cell.section_html = self.toHtml()
        self._adjust_size()

    def set_italic(self, italic: bool):
        cursor = self.textCursor()
        fmt = QTextCharFormat()
        fmt.setFontItalic(italic)
        if cursor.hasSelection():
            cursor.mergeCharFormat(fmt)
            self.setTextCursor(cursor)
        else:
            cur = self.textCursor()
            cur.select(QTextCursor.SelectionType.Document)
            cur.mergeCharFormat(fmt)
            self.mergeCurrentCharFormat(fmt)
        if self.parent_cell:
            self.parent_cell.section_html = self.toHtml()
        self._adjust_size()

    def set_underline(self, underline: bool):
        cursor = self.textCursor()
        fmt = QTextCharFormat()
        fmt.setFontUnderline(underline)
        if cursor.hasSelection():
            cursor.mergeCharFormat(fmt)
            self.setTextCursor(cursor)
        else:
            cur = self.textCursor()
            cur.select(QTextCursor.SelectionType.Document)
            cur.mergeCharFormat(fmt)
            self.mergeCurrentCharFormat(fmt)
        if self.parent_cell:
            self.parent_cell.section_html = self.toHtml()
        self._adjust_size()

    def focusInEvent(self, event):
        super().focusInEvent(event)
        if self.parent_cell:
            ws = self.parent_cell._get_worksheet_view()
            if ws:
                ws.active_cell = self.parent_cell
                if not getattr(self.parent_cell, 'is_selected', False):
                    if getattr(ws, 'selected_cells', None) and len(ws.selected_cells) > 0:
                        ws.clear_cell_selection()

    def mousePressEvent(self, event):
        mods = event.modifiers()
        ws = self.parent_cell._get_worksheet_view() if self.parent_cell else None
        if mods & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier):
            if ws:
                ws.select_cell(self.parent_cell, additive=True)
                event.accept()
                return
        elif mods & Qt.KeyboardModifier.ShiftModifier:
            if ws:
                ws.select_cell(self.parent_cell, range_select=True)
                event.accept()
                return
        else:
            if ws:
                ws.active_cell = self.parent_cell
                if getattr(ws, 'selected_cells', None) and len(ws.selected_cells) > 0:
                    ws.clear_cell_selection()
        super().mousePressEvent(event)

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Tab:
            if self.parent_cell:
                self.parent_cell.indent_section()
            event.accept()
            return
        elif event.key() == Qt.Key.Key_Backtab:
            if self.parent_cell:
                self.parent_cell.outdent_section()
            event.accept()
            return
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self.parent_cell:
                ws = self.parent_cell._get_worksheet_view()
                if ws:
                    ws.clear_cell_selection()
                    idx = ws._get_cell_index_by_id(self.parent_cell.cell_id)
                    if idx != -1 and idx + 1 < len(ws.cells):
                        next_c = ws.cells[idx + 1]
                        if not getattr(next_c, 'is_section_header', False) and not next_c.get_input_text():
                            next_c.set_cell_selected(False)
                            next_c.set_cell_focus()
                            event.accept()
                            return
                    cell = ws.insert_cell_below(self.parent_cell.cell_id)
                    if cell:
                        ws.clear_cell_selection()
                        cell.set_cell_selected(False)
                        cell.set_worksheet_mode(ws.is_worksheet_mode)
                        cell.is_inside_section = True
                        cell.section_level = getattr(self.parent_cell, 'section_level', 0)
                        ws.update_section_hierarchy()
                        cell.set_cell_focus()
            event.accept()
            return
        elif event.key() in (Qt.Key.Key_Backspace, Qt.Key.Key_Delete):
            ws = self.parent_cell._get_worksheet_view() if self.parent_cell else None
            if ws and getattr(ws, 'selected_cells', None) and len(ws.selected_cells) > 1 and self.parent_cell in ws.selected_cells:
                ws.delete_selected_cells()
                event.accept()
                return

            has_selection = self.hasSelectedText()
            sel_text = self.selectedText()
            full_text = self.text()
            all_selected = has_selection and (
                len(sel_text) == len(full_text)
                or sel_text.strip() == full_text.strip()
                or not full_text.strip()
            )
            is_empty = not full_text.strip()
            at_start_backspace = (event.key() == Qt.Key.Key_Backspace and self.cursorPosition() == 0 and not has_selection)

            if is_empty or all_selected or at_start_backspace:
                if self.parent_cell:
                    self.parent_cell.deleteRequested.emit(self.parent_cell.cell_id)
                event.accept()
                return

        super().keyPressEvent(event)

    def contextMenuEvent(self, event):
        self.show_context_menu(event.globalPos())
        event.accept()

    def show_context_menu(self, global_pos):
        menu = self.createStandardContextMenu()
        theme_mode = 'light'
        if self.parent_cell:
            theme_mode = getattr(self.parent_cell, 'theme_mode', 'light')
        Theme.apply_menu_style(menu, theme_mode)

        # Hook standard Delete action in the context menu
        for action in menu.actions():
            txt = action.text().replace("&", "").strip().lower()
            if txt in ("delete", "slet"):
                try:
                    action.triggered.disconnect()
                except Exception:
                    pass
                def _on_delete():
                    if not self.text().strip() or (self.hasSelectedText() and (len(self.selectedText()) == len(self.text()) or self.selectedText().strip() == self.text().strip())):
                        if self.parent_cell:
                            self.parent_cell.deleteRequested.emit(self.parent_cell.cell_id)
                    else:
                        self.backspace()
                action.triggered.connect(_on_delete)
                break

        menu.addSeparator()

        ws = self.parent_cell._get_worksheet_view() if self.parent_cell else None
        selected_count = len(getattr(ws, 'selected_cells', [])) if ws else 0
        if selected_count > 1 and ws and self.parent_cell in ws.selected_cells:
            act_del_all = menu.addAction(f"Delete {selected_count} Selected Elements")
            act_del_all.triggered.connect(ws.delete_selected_cells)
        else:
            is_sub = getattr(self.parent_cell, 'section_level', 0) > 0
            del_label = "Delete Subsection" if is_sub else "Delete Section"
            act_del_sec = menu.addAction(del_label)
            if self.parent_cell:
                act_del_sec.triggered.connect(lambda: self.parent_cell.deleteRequested.emit(self.parent_cell.cell_id))

        if self.parent_cell:
            act_indent = menu.addAction("Indent Section (Tab)")
            act_indent.triggered.connect(self.parent_cell.indent_section)
            if getattr(self.parent_cell, 'section_level', 0) > 0:
                act_outdent = menu.addAction("Outdent Section (Shift+Tab)")
                act_outdent.triggered.connect(self.parent_cell.outdent_section)

        menu.exec(global_pos)


class SectionHeaderRow(QWidget):
    """Container widget for section chevron disclosure and title edit."""
    def __init__(self, parent_cell, parent=None):
        super().__init__(parent)
        self.parent_cell = parent_cell

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            ws = self.parent_cell._get_worksheet_view() if self.parent_cell else None
            mods = event.modifiers()
            if ws:
                if mods & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier):
                    ws.select_cell(self.parent_cell, additive=True)
                elif mods & Qt.KeyboardModifier.ShiftModifier:
                    ws.select_cell(self.parent_cell, range_select=True)
                else:
                    ws.clear_cell_selection()
            if hasattr(self.parent_cell, 'title_edit'):
                self.parent_cell.title_edit.setFocus()
        super().mousePressEvent(event)

    def contextMenuEvent(self, event):
        if hasattr(self.parent_cell, 'title_edit'):
            self.parent_cell.title_edit.contextMenuEvent(event)
        else:
            super().contextMenuEvent(event)


class WorksheetCell(QFrame):
    """
    Execution Group.
    Displays prompt '>', editable mathematical formula or text,
    rendered blue mathematical output with equation labels, or embedded plots.
    """
    executeRequested = pyqtSignal(str, str)     # cell_id, expression
    deleteRequested = pyqtSignal(str)           # cell_id
    insertBelowRequested = pyqtSignal(str)      # cell_id
    plotRequested = pyqtSignal(str)             # expression to plot
    focusNextRequested = pyqtSignal(str)        # cell_id
    focusPrevRequested = pyqtSignal(str)        # cell_id
    cellActivated = pyqtSignal(str, str)        # cell_id, expression
    sectionToggled = pyqtSignal(str, bool)      # cell_id, is_collapsed

    # Input modes
    MODE_2D_MATH = "2d_math"
    MODE_1D_MATH = "1d_math"
    MODE_TEXT = "text"
    MODE_NONEXEC_MATH = "nonexec_math"

    def __init__(self, cell_id: str = None, execution_idx: int = 1, theme_mode: str = "light", font_size: int = 14, font_family: str = "Times New Roman", engine=None, parent=None):
        super().__init__(parent)
        self.cell_id = cell_id or str(uuid.uuid4())
        self.execution_idx = execution_idx
        self.theme_mode = theme_mode
        self.current_result: CASResult = None
        self.input_mode = self.MODE_2D_MATH
        self.is_worksheet_mode = False  # Document mode by default (matching reference screenshot)
        self.is_section_header = False
        self.section_title = ""
        self.section_level = 0
        self.is_inside_section = False
        self._is_outside_section = False
        self.is_collapsed = False
        self.section_bg_colors = []
        self.section_html = ""
        self.plot_canvas = None
        self.current_font_size = font_size
        self.current_font_family = font_family
        self.current_line_spacing = 1.0
        self.engine = engine
        self.zoom_factor = 1.0
        self._current_plot_canvas = None
        self.is_editable = True
        self.is_selected = False

        self.setObjectName("cellExecutionGroup")
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setStyleSheet("background-color: transparent;")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        self._init_ui()

    def set_editable(self, editable: bool):
        self.is_editable = editable
        if hasattr(self, 'input_edit') and self.input_edit:
            self.input_edit.set_editable(editable)

    def set_theme_mode(self, mode: str):
        self.theme_mode = mode
        is_dark = (mode == Theme.DARK)
        if hasattr(self, 'lbl_prompt') and self.lbl_prompt:
            prompt_col = Theme.DARK_PROMPT if is_dark else Theme.OPENMATH_PROMPT
            self.lbl_prompt.setStyleSheet(f"color: {prompt_col}; font-weight: bold;")
        if hasattr(self, 'math_renderer') and self.math_renderer:
            self.math_renderer.set_theme_mode(mode)
        if hasattr(self, 'preview_renderer') and self.preview_renderer:
            self.preview_renderer.set_theme_mode(mode)
        if hasattr(self, 'lbl_eq_label') and self.lbl_eq_label:
            eq_col = Theme.DARK_MATH_BLUE if is_dark else Theme.OPENMATH_MATH_BLUE
            self.lbl_eq_label.setStyleSheet(f"color: {eq_col}; font-weight: 500;")
        if hasattr(self, 'title_edit') and self.title_edit and hasattr(self.title_edit, '_update_style'):
            self.title_edit._update_style()
        if hasattr(self, 'input_edit') and self.input_edit and hasattr(self.input_edit, 'update_theme'):
            self.input_edit.update_theme(mode)
        self._update_selection_style()

    def set_cell_selected(self, selected: bool):
        self.is_selected = selected
        self._update_selection_style()
        if hasattr(self, 'input_edit') and self.input_edit:
            if selected:
                self.input_edit.selectAll()
            else:
                cur = self.input_edit.textCursor()
                if cur.hasSelection():
                    cur.clearSelection()
                    self.input_edit.setTextCursor(cur)
        if hasattr(self, 'title_edit') and self.title_edit and getattr(self, 'is_section_header', False):
            if selected:
                self.title_edit.selectAll()
            else:
                self.title_edit.deselect()

    def _update_selection_style(self):
        if getattr(self, 'is_selected', False):
            is_dark = (getattr(self, 'theme_mode', 'light') == 'dark')
            bg = "#1e3a8a" if is_dark else "#e0f2fe"
            border = "#60a5fa" if is_dark else "#38bdf8"
            self.setStyleSheet(f"""
                QFrame#cellExecutionGroup {{
                    background-color: {bg};
                    border: 1.5px solid {border};
                    border-radius: 4px;
                }}
            """)
        else:
            self.setStyleSheet("background-color: transparent;")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            mods = event.modifiers()
            ws = self._get_worksheet_view()
            if ws and (mods & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier)):
                ws.select_cell(self, additive=True)
                event.accept()
                return
            elif ws and (mods & Qt.KeyboardModifier.ShiftModifier):
                ws.select_cell(self, range_select=True)
                event.accept()
                return
            else:
                if ws and getattr(ws, 'selected_cells', None) and len(ws.selected_cells) > 0:
                    ws.clear_cell_selection()

        if not getattr(self, 'is_section_header', False):
            self.input_edit.setFocus()
        else:
            if hasattr(self, 'title_edit'):
                self.title_edit.setFocus()
        super().mousePressEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if getattr(self, 'is_section_header', False) and hasattr(self, 'title_edit') and self.title_edit:
            self.title_edit._adjust_size()

    def wheelEvent(self, event: QWheelEvent):
        if event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier):
            ws = getattr(self, 'parent_worksheet', None)
            if not ws:
                p = self.parent()
                while p:
                    if hasattr(p, 'handle_wheel_zoom'):
                        ws = p
                        break
                    p = p.parent()
            if ws and ws.handle_wheel_zoom(event):
                event.accept()
                return
        ws = getattr(self, 'parent_worksheet', None)
        if not ws:
            p = self.parent()
            while p:
                if hasattr(p, 'scroll_area'):
                    ws = p
                    break
                p = p.parent()
        if ws and hasattr(ws, 'scroll_area'):
            ws.scroll_area.wheelEvent(event)
            event.accept()
            return
        super().wheelEvent(event)

    def _init_ui(self):
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        # Outer layout: Left bracket bar + Group content
        outer_layout = QHBoxLayout(self)
        outer_layout.setContentsMargins(0, 2, 0, 2)
        outer_layout.setSpacing(4)
        outer_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # 1. Left Bracket '['
        self.bracket_bar = CellBracketBar(self)
        outer_layout.addWidget(self.bracket_bar)

        # 2. Content container (Input line + Output area)
        self.content_container = QWidget(self)
        self.content_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        content_layout = QVBoxLayout(self.content_container)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(4)
        content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Section Header Row (Collapsible chevron ▼ / ► + Heading Label)
        self.section_header_row = SectionHeaderRow(self, parent=self.content_container)
        self.section_header_layout = QHBoxLayout(self.section_header_row)
        self.section_header_layout.setContentsMargins(0, 4, 4, 4)
        self.section_header_layout.setSpacing(6)
        self.section_header_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)

        self.btn_section_toggle = SectionDisclosureWidget(is_collapsed=False, parent=self.section_header_row)
        self.btn_section_toggle.clicked.connect(self.toggle_section_collapsed)
        self.section_header_layout.addWidget(self.btn_section_toggle)

        self.title_edit = SectionTitleEdit(self, parent=self.section_header_row)
        self.lbl_section_title = self.title_edit
        self.section_header_layout.addWidget(self.title_edit, 0)
        self.section_header_layout.addStretch()

        content_layout.addWidget(self.section_header_row)
        self.section_header_row.setVisible(False)

        # Input Row (Prompt '>' + Input Editor)
        self.input_row = QWidget(self.content_container)
        input_row_layout = QHBoxLayout(self.input_row)
        input_row_layout.setContentsMargins(0, 0, 0, 0)
        input_row_layout.setSpacing(4)

        self.lbl_prompt = QLabel(">", self.input_row)
        self.lbl_prompt.setFont(QFont("Consolas", 14, QFont.Weight.Bold))
        self.lbl_prompt.setStyleSheet("color: #b22222; font-weight: bold;")
        self.lbl_prompt.setFixedWidth(16)
        self.lbl_prompt.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        input_row_layout.addWidget(self.lbl_prompt)

        self.input_edit = CellInputEdit(self.input_row, parent_cell=self)
        self.input_edit.executeRequested.connect(self.execute)
        self.input_edit.modeToggleRequested.connect(self.toggle_input_mode)
        self.input_edit.navigateUp.connect(lambda: self.focusPrevRequested.emit(self.cell_id))
        self.input_edit.navigateDown.connect(lambda: self.focusNextRequested.emit(self.cell_id))
        self.input_edit.cursorPositionChanged.connect(self._on_cursor_changed)
        self.input_edit.selectionChanged.connect(self._on_cursor_changed)
        input_row_layout.addWidget(self.input_edit, 1)

        content_layout.addWidget(self.input_row)

        # Live 2D Math LaTeX Preview Row (renders textbook math notation as typed)
        self.preview_row = QWidget(self.content_container)
        self.preview_row_layout = QHBoxLayout(self.preview_row)
        self.preview_row_layout.setContentsMargins(20, 2, 16, 2)
        self.preview_row_layout.setSpacing(8)

        self.lbl_preview_badge = QLabel("2D Math", self.preview_row)
        self.lbl_preview_badge.setFixedHeight(18)
        self.lbl_preview_badge.setStyleSheet("""
            QLabel {
                color: #64748b;
                background-color: #e2e8f0;
                border-radius: 3px;
                padding: 1px 5px;
                font-size: 10px;
                font-weight: bold;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif;
            }
        """)
        self.lbl_preview_badge.setVisible(False)
        self.preview_row_layout.addWidget(self.lbl_preview_badge, 0, Qt.AlignmentFlag.AlignVCenter)

        self.preview_renderer = MathRendererWidget("", font_size=15, theme_mode=self.theme_mode, parent=self.preview_row)
        self.preview_row_layout.addWidget(self.preview_renderer, 1)

        content_layout.addWidget(self.preview_row)
        self.preview_row.setVisible(False)

        # Preview debounce timer
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(100)
        self._preview_timer.timeout.connect(self._update_live_preview)
        self.input_edit.textChanged.connect(self._schedule_live_preview)
        self._last_executed_text = None

        # Output Row (Indented/Centered math output + Right-aligned Equation Label + Quick Remove)
        self.output_row = CellOutputBox(self.content_container)
        self.output_row.dismissRequested.connect(self.clear_output)
        self.output_row_layout = QHBoxLayout(self.output_row)
        self.output_row_layout.setContentsMargins(20, 4, 16, 4)
        self.output_row_layout.setSpacing(8)

        # Math Renderer Widget (Displays formula in math blue)
        self.math_renderer = MathRendererWidget("", font_size=15, theme_mode=Theme.LIGHT, parent=self.output_row)
        self.output_row_layout.addWidget(self.math_renderer, 1)

        # Equation Label, e.g. (1), (2), (3)... on the right
        self.lbl_eq_label = QLabel(f"({self.execution_idx})", self.output_row)
        self.lbl_eq_label.setFont(QFont("Times New Roman", 13))
        self.lbl_eq_label.setStyleSheet("color: #0000aa; font-weight: 500;")
        self.lbl_eq_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.output_row_layout.addWidget(self.lbl_eq_label, 0, Qt.AlignmentFlag.AlignRight)

        # Quick remove button '✕' for output
        self.btn_remove_output = QPushButton("✕", self.output_row)
        self.btn_remove_output.setFixedSize(20, 20)
        self.btn_remove_output.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_remove_output.setToolTip("Remove Output (Delete / Backspace)")
        self.btn_remove_output.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #94a3b8;
                border: 1px solid transparent;
                border-radius: 10px;
                font-size: 11px;
                font-weight: bold;
                padding: 0px;
            }
            QPushButton:hover {
                background: #fee2e2;
                border: 1px solid #fca5a5;
                color: #b91c1c;
            }
            QPushButton:pressed {
                background: #fecaca;
            }
        """)
        self.btn_remove_output.clicked.connect(self.clear_output)
        self.output_row_layout.addWidget(self.btn_remove_output, 0, Qt.AlignmentFlag.AlignVCenter)

        content_layout.addWidget(self.output_row)
        self.output_row.setVisible(False)

        # Embedded Plot Container (for polygonOmråde / plot / LPplot)
        self.plot_container = QWidget(self.content_container)
        self.plot_layout = QVBoxLayout(self.plot_container)
        self.plot_layout.setContentsMargins(20, 4, 20, 8)
        self.plot_layout.setSpacing(2)
        def _on_plot_container_press(event):
            if event.button() == Qt.MouseButton.LeftButton:
                ws = self._get_worksheet_view()
                if ws:
                    ws.clear_cell_selection()
                    ws.active_cell = self
                    ws.activeCellChanged.emit(self)
                self.setFocus()
            QWidget.mousePressEvent(self.plot_container, event)
        self.plot_container.mousePressEvent = _on_plot_container_press
        content_layout.addWidget(self.plot_container)
        self.plot_container.setVisible(False)

        # Error Message Box (Selectable and removable)
        self.error_box = CellErrorBox(self.content_container)
        self.error_box.parent_cell = self
        self.error_box.dismissRequested.connect(self.clear_error)
        self.error_box.suggestionApplied.connect(self._on_suggestion_applied)
        content_layout.addWidget(self.error_box)
        self.error_box.setVisible(False)
        self.lbl_error = self.error_box

        outer_layout.addWidget(self.content_container, 1)

        self.set_worksheet_mode(self.is_worksheet_mode)
        self._apply_mode_styling()

    def _on_cursor_changed(self):
        text = self.get_input_text()
        self.cellActivated.emit(self.cell_id, text)
        self._schedule_live_preview()

    def set_worksheet_mode(self, is_ws_mode: bool):
        """Toggle between traditional Worksheet Mode (with '>' prompt) and Document Mode."""
        self.is_worksheet_mode = is_ws_mode
        if not getattr(self, 'is_section_header', False):
            has_img = hasattr(self, 'input_edit') and hasattr(self.input_edit, 'embedded_images') and bool(self.input_edit.embedded_images)
            is_text_or_img = (self.input_mode == self.MODE_TEXT) or has_img
            show_prompt = is_ws_mode and not is_text_or_img
            self.lbl_prompt.setVisible(show_prompt)
            self.bracket_bar.setVisible(show_prompt)
        else:
            self.lbl_prompt.setVisible(False)
            self.bracket_bar.setVisible(False)

    def toggle_section_collapsed(self):
        """Toggle expanded/collapsed state of this section header."""
        if not getattr(self, 'is_section_header', False):
            return
        self.is_collapsed = not getattr(self, 'is_collapsed', False)
        self.btn_section_toggle.set_collapsed(self.is_collapsed)
        self.sectionToggled.emit(self.cell_id, self.is_collapsed)

    def _get_worksheet_view(self):
        ws = getattr(self, 'parent_worksheet', None)
        if ws:
            return ws
        p = self.parent()
        while p:
            if hasattr(p, 'cells') and hasattr(p, 'insert_cell_below'):
                return p
            p = p.parent()
        return None

    def indent_section(self):
        """Increase section level (nest section deeper)."""
        if not getattr(self, 'is_section_header', False):
            return
        self.section_level = getattr(self, 'section_level', 0) + 1
        if hasattr(self, 'title_edit'):
            self.title_edit._update_style()
        self._apply_indentation()
        ws = self._get_worksheet_view()
        if ws and hasattr(ws, 'update_section_hierarchy'):
            ws.update_section_hierarchy()

    def outdent_section(self):
        """Decrease section level (unnest section)."""
        if not getattr(self, 'is_section_header', False):
            return
        if getattr(self, 'section_level', 0) > 0:
            self.section_level -= 1
            if hasattr(self, 'title_edit'):
                self.title_edit._update_style()
            self._apply_indentation()
            ws = self._get_worksheet_view()
            if ws and hasattr(ws, 'update_section_hierarchy'):
                ws.update_section_hierarchy()

    def outdent_cell(self):
        """Outdent statement (exit subsection or section to root)."""
        if getattr(self, 'is_section_header', False):
            self.outdent_section()
            return
        if getattr(self, 'section_level', 0) > 0:
            self.section_level -= 1
        else:
            self.is_inside_section = False
            self.section_level = 0
            self._is_outside_section = True
        self._apply_indentation()
        ws = self._get_worksheet_view()
        if ws and hasattr(ws, 'update_section_hierarchy'):
            ws.update_section_hierarchy()

    def indent_cell(self):
        """Indent statement into section/subsection."""
        if getattr(self, 'is_section_header', False):
            self.indent_section()
            return
        self._is_outside_section = False
        self.is_inside_section = True
        self.section_level = getattr(self, 'section_level', 0) + 1
        self._apply_indentation()
        ws = self._get_worksheet_view()
        if ws and hasattr(ws, 'update_section_hierarchy'):
            ws.update_section_hierarchy()


    def set_cell_focus(self):
        """Focus the editable text area of this cell."""
        try:
            if getattr(self, 'is_section_header', False) and hasattr(self, 'title_edit') and self.title_edit:
                self.title_edit.setFocus()
            elif hasattr(self, 'input_edit') and self.input_edit:
                self.input_edit.setFocus()
        except Exception:
            pass

    def _apply_indentation(self):
        """Apply hierarchical indentation based on section nesting level."""
        lvl = max(0, getattr(self, 'section_level', 0))
        step = 26
        if getattr(self, 'is_section_header', False):
            indent = lvl * step
            self.section_header_layout.setContentsMargins(indent, 4, 4, 4)
            if hasattr(self, 'content_container') and self.content_container.layout():
                self.content_container.layout().setContentsMargins(0, 0, 0, 0)
        else:
            if getattr(self, 'is_inside_section', False):
                indent = (lvl + 1) * step
            else:
                indent = 0
            if hasattr(self, 'content_container') and self.content_container.layout():
                self.content_container.layout().setContentsMargins(indent, 0, 0, 0)

    def _apply_section_header_styling(self):
        """Apply section header visual presentation matching worksheet style."""
        if not getattr(self, 'is_section_header', False):
            self.section_header_row.setVisible(False)
            return

        self.bracket_bar.setVisible(False)
        self.input_row.setVisible(False)
        if hasattr(self, 'preview_row'):
            self.preview_row.setVisible(False)
        if hasattr(self, 'output_row'):
            self.output_row.setVisible(False)
        self.section_header_row.setVisible(True)

        self.btn_section_toggle.set_collapsed(getattr(self, 'is_collapsed', False))
        self._apply_indentation()

        if hasattr(self, 'title_edit'):
            cur_html = getattr(self, 'section_html', '') or ''
            cur_text = getattr(self, 'section_title', '') or ''
            self.title_edit.blockSignals(True)
            if cur_html and '<' in cur_html and '>' in cur_html:
                self.title_edit.setHtml(cur_html)
            elif cur_text:
                self.title_edit.setPlainText(cur_text)
                sec_bgs = getattr(self, 'section_bg_colors', [])
                if sec_bgs:
                    m_col = _parse_worksheet_color(str(sec_bgs[-1]))
                    if m_col:
                        self.title_edit.set_highlight_color(QColor(m_col))
            else:
                self.title_edit.clear()
            self.title_edit.blockSignals(False)
            self.title_edit._update_style()
            self.title_edit._adjust_size()

    def init_section_header_ui(self):
        """Compatibility alias for _apply_section_header_styling."""
        self._apply_section_header_styling()

    def showEvent(self, event):
        super().showEvent(event)
        if hasattr(self, 'input_edit'):
            self.input_edit._adjust_height()

    def toggle_input_mode(self):
        """F5 mode toggle: 2D Math -> 1D Math -> Nonexecutable Math -> Text -> 2D Math."""
        if self.input_mode == self.MODE_2D_MATH:
            new_mode = self.MODE_1D_MATH
        elif self.input_mode == self.MODE_1D_MATH:
            new_mode = self.MODE_NONEXEC_MATH
        elif self.input_mode == self.MODE_NONEXEC_MATH:
            new_mode = self.MODE_TEXT
        else:
            new_mode = self.MODE_2D_MATH
        self.set_input_mode(new_mode)

    def set_input_mode(self, mode: str):
        self.input_mode = mode
        self.input_edit.set_mode(mode)
        self._apply_prompt_styling(mode)
        self._on_cursor_changed()
        self._schedule_live_preview()

    def _schedule_live_preview(self):
        if hasattr(self, '_preview_timer'):
            self._preview_timer.start()

    def _get_block_executable_text(self, block) -> str:
        """Extract executable math text for a specific text block (line)."""
        if not block.isValid():
            return ""
        line_parts = []
        has_executable = False
        it = block.begin()
        prev_level = 0
        while not it.atEnd():
            frag = it.fragment()
            if frag.isValid():
                fmt = frag.charFormat()
                mode = fmt.property(PROP_MODE)
                effective_mode = mode if mode else getattr(self, 'input_mode', self.MODE_2D_MATH)
                if effective_mode in (self.MODE_2D_MATH, self.MODE_1D_MATH):
                    if fmt.isImageFormat():
                        fid = fmt.property(PROP_FRAC_ID)
                        if fid and hasattr(self.input_edit, 'frac_widgets') and fid in self.input_edit.frac_widgets:
                            line_parts.append(self.input_edit.frac_widgets[fid].text_expression())
                        else:
                            expr = fmt.property(PROP_MATH_EXPR)
                            if expr:
                                line_parts.append(str(expr))
                            else:
                                line_parts.append(frag.text())
                        prev_level = 0
                    else:
                        level = fmt.property(PROP_SUBSCRIPT_LEVEL) or 0
                        text = frag.text()
                        if level > 0 and level > prev_level:
                            for _ in range(level - prev_level):
                                line_parts.append("_")
                        line_parts.append(text)
                        prev_level = level
                    has_executable = True
            it += 1
        if not has_executable:
            return ""
        return "".join(line_parts).strip()

    def get_executable_text(self) -> str:
        """
        Extract only executable math portions (2D Math or 1D Math).
        Text written in 'text' mode or 'nonexec_math' mode is excluded.
        If all text is text or non-executable math, returns empty string.
        """
        doc = self.input_edit.document()
        math_lines = []
        has_executable = False

        block = doc.begin()
        while block.isValid():
            line_parts = []
            it = block.begin()
            prev_level = 0
            while not it.atEnd():
                frag = it.fragment()
                if frag.isValid():
                    fmt = frag.charFormat()
                    mode = fmt.property(PROP_MODE)
                    effective_mode = mode if mode else getattr(self, 'input_mode', self.MODE_2D_MATH)
                    if effective_mode in (self.MODE_2D_MATH, self.MODE_1D_MATH):
                        if fmt.isImageFormat():
                            fid = fmt.property(PROP_FRAC_ID)
                            if fid and hasattr(self.input_edit, 'frac_widgets') and fid in self.input_edit.frac_widgets:
                                line_parts.append(self.input_edit.frac_widgets[fid].text_expression())
                                has_executable = True
                            else:
                                expr = fmt.property(PROP_MATH_EXPR)
                                if expr:
                                    line_parts.append(str(expr))
                                    has_executable = True
                                else:
                                    img_name = fmt.toImageFormat().name()
                                    is_embedded_pic = (
                                        hasattr(self.input_edit, 'embedded_images') and
                                        img_name in self.input_edit.embedded_images
                                    ) or frag.text() == '\ufffc'
                                    if not is_embedded_pic:
                                        line_parts.append(frag.text())
                                        has_executable = True
                            prev_level = 0
                        else:
                            level = fmt.property(PROP_SUBSCRIPT_LEVEL) or 0
                            text = frag.text()
                            if level > 0 and level > prev_level:
                                for _ in range(level - prev_level):
                                    line_parts.append("_")
                            line_parts.append(text)
                            prev_level = level
                            has_executable = True
                it += 1
            math_lines.append("".join(line_parts))
            block = block.next()

        if not has_executable:
            return ""

        clean_lines = []
        for line in math_lines:
            s_line = line.strip()
            if not s_line:
                clean_lines.append("")
                continue
            ends_with_colon = s_line.endswith(':')
            ends_with_semicolon = s_line.endswith(';')
            eq_pos = self.input_edit._find_top_level_equal(line) if hasattr(self.input_edit, '_find_top_level_equal') else -1
            if eq_pos != -1 and ':=' not in line[:eq_pos]:
                lhs = line[:eq_pos].strip()
                if ends_with_colon:
                    clean_lines.append(f"{lhs} :")
                elif ends_with_semicolon:
                    clean_lines.append(f"{lhs} ;")
                else:
                    clean_lines.append(lhs)
            else:
                clean_lines.append(line)

        full_text = "\n".join(clean_lines).strip()
        if "= [Plot Object]" in full_text:
            full_text = full_text.replace("= [Plot Object]", "").strip()
        return full_text

    def _update_live_preview(self):
        # Live preview row is disabled as requested ("remove the blue thing that appears")
        if hasattr(self, 'preview_row'):
            self.preview_row.setVisible(False)

    def _apply_prompt_styling(self, mode: str = None):
        if mode is None:
            mode = self.input_mode
        sz = getattr(self, 'current_font_size', 12)
        if not isinstance(sz, int) or sz <= 0:
            sz = 12
        fam = getattr(self, 'current_font_family', "Times New Roman") or "Times New Roman"
        factor = getattr(self, 'zoom_factor', 1.0)
        display_sz = max(4, round(sz * factor))

        has_img = hasattr(self, 'input_edit') and hasattr(self.input_edit, 'embedded_images') and bool(self.input_edit.embedded_images)
        is_text_or_img = (mode == self.MODE_TEXT) or has_img
        if is_text_or_img:
            if hasattr(self, 'lbl_prompt'):
                self.lbl_prompt.setVisible(False)
            if hasattr(self, 'bracket_bar'):
                self.bracket_bar.setVisible(False)
        elif getattr(self, 'is_worksheet_mode', False) and not getattr(self, 'is_section_header', False):
            if hasattr(self, 'lbl_prompt'):
                self.lbl_prompt.setVisible(True)
            if hasattr(self, 'bracket_bar'):
                self.bracket_bar.setVisible(True)

        if mode == self.MODE_2D_MATH:
            prompt_font = QFont(fam, display_sz, QFont.Weight.Bold)
            self.lbl_prompt.setFont(prompt_font)
            self.lbl_prompt.setText(">")
            self.lbl_prompt.setStyleSheet("color: #000000; font-weight: bold;")
            self.lbl_prompt.setFixedWidth(max(14, self.lbl_prompt.fontMetrics().horizontalAdvance("> ") + 2))
        elif mode == self.MODE_NONEXEC_MATH:
            prompt_font = QFont(fam, display_sz)
            self.lbl_prompt.setFont(prompt_font)
            self.lbl_prompt.setText(" ")
            self.lbl_prompt.setStyleSheet("color: #475569; font-weight: normal;")
            self.lbl_prompt.setFixedWidth(max(14, self.lbl_prompt.fontMetrics().horizontalAdvance("> ") + 2))
        elif mode == self.MODE_1D_MATH:
            c_fam = "Courier New" if "Courier" in fam or "Consolas" in fam else fam
            prompt_font = QFont(c_fam, display_sz, QFont.Weight.Bold)
            self.lbl_prompt.setFont(prompt_font)
            self.lbl_prompt.setText(">")
            self.lbl_prompt.setStyleSheet("color: #b22222; font-weight: bold;")
            self.lbl_prompt.setFixedWidth(max(14, self.lbl_prompt.fontMetrics().horizontalAdvance("> ") + 2))
        else:  # Text mode
            prompt_font = QFont(fam, display_sz)
            self.lbl_prompt.setFont(prompt_font)
            self.lbl_prompt.setText(" ")
            self.lbl_prompt.setStyleSheet("color: #475569; font-weight: normal;")
            self.lbl_prompt.setFixedWidth(max(14, self.lbl_prompt.fontMetrics().horizontalAdvance("> ") + 2))

    def _apply_mode_styling(self):
        """Apply font and prompt styling."""
        sz = getattr(self, 'current_font_size', 12)
        if not isinstance(sz, int) or sz <= 0:
            sz = 12
        fam = getattr(self, 'current_font_family', "Times New Roman") or "Times New Roman"
        factor = getattr(self, 'zoom_factor', 1.0)
        display_sz = max(4, round(sz * factor))

        self.input_edit.setFont(QFont(fam, display_sz))
        self.input_edit.update_font_scaling()
        self._apply_prompt_styling(self.input_mode)

    def set_font_size(self, size: int):
        try:
            val = int(size)
            if val <= 0:
                val = 12
        except (ValueError, TypeError):
            val = 12
        self.current_font_size = max(1, val)  # Guard: Qt requires point size > 0
        if hasattr(self, 'input_edit') and self.input_edit:
            self.input_edit.set_font_size(self.current_font_size)
        else:
            self._apply_mode_styling()
        factor = getattr(self, 'zoom_factor', 1.0)
        if hasattr(self, 'math_renderer') and self.math_renderer:
            self.math_renderer.set_font_size(max(10, self.current_font_size + 3))
            self.math_renderer.set_zoom_factor(factor)
        if hasattr(self, 'preview_renderer') and self.preview_renderer:
            self.preview_renderer.set_font_size(max(10, self.current_font_size + 3))
            self.preview_renderer.set_zoom_factor(factor)
        self.updateGeometry()

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            ws = self._get_worksheet_view()
            if ws:
                ws.clear_cell_selection()
                cell = ws.insert_cell_below(self.cell_id)
                if cell:
                    cell.set_cell_focus()
                    event.accept()
                    return
        super().keyPressEvent(event)

    def set_line_spacing(self, spacing: float):
        try:
            val = float(spacing)
            if val <= 0.1:
                val = 1.0
        except (ValueError, TypeError):
            val = 1.0
        self.current_line_spacing = val
        if hasattr(self, 'input_edit') and self.input_edit:
            self.input_edit.set_line_spacing(val)

    def set_zoom_factor(self, factor: float):
        """Update visual zoom scaling without altering the underlying font size property."""
        self.zoom_factor = max(0.25, min(5.0, factor))
        self._apply_mode_styling()
        if hasattr(self, 'math_renderer') and self.math_renderer:
            self.math_renderer.set_font_size(max(10, self.current_font_size + 3))
            self.math_renderer.set_zoom_factor(self.zoom_factor)
        if hasattr(self, 'preview_renderer') and self.preview_renderer:
            self.preview_renderer.set_font_size(max(10, self.current_font_size + 3))
            self.preview_renderer.set_zoom_factor(self.zoom_factor)
        if hasattr(self, 'lbl_eq_label') and self.lbl_eq_label:
            fam = getattr(self, 'current_font_family', "Times New Roman") or "Times New Roman"
            self.lbl_eq_label.setFont(QFont(fam, max(4, round(11 * self.zoom_factor))))
        if hasattr(self, 'error_box') and self.error_box:
            self.error_box.setFont(QFont("Consolas", max(4, round(11 * self.zoom_factor)), QFont.Weight.Bold))
        if hasattr(self, '_current_plot_canvas') and self._current_plot_canvas:
            self._current_plot_canvas.setFixedSize(int(380 * self.zoom_factor), int(320 * self.zoom_factor))
        self.updateGeometry()

    def set_font_family(self, family: str):
        self.current_font_family = family
        self._apply_mode_styling()

    def set_bold(self, bold: bool):
        if getattr(self, 'is_section_header', False) and hasattr(self, 'title_edit'):
            self.title_edit.set_bold(bold)
        else:
            self.input_edit.set_bold(bold)

    def set_italic(self, italic: bool):
        if getattr(self, 'is_section_header', False) and hasattr(self, 'title_edit'):
            self.title_edit.set_italic(italic)
        else:
            self.input_edit.set_italic(italic)

    def set_underline(self, underline: bool):
        if getattr(self, 'is_section_header', False) and hasattr(self, 'title_edit'):
            self.title_edit.set_underline(underline)
        else:
            self.input_edit.set_underline(underline)

    def set_text_color(self, color: 'QColor'):
        if getattr(self, 'is_section_header', False) and hasattr(self, 'title_edit'):
            self.title_edit.set_text_color(color)
        else:
            self.input_edit.set_text_color(color)

    def set_highlight_color(self, color: 'QColor'):
        if getattr(self, 'is_section_header', False) and hasattr(self, 'title_edit'):
            self.title_edit.set_highlight_color(color)
        else:
            self.input_edit.set_highlight_color(color)

    def clear_text_color(self):
        if getattr(self, 'is_section_header', False) and hasattr(self, 'title_edit'):
            self.title_edit.clear_text_color()
        else:
            self.input_edit.clear_text_color()

    def clear_highlight_color(self):
        if getattr(self, 'is_section_header', False) and hasattr(self, 'title_edit'):
            self.title_edit.clear_highlight_color()
        else:
            self.input_edit.clear_highlight_color()

    def set_execution_idx(self, idx: int):
        self.execution_idx = idx
        self.lbl_eq_label.setText(f"({idx})")

    def set_input_text(self, text: str):
        if self.input_mode == self.MODE_2D_MATH and ('/' in text or r'\frac{' in text):
            self.input_edit.set_spans([{'type': 'text', 'text': text, 'mode': self.MODE_2D_MATH}])
        elif self.input_mode == self.MODE_2D_MATH and re.search(r'\b[a-zA-Z][a-zA-Z0-9]*(?:_[a-zA-Z0-9_]+)+\b', text):
            self.input_edit.set_stepped_math_text(text)
        else:
            self.input_edit.setPlainText(text)

    def get_input_text(self) -> str:
        if hasattr(self.input_edit, 'get_plain_or_math_text'):
            return self.input_edit.get_plain_or_math_text().strip()
        return self.input_edit.toPlainText().strip()

    @staticmethod
    def _parse_fraction_template(text: str):
        """Parse formula templates that contain a fraction into (pre, num, den, post) components."""
        s = text.strip()
        if s.startswith(('plot(', 'plot3d(', 'implicitplot(', 'LPplot(', 'polygonOmråde(',
                         'solve(', 'diff(', 'integrate(', 'taylor(', 'limit(',
                         'rc_cutoff(', 'voltage_divider(', 'to_bin(', 'to_hex(',
                         'two_comp_repr(', 'extract_bitfield(', 'bit_set(', 'bit_clear(',
                         'bit_toggle(', 'adc_volt_to_count(', 'adc_count_to_volt(',
                         'uart_baud_rate(', 'timer_arr_prescaler(')):
            return None

        # Case 1: (num) / (den) with optional pre and post
        # e.g., R_eq := (R_1 · R_2) / (R_1 + R_2)
        m = re.search(r'^(.*?)\s*\(([^()]+)\)\s*/\s*\(([^()]+)\)\s*(.*?)$', s)
        if m:
            return (m.group(1).strip(), m.group(2).strip(), m.group(3).strip(), m.group(4).strip())

        # Case 2: (num / den) in parens, e.g. E := (1/2) · C · V²
        m = re.search(r'^(.*?)\s*\(([0-9a-zA-Z_.]+)\s*/\s*([0-9a-zA-Z_.]+)\)\s*(.*?)$', s)
        if m:
            return (m.group(1).strip(), m.group(2).strip(), m.group(3).strip(), m.group(4).strip())

        # Case 3: num / (den), e.g. XC := 1 / (2 · π · f · C)
        m = re.search(r'^(.*?)\s*([0-9a-zA-Z_.]+)\s*/\s*\(([^()]+)\)\s*(.*?)$', s)
        if m:
            return (m.group(1).strip(), m.group(2).strip(), m.group(3).strip(), m.group(4).strip())

        # Case 4: (num) / den, e.g. (x + 1) / 2
        m = re.search(r'^(.*?)\s*\(([^()]+)\)\s*/\s*([0-9a-zA-Z_.]+)\s*(.*?)$', s)
        if m:
            return (m.group(1).strip(), m.group(2).strip(), m.group(3).strip(), m.group(4).strip())

        return None

    def insert_template(self, text: str):
        if not getattr(self, 'is_editable', True):
            return
        import re

        focus_w = QApplication.focusWidget()
        slot = None
        w = focus_w
        while w:
            try:
                if sip.isdeleted(w):
                    break
                if isinstance(w, FractionSlot):
                    slot = w
                    break
                w = w.parent() if hasattr(w, 'parent') else None
            except Exception:
                break

        if slot is not None:
            try:
                if sip.isdeleted(slot):
                    slot = None
                else:
                    top_frac = slot.parent_frac.get_top_fraction() if (hasattr(slot, 'parent_frac') and slot.parent_frac) else None
                    if top_frac is None or sip.isdeleted(top_frac):
                        slot = None
                    elif hasattr(self.input_edit, 'frac_widgets') and top_frac not in self.input_edit.frac_widgets.values():
                        slot = None
            except Exception:
                slot = None
            if slot is None:
                focus_w = None

        if slot is None and hasattr(self.input_edit, 'frac_widgets'):
            for fw in list(self.input_edit.frac_widgets.values()):
                try:
                    if isinstance(fw, FractionWidget) and not sip.isdeleted(fw):
                        slot_found = fw.get_focused_slot()
                        if slot_found is not None and not sip.isdeleted(slot_found):
                            slot = slot_found
                            focus_w = slot.first_edit()
                            break
                except Exception:
                    continue

        if slot is None and hasattr(self.input_edit, '_active_fraction_slot'):
            candidate = self.input_edit._active_fraction_slot
            if candidate is not None:
                try:
                    if sip.isdeleted(candidate):
                        self.input_edit._active_fraction_slot = None
                    else:
                        top_frac = candidate.parent_frac.get_top_fraction() if candidate.parent_frac else None
                        if top_frac is None or sip.isdeleted(top_frac):
                            self.input_edit._active_fraction_slot = None
                        elif hasattr(self.input_edit, 'frac_widgets') and top_frac not in self.input_edit.frac_widgets.values():
                            self.input_edit._active_fraction_slot = None
                        else:
                            slot = candidate
                            focus_w = slot.first_edit()
                except Exception:
                    self.input_edit._active_fraction_slot = None

        # Check if text is a matrix definition or matrix template (e.g. Matrix([[...]]) or A := Matrix([[...]]))
        stripped_t = text.strip()
        if ':=' in stripped_t and 'Matrix(' in stripped_t:
            parts = stripped_t.split(':=', 1)
            assign_lhs = parts[0].strip()
            mat_data = parse_matrix_string(parts[1])
            if mat_data:
                cursor = self.input_edit.textCursor()
                if cursor.hasSelection():
                    cursor.removeSelectedText()
                fmt = self.input_edit._get_char_format_for_mode(self.input_edit.current_typing_mode)
                cursor.insertText(f"{assign_lhs} := ", fmt)
                self.input_edit.setTextCursor(cursor)
                self.input_edit.insert_matrix_widget(data=mat_data, focus_target="first")
                if hasattr(self, 'preview_row'):
                    self.preview_row.setVisible(False)
                return

        if stripped_t.startswith("Matrix(") or stripped_t.startswith(r"\begin{bmatrix}") or stripped_t.startswith(r"\begin{matrix}"):
            mat_data = parse_matrix_string(stripped_t)
            if mat_data and len(mat_data) > 0 and len(mat_data[0]) > 0:
                cursor = self.input_edit.textCursor()
                if cursor.hasSelection():
                    cursor.removeSelectedText()
                    self.input_edit.setTextCursor(cursor)
                self.input_edit.insert_matrix_widget(data=mat_data, focus_target="first")
                if hasattr(self, 'preview_row'):
                    self.preview_row.setVisible(False)
                return

        if text in (r"\frac{a}{b}", "a/b", "(a)/(b)"):

            if slot is not None and not sip.isdeleted(slot):
                if focus_w is None or sip.isdeleted(focus_w):
                    focus_w = slot.first_edit()
                if focus_w is not None and not sip.isdeleted(focus_w):
                    sel = focus_w.selectedText().strip() if hasattr(focus_w, 'selectedText') else ""
                    cur_text = focus_w.text().strip() if hasattr(focus_w, 'text') else ""
                    num = sel if sel else (cur_text if cur_text and cur_text not in ("a", "b") else "a")
                    if isinstance(focus_w, (QLineEdit, QTextEdit)) and focus_w in slot.items:
                        nested = slot.insert_fraction_at(focus_w, num=num, den="b")
                    else:
                        nested = slot.convert_to_fraction(num=num, den="b")
                    if nested and not sip.isdeleted(nested) and nested.den_edit and not sip.isdeleted(nested.den_edit):
                        nested.den_edit.setFocus()
                        nested.den_edit.selectAll()
                    if hasattr(self, 'preview_row'):
                        self.preview_row.setVisible(False)
                    return

            cursor = self.input_edit.textCursor()
            if cursor.hasSelection():
                sel = self.input_edit._get_selected_math_text(cursor)
                cursor.removeSelectedText()
                self.input_edit.setTextCursor(cursor)
            else:
                sel = ""
            num = sel if sel else "a"
            den = "b"
            self.input_edit.insert_fraction_widget(num, den, focus_target="den" if sel else "num")
            if hasattr(self, 'preview_row'):
                self.preview_row.setVisible(False)
            return

        frac_parts = self._parse_fraction_template(text)
        if frac_parts is not None and slot is None:
            pre, num, den, post = frac_parts
            cursor = self.input_edit.textCursor()
            if cursor.hasSelection():
                cursor.removeSelectedText()
                self.input_edit.setTextCursor(cursor)

            fmt = self.input_edit._get_char_format_for_mode(self.input_edit.current_typing_mode)

            def _fmt_math(s: str) -> str:
                if not s:
                    return ""
                s = format_subscripts_and_superscripts(s)
                s = re.sub(r'(?<=[a-zA-Z0-9_\)\]\}])\s*(?<!\*)\*(?!\*)\s*(?=[a-zA-Z0-9_\(\[\{])', ' · ', s)
                s = s.replace(' * ', ' · ')
                return s

            if pre:
                pre_fmt = _fmt_math(pre.strip())
                cursor = self.input_edit.textCursor()
                cursor.insertText(pre_fmt + " ", fmt)
                self.input_edit.setTextCursor(cursor)

            num_fmt = _fmt_math(num)
            den_fmt = _fmt_math(den)

            self.input_edit.insert_fraction_widget(num_fmt, den_fmt, focus_target="after")

            if post:
                post_fmt = _fmt_math(post.strip())
                cur_after = self.input_edit.textCursor()
                cur_after.insertText(" " + post_fmt, fmt)
                self.input_edit.setTextCursor(cur_after)

            self.input_edit.setFocus()
            if hasattr(self, 'preview_row'):
                self.preview_row.setVisible(False)
            return

        if text in ("a^b", "aᵇ"):
            cursor = self.input_edit.textCursor()
            sel = cursor.selectedText().strip()
            if cursor.hasSelection():
                cursor.removeSelectedText()
            inserted = f"{sel}ᵇ" if sel else "aᵇ"
            cursor.insertText(inserted)
            # Select the 'ᵇ' exponent placeholder so user can immediately type the power
            pos = cursor.position()
            cursor.setPosition(pos - 1)
            cursor.setPosition(pos, QTextCursor.MoveMode.KeepAnchor)
            self.input_edit.setTextCursor(cursor)
            self.input_edit.setFocus()
            if hasattr(self, 'preview_row'):
                self.preview_row.setVisible(False)
            return

        if text in (r"a_n", "a_n", "a[n]", "aₙ"):
            cursor = self.input_edit.textCursor()
            sel = cursor.selectedText().strip()
            if cursor.hasSelection():
                cursor.removeSelectedText()
            inserted = f"{sel}ₙ" if sel else "aₙ"
            cursor.insertText(inserted)
            # Select the 'ₙ' subscript placeholder so user can immediately type the index
            pos = cursor.position()
            cursor.setPosition(pos - 1)
            cursor.setPosition(pos, QTextCursor.MoveMode.KeepAnchor)
            self.input_edit.setTextCursor(cursor)
            self.input_edit.setFocus()
            if hasattr(self, 'preview_row'):
                self.preview_row.setVisible(False)
            return

        if text in (r"\frac{d}{dx}f", "d/dx(f)", "d/dx f", "diff(f, x)"):
            cursor = self.input_edit.textCursor()
            sel = cursor.selectedText().strip()
            if cursor.hasSelection():
                cursor.removeSelectedText()
                self.input_edit.setTextCursor(cursor)
            expr_to_diff = sel if sel else "f"
            self.input_edit.insert_fraction_widget("d", "dx", focus_target="after")
            cur_after = self.input_edit.textCursor()
            p_start = cur_after.position()
            cur_after.insertText(f" ({expr_to_diff})")
            if not sel:
                cur_after.setPosition(p_start + 2)
                cur_after.setPosition(p_start + 3, QTextCursor.MoveMode.KeepAnchor)
                self.input_edit.setTextCursor(cur_after)
            self.input_edit.setFocus()
            if hasattr(self, 'preview_row'):
                self.preview_row.setVisible(False)
            return

        if text in (r"\sqrt{a}", "sqrt(a)", "√(a)", "√a"):
            if slot is not None and not sip.isdeleted(slot):
                if focus_w is None or sip.isdeleted(focus_w):
                    focus_w = slot.first_edit()
                if focus_w is not None and not sip.isdeleted(focus_w):
                    sel = focus_w.selectedText().strip() if hasattr(focus_w, 'selectedText') else ""
                    cur_text = focus_w.text().strip() if hasattr(focus_w, 'text') else ""
                    arg = sel if sel else (cur_text if cur_text and cur_text not in ("a", "b") else "a")
                    slot.insert_radical_at(focus_w, radicand=arg, degree=None)
                    if hasattr(self, 'preview_row'):
                        self.preview_row.setVisible(False)
                    return
            cursor = self.input_edit.textCursor()
            if cursor.hasSelection():
                sel = self.input_edit._get_selected_math_text(cursor)
                cursor.removeSelectedText()
                self.input_edit.setTextCursor(cursor)
            else:
                sel = ""
            arg = sel if sel else "a"
            self.input_edit.insert_radical_widget(radicand=arg, degree=None, focus_target="rad")
            if hasattr(self, 'preview_row'):
                self.preview_row.setVisible(False)
            return

        if text in (r"\sqrt[n]{a}", "root(a, n)", "ⁿ√(a)", "ⁿ√a"):
            if slot is not None and not sip.isdeleted(slot):
                if focus_w is None or sip.isdeleted(focus_w):
                    focus_w = slot.first_edit()
                if focus_w is not None and not sip.isdeleted(focus_w):
                    sel = focus_w.selectedText().strip() if hasattr(focus_w, 'selectedText') else ""
                    cur_text = focus_w.text().strip() if hasattr(focus_w, 'text') else ""
                    arg = sel if sel else (cur_text if cur_text and cur_text not in ("a", "b") else "a")
                    slot.insert_radical_at(focus_w, radicand=arg, degree="n")
                    if hasattr(self, 'preview_row'):
                        self.preview_row.setVisible(False)
                    return
            cursor = self.input_edit.textCursor()
            if cursor.hasSelection():
                sel = self.input_edit._get_selected_math_text(cursor)
                cursor.removeSelectedText()
                self.input_edit.setTextCursor(cursor)
            else:
                sel = ""
            arg = sel if sel else "a"
            self.input_edit.insert_radical_widget(radicand=arg, degree="n", focus_target="deg" if not sel else "rad")
            if hasattr(self, 'preview_row'):
                self.preview_row.setVisible(False)
            return

        if text in (r"\log_{10}(a)", "log(a, 10)", "log₁₀(a)"):
            cursor = self.input_edit.textCursor()
            sel = cursor.selectedText().strip()
            if cursor.hasSelection():
                cursor.removeSelectedText()
            arg = sel if sel else "a"
            pos_before = cursor.position()
            cursor.insertText(f"log₁₀({arg})")
            if not sel:
                cursor.setPosition(pos_before + 6)
                cursor.setPosition(pos_before + 7, QTextCursor.MoveMode.KeepAnchor)
            self.input_edit.setTextCursor(cursor)
            self.input_edit.setFocus()
            if hasattr(self, 'preview_row'):
                self.preview_row.setVisible(False)
            return

        if text in ("e^a", "eᵃ", "exp(a)"):
            cursor = self.input_edit.textCursor()
            sel = cursor.selectedText().strip()
            if cursor.hasSelection():
                cursor.removeSelectedText()
            if sel:
                sup_sel = ''.join(SUPER_MAP.get(c, c) for c in sel)
                inserted = f"e{sup_sel}"
                cursor.insertText(inserted)
            else:
                inserted = "eᵃ"
                cursor.insertText(inserted)
                pos = cursor.position()
                cursor.setPosition(pos - 1)
                cursor.setPosition(pos, QTextCursor.MoveMode.KeepAnchor)
            self.input_edit.setTextCursor(cursor)
            self.input_edit.setFocus()
            if hasattr(self, 'preview_row'):
                self.preview_row.setVisible(False)
            return

        if text in ("|a|", "abs(a)"):
            cursor = self.input_edit.textCursor()
            sel = cursor.selectedText().strip()
            if cursor.hasSelection():
                cursor.removeSelectedText()
            inserted = f"|{sel}|" if sel else "|a|"
            cursor.insertText(inserted)
            if not sel:
                pos = cursor.position()
                cursor.setPosition(pos - 2)
                cursor.setPosition(pos - 1, QTextCursor.MoveMode.KeepAnchor)
            self.input_edit.setTextCursor(cursor)
            self.input_edit.setFocus()
            if hasattr(self, 'preview_row'):
                self.preview_row.setVisible(False)
            return

        if text in ("f : x -> y", "f : x \to y", "f := (x) -> y", "f := x -> y"):
            cursor = self.input_edit.textCursor()
            sel = cursor.selectedText().strip()
            if cursor.hasSelection():
                cursor.removeSelectedText()
            inserted = f"f : x -> {sel}" if sel else "f : x -> y"
            cursor.insertText(inserted)
            if not sel:
                pos = cursor.position()
                cursor.setPosition(pos - 1)
                cursor.setPosition(pos, QTextCursor.MoveMode.KeepAnchor)
            self.input_edit.setTextCursor(cursor)
            self.input_edit.setFocus()
            if hasattr(self, 'preview_row'):
                self.preview_row.setVisible(False)
            return

        if text in (r"\sum_{k=1}^n f", r"\sum f", "Sum(f, (i, k, n))", "∑(f, k = 1..n)", "∑ f"):
            cursor = self.input_edit.textCursor()
            sel = cursor.selectedText().strip()
            if cursor.hasSelection():
                cursor.removeSelectedText()
                self.input_edit.setTextCursor(cursor)
            integrand = sel if sel else "f"
            self.input_edit.insert_big_operator_widget(op_symbol="∑", top="n", bottom="k = 1", body=integrand, focus_target="body" if not sel else "bottom")
            if hasattr(self, 'preview_row'):
                self.preview_row.setVisible(False)
            return

        if text in (r"\prod_{k=1}^n f", r"\prod f", "Product(f, (i, k, n))", "∏(f, k = 1..n)", "∏ f"):
            cursor = self.input_edit.textCursor()
            sel = cursor.selectedText().strip()
            if cursor.hasSelection():
                cursor.removeSelectedText()
                self.input_edit.setTextCursor(cursor)
            integrand = sel if sel else "f"
            self.input_edit.insert_big_operator_widget(op_symbol="∏", top="n", bottom="k = 1", body=integrand, focus_target="body" if not sel else "bottom")
            if hasattr(self, 'preview_row'):
                self.preview_row.setVisible(False)
            return

        if text in (r"\int f\,dx", "integrate(f, x)", "∫(f) dx", "∫ f dx"):
            cursor = self.input_edit.textCursor()
            sel = cursor.selectedText().strip()
            if cursor.hasSelection():
                cursor.removeSelectedText()
            integrand = sel if sel else "f"
            pos_before = cursor.position()
            cursor.insertText(f"∫({integrand}) dx")
            if not sel:
                cursor.setPosition(pos_before + 2)
                cursor.setPosition(pos_before + 3, QTextCursor.MoveMode.KeepAnchor)
            self.input_edit.setTextCursor(cursor)
            self.input_edit.setFocus()
            if hasattr(self, 'preview_row'):
                self.preview_row.setVisible(False)
            return

        if text in (r"\int_a^b f", r"\int_a^b f(x)\,dx", "integrate(f, (x, a, b))", "∫(f, x = a..b)", "∫(f(x), x = a..b)", "∫_a^b f", "∫_a^b f(x) dx"):
            cursor = self.input_edit.textCursor()
            sel = cursor.selectedText().strip()
            if cursor.hasSelection():
                cursor.removeSelectedText()
                self.input_edit.setTextCursor(cursor)
            integrand = sel if sel else ("f(x)" if "f(x)" in text else "f")
            show_diff = ("dx" in text or "f(x)" in text)
            self.input_edit.insert_definite_integral_widget(
                a="a",
                b="b",
                f=integrand,
                show_differential=show_diff,
                focus_target="a" if sel else "f"
            )
            if hasattr(self, 'preview_row'):
                self.preview_row.setVisible(False)
            return

        if text in (r"f|_{x=a}", "eval(f, x = a)", "f|x=a"):
            cursor = self.input_edit.textCursor()
            sel = cursor.selectedText().strip()
            if cursor.hasSelection():
                cursor.removeSelectedText()
                self.input_edit.setTextCursor(cursor)
            f_expr = sel if sel else "f"
            self.input_edit.insert_eval_bar_widget(f=f_expr, cond="x = a", focus_target="cond" if sel else "cond")
            if hasattr(self, 'preview_row'):
                self.preview_row.setVisible(False)
            return

        if text in (r"\binom{n}{k}", "binomial(n, k)", "binom(n, k)", "binom(n,k)"):
            cursor = self.input_edit.textCursor()
            sel = cursor.selectedText().strip()
            if cursor.hasSelection():
                cursor.removeSelectedText()
                self.input_edit.setTextCursor(cursor)
            top_val = sel if sel else "n"
            self.input_edit.insert_binomial_widget(top=top_val, bot="k", focus_target="bot" if sel else "top")
            if hasattr(self, 'preview_row'):
                self.preview_row.setVisible(False)
            return

        if text in (r"\left\{ \begin{matrix} a \\ b \end{matrix} \right.", r"\begin{cases} a \\ b \end{cases}", "piecewise(x < 0, -x, x)", "piecewise"):
            cursor = self.input_edit.textCursor()
            sel = cursor.selectedText().strip()
            if cursor.hasSelection():
                cursor.removeSelectedText()
                self.input_edit.setTextCursor(cursor)
            e1 = sel if sel else "-x"
            self.input_edit.insert_piecewise_widget(expr1=e1, cond1="x < 0", expr2="x", cond2="otherwise", focus_target="expr1")
            if hasattr(self, 'preview_row'):
                self.preview_row.setVisible(False)
            return

        if text in (r"\lim_{x \to a^-}", "limit(f, x = a, dir='-')"):
            cursor = self.input_edit.textCursor()
            sel = cursor.selectedText().strip()
            if cursor.hasSelection():
                cursor.removeSelectedText()
                self.input_edit.setTextCursor(cursor)
            body = sel if sel else "f"
            self.input_edit.insert_limit_widget(target="x → a⁻", body=body, direction="-", focus_target="target" if sel else "body")
            if hasattr(self, 'preview_row'):
                self.preview_row.setVisible(False)
            return

        if text in (r"\lim_{x \to a^+}", "limit(f, x = a, dir='+')"):
            cursor = self.input_edit.textCursor()
            sel = cursor.selectedText().strip()
            if cursor.hasSelection():
                cursor.removeSelectedText()
                self.input_edit.setTextCursor(cursor)
            body = sel if sel else "f"
            self.input_edit.insert_limit_widget(target="x → a⁺", body=body, direction="+", focus_target="target" if sel else "body")
            if hasattr(self, 'preview_row'):
                self.preview_row.setVisible(False)
            return

        if text in (r"\lim_{x \to a} f(x)", "limit(f(x), x, a)", "limit(f, x, a)", r"\lim_{x \to a}"):
            cursor = self.input_edit.textCursor()
            sel = cursor.selectedText().strip()
            if cursor.hasSelection():
                cursor.removeSelectedText()
                self.input_edit.setTextCursor(cursor)
            body = sel if sel else ("f(x)" if "f(x)" in text else "f")
            self.input_edit.insert_limit_widget(target="x → a", body=body, direction="", focus_target="target" if sel else "body")
            if hasattr(self, 'preview_row'):
                self.preview_row.setVisible(False)
            return

        if text in (r"\begin{pmatrix} a \\ b \end{pmatrix}", r"\begin{bmatrix} a \\ b \end{bmatrix}", "Vector([a, b])", "Vector([a,b])"):
            cursor = self.input_edit.textCursor()
            sel = cursor.selectedText().strip()
            if cursor.hasSelection():
                cursor.removeSelectedText()
                self.input_edit.setTextCursor(cursor)
            r1 = sel if sel else "a"
            self.input_edit.insert_vector_widget(r1=r1, r2="b", focus_target="r2" if sel else "r1")
            if hasattr(self, 'preview_row'):
                self.preview_row.setVisible(False)
            return

        if text in (r"\frac{d^2}{dx^2}f(x)", "diff(f(x), x, 2)", "d²/dx²(f(x))", "d²/dx² f(x)"):
            cursor = self.input_edit.textCursor()
            sel = cursor.selectedText().strip()
            if cursor.hasSelection():
                cursor.removeSelectedText()
                self.input_edit.setTextCursor(cursor)
            expr_to_diff = sel if sel else "f(x)"
            self.input_edit.insert_fraction_widget("d²", "dx²", focus_target="after")
            cur_after = self.input_edit.textCursor()
            p_start = cur_after.position()
            cur_after.insertText(f" ({expr_to_diff})")
            if not sel:
                cur_after.setPosition(p_start + 2)
                cur_after.setPosition(p_start + 6, QTextCursor.MoveMode.KeepAnchor)
                self.input_edit.setTextCursor(cur_after)
            self.input_edit.setFocus()
            if hasattr(self, 'preview_row'):
                self.preview_row.setVisible(False)
            return

        if focus_w and isinstance(focus_w, QLineEdit) and not sip.isdeleted(focus_w):
            f_text = focus_w.text()
            f_sel = focus_w.selectedText()
            to_insert = text
            if to_insert.startswith(" "):
                if f_sel:
                    to_insert = f"{f_sel}{to_insert}"
                else:
                    f_pos = focus_w.cursorPosition()
                    if f_pos == 0 or (f_pos <= len(f_text) and (f_text[f_pos - 1].isspace() or f_text[f_pos - 1] in "([{,;:=/*+-·⋅")):
                        to_insert = to_insert.lstrip()
            focus_w.insert(to_insert)
            if hasattr(self, 'preview_row'):
                self.preview_row.setVisible(False)
            return

        cursor = self.input_edit.textCursor()
        sel = cursor.selectedText().strip()

        if self.input_mode == self.MODE_2D_MATH:
            import re
            has_stepped = bool(re.search(r'\b[a-zA-Z][a-zA-Z0-9]*(?:_[a-zA-Z0-9_]+)+\b', text))
            if has_stepped:
                if sel and text.startswith("⟦a⟧"):
                    text = f"{sel}{text[len('⟦a⟧'):]}"
                if cursor.hasSelection():
                    cursor.removeSelectedText()
                self.input_edit.insert_stepped_math_text(text, cursor)
                self.input_edit.setFocus()
                self.input_edit._select_next_placeholder()
                if hasattr(self, 'preview_row'):
                    self.preview_row.setVisible(False)
                return

            text = format_subscripts_and_superscripts(text)
            text = re.sub(r'(?<=[a-zA-Z0-9_\)\]\}])\s*(?<!\*)\*(?!\*)\s*(?=[a-zA-Z0-9_\(\[\{])', ' · ', text)
            text = re.sub(r'^\*\s*', '· ', text)
            text = re.sub(r'\s*\*\s*$', ' ·', text)
            text = text.replace(' * ', ' · ')

        if text.startswith(" "):
            if sel:
                text = f"{sel}{text}"
            else:
                pos = cursor.position()
                if pos == 0:
                    text = text.lstrip()
                else:
                    doc_text = self.input_edit.toPlainText()
                    if pos <= len(doc_text):
                        prev_char = doc_text[pos - 1]
                        if prev_char.isspace() or prev_char in "([{,;:=/*+-·⋅":
                            text = text.lstrip()
        elif sel:
            if text.startswith("⟦a⟧"):
                text = f"{sel}{text[len('⟦a⟧'):]}"
            elif text.startswith("a^"):
                text = f"{sel}^{text[2:]}"
            elif text.startswith("aᵇ"):
                text = f"{sel}ᵇ{text[len('aᵇ'):]}"
            elif text.startswith("a/"):
                text = f"({sel})/{text[2:]}"
            elif text == "sqrt(a)":
                text = f"sqrt({sel})"
            elif text == "a!":
                text = f"({sel})!"
            elif text == "abs(a)":
                text = f"abs({sel})"
            elif text.startswith("a + "):
                text = f"{sel} + {text[4:]}"
            elif text.startswith("a - "):
                text = f"{sel} - {text[4:]}"
            elif text.startswith("a · "):
                text = f"{sel} · {text[4:]}"
            elif text in ("det(M)", "det(⟦M⟧)"):
                text = f"det({sel})"
            elif text in ("inv(M)", "inv(⟦M⟧)"):
                text = f"inv({sel})"
            elif text in ("transpose(M)", "transpose(⟦M⟧)"):
                text = f"transpose({sel})"
            elif text in ("eigenvals(M)", "eigenvals(⟦M⟧)"):
                text = f"eigenvals({sel})"
            elif text in ("rref(M)", "rref(⟦M⟧)"):
                text = f"rref({sel})"
        cursor.insertText(text)
        self.input_edit.setTextCursor(cursor)
        self.input_edit.setFocus()
        self.input_edit._select_next_placeholder()
        if hasattr(self, 'preview_row'):
            self.preview_row.setVisible(False)

    def execute(self):
        if self.input_mode == self.MODE_2D_MATH and not getattr(self.input_edit, 'frac_widgets', None):
            cur_txt = self.input_edit.toPlainText()
            cleaned = CellInputEdit.clean_operator_spacing(cur_txt)
            if cleaned != cur_txt:
                cur = self.input_edit.textCursor()
                cpos = cur.position()
                if re.search(r'\b[a-zA-Z][a-zA-Z0-9]*(?:_[a-zA-Z0-9_]+)+\b', cleaned):
                    self.input_edit.set_stepped_math_text(cleaned)
                else:
                    self.input_edit.setPlainText(cleaned)
                cur.setPosition(min(cpos, len(cleaned)))
                self.input_edit.setTextCursor(cur)
        math_text = self.get_executable_text()
        if not math_text:
            return
        if hasattr(self, '_preview_timer'):
            self._preview_timer.stop()
        self._last_executed_text = math_text
        if hasattr(self, 'preview_row'):
            self.preview_row.setVisible(False)
        self.lbl_error.setVisible(False)
        self.clear_error()

        # In Document Mode (not worksheet mode), evaluate inline as "expr = result"
        # unless it is a plot command, output suppression (:), or pure assignment (:=)
        is_plot_cmd = any(math_text.lstrip().startswith(cmd) for cmd in (
            'plot(', 'plot3d(', 'implicitplot(', 'LPplot(', 'polygonOmråde(', 'polygonOmraade('
        ))
        is_suppressed = math_text.rstrip().endswith(':')
        is_pure_assignment = (':=' in math_text and self.input_edit._find_top_level_equal(math_text) == -1)

        if not getattr(self, 'is_worksheet_mode', False) and not is_plot_cmd and not is_suppressed and not is_pure_assignment:
            if hasattr(self, 'output_row'):
                self.output_row.setVisible(False)
            if hasattr(self, 'plot_container'):
                self.plot_container.setVisible(False)

            doc = self.input_edit.document()
            block = doc.begin()
            while block.isValid():
                btxt = block.text().strip()
                if btxt:
                    if ':=' in btxt and self.input_edit._find_top_level_equal(btxt) == -1:
                        engine = self.input_edit._get_engine()
                        if engine:
                            try:
                                engine.evaluate(btxt)
                            except Exception:
                                pass
                    elif not btxt.endswith(':'):
                        self.input_edit._handle_inline_evaluation(target_block=block)
                block = block.next()

            ws = self._get_worksheet_view()
            if ws:
                ws.statusMessage.emit("Evaluated", 2000)
            return

        self.executeRequested.emit(self.cell_id, math_text)

    def set_result(self, result: CASResult):
        """Display computation result: mathematical formula, equation label, or plot."""
        self.current_result = result
        self.lbl_error.setVisible(False)

        # Trailing colon ':' suppresses output display
        if self.get_input_text().strip().endswith(':'):
            self.output_row.setVisible(False)
            self.plot_container.setVisible(False)
            if hasattr(self, 'preview_row'):
                self.preview_row.setVisible(False)
            return

        # Check if result is a Plot
        if result.is_plot or isinstance(result.raw_result, PlotData):
            self.output_row.setVisible(False)
            self._render_embedded_plot(result.raw_result if isinstance(result.raw_result, PlotData) else result.plot_data.get('plot_obj'))
        else:
            if self.plot_container.isVisible():
                self.plot_container.setVisible(False)

            # Display LaTeX math formula in math blue
            latex_content = result.exact_latex or result.numeric_latex
            from cas_engine.units import infer_unit_from_expression
            inferred_u = infer_unit_from_expression(self.get_executable_text())
            if inferred_u and result.exact_text and re.match(r'^[+-]?\d+(?:[.,]\d+)?(?:[eE][+-]?\d+)?$', result.exact_text.strip()):
                if latex_content and not re.search(r'\\text\{\s*' + re.escape(inferred_u), latex_content):
                    latex_content = f"{latex_content}\\text{{ {inferred_u}}}"
            self.math_renderer.set_latex(latex_content)
            self.output_row.setVisible(True)

    def _render_embedded_plot(self, pdata: PlotData):
        """
        Render PlotData directly inside the worksheet cell with a clean, professional,
        Excel-style graph aesthetic.
        """
        if not pdata:
            return

        # Clear existing plot widgets if any
        while self.plot_layout.count():
            item = self.plot_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Excel-Style Card Container
        card = QFrame(self.plot_container)
        card.setObjectName("excelPlotCard")
        card.setStyleSheet("""
            QFrame#excelPlotCard {
                background-color: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
            }
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(10, 10, 10, 10)
        card_layout.setSpacing(6)

        # Show title only if explicitly specified and not generic "Function Plot"
        title_lbl = None
        if getattr(pdata, 'title', None) and str(pdata.title).strip() and str(pdata.title).strip().lower() not in ("function plot", "parametric curve", "polar curve"):
            title_lbl = QLabel(f"<b>{pdata.title}</b>", card)
            title_lbl.setStyleSheet("color: #1e293b; font-size: 12px; padding: 2px 4px;")
            card_layout.addWidget(title_lbl)

        # Matplotlib Figure with Excel proportions
        fig = Figure(figsize=(5.6, 3.8), dpi=100)
        fig.patch.set_facecolor("#ffffff")

        excel_palette = [
            "#2f5597",  # Excel Classic Dark Blue
            "#ed7d31",  # Excel Orange
            "#70ad47",  # Excel Green
            "#ffc000",  # Excel Gold
            "#4472c4",  # Excel Accent Blue
            "#7030a0",  # Excel Purple
            "#00b0f0",  # Excel Cyan
            "#c00000",  # Excel Crimson
        ]

        leg = None
        if getattr(pdata, 'is_3d', False):
            from mpl_toolkits.mplot3d import Axes3D
            ax = fig.add_subplot(111, projection='3d')
            ax.set_facecolor("#ffffff")
            if getattr(pdata, 'x_grid', None) is not None and getattr(pdata, 'y_grid', None) is not None and getattr(pdata, 'z_grid', None) is not None:
                surf = ax.plot_surface(pdata.x_grid, pdata.y_grid, pdata.z_grid, cmap='viridis', edgecolor='none', alpha=0.9)
                ax.set_xlabel(pdata.x_label or "x", color="#1e293b", fontsize=8)
                ax.set_ylabel(pdata.y_label or "y", color="#1e293b", fontsize=8)
                ax.set_zlabel("z", color="#1e293b", fontsize=8)
                ax.tick_params(colors="#334155", labelsize=7)
        else:
            ax = fig.add_subplot(111)
            ax.set_facecolor("#ffffff")

            # Shaded regions (for polygonOmråde / inequalities)
            if hasattr(pdata, 'regions') and pdata.regions:
                for reg in pdata.regions:
                    ax.fill_between(reg.x_vals, reg.y_min_vals, reg.y_max_vals,
                                    color=reg.color, alpha=reg.alpha, zorder=2)

            # Plot curves with clean Excel palette
            for i, curve in enumerate(pdata.curves):
                col = curve.color or excel_palette[i % len(excel_palette)]
                lbl = curve.label if (pdata.legend or len(pdata.curves) > 1) else None
                if lbl and '\\' in lbl and not (lbl.startswith('$') and lbl.endswith('$')):
                    lbl = f"${lbl}$"
                ax.plot(
                    curve.x_vals, curve.y_vals, curve.style or "-",
                    label=lbl, color=col, linewidth=2.0, antialiased=True, zorder=3
                )

            # Excel-Style Spines: Top and Right hidden
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            ax.spines['left'].set_color("#cbd5e1")
            ax.spines['left'].set_linewidth(1.0)
            ax.spines['bottom'].set_color("#cbd5e1")
            ax.spines['bottom'].set_linewidth(1.0)

            # Excel-Style Gridlines: Clean, light horizontal major grid
            ax.yaxis.grid(True, color="#e5e7eb", linestyle="-", linewidth=0.75, alpha=0.9, zorder=1)
            ax.xaxis.grid(False)

            # Reference baseline at y=0 and x=0 if in range
            try:
                import numpy as np
                all_y = []
                for c in pdata.curves:
                    valid = c.y_vals[np.isfinite(c.y_vals)]
                    if len(valid) > 0:
                        all_y.extend([valid.min(), valid.max()])
                if all_y and min(all_y) < 0 < max(all_y):
                    ax.axhline(0, color="#94a3b8", linewidth=0.9, linestyle="-", zorder=2)

                all_x = []
                for c in pdata.curves:
                    valid = c.x_vals[np.isfinite(c.x_vals)]
                    if len(valid) > 0:
                        all_x.extend([valid.min(), valid.max()])
                if all_x and min(all_x) < 0 < max(all_x):
                    ax.axvline(0, color="#e2e8f0", linewidth=0.8, linestyle="--", zorder=1)
            except Exception:
                pass

            # Typography
            ax.set_xlabel(pdata.x_label or "x", color="#475569", fontsize=9.5, fontweight='medium')
            ax.set_ylabel(pdata.y_label or "y", color="#475569", fontsize=9.5, fontweight='medium')
            ax.tick_params(colors="#64748b", labelsize=8.5, length=3.5, width=0.75)

            if pdata.x_lim:
                ax.set_xlim(pdata.x_lim)
            if hasattr(pdata, 'y_lim') and pdata.y_lim:
                ax.set_ylim(pdata.y_lim)

            # Equal aspect ratio for geometric/parametric/polar shapes
            if getattr(pdata, 'aspect_equal', False) or getattr(pdata, 'is_polar', False):
                try:
                    ax.set_aspect('equal', adjustable='datalim')
                except Exception:
                    pass

            # Excel-style legend
            leg = None
            handles, labels = ax.get_legend_handles_labels()
            if handles and labels:
                leg = ax.legend(
                    loc='upper right', frameon=True, framealpha=0.92,
                    facecolor='#ffffff', edgecolor='#e2e8f0', fontsize=8.5,
                    handlelength=1.5, handletextpad=0.5
                )
                if leg:
                    leg.set_clip_on(False)
                    if leg.get_frame():
                        leg.get_frame().set_clip_on(False)
                    for text in leg.get_texts():
                        text.set_color("#334155")
                        text.set_clip_on(False)
                    for h in getattr(leg, 'legend_handles', []):
                        h.set_clip_on(False)
                    try:
                        leg.set_draggable(True)
                        dleg = getattr(leg, '_draggable', None)
                        if dleg:
                            orig_dleg_update = dleg.update_offset
                            def clamped_leg_update(dx, dy):
                                try:
                                    r = fig.canvas.get_renderer()
                                    box_bbox = dleg.offsetbox.get_bbox(r)
                                    fig_w = fig.bbox.width
                                    fig_h = fig.bbox.height
                                    margin = 6.0

                                    new_x = dleg.offsetbox_x + dx
                                    new_y = dleg.offsetbox_y + dy

                                    clamped_x = max(margin - box_bbox.x0, min(new_x, fig_w - margin - box_bbox.x1))
                                    clamped_y = max(margin - box_bbox.y0, min(new_y, fig_h - margin - box_bbox.y1))

                                    dleg.offsetbox.set_offset((clamped_x, clamped_y))
                                except Exception:
                                    orig_dleg_update(dx, dy)
                            dleg.update_offset = clamped_leg_update
                    except Exception:
                        pass

        # Give extra top headroom when legend is present so it can sit above curves without clipping
        has_legend = bool(leg and leg.get_visible()) if 'leg' in locals() else False
        if has_legend and not getattr(pdata, 'is_3d', False):
            fig.tight_layout(rect=[0, 0, 1, 0.82], pad=1.2)
        else:
            fig.tight_layout(pad=1.2)

        # Make x and y axis labels interactive and draggable with the mouse
        dt_x = None
        dt_y = None
        if not getattr(pdata, 'is_3d', False) and hasattr(ax, 'xaxis') and hasattr(ax, 'yaxis'):
            try:
                dt_x = DraggableAxisLabel(ax.xaxis)
                dt_y = DraggableAxisLabel(ax.yaxis)
            except Exception:
                pass

        canvas = FigureCanvasQTAgg(fig)
        canvas.wheelEvent = lambda event: self.wheelEvent(event)
        factor = getattr(self, 'zoom_factor', 1.0)
        canvas.setFixedSize(int(560 * factor), int(380 * factor))

        # Connect copy and save
        def on_copy():
            pixmap = canvas.grab()
            QApplication.clipboard().setPixmap(pixmap)
            main_win = self.window()
            if main_win and hasattr(main_win, 'statusBar') and main_win.statusBar():
                main_win.statusBar().showMessage("Plot copied to clipboard", 2500)
            elif self.parent_worksheet and hasattr(self.parent_worksheet, 'statusMessage'):
                self.parent_worksheet.statusMessage.emit("Plot copied to clipboard", 2500)

        def on_save():
            fn, _ = QFileDialog.getSaveFileName(self, "Save Plot", "plot.png", "PNG Image (*.png);;SVG Image (*.svg);;PDF (*.pdf)")
            if fn:
                fig.savefig(fn, dpi=300, bbox_inches='tight')
                main_win = self.window()
                if main_win and hasattr(main_win, 'statusBar') and main_win.statusBar():
                    main_win.statusBar().showMessage(f"Plot saved to {os.path.basename(fn)}", 3000)
                elif self.parent_worksheet and hasattr(self.parent_worksheet, 'statusMessage'):
                    self.parent_worksheet.statusMessage.emit(f"Plot saved to {os.path.basename(fn)}", 3000)

        self._current_plot_canvas = canvas
        self._current_plot_ax = ax
        self._current_plot_fig = fig
        self._current_plot_legend = leg
        self._current_plot_draggables = [d for d in [dt_x, dt_y] if d]
        self._current_plot_copy_fn = on_copy
        self._current_plot_save_fn = on_save

        # Context menu on right click of plot (canvas, card, and title)
        self._last_plot_menu_time = 0.0
        def show_plot_menu(pos):
            import time
            now = time.time()
            if now - getattr(self, '_last_plot_menu_time', 0.0) < 0.3:
                return
            self._last_plot_menu_time = now
            self._show_plot_context_menu(pos)

        card.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        card.customContextMenuRequested.connect(lambda pt: show_plot_menu(card.mapToGlobal(pt)))

        # Interactive hover cursor for draggable legend and axis labels
        canvas.setMouseTracking(True)
        orig_mouse_move = canvas.mouseMoveEvent
        def canvas_mouse_move(ev):
            orig_mouse_move(ev)
            if ev.buttons() & Qt.MouseButton.LeftButton:
                canvas.setCursor(Qt.CursorShape.ClosedHandCursor)
                return
            try:
                r = canvas.get_renderer()
                mpl_x = ev.position().x()
                mpl_y = fig.bbox.height - ev.position().y()

                over_draggable = False
                cur_leg = getattr(self, '_current_plot_legend', None)
                if cur_leg and cur_leg.get_visible():
                    if cur_leg.get_window_extent(r).contains(mpl_x, mpl_y):
                        over_draggable = True

                if not over_draggable and hasattr(ax, 'xaxis') and ax.xaxis.label and ax.xaxis.label.get_visible():
                    bx = ax.xaxis.label.get_window_extent(r).padded(4)
                    if bx.contains(mpl_x, mpl_y):
                        over_draggable = True

                if not over_draggable and hasattr(ax, 'yaxis') and ax.yaxis.label and ax.yaxis.label.get_visible():
                    by = ax.yaxis.label.get_window_extent(r).padded(4)
                    if by.contains(mpl_x, mpl_y):
                        over_draggable = True

                if over_draggable:
                    canvas.setCursor(Qt.CursorShape.OpenHandCursor)
                else:
                    canvas.setCursor(Qt.CursorShape.ArrowCursor)
            except Exception:
                pass
        canvas.mouseMoveEvent = canvas_mouse_move

        orig_mouse_release = canvas.mouseReleaseEvent
        def canvas_mouse_release(ev):
            orig_mouse_release(ev)
            canvas.setCursor(Qt.CursorShape.ArrowCursor)
            if ev.button() == Qt.MouseButton.RightButton:
                show_plot_menu(ev.globalPosition().toPoint())
        canvas.mouseReleaseEvent = canvas_mouse_release

        def canvas_context_menu(ev):
            show_plot_menu(ev.globalPos())
            ev.accept()
        canvas.contextMenuEvent = canvas_context_menu

        if title_lbl is not None:
            title_lbl.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            title_lbl.customContextMenuRequested.connect(lambda pt: show_plot_menu(title_lbl.mapToGlobal(pt)))

        card_layout.addWidget(canvas, 0, Qt.AlignmentFlag.AlignCenter)
        self.plot_layout.setContentsMargins(20, 6, 20, 10)
        self.plot_layout.addWidget(card, 0, Qt.AlignmentFlag.AlignLeft)
        self.plot_container.setVisible(True)

    def clear_error(self):
        """Remove/dismiss the error display."""
        self.error_box.setVisible(False)
        self.error_box.setText("")

    def clear_output(self):
        """Remove/dismiss mathematical output row."""
        self.output_row.setVisible(False)
        self.plot_container.setVisible(False)
        if hasattr(self, 'preview_row'):
            self.preview_row.setVisible(False)
        self.current_result = None
        self._last_executed_text = None

    def set_error(self, title: str, details: str, input_expr: str = ""):
        """Display selectable and removable error with smart suggestions."""
        self.output_row.setVisible(False)
        self.plot_container.setVisible(False)
        clean_details = details or title
        clean_details = re.sub(r'CASEngine\._init_builtins\.<locals>\.<lambda>\(\)', 'function()', clean_details)
        clean_details = re.sub(r'<locals>\.<lambda>\(\)', 'function()', clean_details)
        clean_details = re.sub(r'^Invalid argument types:\s*', '', clean_details)
        msg = f"Error, {clean_details}"

        faulty = input_expr or self.get_input_text()
        from cas_engine.error_suggester import suggest_fix
        suggestion = suggest_fix(faulty, details, engine=self.engine)

        self.error_box.set_error_and_suggestion(msg, suggestion)
        self.error_box.setVisible(True)

    def _on_suggestion_applied(self, suggestion: str):
        if suggestion:
            self.input_edit.setPlainText(suggestion)
            tc = self.input_edit.textCursor()
            tc.movePosition(tc.MoveOperation.End)
            self.input_edit.setTextCursor(tc)
            self.input_edit.setFocus()
            self.clear_error()

    def _show_plot_context_menu(self, global_pos):
        menu = QMenu(self)
        Theme.apply_menu_style(menu, getattr(self, 'theme_mode', 'light'))

        act_copy = menu.addAction("📋 Copy Plot Image")
        if hasattr(self, '_current_plot_copy_fn') and self._current_plot_copy_fn:
            act_copy.triggered.connect(self._current_plot_copy_fn)

        act_save = menu.addAction("💾 Save Plot as Image...")
        if hasattr(self, '_current_plot_save_fn') and self._current_plot_save_fn:
            act_save.triggered.connect(self._current_plot_save_fn)

        menu.addSeparator()

        canvas = getattr(self, '_current_plot_canvas', None)
        ax = getattr(self, '_current_plot_ax', None)
        leg = getattr(self, '_current_plot_legend', None)

        if canvas and not sip.isdeleted(canvas):
            # Legend position options
            if leg:
                menu_leg = menu.addMenu("📌 Legend Position")
                Theme.apply_menu_style(menu_leg, getattr(self, 'theme_mode', 'light'))

                positions = [
                    ("Above Plot (Middle Top)", "lower center", (0.5, 1.02)),
                    ("Above Plot (Top Right)", "lower right", (1.0, 1.02)),
                    ("Above Plot (Top Left)", "lower left", (0.0, 1.02)),
                    ("Top Right (Default)", "upper right", None),
                    ("Top Left", "upper left", None),
                    ("Top Center", "upper center", None),
                    ("Bottom Right", "lower right", None),
                    ("Bottom Left", "lower left", None),
                    ("Bottom Center", "lower center", None),
                    ("Center Right", "center right", None),
                    ("Center Left", "center left", None),
                    ("Best (Automatic)", "best", None),
                ]
                for title, loc_code, bbox in positions:
                    def _make_loc_setter(code, b_box):
                        return lambda: (leg.set_bbox_to_anchor(b_box), leg.set_loc(code), canvas.draw_idle())
                    act_loc = menu_leg.addAction(title)
                    act_loc.triggered.connect(_make_loc_setter(loc_code, bbox))

                menu_leg.addSeparator()
                is_vis = leg.get_visible()
                vis_label = "Hide Legend" if is_vis else "Show Legend"
                def _toggle_legend():
                    leg.set_visible(not is_vis)
                    canvas.draw_idle()
                act_vis = menu_leg.addAction(vis_label)
                act_vis.triggered.connect(_toggle_legend)

            # Y-Axis Label position options
            if ax and hasattr(ax, 'yaxis') and ax.yaxis.label:
                y_text = ax.yaxis.label.get_text() or "f(x)"
                menu_y = menu.addMenu(f"📍 Y-Axis Label ('{y_text}')")
                Theme.apply_menu_style(menu_y, getattr(self, 'theme_mode', 'light'))

                def _set_y_pos(x_coord, y_coord, rot, ha):
                    ax.yaxis.set_label_coords(x_coord, y_coord, transform=ax.transAxes)
                    ax.yaxis.label.set_rotation(rot)
                    ax.yaxis.label.set_ha(ha)
                    canvas.draw_idle()

                act_y_left = menu_y.addAction("Left Center (Default, Vertical)")
                act_y_left.triggered.connect(lambda: (
                    setattr(ax.yaxis, '_autolabelpos', True),
                    ax.set_ylabel(ax.get_ylabel()),
                    ax.yaxis.label.set_rotation(90),
                    canvas.draw_idle()
                ))

                act_y_top_h = menu_y.addAction("Top Left (Horizontal)")
                act_y_top_h.triggered.connect(lambda: _set_y_pos(0.0, 1.04, 0, 'right'))

                act_y_top_v = menu_y.addAction("Top Left (Vertical)")
                act_y_top_v.triggered.connect(lambda: _set_y_pos(-0.02, 1.0, 90, 'right'))

            # X-Axis Label position options
            if ax and hasattr(ax, 'xaxis') and ax.xaxis.label:
                x_text = ax.xaxis.label.get_text() or "x"
                menu_x = menu.addMenu(f"📍 X-Axis Label ('{x_text}')")
                Theme.apply_menu_style(menu_x, getattr(self, 'theme_mode', 'light'))

                def _set_x_pos(x_coord, y_coord, ha):
                    ax.xaxis.set_label_coords(x_coord, y_coord, transform=ax.transAxes)
                    ax.xaxis.label.set_ha(ha)
                    canvas.draw_idle()

                act_x_center = menu_x.addAction("Bottom Center (Default)")
                act_x_center.triggered.connect(lambda: (
                    setattr(ax.xaxis, '_autolabelpos', True),
                    ax.set_xlabel(ax.get_xlabel()),
                    canvas.draw_idle()
                ))

                act_x_right = menu_x.addAction("Bottom Right")
                act_x_right.triggered.connect(lambda: _set_x_pos(1.0, -0.06, 'right'))

                act_x_top = menu_x.addAction("Top Right")
                act_x_top.triggered.connect(lambda: _set_x_pos(1.0, 1.04, 'right'))

            # Reset All Positions
            def _reset_all_positions():
                try:
                    if ax:
                        ax.xaxis._autolabelpos = True
                        ax.yaxis._autolabelpos = True
                        ax.set_xlabel(ax.get_xlabel())
                        ax.set_ylabel(ax.get_ylabel())
                        ax.yaxis.label.set_rotation(90)
                    if leg:
                        leg.set_loc('upper right')
                        leg.set_bbox_to_anchor(None)
                        leg.set_visible(True)
                    canvas.draw_idle()
                    main_win = self.window()
                    if main_win and hasattr(main_win, 'statusBar') and main_win.statusBar():
                        main_win.statusBar().showMessage("Plot labels and legend positions reset to default", 2500)
                except Exception:
                    pass

            act_reset = menu.addAction("↺ Reset Positions to Default")
            act_reset.triggered.connect(_reset_all_positions)

            menu.addSeparator()

        act_remove = menu.addAction("Remove Plot (Delete)")
        act_remove.triggered.connect(self.clear_output)

        act_del_grp = menu.addAction("Delete Execution Group")
        act_del_grp.triggered.connect(lambda: self.deleteRequested.emit(self.cell_id))

        menu.exec(global_pos)

    def _show_cell_context_menu(self, global_pos):
        if getattr(self, 'is_section_header', False) and hasattr(self, 'title_edit'):
            self.title_edit.show_context_menu(global_pos)
            return

        menu = QMenu(self)
        Theme.apply_menu_style(menu, getattr(self, 'theme_mode', 'light'))

        ws = self._get_worksheet_view()
        selected_count = len(getattr(ws, 'selected_cells', [])) if ws else 0
        if selected_count > 1 and ws and self in ws.selected_cells:
            act_copy_all = menu.addAction(f"Copy {selected_count} Selected Statements (Ctrl+C)")
            act_copy_all.triggered.connect(ws.copy_selected_cells)
            act_cut_all = menu.addAction(f"Cut {selected_count} Selected Statements (Ctrl+X)")
            act_cut_all.triggered.connect(ws.cut_selected_cells)
            act_del_all = menu.addAction(f"Delete {selected_count} Selected Statements (Delete)")
            act_del_all.triggered.connect(ws.delete_selected_cells)
            menu.addSeparator()

        act_run = menu.addAction("Execute Group (Ctrl+Enter)")
        act_run.triggered.connect(self.execute)

        act_mode = menu.addAction("Toggle 1-D / 2-D Math (F5)")
        act_mode.triggered.connect(self.toggle_input_mode)

        if self.error_box.isVisible():
            act_clr_err = menu.addAction("Remove Error (Delete)")
            act_clr_err.triggered.connect(self.clear_error)
        if self.output_row.isVisible() or self.plot_container.isVisible():
            act_clr_out = menu.addAction("Remove Output (Delete)")
            act_clr_out.triggered.connect(self.clear_output)

        if getattr(self, 'is_inside_section', False):
            act_outdent = menu.addAction("Outdent (Exit Section / Subsection) (Shift+Tab)")
            act_outdent.triggered.connect(ws.outdent_active_cell if ws else self.outdent_cell)
            act_ins_out = menu.addAction("Insert Statement Below Outside Section")
            act_ins_out.triggered.connect(lambda: ws.insert_cell_outside_section(self.cell_id) if ws else None)
            menu.addSeparator()

        menu.addSeparator()
        act_ins_above = menu.addAction("Insert Execution Group Above")
        act_ins_above.triggered.connect(lambda: self.insertBelowRequested.emit(f"before_{self.cell_id}"))

        act_ins_below = menu.addAction("Insert Execution Group Below")
        act_ins_below.triggered.connect(lambda: self.insertBelowRequested.emit(self.cell_id))

        act_del = menu.addAction("Delete Execution Group")
        act_del.triggered.connect(lambda: self.deleteRequested.emit(self.cell_id))

        menu.exec(global_pos)

    def contextMenuEvent(self, event):
        self._show_cell_context_menu(event.globalPos())

    def to_dict(self) -> dict:
        import re
        has_embedded = bool(hasattr(self.input_edit, 'embedded_images') and self.input_edit.embedded_images)
        html_low = self.input_edit.toHtml().lower()
        img_srcs = re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', html_low)
        has_real_img = bool(has_embedded or any(not (s.startswith('frac://') or s.startswith('integral://')) for s in img_srcs))
        is_rich = bool(has_real_img or (self.input_mode == self.MODE_TEXT and '<' in self.input_edit.toHtml()))
        data = {
            'cell_id': self.cell_id,
            'execution_idx': self.execution_idx,
            'input': self.input_edit.toHtml() if is_rich else self.get_input_text(),
            'input_mode': self.input_mode,
            'is_worksheet_mode': self.is_worksheet_mode,
            'is_inside_section': getattr(self, 'is_inside_section', False),
            'is_outside_section': getattr(self, '_is_outside_section', False),
            'line_spacing': getattr(self, 'current_line_spacing', 1.0),
            'spans': None if is_rich else self.input_edit.get_spans(),
        }
        if has_embedded:
            data['embedded_images'] = dict(self.input_edit.embedded_images)
        if getattr(self, 'is_section_header', False):
            data['is_section_header'] = True
            data['section_level'] = getattr(self, 'section_level', 0)
            data['is_collapsed'] = getattr(self, 'is_collapsed', False)
            data['section_bg_colors'] = getattr(self, 'section_bg_colors', [])
            if hasattr(self, 'title_edit') and self.title_edit:
                data['section_html'] = self.title_edit.toHtml()
                data['section_title'] = self.title_edit.toPlainText()
            else:
                data['section_html'] = getattr(self, 'section_html', '')
                data['section_title'] = getattr(self, 'section_title', '')
        else:
            data['section_level'] = getattr(self, 'section_level', 0)
        if self.current_result:
            data['result'] = {
                'exact_latex': self.current_result.exact_latex or '',
                'numeric_latex': self.current_result.numeric_latex or '',
                'exact_text': self.current_result.exact_text or '',
                'numeric_text': self.current_result.numeric_text or '',
                'python_code': getattr(self.current_result, 'python_code', '') or '',
                'result_type': getattr(self.current_result, 'result_type', 'Symbolic') or 'Symbolic',
                'is_plot': getattr(self.current_result, 'is_plot', False),
            }
        if hasattr(self, 'lbl_error') and self.lbl_error.isVisible():
            data['error'] = self.lbl_error.text()
        return data

    def from_dict(self, data: dict):
        self.cell_id = data.get('cell_id', self.cell_id)
        self.set_execution_idx(data.get('execution_idx', self.execution_idx))

        mode_val = data.get('input_mode', self.MODE_2D_MATH)
        if mode_val in (0, '0', self.MODE_2D_MATH):
            target_mode = self.MODE_2D_MATH
        elif mode_val in (1, '1', self.MODE_1D_MATH):
            target_mode = self.MODE_1D_MATH
        elif mode_val in (2, '2', self.MODE_TEXT):
            target_mode = self.MODE_TEXT
        elif mode_val in (3, '3', self.MODE_NONEXEC_MATH):
            target_mode = self.MODE_NONEXEC_MATH
        else:
            target_mode = self.MODE_2D_MATH

        self.input_mode = target_mode
        if hasattr(self, 'input_edit') and self.input_edit:
            self.input_edit.current_typing_mode = target_mode
            self.input_edit._pending_mode = target_mode

        ws_view = self._get_worksheet_view()
        default_ws = getattr(ws_view, 'is_worksheet_mode', False) if ws_view else getattr(self, 'is_worksheet_mode', False)
        self.is_worksheet_mode = data.get('is_worksheet_mode', default_ws)
        self.set_worksheet_mode(self.is_worksheet_mode)

        self.is_section_header = data.get('is_section_header', False)
        self.section_title = data.get('section_title', '')
        self.section_level = data.get('section_level', 0)
        self.is_collapsed = data.get('is_collapsed', False)
        self._is_outside_section = bool(data.get('is_outside_section', False))
        if 'is_inside_section' in data:
            self.is_inside_section = bool(data['is_inside_section'])
        else:
            self.is_inside_section = bool(self.section_level > 0 or not self.is_section_header)
        self.section_bg_colors = data.get('section_bg_colors', [])
        self.section_html = data.get('section_html', '')

        # 1. Restore embedded images
        embedded = data.get('embedded_images', {})
        if embedded:
            if not hasattr(self.input_edit, 'embedded_images'):
                self.input_edit.embedded_images = {}
            self.input_edit.embedded_images.update(embedded)
            for img_id, b64_str in embedded.items():
                try:
                    raw_bytes = base64.b64decode(b64_str)
                    qimg = QImage()
                    if qimg.loadFromData(raw_bytes):
                        qimg = qimg.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
                        self.input_edit.document().addResource(
                            QTextDocument.ResourceType.ImageResource,
                            QUrl(img_id),
                            qimg
                        )
                except Exception:
                    pass

        # 2. Set input content
        inp_text = data.get('input', '')
        spans = data.get('spans')
        if spans:
            self.input_edit.set_spans(spans)
            if hasattr(self, 'output_row'):
                self.output_row.setVisible(False)
        elif embedded or '<img' in inp_text.lower() or '<span' in inp_text.lower() or '<div' in inp_text.lower():
            if '<img' in inp_text.lower():
                import re
                def _clamp_img_tag(m):
                    tag = m.group(0)
                    src_m = re.search(r'src=["\']([^"\']+)["\']', tag)
                    if src_m:
                        src_id = src_m.group(1)
                        res = self.input_edit.document().resource(QTextDocument.ResourceType.ImageResource, QUrl(src_id))
                        if res and not res.isNull():
                            qw = res.size().width()
                            qh = res.size().height()
                            max_w = 700
                            w_m = re.search(r'width=["\']?(\d+)', tag)
                            h_m = re.search(r'height=["\']?(\d+)', tag)
                            if w_m and h_m:
                                cur_w = int(w_m.group(1))
                                cur_h = int(h_m.group(1))
                                ratio_tag = cur_w / max(1, cur_h)
                                ratio_real = qw / max(1, qh)
                                # Auto-heal legacy 480x320 hardcoded bug or distorted aspect ratios
                                if (cur_w == 480 and cur_h == 320 and (qw, qh) != (480, 320)) or abs(ratio_tag - ratio_real) > 0.05:
                                    cur_h = max(20, int(cur_w / ratio_real))
                                if cur_w > max_w:
                                    cur_h = max(20, int(qh * (max_w / max(1, qw))))
                                    cur_w = max_w
                                return f'<img src="{src_id}" width="{cur_w}" height="{cur_h}"/>'
                            elif w_m:
                                cur_w = min(int(w_m.group(1)), max_w)
                                cur_h = max(20, int(qh * (cur_w / max(1, qw))))
                                return f'<img src="{src_id}" width="{cur_w}" height="{cur_h}"/>'
                            else:
                                disp_w = min(qw, max_w)
                                disp_h = max(20, int(qh * (disp_w / max(1, qw))))
                                return f'<img src="{src_id}" width="{disp_w}" height="{disp_h}"/>'
                    return tag
                inp_text = re.sub(r'<img[^>]+>', _clamp_img_tag, inp_text, flags=re.IGNORECASE)
            self.input_edit.setHtml(inp_text)
            self.input_edit._adjust_height()
        else:
            self.set_input_text(inp_text)

        if 'line_spacing' in data:
            self.set_line_spacing(data['line_spacing'])

        if self.is_section_header:
            self._apply_section_header_styling()
        else:
            self.set_input_mode(target_mode)
            self._apply_mode_styling()
            self._apply_indentation()

        res_data = data.get('result')
        if res_data:
            from cas_engine import CASResult
            res = CASResult(
                raw_result=None,
                exact_latex=res_data.get('exact_latex', ''),
                numeric_latex=res_data.get('numeric_latex', ''),
                exact_text=res_data.get('exact_text', ''),
                numeric_text=res_data.get('numeric_text', ''),
                python_code=res_data.get('python_code', ''),
                result_type=res_data.get('result_type', 'Symbolic'),
                is_plot=res_data.get('is_plot', False),
            )
            self.set_result(res)
        elif data.get('error'):
            if hasattr(self, 'lbl_error'):
                self.lbl_error.setText(data['error'])
                self.lbl_error.setVisible(True)
            self.output_row.setVisible(False)
        else:
            self.output_row.setVisible(False)
            if hasattr(self, 'lbl_error'):
                self.lbl_error.setVisible(False)
            if hasattr(self, 'error_box'):
                self.error_box.setVisible(False)
