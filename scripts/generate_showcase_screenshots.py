#!/usr/bin/env python3
"""
Generate high-fidelity showcase screenshots for OpenMath.
Captures real desktop application state offscreen with crisp, legible math output.
Context panel closed to give full spacious width to the calculations and document.
3 Light Theme showcases + 1 Glassy Dark Theme showcase.
"""

import os
import sys
import time

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QSettings
from PyQt6.QtGui import QColor, QFont, QTextTableFormat, QTextCharFormat

from ui.main_window import MainWindow
from ui.theme import Theme

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "resources", "screenshots")
os.makedirs(OUT_DIR, exist_ok=True)


def setup_app(theme_name=Theme.LIGHT):
    settings = QSettings("OpenMath", "OpenMath")
    settings.setValue("theme_mode", theme_name)
    app = QApplication.instance() or QApplication([])
    app.setApplicationName("OpenMath")
    app.setOrganizationName("OpenMath")
    app.setPalette(Theme.get_dialog_palette() if theme_name == Theme.LIGHT else Theme.get_app_palette(Theme.DARK))
    app.setStyleSheet(Theme.get_qss(theme_name))
    return app


def generate_screenshot_1_light():
    print("Generating screenshot 1: Academic Light Calculus...")
    app = setup_app(Theme.LIGHT)
    win = MainWindow()
    win.set_theme(Theme.LIGHT, save=False)
    win.resize(1400, 900)
    win.palette_dock.setVisible(True)
    win.context_dock.setVisible(False)  # Closed context panel to give full room to calculations
    win.plot_dock.setVisible(False)

    ws = win.new_worksheet()
    ws.set_theme_mode(Theme.LIGHT)
    ws.set_worksheet_mode(True)
    win.tab_widget.setTabText(1, "Calculus_Worksheet.mw")
    win.setWindowTitle("Calculus_Worksheet.mw - [Server 3] - OpenMath")

    ws.insert_section_cell("1. Advanced Symbolic Calculus & Analysis", level=0)

    c1 = ws.add_cell("f(x) := sin(x) * exp(-x/3)")
    c1.execute()

    c2 = ws.add_cell("diff(f(x), x)")
    c2.execute()

    c3 = ws.add_cell("int(x^2 * cos(x), x)")
    c3.execute()

    c4 = ws.add_cell("solve(x^3 - 6*x^2 + 11*x - 6 = 0, x)")
    c4.execute()

    if hasattr(ws, 'scroll_area'):
        ws.scroll_area.verticalScrollBar().setValue(0)
        ws.scroll_area.horizontalScrollBar().setValue(0)

    app.processEvents()
    time.sleep(0.3)
    app.processEvents()

    win.show()
    app.processEvents()

    out_path = os.path.join(OUT_DIR, "openmath_desktop_light.png")
    win.grab().save(out_path)
    print(f"Saved {out_path} ({os.path.getsize(out_path)} bytes)")
    win.close()


def generate_screenshot_2_dark():
    print("Generating screenshot 2: Dark Mode Tables...")
    app = setup_app(Theme.DARK)
    win = MainWindow()
    win.set_theme(Theme.DARK, save=False)
    win.resize(1400, 900)
    win.palette_dock.setVisible(True)
    win.context_dock.setVisible(False)  # Closed context panel to give full room to calculations
    win.plot_dock.setVisible(False)

    ws = win.new_worksheet()
    ws.set_theme_mode(Theme.DARK)
    ws.set_worksheet_mode(True)
    win.tab_widget.setTabText(1, "Data_and_Constants.mw")
    win.setWindowTitle("Data_and_Constants.mw - [Server 3] - OpenMath")

    ws.insert_section_cell("Physical Constants & Matrix Analysis", level=0)

    # Insert table cell in text mode
    table_cell = ws.add_cell("")
    table_cell.set_input_mode(table_cell.MODE_TEXT)
    cursor = table_cell.input_edit.textCursor()
    
    table_format = QTextTableFormat()
    table_format.setCellPadding(8)
    table_format.setCellSpacing(0)
    table_format.setBorder(1)
    table_format.setBorderBrush(QColor("#475569"))
    
    data = [
        ["Physical Constant", "Symbol", "Governing Formula", "Standard SI Value"],
        ["Speed of Light", "c", "1 / sqrt(mu_0 * eps_0)", "2.99792458e+08 m/s"],
        ["Planck Constant", "hbar", "h / (2 * pi)", "1.05457181e-34 J*s"],
        ["Fine Structure", "alpha", "e^2 / (4*pi*eps_0*hbar*c)", "7.29735256e-03"]
    ]
    table = cursor.insertTable(len(data), len(data[0]), table_format)

    header_fmt = QTextCharFormat()
    header_fmt.setForeground(QColor("#93c5fd"))
    header_fmt.setFontWeight(QFont.Weight.Bold)

    body_fmt = QTextCharFormat()
    body_fmt.setForeground(QColor("#f8fafc"))

    for r_idx, row in enumerate(data):
        for c_idx, val in enumerate(row):
            cell_cur = table.cellAt(r_idx, c_idx).firstCursorPosition()
            fmt = header_fmt if r_idx == 0 else body_fmt
            cell_cur.insertText(val, fmt)

    c1 = ws.add_cell("M := Matrix([[3, 1], [2, 2]])")
    c1.execute()

    c2 = ws.add_cell("Determinant(M)")
    c2.execute()

    c3 = ws.add_cell("M^2")
    c3.execute()

    if hasattr(ws, 'scroll_area'):
        ws.scroll_area.verticalScrollBar().setValue(0)
        ws.scroll_area.horizontalScrollBar().setValue(0)

    app.processEvents()
    time.sleep(0.3)
    app.processEvents()

    win.show()
    app.processEvents()

    out_path = os.path.join(OUT_DIR, "openmath_dark_tables.png")
    win.grab().save(out_path)
    print(f"Saved {out_path} ({os.path.getsize(out_path)} bytes)")
    win.close()


