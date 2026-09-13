"""
Tests for 2-D Math subscript formatting and variable handling (e.g. V_1 -> V₁).
"""

import unittest
import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtTest import QTest

from cas_engine import CASEngine, MathParser
from ui.math_renderer import expr_to_preview_latex
from ui.worksheet_cell import WorksheetCell, SUB_MAP

app = QApplication.instance() or QApplication(sys.argv)


class TestSubscriptHandling(unittest.TestCase):
    def setUp(self):
        self.engine = CASEngine()
        self.cell = WorksheetCell(engine=self.engine)

    def test_parser_subscript_conversion(self):
        """Test that unicode subscripts on variables get converted to internal syntax V_1."""
        prep = MathParser.preprocess_string("V₁ := 5")
        self.assertEqual(prep, "V_1 := 5")

        prep2 = MathParser.preprocess_string("V₁ + V₂ * 3")
        self.assertEqual(prep2, "V_1 + V_2 * 3")

    def test_assignment_and_evaluation(self):
        """Test assignment and retrieval of subscripted variables in CASEngine."""
        is_assign, var_name, args, expr = MathParser.check_assignment("V₁ := 5")
        self.assertTrue(is_assign)
        self.assertEqual(var_name, "V_1")
        self.assertEqual(expr, "5")

        res = self.engine.evaluate("V₁ := 5")
        self.assertEqual(res.exact_text, "5")

        # Both V₁ and V_1 should be accessible in subsequent calculations
        res_sub = self.engine.evaluate("V₁ + 10")
        self.assertEqual(res_sub.exact_text, "15")

        res_underscore = self.engine.evaluate("V_1 + 10")
        self.assertEqual(res_underscore.exact_text, "15")

    def test_latex_preview(self):
        """Test LaTeX preview formatting for subscript variables."""
        latex1 = expr_to_preview_latex("V₁ := 5")
        self.assertIn("V_{1}", latex1)

        latex2 = expr_to_preview_latex("V_1 := 5")
        self.assertIn("V_{1}", latex2)

    def test_interactive_typing_formatting(self):
        """Test that typing V_1 dynamically formats to V₁ with correct typography."""
        edit = self.cell.input_edit
        edit.setFocus()
        edit.setPlainText("")

        # Type 'V_1'
        QTest.keyClicks(edit, "V_1")
        self.assertEqual(edit.toPlainText(), "V₁")

        # Check font properties: V should be Times New Roman Italic
        cur = edit.textCursor()
        cur.setPosition(0)
        cur.setPosition(1, cur.MoveMode.KeepAnchor)
        fmt = cur.charFormat()
        self.assertEqual(fmt.fontFamily(), "Times New Roman")
        self.assertTrue(fmt.fontItalic())

        # Subscript 1 is rendered upright via Math2DHighlighter
        highlighter = getattr(edit, 'math_highlighter', None)
        self.assertIsNotNone(highlighter)

    def test_assignment_typing_formatting(self):
        """Test typing V_1:=5 produces 'V₁ := 5'."""
        edit = self.cell.input_edit
        edit.setFocus()
        edit.setPlainText("")

        QTest.keyClicks(edit, "V_1:=5")
        self.assertEqual(edit.toPlainText(), "V₁ := 5")

    def test_clean_operator_spacing_with_subscripts_and_parens(self):
        """Test clean_operator_spacing converts underscores to subscripts without corrupting parentheses."""
        res = self.cell.input_edit.clean_operator_spacing("(R_1 + R_2)*(V_1 + V_2)")
        self.assertEqual(res, "(R₁ + R₂) · (V₁ + V₂)")
        self.assertNotIn("₎", res)
        self.assertNotIn("_", res)

    def test_fraction_subscript_formatting(self):
        """Test that FractionWidget initializes with formatted subscripts."""
        from ui.worksheet_cell import FractionWidget
        fw = FractionWidget(num="V_1 + V_2", den="R_1 + R_2")
        self.assertEqual(fw.num_text(), "V₁ + V₂")
        self.assertEqual(fw.den_text(), "R₁ + R₂")

    def test_inline_evaluation_fraction_subscripts(self):
        """Test inline evaluation of ( (V_1 + V_2) / (R_2 + R_1) ) = formats subscripts properly."""
        edit = self.cell.input_edit
        edit.setFocus()
        edit.setPlainText("(")
        cur = edit.textCursor()
        cur.movePosition(cur.MoveOperation.End)
        edit.setTextCursor(cur)
        edit.insert_fraction_widget(num="V_1 + V_2", den="R_2 + R_1")
        cur = edit.textCursor()
        cur.movePosition(cur.MoveOperation.End)
        edit.setTextCursor(cur)
        edit.insertPlainText(")")

        # Inline evaluation
        success = edit._handle_inline_evaluation()
        self.assertTrue(success)

        # There should be two fraction widgets now: the LHS and evaluated RHS
        self.assertEqual(len(edit.frac_widgets), 2)
        fw_lhs = edit.frac_widgets[1]
        fw_rhs = edit.frac_widgets[2]

        self.assertEqual(fw_lhs.num_text(), "V₁ + V₂")
        self.assertEqual(fw_lhs.den_text(), "R₂ + R₁")
        self.assertEqual(fw_rhs.num_text(), "V₁ + V₂")
        self.assertEqual(fw_rhs.den_text(), "R₁ + R₂")
        self.assertNotIn("_", fw_rhs.num_text())
        self.assertNotIn("_", fw_rhs.den_text())

    def test_right_arrow_exits_subscript_and_types_parenthesis(self):
        """Test typing (R_1 + R_2, pressing Right Arrow, then ')' produces (R₁ + R₂) with normal parenthesis."""
        from PyQt6.QtCore import Qt
        edit = self.cell.input_edit
        edit.setFocus()
        edit.setPlainText("")
        QTest.keyClicks(edit, "(R_1 + R_2")
        QTest.keyClick(edit, Qt.Key.Key_Right)
        QTest.keyClicks(edit, ")")
        self.assertEqual(edit.toPlainText(), "(R₁ + R₂)")
        self.assertNotIn("₎", edit.toPlainText())

    def test_direct_parenthesis_after_subscript_never_subscripted(self):
        """Test typing (R_1 + R_2) directly produces (R₁ + R₂) with normal upright closing parenthesis."""
        edit = self.cell.input_edit
        edit.setFocus()
        edit.setPlainText("")
        QTest.keyClicks(edit, "(R_1 + R_2)")
        self.assertEqual(edit.toPlainText(), "(R₁ + R₂)")
        self.assertNotIn("₎", edit.toPlainText())

    def test_right_arrow_exits_subscript_and_types_baseline_digit(self):
        """Test typing R_1, pressing Right Arrow, then typing '2' produces R₁2 on baseline."""
        from PyQt6.QtCore import Qt
        edit = self.cell.input_edit
        edit.setFocus()
        edit.setPlainText("")
        QTest.keyClicks(edit, "R_1")
        QTest.keyClick(edit, Qt.Key.Key_Right)
        QTest.keyClicks(edit, "2")
        self.assertEqual(edit.toPlainText(), "R₁2")

    def test_multidigit_subscript_without_right_arrow(self):
        """Test typing R_12 without Right Arrow continues subscript and produces R₁₂."""
        edit = self.cell.input_edit
        edit.setFocus()
        edit.setPlainText("")
        QTest.keyClicks(edit, "R_12")
        self.assertEqual(edit.toPlainText(), "R₁₂")

    def test_stepped_subscripts_template_insertion(self):
        """Test that inserting two_comp_repr(-5, 8) renders stepped subscripts without visible underscores."""
        from ui.worksheet_cell import PROP_SUBSCRIPT_LEVEL
        self.cell.insert_template("two_comp_repr(-5, 8)")
        raw_text = super(type(self.cell.input_edit), self.cell.input_edit).toPlainText()
        self.assertNotIn("_", raw_text)
        self.assertEqual(raw_text, "twocomprepr(-5, 8)")

        # Verify fragment levels: two (0), comp (1), repr (2), (-5, 8) (0)
        doc = self.cell.input_edit.document()
        block = doc.begin()
        it = block.begin()
        levels = []
        while not it.atEnd():
            frag = it.fragment()
            if frag.isValid():
                lvl = frag.charFormat().property(PROP_SUBSCRIPT_LEVEL) or 0
                levels.append((frag.text(), lvl))
            it += 1
        self.assertEqual(levels, [("two", 0), ("comp", 1), ("repr", 2), ("(-5, 8)", 0)])

        # Verify plain text extraction reconstructs original identifier
        extracted = self.cell.get_input_text()
        self.assertEqual(extracted, "two_comp_repr(-5, 8)")

        # Verify CAS engine evaluation
        res = self.engine.evaluate(extracted)
        self.assertTrue("decimal_signed" in res.exact_text or "Decimal Signed" in res.exact_text or "decimal_signed" in res.raw_result)

    def test_stepped_subscripts_interactive_typing(self):
        """Test typing two_comp_repr(-5, 8) interactively produces stepped subscripts without visible underscores."""
        edit = self.cell.input_edit
        edit.setFocus()
        edit.setPlainText("")
        QTest.keyClicks(edit, "two_comp_repr(-5, 8)")

        raw_text = super(type(edit), edit).toPlainText()
        self.assertNotIn("_", raw_text)
        self.assertEqual(edit.get_plain_or_math_text(), "two_comp_repr(-5, 8)")

    def test_format_subscripts_stepped_placeholder_safety(self):
        """Test that format_subscripts_and_superscripts protects multi-underscore stepped tokens without leaking placeholders."""
        from ui.worksheet_cell import format_subscripts_and_superscripts
        inp = "two_comp_repr(-5, 8) = {'decimal_signed': -5} :"
        out = format_subscripts_and_superscripts(inp)
        self.assertNotIn("\x01", out)
        self.assertNotIn("\x02", out)
        self.assertNotIn("STEPPED", out)
        self.assertTrue(out.startswith("two_comp_repr(-5, 8)"))

    def test_colon_terminated_execution_does_not_corrupt_text(self):
        """Test that typing ':' at the end of an inline evaluated cell and pressing Enter executes cleanly without U+0001 error."""
        edit = self.cell.input_edit
        edit.setFocus()
        self.cell.insert_template("two_comp_repr(-5, 8)")
        cur = edit.textCursor()
        cur.movePosition(cur.MoveOperation.End)
        cur.insertText("=")
        edit.setTextCursor(cur)
        self.assertTrue(edit._handle_inline_evaluation())

        # Append ' :' and execute
        cur = edit.textCursor()
        cur.movePosition(cur.MoveOperation.End)
        cur.insertText(" :")
        edit.setTextCursor(cur)

        self.cell.execute()
        txt = edit.toPlainText()
        self.assertNotIn("\x01", txt)
        self.assertNotIn("STEPPED", txt)
        self.assertTrue(txt.startswith("two_comp_repr(-5, 8)"))
        self.assertFalse(self.cell.lbl_error.isVisible())

    def test_stepped_subscripts_inline_evaluation(self):
        """Test inline evaluation of two_comp(-5, 8) = evaluates to 251 rather than unevaluated twocomp."""
        edit = self.cell.input_edit
        edit.setFocus()
        self.cell.insert_template("two_comp(-5, 8)")
        cur = edit.textCursor()
        cur.movePosition(cur.MoveOperation.End)
        cur.insertText("=")
        edit.setTextCursor(cur)
        success = edit._handle_inline_evaluation()
        self.assertTrue(success)
        txt = edit.toPlainText()
        self.assertIn("= 251", txt)
    def test_bit_toggle_stepped_formatting_and_colon_execution(self):
        """Test bit_toggle inserts with stepped subscripts and colon execution does not mangle into bitₜₒggle."""
        from ui.worksheet_cell import PROP_SUBSCRIPT_LEVEL
        edit = self.cell.input_edit
        edit.setFocus()
        self.cell.insert_template("bit_toggle(0x00, 3)")

        # Verify raw text has no underscore and toggle is level 1
        raw_text = super(type(edit), edit).toPlainText()
        self.assertNotIn("_", raw_text)
        self.assertEqual(edit.toPlainText(), "bit_toggle(0x00, 3)")

        block = edit.document().firstBlock()
        it = block.begin()
        frags = []
        while not it.atEnd():
            frag = it.fragment()
            frags.append((frag.text(), frag.charFormat().property(PROP_SUBSCRIPT_LEVEL)))
            it += 1
        self.assertEqual(frags[0][0], "bit")
        self.assertEqual(frags[1][0], "toggle")
        self.assertEqual(frags[1][1], 1)

        # Inline evaluation
        cur = edit.textCursor()
        cur.movePosition(cur.MoveOperation.End)
        cur.insertText("=")
        edit.setTextCursor(cur)
        self.assertTrue(edit._handle_inline_evaluation())
        self.assertEqual(edit.toPlainText(), "bit_toggle(0x00, 3) = 8")

        # Type ':' at end and execute
        cur = edit.textCursor()
        cur.movePosition(cur.MoveOperation.End)
        cur.insertText(" :")
        edit.setTextCursor(cur)
        self.cell.execute()

        # Ensure no unicode mangling (bitₜₒggle)
        txt = edit.toPlainText()
        self.assertEqual(txt, "bit_toggle(0x00, 3) = 8 :")
        self.assertNotIn("ₜ", txt)
        self.assertNotIn("ₒ", txt)

        # Ensure fragment formatting intact
        block = edit.document().firstBlock()
        it = block.begin()
        frags = []
        while not it.atEnd():
            frag = it.fragment()
            frags.append((frag.text(), frag.charFormat().property(PROP_SUBSCRIPT_LEVEL)))
            it += 1
        self.assertEqual(frags[0][0], "bit")
        self.assertEqual(frags[1][0], "toggle")
        self.assertEqual(frags[1][1], 1)

    def test_format_subscripts_single_underscore_token_safety(self):
        """Test format_subscripts_and_superscripts does not partially mangle tokens like bit_toggle."""
        from ui.worksheet_cell import format_subscripts_and_superscripts
        self.assertEqual(format_subscripts_and_superscripts("bit_toggle(0x00, 3) = 8 :"), "bit_toggle(0x00, 3) = 8 :")
        self.assertEqual(format_subscripts_and_superscripts("bit_set(0x00, 2) = 4 :"), "bit_set(0x00, 2) = 4 :")
        self.assertEqual(format_subscripts_and_superscripts("x_1 + x_2"), "x₁ + x₂")

    def test_insert_template_unit_spacing(self):
        """Test inserting unit templates (e.g. ' kOhm', ' V') smart spacing behavior."""
        edit = self.cell.input_edit
        edit.setPlainText("")
        self.cell.insert_template(" kOhm")
        self.assertEqual(edit.toPlainText(), "kOhm")

        edit.setPlainText("2,5")
        tc = edit.textCursor()
        tc.movePosition(tc.MoveOperation.End)
        edit.setTextCursor(tc)
        self.cell.insert_template(" kOhm")
        self.assertEqual(edit.toPlainText(), "2,5 kOhm")

        edit.setPlainText("2,5 ")
        tc = edit.textCursor()
        tc.movePosition(tc.MoveOperation.End)
        edit.setTextCursor(tc)
        self.cell.insert_template(" kOhm")
        self.assertEqual(edit.toPlainText(), "2,5 kOhm")

        edit.setPlainText("5")
        tc = edit.textCursor()
        tc.movePosition(tc.MoveOperation.End)
        edit.setTextCursor(tc)
        self.cell.insert_template(" V")
        self.assertEqual(edit.toPlainText(), "5 V")


if __name__ == "__main__":
    unittest.main()

