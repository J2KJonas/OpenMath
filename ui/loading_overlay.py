"""
Loading Overlay Component for OpenMath CAS Calculator.
Displays a clean, modern, high-contrast light-themed modal card
over the worksheet area while an existing project or document is loading.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar,
    QFrame, QGraphicsDropShadowEffect, QApplication
)
from PyQt6.QtGui import QPainter, QColor, QFont
from PyQt6.QtCore import Qt, QEvent


class LoadingOverlay(QWidget):
    """
    Semi-transparent overlay widget that floats directly over the central
    document stack to indicate project loading progress in real time.
    Strictly adheres to high-contrast light theme.
    """
    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.hide()

        if parent:
            parent.installEventFilter(self)

        self._build_ui()

    def _build_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Centered white card
        self.card = QFrame(self)
        self.card.setObjectName("loadingCard")
        self.card.setFixedWidth(400)
        self.card.setStyleSheet("""
            #loadingCard {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 12px;
            }
        """)

        shadow = QGraphicsDropShadowEffect(self.card)
        shadow.setBlurRadius(24)
        shadow.setColor(QColor(15, 23, 42, 45))
        shadow.setOffset(0, 8)
        self.card.setGraphicsEffect(shadow)

        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(26, 22, 26, 22)
        card_layout.setSpacing(10)

        # Header with icon and title
        header = QHBoxLayout()
        header.setSpacing(10)

        icon_lbl = QLabel("📂", self.card)
        icon_lbl.setFont(QFont("Segoe UI Emoji", 16))

        title_lbl = QLabel("Opening Project...", self.card)
        title_lbl.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        title_lbl.setStyleSheet("color: #0f172a; border: none; background: transparent;")

        header.addWidget(icon_lbl)
        header.addWidget(title_lbl)
        header.addStretch(1)
        card_layout.addLayout(header)

        # Document name label
        self.lbl_filename = QLabel("", self.card)
        self.lbl_filename.setFont(QFont("Segoe UI", 9, QFont.Weight.DemiBold))
        self.lbl_filename.setStyleSheet("color: #2563eb; border: none; background: transparent;")
        self.lbl_filename.setWordWrap(True)
        card_layout.addWidget(self.lbl_filename)

        # Progress bar
        self.progress_bar = QProgressBar(self.card)
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #e2e8f0;
                border: none;
                border-radius: 4px;
                height: 8px;
            }
            QProgressBar::chunk {
                background-color: #2563eb;
                border-radius: 4px;
            }
        """)
        self.progress_bar.setRange(0, 0)
        card_layout.addWidget(self.progress_bar)

        # Status text
        self.lbl_status = QLabel("Reading worksheet archive...", self.card)
        self.lbl_status.setFont(QFont("Segoe UI", 9))
        self.lbl_status.setStyleSheet("color: #64748b; border: none; background: transparent;")
        self.lbl_status.setWordWrap(True)
        card_layout.addWidget(self.lbl_status)

        root_layout.addWidget(self.card)

    def eventFilter(self, watched, event):
        if watched == self.parent() and event.type() == QEvent.Type.Resize:
            self.resize(self.parent().size())
        return super().eventFilter(watched, event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(248, 250, 252, 215))

    def show_loading(self, filename: str = "", message: str = "Reading worksheet archive..."):
        """Show the overlay card, set indeterminate progress, and bring to front."""
        if filename:
            self.lbl_filename.setText(f"File: {filename}")
            self.lbl_filename.show()
        else:
            self.lbl_filename.hide()
        self.lbl_status.setText(message)
        self.progress_bar.setRange(0, 0)

        if self.parent():
            self.setGeometry(self.parent().rect())
            self.raise_()
        self.show()
        QApplication.processEvents()

    def set_progress(self, current: int, total: int, message: str = ""):
        """Update progress bar values and status message."""
        if total > 0:
            self.progress_bar.setRange(0, total)
            self.progress_bar.setValue(current)
        else:
            self.progress_bar.setRange(0, 0)
        if message:
            self.lbl_status.setText(message)
        QApplication.processEvents()

    def hide_loading(self):
        """Hide the overlay."""
        self.hide()
        QApplication.processEvents()
