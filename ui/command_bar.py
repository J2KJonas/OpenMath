"""
OpenMath Command Bar with intelligent inline next-part suggestions (ghost text),
autocompletion, and history navigation.
"""

import re
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLineEdit, QPushButton, QCompleter,
    QLabel
)
from PyQt6.QtGui import QKeyEvent, QPainter, QColor, QFontMetrics, QFont
from PyQt6.QtCore import Qt, pyqtSignal, QStringListModel, QEvent

from .theme import Theme


class SmartSuggestLineEdit(QLineEdit):
    """
    Enhanced QLineEdit that displays an inline ghost-text suggestion for the next part
    of the mathematical expression/command as the user types.
    Supports [Tab] or [Right Arrow] to accept.
    """
    historyUp = pyqtSignal()
    historyDown = pyqtSignal()
    suggestionChanged = pyqtSignal(str)

    BUILTIN_TEMPLATES = [
        # Calculus
        "diff(sin(x) * exp(x), x)",
        "diff(f(x), x)",
        "diff(f(x), x, 2)",
        "integrate(x² · cos(x), x)",
        "integrate(f(x), x)",
        "integrate(exp(-x²), (x, 0, oo))",
        "integrate(f(x), (x, a, b))",
        "limit(sin(x)/x, x, 0)",
        "limit(f(x), x, 0)",
        "taylor(sin(x), x, 0, 6)",
        "taylor(f(x), x, 0, 6)",
        "dsolve(diff(y(x), x) = y(x), y(x))",
        "dsolve(diff(y(x), x, 2) + 4 · y(x) = 0, y(x))",
        "Sum(1/n², (n, 1, oo))",
        "Product(1 + 1/n², (n, 1, oo))",
        # Algebra
        "solve(x² - 5 · x + 6 = 0, x)",
        "solve([2 · x + 3 · y = 8, 4 · x - y = 2], [x, y])",
        "simplify(sin(x)² + cos(x)²)",
        "expand((x + y + z)²)",
        "factor(x³ - 8)",
        "apart((3 · x + 5) / (x² - 1), x)",
        "together(1/x + 1/y)",
        "collect(x · y + x · z + y, x)",
        "expand_trig(sin(x + y))",
        "trigsimp(sin(x)² + cos(x)²)",
        # Linear Algebra
        "Matrix([[1, 2], [3, 4]])",
        "Matrix([[1, 0, 0], [0, 1, 0], [0, 0, 1]])",
        "det(Matrix([[1, 2], [3, 4]]))",
        "inv(Matrix([[1, 2], [3, 4]]))",
        "eigenvals(Matrix([[1, 2], [3, 4]]))",
        "eigenvects(Matrix([[1, 2], [3, 4]]))",
        "rref(Matrix([[1, 2], [3, 4]]))",
        "charpoly(Matrix([[1, 2], [3, 4]]))",
        "nullspace(Matrix([[1, 2], [3, 4]]))",
        # Embedded Systems & Hardware
        "ubrr_calc(16 * MHz, 9600)",
        "ubrr_calc(72 * MHz, 115200)",
        "baud_rate(16 * MHz, 103)",
        "timer_calc(16 * MHz, 64, 249)",
        "timer_arr(84 * MHz, 84, 1000)",
        "pwm_duty(20000, 1500)",
        "adc_raw(1.65, 3.3, 10)",
        "adc_volt(2048, 3.3, 12)",
        "adc_resolution(3.3, 12)",
        "voltage_divider(5.0, 10 * kOhm, 10 * kOhm)",
        "led_resistor(5.0, 2.0, 20.0)",
        "rc_cutoff(10 * kOhm, 100 * nF)",
        "to_bin(0x5A, 8)",
        "to_hex(255, 8)",
        "twos_comp_repr(-5, 8)",
        "to_q(3.14159, 7, 8)",
        "from_q(804, 8)",
        "ieee754(12.375)",
        "crc8('SENSOR_DATA_OK')",
        "crc16('SENSOR_DATA_OK')",
        # 2D Plots
        "plot(sin(x) · exp(-x/5), (x, -10, 10))",
        "plot([sin(x), cos(x)], (x, -2 · pi, 2 · pi))",
        "plot_parametric(cos(t)³, sin(t)³, (t, 0, 2 · pi))",
        "plot_polar(1 + cos(theta), (theta, 0, 2 · pi))",
    ]

    def __init__(self, parent=None, theme_mode: str = "dark"):
        super().__init__(parent)
        self.theme_mode = theme_mode
        self.suggestion = ""
        self.history = []

        self.textEdited.connect(self._on_text_edited)
        self.textChanged.connect(self._on_text_changed)
        self.cursorPositionChanged.connect(lambda old, new: self.update())

    def set_theme_mode(self, mode: str):
        self.theme_mode = mode
        self.update()

    def set_history(self, history: list):
        self.history = list(history)

    def _on_text_changed(self):
        if not self.text():
            self.suggestion = ""
            self.suggestionChanged.emit("")
            self.update()
        elif not self.suggestion or not self.suggestion.lower().startswith(self.text().lower()):
            self._on_text_edited(self.text())

    def _on_text_edited(self, text: str):
        self.suggestion = self._calculate_suggestion(text)
        self.suggestionChanged.emit(self.suggestion)
        self.update()

    def _calculate_suggestion(self, text: str) -> str:
        s = text.strip()
        if not s:
            return ""

        # 1. Check user command history first (most recent match)
        for h in reversed(self.history):
            if h.lower().startswith(s.lower()) and len(h) > len(s):
                return h

        # 2. Check full template prefix match
        for tmpl in self.BUILTIN_TEMPLATES:
            if tmpl.lower().startswith(s.lower()) and len(tmpl) > len(s):
                # Preserve user's original casing for typed part
                return text + tmpl[len(text):]

        # 3. Check function name + open parenthesis matching
        match = re.match(r'^([a-zA-Z_]\w*)\s*\((.*)$', s)
        if match:
            fn_name, args_part = match.group(1), match.group(2)
            for tmpl in self.BUILTIN_TEMPLATES:
                t_match = re.match(r'^([a-zA-Z_]\w*)\s*\((.*)$', tmpl)
                if t_match and t_match.group(1).lower() == fn_name.lower():
                    t_args = t_match.group(2)
                    if t_args.lower().startswith(args_part.lower()) and len(t_args) > len(args_part):
                        return f"{fn_name}({args_part}{t_args[len(args_part):]}"
                    elif not args_part:
                        return tmpl

        return ""

    def accept_suggestion(self):
        """Fill current input with the suggested text."""
        if self.suggestion and len(self.suggestion) > len(self.text()):
            self.setText(self.suggestion)
            self.setCursorPosition(len(self.suggestion))
            self.suggestion = ""
            self.suggestionChanged.emit("")
            self.update()

    def event(self, event: QEvent) -> bool:
        if event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Tab:
                # 1. If completer popup is open and item selected, fill it
                if self.completer() and self.completer().popup().isVisible():
                    idx = self.completer().popup().currentIndex()
                    if idx.isValid():
                        text = self.completer().popup().model().data(idx)
                        self.setText(text)
                        self.completer().popup().hide()
                        self.setCursorPosition(len(text))
                        return True
                # 2. If inline suggestion exists, accept it
                if self.suggestion and len(self.suggestion) > len(self.text()):
                    self.accept_suggestion()
                    return True
        return super().event(event)

    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()

        # Right Arrow at end of text accepts the inline suggestion
        if key == Qt.Key.Key_Right:
            if self.cursorPosition() == len(self.text()) and self.suggestion and len(self.suggestion) > len(self.text()):
                self.accept_suggestion()
                event.accept()
                return
        elif key == Qt.Key.Key_Escape:
            self.suggestion = ""
            self.suggestionChanged.emit("")
            self.update()
            event.accept()
            return
        elif key == Qt.Key.Key_Up:
            self.historyUp.emit()
            return
        elif key == Qt.Key.Key_Down:
            self.historyDown.emit()
            return

        super().keyPressEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)

        # Draw ghost text suggestion if available and cursor is at end of input
        if self.suggestion and self.text() and self.suggestion.lower().startswith(self.text().lower()):
            if self.cursorPosition() == len(self.text()):
                painter = QPainter(self)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)

                ghost_color = QColor("#64748b" if self.theme_mode == Theme.DARK else "#94a3b8")
                painter.setPen(ghost_color)
                painter.setFont(self.font())

                fm = QFontMetrics(self.font())
                typed_width = fm.horizontalAdvance(self.text())
                remainder = self.suggestion[len(self.text()):]

                rect = self.contentsRect()
                padding_left = 10
                x = rect.left() + padding_left + typed_width
                y = rect.top() + (rect.height() + fm.ascent() - fm.descent()) // 2

                painter.drawText(x, y, remainder)
                painter.end()


