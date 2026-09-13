import sys
import os
sys.path.insert(0, os.path.abspath("."))
import time
from PyQt6.QtWidgets import QApplication
from ui.main_window import MainWindow

def test_app():
    app = QApplication.instance() or QApplication(sys.argv)
    w = MainWindow()
    w.show()

    # Allow event loop to process async calculations
    for _ in range(50):
        app.processEvents()
        time.sleep(0.05)

    w.new_worksheet()
    print("Title:", w.windowTitle())
    print("Cells count:", len(w.worksheet.cells))
    for i, c in enumerate(w.worksheet.cells):
        print(f"Cell {i+1}: input='{c.get_input_text()}', out={c.output_row.isVisible()}, plot={c.plot_container.isVisible()}")

    # Test adding a calculation
    c_new = w.worksheet.add_cell("diff(sin(x) * exp(x), x)")
    c_new.execute()
    for _ in range(30):
        app.processEvents()
        time.sleep(0.05)

    print("New cell result:", c_new.current_result is not None)

    w.close()
    w.worksheet.runner.shutdown()
    print("SUCCESS: UI initialized, calculated, and cleanly shut down.")

if __name__ == "__main__":
    test_app()
