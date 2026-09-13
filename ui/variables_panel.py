"""
OpenMath Variable Manager Panel.
Live variable inspection and management:
- Inspect defined variables, equations, functions, and matrices
- Display columns: Variable, Value, Type
- Filter / search variables
- Unassign selected variable or clear all
- Insert variable name into worksheet on click
"""

from typing import Optional
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QTableWidget,
    QTableWidgetItem, QHeaderView, QPushButton, QLabel, QFrame,
    QMessageBox, QAbstractItemView
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QColor
import sympy as sp

from cas_engine import CASEngine
from .theme import Theme


class VariableManagerWidget(QWidget):
    """
    Sidebar panel for managing and inspecting active CAS variables.
    """
    insertVariable = pyqtSignal(str)
    variableUnassigned = pyqtSignal(str)

    def __init__(self, engine: CASEngine, parent=None, theme_mode: str = "light"):
        super().__init__(parent)
        self.engine = engine
        self.theme_mode = theme_mode
        self._init_ui()
        self._apply_theme_styles()

    def set_theme_mode(self, mode: str):
        self.theme_mode = mode
        self._apply_theme_styles()

    def _apply_theme_styles(self):
        is_dark = (self.theme_mode == "dark")
        bg_panel = "#161e2a" if is_dark else "#f7f8fa"
        bg_table = "#1a2332" if is_dark else "#ffffff"
        bg_hdr = "#202b3a" if is_dark else "#f8fafc"
        border = "#2b384c" if is_dark else "#e2e8f0"
        text_pri = "#f8fafc" if is_dark else "#1e293b"
        text_sec = "#94a3b8" if is_dark else "#475569"
        grid = "#233348" if is_dark else "#f1f5f9"
        input_bg = "#18202e" if is_dark else "#ffffff"

        self.setStyleSheet(f"background-color: {bg_panel};")
        if hasattr(self, 'lbl_title'):
            self.lbl_title.setStyleSheet(f"font-weight: bold; font-size: 11px; color: {text_pri};")
        if hasattr(self, 'lbl_count'):
            self.lbl_count.setStyleSheet(f"font-size: 10px; color: {text_sec};")
        if hasattr(self, 'search_edit'):
            self.search_edit.setStyleSheet(f"""
                QLineEdit {{
                    background-color: {input_bg};
                    color: {text_pri};
                    border: 1px solid {border};
                    border-radius: 4px;
                    padding: 2px 6px;
                    font-size: 11px;
                }}
                QLineEdit:focus {{
                    border: 1px solid {"#38bdf8" if is_dark else "#2563eb"};
                }}
            """)
        if hasattr(self, 'table'):
            self.table.setStyleSheet(f"""
                QTableWidget {{
                    background-color: {bg_table};
                    color: {text_pri};
                    border: 1px solid {border};
                    border-radius: 4px;
                    gridline-color: {grid};
                    font-size: 11px;
                }}
                QTableWidget::item {{
                    padding: 3px;
                }}
                QTableWidget::item:selected {{
                    background-color: {"#1e3a5f" if is_dark else "#dbeafe"};
                    color: {"#38bdf8" if is_dark else "#1e3a8a"};
                }}
                QHeaderView::section {{
                    background-color: {bg_hdr};
                    color: {text_sec};
                    border: none;
                    border-bottom: 1px solid {border};
                    padding: 4px;
                    font-weight: bold;
                    font-size: 10px;
                }}
            """)
        if hasattr(self, 'btn_unassign'):
            self.btn_unassign.setStyleSheet(f"""
                QPushButton {{
                    background-color: {"#202b3a" if is_dark else "#f1f5f9"};
                    color: {text_pri if is_dark else "#334155"};
                    border: 1px solid {border};
                    border-radius: 3px;
                    padding: 2px 8px;
                    font-size: 10.5px;
                }}
                QPushButton:hover {{
                    background-color: {"#28364a" if is_dark else "#e2e8f0"};
                }}
            """)
        if hasattr(self, 'btn_refresh'):
            self.btn_refresh.setStyleSheet(f"""
                QPushButton {{
                    background-color: {"#202b3a" if is_dark else "#f1f5f9"};
                    color: {text_pri if is_dark else "#334155"};
                    border: 1px solid {border};
                    border-radius: 3px;
                    font-size: 11px;
                }}
                QPushButton:hover {{
                    background-color: {"#28364a" if is_dark else "#e2e8f0"};
                }}
            """)

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        # Header info & count
        hdr_layout = QHBoxLayout()
        self.lbl_title = QLabel("Variable Manager")
        self.lbl_title.setStyleSheet("font-weight: bold; font-size: 11px; color: #1e293b;")
        hdr_layout.addWidget(self.lbl_title)

        self.lbl_count = QLabel("0 vars")
        self.lbl_count.setStyleSheet("font-size: 10px; color: #64748b;")
        hdr_layout.addWidget(self.lbl_count, alignment=Qt.AlignmentFlag.AlignRight)
        layout.addLayout(hdr_layout)

        # Search / Filter Bar
        self.search_edit = QLineEdit(self)
        self.search_edit.setPlaceholderText("Filter variables...")
        self.search_edit.setFixedHeight(24)
        self.search_edit.setStyleSheet("""
            QLineEdit {
                background-color: #ffffff;
                color: #1e293b;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                padding: 2px 6px;
                font-size: 11px;
            }
            QLineEdit:focus {
                border: 1px solid #2563eb;
            }
        """)
        self.search_edit.textChanged.connect(self._filter_table)
        layout.addWidget(self.search_edit)

        # Table Widget
        self.table = QTableWidget(self)
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Name", "Value", "Type"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 4px;
                gridline-color: #f1f5f9;
                font-size: 11px;
            }
            QTableWidget::item {
                padding: 3px;
            }
            QTableWidget::item:selected {
                background-color: #dbeafe;
                color: #1e3a8a;
            }
            QHeaderView::section {
                background-color: #f8fafc;
                color: #475569;
                border: none;
                border-bottom: 1px solid #e2e8f0;
                padding: 4px;
                font-weight: bold;
                font-size: 10px;
            }
        """)
        self.table.cellDoubleClicked.connect(self._on_cell_double_clicked)
        layout.addWidget(self.table)

        # Action Buttons Toolbar
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(4)

        self.btn_insert = QPushButton("Insert", self)
        self.btn_insert.setFixedHeight(24)
        self.btn_insert.setToolTip("Insert variable name into worksheet")
        self.btn_insert.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                color: #ffffff;
                border: none;
                border-radius: 3px;
                padding: 2px 8px;
                font-size: 10.5px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #1d4ed8; }
        """)
        self.btn_insert.clicked.connect(self._on_insert_clicked)
        btn_layout.addWidget(self.btn_insert)

        self.btn_unassign = QPushButton("Unassign", self)
        self.btn_unassign.setFixedHeight(24)
        self.btn_unassign.setToolTip("Unassign selected variable (restore to symbol)")
        self.btn_unassign.setStyleSheet("""
            QPushButton {
                background-color: #f1f5f9;
                color: #334155;
                border: 1px solid #cbd5e1;
                border-radius: 3px;
                padding: 2px 8px;
                font-size: 10.5px;
            }
            QPushButton:hover { background-color: #e2e8f0; }
        """)
        self.btn_unassign.clicked.connect(self._on_unassign_clicked)
        btn_layout.addWidget(self.btn_unassign)

        self.btn_clear = QPushButton("Clear All", self)
        self.btn_clear.setFixedHeight(24)
        self.btn_clear.setToolTip("Clear all user variables")
        self.btn_clear.setStyleSheet("""
            QPushButton {
                background-color: #fee2e2;
                color: #991b1b;
                border: 1px solid #fca5a5;
                border-radius: 3px;
                padding: 2px 6px;
                font-size: 10.5px;
            }
            QPushButton:hover { background-color: #fecaca; }
        """)
        self.btn_clear.clicked.connect(self._on_clear_all_clicked)
        btn_layout.addWidget(self.btn_clear)

        self.btn_refresh = QPushButton("↻", self)
        self.btn_refresh.setFixedWidth(24)
        self.btn_refresh.setFixedHeight(24)
        self.btn_refresh.setToolTip("Refresh variable list")
        self.btn_refresh.setStyleSheet("""
            QPushButton {
                background-color: #f1f5f9;
                color: #334155;
                border: 1px solid #cbd5e1;
                border-radius: 3px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #e2e8f0; }
        """)
        self.btn_refresh.clicked.connect(self.refresh)
        btn_layout.addWidget(self.btn_refresh)

        layout.addLayout(btn_layout)

    def refresh(self):
        """Refresh table with current variables from the CAS engine."""
        user_vars = self.engine.get_variables()
        self.table.setRowCount(0)

        row = 0
        for name, val in sorted(user_vars.items()):
            # Determine human readable type
            val_type = type(val).__name__
            if isinstance(val, (int, float, sp.Number)):
                val_type = "Number"
            elif isinstance(val, sp.Matrix):
                val_type = f"Matrix({val.rows}×{val.cols})"
            elif isinstance(val, sp.Eq):
                val_type = "Equation"
            elif callable(val):
                val_type = "Function"
            elif isinstance(val, sp.Symbol):
                val_type = "Symbol"
            elif isinstance(val, sp.Basic):
                val_type = "Expression"

            # Formatted value string
            val_str = str(val)
            if len(val_str) > 60:
                val_str = val_str[:57] + "..."

            self.table.insertRow(row)

            item_name = QTableWidgetItem(name)
            font = item_name.font()
            font.setBold(True)
            item_name.setFont(font)

            item_val = QTableWidgetItem(val_str)
            item_val.setToolTip(str(val))

            item_type = QTableWidgetItem(val_type)
            item_type.setForeground(QColor("#64748b"))

            self.table.setItem(row, 0, item_name)
            self.table.setItem(row, 1, item_val)
            self.table.setItem(row, 2, item_type)
            row += 1

        self.lbl_count.setText(f"{row} var{'s' if row != 1 else ''}")
        self._filter_table(self.search_edit.text())

    def _filter_table(self, text: str):
        """Filter table rows based on search text."""
        query = text.strip().lower()
        for r in range(self.table.rowCount()):
            name_item = self.table.item(r, 0)
            val_item = self.table.item(r, 1)
            type_item = self.table.item(r, 2)
            match = False
            if name_item and query in name_item.text().lower():
                match = True
            elif val_item and query in val_item.text().lower():
                match = True
            elif type_item and query in type_item.text().lower():
                match = True
            self.table.setRowHidden(r, not match)

    def _on_cell_double_clicked(self, row: int, col: int):
        item = self.table.item(row, 0)
        if item:
            self.insertVariable.emit(item.text())

    def _on_insert_clicked(self):
        row = self.table.currentRow()
        if row >= 0:
            item = self.table.item(row, 0)
            if item:
                self.insertVariable.emit(item.text())

    def _on_unassign_clicked(self):
        row = self.table.currentRow()
        if row >= 0:
            item = self.table.item(row, 0)
            if item:
                var_name = item.text()
                self.engine.evaluate(f"unassign('{var_name}')")
                self.variableUnassigned.emit(var_name)
                self.refresh()

    def _on_clear_all_clicked(self):
        reply = QMessageBox.question(
            self, "Clear All Variables",
            "Are you sure you want to unassign and clear all user variables?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            user_vars = list(self.engine.get_variables().keys())
            for v in user_vars:
                self.engine.evaluate(f"unassign('{v}')")
            self.refresh()
