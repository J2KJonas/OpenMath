"""
OpenMath Desktop UI Theme and Matplotlib Style Configurations.
Provides authentic classic desktop scientific-application appearance:
compact UI, traditional gray/white palette, native toolbars, and royal blue math output.
"""

from PyQt6.QtGui import QColor, QFont, QPalette


class Theme:
    """Classic OpenMath Desktop theme and Dark theme interface."""
    OPENMATH = "light"
    LIGHT = "light"
    DARK = "dark"

    # Classic OpenMath Desktop Theme Colors
    OPENMATH_BG_MAIN = "#ececec"
    OPENMATH_BG_SURFACE = "#f3f3f3"
    OPENMATH_BG_CELL = "#ffffff"
    OPENMATH_BG_INPUT = "#ffffff"
    OPENMATH_BORDER = "#b8bcc2"
    OPENMATH_BORDER_LIGHT = "#d9dcdf"
    OPENMATH_BORDER_FOCUS = "#2563eb"
    OPENMATH_TEXT_PRIMARY = "#111827"
    OPENMATH_TEXT_SECONDARY = "#4b5563"
    OPENMATH_TEXT_MUTED = "#6b7280"
    OPENMATH_ACCENT = "#2563eb"          # Royal blue
    OPENMATH_ACCENT_HOVER = "#1d4ed8"
    OPENMATH_PROMPT = "#b22222"          # Dark red prompt
    OPENMATH_MATH_BLUE = "#0044cc"       # Signature output blue
    OPENMATH_MATPLOTLIB_BG = "#ffffff"
    OPENMATH_MATPLOTLIB_TEXT = "#000000"

    # Glassy Dark Theme Colors (Frosted Slate-Navy Glass with Cyan/Sky Accents)
    DARK_BG_MAIN = "#141b26"          # Deep translucent slate-navy base
    DARK_BG_SURFACE = "#1a2332"       # Frosted glass panel & toolbar surface
    DARK_BG_CELL = "#1e2838"          # Elevated worksheet canvas & card background
    DARK_BG_INPUT = "#16202c"         # Slightly recessed input boxes
    DARK_BORDER = "#2b384c"           # Frosted glass subtle boundary
    DARK_BORDER_LIGHT = "#35455e"     # Inset highlights
    DARK_BORDER_FOCUS = "#38bdf8"     # Radiant cyan / sky focus glow
    DARK_TEXT_PRIMARY = "#f8fafc"     # Crisp clean white
    DARK_TEXT_SECONDARY = "#94a3b8"   # Slate gray secondary text
    DARK_TEXT_MUTED = "#64748b"       # Muted annotations
    DARK_ACCENT = "#38bdf8"           # Glowing cyan accent
    DARK_ACCENT_HOVER = "#0ea5e9"     # Sky blue hover
    DARK_PROMPT = "#fb7185"           # Glowing neon coral prompt
    DARK_MATH_BLUE = "#60a5fa"        # Signature glowing math output blue
    DARK_MATPLOTLIB_BG = "#16202c"
    DARK_MATPLOTLIB_TEXT = "#f8fafc"

    LIGHT_BG_MAIN = OPENMATH_BG_MAIN
    LIGHT_BG_SURFACE = OPENMATH_BG_SURFACE
    LIGHT_BG_CELL = OPENMATH_BG_CELL
    LIGHT_BG_INPUT = OPENMATH_BG_INPUT
    LIGHT_BORDER = OPENMATH_BORDER
    LIGHT_BORDER_FOCUS = OPENMATH_BORDER_FOCUS
    LIGHT_TEXT_PRIMARY = OPENMATH_TEXT_PRIMARY
    LIGHT_TEXT_SECONDARY = OPENMATH_TEXT_SECONDARY
    LIGHT_TEXT_MUTED = OPENMATH_TEXT_MUTED
    LIGHT_ACCENT = OPENMATH_ACCENT
    LIGHT_ACCENT_HOVER = OPENMATH_ACCENT_HOVER
    LIGHT_PROMPT = OPENMATH_PROMPT
    LIGHT_MATPLOTLIB_BG = OPENMATH_MATPLOTLIB_BG
    LIGHT_MATPLOTLIB_TEXT = OPENMATH_MATPLOTLIB_TEXT

    @classmethod
    def get_app_palette(cls, mode: str = "light") -> QPalette:
        """Return application palette appropriate for active theme mode."""
        palette = QPalette()
        if mode == cls.DARK:
            palette.setColor(QPalette.ColorRole.Window, QColor("#141b26"))
            palette.setColor(QPalette.ColorRole.WindowText, QColor("#f8fafc"))
            palette.setColor(QPalette.ColorRole.Base, QColor("#16202c"))
            palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#1e2838"))
            palette.setColor(QPalette.ColorRole.Text, QColor("#f8fafc"))
            palette.setColor(QPalette.ColorRole.Button, QColor("#1a2332"))
            palette.setColor(QPalette.ColorRole.ButtonText, QColor("#f8fafc"))
            palette.setColor(QPalette.ColorRole.Highlight, QColor("#0284c7"))
            palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
            palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#1a2332"))
            palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#f8fafc"))
        else:
            palette.setColor(QPalette.ColorRole.Window, QColor("#ececec"))
            palette.setColor(QPalette.ColorRole.WindowText, QColor("#111827"))
            palette.setColor(QPalette.ColorRole.Base, QColor("#ffffff"))
            palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#f3f4f6"))
            palette.setColor(QPalette.ColorRole.Text, QColor("#111827"))
            palette.setColor(QPalette.ColorRole.Button, QColor("#f8fafc"))
            palette.setColor(QPalette.ColorRole.ButtonText, QColor("#111827"))
            palette.setColor(QPalette.ColorRole.Highlight, QColor("#2563eb"))
            palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
            palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#ffffff"))
            palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#111827"))
        return palette

    @classmethod
    def get_dialog_palette(cls) -> QPalette:
        """Return a crisp, high-contrast light palette for clean dialogs."""
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor("#ffffff"))
        palette.setColor(QPalette.ColorRole.WindowText, QColor("#0f172a"))
        palette.setColor(QPalette.ColorRole.Base, QColor("#ffffff"))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#f8fafc"))
        palette.setColor(QPalette.ColorRole.Text, QColor("#0f172a"))
        palette.setColor(QPalette.ColorRole.Button, QColor("#ffffff"))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor("#0f172a"))
        palette.setColor(QPalette.ColorRole.Highlight, QColor("#2563eb"))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
        palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#ffffff"))
        palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#0f172a"))
        return palette

    @classmethod
    def get_qss(cls, mode: str = "light") -> str:
        """Return comprehensive QSS stylesheet for authentic OpenMath look."""
        is_dark = (mode == cls.DARK)
        if not is_dark:
            bg_main = cls.OPENMATH_BG_MAIN
            bg_surface = cls.OPENMATH_BG_SURFACE
            bg_cell = cls.OPENMATH_BG_CELL
            bg_input = cls.OPENMATH_BG_INPUT
            border = cls.OPENMATH_BORDER
            border_light = cls.OPENMATH_BORDER_LIGHT
            border_focus = cls.OPENMATH_BORDER_FOCUS
            text_pri = cls.OPENMATH_TEXT_PRIMARY
            text_sec = cls.OPENMATH_TEXT_SECONDARY
            text_muted = cls.OPENMATH_TEXT_MUTED
            accent = cls.OPENMATH_ACCENT
            accent_hover = cls.OPENMATH_ACCENT_HOVER
            prompt_color = cls.OPENMATH_PROMPT
            math_blue = cls.OPENMATH_MATH_BLUE
            menu_bg = "#ffffff"
            menu_border = "#cbd5e1"
            menu_text = "#1e293b"
            menu_hover_bg = "#eff6ff"
            menu_hover_text = "#2563eb"
            menu_disabled_text = "#94a3b8"
            menu_sep = "#e2e8f0"
            scrollbar_bg = "#f8fafc"
            scrollbar_border = "#e2e8f0"
            scrollbar_handle = "#94a3b8"
            scrollbar_handle_hover = "#64748b"
            scrollbar_handle_pressed = "#334155"
        else:
            bg_main = cls.DARK_BG_MAIN
            bg_surface = cls.DARK_BG_SURFACE
            bg_cell = cls.DARK_BG_CELL
            bg_input = cls.DARK_BG_INPUT
            border = cls.DARK_BORDER
            border_light = cls.DARK_BORDER_LIGHT
            border_focus = cls.DARK_BORDER_FOCUS
            text_pri = cls.DARK_TEXT_PRIMARY
            text_sec = cls.DARK_TEXT_SECONDARY
            text_muted = cls.DARK_TEXT_MUTED
            accent = cls.DARK_ACCENT
            accent_hover = cls.DARK_ACCENT_HOVER
            prompt_color = cls.DARK_PROMPT
            math_blue = cls.DARK_MATH_BLUE
            menu_bg = "#1a2332"
            menu_border = "#2b384c"
            menu_text = "#f8fafc"
            menu_hover_bg = "#233348"
            menu_hover_text = "#38bdf8"
            menu_disabled_text = "#64748b"
            menu_sep = "#2b384c"
            scrollbar_bg = "#16202c"
            scrollbar_border = "#2b384c"
            scrollbar_handle = "#475569"
            scrollbar_handle_hover = "#64748b"
            scrollbar_handle_pressed = "#94a3b8"

        tab_bg = "#161e2a" if is_dark else "#e2e4e8"
        tab_active_bg = bg_cell if is_dark else "#ffffff"
        tab_hover_bg = "#1f2a3a" if is_dark else "#edf0f5"
        btn_bg = "#202b3a" if is_dark else "#f8fafc"
        btn_hover_bg = "#28364a" if is_dark else "#e2e8f0"
        btn_pressed_bg = "#1b2533" if is_dark else "#cbd5e1"
        btn_hover_border = accent if is_dark else "#94a3b8"
        dock_title_bg = "#1b2434" if is_dark else "#e2e4e8"
        status_label_bg = "#18202c" if is_dark else "#fafafa"
        menubar_sel_bg = "#233348" if is_dark else "#dbeafe"
        menubar_sel_fg = "#38bdf8" if is_dark else "#1e3a8a"
        toolbtn_hover_bg = "#233348" if is_dark else "#e0f2fe"
        toolbtn_hover_border = "#38bdf8" if is_dark else "#93c5fd"
        toolbtn_press_bg = "#1e3a5f" if is_dark else "#bfdbfe"

        return f"""
        /* OpenMath Desktop Application Window */
        QMainWindow {{
            background-color: {bg_main};
            color: {text_pri};
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif;
            font-size: 12px;
        }}

        QWidget {{
            color: {text_pri};
        }}

        QStackedWidget {{
            background-color: {bg_main if is_dark else "#f4f6f9"};
        }}

        /* Traditional MenuBar */
        QMenuBar {{
            background-color: {bg_surface};
            color: {text_pri};
            border-bottom: 1px solid {border};
            padding: 2px 4px;
            font-size: 12px;
        }}
        QMenuBar::item {{
            background: transparent;
            padding: 4px 8px;
            border-radius: 3px;
        }}
        QMenuBar::item:selected {{
            background-color: {menubar_sel_bg};
            color: {menubar_sel_fg};
        }}

        /* Modern Desktop Menus */
        QMenu {{
            background-color: {menu_bg};
            border: 1px solid {menu_border};
            border-radius: 8px;
            padding: 6px;
            color: {menu_text};
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            font-size: 13px;
            font-weight: 500;
        }}
        QMenu::item {{
            padding: 6px 24px 6px 14px;
            border-radius: 4px;
            color: {menu_text};
        }}
        QMenu::item:selected {{
            background-color: {menu_hover_bg};
            color: {menu_hover_text};
        }}
        QMenu::item:disabled {{
            color: {menu_disabled_text};
        }}
        QMenu::separator {{
            height: 1px;
            background-color: {menu_sep};
            margin: 4px 6px;
        }}

        /* OpenMath Compact Toolbar */
        QToolBar {{
            background-color: {bg_surface};
            border-bottom: 1px solid {border};
            spacing: 2px;
            padding: 2px 4px;
        }}
        QToolBar::separator {{
            width: 1px;
            background-color: {border};
            margin: 2px 4px;
        }}
        QToolButton {{
            background-color: transparent;
            color: {text_pri};
            border: 1px solid transparent;
            border-radius: 3px;
            padding: 2px 4px;
            font-size: 11px;
        }}
        QToolButton:hover {{
            background-color: {toolbtn_hover_bg};
            border: 1px solid {toolbtn_hover_border};
        }}
        QToolButton:pressed {{
            background-color: {toolbtn_press_bg};
            border: 1px solid {accent};
        }}
        QToolButton:checked {{
            background-color: {toolbtn_hover_bg};
            border: 1px solid {border};
        }}

        /* OpenMath Dock Panels */
        QDockWidget {{
            color: {text_pri};
            font-size: 11px;
            font-weight: bold;
            background-color: {bg_surface};
        }}
        QDockWidget::title {{
            background: {dock_title_bg};
            padding: 5px 8px;
            border-bottom: 1px solid {border};
            border-right: 1px solid {border};
            font-size: 11px;
            font-weight: bold;
            color: {text_pri};
        }}

        /* Tab Widgets (Document Tabs & Dock Tabs) */
        QTabWidget {{
            background-color: {bg_surface};
        }}
        QTabBar {{
            background-color: {tab_bg};
        }}
        QTabWidget::pane {{
            border: 1px solid {border};
            background: {tab_active_bg};
        }}
        QTabBar::tab {{
            background: {tab_bg};
            color: {text_sec};
            padding: 4px 12px;
            border: 1px solid {border};
            border-bottom: none;
            margin-right: 1px;
            font-size: 11px;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif;
        }}
        QTabBar::tab:selected {{
            background: {tab_active_bg};
            color: {text_pri};
            font-weight: bold;
            border-top: 2px solid {accent};
            border-bottom: 1px solid {tab_active_bg};
        }}
        QTabBar::tab:hover:!selected {{
            background: {tab_hover_bg};
        }}

        /* Status Bar (Sunken segments like classic CAS) */
        QStatusBar {{
            background-color: {bg_surface};
            color: {text_sec};
            border-top: 1px solid {border};
            font-size: 11px;
            padding: 2px 4px;
        }}
        QStatusBar QLabel {{
            border: 1px solid {border};
            padding: 2px 8px;
            margin-left: 3px;
            border-radius: 3px;
            background-color: {status_label_bg};
            color: {text_sec};
        }}

        /* Compact PushButtons */
        QPushButton {{
            background-color: {btn_bg};
            color: {text_pri};
            border: 1px solid {border};
            border-radius: 3px;
            padding: 2px 8px;
            font-size: 11px;
        }}
        QPushButton:hover {{
            background-color: {btn_hover_bg};
            border-color: {btn_hover_border};
            color: {accent if is_dark else text_pri};
        }}
        QPushButton:pressed {{
            background-color: {btn_pressed_bg};
        }}

        /* LineEdits, ComboBoxes and SpinBoxes */
        QLineEdit {{
            background-color: {bg_input};
            color: {text_pri};
            border: 1px solid {border};
            border-radius: 3px;
            padding: 2px 6px;
            font-size: 11px;
        }}
        QLineEdit:focus {{
            border-color: {border_focus};
            background-color: {bg_input};
        }}

        QComboBox, QSpinBox, QDoubleSpinBox {{
            background-color: {bg_input};
            color: {text_pri};
            border: 1px solid {border};
            border-radius: 2px;
            padding: 2px 6px;
            font-size: 11px;
        }}
        QComboBox:hover, QSpinBox:hover {{
            border-color: {border_focus};
        }}
        QComboBox QAbstractItemView {{
            background-color: {menu_bg};
            color: {menu_text};
            border: 1px solid {menu_border};
            border-radius: 8px;
            selection-background-color: {menu_hover_bg};
            selection-color: {menu_hover_text};
            min-width: 60px;
            padding: 4px;
        }}

        /* Scrollbars - High-contrast, easy to see and track */
        QScrollBar:vertical {{
            border: none;
            border-left: 1px solid {scrollbar_border};
            background: {scrollbar_bg};
            width: 16px;
            margin: 0px;
        }}
        QScrollBar::handle:vertical {{
            background: {scrollbar_handle};
            min-height: 36px;
            border-radius: 5px;
            margin: 2px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: {scrollbar_handle_hover};
        }}
        QScrollBar::handle:vertical:pressed {{
            background: {scrollbar_handle_pressed};
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
            background: none;
        }}
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
            background: none;
        }}

        QScrollBar:horizontal {{
            border: none;
            border-top: 1px solid {scrollbar_border};
            background: {scrollbar_bg};
            height: 16px;
            margin: 0px;
        }}
        QScrollBar::handle:horizontal {{
            background: {scrollbar_handle};
            min-width: 36px;
            border-radius: 5px;
            margin: 2px;
        }}
        QScrollBar::handle:horizontal:hover {{
            background: {scrollbar_handle_hover};
        }}
        QScrollBar::handle:horizontal:pressed {{
            background: {scrollbar_handle_pressed};
        }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
            width: 0px;
            background: none;
        }}
        QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
            background: none;
        }}

        /* Splitters */
        QSplitter::handle {{
            background-color: {border};
        }}
        QSplitter::handle:horizontal {{
            width: 3px;
        }}
        QSplitter::handle:vertical {{
            height: 3px;
        }}

        /* =========================================================================
           All Popups and Dialogs (Always Clean High-Contrast Light Theme)
           Guarantees 100% readability across Windows/macOS/Linux Dark Mode
           ========================================================================= */
        QDialog, QMessageBox {{
            background-color: #ffffff;
            color: #0f172a;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif;
            font-size: 12px;
        }}

        QDialog QLabel, QMessageBox QLabel {{
            background-color: transparent;
            color: #0f172a;
            font-size: 12px;
        }}

        QMessageBox QLabel#qt_msgbox_label,
        QMessageBox QLabel#qt_msgbox_informativelabel {{
            background-color: transparent;
            color: #0f172a;
            font-size: 12px;
            font-weight: 500;
        }}

        QDialog QScrollArea, QDialog QScrollArea > QWidget, QDialog QScrollArea > QWidget > QWidget {{
            background-color: #f8fafc;
            color: #0f172a;
        }}

        QDialog QPushButton, QMessageBox QPushButton {{
            background-color: #ffffff;
            color: #0f172a;
            border: 1px solid #cbd5e1;
            border-radius: 4px;
            padding: 6px 16px;
            font-size: 12px;
            font-weight: 500;
            min-width: 72px;
            min-height: 24px;
        }}

        QDialog QPushButton:hover, QMessageBox QPushButton:hover {{
            background-color: #f1f5f9;
            border-color: #94a3b8;
        }}

        QDialog QPushButton:pressed, QMessageBox QPushButton:pressed {{
            background-color: #e2e8f0;
        }}

        QDialog QPushButton#primaryBtn, QDialog QPushButton:default, QMessageBox QPushButton:default {{
            background-color: #2563eb;
            color: #ffffff;
            border: 1px solid #1d4ed8;
            font-weight: 600;
        }}

        QDialog QPushButton#primaryBtn:hover, QDialog QPushButton:default:hover, QMessageBox QPushButton:default:hover {{
            background-color: #1d4ed8;
        }}

        QDialog QPushButton#primaryBtn:pressed, QDialog QPushButton:default:pressed, QMessageBox QPushButton:default:pressed {{
            background-color: #1e40af;
        }}

        QDialog QLineEdit, QMessageBox QLineEdit {{
            background-color: #ffffff;
            color: #0f172a;
            border: 1px solid #cbd5e1;
            border-radius: 3px;
            padding: 4px 6px;
            font-size: 12px;
        }}

        QDialog QLineEdit:focus {{
            border-color: #2563eb;
        }}

        QDialog QSpinBox, QDialog QDoubleSpinBox {{
            background-color: #ffffff;
            color: #0f172a;
            border: 1px solid #cbd5e1;
            border-radius: 3px;
            padding: 2px 4px;
            font-size: 12px;
        }}

        QDialog QComboBox {{
            background-color: #ffffff;
            color: #0f172a;
            border: 1px solid #cbd5e1;
            border-radius: 3px;
            padding: 2px 6px;
            font-size: 12px;
        }}

        QDialog QComboBox QAbstractItemView {{
            background-color: #ffffff;
            color: #0f172a;
            border: 1px solid #cbd5e1;
            selection-background-color: #eff6ff;
            selection-color: #2563eb;
        }}

        QDialog QTextEdit, QDialog QPlainTextEdit {{
            background-color: #ffffff;
            color: #0f172a;
            border: 1px solid #cbd5e1;
        }}

        QDialog QCheckBox, QMessageBox QCheckBox {{
            background-color: transparent;
            color: #0f172a;
            font-size: 12px;
            font-weight: 500;
            spacing: 6px;
        }}

        QDialog QGroupBox {{
            background-color: transparent;
            color: #0f172a;
            border: 1px solid #e2e8f0;
            border-radius: 4px;
            margin-top: 8px;
            padding-top: 10px;
            font-weight: bold;
        }}

        QDialog QGroupBox::title {{
            color: #0f172a;
            subcontrol-origin: margin;
            subcontrol-position: top left;
            padding: 0 4px;
        }}
        """

    @classmethod
    def get_matplotlib_style(cls, mode: str = "light") -> dict:
        """Return rcParams for Matplotlib according to active theme."""
        if mode == cls.DARK:
            return {
                'figure.facecolor': cls.DARK_MATPLOTLIB_BG,
                'axes.facecolor': cls.DARK_MATPLOTLIB_BG,
                'axes.edgecolor': cls.DARK_BORDER,
                'axes.labelcolor': cls.DARK_TEXT_PRIMARY,
                'xtick.color': cls.DARK_TEXT_SECONDARY,
                'ytick.color': cls.DARK_TEXT_SECONDARY,
                'text.color': cls.DARK_TEXT_PRIMARY,
                'grid.color': '#334155',
                'grid.linestyle': '--',
                'grid.alpha': 0.7,
                'font.family': 'sans-serif',
                'mathtext.fontset': 'cm',
            }
        else:
            return {
                'figure.facecolor': cls.OPENMATH_MATPLOTLIB_BG,
                'axes.facecolor': cls.OPENMATH_MATPLOTLIB_BG,
                'axes.edgecolor': "#64748b",
                'axes.labelcolor': "#1e293b",
                'xtick.color': "#334155",
                'ytick.color': "#334155",
                'text.color': "#000000",
                'grid.color': '#cbd5e1',
                'grid.linestyle': '--',
                'grid.alpha': 0.7,
                'font.family': 'sans-serif',
                'mathtext.fontset': 'cm',
            }

    @classmethod
    def get_menu_style(cls, mode: str = "light") -> str:
        """Return stylesheet for clean, modern context menus."""
        is_dark = (mode == cls.DARK)
        if not is_dark:
            return """
                QMenu {
                    background-color: #ffffff;
                    border: 1px solid #cbd5e1;
                    border-radius: 8px;
                    padding: 6px;
                    color: #1e293b;
                    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                    font-size: 13px;
                    font-weight: 500;
                }
                QMenu::item {
                    padding: 6px 24px 6px 14px;
                    border-radius: 4px;
                    color: #1e293b;
                }
                QMenu::item:selected {
                    background-color: #eff6ff;
                    color: #2563eb;
                }
                QMenu::item:disabled {
                    color: #94a3b8;
                }
                QMenu::separator {
                    height: 1px;
                    background-color: #e2e8f0;
                    margin: 4px 6px;
                }
            """
        else:
            return """
                QMenu {
                    background-color: #1a2332;
                    border: 1px solid #2b384c;
                    border-radius: 8px;
                    padding: 6px;
                    color: #f8fafc;
                    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                    font-size: 13px;
                    font-weight: 500;
                }
                QMenu::item {
                    padding: 6px 24px 6px 14px;
                    border-radius: 4px;
                    color: #f8fafc;
                }
                QMenu::item:selected {
                    background-color: #233348;
                    color: #38bdf8;
                }
                QMenu::item:disabled {
                    color: #64748b;
                }
                QMenu::separator {
                    height: 1px;
                    background-color: #2b384c;
                    margin: 4px 6px;
                }
            """

    @classmethod
    def apply_menu_style(cls, menu, mode: str = "light"):
        """Apply modern clean menu styling to a QMenu instance."""
        if menu:
            menu.setStyleSheet(cls.get_menu_style(mode))

