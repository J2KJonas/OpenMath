"""
OpenMath Start Page View.
Displays the default startup screen containing:
- 'New Document' (empty document) button
- 'Open Documents' (open existing project) button
Uses clean off-white / light slate white desktop background with crisp white card.
Features responsive layout where the buttons, font sizes, margins, and layout
dynamically adapt to the window size.
"""

import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QBoxLayout, QPushButton,
    QLabel, QFrame, QSizePolicy, QStyleOption, QStyle, QScrollArea, QLayout
)
from PyQt6.QtGui import QFont, QCursor, QPainter, QDesktopServices, QIcon
from PyQt6.QtCore import Qt, pyqtSignal, QUrl, QSize


class StartPageView(QWidget):
    """
    OpenMath Start Page displayed as 'Start.mw'.
    Contains the 2 primary actions: 'New Document' and 'Open Documents'.
    Dynamically adjusts button size, font size, padding, and arrangement
    based on the window dimensions.
    """
    newDocumentRequested = pyqtSignal()
    openDocumentRequested = pyqtSignal()

    def __init__(self, parent=None, theme_mode="light"):
        super().__init__(parent)
        self.theme_mode = theme_mode
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAutoFillBackground(True)
        self.setStyleSheet("background-color: #f4f6f9;")
        self._init_ui()
        self.set_theme_mode(theme_mode)

    def set_theme_mode(self, mode: str):
        """Update StartPage styling based on theme (dark / light)."""
        self.theme_mode = mode
        is_dark = (mode == "dark")
        bg_col = "#141b26" if is_dark else "#f4f6f9"
        card_bg = "#1a2332" if is_dark else "#ffffff"
        card_border = "#2b384c" if is_dark else "#d8dee4"
        title_col = "#38bdf8" if is_dark else "#1e3a8a"
        sep_col = "#2b384c" if is_dark else "#e2e8f0"
        hint_col = "#94a3b8" if is_dark else "#334155"
        dev_col = "#94a3b8" if is_dark else "#475569"

        self.setStyleSheet(f"background-color: {bg_col};")
        if hasattr(self, 'card'):
            self.card.setStyleSheet(f"""
                QFrame#startPageCard {{
                    background-color: {card_bg};
                    border: 1px solid {card_border};
                    border-radius: 6px;
                }}
            """)
        if hasattr(self, 'lbl_title'):
            self.lbl_title.setStyleSheet(f"color: {title_col}; background: transparent; border: none;")
        if hasattr(self, 'sep'):
            self.sep.setStyleSheet(f"color: {sep_col}; background-color: {sep_col}; border: none; height: 1px;")
        if hasattr(self, 'lbl_hint'):
            self.lbl_hint.setStyleSheet(f"color: {hint_col}; background: transparent; border: none;")
        if hasattr(self, 'dev_sep'):
            self.dev_sep.setStyleSheet(f"color: {sep_col}; background-color: {sep_col}; border: none; height: 1px;")
        if hasattr(self, 'lbl_dev'):
            self.lbl_dev.setStyleSheet(f"color: {dev_col}; background: transparent; border: none;")

        self._update_responsive_layout()

    def minimumSizeHint(self):
        return QSize(260, 200)

    def sizeHint(self):
        return QSize(500, 420)

    def paintEvent(self, event):
        """Ensure background color is always painted by Qt."""
        opt = QStyleOption()
        opt.initFrom(self)
        p = QPainter(self)
        self.style().drawPrimitive(QStyle.PrimitiveElement.PE_Widget, opt, p, self)

    def _init_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # Outer scroll area for safety on very small window sizes
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setStyleSheet("QScrollArea { background-color: transparent; border: none; }")
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self.container = QWidget()
        self.container.setStyleSheet("background-color: transparent;")
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.container_layout.setContentsMargins(16, 16, 16, 16)
        self.container_layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)

        # Center content card in pure crisp white
        self.card = QFrame(self.container)
        self.card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        self.card.setStyleSheet("""
            QFrame#startPageCard {
                background-color: #ffffff;
                border: 1px solid #d8dee4;
                border-radius: 6px;
            }
        """)
        self.card.setObjectName("startPageCard")

        self.card_layout = QVBoxLayout(self.card)
        self.card_layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)

        # Header: Title
        self.header_layout = QVBoxLayout()
        self.header_layout.setSpacing(4)

        self.lbl_title = QLabel("OpenMath", self.card)
        self.lbl_title.setStyleSheet("color: #1e3a8a; background: transparent; border: none;")
        self.lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.header_layout.addWidget(self.lbl_title)

        self.card_layout.addLayout(self.header_layout)

        # Separator line
        self.sep = QFrame(self.card)
        self.sep.setFrameShape(QFrame.Shape.HLine)
        self.sep.setStyleSheet("color: #e2e8f0; background-color: #e2e8f0; border: none; height: 1px;")
        self.card_layout.addWidget(self.sep)

        # Actions Container for the 2 buttons (QBoxLayout allows switching between vertical and horizontal)
        self.btn_layout = QBoxLayout(QBoxLayout.Direction.TopToBottom)

        # 1. 'New Document' Button
        self.btn_new = QPushButton("📄   New Document", self.card)
        self.btn_new.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_new.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.btn_new.clicked.connect(self.newDocumentRequested.emit)
        self.btn_layout.addWidget(self.btn_new)

        # 2. 'Open Documents' Button
        self.btn_open = QPushButton("📂   Open Documents", self.card)
        self.btn_open.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_open.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.btn_open.clicked.connect(self.openDocumentRequested.emit)
        self.btn_layout.addWidget(self.btn_open)

        self.card_layout.addLayout(self.btn_layout)

        # Footer note
        self.lbl_hint = QLabel("Select 'New Document' to start an empty worksheet,\nor 'Open Documents' to load a .mw project.", self.card)
        self.lbl_hint.setStyleSheet("color: #334155; background: transparent; border: none;")
        self.lbl_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_hint.setWordWrap(True)
        self.card_layout.addWidget(self.lbl_hint)

        # Developer credits divider
        self.dev_sep = QFrame(self.card)
        self.dev_sep.setFrameShape(QFrame.Shape.HLine)
        self.dev_sep.setStyleSheet("color: #e2e8f0; background-color: #e2e8f0; border: none; height: 1px;")
        self.card_layout.addWidget(self.dev_sep)

        # Developer credits & GitHub buttons
        self.dev_layout = QVBoxLayout()
        self.dev_layout.setSpacing(6)

        self.lbl_dev = QLabel("Developed by", self.card)
        self.lbl_dev.setStyleSheet("color: #475569; background: transparent; border: none;")
        self.lbl_dev.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.dev_layout.addWidget(self.lbl_dev)

        self.btn_links_layout = QHBoxLayout()
        self.btn_links_layout.setSpacing(8)

        gh_icon_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "resources", "github.png"))
        gh_icon = QIcon(gh_icon_path) if os.path.isfile(gh_icon_path) else QIcon()

        self.btn_j2k = QPushButton("  J2KDevelop  ↗", self.card)
        if not gh_icon.isNull():
            self.btn_j2k.setIcon(gh_icon)
            self.btn_j2k.setIconSize(QSize(16, 16))
        self.btn_j2k.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_j2k.setToolTip("Visit J2KDevelop on GitHub (https://github.com/J2KJonas)")
        self.btn_j2k.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://github.com/J2KJonas")))

        self.btn_elomar = QPushButton("  Elomarstudio  ↗", self.card)
        if not gh_icon.isNull():
            self.btn_elomar.setIcon(gh_icon)
            self.btn_elomar.setIconSize(QSize(16, 16))
        self.btn_elomar.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_elomar.setToolTip("Visit Elomarstudio on GitHub (https://github.com/elomarjc)")
        self.btn_elomar.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://github.com/elomarjc")))

        self.btn_links_layout.addWidget(self.btn_j2k)
        self.btn_links_layout.addWidget(self.btn_elomar)
        self.dev_layout.addLayout(self.btn_links_layout)

        self.card_layout.addLayout(self.dev_layout)
        self.container_layout.addWidget(self.card)
        self.scroll_area.setWidget(self.container)
        root_layout.addWidget(self.scroll_area)

        self._update_responsive_layout()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_responsive_layout()

    def _update_responsive_layout(self):
        w = self.width()
        h = self.height()
        if w <= 0 or h <= 0:
            return

        # Check if we should arrange buttons side-by-side or stacked
        is_wide_and_short = (h < 420 and w >= 500)

        if is_wide_and_short:
            self.btn_layout.setDirection(QBoxLayout.Direction.LeftToRight)
            btn_h = max(36, min(42, int(34 + h * 0.02)))
            btn_font = 11.5
            btn_pad_left = 12
            btn_text_align = "center"
            btn_text_new = "📄 New Document"
            btn_text_open = "📂 Open Documents"
            card_w = min(620, max(460, int(w * 0.88)))
            card_pad_v = 12
            card_pad_h = 18
            spacing = 8
            title_pt = 18
            hint_pt = 9.5
            dev_btn_h = 28
            dev_btn_font = 9
            show_hint = (h >= 320)
            show_dev = (h >= 280)
        elif h < 460:
            # Compact vertical
            self.btn_layout.setDirection(QBoxLayout.Direction.TopToBottom)
            btn_h = max(36, min(42, int(34 + (h - 260) * 0.04)))
            btn_font = 11.5
            btn_pad_left = 14
            btn_text_align = "left"
            btn_text_new = "📄   New Document"
            btn_text_open = "📂   Open Documents"
            card_w = min(480, max(260, int(w * 0.85)))
            card_pad_v = 14
            card_pad_h = 20
            spacing = 8
            title_pt = 20
            hint_pt = 9.5
            dev_btn_h = 28
            dev_btn_font = 9
            show_hint = (h >= 360)
            show_dev = (h >= 310)
        elif h < 600:
            # Medium vertical
            self.btn_layout.setDirection(QBoxLayout.Direction.TopToBottom)
            btn_h = max(44, min(50, int(42 + (h - 460) * 0.05)))
            btn_font = 13.0
            btn_pad_left = 18
            btn_text_align = "left"
            btn_text_new = "📄   New Document"
            btn_text_open = "📂   Open Documents"
            card_w = min(520, max(320, int(w * 0.84)))
            card_pad_v = 22
            card_pad_h = 28
            spacing = 16
            title_pt = 23
            hint_pt = 10.5
            dev_btn_h = 32
            dev_btn_font = 9.5
            show_hint = True
            show_dev = True
        else:
            # Spacious / large window
            self.btn_layout.setDirection(QBoxLayout.Direction.TopToBottom)
            btn_h = max(52, min(56, int(50 + (h - 600) * 0.02)))
            btn_font = 15.0
            btn_pad_left = 22
            btn_text_align = "left"
            btn_text_new = "📄   New Document"
            btn_text_open = "📂   Open Documents"
            card_w = min(540, max(360, int(w * 0.82)))
            card_pad_v = 30
            card_pad_h = 34
            spacing = 22
            title_pt = 26
            hint_pt = 11.0
            dev_btn_h = 36
            dev_btn_font = 10
            show_hint = True
            show_dev = True

        # Apply sizes and visibility
        self.card.setMaximumWidth(card_w)
        self.card_layout.setContentsMargins(card_pad_h, card_pad_v, card_pad_h, card_pad_v)
        self.card_layout.setSpacing(spacing)
        self.btn_layout.setSpacing(max(6, spacing // 2))

        self.lbl_title.setFont(QFont("Times New Roman", title_pt, QFont.Weight.Bold))
        self.lbl_hint.setFont(QFont("Segoe UI", int(hint_pt)))
        self.lbl_hint.setVisible(show_hint)

        self.dev_sep.setVisible(show_dev)
        self.lbl_dev.setVisible(show_dev)
        self.btn_j2k.setVisible(show_dev)
        self.btn_elomar.setVisible(show_dev)

        self.btn_new.setText(btn_text_new)
        self.btn_open.setText(btn_text_open)

        is_dark = (getattr(self, 'theme_mode', 'light') == "dark")
        if is_dark:
            btn_style = f"""
                QPushButton {{
                    background-color: #1e2838;
                    color: #f8fafc;
                    font-family: "Segoe UI", -apple-system, sans-serif;
                    font-size: {btn_font}pt;
                    font-weight: bold;
                    border: 1.5px solid #2b384c;
                    border-radius: 4px;
                    padding-left: {btn_pad_left}px;
                    padding-right: {btn_pad_left if btn_text_align == 'center' else 8}px;
                    text-align: {btn_text_align};
                }}
                QPushButton:hover {{
                    background-color: #263346;
                    border-color: #38bdf8;
                    color: #38bdf8;
                }}
                QPushButton:pressed {{
                    background-color: #141c28;
                    border-color: #0284c7;
                }}
            """
            dev_btn_style = f"""
                QPushButton {{
                    background-color: #1e2838;
                    color: #cbd5e1;
                    border: 1px solid #2b384c;
                    border-radius: 4px;
                    padding: 2px 10px;
                    font-size: {dev_btn_font}pt;
                }}
                QPushButton:hover {{
                    background-color: #263346;
                    border-color: #38bdf8;
                    color: #38bdf8;
                }}
                QPushButton:pressed {{
                    background-color: #141c28;
                }}
            """
        else:
            btn_style = f"""
                QPushButton {{
                    background-color: #ffffff;
                    color: #0f172a;
                    font-family: "Segoe UI", -apple-system, sans-serif;
                    font-size: {btn_font}pt;
                    font-weight: bold;
                    border: 1.5px solid #cbd5e1;
                    border-radius: 4px;
                    padding-left: {btn_pad_left}px;
                    padding-right: {btn_pad_left if btn_text_align == 'center' else 8}px;
                    text-align: {btn_text_align};
                }}
                QPushButton:hover {{
                    background-color: #f0f7ff;
                    border-color: #2563eb;
                    color: #1d4ed8;
                }}
                QPushButton:pressed {{
                    background-color: #dbeafe;
                    border-color: #1d4ed8;
                }}
            """
            dev_btn_style = f"""
                QPushButton {{
                    background-color: #f8fafc;
                    color: #1e293b;
                    border: 1px solid #cbd5e1;
                    border-radius: 4px;
                    padding: 2px 10px;
                    font-size: {dev_btn_font}pt;
                }}
                QPushButton:hover {{
                    background-color: #f1f5f9;
                    border-color: #2563eb;
                    color: #2563eb;
                }}
                QPushButton:pressed {{
                    background-color: #e2e8f0;
                }}
            """
        for b in (self.btn_new, self.btn_open):
            b.setFixedHeight(btn_h)
            b.setStyleSheet(btn_style)

        for b in (self.btn_j2k, self.btn_elomar):
            b.setFixedHeight(dev_btn_h)
            b.setStyleSheet(dev_btn_style)
