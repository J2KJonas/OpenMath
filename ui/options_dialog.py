"""
OpenMath Options and Customization Dialog.
Provides an authentic, polished preferences window for configuring themes,
typography, CAS engine calculations, worksheet behavior, and keyboard shortcuts.
"""

from PyQt6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTabWidget, QRadioButton, QButtonGroup, QComboBox, QSpinBox,
    QCheckBox, QGroupBox, QFormLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QLineEdit, QMessageBox, QFrame, QScrollArea, QApplication
)
from PyQt6.QtCore import Qt, pyqtSignal, QSettings, QSize
from PyQt6.QtGui import QFont, QColor, QIcon, QKeySequence

from .theme import Theme


class OptionsDialog(QDialog):
    """
    Polished and modern preferences dialog for OpenMath desktop application.
    """
    settingsApplied = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_win = parent
        self.setWindowTitle("Options & Settings")
        self.setMinimumSize(680, 520)
        self.resize(720, 560)

        # Cache initial settings
        self.settings = QSettings("OpenMath", "OpenMath")
        self._load_current_values()

        self._build_ui()
        self._apply_dialog_theme()

    def _load_current_values(self):
        """Read active values from main window and QSettings."""
        # 1. Theme
        if self.main_win and hasattr(self.main_win, 'theme_mode'):
            self.val_theme = self.main_win.theme_mode
        else:
            self.val_theme = self.settings.value("theme_mode", Theme.LIGHT)

        # 2. Decimal separator
        from cas_engine.formatter import MathFormatter
        self.val_decimal = getattr(MathFormatter, 'decimal_separator', ',')

        # 3. Typography
        if self.main_win and hasattr(self.main_win, 'combo_font'):
            self.val_font_family = self.main_win.combo_font.currentText()
        else:
            self.val_font_family = self.settings.value("default_font_family", "Times New Roman")

        if self.main_win and hasattr(self.main_win, 'combo_font_size'):
            try:
                self.val_font_size = int(self.main_win.combo_font_size.currentText())
            except ValueError:
                self.val_font_size = 12
        else:
            self.val_font_size = int(self.settings.value("default_font_size", 12))

        # 4. Zoom
        if self.main_win and hasattr(self.main_win, 'worksheet') and self.main_win.worksheet:
            self.val_zoom = getattr(self.main_win.worksheet, 'zoom_percent', 100)
        else:
            self.val_zoom = int(self.settings.value("default_zoom", 100))

        # 5. Panel & Toolbar visibility
        if self.main_win:
            self.val_show_palette = self.main_win.palette_dock.isVisible() if hasattr(self.main_win, 'palette_dock') else True
            self.val_show_context = self.main_win.context_dock.isVisible() if hasattr(self.main_win, 'context_dock') else False
            self.val_show_plot = self.main_win.plot_dock.isVisible() if hasattr(self.main_win, 'plot_dock') else False
            self.val_show_main_toolbar = self.main_win.main_toolbar.isVisible() if hasattr(self.main_win, 'main_toolbar') else True
            self.val_show_tab_bar = self.main_win.tab_bar_toolbar.isVisible() if hasattr(self.main_win, 'tab_bar_toolbar') else True
            self.val_show_context_bar = self.main_win.context_toolbar.isVisible() if hasattr(self.main_win, 'context_toolbar') else True
            self.val_show_status = self.main_win.statusBar().isVisible() if hasattr(self.main_win, 'statusBar') else True
        else:
            self.val_show_palette = str(self.settings.value("palette_dock_visible", "true")).lower() in ("true", "1")
            self.val_show_context = str(self.settings.value("context_dock_visible", "false")).lower() in ("true", "1")
            self.val_show_plot = str(self.settings.value("plot_dock_visible", "false")).lower() in ("true", "1")
            self.val_show_main_toolbar = str(self.settings.value("main_toolbar_visible", "true")).lower() in ("true", "1")
            self.val_show_tab_bar = str(self.settings.value("tab_bar_toolbar_visible", "true")).lower() in ("true", "1")
            self.val_show_context_bar = str(self.settings.value("context_toolbar_visible", "true")).lower() in ("true", "1")
            self.val_show_status = True

        # 6. Precision & Engine
        self.val_precision = int(self.settings.value("float_precision", 10))
        self.val_timeout = int(self.settings.value("exec_timeout", 10))

        # 7. Worksheet
        self.val_default_mode = self.settings.value("default_cell_mode", "math")
        self.val_editable = str(self.settings.value("default_editable", "true")).lower() in ("true", "1")

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 14, 16, 14)
        main_layout.setSpacing(12)

        # Header banner
        header = QWidget()
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(4, 2, 4, 8)
        h_layout.setSpacing(10)

        lbl_icon = QLabel("⚙️")
        lbl_icon.setStyleSheet("font-size: 26px;")
        h_layout.addWidget(lbl_icon)

        title_layout = QVBoxLayout()
        title_layout.setSpacing(2)
        lbl_title = QLabel("Options & Preferences")
        lbl_title.setStyleSheet("font-size: 16px; font-weight: bold;")
        lbl_desc = QLabel("Customize theme colors, calculation format, typography, and editor shortcuts.")
        lbl_desc.setStyleSheet("color: #64748b; font-size: 11px;")
        title_layout.addWidget(lbl_title)
        title_layout.addWidget(lbl_desc)
        h_layout.addLayout(title_layout)
        h_layout.addStretch()

        main_layout.addWidget(header)

        # Tab Widget
        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_appearance_tab(), "Appearance & Theme")
        self.tabs.addTab(self._build_calculation_tab(), "Calculation & CAS")
        self.tabs.addTab(self._build_editor_tab(), "Worksheet & Editor")
        self.tabs.addTab(self._build_shortcuts_tab(), "Keyboard Shortcuts")
        main_layout.addWidget(self.tabs, 1)

        # Bottom Button Bar
        btn_bar = QHBoxLayout()
        btn_bar.setContentsMargins(0, 8, 0, 0)
        btn_bar.setSpacing(8)

        self.btn_defaults = QPushButton("Reset to Defaults")
        self.btn_defaults.setToolTip("Restore standard factory default settings")
        self.btn_defaults.clicked.connect(self._on_reset_defaults)
        btn_bar.addWidget(self.btn_defaults)

        btn_bar.addStretch()

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        btn_bar.addWidget(self.btn_cancel)

        self.btn_apply = QPushButton("Apply")
        self.btn_apply.clicked.connect(self._on_apply)
        btn_bar.addWidget(self.btn_apply)

        self.btn_ok = QPushButton("OK")
        self.btn_ok.setDefault(True)
        self.btn_ok.setStyleSheet("font-weight: bold; background-color: #2563eb; color: #ffffff; padding: 5px 16px; border-radius: 4px;")
        self.btn_ok.clicked.connect(self._on_ok)
        btn_bar.addWidget(self.btn_ok)

        main_layout.addLayout(btn_bar)

    def _build_appearance_tab(self) -> QWidget:
        widget = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(14)

        # 1. Theme Selection Group
        grp_theme = QGroupBox("Theme Mode")
        grp_theme_layout = QVBoxLayout(grp_theme)
        grp_theme_layout.setSpacing(8)

        self.bg_theme = QButtonGroup(self)
        self.rb_light = QRadioButton("☀️  Light Mode (Maple Classic)")
        self.rb_light.setToolTip("Classic clean light gray palette with blue accents")
        self.rb_dark = QRadioButton("🌙  Dark Mode (Slate Dark)")
        self.rb_dark.setToolTip("High contrast dark workspace optimized for low light")

        self.bg_theme.addButton(self.rb_light, 0)
        self.bg_theme.addButton(self.rb_dark, 1)

        if self.val_theme == Theme.DARK:
            self.rb_dark.setChecked(True)
        else:
            self.rb_light.setChecked(True)

        grp_theme_layout.addWidget(self.rb_light)
        grp_theme_layout.addWidget(self.rb_dark)
        layout.addWidget(grp_theme)

        # 2. Typography Group
        grp_font = QGroupBox("Default Typography")
        form_font = QFormLayout(grp_font)
        form_font.setContentsMargins(12, 12, 12, 12)
        form_font.setSpacing(10)

        self.combo_family = QComboBox()
        self.combo_family.addItems([
            "Times New Roman", "Arial", "Cambria Math", "Segoe UI",
            "Consolas", "Courier New", "Helvetica", "Georgia"
        ])
        idx_family = self.combo_family.findText(self.val_font_family)
        if idx_family >= 0:
            self.combo_family.setCurrentIndex(idx_family)

        self.combo_size = QComboBox()
        self.combo_size.addItems(["9", "10", "11", "12", "14", "16", "18", "20", "24"])
        idx_size = self.combo_size.findText(str(self.val_font_size))
        if idx_size >= 0:
            self.combo_size.setCurrentIndex(idx_size)

        form_font.addRow("Font Family:", self.combo_family)
        form_font.addRow("Base Font Size:", self.combo_size)
        layout.addWidget(grp_font)

        # 3. Zoom Group
        grp_zoom = QGroupBox("Workspace Zoom")
        form_zoom = QFormLayout(grp_zoom)
        form_zoom.setContentsMargins(12, 12, 12, 12)
        form_zoom.setSpacing(10)

        self.combo_zoom = QComboBox()
        self.combo_zoom.addItems(["50%", "75%", "100%", "125%", "150%", "200%"])
        idx_zoom = self.combo_zoom.findText(f"{self.val_zoom}%")
        if idx_zoom >= 0:
            self.combo_zoom.setCurrentIndex(idx_zoom)
        else:
            self.combo_zoom.setCurrentText("100%")

        form_zoom.addRow("Default Zoom Level:", self.combo_zoom)
        layout.addWidget(grp_zoom)

        # 4. Dock Panels & Toolbars Group
        grp_panels = QGroupBox("Panels & Toolbars")
        v_panels = QVBoxLayout(grp_panels)
        v_panels.setSpacing(8)

        self.chk_palette = QCheckBox("Show Palettes sidebar on the left")
        self.chk_palette.setChecked(self.val_show_palette)
        self.chk_context = QCheckBox("Show Context operations panel on the right")
        self.chk_context.setChecked(self.val_show_context)
        self.chk_plot = QCheckBox("Show Plot & Graphics panel")
        self.chk_plot.setChecked(self.val_show_plot)
        self.chk_main_toolbar = QCheckBox("Show Main Toolbar")
        self.chk_main_toolbar.setChecked(self.val_show_main_toolbar)
        self.chk_tab_bar = QCheckBox("Show Document Tabs")
        self.chk_tab_bar.setChecked(self.val_show_tab_bar)
        self.chk_context_bar = QCheckBox("Show Context Bar")
        self.chk_context_bar.setChecked(self.val_show_context_bar)
        self.chk_status = QCheckBox("Show Status Bar at bottom")
        self.chk_status.setChecked(self.val_show_status)

        v_panels.addWidget(self.chk_palette)
        v_panels.addWidget(self.chk_context)
        v_panels.addWidget(self.chk_plot)
        v_panels.addWidget(self.chk_main_toolbar)
        v_panels.addWidget(self.chk_tab_bar)
        v_panels.addWidget(self.chk_context_bar)
        v_panels.addWidget(self.chk_status)
        layout.addWidget(grp_panels)

        layout.addStretch()
        scroll.setWidget(content)

        outer = QVBoxLayout(widget)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)
        return widget

    def _build_calculation_tab(self) -> QWidget:
        widget = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(14)

        # 1. Decimal Separator Group
        grp_dec = QGroupBox("Decimal Notation")
        v_dec = QVBoxLayout(grp_dec)
        v_dec.setSpacing(8)

        self.bg_decimal = QButtonGroup(self)
        self.rb_comma = QRadioButton("Comma separator: 3,14 (European / Danish standard)")
        self.rb_dot = QRadioButton("Period separator: 3.14 (US / International standard)")
        self.bg_decimal.addButton(self.rb_comma, 0)
        self.bg_decimal.addButton(self.rb_dot, 1)

        if self.val_decimal == '.':
            self.rb_dot.setChecked(True)
        else:
            self.rb_comma.setChecked(True)

        v_dec.addWidget(self.rb_comma)
        v_dec.addWidget(self.rb_dot)
        layout.addWidget(grp_dec)

        # 2. Precision & Calculation
        grp_calc = QGroupBox("Calculation Engine Settings")
        form_calc = QFormLayout(grp_calc)
        form_calc.setContentsMargins(12, 12, 12, 12)
        form_calc.setSpacing(10)

        self.spin_precision = QSpinBox()
        self.spin_precision.setRange(1, 50)
        self.spin_precision.setValue(self.val_precision)
        self.spin_precision.setSuffix(" digits")

        self.spin_timeout = QSpinBox()
        self.spin_timeout.setRange(1, 120)
        self.spin_timeout.setValue(self.val_timeout)
        self.spin_timeout.setSuffix(" seconds")

        self.chk_auto_simplify = QCheckBox("Automatically simplify algebraic answers")
        self.chk_auto_simplify.setChecked(True)

        form_calc.addRow("Numeric Float Precision:", self.spin_precision)
        form_calc.addRow("Execution Timeout:", self.spin_timeout)
        form_calc.addRow("", self.chk_auto_simplify)
        layout.addWidget(grp_calc)

        layout.addStretch()
        scroll.setWidget(content)

        outer = QVBoxLayout(widget)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)
        return widget

    def _build_editor_tab(self) -> QWidget:
        widget = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(14)

        # 1. Default Cell Mode
        grp_mode = QGroupBox("Default Input Mode for New Cells")
        v_mode = QVBoxLayout(grp_mode)
        v_mode.setSpacing(8)

        self.bg_mode = QButtonGroup(self)
        self.rb_mode_math = QRadioButton("Math Mode (Interactive executable 2D math)")
        self.rb_mode_text = QRadioButton("Text Mode (Narrative documentation and explanations)")
        self.rb_mode_nonexec = QRadioButton("Nonexecutable Math (Mathematical notation without evaluation)")

        self.bg_mode.addButton(self.rb_mode_math, 0)
        self.bg_mode.addButton(self.rb_mode_text, 1)
        self.bg_mode.addButton(self.rb_mode_nonexec, 2)

        if self.val_default_mode == "text":
            self.rb_mode_text.setChecked(True)
        elif self.val_default_mode == "nonexec":
            self.rb_mode_nonexec.setChecked(True)
        else:
            self.rb_mode_math.setChecked(True)

        v_mode.addWidget(self.rb_mode_math)
        v_mode.addWidget(self.rb_mode_text)
        v_mode.addWidget(self.rb_mode_nonexec)
        layout.addWidget(grp_mode)

        # 2. Worksheet Behavior
        grp_behavior = QGroupBox("Editor Behavior")
        v_beh = QVBoxLayout(grp_behavior)
        v_beh.setSpacing(8)

        self.chk_editable = QCheckBox("Worksheets are editable by default")
        self.chk_editable.setChecked(self.val_editable)

        self.chk_auto_scroll = QCheckBox("Automatically keep evaluated cell visible on screen")
        self.chk_auto_scroll.setChecked(True)

        self.chk_tab_close_confirm = QCheckBox("Prompt confirmation when closing worksheets with unsaved changes")
        self.chk_tab_close_confirm.setChecked(True)

        v_beh.addWidget(self.chk_editable)
        v_beh.addWidget(self.chk_auto_scroll)
        v_beh.addWidget(self.chk_tab_close_confirm)
        layout.addWidget(grp_behavior)

        layout.addStretch()
        scroll.setWidget(content)

        outer = QVBoxLayout(widget)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)
        return widget

    def _build_shortcuts_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # Search filter
        search_box = QHBoxLayout()
        lbl_s = QLabel("Search Shortcuts:")
        self.edit_search_shortcuts = QLineEdit()
        self.edit_search_shortcuts.setPlaceholderText("Filter shortcuts by key or action...")
        self.edit_search_shortcuts.textChanged.connect(self._filter_shortcuts)
        search_box.addWidget(lbl_s)
        search_box.addWidget(self.edit_search_shortcuts)
        layout.addLayout(search_box)

        # Shortcuts table
        self.tbl_shortcuts = QTableWidget()
        self.tbl_shortcuts.setColumnCount(3)
        self.tbl_shortcuts.setHorizontalHeaderLabels(["Action", "Shortcut", "Category"])
        self.tbl_shortcuts.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tbl_shortcuts.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl_shortcuts.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl_shortcuts.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tbl_shortcuts.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        self.shortcut_data = [
            ("Evaluate Cell & Advance", "Shift + Enter", "Execution"),
            ("Evaluate Active Group", "Enter", "Execution"),
            ("Evaluate Entire Document", "Ctrl + R", "Execution"),
            ("Insert Fraction Template", "/", "Templates"),
            ("Insert Exponent / Superscript", "^", "Templates"),
            ("Insert Subscript Index", "_", "Templates"),
            ("Toggle Math / Text Mode", "F5", "Worksheet"),
            ("Assign Variable / New Statement", ": + Enter", "Worksheet"),
            ("Autocomplete / Command Palette", "Ctrl + Space / Esc", "Editing"),
            ("Custom Size Matrix Wizard", "Ctrl + M", "Tools"),
            ("Open Options & Preferences", "Ctrl + ,", "Application"),
            ("Toggle Light / Dark Theme", "Ctrl + T", "Appearance"),
            ("Zoom In / Out", "Ctrl + Plus / Minus", "View"),
            ("Reset Zoom to 100%", "Ctrl + 0", "View"),
            ("New Document Tab", "Ctrl + N", "File"),
            ("Save Worksheet", "Ctrl + S", "File"),
            ("Export to PDF", "Ctrl + P", "File"),
        ]

        self._populate_shortcuts(self.shortcut_data)
        layout.addWidget(self.tbl_shortcuts)

        return widget

    def _populate_shortcuts(self, rows):
        self.tbl_shortcuts.setRowCount(len(rows))
        for r_idx, (act, sc, cat) in enumerate(rows):
            item_act = QTableWidgetItem(act)
            item_sc = QTableWidgetItem(sc)
            item_cat = QTableWidgetItem(cat)
            item_sc.setFont(QFont("Consolas, Courier New", 10, QFont.Weight.Bold))
            self.tbl_shortcuts.setItem(r_idx, 0, item_act)
            self.tbl_shortcuts.setItem(r_idx, 1, item_sc)
            self.tbl_shortcuts.setItem(r_idx, 2, item_cat)

    def _filter_shortcuts(self, query: str):
        q = query.strip().lower()
        if not q:
            filtered = self.shortcut_data
        else:
            filtered = [r for r in self.shortcut_data if q in r[0].lower() or q in r[1].lower() or q in r[2].lower()]
        self._populate_shortcuts(filtered)

    def _apply_dialog_theme(self):
        """Style the dialog based on the current theme mode."""
        is_dark = (self.val_theme == Theme.DARK)
        if is_dark:
            self.setStyleSheet("""
                QDialog {
                    background-color: #0f172a;
                    color: #f1f5f9;
                }
                QGroupBox {
                    font-weight: bold;
                    border: 1px solid #334155;
                    border-radius: 6px;
                    margin-top: 10px;
                    padding-top: 12px;
                    color: #e2e8f0;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    subcontrol-position: top left;
                    left: 10px;
                    padding: 0 4px;
                }
                QTabWidget::pane {
                    border: 1px solid #334155;
                    border-radius: 4px;
                    background-color: #1e293b;
                }
                QTabBar::tab {
                    background: #0f172a;
                    color: #94a3b8;
                    padding: 8px 16px;
                    border-top-left-radius: 4px;
                    border-top-right-radius: 4px;
                    margin-right: 2px;
                }
                QTabBar::tab:selected {
                    background: #1e293b;
                    color: #38bdf8;
                    font-weight: bold;
                    border-bottom: 2px solid #38bdf8;
                }
                QTableWidget {
                    background-color: #0f172a;
                    color: #f1f5f9;
                    gridline-color: #334155;
                    border: 1px solid #334155;
                    border-radius: 4px;
                }
                QHeaderView::section {
                    background-color: #1e293b;
                    color: #cbd5e1;
                    padding: 4px;
                    border: 1px solid #334155;
                }
                QComboBox, QSpinBox, QLineEdit {
                    background-color: #0f172a;
                    color: #f8fafc;
                    border: 1px solid #475569;
                    border-radius: 4px;
                    padding: 4px 8px;
                }
                QPushButton {
                    background-color: #1e293b;
                    color: #e2e8f0;
                    border: 1px solid #475569;
                    border-radius: 4px;
                    padding: 5px 12px;
                }
                QPushButton:hover {
                    background-color: #334155;
                }
            """)
        else:
            self.setStyleSheet("""
                QDialog {
                    background-color: #f8fafc;
                    color: #0f172a;
                }
                QGroupBox {
                    font-weight: bold;
                    border: 1px solid #cbd5e1;
                    border-radius: 6px;
                    margin-top: 10px;
                    padding-top: 12px;
                    color: #1e293b;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    subcontrol-position: top left;
                    left: 10px;
                    padding: 0 4px;
                }
                QTabWidget::pane {
                    border: 1px solid #cbd5e1;
                    border-radius: 4px;
                    background-color: #ffffff;
                }
                QTabBar::tab {
                    background: #e2e8f0;
                    color: #475569;
                    padding: 8px 16px;
                    border-top-left-radius: 4px;
                    border-top-right-radius: 4px;
                    margin-right: 2px;
                }
                QTabBar::tab:selected {
                    background: #ffffff;
                    color: #1d4ed8;
                    font-weight: bold;
                    border-bottom: 2px solid #2563eb;
                }
                QTableWidget {
                    background-color: #ffffff;
                    color: #1e293b;
                    gridline-color: #e2e8f0;
                    border: 1px solid #cbd5e1;
                    border-radius: 4px;
                }
                QHeaderView::section {
                    background-color: #f1f5f9;
                    color: #475569;
                    padding: 4px;
                    border: 1px solid #cbd5e1;
                }
                QComboBox, QSpinBox, QLineEdit {
                    background-color: #ffffff;
                    color: #0f172a;
                    border: 1px solid #cbd5e1;
                    border-radius: 4px;
                    padding: 4px 8px;
                }
                QPushButton {
                    background-color: #ffffff;
                    color: #334155;
                    border: 1px solid #cbd5e1;
                    border-radius: 4px;
                    padding: 5px 12px;
                }
                QPushButton:hover {
                    background-color: #f1f5f9;
                }
            """)

    def _on_apply(self):
        """Apply all configured options to the running application and persist to QSettings."""
        # 1. Theme
        target_theme = Theme.DARK if self.rb_dark.isChecked() else Theme.LIGHT
        if self.main_win and hasattr(self.main_win, 'set_theme'):
            self.main_win.set_theme(target_theme)
        else:
            self.settings.setValue("theme_mode", target_theme)

        # 2. Decimal separator
        target_sep = '.' if self.rb_dot.isChecked() else ','
        if self.main_win and hasattr(self.main_win, '_set_decimal_separator'):
            self.main_win._set_decimal_separator(target_sep)
        self.settings.setValue("decimal_separator", target_sep)

        # 3. Typography
        target_family = self.combo_family.currentText()
        target_size = int(self.combo_size.currentText())
        if self.main_win and hasattr(self.main_win, 'combo_font'):
            self.main_win.combo_font.setCurrentText(target_family)
        if self.main_win and hasattr(self.main_win, 'combo_font_size'):
            self.main_win.combo_font_size.setCurrentText(str(target_size))
        self.settings.setValue("default_font_family", target_family)
        self.settings.setValue("default_font_size", target_size)

        # 4. Zoom
        zoom_str = self.combo_zoom.currentText().replace("%", "")
        try:
            target_zoom = int(zoom_str)
            if self.main_win and hasattr(self.main_win, 'set_zoom'):
                self.main_win.set_zoom(target_zoom)
            self.settings.setValue("default_zoom", target_zoom)
        except ValueError:
            pass

        # 5. Panel & Toolbar visibility
        if self.main_win:
            if hasattr(self.main_win, 'palette_dock'):
                self.main_win.palette_dock.setVisible(self.chk_palette.isChecked())
            if hasattr(self.main_win, 'context_dock'):
                self.main_win.context_dock.setVisible(self.chk_context.isChecked())
            if hasattr(self.main_win, 'plot_dock'):
                self.main_win.plot_dock.setVisible(self.chk_plot.isChecked())
            if hasattr(self.main_win, 'main_toolbar'):
                self.main_win.main_toolbar.setVisible(self.chk_main_toolbar.isChecked())
            if hasattr(self.main_win, 'tab_bar_toolbar'):
                self.main_win.tab_bar_toolbar.setVisible(self.chk_tab_bar.isChecked())
            if hasattr(self.main_win, 'context_toolbar'):
                self.main_win.context_toolbar.setVisible(self.chk_context_bar.isChecked())
            if hasattr(self.main_win, 'statusBar'):
                self.main_win.statusBar().setVisible(self.chk_status.isChecked())
            if hasattr(self.main_win, 'save_settings'):
                self.main_win.save_settings()

        self.settings.setValue("palette_dock_visible", self.chk_palette.isChecked())
        self.settings.setValue("context_dock_visible", self.chk_context.isChecked())
        self.settings.setValue("plot_dock_visible", self.chk_plot.isChecked())
        self.settings.setValue("main_toolbar_visible", self.chk_main_toolbar.isChecked())
        self.settings.setValue("tab_bar_toolbar_visible", self.chk_tab_bar.isChecked())
        self.settings.setValue("context_toolbar_visible", self.chk_context_bar.isChecked())

        # 6. Precision & Timeout
        self.settings.setValue("float_precision", self.spin_precision.value())
        self.settings.setValue("exec_timeout", self.spin_timeout.value())

        # 7. Worksheet mode & editable
        if self.rb_mode_text.isChecked():
            cell_mode = "text"
        elif self.rb_mode_nonexec.isChecked():
            cell_mode = "nonexec"
        else:
            cell_mode = "math"
        self.settings.setValue("default_cell_mode", cell_mode)
        self.settings.setValue("default_editable", self.chk_editable.isChecked())

        if self.main_win and hasattr(self.main_win, 'chk_editable'):
            self.main_win.chk_editable.setChecked(self.chk_editable.isChecked())

        self.settings.sync()
        self.settingsApplied.emit()
        self._apply_dialog_theme()

    def _on_ok(self):
        self._on_apply()
        self.accept()

    def _on_reset_defaults(self):
        reply = QMessageBox.question(
            self,
            "Reset Options",
            "Are you sure you want to reset all options to standard factory defaults?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.rb_light.setChecked(True)
            self.rb_comma.setChecked(True)
            self.combo_family.setCurrentText("Times New Roman")
            self.combo_size.setCurrentText("12")
            self.combo_zoom.setCurrentText("100%")
            self.chk_palette.setChecked(True)
            self.chk_context.setChecked(False)
            self.chk_plot.setChecked(False)
            self.chk_main_toolbar.setChecked(True)
            self.chk_tab_bar.setChecked(True)
            self.chk_context_bar.setChecked(True)
            self.chk_status.setChecked(True)
            self.spin_precision.setValue(10)
            self.spin_timeout.setValue(10)
            self.chk_auto_simplify.setChecked(True)
            self.rb_mode_math.setChecked(True)
            self.chk_editable.setChecked(True)
            self.chk_auto_scroll.setChecked(True)
            self.chk_tab_close_confirm.setChecked(True)
            self._on_apply()
