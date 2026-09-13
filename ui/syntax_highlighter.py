"""
Syntax highlighter for mathematical expressions, SymPy functions, and CAS commands.
"""

import re
from PyQt6.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor, QFont
from PyQt6.QtCore import Qt


class MathSyntaxHighlighter(QSyntaxHighlighter):
    """
    Syntax highlighter for mathematical and CAS code editors.
    Supports dark and light themes.
    """

    def __init__(self, parent=None, theme_mode: str = "dark"):
        super().__init__(parent)
        self.theme_mode = theme_mode
        self.rules = []
        self._init_formats()
        self._build_rules()

    def set_theme_mode(self, mode: str):
        """Update theme mode and re-highlight."""
        self.theme_mode = mode
        self._init_formats()
        self._build_rules()
        self.rehighlight()

    def _init_formats(self):
        is_dark = (self.theme_mode == "dark")

        # Formats
        self.fmt_func = QTextCharFormat()
        self.fmt_func.setForeground(QColor("#38bdf8" if is_dark else "#0284c7"))  # Cyan / Deep sky
        self.fmt_func.setFontWeight(QFont.Weight.Bold)

        self.fmt_calc = QTextCharFormat()
        self.fmt_calc.setForeground(QColor("#a78bfa" if is_dark else "#7c3aed"))  # Purple for diff/int/solve
        self.fmt_calc.setFontWeight(QFont.Weight.Bold)

        self.fmt_num = QTextCharFormat()
        self.fmt_num.setForeground(QColor("#fbbf24" if is_dark else "#d97706"))  # Amber / Orange

        self.fmt_op = QTextCharFormat()
        self.fmt_op.setForeground(QColor("#f472b6" if is_dark else "#db2777"))  # Pink / Magenta
        self.fmt_op.setFontWeight(QFont.Weight.Bold)

        self.fmt_sym = QTextCharFormat()
        self.fmt_sym.setForeground(QColor("#34d399" if is_dark else "#059669"))  # Emerald for Greek / Constants

        self.fmt_comment = QTextCharFormat()
        self.fmt_comment.setForeground(QColor("#64748b" if is_dark else "#94a3b8"))
        self.fmt_comment.setFontItalic(True)

        # Placeholders ⟦...⟧: refined LaTeX-style token badge
        self.fmt_placeholder = QTextCharFormat()
        self.fmt_placeholder.setForeground(QColor("#1d4ed8" if not is_dark else "#93c5fd"))
        self.fmt_placeholder.setBackground(QColor("#eff6ff" if not is_dark else "#1e293b"))
        self.fmt_placeholder.setFontWeight(QFont.Weight.DemiBold)
        self.fmt_placeholder.setFontItalic(True)

    def _build_rules(self):
        self.rules = []

        # Functions & CAS commands
        cas_funcs = [
            r'\b(?:diff|integrate|limit|series|taylor|dsolve|solve|solveset|nsolve)\b',
            r'\b(?:simplify|expand|factor|apart|together|cancel|collect|roots|trigsimp|expand_trig)\b',
            r'\b(?:Matrix|eye|zeros|ones|diag|det|inv|transpose|eigenvals|eigenvects|rref|nullspace|rank|trace|charpoly)\b',
            r'\b(?:sin|cos|tan|sec|csc|cot|asin|acos|atan|sinh|cosh|tanh|asinh|acosh|atanh|arcsin|arccos|arctan)\b',
            r'\b(?:exp|log|ln|sqrt|cbrt|Abs|abs|factorial|gamma|erf|zeta|binomial|Piecewise|floor|ceiling)\b',
            r'\b(?:plot|plot_parametric|plot_polar|clear|reset|whos)\b',
            r'\b(?:to_bin|to_hex|twos_comp|twos_comp_repr|two_comp|two_comp_repr|bit_get|bit_set|bit_clear|bit_toggle|bit_mask|bit_field)\b',
            r'\b(?:to_q|from_q|ieee754|ubrr_calc|baud_rate|timer_calc|timer_arr|pwm_duty|adc_raw|adc_volt|adc_resolution)\b',
            r'\b(?:voltage_divider|voltage_divider_r1|led_resistor|rc_cutoff|crc8|crc16)\b',
            r'\b(?:V|mV|uV|μV|kV|MV|MegaVolt|kHz|MHz|GHz|Hz|MegaHz|ms|us|μs|ns|ps|s|Ohm|kOhm|MOhm|MegaOhm|GOhm|kΩ|MΩ|GΩ|Ω|uF|μF|nF|pF|mF|F|mA|uA|μA|A|kA|MA|MegaAmp|W|mW|uW|μW|kW|MW|MegaWatt)\b',
        ]
        for pattern in cas_funcs:
            self.rules.append((re.compile(pattern), self.fmt_func))

        # Numbers (including floats with dot or comma decimals, scientific notation, leading decimals)
        self.rules.append((re.compile(r'\b\d+(?:[.,]\d+)?(?:[eE][+-]?\d+)?\b'), self.fmt_num))
        self.rules.append((re.compile(r'(?:(?<=\b)|(?<=[^\w]))[.,]\d+(?:[eE][+-]?\d+)?\b'), self.fmt_num))

        # Operators & assignments (including multiplication dots · and ⋅)
        self.rules.append((re.compile(r'[:=+\-*/^!<>%~&|·⋅]'), self.fmt_op))

        # Greek letters & mathematical constants
        greek_and_consts = (
            r'\b(?:pi|Pi|E|I|oo|infinity|alpha|beta|gamma|delta|epsilon|zeta|eta|theta|'
            r'iota|kappa|lambda|mu|nu|xi|omicron|rho|sigma|tau|upsilon|phi|chi|psi|omega|'
            r'Gamma|Delta|Theta|Lambda|Xi|Pi|Sigma|Upsilon|Phi|Psi|Omega)\b'
        )
        self.rules.append((re.compile(greek_and_consts), self.fmt_sym))

        # Comments
        self.rules.append((re.compile(r'#.*'), self.fmt_comment))

        # Template placeholders ⟦...⟧ (added at end to highlight over operator/numbers)
        self.rules.append((re.compile(r'⟦.*?⟧'), self.fmt_placeholder))

    def highlightBlock(self, text: str):
        for pattern, fmt in self.rules:
            for match in pattern.finditer(text):
                start, end = match.span()
                self.setFormat(start, end - start, fmt)
