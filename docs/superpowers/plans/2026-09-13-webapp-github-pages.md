# OpenMath WebApp & GitHub Pages Hosting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a fully client-side, phone-responsive and desktop-optimized WebApp version of OpenMath powered by Pyodide (Python/SymPy WebAssembly), KaTeX, and Chart.js, deployed seamlessly to GitHub Pages via an automated GitHub Actions workflow.

**Architecture:** A zero-toolchain modular web architecture in `web/`. A background Web Worker runs Pyodide WebAssembly with SymPy and NumPy, loading OpenMath's `cas_engine` into memory. The frontend features a reactive worksheet with high-DPI KaTeX math rendering, collapsible desktop palettes, an interactive Matrix Wizard, 2D plotting via HTML5 Canvas, and an ergonomic mobile math dock with quick symbols and an expandable tabbed touch keypad.

**Tech Stack:** JavaScript (ES6+ Modules, Web Workers), HTML5, CSS3 (Responsive Design Tokens), Pyodide (WebAssembly Python 3.11+), SymPy, NumPy, KaTeX, Chart.js, GitHub Actions (`actions/deploy-pages@v4`).

---

### Task 1: Dedicated Feature Branch & Directory Scaffold

**Files:**
- Create: `web/index.html` (initial placeholder)
- Create: `web/manifest.json`
- Directory: `web/css/`, `web/js/`, `web/py/`

- [ ] **Step 1: Create and switch to feature branch**
```bash
git checkout -b feature/webapp-github-pages
```

- [ ] **Step 2: Create directory tree**
```powershell
New-Item -ItemType Directory -Force -Path "web\css", "web\js", "web\py", ".github\workflows"
```

- [ ] **Step 3: Create web app manifest `web/manifest.json`**
```json
{
  "name": "OpenMath Web CAS Calculator",
  "short_name": "OpenMath",
  "description": "Symbolic mathematical calculator, CAS engine, and interactive worksheet",
  "start_url": "./index.html",
  "display": "standalone",
  "background_color": "#1e222b",
  "theme_color": "#38bdf8",
  "icons": [
    {
      "src": "../resources/AppIcon.png",
      "sizes": "512x512",
      "type": "image/png"
    }
  ]
}
```

- [ ] **Step 4: Commit initial structure**
```bash
git add web/manifest.json
git commit -m "feat(web): initialize web directory scaffold and PWA manifest"
```

---

### Task 2: Python CAS Bridge (`web/py/cas_bridge.py`)

**Files:**
- Create: `web/py/cas_bridge.py`
- Test: `tests/test_cas_bridge.py`

- [ ] **Step 1: Write the failing test `tests/test_cas_bridge.py`**
```python
import pytest
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from web.py.cas_bridge import evaluate_expression, get_system_info

def test_basic_algebra():
    res = evaluate_expression("expand((x+1)^3)", precision=6)
    assert res["error"] is None
    assert "x^{3}" in res["exact_latex"] or "x**3" in res["exact_text"]

def test_calculus():
    res = evaluate_expression("diff(sin(x)*cos(x), x)", precision=6)
    assert res["error"] is None
    assert "cos" in res["exact_latex"]

def test_syntax_error_handling():
    res = evaluate_expression("integrate(sin(x", precision=6)
    assert res["error"] is not None
    assert "syntax" in res["error"].lower() or "bracket" in res["error"].lower() or "error" in res["error"].lower()

def test_embedded_math():
    res = evaluate_expression("to_bin(42, 8)", precision=6)
    assert res["error"] is None
    assert "00101010" in res["exact_text"] or "0b" in res["exact_text"]

def test_plot_generation():
    res = evaluate_expression("plot(sin(x), (x, -5, 5))", precision=6)
    assert res["error"] is None
    assert res["is_plot"] is True
    assert "curves" in res["plot_data"]
```

- [ ] **Step 2: Run test to verify it fails**
```bash
python -m pytest tests/test_cas_bridge.py -v
```
Expected: FAIL (ModuleNotFoundError: No module named 'web.py.cas_bridge')