def generate_screenshot_3_sections():
    print("Generating screenshot 3: Hierarchical Sections Tree (Light Theme)...")
    app = setup_app(Theme.LIGHT)
    win = MainWindow()
    win.set_theme(Theme.LIGHT, save=False)
    win.resize(1400, 900)
    win.palette_dock.setVisible(True)
    win.context_dock.setVisible(False)  # Closed context panel to give full room to calculations
    win.plot_dock.setVisible(False)

    ws = win.new_worksheet()
    ws.set_theme_mode(Theme.LIGHT)
    ws.set_worksheet_mode(True)
    win.tab_widget.setTabText(1, "Physics_Course_Notes.mw")
    win.setWindowTitle("Physics_Course_Notes.mw - [Server 3] - OpenMath")

    ws.insert_section_cell("1. Classical Mechanics", level=0)
    ws.insert_section_cell("1.1 Kinematics & Trajectory", level=1)
    c1 = ws.add_cell("x(t) := x_0 + v_0*t + (1/2)*a*t^2")
    c1.execute()
    c2 = ws.add_cell("v(t) := diff(x(t), t)")
    c2.execute()

    ws.insert_section_cell("1.2 Conservation of Energy", level=1)
    c3 = ws.add_cell("E_k := (1/2) * m * v(t)^2")
    c3.execute()
    c4 = ws.add_cell("E_p := m * g * y(t)")
    c4.execute()

    ws.insert_section_cell("2. Electromagnetism & Waves", level=0)
    ws.insert_section_cell("2.1 Maxwell Equations", level=1)
    c5 = ws.add_cell("c := 1 / sqrt(mu_0 * epsilon_0)")
    c5.execute()

    if hasattr(ws, 'scroll_area'):
        ws.scroll_area.verticalScrollBar().setValue(0)
        ws.scroll_area.horizontalScrollBar().setValue(0)

    app.processEvents()
    time.sleep(0.3)
    app.processEvents()

    win.show()
    app.processEvents()

    out_path = os.path.join(OUT_DIR, "openmath_sections_tree.png")
    win.grab().save(out_path)
    print(f"Saved {out_path} ({os.path.getsize(out_path)} bytes)")
    win.close()


def generate_screenshot_4_calculus():
    print("Generating screenshot 4: Typeset Calculus & Matrices with Plotter (Light Theme)...")
    app = setup_app(Theme.LIGHT)
    win = MainWindow()
    win.set_theme(Theme.LIGHT, save=False)
    win.resize(1400, 900)
    win.palette_dock.setVisible(True)
    win.context_dock.setVisible(False)  # Closed context panel to give full room to calculations
    win.plot_dock.setVisible(True)
    win.plot_panel.set_theme_mode(Theme.LIGHT)

    ws = win.new_worksheet()
    ws.set_theme_mode(Theme.LIGHT)
    ws.set_worksheet_mode(True)
    win.tab_widget.setTabText(1, "Linear_Algebra_and_Calculus.mw")
    win.setWindowTitle("Linear_Algebra_and_Calculus.mw - [Server 3] - OpenMath")

    ws.insert_section_cell("Orthogonal Matrices & Dynamic Plots", level=0)

    c1 = ws.add_cell("M := Matrix([[cos(theta), -sin(theta)], [sin(theta), cos(theta)]])")
    c1.execute()

    c2 = ws.add_cell("det(M)")
    c2.execute()

    c3 = ws.add_cell("A := Matrix([[3, 1], [0, 2]])")
    c3.execute()

    c4 = ws.add_cell("int(x^2 * exp(x), x)")
    c4.execute()

    # Draw plot in plot dock
    win.plot_panel.expr_input.setText("sin(x) * exp(-x/5)")
    win.plot_panel.spin_min.setValue(0.0)
    win.plot_panel.spin_max.setValue(15.0)
    win.plot_panel.plot_current_expression()

    if hasattr(ws, 'scroll_area'):
        ws.scroll_area.verticalScrollBar().setValue(0)
        ws.scroll_area.horizontalScrollBar().setValue(0)

    app.processEvents()
    time.sleep(0.4)
    app.processEvents()

    win.show()
    app.processEvents()

    out_path = os.path.join(OUT_DIR, "openmath_desktop_calculus.png")
    win.grab().save(out_path)
    print(f"Saved {out_path} ({os.path.getsize(out_path)} bytes)")
    win.close()


if __name__ == "__main__":
    generate_screenshot_1_light()
    generate_screenshot_2_dark()
    generate_screenshot_3_sections()
    generate_screenshot_4_calculus()
    print("ALL 4 SHOWCASE SCREENSHOTS GENERATED SUCCESSFULLY!")
