"""
OpenMath Palette Sidebar Panel.
Reproduces the authentic palette dock layout:
- Top tabs: Palettes / Formulas / Variables
- Collapsible accordion sections: Favorites, Expression, Calculus, Common Symbols, Greek, Matrices, Embedded Systems, Units, Plots
- Expression 2D math templates with placeholders
- Common Symbols grid (Greek, sets, logic, arithmetic)
- Embedded systems engineering calculators and bitwise wizards
"""

import json
import time
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QPushButton, QScrollArea, QFrame, QToolButton, QTabWidget,
    QSizePolicy, QLineEdit, QMenu, QMessageBox, QApplication
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QTimer, QPoint, QPointF, QSettings, QMimeData
from PyQt6.QtGui import QFont, QIcon, QAction, QDrag, QPixmap, QPainter, QColor, QBrush

from .matrix_dialog import MatrixDialog
from .math_renderer import MathRendererWidget
from .theme import Theme
from .variables_panel import VariableManagerWidget
from cas_engine import CASEngine


class PaletteHeaderButton(QPushButton):
    """Collapsible accordion header with arrow icon (▼ / ▶) and hold/drag-to-reorder support."""
    dragStarted = pyqtSignal(str)

    def __init__(self, title: str, parent=None, theme_mode: str = "light"):
        super().__init__(parent)
        self.title_text = title
        self.theme_mode = theme_mode
        self.is_expanded = True
        self.setFixedHeight(24)
        self.setCheckable(True)
        self.setChecked(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(f"{title}\nClick to toggle • Hold and drag to reorder")

        self._drag_start_pos = None
        self._is_dragging = False
        self._hold_active = False

        self._hold_timer = QTimer(self)
        self._hold_timer.setSingleShot(True)
        self._hold_timer.timeout.connect(self._on_hold_timeout)

        self._update_text()
        self._apply_style()

    def _apply_style(self):
        if self.theme_mode == "light":
            bg = "#e6e8ec"
            fg = "#2b2f38"
            border = "#c8ccd2"
            hover = "#dbe0e8"
        else:
            bg = "#1c2433"
            fg = "#f8fafc"
            border = "#2b384c"
            hover = "#233348"

        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg};
                color: {fg};
                border: 1px solid {border};
                border-radius: 2px;
                text-align: left;
                padding-left: 6px;
                padding-right: 6px;
                font-size: 11px;
                font-family: "Segoe UI", -apple-system, Arial, sans-serif;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {hover};
            }}
        """)

    def set_dragging_style(self, is_dragging: bool):
        if is_dragging:
            self.setStyleSheet("""
                QPushButton {
                    background-color: #dbeafe;
                    color: #1d4ed8;
                    border: 1px dashed #3b82f6;
                    border-radius: 2px;
                    text-align: left;
                    padding-left: 6px;
                    font-size: 11px;
                    font-family: "Segoe UI", -apple-system, Arial, sans-serif;
                    font-weight: bold;
                }
            """)
        else:
            self._apply_style()

    def _update_text(self):
        arrow = "▼ " if self.is_expanded else "▶ "
        display_title = self.title_text.replace("&", "&&") if "&&" not in self.title_text else self.title_text
        self.setText(arrow + display_title)

    def set_expanded(self, expanded: bool):
        self.is_expanded = expanded
        self.setChecked(expanded)
        self._update_text()

    def _on_toggle(self):
        self.is_expanded = not self.is_expanded
        self._update_text()

    def _on_hold_timeout(self):
        if self._drag_start_pos is not None:
            self._hold_active = True
            self.dragStarted.emit(self.title_text)
            self.set_dragging_style(True)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_pos = event.pos()
            self._is_dragging = False
            self._hold_active = False
            self._hold_timer.start(250)
            event.accept()
            return
        elif event.button() == Qt.MouseButton.RightButton:
            self._show_header_context_menu(event.pos())
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_start_pos is not None and (event.buttons() & Qt.MouseButton.LeftButton):
            dist = (event.pos() - self._drag_start_pos).manhattanLength()
            if dist >= 4 or self._hold_active:
                if not self._is_dragging:
                    self._hold_timer.stop()
                    self._is_dragging = True
                    self._start_drag()
                    return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._hold_timer.stop()
        if event.button() == Qt.MouseButton.LeftButton:
            if not self._is_dragging and not self._hold_active and self._drag_start_pos is not None:
                self._on_toggle()
                self.clicked.emit()
            elif self._hold_active and not self._is_dragging:
                panel = self._find_palette_panel()
                if panel:
                    panel.on_section_drag_ended()
            self._drag_start_pos = None
            self._is_dragging = False
            self._hold_active = False
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def _start_drag(self):
        if not self._hold_active:
            self.dragStarted.emit(self.title_text)
            self.set_dragging_style(True)

        drag = QDrag(self)
        mime_data = QMimeData()
        mime_data.setData("application/x-openmath-palette-section", self.title_text.encode("utf-8"))
        drag.setMimeData(mime_data)

        pixmap = self.grab()
        drag_pixmap = QPixmap(pixmap.size())
        drag_pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(drag_pixmap)
        painter.setOpacity(0.85)
        painter.drawPixmap(0, 0, pixmap)
        painter.setPen(QColor("#2563eb"))
        painter.drawRect(0, 0, pixmap.width() - 1, pixmap.height() - 1)
        painter.end()

        drag.setPixmap(drag_pixmap)
        drag.setHotSpot(QPoint(min(30, pixmap.width() // 2), pixmap.height() // 2))

        drag.exec(Qt.DropAction.MoveAction)

        panel = self._find_palette_panel()
        if panel:
            panel.on_section_drag_ended()

    def _find_palette_panel(self):
        curr = self.parent()
        while curr is not None:
            if isinstance(curr, PalettePanel):
                return curr
            curr = curr.parent()
        return None

    def _show_header_context_menu(self, pos: QPoint):
        panel = self._find_palette_panel()
        if not panel:
            return

        menu = QMenu(self)
        Theme.apply_menu_style(menu, self.theme_mode)

        title = self.title_text
        curr_idx = panel.section_order.index(title) if hasattr(panel, "section_order") and title in panel.section_order else -1

        toggle_act = QAction("Collapse Section" if self.is_expanded else "Expand Section", menu)
        toggle_act.triggered.connect(self._on_toggle)
        menu.addAction(toggle_act)

        menu.addSeparator()

        move_up = QAction("Move Up", menu)
        move_up.setEnabled(curr_idx > 0)
        move_up.triggered.connect(lambda: panel.move_section(title, -1))
        menu.addAction(move_up)

        move_down = QAction("Move Down", menu)
        move_down.setEnabled(curr_idx >= 0 and curr_idx < len(panel.section_order) - 1)
        move_down.triggered.connect(lambda: panel.move_section(title, 1))
        menu.addAction(move_down)

        menu.addSeparator()

        collapse_all = QAction("Collapse All Sections", menu)
        collapse_all.triggered.connect(panel.collapse_all_sections)
        menu.addAction(collapse_all)

        expand_all = QAction("Expand All Sections", menu)
        expand_all.triggered.connect(panel.expand_all_sections)
        menu.addAction(expand_all)

        menu.addSeparator()

        reset_order = QAction("Reset Section Order", menu)
        reset_order.triggered.connect(panel.reset_section_order)
        menu.addAction(reset_order)

        menu.exec(self.mapToGlobal(pos))


class AccordionSection(QWidget):
    """Section within the Palette containing a header and content widget."""
    def __init__(self, title: str, content_widget: QWidget, start_expanded: bool = True, parent=None, theme_mode: str = "light"):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(1)

        self.header = PaletteHeaderButton(title, self, theme_mode=theme_mode)
        self.header.is_expanded = start_expanded
        self.header._update_text()
        layout.addWidget(self.header)

        self.content = content_widget
        self.content.setVisible(start_expanded)
        layout.addWidget(self.content)

        self.header.clicked.connect(lambda: self.content.setVisible(self.header.is_expanded))

    def set_expanded(self, expanded: bool):
        self.header.set_expanded(expanded)
        self.content.setVisible(expanded)


class DropIndicator(QWidget):
    """Visual line indicator showing where a dragged section will be inserted."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(8)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        is_dark = getattr(getattr(self.parent(), 'panel', None), 'theme_mode', 'light') == "dark"
        line_color = QColor("#38bdf8" if is_dark else "#2563eb")
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(line_color))

        w = self.width()
        h = self.height()
        line_h = 3
        y = (h - line_h) // 2

        # Draw vibrant blue insertion bar with circular endpoints
        painter.drawRoundedRect(6, y, max(4, w - 12), line_h, 1.5, 1.5)
        r = 3.5
        painter.drawEllipse(QPointF(6, y + line_h / 2), r, r)
        painter.drawEllipse(QPointF(w - 6, y + line_h / 2), r, r)


