"""
Main Application Window for OpenMath Computer Algebra System (CAS).
Reproduces the complete visual layout, menus, toolbars, and workflow:
- Start Document is Start.mw by default with two buttons: 'New Document' and 'Open Documents'
- Only Start.mw is opened initially (no other tabs at first)
- Title Bar: Start.mw - [Server 3] - OpenMath
- Traditional Menu Bar: File, Edit, View, Insert, Format, Evaluate, Tools, Window, Help
- Compact Toolbar & Full-width Document Tabs Bar
- Context Bar: [Text], [Nonexecutable Math], [Math], [C], [Times New Roman ▾], [12 ▾], B, I, U, alignments
- Left Palette Dock: Favorites, Expression 2D templates, Common Symbols, Calculus, Greek, Embedded Systems, Units, Plots
- Central Area: Stacked Document System (StartPageView & WorksheetView pages)
- Right Context Panel: '>>' collapse button, prominent Math Editor Shortcuts, and dynamic operations
- Authentic sunken segmented Status Bar: Ready, Editable, Profile, Path, Memory, Time, Zoom, Math Mode
"""

import os
import sys
import json
import subprocess
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QDockWidget, QMenuBar, QMenu, QToolBar, QStatusBar, QTabWidget, QTabBar,
    QFileDialog, QMessageBox, QLabel, QPushButton, QToolButton,
    QComboBox, QLineEdit, QCheckBox, QApplication, QSizePolicy,
    QStackedWidget, QCompleter, QDialog, QGroupBox, QDialogButtonBox,
    QWidgetAction, QGridLayout, QFrame
)
from PyQt6.QtGui import (
    QAction, QIcon, QFont, QKeySequence, QPixmap, QPainter, QColor, QPen,
    QIntValidator, QPalette, QDesktopServices, QCursor
)
from PyQt6.QtCore import Qt, QSize, QEvent, QTimer, QRect, QSettings, QPoint, QUrl, QPointF, QRectF
try:
    from PyQt6 import sip
except ImportError:
    import sip

from cas_engine import CASEngine, PlotData
from .start_page import StartPageView
from .worksheet_view import WorksheetView
from .palette_panel import PalettePanel
from .context_panel import ContextPanel
from .plot_panel import PlotPanel
from .matrix_dialog import MatrixDialog
from .loading_overlay import LoadingOverlay
from .theme import Theme


def get_current_process_memory_mb() -> float:
    """Retrieve the current working set memory usage in megabytes."""
    try:
        if sys.platform == "win32":
            import ctypes
            from ctypes import wintypes
            class PROCESS_MEMORY_COUNTERS_EX(ctypes.Structure):
                _fields_ = [
                    ('cb', wintypes.DWORD),
                    ('PageFaultCount', wintypes.DWORD),
                    ('PeakWorkingSetSize', ctypes.c_size_t),
                    ('WorkingSetSize', ctypes.c_size_t),
                    ('QuotaPeakPagedPoolUsage', ctypes.c_size_t),
                    ('QuotaPagedPoolUsage', ctypes.c_size_t),
                    ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t),
                    ('QuotaNonPagedPoolUsage', ctypes.c_size_t),
                    ('PagefileUsage', ctypes.c_size_t),
                    ('PeakPagefileUsage', ctypes.c_size_t),
                    ('PrivateUsage', ctypes.c_size_t),
                ]
            kernel32 = ctypes.windll.kernel32
            psapi = ctypes.windll.psapi
            kernel32.GetCurrentProcess.restype = wintypes.HANDLE
            psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD]
            psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
            pmc = PROCESS_MEMORY_COUNTERS_EX()
            pmc.cb = ctypes.sizeof(pmc)
            p = kernel32.GetCurrentProcess()
            if psapi.GetProcessMemoryInfo(p, ctypes.byref(pmc), pmc.cb):
                return pmc.WorkingSetSize / (1024.0 * 1024.0)
        else:
            import resource
            usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            if sys.platform == "darwin":
                return usage / (1024.0 * 1024.0)
            return usage / 1024.0
    except Exception:
        pass
    return 0.0


