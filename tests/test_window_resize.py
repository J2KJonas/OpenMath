import unittest
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QPointF, QEvent
from PyQt6.QtGui import QMouseEvent, QPointingDevice
from ui.main_window import MainWindow


class TestWindowResizeGrips(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance()
        if cls.app is None:
            cls.app = QApplication([])

    def setUp(self):
        self.win = MainWindow()
        self.win.setGeometry(150, 150, 900, 600)
        self.win.show()
        self.app.processEvents()
        self.dev = QPointingDevice.primaryPointingDevice()

    def tearDown(self):
        self.win.close()
        self.app.processEvents()

    def _drag_grip(self, grip, dx, dy):
        p_start = QPointF(grip.rect().center())
        g_start = grip.mapToGlobal(p_start.toPoint())
        g_start_f = QPointF(g_start.x(), g_start.y())
        g_end_f = QPointF(g_start.x() + dx, g_start.y() + dy)

        self.app.sendEvent(grip, QMouseEvent(QEvent.Type.MouseButtonPress, p_start, g_start_f, Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, self.dev))
        self.app.sendEvent(grip, QMouseEvent(QEvent.Type.MouseMove, p_start + QPointF(dx, dy), g_end_f, Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, self.dev))
        self.app.sendEvent(grip, QMouseEvent(QEvent.Type.MouseButtonRelease, p_start + QPointF(dx, dy), g_end_f, Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier, self.dev))
        self.app.processEvents()

    def test_all_grips_exist_with_proper_cursors(self):
        """All 4 corners and 4 edges must have dedicated resize grips with standard resize cursors."""
        grips = self.win._resize_grips
        self.assertEqual(len(grips), 8)

        expected_cursors = {
            "bottom_right": Qt.CursorShape.SizeFDiagCursor,
            "bottom_left": Qt.CursorShape.SizeBDiagCursor,
            "top_right": Qt.CursorShape.SizeBDiagCursor,
            "top_left": Qt.CursorShape.SizeFDiagCursor,
            "left": Qt.CursorShape.SizeHorCursor,
            "right": Qt.CursorShape.SizeHorCursor,
            "top": Qt.CursorShape.SizeVerCursor,
            "bottom": Qt.CursorShape.SizeVerCursor,
        }

        for key, expected_cursor in expected_cursors.items():
            self.assertIn(key, grips)
            self.assertEqual(grips[key].cursor().shape(), expected_cursor, f"Incorrect cursor for {key}")
            self.assertTrue(grips[key].isVisible(), f"Grip {key} should be visible")

    def test_bottom_right_and_bottom_left_resize(self):
        """Verify window resize functionality from bottom-right and bottom-left corners."""
        w0, h0 = self.win.width(), self.win.height()
        self._drag_grip(self.win._resize_grips["bottom_right"], 40, 30)
        self.assertEqual(self.win.width(), w0 + 40)
        self.assertEqual(self.win.height(), h0 + 30)

        w1, h1 = self.win.width(), self.win.height()
        self._drag_grip(self.win._resize_grips["bottom_left"], -30, 20)
        self.assertEqual(self.win.width(), w1 + 30)
        self.assertEqual(self.win.height(), h1 + 20)

    def test_top_corners_and_edges_resize(self):
        """Verify window resize functionality from top corners and edges."""
        w0, h0 = self.win.width(), self.win.height()
        self._drag_grip(self.win._resize_grips["top_right"], 30, 25)
        self.assertEqual(self.win.width(), w0 + 30)
        self.assertEqual(self.win.height(), h0 - 25)

        w1 = self.win.width()
        self._drag_grip(self.win._resize_grips["right"], 20, 0)
        self.assertEqual(self.win.width(), w1 + 20)

    def test_grips_hidden_when_maximized(self):
        """Resize grips must be hidden when window is maximized and restored when normal."""
        from PyQt6.QtTest import QTest

        self.win.showMaximized()
        QTest.qWait(100)

        for key, grip in self.win._resize_grips.items():
            self.assertFalse(grip.isVisible(), f"Grip {key} should be hidden when maximized")

        self.win.showNormal()
        QTest.qWait(100)

        for key, grip in self.win._resize_grips.items():
            self.assertTrue(grip.isVisible(), f"Grip {key} should be restored when normal")


if __name__ == "__main__":
    unittest.main()