class PaletteContainerWidget(QWidget):
    """Container widget holding accordion sections with drag-and-drop reordering support."""
    def __init__(self, panel, parent=None):
        super().__init__(parent)
        self.panel = panel
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat("application/x-openmath-palette-section"):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat("application/x-openmath-palette-section"):
            pos = event.position().toPoint()
            self.panel.update_drag_indicator(pos)
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self.panel.hide_drag_indicator()
        event.accept()

    def dropEvent(self, event):
        if event.mimeData().hasFormat("application/x-openmath-palette-section"):
            data = event.mimeData().data("application/x-openmath-palette-section").data().decode("utf-8")
            pos = event.position().toPoint()
            self.panel.handle_section_drop(data, pos)
            event.acceptProposedAction()
        else:
            event.ignore()


class PaletteItemButton(QPushButton):
    """Button representing a palette symbol or template with right-click context menu support."""
    rightClicked = pyqtSignal(QPoint)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._last_right_click_time = 0.0
        self.item_data = None

    def update_theme(self, mode: str):
        is_dark = (mode == Theme.DARK)
        bg = "#202b3a" if is_dark else "#ffffff"
        fg = "#f8fafc" if is_dark else "#0f172a"
        border = "#2e3b4f" if is_dark else "#d1d5db"
        hover_bg = "#2a384c" if is_dark else "#f0f7ff"
        hover_border = "#38bdf8" if is_dark else "#3b82f6"
        hover_fg = "#38bdf8" if is_dark else "#1d4ed8"
        pressed_bg = "#1b2533" if is_dark else "#dbeafe"

        font_family = "Times New Roman"
        if getattr(self, 'item_data', None) and isinstance(self.item_data, dict):
            font_family = self.item_data.get('font_family', font_family)

        self.setStyleSheet(f"""
            QPushButton, PaletteItemButton {{
                background-color: {bg};
                color: {fg};
                border: 1px solid {border};
                border-radius: 3px;
                font-family: "{font_family}", serif;
                font-size: 12px;
                padding: 2px;
            }}
            QPushButton:hover, PaletteItemButton:hover {{
                background-color: {hover_bg};
                border-color: {hover_border};
                color: {hover_fg};
            }}
            QPushButton:pressed, PaletteItemButton:pressed {{
                background-color: {pressed_bg};
            }}
        """)

        # If math icon, re-render pixmap with theme math color
        if getattr(self, 'item_data', None) and isinstance(self.item_data, dict) and self.item_data.get("kind") == "math":
            ltx = self.item_data.get("latex")
            if ltx:
                from PyQt6.QtWidgets import QApplication
                screen = QApplication.primaryScreen()
                screen_dpr = float(screen.devicePixelRatio()) if screen else 1.0
                dpr = max(2.0, screen_dpr)
                math_color = "#f8fafc" if is_dark else "#0f172a"
                pixmap = MathRendererWidget.render_latex_to_pixmap(
                    ltx,
                    font_size=18,
                    theme_mode=mode,
                    dpi_scale=dpr * 1.5,
                    color=math_color
                )
                if pixmap and not pixmap.isNull():
                    max_icon_h = self.item_data.get("max_icon_h", 24)
                    max_icon_w = self.item_data.get("max_icon_w", 180)
                    target_ph = int(max_icon_h * dpr)
                    target_pw = int(max_icon_w * dpr)
                    if pixmap.height() > target_ph or pixmap.width() > target_pw:
                        pixmap = pixmap.scaled(
                            target_pw, target_ph,
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation
                        )
                    pixmap.setDevicePixelRatio(dpr)
                    self.setIcon(QIcon(pixmap))
                    logical_w = max(1, int(pixmap.width() / dpr))
                    logical_h = max(1, int(pixmap.height() / dpr))
                    self.setIconSize(QSize(logical_w, logical_h))

    def mousePressEvent(self, event):
        is_right = (event.button() == Qt.MouseButton.RightButton) or (
            event.button() == Qt.MouseButton.LeftButton and bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
        )
        if is_right:
            self._last_right_click_time = time.time()
            self.rightClicked.emit(event.pos())
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if time.time() - getattr(self, "_last_right_click_time", 0.0) < 0.3:
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event):
        now = time.time()
        if now - getattr(self, "_last_right_click_time", 0.0) < 0.3:
            event.accept()
            return
        self._last_right_click_time = now
        self.rightClicked.emit(event.pos())
        event.accept()


class FormulaCard(QFrame):
    """Clickable card for a formula template with title, code badge, description, and click-to-insert."""
    clicked = pyqtSignal(str)
    rightClicked = pyqtSignal(QPoint)

    def __init__(self, title: str, formula: str, desc: str = "", theme_mode: str = "light", parent=None):
        super().__init__(parent)
        self.title = title
        self.formula = formula
        self.desc = desc
        self.theme_mode = theme_mode
        self._last_right_click_time = 0.0
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFrameShape(QFrame.Shape.StyledPanel)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(7, 6, 7, 6)
        layout.setSpacing(3)

        # Header: Title + "+ Insert" badge
        h_box = QHBoxLayout()
        h_box.setContentsMargins(0, 0, 0, 0)
        h_box.setSpacing(4)

        self.title_lbl = QLabel(title)
        h_box.addWidget(self.title_lbl)
        h_box.addStretch()

        self.badge = QLabel("+ Insert")
        h_box.addWidget(self.badge)
        layout.addLayout(h_box)

        # Formula code badge
        disp_formula = formula
        try:
            from .worksheet_cell import format_subscripts_and_superscripts
            disp_formula = format_subscripts_and_superscripts(formula)
        except Exception:
            pass
        self.code_lbl = QLabel(disp_formula)
        self.code_lbl.setWordWrap(True)
        layout.addWidget(self.code_lbl)

        # Description
        if desc:
            self.desc_lbl = QLabel(desc)
            self.desc_lbl.setWordWrap(True)
            layout.addWidget(self.desc_lbl)

        self.set_theme_mode(theme_mode)

    def set_theme_mode(self, mode: str):
        self.theme_mode = mode
        is_dark = (mode == Theme.DARK)
        self.title_lbl.setStyleSheet(f"""
            font-weight: 600;
            font-size: 11px;
            color: {"#f8fafc" if is_dark else "#1e293b"};
        """)
        self.badge.setStyleSheet(f"""
            color: {"#38bdf8" if is_dark else "#2563eb"};
            font-size: 10px;
            font-weight: 600;
        """)
        self.code_lbl.setStyleSheet(f"""
            background-color: {"#18202e" if is_dark else "#f8fafc"};
            color: {"#7dd3fc" if is_dark else "#0f172a"};
            border: 1px solid {"#2b384c" if is_dark else "#cbd5e1"};
            border-radius: 4px;
            padding: 2px 5px;
            font-family: "SF Mono", "Menlo", "Consolas", monospace;
            font-size: 10.5px;
        """)
        if hasattr(self, 'desc_lbl'):
            self.desc_lbl.setStyleSheet(f"""
                color: {"#94a3b8" if is_dark else "#64748b"};
                font-size: 9.5px;
            """)
        self.setStyleSheet(f"""
            FormulaCard {{
                background-color: {"#1c2433" if is_dark else "#ffffff"};
                border: 1px solid {"#2b384c" if is_dark else "#e2e8f0"};
                border-radius: 6px;
            }}
            FormulaCard:hover {{
                background-color: {"#233348" if is_dark else "#f0f7ff"};
                border-color: {"#38bdf8" if is_dark else "#93c5fd"};
            }}
        """)

    def mousePressEvent(self, event):
        is_right = (event.button() == Qt.MouseButton.RightButton) or (
            event.button() == Qt.MouseButton.LeftButton and bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
        )
        if is_right:
            self._last_right_click_time = time.time()
            self.rightClicked.emit(event.pos())
            event.accept()
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.formula)
            self.badge.setText("✓ Inserted!")
            self.badge.setStyleSheet("color: #16a34a; font-size: 10px; font-weight: bold;")
            QTimer.singleShot(1200, self._reset_badge)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if time.time() - getattr(self, "_last_right_click_time", 0.0) < 0.3:
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event):
        now = time.time()
        if now - getattr(self, "_last_right_click_time", 0.0) < 0.3:
            event.accept()
            return
        self._last_right_click_time = now
        self.rightClicked.emit(event.pos())
        event.accept()

    def get_item_data(self) -> dict:
        return {
            "kind": "text",
            "label": self.title,
            "template": self.formula,
            "tooltip": f"{self.title}: {self.desc}" if self.desc else self.title,
            "font_family": "Segoe UI",
            "height": 28,
            "is_wide": True,
        }

    def _reset_badge(self):
        self.badge.setText("+ Insert")
        self.badge.setStyleSheet(f"""
            color: {"#2563eb" if self.theme_mode == Theme.LIGHT else "#60a5fa"};
            font-size: 10px;
            font-weight: 600;
        """)

    def matches_query(self, query: str) -> bool:
        q = query.lower()
        return (q in self.title.lower() or
                q in self.formula.lower() or
                q in self.desc.lower())


