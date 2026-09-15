"""
Interactive Worksheet View for OpenMath CAS Calculator.
Contains stacked, chronologically ordered execution groups (WorksheetCell widgets).
Supports batch evaluation, cell reordering, equation numbering, serialization,
Worksheet Mode vs Document Mode, and active expression tracking for Context Panel.
"""

import json
import uuid
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QPushButton,
    QLabel, QFrame, QSizePolicy, QFileDialog, QMessageBox, QApplication,
    QLineEdit, QTextEdit
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QEvent, QPoint, QMimeData
from PyQt6.QtGui import QTextCursor, QWheelEvent, QKeyEvent, QPainter, QPen, QColor, QUndoStack, QUndoCommand, QKeySequence, QFont

from cas_engine import CASEngine, CASResult, PlotData
from .worksheet_cell import WorksheetCell
from .thread_worker import CalculationRunner
from .theme import Theme
try:
    from PyQt6 import sip
except ImportError:
    import sip


class SectionScopeOverlay(QWidget):
    """
    Continuous section scope bracket overlay.
    Paints crisp hierarchical tree brackets on the left margin:
    - Vertical lines descending from disclosure chevrons (▼).
    - Horizontal terminal ticks (└───) at the bottom boundary of each section/subsection.
    """
    def __init__(self, container):
        super().__init__(container)
        self.container = container
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setStyleSheet("background: transparent;")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        pen = QPen(QColor("#8e9aaf"), 1)
        painter.setPen(pen)

        cells = getattr(self.container, 'cells', [])
        for i, cell in enumerate(cells):
            try:
                if sip.isdeleted(cell):
                    continue
            except (RuntimeError, ReferenceError):
                continue

            if not cell.isVisible() or not getattr(cell, 'is_section_header', False):
                continue
            if getattr(cell, 'is_collapsed', False):
                continue

            arrow = getattr(cell, 'btn_section_toggle', None)
            if not arrow or not arrow.isVisible():
                continue

            sec_level = getattr(cell, 'section_level', 0)
            try:
                tip = arrow.mapTo(self.container, QPoint(arrow.width() // 2, arrow.height() - 2))
            except Exception:
                continue

            start_x = tip.x()
            start_y = tip.y()

            last_cell = None
            for child in cells[i + 1:]:
                try:
                    if sip.isdeleted(child):
                        continue
                except (RuntimeError, ReferenceError):
                    continue

                if not child.isVisible():
                    continue
                if getattr(child, 'is_section_header', False):
                    if getattr(child, 'section_level', 0) <= sec_level:
                        break
                else:
                    if getattr(child, '_is_outside_section', False) or getattr(child, 'section_level', 0) < sec_level:
                        break
                last_cell = child

            if last_cell is not None:
                end_y = last_cell.y() + last_cell.height() - 4
                if end_y > start_y:
                    painter.drawLine(start_x, start_y, start_x, end_y)
                    painter.drawLine(start_x, end_y, start_x + 8, end_y)


class WorksheetContainer(QWidget):
    """Container widget that ensures clicks anywhere on the white page activate and focus a cell."""
    def __init__(self, worksheet_view, parent=None):
        super().__init__(parent)
        self.ws_view = worksheet_view
        self.setStyleSheet("background-color: #ffffff;")
        self.overlay = SectionScopeOverlay(self)
        self._drag_start_pos = None
        self._is_dragging = False

    @property
    def cells(self):
        return self.ws_view.cells

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'overlay'):
            self.overlay.setGeometry(0, 0, self.width(), self.height())
            self.overlay.raise_()
            self.overlay.update()

    def wheelEvent(self, event):
        if hasattr(self.ws_view, 'scroll_area'):
            self.ws_view.scroll_area.wheelEvent(event)
            event.accept()
        else:
            super().wheelEvent(event)

    def mousePressEvent(self, event):
        pos = event.position().toPoint() if hasattr(event, 'position') else event.pos()
        self._drag_start_pos = pos
        self._is_dragging = False

        target_cell = None
        for cell in self.ws_view.cells:
            geo = cell.geometry()
            if geo.top() <= pos.y() <= geo.bottom():
                target_cell = cell
                break
        if not target_cell and self.ws_view.cells:
            if pos.y() > self.ws_view.cells[-1].geometry().bottom():
                last_c = self.ws_view.cells[-1]
                if getattr(last_c, 'is_inside_section', False) or getattr(last_c, 'is_section_header', False):
                    if not getattr(last_c, 'is_section_header', False) and not last_c.get_input_text().strip():
                        last_c.is_inside_section = False
                        last_c._is_outside_section = True
                        last_c.section_level = 0
                        last_c._apply_indentation()
                        self.ws_view.update_section_hierarchy()
                        target_cell = last_c
                    else:
                        target_cell = self.ws_view.insert_cell_outside_section(last_c.cell_id)
                else:
                    target_cell = self.ws_view.cells[-1]
            elif pos.y() < self.ws_view.cells[0].geometry().top():
                target_cell = self.ws_view.cells[0]

        mods = event.modifiers()
        if target_cell:
            if mods & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier):
                self.ws_view.select_cell(target_cell, additive=True)
            elif mods & Qt.KeyboardModifier.ShiftModifier:
                self.ws_view.select_cell(target_cell, range_select=True)
            else:
                self.ws_view.clear_cell_selection()
                self.ws_view.active_cell = target_cell
                self.ws_view.activeCellChanged.emit(target_cell)
                try:
                    if not sip.isdeleted(target_cell) and hasattr(target_cell, 'input_edit') and not sip.isdeleted(target_cell.input_edit):
                        target_cell.input_edit.setFocus()
                    elif not sip.isdeleted(target_cell) and hasattr(target_cell, 'title_edit') and not sip.isdeleted(target_cell.title_edit):
                        target_cell.title_edit.setFocus()
                except (RuntimeError, AttributeError, ReferenceError):
                    pass
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if (event.buttons() & Qt.MouseButton.LeftButton) and self._drag_start_pos is not None:
            pos = event.position().toPoint() if hasattr(event, 'position') else event.pos()
            dy = abs(pos.y() - self._drag_start_pos.y())
            if dy > 25:
                min_y = min(self._drag_start_pos.y(), pos.y())
                max_y = max(self._drag_start_pos.y(), pos.y())
                dragged_cells = []
                for cell in self.ws_view.cells:
                    geo = cell.geometry()
                    if geo.bottom() - 8 >= min_y and geo.top() + 8 <= max_y:
                        dragged_cells.append(cell)
                if len(dragged_cells) > 1:
                    self._is_dragging = True
                    self.ws_view.clear_cell_selection()
                    for c in dragged_cells:
                        c.set_cell_selected(True)
                        self.ws_view.selected_cells.append(c)
                    if self.ws_view.selected_cells:
                        self.ws_view.active_cell = self.ws_view.selected_cells[-1]
                        self.ws_view.activeCellChanged.emit(self.ws_view.active_cell)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_start_pos = None
        self._is_dragging = False
        super().mouseReleaseEvent(event)


class DeleteCellsCommand(QUndoCommand):
    """Undoable command for deleting one or multiple cells (sections, math, images, text)."""
    def __init__(self, worksheet, cell_items, description="Delete Statement(s)"):
        super().__init__(description)
        self.worksheet = worksheet
        # cell_items: list of (original_index, cell_dict) sorted by original_index ascending
        self.cell_items = list(cell_items)
        self.deleted_ids = [item[1].get('cell_id') for item in self.cell_items]
        self._created_placeholder_id = None

    def redo(self):
        ws = self.worksheet
        ws._is_undo_redo = True
        try:
            import time
            ws._last_doc_action_time = time.time()

            # Ensure any collapsed sections to be deleted are expanded first
            for cid in self.deleted_ids:
                idx = ws._get_cell_index_by_id(cid)
                if idx != -1:
                    c = ws.cells[idx]
                    if getattr(c, 'is_section_header', False) and getattr(c, 'is_collapsed', False):
                        ws._on_section_toggled(cid, is_collapsed=False)

            min_idx = len(ws.cells)
            for cid in self.deleted_ids:
                idx = ws._get_cell_index_by_id(cid)
                if idx != -1:
                    min_idx = min(min_idx, idx)
                    c = ws.cells.pop(idx)
                    ws.cells_layout.removeWidget(c)
                    c.deleteLater()

            ws.clear_cell_selection()

            if not ws.cells:
                # Worksheet must never be completely empty
                placeholder = ws._create_cell_from_dict({'input': '', 'input_mode': 0})
                ws.cells.append(placeholder)
                ws.cells_layout.addWidget(placeholder)
                self._created_placeholder_id = placeholder.cell_id

            ws.renumber_equation_labels()
            ws.cellCountChanged.emit(len(ws.cells))

            if ws.cells:
                target_idx = min(min_idx, len(ws.cells) - 1)
                ws.active_cell = ws.cells[target_idx]
                ws.activeCellChanged.emit(ws.active_cell)
                try:
                    if hasattr(ws.active_cell, 'input_edit') and not sip.isdeleted(ws.active_cell.input_edit):
                        ws.active_cell.input_edit.setFocus()
                    elif hasattr(ws.active_cell, 'title_edit') and not sip.isdeleted(ws.active_cell.title_edit):
                        ws.active_cell.title_edit.setFocus()
                except Exception:
                    pass

            ws.ensure_section_content()
            ws.update_section_hierarchy()
            if hasattr(ws, 'container') and hasattr(ws.container, 'overlay'):
                ws.container.overlay.update()
        finally:
            ws._is_undo_redo = False

    def undo(self):
        ws = self.worksheet
        ws._is_undo_redo = True
        try:
            import time
            ws._last_doc_action_time = time.time()

            if self._created_placeholder_id:
                pidx = ws._get_cell_index_by_id(self._created_placeholder_id)
                if pidx != -1:
                    pc = ws.cells.pop(pidx)
                    ws.cells_layout.removeWidget(pc)
                    pc.deleteLater()
                self._created_placeholder_id = None

            restored_cells = []
            for orig_idx, cdict in self.cell_items:
                cell = ws._create_cell_from_dict(cdict)
                if orig_idx < len(ws.cells):
                    ws.cells.insert(orig_idx, cell)
                    ws.cells_layout.insertWidget(orig_idx, cell)
                else:
                    ws.cells.append(cell)
                    ws.cells_layout.addWidget(cell)
                restored_cells.append(cell)

            ws.clear_cell_selection()
            for c in restored_cells:
                c.set_cell_selected(True)
                ws.selected_cells.append(c)

            if restored_cells:
                ws.active_cell = restored_cells[-1]
                ws.activeCellChanged.emit(ws.active_cell)

            ws.renumber_equation_labels()
            ws.cellCountChanged.emit(len(ws.cells))
            ws.update_section_hierarchy()

            for orig_idx, cdict in self.cell_items:
                if cdict.get('is_section_header') and cdict.get('is_collapsed'):
                    ws._on_section_toggled(cdict.get('cell_id'), is_collapsed=True)

            ws.adjust_visible_cells_height()
            if hasattr(ws, 'container') and hasattr(ws.container, 'overlay'):
                ws.container.overlay.update()

            if restored_cells:
                try:
                    ws.ensure_cell_visible(restored_cells[0])
                except Exception:
                    pass

            ws.statusMessage.emit(f"Restored {len(restored_cells)} statement(s)", 2500)
        finally:
            ws._is_undo_redo = False