- [ ] **Step 3: Implement `web/py/cas_bridge.py`**
```python
"""
Bridge between Pyodide WebAssembly worker and OpenMath cas_engine.
Serializes CASResult into JSON-compatible dictionaries.
"""
import sys
import os
import traceback
import json

# Ensure cas_engine is accessible on path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from cas_engine.engine import CASEngine
from cas_engine.plot_engine import PlotData

_engine = None

def get_engine():
    global _engine
    if _engine is None:
        _engine = CASEngine()
    return _engine

def evaluate_expression(expr: str, precision: int = 6) -> dict:
    """Evaluate mathematical expression and return JSON-serializable dictionary."""
    engine = get_engine()
    try:
        res = engine.evaluate(expr, precision=precision)
        plot_dict = None
        if res.is_plot and res.plot_data:
            p_data: PlotData = res.plot_data
            curves = []
            for c in getattr(p_data, 'curves', []):
                curves.append({
                    "x": list(float(v) for v in c.x_vals if v is not None),
                    "y": list(float(v) for v in c.y_vals if v is not None),
                    "label": c.label,
                    "color": getattr(c, 'color', None)
                })
            regions = []
            for r in getattr(p_data, 'regions', []):
                regions.append({
                    "x": list(float(v) for v in r.x_vals if v is not None),
                    "y_min": list(float(v) for v in r.y_min_vals if v is not None),
                    "y_max": list(float(v) for v in r.y_max_vals if v is not None),
                    "color": r.color,
                    "alpha": r.alpha,
                    "label": r.label
                })
            plot_dict = {
                "title": p_data.title or "",
                "x_label": p_data.x_label or "x",
                "y_label": p_data.y_label or "y",
                "curves": curves,
                "regions": regions
            }

        return {
            "exact_latex": res.exact_latex or "",
            "numeric_latex": res.numeric_latex or "",
            "exact_text": res.exact_text or "",
            "numeric_text": res.numeric_text or "",
            "python_code": res.python_code or "",
            "is_numeric_available": res.is_numeric_available,
            "is_plot": res.is_plot,
            "plot_data": plot_dict,
            "execution_time_ms": round(res.execution_time_ms, 2),
            "suppress_output": getattr(res, 'suppress_output', False),
            "error": None
        }
    except Exception as e:
        return {
            "exact_latex": "",
            "numeric_latex": "",
            "exact_text": "",
            "numeric_text": "",
            "python_code": "",
            "is_numeric_available": False,
            "is_plot": False,
            "plot_data": None,
            "execution_time_ms": 0.0,
            "suppress_output": False,
            "error": str(e)
        }

def get_system_info():
    import sympy
    import numpy
    return {
        "sympy_version": sympy.__version__,
        "numpy_version": numpy.__version__,
        "python_version": sys.version
    }
```

- [ ] **Step 4: Run test to verify it passes**
```bash
python -m pytest tests/test_cas_bridge.py -v
```
Expected: PASS (5/5 tests passed)

- [ ] **Step 5: Commit bridge implementation**
```bash
git add web/py/cas_bridge.py tests/test_cas_bridge.py
git commit -m "feat(web): add Python cas_bridge and test suite for Pyodide worker"
```

---

### Task 3: Pyodide Web Worker (`web/js/cas-worker.js`)

**Files:**
- Create: `web/js/cas-worker.js`

- [ ] **Step 1: Write `web/js/cas-worker.js`**
Handle asynchronous initialization, mounting pure Python modules of `cas_engine/`, handling `EVALUATE`, `RESET`, and `WHOS` commands with error resilience.

- [ ] **Step 2: Commit worker implementation**
```bash
git add web/js/cas-worker.js
git commit -m "feat(web): implement Pyodide Web Worker for background math execution"
```

---

### Task 4: Responsive HTML5 Canvas & Plot Engine (`web/js/plotter.js`)

**Files:**
- Create: `web/js/plotter.js`

- [ ] **Step 1: Write `web/js/plotter.js`**
Supports dynamic 2D plotting of multi-curve function expressions, polar coordinates, and filled linear inequality regions (`polygonOmraade`, `LPplot`). Includes auto-scaling, grid lines, axis labels, legends, and touch-responsive inspection.

- [ ] **Step 2: Commit plotter module**
```bash
git add web/js/plotter.js
git commit -m "feat(web): add responsive 2D canvas plotting engine for functions and regions"
```

---

### Task 5: Math Palettes & Interactive Matrix Wizard (`web/js/palette.js`)

**Files:**
- Create: `web/js/palette.js`

- [ ] **Step 1: Write `web/js/palette.js`**
- Expression templates ($\int, d/dx, \sqrt{}, \dots$)
- Categorized accordion drawers: Algebra, Calculus, Linear Algebra, Greek/Symbols, Embedded & Hardware
- Interactive Modal Matrix Wizard: visual $M \times N$ grid configuration with presets (Identity, Zeros, Ones, Custom) outputting formatted matrix expressions (e.g. `Matrix([[1, 0], [0, 1]])`).

- [ ] **Step 2: Commit palette module**
```bash
git add web/js/palette.js
git commit -m "feat(web): implement math palettes, symbol ribbons, and Matrix Wizard dialog"
```

---

### Task 6: Worksheet & KaTeX Math Renderer (`web/js/worksheet.js`)

**Files:**
- Create: `web/js/worksheet.js`

- [ ] **Step 1: Write `web/js/worksheet.js`**
- Stacked `[In n]` and `[Out n]` calculation cells.
- Exact vs. Numeric evaluation switch per cell and globally.
- Per-cell precision configuration.
- Real-time LaTeX typesetting using KaTeX with retina high-DPI scaling.
- One-click copy buttons (Copy LaTeX, Copy Plain Text, Copy Python).
- Worksheet export (LaTeX document, Markdown, JSON, plain text).

- [ ] **Step 2: Commit worksheet module**
```bash
git add web/js/worksheet.js
git commit -m "feat(web): add interactive worksheet cell manager and KaTeX renderer"
```

