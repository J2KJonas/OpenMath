"""
Unit tests for Worksheet (.mw) importer/exporter, Variable Manager, and dynamic Context Panel.
"""

import os
import unittest
import sympy as sp
from PyQt6.QtWidgets import QApplication

from cas_engine import CASEngine, WorksheetIO
from ui.variables_panel import VariableManagerWidget
from ui.context_panel import ContextPanel
from ui.palette_panel import PalettePanel


class TestWorksheetFeatures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.engine = CASEngine()

    def test_mw_save_and_load_roundtrip(self):
        cells = [
            {'input': '# Calculus Document', 'input_mode': 2},
            {'input': 'f := x^3 - 3*x + 1', 'input_mode': 0, 'result': {'exact_text': 'x^3 - 3*x + 1'}},
            {'input': 'diff(f, x)', 'input_mode': 0, 'result': {'exact_text': '3*x^2 - 3'}}
        ]
        mw_xml = WorksheetIO.save_mw_string(cells)
        self.assertTrue("<Worksheet>" in mw_xml)
        self.assertTrue("Calculus Document" in mw_xml)
        self.assertTrue("input-equation=" in mw_xml)

        loaded = WorksheetIO.load_mw_string(mw_xml)
        self.assertEqual(len(loaded), 3)
        self.assertEqual(loaded[0]['input'], '# Calculus Document')
        self.assertEqual(loaded[0]['input_mode'], WorksheetIO.MODE_TEXT)
        self.assertEqual(loaded[1]['input'], 'f := x^3 - 3*x + 1')
        self.assertEqual(loaded[1]['input_mode'], WorksheetIO.MODE_2D_MATH)
        self.assertEqual(loaded[2]['input'], 'diff(f, x)')

    def test_mw_load_real_example(self):
        example_path = r"C:\Program Files\OpenMath 2025\examples\addtable.mw"
        if os.path.isfile(example_path):
            loaded = WorksheetIO.load_mw_file(example_path)
            self.assertGreater(len(loaded), 10)
            # Verify mathematical inputs were extracted
            math_inputs = [c['input'] for c in loaded if c['input_mode'] in (0, 1) and c['input']]
            self.assertTrue(any('with(inttrans)' in inp for inp in math_inputs))

    def test_variable_manager_widget(self):
        self.engine.evaluate("k := 42")
        self.engine.evaluate("M := Matrix([[1, 2], [3, 4]])")
        self.engine.evaluate("eq := x^2 - 4 = 0")

        var_widget = VariableManagerWidget(self.engine)
        var_widget.refresh()

        self.assertEqual(var_widget.table.rowCount(), 3)
        names = [var_widget.table.item(r, 0).text() for r in range(3)]
        self.assertTrue('k' in names)
        self.assertTrue('M' in names)
        self.assertTrue('eq' in names)

        # Test filter
        var_widget.search_edit.setText("Matrix")
        hidden_rows = [var_widget.table.isRowHidden(r) for r in range(3)]
        self.assertTrue(any(hidden_rows))

        # Test unassign
        var_widget.table.selectRow(names.index('k'))
        var_widget.btn_unassign.click()
        self.assertEqual(var_widget.table.rowCount(), 2)
        self.assertTrue(isinstance(self.engine.namespace['k'], sp.Symbol))

    def test_context_panel_dynamic_types(self):
        panel = ContextPanel()

        # 1. Matrix target
        panel.set_target_expression("Matrix([[1, 2], [3, 4]])")
        self.assertTrue("Matrix" in panel.lbl_target_expr.text())

        # 2. Equation target
        panel.set_target_expression("x^2 - 5*x + 6 = 0")
        self.assertTrue("Equation" in panel.lbl_target_expr.text())

        # 3. Integer target
        panel.set_target_expression("123456")
        self.assertTrue("Integer" in panel.lbl_target_expr.text())

        # 4. Polynomial target
        panel.set_target_expression("x^3 + 2*x + 1")
        self.assertTrue("Polynomial" in panel.lbl_target_expr.text())

    def test_palette_panel_variables_tab(self):
        palette = PalettePanel(engine=self.engine)
        self.assertEqual(palette.tabs.count(), 3)
        self.assertEqual(palette.tabs.tabText(2), "Variables")
        self.assertIsNotNone(palette.var_manager)

    def test_typesetting_parser(self):
        from cas_engine.typesetting_parser import parse_typesetting, batch_decode_displays
        # Test AST parser on Typesetting string
        lprint_str = 'Typesetting:-mrow(Typesetting:-mfrac(Typesetting:-mn("200"), Typesetting:-mn("8")))'
        node = parse_typesetting(lprint_str)
        self.assertIsNotNone(node)
        self.assertEqual(node.to_math(), "(200)/(8)")
        self.assertEqual(node.to_latex(), r"\frac{200}{8}")

        # Test batch base64 display decoder
        stream = 'LUklbXJvd0c2Iy9JK21vZHVsZW5hbWVHNiJJLFR5cGVzZXR0aW5nR0koX3N5c2xpYkdGJzYlLUkmbWZyYWNHRiQ2KC1GIzYmLUkjbW5HRiQ2JVEkMjAwRicvJTBmb250X3N0eWxlX25hbWVHUSkyRH5JbnB1dEYnLyUsbWF0aHZhcmlhbnRHUSdub3JtYWxGJy1JI21vR0YkNi5RJyZzZG90O0YnRjRGNy8lJmZlbmNlR1EmZmFsc2VGJy8lKnNlcGFyYXRvckdGQC8lKXN0cmV0Y2h5R0ZALyUqc3ltbWV0cmljR0ZALyUobGFyZ2VvcEdGQC8lLm1vdmFibGVsaW1pdHNHRkAvJSdhY2NlbnRHRkAvJSdsc3BhY2VHUSYwLjBlbUYnLyUncnNwYWNlR0ZPLUYxNiVRIjhGJ0Y0RjdGNy1GIzYnLUYxNiRRJDAuMUYnRjctRjs2LUY9RjdGPkZBRkNGRUZHRklGS0ZNRlAtSSVtc3VwR0YkNiUtRjE2JFEjMTBGJ0Y3LUYjNiUtRjE2JFEiNkYnRjcvJSdpdGFsaWNHUSV0cnVlRicvRjhRJ2l0YWxpY0YnLyUxc3VwZXJzY3JpcHRzaGlmdEdRIjBGJ0Zhb0Zkby8lLmxpbmV0aGlja25lc3NHUSIxRicvJStkZW5vbWFsaWduR1EnY2VudGVyRicvJSludW1hbGlnbkdGXnAvJSliZXZlbGxlZEdGQC8lK2V4ZWN1dGFibGVHRkBGNw=='
        results = batch_decode_displays([stream])
        self.assertEqual(len(results), 1)
        math_s, latex_s = results[0]
        self.assertTrue('200' in math_s and '8' in math_s)

    def test_section_collapsing_and_hierarchy(self):
        from ui.worksheet_view import WorksheetView
        ws = WorksheetView(engine=self.engine)

        # Create Section Header (Problem 1)
        sec1 = ws.add_cell(expression="Problem 1", focus=False)
        sec1.from_dict({
            'cell_id': 'sec_1',
            'is_section_header': True,
            'section_title': 'Problem 1',
            'section_level': 0,
            'is_collapsed': False,
        })

        child1 = ws.add_cell(expression="x := 10", focus=False)
        child2 = ws.add_cell(expression="y := 20", focus=False)

        # Create Section Header (Problem 2)
        sec2 = ws.add_cell(expression="Problem 2", focus=False)
        sec2.from_dict({
            'cell_id': 'sec_2',
            'is_section_header': True,
            'section_title': 'Problem 2',
            'section_level': 0,
            'is_collapsed': False,
        })
        child3 = ws.add_cell(expression="z := 30", focus=False)

        # Verify initial visible state
        self.assertFalse(child1.isHidden())
        self.assertFalse(child2.isHidden())
        self.assertFalse(child3.isHidden())

        # Collapse Section 1
        sec1.toggle_section_collapsed()
        self.assertTrue(sec1.is_collapsed)
        self.assertTrue(child1.isHidden())
        self.assertTrue(child2.isHidden())
        # Section 2 and its child should remain visible
        self.assertFalse(sec2.isHidden())
        self.assertFalse(child3.isHidden())

        # Expand Section 1
        sec1.toggle_section_collapsed()
        self.assertFalse(sec1.is_collapsed)
        self.assertFalse(child1.isHidden())
        self.assertFalse(child2.isHidden())

    def test_embedded_image_cell_roundtrip(self):
        from PyQt6.QtGui import QImage, QColor, QTextDocument
        from PyQt6.QtCore import QMimeData, QUrl
        from ui.worksheet_cell import WorksheetCell

        cell = WorksheetCell()
        img = QImage(120, 80, QImage.Format.Format_RGB32)
        img.fill(QColor(0, 128, 255))

        mime = QMimeData()
        mime.setImageData(img)
        cell.input_edit.insertFromMimeData(mime)

        self.assertTrue(hasattr(cell.input_edit, 'embedded_images'))
        self.assertEqual(len(cell.input_edit.embedded_images), 1)

        # Roundtrip via to_dict / from_dict
        data = cell.to_dict()
        self.assertIn('embedded_images', data)
        self.assertIn('<img', data['input'])

        restored_cell = WorksheetCell()
        restored_cell.from_dict(data)

        img_id = list(data['embedded_images'].keys())[0]
        res = restored_cell.input_edit.document().resource(QTextDocument.ResourceType.ImageResource, QUrl(img_id))
        self.assertIsNotNone(res)
        self.assertFalse(res.isNull())
        self.assertEqual(res.size().width(), 120)
        self.assertEqual(res.size().height(), 80)

    def test_embedded_image_height_adjustment(self):
        from PyQt6.QtGui import QImage, QColor
        from PyQt6.QtCore import QMimeData
        from ui.worksheet_cell import WorksheetCell

        cell = WorksheetCell()
        img = QImage(300, 220, QImage.Format.Format_RGB32)
        img.fill(QColor(255, 0, 0))

        mime = QMimeData()
        mime.setImageData(img)
        cell.input_edit.insertFromMimeData(mime)
        cell.input_edit._adjust_height()

        self.assertGreaterEqual(cell.input_edit.height(), 220)

    def test_copy_paste_image_in_document(self):
        from PyQt6.QtGui import QImage, QColor, QTextCursor, QKeyEvent
        from PyQt6.QtCore import Qt
        from ui.worksheet_cell import WorksheetCell, CellInputEdit

        cell = WorksheetCell()
        img = QImage(100, 100, QImage.Format.Format_RGB32)
        img.fill(QColor(255, 0, 128))

        # Insert image
        cell.input_edit.insert_image_object(img)
        self.assertEqual(len(cell.input_edit.embedded_images), 1)

        # Select the image
        cursor = cell.input_edit.textCursor()
        cursor.setPosition(0)
        cursor.setPosition(1, QTextCursor.MoveMode.KeepAnchor)
        cell.input_edit.setTextCursor(cursor)

        # Copy from selection
        mime = cell.input_edit.createMimeDataFromSelection()
        self.assertTrue(mime.hasImage())
        self.assertTrue(mime.hasHtml())

        # Move cursor after image / under image
        cursor = cell.input_edit.textCursor()
        cursor.setPosition(1)
        cell.input_edit.setTextCursor(cursor)
        cell.input_edit.insertPlainText("\n")

        # Paste via insertFromMimeData (what Ctrl+V triggers)
        cell.input_edit.insertFromMimeData(mime)

        self.assertEqual(len(cell.input_edit.embedded_images), 2)
        self.assertGreaterEqual(cell.input_edit.toHtml().count('<img'), 2)


    def test_mw_import_with_pill_and_text_fields(self):
        sample_mw = """<?xml version="1.0" encoding="UTF-8"?>
<Worksheet><Section collapsed="false"><Title>
<Text-field style="Heading 1" layout="Heading 1" background="[0,255,0]">Solution Section</Text-field>
</Title>
<Group><Input>
<Text-field style="Text" layout="Normal" background="[0,255,0]">Verified correct result<Equation executable="true" style="2D Math" input-equation="" display="JSFH">JSFH</Equation></Text-field>
</Input></Group>
</Section></Worksheet>"""
        loaded = WorksheetIO.load_mw_string(sample_mw)
        self.assertEqual(len(loaded), 2)
        # Check section header with pill
        sec = loaded[0]
        self.assertTrue(sec.get('is_section_header'))
        self.assertIn('rgb(0,255,0)', sec.get('section_html', ''))
        # Check text field preserved despite dummy Equation tag
        tf_cell = loaded[1]
        self.assertIn('Verified correct result', tf_cell.get('input', ''))
        self.assertIn('rgb(0,255,0)', tf_cell.get('input', ''))

    def test_open_xml_mw_document(self):
        """Verify MainWindow can open a native XML .mw document without JSONDecodeError."""
        import tempfile
        from ui.main_window import MainWindow

        sample_mw = """<?xml version="1.0" encoding="UTF-8"?>
<Worksheet><Version major="2021" minor="0" />
<Input><Text-field prompt="> " style="Maple Input">diff(sin(x), x)</Text-field></Input>
</Worksheet>"""
        with tempfile.NamedTemporaryFile(suffix='.mw', mode='w', delete=False, encoding='utf-8') as f:
            f.write(sample_mw)
            tmp_path = f.name

        win = MainWindow()
        try:
            win.load_worksheet_from_file(tmp_path)
            self.assertIsNotNone(win.worksheet)
            self.assertGreater(len(win.worksheet.cells), 0)
            self.assertEqual(win.worksheet.cells[0].get_input_text(), "diff(sin(x), x)")
        finally:
            win.close()
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_open_empty_mw_document(self):
        """Verify opening an empty .mw file does not crash with Expecting value line 1 column 1."""
        import tempfile
        from ui.main_window import MainWindow

        with tempfile.NamedTemporaryFile(suffix='.mw', mode='w', delete=False, encoding='utf-8') as f:
            f.write("")
            tmp_path = f.name

        win = MainWindow()
        try:
            win.load_worksheet_from_file(tmp_path)
            self.assertIsNotNone(win.worksheet)
            self.assertGreater(len(win.worksheet.cells), 0)
            self.assertEqual(win.worksheet.cells[0].lbl_prompt.text(), ">")
        finally:
            win.close()
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_mw_save_and_open_roundtrip_main_window(self):
        """Verify MainWindow saves .mw as XML and reopens it cleanly."""
        import tempfile
        from ui.main_window import MainWindow

        with tempfile.NamedTemporaryFile(suffix='.mw', mode='w', delete=False, encoding='utf-8') as f:
            tmp_path = f.name

        win = MainWindow()
        try:
            ws = win.new_worksheet()
            ws.cells[0].set_input_text("x^2 + 2*x + 1")
            expected_text = ws.cells[0].get_input_text()
            win.current_file_path = tmp_path
            ws.file_path = tmp_path
            win.save_worksheet()

            # Verify file was written as XML
            with open(tmp_path, "r", encoding="utf-8") as f:
                saved_content = f.read()
            self.assertTrue(saved_content.startswith("<?xml") or "<Worksheet" in saved_content)

            # Now open it in a fresh window
            win2 = MainWindow()
            try:
                win2.load_worksheet_from_file(tmp_path)
                self.assertIsNotNone(win2.worksheet)
                from cas_engine.parser import MathParser
                self.assertEqual(
                    MathParser.parse(win2.worksheet.cells[0].get_input_text()).sympy_expr,
                    MathParser.parse(expected_text).sympy_expr
                )
            finally:
                win2.close()
        finally:
            win.close()
            if os.path.exists(tmp_path):
                os.remove(tmp_path)


    def test_mw_nested_subsections_hierarchy_and_styling(self):
        """Test that importing nested sections/subsections from .mw XML builds correct hierarchy and styling."""
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<Worksheet>
<Version major="2021" minor="0"/>
<View-Properties presentation="false"/>
<Section collapsed="false" isCollapsible="true">
  <Title><Text-field><Font background="[0,255,0]">Problem 1</Font></Text-field></Title>
  <Section collapsed="false" isCollapsible="true">
    <Title><Text-field>1</Text-field></Title>
    <Group><Input><Text-field style="Maple Input">a := 10;</Text-field></Input></Group>
  </Section>
  <Section collapsed="false" isCollapsible="true">
    <Title><Text-field>2</Text-field></Title>
    <Group><Input><Text-field style="Maple Input">b := 20;</Text-field></Input></Group>
  </Section>
