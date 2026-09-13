"""
OpenMath Context Panel.
Provides dynamic contextual mathematical operations reacting to the active cell / selection
(Simplify, Factor, Expand, Solve, Differentiate, Integrate, Matrix Operations, Embedded Systems calculations)
and includes the Math Editor Shortcuts cheatsheet.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QToolButton, QSizePolicy, QGridLayout,
    QGroupBox, QStyleOption, QStyle
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QColor, QPainter

import re
import sympy as sp

from .theme import Theme


class ContextPanel(QWidget):
    """
    Right-side OpenMath Context Panel.
    Reacts dynamically to current selection, active expression, or output.
    """
    operationRequested = pyqtSignal(str)   # CAS command to execute, e.g. "factor(ans)"
    collapseRequested = pyqtSignal()       # >> toggle clicked

    def __init__(self, parent=None, theme_mode: str = "light"):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAutoFillBackground(True)
        self.theme_mode = theme_mode
        self.current_expr_str = ""
        self.is_collapsed = False
        self.shortcut_labels = []
        self._init_ui()
        self._apply_theme_styles()

    def paintEvent(self, event):
        opt = QStyleOption()
        opt.initFrom(self)
        p = QPainter(self)
        self.style().drawPrimitive(QStyle.PrimitiveElement.PE_Widget, opt, p, self)

    def _init_ui(self):
        self.setObjectName("contextPanelRoot")
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Header bar with title and ">>" collapse button
        self.header_frame = QFrame(self)
        self.header_frame.setObjectName("contextPanelHeader")
        self.header_frame.setFixedHeight(30)
        header_layout = QHBoxLayout(self.header_frame)
        header_layout.setContentsMargins(8, 0, 4, 0)
        header_layout.setSpacing(4)

        self.lbl_title = QLabel("Context Panel")
        header_layout.addWidget(self.lbl_title)

        header_layout.addStretch()

        self.btn_collapse = QToolButton(self.header_frame)
        self.btn_collapse.setText("»")
        self.btn_collapse.setToolTip("Collapse Context Panel")
        self.btn_collapse.setFixedSize(22, 22)
        self.btn_collapse.clicked.connect(self.collapseRequested.emit)
        header_layout.addWidget(self.btn_collapse)

        main_layout.addWidget(self.header_frame)

        # Scroll area for dynamic panels
        self.scroll = QScrollArea(self)
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)

        self.content_widget = QWidget()
        self.content_widget.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.content_widget.setAutoFillBackground(True)
        self.content_widget.setObjectName("contextContent")
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(6, 6, 6, 6)
        self.content_layout.setSpacing(8)

        # 1. Math Editor Shortcuts Card (Prominent at top)
        self.shortcuts_card = QFrame(self.content_widget)
        sc_layout = QVBoxLayout(self.shortcuts_card)
        sc_layout.setContentsMargins(6, 6, 6, 6)
        sc_layout.setSpacing(4)

        self.lbl_sc_title = QLabel("Math Editor Shortcuts")
        sc_layout.addWidget(self.lbl_sc_title)

        shortcuts = [
            ("Evaluate", "Enter"),
            ("Evaluate Inline", "Alt+Enter"),
            ("Toggle Math/Text", "F5"),
            ("Toggle to Executable Math", "Shift+F5"),
            ("Exit Fraction/Superscript", "→"),
            ("Assignments", "a := b"),
            ("Functions", "f := x -> x²"),
            ("Equations", "x = y"),
            ("Command Complete", "Esc"),
            ("Navigate Placeholders", "Tab"),
        ]

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(3)
        self.shortcut_labels.clear()
        for r, (action, key) in enumerate(shortcuts):
            l_act = QLabel(f"{action}:")
            l_key = QLabel(key)
            self.shortcut_labels.append((l_act, l_key))
            grid.addWidget(l_act, r, 0)
            grid.addWidget(l_key, r, 1)

        sc_layout.addLayout(grid)
        self.content_layout.addWidget(self.shortcuts_card)

        # 2. Target Expression Summary Card
        self.target_box = QFrame(self.content_widget)
        tb_layout = QVBoxLayout(self.target_box)
        tb_layout.setContentsMargins(6, 6, 6, 6)
        tb_layout.setSpacing(3)
        self.lbl_target_header = QLabel("Active Target:")
        tb_layout.addWidget(self.lbl_target_header)

        self.lbl_target_expr = QLabel("No expression selected")
        self.lbl_target_expr.setWordWrap(True)
        tb_layout.addWidget(self.lbl_target_expr)
        self.content_layout.addWidget(self.target_box)

        # 3. Context Operations Section (Dynamic based on selected expression)
        self.ops_box = QFrame(self.content_widget)
        self.ops_layout = QVBoxLayout(self.ops_box)
        self.ops_layout.setContentsMargins(0, 0, 0, 0)
        self.ops_layout.setSpacing(6)
        self._build_operations_buttons()
        self.content_layout.addWidget(self.ops_box)

        self.content_layout.addStretch()
        self.scroll.setWidget(self.content_widget)
        main_layout.addWidget(self.scroll, 1)

    def set_theme_mode(self, mode: str):
        """Update Context Panel theme mode dynamically."""
        self.theme_mode = mode
        self._apply_theme_styles()

    def _apply_theme_styles(self):
        is_dark = (self.theme_mode == "dark")
        panel_bg = "#161e2a" if is_dark else "#f7f8fa"
        header_bg = "#1c2433" if is_dark else "#e4e6ea"
        card_bg = "#1c2433" if is_dark else "#ffffff"
        target_bg = "#182230" if is_dark else "#f0f4f8"
        border_col = "#2b384c" if is_dark else "#cbd5e1"
        header_border = "#2b384c" if is_dark else "#b8bcc2"
        text_pri = "#f8fafc" if is_dark else "#1e293b"
        text_sec = "#94a3b8" if is_dark else "#475569"
        key_color = "#38bdf8" if is_dark else "#1e3a8a"
        target_color = "#7dd3fc" if is_dark else "#0000aa"

        self.setStyleSheet(f"background-color: {panel_bg};")
        if hasattr(self, 'header_frame'):
            self.header_frame.setStyleSheet(f"""
                QFrame#contextPanelHeader {{
                    background-color: {header_bg};
                    border-bottom: 1px solid {header_border};
                    border-left: 1px solid {header_border};
                }}
            """)
        if hasattr(self, 'lbl_title'):
            self.lbl_title.setStyleSheet(f"font-weight: bold; font-size: 11px; color: {text_pri};")
        if hasattr(self, 'btn_collapse'):
            self.btn_collapse.setStyleSheet(f"""
                QToolButton {{
                    font-size: 13px;
                    font-weight: bold;
                    color: {key_color};
                    border: 1px solid transparent;
                    border-radius: 3px;
                    background: transparent;
                }}
                QToolButton:hover {{
                    background: {'#233348' if is_dark else '#dbeafe'};
                    border-color: {border_col};
                }}
            """)
        if hasattr(self, 'scroll'):
            self.scroll.setStyleSheet(f"QScrollArea {{ background-color: {panel_bg}; border-left: 1px solid {border_col}; }}")
        if hasattr(self, 'content_widget'):
            self.content_widget.setStyleSheet(f"background-color: {panel_bg};")
        if hasattr(self, 'shortcuts_card'):
            self.shortcuts_card.setStyleSheet(f"""
                QFrame {{
                    background-color: {card_bg};
                    border: 1px solid {border_col};
                    border-radius: 4px;
                    padding: 6px;
                }}
            """)
        if hasattr(self, 'lbl_sc_title'):
            self.lbl_sc_title.setStyleSheet(f"font-weight: bold; font-size: 11px; color: {text_pri}; margin-bottom: 4px;")
        for l_act, l_key in self.shortcut_labels:
            l_act.setStyleSheet(f"font-size: 11px; color: {text_sec};")
            l_key.setStyleSheet(f"font-size: 11px; font-weight: bold; color: {key_color};")
        if hasattr(self, 'target_box'):
            self.target_box.setStyleSheet(f"""
                QFrame {{
                    background-color: {target_bg};
                    border: 1px solid {border_col};
                    border-radius: 4px;
                    padding: 4px;
                }}
            """)
        if hasattr(self, 'lbl_target_header'):
            self.lbl_target_header.setStyleSheet(f"font-size: 10px; font-weight: bold; color: {text_sec};")
        if hasattr(self, 'lbl_target_expr'):
            self.lbl_target_expr.setStyleSheet(f"font-family: 'Times New Roman', serif; font-size: 13px; color: {target_color};")

        expr_type = self._detect_type(self.current_expr_str)
        self._build_operations_buttons(expr_type)

    def _create_action_button(self, text: str, command_template: str, tooltip: str = "") -> QPushButton:
        btn = QPushButton(text)
        btn.setToolTip(tooltip or text)
        btn.setFixedHeight(24)
        is_dark = (self.theme_mode == "dark")
        bg = "#202b3a" if is_dark else "#f8fafc"
        border = "#2e3b4f" if is_dark else "#cbd5e1"
        fg = "#f1f5f9" if is_dark else "#1e293b"
        hover_bg = "#2a384c" if is_dark else "#e0f2fe"
        hover_border = "#38bdf8" if is_dark else "#38bdf8"
        hover_fg = "#38bdf8" if is_dark else "#0369a1"
        pressed_bg = "#1b2533" if is_dark else "#bae6fd"
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg};
                border: 1px solid {border};
                border-radius: 3px;
                font-size: 11px;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif;
                color: {fg};
                padding: 2px 6px;
                text-align: left;
            }}
            QPushButton:hover {{
                background-color: {hover_bg};
                border-color: {hover_border};
                color: {hover_fg};
            }}
            QPushButton:pressed {{
                background-color: {pressed_bg};
            }}
        """)
        btn.clicked.connect(lambda: self._execute_action(command_template))
        return btn

    def _detect_type(self, target: str, result_obj=None) -> str:
        raw = getattr(result_obj, 'raw_result', None) if result_obj else None
        if raw is not None:
            if isinstance(raw, sp.Matrix):
                return "Matrix"
            elif isinstance(raw, sp.Eq):
                return "Equation"
            elif isinstance(raw, (int, sp.Integer)):
                return "Integer"
            elif isinstance(raw, (float, sp.Float, sp.Rational, sp.Number)):
                return "Number"
            elif isinstance(raw, (list, tuple)):
                return "List"

        s = target.strip()
        if ':=' in s:
            s = s.split(':=', 1)[1].strip()

        if s.startswith('Matrix(') or s.startswith('Vector('):
            return "Matrix"
        elif '=' in s and not any(op in s for op in ['==', '<=', '>=', '!=']):
            return "Equation"
        elif re.match(r'^-?\d+$', s):
            return "Integer"
        elif re.match(r'^-?\d+\.\d+$', s):
            return "Number"
        elif any(sym in s for sym in ['x', 'y', 'z', 't', 's', 'sin', 'cos', 'exp', '^']):
            return "Polynomial"
        return "General"

    def _build_operations_buttons(self, expr_type: str = "General"):
        # Clear existing
        while self.ops_layout.count():
            item = self.ops_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if expr_type == "Matrix":
            # Matrix Operations prominent
            grp_mat = QGroupBox("Matrix & Linear Algebra")
            grp_mat.setStyleSheet(self._groupbox_qss())
            l_mat = QVBoxLayout(grp_mat)
            l_mat.setSpacing(3)
            l_mat.setContentsMargins(6, 12, 6, 6)
            l_mat.addWidget(self._create_action_button("Determinant", "det({expr})", "Compute matrix determinant"))
            l_mat.addWidget(self._create_action_button("Inverse", "inv({expr})", "Compute matrix inverse"))
            l_mat.addWidget(self._create_action_button("Transpose", "transpose({expr})", "Transpose matrix"))
            l_mat.addWidget(self._create_action_button("Eigenvalues", "eigenvals({expr})", "Compute eigenvalues"))
            l_mat.addWidget(self._create_action_button("Eigenvectors", "eigenvects({expr})", "Compute eigenvectors"))
            l_mat.addWidget(self._create_action_button("Rank", "rank({expr})", "Compute matrix rank"))
            l_mat.addWidget(self._create_action_button("Trace", "trace({expr})", "Compute matrix trace"))
            l_mat.addWidget(self._create_action_button("Reduced Row Echelon (RREF)", "rref({expr})", "Compute RREF"))
            l_mat.addWidget(self._create_action_button("Characteristic Poly", "charpoly({expr})", "Characteristic polynomial"))
            l_mat.addWidget(self._create_action_button("LU Decomposition", "LUDecomposition({expr})", "LU matrix decomposition"))
            l_mat.addWidget(self._create_action_button("QR Decomposition", "QRDecomposition({expr})", "QR matrix decomposition"))
            self.ops_layout.addWidget(grp_mat)

            grp_alg = QGroupBox("General Operations")
            grp_alg.setStyleSheet(self._groupbox_qss())
            l_alg = QVBoxLayout(grp_alg)
            l_alg.setSpacing(3)
            l_alg.setContentsMargins(6, 12, 6, 6)
            l_alg.addWidget(self._create_action_button("Simplify Elements", "simplify({expr})", "Simplify all matrix entries"))
            self.ops_layout.addWidget(grp_alg)

        elif expr_type == "Equation":
            # Equation operations prominent
            grp_eq = QGroupBox("Equation Operations")
            grp_eq.setStyleSheet(self._groupbox_qss())
            l_eq = QVBoxLayout(grp_eq)
            l_eq.setSpacing(3)
            l_eq.setContentsMargins(6, 12, 6, 6)
            l_eq.addWidget(self._create_action_button("Solve (Symbolic)", "solve({expr}, x)", "Solve equation symbolically for x"))
            l_eq.addWidget(self._create_action_button("Solve (Numerical)", "fsolve({expr}, x)", "Solve equation numerically"))
            l_eq.addWidget(self._create_action_button("Left-Hand Side (lhs)", "lhs({expr})", "Extract left-hand side"))
            l_eq.addWidget(self._create_action_button("Right-Hand Side (rhs)", "rhs({expr})", "Extract right-hand side"))
            l_eq.addWidget(self._create_action_button("Plot Equation", "plot(lhs({expr}) - rhs({expr}), (x, -10, 10))", "Plot root curve of equation"))
            self.ops_layout.addWidget(grp_eq)

            grp_alg = QGroupBox("Algebra")
            grp_alg.setStyleSheet(self._groupbox_qss())
            l_alg = QVBoxLayout(grp_alg)
            l_alg.setSpacing(3)
            l_alg.setContentsMargins(6, 12, 6, 6)
            l_alg.addWidget(self._create_action_button("Expand", "expand({expr})", "Expand both sides"))
            l_alg.addWidget(self._create_action_button("Simplify", "simplify({expr})", "Simplify equation"))
            self.ops_layout.addWidget(grp_alg)

        elif expr_type in ("Integer", "Number"):
            # Number Theory & Representations prominent
            grp_nt = QGroupBox("Number Theory")
            grp_nt.setStyleSheet(self._groupbox_qss())
            l_nt = QVBoxLayout(grp_nt)
            l_nt.setSpacing(3)
            l_nt.setContentsMargins(6, 12, 6, 6)
            l_nt.addWidget(self._create_action_button("Prime Factors (ifactor)", "ifactor({expr})", "Integer prime factorization"))
            l_nt.addWidget(self._create_action_button("Next Prime", "nextprime({expr})", "Next smallest prime"))
            l_nt.addWidget(self._create_action_button("Divisors", "divisors({expr})", "List all integer divisors"))
            l_nt.addWidget(self._create_action_button("Euler Totient (phi)", "euler_phi({expr})", "Euler's totient function"))
            self.ops_layout.addWidget(grp_nt)

            grp_emb = QGroupBox("Digital Hardware Representations")
            grp_emb.setStyleSheet(self._groupbox_qss())
            l_emb = QVBoxLayout(grp_emb)
            l_emb.setSpacing(3)
            l_emb.setContentsMargins(6, 12, 6, 6)
            l_emb.addWidget(self._create_action_button("Binary Repr (8-bit)", "to_bin({expr}, 8)", "Format integer as 8-bit binary nibbles"))
            l_emb.addWidget(self._create_action_button("Binary Repr (16-bit)", "to_bin({expr}, 16)", "Format integer as 16-bit binary"))
            l_emb.addWidget(self._create_action_button("Binary Repr (32-bit)", "to_bin({expr}, 32)", "Format integer as 32-bit binary"))
            l_emb.addWidget(self._create_action_button("Hex Repr (0x)", "to_hex({expr}, 8)", "Format integer as 8-bit hex"))
            l_emb.addWidget(self._create_action_button("Two's Comp Breakdown", "twos_comp_repr({expr}, 8)", "Analyze signed/unsigned integer range"))
            l_emb.addWidget(self._create_action_button("IEEE-754 Float Bitfield", "ieee754({expr})", "Decompose floating point number"))
            self.ops_layout.addWidget(grp_emb)

        else:
            # Default / Polynomial / General Expression
            grp_alg = QGroupBox("Algebra & Simplification")
            grp_alg.setStyleSheet(self._groupbox_qss())
            l_alg = QVBoxLayout(grp_alg)
            l_alg.setSpacing(3)
            l_alg.setContentsMargins(6, 12, 6, 6)
            l_alg.addWidget(self._create_action_button("Factor", "factor({expr})", "Factor polynomial expression"))
            l_alg.addWidget(self._create_action_button("Expand", "expand({expr})", "Expand polynomial or trigonometric expression"))
            l_alg.addWidget(self._create_action_button("Simplify", "simplify({expr})", "Simplify mathematical expression"))
            l_alg.addWidget(self._create_action_button("Normal (Rational)", "normal({expr})", "Cancel common rational factors"))
            l_alg.addWidget(self._create_action_button("Partial Fractions", "convert({expr}, parfrac, x)", "Partial fraction decomposition"))
            l_alg.addWidget(self._create_action_button("Degree (w.r.t x)", "degree({expr}, x)", "Polynomial degree"))
            l_alg.addWidget(self._create_action_button("Solve roots (x)", "solve({expr} = 0, x)", "Solve for roots w.r.t x"))
            self.ops_layout.addWidget(grp_alg)

            grp_calc = QGroupBox("Calculus")
            grp_calc.setStyleSheet(self._groupbox_qss())
            l_calc = QVBoxLayout(grp_calc)
            l_calc.setSpacing(3)
            l_calc.setContentsMargins(6, 12, 6, 6)
            l_calc.addWidget(self._create_action_button("Differentiate (d/dx)", "diff({expr}, x)", "Differentiate expression with respect to x"))
            l_calc.addWidget(self._create_action_button("Integrate (∫ dx)", "integrate({expr}, x)", "Compute indefinite integral with respect to x"))
            l_calc.addWidget(self._create_action_button("Taylor Series (x=0)", "taylor({expr}, x, 0, 6)", "Compute 6th-order Taylor series around 0"))
            l_calc.addWidget(self._create_action_button("Plot 2D", "plot({expr}, (x, -10, 10))", "Plot 2D function on standard interval"))
            self.ops_layout.addWidget(grp_calc)

            grp_poly = QGroupBox("Optimization & Polygons")
            grp_poly.setStyleSheet(self._groupbox_qss())
            l_poly = QVBoxLayout(grp_poly)
            l_poly.setSpacing(3)
            l_poly.setContentsMargins(6, 12, 6, 6)
            l_poly.addWidget(self._create_action_button("polygonOmråde", "polygonOmråde(Uligheder, x = -1 .. 13, y = -1 .. 12)", "Plot feasible polygon area"))
            l_poly.addWidget(self._create_action_button("LPplot Level Curves", "LPplot({expr}, Uligheder, [0, 120, 300])", "Plot linear programming level curves"))
            self.ops_layout.addWidget(grp_poly)

    def _groupbox_qss(self) -> str:
        is_dark = (self.theme_mode == "dark")
        bg = "#1c2433" if is_dark else "#f8fafc"
        border = "#2b384c" if is_dark else "#cbd5e1"
        title_col = "#38bdf8" if is_dark else "#334155"
        return f"""
            QGroupBox {{
                font-size: 11px;
                font-weight: bold;
                color: {title_col};
                border: 1px solid {border};
                border-radius: 4px;
                margin-top: 10px;
                background-color: {bg};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 4px;
                background-color: {bg};
                color: {title_col};
            }}
        """

    def set_target_expression(self, expr_str: str, result_obj=None):
        """Update active expression displayed and targeted by Context Panel operations."""
        clean = (expr_str or "").strip()
        self.current_expr_str = clean
        expr_type = self._detect_type(clean, result_obj)
        if clean:
            display = clean if len(clean) <= 35 else clean[:32] + "..."
            self.lbl_target_expr.setText(f"{display} ({expr_type})")
            self.target_box.setVisible(True)
        else:
            self.lbl_target_expr.setText("No expression selected")

        self._build_operations_buttons(expr_type)

    def _execute_action(self, template: str):
        target = self.current_expr_str
        if not target:
            target = "x"
        if ':=' in target:
            target = target.split(':=', 1)[1].strip()
        cmd = template.replace("{expr}", target)
        self.operationRequested.emit(cmd)
