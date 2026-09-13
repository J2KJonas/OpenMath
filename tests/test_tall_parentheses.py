import unittest
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeyEvent, QTextCursor
from ui.worksheet_cell import WorksheetCell, PROP_TALL_PAREN
from cas_engine import MathParser

app = QApplication.instance() or QApplication([])

class TestTallParenthesesAndZoomedFractions(unittest.TestCase):
    def setUp(self):
        self.cell = WorksheetCell()
        self.cell.resize(800, 400)
        self.cell.show()
        self.edit = self.cell.input_edit
        app.processEvents()

    def tearDown(self):
        self.cell.close()
        self.cell.deleteLater()
        app.processEvents()

    def test_zoomed_fraction_selection_slash(self):
        """Verifies that selecting text and pressing '/' at 200% zoom does not clip numerator."""
        self.cell.set_zoom_factor(2.0)
        app.processEvents()

        self.edit.insertPlainText('V\u2082 + V\u2081')
        app.processEvents()
        self.edit.selectAll()

        # Press '/'
        key_event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Slash, Qt.KeyboardModifier.NoModifier, '/')
        self.edit.keyPressEvent(key_event)
        app.processEvents()

        self.assertEqual(len(self.edit.frac_widgets), 1)
        frac = list(self.edit.frac_widgets.values())[0]
        self.assertGreater(frac.width(), 90)
        self.assertEqual(frac.num_text(), 'V\u2082 + V\u2081')

    def test_tall_parenthesis_detection(self):
        """Verifies that matching parentheses around a fraction are detected and marked as tall."""
        self.edit.insertPlainText('(')
        self.edit.insert_fraction_widget(num='V_2 + V_1', den='(R_1 + R_2)', focus_target=None)
        self.edit.move_cursor_after_fraction(1)
        self.edit.insertPlainText(')')
        app.processEvents()

        pairs = self.edit._find_tall_parenthesis_pairs()
        self.assertEqual(len(pairs), 1)
        self.assertEqual(pairs[0]['open_pos'], 0)
        self.assertEqual(pairs[0]['close_pos'], 2)

        cur_open = self.edit.textCursor()
        cur_open.setPosition(0)
        cur_open.setPosition(1, QTextCursor.MoveMode.KeepAnchor)
        self.assertTrue(cur_open.charFormat().property(PROP_TALL_PAREN))

        cur_close = self.edit.textCursor()
        cur_close.setPosition(2)
        cur_close.setPosition(3, QTextCursor.MoveMode.KeepAnchor)
        self.assertTrue(cur_close.charFormat().property(PROP_TALL_PAREN))

    def test_parenthesis_selection_wrapping(self):
        """Verifies that selecting a fraction and typing '(' wraps it in tall parentheses."""
        self.edit.insert_fraction_widget(num='a', den='b', focus_target=None)
        self.edit.selectAll()
        app.processEvents()

        key_event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_ParenLeft, Qt.KeyboardModifier.NoModifier, '(')
        self.edit.keyPressEvent(key_event)
        app.processEvents()

        pairs = self.edit._find_tall_parenthesis_pairs()
        self.assertEqual(len(pairs), 1)
        self.assertEqual(pairs[0]['open_pos'], 0)
        self.assertEqual(pairs[0]['close_pos'], 2)

    def test_executable_text_with_tall_parentheses(self):
        """Verifies that get_executable_text properly extracts mathematical parentheses and expressions."""
        self.edit.insertPlainText('(')
        self.edit.insert_fraction_widget(num='V_2 + V_1', den='R_1 + R_2', focus_target=None)
        self.edit.move_cursor_after_fraction(1)
        self.edit.insertPlainText(')')
        app.processEvents()

        exec_text = self.cell.get_executable_text()
        self.assertTrue(exec_text.startswith('('))
        self.assertTrue(exec_text.endswith(')'))
        self.assertIn('(V₂+V₁)/(R₁+R₂)', exec_text.replace(' ', ''))
        self.assertIn('(V_2+V_1)/(R_1+R_2)', MathParser.preprocess_string(exec_text).replace(' ', ''))

if __name__ == '__main__':
    unittest.main()