DEFAULT_FAVORITES = [
    {
        "kind": "math",
        "latex": r"\frac{a}{b}",
        "template": r"\frac{a}{b}",
        "tooltip": "Fraction (a / b)",
        "fallback": "a / b",
        "height": 34,
        "max_icon_h": 26,
        "max_icon_w": 58,
        "is_wide": False,
        "font_family": "Times New Roman",
    },
    {
        "kind": "math",
        "latex": r"\sqrt{a}",
        "template": "√(a)",
        "tooltip": "Square root (√a)",
        "fallback": "√a",
        "height": 34,
        "max_icon_h": 26,
        "max_icon_w": 58,
        "is_wide": False,
        "font_family": "Times New Roman",
    },
    {
        "kind": "math",
        "latex": r"\frac{d}{dx}f",
        "template": r"\frac{d}{dx}f",
        "tooltip": "Derivative template d/dx f",
        "fallback": "d/dx f",
        "height": 34,
        "max_icon_h": 26,
        "max_icon_w": 58,
        "is_wide": False,
        "font_family": "Times New Roman",
    },
    {
        "kind": "math",
        "latex": r"\int f\,dx",
        "template": "∫(f) dx",
        "tooltip": "Indefinite integral ∫ f dx",
        "fallback": "∫ f dx",
        "height": 34,
        "max_icon_h": 26,
        "max_icon_w": 58,
        "is_wide": False,
        "font_family": "Times New Roman",
    },
    {
        "kind": "text",
        "label": "to_bin(0x5A, 8)",
        "template": "to_bin(0x5A, 8)",
        "tooltip": "Format integer as 8-bit binary nibbles",
        "font_family": "Segoe UI",
        "height": 26,
        "is_wide": True,
    },
    {
        "kind": "text",
        "label": "polygonOmråde",
        "template": "polygonOmråde(Uligheder, x = -1 .. 13, y = -1 .. 12)",
        "tooltip": "Feasible polygon region",
        "font_family": "Segoe UI",
        "height": 26,
        "is_wide": True,
    },
]

DEFAULT_SECTION_ORDER = [
    "Favorites",
    "Expression",
    "Embedded Systems",
    "Units",
    "Calculus",
    "Common Symbols",
    "Greek",
    "Matrices & Vectors",
]