class InsertCellsCommand(QUndoCommand):
    """Undoable command for inserting one or multiple cells into worksheet."""
    def __init__(self, worksheet, cell_items, description="Insert Statement(s)", select_inserted=False):
        super().__init__(description)
        self.worksheet = worksheet
        # cell_items: list of (target_index, cell_dict)
        self.cell_items = list(cell_items)
        self.inserted_ids = [item[1].get('cell_id') for item in self.cell_items]
        self.select_inserted = select_inserted

    def redo(self):
        ws = self.worksheet
        ws._is_undo_redo = True
        try:
            import time
            ws._last_doc_action_time = time.time()
            inserted_cells = []
            for target_pos, cdict in self.cell_items:
                cell = ws._create_cell_from_dict(cdict)
                if target_pos < len(ws.cells):
                    ws.cells.insert(target_pos, cell)
                    ws.cells_layout.insertWidget(target_pos, cell)
                else:
                    ws.cells.append(cell)
                    ws.cells_layout.addWidget(cell)
                inserted_cells.append(cell)

            ws.clear_cell_selection()
            if self.select_inserted:
                for c in inserted_cells:
                    c.set_cell_selected(True)
                    ws.selected_cells.append(c)
            else:
                for c in inserted_cells:
                    c.set_cell_selected(False)

            if inserted_cells:
                ws.active_cell = inserted_cells[-1]
                ws.activeCellChanged.emit(ws.active_cell)
                try:
                    if hasattr(ws.active_cell, 'input_edit') and not sip.isdeleted(ws.active_cell.input_edit):
                        ws.active_cell.input_edit.setFocus()
                    elif hasattr(ws.active_cell, 'title_edit') and not sip.isdeleted(ws.active_cell.title_edit):
                        ws.active_cell.title_edit.setFocus()
                except Exception:
                    pass
                try:
                    ws.ensure_cell_visible(ws.active_cell)
                except Exception:
                    pass

            ws.renumber_equation_labels()
            ws.cellCountChanged.emit(len(ws.cells))
            ws.update_section_hierarchy()
            if hasattr(ws, 'container') and hasattr(ws.container, 'overlay'):
                ws.container.overlay.update()
        finally:
            ws._is_undo_redo = False

    def undo(self):
        ws = self.worksheet
        ws._is_undo_redo = True
        try:
            import time
            ws._last_doc_action_time = time.time()
            for cid in self.inserted_ids:
                idx = ws._get_cell_index_by_id(cid)
                if idx != -1:
                    c = ws.cells.pop(idx)
                    ws.cells_layout.removeWidget(c)
                    c.deleteLater()

            ws.clear_cell_selection()
            if not ws.cells:
                placeholder = ws._create_cell_from_dict({'input': '', 'input_mode': 0})
                ws.cells.append(placeholder)
                ws.cells_layout.addWidget(placeholder)

            ws.renumber_equation_labels()
            ws.cellCountChanged.emit(len(ws.cells))
            ws.update_section_hierarchy()
            if hasattr(ws, 'container') and hasattr(ws.container, 'overlay'):
                ws.container.overlay.update()
            if ws.cells:
                ws.active_cell = ws.cells[-1]
                ws.activeCellChanged.emit(ws.active_cell)
        finally:
            ws._is_undo_redo = False


