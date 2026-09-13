"""
Interactive Matrix Builder Dialog.
Enables creating matrices of arbitrary dimensions (M x N) with live compact grid editing,
modernized dropdowns with custom chevron arrows, centered compact presets, and custom dimension inputs.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QPushButton, QLineEdit, QScrollArea, QWidget, QFrame, QComboBox, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QPointF
from PyQt6.QtGui import QIntValidator, QPainter, QColor, QPen


class ModernComboBox(QComboBox):
    """Editable combo box with a modernized, sleek vector chevron down-arrow."""
    def __init__(self, parent=None, theme_mode: str = "light"):
        super().__init__(parent)
        self.theme_mode = theme_mode
        self.setEditable(True)
        self.setFixedHeight(26)
        self.setFixedWidth(76)

        bg = "#ffffff" if theme_mode == "light" else "#1e2430"
        fg = "#0f172a" if theme_mode == "light" else "#f8fafc"
        border = "#cbd5e1" if theme_mode == "light" else "#3b4354"
        focus_border = "#2563eb" if theme_mode == "light" else "#3b82f6"
        menu_bg = "#ffffff" if theme_mode == "light" else "#1e2430"
        menu_fg = "#0f172a" if theme_mode == "light" else "#f8fafc"
        sel_bg = "#eff6ff" if theme_mode == "light" else "#26354d"
        sel_fg = "#2563eb" if theme_mode == "light" else "#60a5fa"

        self.setStyleSheet(f"""
            QComboBox {{
                background-color: {bg};
                color: {fg};
                border: 1px solid {border};
                border-radius: 4px;
                padding-left: 8px;
                padding-right: 0px;
                font-size: 12px;
            }}
            QComboBox:hover {{
                border-color: {"#94a3b8" if theme_mode == "light" else "#4b5563"};
            }}
            QComboBox:focus {{
                border-color: {focus_border};
            }}
            QComboBox QLineEdit {{
                color: {fg};
                background: transparent;
                border: none;
                padding: 0px;
                margin: 0px;
                font-size: 12px;
                font-weight: 600;
            }}
            QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 22px;
                border: none;
                background: transparent;
            }}
            QComboBox::down-arrow {{
                image: none;
                border: none;
                width: 0px;
                height: 0px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {menu_bg};
                color: {menu_fg};
                border: 1px solid {border};
                border-radius: 4px;
                selection-background-color: {sel_bg};
                selection-color: {sel_fg};
                outline: none;
                padding: 2px;
            }}
        """)

        if self.lineEdit():
            self.lineEdit().setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

    def focusInEvent(self, event):
        super().focusInEvent(event)
        self.update()

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        arrow_color = QColor("#2563eb") if self.hasFocus() else (
            QColor("#64748b") if self.theme_mode == "light" else QColor("#94a3b8")
        )
        pen = QPen(arrow_color, 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)

        # Draw a sleek, modern chevron in the right 20px area
        cx = self.width() - 11.5
        cy = self.height() / 2.0
        painter.drawLine(QPointF(cx - 3.5, cy - 1.5), QPointF(cx, cy + 2.0))
        painter.drawLine(QPointF(cx, cy + 2.0), QPointF(cx + 3.5, cy - 1.5))


class MatrixCellEdit(QLineEdit):
    """Compact matrix cell editor with auto-select on focus and arrow/Enter navigation."""
    def __init__(self, row: int, col: int, dialog, theme_mode: str = "light", parent=None):
        super().__init__(parent)
        self.row = row
        self.col = col
        self.dialog = dialog
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFixedHeight(28)
        self.setMinimumWidth(44)
        self.setMaximumWidth(76)

        bg = "#ffffff" if theme_mode == "light" else "#1e2430"
        fg = "#0f172a" if theme_mode == "light" else "#f8fafc"
        border = "#cbd5e1" if theme_mode == "light" else "#3b4354"
        focus_border = "#2563eb" if theme_mode == "light" else "#3b82f6"

        self.setStyleSheet(f"""
            QLineEdit {{
                background-color: {bg};
                color: {fg};
                border: 1px solid {border};
                border-radius: 4px;
                font-family: "SF Mono", "Menlo", "Consolas", monospace;
                font-size: 11.5px;
                font-weight: 500;
                padding: 1px 4px;
            }}
            QLineEdit:focus {{
                border: 1.5px solid {focus_border};
                background-color: {"#f0f7ff" if theme_mode == "light" else "#172033"};
            }}
        """)

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        QTimer.singleShot(0, self.selectAll)

    def focusInEvent(self, event):
        super().focusInEvent(event)
        QTimer.singleShot(0, self.selectAll)

    def keyPressEvent(self, event):
        key = event.key()
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Down):
            next_row = self.row + 1
            if next_row < len(self.dialog.cells):
                self.dialog.cells[next_row][self.col].setFocus()
                return
        elif key == Qt.Key.Key_Up:
            prev_row = self.row - 1
            if prev_row >= 0:
                self.dialog.cells[prev_row][self.col].setFocus()
                return
        elif key == Qt.Key.Key_Right and self.cursorPosition() == len(self.text()):
            next_col = self.col + 1
            if next_col < len(self.dialog.cells[self.row]):
                self.dialog.cells[self.row][next_col].setFocus()
                return
        elif key == Qt.Key.Key_Left and self.cursorPosition() == 0:
            prev_col = self.col - 1
            if prev_col >= 0:
                self.dialog.cells[self.row][prev_col].setFocus()
                return
        super().keyPressEvent(event)


class _SpinBoxAdapter:
    """Adapter providing .setValue() and .value() for QComboBox backwards-compatibility."""
    def __init__(self, combo: QComboBox):
        self._combo = combo

    def setValue(self, val: int):
        self._combo.setCurrentText(str(val))

    def value(self) -> int:
        try:
            return max(1, int(self._combo.currentText().strip()))
        except (ValueError, TypeError):
            return 3


class MatrixDialog(QDialog):
    """Dialog for creating and editing symbolic/numerical matrices."""
    matrixCreated = pyqtSignal(str)

    def __init__(self, parent=None, theme_mode: str = "light"):
        super().__init__(parent)
        self.setWindowTitle("Matrix Wizard")
        self.resize(460, 350)
        self.setMinimumSize(380, 280)
        self.theme_mode = theme_mode
        self.cells = []
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(14, 12, 14, 12)
        main_layout.setSpacing(10)

        # Dimension Controls: Rows [Dropdown]  Cols [Dropdown]
        dim_layout = QHBoxLayout()
        dim_layout.setSpacing(8)

        lbl_dim = QLabel("Dimensions:")
        lbl_dim.setStyleSheet("font-weight: 600; font-size: 11px;")
        dim_layout.addWidget(lbl_dim)

        dim_layout.addWidget(QLabel("Rows:"))
        self.rows_combo = ModernComboBox(theme_mode=self.theme_mode)
        self.rows_combo.addItems([str(i) for i in range(1, 11)])
        self.rows_combo.setCurrentText("3")
        self.rows_combo.setValidator(QIntValidator(1, 30))
        self.rows_combo.setToolTip("Select or type number of rows (1 - 30)")
        self.rows_combo.currentTextChanged.connect(self._on_dimensions_changed)
        dim_layout.addWidget(self.rows_combo)

        dim_layout.addWidget(QLabel("Cols:"))
        self.cols_combo = ModernComboBox(theme_mode=self.theme_mode)
        self.cols_combo.addItems([str(i) for i in range(1, 11)])
        self.cols_combo.setCurrentText("3")
        self.cols_combo.setValidator(QIntValidator(1, 30))
        self.cols_combo.setToolTip("Select or type number of columns (1 - 30)")
        self.cols_combo.currentTextChanged.connect(self._on_dimensions_changed)
        dim_layout.addWidget(self.cols_combo)

        # Adapters for backwards-compatibility
        self.rows_spin = _SpinBoxAdapter(self.rows_combo)
        self.cols_spin = _SpinBoxAdapter(self.cols_combo)

        dim_layout.addStretch()
        main_layout.addLayout(dim_layout)

        # Presets Toolbar - Compact, Centered Buttons
        presets_layout = QHBoxLayout()
        presets_layout.setSpacing(5)

        lbl_presets = QLabel("Presets:")
        lbl_presets.setStyleSheet("font-weight: 600; font-size: 11px;")
        presets_layout.addWidget(lbl_presets)

        preset_btns = [
            ("Identity", 54, self._fill_identity),
            ("Zeros", 46, self._fill_zeros),
            ("Ones", 44, self._fill_ones),
            ("Diagonal", 58, self._fill_diagonal),
            ("Clear", 44, self._clear_all),
        ]

        preset_style = f"""
            QPushButton {{
                background-color: {"#f1f5f9" if self.theme_mode == "light" else "#262d3d"};
                color: {"#334155" if self.theme_mode == "light" else "#cbd5e1"};
                border: 1px solid {"#cbd5e1" if self.theme_mode == "light" else "#3b4354"};
                border-radius: 4px;
                font-size: 11px;
                font-weight: 500;
                text-align: center;
                padding: 0px;
            }}
            QPushButton:hover {{
                background-color: {"#eff6ff" if self.theme_mode == "light" else "#333b4d"};
                border-color: {"#93c5fd" if self.theme_mode == "light" else "#4b5563"};
                color: {"#1d4ed8" if self.theme_mode == "light" else "#93c5fd"};
            }}
            QPushButton:pressed {{
                background-color: {"#dbeafe" if self.theme_mode == "light" else "#3b4354"};
            }}
        """

        for name, width, callback in preset_btns:
            btn = QPushButton(name)
            btn.setFixedWidth(width)
            btn.setFixedHeight(23)
            btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            btn.setStyleSheet(preset_style)
            btn.clicked.connect(callback)
            presets_layout.addWidget(btn)

        presets_layout.addStretch()
        main_layout.addLayout(presets_layout)

        # Matrix Grid Scroll Area
        self.grid_scroll = QScrollArea()
        self.grid_scroll.setWidgetResizable(True)
        self.grid_scroll.setFrameShape(QFrame.Shape.StyledPanel)
        self.grid_scroll.setStyleSheet(f"""
            QScrollArea {{
                background-color: {"#f8fafc" if self.theme_mode == "light" else "#151921"};
                border: 1px solid {"#e2e8f0" if self.theme_mode == "light" else "#2a3241"};
                border-radius: 6px;
            }}
        """)

        self.grid_container = QWidget()
        self.grid_container.setStyleSheet("background: transparent;")
        self.grid_layout = QGridLayout(self.grid_container)
        self.grid_layout.setContentsMargins(12, 10, 12, 10)
        self.grid_layout.setSpacing(5)
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.grid_scroll.setWidget(self.grid_container)

        main_layout.addWidget(self.grid_scroll, 1)

        # Bottom Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)
        btn_layout.addStretch()

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setFixedHeight(28)
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)

        self.btn_insert = QPushButton("Insert Matrix")
        self.btn_insert.setFixedHeight(28)
        self.btn_insert.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                color: #ffffff;
                border: 1px solid #1d4ed8;
                border-radius: 4px;
                font-weight: 600;
                font-size: 11.5px;
                padding: 4px 14px;
            }
            QPushButton:hover {
                background-color: #1d4ed8;
            }
        """)
        self.btn_insert.clicked.connect(self._on_insert)
        btn_layout.addWidget(self.btn_insert)

        main_layout.addLayout(btn_layout)

        self._rebuild_grid()

    def _on_dimensions_changed(self, _text=None):
        r_txt = self.rows_combo.currentText().strip()
        c_txt = self.cols_combo.currentText().strip()
        if r_txt.isdigit() and c_txt.isdigit():
            r = int(r_txt)
            c = int(c_txt)
            if 1 <= r <= 30 and 1 <= c <= 30:
                self._rebuild_grid()

    def get_rows_count(self) -> int:
        try:
            return max(1, min(30, int(self.rows_combo.currentText().strip())))
        except (ValueError, TypeError):
            return 3

    def get_cols_count(self) -> int:
        try:
            return max(1, min(30, int(self.cols_combo.currentText().strip())))
        except (ValueError, TypeError):
            return 3

    def _rebuild_grid(self):
        """Rebuild the grid of line edits according to rows & cols."""
        for row in self.cells:
            for edit in row:
                self.grid_layout.removeWidget(edit)
                edit.deleteLater()
        self.cells = []

        rows = self.get_rows_count()
        cols = self.get_cols_count()

        for r in range(rows):
            row_edits = []
            for c in range(cols):
                edit = MatrixCellEdit(r, c, self, theme_mode=self.theme_mode)
                edit.setPlaceholderText(f"a_{{{r+1},{c+1}}}")
                if r == c:
                    edit.setText("1")
                else:
                    edit.setText("0")
                self.grid_layout.addWidget(edit, r, c)
                row_edits.append(edit)
            self.cells.append(row_edits)

        if self.cells and self.cells[0]:
            self.cells[0][0].setFocus()

    def _fill_identity(self):
        rows = len(self.cells)
        for r in range(rows):
            cols = len(self.cells[r])
            for c in range(cols):
                self.cells[r][c].setText("1" if r == c else "0")

    def _fill_zeros(self):
        for row in self.cells:
            for edit in row:
                edit.setText("0")

    def _fill_ones(self):
        for row in self.cells:
            for edit in row:
                edit.setText("1")

    def _fill_diagonal(self):
        rows = len(self.cells)
        for r in range(rows):
            cols = len(self.cells[r])
            for c in range(cols):
                self.cells[r][c].setText(f"d_{r+1}" if r == c else "0")

    def _clear_all(self):
        for row in self.cells:
            for edit in row:
                edit.setText("")

    def get_matrix_string(self) -> str:
        """Convert current grid values to SymPy Matrix string format."""
        row_strs = []
        for row in self.cells:
            items = []
            for edit in row:
                val = edit.text().strip()
                if not val:
                    val = "0"
                items.append(val)
            row_strs.append(f"[{', '.join(items)}]")

        return f"Matrix([{', '.join(row_strs)}])"

    def _on_insert(self):
        mat_str = self.get_matrix_string()
        self.matrixCreated.emit(mat_str)
        self.accept()