def create_toolbar_action_icon(name: str, color: str = None) -> QIcon:
    """Generate crisp, retina-sharp vector icons for formatting toolbar buttons."""
    pm = QPixmap(32, 32)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

    main_c = QColor(color) if color else QColor('#0f172a')

    if name == 'bold':
        p.setFont(QFont('Segoe UI', 15, QFont.Weight.Bold))
        p.setPen(main_c)
        p.drawText(QRect(0, 0, 32, 32), Qt.AlignmentFlag.AlignCenter, 'B')
    elif name == 'italic':
        f = QFont('Times New Roman', 16, QFont.Weight.Bold)
        f.setItalic(True)
        p.setFont(f)
        p.setPen(main_c)
        p.drawText(QRect(0, 0, 32, 32), Qt.AlignmentFlag.AlignCenter, 'I')
    elif name == 'underline':
        p.setFont(QFont('Segoe UI', 13, QFont.Weight.Bold))
        p.setPen(main_c)
        p.drawText(QRect(0, -3, 32, 28), Qt.AlignmentFlag.AlignCenter, 'U')
        pen = QPen(main_c, 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.drawLine(8, 25, 24, 25)
    elif name == 'align_left':
        pen = QPen(main_c, 2.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.drawLine(5, 7, 27, 7)
        p.drawLine(5, 13, 19, 13)
        p.drawLine(5, 19, 27, 19)
        p.drawLine(5, 25, 15, 25)
    elif name == 'align_center':
        pen = QPen(main_c, 2.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.drawLine(5, 7, 27, 7)
        p.drawLine(9, 13, 23, 13)
        p.drawLine(5, 19, 27, 19)
        p.drawLine(10, 25, 22, 25)
    elif name == 'align_right':
        pen = QPen(main_c, 2.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.drawLine(5, 7, 27, 7)
        p.drawLine(13, 13, 27, 13)
        p.drawLine(5, 19, 27, 19)
        p.drawLine(17, 25, 27, 25)
    elif name == 'outdent':
        pen = QPen(main_c, 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.drawLine(17, 16, 5, 16)
        p.drawLine(9, 12, 5, 16)
        p.drawLine(9, 20, 5, 16)
        p.drawLine(20, 9, 28, 9)
        p.drawLine(20, 16, 28, 16)
        p.drawLine(20, 23, 28, 23)
    elif name == 'indent':
        pen = QPen(main_c, 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.drawLine(5, 16, 17, 16)
        p.drawLine(13, 12, 17, 16)
        p.drawLine(13, 20, 17, 16)
        p.drawLine(20, 9, 28, 9)
        p.drawLine(20, 16, 28, 16)
        p.drawLine(20, 23, 28, 23)
    elif name == 'line_spacing':
        pen = QPen(main_c, 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        # Vertical line with up and down arrows
        p.drawLine(7, 10, 7, 22)
        p.drawLine(4, 12, 7, 8)
        p.drawLine(10, 12, 7, 8)
        p.drawLine(4, 20, 7, 24)
        p.drawLine(10, 20, 7, 24)
        # Horizontal text lines
        p.drawLine(14, 8, 27, 8)
        p.drawLine(14, 13, 27, 13)
        p.drawLine(14, 19, 27, 19)
        p.drawLine(14, 24, 27, 24)
    elif name == 'text_color':
        # "A" with a colored underline bar
        p.setFont(QFont('Segoe UI', 13, QFont.Weight.Bold))
        p.setPen(main_c)
        p.drawText(QRect(0, -2, 32, 28), Qt.AlignmentFlag.AlignCenter, 'A')
        # Colored bar (red by default in icon; actual swatch on button)
        pen = QPen(QColor('#e11d48'), 3.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.drawLine(8, 26, 24, 26)
    elif name == 'highlight':
        # Marker pen icon: rectangle body + tip
        pen = QPen(main_c, 1.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.setBrush(QColor('#fde047'))
        p.drawRoundedRect(10, 5, 12, 17, 2, 2)
        p.setBrush(QColor('#ca8a04'))
        p.drawRect(10, 20, 12, 4)
        # tip
        p.setBrush(QColor('#92400e'))
        from PyQt6.QtGui import QPolygon
        from PyQt6.QtCore import QPoint
        poly = QPolygon([QPoint(11, 24), QPoint(21, 24), QPoint(19, 28), QPoint(13, 28)])
        p.drawPolygon(poly)
    elif name in ('section', 'header'):
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor('#475569'))
        from PyQt6.QtGui import QPolygonF
        from PyQt6.QtCore import QPointF
        # Offset to the left so the arrow is centered in the button portion of the split dropdown button
        poly = QPolygonF([QPointF(1, 12), QPointF(15, 12), QPointF(8, 21)])
        p.drawPolygon(poly)

    p.end()
    return QIcon(pm)


from PyQt6.QtWidgets import QColorDialog


class ColorSwatchButton(QPushButton):
    """
    A toolbar button that shows a color swatch strip under an icon letter.
    Clicking the main area opens a QColorDialog; right-click resets to default.
    """
    from PyQt6.QtCore import pyqtSignal
    colorReset = pyqtSignal()

    def __init__(self, icon_name: str, default_color: QColor, tooltip: str, parent=None):
        super().__init__(parent)
        self._icon_name = icon_name
        self._color = default_color
        self._default_color = default_color
        self._theme_mode = "light"
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setFixedSize(26, 24)
        self.setToolTip(tooltip)
        self._update_icon()
        self.update_theme("light")

    def update_theme(self, mode: str):
        self._theme_mode = mode
        is_dark = (mode == "dark")
        bg = "#202b3a" if is_dark else "#ffffff"
        border = "#2e3b4f" if is_dark else "#cbd5e1"
        hover_bg = "#2a384c" if is_dark else "#f1f5f9"
        hover_border = "#38bdf8" if is_dark else "#94a3b8"
        pressed_bg = "#1b2533" if is_dark else "#e2e8f0"
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg};
                border: 1px solid {border};
                border-radius: 3px;
                padding: 0px;
            }}
            QPushButton:hover {{
                background-color: {hover_bg};
                border-color: {hover_border};
            }}
            QPushButton:pressed {{
                background-color: {pressed_bg};
            }}
        """)
        self._update_icon()

    def _update_icon(self):
        pm = QPixmap(32, 32)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        is_dark = (getattr(self, '_theme_mode', 'light') == 'dark')
        icon_fg = QColor('#f8fafc') if is_dark else QColor('#0f172a')
        if self._icon_name == 'text_color':
            p.setFont(QFont('Segoe UI', 13, QFont.Weight.Bold))
            p.setPen(icon_fg)
            p.drawText(QRect(0, -2, 32, 26), Qt.AlignmentFlag.AlignCenter, 'A')
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(self._color)
            p.drawRect(7, 26, 18, 4)
        elif self._icon_name == 'highlight':
            # marker body
            p.setPen(icon_fg)
            p.setBrush(self._color)
            p.drawRoundedRect(10, 4, 12, 18, 2, 2)
            # tip
            p.setPen(QPen(icon_fg, 1.2))
            p.setBrush(QColor('#92400e'))
            p.drawRect(12, 22, 8, 3)
        p.end()
        self.setIcon(QIcon(pm))
        self.setIconSize(QSize(20, 20))

    def set_color(self, color: QColor):
        self._color = color
        self._update_icon()

    def current_color(self) -> QColor:
        return self._color

    def mousePressEvent(self, event):
        from PyQt6.QtCore import Qt as _Qt
        if event.button() == _Qt.MouseButton.RightButton:
            self.set_color(self._default_color)
            self.colorReset.emit()
        else:
            super().mousePressEvent(event)


COMMON_20_COLORS = [
    # Row 1: Neutrals & Core Dark Colors
    ("#000000", "Black"),
    ("#475569", "Dark Slate"),
    ("#94a3b8", "Gray"),
    ("#dc2626", "Red"),
    ("#ea580c", "Orange"),

    # Row 2: Earthy & Vibrant Accents
    ("#ca8a04", "Dark Yellow"),
    ("#facc15", "Yellow"),
    ("#16a34a", "Green"),
    ("#0d9488", "Teal"),
    ("#0284c7", "Sky Blue"),

    # Row 3: Rich Cool Tones & Pinks
    ("#2563eb", "Blue"),
    ("#4f46e5", "Indigo"),
    ("#9333ea", "Purple"),
    ("#db2777", "Pink"),
    ("#881337", "Maroon"),

    # Row 4: Classic Soft Pastels (Widely used for Highlighting)
    ("#fef08a", "Pastel Yellow"),
    ("#bbf7d0", "Pastel Green"),
    ("#bae6fd", "Pastel Blue"),
    ("#e9d5ff", "Pastel Purple"),
    ("#fce7f3", "Pastel Pink"),
]


class ColorPaletteMenu(QMenu):
    """
    A clean, modern popup palette displaying 20 commonly used colors for font and highlight,
    plus an option to reset to default/transparent and an option for custom color picking.
    """
    def __init__(self, parent_btn: ColorSwatchButton, is_highlight: bool, on_color_selected, on_reset, on_custom_color, theme_mode: str = "light", parent=None):
        super().__init__(parent or parent_btn)
        self.parent_btn = parent_btn
        self.is_highlight = is_highlight
        self.on_color_selected = on_color_selected
        self.on_reset = on_reset
        self.on_custom_color = on_custom_color

        is_dark = (theme_mode == "dark")
        bg_color = "#1e293b" if is_dark else "#ffffff"
        border_color = "#334155" if is_dark else "#cbd5e1"
        text_color = "#f8fafc" if is_dark else "#1e293b"
        btn_bg = "#334155" if is_dark else "#f8fafc"
        btn_border = "#475569" if is_dark else "#e2e8f0"
        btn_hover_bg = "#475569" if is_dark else "#f1f5f9"
        sub_text_color = "#94a3b8" if is_dark else "#64748b"

        self.setStyleSheet(f"""
            QMenu {{
                background-color: {bg_color};
                border: 1px solid {border_color};
                border-radius: 8px;
                padding: 4px;
            }}
        """)

        container = QWidget(self)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        # 1. Reset / Automatic Button
        reset_text = "No Color (Transparent)" if is_highlight else "Automatic (Black)"
        btn_reset = QPushButton(reset_text)
        btn_reset.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn_reset.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_reset.setStyleSheet(f"""
            QPushButton {{
                background-color: {btn_bg};
                border: 1px solid {btn_border};
                border-radius: 4px;
                padding: 5px 10px;
                font-size: 12px;
                font-weight: 500;
                color: {text_color};
                text-align: left;
            }}
            QPushButton:hover {{
                background-color: {btn_hover_bg};
                border-color: #3b82f6;
            }}
        """)
        def handle_reset():
            self.close()
            if self.on_reset:
                self.on_reset()
        btn_reset.clicked.connect(handle_reset)
        layout.addWidget(btn_reset)

        # 2. Section Header
        header = QLabel("Standard Colors (20)")
        header.setStyleSheet(f"""
            color: {sub_text_color};
            font-size: 11px;
            font-weight: 600;
            padding: 2px 0 0 1px;
        """)
        layout.addWidget(header)

        # 3. 20 Colors Grid (4 rows x 5 columns)
        grid = QGridLayout()
        grid.setSpacing(5)
        grid.setContentsMargins(0, 0, 0, 0)

        cur_hex = parent_btn.current_color().name().lower() if parent_btn else ""

        for idx, (hex_code, name) in enumerate(COMMON_20_COLORS):
            r, c = divmod(idx, 5)
            cbtn = QPushButton()
            cbtn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            cbtn.setFixedSize(24, 24)
            cbtn.setToolTip(f"{name} ({hex_code})")
            cbtn.setCursor(Qt.CursorShape.PointingHandCursor)

            is_cur = (cur_hex == hex_code.lower())
            border_style = "2px solid #2563eb" if is_cur else f"1px solid {border_color}"
            cbtn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {hex_code};
                    border: {border_style};
                    border-radius: 4px;
                }}
                QPushButton:hover {{
                    border: 2px solid #3b82f6;
                }}
            """)

            def make_handler(col_hex):
                return lambda: self._select_color(QColor(col_hex))

            cbtn.clicked.connect(make_handler(hex_code))
            grid.addWidget(cbtn, r, c)

        layout.addLayout(grid)

        # 4. Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {btn_border}; margin: 2px 0;")
        layout.addWidget(sep)

        # 5. More Colors...
        btn_more = QPushButton("More Colors...")
        btn_more.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn_more.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_more.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: 1px solid transparent;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 12px;
                color: {text_color};
                text-align: left;
            }}
            QPushButton:hover {{
                background-color: {btn_hover_bg};
                border-color: {btn_border};
            }}
        """)
        def handle_more():
            self.close()
            if self.on_custom_color:
                self.on_custom_color()
        btn_more.clicked.connect(handle_more)
        layout.addWidget(btn_more)

        action = QWidgetAction(self)
        action.setDefaultWidget(container)
        self.addAction(action)

    def _select_color(self, color: QColor):
        self.close()
        if self.on_color_selected:
            self.on_color_selected(color)


class ExportPdfDialog(QDialog):
    """
    Dialog shown before exporting to PDF asking if exercises / sections
    should be unfolded so that all contents are included.
    Explicitly styled with a clean white theme so it remains 100% readable
    regardless of system light/dark mode settings.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Export as PDF")
        self.setFixedWidth(450)
        self.setModal(True)

        # Explicitly enforce bright white theme via palette
        self.setAutoFillBackground(True)
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor("#ffffff"))
        palette.setColor(QPalette.ColorRole.WindowText, QColor("#0f172a"))
        palette.setColor(QPalette.ColorRole.Base, QColor("#ffffff"))
        palette.setColor(QPalette.ColorRole.Text, QColor("#0f172a"))
        palette.setColor(QPalette.ColorRole.Button, QColor("#f8fafc"))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor("#0f172a"))
        self.setPalette(palette)

        icon_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "resources", "check_white.png")).replace("\\", "/")

        self.setStyleSheet(f"""
            QDialog {{
                background-color: #ffffff;
                color: #0f172a;
            }}
            QLabel {{
                background-color: transparent;
                color: #0f172a;
            }}
            QCheckBox {{
                background-color: transparent;
                color: #0f172a;
                font-size: 13px;
                font-weight: 600;
                spacing: 8px;
            }}
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
                border: 1.5px solid #2563eb;
                border-radius: 3px;
                background-color: #ffffff;
            }}
            QCheckBox::indicator:hover {{
                border-color: #1d4ed8;
                background-color: #eff6ff;
            }}
            QCheckBox::indicator:checked {{
                background-color: #2563eb;
                border-color: #2563eb;
                image: url("{icon_path}");
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(22, 22, 22, 20)

        # Title
        lbl_title = QLabel("PDF Export Options")
        lbl_title.setStyleSheet("font-size: 15px; font-weight: bold; color: #0f172a; margin-bottom: 2px;")
        layout.addWidget(lbl_title)

        # Description
        lbl_info = QLabel("Choose whether collapsed exercises and sections should be opened before generating the PDF:")
        lbl_info.setWordWrap(True)
        lbl_info.setStyleSheet("font-size: 12px; color: #334155; line-height: 1.4;")
        layout.addWidget(lbl_info)

        # Checkbox
        self.chk_unfold = QCheckBox("Unfold and show all exercises / sections")
        self.chk_unfold.setChecked(True)
        self.chk_unfold.setCursor(Qt.CursorShape.PointingHandCursor)
        layout.addWidget(self.chk_unfold)

        # Hint text
        lbl_desc = QLabel(
            "When checked, all exercises (e.g. ▶ Problem 1, ▶ Problem 2) will be unfolded "
            "so that all problem steps, math equations, and results are included in the PDF."
        )
        lbl_desc.setWordWrap(True)
        lbl_desc.setStyleSheet("color: #475569; font-size: 11px; margin-left: 24px; line-height: 1.4;")
        layout.addWidget(lbl_desc)

        layout.addSpacing(6)

        # Buttons
        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        ok_btn = btn_box.button(QDialogButtonBox.StandardButton.Ok)
        if ok_btn:
            ok_btn.setText("Export as PDF...")
            ok_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            ok_btn.setStyleSheet("""
                QPushButton {
                    background-color: #2563eb;
                    color: #ffffff;
                    border: 1px solid #1d4ed8;
                    border-radius: 4px;
                    padding: 6px 16px;
                    font-size: 12px;
                    font-weight: 600;
                    min-height: 24px;
                }
                QPushButton:hover {
                    background-color: #1d4ed8;
                }
                QPushButton:pressed {
                    background-color: #1e40af;
                }
            """)
        cancel_btn = btn_box.button(QDialogButtonBox.StandardButton.Cancel)
        if cancel_btn:
            cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            cancel_btn.setStyleSheet("""
                QPushButton {
                    background-color: #ffffff;
                    color: #334155;
                    border: 1px solid #cbd5e1;
                    border-radius: 4px;
                    padding: 6px 14px;
                    font-size: 12px;
                    font-weight: 500;
                    min-height: 24px;
                }
                QPushButton:hover {
                    background-color: #f8fafc;
                    border-color: #94a3b8;
                }
                QPushButton:pressed {
                    background-color: #f1f5f9;
                }
            """)
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def should_unfold_all(self) -> bool:
        return self.chk_unfold.isChecked()


class AboutOpenMathDialog(QDialog):
    """
    Modern, professional About dialog for OpenMath featuring
    clear typography, branding, and high-contrast GitHub buttons.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About OpenMath")
        self.setFixedSize(510, 360)
        self.setModal(True)

        icon_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "resources", "AppIcon.png"))
        if os.path.isfile(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.setStyleSheet("""
            QDialog {
                background-color: #ffffff;
            }
            QLabel {
                background-color: transparent;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 20)
        layout.setSpacing(14)

        # Header: App Icon + Name & Subtitle
        header = QHBoxLayout()
        header.setSpacing(18)

        if os.path.isfile(icon_path):
            lbl_icon = QLabel(self)
            pix = QPixmap(icon_path).scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            lbl_icon.setPixmap(pix)
            lbl_icon.setFixedSize(64, 64)
            header.addWidget(lbl_icon)

        title_col = QVBoxLayout()
        title_col.setSpacing(3)
        title_col.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        lbl_app_name = QLabel("OpenMath", self)
        lbl_app_name.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        lbl_app_name.setStyleSheet("color: #0f172a;")
        title_col.addWidget(lbl_app_name)

        lbl_tagline = QLabel("Desktop Symbolic & Numerical Computer Algebra System", self)
        lbl_tagline.setFont(QFont("Segoe UI", 10))
        lbl_tagline.setStyleSheet("color: #64748b;")
        lbl_tagline.setWordWrap(True)
        title_col.addWidget(lbl_tagline)

        header.addLayout(title_col)
        header.addStretch()
        layout.addLayout(header)

        # Separator line
        sep = QFrame(self)
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #e2e8f0; background-color: #e2e8f0; border: none; height: 1px;")
        layout.addWidget(sep)

        # Description
        lbl_desc = QLabel(
            "Specialized for symbolic mathematics, engineering calculations, "
            "algebra, calculus, and linear programming.", self
        )
        lbl_desc.setFont(QFont("Segoe UI", 10))
        lbl_desc.setStyleSheet("color: #334155; line-height: 1.4;")
        lbl_desc.setWordWrap(True)
        layout.addWidget(lbl_desc)

        # Developers Section Card
        dev_box = QFrame(self)
        dev_box.setStyleSheet("""
            QFrame {
                background-color: #f8fafc;
                border: 1.5px solid #e2e8f0;
                border-radius: 8px;
            }
        """)
        dev_layout = QVBoxLayout(dev_box)
        dev_layout.setContentsMargins(16, 12, 16, 12)
        dev_layout.setSpacing(10)

        lbl_dev_title = QLabel("Developed by", dev_box)
        lbl_dev_title.setFont(QFont("Segoe UI", 10))
        lbl_dev_title.setStyleSheet("color: #475569; border: none;")
        lbl_dev_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dev_layout.addWidget(lbl_dev_title)

        btns_row = QHBoxLayout()
        btns_row.setSpacing(12)

        btn_style = """
            QPushButton {
                background-color: #ffffff;
                color: #0f172a;
                font-size: 11pt;
                font-weight: 600;
                border: 1.5px solid #cbd5e1;
                border-radius: 6px;
                padding: 7px 14px;
                text-align: center;
            }
            QPushButton:hover {
                background-color: #eff6ff;
                border-color: #2563eb;
                color: #1d4ed8;
            }
            QPushButton:pressed {
                background-color: #dbeafe;
                border-color: #1d4ed8;
            }
        """

        gh_icon_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "resources", "github.png"))
        gh_icon = QIcon(gh_icon_path) if os.path.isfile(gh_icon_path) else QIcon()

        btn_j2k = QPushButton("  J2KDevelop  ↗", dev_box)
        if not gh_icon.isNull():
            btn_j2k.setIcon(gh_icon)
            btn_j2k.setIconSize(QSize(16, 16))
        btn_j2k.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_j2k.setStyleSheet(btn_style)
        btn_j2k.setToolTip("Visit J2KDevelop on GitHub (https://github.com/J2KJonas)")
        btn_j2k.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://github.com/J2KJonas")))

        btn_elomar = QPushButton("  Elomarstudio  ↗", dev_box)
        if not gh_icon.isNull():
            btn_elomar.setIcon(gh_icon)
            btn_elomar.setIconSize(QSize(16, 16))
        btn_elomar.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_elomar.setStyleSheet(btn_style)
        btn_elomar.setToolTip("Visit Elomarstudio on GitHub (https://github.com/elomarjc)")
        btn_elomar.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://github.com/elomarjc")))

        btns_row.addWidget(btn_j2k)
        btns_row.addWidget(btn_elomar)
        dev_layout.addLayout(btns_row)

        layout.addWidget(dev_box)
        layout.addStretch()

        # Bottom row with OK button
        bottom_row = QHBoxLayout()
        bottom_row.addStretch()

        btn_close = QPushButton("OK", self)
        btn_close.setFixedSize(92, 36)
        btn_close.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_close.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        btn_close.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                color: #ffffff;
                border: none;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #1d4ed8;
            }
            QPushButton:pressed {
                background-color: #1e40af;
            }
        """)
        btn_close.clicked.connect(self.accept)
        btn_close.setDefault(True)
        bottom_row.addWidget(btn_close)

        layout.addLayout(bottom_row)


def _is_dark_theme(widget) -> bool:
    if not widget:
        return False
    top = widget.window() if hasattr(widget, 'window') else None
    if top and hasattr(top, 'theme_mode'):
        return getattr(top, 'theme_mode', '') == "dark"
    return False


class TabCloseButton(QToolButton):
    """High-visibility, clearly defined button for closing document tabs."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(16, 16)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Close Worksheet")

    def enterEvent(self, event):
        super().enterEvent(event)
        self.update()

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)

        is_hover = self.underMouse()
        is_down = self.isDown()
        is_dark = _is_dark_theme(self)

        if is_dark:
            if is_down:
                p.setBrush(QColor('#7f1d1d'))
                p.setPen(QPen(QColor('#ef4444'), 1.0))
                icon_color = QColor('#fecaca')
            elif is_hover:
                p.setBrush(QColor('#450a0a'))
                p.setPen(QPen(QColor('#dc2626'), 1.0))
                icon_color = QColor('#fca5a5')
            else:
                p.setBrush(QColor('#1a2332'))
                p.setPen(QPen(QColor('#2b384c'), 1.0))
                icon_color = QColor('#94a3b8')
        else:
            if is_down:
                p.setBrush(QColor('#fecaca'))
                p.setPen(QPen(QColor('#dc2626'), 1.0))
                icon_color = QColor('#b91c1c')
            elif is_hover:
                p.setBrush(QColor('#fee2e2'))
                p.setPen(QPen(QColor('#f87171'), 1.0))
                icon_color = QColor('#dc2626')
            else:
                p.setBrush(QColor('#f1f3f5'))
                p.setPen(QPen(QColor('#c4c8cc'), 1.0))
                icon_color = QColor('#374151')

        p.drawRoundedRect(rect, 3.0, 3.0)

        cx = self.width() / 2.0
        cy = self.height() / 2.0
        r = 3.5
        pen = QPen(icon_color, 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.drawLine(QPointF(cx - r, cy - r), QPointF(cx + r, cy + r))
        p.drawLine(QPointF(cx + r, cy - r), QPointF(cx - r, cy + r))
        p.end()


class CleanAddTabButton(QToolButton):
    """Modern, cleanly centered '+' button for adding document tabs."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(20, 20)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("New Worksheet Tab")

    def enterEvent(self, event):
        super().enterEvent(event)
        self.update()

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)

        is_hover = self.underMouse()
        is_down = self.isDown()
        is_dark = _is_dark_theme(self)

        if is_dark:
            if is_down:
                p.setBrush(QColor('#141b26'))
                p.setPen(QPen(QColor('#0284c7'), 1.0))
                icon_color = QColor('#0ea5e9')
            elif is_hover:
                p.setBrush(QColor('#222f42'))
                p.setPen(QPen(QColor('#38bdf8'), 1.0))
                icon_color = QColor('#38bdf8')
            else:
                p.setBrush(QColor('#1a2332'))
                p.setPen(QPen(QColor('#2b384c'), 1.0))
                icon_color = QColor('#94a3b8')
        else:
            if is_down:
                p.setBrush(QColor('#dbeafe'))
                p.setPen(QPen(QColor('#1d4ed8'), 1.0))
                icon_color = QColor('#1d4ed8')
            elif is_hover:
                p.setBrush(QColor('#eff6ff'))
                p.setPen(QPen(QColor('#3b82f6'), 1.0))
                icon_color = QColor('#2563eb')
            else:
                p.setBrush(QColor('#f8fafc'))
                p.setPen(QPen(QColor('#cbd5e1'), 1.0))
                icon_color = QColor('#475569')

        p.drawRoundedRect(rect, 4.0, 4.0)

        cx = self.width() / 2.0
        cy = self.height() / 2.0
        r = 4.5
        pen = QPen(icon_color, 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.drawLine(QPointF(cx - r, cy), QPointF(cx + r, cy))
        p.drawLine(QPointF(cx, cy - r), QPointF(cx, cy + r))
        p.end()


class CleanTabOverflowButton(QToolButton):
    """Modern dropdown chevron button showing hidden tabs that do not fit in the tab bar."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(20, 20)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("More Tabs")

    def enterEvent(self, event):
        super().enterEvent(event)
        self.update()

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)

        is_hover = self.underMouse()
        is_down = self.isDown()
        is_dark = _is_dark_theme(self)

        if is_dark:
            if is_down:
                p.setBrush(QColor('#141b26'))
                p.setPen(QPen(QColor('#0284c7'), 1.0))
                icon_color = QColor('#0ea5e9')
            elif is_hover:
                p.setBrush(QColor('#222f42'))
                p.setPen(QPen(QColor('#38bdf8'), 1.0))
                icon_color = QColor('#38bdf8')
            else:
                p.setBrush(QColor('#1a2332'))
                p.setPen(QPen(QColor('#2b384c'), 1.0))
                icon_color = QColor('#94a3b8')
        else:
            if is_down:
                p.setBrush(QColor('#dbeafe'))
                p.setPen(QPen(QColor('#1d4ed8'), 1.0))
                icon_color = QColor('#1d4ed8')
            elif is_hover:
                p.setBrush(QColor('#eff6ff'))
                p.setPen(QPen(QColor('#3b82f6'), 1.0))
                icon_color = QColor('#2563eb')
            else:
                p.setBrush(QColor('#f8fafc'))
                p.setPen(QPen(QColor('#cbd5e1'), 1.0))
                icon_color = QColor('#475569')

        p.drawRoundedRect(rect, 4.0, 4.0)

        cx = self.width() / 2.0
        cy = self.height() / 2.0
        pen = QPen(icon_color, 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        p.drawLine(QPointF(cx - 4.0, cy - 1.5), QPointF(cx, cy + 2.5))
        p.drawLine(QPointF(cx, cy + 2.5), QPointF(cx + 4.0, cy - 1.5))
        p.end()


class DocumentTabBar(QTabBar):
    """Custom QTabBar ensuring all tabs have clean, obvious close buttons safely inside tab boundaries."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._repositioning = False
        self._prev_start_idx = 0

    def minimumSizeHint(self):
        return QSize(50, 26)

    def tabInserted(self, index: int):
        super().tabInserted(index)
        btn = TabCloseButton(self)
        btn.clicked.connect(lambda: self._on_close_clicked(btn))
        btn.installEventFilter(self)
        self.setTabButton(index, QTabBar.ButtonPosition.RightSide, btn)
        self.setTabButton(index, QTabBar.ButtonPosition.LeftSide, None)
        self._reposition_close_buttons()

    def tabLayoutChange(self):
        super().tabLayoutChange()
        self._reposition_close_buttons()
        win = self.window()
        if win and hasattr(win, '_update_tab_bar_layout'):
            win._update_tab_bar_layout()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._reposition_close_buttons()

    def eventFilter(self, watched, event):
        if not getattr(self, '_repositioning', False) and event.type() in (QEvent.Type.Move, QEvent.Type.Resize):
            for i in range(self.count()):
                if self.tabButton(i, QTabBar.ButtonPosition.RightSide) is watched:
                    if hasattr(self, 'isTabVisible') and not self.isTabVisible(i):
                        watched.setVisible(False)
                        return True
                    r = self.tabRect(i)
                    proper_x = r.x() + r.width() - watched.width() - 6
                    proper_y = r.y() + (r.height() - watched.height()) // 2
                    if watched.x() != proper_x or watched.y() != proper_y:
                        self._repositioning = True
                        watched.move(proper_x, proper_y)
                        self._repositioning = False
                        return True
                    break
        return super().eventFilter(watched, event)

    def _reposition_close_buttons(self):
        if getattr(self, '_repositioning', False):
            return
        self._repositioning = True
        try:
            for i in range(self.count()):
                if self.tabButton(i, QTabBar.ButtonPosition.LeftSide) is not None:
                    self.setTabButton(i, QTabBar.ButtonPosition.LeftSide, None)
                btn = self.tabButton(i, QTabBar.ButtonPosition.RightSide)
                if btn:
                    if hasattr(self, 'isTabVisible') and not self.isTabVisible(i):
                        btn.setVisible(False)
                        continue
                    btn.setVisible(True)
                    r = self.tabRect(i)
                    proper_x = r.x() + r.width() - btn.width() - 6
                    proper_y = r.y() + (r.height() - btn.height()) // 2
                    btn.move(proper_x, proper_y)
        finally:
            self._repositioning = False

    def _on_close_clicked(self, btn):
        for i in range(self.count()):
            if self.tabButton(i, QTabBar.ButtonPosition.RightSide) is btn:
                self.tabCloseRequested.emit(i)
                break


class DocumentTabWidget(QTabWidget):
    """Custom QTabWidget with bounded minimum size hint to prevent pushing parent window width."""
    def minimumSizeHint(self):
        return QSize(50, 26)


class MainWindow(QMainWindow):
    """
    OpenMath Desktop Application Main Window.
    """

    HELP_TOPICS = {
        "diff": {
            "title": "diff - Symbolic Derivative",
            "syntax": "diff(f, x) or diff(f, x, n)",
            "desc": "Calculates the symbolic derivative of f with respect to variable x (or nth derivative).",
            "example": "diff(x³ + sin(x), x)"
        },
        "integrate": {
            "title": "integrate - Symbolic Integration",
            "syntax": "integrate(f, x) or integrate(f, (x, a, b))",
            "desc": "Computes the symbolic indefinite or definite integral of f with respect to variable x.",
            "example": "integrate(x² · exp(x), (x, 0, 1))"
        },
        "solve": {
            "title": "solve - Solve Algebraic Equations",
            "syntax": "solve(equation, x) or solve([eq1, eq2], [x, y])",
            "desc": "Solves single equations or systems of algebraic equations for unknown variables.",
            "example": "solve(x² - 4 = 0, x)"
        },
        "limit": {
            "title": "limit - Mathematical Limits",
            "syntax": "limit(f, x, a)",
            "desc": "Computes the symbolic limit of expression f as variable x approaches value a.",
            "example": "limit(sin(x)/x, x, 0)"
        },
        "taylor": {
            "title": "taylor - Taylor Series Expansion",
            "syntax": "taylor(f, x, x0, n)",
            "desc": "Computes the Taylor polynomial of degree n around point x0.",
            "example": "taylor(exp(x), x, 0, 5)"
        },
        "plot": {
            "title": "plot - 2D Function Plot",
            "syntax": "plot(f(x), (x, a, b))",
            "desc": "Renders a dynamic 2D Cartesian function plot of f(x) over the interval [a, b].",
            "example": "plot(sin(x) * exp(-x/5), (x, -10, 10))"
        },
        "polygonOmråde": {
            "title": "polygonOmråde - Feasible Polygon Region",
            "syntax": "polygonOmråde([inequalities], x=xmin..xmax, y=ymin..ymax)",
            "desc": "Visualizes the feasible polygonal region bounded by linear inequalities.",
            "example": "polygonOmråde([x >= 0, y >= 0, x + y <= 10], x = 0..12, y = 0..12)"
        },
        "LPplot": {
            "title": "LPplot - Linear Programming Level Curves",
            "syntax": "LPplot(objective, [constraints], [levels])",
            "desc": "Plots objective function level curves along with the feasible region polygon.",
            "example": "LPplot(30*x + 20*y, [x >= 0, y >= 0, x + y <= 10], [100, 200, 300])"
        },
        "to_bin": {
            "title": "to_bin - Binary Representation",
            "syntax": "to_bin(val, bits=8)",
            "desc": "Formats an integer as a spaced nibble binary string (e.g. 0b1010_0101).",
            "example": "to_bin(0xA5, 8)"
        },
        "to_hex": {
            "title": "to_hex - Hexadecimal Representation",
            "syntax": "to_hex(val, bits=8)",
            "desc": "Formats an integer into standard uppercase hexadecimal notation.",
            "example": "to_hex(255, 8)"
        },
        "twos_comp_repr": {
            "title": "twos_comp_repr - Two's Complement Breakdown",
            "syntax": "twos_comp_repr(val, bits=8)",
            "desc": "Calculates complete signed and unsigned two's complement breakdown for val.",
            "example": "twos_comp_repr(-5, 8)"
        },
        "two_comp_repr": {
            "title": "two_comp_repr - Two's Complement Breakdown",
            "syntax": "two_comp_repr(val, bits=8)",
            "desc": "Calculates complete signed and unsigned two's complement breakdown for val.",
            "example": "two_comp_repr(-5, 8)"
        },
        "bit_set": {
            "title": "bit_set - Set Register Bit",
            "syntax": "bit_set(reg, bit_index)",
            "desc": "Sets the bit at bit_index of register to 1.",
            "example": "bit_set(0x00, 3)"
        },
        "bit_clear": {
            "title": "bit_clear - Clear Register Bit",
            "syntax": "bit_clear(reg, bit_index)",
            "desc": "Clears the bit at bit_index of register to 0.",
            "example": "bit_clear(0xFF, 3)"
        },
        "bit_toggle": {
            "title": "bit_toggle - Toggle Register Bit",
            "syntax": "bit_toggle(reg, bit_index)",
            "desc": "Toggles / inverts the bit at bit_index of register.",
            "example": "bit_toggle(0x0F, 2)"
        },
        "voltage_divider": {
            "title": "voltage_divider - Voltage Divider Formula",
            "syntax": "voltage_divider(v_in, r1, r2)",
            "desc": "Calculates output voltage Vout = Vin * (R2 / (R1 + R2)).",
            "example": "voltage_divider(5.0, 10*kOhm, 10*kOhm)"
        },
        "rc_cutoff": {
            "title": "rc_cutoff - RC Filter Cutoff Frequency & Tau",
            "syntax": "rc_cutoff(r_ohms, c_farads)",
            "desc": "Computes cutoff frequency fc = 1/(2*pi*R*C) and time constant tau = R*C.",
            "example": "rc_cutoff(10*kOhm, 100*nF)"
        },
        "matrix": {
            "title": "Matrix - Symbolic & Numerical Matrix",
            "syntax": "Matrix([[a, b], [c, d]])",
            "desc": "Constructs a symbolic or numerical matrix. Supports det, inv, and arithmetic.",
            "example": "Matrix([[1, 2], [3, 4]])"
        },
        "simplify": {
            "title": "simplify - Simplify Expression",
            "syntax": "simplify(expr)",
            "desc": "Applies symbolic transformations to simplify mathematical expressions.",
            "example": "simplify((x² - 1)/(x - 1))"
        },
        "factor": {
            "title": "factor - Factor Polynomial",
            "syntax": "factor(expr)",
            "desc": "Factors an algebraic polynomial into irreducible components.",
            "example": "factor(x² - 5 · x + 6)"
        },
        "expand": {
            "title": "expand - Expand Algebraic Expression",
            "syntax": "expand(expr)",
            "desc": "Expands products and powers of polynomial expressions.",
            "example": "expand((x + 2)³)"
        }
    }

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Start.mw - [Server 3] - OpenMath")
        self.resize(1380, 880)

        # Core State
        self.theme_mode = Theme.LIGHT
        self.engine = CASEngine()
        self.current_file_path = None
        self.document_counter = 0

        self._init_ui()
        self._apply_theme()

    def _init_ui(self):
        self.setDockNestingEnabled(True)
        self.setCorner(Qt.Corner.TopLeftCorner, Qt.DockWidgetArea.LeftDockWidgetArea)
        self.setCorner(Qt.Corner.BottomLeftCorner, Qt.DockWidgetArea.LeftDockWidgetArea)
        self.setCorner(Qt.Corner.TopRightCorner, Qt.DockWidgetArea.RightDockWidgetArea)
        self.setCorner(Qt.Corner.BottomRightCorner, Qt.DockWidgetArea.RightDockWidgetArea)

        # 1. Central Widget: Document Stack with soft white background
        self.doc_stack = QStackedWidget(self)
        self.doc_stack.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.doc_stack.setAutoFillBackground(True)
        self.doc_stack.setStyleSheet("background-color: #f4f6f9;")
        self.setCentralWidget(self.doc_stack)

        # Initial Document: Start Page View with 'New Document' and 'Open Documents'
        self.start_page = StartPageView(self)
        self.start_page.newDocumentRequested.connect(self.new_worksheet)
        self.start_page.openDocumentRequested.connect(self.open_worksheet)
        self.doc_stack.addWidget(self.start_page)
        self.worksheet = None

        # Loading Overlay on doc_stack for project loading
        self.loading_overlay = LoadingOverlay(self.doc_stack)

        # 2. Left Dock: Palette Sidebar
        self.palette_dock = QDockWidget("Palettes", self)
        self.palette_dock.setObjectName("PaletteDock")
        self.palette_dock.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
        self.palette_dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetClosable |
            QDockWidget.DockWidgetFeature.DockWidgetMovable
        )
        self.palette_panel = PalettePanel(self, theme_mode=self.theme_mode, engine=self.engine)
        self.palette_panel.insertTemplate.connect(self._on_insert_template)
        self.palette_panel.openMatrixDialog.connect(self._open_matrix_dialog)
        self.palette_dock.setWidget(self.palette_panel)
        self.palette_dock.setMinimumWidth(250)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.palette_dock)

        # 3. Right Dock: Context Panel
        self.context_dock = QDockWidget("Context Panel", self)
        self.context_dock.setObjectName("ContextDock")
        self.context_dock.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
        self.context_dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetClosable |
            QDockWidget.DockWidgetFeature.DockWidgetMovable
        )
        self.context_panel = ContextPanel(self, theme_mode=self.theme_mode)
        self.context_panel.operationRequested.connect(self._on_context_operation_requested)
        self.context_panel.collapseRequested.connect(self._toggle_context_panel)
        self.context_dock.setWidget(self.context_panel)
        self.context_dock.setMinimumWidth(240)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.context_dock)
        self.context_dock.setVisible(False)

        # 4. Secondary Right Dock: Standalone 2D Plotter (Hidden by default)
        self.plot_dock = QDockWidget("2D Dynamic Graph Plotter", self)
        self.plot_dock.setObjectName("PlotDock")
        self.plot_dock.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
        self.plot_dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetClosable |
            QDockWidget.DockWidgetFeature.DockWidgetMovable
        )
        self.plot_panel = PlotPanel(self, theme_mode=self.theme_mode)
        self.plot_panel.plotInserted.connect(self._on_plot_inserted_from_panel)
        self.plot_dock.setWidget(self.plot_panel)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.plot_dock)
        self.plot_dock.setVisible(False)

        # 5. Create Menus, Toolbars, and Status Bar
        self._create_actions()
        self._create_all_toolbars()
        self._create_menus()
        self._create_status_bar()

        # 6. Load persistent layout settings or apply clean default
        self._setup_settings_tracking()
        self.load_settings()

    def _create_all_toolbars(self):
        """
        Create 3-tiered top toolbars spanning the full window width:
        Tier 1: Main command toolbar (icons)
        Tier 2: Document tab bar (Start.mw initially)
        Tier 3: Context Bar ([Text], [Nonexecutable Math], [Math], [C], Times New Roman, 12, B, I, U, etc.)
        """
        # Tier 1: Main Toolbar
        self.main_toolbar = QToolBar("Main Toolbar", self)
        self.main_toolbar.setObjectName("MainToolbar")
        self.main_toolbar.setMovable(False)
        self.main_toolbar.setIconSize(QSize(16, 16))
        self._populate_main_toolbar(self.main_toolbar)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.main_toolbar)

        # Tier 2: Document Tabs Toolbar
        self.addToolBarBreak(Qt.ToolBarArea.TopToolBarArea)
        self.tab_bar_toolbar = QToolBar("Document Tabs", self)
        self.tab_bar_toolbar.setObjectName("DocumentTabsToolbar")
        self.tab_bar_toolbar.setMovable(False)
        self.tab_bar_toolbar.setStyleSheet("QToolBar { background-color: #e2e4e8; border-bottom: 1px solid #b8bcc2; padding: 0px; }")
        self._populate_tab_bar_toolbar(self.tab_bar_toolbar)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.tab_bar_toolbar)

        # Tier 3: Context Bar Toolbar
        self.addToolBarBreak(Qt.ToolBarArea.TopToolBarArea)
        self.context_toolbar = QToolBar("Context Bar", self)
        self.context_toolbar.setObjectName("ContextBarToolbar")
        self.context_toolbar.setMovable(False)
        self.context_toolbar.setStyleSheet("QToolBar { background-color: #f3f4f6; border-bottom: 1px solid #cbd5e1; padding: 1px 4px; }")
        self._populate_context_toolbar(self.context_toolbar)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.context_toolbar)

    def _populate_main_toolbar(self, toolbar: QToolBar):
        btn_style = """
            QPushButton {
                background-color: #f8fafc;
                color: #334155;
                border: 1px solid #cbd5e1;
                border-radius: 3px;
                padding: 2px 8px;
                font-size: 11px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #e2e8f0;
                color: #0f172a;
            }
            QPushButton:pressed {
                background-color: #cbd5e1;
            }
        """

        btn_new = QPushButton("📄 New")
        btn_new.setToolTip("New Worksheet (Ctrl+N)")
        btn_new.setFixedHeight(24)
        btn_new.setStyleSheet(btn_style)
        btn_new.clicked.connect(self.new_worksheet)
        toolbar.addWidget(btn_new)

        btn_open = QPushButton("📂 Open")
        btn_open.setToolTip("Open Document (Ctrl+O)")
        btn_open.setFixedHeight(24)
        btn_open.setStyleSheet(btn_style)
        btn_open.clicked.connect(self.open_worksheet)
        toolbar.addWidget(btn_open)

        btn_save = QPushButton("💾 Save")
        btn_save.setToolTip("Save Document (Ctrl+S)")
        btn_save.setFixedHeight(24)
        btn_save.setStyleSheet(btn_style)
        btn_save.clicked.connect(self.save_worksheet)
        toolbar.addWidget(btn_save)

        btn_print = QPushButton("🖨️ Print")
        btn_print.setToolTip("Print Document (Ctrl+P)")
        btn_print.setFixedHeight(24)
        btn_print.setStyleSheet(btn_style)
        btn_print.clicked.connect(self._print_worksheet)
        toolbar.addWidget(btn_print)

        toolbar.addSeparator()

        btn_undo = QPushButton("Undo")
        btn_undo.setToolTip("Undo (Ctrl+Z)")
        btn_undo.setFixedHeight(24)
        btn_undo.setStyleSheet(btn_style)
        btn_undo.clicked.connect(self._edit_undo)
        toolbar.addWidget(btn_undo)

        btn_redo = QPushButton("Redo")
        btn_redo.setToolTip("Redo (Ctrl+Y, Ctrl+Shift+Z)")
        btn_redo.setFixedHeight(24)
        btn_redo.setStyleSheet(btn_style)
        btn_redo.clicked.connect(self._edit_redo)
        toolbar.addWidget(btn_redo)

        toolbar.addSeparator()

        btn_exec_one = QPushButton("▶ Eval")
        btn_exec_one.setToolTip("Evaluate Active Cell (Enter)")
        btn_exec_one.setFixedHeight(24)
        btn_exec_one.setStyleSheet("""
            QPushButton {
                background-color: #f0fdf4;
                color: #15803d;
                border: 1px solid #86efac;
                border-radius: 3px;
                padding: 2px 8px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #dcfce7;
                border-color: #4ade80;
            }
        """)
        btn_exec_one.clicked.connect(self._execute_active_group)
        toolbar.addWidget(btn_exec_one)

        btn_exec_all = QPushButton("▶▶ Eval All")
        btn_exec_all.setToolTip("Execute Entire Worksheet (Ctrl+Shift+Enter)")
        btn_exec_all.setFixedHeight(24)
        btn_exec_all.setStyleSheet("""
            QPushButton {
                background-color: #eff6ff;
                color: #1d4ed8;
                border: 1px solid #93c5fd;
                border-radius: 3px;
                padding: 2px 8px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #dbeafe;
                border-color: #60a5fa;
            }
        """)
        btn_exec_all.clicked.connect(self._execute_all_groups)
        toolbar.addWidget(btn_exec_all)

        btn_stop = QPushButton("⏹ Stop")
        btn_stop.setToolTip("Stop Current Calculation")
        btn_stop.setFixedHeight(24)
        btn_stop.setStyleSheet("""
            QPushButton {
                background-color: #fef2f2;
                color: #b91c1c;
                border: 1px solid #fca5a5;
                border-radius: 3px;
                padding: 2px 8px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #fee2e2;
                border-color: #f87171;
            }
        """)
        btn_stop.clicked.connect(self._stop_computation)
        toolbar.addWidget(btn_stop)

        btn_restart = QPushButton("↺ Restart")
        btn_restart.setToolTip("Restart CAS Engine & Clear Worksheet")
        btn_restart.setFixedHeight(24)
        btn_restart.setStyleSheet(btn_style)
        btn_restart.clicked.connect(self._restart_worksheet)
        toolbar.addWidget(btn_restart)

        toolbar.addSeparator()

        btn_zoom_out = QPushButton("Zoom −")
        btn_zoom_out.setToolTip("Zoom Out (Ctrl+-)")
        btn_zoom_out.setFixedHeight(24)
        btn_zoom_out.setStyleSheet(btn_style)
        btn_zoom_out.clicked.connect(self._zoom_out)
        toolbar.addWidget(btn_zoom_out)

        btn_zoom_in = QPushButton("Zoom +")
        btn_zoom_in.setToolTip("Zoom In (Ctrl+=)")
        btn_zoom_in.setFixedHeight(24)
        btn_zoom_in.setStyleSheet(btn_style)
        btn_zoom_in.clicked.connect(self._zoom_in)
        toolbar.addWidget(btn_zoom_in)

        search_edit = QLineEdit()
        search_edit.setPlaceholderText("🔍 Search Help & Functions (e.g. solve, diff)...")
        search_edit.setToolTip("Search functions, CAS commands, or worksheet text (Press Enter)")
        search_edit.setFixedWidth(270)
        search_edit.setFixedHeight(24)
        search_edit.setStyleSheet("""
            QLineEdit {
                background-color: #ffffff;
                color: #0f172a;
                border: 1px solid #94a3b8;
                border-radius: 4px;
                padding: 2px 8px;
                font-size: 11px;
                selection-background-color: #2563eb;
                selection-color: #ffffff;
            }
            QLineEdit:focus {
                border: 1px solid #2563eb;
                background-color: #ffffff;
            }
        """)
        topic_keys = list(self.HELP_TOPICS.keys())
        completer = QCompleter(topic_keys, search_edit)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        search_edit.setCompleter(completer)
        search_edit.returnPressed.connect(lambda: self._on_search_triggered(search_edit.text()))
        self.main_toolbar_buttons = [btn_new, btn_open, btn_save, btn_print, btn_undo, btn_redo, btn_restart, btn_zoom_out, btn_zoom_in]
        self.btn_exec_one = btn_exec_one
        self.btn_exec_all = btn_exec_all
        self.btn_stop = btn_stop
        self.toolbar_search_edit = search_edit
        toolbar.addWidget(search_edit)

    def _populate_tab_bar_toolbar(self, toolbar: QToolBar):
        container = QWidget()
        self.tab_bar_container = container
        container.setStyleSheet("background-color: #e2e4e8;")
        layout = QHBoxLayout(container)
        layout.setContentsMargins(4, 2, 4, 0)
        layout.setSpacing(4)

        self.tab_widget = DocumentTabWidget()
        self.tab_bar = DocumentTabBar(self.tab_widget)
        self.tab_widget.setTabBar(self.tab_bar)
        self.tab_widget.setDocumentMode(False)
        self.tab_widget.setTabsClosable(False)
        self.tab_widget.setFixedHeight(26)
        self.tab_widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.tab_widget.setStyleSheet("""
            QTabWidget { background-color: transparent; border: none; }
            QTabBar { background-color: transparent; border: none; }
            QTabWidget::pane { border: none; background: transparent; }
            QTabBar::tab {
                background: #e2e4e8;
                color: #374151;
                border: 1px solid #b8bcc2;
                border-bottom: none;
                min-width: 130px;
                padding: 4px 26px 4px 14px;
                font-size: 11px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background: #ffffff;
                color: #111827;
                font-weight: bold;
                border-top: 2px solid #2563eb;
            }
            QTabBar::tab:hover:!selected {
                background: #edf0f5;
            }
        """)

        # Start document tab only initially: Start.mw (no other tabs at first!)
        self.tab_widget.addTab(QWidget(), "Start.mw")
        self.tab_bar.setTabButton(0, QTabBar.ButtonPosition.LeftSide, None)
        self.tab_widget.setCurrentIndex(0)
        self.tab_widget.currentChanged.connect(self._on_tab_changed)
        self.tab_widget.currentChanged.connect(lambda _: self._update_tab_bar_layout())
        self.tab_widget.tabCloseRequested.connect(self._on_tab_close_requested)
        self.tab_bar.tabCloseRequested.connect(self._on_tab_close_requested)

        self.tab_widget.installEventFilter(self)
        self.tab_widget.tabBar().installEventFilter(self)

        self.btn_add_tab = CleanAddTabButton(container)
        self.btn_add_tab.clicked.connect(self.new_worksheet)

        self.btn_tab_overflow = CleanTabOverflowButton(container)
        self.btn_tab_overflow.clicked.connect(self._show_tab_overflow_menu)

        layout.addWidget(self.tab_widget)
        layout.addWidget(self.btn_add_tab)
        layout.addWidget(self.btn_tab_overflow)
        layout.addStretch()

        toolbar.addWidget(container)
        QTimer.singleShot(0, self._update_tab_bar_layout)

    def _compute_visible_tab_range(self, tab_widths, current_idx, max_w, prev_start_idx=0):
        total = len(tab_widths)
        if total == 0:
            return 0, 0
        if sum(tab_widths) <= max_w:
            return 0, total

        current_idx = max(0, min(current_idx, total - 1))
        start = max(0, min(prev_start_idx, total - 1))
        if current_idx < start:
            start = current_idx

        def fit_from(s):
            curr_w = 0
            count = 0
            for i in range(s, total):
                if count > 0 and curr_w + tab_widths[i] > max_w:
                    break
                curr_w += tab_widths[i]
                count += 1
            return count

        count = fit_from(start)
        if current_idx >= start + count:
            start = current_idx
            curr_w = tab_widths[start]
            while start > 0 and curr_w + tab_widths[start - 1] <= max_w:
                start -= 1
                curr_w += tab_widths[start]
            count = fit_from(start)

        while start > 0:
            if sum(tab_widths[start - 1 : start + count]) <= max_w:
                start -= 1
                count += 1
            else:
                break

        return start, start + count

    def _update_tab_bar_layout(self):
        if not hasattr(self, 'btn_add_tab') or not hasattr(self, 'btn_tab_overflow') or not hasattr(self, 'tab_widget'):
            return
        if getattr(self, '_updating_tab_layout', False):
            return
        self._updating_tab_layout = True
        try:
            self._do_update_tab_bar_layout()
        finally:
            self._updating_tab_layout = False

    def _do_update_tab_bar_layout(self):
        tb = self.tab_widget.tabBar()
        total = tb.count()
        if total == 0:
            self.btn_add_tab.setVisible(True)
            self.btn_tab_overflow.setVisible(False)
            return

        available_w = self.tab_bar_toolbar.width()
        if available_w <= 0 and hasattr(self, 'tab_widget') and self.tab_widget.parentWidget():
            available_w = self.tab_widget.parentWidget().width()
        if available_w <= 0:
            available_w = self.width()
        if available_w <= 0:
            return

        tab_widths = []
        for i in range(total):
            txt = tb.tabText(i)
            fm_w = tb.fontMetrics().boundingRect(txt).width()
            tab_widths.append(max(174, fm_w + 44))

        sum_all_w = sum(tab_widths)
        btn_add_w = self.btn_add_tab.width()
        btn_overflow_w = self.btn_tab_overflow.width()

        max_w_for_tabs = max(100, available_w - (btn_add_w + btn_overflow_w + 24))

        if sum_all_w <= max_w_for_tabs:
            for i in range(total):
                if hasattr(tb, 'setTabVisible'):
                    tb.setTabVisible(i, True)
            tb._prev_start_idx = 0
            tb._reposition_close_buttons()

            self.btn_add_tab.setVisible(True)
            self.btn_tab_overflow.setVisible(False)
            return

        current_idx = self.tab_widget.currentIndex()
        if current_idx < 0:
            current_idx = 0

        prev_start = getattr(tb, '_prev_start_idx', 0)
        start_idx, end_idx = self._compute_visible_tab_range(tab_widths, current_idx, max_w_for_tabs, prev_start)
        tb._prev_start_idx = start_idx

        for i in range(total):
            is_vis = (start_idx <= i < end_idx)
            if hasattr(tb, 'setTabVisible'):
                tb.setTabVisible(i, is_vis)

        tb._reposition_close_buttons()

        hidden_count = total - (end_idx - start_idx)
        if hidden_count > 0:
            self.btn_add_tab.setVisible(False)
            self.btn_tab_overflow.setVisible(True)
            self.btn_tab_overflow.setToolTip(f"More Tabs ({hidden_count} hidden)")
        else:
            self.btn_add_tab.setVisible(True)
            self.btn_tab_overflow.setVisible(False)

    def _update_add_tab_button_pos(self):
        self._update_tab_bar_layout()

    def _select_tab_and_refresh(self, idx: int):
        if 0 <= idx < self.tab_widget.count():
            self.tab_widget.setCurrentIndex(idx)
            self._update_tab_bar_layout()

    def _show_tab_overflow_menu(self):
        if not hasattr(self, 'tab_widget') or not hasattr(self, 'btn_tab_overflow'):
            return
        tb = self.tab_widget.tabBar()
        hidden_indices = [i for i in range(tb.count()) if hasattr(tb, 'isTabVisible') and not tb.isTabVisible(i)]
        if not hidden_indices:
            return

        menu = QMenu(self)
        is_dark = _is_dark_theme(self)
        if is_dark:
            menu.setStyleSheet("""
                QMenu {
                    background-color: #1e293b;
                    border: 1px solid #334155;
                    border-radius: 4px;
                    padding: 4px;
                }
                QMenu::item {
                    padding: 6px 20px 6px 12px;
                    border-radius: 3px;
                    color: #e2e8f0;
                    font-size: 11px;
                }
                QMenu::item:selected {
                    background-color: #0f172a;
                    color: #38bdf8;
                }
            """)
        else:
            menu.setStyleSheet("""
                QMenu {
                    background-color: #ffffff;
                    border: 1px solid #cbd5e1;
                    border-radius: 4px;
                    padding: 4px;
                }
                QMenu::item {
                    padding: 6px 20px 6px 12px;
                    border-radius: 3px;
                    color: #1f2937;
                    font-size: 11px;
                }
                QMenu::item:selected {
                    background-color: #e0f2fe;
                    color: #0369a1;
                }
            """)

        for idx in hidden_indices:
            title = self.tab_widget.tabText(idx)
            act = menu.addAction(title)
            act.triggered.connect(lambda checked, i=idx: self._select_tab_and_refresh(i))

        menu.addSeparator()
        action_new = menu.addAction("+ New Document")
        action_new.triggered.connect(self.new_worksheet)

        btn_rect = self.btn_tab_overflow.rect()
        global_pos = self.btn_tab_overflow.mapToGlobal(QPoint(0, btn_rect.height() + 2))
        menu.exec(global_pos)

    def eventFilter(self, watched, event):
        if hasattr(self, 'tab_widget') and hasattr(self, 'btn_add_tab'):
            if watched in (self.tab_widget, self.tab_widget.tabBar(), getattr(self, 'tab_bar_toolbar', None)):
                if event.type() in (QEvent.Type.Resize, QEvent.Type.LayoutRequest, QEvent.Type.Show, QEvent.Type.Move):
                    self._update_tab_bar_layout()
        return super().eventFilter(watched, event)

    def _populate_context_toolbar(self, toolbar: QToolBar):
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(3)

        self.STYLE_MODE_SELECTED = "font-weight: bold; background-color: #e0f2fe; color: #0369a1; border: 1px solid #38bdf8; border-radius: 2px; padding: 2px 8px; font-size: 11px;"
        self.STYLE_MODE_UNSELECTED = "background-color: #f8fafc; color: #374151; border: 1px solid #cbd5e1; border-radius: 2px; padding: 2px 8px; font-size: 11px;"

        self.btn_mode_text = QPushButton("Text")
        self.btn_mode_text.setFixedHeight(22)
        self.btn_mode_text.setStyleSheet(self.STYLE_MODE_UNSELECTED)
        self.btn_mode_text.clicked.connect(lambda: self._set_current_cell_mode("text"))
        layout.addWidget(self.btn_mode_text)

        self.btn_mode_nonexec = QPushButton("Nonexecutable Math")
        self.btn_mode_nonexec.setFixedHeight(22)
        self.btn_mode_nonexec.setStyleSheet(self.STYLE_MODE_UNSELECTED)
        self.btn_mode_nonexec.clicked.connect(lambda: self._set_current_cell_mode("nonexec_math"))
        layout.addWidget(self.btn_mode_nonexec)

        self.btn_mode_math = QPushButton("Math")
        self.btn_mode_math.setFixedHeight(22)
        self.btn_mode_math.setStyleSheet(self.STYLE_MODE_SELECTED)
        self.btn_mode_math.clicked.connect(lambda: self._set_current_cell_mode("2d_math"))
        layout.addWidget(self.btn_mode_math)

        self.btn_c = QPushButton("C")
        self.btn_c.setFixedWidth(24)
        self.btn_c.setFixedHeight(22)
        self.btn_c.setStyleSheet(self.STYLE_MODE_UNSELECTED)
        self.btn_c.clicked.connect(lambda: self._set_current_cell_mode("1d_math"))
        layout.addWidget(self.btn_c)

        self.combo_font = QComboBox()
        self.combo_font.addItems(["Times New Roman", "Arial", "Consolas", "Courier New", "Cambria Math"])
        self.combo_font.setFixedHeight(22)
        self.combo_font.setCurrentText("Times New Roman")
        self.combo_font.currentTextChanged.connect(self._on_font_family_changed)
        layout.addWidget(self.combo_font)

        self.combo_font_size = QComboBox()
        self.combo_font_size.setEditable(True)
        self.combo_font_size.setValidator(QIntValidator(1, 300, self))
        font_sizes = [
            "6", "7", "8", "9", "10", "11", "12", "14", "16", "18", "20",
            "22", "24", "26", "28", "32", "36", "40", "44", "48", "54",
            "60", "66", "72", "80", "88", "96", "100", "110", "120"
        ]
        self.combo_font_size.addItems(font_sizes)
        self.combo_font_size.setFixedHeight(22)
        self.combo_font_size.setFixedWidth(56)
        self.combo_font_size.view().setMinimumWidth(72)
        self.combo_font_size.setCurrentText("12")
        self.combo_font_size.currentIndexChanged.connect(lambda idx: self._on_font_size_changed(self.combo_font_size.currentText()))
        if self.combo_font_size.lineEdit():
            self.combo_font_size.lineEdit().returnPressed.connect(lambda: self._on_font_size_changed(self.combo_font_size.currentText()))
            self.combo_font_size.lineEdit().editingFinished.connect(lambda: self._on_font_size_changed(self.combo_font_size.currentText()))
        layout.addWidget(self.combo_font_size)

        btn_style = """
            QPushButton {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 3px;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: #f1f5f9;
                border-color: #94a3b8;
            }
            QPushButton:pressed {
                background-color: #e2e8f0;
            }
        """

        btn_b = QPushButton()
        btn_b.setIcon(create_toolbar_action_icon("bold"))
        btn_b.setIconSize(QSize(18, 18))
        btn_b.setFixedSize(26, 24)
        btn_b.setStyleSheet(btn_style)
        btn_b.setToolTip("Bold (Ctrl+B)")
        btn_b.clicked.connect(self._on_bold_clicked)
        layout.addWidget(btn_b)

        btn_i = QPushButton()
        btn_i.setIcon(create_toolbar_action_icon("italic"))
        btn_i.setIconSize(QSize(18, 18))
        btn_i.setFixedSize(26, 24)
        btn_i.setStyleSheet(btn_style)
        btn_i.setToolTip("Italic (Ctrl+I)")
        btn_i.clicked.connect(self._on_italic_clicked)
        layout.addWidget(btn_i)

        btn_u = QPushButton()
        btn_u.setIcon(create_toolbar_action_icon("underline"))
        btn_u.setIconSize(QSize(18, 18))
        btn_u.setFixedSize(26, 24)
        btn_u.setStyleSheet(btn_style)
        btn_u.setToolTip("Underline (Ctrl+U)")
        btn_u.clicked.connect(self._on_underline_clicked)
        layout.addWidget(btn_u)

        btn_al_left = QPushButton()
        btn_al_left.setIcon(create_toolbar_action_icon("align_left"))
        btn_al_left.setIconSize(QSize(18, 18))
        btn_al_left.setFixedSize(26, 24)
        btn_al_left.setStyleSheet(btn_style)
        btn_al_left.setToolTip("Align Left")
        btn_al_left.clicked.connect(lambda: self._set_alignment(Qt.AlignmentFlag.AlignLeft))
        layout.addWidget(btn_al_left)

        btn_al_center = QPushButton()
        btn_al_center.setIcon(create_toolbar_action_icon("align_center"))
        btn_al_center.setIconSize(QSize(18, 18))
        btn_al_center.setFixedSize(26, 24)
        btn_al_center.setStyleSheet(btn_style)
        btn_al_center.setToolTip("Align Center")
        btn_al_center.clicked.connect(lambda: self._set_alignment(Qt.AlignmentFlag.AlignHCenter))
        layout.addWidget(btn_al_center)

        btn_al_right = QPushButton()
        btn_al_right.setIcon(create_toolbar_action_icon("align_right"))
        btn_al_right.setIconSize(QSize(18, 18))
        btn_al_right.setFixedSize(26, 24)
        btn_al_right.setStyleSheet(btn_style)
        btn_al_right.setToolTip("Align Right")
        btn_al_right.clicked.connect(lambda: self._set_alignment(Qt.AlignmentFlag.AlignRight))
        layout.addWidget(btn_al_right)

        btn_outdent = QPushButton()
        btn_outdent.setIcon(create_toolbar_action_icon("outdent"))
        btn_outdent.setIconSize(QSize(18, 18))
        btn_outdent.setFixedSize(26, 24)
        btn_outdent.setStyleSheet(btn_style)
        btn_outdent.setToolTip("Decrease Indent / Exit Section (Shift+Tab)")
        btn_outdent.clicked.connect(self._outdent_active_section)
        layout.addWidget(btn_outdent)

        btn_indent = QPushButton()
        btn_indent.setIcon(create_toolbar_action_icon("indent"))
        btn_indent.setIconSize(QSize(18, 18))
        btn_indent.setFixedSize(26, 24)
        btn_indent.setStyleSheet(btn_style)
        btn_indent.setToolTip("Increase Indent (Tab)")
        btn_indent.clicked.connect(self._on_indent_clicked)
        layout.addWidget(btn_indent)

        # ── Line Spacing ToolButton with Dropdown Menu ───────────────────────
        self.btn_line_spacing = QToolButton()
        self.btn_line_spacing.setIcon(create_toolbar_action_icon("line_spacing"))
        self.btn_line_spacing.setIconSize(QSize(18, 18))
        self.btn_line_spacing.setFixedSize(26, 24)
        self.btn_line_spacing.setStyleSheet("""
            QToolButton {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 3px;
                padding: 0px;
            }
            QToolButton:hover {
                background-color: #f1f5f9;
                border-color: #94a3b8;
            }
            QToolButton:pressed {
                background-color: #e2e8f0;
            }
            QToolButton::menu-indicator {
                image: none;
                width: 0px;
                height: 0px;
            }
            QToolButton::menu-arrow {
                image: none;
                width: 0px;
                height: 0px;
            }
            QToolButton::menu-button {
                width: 0px;
                border: none;
            }
        """)
        self.btn_line_spacing.setToolTip("Line Spacing")
        self.btn_line_spacing.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)

        self.menu_line_spacing = QMenu(self.btn_line_spacing)
        self.menu_line_spacing.setStyleSheet(Theme.get_qss(self.theme_mode))
        self.line_spacing_actions = {}
        spacing_options = ["1.0", "1.15", "1.25", "1.5", "2.0", "2.5", "3.0"]
        for opt in spacing_options:
            label = f"{opt} (Single)" if opt == "1.0" else (f"{opt} (Double)" if opt == "2.0" else opt)
            act = self.menu_line_spacing.addAction(label)
            act.setCheckable(True)
            if opt == "1.0":
                act.setChecked(True)
            act.triggered.connect(lambda checked, o=opt: self._on_line_spacing_changed(o))
            self.line_spacing_actions[opt] = act
        self.btn_line_spacing.setMenu(self.menu_line_spacing)
        layout.addWidget(self.btn_line_spacing)

        # ── Separator before color buttons ──────────────────────────────
        sep = QLabel("|")
        sep.setStyleSheet("color: #cbd5e1; margin: 0 3px;")
        layout.addWidget(sep)

        # Text color button (A with color swatch bar)
        self.btn_text_color = ColorSwatchButton(
            icon_name='text_color',
            default_color=QColor('#000000'),
            tooltip='Text Color (click to pick, right-click to reset)'
        )
        self.btn_text_color.clicked.connect(self._on_text_color_clicked)
        self.btn_text_color.colorReset.connect(self._on_text_color_reset)
        layout.addWidget(self.btn_text_color)

        # Highlight button (marker icon with color swatch body)
        self.btn_highlight = ColorSwatchButton(
            icon_name='highlight',
            default_color=QColor('#ffff00'),
            tooltip='Highlight Color (click to pick, right-click to remove)'
        )
        self.btn_highlight.clicked.connect(self._on_highlight_clicked)
        self.btn_highlight.colorReset.connect(self._on_highlight_reset)
        layout.addWidget(self.btn_highlight)

        # Section Header button (downward triangle ▼)
        self.btn_section = QToolButton()
        self.btn_section.setIcon(create_toolbar_action_icon('section'))
        self.btn_section.setIconSize(QSize(18, 18))
        self.btn_section.setFixedSize(28, 24)
        self.btn_section.setToolTip("Insert Section Header (click to insert, dropdown for sub-sections / indent)")
        self.btn_section.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        self.btn_section.setStyleSheet("""
            QToolButton {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 3px;
                padding: 0px;
            }
            QToolButton:hover {
                background-color: #f1f5f9;
                border-color: #94a3b8;
            }
            QToolButton:pressed {
                background-color: #e2e8f0;
            }
            QToolButton::menu-button {
                width: 10px;
                border-left: 1px solid #e2e8f0;
            }
        """)

        self.menu_section = QMenu(self.btn_section)
        act_sec = self.menu_section.addAction("Insert Section")
        act_sec.triggered.connect(lambda: self._insert_section(level=0))
        act_subsec = self.menu_section.addAction("Insert Sub-section")
        act_subsec.triggered.connect(lambda: self._insert_section(level=1))
        self.menu_section.addSeparator()
        act_indent = self.menu_section.addAction("Indent Section / Statement (Tab)")
        act_indent.triggered.connect(self._indent_active_section)
        act_outdent = self.menu_section.addAction("Outdent / Exit Section (Shift+Tab)")
        act_outdent.triggered.connect(self._outdent_active_section)
        act_outside = self.menu_section.addAction("Insert Statement Outside Section")
        act_outside.triggered.connect(self._insert_cell_outside_section)

        self.btn_section.setMenu(self.menu_section)
        self.btn_section.clicked.connect(self._on_section_button_clicked)
        layout.addWidget(self.btn_section)

        self.context_container = container
        self.context_format_buttons = [btn_b, btn_i, btn_u, btn_al_left, btn_al_center, btn_al_right, btn_outdent, btn_indent]
        self.format_btn_map = {
            'btn_b': ('bold', btn_b),
            'btn_i': ('italic', btn_i),
            'btn_u': ('underline', btn_u),
            'btn_al_left': ('align_left', btn_al_left),
            'btn_al_center': ('align_center', btn_al_center),
            'btn_al_right': ('align_right', btn_al_right),
            'btn_outdent': ('outdent', btn_outdent),
            'btn_indent': ('indent', btn_indent),
        }

        layout.addStretch()
        toolbar.addWidget(container)

    def _ensure_active_worksheet(self) -> WorksheetView:
        """Return the active worksheet, or create a new empty one if on Start Page."""
        if self.worksheet is None or not isinstance(self.worksheet, WorksheetView):
            return self.new_worksheet()
        return self.worksheet

    def _on_section_button_clicked(self):
        """Called when user clicks the Section Header button (▼)."""
        self._insert_section(level=None)

    def _insert_section(self, level: int = None):
        """Insert a collapsible section header at the requested or inherited level."""
        ws = self._ensure_active_worksheet()
        if not ws:
            return
        active = ws.active_cell
        after_id = active.cell_id if active else None
        if len(ws.cells) == 1 and not ws.cells[0].is_section_header and not ws.cells[0].get_input_text().strip():
            after_id = f"before_{ws.cells[0].cell_id}"
        cell = ws.insert_section_cell(title="", level=level, insert_after_id=after_id)
        if cell and hasattr(cell, 'title_edit'):
            cell.title_edit.setFocus()

    def _indent_active_section(self):
        """Increase nesting level of currently focused section or cell."""
        ws = self._ensure_active_worksheet()
        if ws:
            ws.indent_active_cell()

    def _outdent_active_section(self):
        """Decrease nesting level of currently focused section or cell (exit section/subsection)."""
        ws = self._ensure_active_worksheet()
        if ws:
            ws.outdent_active_cell()

    def _insert_cell_outside_section(self):
        """Insert an execution block below that is outside of the current section."""
        ws = self._ensure_active_worksheet()
        if ws:
            ws.insert_cell_outside_section()

    def _execute_active_group(self):
        ws = self._ensure_active_worksheet()
        if ws.active_cell:
            ws.active_cell.execute()

    def _execute_all_groups(self):
        if self.worksheet:
            self.worksheet.run_all_cells()

    def _restart_worksheet(self):
        if self.worksheet:
            self.worksheet.clear_worksheet()

    def _stop_computation(self):
        if self.worksheet and hasattr(self.worksheet, 'runner'):
            self.worksheet.runner.cancel_all()
        self.statusBar().showMessage("Computation stopped.", 3000)

    def _edit_cut(self):
        if not self.worksheet or not getattr(self.worksheet, 'is_editable', True):
            return
        if self.worksheet and getattr(self.worksheet, 'selected_cells', None) and len(self.worksheet.selected_cells) >= 1:
            self.worksheet.cut_selected_cells()
            return
        w = QApplication.focusWidget()
        if w and hasattr(w, 'cut'):
            w.cut()
        elif self.worksheet and self.worksheet.active_cell:
            cell = self.worksheet.active_cell
            if hasattr(cell, 'input_edit'):
                cell.input_edit.cut()

    def _edit_copy(self):
        if self.worksheet and getattr(self.worksheet, 'selected_cells', None) and len(self.worksheet.selected_cells) >= 1:
            self.worksheet.copy_selected_cells()
            return
        w = QApplication.focusWidget()
        if w and hasattr(w, 'copy'):
            w.copy()
        elif self.worksheet and self.worksheet.active_cell:
            cell = self.worksheet.active_cell
            if hasattr(cell, 'input_edit'):
                cell.input_edit.copy()

    def _edit_paste(self):
        if self.worksheet and not getattr(self.worksheet, 'is_editable', True):
            return
        if self.worksheet and self.worksheet.paste_cells():
            return
        clipboard = QApplication.clipboard()
        md = clipboard.mimeData() if clipboard else None
        has_img = bool(md and (
            md.hasImage() or 
            (md.hasHtml() and '<img' in md.html().lower()) or 
            (md.hasUrls() and any(u.isLocalFile() and u.toLocalFile().lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif', '.webp')) for u in md.urls()))
        ))
        w = QApplication.focusWidget()
        if w and hasattr(w, 'insertFromMimeData') and has_img:
            w.insertFromMimeData(md)
            return
        if w and hasattr(w, 'paste'):
            w.paste()
        elif self.worksheet and self.worksheet.active_cell:
            cell = self.worksheet.active_cell
            if hasattr(cell, 'input_edit'):
                if has_img:
                    cell.input_edit.insertFromMimeData(md)
                else:
                    cell.input_edit.paste()
            elif hasattr(cell, 'expression_edit'):
                cell.expression_edit.paste()

    def _edit_delete(self):
        ws = getattr(self, 'worksheet', None)
        if not ws or not getattr(ws, 'is_editable', True):
            return
        if getattr(ws, 'selected_cells', None) and len(ws.selected_cells) >= 1:
            ws.delete_selected_cells()
            return
        w = QApplication.focusWidget()
        if w and hasattr(w, 'textCursor'):
            cursor = w.textCursor()
            if cursor.hasSelection():
                cursor.removeSelectedText()
                return
        if w and isinstance(w, QLineEdit) and w.hasSelectedText():
            w.backspace()
            return
        if ws.active_cell:
            ws.delete_cells([ws.active_cell.cell_id])

    def _edit_select_all(self):
        if self.worksheet and self.worksheet.cells:
            self.worksheet.select_all_cells()

    def _edit_undo(self):
        ws = getattr(self, 'worksheet', None)
        if ws and not sip.isdeleted(ws):
            ws.undo()
        else:
            w = QApplication.focusWidget()
            if w and hasattr(w, 'undo'):
                w.undo()

    def _edit_redo(self):
        ws = getattr(self, 'worksheet', None)
        if ws and not sip.isdeleted(ws):
            ws.redo()
        else:
            w = QApplication.focusWidget()
            if w and hasattr(w, 'redo'):
                w.redo()


    def _on_search_triggered(self, query: str):
        query = query.strip()
        if not query:
            return

        q_lower = query.lower()
        # Direct match in help topics
        if q_lower in self.HELP_TOPICS:
            self._show_command_help_dialog(q_lower)
            return

        # Prefix/partial match in help topics
        for key in self.HELP_TOPICS:
            if q_lower == key.lower() or key.lower().startswith(q_lower):
                self._show_command_help_dialog(key)
                return

        # Search inside active worksheet cells
        if self.worksheet:
            for cell in self.worksheet.cells:
                if hasattr(cell, 'expression_edit'):
                    txt = cell.expression_edit.toPlainText()
                    if query.lower() in txt.lower():
                        cell.expression_edit.setFocus()
                        self.statusBar().showMessage(f"Found '{query}' in worksheet cell.", 3000)
                        return

        self.statusBar().showMessage(f"No help topic or cell found for '{query}'.", 3000)

    def _show_command_help_dialog(self, topic_key: str):
        info = self.HELP_TOPICS.get(topic_key)
        if not info:
            return

        dlg = QDialog(self)
        dlg.setWindowTitle(f"Help - {info['title']}")
        dlg.resize(480, 320)
        dlg.setStyleSheet("""
            QDialog {
                background-color: #ffffff;
                color: #0f172a;
            }
            QLabel {
                color: #0f172a;
            }
        """)

        layout = QVBoxLayout(dlg)
        layout.setSpacing(12)
        layout.setContentsMargins(18, 18, 18, 18)

        # Title
        title_lbl = QLabel(f"<h3>{info['title']}</h3>")
        layout.addWidget(title_lbl)

        # Description
        desc_lbl = QLabel(info['desc'])
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet("font-size: 13px; color: #334155; line-height: 1.4;")
        layout.addWidget(desc_lbl)

        # Syntax Section
        s_title = QLabel("SYNTAX")
        s_title.setStyleSheet("font-size: 11px; font-weight: bold; color: #64748b; letter-spacing: 0.5px; margin-top: 4px;")
        layout.addWidget(s_title)

        s_val = QLabel(info['syntax'])
        s_val.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        s_val.setStyleSheet("font-family: 'Menlo', 'Courier New', monospace; font-size: 12px; background-color: #f8fafc; border: 1px solid #e2e8f0; padding: 7px 12px; border-radius: 6px; color: #0f172a;")
        layout.addWidget(s_val)

        # Example Section
        e_title = QLabel("EXAMPLE")
        e_title.setStyleSheet("font-size: 11px; font-weight: bold; color: #64748b; letter-spacing: 0.5px; margin-top: 6px;")
        layout.addWidget(e_title)

        e_val = QLabel(info['example'])
        e_val.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        e_val.setStyleSheet("font-family: 'Menlo', 'Courier New', monospace; font-size: 12px; background-color: #eff6ff; border: 1px solid #bfdbfe; padding: 7px 12px; border-radius: 6px; color: #1d4ed8; font-weight: 500;")
        layout.addWidget(e_val)

        layout.addStretch()

        # Buttons
        btn_box = QHBoxLayout()
        btn_box.addStretch()

        btn_insert = QPushButton("Insert Example into Worksheet")
        btn_insert.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                color: #ffffff;
                font-weight: bold;
                padding: 6px 14px;
                border-radius: 4px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #1d4ed8;
            }
        """)
        def on_insert():
            ws = self._ensure_active_worksheet()
            if ws:
                ws.insert_template_to_active(info['example'])
            dlg.accept()

        btn_insert.clicked.connect(on_insert)
        btn_box.addWidget(btn_insert)

        btn_close = QPushButton("Close")
        btn_close.setStyleSheet("""
            QPushButton {
                background-color: #e2e8f0;
                color: #334155;
                padding: 6px 14px;
                border-radius: 4px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #cbd5e1;
            }
        """)
        btn_close.clicked.connect(dlg.reject)
        btn_box.addWidget(btn_close)

        layout.addLayout(btn_box)
        dlg.exec()

    def _zoom_in(self):
        if self.worksheet:
            self.worksheet.zoom_in()

    def _zoom_out(self):
        if self.worksheet:
            self.worksheet.zoom_out()

    def _zoom_reset(self):
        if self.worksheet:
            self.worksheet.zoom_reset()

    def _on_zoom_changed(self, percent: int):
        self.lbl_zoom.setText(f"Zoom: {percent}%")

    def _update_mode_buttons(self, mode: str):
        if hasattr(self, 'btn_mode_text'):
            self.btn_mode_text.setStyleSheet(self.STYLE_MODE_SELECTED if mode == "text" else self.STYLE_MODE_UNSELECTED)
            self.btn_mode_nonexec.setStyleSheet(self.STYLE_MODE_SELECTED if mode == "nonexec_math" else self.STYLE_MODE_UNSELECTED)
            self.btn_mode_math.setStyleSheet(self.STYLE_MODE_SELECTED if mode == "2d_math" else self.STYLE_MODE_UNSELECTED)
            self.btn_c.setStyleSheet(self.STYLE_MODE_SELECTED if mode == "1d_math" else self.STYLE_MODE_UNSELECTED)

    def _set_current_cell_mode(self, mode: str):
        ws = self._ensure_active_worksheet()
        if ws.active_cell:
            ws.active_cell.set_input_mode(mode)
            self._update_mode_buttons(mode)
            if mode == "2d_math":
                self.lbl_mode.setText("Math Mode")
            elif mode == "nonexec_math":
                self.lbl_mode.setText("Nonexecutable Math")
            elif mode == "1d_math":
                self.lbl_mode.setText("1D Math")
            else:
                self.lbl_mode.setText("Text Mode")
            ws.active_cell.input_edit.setFocus()

    def _create_actions(self):
        # File Actions
        self.act_new = QAction("New Worksheet", self)
        self.act_new.setShortcut(QKeySequence.StandardKey.New)
        self.act_new.triggered.connect(self.new_worksheet)

        self.act_open = QAction("Open...", self)
        self.act_open.setShortcut(QKeySequence.StandardKey.Open)
        self.act_open.triggered.connect(self.open_worksheet)

        self.act_save = QAction("Save", self)
        self.act_save.setShortcut(QKeySequence.StandardKey.Save)
        self.act_save.triggered.connect(self.save_worksheet)

        self.act_save_as = QAction("Save As...", self)
        self.act_save_as.setShortcut(QKeySequence.StandardKey.SaveAs)
        self.act_save_as.triggered.connect(self.save_worksheet_as)

        self.act_print = QAction("Print...", self)
        self.act_print.setShortcut(QKeySequence.StandardKey.Print)
        self.act_print.triggered.connect(self._print_worksheet)
        self.addAction(self.act_print)

        self.act_export_pdf = QAction("Export as PDF (.pdf)...", self)
        self.act_export_pdf.triggered.connect(self.export_pdf)

        self.act_export_tex = QAction("Export to LaTeX (.tex)...", self)
        self.act_export_tex.triggered.connect(self.export_latex)

        self.act_export_md = QAction("Export to Markdown (.md)...", self)
        self.act_export_md.triggered.connect(self.export_markdown)

        self.act_exit = QAction("Exit", self)
        self.act_exit.setShortcut(QKeySequence.StandardKey.Quit)
        self.act_exit.triggered.connect(self.close)

        # Edit Actions
        self.act_undo = QAction("Undo", self)
        self.act_undo.setShortcut(QKeySequence.StandardKey.Undo)
        self.act_undo.triggered.connect(self._edit_undo)

        self.act_redo = QAction("Redo", self)
        self.act_redo.setShortcuts([QKeySequence.StandardKey.Redo, QKeySequence("Ctrl+Shift+Z"), QKeySequence("Ctrl+Y")])
        self.act_redo.triggered.connect(self._edit_redo)

        self.act_cut = QAction("Cut", self)
        self.act_cut.setShortcut(QKeySequence.StandardKey.Cut)
        self.act_cut.triggered.connect(self._edit_cut)

        self.act_copy = QAction("Copy", self)
        self.act_copy.setShortcut(QKeySequence.StandardKey.Copy)
        self.act_copy.triggered.connect(self._edit_copy)

        self.act_paste = QAction("Paste", self)
        self.act_paste.setShortcut(QKeySequence.StandardKey.Paste)
        self.act_paste.triggered.connect(self._edit_paste)

        self.act_delete = QAction("Delete", self)
        self.act_delete.setShortcut(QKeySequence.StandardKey.Delete)
        self.act_delete.triggered.connect(self._edit_delete)

        self.act_select_all = QAction("Select All", self)
        self.act_select_all.setShortcut(QKeySequence.StandardKey.SelectAll)
        self.act_select_all.triggered.connect(self._edit_select_all)

        self.act_clear = QAction("Restart & Clear Worksheet", self)
        self.act_clear.triggered.connect(self._restart_worksheet)

        # Evaluate Actions
        self.act_run_cell = QAction("Execute Group", self)
        self.act_run_cell.setShortcut("Return")
        self.act_run_cell.setToolTip("Execute active group (Enter)")
        self.act_run_cell.triggered.connect(self._execute_active_group)

        self.act_run_all = QAction("Execute Entire Worksheet", self)
        self.act_run_all.setShortcut("Ctrl+Shift+Return")
        self.act_run_all.setToolTip("Execute all groups in worksheet (!!!)")
        self.act_run_all.triggered.connect(self._execute_all_groups)

        self.act_stop = QAction("Stop Execution", self)
        self.act_stop.setToolTip("Halt current computation")

        self.act_restart = QAction("Restart Kernel", self)
        self.act_restart.setToolTip("Restart CAS engine and clear variables")
        self.act_restart.triggered.connect(self._restart_worksheet)

        # Insert Actions
        self.act_insert_cell_after = QAction("Execution Group After Cursor", self)
        self.act_insert_cell_after.setShortcut("Ctrl+J")
        self.act_insert_cell_after.triggered.connect(lambda: self._ensure_active_worksheet().add_cell())

        self.act_insert_cell_before = QAction("Execution Group Before Cursor", self)
        self.act_insert_cell_before.setShortcut("Ctrl+K")
        self.act_insert_cell_before.triggered.connect(lambda: self._ensure_active_worksheet().add_cell(insert_after_id=f"before_{self.worksheet.active_cell.cell_id}" if self.worksheet and self.worksheet.active_cell else None))

        self.act_toggle_mode_f5 = QAction("Toggle 1-D / 2-D Math", self)
        self.act_toggle_mode_f5.setShortcut("F5")
        self.act_toggle_mode_f5.triggered.connect(lambda: self.worksheet.active_cell.toggle_input_mode() if self.worksheet and self.worksheet.active_cell else None)

        self.act_matrix = QAction("Matrix Wizard...", self)
        self.act_matrix.setShortcut("Ctrl+M")
        self.act_matrix.triggered.connect(self._open_matrix_dialog)

        # View Toggles
        self.act_toggle_palette = self.palette_dock.toggleViewAction()
        self.act_toggle_palette.setText("Palettes Dock")

        self.act_toggle_context = self.context_dock.toggleViewAction()
        self.act_toggle_context.setText("Context Panel")

        self.act_toggle_plotter = self.plot_dock.toggleViewAction()
        self.act_toggle_plotter.setText("2D Plotter Dock")

        self.act_toggle_doc_mode = QAction("Document Mode (Free-form)", self)
        self.act_toggle_doc_mode.setCheckable(True)
        self.act_toggle_doc_mode.setChecked(True)
        self.act_toggle_doc_mode.toggled.connect(lambda checked: self.worksheet.set_worksheet_mode(not checked) if self.worksheet else None)

        # Zoom Actions
        self.act_zoom_in = QAction("Zoom In", self)
        self.act_zoom_in.setShortcuts([
            QKeySequence.StandardKey.ZoomIn,
            QKeySequence("Ctrl+="),
            QKeySequence("Ctrl++"),
            QKeySequence("Ctrl+Shift+="),
            QKeySequence("Ctrl+Shift++"),
            QKeySequence("Meta+="),
            QKeySequence("Meta++")
        ])
        self.act_zoom_in.triggered.connect(self._zoom_in)
        self.addAction(self.act_zoom_in)

        self.act_zoom_out = QAction("Zoom Out", self)
        self.act_zoom_out.setShortcuts([
            QKeySequence.StandardKey.ZoomOut,
            QKeySequence("Ctrl+-"),
            QKeySequence("Ctrl+Shift+-"),
            QKeySequence("Meta+-")
        ])
        self.act_zoom_out.triggered.connect(self._zoom_out)
        self.addAction(self.act_zoom_out)

        self.act_zoom_reset = QAction("Actual Size (100%)", self)
        self.act_zoom_reset.setShortcuts([
            QKeySequence("Ctrl+0"),
            QKeySequence("Meta+0")
        ])
        self.act_zoom_reset.triggered.connect(self._zoom_reset)
        self.addAction(self.act_zoom_reset)

    def _create_menus(self):
        menubar = self.menuBar()

        # 1. File Menu
        menu_file = menubar.addMenu("&File")
        menu_file.addAction(self.act_new)
        menu_file.addAction(self.act_open)
        menu_file.addAction(self.act_save)
        menu_file.addAction(self.act_save_as)
        menu_file.addSeparator()
        menu_file.addAction(self.act_export_pdf)
        menu_file.addAction(self.act_export_tex)
        menu_file.addAction(self.act_export_md)
        menu_file.addSeparator()
        menu_file.addAction(self.act_exit)

        # 2. Edit Menu
        menu_edit = menubar.addMenu("&Edit")
        menu_edit.addAction(self.act_undo)
        menu_edit.addAction(self.act_redo)
        menu_edit.addSeparator()
        menu_edit.addAction(self.act_cut)
        menu_edit.addAction(self.act_copy)
        menu_edit.addAction(self.act_paste)
        menu_edit.addAction(self.act_delete)
        menu_edit.addSeparator()
        menu_edit.addAction(self.act_select_all)
        menu_edit.addSeparator()
        menu_edit.addAction(self.act_clear)

        # 3. View Menu
        menu_view = menubar.addMenu("&View")
        menu_view.addAction(self.act_toggle_palette)
        menu_view.addAction(self.act_toggle_context)
        menu_view.addAction(self.act_toggle_plotter)
        menu_view.addSeparator()
        menu_view.addAction(self.main_toolbar.toggleViewAction())
        menu_view.addAction(self.tab_bar_toolbar.toggleViewAction())
        menu_view.addAction(self.context_toolbar.toggleViewAction())
        menu_view.addSeparator()
        menu_view.addAction(self.act_toggle_doc_mode)
        menu_view.addSeparator()

        menu_zoom = menu_view.addMenu("Zoom")
        menu_zoom.addAction(self.act_zoom_in)
        menu_zoom.addAction(self.act_zoom_out)
        menu_zoom.addAction(self.act_zoom_reset)
        menu_zoom.addSeparator()
        for z in [50, 75, 100, 125, 150, 175, 200, 250, 300]:
            menu_zoom.addAction(f"{z}%", lambda val=z: self.worksheet.set_zoom(val) if self.worksheet else None)

        # 4. Insert Menu
        menu_insert = menubar.addMenu("&Insert")
        menu_insert.addAction(self.act_insert_cell_after)
        menu_insert.addAction(self.act_insert_cell_before)
        menu_insert.addAction("Statement Outside Section", self._insert_cell_outside_section)
        menu_insert.addSeparator()
        menu_insert.addAction("Section", lambda: self._insert_section(0))
        menu_insert.addAction("Subsection", lambda: self._insert_section(1))
        menu_insert.addAction(self.act_toggle_mode_f5)
        menu_insert.addSeparator()
        menu_insert.addAction("Image...", self._on_insert_image)
        menu_insert.addAction(self.act_matrix)
        menu_insert.addSeparator()
        menu_insert.addAction("polygonOmråde Linear Inequality Region", lambda: self._on_insert_template("polygonOmråde(Uligheder, x = -1 .. 13, y = -1 .. 12)"))
        menu_insert.addAction("LPplot Level Curves", lambda: self._on_insert_template("LPplot(30*x + 20*y, Uligheder, [0, 120, 300])"))
        menu_insert.addAction("Derivative d/dx", lambda: self._on_insert_template("diff(f(x), x)"))
        menu_insert.addAction("Indefinite Integral", lambda: self._on_insert_template("integrate(f(x), x)"))
        menu_insert.addAction("Taylor Series", lambda: self._on_insert_template("taylor(f(x), x, 0, 6)"))
        menu_insert.addAction("Embedded Bitwise Representation (0b)", lambda: self._on_insert_template("to_bin(0x5A, 8)"))

        # 5. Format Menu
        menu_format = menubar.addMenu("&Format")
        menu_format.addAction("2-D Math", lambda: self._set_current_cell_mode("2d_math"))
        menu_format.addAction("1-D Math", lambda: self._set_current_cell_mode("1d_math"))
        menu_format.addAction("Text", lambda: self._set_current_cell_mode("text"))
        menu_format.addSeparator()
        menu_format.addAction("Indent Section / Statement (Tab)", self._indent_active_section)
        menu_format.addAction("Outdent / Exit Section (Shift+Tab)", self._outdent_active_section)
        menu_format.addSeparator()

        menu_spacing = menu_format.addMenu("Line Spacing")
        spacing_options = ["1.0", "1.15", "1.25", "1.5", "2.0", "2.5", "3.0"]
        for opt in spacing_options:
            label = f"{opt} (Single)" if opt == "1.0" else (f"{opt} (Double)" if opt == "2.0" else opt)
            act = menu_spacing.addAction(label)
            act.triggered.connect(lambda checked, o=opt: self._on_line_spacing_changed(o))

        menu_decimal = menu_format.addMenu("Decimal Separator")
        self.act_dec_comma = QAction("Comma ( , )", self, checkable=True)
        self.act_dec_dot = QAction("Period ( . )", self, checkable=True)
        self.act_dec_comma.setChecked(True)
        self.act_dec_dot.setChecked(False)
        self.act_dec_comma.triggered.connect(lambda: self._set_decimal_separator(','))
        self.act_dec_dot.triggered.connect(lambda: self._set_decimal_separator('.'))
        menu_decimal.addAction(self.act_dec_comma)
        menu_decimal.addAction(self.act_dec_dot)

        # 6. Evaluate Menu
        menu_eval = menubar.addMenu("E&valuate")
        menu_eval.addAction("Execute Selection (Enter)", self._execute_active_group)
        menu_eval.addAction(self.act_run_all)
        menu_eval.addAction(self.act_stop)
        menu_eval.addSeparator()
        menu_eval.addAction(self.act_restart)

        # 7. Options Menu (renamed from Tools)
        menu_options = menubar.addMenu("&Options")
        act_options = menu_options.addAction("Options & Preferences...", self._show_options_dialog)
        act_options.setShortcut(QKeySequence("Ctrl+,"))
        menu_options.addSeparator()

        # Theme submenu
        menu_theme = menu_options.addMenu("Theme")
        self.act_theme_light = menu_theme.addAction("Light Mode (Maple Classic)")
        self.act_theme_dark = menu_theme.addAction("Dark Mode (Slate Dark)")
        self.act_theme_light.setCheckable(True)
        self.act_theme_dark.setCheckable(True)
        self.act_theme_light.setChecked(self.theme_mode == Theme.LIGHT)
        self.act_theme_dark.setChecked(self.theme_mode == Theme.DARK)
        self.act_theme_light.triggered.connect(lambda: self.set_theme(Theme.LIGHT))
        self.act_theme_dark.triggered.connect(lambda: self.set_theme(Theme.DARK))

        # Decimal Separator submenu
        menu_decimal_opt = menu_options.addMenu("Decimal Separator")
        menu_decimal_opt.addAction(self.act_dec_comma)
        menu_decimal_opt.addAction(self.act_dec_dot)

        menu_options.addSeparator()
        menu_options.addAction("Restore Default Layout", self._restore_default_layout)

        # 8. Help Menu
        menu_help = menubar.addMenu("&Help")
        menu_help.addAction("Help Topics (e.g. ? polygonOmråde)", self._show_help_dialog)
        menu_help.addAction("About OpenMath", self._show_about_dialog)

    def _create_status_bar(self):
        """Sunken segmented status bar."""
        statusbar = self.statusBar()
        statusbar.setSizeGripEnabled(False)

        self.lbl_status_msg = QLabel("Ready")
        statusbar.addWidget(self.lbl_status_msg, 1)

        self.chk_editable = QCheckBox("Editable")
        self.chk_editable.setChecked(True)
        self.chk_editable.setEnabled(self.worksheet is not None)
        self.chk_editable.setCursor(Qt.CursorShape.PointingHandCursor)
        self.chk_editable.toggled.connect(self._on_editable_toggled)
        statusbar.addPermanentWidget(self.chk_editable)

        self.lbl_profile = QLabel("Default Profile")
        self.lbl_profile.setToolTip("Active Profile: Default Profile")
        statusbar.addPermanentWidget(self.lbl_profile)

        self.lbl_path = QLabel("")
        self.lbl_path.setCursor(Qt.CursorShape.PointingHandCursor)
        self.lbl_path.mousePressEvent = self._on_path_clicked
        statusbar.addPermanentWidget(self.lbl_path)

        self.lbl_memory = QLabel("Memory: 0.00M")
        self.lbl_memory.setToolTip("Process Memory Working Set")
        statusbar.addPermanentWidget(self.lbl_memory)

        self.lbl_time = QLabel("Time: 0.00s")
        self.lbl_time.setToolTip("Execution time of last CAS evaluation")
        statusbar.addPermanentWidget(self.lbl_time)

        self.lbl_decimal = QLabel('Decimal: <span style="font-size: 15px; font-weight: bold;">,</span>')
        self.lbl_decimal.setToolTip("Decimal Separator: Comma ( , ). Click to toggle.")
        self.lbl_decimal.setCursor(Qt.CursorShape.PointingHandCursor)
        self.lbl_decimal.mousePressEvent = lambda e: self._toggle_decimal_separator()
        statusbar.addPermanentWidget(self.lbl_decimal)

        self.lbl_zoom = QLabel("Zoom: 100%")
        self.lbl_zoom.setCursor(Qt.CursorShape.PointingHandCursor)
        self.lbl_zoom.setToolTip("Click to reset zoom to 100%")
        self.lbl_zoom.mousePressEvent = lambda e: self.worksheet.zoom_reset() if self.worksheet else None
        statusbar.addPermanentWidget(self.lbl_zoom)

        self.lbl_mode = QLabel("Start Page")
        self.lbl_mode.setStyleSheet("font-weight: bold; color: #1e3a8a;")
        statusbar.addPermanentWidget(self.lbl_mode)

        self._memory_timer = QTimer(self)
        self._memory_timer.setInterval(2000)
        self._memory_timer.timeout.connect(self._update_memory_display)
        self._memory_timer.start()
        self._update_memory_display()

        self._update_editable_ui()
        self._update_path_display()

    def _update_editable_ui(self):
        if not hasattr(self, 'chk_editable'):
            return

        icon_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "resources", "check_white.png")).replace("\\", "/")

        if self.worksheet is None:
            self.chk_editable.setEnabled(False)
            self.chk_editable.blockSignals(True)
            self.chk_editable.setChecked(True)
            self.chk_editable.setText("Editable")
            self.chk_editable.setToolTip("Open or create a document to edit.")
            self.chk_editable.setStyleSheet("""
                QCheckBox {
                    font-size: 11px;
                    color: #9ca3af;
                    margin-right: 4px;
                    padding: 2px 4px;
                    spacing: 6px;
                }
                QCheckBox::indicator {
                    width: 14px;
                    height: 14px;
                    border: 1.5px solid #cbd5e1;
                    border-radius: 3px;
                    background-color: #f1f5f9;
                }
            """)
            self.chk_editable.blockSignals(False)
            return

        is_edit = getattr(self.worksheet, 'is_editable', True)
        self.chk_editable.setEnabled(True)
        self.chk_editable.blockSignals(True)
        self.chk_editable.setChecked(is_edit)
        self.chk_editable.blockSignals(False)

        is_dark = _is_dark_theme(self)
        text_color = "#f8fafc" if is_dark else "#1e293b"

        if is_edit:
            self.chk_editable.setText("Editable")
            self.chk_editable.setToolTip("Document is editable. Click to switch to View Mode.")
            self.chk_editable.setStyleSheet(f"""
                QCheckBox {{
                    font-size: 11px;
                    font-weight: 600;
                    color: {text_color};
                    margin-right: 4px;
                    padding: 2px 6px;
                    spacing: 6px;
                }}
                QCheckBox::indicator {{
                    width: 14px;
                    height: 14px;
                    border: 1.5px solid #0284c7;
                    border-radius: 3px;
                    background-color: #0284c7;
                    image: url("{icon_path}");
                }}
                QCheckBox::indicator:hover {{
                    border-color: #0369a1;
                    background-color: #0369a1;
                }}
            """)
        else:
            self.chk_editable.setText("View Mode (Click to Edit)")
            self.chk_editable.setToolTip("Document is in View Mode (Read-Only). Click here to enable editing.")
            self.chk_editable.setStyleSheet("""
                QCheckBox {
                    font-size: 11px;
                    font-weight: bold;
                    color: #92400e;
                    background-color: #fef3c7;
                    border: 1px solid #fcd34d;
                    border-radius: 3px;
                    padding: 2px 8px;
                    margin-right: 4px;
                    spacing: 6px;
                }
                QCheckBox::indicator {
                    width: 14px;
                    height: 14px;
                    border: 1.5px solid #78350f;
                    border-radius: 3px;
                    background-color: #fef3c7;
                }
                QCheckBox::indicator:hover {
                    border-color: #92400e;
                    background-color: #fde68a;
                }
            """)

    def _on_editable_toggled(self, checked: bool):
        if self.worksheet and not sip.isdeleted(self.worksheet):
            self.worksheet.set_editable(checked)
        self._update_editable_ui()
        msg = "Document is now editable." if checked else "Document is now in View Mode (Read-Only)."
        self._show_status(msg, 2500)

    def _on_execution_time_changed(self, time_s: float):
        if hasattr(self, 'lbl_time'):
            self.lbl_time.setText(f"Time: {time_s:.2f}s")
        self._update_memory_display()

    def _update_memory_display(self):
        if hasattr(self, 'lbl_memory'):
            mem = get_current_process_memory_mb()
            if mem > 0:
                self.lbl_memory.setText(f"Memory: {mem:.2f}M")

    def _update_path_display(self):
        if not hasattr(self, 'lbl_path'):
            return
        if self.worksheet is None:
            self.lbl_path.setText("")
            self.lbl_path.setStyleSheet("")
            self.lbl_path.setToolTip("")
            return

        doc_path = getattr(self.worksheet, 'file_path', None) or self.current_file_path
        if doc_path:
            self.lbl_path.setText(doc_path)
            self.lbl_path.setStyleSheet("color: #374151; padding: 0 4px;")
            self.lbl_path.setToolTip(f"{doc_path}\nClick to reveal in file manager")
        else:
            self.lbl_path.setText("Save Document")
            self.lbl_path.setStyleSheet("color: #dc2626; font-weight: bold; padding: 0 4px;")
            self.lbl_path.setToolTip("Document is unsaved. Click to save now.")

    def _on_path_clicked(self, event):
        if self.worksheet is None:
            return
        doc_path = getattr(self.worksheet, 'file_path', None) or self.current_file_path
        if doc_path and os.path.exists(doc_path):
            try:
                abs_path = os.path.abspath(doc_path)
                if sys.platform == "win32":
                    subprocess.Popen(f'explorer /select,"{abs_path}"')
                elif sys.platform == "darwin":
                    subprocess.Popen(["open", "-R", abs_path])
                else:
                    folder = os.path.dirname(abs_path)
                    subprocess.Popen(["xdg-open", folder])
            except Exception as e:
                self._show_status(f"Could not open file location: {e}", 3000)
        else:
            self.save_worksheet()

    def _set_decimal_separator(self, sep: str):
        from cas_engine.formatter import MathFormatter
        from cas_engine.parser import MathParser
        MathFormatter.set_decimal_separator(sep)
        MathParser.set_decimal_separator(sep)
        if hasattr(self, 'act_dec_comma'):
            self.act_dec_comma.setChecked(sep == ',')
        if hasattr(self, 'act_dec_dot'):
            self.act_dec_dot.setChecked(sep == '.')
        if hasattr(self, 'lbl_decimal'):
            self.lbl_decimal.setText(f'Decimal: <span style="font-size: 15px; font-weight: bold;">{sep}</span>')
            self.lbl_decimal.setToolTip(f"Decimal Separator: {'Comma ( , )' if sep == ',' else 'Period ( . )'}. Click to toggle.")
        # Refresh current active cell preview if available
        if hasattr(self, 'worksheet') and self.worksheet and hasattr(self.worksheet, 'active_cell') and self.worksheet.active_cell:
            if hasattr(self.worksheet.active_cell, '_update_live_preview'):
                self.worksheet.active_cell._update_live_preview()

    def _toggle_decimal_separator(self):
        from cas_engine.formatter import MathFormatter
        current = getattr(MathFormatter, 'decimal_separator', ',')
        new_sep = '.' if current == ',' else ','
        self._set_decimal_separator(new_sep)

    def _restore_default_layout(self):
        self.palette_dock.setVisible(True)
        self.context_dock.setVisible(False)
        self.plot_dock.setVisible(False)
        self.main_toolbar.setVisible(True)
        self.tab_bar_toolbar.setVisible(True)
        self.context_toolbar.setVisible(True)
        self.resizeDocks([self.palette_dock], [275], Qt.Orientation.Horizontal)
        self.save_settings()

    def _toggle_context_panel(self):
        self.context_dock.setVisible(not self.context_dock.isVisible())
        self.save_settings()

    def _on_active_cell_changed(self, cell):
        if cell:
            text = cell.get_input_text()
            self.context_panel.set_target_expression(text, result_obj=getattr(cell, 'current_result', None))
            if hasattr(self.palette_panel, 'refresh_variables'):
                self.palette_panel.refresh_variables()
            self._update_mode_buttons(cell.input_mode)

            if cell.input_mode == cell.MODE_2D_MATH:
                mode_name = "Math Mode"
            elif cell.input_mode == getattr(cell, 'MODE_NONEXEC_MATH', 'nonexec_math'):
                mode_name = "Nonexecutable Math"
            elif cell.input_mode == cell.MODE_1D_MATH:
                mode_name = "1D Math"
            else:
                mode_name = "Text Mode"
            self.lbl_mode.setText(mode_name)

            # Sync font toolbar widgets
            self.combo_font.blockSignals(True)
            self.combo_font.setCurrentText(getattr(cell, 'current_font_family', "Times New Roman"))
            self.combo_font.blockSignals(False)

            target_sz = getattr(cell, 'current_font_size', 12)
            if hasattr(cell, 'input_edit') and cell.input_edit:
                cur_pt = cell.input_edit.textCursor().charFormat().fontPointSize()
                if cur_pt <= 0:
                    cur_pt = cell.input_edit.currentCharFormat().fontPointSize()
                if cur_pt > 0:
                    factor = getattr(cell, 'zoom_factor', 1.0)
                    target_sz = int(round(cur_pt / factor))

            self.combo_font_size.blockSignals(True)
            if self.combo_font_size.lineEdit():
                self.combo_font_size.lineEdit().blockSignals(True)
            self.combo_font_size.setCurrentText(str(target_sz))
            if self.combo_font_size.lineEdit():
                self.combo_font_size.lineEdit().blockSignals(False)
            self.combo_font_size.blockSignals(False)

            # Sync line spacing toolbar widgets
            if hasattr(cell, 'input_edit') and cell.input_edit:
                block_fmt = cell.input_edit.textCursor().blockFormat()
                if block_fmt.lineHeightType() == 1 and block_fmt.lineHeight() > 0:
                    val = block_fmt.lineHeight() / 100.0
                    sp_str = f"{val:.2f}".rstrip('0').rstrip('.')
                else:
                    sp_str = str(getattr(cell, 'current_line_spacing', 1.0))
                self._sync_line_spacing_ui(sp_str)
            else:
                self._sync_line_spacing_ui("1.0")

    def _on_line_spacing_changed(self, spacing_str: str = ""):
        if not spacing_str and hasattr(self, 'combo_line_spacing'):
            spacing_str = self.combo_line_spacing.currentText()
        try:
            val = float(str(spacing_str).strip())
        except (ValueError, TypeError):
            val = 1.0

        clean_str = f"{val:.2f}".rstrip('0').rstrip('.')
        if clean_str in ("1", "1."):
            clean_str = "1.0"
        elif clean_str in ("2", "2."):
            clean_str = "2.0"
        elif clean_str in ("3", "3."):
            clean_str = "3.0"

        self._sync_line_spacing_ui(clean_str)

        ws = self._ensure_active_worksheet()
        if ws:
            ws.set_active_cell_line_spacing(val)

    def _sync_line_spacing_ui(self, spacing_str: str):
        clean_str = str(spacing_str)
        if clean_str in ("1", "1."):
            clean_str = "1.0"
        elif clean_str in ("2", "2."):
            clean_str = "2.0"
        elif clean_str in ("3", "3."):
            clean_str = "3.0"

        if hasattr(self, 'combo_line_spacing'):
            self.combo_line_spacing.blockSignals(True)
            self.combo_line_spacing.setCurrentText(clean_str)
            self.combo_line_spacing.blockSignals(False)

        if hasattr(self, 'line_spacing_actions'):
            for opt, act in self.line_spacing_actions.items():
                act.setChecked(opt == clean_str)

    def _on_font_family_changed(self, family: str):
        if self.worksheet and family:
            self.worksheet.set_active_cell_font_family(family)

    def _on_font_size_changed(self, size_str: str = ""):
        if not size_str and hasattr(self, 'combo_font_size'):
            size_str = self.combo_font_size.currentText()
        if self.worksheet and size_str and size_str.strip().isdigit():
            val = int(size_str.strip())
            if 1 <= val <= 300:
                self.worksheet.set_active_cell_font_size(val)

    def _on_bold_clicked(self):
        if self.worksheet:
            self.worksheet.toggle_active_cell_bold()

    def _on_italic_clicked(self):
        if self.worksheet:
            self.worksheet.toggle_active_cell_italic()

    def _on_underline_clicked(self):
        if self.worksheet:
            self.worksheet.toggle_active_cell_underline()

    def _set_alignment(self, align: Qt.AlignmentFlag):
        ws = self._ensure_active_worksheet()
        if ws and ws.active_cell:
            ws.active_cell.input_edit.setAlignment(align)

    def _on_indent_clicked(self):
        ws = self._ensure_active_worksheet()
        if ws and ws.active_cell:
            ws.active_cell.input_edit.insertPlainText("  ")

    def _on_text_color_clicked(self):
        """Open 20-color simplified palette for text foreground color."""
        if not self.worksheet:
            return
        menu = ColorPaletteMenu(
            parent_btn=self.btn_text_color,
            is_highlight=False,
            on_color_selected=self._apply_text_color,
            on_reset=self._on_text_color_reset,
            on_custom_color=self._open_custom_text_color_dialog,
            theme_mode=self.theme_mode,
            parent=self
        )
        pos = self.btn_text_color.mapToGlobal(QPoint(0, self.btn_text_color.height()))
        menu.exec(pos)

    def _apply_text_color(self, color: QColor):
        if color.isValid() and self.worksheet:
            self.btn_text_color.set_color(color)
            self.worksheet.set_active_cell_text_color(color)

    def _open_custom_text_color_dialog(self):
        if not self.worksheet:
            return
        cur = self.btn_text_color.current_color()
        color = QColorDialog.getColor(
            cur,
            self,
            "Text Color",
            QColorDialog.ColorDialogOption.ShowAlphaChannel
        )
        if color.isValid():
            self._apply_text_color(color)

    def _on_highlight_clicked(self):
        """Open 20-color simplified palette for background highlight color."""
        if not self.worksheet:
            return
        menu = ColorPaletteMenu(
            parent_btn=self.btn_highlight,
            is_highlight=True,
            on_color_selected=self._apply_highlight_color,
            on_reset=self._on_highlight_reset,
            on_custom_color=self._open_custom_highlight_dialog,
            theme_mode=self.theme_mode,
            parent=self
        )
        pos = self.btn_highlight.mapToGlobal(QPoint(0, self.btn_highlight.height()))
        menu.exec(pos)

    def _apply_highlight_color(self, color: QColor):
        if not self.worksheet:
            return
        if color.isValid() and color.alpha() > 0:
            self.btn_highlight.set_color(color)
            self.worksheet.set_active_cell_highlight_color(color)
        else:
            self._on_highlight_reset()

    def _open_custom_highlight_dialog(self):
        if not self.worksheet:
            return
        cur = self.btn_highlight.current_color()
        color = QColorDialog.getColor(
            cur,
            self,
            "Highlight Color",
            QColorDialog.ColorDialogOption.ShowAlphaChannel
        )
        if color.isValid():
            self._apply_highlight_color(color)

    def _on_text_color_reset(self):
        """Reset text color to default black."""
        self.btn_text_color.set_color(QColor('#000000'))
        if self.worksheet:
            self.worksheet.clear_active_cell_text_color()

    def _on_highlight_reset(self):
        """Clear highlight color."""
        self.btn_highlight.set_color(QColor('#ffff00'))
        if self.worksheet:
            self.worksheet.clear_active_cell_highlight_color()

    def _on_context_operation_requested(self, cmd: str):
        ws = self._ensure_active_worksheet()
        cell = ws.add_cell(expression=cmd)
        cell.execute()

    def _on_insert_template(self, template_str: str):
        ws = self._ensure_active_worksheet()
        ws.insert_template_to_active(template_str)

    def _on_insert_image(self):
        ws = self._ensure_active_worksheet()
        if ws and ws.active_cell and hasattr(ws.active_cell, 'input_edit'):
            ws.active_cell.input_edit._on_insert_image_dialog()

    def _open_matrix_dialog(self):
        dialog = MatrixDialog(self, theme_mode=self.theme_mode)
        if dialog.exec():
            mat_str = dialog.get_matrix_string()
            if mat_str:
                ws = self._ensure_active_worksheet()
                ws.insert_template_to_active(mat_str)

    def _on_worksheet_plot_requested(self, expr_str: str):
        self.plot_dock.setVisible(True)
        self.plot_dock.raise_()
        self.plot_panel.expr_input.setText(expr_str)
        self.plot_panel.plot_current_expression()

    def _on_plot_inserted_from_panel(self, plot_data):
        ws = self._ensure_active_worksheet()
        cell = ws.add_cell(expression=f"plot({self.plot_panel.expr_input.text()})")
        cell.execute()

    def _on_tab_changed(self, index: int):
        if index < 0 or index >= self.doc_stack.count():
            return
        self.doc_stack.setCurrentIndex(index)
        current_w = self.doc_stack.currentWidget()
        if isinstance(current_w, WorksheetView):
            self.worksheet = current_w
            self.current_file_path = getattr(self.worksheet, 'file_path', None)
            tab_text = self.tab_widget.tabText(index)
            clean_title = tab_text.replace("*", "")
            self.setWindowTitle(f"{clean_title}* - [Server 3] - OpenMath")
            if self.worksheet.active_cell:
                self.context_panel.set_target_expression(self.worksheet.active_cell.get_input_text())
            self.lbl_mode.setText("Math Mode")
            self.lbl_zoom.setText(f"Zoom: {self.worksheet.zoom_percent}%")
        else:
            self.worksheet = None
            self.current_file_path = None
            self.setWindowTitle("Start.mw - [Server 3] - OpenMath")
            self.context_panel.set_target_expression("")
            self.lbl_mode.setText("Start Page")
        self._update_editable_ui()
        self._update_path_display()

    def _on_tab_close_requested(self, index: int):
        if index == 0 and isinstance(self.doc_stack.widget(0), StartPageView):
            if self.tab_widget.count() == 1:
                return  # Do not close the Start Page if it is the only tab

        w = self.doc_stack.widget(index)
        if isinstance(w, WorksheetView) and hasattr(w, 'runner'):
            w.runner.shutdown()

        self.doc_stack.removeWidget(w)
        self.tab_widget.removeTab(index)
        w.deleteLater()

        self._on_tab_changed(self.tab_widget.currentIndex())
        self._update_add_tab_button_pos()
        QTimer.singleShot(0, self._update_add_tab_button_pos)

    def new_worksheet(self) -> WorksheetView:
        """Create a new empty document/worksheet and add it as a new tab."""
        self.document_counter += 1
        new_ws = WorksheetView(self.engine, self, theme_mode=self.theme_mode)
        new_ws.file_path = None
        new_ws.statusMessage.connect(self._show_status)
        new_ws.plotRequested.connect(self._on_worksheet_plot_requested)
        new_ws.activeCellChanged.connect(self._on_active_cell_changed)
        new_ws.zoomChanged.connect(self._on_zoom_changed)
        new_ws.executionTimeChanged.connect(self._on_execution_time_changed)
        new_ws.editableChanged.connect(lambda ed: self._update_editable_ui())
        if hasattr(self, 'chk_editable'):
            new_ws.set_editable(self.chk_editable.isChecked())

        stack_idx = self.doc_stack.addWidget(new_ws)
        tab_title = f"*Untitled ({self.document_counter})"
        tab_idx = self.tab_widget.addTab(QWidget(), tab_title)

        self.tab_widget.setCurrentIndex(tab_idx)
        self.doc_stack.setCurrentIndex(stack_idx)
        self.worksheet = new_ws
        self.current_file_path = None
        self.lbl_zoom.setText(f"Zoom: {new_ws.zoom_percent}%")
        self.setWindowTitle(f"Untitled ({self.document_counter})* - [Server 3] - OpenMath")
        self._update_editable_ui()
        self._update_path_display()
        self._update_add_tab_button_pos()
        QTimer.singleShot(0, self._update_add_tab_button_pos)
        self._show_status("New empty document created.", 2000)
        return new_ws

    def load_worksheet_from_file(self, path: str):
        """Load a worksheet file (.mw or .json) into a new tab with visual loading indicator."""
        if not path or not os.path.isfile(path):
            return
        abs_path = os.path.abspath(path)
        base_name = os.path.basename(abs_path)

        if hasattr(self, 'loading_overlay'):
            self.loading_overlay.show_loading(base_name, "Reading worksheet archive...")
        self._show_status(f"Opening {base_name}...", 0)
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        QApplication.processEvents()

        try:
            import zipfile
            content = ""
            if zipfile.is_zipfile(abs_path):
                try:
                    if hasattr(self, 'loading_overlay'):
                        self.loading_overlay.set_progress(0, 0, "Extracting worksheet XML from archive...")
                    with zipfile.ZipFile(abs_path, 'r') as zf:
                        names = zf.namelist()
                        target = next((n for n in ['content.xml', 'document.xml'] if n in names), None)
                        if not target:
                            target = next((n for n in names if n.endswith('.mw') or n.endswith('.xml')), None)
                        if target:
                            content = zf.read(target).decode('utf-8', errors='replace')
                        else:
                            content = ""
                except Exception:
                    content = ""
            else:
                try:
                    with open(abs_path, "r", encoding="utf-8-sig") as f:
                        content = f.read()
                except UnicodeDecodeError:
                    with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
                        content = f.read()

            self.document_counter += 1
            new_ws = WorksheetView(self.engine, self, theme_mode=self.theme_mode)
            new_ws.file_path = abs_path
            new_ws.statusMessage.connect(self._show_status)
            new_ws.plotRequested.connect(self._on_worksheet_plot_requested)
            new_ws.activeCellChanged.connect(self._on_active_cell_changed)
            new_ws.zoomChanged.connect(self._on_zoom_changed)
            new_ws.executionTimeChanged.connect(self._on_execution_time_changed)
            new_ws.editableChanged.connect(lambda ed: self._update_editable_ui())
            if hasattr(self, 'chk_editable'):
                new_ws.set_editable(self.chk_editable.isChecked())

            progress_cb = self.loading_overlay.set_progress if hasattr(self, 'loading_overlay') else None
            new_ws.load_from_content(content, file_path=abs_path, progress_callback=progress_cb)

            stack_idx = self.doc_stack.addWidget(new_ws)
            tab_idx = self.tab_widget.addTab(QWidget(), base_name)

            self.tab_widget.setCurrentIndex(tab_idx)
            self.doc_stack.setCurrentIndex(stack_idx)
            self.worksheet = new_ws
            self.current_file_path = abs_path
            self.setWindowTitle(f"{base_name} - [Server 3] - OpenMath")
            self._update_editable_ui()
            self._update_path_display()
            self._update_add_tab_button_pos()
            QTimer.singleShot(0, self._update_add_tab_button_pos)
            self._show_status(f"Loaded {abs_path} ({len(new_ws.cells)} cells)", 3000)
        except Exception as e:
            QMessageBox.critical(self, "Error Loading Worksheet", str(e))
        finally:
            QApplication.restoreOverrideCursor()
            if hasattr(self, 'loading_overlay'):
                self.loading_overlay.hide_loading()

    def open_worksheet(self):
        """Open an existing project/worksheet via file dialog and load it into a new tab."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Worksheet", "",
            "Worksheet (*.mw *.json);;All Files (*.*)"
        )
        if path:
            self.load_worksheet_from_file(path)

    def save_worksheet(self):
        if self.worksheet is None:
            return
        target_path = getattr(self.worksheet, 'file_path', None) or self.current_file_path
        if not target_path:
            self.save_worksheet_as()
        else:
            try:
                if target_path.lower().endswith('.mw'):
                    data = self.worksheet.to_mw()
                else:
                    data = self.worksheet.to_json()
                with open(target_path, "w", encoding="utf-8") as f:
                    f.write(data)
                self.worksheet.file_path = target_path
                self.current_file_path = target_path
                base_name = os.path.basename(target_path)
                self.tab_widget.setTabText(self.tab_widget.currentIndex(), base_name)
                self.setWindowTitle(f"{base_name} - [Server 3] - OpenMath")
                self._update_path_display()
                self._show_status(f"Saved to {target_path}", 3000)
            except Exception as e:
                QMessageBox.critical(self, "Error Saving Worksheet", str(e))

    def save_worksheet_as(self):
        if self.worksheet is None:
            return
        default_name = getattr(self.worksheet, 'file_path', None) or "Untitled.mw"
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Worksheet", default_name,
            "Worksheet (*.mw);;JSON Worksheet (*.json);;All Files (*.*)"
        )
        if path:
            abs_path = os.path.abspath(path)
            self.worksheet.file_path = abs_path
            self.current_file_path = abs_path
            try:
                if abs_path.lower().endswith('.mw'):
                    data = self.worksheet.to_mw()
                else:
                    data = self.worksheet.to_json()
                with open(abs_path, "w", encoding="utf-8") as f:
                    f.write(data)
                base_name = os.path.basename(abs_path)
                self.tab_widget.setTabText(self.tab_widget.currentIndex(), base_name)
                self.setWindowTitle(f"{base_name} - [Server 3] - OpenMath")
                self._update_path_display()
                self._show_status(f"Saved to {abs_path}", 3000)
            except Exception as e:
                QMessageBox.critical(self, "Error Saving Worksheet", str(e))

    def _print_worksheet(self):
        self.export_pdf()

    def export_pdf(self):
        """Export the current worksheet as a PDF document."""
        if self.worksheet is None:
            QMessageBox.information(self, "Export as PDF", "Please create or open a document first.")
            return

        dlg = ExportPdfDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        if dlg.should_unfold_all():
            self.worksheet.expand_all_sections()
            QApplication.processEvents()

        default_name = "worksheet.pdf"
        target_path = getattr(self.worksheet, 'file_path', None) or self.current_file_path
        if target_path:
            base = os.path.splitext(os.path.basename(target_path))[0]
            default_name = f"{base}.pdf"

        path, _ = QFileDialog.getSaveFileName(
            self, "Export as PDF", default_name,
            "PDF Document (*.pdf);;All Files (*.*)"
        )
        if path:
            try:
                self.worksheet.export_to_pdf(path)
                self._show_status(f"Exported PDF to {path}", 3000)
            except Exception as e:
                QMessageBox.critical(self, "Export Error", str(e))

    def export_latex(self):
        if self.worksheet is None:
            QMessageBox.information(self, "Export", "Please create or open a document first.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export LaTeX", "worksheet.tex", "LaTeX Document (*.tex)")
        if path:
            try:
                tex = self.worksheet.export_to_latex_doc()
                with open(path, "w", encoding="utf-8") as f:
                    f.write(tex)
                self._show_status(f"Exported LaTeX to {path}", 3000)
            except Exception as e:
                QMessageBox.critical(self, "Export Error", str(e))

    def export_markdown(self):
        if self.worksheet is None:
            QMessageBox.information(self, "Export", "Please create or open a document first.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export Markdown", "worksheet.md", "Markdown Document (*.md)")
        if path:
            try:
                md = self.worksheet.export_to_markdown()
                with open(path, "w", encoding="utf-8") as f:
                    f.write(md)
                self._show_status(f"Exported Markdown to {path}", 3000)
            except Exception as e:
                QMessageBox.critical(self, "Export Error", str(e))

    def _show_status(self, msg: str, timeout_ms: int = 3000):
        self.lbl_status_msg.setText(msg)

    def _show_help_dialog(self):
        QMessageBox.information(
            self, "OpenMath Help",
            "Type '? command' to inspect help on any function (e.g. '? polygonOmråde', '? to_bin', '? diff').\n\n"
            "Key Features:\n"
            "• Enter: Evaluate group\n"
            "• F5: Toggle 1-D / 2-D Math mode\n"
            "• Esc / Ctrl+Space: Command Completion\n"
            "• Tab: Navigate template placeholders\n"
            "• Context Panel: Live algebraic, calculus, and embedded operations on the right"
        )

    def _show_about_dialog(self):
        dlg = AboutOpenMathDialog(self)
        dlg.exec()

    def changeEvent(self, event):
        if event.type() == QEvent.Type.ActivationChange:
            if self.isActiveWindow():
                if self.worksheet and not sip.isdeleted(self.worksheet) and self.worksheet.active_cell:
                    def _restore_focus():
                        try:
                            fw = QApplication.focusWidget()
                            if self.worksheet and not sip.isdeleted(self.worksheet) and self.worksheet.active_cell:
                                ac = self.worksheet.active_cell
                                if not sip.isdeleted(ac) and hasattr(ac, 'input_edit') and not sip.isdeleted(ac.input_edit):
                                    if not (fw and ac.isAncestorOf(fw)):
                                        ac.input_edit.setFocus()
                        except (RuntimeError, AttributeError, ReferenceError):
                            pass
                    QTimer.singleShot(20, _restore_focus)
        super().changeEvent(event)

    def _setup_settings_tracking(self):
        self._settings_timer = QTimer(self)
        self._settings_timer.setSingleShot(True)
        self._settings_timer.setInterval(250)
        self._settings_timer.timeout.connect(self.save_settings)

        self.palette_dock.visibilityChanged.connect(lambda v: self._settings_timer.start(100))
        self.context_dock.visibilityChanged.connect(lambda v: self._settings_timer.start(100))
        self.plot_dock.visibilityChanged.connect(lambda v: self._settings_timer.start(100))
        self.main_toolbar.visibilityChanged.connect(lambda v: self._settings_timer.start(100))
        self.tab_bar_toolbar.visibilityChanged.connect(lambda v: self._settings_timer.start(100))
        self.context_toolbar.visibilityChanged.connect(lambda v: self._settings_timer.start(100))

    def _is_component_visible(self, widget) -> bool:
        if widget is None:
            return False
        if self.isVisible():
            return widget.isVisible()
        return not widget.isHidden()

    def createPopupMenu(self):
        menu = super().createPopupMenu()
        if menu:
            menu.setStyleSheet(Theme.get_qss(self.theme_mode))
        return menu

    def save_settings(self):
        if getattr(self, '_loading_settings', False):
            return
        settings = QSettings("OpenMath", "OpenMath")
        if self.isVisible():
            settings.setValue("geometry", self.saveGeometry())
            settings.setValue("windowState", self.saveState())
        settings.setValue("context_dock_visible", self._is_component_visible(self.context_dock))
        settings.setValue("palette_dock_visible", self._is_component_visible(self.palette_dock))
        settings.setValue("plot_dock_visible", self._is_component_visible(self.plot_dock))
        settings.setValue("main_toolbar_visible", self._is_component_visible(self.main_toolbar))
        settings.setValue("tab_bar_toolbar_visible", self._is_component_visible(self.tab_bar_toolbar))
        settings.setValue("context_toolbar_visible", self._is_component_visible(self.context_toolbar))
        settings.setValue("theme_mode", self.theme_mode)
        from cas_engine.formatter import MathFormatter
        settings.setValue("decimal_separator", getattr(MathFormatter, 'decimal_separator', ','))
        if self._is_component_visible(self.palette_dock) and self.palette_dock.width() > 100:
            settings.setValue("palette_width", self.palette_dock.width())
        settings.sync()

    def load_settings(self):
        self._loading_settings = True
        try:
            settings = QSettings("OpenMath", "OpenMath")
            saved_theme = settings.value("theme_mode")
            if saved_theme in (Theme.LIGHT, Theme.DARK):
                self.set_theme(saved_theme, save=False)
            else:
                # First launch default: Light theme
                self.set_theme(Theme.LIGHT, save=False)

            saved_dec = settings.value("decimal_separator")
            if saved_dec in (",", "."):
                self._set_decimal_separator(saved_dec)
            else:
                self._set_decimal_separator(',')

            geom = settings.value("geometry")
            state = settings.value("windowState")
            if geom is not None:
                self.restoreGeometry(geom)
            if state is not None:
                self.restoreState(state)
                ctx_vis = settings.value("context_dock_visible")
                if ctx_vis is not None:
                    self.context_dock.setVisible(str(ctx_vis).lower() in ("true", "1"))
                else:
                    self.context_dock.setVisible(False)

                pal_vis = settings.value("palette_dock_visible")
                if pal_vis is not None:
                    self.palette_dock.setVisible(str(pal_vis).lower() in ("true", "1"))
                else:
                    self.palette_dock.setVisible(True)

                plot_vis = settings.value("plot_dock_visible")
                if plot_vis is not None:
                    self.plot_dock.setVisible(str(plot_vis).lower() in ("true", "1"))
                else:
                    self.plot_dock.setVisible(False)

                tb_main_vis = settings.value("main_toolbar_visible")
                if tb_main_vis is not None:
                    self.main_toolbar.setVisible(str(tb_main_vis).lower() in ("true", "1"))
                else:
                    self.main_toolbar.setVisible(True)

                tb_tabs_vis = settings.value("tab_bar_toolbar_visible")
                if tb_tabs_vis is not None:
                    self.tab_bar_toolbar.setVisible(str(tb_tabs_vis).lower() in ("true", "1"))
                else:
                    self.tab_bar_toolbar.setVisible(True)

                tb_ctx_vis = settings.value("context_toolbar_visible")
                if tb_ctx_vis is not None:
                    self.context_toolbar.setVisible(str(tb_ctx_vis).lower() in ("true", "1"))
                else:
                    self.context_toolbar.setVisible(True)

                if not self.palette_dock.isHidden():
                    saved_pw = settings.value("palette_width")
                    target_pw = 275
                    if saved_pw is not None:
                        try:
                            target_pw = max(270, int(saved_pw))
                        except Exception:
                            pass
                    self.resizeDocks([self.palette_dock], [target_pw], Qt.Orientation.Horizontal)
            else:
                # Default initial layout matching user preference (Screenshot 2026-09-13 at 03.29.38):
                # - Palettes Dock: Visible (True)
                # - Context Panel: Hidden (False)
                # - 2D Plotter Dock: Hidden (False)
                # - Main Toolbar: Visible (True)
                # - Document Tabs Toolbar: Visible (True)
                # - Context Bar Toolbar: Visible (True)
                self.palette_dock.setVisible(True)
                self.context_dock.setVisible(False)
                self.plot_dock.setVisible(False)
                self.main_toolbar.setVisible(True)
                self.tab_bar_toolbar.setVisible(True)
                self.context_toolbar.setVisible(True)
                self.resizeDocks([self.palette_dock], [275], Qt.Orientation.Horizontal)
        finally:
            self._loading_settings = False

    def showEvent(self, event):
        super().showEvent(event)
        if not getattr(self, '_initial_layout_applied', False):
            self._initial_layout_applied = True
            settings = QSettings("OpenMath", "OpenMath")
            saved_pw = settings.value("palette_width")
            if saved_pw is not None:
                try:
                    target_pw = max(270, int(saved_pw))
                    if self.palette_dock.isVisible():
                        self.resizeDocks([self.palette_dock], [target_pw], Qt.Orientation.Horizontal)
                except Exception:
                    pass
            elif self.palette_dock.isVisible():
                self.resizeDocks([self.palette_dock], [275], Qt.Orientation.Horizontal)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_add_tab_button_pos()
        if hasattr(self, '_settings_timer'):
            self._settings_timer.start(250)

    def closeEvent(self, event):
        if hasattr(self, '_memory_timer') and self._memory_timer.isActive():
            self._memory_timer.stop()
        self.save_settings()
        for i in range(self.doc_stack.count()):
            w = self.doc_stack.widget(i)
            if isinstance(w, WorksheetView) and hasattr(w, 'runner'):
                w.runner.shutdown()
        event.accept()

    def _show_options_dialog(self):
        from .options_dialog import OptionsDialog
        dlg = OptionsDialog(self)
        dlg.exec()

    def set_theme(self, mode: str, save: bool = True):
        if mode not in (Theme.LIGHT, Theme.DARK):
            return
        self.theme_mode = mode
        self._apply_theme()
        if hasattr(self, 'act_theme_light'):
            self.act_theme_light.setChecked(mode == Theme.LIGHT)
        if hasattr(self, 'act_theme_dark'):
            self.act_theme_dark.setChecked(mode == Theme.DARK)
        if save and not getattr(self, '_loading_settings', False):
            self.save_settings()

    def toggle_theme(self):
        new_mode = Theme.DARK if self.theme_mode == Theme.LIGHT else Theme.LIGHT
        self.set_theme(new_mode)

    def _update_main_toolbar_buttons_theme(self):
        is_dark = (self.theme_mode == Theme.DARK)
        if is_dark:
            btn_style = """
                QPushButton {
                    background-color: #1e2838;
                    color: #f8fafc;
                    border: 1px solid #2b384c;
                    border-radius: 3px;
                    padding: 2px 8px;
                    font-size: 11px;
                    font-weight: 500;
                }
                QPushButton:hover {
                    background-color: #263346;
                    color: #38bdf8;
                    border-color: #38bdf8;
                }
                QPushButton:pressed {
                    background-color: #141c28;
                }
            """
            exec_one_style = """
                QPushButton {
                    background-color: #064e3b;
                    color: #6ee7b7;
                    border: 1px solid #059669;
                    border-radius: 3px;
                    padding: 2px 8px;
                    font-size: 11px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #065f46;
                    border-color: #34d399;
                }
            """
            exec_all_style = """
                QPushButton {
                    background-color: #1e3a8a;
                    color: #93c5fd;
                    border: 1px solid #3b82f6;
                    border-radius: 3px;
                    padding: 2px 8px;
                    font-size: 11px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #1d4ed8;
                    border-color: #60a5fa;
                }
            """
            stop_style = """
                QPushButton {
                    background-color: #450a0a;
                    color: #fca5a5;
                    border: 1px solid #dc2626;
                    border-radius: 3px;
                    padding: 2px 8px;
                    font-size: 11px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #5c0f0f;
                    border-color: #ef4444;
                }
            """
            search_style = """
                QLineEdit {
                    background-color: #16202c;
                    color: #f8fafc;
                    border: 1px solid #2b384c;
                    border-radius: 4px;
                    padding: 2px 8px;
                    font-size: 11px;
                    selection-background-color: #0284c7;
                    selection-color: #ffffff;
                }
                QLineEdit:focus {
                    border: 1px solid #38bdf8;
                    background-color: #1a2433;
                }
            """
        else:
            btn_style = """
                QPushButton {
                    background-color: #f1f5f9;
                    color: #1e293b;
                    border: 1px solid #cbd5e1;
                    border-radius: 3px;
                    padding: 2px 8px;
                    font-size: 11px;
                    font-weight: 500;
                }
                QPushButton:hover {
                    background-color: #e2e8f0;
                    color: #0f172a;
                }
                QPushButton:pressed {
                    background-color: #cbd5e1;
                }
            """
            exec_one_style = """
                QPushButton {
                    background-color: #f0fdf4;
                    color: #15803d;
                    border: 1px solid #86efac;
                    border-radius: 3px;
                    padding: 2px 8px;
                    font-size: 11px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #dcfce7;
                    border-color: #4ade80;
                }
            """
            exec_all_style = """
                QPushButton {
                    background-color: #eff6ff;
                    color: #1d4ed8;
                    border: 1px solid #93c5fd;
                    border-radius: 3px;
                    padding: 2px 8px;
                    font-size: 11px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #dbeafe;
                    border-color: #60a5fa;
                }
            """
            stop_style = """
                QPushButton {
                    background-color: #fef2f2;
                    color: #b91c1c;
                    border: 1px solid #fca5a5;
                    border-radius: 3px;
                    padding: 2px 8px;
                    font-size: 11px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #fee2e2;
                    border-color: #f87171;
                }
            """
            search_style = """
                QLineEdit {
                    background-color: #ffffff;
                    color: #0f172a;
                    border: 1px solid #94a3b8;
                    border-radius: 4px;
                    padding: 2px 8px;
                    font-size: 11px;
                    selection-background-color: #2563eb;
                    selection-color: #ffffff;
                }
                QLineEdit:focus {
                    border: 1px solid #2563eb;
                    background-color: #ffffff;
                }
            """

        if hasattr(self, 'main_toolbar_buttons'):
            for b in self.main_toolbar_buttons:
                b.setStyleSheet(btn_style)
        if hasattr(self, 'btn_exec_one'):
            self.btn_exec_one.setStyleSheet(exec_one_style)
        if hasattr(self, 'btn_exec_all'):
            self.btn_exec_all.setStyleSheet(exec_all_style)
        if hasattr(self, 'btn_stop'):
            self.btn_stop.setStyleSheet(stop_style)
        if hasattr(self, 'toolbar_search_edit'):
            self.toolbar_search_edit.setStyleSheet(search_style)

    def _update_context_bar_theme(self):
        is_dark = (self.theme_mode == Theme.DARK)
        if is_dark:
            self.STYLE_MODE_SELECTED = "font-weight: bold; background-color: #1e3a5f; color: #38bdf8; border: 1px solid #38bdf8; border-radius: 2px; padding: 2px 8px; font-size: 11px;"
            self.STYLE_MODE_UNSELECTED = "background-color: #1e2838; color: #cbd5e1; border: 1px solid #2b384c; border-radius: 2px; padding: 2px 8px; font-size: 11px;"
            btn_style = """
                QPushButton {
                    background-color: #1e2838;
                    border: 1px solid #2b384c;
                    border-radius: 3px;
                    padding: 0px;
                }
                QPushButton:hover {
                    background-color: #263346;
                    border-color: #38bdf8;
                }
                QPushButton:pressed {
                    background-color: #141c28;
                }
            """
            tool_btn_style = """
                QToolButton {
                    background-color: #1e2838;
                    border: 1px solid #2b384c;
                    border-radius: 3px;
                    padding: 0px;
                }
                QToolButton:hover {
                    background-color: #263346;
                    border-color: #38bdf8;
                }
                QToolButton:pressed {
                    background-color: #141c28;
                }
                QToolButton::menu-indicator, QToolButton::menu-arrow {
                    image: none;
                    width: 0px;
                    height: 0px;
                }
                QToolButton::menu-button {
                    width: 0px;
                    border: none;
                }
            """
            section_style = """
                QToolButton {
                    background-color: #1e2838;
                    border: 1px solid #2b384c;
                    border-radius: 3px;
                    padding: 0px;
                }
                QToolButton:hover {
                    background-color: #263346;
                    border-color: #38bdf8;
                }
                QToolButton:pressed {
                    background-color: #141c28;
                }
                QToolButton::menu-button {
                    width: 10px;
                    border-left: 1px solid #2b384c;
                }
            """
            combo_style = """
                QComboBox {
                    background-color: #1e2838;
                    color: #f8fafc;
                    border: 1px solid #2b384c;
                    border-radius: 3px;
                    padding: 2px 6px;
                    font-size: 11px;
                }
                QComboBox:hover {
                    border-color: #38bdf8;
                }
                QComboBox::drop-down {
                    border: none;
                    width: 14px;
                }
                QComboBox QAbstractItemView {
                    background-color: #1a2332;
                    color: #f8fafc;
                    selection-background-color: #0284c7;
                    selection-color: #ffffff;
                    border: 1px solid #2b384c;
                }
            """
            icon_col = "#e2e8f0"
        else:
            self.STYLE_MODE_SELECTED = "font-weight: bold; background-color: #e0f2fe; color: #0369a1; border: 1px solid #38bdf8; border-radius: 2px; padding: 2px 8px; font-size: 11px;"
            self.STYLE_MODE_UNSELECTED = "background-color: #f8fafc; color: #374151; border: 1px solid #cbd5e1; border-radius: 2px; padding: 2px 8px; font-size: 11px;"
            btn_style = """
                QPushButton {
                    background-color: #ffffff;
                    border: 1px solid #cbd5e1;
                    border-radius: 3px;
                    padding: 0px;
                }
                QPushButton:hover {
                    background-color: #f1f5f9;
                    border-color: #94a3b8;
                }
                QPushButton:pressed {
                    background-color: #e2e8f0;
                }
            """
            tool_btn_style = """
                QToolButton {
                    background-color: #ffffff;
                    border: 1px solid #cbd5e1;
                    border-radius: 3px;
                    padding: 0px;
                }
                QToolButton:hover {
                    background-color: #f1f5f9;
                    border-color: #94a3b8;
                }
                QToolButton:pressed {
                    background-color: #e2e8f0;
                }
                QToolButton::menu-indicator, QToolButton::menu-arrow {
                    image: none;
                    width: 0px;
                    height: 0px;
                }
                QToolButton::menu-button {
                    width: 0px;
                    border: none;
                }
            """
            section_style = """
                QToolButton {
                    background-color: #ffffff;
                    border: 1px solid #cbd5e1;
                    border-radius: 3px;
                    padding: 0px;
                }
                QToolButton:hover {
                    background-color: #f1f5f9;
                    border-color: #94a3b8;
                }
                QToolButton:pressed {
                    background-color: #e2e8f0;
                }
                QToolButton::menu-button {
                    width: 10px;
                    border-left: 1px solid #e2e8f0;
                }
            """
            combo_style = """
                QComboBox {
                    background-color: #ffffff;
                    color: #0f172a;
                    border: 1px solid #cbd5e1;
                    border-radius: 3px;
                    padding: 2px 6px;
                    font-size: 11px;
                }
                QComboBox:hover {
                    border-color: #94a3b8;
                }
                QComboBox::drop-down {
                    border: none;
                    width: 14px;
                }
                QComboBox QAbstractItemView {
                    background-color: #ffffff;
                    color: #0f172a;
                    selection-background-color: #2563eb;
                    selection-color: #ffffff;
                    border: 1px solid #cbd5e1;
                }
            """
            icon_col = "#0f172a"

        if hasattr(self, 'format_btn_map'):
            for k, (name, btn) in self.format_btn_map.items():
                btn.setIcon(create_toolbar_action_icon(name, icon_col))
                btn.setStyleSheet(btn_style)

        if hasattr(self, 'combo_font'):
            self.combo_font.setStyleSheet(combo_style)
        if hasattr(self, 'combo_font_size'):
            self.combo_font_size.setStyleSheet(combo_style)
        if hasattr(self, 'btn_line_spacing'):
            self.btn_line_spacing.setIcon(create_toolbar_action_icon("line_spacing", icon_col))
            self.btn_line_spacing.setStyleSheet(tool_btn_style)
        if hasattr(self, 'btn_section'):
            self.btn_section.setIcon(create_toolbar_action_icon("section", icon_col))
            self.btn_section.setStyleSheet(section_style)
        if hasattr(self, 'btn_text_color'):
            self.btn_text_color.update_theme(self.theme_mode)
        if hasattr(self, 'btn_highlight'):
            self.btn_highlight.update_theme(self.theme_mode)

        mode = "2d_math"
        if hasattr(self, 'worksheet') and self.worksheet and getattr(self.worksheet, 'active_cell', None):
            mode = getattr(self.worksheet.active_cell, 'input_mode', '2d_math')
        self._update_mode_buttons(mode)

    def _apply_theme(self):
        qss = Theme.get_qss(self.theme_mode)
        self.setStyleSheet(qss)
        app = QApplication.instance()
        if app:
            app.setStyleSheet(qss)
            app.setPalette(Theme.get_app_palette(self.theme_mode))

        is_dark = (self.theme_mode == Theme.DARK)

        # Update main and context toolbars
        if hasattr(self, 'main_toolbar'):
            if is_dark:
                self.main_toolbar.setStyleSheet("QToolBar { background-color: #1a2332; border-bottom: 1px solid #2b384c; spacing: 4px; padding: 2px 6px; }")
            else:
                self.main_toolbar.setStyleSheet("QToolBar { background-color: #f8fafc; border-bottom: 1px solid #e2e8f0; spacing: 4px; padding: 2px 6px; }")
        if hasattr(self, 'context_toolbar'):
            if is_dark:
                self.context_toolbar.setStyleSheet("QToolBar { background-color: #1a2332; border-bottom: 1px solid #2b384c; spacing: 4px; padding: 2px 6px; }")
            else:
                self.context_toolbar.setStyleSheet("QToolBar { background-color: #f8fafc; border-bottom: 1px solid #e2e8f0; spacing: 4px; padding: 2px 6px; }")
        if hasattr(self, 'context_container'):
            self.context_container.setStyleSheet("background-color: transparent;")

        # Update tab bar toolbar & tabs
        if hasattr(self, 'tab_bar_toolbar'):
            if is_dark:
                self.tab_bar_toolbar.setStyleSheet("QToolBar { background-color: #141b26; border-bottom: 1px solid #2b384c; }")
            else:
                self.tab_bar_toolbar.setStyleSheet("QToolBar { background-color: #e2e4e8; border-bottom: 1px solid #cbd5e1; }")
        if hasattr(self, 'tab_bar_container'):
            if is_dark:
                self.tab_bar_container.setStyleSheet("background-color: #141b26; border-bottom: 1px solid #2b384c;")
            else:
                self.tab_bar_container.setStyleSheet("background-color: #e2e4e8;")
        if hasattr(self, 'tab_widget'):
            if is_dark:
                self.tab_widget.setStyleSheet("""
                    QTabWidget { background-color: transparent; border: none; }
                    QTabBar { background-color: transparent; border: none; }
                    QTabWidget::pane { border: none; background: transparent; }
                    QTabBar::tab {
                        background: #141b26;
                        color: #94a3b8;
                        border: 1px solid #2b384c;
                        border-bottom: none;
                        min-width: 130px;
                        padding: 4px 26px 4px 14px;
                        font-size: 11px;
                        margin-right: 2px;
                    }
                    QTabBar::tab:selected {
                        background: #1e2838;
                        color: #f8fafc;
                        font-weight: bold;
                        border-top: 2px solid #38bdf8;
                    }
                    QTabBar::tab:hover:!selected {
                        background: #1a2332;
                        color: #cbd5e1;
                    }
                """)
            else:
                self.tab_widget.setStyleSheet("""
                    QTabWidget { background-color: transparent; border: none; }
                    QTabBar { background-color: transparent; border: none; }
                    QTabWidget::pane { border: none; background: transparent; }
                    QTabBar::tab {
                        background: #e2e4e8;
                        color: #374151;
                        border: 1px solid #b8bcc2;
                        border-bottom: none;
                        min-width: 130px;
                        padding: 4px 26px 4px 14px;
                        font-size: 11px;
                        margin-right: 2px;
                    }
                    QTabBar::tab:selected {
                        background: #ffffff;
                        color: #111827;
                        font-weight: bold;
                        border-top: 2px solid #2563eb;
                    }
                    QTabBar::tab:hover:!selected {
                        background: #edf0f5;
                    }
                """)

        self._update_main_toolbar_buttons_theme()
        self._update_context_bar_theme()

        # Update status bar
        if hasattr(self, 'lbl_mode'):
            self.lbl_mode.setStyleSheet("font-weight: bold; color: #38bdf8;" if is_dark else "font-weight: bold; color: #1e3a8a;")
        self.statusBar().setStyleSheet("QStatusBar { background-color: #141b26; border-top: 1px solid #2b384c; color: #cbd5e1; }" if is_dark else "")
        self._update_editable_ui()

        # Update worksheets & StartPage
        for i in range(self.doc_stack.count()):
            w = self.doc_stack.widget(i)
            if isinstance(w, WorksheetView):
                w.set_theme_mode(self.theme_mode)
            elif hasattr(w, 'set_theme_mode'):
                w.set_theme_mode(self.theme_mode)

        # Update panels
        if hasattr(self, 'palette_panel') and self.palette_panel:
            self.palette_panel.set_theme_mode(self.theme_mode)
        if hasattr(self, 'context_panel') and self.context_panel:
            self.context_panel.set_theme_mode(self.theme_mode)
        if hasattr(self, 'plot_panel') and self.plot_panel:
            self.plot_panel.set_theme_mode(self.theme_mode)

        # Redraw custom tab buttons
        if hasattr(self, 'tab_bar') and self.tab_bar:
            self.tab_bar.update()
        if hasattr(self, 'btn_add_tab') and self.btn_add_tab:
            self.btn_add_tab.update()
        if hasattr(self, 'btn_tab_overflow') and self.btn_tab_overflow:
            self.btn_tab_overflow.update()
        self._update_tab_bar_layout()
