import sys
import unittest
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QTextCursor

from ui.worksheet_cell import WorksheetCell, RadicalWidget, FractionWidget, DefiniteIntegralWidget, CellInputEdit

app = QApplication.instance()
if app is None:
    app = QApplication(sys.argv)

class TestMultilineWrapping(unittest.TestCase):
    def setUp(self):
        self.cell = WorksheetCell(font_size=13)
        self.cell.resize(800, 600)
        self.edit = self.cell.input_edit
        self.edit.resize(750, 40)
        self.cell.show()

    def tearDown(self):
        self.cell.close()

    def test_radical_wrapping(self):
        # Insert radical with very long radicand
        long_rad = "0" * 120
        self.edit.insert_radical_widget(radicand=long_rad)
        app.processEvents()

        self.assertEqual(len(self.edit.frac_widgets), 1)
        rad = list(self.edit.frac_widgets.values())[0]
        self.assertIsInstance(rad, RadicalWidget)

        # Ensure radical width does not exceed viewport width
        vp_w = self.edit.viewport().width()
        self.assertLessEqual(rad.width(), vp_w)
        # Ensure rad_edit has wrapped onto multiple lines
        rad_lines = rad.rad_edit.document().begin().layout().lineCount()
        self.assertGreater(rad_lines, 1)
        # Ensure cell height has grown to accommodate the wrapped radical
        self.assertGreater(self.cell.height(), 40)

    def test_radical_dynamic_resize(self):
        long_rad = "0" * 100
        self.edit.insert_radical_widget(radicand=long_rad)
        app.processEvents()
        rad = list(self.edit.frac_widgets.values())[0]

        # Initial size at 800px width
        w1 = rad.width()
        h1 = rad.height()

        # Resize cell down to 400px
        self.cell.resize(400, 600)
        self.edit.resize(350, 40)
        app.processEvents()

        w2 = rad.width()
        h2 = rad.height()
        vp_w2 = self.edit.viewport().width()

        # Widget width must adapt and stay <= viewport width
        self.assertLessEqual(w2, vp_w2)
        # Height should increase as more lines wrap
        self.assertGreaterEqual(h2, h1)

        # Resize back to 900px
        self.cell.resize(900, 600)
        self.edit.resize(850, 40)
        app.processEvents()

        w3 = rad.width()
        h3 = rad.height()
        self.assertLessEqual(h3, h2)

    def test_fraction_wrapping(self):
        long_num = "1234567890" * 10
        self.edit.insert_fraction_widget(num=long_num, den="2")
        app.processEvents()
        frac = list(self.edit.frac_widgets.values())[0]
        self.assertIsInstance(frac, FractionWidget)
        vp_w = self.edit.viewport().width()
        self.assertLessEqual(frac.width(), vp_w)

    def test_integral_wrapping(self):
        long_f = "x" * 100
        self.edit.insert_definite_integral_widget(a="0", b="1", f=long_f)
        app.processEvents()
        integ = list(self.edit.frac_widgets.values())[0]
        self.assertIsInstance(integ, DefiniteIntegralWidget)
        vp_w = self.edit.viewport().width()
        self.assertLessEqual(integ.width(), vp_w)
        lines = integ.f_edit.document().begin().layout().lineCount()
        self.assertGreater(lines, 1)

    def test_plain_math_wrapping(self):
        # Long sequence of characters without spaces
        long_text = "x" * 200
        self.edit.insertPlainText(long_text)
        app.processEvents()
        doc = self.edit.document()
        lines = doc.begin().layout().lineCount()
        self.assertGreater(lines, 1)
        self.assertGreater(self.edit.height(), 30)

    def test_full_width_input_edit(self):
        # In a 1000px wide WorksheetView, cell and input_edit must fill the container width (> 900px)
        from ui.worksheet_view import WorksheetView
        from cas_engine import CASEngine
        wv = WorksheetView(engine=CASEngine())
        wv.resize(1000, 600)
        wv.show()
        app.processEvents()

        cell = wv.cells[0]
        self.assertGreater(cell.width(), 900)
        self.assertGreater(cell.input_edit.width(), 900)

        # Typing 35 characters must NOT wrap to a new line (as it did when stuck at 256px)
        text = 'gdsrgdgrdgrdgrdgrdgrg g df gr gdr gd'
        cell.input_edit.setPlainText(text)
        app.processEvents()
        lines = cell.input_edit.document().begin().layout().lineCount()
        self.assertEqual(lines, 1)

        # Only when text exceeds the ~960px right side does it wrap to line 2
        long_text = 'gdsrgdgrdgrdgrdgrdgrg g df gr gdr gd ' * 4
        cell.input_edit.setPlainText(long_text)
        app.processEvents()
        multilines = cell.input_edit.document().begin().layout().lineCount()
        self.assertGreater(multilines, 1)

        wv.close()

if __name__ == '__main__':
    unittest.main()