class WorksheetView(QWidget):
    """
    OpenMath Document Area displaying stacked execution groups on a continuous white page.
    """
    cellCountChanged = pyqtSignal(int)
    plotRequested = pyqtSignal(str)
    statusMessage = pyqtSignal(str, int)
    activeCellChanged = pyqtSignal(object)  # Emits active WorksheetCell for Context Panel
    zoomChanged = pyqtSignal(int)           # Emits zoom level percentage (e.g. 100, 125, 150)
    executionTimeChanged = pyqtSignal(float)
    editableChanged = pyqtSignal(bool)

    def __init__(self, engine: CASEngine, parent=None, theme_mode: str = "light"):
        super().__init__(parent)
        self.engine = engine
        self.theme_mode = theme_mode
        self.file_path = None
        self.is_editable = True
        self.is_worksheet_mode = False  # Document mode by default
        self.zoom_percent = 100
        self._smooth_zoom = 100.0

        self.runner = CalculationRunner(self.engine, self)
        self.runner.finished.connect(self._on_cell_calc_finished)
        self.runner.error.connect(self._on_cell_calc_error)

        self.cells = []  # List of WorksheetCell
        self.selected_cells = []  # List of multi-selected WorksheetCell
        self.active_cell: WorksheetCell = None
        self.execution_counter = 0
        self.default_font_size = 12
        self.default_font_family = "Times New Roman"
        self.default_line_spacing = 1.0
        self.current_text_color = None
        self.current_highlight_color = None

        self.undo_stack = QUndoStack(self)
        self._is_undo_redo = False
        self._last_doc_action_time = 0.0
        self._last_text_edit_time = 0.0

        self._init_ui()

    def set_editable(self, editable: bool):
        self.is_editable = editable
        if hasattr(self, 'view_mode_banner'):
            self.view_mode_banner.setVisible(not editable)
        for cell in self.cells:
            cell.set_editable(editable)
        self.editableChanged.emit(editable)

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Prominent View Mode banner (appears when document is in read-only / view mode)
        self.view_mode_banner = QFrame(self)
        self.view_mode_banner.setObjectName("viewModeBanner")
        self.view_mode_banner.setStyleSheet("""
            QFrame#viewModeBanner {
                background-color: #fef3c7;
                border-bottom: 1px solid #fcd34d;
            }
            QFrame#viewModeBanner QLabel {
                background: transparent;
                background-color: transparent;
            }
        """)
        banner_layout = QHBoxLayout(self.view_mode_banner)
        banner_layout.setContentsMargins(16, 6, 16, 6)
        banner_layout.setSpacing(10)

        lbl_lock = QLabel("🔒", self.view_mode_banner)
        lbl_lock.setStyleSheet("font-size: 13px; background: transparent;")
        banner_layout.addWidget(lbl_lock)

        lbl_msg = QLabel("VIEW MODE: This document is read-only. Editing and calculations are locked.", self.view_mode_banner)
        lbl_msg.setStyleSheet("font-size: 11px; font-weight: bold; color: #92400e; background: transparent;")
        banner_layout.addWidget(lbl_msg, 1)

        self.btn_enable_edit = QPushButton("Enable Editing", self.view_mode_banner)
        self.btn_enable_edit.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_enable_edit.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                color: #ffffff;
                font-weight: bold;
                font-size: 11px;
                padding: 4px 14px;
                border-radius: 4px;
                border: 1px solid #1d4ed8;
            }
            QPushButton:hover {
                background-color: #1d4ed8;
            }
            QPushButton:pressed {
                background-color: #1e40af;
            }
        """)
        self.btn_enable_edit.clicked.connect(lambda: self.set_editable(True))
        banner_layout.addWidget(self.btn_enable_edit)

        self.view_mode_banner.setVisible(not self.is_editable)
        main_layout.addWidget(self.view_mode_banner)

        # Scroll Area for continuous document page
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self._apply_scroll_area_style()
        self.scroll_area.verticalScrollBar().setSingleStep(30)

        self.container = WorksheetContainer(self)
        self.cells_layout = QVBoxLayout(self.container)
        self.cells_layout.setContentsMargins(12, 16, 24, 24)
        self.cells_layout.setSpacing(6)
        self.cells_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.scroll_area.setWidget(self.container)
        self.scroll_area.installEventFilter(self)
        self.scroll_area.viewport().installEventFilter(self)
        self.container.installEventFilter(self)
        main_layout.addWidget(self.scroll_area)

        # Add initial empty execution group
        self.add_cell()

    def _apply_scroll_area_style(self):
        is_dark = (getattr(self, 'theme_mode', 'light') == 'dark')
        bg_col = "#18202e" if is_dark else "#ffffff"
        if hasattr(self, 'container') and self.container:
            self.container.setStyleSheet(f"background-color: {bg_col};")
        if is_dark:
            self.scroll_area.setStyleSheet(f"""
                QScrollArea {{
                    background-color: {bg_col};
                    border: none;
                }}
                QScrollBar:vertical {{
                    border: none;
                    border-left: 1px solid #2b384c;
                    background: #16202c;
                    width: 16px;
                    margin: 0px;
                }}
                QScrollBar::handle:vertical {{
                    background: #475569;
                    min-height: 36px;
                    border-radius: 5px;
                    margin: 2px;
                }}
                QScrollBar::handle:vertical:hover {{
                    background: #64748b;
                }}
                QScrollBar::handle:vertical:pressed {{
                    background: #94a3b8;
                }}
                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                    height: 0px;
                    background: none;
                }}
                QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                    background: none;
                }}
            """)
        else:
            self.scroll_area.setStyleSheet(f"""
                QScrollArea {{
                    background-color: #ffffff;
                    border: none;
                }}
                QScrollBar:vertical {{
                    border: none;
                    border-left: 1px solid #e2e8f0;
                    background: #f8fafc;
                    width: 16px;
                    margin: 0px;
                }}
                QScrollBar::handle:vertical {{
                    background: #94a3b8;
                    min-height: 36px;
                    border-radius: 5px;
                    margin: 2px;
                }}
                QScrollBar::handle:vertical:hover {{
                    background: #64748b;
                }}
                QScrollBar::handle:vertical:pressed {{
                    background: #334155;
                }}
                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                    height: 0px;
                    background: none;
                }}
                QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                    background: none;
                }}
            """)

    def set_theme_mode(self, mode: str):
        self.theme_mode = mode
        self._apply_scroll_area_style()
        for cell in self.cells:
            if hasattr(cell, 'set_theme_mode'):
                cell.set_theme_mode(mode)

    def set_worksheet_mode(self, is_ws_mode: bool):
        """Switch between Worksheet Mode ('>' prompts & brackets) and Document Mode (clean free-form math)."""
        self.is_worksheet_mode = is_ws_mode
        for cell in self.cells:
            cell.set_worksheet_mode(is_ws_mode)

    def set_zoom(self, percent: int):
        """Scale document zoom level without altering underlying font sizes."""
        self.zoom_percent = max(25, min(500, int(percent)))
        self._smooth_zoom = float(self.zoom_percent)
        factor = self.zoom_percent / 100.0
        self.setUpdatesEnabled(False)
        if hasattr(self, 'container') and self.container:
            self.container.setUpdatesEnabled(False)
        try:
            for cell in self.cells:
                cell.set_zoom_factor(factor)
        finally:
            if hasattr(self, 'container') and self.container:
                self.container.setUpdatesEnabled(True)
            self.setUpdatesEnabled(True)
        self.zoomChanged.emit(self.zoom_percent)
        self.statusMessage.emit(f"Zoom: {self.zoom_percent}%", 1500)

    def zoom_in(self, step: int = 25):
        """Zoom in by step percent."""
        self.set_zoom(self.zoom_percent + step)

    def zoom_out(self, step: int = 25):
        """Zoom out by step percent."""
        self.set_zoom(self.zoom_percent - step)

    def zoom_reset(self):
        """Reset zoom to standard 100%."""
        self.set_zoom(100)

    def handle_native_gesture_zoom(self, event) -> bool:
        """Handle trackpad pinch-to-zoom and smart-zoom gestures."""
        try:
            gt = event.gestureType()
        except Exception:
            return False

        if gt == Qt.NativeGestureType.ZoomNativeGesture:
            delta = event.value()
            if abs(delta) < 0.0001:
                return True
            if not hasattr(self, '_smooth_zoom'):
                self._smooth_zoom = float(self.zoom_percent)
            self._smooth_zoom = max(25.0, min(500.0, self._smooth_zoom * (1.0 + delta * 1.5)))
            new_pct = int(round(self._smooth_zoom))
            if new_pct != self.zoom_percent:
                self.set_zoom(new_pct)
            return True
        elif gt == Qt.NativeGestureType.SmartZoomNativeGesture:
            if abs(self.zoom_percent - 100) < 5:
                self.set_zoom(150)
            else:
                self.set_zoom(100)
            return True
        return False

    def handle_wheel_zoom(self, event: QWheelEvent) -> bool:
        """Handle Ctrl/Cmd + touchpad two-finger scroll or mouse wheel zoom."""
        mods = event.modifiers()
        if mods & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier):
            p_delta = event.pixelDelta().y()
            a_delta = event.angleDelta().y()

            if p_delta != 0:
                if not hasattr(self, '_smooth_zoom'):
                    self._smooth_zoom = float(self.zoom_percent)
                self._smooth_zoom = max(25.0, min(500.0, self._smooth_zoom + p_delta * 0.5))
                new_pct = int(round(self._smooth_zoom))
            elif a_delta != 0:
                step = 10 if a_delta > 0 else -10
                new_pct = max(25, min(500, self.zoom_percent + step))
                self._smooth_zoom = float(new_pct)
            else:
                return False

            if new_pct != self.zoom_percent:
                self.set_zoom(new_pct)
            event.accept()
            return True
        return False

    def _on_cell_text_changed(self):
        if not getattr(self, '_is_loading', False) and not getattr(self, '_is_undo_redo', False):
            import time
            self._last_text_edit_time = time.time()

    def _create_cell_from_dict(self, cdata: dict) -> WorksheetCell:
        self.execution_counter += 1
        cell = WorksheetCell(
            execution_idx=cdata.get('execution_idx', self.execution_counter),
            theme_mode=self.theme_mode,
            font_size=self.default_font_size,
            font_family=self.default_font_family,
            engine=self.engine,
            parent=self.container
        )
        cell.parent_worksheet = self
        cell.set_worksheet_mode(self.is_worksheet_mode)
        cell.set_zoom_factor(self.zoom_percent / 100.0)
        cell.set_line_spacing(self.default_line_spacing)
        cell.set_editable(self.is_editable)

        cell.installEventFilter(self)
        if hasattr(cell, 'input_edit') and cell.input_edit:
            cell.input_edit.installEventFilter(self)
            try:
                cell.input_edit.textChanged.connect(self._on_cell_text_changed)
            except Exception:
                pass
        if hasattr(cell, 'title_edit') and cell.title_edit:
            cell.title_edit.installEventFilter(self)
            try:
                cell.title_edit.textChanged.connect(self._on_cell_text_changed)
            except Exception:
                pass

        cell.executeRequested.connect(self._on_cell_execute_requested)
        cell.deleteRequested.connect(self.delete_cell)
        cell.insertBelowRequested.connect(self._handle_insert_request)
        cell.plotRequested.connect(self.plotRequested.emit)
        cell.focusNextRequested.connect(self._focus_next_cell)
        cell.focusPrevRequested.connect(self._focus_prev_cell)
        cell.cellActivated.connect(self._on_cell_activated)
        cell.sectionToggled.connect(self._on_section_toggled)

        cell.from_dict(cdata)
        return cell

    def ensure_cell_visible(self, cell, delay_ms: int = 50, xmargin: int = 50, ymargin: int = 50):
        """Scroll the scroll area to ensure the given cell is visible after layout updates."""
        if not cell:
            return
        def _scroll():
            try:
                from PyQt6 import sip
                if not sip.isdeleted(self) and not sip.isdeleted(self.scroll_area) and not sip.isdeleted(cell):
                    self.scroll_area.ensureWidgetVisible(cell, xmargin, ymargin)
            except (RuntimeError, AttributeError, ReferenceError):
                pass
        if delay_ms > 0:
            QTimer.singleShot(delay_ms, _scroll)
        else:
            _scroll()

    def add_cell(self, expression: str = "", insert_after_id: str = None, focus: bool = True) -> WorksheetCell:
        """Create and insert a new execution block."""
        self.execution_counter += 1
        cell = WorksheetCell(
            execution_idx=self.execution_counter,
            theme_mode=self.theme_mode,
            font_size=self.default_font_size,
            font_family=self.default_font_family,
            engine=self.engine,
            parent=self.container
        )
        cell.set_worksheet_mode(self.is_worksheet_mode)
        cell.set_zoom_factor(self.zoom_percent / 100.0)
        cell.set_line_spacing(self.default_line_spacing)
        cell.parent_worksheet = self
        if getattr(self, 'current_text_color', None):
            cell.set_text_color(self.current_text_color)
        if getattr(self, 'current_highlight_color', None):
            cell.set_highlight_color(self.current_highlight_color)
        cell.installEventFilter(self)
        cell.input_edit.installEventFilter(self)
        try:
            cell.input_edit.textChanged.connect(self._on_cell_text_changed)
        except Exception:
            pass
        if expression:
            cell.set_input_text(expression)

        cell.executeRequested.connect(self._on_cell_execute_requested)
        cell.deleteRequested.connect(self.delete_cell)
        cell.insertBelowRequested.connect(self._handle_insert_request)
        cell.plotRequested.connect(self.plotRequested.emit)
        cell.focusNextRequested.connect(self._focus_next_cell)
        cell.focusPrevRequested.connect(self._focus_prev_cell)
        cell.cellActivated.connect(self._on_cell_activated)
        cell.sectionToggled.connect(self._on_section_toggled)

        if insert_after_id:
            if insert_after_id.startswith("before_"):
                actual_id = insert_after_id[len("before_"):]
                idx = self._get_cell_index_by_id(actual_id)
                if idx != -1:
                    self.cells.insert(idx, cell)
                    self.cells_layout.insertWidget(idx, cell)
                else:
                    self.cells.append(cell)
                    self.cells_layout.addWidget(cell)
            else:
                idx = self._get_cell_index_by_id(insert_after_id)
                if idx != -1:
                    self.cells.insert(idx + 1, cell)
                    self.cells_layout.insertWidget(idx + 1, cell)
                else:
                    self.cells.append(cell)
                    self.cells_layout.addWidget(cell)
        else:
            self.cells.append(cell)
            self.cells_layout.addWidget(cell)

        if not getattr(self, '_is_loading', False):
            self.active_cell = cell
            self.activeCellChanged.emit(cell)
            self.renumber_equation_labels()
            self.cellCountChanged.emit(len(self.cells))
            self.update_section_hierarchy()

        if focus:
            try:
                if not sip.isdeleted(cell) and hasattr(cell, 'input_edit') and not sip.isdeleted(cell.input_edit):
                    cell.input_edit.setFocus()
            except (RuntimeError, AttributeError, ReferenceError):
                pass
            self.ensure_cell_visible(cell)
        return cell

    def _handle_insert_request(self, target_id: str):
        if not self.is_editable:
            return
        self.add_cell(insert_after_id=target_id)

    def _on_cell_activated(self, cell_id: str, expression: str):
        cell = self._get_cell_by_id(cell_id)
        if cell:
            self.active_cell = cell
            self.activeCellChanged.emit(cell)

    def delete_cell(self, cell_id: str):
        """Remove an execution block or section from the worksheet with undo/redo."""
        if not self.is_editable:
            return
        cell = self._get_cell_by_id(cell_id)
        if cell and not getattr(cell, 'is_section_header', False) and self.is_only_content_in_section(cell):
            cell.set_input_text("")
            cell.clear_output()
            self.clear_cell_selection()
            cell.set_cell_focus()
            return
        self.delete_cells([cell_id])

    def clear_all_table_overlays(self, except_cell=None):
        """Clear table outlines and overlays across all cells."""
        for c in getattr(self, 'cells', []):
            if c is except_cell:
                continue
            try:
                if not sip.isdeleted(c) and hasattr(c, 'input_edit') and c.input_edit:
                    if getattr(c.input_edit, '_selected_table', None) is not None or getattr(c.input_edit, '_active_table', None) is not None:
                        c.input_edit._selected_table = None
                        c.input_edit._active_table = None
                        c.input_edit.viewport().update()
            except Exception:
                pass

    def clear_cell_selection(self):
        """Deselect all currently selected cells."""
        for c in list(getattr(self, 'selected_cells', [])):
            try:
                if not sip.isdeleted(c) and hasattr(c, 'set_cell_selected'):
                    c.set_cell_selected(False)
            except Exception:
                pass
        self.clear_all_table_overlays()
        if hasattr(self, 'selected_cells'):
            self.selected_cells.clear()

    def select_cell(self, cell: WorksheetCell, additive: bool = False, range_select: bool = False):
        """Select a cell with support for Ctrl (additive) and Shift (range) multi-selection."""
        if not cell or cell not in self.cells:
            return

        if range_select and self.active_cell and self.active_cell in self.cells:
            start_idx = self.cells.index(self.active_cell)
            end_idx = self.cells.index(cell)
            lo, hi = min(start_idx, end_idx), max(start_idx, end_idx)
            self.clear_cell_selection()
            for i in range(lo, hi + 1):
                c = self.cells[i]
                c.set_cell_selected(True)
                self.selected_cells.append(c)
        elif additive:
            if cell in self.selected_cells:
                cell.set_cell_selected(False)
                self.selected_cells.remove(cell)
            else:
                cell.set_cell_selected(True)
                self.selected_cells.append(cell)
        else:
            self.clear_cell_selection()
            cell.set_cell_selected(True)
            self.selected_cells.append(cell)

        self.active_cell = cell
        self.activeCellChanged.emit(cell)

    def select_range(self, start_cell: WorksheetCell, end_cell: WorksheetCell):
        """Select all cells in the range between start_cell and end_cell."""
        if not start_cell or not end_cell or start_cell not in self.cells or end_cell not in self.cells:
            return
        start_idx = self.cells.index(start_cell)
        end_idx = self.cells.index(end_cell)
        lo, hi = min(start_idx, end_idx), max(start_idx, end_idx)
        self.clear_cell_selection()
        for i in range(lo, hi + 1):
            c = self.cells[i]
            c.set_cell_selected(True)
            self.selected_cells.append(c)
        self.active_cell = end_cell
        self.activeCellChanged.emit(end_cell)

    def select_all_cells(self):
        """Select all execution groups / statements in the worksheet."""
        self.clear_cell_selection()
        for cell in self.cells:
            cell.set_cell_selected(True)
            self.selected_cells.append(cell)
        if self.selected_cells:
            self.active_cell = self.selected_cells[-1]
            self.activeCellChanged.emit(self.active_cell)
            self.statusMessage.emit(f"Selected all {len(self.selected_cells)} statements", 2000)

    def copy_selected_cells(self):
        """Copy selected cells to clipboard as plain text and rich OpenMath cell data."""
        if not getattr(self, 'selected_cells', None):
            if self.active_cell:
                cells_to_copy = [self.active_cell]
            else:
                return
        else:
            # Preserve chronological document order
            cells_to_copy = [c for c in self.cells if c in self.selected_cells]

        if not cells_to_copy:
            return

        texts = []
        for c in cells_to_copy:
            if getattr(c, 'is_section_header', False):
                t = getattr(c, 'section_title', '')
            else:
                t = c.get_input_text()
            texts.append(t)

        plain_text = "\n".join(texts)
        cells_data = [c.to_dict() for c in cells_to_copy]
        json_str = json.dumps(cells_data)

        mime = QMimeData()
        mime.setText(plain_text)
        mime.setData("application/x-openmath-cells", json_str.encode('utf-8'))
        QApplication.clipboard().setMimeData(mime)
        self.statusMessage.emit(f"Copied {len(cells_to_copy)} statement(s) to clipboard", 2500)

    def cut_selected_cells(self):
        """Cut selected cells to clipboard and remove them from worksheet."""
        if not self.is_editable:
            return
        count = len(self.selected_cells) if getattr(self, 'selected_cells', None) else 1
        self.copy_selected_cells()
        self.delete_selected_cells()
        self.statusMessage.emit(f"Cut {count} statement(s)", 2500)

    def paste_cells(self) -> bool:
        """Paste cells or multi-statement text from clipboard into worksheet."""
        if not self.is_editable:
            return False
        clipboard = QApplication.clipboard()
        mime = clipboard.mimeData()
        if not mime:
            return False

        # 1. Check for rich OpenMath cell data
        if mime.hasFormat("application/x-openmath-cells"):
            raw_bytes = mime.data("application/x-openmath-cells")
            try:
                cells_data = json.loads(bytes(raw_bytes).decode('utf-8'))
            except Exception:
                cells_data = None

            if cells_data and isinstance(cells_data, list):
                self.undo_stack.beginMacro("Paste Statement(s)")
                try:
                    insert_idx = len(self.cells)
                    if getattr(self, 'selected_cells', None) and len(self.selected_cells) > 0:
                        first_sel = next((c for c in self.cells if c in self.selected_cells), None)
                        if first_sel:
                            insert_idx = self.cells.index(first_sel)
                        self.delete_selected_cells()
                    elif self.active_cell and self.active_cell in self.cells:
                        act_idx = self.cells.index(self.active_cell)
                        if len(self.cells) == 1 and not self.cells[0].get_input_text().strip() and not getattr(self.cells[0], 'is_section_header', False):
                            insert_idx = 0
                            c = self.cells.pop(0)
                            self.cells_layout.removeWidget(c)
                            c.deleteLater()
                        elif not self.active_cell.get_input_text().strip():
                            insert_idx = act_idx
                            self.delete_cell(self.active_cell.cell_id)
                        else:
                            insert_idx = act_idx + 1

                    inserted_items = []
                    for i, c_data in enumerate(cells_data):
                        target_pos = insert_idx + i
                        c_data_copy = dict(c_data)
                        c_data_copy['cell_id'] = str(uuid.uuid4())
                        c_data_copy['execution_idx'] = self.execution_counter + i + 1
                        inserted_items.append((target_pos, c_data_copy))

                    cmd = InsertCellsCommand(self, inserted_items, description="Paste Statement(s)")
                    self.undo_stack.push(cmd)
                    self.execution_counter += len(inserted_items)
                    self.statusMessage.emit(f"Pasted {len(inserted_items)} statement(s)", 2500)
                    return True
                finally:
                    self.undo_stack.endMacro()

        # 2. If multi-cell selection is active and plain text is pasted:
        if getattr(self, 'selected_cells', None) and len(self.selected_cells) > 1 and mime.hasText():
            text = mime.text()
            lines = [line for line in text.splitlines() if line.strip()]
            if len(lines) > 1:
                first_sel = next((c for c in self.cells if c in self.selected_cells), None)
                insert_idx = self.cells.index(first_sel) if first_sel else len(self.cells)
                mode = first_sel.input_mode if first_sel else "2d_math"
                self.undo_stack.beginMacro("Paste Text Lines")
                try:
                    self.delete_selected_cells()
                    inserted_items = []
                    for i, line in enumerate(lines):
                        cdict = {
                            'cell_id': str(uuid.uuid4()),
                            'execution_idx': self.execution_counter + i + 1,
                            'input': line,
                            'input_mode': mode,
                        }
                        inserted_items.append((insert_idx + i, cdict))
                    cmd = InsertCellsCommand(self, inserted_items, description="Paste Text Lines")
                    self.undo_stack.push(cmd)
                    self.execution_counter += len(inserted_items)
                    return True
                finally:
                    self.undo_stack.endMacro()
            else:
                self.delete_selected_cells()
                if self.active_cell and hasattr(self.active_cell, 'input_edit'):
                    self.active_cell.input_edit.insertPlainText(text)
                return True

        return False

    def delete_selected_cells(self):
        """Delete all cells currently selected."""
        if not self.is_editable:
            return
        if getattr(self, 'selected_cells', None):
            cell_ids = [c.cell_id for c in list(self.selected_cells) if c in self.cells]
            if cell_ids:
                self.delete_cells(cell_ids)
                return
        if self.active_cell and self.active_cell in self.cells:
            self.delete_cells([self.active_cell.cell_id])

    def delete_cells(self, cell_ids: list):
        """Batch remove execution blocks / sections from worksheet with full undo/redo."""
        if not self.is_editable or not cell_ids:
            return
        if getattr(self, '_is_undo_redo', False):
            return

        if len(cell_ids) == 1:
            c = self._get_cell_by_id(cell_ids[0])
            if c and not getattr(c, 'is_section_header', False) and self.is_only_content_in_section(c):
                c.set_input_text("")
                c.clear_output()
                self.clear_cell_selection()
                c.set_cell_focus()
                return

        cell_items = []
        for cid in cell_ids:
            idx = self._get_cell_index_by_id(cid)
            if idx != -1:
                cell_items.append((idx, self.cells[idx].to_dict()))

        if not cell_items:
            return

        cell_items.sort(key=lambda item: item[0])
        cmd = DeleteCellsCommand(self, cell_items)
        self.undo_stack.push(cmd)

    def insert_cell_below(self, cell_id: str = None) -> WorksheetCell:
        """Insert an execution block below the specified cell and focus it with undo support."""
        if not self.is_editable:
            return None
        if not cell_id and self.active_cell:
            cell_id = self.active_cell.cell_id
        target_pos = len(self.cells)
        sec_level = 0
        is_inside = False
        ref_mode = 0
        if cell_id:
            idx = self._get_cell_index_by_id(cell_id)
            if idx != -1:
                target_pos = idx + 1
                ref_cell = self.cells[idx]
                ref_mode = getattr(ref_cell, 'input_mode', 0)
                if getattr(ref_cell, 'is_section_header', False):
                    sec_level = getattr(ref_cell, 'section_level', 0)
                    is_inside = True
                else:
                    sec_level = getattr(ref_cell, 'section_level', 0)
                    is_inside = getattr(ref_cell, 'is_inside_section', False)
        elif self.cells:
            ref_cell = self.cells[-1]
            ref_mode = getattr(ref_cell, 'input_mode', 0)
            sec_level = getattr(ref_cell, 'section_level', 0)
            is_inside = getattr(ref_cell, 'is_inside_section', False)

        self.execution_counter += 1
        cdict = {
            'cell_id': str(uuid.uuid4()),
            'execution_idx': self.execution_counter,
            'input': '',
            'input_mode': ref_mode,
            'is_worksheet_mode': self.is_worksheet_mode,
            'is_inside_section': is_inside,
            'section_level': sec_level,
        }
        cmd = InsertCellsCommand(self, [(target_pos, cdict)], description="Insert Statement")
        self.undo_stack.push(cmd)
        return self.active_cell

    def insert_cell_outside_section(self, cell_id: str = None) -> WorksheetCell:
        """Insert an execution block below that is outside of the current section."""
        if not self.is_editable:
            return None
        if not cell_id and self.active_cell:
            cell_id = self.active_cell.cell_id
        target_pos = len(self.cells)
        ref_cell = None
        if cell_id:
            idx = self._get_cell_index_by_id(cell_id)
            if idx != -1:
                target_pos = idx + 1
                ref_cell = self.cells[idx]
        elif self.cells:
            ref_cell = self.cells[-1]
        ref_mode = getattr(ref_cell, 'input_mode', 0) if ref_cell else 0
        self.execution_counter += 1
        cdict = {
            'cell_id': str(uuid.uuid4()),
            'execution_idx': self.execution_counter,
            'input': '',
            'input_mode': ref_mode,
            'is_worksheet_mode': self.is_worksheet_mode,
            'is_inside_section': False,
            'is_outside_section': True,
            'section_level': 0,
        }
        cmd = InsertCellsCommand(self, [(target_pos, cdict)], description="Insert Statement Outside Section")
        self.undo_stack.push(cmd)
        self.update_section_hierarchy()
        return self.active_cell

    def outdent_active_cell(self):
        """Outdent active cell (exit subsection -> exit section)."""
        if not self.active_cell:
            return
        if getattr(self.active_cell, 'is_section_header', False):
            self.active_cell.outdent_section()
        else:
            self.active_cell.outdent_cell()
        self.ensure_section_content()
        self.update_section_hierarchy()
        if hasattr(self, 'container') and hasattr(self.container, 'overlay'):
            self.container.overlay.update()

    def indent_active_cell(self):
        """Indent active cell (into subsection / deeper section level)."""
        if not self.active_cell:
            return
        if getattr(self.active_cell, 'is_section_header', False):
            self.active_cell.indent_section()
        else:
            self.active_cell.indent_cell()
        self.update_section_hierarchy()
        if hasattr(self, 'container') and hasattr(self.container, 'overlay'):
            self.container.overlay.update()

    def insert_section_cell(self, title: str = "", level: int = None, insert_after_id: str = None) -> WorksheetCell:
        """Create and insert a collapsible section header cell with undo support."""
        if not self.is_editable:
            return None

        if not insert_after_id and self.active_cell:
            insert_after_id = self.active_cell.cell_id

        # Determine nesting level: if level is None, inherit from active or surrounding cell
        if level is None:
            if self.active_cell:
                level = getattr(self.active_cell, 'section_level', 0)
            else:
                level = 0

        self.execution_counter += 1
        target_pos = len(self.cells)
        if insert_after_id:
            if insert_after_id.startswith("before_"):
                actual_id = insert_after_id[len("before_"):]
                idx = self._get_cell_index_by_id(actual_id)
                if idx != -1:
                    target_pos = idx
            else:
                idx = self._get_cell_index_by_id(insert_after_id)
                if idx != -1:
                    target_pos = idx + 1

        sec_level = max(0, level)
        cdict = {
            'cell_id': str(uuid.uuid4()),
            'execution_idx': self.execution_counter,
            'is_section_header': True,
            'section_title': title,
            'section_level': sec_level,
            'is_collapsed': False,
            'input': '',
            'input_mode': 0,
            'is_worksheet_mode': self.is_worksheet_mode,
        }
        self.execution_counter += 1
        child_dict = {
            'cell_id': str(uuid.uuid4()),
            'execution_idx': self.execution_counter,
            'input': '',
            'input_mode': 0,
            'is_worksheet_mode': self.is_worksheet_mode,
            'is_inside_section': True,
            'section_level': sec_level,
        }
        cmd = InsertCellsCommand(self, [(target_pos, cdict), (target_pos + 1, child_dict)], description="Insert Section")
        self.undo_stack.push(cmd)
        sec_cell = self._get_cell_by_id(cdict['cell_id'])
        if sec_cell:
            self.active_cell = sec_cell
            self.activeCellChanged.emit(sec_cell)
            if hasattr(sec_cell, 'title_edit'):
                sec_cell.title_edit.setFocus()
            return sec_cell
        return self.active_cell

    def update_section_hierarchy(self):
        """Update section nesting hierarchy, indentation, and tree scope lines."""
        section_stack = []

        for cell in self.cells:
            try:
                import sip
                if sip.isdeleted(cell):
                    continue
            except Exception:
                pass

            if getattr(cell, 'is_section_header', False):
                lvl = max(0, getattr(cell, 'section_level', 0))
                while section_stack and section_stack[-1] >= lvl:
                    section_stack.pop()
                section_stack.append(lvl)
                cell.is_inside_section = bool(len(section_stack) > 1)
                cell._apply_indentation()
                if not getattr(cell, '_is_lazy', False) and getattr(cell, '_title_edit', None) is not None:
                    cell.title_edit._update_style()
            else:
                if getattr(cell, '_is_outside_section', False):
                    section_stack.clear()
                    cell.section_level = 0
                    cell.is_inside_section = False
                elif section_stack:
                    cell.section_level = section_stack[-1]
                    cell.is_inside_section = True
                else:
                    cell.section_level = 0
                    cell.is_inside_section = False
                cell._apply_indentation()

        if hasattr(self, 'container') and hasattr(self.container, 'overlay'):
            self.container.overlay.update()

    def get_parent_section_for_cell(self, cell: WorksheetCell):
        """Return the section header cell that owns this cell, or None if at root."""
        if not cell or cell not in self.cells or getattr(cell, 'is_section_header', False):
            return None
        if getattr(cell, '_is_outside_section', False) or not getattr(cell, 'is_inside_section', False):
            return None
        idx = self.cells.index(cell)
        sec_level = getattr(cell, 'section_level', 0)
        for i in range(idx - 1, -1, -1):
            c = self.cells[i]
            if getattr(c, 'is_section_header', False) and getattr(c, 'section_level', 0) <= sec_level:
                return c
        return None

    def get_section_content_cells(self, section_header: WorksheetCell) -> list:
        """Return all non-section content cells directly or indirectly belonging to section_header."""
        if not section_header or section_header not in self.cells:
            return []
        idx = self.cells.index(section_header)
        sec_level = getattr(section_header, 'section_level', 0)
        content_cells = []
        for c in self.cells[idx + 1:]:
            if getattr(c, 'is_section_header', False):
                if getattr(c, 'section_level', 0) <= sec_level:
                    break
            else:
                if getattr(c, '_is_outside_section', False) or getattr(c, 'section_level', 0) < sec_level:
                    break
                content_cells.append(c)
        return content_cells

    def is_only_content_in_section(self, cell: WorksheetCell) -> bool:
        """Check if cell is the sole content cell of its enclosing section/subsection."""
        sec = self.get_parent_section_for_cell(cell)
        if not sec:
            return False
        contents = self.get_section_content_cells(sec)
        return len(contents) <= 1

    def ensure_section_content(self):
        """Ensure every section and subsection has at least one content cell inside it."""
        if not self.cells or getattr(self, '_is_loading', False) or getattr(self, '_ensuring_content', False):
            return

        self._ensuring_content = True
        try:
            i = 0
            added = False
            while i < len(self.cells):
                cell = self.cells[i]
                if getattr(cell, 'is_section_header', False):
                    sec_level = getattr(cell, 'section_level', 0)
                    has_child = False
                    for next_cell in self.cells[i + 1:]:
                        if getattr(next_cell, 'is_section_header', False):
                            if getattr(next_cell, 'section_level', 0) > sec_level:
                                has_child = True
                            break
                        else:
                            if not getattr(next_cell, '_is_outside_section', False) and getattr(next_cell, 'section_level', 0) >= sec_level:
                                has_child = True
                            break

                    if not has_child:
                        self.execution_counter += 1
                        placeholder = self._create_cell_from_dict({
                            'cell_id': str(uuid.uuid4()),
                            'execution_idx': self.execution_counter,
                            'input': '',
                            'input_mode': 0,
                            'is_worksheet_mode': self.is_worksheet_mode,
                            'is_inside_section': True,
                            'section_level': sec_level,
                            'is_outside_section': False,
                        })
                        insert_pos = i + 1
                        if insert_pos < len(self.cells):
                            self.cells.insert(insert_pos, placeholder)
                            self.cells_layout.insertWidget(insert_pos, placeholder)
                        else:
                            self.cells.append(placeholder)
                            self.cells_layout.addWidget(placeholder)
                        added = True
                        i += 1
                i += 1

            if added:
                self.renumber_equation_labels()
                self.cellCountChanged.emit(len(self.cells))
        finally:
            self._ensuring_content = False

    def renumber_equation_labels(self):
        """Update (1), (2), (3)... equation labels in order."""
        eq_num = 1
        for cell in self.cells:
            cell.set_execution_idx(eq_num)
            eq_num += 1

    def insert_template_to_active(self, template_str: str):
        """Insert a template into currently focused cell."""
        if not self.is_editable:
            return
        if self.active_cell is None and self.cells:
            self.active_cell = self.cells[-1]

        if self.active_cell:
            self.active_cell.insert_template(template_str)

    def _get_cell_by_id(self, cell_id: str) -> WorksheetCell:
        for c in self.cells:
            if c.cell_id == cell_id:
                return c
        return None

    def _get_cell_index_by_id(self, cell_id: str) -> int:
        for i, c in enumerate(self.cells):
            if c.cell_id == cell_id:
                return i
        return -1

    def _on_cell_execute_requested(self, cell_id: str, expression: str):
        """Trigger async evaluation for the execution group."""
        cell = self._get_cell_by_id(cell_id)
        if not cell:
            return
        self.runner.run_calculation(cell_id, expression, precision=10)

    def _on_cell_calc_finished(self, cell_id: str, result: CASResult):
        cell = self._get_cell_by_id(cell_id)
        if not cell:
            return

        cell.set_result(result)
        self.renumber_equation_labels()
        self.statusMessage.emit(f"Evaluated in {result.execution_time_ms:.1f}ms", 3000)
        self.executionTimeChanged.emit(result.execution_time_ms / 1000.0)

        is_load_eval = cell_id in getattr(self, '_loading_cell_ids', set())
        if is_load_eval:
            self._loading_cell_ids.discard(cell_id)

        # Automatically advance focus to next cell or insert empty execution group below if at bottom
        if not is_load_eval and not cell.get_input_text().startswith("?"):
            self._focus_next_cell(cell_id)

    def _on_cell_calc_error(self, cell_id: str, title: str, details: str):
        if hasattr(self, '_loading_cell_ids'):
            self._loading_cell_ids.discard(cell_id)
        cell = self._get_cell_by_id(cell_id)
        if not cell:
            return
        cell.set_error(title, details)
        self.statusMessage.emit(f"Error: {details or title}", 4000)

    def _focus_next_cell(self, cell_id: str):
        idx = self._get_cell_index_by_id(cell_id)
        curr = self.cells[idx] if 0 <= idx < len(self.cells) else None
        curr_is_sec = getattr(curr, 'is_section_header', False)
        curr_lvl = getattr(curr, 'section_level', 0)
        curr_inside = getattr(curr, 'is_inside_section', False) or curr_is_sec

        if idx != -1 and idx < len(self.cells) - 1:
            next_cell = self.cells[idx + 1]
            next_is_sec = getattr(next_cell, 'is_section_header', False)
            next_lvl = getattr(next_cell, 'section_level', 0)
            next_inside = getattr(next_cell, 'is_inside_section', False)

            # If current cell is inside a section/subsection, but next cell is outside or in an outer section:
            # staying inside means inserting a new cell inside the section below curr
            if curr_inside and (not next_inside or (next_is_sec and next_lvl <= curr_lvl) or next_lvl < curr_lvl):
                if curr.get_input_text().strip() or curr_is_sec:
                    new_cell = self.insert_cell_below(curr.cell_id)
                    if new_cell:
                        try:
                            if not sip.isdeleted(new_cell) and hasattr(new_cell, 'input_edit') and not sip.isdeleted(new_cell.input_edit):
                                new_cell.input_edit.setFocus()
                            self.active_cell = new_cell
                            self.activeCellChanged.emit(new_cell)
                            self.ensure_cell_visible(new_cell)
                        except (RuntimeError, AttributeError, ReferenceError):
                            pass
                        return

            try:
                if not sip.isdeleted(next_cell) and hasattr(next_cell, 'input_edit') and not sip.isdeleted(next_cell.input_edit):
                    next_cell.input_edit.setFocus()
                    cur = next_cell.input_edit.textCursor()
                    cur.movePosition(QTextCursor.MoveOperation.Start)
                    next_cell.input_edit.setTextCursor(cur)
                    self.active_cell = next_cell
                    self.activeCellChanged.emit(next_cell)
                    self.ensure_cell_visible(next_cell)
            except (RuntimeError, AttributeError, ReferenceError):
                pass
        elif idx == len(self.cells) - 1:
            if curr and curr.get_input_text().strip():
                new_cell = self.insert_cell_below(curr.cell_id)
                if not new_cell:
                    new_cell = self.add_cell()
                try:
                    if not sip.isdeleted(new_cell) and hasattr(new_cell, 'input_edit') and not sip.isdeleted(new_cell.input_edit):
                        new_cell.input_edit.setFocus()
                    self.active_cell = new_cell
                    self.activeCellChanged.emit(new_cell)
                    self.ensure_cell_visible(new_cell)
                except (RuntimeError, AttributeError, ReferenceError):
                    pass

    def _focus_prev_cell(self, cell_id: str):
        idx = self._get_cell_index_by_id(cell_id)
        if idx > 0:
            prev_cell = self.cells[idx - 1]
            try:
                if not sip.isdeleted(prev_cell) and hasattr(prev_cell, 'input_edit') and not sip.isdeleted(prev_cell.input_edit):
                    prev_cell.input_edit.setFocus()
                    cur = prev_cell.input_edit.textCursor()
                    cur.movePosition(QTextCursor.MoveOperation.End)
                    prev_cell.input_edit.setTextCursor(cur)
                    self.active_cell = prev_cell
                    self.activeCellChanged.emit(prev_cell)
                    self.ensure_cell_visible(prev_cell)
            except (RuntimeError, AttributeError, ReferenceError):
                pass

    def set_active_cell_font_size(self, size: int):
        self.default_font_size = size
        if self.active_cell:
            self.active_cell.set_font_size(size)

    def set_active_cell_line_spacing(self, spacing: float):
        self.default_line_spacing = spacing
        if self.active_cell:
            self.active_cell.set_line_spacing(spacing)

    def set_active_cell_font_family(self, family: str):
        self.default_font_family = family
        if self.active_cell:
            self.active_cell.set_font_family(family)

    def _get_target_cells(self):
        target_cells = list(self.selected_cells) if getattr(self, 'selected_cells', None) else ([self.active_cell] if self.active_cell else [])
        if not target_cells:
            focused = QApplication.focusWidget()
            for cell in self.cells:
                if cell == focused or cell.isAncestorOf(focused):
                    target_cells = [cell]
                    self.active_cell = cell
                    break
        return target_cells

    def toggle_active_cell_bold(self):
        for cell in self._get_target_cells():
            if getattr(cell, 'is_section_header', False) and hasattr(cell, 'title_edit'):
                cur = (cell.title_edit.fontWeight() == QFont.Weight.Bold)
            else:
                cur = cell.input_edit.font().bold()
            cell.set_bold(not cur)

    def toggle_active_cell_italic(self):
        for cell in self._get_target_cells():
            if getattr(cell, 'is_section_header', False) and hasattr(cell, 'title_edit'):
                cur = cell.title_edit.fontItalic()
            else:
                cur = cell.input_edit.font().italic()
            cell.set_italic(not cur)

    def toggle_active_cell_underline(self):
        for cell in self._get_target_cells():
            if getattr(cell, 'is_section_header', False) and hasattr(cell, 'title_edit'):
                cur = cell.title_edit.fontUnderline()
            else:
                cur = cell.input_edit.font().underline()
            cell.set_underline(not cur)

    def set_active_cell_text_color(self, color):
        self.current_text_color = color if (color and color.isValid()) else None
        for cell in self._get_target_cells():
            cell.set_text_color(color)
        if getattr(self, 'selected_cells', None):
            self.clear_cell_selection()

    def set_active_cell_highlight_color(self, color):
        self.current_highlight_color = color if (color and color.isValid() and color.alpha() > 0) else None
        for cell in self._get_target_cells():
            cell.set_highlight_color(color)
        if getattr(self, 'selected_cells', None):
            self.clear_cell_selection()

    def clear_active_cell_text_color(self):
        self.current_text_color = None
        for cell in self._get_target_cells():
            cell.clear_text_color()
        if getattr(self, 'selected_cells', None):
            self.clear_cell_selection()

    def clear_active_cell_highlight_color(self):
        self.current_highlight_color = None
        for cell in self._get_target_cells():
            cell.clear_highlight_color()
        if getattr(self, 'selected_cells', None):
            self.clear_cell_selection()

    def run_all_cells(self):
        """Sequentially execute all cells in the worksheet (Execute All button)."""
        for cell in self.cells:
            text = cell.get_input_text()
            if text:
                cell.execute()

    def clear_worksheet(self):
        """Remove all cells and reset CAS engine."""
        if hasattr(self, 'undo_stack'):
            self.undo_stack.clear()
        for cell in list(self.cells):
            self.cells_layout.removeWidget(cell)
            cell.deleteLater()
        self.cells.clear()
        self.execution_counter = 0
        self.engine.reset()
        self.add_cell()
        self.statusMessage.emit("Worksheet restarted.", 3000)

    def _scroll_to_bottom(self):
        def _do_scroll():
            try:
                if not sip.isdeleted(self) and not sip.isdeleted(self.scroll_area):
                    sb = self.scroll_area.verticalScrollBar()
                    if not sip.isdeleted(sb):
                        sb.setValue(sb.maximum())
            except (RuntimeError, AttributeError, ReferenceError):
                pass
        QTimer.singleShot(100, _do_scroll)

    def export_to_latex_doc(self) -> str:
        lines = [
            r"\documentclass[11pt,a4paper]{article}",
            r"\usepackage{amsmath,amssymb,amsfonts}",
            r"\usepackage{geometry}",
            r"\geometry{margin=1in}",
            r"\usepackage{xcolor}",
            r"\title{Worksheet}",
            r"\date{\today}",
            r"\begin{document}",
            r"\maketitle",
            ""
        ]
        for cell in self.cells:
            inp = cell.get_input_text()
            if not inp:
                continue
            lines.append(r"\begin{flushleft}")
            lines.append(r"\texttt{> " + inp.replace("_", r"\_").replace("^", r"\textasciicircum ") + r"}")
            if cell.current_result:
                tex = cell.current_result.exact_latex or cell.current_result.numeric_latex
                lines.append(r"\begin{equation}")
                lines.append(tex)
                lines.append(r"\end{equation}")
            lines.append(r"\end{flushleft}")
            lines.append("")
        lines.append(r"\end{document}")
        return "\n".join(lines)

    def export_to_markdown(self) -> str:
        lines = ["# Worksheet Document\n"]
        for cell in self.cells:
            inp = cell.get_input_text()
            if not inp:
                continue
            lines.append(f"> `{inp}`\n")
            if cell.current_result:
                tex = cell.current_result.exact_latex or cell.current_result.numeric_latex
                lines.append(f"$${tex}$$ `({cell.execution_idx})`\n")
        return "\n".join(lines)

    def to_json(self) -> str:
        data = {
            'version': '2021',
            'is_worksheet_mode': self.is_worksheet_mode,
            'cells': [cell.to_dict() for cell in self.cells]
        }
        return json.dumps(data, indent=2)

    def _on_section_toggled(self, section_cell_id: str, is_collapsed: bool):
        """Collapse or expand all cells belonging to this section hierarchy."""
        idx = self._get_cell_index_by_id(section_cell_id)
        if idx == -1 or idx >= len(self.cells):
            return
        sec_cell = self.cells[idx]
        parent_level = getattr(sec_cell, 'section_level', 0)

        collapsed_sublevel = None
        for c in self.cells[idx + 1:]:
            if getattr(c, 'is_section_header', False):
                c_level = getattr(c, 'section_level', 0)
                if c_level <= parent_level:
                    # Exited current section hierarchy
                    break
                if is_collapsed:
                    c.setVisible(False)
                else:
                    if collapsed_sublevel is not None and c_level > collapsed_sublevel:
                        c.setVisible(False)
                    else:
                        c.setVisible(True)
                        if hasattr(c, 'input_edit'):
                            c.input_edit._adjust_height()
                        if getattr(c, 'is_collapsed', False):
                            collapsed_sublevel = c_level
                        else:
                            collapsed_sublevel = None
                continue

            if getattr(c, '_is_outside_section', False) or getattr(c, 'section_level', 0) < parent_level:
                break

            if is_collapsed:
                c.setVisible(False)
            else:
                if collapsed_sublevel is not None:
                    c.setVisible(False)
                else:
                    c.setVisible(True)
                    if hasattr(c, 'input_edit'):
                        c.input_edit._adjust_height()

        if hasattr(self, 'container') and hasattr(self.container, 'overlay'):
            self.container.overlay.update()

    def adjust_visible_cells_height(self):
        """Recalculate layout heights for all visible cells."""
        for cell in self.cells:
            if cell.isVisible() and hasattr(cell, 'input_edit'):
                cell.input_edit._adjust_height()
        if hasattr(self, 'container') and hasattr(self.container, 'overlay'):
            self.container.overlay.update()

    def expand_all_sections(self):
        """Unfold / expand all collapsible sections so all cells are shown."""
        for cell in self.cells:
            if getattr(cell, 'is_section_header', False):
                cell.is_collapsed = False
                if hasattr(cell, 'btn_section_toggle'):
                    cell.btn_section_toggle.set_collapsed(False)
            cell.setVisible(True)
            if hasattr(cell, 'input_edit'):
                cell.input_edit._adjust_height()
        if hasattr(self, 'container') and hasattr(self.container, 'overlay'):
            self.container.overlay.update()
        self.adjust_visible_cells_height()

    def has_sections(self) -> bool:
        """Return True if worksheet contains any section headers."""
        return any(getattr(c, 'is_section_header', False) for c in self.cells)

    def has_collapsed_sections(self) -> bool:
        """Return True if any section header is currently collapsed."""
        return any(getattr(c, 'is_section_header', False) and getattr(c, 'is_collapsed', False) for c in self.cells)

    def export_to_pdf(self, file_path: str):
        """Export the worksheet directly to a vector PDF document scaled to fill the entire A4 page."""
        from PyQt6.QtGui import QPdfWriter, QPainter, QPageSize, QPageLayout, QRegion
        from PyQt6.QtCore import QMarginsF, QPoint, QRect

        writer = QPdfWriter(file_path)
        writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        layout = QPageLayout(
            QPageSize(QPageSize.PageSizeId.A4),
            QPageLayout.Orientation.Portrait,
            QMarginsF(15, 15, 15, 15),
            QPageLayout.Unit.Millimeter
        )
        writer.setPageLayout(layout)
        dpi = 300
        writer.setResolution(dpi)

        p_rect = layout.paintRectPixels(dpi)

        # Format container to standard A4 printable width (~800px) so text wrapping,
        # font sizing, equations, and section blocks fill the full width of the A4 page
        orig_min = self.container.minimumWidth() if hasattr(self, 'container') else 0
        orig_max = self.container.maximumWidth() if hasattr(self, 'container') else 16777215

        target_w = 800
        if hasattr(self, 'container'):
            self.container.setFixedWidth(target_w)
            QApplication.processEvents()
            self.adjust_visible_cells_height()
            QApplication.processEvents()

        try:
            painter = QPainter(writer)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

            visible_cells = [c for c in self.cells if not c.isHidden()]
            # Ensure reference width is at least target_w (800) so content and figures
            # are never over-scaled or clipped beyond printable page margins
            ref_w = max([target_w] + [c.width() for c in visible_cells])

            # Scale cells to fill the full printable width of the A4 page
            scale = p_rect.width() / ref_w

            # Plan pagination across pages
            pages = []  # list of pages. Each page has list of (cell, cur_y, source_y, slice_h, scaled_slice, is_full)
            page_cell_bounds = []  # list of dicts: page_idx -> {cell: (top_y, bottom_y)}

            cur_page_items = []
            cur_bounds = {}
            cur_y = 0

            for cell in visible_cells:
                cell_w = max(1, cell.width())
                cell_h = max(1, cell.height())
                scaled_h = int(cell_h * scale)

                if cur_y + scaled_h > p_rect.height() and cur_y > 0:
                    pages.append(cur_page_items)
                    page_cell_bounds.append(cur_bounds)
                    cur_page_items = []
                    cur_bounds = {}
                    cur_y = 0

                if cur_y + scaled_h <= p_rect.height():
                    cur_page_items.append((cell, cur_y, 0, cell_h, scaled_h, True))
                    if cell not in cur_bounds:
                        cur_bounds[cell] = (cur_y, cur_y + scaled_h)
                    else:
                        cur_bounds[cell] = (min(cur_bounds[cell][0], cur_y), max(cur_bounds[cell][1], cur_y + scaled_h))
                    cur_y += scaled_h + int(6 * scale)
                else:
                    # Cell is taller than an entire page -> paginate it into slices
                    remaining_h = cell_h
                    source_y = 0
                    while remaining_h > 0:
                        available_h = int((p_rect.height() - cur_y) / scale)
                        if available_h <= 30 and cur_y > 0:
                            pages.append(cur_page_items)
                            page_cell_bounds.append(cur_bounds)
                            cur_page_items = []
                            cur_bounds = {}
                            cur_y = 0
                            available_h = int(p_rect.height() / scale)
                        slice_h = min(remaining_h, available_h)
                        scaled_slice = int(slice_h * scale)
                        cur_page_items.append((cell, cur_y, source_y, slice_h, scaled_slice, False))
                        if cell not in cur_bounds:
                            cur_bounds[cell] = (cur_y, cur_y + scaled_slice)
                        else:
                            cur_bounds[cell] = (min(cur_bounds[cell][0], cur_y), max(cur_bounds[cell][1], cur_y + scaled_slice))
                        cur_y += scaled_slice
                        source_y += slice_h
                        remaining_h -= slice_h
                        if cur_y >= p_rect.height() and remaining_h > 0:
                            pages.append(cur_page_items)
                            page_cell_bounds.append(cur_bounds)
                            cur_page_items = []
                            cur_bounds = {}
                            cur_y = 0
                    cur_y += int(6 * scale)

            if cur_page_items:
                pages.append(cur_page_items)
                page_cell_bounds.append(cur_bounds)

            # Discover all expanded sections and their child cells
            sections_info = []
            for i, cell in enumerate(visible_cells):
                if not getattr(cell, 'is_section_header', False):
                    continue
                if getattr(cell, 'is_collapsed', False):
                    continue
                arrow = getattr(cell, 'btn_section_toggle', None)
                if not arrow or not arrow.isVisible():
                    continue

                sec_level = getattr(cell, 'section_level', 0)
                children = []
                for child in visible_cells[i + 1:]:
                    if getattr(child, 'is_section_header', False):
                        if getattr(child, 'section_level', 0) <= sec_level:
                            break
                    else:
                        if getattr(child, '_is_outside_section', False) or getattr(child, 'section_level', 0) < sec_level:
                            break
                    children.append(child)

                if not children:
                    continue

                last_cell = children[-1]
                tip = arrow.mapTo(cell, QPoint(arrow.width() // 2, arrow.height() - 2))
                sections_info.append({
                    'header_cell': cell,
                    'last_cell': last_cell,
                    'all_cells': [cell] + children,
                    'tip_x': tip.x(),
                    'tip_y': tip.y(),
                })

            scope_pen = QPen(QColor("#8e9aaf"), max(1, round(1.2 * scale)), Qt.PenStyle.SolidLine, Qt.PenCapStyle.SquareCap)

            for page_idx, page_items in enumerate(pages):
                if page_idx > 0:
                    writer.newPage()

                # 1. Render cell contents for this page
                for cell, cur_y, source_y, slice_h, scaled_slice, is_full in page_items:
                    cell_w = max(1, cell.width())
                    painter.save()
                    if is_full:
                        painter.translate(0, cur_y)
                        painter.scale(scale, scale)
                        cell.render(painter)
                    else:
                        painter.translate(0, cur_y - int(source_y * scale))
                        painter.scale(scale, scale)
                        clip_rect = QRect(0, source_y, cell_w, slice_h)
                        cell.render(painter, QPoint(0, 0), QRegion(clip_rect))
                    painter.restore()

                # 2. Render section & subsection scope lines on this page
                bounds = page_cell_bounds[page_idx]
                painter.save()
                painter.setPen(scope_pen)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

                for sinfo in sections_info:
                    header = sinfo['header_cell']
                    last_c = sinfo['last_cell']
                    sec_cells = sinfo['all_cells']

                    # Check if any cell of this section is on this page
                    page_cells = [c for c in sec_cells if c in bounds]
                    if not page_cells:
                        continue

                    line_x = int(sinfo['tip_x'] * scale)

                    # Top of line on this page
                    if header in bounds:
                        y_start = bounds[header][0] + int(sinfo['tip_y'] * scale)
                    else:
                        # Section started on a previous page: continue from top of first section cell on this page
                        y_start = bounds[page_cells[0]][0]

                    # Bottom of line on this page
                    is_last_page_for_section = (last_c in bounds)
                    if is_last_page_for_section:
                        y_end = bounds[last_c][1] - int(4 * scale)
                    else:
                        # Section continues onto a later page: line extends to bottom of last section cell on this page
                        y_end = bounds[page_cells[-1]][1]

                    if y_end > y_start:
                        painter.drawLine(line_x, y_start, line_x, y_end)
                        if is_last_page_for_section:
                            tick_len = int(8 * scale)
                            painter.drawLine(line_x, y_end, line_x + tick_len, y_end)

                painter.restore()

            painter.end()
        finally:
            if hasattr(self, 'container'):
                self.container.setMinimumWidth(orig_min)
                self.container.setMaximumWidth(orig_max)
                self.adjust_visible_cells_height()
                QApplication.processEvents()

    def to_mw(self) -> str:
        """Serialize current worksheet cells to native .mw XML format."""
        from cas_engine import WorksheetIO
        cells_data = [cell.to_dict() for cell in self.cells]
        return WorksheetIO.save_mw_string(cells_data)

    def load_from_content(self, content: str, file_path: str = "", progress_callback=None):
        """Universal loader for worksheet documents (.mw XML, JSON, or empty)."""
        if not content or not content.strip():
            for cell in list(self.cells):
                self.cells_layout.removeWidget(cell)
                cell.deleteLater()
            self.cells.clear()
            self.add_cell(focus=True)
            return

        stripped = content.strip()
        if stripped.startswith('{'):
            try:
                self.load_from_json(content, progress_callback=progress_callback)
                return
            except Exception:
                self.load_from_mw(content, progress_callback=progress_callback)
                return

        if stripped.startswith('<') or file_path.lower().endswith('.mw'):
            try:
                self.load_from_mw(content, progress_callback=progress_callback)
                return
            except Exception:
                self.load_from_json(content, progress_callback=progress_callback)
                return

        try:
            self.load_from_json(content, progress_callback=progress_callback)
        except Exception:
            self.load_from_mw(content, progress_callback=progress_callback)

    def load_from_mw(self, mw_str: str, progress_callback=None):
        """Load cells from a native .mw XML string into the worksheet."""
        if not mw_str or not mw_str.strip():
            for cell in list(self.cells):
                self.cells_layout.removeWidget(cell)
                cell.deleteLater()
            self.cells.clear()
            self.add_cell(focus=True)
            return

        stripped = mw_str.strip()
        if stripped.startswith('{'):
            self.load_from_json(mw_str, progress_callback=progress_callback)
            return

        if progress_callback:
            progress_callback(0, 0, "Parsing worksheet elements...")

        from cas_engine import WorksheetIO
        cells_data = WorksheetIO.load_mw_string(mw_str)

        for cell in list(self.cells):
            self.cells_layout.removeWidget(cell)
            cell.deleteLater()
        self.cells.clear()
        if hasattr(self, 'undo_stack'):
            self.undo_stack.clear()

        total_cells = len(cells_data)
        if progress_callback:
            progress_callback(0, total_cells, f"Loading 0 of {total_cells} elements...")

        self._loading_cell_ids = set()
        self._is_loading = True
        self.setUpdatesEnabled(False)
        self.container.setUpdatesEnabled(False)
        collapsed_depth_stack = []
        try:
            for i, cdata in enumerate(cells_data):
                sec_level = cdata.get('section_level', 0)
                is_sec = bool(cdata.get('is_section_header', False))
                if is_sec:
                    while collapsed_depth_stack and collapsed_depth_stack[-1] >= sec_level:
                        collapsed_depth_stack.pop()
                elif cdata.get('_is_outside_section'):
                    collapsed_depth_stack.clear()
                else:
                    while collapsed_depth_stack and collapsed_depth_stack[-1] > sec_level:
                        collapsed_depth_stack.pop()
                is_initially_hidden = bool(collapsed_depth_stack)

                if is_initially_hidden:
                    cell = WorksheetCell(
                        execution_idx=cdata.get('execution_idx', self.execution_counter + 1),
                        theme_mode=self.theme_mode,
                        font_size=self.default_font_size,
                        font_family=self.default_font_family,
                        engine=self.engine,
                        parent=self.container,
                        lazy=True,
                        lazy_data=cdata
                    )
                    cell.parent_worksheet = self
                    self.cells.append(cell)
                    self.cells_layout.addWidget(cell)
                else:
                    cell = self.add_cell(expression="", focus=False)
                    cell.from_dict(cdata)

                if cdata.get('is_section_header') and cdata.get('is_collapsed'):
                    collapsed_depth_stack.append(sec_level)

                self.execution_counter = max(self.execution_counter, cell.execution_idx)
                if progress_callback and (i % 50 == 0 or i == total_cells - 1):
                    progress_callback(i + 1, total_cells, f"Loading element {i + 1} of {total_cells}...")
        finally:
            self._is_loading = False
            self.setUpdatesEnabled(True)
            self.container.setUpdatesEnabled(True)

        self.renumber_equation_labels()
        self.cellCountChanged.emit(len(self.cells))
        self.update_section_hierarchy()
        QTimer.singleShot(0, self.adjust_visible_cells_height)

        if self.cells:
            first_cell = self.cells[0]
            self.active_cell = first_cell
            self.activeCellChanged.emit(first_cell)
            def _focus_first():
                try:
                    if not sip.isdeleted(first_cell) and hasattr(first_cell, 'input_edit') and not sip.isdeleted(first_cell.input_edit):
                        fw = QApplication.focusWidget()
                        if fw is not None and (fw == first_cell.input_edit or first_cell.isAncestorOf(fw)):
                            return
                        first_cell.input_edit.setFocus()
                except (RuntimeError, AttributeError, ReferenceError):
                    pass
            QTimer.singleShot(50, _focus_first)
        else:
            self.add_cell(focus=True)

    def move_cell_to(self, cell: WorksheetCell, target_idx: int):
        """Move an existing cell to a new position in the worksheet."""
        if not cell or cell not in self.cells or target_idx < 0 or target_idx >= len(self.cells):
            return
        cur_idx = self.cells.index(cell)
        if cur_idx == target_idx:
            return
        self.cells_layout.removeWidget(cell)
        self.cells.pop(cur_idx)
        self.cells.insert(target_idx, cell)
        self.cells_layout.insertWidget(target_idx, cell)
        self.update_section_hierarchy()
        self.renumber_equation_labels()

    def load_from_json(self, json_str: str, progress_callback=None):
        if not json_str or not json_str.strip():
            for cell in list(self.cells):
                self.cells_layout.removeWidget(cell)
                cell.deleteLater()
            self.cells.clear()
            self.add_cell(focus=True)
            return

        stripped = json_str.strip()
        if stripped.startswith('<'):
            self.load_from_mw(json_str, progress_callback=progress_callback)
            return

        if progress_callback:
            progress_callback(0, 0, "Reading document structure...")

        try:
            data = json.loads(json_str)
        except Exception:
            try:
                self.load_from_mw(json_str, progress_callback=progress_callback)
                return
            except Exception:
                raise

        self.is_worksheet_mode = data.get('is_worksheet_mode', True)
        cell_data_list = data.get('cells', [])

        for cell in list(self.cells):
            self.cells_layout.removeWidget(cell)
            cell.deleteLater()
        self.cells.clear()
        if hasattr(self, 'undo_stack'):
            self.undo_stack.clear()

        total_cells = len(cell_data_list)
        if progress_callback:
            progress_callback(0, total_cells, f"Loading 0 of {total_cells} elements...")

        self._loading_cell_ids = set()
        self._is_loading = True
        self.setUpdatesEnabled(False)
        self.container.setUpdatesEnabled(False)
        collapsed_depth_stack = []
        try:
            for i, cdata in enumerate(cell_data_list):
                sec_level = cdata.get('section_level', 0)
                is_sec = bool(cdata.get('is_section_header', False))
                if is_sec:
                    while collapsed_depth_stack and collapsed_depth_stack[-1] >= sec_level:
                        collapsed_depth_stack.pop()
                elif cdata.get('_is_outside_section'):
                    collapsed_depth_stack.clear()
                else:
                    while collapsed_depth_stack and collapsed_depth_stack[-1] > sec_level:
                        collapsed_depth_stack.pop()
                is_initially_hidden = bool(collapsed_depth_stack)

                if is_initially_hidden:
                    cell = WorksheetCell(
                        execution_idx=cdata.get('execution_idx', self.execution_counter + 1),
                        theme_mode=self.theme_mode,
                        font_size=self.default_font_size,
                        font_family=self.default_font_family,
                        engine=self.engine,
                        parent=self.container,
                        lazy=True,
                        lazy_data=cdata
                    )
                    cell.parent_worksheet = self
                    self.cells.append(cell)
                    self.cells_layout.addWidget(cell)
                else:
                    cell = self.add_cell(expression="", focus=False)
                    cell.from_dict(cdata)

                if cdata.get('is_section_header') and cdata.get('is_collapsed'):
                    collapsed_depth_stack.append(sec_level)

                self.execution_counter = max(self.execution_counter, cell.execution_idx)
                if progress_callback and (i % 50 == 0 or i == total_cells - 1):
                    progress_callback(i + 1, total_cells, f"Loading element {i + 1} of {total_cells}...")
        finally:
            self._is_loading = False
            self.setUpdatesEnabled(True)
            self.container.setUpdatesEnabled(True)

        self.renumber_equation_labels()
        self.cellCountChanged.emit(len(self.cells))
        self.update_section_hierarchy()

        if progress_callback:
            progress_callback(total_cells, total_cells, "Finalizing sections and layout...")

        # Apply initial collapse states for collapsed sections
        for cell in self.cells:
            if getattr(cell, 'is_section_header', False) and getattr(cell, 'is_collapsed', False):
                self._on_section_toggled(cell.cell_id, True)

        self.update_section_hierarchy()
        QTimer.singleShot(0, self.adjust_visible_cells_height)

        if self.cells:
            first_cell = self.cells[0]
            self.active_cell = first_cell
            self.activeCellChanged.emit(first_cell)
            def _focus_first():
                try:
                    if not sip.isdeleted(first_cell) and hasattr(first_cell, 'input_edit') and not sip.isdeleted(first_cell.input_edit):
                        fw = QApplication.focusWidget()
                        if fw is not None and (fw == first_cell.input_edit or first_cell.isAncestorOf(fw)):
                            return
                        first_cell.input_edit.setFocus()
                except (RuntimeError, AttributeError, ReferenceError):
                    pass
            QTimer.singleShot(50, _focus_first)
            def _reset_scroll():
                try:
                    if not sip.isdeleted(self) and not sip.isdeleted(self.scroll_area):
                        sb = self.scroll_area.verticalScrollBar()
                        if not sip.isdeleted(sb):
                            sb.setValue(0)
                except (RuntimeError, AttributeError, ReferenceError):
                    pass
            QTimer.singleShot(50, _reset_scroll)
        else:
            self.add_cell(focus=True)

    def mousePressEvent(self, event):
        try:
            if self.active_cell and not sip.isdeleted(self.active_cell) and hasattr(self.active_cell, 'input_edit') and not sip.isdeleted(self.active_cell.input_edit):
                self.active_cell.input_edit.setFocus()
            elif self.cells and not sip.isdeleted(self.cells[-1]) and hasattr(self.cells[-1], 'input_edit') and not sip.isdeleted(self.cells[-1].input_edit):
                self.cells[-1].input_edit.setFocus()
        except (RuntimeError, AttributeError, ReferenceError):
            pass
        super().mousePressEvent(event)

    def undo(self):
        """Perform undo on active text editor or document undo stack."""
        if not self.is_editable:
            return

        fw = QApplication.focusWidget()
        editor_has_undo = False
        editor = None
        if fw and not sip.isdeleted(fw):
            if isinstance(fw, QTextEdit):
                editor = fw
                editor_has_undo = fw.document().isUndoAvailable()
            elif isinstance(fw, QLineEdit):
                editor = fw
                editor_has_undo = fw.isUndoAvailable()

        has_multi_sel = bool(getattr(self, 'selected_cells', None) and len(self.selected_cells) > 0)
        stack_can_undo = hasattr(self, 'undo_stack') and self.undo_stack.canUndo()

        doc_is_newer = stack_can_undo and (getattr(self, '_last_doc_action_time', 0) >= getattr(self, '_last_text_edit_time', 0))

        if has_multi_sel and stack_can_undo:
            self.undo_stack.undo()
        elif doc_is_newer:
            self.undo_stack.undo()
            self._last_doc_action_time = 0
        elif editor_has_undo and editor:
            editor.undo()
        elif stack_can_undo:
            self.undo_stack.undo()
            self._last_doc_action_time = 0
        elif editor_has_undo and editor:
            editor.undo()

    def redo(self):
        """Perform redo on active text editor or document undo stack."""
        if not self.is_editable:
            return

        fw = QApplication.focusWidget()
        editor_has_redo = False
        editor = None
        if fw and not sip.isdeleted(fw):
            if isinstance(fw, QTextEdit):
                editor = fw
                editor_has_redo = fw.document().isRedoAvailable()
            elif isinstance(fw, QLineEdit):
                editor = fw
                editor_has_redo = fw.isRedoAvailable()

        has_multi_sel = bool(getattr(self, 'selected_cells', None) and len(self.selected_cells) > 0)
        stack_can_redo = hasattr(self, 'undo_stack') and self.undo_stack.canRedo()

        doc_is_newer = stack_can_redo and (getattr(self, '_last_doc_action_time', 0) >= getattr(self, '_last_text_edit_time', 0))

        if has_multi_sel and stack_can_redo:
            self.undo_stack.redo()
        elif doc_is_newer:
            self.undo_stack.redo()
            self._last_doc_action_time = 0
        elif editor_has_redo and editor:
            editor.redo()
        elif stack_can_redo:
            self.undo_stack.redo()
            self._last_doc_action_time = 0
        elif editor_has_redo and editor:
            editor.redo()

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.NativeGesture:
            if self.handle_native_gesture_zoom(event):
                event.accept()
                return True
        elif event.type() == QEvent.Type.Wheel:
            if event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier):
                if self.handle_wheel_zoom(event):
                    event.accept()
                    return True
        elif event.type() == QEvent.Type.KeyPress:
            # 1. Delete / Backspace on cell selection
            if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
                if hasattr(self, 'selected_cells') and len(self.selected_cells) >= 1:
                    self.delete_selected_cells()
                    event.accept()
                    return True
                fw = QApplication.focusWidget()
                if fw and isinstance(fw, (QLineEdit, QTextEdit)):
                    return super().eventFilter(obj, event)
                if self.active_cell:
                    self.delete_cells([self.active_cell.cell_id])
                    event.accept()
                    return True

            # 2. Keyboard shortcuts for Undo and Redo
            if event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier):
                if event.key() == Qt.Key.Key_Z:
                    if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                        self.redo()
                    else:
                        self.undo()
                    event.accept()
                    return True
                elif event.key() == Qt.Key.Key_Y:
                    self.redo()
                    event.accept()
                    return True
                elif event.key() in (Qt.Key.Key_Plus, Qt.Key.Key_Equal):
                    self.zoom_in()
                    event.accept()
                    return True
                elif event.key() in (Qt.Key.Key_Minus, Qt.Key.Key_Underscore):
                    self.zoom_out()
                    event.accept()
                    return True
                elif event.key() == Qt.Key.Key_0:
                    self.zoom_reset()
                    event.accept()
                    return True
        return super().eventFilter(obj, event)

    def wheelEvent(self, event: QWheelEvent):
        if event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier):
            if self.handle_wheel_zoom(event):
                event.accept()
                return
        super().wheelEvent(event)

    def event(self, event: QEvent):
        if event.type() == QEvent.Type.NativeGesture:
            if self.handle_native_gesture_zoom(event):
                event.accept()
                return True
        return super().event(event)
