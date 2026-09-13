# OpenMath

A desktop mathematical calculator application focusing on symbolic computation, mathematical rendering, and an interactive worksheet document feel.

**Developed by [J2KJonas](https://github.com/J2KJonas) and [elomarjc](https://github.com/elomarjc)**

![Platform](https://img.shields.io/badge/Platform-macOS%20%7C%20Linux%20%7C%20Windows-blue)
![Python](https://img.shields.io/badge/Python-3.10%2B-brightgreen)
![PyQt6](https://img.shields.io/badge/GUI-PyQt6-green)
![SymPy](https://img.shields.io/badge/Engine-SymPy-orange)
![Matplotlib](https://img.shields.io/badge/Plots%20%26%20LaTeX-Matplotlib-blue)

---

## Key Features

### 1. Interactive Worksheet / Document Layout
- **Stacked Execution Blocks (Cells)**: Chronologically ordered `[In n]` and `[Out n]` calculation cells.
- **High-DPI Typeset LaTeX**: Beautifully rendered mathematical formulas via Matplotlib's MathText engine with retina scaling.
- **Exact vs. Numeric Evaluation Switch**: Instantly toggle between exact symbolic representations (e.g. $\sqrt{2}$, $\frac{\pi}{4}$) and arbitrary-precision floating point approximations (e.g. $1.41421356$, $0.785398$).
- **Per-Cell Precision Control**: Configurable digit precision from 2 to 50 decimal digits.
- **One-Click Exports**: Copy LaTeX formula to clipboard, copy plain text or Python code.
- **Worksheet Serialization**: Save/load worksheets to `.mw` or export directly to standalone `.tex` (compilable LaTeX documents) and `.md` (Markdown documents).

### 2. Symbolic Operations Palette & Math Toolbar
- **Expression Templates**: $\int \square \, dx$, $\int_a^b \square \, dx$, $\frac{d}{dx}\square$, $\lim_{x\to a}\square$, $\sum_{i=1}^n\square$, $\prod_{i=1}^n\square$, $\sqrt{\square}$, $\sqrt[n]{\square}$, $\frac{a}{b}$, $x^y$, $|x|$, $\log_b(x)$.
- **Algebra**: Expand, Factor, Simplify, Solve for $x$, Solve Linear/Nonlinear Systems, Partial Fractions (`apart`), Collect, Trig Expand/Simplify.
- **Calculus**: Differentiate ($d/dx, d^n/dx^n$), Indefinite & Definite Integrals, Limits, Taylor & Laurent Series expansions, Differential Equations solver (`dsolve`).
- **Linear Algebra**:
  - **✨ Interactive Matrix Wizard**: Visual dialog to configure arbitrary $M \times N$ matrices with Identity, Zeros, Ones, Diagonal, and custom presets.
  - Operations: Determinant ($\det M$), Matrix Inverse ($M^{-1}$), Eigenvalues, Eigenvectors, Nullspace, Rank, Reduced Row Echelon Form (RREF), Transpose ($M^T$), and Characteristic Polynomial.
- **Greek & Symbols Palette**: $\alpha, \beta, \gamma, \delta, \theta, \lambda, \mu, \pi, \sigma, \phi, \psi, \omega, \infty, \partial, \nabla, \pm, \neq, \leq, \geq$, etc.
- **Transcendental & Special Functions**: Trigonometric, Hyperbolic, Exponential, Logarithmic, Gamma ($\Gamma$), Error Function ($\text{erf}$), and Bessel functions.

### 3. Embedded Systems & Digital Hardware Engine
- **Bitwise Logic & Masks**: `to_bin(val, bits)`, `to_hex(val, bits)`, `twos_comp_repr(val, bits)`, `bit_set`, `bit_clear`, `bit_toggle`, `bit_field(val, start, end)`.
- **Fixed-Point Arithmetic**: Convert floating-point to/from Q-format fixed point (`to_q(3.1415, 7, 8)`, `from_q(804, 8)`).
- **IEEE-754 Floating Point**: Single and double precision decomposition into sign, biased exponent, and mantissa (`ieee754(12.375)`).
- **Microcontroller Hardware Calculations**:
  - **UART Baud Rate**: Calculate UBRR/BRR register values and baud rate error % (`ubrr_calc(16*MHz, 9600)`).
  - **Timers & Prescalers**: Frequency, tick time, period, and overflow interval (`timer_calc(16*MHz, 64, 249)`).
  - **PWM Generation**: Find required ARR register for target frequency (`timer_arr(84*MHz, 84, 1000)`) and duty cycle (`pwm_duty(1000, 250)`).
- **Sensors, ADC & DAC**:
  - ADC Quantization Step (LSB voltage) & Theoretical SNR (`adc_resolution(3.3, 12)`).
  - Analog voltage to Raw ADC counts (`adc_raw(1.65, 3.3, 10)`) and vice versa (`adc_volt(512, 3.3, 10)`).
- **Electronics & Signal Conditioning**:
  - Voltage Dividers (`voltage_divider(5.0, 10*kOhm, 10*kOhm)`).
  - LED Current Limiting Resistor & Power dissipation (`led_resistor(5.0, 2.0, 20.0)`).
  - RC Filter Cutoff Frequency & Time Constant $\tau$ (`rc_cutoff(10*kOhm, 100*nF)`).
  - CRC Checksums: CRC-8 and CRC-16-CCITT (`crc8('DATA')`, `crc16('DATA')`).
- **SI Engineering Units**: `kHz`, `MHz`, `GHz`, `ms`, `us`, `ns`, `kOhm`, `MOhm`, `uF`, `nF`, `pF`, `mA`, `uA`.

### 4. Embedded 2D Dynamic Plotter
- Integrated **Matplotlib 2D Plotter** with interactive navigation (Pan, Box Zoom, Home/Reset, Save figure).
- Supports:
  - **Function Plots**: $y = f(x)$ or multi-curve lists `[sin(x), cos(x)]`.
  - **Parametric Plots**: $(x(t), y(t))$ over $t \in [t_{\min}, t_{\max}]$.
  - **Polar Plots**: $r = f(\theta)$ over $\theta \in [\theta_{\min}, \theta_{\max}]$.
- Automated discontinuity handling (avoids vertical line artifacts on asymptotes like $\tan x$ or $1/x$).
- **Insert to Worksheet**: Embed dynamic plot commands and figures directly into notebook cells.

### 5. Input Assistant & Smart Syntax Preprocessor
- **Natural Shorthand Math**: Auto-converts `2x` $\rightarrow$ `2*x`, `(x+1)(x-1)` $\rightarrow$ `(x+1)*(x-1)`, `x^2` $\rightarrow$ `x**2`, `√x` $\rightarrow$ `sqrt(x)`.
- **Assignment Operator (`:=`)**: `f(x) := sin(x) + cos(x)`, `a := 15`.
- **Equation Solving**: `solve(x^2 - 5x + 6 = 0, x)`.
- **Dedicated Status Bar**: Diagnostic error messages in plain language without GUI crashes.

### 6. Multithreaded Execution & Modern Themes
- **Non-Blocking Calculation Worker**: Heavy computations (integrals, series, solves) run in background `QThread` workers, keeping the GUI 100% responsive.
- **Dual Themes**:
  - **Modern Slate Dark**: Sleek dark IDE theme with cyan mathematical highlights.
  - **Academic Light**: Clean, warm white/slate academic aesthetic.

---

## Technology Stack

- **GUI Framework**: PyQt6
- **Math Engine**: SymPy
- **Plotting & LaTeX Rendering**: Matplotlib (`FigureCanvasQTAgg` & `FigureCanvasAgg`)
- **Numerical Support**: NumPy

---

## Installation & Setup

### 1. Clone the repository
```bash
git clone https://github.com/J2KJonas/calculator.git
cd calculator
```

### 2. Run the Application

#### Linux (Zorin OS, Ubuntu, Debian, Fedora, Arch):

1. **Install system prerequisites** (if not already installed):
   - **Zorin OS / Ubuntu / Debian**:
     ```bash
     sudo apt update
     sudo apt install -y python3 python3-venv python3-pip libxcb-cursor0 libxkbcommon-x11-0 libgl1 libegl1
     ```
   - **Fedora**:
     ```bash
     sudo dnf install -y python3 python3-pip libxcb-cursor libxkbcommon-x11
     ```
   - **Arch Linux**:
     ```bash
     sudo pacman -S python python-pip libxcb xcb-util-cursor libxkbcommon
     ```

2. **Launch with the universal script** (automatically sets up `.venv` and installs dependencies):
   ```bash
   chmod +x run.sh
   ./run.sh
   ```

   > [!NOTE]
   > **PEP 668 on Zorin OS / Ubuntu 24.04+**: Modern Linux distributions prevent running `pip install` on the system Python. `./run.sh` automatically creates and uses an isolated `.venv` virtual environment for you.
   > If you prefer to manually manage your virtual environment:
   > ```bash
   > python3 -m venv .venv
   > source .venv/bin/activate
   > pip install -r requirements.txt
   > python3 main.py
   > ```

3. *(Optional)* **Add OpenMath to your Application Menu and Desktop**:
   ```bash
   chmod +x create_shortcut_linux.sh
   ./create_shortcut_linux.sh
   ```
   On Zorin OS / GNOME desktops, this adds OpenMath directly to your Start / Applications menu and places a trusted launcher on your Desktop.

#### Windows:
- Double-click **`run.bat`** (or run `python main.py` / `py -3 main.py` in Command Prompt / PowerShell)
- *(Optional)* Create Desktop & Start Menu shortcuts: double-click **`create_shortcut_windows.bat`**

#### macOS (Apple Silicon M1/M2/M3/M4 & Intel):
- Run in terminal:
  ```bash
  chmod +x run.sh
  ./run.sh
  ```
  *(or `python3 main.py`)*
- *(Optional)* Create native macOS Application in `~/Applications/OpenMath.app` and on Desktop:
  ```bash
  chmod +x create_shortcut.sh
  ./create_shortcut.sh
  ```

---

## Keyboard Shortcuts

| Shortcut (Win / Linux) | Shortcut (macOS) | Action |
| :--- | :--- | :--- |
| `Shift + Enter` | `Shift + Enter` | Evaluate current cell and focus/create next cell |
| `Ctrl + Enter` | `Cmd + Enter` / `Ctrl + Enter` | Insert a new execution cell below |
| `Ctrl + Shift + Return` | `Cmd + Shift + Return` | Run all cells in worksheet |
| `Ctrl + M` | `Cmd + M` | Open Matrix Wizard dialog |
| `Ctrl + T` | `Cmd + T` | Toggle between Dark Slate and Academic Light theme |
| `Ctrl + S` | `Cmd + S` | Save worksheet to file (`.mw`) |
| `Ctrl + O` | `Cmd + O` | Open saved worksheet |
| `Ctrl + N` | `Cmd + N` | New blank worksheet session |
| `Ctrl + Space` / `Esc` | `Cmd + Space` / `Esc` | Trigger autocompletion popup |
| `F5` | `F5` | Toggle typing mode (2D Math / 1D Math / Nonexec / Text) |
| `Up / Down Arrow` | `Up / Down Arrow` | Navigate between cell editors / history |

---

## Project Structure

```
calculator/
├── main.py                     # Application entry point (High-DPI & taskbar configured)
├── run.py                      # Quick Python launcher script
├── run.bat                     # One-click launcher for Windows
├── run.sh                      # Universal launcher for macOS (Apple Silicon / Intel) & Linux
├── create_shortcut.sh          # macOS Application Bundle & Desktop shortcut generator
├── create_shortcut_windows.bat # Windows Desktop & Start Menu shortcut installer (bat)
├── create_shortcut_windows.ps1 # Windows shortcut creation script (PowerShell)
├── create_shortcut_linux.sh    # Linux Desktop Entry (.desktop) installer
├── requirements.txt            # Package dependencies
├── resources/                  # Application icons & visual assets
│   ├── AppIcon.icns            # macOS multi-resolution icon
│   ├── AppIcon.ico             # Windows multi-resolution icon
│   └── AppIcon.png             # Linux / Qt high-resolution icon (1024x1024)
├── cas_engine/                 # Symbolic math & evaluation engine core
│   ├── __init__.py
│   ├── engine.py               # Stateful evaluation engine & variable scope
│   ├── parser.py               # Math shorthand parser & syntax preprocessor
│   ├── formatter.py            # Typeset LaTeX & numeric evaluator
│   ├── plot_engine.py          # 2D coordinate calculation engine
│   └── embedded.py             # Embedded systems & MCU calculations
├── ui/                         # PyQt6 Desktop Interface
│   ├── __init__.py
│   ├── main_window.py          # Main QMainWindow with docks & menus
│   ├── worksheet_view.py       # Scrollable notebook container
│   ├── worksheet_cell.py       # Execution block widget [In n] / [Out n] & 2D Math
│   ├── math_renderer.py        # High-DPI LaTeX formula renderer
│   ├── command_bar.py          # Interactive bottom prompt & history
│   ├── palette_panel.py        # Left sidebar with math templates & symbols
│   ├── matrix_dialog.py        # Matrix creator & preset wizard
│   ├── plot_panel.py           # Embedded 2D dynamic graph panel
│   ├── syntax_highlighter.py   # Math/SymPy syntax highlighter
│   ├── thread_worker.py        # QThread background worker with clean shutdown
│   └── theme.py                # Slate Dark & Academic Light stylesheets
└── tests/                      # Comprehensive Unit & UI Test Suite
    ├── test_engine.py          # Math evaluation tests
    ├── test_parser.py          # Shorthand math parser tests
    ├── test_formatter.py       # LaTeX & numeric precision tests
    ├── test_subscripts.py      # Variable subscript tests
    ├── test_embedded.py        # Embedded systems & hardware calculations tests
    ├── test_ui.py              # Headless PyQt6 UI component tests
    └── test_ui_worksheet.py    # Interactive worksheet flow tests
```

---

## Running Tests

Run the full automated test suite:
```bash
python3 -m unittest discover -s tests
```

All 68 unit and UI tests run in headless-compatible mode and cleanly terminate all background calculation threads.

---

## Troubleshooting & FAQs

### `NameError: name 'Optional' is not defined`
If you encounter this error when launching on Windows, macOS, or Linux, ensure you are using the latest version of the repository. The typing annotation in `ui/worksheet_cell.py` imports `Optional` from the standard library `typing` module, compatible with Python 3.10 through 3.14+.

### `error: externally-managed-environment` (PEP 668)
If you see this error when installing via `pip` on Zorin OS, Ubuntu 23.04+, or Debian 12+, use `./run.sh`, which automatically provisions a virtual environment in `.venv`.
Alternatively, create and activate a virtual environment manually:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Linux: `qt.qpa.plugin: Could not load the Qt platform plugin "xcb"`
If you run on a headless or minimal Linux desktop, install the missing Qt XCB/Wayland dependencies:
- **Zorin OS / Ubuntu / Debian**:
  ```bash
  sudo apt install -y libxcb-cursor0 libxkbcommon-x11-0 libgl1 libegl1
  ```
- **Fedora**:
  ```bash
  sudo dnf install -y libxcb-cursor libxkbcommon-x11
  ```
- **Arch Linux**:
  ```bash
  sudo pacman -S libxcb xcb-util-cursor libxkbcommon
  ```

### Wayland vs X11 Display Issues (Zorin OS / Ubuntu)
Zorin OS uses Wayland by default. If your graphics driver or desktop environment causes visual glitches under Wayland, you can force Qt to use the X11 / XWayland backend:
```bash
QT_QPA_PLATFORM=xcb ./run.sh
```

### macOS Apple Silicon (M1 / M2 / M3 / M4) Architecture
`run.sh` and `create_shortcut.sh` automatically detect Apple Silicon architecture (`arm64`) and ensure that your native Homebrew Python (`/opt/homebrew/bin/python3`) or local virtual environment is executed natively without emulation overhead:
```bash
chmod +x run.sh create_shortcut.sh
./run.sh
```

### Windows Taskbar Icon & Grouping
When running on Windows via `python main.py` or `run.bat`, the application explicitly registers a Windows Application User Model ID (`SetCurrentProcessExplicitAppUserModelID`) so that OpenMath displays its own dedicated application icon in the Windows taskbar rather than grouping under the generic Python executable.

---

## License
MIT License. Open-source scientific desktop software.
