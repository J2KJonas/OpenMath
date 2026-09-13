"""
Background calculation kernel worker using a persistent QThread and signal queue.
Prevents heavy mathematical calculations from freezing the main GUI thread while
guaranteeing thread-safe execution, sequential state consistency, and clean shutdown.
"""

import sys
import queue
from PyQt6.QtCore import QObject, QThread, pyqtSignal, pyqtSlot
from cas_engine import CASEngine, CASResult


class CASKernelWorker(QObject):
    """
    Worker running inside a dedicated background QThread.
    Processes calculation requests sequentially to maintain CAS state consistency.
    """
    started = pyqtSignal(str)                  # cell_id
    finished = pyqtSignal(str, object)         # cell_id, CASResult
    error = pyqtSignal(str, str, str)          # cell_id, title, details

    def __init__(self, engine: CASEngine):
        super().__init__()
        self.engine = engine
        self._is_interrupted = False

    @pyqtSlot(str, str, int)
    def evaluate_task(self, cell_id: str, expression: str, precision: int):
        """Execute calculation in the worker thread."""
        self._is_interrupted = False
        self.started.emit(cell_id)

        try:
            result = self.engine.evaluate(expression, precision=precision)
            if not self._is_interrupted:
                self.finished.emit(cell_id, result)
            else:
                self.error.emit(cell_id, "Interrupted", "Calculation was interrupted.")
        except SyntaxError as se:
            err_title = "Syntax Error"
            err_details = f"Could not parse expression: {se.msg if hasattr(se, 'msg') else str(se)}"
            self.error.emit(cell_id, err_title, err_details)
        except ZeroDivisionError:
            err_title = "Math Error"
            err_details = "Division by zero encountered in expression."
            self.error.emit(cell_id, err_title, err_details)
        except TypeError as te:
            err_title = "Type Error"
            import re
            msg = str(te)
            msg = re.sub(r'CASEngine\._init_builtins\.<locals>\.<lambda>\(\)', 'function()', msg)
            msg = re.sub(r'<locals>\.<lambda>\(\)', 'function()', msg)
            self.error.emit(cell_id, err_title, msg)
        except Exception as e:
            err_title = type(e).__name__
            import re
            msg = str(e) if str(e) else "An unexpected error occurred during CAS evaluation."
            msg = re.sub(r'CASEngine\._init_builtins\.<locals>\.<lambda>\(\)', 'function()', msg)
            msg = re.sub(r'<locals>\.<lambda>\(\)', 'function()', msg)
            self.error.emit(cell_id, err_title, msg)

    @pyqtSlot()
    def interrupt(self):
        self._is_interrupted = True


import atexit
import weakref

_all_runners = weakref.WeakSet()


def _cleanup_all_runners():
    for r in list(_all_runners):
        try:
            r.shutdown()
        except Exception:
            pass


atexit.register(_cleanup_all_runners)


class CalculationRunner(QObject):
    """
    Manages the persistent CAS kernel thread and communicates via Qt signals.
    """
    request_evaluate = pyqtSignal(str, str, int)  # cell_id, expression, precision
    finished = pyqtSignal(str, object)            # cell_id, CASResult
    error = pyqtSignal(str, str, str)             # cell_id, title, details

    def __init__(self, engine: CASEngine, parent=None):
        super().__init__(parent)
        self.engine = engine

        # Create persistent background thread & worker
        self.thread = QThread()
        self.worker = CASKernelWorker(self.engine)
        self.worker.moveToThread(self.thread)

        # Connect signals
        self.request_evaluate.connect(self.worker.evaluate_task)
        self.worker.finished.connect(self.finished)
        self.worker.error.connect(self.error)

        # Start kernel thread loop
        self.thread.start()
        _all_runners.add(self)

    def run_calculation(self, cell_id: str, expression: str, precision: int = 6):
        """Enqueue calculation to background kernel."""
        self.request_evaluate.emit(cell_id, expression, precision)

    def cancel_all(self):
        """Interrupt any running calculation."""
        self.worker.interrupt()

    def shutdown(self):
        """Gracefully stop background thread on application close."""
        try:
            if hasattr(self, 'thread') and self.thread is not None:
                if self.thread.isRunning():
                    if hasattr(self, 'worker') and self.worker is not None:
                        self.worker.interrupt()
                    self.thread.quit()
                    if not self.thread.wait(1000):
                        self.thread.terminate()
                        self.thread.wait(500)
        except (RuntimeError, AttributeError, Exception):
            pass

    def __del__(self):
        try:
            self.shutdown()
        except Exception:
            pass
