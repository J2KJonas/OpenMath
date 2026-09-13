"""
Unit tests for Table parsing, rendering, and serialization in .mw files.
"""

import unittest
from PyQt6.QtWidgets import QApplication
from cas_engine import WorksheetIO
from ui.worksheet_cell import WorksheetCell


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


if __name__ == '__main__':
    unittest.main()
