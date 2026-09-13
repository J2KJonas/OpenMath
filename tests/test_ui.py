"""
Headless UI component tests for OpenMath UI components:
Start Page, Worksheet, Cells, Palettes Dock, Context Panel, and MathRenderer.
"""

import os
import sys
import unittest

# Run Qt headless in tests
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtWidgets import QApplication, QPushButton, QMenu, QFileDialog, QDialog
from PyQt6.QtCore import Qt, QEvent, QPoint, QPointF
from PyQt6.QtGui import QKeyEvent, QMouseEvent, QPalette
from cas_engine import CASEngine
from ui.main_window import MainWindow
from ui.worksheet_view import WorksheetView
from ui.math_renderer import MathRendererWidget
from ui.matrix_dialog import MatrixDialog
from ui.start_page import StartPageView
from ui.worksheet_cell import PROP_MODE

app = QApplication.instance() or QApplication(sys.argv)


class TestUIComponents(unittest.TestCase):
    def setUp(self):
        self.engine = CASEngine()
        self.window = MainWindow()
        self.window.show()

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        QApplication.processEvents()

    def test_main_window_initialization(self):
        self.assertIsNotNone(self.window.start_page)
        self.assertIsNotNone(self.window.palette_panel)
        self.assertIsNotNone(self.window.context_panel)
        # Verify only Start.mw tab is opened initially
        self.assertEqual(self.window.tab_widget.count(), 1)
        self.assertEqual(self.window.tab_widget.tabText(0), "Start.mw")
        self.assertIsInstance(self.window.doc_stack.currentWidget(), StartPageView)

    def test_new_document_workflow(self):
        # Click 'New Document' from Start Page
        self.window.start_page.btn_new.click()
        self.assertEqual(self.window.tab_widget.count(), 2)
        self.assertEqual(self.window.tab_widget.tabText(1), "*Untitled (1)")
        self.assertIsInstance(self.window.doc_stack.currentWidget(), WorksheetView)
        self.assertGreater(len(self.window.worksheet.cells), 0)

    def test_start_page_responsive_buttons(self):
        """Verify New Document and Open Documents buttons dynamically adapt to window size without overlap."""
        from PyQt6.QtWidgets import QApplication, QBoxLayout
        sp = StartPageView()
        sp.show()

        # Test large window
        sp.resize(1000, 700)
        sp._update_responsive_layout()
        QApplication.processEvents()
        self.assertEqual(sp.btn_layout.direction(), QBoxLayout.Direction.TopToBottom)
        self.assertGreaterEqual(sp.btn_new.height(), 52)
        self.assertGreater(sp.btn_open.geometry().y(), sp.btn_new.geometry().y() + sp.btn_new.height() - 1)

        # Test wide and short window (like small laptop or dock open)
        sp.resize(600, 350)
        sp._update_responsive_layout()
        QApplication.processEvents()
        self.assertEqual(sp.btn_layout.direction(), QBoxLayout.Direction.LeftToRight)
        self.assertLessEqual(sp.btn_new.height(), 42)
        self.assertGreater(sp.btn_open.geometry().x(), sp.btn_new.geometry().x() + sp.btn_new.width() - 1)

        # Test compact window
        sp.resize(400, 300)
        sp._update_responsive_layout()
        QApplication.processEvents()
        self.assertLessEqual(sp.btn_new.height(), 40)
        self.assertGreater(sp.btn_open.geometry().y(), sp.btn_new.geometry().y() + sp.btn_new.height() - 1)

    def test_math_renderer_pixmap(self):
        pixmap = MathRendererWidget.render_latex_to_pixmap(r"\frac{\sin(x)}{x}", font_size=14)
        self.assertIsNotNone(pixmap)
        self.assertFalse(pixmap.isNull())

    def test_matrix_dialog_string_generation(self):
        dlg = MatrixDialog(parent=None)
        self.assertTrue(dlg.rows_combo.isEditable())
        self.assertTrue(dlg.cols_combo.isEditable())

        # Test selecting or typing custom dimensions via combo boxes
        dlg.rows_combo.setCurrentText("4")
        dlg.cols_combo.setCurrentText("2")
        self.assertEqual(len(dlg.cells), 4)
        self.assertEqual(len(dlg.cells[0]), 2)

        # Test backwards-compatible spin adapters
        dlg.rows_spin.setValue(2)
        dlg.cols_spin.setValue(2)
        self.assertEqual(len(dlg.cells), 2)
        self.assertEqual(len(dlg.cells[0]), 2)
        dlg._fill_identity()
        mat_str = dlg.get_matrix_string()
        self.assertEqual(mat_str, "Matrix([[1, 0], [0, 1]])")

        # Test custom value editing in cells
        dlg.cells[0][1].setText("5")
        self.assertEqual(dlg.get_matrix_string(), "Matrix([[1, 5], [0, 1]])")

    def test_worksheet_serialization(self):
        ws = self.window.new_worksheet()
        json_str = ws.to_json()
        self.assertIn("cells", json_str)
        ws.load_from_json(json_str)
        self.assertGreater(len(ws.cells), 0)

    def test_load_from_json_timer_cleanup(self):
        """Ensure loading a saved .mw file does not cause RuntimeError from deleted cell timers."""
        import time
        ws = self.window.new_worksheet()
        mw_content = '{"version": "2021", "is_worksheet_mode": true, "cells": [{"input": "3 + 3"}, {"input": "x^2"}]}'
        ws.load_from_json(mw_content)
        # Process deferred delete events and allow 50ms timers to fire
        t0 = time.time()
        while time.time() - t0 < 0.1:
            QApplication.processEvents()
            time.sleep(0.01)
        self.assertEqual(len(ws.cells), 2)
        self.assertEqual(ws.active_cell, ws.cells[0])

    def test_open_worksheet_mw_file(self):
        """Test opening a saved .mw file via open_worksheet with file dialog and event loop."""
        import tempfile
        import time
        import os
        from unittest.mock import patch
        from PyQt6.QtWidgets import QFileDialog

        with tempfile.NamedTemporaryFile(suffix='.mw', mode='w', delete=False, encoding='utf-8') as f:
            f.write('{"version": "2021", "is_worksheet_mode": true, "cells": [{"input": "5*5"}, {"input": "sin(pi/2)"}]}')
            tmp_path = f.name

        try:
            with patch.object(QFileDialog, 'getOpenFileName', return_value=(tmp_path, 'Worksheet (*.mw *.json)')):
                self.window.open_worksheet()

            t0 = time.time()
            while time.time() - t0 < 0.15:
                QApplication.processEvents()
                time.sleep(0.01)

            self.assertIsNotNone(self.window.worksheet)
            self.assertEqual(len(self.window.worksheet.cells), 2)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_palette_dock_toggle(self):
        self.window.palette_dock.setVisible(False)
        self.assertFalse(self.window.palette_dock.isVisible())
        self.window.palette_dock.setVisible(True)
        self.assertTrue(self.window.palette_dock.isVisible())

    def test_context_dock_toggle(self):
        self.window.context_dock.setVisible(False)
        self.assertFalse(self.window.context_dock.isVisible())
        self.window.context_dock.setVisible(True)
        self.assertTrue(self.window.context_dock.isVisible())

    def test_template_insertion_into_cell(self):
        ws = self.window.new_worksheet()
        active_cell = ws.active_cell
        self.assertIsNotNone(active_cell)
        self.window._on_insert_template("to_bin(255, 8)")
        self.assertTrue("to_bin(255, 8)" in active_cell.get_input_text() or "toᵦᵢₙ(255, 8)" in active_cell.get_input_text())

    def test_context_panel_shortcuts_visible(self):
        self.window.context_dock.setVisible(True)
        self.assertIsNotNone(self.window.context_panel.shortcuts_card)
        self.assertTrue(self.window.context_panel.shortcuts_card.isVisible())

    def test_palette_latex_buttons(self):
        from PyQt6.QtWidgets import QPushButton
        from ui.palette_panel import PalettePanel
        panel = PalettePanel(theme_mode="light")
        # Check that expression and calculus sections contain buttons with icons
        buttons = panel.findChildren(QPushButton)
        math_buttons = [b for b in buttons if not b.icon().isNull()]
        self.assertGreater(len(math_buttons), 20, "Expected at least 20 LaTeX-rendered palette buttons")

    def test_palette_section_order(self):
        """Verify Embedded Systems is directly under Expression and Units is directly under Embedded Systems."""
        from ui.palette_panel import PalettePanel, AccordionSection
        panel = PalettePanel(theme_mode="light")
        sections = panel.findChildren(AccordionSection)
        titles = [s.header.title_text for s in sections]
        self.assertIn("Expression", titles)
        self.assertIn("Embedded Systems", titles)
        self.assertIn("Units", titles)
        idx_expr = titles.index("Expression")
        idx_emb = titles.index("Embedded Systems")
        idx_units = titles.index("Units")
        self.assertEqual(idx_emb, idx_expr + 1)
        self.assertEqual(idx_units, idx_emb + 1)

    def test_palette_favorites_right_click_and_toggle(self):
        """Test right-clicking palette buttons to favorite and unfavorite items."""
        from PyQt6.QtCore import Qt, QPointF, QSettings
        from PyQt6.QtGui import QMouseEvent
        from ui.palette_panel import PalettePanel, PaletteItemButton

        settings = QSettings("OpenMath", "OpenMath")
        settings.remove("palette_favorites")

        panel = PalettePanel(theme_mode="light")
        buttons = panel.findChildren(PaletteItemButton)
        ab_btn = next((b for b in buttons if "a + b" in b.toolTip() or b.text() == "a + b"), None)
        self.assertIsNotNone(ab_btn, "Expected to find 'a + b' button in palette")

        rc_received = []
        ab_btn.rightClicked.connect(lambda pos: rc_received.append(pos))
        ev = QMouseEvent(QMouseEvent.Type.MouseButtonPress, QPointF(5, 5), QPointF(5, 5),
                         Qt.MouseButton.RightButton, Qt.MouseButton.RightButton, Qt.KeyboardModifier.NoModifier)
        ab_btn.mousePressEvent(ev)
        self.assertEqual(len(rc_received), 1)

        # Test Mac Control+Click triggers rightClicked
        rc_ctrl = []
        ab_btn.rightClicked.connect(lambda pos: rc_ctrl.append(pos))
        ev_ctrl = QMouseEvent(QMouseEvent.Type.MouseButtonPress, QPointF(5, 5), QPointF(5, 5),
                              Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.ControlModifier)
        ab_btn.mousePressEvent(ev_ctrl)
        self.assertEqual(len(rc_ctrl), 1)

        # Test right clicking a button inside the Favorites section
        fav_buttons = panel.fav_content_widget.findChildren(PaletteItemButton)
        self.assertGreater(len(fav_buttons), 0, "Expected buttons in default Favorites section")
        first_fav_btn = fav_buttons[0]
        fav_rc = []
        first_fav_btn.rightClicked.connect(lambda pos: fav_rc.append(pos))
        first_fav_btn.mousePressEvent(ev)
        self.assertEqual(len(fav_rc), 1)

        # Test removing from favorites
        first_fav_item = panel.favorite_items[0]
        initial_fav_count = len(panel.favorite_items)
        panel.remove_favorite(first_fav_item)
        self.assertEqual(len(panel.favorite_items), initial_fav_count - 1)
        self.assertFalse(panel._is_favorited(first_fav_item))

        # Test restoring defaults
        panel.restore_default_favorites()
        self.assertEqual(len(panel.favorite_items), initial_fav_count)
        self.assertTrue(panel._is_favorited(first_fav_item))

        item_data = {
            "kind": "math",
            "latex": "a + b",
            "template": "a + b",
            "tooltip": "Addition (a + b)",
            "fallback": "a + b",
            "height": 34,
            "max_icon_h": 26,
            "max_icon_w": 58,
            "is_wide": False,
        }
        panel.add_favorite(item_data)
        self.assertTrue(panel._is_favorited(item_data))
        self.assertEqual(len(panel.favorite_items), initial_fav_count + 1)
        self.assertTrue(panel.fav_section.header.is_expanded)

        panel.remove_favorite(item_data)
        self.assertFalse(panel._is_favorited(item_data))
        self.assertEqual(len(panel.favorite_items), initial_fav_count)

        settings.remove("palette_favorites")

    def test_palette_section_drag_reorder_and_persistence(self):
        """Test section folding on drag, drop indicator, reordering, and QSettings persistence."""
        from PyQt6.QtCore import Qt, QPoint, QSettings
        from PyQt6.QtWidgets import QApplication
        import json
        from ui.palette_panel import PalettePanel, DEFAULT_SECTION_ORDER

        settings = QSettings("OpenMath", "OpenMath")
        settings.remove("palette_section_order")

        panel = PalettePanel(theme_mode="light")
        panel.show()
        QApplication.processEvents()

        # Initial order matches default
        self.assertEqual(panel.section_order, DEFAULT_SECTION_ORDER)

        # Expand Calculus to test that drag folds it in
        panel.sections["Calculus"].set_expanded(True)
        self.assertTrue(panel.sections["Calculus"].header.is_expanded)

        # 1. Start drag on 'Plots' section
        panel._on_section_drag_started("Plots")
        self.assertTrue(panel._is_dragging_section)
        self.assertEqual(panel._dragged_section_title, "Plots")

        # ALL sections must fold in
        for sec_name in panel.section_order:
            self.assertFalse(panel.sections[sec_name].header.is_expanded,
                             f"Section {sec_name} should fold in during drag")

        # 2. Test drop indicator positioning
        first_sec = panel.sections[panel.section_order[0]]
        panel.update_drag_indicator(QPoint(20, first_sec.geometry().top() - 5))
        self.assertTrue(panel.drop_indicator.isVisible())

        # 3. Drop 'Plots' at top (position before first section)
        panel.handle_section_drop("Plots", QPoint(20, first_sec.geometry().top() - 5))
        self.assertFalse(panel.drop_indicator.isVisible())
        self.assertEqual(panel.section_order[0], "Plots")

        # Dropped section should be expanded
        self.assertTrue(panel.sections["Plots"].header.is_expanded)
        # Previously expanded section should be restored
        self.assertTrue(panel.sections["Calculus"].header.is_expanded)

        # 4. Verify persistence in QSettings
        saved_raw = settings.value("palette_section_order")
        self.assertIsNotNone(saved_raw)
        saved_order = json.loads(saved_raw)
        self.assertEqual(saved_order[0], "Plots")

        # 5. Opening a new PalettePanel should restore the persisted order
        panel2 = PalettePanel(theme_mode="light")
        self.assertEqual(panel2.section_order[0], "Plots")

        # 6. Test move_section (context menu action)
        panel.move_section("Plots", 1)  # Move down by 1
        self.assertEqual(panel.section_order[1], "Plots")

        # 7. Test reset_section_order
        panel.reset_section_order()
        self.assertEqual(panel.section_order, DEFAULT_SECTION_ORDER)

        settings.remove("palette_section_order")

    def test_custom_size_matrix_button(self):
        """Verify the matrix wizard button says 'Custom Size Matrix' without emoji."""
        from ui.palette_panel import PalettePanel
        from PyQt6.QtWidgets import QPushButton
        panel = PalettePanel(theme_mode="light")
        sec = panel.sections["Matrices & Vectors"]
        btns = [b.text() for b in sec.findChildren(QPushButton)]
        self.assertIn("Custom Size Matrix", btns)
        self.assertFalse(any("✨" in b for b in btns))

    def test_expr_to_preview_latex(self):
        from ui.math_renderer import expr_to_preview_latex
        self.assertEqual(expr_to_preview_latex("(⟦a⟧)/(⟦b⟧)"), r"\frac{a}{b}")
        self.assertEqual(expr_to_preview_latex("⟦a⟧^(⟦b⟧)"), r"a^{b}")
        self.assertEqual(expr_to_preview_latex("sqrt(⟦a⟧)"), r"\sqrt{a}")
        self.assertIn(r"\frac{d}{d x}", expr_to_preview_latex("diff(⟦f⟧, ⟦x⟧)"))
        self.assertIn(r"\int", expr_to_preview_latex("integrate(⟦f⟧, ⟦x⟧)"))
        self.assertIn(r"\lim", expr_to_preview_latex("limit(⟦f⟧, ⟦x⟧, ⟦a⟧)"))

    def test_live_2d_math_preview_workflow(self):
        ws = self.window.new_worksheet()
        cell = ws.active_cell
        self.assertIsNotNone(cell)
        cell.set_input_mode(cell.MODE_2D_MATH)
        cell.insert_template("a + b")
        cell._update_live_preview()
        self.assertFalse(cell.preview_row.isVisible())

    def test_latex_preprocessing_in_cas_engine(self):
        # Test evaluating template with unedited placeholders
        res1 = self.engine.evaluate("⟦a⟧ / ⟦b⟧")
        self.assertIsNotNone(res1.exact_latex)
        # Test evaluating raw LaTeX syntax
        res2 = self.engine.evaluate(r"\frac{10}{2}")
        self.assertIn("5", res2.exact_text)

    def test_variable_assignment_with_colon_on_enter(self):
        import time
        from PyQt6.QtGui import QKeyEvent
        from PyQt6.QtCore import QCoreApplication

        ws = self.window.new_worksheet()
        cell0 = ws.cells[0]
        cell0.input_edit.setPlainText('U := 100 :')

        # Simulate pressing Enter
        key_event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier)
        cell0.input_edit.keyPressEvent(key_event)

        for _ in range(50):
            QCoreApplication.processEvents()
            time.sleep(0.02)
            if 'U' in self.window.engine.namespace and len(ws.cells) > 1 and ws.active_cell == ws.cells[1]:
                break

        self.assertEqual(self.window.engine.namespace.get('U'), 100)
        self.assertTrue(cell0.output_row.isHidden())
        self.assertTrue(cell0.preview_row.isHidden())
        self.assertEqual(len(ws.cells), 2)
        self.assertEqual(ws.active_cell, ws.cells[1])

        # Second cell using U
        cell1 = ws.cells[1]
        cell1.input_edit.setPlainText('U + 50')
        key_shift_enter = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.ShiftModifier)
        cell1.input_edit.keyPressEvent(key_shift_enter)
        self.assertIn('150', cell1.get_input_text())

    def test_zoom_scaling_and_shortcuts(self):
        from PyQt6.QtGui import QKeyEvent, QWheelEvent
        from PyQt6.QtCore import QPoint, QPointF

        ws = self.window.new_worksheet()
        cell = ws.cells[0]
        self.assertEqual(ws.zoom_percent, 100)
        self.assertEqual(cell.current_font_size, 12)
        self.assertEqual(cell.input_edit.font().pointSize(), 12)

        # Zoom in via shortcut Ctrl+=
        key_zoom_in = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Equal, Qt.KeyboardModifier.ControlModifier)
        cell.input_edit.keyPressEvent(key_zoom_in)
        self.assertEqual(ws.zoom_percent, 125)
        # Font size setting must not change
        self.assertEqual(cell.current_font_size, 12)
        # Display font size is zoomed
        self.assertEqual(cell.input_edit.font().pointSize(), 15)

        # Zoom out via shortcut Ctrl+-
        key_zoom_out = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Minus, Qt.KeyboardModifier.ControlModifier)
        cell.input_edit.keyPressEvent(key_zoom_out)
        self.assertEqual(ws.zoom_percent, 100)
        self.assertEqual(cell.current_font_size, 12)
        self.assertEqual(cell.input_edit.font().pointSize(), 12)

        # Wheel zoom with Ctrl
        wheel_ev = QWheelEvent(
            QPointF(50, 50), QPointF(50, 50),
            QPoint(0, 0), QPoint(0, 120),
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.ControlModifier,
            Qt.ScrollPhase.NoScrollPhase,
            False
        )
        cell.input_edit.wheelEvent(wheel_ev)
        self.assertEqual(ws.zoom_percent, 110)
        self.assertEqual(cell.current_font_size, 12)

        # Reset zoom Ctrl+0
        key_reset = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_0, Qt.KeyboardModifier.ControlModifier)
        cell.input_edit.keyPressEvent(key_reset)
        self.assertEqual(ws.zoom_percent, 100)
        self.assertEqual(cell.current_font_size, 12)

    def test_decimal_comma_ui_and_execution(self):
        """Test that decimal comma input and formatting works in UI and execution engine."""
        from cas_engine.formatter import MathFormatter
        from cas_engine.parser import MathParser
        win = MainWindow()
        win.new_worksheet()
        ws = win.worksheet
        cell = ws.active_cell
        self.assertIsNotNone(cell)

        # Default decimal separator is comma ','
        self.assertEqual(MathFormatter.decimal_separator, ',')
        self.assertEqual(MathParser.decimal_separator, ',')
        self.assertEqual(win.lbl_decimal.text(), 'Decimal: <span style="font-size: 15px; font-weight: bold;">,</span>')

        # Evaluate expression with decimal commas
        res = win.engine.evaluate("1,5 + 2,5")
        self.assertEqual(float(res.raw_result), 4.0)

        # Assignment with decimal comma
        win.engine.evaluate("v := 2,5:")
        self.assertAlmostEqual(float(win.engine.namespace['v']), 2.5)

        # Function definition and evaluation with decimal comma
        win.engine.evaluate("g(x) := 1,5*x")
        res_g = win.engine.evaluate("g(4)")
        self.assertAlmostEqual(float(res_g.raw_result), 6.0)

        # Formatting uses decimal comma
        res_dec = win.engine.evaluate("1,2 + 2,3")
        self.assertIn("3,5", res_dec.numeric_text)
        self.assertIn("3{,}5", res_dec.numeric_latex)

        # Toggle separator to period '.'
        win._toggle_decimal_separator()
        self.assertEqual(MathFormatter.decimal_separator, '.')
        self.assertEqual(win.lbl_decimal.text(), 'Decimal: <span style="font-size: 15px; font-weight: bold;">.</span>')

        # Toggle back to comma ','
        win._toggle_decimal_separator()
        self.assertEqual(MathFormatter.decimal_separator, ',')
        self.assertEqual(win.lbl_decimal.text(), 'Decimal: <span style="font-size: 15px; font-weight: bold;">,</span>')

    def test_multiplication_dot_typing_and_evaluation(self):
        """Test that typing '*' turns into professional multiplication dot '·' and evaluates correctly."""
        from PyQt6.QtGui import QKeyEvent
        win = MainWindow()
        win.new_worksheet()
        cell = win.worksheet.active_cell
        self.assertIsNotNone(cell)

        # Type 'a' then '*'
        cell.input_edit.insertPlainText("a")
        key_star = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Asterisk, Qt.KeyboardModifier.NoModifier, "*")
        cell.input_edit.keyPressEvent(key_star)
        self.assertIn("·", cell.get_input_text())

        # Type 'b' -> 'a · b'
        cell.input_edit.insertPlainText("b")
        self.assertEqual(cell.get_input_text().strip(), "a · b")

        # Evaluate expression with dot
        res = win.engine.evaluate(cell.get_input_text())
        self.assertEqual(str(res.raw_result), "a*b")

        # Arithmetic evaluation with dot
        res_num = win.engine.evaluate("2 · 3")
        self.assertEqual(float(res_num.raw_result), 6.0)

    def test_exponent_caret_typing_and_symbol_i(self):
        """Test that typing '^' then '2' formats to pretty superscript a² and evaluates correctly."""
        from PyQt6.QtGui import QKeyEvent
        from ui.worksheet_cell import CellInputEdit
        win = MainWindow()
        win.new_worksheet()
        cell = win.worksheet.active_cell
        self.assertIsNotNone(cell)

        # Type 'I' then '^' then '2' via key events
        cell.input_edit.insertPlainText("I")
        key_caret = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_AsciiCircum, Qt.KeyboardModifier.NoModifier, "^")
        cell.input_edit.keyPressEvent(key_caret)
        key_2 = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_2, Qt.KeyboardModifier.NoModifier, "2")
        cell.input_edit.keyPressEvent(key_2)
        self.assertEqual(cell.get_input_text().strip(), "I²")

        # Verify clean_operator_spacing formats to pretty superscript
        self.assertEqual(CellInputEdit.clean_operator_spacing("I ^ 2"), "I²")
        self.assertEqual(CellInputEdit.clean_operator_spacing("a^2 + b^3"), "a² + b³")

        # Evaluate I² symbolically (not -1, as I represents current)
        res = win.engine.evaluate("I²")
        self.assertEqual(str(res.raw_result), "I**2")

        # Evaluate P := R * I²
        res_p = win.engine.evaluate("P := R * I²")
        self.assertIn("I", str(res_p.raw_result))
        self.assertIn("R", str(res_p.raw_result))

        # Evaluate multi-digit superscripts
        res_multi = win.engine.evaluate("x¹²")
        self.assertEqual(str(res_multi.raw_result), "x**12")

        # Evaluate imaginary unit i² -> -1
        res_i = win.engine.evaluate("i²")
        self.assertEqual(int(res_i.raw_result), -1)

    def test_colon_auto_spacing_and_suppression(self):
        """Test typing ':' auto-spaces at end of math statement, typing '=' creates ':=', and ':' suppresses output."""
        from PyQt6.QtGui import QKeyEvent
        from ui.worksheet_cell import CellInputEdit
        win = MainWindow()
        win.new_worksheet()
        cell = win.worksheet.active_cell
        self.assertIsNotNone(cell)

        # 1. Typing 'potato' then ':' -> auto-space to 'potato :'
        cell.input_edit.setPlainText('')
        cell.input_edit.insertPlainText("potato")
        ev_colon = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Colon, Qt.KeyboardModifier.NoModifier, ":")
        cell.input_edit.keyPressEvent(ev_colon)
        self.assertEqual(cell.input_edit.toPlainText(), "potato :")

        # 2. Typing '=' after ':' converts 'a :' to 'a := '
        cell.input_edit.setPlainText('')
        cell.input_edit.insertPlainText("a")
        cell.input_edit.keyPressEvent(ev_colon)
        self.assertEqual(cell.input_edit.toPlainText(), "a :")
        ev_equal = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Equal, Qt.KeyboardModifier.NoModifier, "=")
        cell.input_edit.keyPressEvent(ev_equal)
        self.assertEqual(cell.input_edit.toPlainText(), "a := ")

        # 3. clean_operator_spacing handles trailing colon
        cleaned = CellInputEdit.clean_operator_spacing("potato + 20 = a · o² · p · t² + 20:")
        self.assertEqual(cleaned, "potato + 20 = a · o² · p · t² + 20 :")

        # 4. Trailing colon suppresses output display
        cell.input_edit.setPlainText("potato := 42 :")
        cell.execute()
        app.processEvents()
        self.assertFalse(cell.output_row.isVisible())

    def test_exponent_template_selection(self):
        """Test that inserting exponent template wraps selected text (e.g. 'I' -> 'I^⟦b⟧')."""
        win = MainWindow()
        win.new_worksheet()
        cell = win.worksheet.active_cell
        self.assertIsNotNone(cell)

        cell.input_edit.setPlainText("I")
        cursor = cell.input_edit.textCursor()
        cursor.select(cursor.SelectionType.Document)
        cell.input_edit.setTextCursor(cursor)

        cell.insert_template("⟦a⟧^⟦b⟧")
        self.assertEqual(cell.get_input_text().strip(), "I^⟦b⟧")

    def test_text_mode_preservation_and_nonexec_math(self):
        """
        Verify that:
        1. Text written in 'Text' mode remains upright/non-italic text.
        2. Switching to 'Nonexecutable Math' does not alter previous text.
        3. Nonexecutable Math has no live preview (the blue is NOT there) and does not execute.
        # 4. Newly written text in Nonexecutable Math is upright normal form (not italic).
        """
        ws = self.window.new_worksheet()
        cell = ws.active_cell
        self.assertIsNotNone(cell)

        # 1. Select "Text" mode and write text
        cell.set_input_mode(cell.MODE_TEXT)
        self.assertEqual(cell.input_mode, "text")

        user_text = "hey there dette er opgaven som jeg skal lave, det var da dejligt. solve(1+2=3)"
        cell.input_edit.insertPlainText(user_text)

        # All characters must be in text mode (not italic)
        for i in range(len(user_text)):
            c = cell.input_edit.textCursor()
            c.setPosition(i)
            c.setPosition(i + 1, c.MoveMode.KeepAnchor)
            self.assertEqual(c.charFormat().property(PROP_MODE), "text")
            self.assertFalse(c.charFormat().fontItalic())

        # No blue preview in text mode
        cell._update_live_preview()
        self.assertFalse(cell.preview_row.isVisible())

        # 2. Switch to Nonexecutable Math
        cell.set_input_mode(cell.MODE_NONEXEC_MATH)
        self.assertEqual(cell.input_mode, "nonexec_math")

        # Crucial check: Previous text MUST still be text mode and NOT italic!
        for i in range(len(user_text)):
            c = cell.input_edit.textCursor()
            c.setPosition(i)
            c.setPosition(i + 1, c.MoveMode.KeepAnchor)
            self.assertEqual(c.charFormat().property(PROP_MODE), "text")
            self.assertFalse(c.charFormat().fontItalic())

        # Crucial check: Nonexecutable Math text must NOT be executed and NO blue preview!
        cell._update_live_preview()
        self.assertFalse(cell.preview_row.isVisible())

        # 3. Type text after selecting Nonexecutable Math
        cell.input_edit.insertPlainText("\n1 + 2 = 3")

        # Newly written text must be nonexecutable math and upright (NOT italic)
        c_new = cell.input_edit.textCursor()
        c_new.setPosition(len(user_text) + 2)
        c_new.setPosition(len(user_text) + 3, c_new.MoveMode.KeepAnchor)
        self.assertEqual(c_new.charFormat().property(PROP_MODE), "nonexec_math")
        self.assertFalse(c_new.charFormat().fontItalic())

        # Still NO preview and NO execution
        cell._update_live_preview()
        self.assertFalse(cell.preview_row.isVisible())

        cell.execute()
        self.assertFalse(cell.output_row.isVisible())

    def test_text_mode_switch_to_math(self):
        """
        Verify that when switching from 'Text' to 'Math':
        1. Previous text remains in text mode and does not turn into math or evaluate.
        2. Only newly typed text in Math mode is executable and previewed.
        """
        ws = self.window.new_worksheet()
        cell = ws.active_cell
        self.assertIsNotNone(cell)

        # Write in Text mode
        cell.set_input_mode(cell.MODE_TEXT)
        user_text = "hey there dette er opgaven som jeg skal lave, det var da dejligt."
        cell.input_edit.insertPlainText(user_text)

        # Switch to Math mode
        cell.set_input_mode(cell.MODE_2D_MATH)

        # Previous text must NOT change to italic
        c = cell.input_edit.textCursor()
        c.setPosition(5)
        c.setPosition(6, c.MoveMode.KeepAnchor)
        self.assertEqual(c.charFormat().property(PROP_MODE), "text")
        self.assertFalse(c.charFormat().fontItalic())

        # Because all existing text is 'text', executable text is empty -> no preview!
        self.assertEqual(cell.get_executable_text(), "")
        cell._update_live_preview()
        self.assertFalse(cell.preview_row.isVisible())

        # Now type math
        cell.input_edit.insertPlainText("\nsolve(1 + 2 = 3)")
        self.assertEqual(cell.get_executable_text(), "solve(1 + 2 = 3)")

        # Writing math does NOT show the blue preview row ("blue thing")
        cell._update_live_preview()
        self.assertFalse(cell.preview_row.isVisible())

    def test_spans_serialization(self):
        """Verify that cell serialization preserves mixed mode spans."""
        ws = self.window.new_worksheet()
        cell = ws.active_cell

        cell.set_input_mode(cell.MODE_TEXT)
        cell.input_edit.insertPlainText("Text part\n")
        cell.set_input_mode(cell.MODE_NONEXEC_MATH)
        cell.input_edit.insertPlainText("Nonexec math part\n")
        cell.set_input_mode(cell.MODE_2D_MATH)
        cell.input_edit.insertPlainText("1 + 2")

        data = cell.to_dict()
        self.assertIn('spans', data)

        cell2 = ws.add_cell()
        cell2.from_dict(data)

        spans2 = cell2.input_edit.get_spans()
        modes = [s['mode'] for s in spans2]
        self.assertIn("text", modes)
        self.assertIn("nonexec_math", modes)
        self.assertIn("2d_math", modes)

    def test_isolated_multiple_calculations_and_no_duplicate_preview(self):
        """
        Verify:
        1. Inline evaluations do NOT show the duplicate blue preview row below.
        2. Multiple calculations in the same cell remain independent (top is not affected by bottom).
        3. Multiline text does not distort into compound equations like '2 = 2 = 3'.
        """
        from PyQt6.QtGui import QKeyEvent
        from ui.math_renderer import expr_to_preview_latex

        ws = self.window.new_worksheet()
        cell = ws.active_cell
        self.assertIsNotNone(cell)

        # 1. First calculation: 1 + 1 in 2D Math
        cell.set_input_mode(cell.MODE_2D_MATH)
        cell.input_edit.insertPlainText("1 + 1")

        # Evaluate inline (Shift+Enter)
        shift_enter = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.ShiftModifier)
        cell.input_edit.keyPressEvent(shift_enter)

        # Block 0 should now be "1 + 1 = 2"
        self.assertIn("1 + 1 = 2", cell.input_edit.toPlainText())
        # Blue preview row must NOT repeat the result
        self.assertFalse(cell.preview_row.isVisible())

        # 2. Add text line: hej
        cell.input_edit.insertPlainText("\n")
        cell.set_input_mode(cell.MODE_TEXT)
        cell.input_edit.insertPlainText("hej")
        cell._update_live_preview()
        self.assertFalse(cell.preview_row.isVisible())

        # 3. Add nonexec math line: hej
        cell.input_edit.insertPlainText("\n")
        cell.set_input_mode(cell.MODE_NONEXEC_MATH)
        cell.input_edit.insertPlainText("hej")
        cell._update_live_preview()
        self.assertFalse(cell.preview_row.isVisible())

        # 4. Add second calculation: 1 + 2 in 2D Math
        cell.input_edit.insertPlainText("\n")
        cell.set_input_mode(cell.MODE_2D_MATH)
        cell.input_edit.insertPlainText("1 + 2")

        # Crucial check: While writing math, preview row ("blue thing") is NOT visible
        cell._update_live_preview()
        self.assertFalse(cell.preview_row.isVisible())

        # Evaluate line 4 inline (Shift+Enter)
        cell.input_edit.keyPressEvent(shift_enter)

        # Line 4 should now be "1 + 2 = 3"
        lines = cell.input_edit.toPlainText().split('\n')
        self.assertEqual(lines[0].strip(), "1 + 1 = 2")
        self.assertEqual(lines[1].strip(), "hej")
        self.assertEqual(lines[2].strip(), "hej")
        self.assertEqual(lines[3].strip(), "1 + 2 = 3")

        # Crucial check: Preview row must be hidden, no duplicate blue preview!
        self.assertFalse(cell.preview_row.isVisible())

        # Crucial check: expr_to_preview_latex on multiline text does not produce "2 = 2 = 3"
        preview_ltx = expr_to_preview_latex("1 + 1 = 2\n1 + 2 = 3")
        self.assertNotIn("2 = 2 = 3", preview_ltx)

    def test_no_blue_preview_while_writing_in_math_mode(self):
        """Verify that typing math like '1 + 3' in math mode does NOT show the blue preview row."""
        ws = self.window.new_worksheet()
        cell = ws.active_cell
        self.assertIsNotNone(cell)

        cell.set_input_mode(cell.MODE_2D_MATH)
        cell.input_edit.insertPlainText("1 + 3")
        cell._update_live_preview()

        # Blue preview must be hidden while typing math
        self.assertFalse(cell.preview_row.isVisible())

    def test_seamless_inline_fraction(self):
        """Verify seamless inline fraction editing and evaluation."""
        from PyQt6.QtCore import QPointF
        from PyQt6.QtGui import QMouseEvent, QKeyEvent
        from PyQt6.QtWidgets import QApplication

        ws = self.window.new_worksheet()
        QApplication.processEvents()
        cell = ws.active_cell
        self.assertIsNotNone(cell)

        # 1. Typing 'a' then '/' in 2D math mode automatically creates inline FractionWidget
        cell.set_input_mode(cell.MODE_2D_MATH)
        cell.input_edit.insertPlainText("a")
        slash_event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Slash, Qt.KeyboardModifier.NoModifier, "/")
        cell.input_edit.keyPressEvent(slash_event)
        QApplication.processEvents()

        # Fraction widget should exist with num="a", den="b", and denominator focused with "b" selected
        self.assertEqual(len(cell.input_edit.frac_widgets), 1)
        frac = list(cell.input_edit.frac_widgets.values())[0]
        self.assertEqual(frac.num_edit.text(), "a")
        self.assertEqual(frac.den_edit.text(), "b")
        self.assertTrue(frac.den_edit.hasFocus())
        self.assertEqual(frac.den_edit.selectedText(), "b")

        # 2. Replacing denominator with '3'
        frac.den_edit.insert("3")
        self.assertEqual(frac.den_edit.text(), "3")

        # 3. Clicking numerator selects 'a' immediately
        click_pos = QPointF(frac.num_edit.rect().center())
        mouse_press = QMouseEvent(QMouseEvent.Type.MouseButtonPress, click_pos, Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        frac.num_edit.mousePressEvent(mouse_press)
        QApplication.processEvents()
        self.assertEqual(frac.num_edit.selectedText(), "a")

        # 4. Replacing numerator with '2'
        frac.num_edit.insert("2")
        self.assertEqual(frac.num_edit.text(), "2")

        # 5. Executable math text is (2)/(3)
        self.assertEqual(cell.get_executable_text(), "(2)/(3)")

        # 6. Evaluation with CASEngine produces 2/3
        res = self.window.engine.evaluate(cell.get_executable_text())
        self.assertEqual(res.exact_text, "2/3")

    def test_fraction_result_and_context_menu(self):
        """
        Test that:
        1. Evaluating 10/30 + 300/100 inline results in a 2D fraction 10/3.
        2. Right-clicking 10/3 and converting to decimal produces 3,3333333333.
        3. Simplifying 10/30 produces 1/3.
        4. Simplifying 300/100 produces 3.
        """
        ws = self.window.new_worksheet()
        cell = ws.active_cell
        edit = cell.input_edit

        # 1. Insert 10/30 + 300/100
        edit.insert_fraction_widget("10", "30", focus_target=None)
        edit.insertPlainText(" + ")
        edit.insert_fraction_widget("300", "100", focus_target=None)
        QApplication.processEvents()
        self.assertEqual(len(edit.frac_widgets), 2)

        # 2. Inline evaluation
        ok = edit._handle_inline_evaluation()
        self.assertTrue(ok)
        QApplication.processEvents()

        # Result is a 3rd fraction widget (10/3)
        self.assertEqual(len(edit.frac_widgets), 3)
        fids = list(edit.frac_widgets.keys())
        result_frac = edit.frac_widgets[fids[2]]
        self.assertEqual(result_frac.num_edit.text(), "10")
        self.assertEqual(result_frac.den_edit.text(), "3")

        # 3. Simplify first fraction (10/30 -> 1/3)
        frac_1 = edit.frac_widgets[fids[0]]
        frac_1.simplify()
        self.assertEqual(frac_1.num_edit.text(), "1")
        self.assertEqual(frac_1.den_edit.text(), "3")

        # 4. Simplify second fraction (300/100 -> 3)
        frac_2 = edit.frac_widgets[fids[1]]
        frac_2.simplify()
        self.assertIn("3", edit.toPlainText())

        # 5. Convert result fraction (10/3) to decimal
        result_frac.convert_to_decimal()
        plain = edit.toPlainText()
        self.assertTrue("3,3333333333" in plain or "3.3333333333" in plain)

    def test_select_all_preserves_fractions(self):
        """Verify that selecting all text in CellInputEdit preserves embedded FractionWidgets."""
        ws = self.window.new_worksheet()
        cell = ws.active_cell
        edit = cell.input_edit

        edit.insert_fraction_widget("10", "30", focus_target=None)
        edit.insertPlainText(" + ")
        edit.insert_fraction_widget("30", "30", focus_target=None)
        edit._handle_inline_evaluation()
        QApplication.processEvents()
        self.assertEqual(len(edit.frac_widgets), 3)

        # Select all
        edit.selectAll()
        QApplication.processEvents()

        # All 3 fraction widgets must remain intact
        self.assertEqual(len(edit.frac_widgets), 3)
        for w in edit.frac_widgets.values():
            self.assertTrue(w.isVisible())

    def test_fraction_decimal_roundtrip_91_3(self):
        """
        Verify the exact user scenario:
        1. 10/30 + 30 evaluates inline to 91/3.
        2. Converting 91/3 to decimal yields 30,3333333333.
        3. Right-clicking/converting 30,3333333333 back to fraction yields 91/3.
        4. Standalone decimal 1,25 resolves to 5/4 via decimal_to_fraction.
        """
        from ui.worksheet_cell import decimal_to_fraction
        # Test direct mathematical helper
        rat = decimal_to_fraction("30,3333333333")
        self.assertIsNotNone(rat)
        self.assertEqual(str(rat), "91/3")

        rat_125 = decimal_to_fraction("1,25")
        self.assertIsNotNone(rat_125)
        self.assertEqual(str(rat_125), "5/4")

        # Test UI flow in worksheet
        ws = self.window.new_worksheet()
        cell = ws.active_cell
        edit = cell.input_edit

        # Insert 10/30 + 30
        edit.insert_fraction_widget("10", "30", focus_target=None)
        edit.insertPlainText(" + 30")
        QApplication.processEvents()

        ok = edit._handle_inline_evaluation()
        self.assertTrue(ok)
        QApplication.processEvents()

        # Result fraction is 91/3
        fids = list(edit.frac_widgets.keys())
        self.assertEqual(len(fids), 2)
        res_frac = edit.frac_widgets[fids[1]]
        self.assertEqual(res_frac.num_edit.text(), "91")
        self.assertEqual(res_frac.den_edit.text(), "3")

        # Convert to decimal -> 30,3333333333
        res_frac.convert_to_decimal()
        QApplication.processEvents()
        plain = edit.toPlainText()
        self.assertTrue("30,3333333333" in plain or "30.3333333333" in plain)

        # Check that fraction history recorded 91/3
        self.assertTrue(hasattr(edit, "_frac_history"))
        self.assertIn("30,3333333333", edit._frac_history)
        self.assertEqual(edit._frac_history["30,3333333333"], ("91", "3"))

    def test_window_settings_persistence(self):
        """Verify that dock visibility and layout state are saved and restored."""
        from PyQt6.QtCore import QSettings
        settings = QSettings("J2K", "Calculator")
        settings.clear()

        # Create window 1 with context dock closed and custom palette width
        w1 = MainWindow()
        w1.show()
        QApplication.processEvents()

        self.assertFalse(w1.context_dock.isVisible())
        self.assertTrue(w1.palette_dock.isVisible())
        self.assertGreaterEqual(w1.palette_dock.width(), 260)

        # Toggle context dock on
        w1.context_dock.setVisible(True)
        QApplication.processEvents()
        w1.save_settings()
        w1.close()
        w1.deleteLater()

        # Create window 2 and load settings
        w2 = MainWindow()
        w2.show()
        QApplication.processEvents()

        # Must restore context dock as open
        self.assertTrue(w2.context_dock.isVisible())
        self.assertTrue(w2.palette_dock.isVisible())

        # Now close context dock and save
        w2.context_dock.setVisible(False)
        w2.save_settings()
        w2.close()
        w2.deleteLater()

        # Create window 3
        w3 = MainWindow()
        w3.show()
        QApplication.processEvents()
        self.assertFalse(w3.context_dock.isVisible())
        self.assertTrue(w3.palette_dock.isVisible())
        self.assertGreaterEqual(w3.palette_dock.width(), 260)
        w3.close()
        w3.deleteLater()


    def test_definite_integral_widget(self):
        """Verify 2D definite integral widget insertion, editing, navigation, and evaluation."""
        from PyQt6.QtGui import QKeyEvent
        from PyQt6.QtCore import QEvent
        from ui.worksheet_cell import DefiniteIntegralWidget
        from cas_engine.engine import CASEngine
        ws = self.window.new_worksheet()
        cell = ws.active_cell

        # 1. Insert template
        cell.insert_template(r"\int_a^b f")
        QApplication.processEvents()

        widgets = [w for w in cell.input_edit.frac_widgets.values() if isinstance(w, DefiniteIntegralWidget)]
        self.assertEqual(len(widgets), 1)
        w = widgets[0]

        self.assertEqual(w.a_edit.text(), "a")
        self.assertEqual(w.b_edit.text(), "b")
        self.assertEqual(w.f_edit.text(), "f")

        # 2. Modify values: a=0, b=1, f=x²
        w.a_edit.setText("0")
        w.b_edit.setText("1")
        w.f_edit.setText("x²")
        QApplication.processEvents()

        self.assertEqual(cell.get_input_text(), "integrate(x², (x, 0, 1))")

        # 3. Execution
        engine = CASEngine()
        cell.engine = engine
        res = engine.evaluate(cell.get_executable_text())
        cell.set_result(res)
        self.assertIsNotNone(cell.current_result)
        self.assertEqual(cell.current_result.exact_text, "1/3")

        # 4. Keyboard navigation: Tab from a -> b -> f
        w.a_edit.setFocus()
        ev_tab = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Tab, Qt.KeyboardModifier.NoModifier)
        w.a_edit.keyPressEvent(ev_tab)
        self.assertEqual(QApplication.focusWidget(), w.b_edit)

        w.b_edit.keyPressEvent(ev_tab)
        self.assertEqual(QApplication.focusWidget(), w.f_edit)

        # 5. Keyboard navigation: Up/Down between limits
        w.a_edit.setFocus()
        ev_up = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Up, Qt.KeyboardModifier.NoModifier)
        w.a_edit.keyPressEvent(ev_up)
        self.assertEqual(QApplication.focusWidget(), w.b_edit)

        ev_down = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Down, Qt.KeyboardModifier.NoModifier)
        w.b_edit.keyPressEvent(ev_down)
        self.assertEqual(QApplication.focusWidget(), w.a_edit)

        # 6. Toggle differential
        self.assertFalse(w.show_differential)
        w.toggle_differential()
        self.assertTrue(w.show_differential)
        self.assertTrue(w.x_edit.isVisible())
        self.assertEqual(w.x_edit.text(), "x")
        w.toggle_differential()
        self.assertFalse(w.show_differential)

        # 7. Backspace deletion on empty text
        w.f_edit.setText("")
        ev_bs = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Backspace, Qt.KeyboardModifier.NoModifier)
        w.f_edit.keyPressEvent(ev_bs)
        QApplication.processEvents()
        self.assertEqual(len(cell.input_edit.frac_widgets), 0)

    def test_nested_fractions_creation_and_evaluation(self):
        """Test creating and evaluating nested fractions like 1 / (3/20)."""
        from ui.worksheet_cell import FractionWidget, FractionSlot
        from cas_engine import CASEngine

        ws = self.window.new_worksheet()
        cell = ws.add_cell()

        # 1. Direct creation of 1 / (3/20)
        cell.input_edit.insert_fraction_widget(num="1", den="3/20", focus_target=None)
        self.assertEqual(len(cell.input_edit.frac_widgets), 1)
        frac = list(cell.input_edit.frac_widgets.values())[0]

        # Verify den_slot is a nested fraction
        self.assertTrue(frac.den_slot.is_fraction())
        self.assertEqual(frac.den_slot.child_frac.num_text(), "3")
        self.assertEqual(frac.den_slot.child_frac.den_text(), "20")
        self.assertEqual(frac.text_expression(), "(1)/((3)/(20))")

        # Verify CASEngine evaluates (1)/((3)/(20)) to 20/3
        engine = CASEngine()
        res = engine.evaluate(frac.text_expression())
        self.assertEqual(res.exact_text, "20/3")

        # 2. Interactive creation by typing '/' in denominator
        cell2 = ws.add_cell()
        cell2.input_edit.insert_fraction_widget(num="1", den="3", focus_target=None)
        frac2 = list(cell2.input_edit.frac_widgets.values())[0]
        self.assertFalse(frac2.den_slot.is_fraction())

        # Type '/' in denominator slot
        slash_ev = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Slash, Qt.KeyboardModifier.NoModifier, "/")
        frac2.den_slot.first_edit().keyPressEvent(slash_ev)
        self.assertTrue(frac2.den_slot.is_fraction())
        self.assertEqual(frac2.den_slot.child_frac.num_text(), "3")

        # Type '20' into nested denominator
        frac2.den_slot.child_frac.den_edit.setText("20")
        self.assertEqual(frac2.text_expression(), "(1)/((3)/(20))")

    def test_nested_fraction_template_insertion(self):
        """Test that clicking a fraction template while focused inside a slot nests the fraction."""
        ws = self.window.new_worksheet()
        cell = ws.add_cell()
        cell.input_edit.insert_fraction_widget(num="1", den="b", focus_target="den")
        frac = list(cell.input_edit.frac_widgets.values())[0]

        # Denominator line edit has focus
        frac.den_slot.first_edit().setFocus()
        frac.den_slot.first_edit().setText("3")

        # Insert fraction template \frac{a}{b}
        cell.insert_template(r"\frac{a}{b}")
        self.assertTrue(frac.den_slot.is_fraction())
        self.assertEqual(frac.den_slot.child_frac.num_text(), "3")
        self.assertEqual(frac.den_slot.child_frac.den_text(), "b")

    def test_load_saved_mw_with_fractions_and_no_errors(self):
        """
        Verify the exact user scenario: opening a saved .mw file faithfully restores 2D
        fractions (including nested fractions) and produces 0 errors on load.
        """
        import json
        ws = self.window.new_worksheet()
        saved_doc = {
            "version": "2021",
            "is_worksheet_mode": True,
            "cells": [
                {
                    "cell_id": "cell_1",
                    "execution_idx": 1,
                    "input": "(1)/(R) = (1)/(10) + (1)/(20) = (3)/(20)",
                    "input_mode": "2d_math",
                    "is_worksheet_mode": True,
                    "spans": [
                        {
                            "mode": "2d_math",
                            "text": "(1)/(R) = (1)/(10) + (1)/(20) = (3)/(20)"
                        }
                    ]
                },
                {
                    "cell_id": "cell_2",
                    "execution_idx": 2,
                    "input": "R := (1)/(3/20) = (20)/(3) = 6,667",
                    "input_mode": "2d_math",
                    "is_worksheet_mode": True,
                    "spans": [
                        {
                            "mode": "2d_math",
                            "text": "R := (1)/(3/20) = (20)/(3) = 6,667"
                        }
                    ]
                }
            ]
        }

        ws.load_from_json(json.dumps(saved_doc))
        self.assertEqual(len(ws.cells), 2)

        # Check Cell 1: 4 fractions restored as 2D FractionWidgets
        cell1 = ws.cells[0]
        self.assertEqual(len(cell1.input_edit.frac_widgets), 4)
        f_list1 = list(cell1.input_edit.frac_widgets.values())
        self.assertEqual(f_list1[0].text_expression(), "(1)/(R)")
        self.assertEqual(f_list1[1].text_expression(), "(1)/(10)")
        self.assertEqual(f_list1[2].text_expression(), "(1)/(20)")
        self.assertEqual(f_list1[3].text_expression(), "(3)/(20)")
        self.assertFalse(cell1.lbl_error.isVisible())
        self.assertFalse(cell1.error_box.isVisible())

        # Check Cell 2: 2 fractions restored, with first fraction containing a nested fraction
        cell2 = ws.cells[1]
        self.assertEqual(len(cell2.input_edit.frac_widgets), 2)
        f_list2 = list(cell2.input_edit.frac_widgets.values())
        frac_nested = f_list2[0]
        self.assertTrue(frac_nested.den_slot.is_fraction())
        self.assertEqual(frac_nested.den_slot.child_frac.num_text(), "3")
        self.assertEqual(frac_nested.den_slot.child_frac.den_text(), "20")
        self.assertEqual(f_list2[1].text_expression(), "(20)/(3)")
        self.assertFalse(cell2.lbl_error.isVisible())
        self.assertFalse(cell2.error_box.isVisible())

        # Roundtrip to_json and load_from_json preserves everything
        json_exported = ws.to_json()
        ws2 = self.window.new_worksheet()
        ws2.load_from_json(json_exported)
        self.assertEqual(len(ws2.cells), 2)
        self.assertEqual(len(ws2.cells[0].input_edit.frac_widgets), 4)
        self.assertEqual(len(ws2.cells[1].input_edit.frac_widgets), 2)
        self.assertFalse(ws2.cells[0].lbl_error.isVisible())
        self.assertFalse(ws2.cells[1].lbl_error.isVisible())

    def test_fraction_numbers_centered(self):
        from ui.worksheet_cell import FractionWidget
        cell = self.window.new_worksheet().cells[0]
        fw = FractionWidget(num="1", den="20", parent_edit=cell.input_edit)
        fw.show()

        # Check that slot widths span the full fraction bar width
        self.assertEqual(fw.num_slot.width(), fw.width())
        self.assertEqual(fw.den_slot.width(), fw.width())

        # Check that line edit texts are centered
        self.assertTrue(bool(fw.num_slot.edit.alignment() & Qt.AlignmentFlag.AlignCenter))
        self.assertTrue(bool(fw.den_slot.edit.alignment() & Qt.AlignmentFlag.AlignCenter))

        # Check nested fraction centering
        fw_nested = FractionWidget(num="1", den="3/20", parent_edit=cell.input_edit)
        fw_nested.show()
        self.assertTrue(fw_nested.den_slot.is_fraction())
        self.assertEqual(fw_nested.num_slot.width(), fw_nested.width())
        self.assertEqual(fw_nested.den_slot.width(), fw_nested.width())
        child = fw_nested.den_slot.child_frac
        self.assertIsNotNone(child)
        # Nested fraction's slots also span its own width and are centered
        self.assertEqual(child.num_slot.width(), child.width())
        self.assertEqual(child.den_slot.width(), child.width())
        self.assertTrue(bool(child.num_slot.edit.alignment() & Qt.AlignmentFlag.AlignCenter))
        self.assertTrue(bool(child.den_slot.edit.alignment() & Qt.AlignmentFlag.AlignCenter))

    def test_two_fractions_next_to_each_other_in_fraction(self):
        """Test placing two fractions next to each other in a fraction slot, e.g. 1 / (1/30 + 1/30)."""
        from ui.worksheet_cell import FractionWidget
        from cas_engine import CASEngine

        ws = self.window.new_worksheet()
        cell = ws.add_cell()

        # 1. Direct creation from string with two fractions in denominator
        cell.input_edit.insert_fraction_widget(num="1", den="(1)/(30) + (1)/(30)", focus_target=None)
        frac = list(cell.input_edit.frac_widgets.values())[0]

        self.assertTrue(frac.den_slot.is_fraction())
        self.assertEqual(len(frac.den_slot.child_fracs), 2)
        self.assertEqual(frac.den_slot.child_fracs[0].text_expression(), "(1)/(30)")
        self.assertEqual(frac.den_slot.child_fracs[1].text_expression(), "(1)/(30)")
        self.assertEqual(frac.text_expression(), "(1)/((1)/(30) + (1)/(30))")

        # Evaluate via CAS engine -> 15
        engine = CASEngine()
        res = engine.evaluate(frac.text_expression())
        self.assertEqual(res.exact_text, "15")

        # 2. Interactive creation: type 1/ in denominator, then Right Arrow, then +, then 1/30
        cell2 = ws.add_cell()
        cell2.input_edit.insert_fraction_widget(num="1", den="b", focus_target="den")
        frac2 = list(cell2.input_edit.frac_widgets.values())[0]

        # In denominator edit, type 1 then /
        den_ed = frac2.den_slot.first_edit()
        den_ed.setText("1")
        ev_slash = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Slash, Qt.KeyboardModifier.NoModifier, "/")
        den_ed.keyPressEvent(ev_slash)
        QApplication.processEvents()

        self.assertEqual(len(frac2.den_slot.child_fracs), 1)
        child1 = frac2.den_slot.child_fracs[0]
        # Type 30 into child1 denominator
        child1.den_slot.first_edit().setText("30")
        self.assertEqual(child1.text_expression(), "(1)/(30)")

        # Press Right Arrow in child1 denominator -> MUST move to edit between, NOT out of fraction!
        child1_den_ed = child1.den_slot.first_edit()
        child1_den_ed.setFocus()
        QApplication.processEvents()
        child1_den_ed.setCursorPosition(len(child1_den_ed.text()))
        ev_right = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Right, Qt.KeyboardModifier.NoModifier)
        child1_den_ed.keyPressEvent(ev_right)
        QApplication.processEvents()

        cur_focus = QApplication.focusWidget()
        # Verify focus is still INSIDE frac2.den_slot!
        self.assertIn(cur_focus, frac2.den_slot.items)
        self.assertEqual(cur_focus, frac2.den_slot.items[2])

        # Type ' + ' and '1'
        cur_focus.setText(" + 1")
        cur_focus.setCursorPosition(len(cur_focus.text()))
        # Type '/' to create second fraction next to the first
        cur_focus.keyPressEvent(ev_slash)
        QApplication.processEvents()

        self.assertEqual(len(frac2.den_slot.child_fracs), 2)
        child2 = frac2.den_slot.child_fracs[1]
        child2.den_slot.first_edit().setText("30")
        QApplication.processEvents()

        self.assertEqual(frac2.text_expression(), "(1)/((1)/(30) + (1)/(30))")
        res2 = engine.evaluate(frac2.text_expression())
        self.assertEqual(res2.exact_text, "15")

    def test_status_bar_profile_path_editable_memory_time(self):
        """Test status bar features: Default Profile, dynamic file path, 'Save Document' in red, editable toggle, memory and time."""
        import tempfile
        win = MainWindow()
        # 1. Profile label must say "Default Profile"
        self.assertEqual(win.lbl_profile.text(), "Default Profile")

        # 2. On Start Page, path is empty and editable checkbox is disabled
        self.assertIsNone(win.worksheet)
        self.assertEqual(win.lbl_path.text(), "")
        self.assertFalse(win.chk_editable.isEnabled())

        # 3. Create a new worksheet -> path is "Save Document" in red text, editable is True
        win.new_worksheet()
        ws = win.worksheet
        self.assertIsNotNone(ws)
        self.assertEqual(win.lbl_path.text(), "Save Document")
        self.assertIn("#dc2626", win.lbl_path.styleSheet())
        self.assertTrue(win.chk_editable.isEnabled())
        self.assertTrue(win.chk_editable.isChecked())
        self.assertTrue(ws.is_editable)
        self.assertFalse(ws.cells[0].input_edit.isReadOnly())

        # 4. Test toggling editable mode
        win.chk_editable.setChecked(False)
        self.assertFalse(ws.is_editable)
        self.assertTrue(ws.cells[0].input_edit.isReadOnly())
        self.assertEqual(win.chk_editable.text(), "View Mode (Click to Edit)")
        self.assertFalse(ws.view_mode_banner.isHidden())

        # Test typing in view mode: MUST NOT CRASH and MUST NOT MUTATE
        initial_text = ws.cells[0].get_input_text()
        key_ev = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_A, Qt.KeyboardModifier.NoModifier, "a")
        ws.cells[0].input_edit.keyPressEvent(key_ev)
        self.assertEqual(ws.cells[0].get_input_text(), initial_text)

        # Test clicking 'Enable Editing' button on banner
        ws.btn_enable_edit.click()
        self.assertTrue(ws.is_editable)
        self.assertFalse(ws.cells[0].input_edit.isReadOnly())
        self.assertTrue(ws.view_mode_banner.isHidden())
        self.assertEqual(win.chk_editable.text(), "Editable")

        # 5. Test saving worksheet updates file path display
        with tempfile.NamedTemporaryFile(suffix=".mw", delete=False) as tf:
            temp_path = tf.name
        try:
            ws.cells[0].set_input_text("2 + 2")
            win.worksheet.file_path = os.path.abspath(temp_path)
            win.save_worksheet()
            self.assertEqual(win.lbl_path.text(), os.path.abspath(temp_path))
            self.assertNotIn("#dc2626", win.lbl_path.styleSheet())

            # 6. Test memory display format
            win._update_memory_display()
            self.assertTrue(win.lbl_memory.text().startswith("Memory: "))
            self.assertTrue(win.lbl_memory.text().endswith("M"))

            # 7. Test time display update
            win._on_execution_time_changed(0.05)
            self.assertEqual(win.lbl_time.text(), "Time: 0.05s")

            # 8. Test zoom reset via status bar
            ws.set_zoom(170)
            self.assertEqual(win.lbl_zoom.text(), "Zoom: 170%")
            # Trigger mousePressEvent on zoom label
            win.lbl_zoom.mousePressEvent(None)
            self.assertEqual(ws.zoom_percent, 100)
            self.assertEqual(win.lbl_zoom.text(), "Zoom: 100%")
        finally:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass
            win.close()

    def test_plot_buttons_removed_and_context_menu(self):
        """Verify buttons on plots are removed and actions only appear on plot right-click."""
        win = MainWindow()
        try:
            win.new_worksheet()
            ws = win.worksheet
            self.assertIsNotNone(ws)
            cell = ws.cells[0]

            res = win.engine.evaluate("plot(sin(x))")
            cell.set_result(res)

            # 1. Verify plot container is visible
            self.assertFalse(cell.plot_container.isHidden())

            # 2. Verify NO QPushButton exists in plot container (buttons removed)
            btns = cell.plot_container.findChildren(QPushButton)
            self.assertEqual(len(btns), 0)

            # 3. Verify right click on canvas triggers plot context menu
            self.assertTrue(hasattr(cell, '_current_plot_canvas'))
            canvas = cell._current_plot_canvas
            self.assertIsNotNone(canvas)

            captured_actions = []
            orig_exec = QMenu.exec
            try:
                def mock_exec(menu_obj, *args, **kwargs):
                    captured_actions.extend([a.text() for a in menu_obj.actions()])
                    return None
                QMenu.exec = mock_exec

                # Trigger plot context menu
                captured_actions.clear()
                cell._show_plot_context_menu(QPoint(100, 100))
                self.assertTrue(any("Copy Plot" in a for a in captured_actions))
                self.assertTrue(any("Save Plot" in a for a in captured_actions))
                self.assertTrue(any("Remove Plot" in a for a in captured_actions))
                self.assertTrue(any("Y-Axis Label" in a for a in captured_actions))
                self.assertTrue(any("X-Axis Label" in a for a in captured_actions))
                self.assertTrue(any("Reset Positions" in a for a in captured_actions))

                # Verify draggable axis labels exist
                self.assertGreaterEqual(len(cell._current_plot_draggables), 2)

                # Trigger cell context menu -> verify plot actions do NOT appear
                captured_actions.clear()
                cell._show_cell_context_menu(QPoint(100, 100))
                self.assertFalse(any("Copy Plot" in a for a in captured_actions))
                self.assertFalse(any("Save Plot" in a for a in captured_actions))

                # Test executing copy and save handlers
                cell._current_plot_copy_fn()

                import tempfile
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tf:
                    tmp_fn = tf.name
                orig_save_dialog = QFileDialog.getSaveFileName
                try:
                    QFileDialog.getSaveFileName = lambda *args, **kwargs: (tmp_fn, "PNG Image (*.png)")
                    cell._current_plot_save_fn()
                    self.assertTrue(os.path.exists(tmp_fn))
                    self.assertGreater(os.path.getsize(tmp_fn), 0)
                finally:
                    QFileDialog.getSaveFileName = orig_save_dialog
                    if os.path.exists(tmp_fn):
                        try:
                            os.remove(tmp_fn)
                        except Exception:
                            pass
            finally:
                QMenu.exec = orig_exec
        finally:
            win.close()

    def test_plot_legend_clamping_and_above_plot_options(self):
        """Test that plot legends with multiple curves have sufficient headroom,
        are clamped so they cannot be dragged off-canvas at the top,
        and context menu offers 'Above Plot' options."""
        win = MainWindow()
        try:
            ws = win.new_worksheet()
            cell = ws.cells[0]

            # Multi-curve plot like in user's report
            res = win.engine.evaluate("plot([2*x + 1, 4 - x, 0.5*x - 2])")
            cell.set_result(res)

            canvas = getattr(cell, '_current_plot_canvas', None)
            self.assertIsNotNone(canvas)
            fig = getattr(cell, '_current_plot_fig', None)
            leg = getattr(cell, '_current_plot_legend', None)
            self.assertIsNotNone(leg)

            # Check canvas dimensions match figure
            self.assertEqual(canvas.width(), 560)
            self.assertEqual(canvas.height(), 380)

            # Check that "Function Plot" and emoji "📈" are removed
            from PyQt6.QtWidgets import QLabel
            labels = cell.plot_container.findChildren(QLabel)
            label_texts = [lbl.text() for lbl in labels]
            self.assertFalse(any("Function Plot" in txt for txt in label_texts))
            self.assertFalse(any("📈" in txt for txt in label_texts))

            # Check draggable legend is clamped within canvas
            dleg = getattr(leg, '_draggable', None)
            self.assertIsNotNone(dleg)
            dleg.save_offset()
            # Try dragging way past top boundary
            dleg.update_offset(0, 1000)
            dleg.finalize_offset()
            fig.canvas.draw()

            r = fig.canvas.get_renderer()
            bbox = leg.get_window_extent(r)
            # Legend top must stay within figure/canvas height
            self.assertLessEqual(bbox.y1, fig.bbox.height)
            self.assertGreaterEqual(bbox.y1, fig.bbox.height - 15)

            # Check context menu includes Above Plot options
            captured_actions = []
            orig_exec = QMenu.exec
            try:
                def mock_exec(menu_obj, *args, **kwargs):
                    for a in menu_obj.actions():
                        captured_actions.append(a.text())
                        if a.menu():
                            for sub_a in a.menu().actions():
                                captured_actions.append(sub_a.text())
                    return None
                QMenu.exec = mock_exec
                cell._show_plot_context_menu(QPoint(100, 100))
                self.assertTrue(any("Above Plot (Middle Top)" in a for a in captured_actions))
                self.assertTrue(any("Above Plot (Top Right)" in a for a in captured_actions))
            finally:
                QMenu.exec = orig_exec
        finally:
            win.close()

    def test_export_pdf_dialog_and_unfold_sections(self):
        """Test PDF export dialog, menu item, unfolding collapsed sections, and PDF export."""
        from ui.main_window import ExportPdfDialog
        import tempfile

        # 1. Verify ExportPdfDialog options and default state
        dlg = ExportPdfDialog()
        self.assertTrue(dlg.should_unfold_all(), "Checkbox should be checked by default")
        dlg.chk_unfold.setChecked(False)
        self.assertFalse(dlg.should_unfold_all())
        dlg.close()

        # 2. Verify MainWindow File menu contains 'Export as PDF (.pdf)...'
        win = MainWindow()
        try:
            self.assertTrue(hasattr(win, 'act_export_pdf'))
            self.assertEqual(win.act_export_pdf.text(), "Export as PDF (.pdf)...")

            file_menu = win.menuBar().actions()[0].menu()
            file_action_texts = [a.text() for a in file_menu.actions()]
            self.assertIn("Export as PDF (.pdf)...", file_action_texts)

            # 3. Create document with collapsible sections (e.g. Problem 1)
            ws = win.new_worksheet()
            # Set first cell as section header
            cell1 = ws.cells[0]
            cell1.is_section_header = True
            cell1.section_level = 1
            cell1.section_title = "Problem 1"
            if hasattr(cell1, 'init_section_header_ui'):
                cell1.init_section_header_ui()

            # Add child cells under Problem 1
            cell2 = ws.add_cell("diff(sin(x), x)")
            cell2.execute()

            # Collapse section 1
            cell1.is_collapsed = True
            ws._on_section_toggled(cell1.cell_id, True)
            self.assertTrue(cell2.isHidden(), "Child cell should be hidden when section is collapsed")

            # Verify expand_all_sections unfolds and unhides all cells
            ws.expand_all_sections()
            self.assertFalse(cell1.is_collapsed, "Section should be marked not collapsed")
            self.assertFalse(cell2.isHidden(), "Child cell should be visible after expand_all_sections")

            # 4. Verify export_to_pdf writes a valid PDF
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
                pdf_path = f.name
            try:
                ws.export_to_pdf(pdf_path)
                self.assertTrue(os.path.exists(pdf_path))
                self.assertGreater(os.path.getsize(pdf_path), 500)
                with open(pdf_path, 'rb') as pf:
                    header = pf.read(5)
                    self.assertEqual(header, b"%PDF-")
            finally:
                if os.path.exists(pdf_path):
                    try:
                        os.remove(pdf_path)
                    except Exception:
                        pass

            # 5. Test MainWindow.export_pdf workflow with dialog confirmation
            from unittest.mock import patch
            cell1.is_collapsed = True
            ws._on_section_toggled(cell1.cell_id, True)
            self.assertTrue(cell2.isHidden())

            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
                win_pdf_path = f.name

            try:
                with patch.object(ExportPdfDialog, 'exec', return_value=QDialog.DialogCode.Accepted):
                    with patch('PyQt6.QtWidgets.QFileDialog.getSaveFileName', return_value=(win_pdf_path, 'PDF Document (*.pdf)')):
                        win.export_pdf()

                # Should have unfolded sections and exported successfully
                self.assertFalse(cell1.is_collapsed)
                self.assertFalse(cell2.isHidden())
                self.assertTrue(os.path.exists(win_pdf_path))
                self.assertGreater(os.path.getsize(win_pdf_path), 500)
            finally:
                if os.path.exists(win_pdf_path):
                    try:
                        os.remove(win_pdf_path)
                    except Exception:
                        pass
        finally:
            win.close()

    def test_toolbar_buttons_removed_and_2d_math_combo_removed(self):
        """Test that 2D Math dropdown and Cut/Copy/Paste/Text/Math toolbar buttons are removed."""
        win = MainWindow()
        try:
            # 1. Verify 2D Math combo is removed from MainWindow
            self.assertFalse(hasattr(win, 'combo_math_mode'))

            # Verify no QComboBox in context bar contains "2D Math"
            from PyQt6.QtWidgets import QComboBox
            context_bar_combos = win.context_toolbar.findChildren(QComboBox)
            for cb in context_bar_combos:
                combo_items = [cb.itemText(i) for i in range(cb.count())]
                self.assertNotIn("2D Math", combo_items)

            # 2. Verify main toolbar buttons
            from PyQt6.QtWidgets import QPushButton
            main_toolbar_buttons = win.main_toolbar.findChildren(QPushButton)
            btn_texts = [b.text().strip() for b in main_toolbar_buttons]

            # Removed buttons: Cut, Copy, Paste, T Text, [> Math
            self.assertNotIn("Cut", btn_texts)
            self.assertNotIn("Copy", btn_texts)
            self.assertNotIn("Paste", btn_texts)
            self.assertNotIn("T Text", btn_texts)
            self.assertNotIn("[> Math", btn_texts)

            # Retained buttons: Undo, Redo, Eval, Eval All, Stop
            self.assertIn("Undo", btn_texts)
            self.assertIn("Redo", btn_texts)
            self.assertTrue(any("Eval" in t for t in btn_texts))
            self.assertTrue(any("Stop" in t for t in btn_texts))

            # 3. Verify mode buttons still work properly without the combo
            ws = win.new_worksheet()
            cell = ws.cells[0]

            win.btn_mode_text.click()
            self.assertEqual(cell.input_mode, "text")
            self.assertEqual(win.lbl_mode.text(), "Text Mode")

            win.btn_mode_math.click()
            self.assertEqual(cell.input_mode, "2d_math")
            self.assertEqual(win.lbl_mode.text(), "Math Mode")

            win.btn_mode_nonexec.click()
            self.assertEqual(cell.input_mode, "nonexec_math")
            self.assertEqual(win.lbl_mode.text(), "Nonexecutable Math")

            win.btn_c.click()
            self.assertEqual(cell.input_mode, "1d_math")
            self.assertEqual(win.lbl_mode.text(), "1D Math")
        finally:
            win.close()

    def test_popups_and_dialogs_light_theme_readable(self):
        """Test that dialogs, message boxes, and popups always have a readable light theme."""
        from ui.theme import Theme
        from PyQt6.QtWidgets import QMessageBox

        # 1. Test dialog palette enforces bright white theme
        pal = Theme.get_dialog_palette()
        self.assertEqual(pal.color(QPalette.ColorRole.Window).name(), "#ffffff")
        self.assertEqual(pal.color(QPalette.ColorRole.WindowText).name(), "#0f172a")
        self.assertEqual(pal.color(QPalette.ColorRole.Base).name(), "#ffffff")

        # 2. Test QSS includes light theme rules for QDialog and QMessageBox in both modes
        for mode in ("light", "dark"):
            qss = Theme.get_qss(mode)
            self.assertIn("QDialog, QMessageBox", qss)
            self.assertIn("background-color: #ffffff;", qss)
            self.assertIn("color: #0f172a;", qss)

        # 3. Test QMessageBox rendering under MainWindow
        win = MainWindow()
        try:
            msg = QMessageBox(
                QMessageBox.Icon.Critical,
                "Error Loading Worksheet",
                "Expecting value line 1 column 1 (char 1)",
                parent=win
            )
            app = QApplication.instance()
            self.assertIsNotNone(app)
            self.assertIn("background-color: #ffffff", app.styleSheet())
            msg.close()
        finally:
            win.close()

    def test_loading_overlay_on_open_project(self):
        """Test that LoadingOverlay is integrated into MainWindow and used during project loading."""
        import tempfile
        from ui.loading_overlay import LoadingOverlay

        win = MainWindow()
        try:
            self.assertTrue(hasattr(win, 'loading_overlay'))
            self.assertIsInstance(win.loading_overlay, LoadingOverlay)
            self.assertTrue(win.loading_overlay.isHidden())

            # Test progress bar & status updates
            win.loading_overlay.show_loading("test_project.mw", "Reading worksheet archive...")
            self.assertFalse(win.loading_overlay.isHidden())
            self.assertIn("test_project.mw", win.loading_overlay.lbl_filename.text())
            self.assertEqual(win.loading_overlay.lbl_status.text(), "Reading worksheet archive...")

            win.loading_overlay.set_progress(5, 10, "Loading element 5 of 10...")
            self.assertEqual(win.loading_overlay.progress_bar.value(), 5)
            self.assertEqual(win.loading_overlay.progress_bar.maximum(), 10)
            self.assertEqual(win.loading_overlay.lbl_status.text(), "Loading element 5 of 10...")

            win.loading_overlay.hide_loading()
            self.assertTrue(win.loading_overlay.isHidden())

            # Test loading actual file through load_worksheet_from_file
            content = """{
                "is_worksheet_mode": true,
                "cells": [
                    {"cell_type": "math", "input_text": "f(x) := x^2", "output_text": "x^2"},
                    {"cell_type": "text", "input_text": "Some notes here", "output_text": ""}
                ]
            }"""
            with tempfile.NamedTemporaryFile("w", suffix=".mw", delete=False, encoding="utf-8") as tf:
                tf.write(content)
                temp_path = tf.name

            try:
                win.load_worksheet_from_file(temp_path)
                self.assertIsNotNone(win.worksheet)
                self.assertEqual(len(win.worksheet.cells), 2)
                # Overlay should be hidden when loading finishes
                self.assertTrue(win.loading_overlay.isHidden())
            finally:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
        finally:
            win.close()

    def test_scrollbar_visibility_and_wheel_scrolling(self):
        """Verify high-contrast 16px scrollbar styling and wheel scrolling propagation through cells."""
        from PyQt6.QtGui import QWheelEvent
        from PyQt6.QtCore import QPointF, QPoint

        ws = self.window.new_worksheet()
        ws.resize(800, 400)
        for i in range(25):
            c = ws.add_cell()
            c.input_edit.setPlainText(f"x_{i} := {i} * 100")
        ws.scroll_area.resize(800, 400)
        ws.container.setMinimumHeight(3000)
        QApplication.processEvents()

        vbar = ws.scroll_area.verticalScrollBar()
        # Verify singleStep and stylesheet definition
        self.assertEqual(vbar.singleStep(), 30)
        stylesheet = ws.scroll_area.styleSheet()
        self.assertIn("16px", stylesheet)
        self.assertIn("#94a3b8", stylesheet)
        self.assertIn("#64748b", stylesheet)
        self.assertIn("#334155", stylesheet)

        # Verify wheel scrolling over cell input_edit
        vbar.setValue(100)
        QApplication.processEvents()
        current_val = vbar.value()

        cell = ws.cells[0]
        ev_scroll = QWheelEvent(
            QPointF(10, 10), QPointF(10, 10), QPoint(0, 0), QPoint(0, -120),
            Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.NoScrollPhase, False
        )
        cell.input_edit.wheelEvent(ev_scroll)
        QApplication.processEvents()
        self.assertGreater(vbar.value(), current_val)

        # Verify wheel scrolling over cell frame
        val_before_frame = vbar.value()
        cell.wheelEvent(ev_scroll)
        QApplication.processEvents()
        self.assertGreater(vbar.value(), val_before_frame)

        # Verify Ctrl+wheel triggers zoom rather than scroll
        val_before_zoom = vbar.value()
        initial_zoom = ws.zoom_percent
        ev_zoom = QWheelEvent(
            QPointF(10, 10), QPointF(10, 10), QPoint(0, 0), QPoint(0, 120),
            Qt.MouseButton.NoButton, Qt.KeyboardModifier.ControlModifier, Qt.ScrollPhase.NoScrollPhase, False
        )
        cell.input_edit.wheelEvent(ev_zoom)
        QApplication.processEvents()
        self.assertGreater(ws.zoom_percent, initial_zoom)
        self.assertEqual(vbar.value(), val_before_zoom)

    def test_line_spacing_and_font_size_selection_behavior(self):
        """Verify line spacing dropdown and selection vs unselected text behavior for line spacing and font size."""
        from PyQt6.QtGui import QTextCursor

        # 1. Verify line spacing toolbar controls exist and contain standard options
        self.assertTrue(hasattr(self.window, 'btn_line_spacing'))
        options = list(self.window.line_spacing_actions.keys())
        for expected in ["1.0", "1.15", "1.25", "1.5", "2.0", "2.5", "3.0"]:
            self.assertIn(expected, options)

        ws = self.window.new_worksheet()

        # 2. Line spacing on selected text only
        cell1 = ws.add_cell()
        cell1.input_edit.setPlainText("Line A\nLine B\nLine C")
        edit1 = cell1.input_edit
        c1 = edit1.textCursor()
        c1.setPosition(7) # start of Line B
        c1.setPosition(13, QTextCursor.MoveMode.KeepAnchor) # select Line B
        edit1.setTextCursor(c1)
        self.window._on_line_spacing_changed("2.0")

        b0 = edit1.document().findBlockByNumber(0)
        b1 = edit1.document().findBlockByNumber(1)
        b2 = edit1.document().findBlockByNumber(2)
        self.assertEqual(b0.blockFormat().lineHeight(), 0.0)
        self.assertEqual(b1.blockFormat().lineHeight(), 200.0)
        self.assertEqual(b2.blockFormat().lineHeight(), 0.0)

        # 3. Line spacing with NO selection (applies only to current/next block)
        c1.setPosition(edit1.document().characterCount() - 1)
        edit1.setTextCursor(c1) # cursor at end of Line C, no selection
        self.window._on_line_spacing_changed("1.5")
        self.assertEqual(edit1.document().findBlockByNumber(0).blockFormat().lineHeight(), 0.0)
        self.assertEqual(edit1.document().findBlockByNumber(1).blockFormat().lineHeight(), 200.0)
        self.assertEqual(edit1.document().findBlockByNumber(2).blockFormat().lineHeight(), 150.0)

        # 4. Font size on selected text only
        cell2 = ws.add_cell()
        cell2.input_edit.setPlainText("Normal and Big")
        edit2 = cell2.input_edit
        c2 = edit2.textCursor()
        c2.setPosition(11)
        c2.setPosition(14, QTextCursor.MoveMode.KeepAnchor) # select 'Big'
        edit2.setTextCursor(c2)
        self.window._on_font_size_changed("24")

        c_norm = QTextCursor(edit2.document())
        c_norm.setPosition(3)
        self.assertNotEqual(c_norm.charFormat().fontPointSize(), 24.0)
        c_big = QTextCursor(edit2.document())
        c_big.setPosition(12)
        self.assertEqual(c_big.charFormat().fontPointSize(), 24.0)

        # 5. Font size with NO selection (applies only to upcoming typing, not existing text)
        c2.movePosition(QTextCursor.MoveOperation.End)
        edit2.setTextCursor(c2)
        self.window._on_font_size_changed("36")
        # Ensure existing text wasn't changed
        c_norm2 = QTextCursor(edit2.document())
        c_norm2.setPosition(3)
        self.assertNotEqual(c_norm2.charFormat().fontPointSize(), 36.0)
        # Type new text and verify it receives 36.0
        edit2.insertPlainText(" EXTRA")
        c_extra = QTextCursor(edit2.document())
        c_extra.setPosition(edit2.document().characterCount() - 2)
        self.assertEqual(c_extra.charFormat().fontPointSize(), 36.0)

    def test_enter_newlines_on_empty_lines_does_not_crash(self):
        """Verify pressing Enter repeatedly on empty lines to create space does not crash or exit."""
        from PyQt6.QtTest import QTest
        ws = self.window.new_worksheet()
        cell = ws.add_cell()
        edit = cell.input_edit
        edit.setFocus()
        QApplication.processEvents()

        # Type multiple lines of text
        for word in ['potato', 'potato', 'poato', 'potato']:
            QTest.keyClicks(edit, word)
            QTest.keyClick(edit, Qt.Key.Key_Return)
            QApplication.processEvents()

        initial_blocks = edit.document().blockCount()
        self.assertEqual(initial_blocks, 5)

        # Press Enter multiple times on the empty line to make vertical whitespace
        for _ in range(5):
            QTest.keyClick(edit, Qt.Key.Key_Return)
            QApplication.processEvents()

        self.assertEqual(edit.document().blockCount(), 10)

        # Also test on a fresh empty cell
        cell_empty = ws.add_cell()
        edit_empty = cell_empty.input_edit
        edit_empty.setFocus()
        QApplication.processEvents()
        self.assertEqual(edit_empty.document().blockCount(), 1)
        for _ in range(4):
            QTest.keyClick(edit_empty, Qt.Key.Key_Return)
            QApplication.processEvents()
        self.assertEqual(edit_empty.document().blockCount(), 5)

    def test_simplified_20_color_palette(self):
        """Verify the simplified 20-color palette for font color and highlight."""
        from ui.main_window import COMMON_20_COLORS, ColorPaletteMenu
        from PyQt6.QtGui import QColor

        # 1. Verify exactly 20 colors are defined
        self.assertEqual(len(COMMON_20_COLORS), 20)

        ws = self.window.new_worksheet()
        cell = ws.add_cell()
        edit = cell.input_edit
        edit.setPlainText("Text with color")
        c = edit.textCursor()
        c.select(c.SelectionType.Document)
        edit.setTextCursor(c)

        # 2. Test applying font color
        red = QColor("#dc2626")
        self.window._apply_text_color(red)
        self.assertEqual(self.window.btn_text_color.current_color().name().lower(), "#dc2626")
        self.assertEqual(edit.textCursor().charFormat().foreground().color().name().lower(), "#dc2626")

        # 3. Test applying highlight color (pastel yellow)
        pastel_yellow = QColor("#fef08a")
        self.window._apply_highlight_color(pastel_yellow)
        self.assertEqual(self.window.btn_highlight.current_color().name().lower(), "#fef08a")
        self.assertEqual(edit.textCursor().charFormat().background().color().name().lower(), "#fef08a")

        # 4. Test resetting font color
        self.window._on_text_color_reset()
        self.assertEqual(self.window.btn_text_color.current_color().name().lower(), "#000000")
        self.assertEqual(edit.textCursor().charFormat().foreground().color().name().lower(), "#000000")

        # 5. Test resetting highlight color
        self.window._on_highlight_reset()
        self.assertEqual(self.window.btn_highlight.current_color().name().lower(), "#ffff00")
        self.assertEqual(edit.textCursor().charFormat().background().style(), Qt.BrushStyle.NoBrush)

        # 6. Verify menu components
        menu_text = ColorPaletteMenu(
            self.window.btn_text_color, False,
            self.window._apply_text_color, self.window._on_text_color_reset,
            None, 'light', self.window
        )
        self.assertIsNotNone(menu_text)

        menu_hl = ColorPaletteMenu(
            self.window.btn_highlight, True,
            self.window._apply_highlight_color, self.window._on_highlight_reset,
            None, 'light', self.window
        )
        self.assertIsNotNone(menu_hl)

    def test_continuous_typing_retains_color_and_highlight(self):
        """Verify that typing continuously without selection preserves font color and highlight across all letters."""
        from PyQt6.QtGui import QColor, QKeyEvent, QTextFormat
        from PyQt6.QtCore import Qt, QEvent

        ws = self.window.new_worksheet()
        cell = ws.add_cell()
        edit = cell.input_edit

        # 1. Set font color red (#dc2626) without text selection
        edit.set_text_color(QColor("#dc2626"))

        # Type 'potato' letter by letter
        for ch in 'potato':
            ev = QKeyEvent(QEvent.Type.KeyPress, 0, Qt.KeyboardModifier.NoModifier, ch)
            edit.keyPressEvent(ev)

        self.assertEqual(edit.toPlainText(), "potato")
        # Every single letter must retain the red foreground color
        for i in range(len("potato")):
            c = edit.textCursor()
            c.setPosition(i)
            c.setPosition(i + 1, c.MoveMode.KeepAnchor)
            cf = c.charFormat()
            self.assertTrue(cf.hasProperty(QTextFormat.Property.ForegroundBrush))
            self.assertEqual(cf.foreground().color().name().lower(), "#dc2626")
            self.assertFalse(cf.hasProperty(QTextFormat.Property.BackgroundBrush) and cf.background().style() != Qt.BrushStyle.NoBrush)

        # 2. Add green highlight (#22c55e) and type 'chips'
        edit.set_highlight_color(QColor("#22c55e"))
        for ch in 'chips':
            ev = QKeyEvent(QEvent.Type.KeyPress, 0, Qt.KeyboardModifier.NoModifier, ch)
            edit.keyPressEvent(ev)

        self.assertEqual(edit.toPlainText(), "potatochips")
        # 'potato' characters must STILL have no highlight, and red foreground
        for i in range(len("potato")):
            c = edit.textCursor()
            c.setPosition(i)
            c.setPosition(i + 1, c.MoveMode.KeepAnchor)
            cf = c.charFormat()
            self.assertEqual(cf.foreground().color().name().lower(), "#dc2626")
            self.assertFalse(cf.hasProperty(QTextFormat.Property.BackgroundBrush) and cf.background().style() != Qt.BrushStyle.NoBrush)

        # 'chips' characters must have both red foreground and green background
        for i in range(len("potato"), len("potatochips")):
            c = edit.textCursor()
            c.setPosition(i)
            c.setPosition(i + 1, c.MoveMode.KeepAnchor)
            cf = c.charFormat()
            self.assertEqual(cf.foreground().color().name().lower(), "#dc2626")
            self.assertEqual(cf.background().color().name().lower(), "#22c55e")

        # 3. Clear highlight and clear text color, then type 'plain'
        edit.clear_highlight_color()
        edit.clear_text_color()
        for ch in 'plain':
            ev = QKeyEvent(QEvent.Type.KeyPress, 0, Qt.KeyboardModifier.NoModifier, ch)
            edit.keyPressEvent(ev)

        self.assertEqual(edit.toPlainText(), "potatochipsplain")
        for i in range(len("potatochips"), len("potatochipsplain")):
            c = edit.textCursor()
            c.setPosition(i)
            c.setPosition(i + 1, c.MoveMode.KeepAnchor)
            cf = c.charFormat()
            self.assertFalse(cf.hasProperty(QTextFormat.Property.BackgroundBrush) and cf.background().style() != Qt.BrushStyle.NoBrush)


    def test_multi_statement_selection_and_operations(self):
        """Test selecting multiple math statements, text, and nonexec math, and deleting/copying/pasting."""
        win = MainWindow()
        ws = win.new_worksheet()
        
        # 1. Setup 3 cells with different modes: math, text, nonexec_math
        cell0 = ws.active_cell
        cell0.set_input_text("potato :")
        cell0.set_input_mode(cell0.MODE_2D_MATH)

        cell1 = ws.add_cell()
        cell1.set_input_mode(cell1.MODE_TEXT)
        cell1.set_input_text("Here is a description text")

        cell2 = ws.add_cell()
        cell2.set_input_mode(cell2.MODE_NONEXEC_MATH)
        cell2.set_input_text("x^2 + y^2 = 1")

        self.assertEqual(len(ws.cells), 3)

        # 2. Select all statements
        ws.select_all_cells()
        self.assertEqual(len(ws.selected_cells), 3)
        for c in ws.cells:
            self.assertTrue(c.is_selected)
            self.assertTrue(c.input_edit.textCursor().hasSelection())

        # 3. Copy selected statements
        ws.copy_selected_cells()
        cb = QApplication.clipboard()
        cell2_text = cell2.get_input_text()
        self.assertIn("potato :", cb.text())
        self.assertIn("Here is a description text", cb.text())
        self.assertIn(cell2_text, cb.text())
        self.assertTrue(cb.mimeData().hasFormat("application/x-openmath-cells"))

        # 4. Delete selected statements
        ws.delete_selected_cells()
        self.assertEqual(len(ws.cells), 1)  # Clear leaves 1 empty cell

        # 5. Paste statements back
        success = ws.paste_cells()
        self.assertTrue(success)
        self.assertEqual(len(ws.cells), 3)
        self.assertEqual(ws.cells[0].input_mode, ws.cells[0].MODE_2D_MATH)
        self.assertEqual(ws.cells[0].get_input_text(), "potato :")
        self.assertEqual(ws.cells[1].input_mode, ws.cells[1].MODE_TEXT)
        self.assertEqual(ws.cells[1].get_input_text(), "Here is a description text")
        self.assertEqual(ws.cells[2].input_mode, ws.cells[2].MODE_NONEXEC_MATH)
        self.assertEqual(ws.cells[2].get_input_text(), cell2_text)

        # 6. Test Shift+Click range selection from cell0 to cell2
        ws.clear_cell_selection()
        ws.active_cell = ws.cells[0]
        ev_shift_click = QMouseEvent(
            QEvent.Type.MouseButtonPress,
            QPointF(10, 10),
            QPointF(10, 10),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.ShiftModifier
        )
        ws.cells[2].input_edit.mousePressEvent(ev_shift_click)
        self.assertEqual(len(ws.selected_cells), 3)

        # 7. Test Delete key in input_edit deletes multi-selected statements
        ev_del = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Delete, Qt.KeyboardModifier.NoModifier)
        ws.cells[2].input_edit.keyPressEvent(ev_del)
        self.assertEqual(len(ws.cells), 1)

    def test_multi_statement_mouse_drag_and_shortcuts(self):
        """Test cross-cell mouse drag selection, Shift+Arrows, and Ctrl+A select-all."""
        win = MainWindow()
        ws = win.new_worksheet()

        cell0 = ws.active_cell
        cell0.set_input_text("statement 1")
        cell1 = ws.add_cell(expression="statement 2")
        cell2 = ws.add_cell(expression="statement 3")
        self.assertEqual(len(ws.cells), 3)

        # Update geometries
        ws.container.adjustSize()
        for c in ws.cells:
            c.adjustSize()

        # 1. Test select_range
        ws.select_range(cell0, cell1)
        self.assertEqual(len(ws.selected_cells), 2)
        self.assertTrue(cell0.is_selected)
        self.assertTrue(cell1.is_selected)
        self.assertFalse(cell2.is_selected)

        # 2. Test Cut and Paste via MainWindow actions
        win._edit_cut()
        self.assertEqual(len(ws.cells), 1)
        self.assertEqual(ws.cells[0], cell2)

        win._edit_paste()
        self.assertEqual(len(ws.cells), 3)

        # 3. Test Select All action from MainWindow Edit menu
        win._edit_select_all()
        self.assertEqual(len(ws.selected_cells), 3)

    def test_delete_and_undo_redo_statements(self):
        """Test deleting mixed selection (sections, subsections, images, math) and full Undo/Redo."""
        win = MainWindow()
        ws = win.new_worksheet()
        ws.cells[0].deleteLater()
        ws.cells.clear()
        ws.undo_stack.clear()

        # Cell 0: Root Section
        sec0 = ws.insert_section_cell(title="Main Section", level=0)
        # Cell 1: Subsection
        sec1 = ws.insert_section_cell(title="Subsection 1", level=1, insert_after_id=sec0.cell_id)
        # Cell 2: Math cell u
        c_u = ws.add_cell(expression="u := Vector([1, 2])", insert_after_id=sec1.cell_id)
        # Cell 3: Image cell
        c_img = ws.add_cell(expression="", insert_after_id=c_u.cell_id)
        c_img.set_input_mode(c_img.MODE_TEXT)
        c_img.input_edit.setHtml('<img src="img_sample.png" width="100" height="50"/>')
        # Cell 4: Math cell v
        c_v = ws.add_cell(expression="v := Vector([3, 4])", insert_after_id=c_img.cell_id)
        # Cell 5: Math cell result
        c_res = ws.add_cell(expression="u + v", insert_after_id=c_v.cell_id)

        self.assertEqual(len(ws.cells), 6)
        self.assertEqual(ws.cells[1].section_title, "Subsection 1")

        # 1. Multi-select Subsection 1, u, Image, and v (cells 1, 2, 3, 4)
        ws.clear_cell_selection()
        for i in [1, 2, 3, 4]:
            ws.cells[i].set_cell_selected(True)
            ws.selected_cells.append(ws.cells[i])
        self.assertEqual(len(ws.selected_cells), 4)

        # 2. Delete selected items (via MainWindow Delete action or delete_selected_cells)
        win._edit_delete()
        self.assertEqual(len(ws.cells), 2)
        self.assertEqual(ws.cells[0].section_title, "Main Section")
        self.assertEqual(ws.cells[1].get_input_text(), "u + v")

        # 3. Test Undo via win._edit_undo() (toolbar Undo button or Ctrl+Z)
        win._edit_undo()
        self.assertEqual(len(ws.cells), 6)
        self.assertEqual(ws.cells[0].section_title, "Main Section")
        self.assertEqual(ws.cells[1].section_title, "Subsection 1")
        self.assertEqual(ws.cells[1].section_level, 1)
        self.assertEqual(ws.cells[2].get_input_text(), "u := Vector([1, 2])")
        self.assertIn("img_sample.png", ws.cells[3].input_edit.toHtml())
        self.assertEqual(ws.cells[4].get_input_text(), "v := Vector([3, 4])")
        self.assertEqual(ws.cells[5].get_input_text(), "u + v")

        # All 4 restored cells should be selected
        self.assertEqual(len(ws.selected_cells), 4)

        # 4. Test Redo via win._edit_redo() (toolbar Redo button or Ctrl+Y / Ctrl+Shift+Z)
        win._edit_redo()
        self.assertEqual(len(ws.cells), 2)
        self.assertEqual(ws.cells[0].section_title, "Main Section")
        self.assertEqual(ws.cells[1].get_input_text(), "u + v")

        # 5. Test Undo again via keyboard event Ctrl+Z
        ev_undo = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
        ws.eventFilter(ws, ev_undo)
        self.assertEqual(len(ws.cells), 6)
        self.assertEqual(ws.cells[1].section_title, "Subsection 1")

        # 6. Test Redo via keyboard event Ctrl+Y
        ev_redo = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Y, Qt.KeyboardModifier.ControlModifier)
        ws.eventFilter(ws, ev_redo)
        self.assertEqual(len(ws.cells), 2)

        # 7. Test Redo via keyboard event Ctrl+Shift+Z
        ev_undo2 = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
        ws.eventFilter(ws, ev_undo2)
        self.assertEqual(len(ws.cells), 6)
        ev_redo_shift = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier)
        ws.eventFilter(ws, ev_redo_shift)
        self.assertEqual(len(ws.cells), 2)

    def test_section_and_cell_font_and_highlight_coloring_and_unselect(self):
        """Verify font and highlight color application, partial selection, and auto-deselection."""
        from PyQt6.QtGui import QTextCursor, QColor
        win = self.window
        ws = win.new_worksheet()
        # Create a section cell
        sec_cell = ws.cells[0]
        sec_cell.is_section_header = True
        sec_cell.section_title = "Problem 1: Complex Analysis"
        sec_cell._apply_section_header_styling()
        ws.active_cell = sec_cell

        # 1. Partial selection inside section title
        title_edit = sec_cell.title_edit
        self.assertEqual(title_edit.toPlainText(), "Problem 1: Complex Analysis")

        # Select "Problem 1" (chars 0 to 9)
        cur = title_edit.textCursor()
        cur.setPosition(0)
        cur.setPosition(9, QTextCursor.MoveMode.KeepAnchor)
        title_edit.setTextCursor(cur)
        self.assertTrue(title_edit.hasSelectedText())
        self.assertEqual(title_edit.selectedText(), "Problem 1")

        # Apply highlight color (yellow)
        hl_color = QColor("#ffff00")
        ws.set_active_cell_highlight_color(hl_color)

        # Selection should be automatically cleared!
        self.assertFalse(title_edit.hasSelectedText())

        # Verify "Problem 1" is highlighted with yellow, but "Complex" is not
        cur = title_edit.textCursor()
        cur.setPosition(2)
        fmt = cur.charFormat()
        self.assertEqual(fmt.background().color().name().lower(), "#ffff00")

        cur.setPosition(15)  # "Complex"
        fmt2 = cur.charFormat()
        self.assertEqual(fmt2.background().style(), Qt.BrushStyle.NoBrush)

        # 2. Select "Complex" (chars 11 to 18) and apply text color (red)
        cur = title_edit.textCursor()
        cur.setPosition(11)
        cur.setPosition(18, QTextCursor.MoveMode.KeepAnchor)
        title_edit.setTextCursor(cur)
        self.assertTrue(title_edit.hasSelectedText())
        self.assertEqual(title_edit.selectedText(), "Complex")

        txt_color = QColor("#dc2626")
        ws.set_active_cell_text_color(txt_color)

        # Selection should be cleared!
        self.assertFalse(title_edit.hasSelectedText())

        # Verify "Complex" has red foreground
        cur.setPosition(14)
        self.assertEqual(cur.charFormat().foreground().color().name().lower(), "#dc2626")

        # 3. Test normal math/text cell
        cell2 = ws.add_cell(expression="sin(x) + cos(x)")
        ws.active_cell = cell2
        input_edit = cell2.input_edit

        # Select "sin(x)" (chars 0 to 6)
        cur = input_edit.textCursor()
        cur.setPosition(0)
        cur.setPosition(6, QTextCursor.MoveMode.KeepAnchor)
        input_edit.setTextCursor(cur)
        self.assertTrue(input_edit.textCursor().hasSelection())

        # Apply green highlight
        ws.set_active_cell_highlight_color(QColor("#00ff00"))

        # Selection should be cleared!
        self.assertFalse(input_edit.textCursor().hasSelection())

        cur.setPosition(2)
        self.assertEqual(cur.charFormat().background().color().name().lower(), "#00ff00")
        cur.setPosition(10)
        self.assertEqual(cur.charFormat().background().style(), Qt.BrushStyle.NoBrush)

        # 4. Serialization roundtrip preserves rich HTML
        d = sec_cell.to_dict()
        self.assertIn("section_html", d)
        self.assertIn("#ffff00", d["section_html"])

        sec_cell2 = ws.add_cell()
        sec_cell2.from_dict(d)
        self.assertEqual(sec_cell2.section_title, "Problem 1: Complex Analysis")
        cur_restored = sec_cell2.title_edit.textCursor()
        cur_restored.setPosition(2)
        self.assertEqual(cur_restored.charFormat().background().color().name().lower(), "#ffff00")

    def test_export_to_pdf_with_section_scope_lines(self):
        """Verify export_to_pdf renders sections, subsections, and scope lines."""
        import tempfile
        win = self.window
        ws = win.new_worksheet()

        c0 = ws.cells[0]
        c0.is_section_header = True
        c0.section_title = "Problem 1"
        c0.section_level = 0
        c0._apply_section_header_styling()

        c1 = ws.add_cell("x := 10")

        c2 = ws.add_cell()
        c2.is_section_header = True
        c2.section_title = "1"
        c2.section_level = 1
        c2._apply_section_header_styling()

        c3 = ws.add_cell("y := 20")

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tf:
            pdf_path = tf.name

        try:
            ws.export_to_pdf(pdf_path)
            self.assertTrue(os.path.exists(pdf_path))
            self.assertGreater(os.path.getsize(pdf_path), 1000)
        finally:
            if os.path.exists(pdf_path):
                try:
                    os.remove(pdf_path)
                except Exception:
                    pass

    def test_dynamic_add_tab_button(self):
        """Verify that the '+' button dynamically tracks tab bar positions and updates visibility."""
        btn = getattr(self.window, 'btn_add_tab', None)
        self.assertIsNotNone(btn)
        self.window.resize(1400, 900)
        self.window.show()
        QApplication.processEvents()
        self.window._update_add_tab_button_pos()
        self.assertTrue(btn.isVisible())
        x1 = btn.x()

        # Add 1 more tab
        self.window.new_worksheet()
        QApplication.processEvents()
        self.window._update_add_tab_button_pos()
        self.assertTrue(btn.isVisible())
        x2 = btn.x()
        self.assertGreater(x2, x1, "'+' button should move to the right as more tabs are opened")

        # When too many tabs are opened, it should hide
        for _ in range(25):
            self.window.new_worksheet()
        QApplication.processEvents()
        self.window._update_add_tab_button_pos()
        self.assertFalse(btn.isVisible(), "'+' button should disappear when tabs overflow the tab widget")

    def test_document_mode_eval_and_eval_all_inline(self):
        """Test that Eval and Eval All in Document Mode evaluate inline as 'expr = result' without block output row."""
        ws = self.window.new_worksheet()
        cell0 = ws.cells[0]
        cell0.input_edit.setPlainText("to_bin(0x5A, 8)")

        cell1 = ws.add_cell("to_hex(0x5A, 8)")
        cell2 = ws.add_cell("15 * 3")

        # Click Eval (active group) on cell 0
        ws.active_cell = cell0
        self.window._execute_active_group()
        QApplication.processEvents()

        self.assertIn("0b0101 1010", cell0.get_input_text())
        self.assertFalse(cell0.output_row.isVisible())

        # Click Eval All
        self.window._execute_all_groups()
        QApplication.processEvents()

        self.assertIn("0b0101 1010", cell0.get_input_text())
        self.assertIn("0x5A", cell1.get_input_text())
        self.assertIn("45", cell2.get_input_text())
        self.assertFalse(cell0.output_row.isVisible())
        self.assertFalse(cell1.output_row.isVisible())
        self.assertFalse(cell2.output_row.isVisible())


if __name__ == '__main__':
    unittest.main()




