"""
Embedded 2D Dynamic Function Plotter for CAS Calculator.
Uses Matplotlib FigureCanvasQTAgg and NavigationToolbar2QT.
Supports standard y=f(x), parametric, and polar plots with export and worksheet insertion.
"""

import matplotlib
matplotlib.use('Agg')
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QLineEdit, QPushButton, QComboBox, QDoubleSpinBox, QCheckBox,
    QFileDialog, QGroupBox, QSplitter, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal
from cas_engine import PlotEngine, PlotData
from .theme import Theme


class PlotPanel(QWidget):
    """
    Embedded 2D Plotter Widget.
    """
    plotInserted = pyqtSignal(object)  # PlotData to insert into worksheet cell

    def __init__(self, parent=None, theme_mode: str = "dark"):
        super().__init__(parent)
        self.theme_mode = theme_mode
        self.current_plot_data = None
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(4)

        # 1. Top Plotting Controls Toolbar
        ctrl_layout = QGridLayout()
        ctrl_layout.setSpacing(6)

        # Expression Input
        ctrl_layout.addWidget(QLabel("Function(s):"), 0, 0)
        self.expr_input = QLineEdit()
        self.expr_input.setPlaceholderText("e.g. sin(x)*exp(-x/5) or [sin(x), cos(x)]")
        self.expr_input.setText("sin(x) * exp(-x/5)")
        self.expr_input.returnPressed.connect(self.plot_current_expression)
        ctrl_layout.addWidget(self.expr_input, 0, 1, 1, 3)

        # Plot Type
        ctrl_layout.addWidget(QLabel("Type:"), 0, 4)
        self.type_combo = QComboBox()
        self.type_combo.addItems(["Function y=f(x)", "Parametric (x(t), y(t))", "Polar r=f(θ)"])
        self.type_combo.currentIndexChanged.connect(self._on_type_changed)
        ctrl_layout.addWidget(self.type_combo, 0, 5)

        # Range Controls
        ctrl_layout.addWidget(QLabel("Range:"), 1, 0)
        range_box = QHBoxLayout()
        range_box.setSpacing(4)

        self.lbl_var = QLabel("x ∈ [")
        range_box.addWidget(self.lbl_var)

        self.spin_min = QDoubleSpinBox()
        self.spin_min.setRange(-1e6, 1e6)
        self.spin_min.setValue(-10.0)
        range_box.addWidget(self.spin_min)

        range_box.addWidget(QLabel(","))

        self.spin_max = QDoubleSpinBox()
        self.spin_max.setRange(-1e6, 1e6)
        self.spin_max.setValue(10.0)
        range_box.addWidget(self.spin_max)

        range_box.addWidget(QLabel("]"))
        ctrl_layout.addLayout(range_box, 1, 1)

        # Options: Grid & Legend
        opts_box = QHBoxLayout()
        self.chk_grid = QCheckBox("Grid")
        self.chk_grid.setChecked(True)
        self.chk_grid.stateChanged.connect(self.replot)
        opts_box.addWidget(self.chk_grid)

        self.chk_legend = QCheckBox("Legend")
        self.chk_legend.setChecked(True)
        self.chk_legend.stateChanged.connect(self.replot)
        opts_box.addWidget(self.chk_legend)
        ctrl_layout.addLayout(opts_box, 1, 2)

        # Plot Action Button
        self.btn_plot = QPushButton("📈 Plot")
        self.btn_plot.setObjectName("primaryBtn")
        self.btn_plot.clicked.connect(self.plot_current_expression)
        ctrl_layout.addWidget(self.btn_plot, 1, 3)

        # Insert to Worksheet Button
        self.btn_insert = QPushButton("📋 Insert to Worksheet")
        self.btn_insert.setToolTip("Embed current plot in active worksheet cell")
        self.btn_insert.clicked.connect(self._on_insert_to_worksheet)
        ctrl_layout.addWidget(self.btn_insert, 1, 4, 1, 2)

        main_layout.addLayout(ctrl_layout)

        # 2. Matplotlib Canvas
        self.fig = Figure(figsize=(6, 4), dpi=100)
        self.canvas = FigureCanvasQTAgg(self.fig)
        self.canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.ax = self.fig.add_subplot(111)

        main_layout.addWidget(self.canvas, 1)

        # 3. Matplotlib Navigation Toolbar
        self.toolbar = NavigationToolbar2QT(self.canvas, self)
        main_layout.addWidget(self.toolbar)

        self._apply_theme()
        self.plot_current_expression()

    def set_theme_mode(self, mode: str):
        """Update theme mode (dark/light) and refresh plot colors."""
        self.theme_mode = mode
        self._apply_theme()
        if self.current_plot_data:
            self.display_plot_data(self.current_plot_data)
        else:
            self.replot()

    def _apply_theme(self):
        """Apply theme colors to matplotlib figure and axes."""
        rc = Theme.get_matplotlib_style(self.theme_mode)
        self.fig.patch.set_facecolor(rc['figure.facecolor'])
        self.ax.set_facecolor(rc['axes.facecolor'])
        for spine in self.ax.spines.values():
            spine.set_color(rc['axes.edgecolor'])
        self.ax.xaxis.label.set_color(rc['axes.labelcolor'])
        self.ax.yaxis.label.set_color(rc['axes.labelcolor'])
        self.ax.tick_params(colors=rc['xtick.color'])
        self.canvas.draw_idle()

    def _on_type_changed(self, idx: int):
        if idx == 0:  # Function
            self.lbl_var.setText("x ∈ [")
            self.spin_min.setValue(-10.0)
            self.spin_max.setValue(10.0)
            if not self.expr_input.text():
                self.expr_input.setText("sin(x) * exp(-x/5)")
        elif idx == 1:  # Parametric
            self.lbl_var.setText("t ∈ [")
            self.spin_min.setValue(0.0)
            self.spin_max.setValue(6.283)
            self.expr_input.setText("cos(t)^3, sin(t)^3")
        elif idx == 2:  # Polar
            self.lbl_var.setText("θ ∈ [")
            self.spin_min.setValue(0.0)
            self.spin_max.setValue(6.283)
            self.expr_input.setText("1 + cos(theta)")

    def plot_current_expression(self):
        """Parse text input and generate plot data."""
        text = self.expr_input.text().strip()
        if not text:
            return

        p_type = self.type_combo.currentIndex()
        v_min = self.spin_min.value()
        v_max = self.spin_max.value()

        try:
            if p_type == 0:  # Function y = f(x)
                if text.startswith('[') and text.endswith(']'):
                    items = [x.strip() for x in text[1:-1].split(',') if x.strip()]
                else:
                    items = [text]
                pdata = PlotEngine.generate_plot(items, var='x', x_min=v_min, x_max=v_max, title=f"Plot of {text}")
            elif p_type == 1:  # Parametric
                parts = [p.strip() for p in text.split(',') if p.strip()]
                if len(parts) >= 2:
                    pdata = PlotEngine.generate_parametric_plot(parts[0], parts[1], t_symbol='t', t_min=v_min, t_max=v_max, title=f"Parametric ({parts[0]}, {parts[1]})")
                else:
                    return
            elif p_type == 2:  # Polar
                pdata = PlotEngine.generate_polar_plot(text, theta_symbol='theta', theta_min=v_min, theta_max=v_max, title=f"Polar r = {text}")

            self.display_plot_data(pdata)
        except Exception as e:
            self.ax.clear()
            self.ax.text(0.5, 0.5, f"Plot Error:\n{str(e)}", ha='center', va='center', color='red', transform=self.ax.transAxes)
            self.canvas.draw()

    def display_plot_data(self, pdata: PlotData):
        """Render PlotData onto Matplotlib canvas."""
        self.current_plot_data = pdata
        self.ax.clear()

        self._apply_theme()
        rc = Theme.get_matplotlib_style(self.theme_mode)

        # Plot curves with modern color palette
        palette = ['#38bdf8', '#f472b6', '#34d399', '#fbbf24', '#a78bfa', '#f87171', '#60a5fa']

        for i, curve in enumerate(pdata.curves):
            color = curve.color or palette[i % len(palette)]
            lbl = curve.label
            if lbl and '\\' in lbl and not (lbl.startswith('$') and lbl.endswith('$')):
                lbl = f"${lbl}$"
            self.ax.plot(curve.x_vals, curve.y_vals, curve.style, label=lbl, color=color, linewidth=2.0)

        if getattr(pdata, 'aspect_equal', False) or getattr(pdata, 'is_polar', False):
            try:
                self.ax.set_aspect('equal', adjustable='datalim')
            except Exception:
                pass

        # Axes labels & Title
        self.ax.set_title(pdata.title, color=rc['text.color'], fontsize=12, fontweight='bold', pad=8)
        self.ax.set_xlabel(pdata.x_label, color=rc['axes.labelcolor'], fontsize=10)
        self.ax.set_ylabel(pdata.y_label, color=rc['axes.labelcolor'], fontsize=10)

        # Grid
        if self.chk_grid.isChecked():
            self.ax.grid(True, color=rc['grid.color'], linestyle=rc['grid.linestyle'], alpha=rc['grid.alpha'])
        else:
            self.ax.grid(False)

        # Render shaded regions (for polygonOmråde / inequalities)
        if hasattr(pdata, 'regions') and pdata.regions:
            for reg in pdata.regions:
                self.ax.fill_between(reg.x_vals, reg.y_min_vals, reg.y_max_vals,
                                     color=reg.color, alpha=reg.alpha)

        # Legend
        if self.chk_legend.isChecked() and pdata.legend and (len(pdata.curves) > 0 or (hasattr(pdata, 'regions') and pdata.regions)):
            leg = self.ax.legend(loc='best', facecolor=rc['axes.facecolor'], edgecolor=rc['axes.edgecolor'])
            if leg:
                for text in leg.get_texts():
                    text.set_color(rc['text.color'])

        # Auto/Manual limits
        if pdata.x_lim:
            self.ax.set_xlim(pdata.x_lim)
        if hasattr(pdata, 'y_lim') and pdata.y_lim:
            self.ax.set_ylim(pdata.y_lim)

        self.canvas.draw()

    def replot(self):
        """Redraw current plot with updated options."""
        if self.current_plot_data:
            self.display_plot_data(self.current_plot_data)
        else:
            self.plot_current_expression()

    def _on_insert_to_worksheet(self):
        if self.current_plot_data:
            self.plotInserted.emit(self.current_plot_data)