---

### Task 7: Mobile Math Dock & Responsive Controls (`web/js/mobile-dock.js`)

**Files:**
- Create: `web/js/mobile-dock.js`

- [ ] **Step 1: Write `web/js/mobile-dock.js`**
- Floating bottom math dock optimized for iPhone/Android touch screens.
- Horizontal scrollable quick-symbol ribbon (`^`, `√`, `x`, `y`, `π`, `:=`, `(`, `)`, `+`, `-`, `*`, `/`).
- Expandable bottom drawer with categorized tabs:
  - `123`: Numbers and basic arithmetic.
  - `fx`: Algebraic functions (`factor`, `expand`, `solve`, `simplify`).
  - `calc`: Calculus operations ($d/dx, \int, \lim, \sum$).
  - `matrix`: Matrix commands and determinants.
  - `sym`: Greek alphabet and constants.
  - `embed`: Hardware math (`to_bin`, `to_hex`, `adc_volt`, `rc_cutoff`).
- Touch-friendly 44px+ buttons with haptic feedback (where supported).

- [ ] **Step 2: Commit mobile dock module**
```bash
git add web/js/mobile-dock.js
git commit -m "feat(web): implement phone-responsive touch math keyboard dock"
```

---

### Task 8: Main App Coordinator & HTML Layout (`web/index.html`, `web/js/app.js`)

**Files:**
- Create: `web/index.html`
- Create: `web/js/app.js`

- [ ] **Step 1: Write `web/index.html`**
Full desktop and mobile HTML5 layout including navbar, palette sidebar, worksheet area, status bar, matrix dialog modal, and mobile dock.

- [ ] **Step 2: Write `web/js/app.js`**
Coordinates worker initialization, worksheet events, theme switching (Slate Dark / Academic Light), keyboard shortcuts (`Shift+Enter` to run, `Ctrl+Enter`), export handlers, and loading overlay.

- [ ] **Step 3: Commit application entry point**
```bash
git add web/index.html web/js/app.js
git commit -m "feat(web): add main application shell and coordinator logic"
```

---

### Task 9: CSS Design Tokens & Responsive Layouts (`web/css/`)

**Files:**
- Create: `web/css/style.css`
- Create: `web/css/desktop.css`
- Create: `web/css/mobile.css`

- [ ] **Step 1: Write `web/css/style.css`** (Design tokens, Slate Dark & Academic Light themes, typography, buttons, inputs, modals).
- [ ] **Step 2: Write `web/css/desktop.css`** (Multi-column layout, sidebar panels, toolbar menus).
- [ ] **Step 3: Write `web/css/mobile.css`** (Full-width cards, touch targets, bottom dock drawer animations, phone breakpoints).
- [ ] **Step 4: Commit CSS styles**
```bash
git add web/css/style.css web/css/desktop.css web/css/mobile.css
git commit -m "feat(web): add responsive CSS styling for desktop and phone devices"
```

---

### Task 10: Local Web Runner (`run_web.py`)

**Files:**
- Create: `run_web.py`

- [ ] **Step 1: Write `run_web.py`**
Simple, zero-dependency script to launch local web server on port 8000 and automatically open the default browser to `http://localhost:8000/web/`.

- [ ] **Step 2: Commit runner script**
```bash
git add run_web.py
git commit -m "feat(web): add run_web.py for one-command local testing"
```

---

### Task 11: GitHub Pages Deployment Workflow (`.github/workflows/pages.yml`)

**Files:**
- Create: `.github/workflows/pages.yml`

- [ ] **Step 1: Write `.github/workflows/pages.yml`**
Configured with GitHub's modern `deploy-pages` action:
- Copies `cas_engine/` pure Python files into `web/cas_engine/` so Pyodide can load them statically.
- Configures GitHub Pages.
- Uploads and deploys static site artifact on every push to `main`.

- [ ] **Step 2: Commit workflow**
```bash
git add .github/workflows/pages.yml
git commit -m "ci: add GitHub Actions workflow for automated GitHub Pages deployment"
```

---

### Task 12: Documentation & README Updates

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update `README.md`**
Add:
- WebApp status badge.
- Link to GitHub Pages deployment.
- Instructions for running the web version locally (`python run_web.py`).
- Mobile-responsive features summary.

- [ ] **Step 2: Commit README updates**
```bash
git add README.md
git commit -m "docs: add OpenMath WebApp details, live site link, and usage instructions"
```

---

### Task 13: Full Verification & PR Readiness

- [ ] **Step 1: Run all tests**
```bash
python -m pytest tests/ -v
```
Expected: All tests pass.

- [ ] **Step 2: Run local web server and verify files serve with HTTP 200**
Verify all HTML, JS, CSS, and manifest assets are cleanly reachable without 404s.

- [ ] **Step 3: Check git status and branch cleanliness**
```bash
git status
git log -n 10 --oneline
```
Verify all commits are clean, well-formatted, and ready for PR creation to `J2KJonas/OpenMath:main`.