</Section>
<Section collapsed="false" isCollapsible="true">
  <Title><Text-field><Font background="[255,0,0]">Problem 2</Font></Text-field></Title>
  <Section collapsed="false" isCollapsible="true">
    <Title><Text-field>1</Text-field></Title>
    <Group><Input><Text-field style="Maple Input">c := 30;</Text-field></Input></Group>
  </Section>
  <Section collapsed="false" isCollapsible="true">
    <Title><Text-field>2</Text-field></Title>
    <Group><Input><Text-field style="Maple Input">d := 40;</Text-field></Input></Group>
  </Section>
  <Section collapsed="false" isCollapsible="true">
    <Title><Text-field>3.</Text-field></Title>
    <Group><Input><Text-field style="Maple Input">e := 50;</Text-field></Input></Group>
  </Section>
</Section>
</Worksheet>
"""
        from ui.worksheet_view import WorksheetView
        ws = WorksheetView(self.engine)
        ws.load_from_content(xml_content, file_path="test_sections.mw")

        # Find section header cells
        sec_headers = [c for c in ws.cells if getattr(c, 'is_section_header', False)]
        self.assertEqual(len(sec_headers), 7)

        # Problem 1 (level 0)
        p1 = sec_headers[0]
        self.assertEqual(p1.section_title, "Problem 1")
        self.assertEqual(p1.section_level, 0)
        self.assertEqual(p1.section_header_layout.contentsMargins().left(), 0)
        self.assertEqual(p1.content_container.layout().contentsMargins().left(), 0)
        self.assertIn("[0,255,0]", p1.section_bg_colors)

        # Subsection 1 under Problem 1 (level 1)
        sub1_1 = sec_headers[1]
        self.assertEqual(sub1_1.section_title, "1")
        self.assertEqual(sub1_1.section_level, 1)
        self.assertEqual(sub1_1.section_header_layout.contentsMargins().left(), 26)
        self.assertEqual(sub1_1.content_container.layout().contentsMargins().left(), 0)

        # Subsection 2 under Problem 1 (level 1)
        sub1_2 = sec_headers[2]
        self.assertEqual(sub1_2.section_title, "2")
        self.assertEqual(sub1_2.section_level, 1)
        self.assertEqual(sub1_2.section_header_layout.contentsMargins().left(), 26)
        self.assertEqual(sub1_2.content_container.layout().contentsMargins().left(), 0)

        # Problem 2 (level 0)
        p2 = sec_headers[3]
        self.assertEqual(p2.section_title, "Problem 2")
        self.assertEqual(p2.section_level, 0)
        self.assertEqual(p2.section_header_layout.contentsMargins().left(), 0)
        self.assertEqual(p2.content_container.layout().contentsMargins().left(), 0)
        self.assertIn("[255,0,0]", p2.section_bg_colors)

        # Subsection 1 under Problem 2 (level 1)
        sub2_1 = sec_headers[4]
        self.assertEqual(sub2_1.section_title, "1")
        self.assertEqual(sub2_1.section_level, 1)
        self.assertEqual(sub2_1.section_header_layout.contentsMargins().left(), 26)
        self.assertEqual(sub2_1.content_container.layout().contentsMargins().left(), 0)

        # Subsection 2 under Problem 2 (level 1)
        sub2_2 = sec_headers[5]
        self.assertEqual(sub2_2.section_title, "2")
        self.assertEqual(sub2_2.section_level, 1)
        self.assertEqual(sub2_2.section_header_layout.contentsMargins().left(), 26)
        self.assertEqual(sub2_2.content_container.layout().contentsMargins().left(), 0)

        # Subsection 3. under Problem 2 (level 1)
        sub2_3 = sec_headers[6]
        self.assertEqual(sub2_3.section_title, "3.")
        self.assertEqual(sub2_3.section_level, 1)
        self.assertEqual(sub2_3.section_header_layout.contentsMargins().left(), 26)
    def test_section_outdent_and_straight_line(self):
        from ui.worksheet_view import WorksheetView
        ws = WorksheetView(engine=self.engine)
        ws.is_worksheet_mode = False  # Document mode

        # Insert Section
        sec = ws.insert_section_cell(title="Opgave 1", level=0)
        self.assertFalse(sec.is_worksheet_mode)
        self.assertFalse(sec.lbl_prompt.isVisible())
        self.assertFalse(sec.bracket_bar.isVisible())

        # Insert cell inside section below
        c1 = ws.insert_cell_below(sec.cell_id)
        self.assertFalse(c1.is_worksheet_mode)
        self.assertFalse(c1.lbl_prompt.isVisible())
        self.assertFalse(c1.bracket_bar.isVisible())
        self.assertTrue(c1.is_inside_section)
        self.assertEqual(c1.section_level, 0)

        # Outdent cell: exits section
        ws.active_cell = c1
        ws.outdent_active_cell()
        self.assertFalse(c1.is_inside_section)
        self.assertEqual(c1.section_level, 0)

        # When section collapses, c1 (outside section) should remain visible
        sec.toggle_section_collapsed()
        self.assertTrue(sec.is_collapsed)
        self.assertFalse(c1.isHidden())

        # Insert statement outside section
        c2 = ws.insert_cell_outside_section()
        self.assertFalse(c2.is_inside_section)
        self.assertFalse(c2.is_worksheet_mode)


if __name__ == '__main__':
    unittest.main()