class CommandBar(QWidget):
    """
    Bottom Command Bar providing single-line entry with inline ghost-text suggestions,
    history navigation, and action buttons.
    """
    commandSubmitted = pyqtSignal(str)
    templateRequested = pyqtSignal(str)

    AUTOCOMPLETE_WORDS = [
        "diff", "integrate", "limit", "series", "taylor", "dsolve", "solve", "solveset",
        "simplify", "expand", "factor", "apart", "together", "cancel", "collect",
        "Matrix", "eye", "zeros", "ones", "diag", "det", "inv", "transpose",
        "eigenvals", "eigenvects", "rref", "nullspace", "rank", "trace", "charpoly",
        "sin", "cos", "tan", "sec", "csc", "cot", "asin", "acos", "atan",
        "sinh", "cosh", "tanh", "exp", "log", "ln", "sqrt", "Abs",
        "plot", "plot_parametric", "plot_polar", "pi", "oo", "clear", "reset", "whos",
        "alpha", "beta", "gamma", "theta", "lambda", "phi", "omega",
        # Embedded Systems
        "to_bin", "to_hex", "twos_comp", "twos_comp_repr", "two_comp", "two_comp_repr",
        "bit_get", "bit_set", "bit_clear", "bit_toggle", "bit_mask", "bit_field",
        "to_q", "from_q", "ieee754", "ubrr_calc", "baud_rate", "timer_calc",
        "timer_arr", "pwm_duty", "adc_raw", "adc_volt", "adc_resolution",
        "voltage_divider", "voltage_divider_r1", "led_resistor", "rc_cutoff",
        "crc8", "crc16", "V", "mV", "uV", "kV", "MV", "MegaVolt", "kHz", "MHz", "GHz", "Hz", "MegaHz",
        "ms", "us", "ns", "ps", "s", "Ohm", "kOhm", "MOhm", "MegaOhm", "GOhm", "uF", "nF", "pF", "mF", "F",
        "mA", "uA", "A", "kA", "MA", "MegaAmp", "W", "mW", "uW", "kW", "MW", "MegaWatt"
    ]

    def __init__(self, parent=None, theme_mode: str = "dark"):
        super().__init__(parent)
        self.theme_mode = theme_mode
        self.history = []
        self.history_index = -1
        self._init_ui()

    def _init_ui(self):
        container_layout = QVBoxLayout(self)
        container_layout.setContentsMargins(6, 4, 6, 6)
        container_layout.setSpacing(2)

        # Main Input Row
        row_layout = QHBoxLayout()
        row_layout.setSpacing(6)

        lbl = QLabel("Prompt >")
        lbl.setStyleSheet("font-weight: bold; color: #38bdf8;")
        row_layout.addWidget(lbl)

        self.input_field = SmartSuggestLineEdit(self, theme_mode=self.theme_mode)
        self.input_field.setPlaceholderText("Enter formula (e.g., diff(sin(x)*exp(x), x) or ubrr_calc(16*MHz, 9600))")
        self.input_field.returnPressed.connect(self._submit)
        self.input_field.historyUp.connect(self._nav_history_up)
        self.input_field.historyDown.connect(self._nav_history_down)
        self.input_field.suggestionChanged.connect(self._on_suggestion_changed)

        # Dropdown Autocompletion
        self.completer_model = QStringListModel(self.AUTOCOMPLETE_WORDS)
        self.completer = QCompleter(self.completer_model, self)
        self.completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.input_field.setCompleter(self.completer)

        row_layout.addWidget(self.input_field, 1)

        # Action Buttons
        self.btn_eval = QPushButton("▶ Evaluate")
        self.btn_eval.setObjectName("primaryBtn")
        self.btn_eval.clicked.connect(self._submit)
        row_layout.addWidget(self.btn_eval)

        self.btn_clear = QPushButton("✕ Clear")
        self.btn_clear.setToolTip("Clear input text")
        self.btn_clear.clicked.connect(self.input_field.clear)
        row_layout.addWidget(self.btn_clear)

        container_layout.addLayout(row_layout)

        # Inline Suggestion Helper Hint
        self.lbl_suggestion_hint = QLabel("")
        self.lbl_suggestion_hint.setStyleSheet("color: #38bdf8; font-size: 11px; margin-left: 65px;")
        self.lbl_suggestion_hint.setVisible(False)
        container_layout.addWidget(self.lbl_suggestion_hint)

    def _on_suggestion_changed(self, suggestion: str):
        if suggestion and len(suggestion) > len(self.input_field.text()):
            remainder = suggestion[len(self.input_field.text()):]
            self.lbl_suggestion_hint.setText(f"💡 Press <b>Tab</b> or <b>→</b> to complete: <span style='color: #a78bfa;'>{remainder}</span>")
            self.lbl_suggestion_hint.setVisible(True)
        else:
            self.lbl_suggestion_hint.setText("")
            self.lbl_suggestion_hint.setVisible(False)

    def set_theme_mode(self, mode: str):
        self.theme_mode = mode
        self.input_field.set_theme_mode(mode)

    def update_variable_completions(self, var_names: list):
        """Add user-defined variable names to autocomplete list."""
        all_words = sorted(list(set(self.AUTOCOMPLETE_WORDS + var_names)))
        self.completer_model.setStringList(all_words)

    def _submit(self):
        text = self.input_field.text().strip()
        if not text:
            return

        # Add to history
        if not self.history or self.history[-1] != text:
            self.history.append(text)
            self.input_field.set_history(self.history)
        self.history_index = len(self.history)

        self.commandSubmitted.emit(text)
        self.input_field.clear()
        self.input_field.suggestion = ""
        self.lbl_suggestion_hint.setVisible(False)

    def _nav_history_up(self):
        if not self.history:
            return
        if self.history_index > 0:
            self.history_index -= 1
            self.input_field.setText(self.history[self.history_index])
            self.input_field.setCursorPosition(len(self.history[self.history_index]))

    def _nav_history_down(self):
        if not self.history:
            return
        if self.history_index < len(self.history) - 1:
            self.history_index += 1
            self.input_field.setText(self.history[self.history_index])
            self.input_field.setCursorPosition(len(self.history[self.history_index]))
        else:
            self.history_index = len(self.history)
            self.input_field.clear()

    def insert_text(self, text: str):
        self.input_field.insert(text)
        self.input_field.setFocus()
