"""
Unit tests for Table parsing, rendering, and serialization in .mw files.
"""

import unittest
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QPoint, QPointF, QRectF
from PyQt6.QtGui import QMouseEvent, QTextTable, QTextLength
from cas_engine import CASEngine, WorksheetIO
from ui.worksheet_cell import WorksheetCell
from ui.worksheet_view import WorksheetView


class TestTableLoadingAndRendering(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_table_parsing_into_single_cell(self):
        sample_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<Worksheet>
<Table visible="true" exterior="all" interior="group" width="80%">
  <Table-Column weight="100"/>
  <Table-Column weight="200"/>
  <Table-Row align="top">
    <Table-Cell padding="5"><Presentation-Block><Group><Input><Text-field style="Text">Metric</Text-field></Input></Group></Presentation-Block></Table-Cell>
    <Table-Cell padding="5"><Presentation-Block><Group><Input><Text-field style="Text">Value</Text-field></Input></Group></Presentation-Block></Table-Cell>
  </Table-Row>
  <Table-Row align="top">
    <Table-Cell padding="5"><Presentation-Block><Group><Input><Text-field style="Text">Radius r</Text-field></Input></Group></Presentation-Block></Table-Cell>
    <Table-Cell padding="5"><Presentation-Block><Group><Input><Text-field style="Text">15.5 mm</Text-field></Input></Group></Presentation-Block></Table-Cell>
  </Table-Row>
</Table>
</Worksheet>
'''
        cells = WorksheetIO.load_mw_string(sample_xml)
        self.assertEqual(len(cells), 1)
        cell_data = cells[0]
        self.assertTrue(cell_data.get('is_table'))
        self.assertIn('<table', cell_data.get('input', '').lower())
        self.assertIn('Metric', cell_data.get('input', ''))
        self.assertIn('Radius r', cell_data.get('input', ''))
        self.assertIn('15.5 mm', cell_data.get('input', ''))

    def test_table_cell_rendering_in_widget(self):
        cell_data = {
            'input': '<table border="1"><tr><td>Cell 1</td><td>Cell 2</td></tr></table>',
            'input_mode': 2,
            'is_table': True
        }
        cell_widget = WorksheetCell(execution_idx=1)
        cell_widget.from_dict(cell_data)
        self.assertTrue(cell_widget.is_table)
        plain = cell_widget.get_input_text()
        self.assertIn('Cell 1', plain)
        self.assertIn('Cell 2', plain)

    def test_table_save_and_reload_roundtrip(self):
        cells = [{
            'input': '<table border="1"><tr><td>Col A</td><td>Col B</td></tr><tr><td>Val 1</td><td>Val 2</td></tr></table>',
            'input_mode': 2,
            'is_table': True
        }]
        mw_xml = WorksheetIO.save_mw_string(cells)
        self.assertIn('<Table', mw_xml)
        self.assertIn('<Table-Row', mw_xml)
        self.assertIn('<Table-Cell', mw_xml)

        reloaded = WorksheetIO.load_mw_string(mw_xml)
        self.assertEqual(len(reloaded), 1)
        self.assertTrue(reloaded[0].get('is_table'))
        self.assertIn('Col A', reloaded[0].get('input'))
        self.assertIn('Val 1', reloaded[0].get('input'))

    def test_table_official_attributes_and_spans(self):
        sample_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<Worksheet>
<Table visible="true" exterior="horizontal" interior="all" alignment="center" width="90%">
  <Table-Column weight="150" separator="true"/>
  <Table-Column weight="150" separator="true"/>
  <Table-Row align="top" separator="true">
    <Table-Cell columnspan="2" padding="8" fillcolor="[240,240,255]"><Presentation-Block><Group><Input><Text-field style="Title">Merged Header</Text-field></Input></Group></Presentation-Block></Table-Cell>
  </Table-Row>
  <Table-Row align="top">
    <Table-Cell padding="6"><Presentation-Block><Group><Input><Text-field style="Text">Item 1</Text-field></Input></Group></Presentation-Block></Table-Cell>
    <Table-Cell padding="6"><Presentation-Block><Group><Input><Text-field style="Text">100</Text-field></Input></Group></Presentation-Block></Table-Cell>
  </Table-Row>
</Table>
</Worksheet>
'''
        cells = WorksheetIO.load_mw_string(sample_xml)
        self.assertEqual(len(cells), 1)
        tbl_html = cells[0].get('input', '')
        self.assertIn('colspan="2"', tbl_html)
        self.assertIn('margin: 8px auto', tbl_html)
        self.assertIn('background-color: #f0f0ff', tbl_html)
        self.assertIn('padding: 8px 12px', tbl_html)

    def test_math_and_hyperlink_elements(self):
        sample_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<Worksheet>
  <Group>
    <Input>
      <Text-field style="Text">
        Check out our website at <Hyperlink linktarget="https://openmath.org" tooltip="Visit OpenMath">OpenMath</Hyperlink> for details.
      </Text-field>
    </Input>
  </Group>
</Worksheet>
'''
        cells = WorksheetIO.load_mw_string(sample_xml)
        self.assertEqual(len(cells), 1)
        self.assertIn('<a href="https://openmath.org"', cells[0]['input'])
        self.assertIn('title="Visit OpenMath"', cells[0]['input'])
        self.assertIn('OpenMath', cells[0]['input'])

    def test_save_mw_includes_official_styles(self):
        cells = [{'input': 'x + 1', 'input_mode': 1}]
        mw_xml = WorksheetIO.save_mw_string(cells)
        self.assertIn('<Styles>', mw_xml)
        self.assertIn('<Font name="2D Math"', mw_xml)
        self.assertIn('<Font name="Heading 1"', mw_xml)
        self.assertIn('<Layout name="Normal"', mw_xml)


class TestTableInteractionAndResizing(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.cell = WorksheetCell(execution_idx=1)
        self.cell.resize(600, 400)
        table_html = (
            '<table border="1" cellpadding="4" style="width: 300px;">'
            '<tr><td>Col 1</td><td>Col 2</td><td>Col 3</td></tr>'
            '<tr><td>Val 1</td><td>Val 2</td><td>Val 3</td></tr>'
            '</table>'
        )
        self.cell.from_dict({'input': table_html, 'input_mode': 2, 'is_table': True})
        self.cell.show()
        self.app.processEvents()

    def test_find_all_tables_and_geometry(self):
        edit = self.cell.input_edit
        tables = edit._find_all_tables()
        self.assertEqual(len(tables), 1)
        tbl = tables[0]
        self.assertEqual(tbl.columns(), 3)
        self.assertEqual(tbl.rows(), 2)

        geo = edit._get_table_geometry(tbl)
        self.assertGreater(geo.width(), 0)
        self.assertGreater(geo.height(), 0)

        widths = edit._get_table_col_widths(tbl)
        self.assertEqual(len(widths), 3)
        for w in widths:
            self.assertGreater(w, 0)

        dividers = edit._get_table_col_divider_xs(tbl)
        self.assertEqual(len(dividers), 2)  # 2 vertical dividers for 3 columns

    def test_column_divider_drag_resizing(self):
        edit = self.cell.input_edit
        tables = edit._find_all_tables()
        tbl = tables[0]

        # Simulate dragging the column divider between column 0 and column 1
        edit._active_table = tbl
        edit._resizing_table_col = True
        edit._table_resize_col_idx = 0
        edit._table_orig_col_widths = [80.0, 80.0, 80.0]
        edit._table_drag_start_mouse = QPoint(100, 50)

        move_ev = QMouseEvent(
            QMouseEvent.Type.MouseMove,
            QPointF(130, 50),
            QPointF(130, 50),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier
        )
        edit.mouseMoveEvent(move_ev)

        # Check that column 0 grew and column 1 shrank
        constraints = tbl.format().columnWidthConstraints()
        self.assertEqual(len(constraints), 3)
        self.assertAlmostEqual(constraints[0].rawValue(), 110.0, delta=1.0)
        self.assertAlmostEqual(constraints[1].rawValue(), 50.0, delta=1.0)
        self.assertAlmostEqual(constraints[2].rawValue(), 80.0, delta=1.0)

        # Release mouse
        rel_ev = QMouseEvent(
            QMouseEvent.Type.MouseButtonRelease,
            QPointF(130, 50),
            QPointF(130, 50),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier
        )
        edit.mouseReleaseEvent(rel_ev)
        self.assertFalse(edit._resizing_table_col)

    def test_table_right_border_width_resizing(self):
        edit = self.cell.input_edit
        tables = edit._find_all_tables()
        tbl = tables[0]

        edit._active_table = tbl
        edit._resizing_table_size = True
        edit._table_resize_hit = 'right_border'
        edit._table_orig_col_widths = [60.0, 60.0, 60.0]
        edit._table_orig_rect = QRectF(20, 20, 180, 80)
        edit._table_orig_cell_padding = 4.0
        edit._table_drag_start_mouse = QPoint(200, 40)

        # Drag 60px to the right
        move_ev = QMouseEvent(
            QMouseEvent.Type.MouseMove,
            QPointF(260, 40),
            QPointF(260, 40),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier
        )
        edit.mouseMoveEvent(move_ev)

        fmt = tbl.format()
        self.assertAlmostEqual(fmt.width().rawValue(), 240.0, delta=1.0)
        constraints = fmt.columnWidthConstraints()
        self.assertEqual(len(constraints), 3)
        for c in constraints:
            self.assertAlmostEqual(c.rawValue(), 80.0, delta=1.0)

    def test_table_bottom_border_padding_resizing(self):
        edit = self.cell.input_edit
        tables = edit._find_all_tables()
        tbl = tables[0]

        edit._active_table = tbl
        edit._resizing_table_size = True
        edit._table_resize_hit = 'bottom_border'
        edit._table_orig_col_widths = [60.0, 60.0, 60.0]
        edit._table_orig_rect = QRectF(20, 20, 180, 80)
        edit._table_orig_cell_padding = 4.0
        edit._table_drag_start_mouse = QPoint(100, 100)

        # Drag 20px down
        move_ev = QMouseEvent(
            QMouseEvent.Type.MouseMove,
            QPointF(100, 120),
            QPointF(100, 120),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier
        )
        edit.mouseMoveEvent(move_ev)

        fmt = tbl.format()
        self.assertGreater(fmt.cellPadding(), 4.0)

    def test_table_row_and_column_structural_operations(self):
        edit = self.cell.input_edit
        tables = edit._find_all_tables()
        tbl = tables[0]

        initial_rows = tbl.rows()
        initial_cols = tbl.columns()

        tbl.insertRows(1, 1)
        self.assertEqual(tbl.rows(), initial_rows + 1)

        tbl.insertColumns(1, 1)
        self.assertEqual(tbl.columns(), initial_cols + 1)

        tbl.removeRows(1, 1)
        self.assertEqual(tbl.rows(), initial_rows)

        tbl.removeColumns(1, 1)
        self.assertEqual(tbl.columns(), initial_cols)


class TestLazyCellHydration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_lazy_cell_transparent_hydration_on_expand(self):
        engine = CASEngine()
        ws = WorksheetView(engine=engine)
        ws.resize(800, 600)

        # Create a collapsed section header followed by a child cell
        sample_data = [
            {
                'input': 'Section Title',
                'is_section_header': True,
                'section_level': 0,
                'is_collapsed': True,
                'execution_idx': 1
            },
            {
                'input': 'x := 42;',
                'input_mode': 1,
                'section_level': 0,
                'is_section_header': False,
                'execution_idx': 2
            }
        ]

        # Load into worksheet via JSON
        import json
        ws.load_from_json(json.dumps({'cells': sample_data}))
        ws.show()
        self.app.processEvents()

        self.assertEqual(len(ws.cells), 2)
        sec_header = ws.cells[0]
        child_cell = ws.cells[1]

        # Verify child cell was instantiated as lazy and hidden
        self.assertTrue(child_cell._is_lazy)
        self.assertTrue(child_cell.isHidden())

        # Uncollapse the section
        sec_header.is_collapsed = False
        ws._on_section_toggled(sec_header.cell_id, False)
        self.app.processEvents()

        # Verify child cell automatically hydrated and became visible
        self.assertFalse(child_cell._is_lazy)
        self.assertFalse(child_cell.isHidden())
        self.assertIn('x := 42;', child_cell.get_input_text())


if __name__ == '__main__':
    unittest.main()

