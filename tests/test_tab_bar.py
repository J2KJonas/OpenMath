import unittest
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from ui.main_window import MainWindow, DocumentTabBar, DocumentTabWidget


class TestTabBarLayout(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance()
        if cls.app is None:
            cls.app = QApplication([])

    def setUp(self):
        self.win = MainWindow()
        self.win.resize(1000, 700)
        self.win.show()
        self.app.processEvents()

    def tearDown(self):
        self.win.close()
        self.app.processEvents()

    def test_single_tab_initial_state(self):
        """Initial state should show Start.mw, no scroll buttons, and [+] button."""
        tb = self.win.tab_bar
        self.assertEqual(tb.count(), 1)
        self.assertFalse(tb.usesScrollButtons())
        self.assertTrue(tb.isTabVisible(0))
        self.assertTrue(self.win.btn_add_tab.isVisible())
        self.assertFalse(self.win.btn_tab_overflow.isVisible())

    def test_new_worksheet_shows_both_tabs(self):
        """Adding a new worksheet should display both tabs side-by-side without scrolling off."""
        self.win.new_worksheet()
        self.app.processEvents()

        tb = self.win.tab_bar
        self.assertEqual(tb.count(), 2)
        self.assertFalse(tb.usesScrollButtons())
        self.assertTrue(tb.isTabVisible(0))
        self.assertTrue(tb.isTabVisible(1))

        # Check that tab 0 is not scrolled off to negative x coordinates
        rect0 = tb.tabRect(0)
        rect1 = tb.tabRect(1)
        self.assertGreaterEqual(rect0.x(), 0)
        self.assertGreaterEqual(rect1.x(), rect0.x() + rect0.width() - 2)

        # Tab widget sizeHint should encompass both tabs
        self.assertGreaterEqual(self.win.tab_widget.width(), rect0.width() + rect1.width() - 4)

        # [+] should be visible, [v] overflow hidden
        self.assertTrue(self.win.btn_add_tab.isVisible())
        self.assertFalse(self.win.btn_tab_overflow.isVisible())

    def test_tab_overflow_behavior(self):
        """When tabs exceed available width, overflow button appears with hidden tabs."""
        # Add multiple documents
        for _ in range(7):
            self.win.new_worksheet()
        self.win.resize(600, 600)
        self.app.processEvents()

        tb = self.win.tab_bar
        hidden_indices = [i for i in range(tb.count()) if not tb.isTabVisible(i)]
        self.assertGreater(len(hidden_indices), 0)
        self.assertTrue(self.win.btn_tab_overflow.isVisible())
        self.assertIn("hidden", self.win.btn_tab_overflow.toolTip().lower())

        # Selecting a hidden tab should bring it into the visible range
        hidden_idx = hidden_indices[0]
        self.win._select_tab_and_refresh(hidden_idx)
        self.app.processEvents()
        self.assertTrue(tb.isTabVisible(hidden_idx))


if __name__ == "__main__":
    unittest.main()