class PalettePanel(QWidget):
    """
    OpenMath Mathematical Palette Sidebar.
    """
    insertTemplate = pyqtSignal(str)
    openMatrixDialog = pyqtSignal()

    def __init__(self, parent=None, theme_mode: str = "light", engine: CASEngine = None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._theme_mode = theme_mode
        self.engine = engine
        self.var_manager = None
        self.fav_section = None
        self.fav_content_widget = None
        self.fav_layout = None
        self.palettes_scroll = None
        self.favorite_items = self._load_favorites()
        self.sections = {}
        self.section_order = self._load_section_order()
        self._is_dragging_section = False
        self._dragged_section_title = None
        self._pre_drag_expanded = {}
        self.drop_indicator = None
        self.palette_container = None
        self.container_layout = None
        self.setMinimumWidth(250)
        self.setStyleSheet("background-color: #f7f8fa;")
        self._init_ui()

    @property
    def theme_mode(self) -> str:
        return self._theme_mode

    def set_theme_mode(self, value: str):
        self.theme_mode = value

    @theme_mode.setter
    def theme_mode(self, value: str):
        self._theme_mode = value
        is_dark = (value == Theme.DARK)
        panel_bg = "#161e2a" if is_dark else "#f7f8fa"
        self.setStyleSheet(f"background-color: {panel_bg};")
        if hasattr(self, "palettes_scroll") and self.palettes_scroll:
            self.palettes_scroll.setStyleSheet(f"background-color: {panel_bg};")
        if hasattr(self, "palette_container") and self.palette_container:
            self.palette_container.setStyleSheet(f"background-color: {panel_bg};")
        if hasattr(self, "tabs") and self.tabs:
            tab_bg = "#161e2a" if is_dark else "#e2e5e9"
            tab_active_bg = "#1e2838" if is_dark else "#ffffff"
            tab_active_fg = "#f8fafc" if is_dark else "#0f172a"
            tab_fg = "#94a3b8" if is_dark else "#334155"
            border = "#2b384c" if is_dark else "#c8ccd2"
            self.tabs.setStyleSheet(f"""
                QTabWidget {{ background-color: {tab_bg}; }}
                QTabBar {{ background-color: {tab_bg}; }}
                QTabWidget::pane {{ border: 1px solid {border}; background-color: {panel_bg}; }}
                QTabBar::tab {{
                    background: {tab_bg};
                    color: {tab_fg};
                    border: 1px solid {border};
                    padding: 4px 8px;
                    font-size: 11px;
                    margin-right: 1px;
                    min-width: 60px;
                }}
                QTabBar::tab:selected {{
                    background: {tab_active_bg};
                    color: {tab_active_fg};
                    border-bottom: 1px solid {tab_active_bg};
                    font-weight: bold;
                }}
                QTabBar::tab:hover:!selected {{
                    background: {'#1f2a3a' if is_dark else '#edf0f5'};
                }}
            """)
        if hasattr(self, "fav_layout") and self.fav_layout is not None:
            self._refresh_favorites_ui()
        for sec in getattr(self, "sections", {}).values():
            if hasattr(sec, "header"):
                sec.header.theme_mode = value
                sec.header._apply_style()
        # Update all PaletteItemButton in palette_container
        if hasattr(self, "palette_container") and self.palette_container:
            for btn in self.palette_container.findChildren(PaletteItemButton):
                if hasattr(btn, 'update_theme'):
                    btn.update_theme(value)
        # Update formulas tab
        if hasattr(self, "tabs"):
            for card in self.tabs.findChildren(FormulaCard):
                if hasattr(card, 'set_theme_mode'):
                    card.set_theme_mode(value)
            for le in self.tabs.findChildren(QLineEdit):
                input_bg = "#18202e" if is_dark else "#ffffff"
                input_fg = "#f8fafc" if is_dark else "#1e293b"
                border_col = "#2b384c" if is_dark else "#cbd5e1"
                focus_border = "#38bdf8" if is_dark else "#2563eb"
                le.setStyleSheet(f"""
                    QLineEdit {{
                        background-color: {input_bg};
                        color: {input_fg};
                        border: 1px solid {border_col};
                        border-radius: 5px;
                        padding: 5px 8px;
                        font-size: 11px;
                    }}
                    QLineEdit:focus {{
                        border: 1.5px solid {focus_border};
                    }}
                """)
        # Update variable manager
        if getattr(self, "var_manager", None) and hasattr(self.var_manager, "set_theme_mode"):
            self.var_manager.set_theme_mode(value)

    def _load_section_order(self) -> list:
        try:
            settings = QSettings("OpenMath", "OpenMath")
            raw = settings.value("palette_section_order", None)
            if raw is not None:
                if isinstance(raw, str):
                    order = json.loads(raw)
                elif isinstance(raw, list):
                    order = list(raw)
                valid_order = [s for s in order if s in DEFAULT_SECTION_ORDER]
                for s in DEFAULT_SECTION_ORDER:
                    if s not in valid_order:
                        valid_order.append(s)
                return valid_order
        except Exception:
            pass
        return list(DEFAULT_SECTION_ORDER)

    def _save_section_order(self):
        try:
            settings = QSettings("OpenMath", "OpenMath")
            settings.setValue("palette_section_order", json.dumps(self.section_order))
        except Exception:
            pass

    def _rebuild_sections_layout(self):
        if not self.container_layout:
            return
        while self.container_layout.count():
            self.container_layout.takeAt(0)

        for name in self.section_order:
            if name in self.sections:
                self.container_layout.addWidget(self.sections[name])

        self.container_layout.addStretch()

    def _on_section_drag_started(self, title: str):
        self._is_dragging_section = True
        self._dragged_section_title = title
        self._pre_drag_expanded = {
            name: sec.header.is_expanded for name, sec in self.sections.items()
        }
        for name, sec in self.sections.items():
            sec.set_expanded(False)

        if title in self.sections:
            self.sections[title].header.set_dragging_style(True)

    def update_drag_indicator(self, pos: QPoint):
        if not self._is_dragging_section or not self.drop_indicator or not self.palette_container:
            return

        target_idx, target_y = self._get_drop_index_and_y(pos)
        w = self.palette_container.width()
        self.drop_indicator.setGeometry(4, int(target_y - 4), max(10, w - 8), 8)
        self.drop_indicator.show()
        self.drop_indicator.raise_()

    def hide_drag_indicator(self):
        if self.drop_indicator:
            self.drop_indicator.hide()

    def _get_drop_index_and_y(self, pos: QPoint) -> tuple:
        mouse_y = pos.y()
        visible_sections = [
            name for name in self.section_order
            if name in self.sections and self.sections[name].isVisible()
        ]
        if not visible_sections:
            return 0, 0

        first_sec = self.sections[visible_sections[0]]
        if mouse_y < first_sec.geometry().center().y():
            return 0, first_sec.geometry().top()

        for idx in range(len(visible_sections) - 1):
            sec_curr = self.sections[visible_sections[idx]]
            sec_next = self.sections[visible_sections[idx + 1]]
            boundary_y = (sec_curr.geometry().bottom() + sec_next.geometry().top()) / 2
            if mouse_y < boundary_y:
                return idx + 1, sec_curr.geometry().bottom() + 1

        last_sec = self.sections[visible_sections[-1]]
        return len(visible_sections), last_sec.geometry().bottom() + 1

    def handle_section_drop(self, source_title: str, pos: QPoint):
        self.hide_drag_indicator()
        if source_title not in self.section_order:
            self.on_section_drag_ended()
            return

        target_idx, _ = self._get_drop_index_and_y(pos)
        old_idx = self.section_order.index(source_title)

        if target_idx <= old_idx:
            new_idx = target_idx
        else:
            new_idx = target_idx - 1

        new_idx = max(0, min(new_idx, len(self.section_order) - 1))

        if new_idx != old_idx:
            self.section_order.remove(source_title)
            self.section_order.insert(new_idx, source_title)
            self._save_section_order()
            self._rebuild_sections_layout()

        self._restore_header_styles()

        for name, was_expanded in getattr(self, "_pre_drag_expanded", {}).items():
            if name in self.sections:
                self.sections[name].set_expanded(was_expanded)
        if source_title in self.sections:
            self.sections[source_title].set_expanded(True)

        self._is_dragging_section = False
        self._dragged_section_title = None

        win = self.window()
        if win and hasattr(win, "statusBar") and win.statusBar():
            win.statusBar().showMessage(f"Moved '{source_title}' to position {new_idx + 1}", 3000)

    def _restore_header_styles(self):
        for sec in self.sections.values():
            sec.header.set_dragging_style(False)

    def on_section_drag_ended(self):
        self.hide_drag_indicator()
        self._restore_header_styles()
        if self._is_dragging_section:
            for name, was_expanded in getattr(self, "_pre_drag_expanded", {}).items():
                if name in self.sections:
                    self.sections[name].set_expanded(was_expanded)
        self._is_dragging_section = False
        self._dragged_section_title = None

    def move_section(self, name: str, direction: int):
        if name not in self.section_order:
            return
        idx = self.section_order.index(name)
        new_idx = idx + direction
        if 0 <= new_idx < len(self.section_order):
            self.section_order.pop(idx)
            self.section_order.insert(new_idx, name)
            self._save_section_order()
            self._rebuild_sections_layout()
            win = self.window()
            if win and hasattr(win, "statusBar") and win.statusBar():
                win.statusBar().showMessage(f"Moved '{name}' to position {new_idx + 1}", 3000)

    def reset_section_order(self):
        self.section_order = list(DEFAULT_SECTION_ORDER)
        self._save_section_order()
        self._rebuild_sections_layout()
        win = self.window()
        if win and hasattr(win, "statusBar") and win.statusBar():
            win.statusBar().showMessage("Reset palette section order to default", 3000)

    def collapse_all_sections(self):
        for sec in self.sections.values():
            sec.set_expanded(False)

    def expand_all_sections(self):
        for sec in self.sections.values():
            sec.set_expanded(True)

    def _item_key(self, item: dict) -> tuple:
        kind = item.get("kind", "")
        tmpl = (item.get("template") or "").strip()
        latex = (item.get("latex") or "").strip()
        if kind == "math" and latex:
            return (kind, latex, tmpl)
        return (kind, tmpl)

    def _is_favorited(self, item: dict) -> bool:
        target_key = self._item_key(item)
        return any(self._item_key(fav) == target_key for fav in self.favorite_items)

    def _load_favorites(self) -> list:
        try:
            settings = QSettings("OpenMath", "OpenMath")
            raw = settings.value("palette_favorites", None)
            if raw is not None:
                if isinstance(raw, str):
                    return json.loads(raw)
                elif isinstance(raw, list):
                    return raw
        except Exception:
            pass
        return [dict(x) for x in DEFAULT_FAVORITES]

    def _save_favorites(self):
        try:
            settings = QSettings("OpenMath", "OpenMath")
            settings.setValue("palette_favorites", json.dumps(self.favorite_items))
        except Exception:
            pass

    def add_favorite(self, item_data: dict):
        if not self._is_favorited(item_data):
            self.favorite_items.append(dict(item_data))
            self._save_favorites()
            self._refresh_favorites_ui()
            if self.fav_section:
                self.fav_section.set_expanded(True)
            if hasattr(self, "palettes_scroll") and self.palettes_scroll:
                self.palettes_scroll.verticalScrollBar().setValue(0)
            win = self.window()
            if win and hasattr(win, "statusBar") and win.statusBar():
                label = item_data.get("tooltip") or item_data.get("fallback") or item_data.get("label") or item_data.get("template", "")
                label = label.split("\n")[0]
                win.statusBar().showMessage(f"Added '{label}' to Favorites", 3000)

    def remove_favorite(self, item_data: dict):
        target_key = self._item_key(item_data)
        self.favorite_items = [fav for fav in self.favorite_items if self._item_key(fav) != target_key]
        self._save_favorites()
        self._refresh_favorites_ui()
        win = self.window()
        if win and hasattr(win, "statusBar") and win.statusBar():
            label = item_data.get("tooltip") or item_data.get("fallback") or item_data.get("label") or item_data.get("template", "")
            label = label.split("\n")[0]
            win.statusBar().showMessage(f"Removed '{label}' from Favorites", 3000)

    def clear_all_favorites(self, confirm: bool = True):
        if confirm:
            reply = QMessageBox.question(
                self,
                "Clear Favorites",
                "Are you sure you want to remove all items from Favorites?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        self.favorite_items.clear()
        self._save_favorites()
        self._refresh_favorites_ui()
        win = self.window()
        if win and hasattr(win, "statusBar") and win.statusBar():
            win.statusBar().showMessage("Cleared all Favorites", 3000)

    def restore_default_favorites(self):
        self.favorite_items = [dict(x) for x in DEFAULT_FAVORITES]
        self._save_favorites()
        self._refresh_favorites_ui()
        win = self.window()
        if win and hasattr(win, "statusBar") and win.statusBar():
            win.statusBar().showMessage("Restored default Favorites", 3000)

    def _show_item_context_menu(self, btn: QWidget, pos: QPoint, item_data: dict, in_favorites: bool = False):
        menu = QMenu(self)
        Theme.apply_menu_style(menu, self.theme_mode)

        tmpl = item_data.get("template", "")
        is_fav = self._is_favorited(item_data)

        if in_favorites:
            remove_act = QAction("Remove from Favorites", menu)
            remove_act.triggered.connect(lambda: self.remove_favorite(item_data))
            menu.addAction(remove_act)

            menu.addSeparator()

            insert_act = QAction("Insert into Document", menu)
            insert_act.triggered.connect(lambda: self.insertTemplate.emit(tmpl))
            menu.addAction(insert_act)

            menu.addSeparator()

            clear_act = QAction("Clear All Favorites", menu)
            clear_act.triggered.connect(self.clear_all_favorites)
            menu.addAction(clear_act)

            restore_act = QAction("Restore Default Favorites", menu)
            restore_act.triggered.connect(self.restore_default_favorites)
            menu.addAction(restore_act)
        else:
            if is_fav:
                status_act = QAction("✓  In Favorites", menu)
                status_act.setEnabled(False)
                menu.addAction(status_act)

                remove_act = QAction("Remove from Favorites", menu)
                remove_act.triggered.connect(lambda: self.remove_favorite(item_data))
                menu.addAction(remove_act)
            else:
                add_act = QAction("Add to Favorites", menu)
                add_act.triggered.connect(lambda: self.add_favorite(item_data))
                menu.addAction(add_act)

            menu.addSeparator()

            insert_act = QAction("Insert into Document", menu)
            insert_act.triggered.connect(lambda: self.insertTemplate.emit(tmpl))
            menu.addAction(insert_act)

        global_pos = btn.mapToGlobal(pos)
        menu.exec(global_pos)

    def _refresh_favorites_ui(self):
        if self.fav_layout is None:
            return

        while self.fav_layout.count():
            item = self.fav_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)
                widget.deleteLater()

        if not self.favorite_items:
            empty_lbl = QLabel("Right-click any item to add to Favorites.")
            empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_lbl.setWordWrap(True)
            empty_lbl.setStyleSheet(f"""
                color: {"#94a3b8" if self.theme_mode == Theme.LIGHT else "#64748b"};
                font-size: 11px;
                font-style: italic;
                padding: 10px 4px;
            """)
            self.fav_layout.addWidget(empty_lbl, 0, 0, 1, 3)
            return

        cols = 3
        row = 0
        col = 0
        for fav_data in self.favorite_items:
            is_wide = fav_data.get("is_wide", False)
            if fav_data.get("kind") == "math":
                btn = self._make_math_btn(
                    latex_math=fav_data["latex"],
                    template=fav_data["template"],
                    tooltip=fav_data.get("tooltip", ""),
                    fallback_label=fav_data.get("fallback", ""),
                    height=fav_data.get("height", 34),
                    max_icon_h=fav_data.get("max_icon_h", 26),
                    max_icon_w=fav_data.get("max_icon_w", 58 if not is_wide else 180),
                    font_family=fav_data.get("font_family", "Times New Roman"),
                    is_wide=is_wide,
                    in_favorites=True,
                    item_data=fav_data,
                )
            else:
                btn = self._make_grid_btn(
                    label=fav_data.get("label", fav_data.get("template", "")),
                    template=fav_data["template"],
                    tooltip=fav_data.get("tooltip", ""),
                    font_family=fav_data.get("font_family", '-apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif'),
                    height=fav_data.get("height", 26),
                    is_wide=is_wide,
                    in_favorites=True,
                    item_data=fav_data,
                )

            if is_wide:
                if col != 0:
                    row += 1
                    col = 0
                self.fav_layout.addWidget(btn, row, 0, 1, cols)
                row += 1
                col = 0
            else:
                self.fav_layout.addWidget(btn, row, col, 1, 1)
                col += 1
                if col >= cols:
                    col = 0
                    row += 1

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Tab bar at top: Palettes / Formulas / Variables
        self.tabs = QTabWidget(self)
        self.tabs.tabBar().setElideMode(Qt.TextElideMode.ElideNone)
        self.tabs.setStyleSheet("""
            QTabWidget {
                background-color: #e2e5e9;
            }
            QTabBar {
                background-color: #e2e5e9;
            }
            QTabWidget::pane {
                border: 1px solid #c8ccd2;
                background-color: #f7f8fa;
            }
            QTabBar::tab {
                background: #e2e5e9;
                color: #334155;
                border: 1px solid #c8ccd2;
                padding: 4px 8px;
                font-size: 11px;
                margin-right: 1px;
                min-width: 60px;
            }
            QTabBar::tab:selected {
                background: #ffffff;
                color: #0f172a;
                border-bottom: 1px solid #ffffff;
                font-weight: bold;
            }
            QTabBar::tab:hover:!selected {
                background: #edf0f5;
            }
        """)

        # Palettes Tab
        self.palettes_scroll = QScrollArea()
        self.palettes_scroll.setWidgetResizable(True)
        self.palettes_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.palettes_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.palettes_scroll.setStyleSheet("background-color: #f7f8fa;")

        self.palette_container = PaletteContainerWidget(self)
        self.container_layout = QVBoxLayout(self.palette_container)
        self.container_layout.setContentsMargins(2, 2, 2, 2)
        self.container_layout.setSpacing(3)

        self.drop_indicator = DropIndicator(self.palette_container)
        self.drop_indicator.hide()

        # 1. Favorites
        self.fav_content_widget = QWidget()
        self.fav_layout = QGridLayout(self.fav_content_widget)
        self.fav_layout.setContentsMargins(2, 2, 2, 2)
        self.fav_layout.setSpacing(2)
        self.fav_section = AccordionSection("Favorites", self.fav_content_widget, start_expanded=True, theme_mode=self.theme_mode)
        self._refresh_favorites_ui()

        # Construct dictionary of all sections
        self.sections = {
            "Favorites": self.fav_section,
            "Expression": AccordionSection("Expression", self._create_expression_section(), start_expanded=True, theme_mode=self.theme_mode),
            "Embedded Systems": AccordionSection("Embedded Systems", self._create_embedded_section(), start_expanded=True, theme_mode=self.theme_mode),
            "Units": AccordionSection("Units", self._create_units_section(), start_expanded=True, theme_mode=self.theme_mode),
            "Calculus": AccordionSection("Calculus", self._create_calculus_section(), start_expanded=True, theme_mode=self.theme_mode),
            "Common Symbols": AccordionSection("Common Symbols", self._create_common_symbols_section(), start_expanded=True, theme_mode=self.theme_mode),
            "Greek": AccordionSection("Greek", self._create_greek_section(), start_expanded=False, theme_mode=self.theme_mode),
            "Matrices & Vectors": AccordionSection("Matrices & Vectors", self._create_matrices_section(), start_expanded=False, theme_mode=self.theme_mode),
        }

        for sec in self.sections.values():
            sec.header.dragStarted.connect(self._on_section_drag_started)

        # Add sections according to user-saved / default section_order
        for name in self.section_order:
            if name in self.sections:
                self.container_layout.addWidget(self.sections[name])

        self.container_layout.addStretch()
        self.palettes_scroll.setWidget(self.palette_container)

        # Formulas Tab (replaces Workbook)
        formulas_widget = self._create_formulas_tab()

        self.tabs.addTab(self.palettes_scroll, "Palettes")
        self.tabs.addTab(formulas_widget, "Formulas")

        # Variables Tab (Variable Manager)
        if self.engine:
            self.var_manager = VariableManagerWidget(self.engine, self, theme_mode=self.theme_mode)
            self.var_manager.insertVariable.connect(self.insertTemplate.emit)
            self.tabs.addTab(self.var_manager, "Variables")

        main_layout.addWidget(self.tabs)

    def refresh_variables(self):
        """Refresh Variable Manager table if present."""
        if self.var_manager:
            self.var_manager.refresh()

    def _make_math_btn(
        self,
        latex_math: str,
        template: str,
        tooltip: str = "",
        fallback_label: str = "",
        height: int = 32,
        max_icon_h: int = 24,
        max_icon_w: int = 180,
        font_family: str = "Times New Roman",
        is_wide: bool = None,
        in_favorites: bool = False,
        item_data: dict = None,
    ) -> QPushButton:
        if is_wide is None:
            is_wide = (max_icon_w > 80)

        if item_data is None:
            item_data = {
                "kind": "math",
                "latex": latex_math,
                "template": template,
                "tooltip": tooltip,
                "fallback": fallback_label,
                "height": height,
                "max_icon_h": max_icon_h,
                "max_icon_w": max_icon_w,
                "font_family": font_family,
                "is_wide": is_wide,
            }

        btn = PaletteItemButton()
        btn.item_data = item_data
        btn.setFixedHeight(height)
        btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        from PyQt6.QtWidgets import QApplication
        screen = QApplication.primaryScreen()
        screen_dpr = float(screen.devicePixelRatio()) if screen else 1.0
        # High DPI scale factor: minimum 2.0 to ensure crisp Retina rendering
        dpr = max(2.0, screen_dpr)

        is_dark = (self.theme_mode == Theme.DARK)
        math_color = "#f8fafc" if is_dark else "#0f172a"
        pixmap = MathRendererWidget.render_latex_to_pixmap(
            latex_math,
            font_size=18,
            theme_mode=self.theme_mode,
            dpi_scale=dpr * 1.5,
            color=math_color
        )

        if pixmap and not pixmap.isNull():
            target_ph = int(max_icon_h * dpr)
            target_pw = int(max_icon_w * dpr)
            if pixmap.height() > target_ph or pixmap.width() > target_pw:
                pixmap = pixmap.scaled(
                    target_pw, target_ph,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
            pixmap.setDevicePixelRatio(dpr)
            btn.setIcon(QIcon(pixmap))
            logical_w = max(1, int(pixmap.width() / dpr))
            logical_h = max(1, int(pixmap.height() / dpr))
            btn.setIconSize(QSize(logical_w, logical_h))
        else:
            btn.setText(fallback_label or latex_math)

        btn_bg = "#202b3a" if is_dark else "#ffffff"
        btn_fg = "#f8fafc" if is_dark else "#0f172a"
        btn_border = "#2e3b4f" if is_dark else "#d1d5db"
        btn_hover_bg = "#2a384c" if is_dark else "#f0f7ff"
        btn_hover_border = "#38bdf8" if is_dark else "#3b82f6"
        btn_hover_fg = "#38bdf8" if is_dark else "#1d4ed8"
        btn_pressed_bg = "#1b2533" if is_dark else "#dbeafe"

        btn.setStyleSheet(f"""
            QPushButton, PaletteItemButton {{
                background-color: {btn_bg};
                color: {btn_fg};
                border: 1px solid {btn_border};
                border-radius: 3px;
                font-family: "{font_family}", serif;
                font-size: 12px;
                padding: 2px;
            }}
            QPushButton:hover, PaletteItemButton:hover {{
                background-color: {btn_hover_bg};
                border-color: {btn_hover_border};
                color: {btn_hover_fg};
            }}
            QPushButton:pressed, PaletteItemButton:pressed {{
                background-color: {btn_pressed_bg};
            }}
        """)
        tip_text = tooltip if tooltip else (fallback_label or latex_math)
        btn.setToolTip(f"{tip_text}\n(Right-click for favorites)" if tip_text else "Right-click for favorites")
        btn.clicked.connect(lambda checked=False, tmpl=template: self.insertTemplate.emit(tmpl))
        btn.rightClicked.connect(lambda pos, b=btn, d=item_data, fav=in_favorites: self._show_item_context_menu(b, pos, d, fav))
        return btn

    def _make_grid_btn(
        self,
        label: str,
        template: str,
        tooltip: str = "",
        font_family: str = '-apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif',
        height: int = 26,
        is_wide: bool = None,
        in_favorites: bool = False,
        item_data: dict = None,
    ) -> QPushButton:
        if is_wide is None:
            is_wide = (len(label) > 6)

        if item_data is None:
            item_data = {
                "kind": "text",
                "label": label,
                "template": template,
                "tooltip": tooltip,
                "font_family": font_family,
                "height": height,
                "is_wide": is_wide,
            }

        btn = PaletteItemButton(label)
        btn.item_data = item_data
        tip_text = tooltip if tooltip else label
        btn.setToolTip(f"{tip_text}\n(Right-click for favorites)" if tip_text else "Right-click for favorites")
        btn.setFixedHeight(height)
        btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        is_dark = (self.theme_mode == Theme.DARK)
        btn_bg = "#202b3a" if is_dark else "#ffffff"
        btn_fg = "#f8fafc" if is_dark else "#0f172a"
        btn_border = "#2e3b4f" if is_dark else "#d1d5db"
        btn_hover_bg = "#2a384c" if is_dark else "#f0f7ff"
        btn_hover_border = "#38bdf8" if is_dark else "#3b82f6"
        btn_hover_fg = "#38bdf8" if is_dark else "#1d4ed8"
        btn_pressed_bg = "#1b2533" if is_dark else "#dbeafe"

        btn.setStyleSheet(f"""
            QPushButton, PaletteItemButton {{
                background-color: {btn_bg};
                color: {btn_fg};
                border: 1px solid {btn_border};
                border-radius: 3px;
                font-family: {font_family};
                font-size: 12px;
                padding: 1px;
            }}
            QPushButton:hover, PaletteItemButton:hover {{
                background-color: {btn_hover_bg};
                border-color: {btn_hover_border};
                color: {btn_hover_fg};
            }}
            QPushButton:pressed, PaletteItemButton:pressed {{
                background-color: {btn_pressed_bg};
            }}
        """)
        btn.clicked.connect(lambda checked=False, tmpl=template: self.insertTemplate.emit(tmpl))
        btn.rightClicked.connect(lambda pos, b=btn, d=item_data, fav=in_favorites: self._show_item_context_menu(b, pos, d, fav))
        return btn

    def _create_expression_section(self) -> QWidget:
        w = QWidget()
        grid = QGridLayout(w)
        grid.setContentsMargins(2, 2, 2, 2)
        grid.setSpacing(2)

        items = [
            (r"a + b", "a + b", "Addition (a + b)", "a + b"),
            (r"a - b", "a - b", "Subtraction (a - b)", "a - b"),
            (r"a \cdot b", "a · b", "Multiplication (a · b)", "a · b"),
            (r"\frac{a}{b}", r"\frac{a}{b}", "Fraction (a / b)", "a / b"),
            (r"a^b", "aᵇ", "Exponent / Power (aᵇ)", "aᵇ"),
            (r"\sqrt{a}", "√(a)", "Square root (√a)", "√a"),
            (r"\sqrt[n]{a}", "ⁿ√(a)", "Nth root (ⁿ√a)", "ⁿ√a"),
            (r"a!", "a!", "Factorial (a!)", "a!"),
            (r"|a|", "|a|", "Absolute value (|a|)", "|a|"),
            (r"e^a", "eᵃ", "Exponential (e^a)", "eᵃ"),
            (r"\ln(a)", "ln(a)", "Natural logarithm (ln a)", "ln(a)"),
            (r"\log_{10}(a)", "log₁₀(a)", "Base 10 log (log₁₀ a)", "log₁₀(a)"),
            (r"\sin(a)", "sin(a)", "Sine (sin a)", "sin(a)"),
            (r"\cos(a)", "cos(a)", "Cosine (cos a)", "cos(a)"),
            (r"\tan(a)", "tan(a)", "Tangent (tan a)", "tan(a)"),
            (r"a_n", "aₙ", "Subscript index (a_n)", "aₙ"),
            (r"f(a)", "f(a)", "Function evaluation f(a)", "f(a)"),
            (r"f(a,b)", "f(a, b)", "2-variable function f(a,b)", "f(a,b)"),
            (r"f : x \to y", "f : x -> y", "Function mapping definition (f : x -> y)", "f : x -> y"),
            (r"\sum_{k=1}^n f", r"\sum_{k=1}^n f", "Summation template", "∑ f"),
            (r"\prod_{k=1}^n f", r"\prod_{k=1}^n f", "Product template", "∏ f"),
            (r"\frac{d}{dx}f", r"\frac{d}{dx}f", "Derivative template d/dx f", "d/dx f"),
            (r"\int f\,dx", "∫(f) dx", "Indefinite integral ∫ f dx", "∫ f dx"),
            (r"\int_a^b f", r"\int_a^b f", "Definite integral ∫_a^b f", "∫_a^b f"),
            (r"f|_{x=a}", "eval(f, x = a)", "Evaluation at point (eval)", "f|x=a"),
            (r"\binom{n}{k}", "binomial(n, k)", "Binomial coefficient (n choose k)", "binom(n,k)"),
            (r"\left\{ \begin{matrix} a \\ b \end{matrix} \right.", "piecewise(x < 0, -x, x)", "Piecewise function", "piecewise"),
            (r"\lim_{x \to a^-}", "limit(f, x = a, dir='-')", "Left-sided limit", "lim_(x→a⁻)"),
            (r"\lim_{x \to a^+}", "limit(f, x = a, dir='+')", "Right-sided limit", "lim_(x→a⁺)"),
            (r"\begin{bmatrix} a \\ b \end{bmatrix}", "Vector([a, b])", "Column Vector", "Vector([a,b])"),
        ]

        cols = 3
        for idx, (ltx, tmpl, tip, fb) in enumerate(items):
            r = idx // cols
            c = idx % cols
            grid.addWidget(self._make_math_btn(ltx, tmpl, tip, fb, height=34, max_icon_h=26, max_icon_w=58), r, c)

        return w

    def _create_common_symbols_section(self) -> QWidget:
        w = QWidget()
        grid = QGridLayout(w)
        grid.setContentsMargins(2, 2, 2, 2)
        grid.setSpacing(2)

        symbols = [
            (r"\pi", "π", "Pi (3.14159...)", "π"),
            (r"e", "e", "Euler constant (2.71828...)", "e"),
            (r"i", "i", "Imaginary unit", "i"),
            (r"j", "j", "Engineering imaginary unit", "j"),
            (r"d", "d", "Differential operator", "d"),
            (r"\infty", "∞", "Infinity", "∞"),
            (r"\sum", "∑", "Summation", "∑"),
            (r"\prod", "∏", "Product", "∏"),
            (r"\int", "∫", "Integral", "∫"),
            (r"\partial", "∂", "Partial derivative", "∂"),
            (r"\cap", "∩", "Intersection", "∩"),
            (r"\cup", "∪", "Union", "∪"),
            (r"\ge", "≥", "Greater than or equal", "≥"),
            (r">", ">", "Greater than", ">"),
            (r"\le", "≤", "Less than or equal", "≤"),
            (r"<", "<", "Less than", "<"),
            (r"\neq", "≠", "Not equal", "≠"),
            (r"\equiv", "≡", "Identical / Equivalent", "≡"),
            (r"\in", "∈", "Element of", "∈"),
            (r"\notin", "∉", "Not element of", "∉"),
            (r"\subset", "⊂", "Subset of", "⊂"),
            (r"\supset", "⊃", "Superset of", "⊃"),
            (r"\emptyset", "∅", "Empty set", "∅"),
            (r"\exists", "∃", "There exists", "∃"),
            (r"\forall", "∀", "For all", "∀"),
            (r"\neg", "¬", "Logical Not", "¬"),
            (r"\wedge", "∧", "Logical And", "∧"),
            (r"\vee", "∨", "Logical Or", "∨"),
            (r"\Rightarrow", "⇒", "Implies", "⇒"),
            (r"\mathbb{C}", "ℂ", "Complex numbers", "ℂ"),
            (r"\mathbb{R}", "ℝ", "Real numbers", "ℝ"),
            (r"\mathbb{N}", "ℕ", "Natural numbers", "ℕ"),
            (r"\mathbb{Z}", "ℤ", "Integers", "ℤ"),
            (r"\mathbb{Q}", "ℚ", "Rational numbers", "ℚ"),
        ]

        cols = 5
        for idx, (ltx, tmpl, tip, fb) in enumerate(symbols):
            r = idx // cols
            c = idx % cols
            grid.addWidget(self._make_math_btn(ltx, tmpl, tip, fb, height=28, max_icon_h=20, max_icon_w=32), r, c)

        return w

    def _create_calculus_section(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)

        calc_math = [
            (r"\frac{d}{dx}f(x)", r"\frac{d}{dx}f", "First derivative", "d/dx f(x)"),
            (r"\frac{d^2}{dx^2}f(x)", "diff(f(x), x, 2)", "Second derivative", "d²/dx² f(x)"),
            (r"\int f(x)\,dx", "∫(f(x)) dx", "Indefinite integral", "∫ f(x) dx"),
            (r"\int_a^b f(x)\,dx", r"\int_a^b f(x)\,dx", "Definite integral", "∫_a^b f(x) dx"),
            (r"\lim_{x \to a} f(x)", "limit(f(x), x, a)", "Limit", "lim_(x→a) f(x)"),
        ]
        for ltx, tmpl, tip, fb in calc_math:
            btn = self._make_math_btn(ltx, tmpl, tip, fb, height=30, max_icon_h=22, max_icon_w=180)
            layout.addWidget(btn)

        calc_cmds = [
            ("Taylor Series", "taylor(f(x), x, 0, 6)", "Taylor series expansion"),
            ("solve(eq, x)", "solve(x² - 4 = 0, x)", "Solve equation"),
            ("dsolve(ODE)", "dsolve(diff(y(x), x) = y(x), y(x))", "Ordinary differential equation"),
        ]
        for lbl, tmpl, tip in calc_cmds:
            layout.addWidget(self._make_grid_btn(lbl, tmpl, tip, height=30))

        return w

    def _create_greek_section(self) -> QWidget:
        w = QWidget()
        grid = QGridLayout(w)
        grid.setContentsMargins(2, 2, 2, 2)
        grid.setSpacing(2)

        letters = [
            (r"\alpha", "α"), (r"\beta", "β"), (r"\gamma", "γ"), (r"\delta", "δ"),
            (r"\epsilon", "ε"), (r"\zeta", "ζ"), (r"\eta", "η"), (r"\theta", "θ"),
            (r"\kappa", "κ"), (r"\lambda", "λ"), (r"\mu", "μ"), (r"\nu", "ν"),
            (r"\xi", "ξ"), (r"\pi", "π"), (r"\rho", "ρ"), (r"\sigma", "σ"),
            (r"\tau", "τ"), (r"\phi", "φ"), (r"\chi", "χ"), (r"\psi", "ψ"),
            (r"\omega", "ω"), (r"\Gamma", "Γ"), (r"\Delta", "Δ"), (r"\Theta", "Θ"),
            (r"\Lambda", "Λ"), (r"\Sigma", "Σ"), (r"\Phi", "Φ"), (r"\Omega", "Ω")
        ]
        cols = 4
        for idx, (ltx, sym) in enumerate(letters):
            r = idx // cols
            c = idx % cols
            grid.addWidget(self._make_math_btn(ltx, sym, f"Greek {sym}", sym, height=28, max_icon_h=20, max_icon_w=36), r, c)

        return w

    def _create_matrices_section(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)

        btn_wiz = QPushButton("Custom Size Matrix")
        btn_wiz.setToolTip("Configure and insert a custom-sized matrix (M × N)")
        btn_wiz.setFixedHeight(26)
        btn_wiz.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                color: #ffffff;
                border: 1px solid #1d4ed8;
                border-radius: 2px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover { background-color: #1d4ed8; }
        """)
        btn_wiz.clicked.connect(self.openMatrixDialog.emit)
        layout.addWidget(btn_wiz)

        templates = [
            ("2x2 Matrix", "Matrix([[1, 2], [3, 4]])"),
            ("3x3 Matrix", "Matrix([[1, 0, 0], [0, 1, 0], [0, 0, 1]])"),
            ("Determinant", "det(⟦M⟧)"),
            ("Inverse", "inv(⟦M⟧)"),
            ("Transpose", "transpose(⟦M⟧)"),
            ("Eigenvalues", "eigenvals(⟦M⟧)"),
            ("RREF", "rref(⟦M⟧)"),
        ]
        for lbl, tmpl in templates:
            layout.addWidget(self._make_grid_btn(lbl, tmpl, lbl))

        return w

    def _create_embedded_section(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)

        emb_items = [
            ("Binary Repr (0b)", "to_bin(0x5A, 8)", "Format integer as 8-bit binary nibbles"),
            ("Hex Repr (0x)", "to_hex(255, 8)", "Format integer as 8-bit hex"),
            ("Two's Complement", "two_comp_repr(-5, 8)", "Calculate two's complement signed/unsigned breakdown"),
            ("Set Bit", "bit_set(0x00, 3)", "Set bit of register to 1"),
            ("Clear Bit", "bit_clear(0xFF, 3)", "Clear bit of register to 0"),
            ("Toggle Bit", "bit_toggle(0x00, 3)", "Toggle bit of register"),
            ("Extract Bitfield", "bit_field(0xABCD, 4, 7)", "Extract bitfield range"),
            ("Q-Format Fixed Pt", "to_q(3.1415, 7, 8)", "Convert float to Q-format integer"),
            ("IEEE-754 Float", "ieee754(12.375)", "IEEE-754 floating-point bits"),
            ("UART Baud & Error", "ubrr_calc(16 · MHz, 9600)", "UART UBRR & baud rate error"),
            ("Timer Prescaler/ARR", "timer_calc(16 MHz, 64, 249)", "Timer frequency & period"),
            ("ADC Count to Volt", "adc_volt(512, 3.3, 10)", "Convert ADC count to voltage"),
            ("Voltage Divider", "voltage_divider(5.0 V, 10 kOhm, 10 kOhm)", "Voltage divider formula"),
            ("RC Cutoff & Tau", "rc_cutoff(10 kOhm, 100 nF)", "RC filter cutoff frequency & tau"),
        ]
        for lbl, tmpl, tip in emb_items:
            layout.addWidget(self._make_grid_btn(lbl, tmpl, tip, font_family="Segoe UI"))

        return w

    def _create_units_section(self) -> QWidget:
        w = QWidget()
        grid = QGridLayout(w)
        grid.setContentsMargins(2, 2, 2, 2)
        grid.setSpacing(2)

        units = [
            # Voltage
            ("mV", " mV"), ("V", " V"), ("kV", " kV"), ("MV", " MV"),
            # Resistance
            ("Ω", " Ohm"), ("kΩ", " kOhm"), ("MΩ", " MOhm"), ("GΩ", " GOhm"),
            # Current
            ("μA", " uA"), ("mA", " mA"), ("A", " A"), ("MA", " MA"),
            # Power
            ("mW", " mW"), ("W", " W"), ("kW", " kW"), ("MW", " MW"),
            # Frequency
            ("Hz", " Hz"), ("kHz", " kHz"), ("MHz", " MHz"), ("GHz", " GHz"),
            # Time
            ("ns", " ns"), ("μs", " us"), ("ms", " ms"), ("s", " s"),
            # Capacitance
            ("pF", " pF"), ("nF", " nF"), ("μF", " uF"), ("mF", " mF"),
        ]
        cols = 4
        for idx, (lbl, tmpl) in enumerate(units):
            r = idx // cols
            c = idx % cols
            grid.addWidget(self._make_grid_btn(lbl, tmpl, f"Unit {lbl}"), r, c)

        return w

    def _create_favorites_section(self) -> QWidget:
        return self.fav_content_widget

    def _create_formulas_tab(self) -> QWidget:
        """Create the Formulas & Plots lookup tab with live search and quick insertion."""
        container = QWidget()
        container.setStyleSheet("background-color: #f7f8fa;")
        vbox = QVBoxLayout(container)
        vbox.setContentsMargins(4, 6, 4, 4)
        vbox.setSpacing(6)

        # Search Bar
        search_edit = QLineEdit()
        search_edit.setPlaceholderText("🔍 Search formulas & plots...")
        search_edit.setClearButtonEnabled(True)
        search_edit.setStyleSheet(f"""
            QLineEdit {{
                background-color: {"#ffffff" if self.theme_mode == Theme.LIGHT else "#1e232e"};
                color: {"#1e293b" if self.theme_mode == Theme.LIGHT else "#f0f4fc"};
                border: 1px solid {"#cbd5e1" if self.theme_mode == Theme.LIGHT else "#3b4354"};
                border-radius: 5px;
                padding: 5px 8px;
                font-size: 11px;
            }}
            QLineEdit:focus {{
                border: 1.5px solid {"#2563eb" if self.theme_mode == Theme.LIGHT else "#60a5fa"};
            }}
        """)
        vbox.addWidget(search_edit)

        # Scroll area for formula categories
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("background-color: transparent;")

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(2, 2, 2, 2)
        scroll_layout.setSpacing(4)

        all_sections = []

        def _build_category(title: str, items: list, start_expanded: bool = True):
            cat_widget = QWidget()
            cat_layout = QVBoxLayout(cat_widget)
            cat_layout.setContentsMargins(2, 2, 2, 2)
            cat_layout.setSpacing(4)

            cards = []
            for item_title, formula_str, desc in items:
                card = FormulaCard(item_title, formula_str, desc, theme_mode=self.theme_mode)
                card.clicked.connect(self.insertTemplate.emit)
                card.rightClicked.connect(lambda pos, c=card: self._show_item_context_menu(c, pos, c.get_item_data(), in_favorites=False))
                cat_layout.addWidget(card)
                cards.append(card)

            section = AccordionSection(title, cat_widget, start_expanded=start_expanded)
            scroll_layout.addWidget(section)
            all_sections.append((section, cards))

        # 1. Plotting Formulas
        plot_items = [
            ("Linear Line (Single)", "plot(2 · x + 3, x = -10..10)", "2D straight line with slope and y-intercept"),
            ("Multiple Lines", "plot([2 · x + 1, -x + 4, 0.5 · x - 2], x = -5..5)", "Compare multiple linear curves on the same plot"),
            ("Quadratic / Parabola", "plot(x² - 4 · x + 3, x = -2..6)", "Parabola with vertex and roots"),
            ("Cubic Polynomial", "plot(x³ - 3 · x, x = -2.5..2.5)", "3rd degree polynomial curve"),
            ("Sine Wave", "plot(sin(x), x = -2 · π .. 2 · π)", "Periodic harmonic sine wave"),
            ("Cosine Wave", "plot(cos(x), x = -2 · π .. 2 · π)", "Periodic harmonic cosine wave"),
            ("Damped Oscillation", "plot(exp(-0.2 · x) · cos(2 · x), x = 0..20)", "Decaying sinusoidal oscillation curve"),
            ("Exponential Decay", "plot(exp(-x/2), x = 0..10)", "Exponential decay function"),
            ("Rational Curve", "plot(1 / (x² + 1), x = -5..5)", "Bell-shaped rational curve"),
            ("Parametric Circle", "plot([cos(t), sin(t)], t = 0 .. 2 · π)", "2D parametric circular trajectory"),
            ("Polar Rose", "plot(cos(4 · theta), theta = 0 .. 2 · π)", "4-petal polar rose plot"),
            ("Feasible Region (LP)", "polygonOmråde([x >= 0, y >= 0, x + y <= 10], x = 0..12, y = 0..12)", "Linear programming feasible polygon"),
            ("LP Level Curves", "LPplot(30 · x + 20 · y, [x >= 0, y >= 0, x + y <= 10], [100, 200, 300])", "Optimization objective level lines"),
            ("3D Surface Plot", "plot3d(sin(x) · cos(y), x = -π .. π, y = -π .. π)", "3D bivariate surface plot"),
        ]
        _build_category("Plotting Formulas", plot_items, start_expanded=True)

        # 2. Embedded Systems & Hardware Formulas
        embedded_items = [
            ("Ohm's Law", "V := I · R", "Voltage, current, and resistance: V = I · R"),
            ("Voltage Divider", "voltage_divider(5.0, 10000, 4700)", "Calculate Vout from Vin, R1, and R2"),
            ("Parallel Resistors", "R_eq := (R_1 · R_2) / (R_1 + R_2)", "Equivalent resistance of parallel pair"),
            ("RC Low-Pass Cutoff", "rc_cutoff(10 kOhm, 100 nF)", "fc = 1 / (2 · pi · R · C)"),
            ("RC Time Constant", "tau := R · C", "Step response time constant tau = R · C"),
            ("ADC Voltage to Count", "adc_volt_to_count(3.3, 3.3, 12)", "Convert analog volts to N-bit digital integer"),
            ("ADC Count to Voltage", "adc_count_to_volt(2048, 3.3, 12)", "Convert raw digital count to measured volts"),
            ("UART Baud Divisor", "uart_baud_rate(72e6, 115200)", "Calculate UART clock prescaler register"),
            ("Timer ARR Prescaler", "timer_arr_prescaler(72e6, 1000)", "Timer auto-reload & prescaler for frequency"),
            ("Bit Set", "bit_set(0x00, 3)", "Set bit n in register: reg | (1 << bit)"),
            ("Bit Clear", "bit_clear(0xFF, 3)", "Clear bit n in register: reg & ~(1 << bit)"),
            ("Bit Toggle", "bit_toggle(0x00, 2)", "Toggle bit n in register: reg ^ (1 << bit)"),
            ("Extract Bitfield", "extract_bitfield(0xABCD, 4, 8)", "Extract bits at given offset and width"),
            ("Binary Representation", "to_bin(0xA5, 8)", "Format integer as binary bit string"),
            ("Hex Representation", "to_hex(165, 8)", "Format integer as hexadecimal string"),
            ("Two's Complement", "two_comp_repr(-42, 8)", "Signed 2's complement representation"),
            ("Electric Power (P = I²R)", "P := I² · R", "Electrical power dissipated in resistor"),
            ("Capacitor Energy", "E := (1/2) · C · V²", "Stored electrical energy in joules"),
            ("Inductive Reactance (XL)", "XL := 2 · π · f · L", "AC impedance of inductor in ohms"),
            ("Capacitive Reactance (XC)", "XC := 1 / (2 · π · f · C)", "AC impedance of capacitor in ohms"),
        ]
        _build_category("Embedded & Hardware", embedded_items, start_expanded=True)

        # 3. Mathematics & Calculus
        math_items = [
            ("Derivative", "diff(f(x), x)", "Differentiate f(x) with respect to x"),
            ("Definite Integral", "∫(f(x), x = a..b)", "Definite Riemann integral from a to b"),
            ("Indefinite Integral", "∫(f(x)) dx", "Antiderivative of f(x)"),
            ("Summation", "∑(k², k = 1..n)", "Sum of terms from k=1 to n"),
            ("Product", "∏(k, k = 1..n)", "Product of terms from k=1 to n"),
            ("Square Root", "√(x² + 1)", "Square root radical"),
            ("Base-10 Logarithm", "log₁₀(x)", "Common logarithm base 10"),
            ("Solve Equation", "solve(f(x) = 0, x)", "Solve algebraic equation for x"),
            ("Solve System", "solve([x + y = 10, 2 · x - y = 4], [x, y])", "Solve system of simultaneous equations"),
            ("Taylor Series", "taylor(f(x), x, 0, 5)", "Taylor polynomial expansion"),
            ("Limit", "limit(f(x), x = 0)", "Evaluate limit as x approaches value"),
        ]
        _build_category("Calculus & Algebra", math_items, start_expanded=False)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        vbox.addWidget(scroll)

        # Real-time search filter
        def on_search(text: str):
            query = text.strip().lower()
            for section, cards in all_sections:
                any_card_visible = False
                for card in cards:
                    if not query or card.matches_query(query):
                        card.setVisible(True)
                        any_card_visible = True
                    else:
                        card.setVisible(False)
                section.setVisible(any_card_visible)
                if query and any_card_visible:
                    section.content.setVisible(True)
                    section.header.is_expanded = True
                    section.header._update_text()

        search_edit.textChanged.connect(on_search)
        return container
