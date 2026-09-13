# OpenMath WebApp & GitHub Pages Hosting Specification

- **Date**: 2026-09-13
- **Author**: Antigravity Assistant & elomarjc
- **Target Repository**: [OpenMath (https://github.com/J2KJonas/OpenMath)](https://github.com/J2KJonas/OpenMath)
- **Status**: Approved by User

---

## 1. Executive Summary
OpenMath is a desktop mathematical CAS calculator built with Python, PyQt6, SymPy, Matplotlib, and NumPy. This specification outlines the architecture, user experience, implementation details, and deployment automation to add a fully functional, phone-responsive and desktop-optimized WebApp version of OpenMath hosted directly on **GitHub Pages** with zero hosting costs and zero external server dependencies.

---

## 2. Goals & Success Criteria

1. **Client-Side CAS Runtime**: Run SymPy, NumPy, and OpenMath's complete `cas_engine/` within the browser via **Pyodide (WebAssembly)** inside a dedicated Web Worker.
2. **Identical Math Capabilities**: Support full symbolic operations (algebra, calculus, differential equations, linear algebra matrices, embedded hardware functions, and 2D plotting).
3. **High-DPI Math Rendering**: High-performance formula rendering matching desktop MathText using **KaTeX**.
4. **Desktop & Phone Responsive UX**:
   - Desktop: Multi-column worksheet layout with collapsible palettes (Templates, Algebra, Calculus, Linear Algebra, Embedded, Greek symbols), Matrix Wizard, exact/numeric toggles, and cell controls.
   - Mobile/Phone: Responsive full-width worksheet cards with touch-friendly controls, quick symbol ribbon, and an expandable bottom math keyboard dock with categorized tabs.
5. **Static GitHub Pages Deployment**: Fully automated via `.github/workflows/pages.yml` deploying from the `web/` directory on pushes to `main`.
6. **Clean Git Branching & PR Ready**: Implemented on a dedicated feature branch with clean commits, ready for a pull request to `J2KJonas/OpenMath:main`.

---

## 3. Architecture & File Structure

```
OpenMath/
├── .github/
│   └── workflows/
│       ├── release.yml               # Existing desktop PyInstaller releases
│       └── pages.yml                 # GitHub Pages deployment workflow
├── cas_engine/                       # Existing CAS engine (reused directly)
│   ├── engine.py
│   ├── parser.py
│   ├── formatter.py
│   ├── plot_engine.py
│   ├── embedded.py
│   ├── units.py
│   └── ...
├── web/                              # Complete standalone WebApp
│   ├── index.html                    # Application layout and entry point
│   ├── manifest.json                 # Web App Manifest (PWA support)
│   ├── css/
│   │   ├── style.css                 # Base theme, typography, color palette tokens
│   │   ├── desktop.css               # Desktop sidebar, toolbars, worksheet view
│   │   └── mobile.css                # Mobile bottom dock, sheets, responsive cards
│   ├── js/
│   │   ├── app.js                    # UI coordinator, theme manager, shortcuts
│   │   ├── cas-worker.js             # Pyodide WebAssembly worker runner
│   │   ├── worksheet.js              # Calculation cells, history, evaluation queue
│   │   ├── palette.js                # Desktop math palettes & matrix wizard
│   │   ├── mobile-dock.js            # Mobile quick symbol ribbon & tabbed keypad
│   │   └── plotter.js                # 2D curve and polygon area canvas renderer
│   ├── py/
│   │   └── cas_bridge.py             # Python interface connecting Pyodide to cas_engine
│   └── vendor/                       # KaTeX & Chart.js assets / CDN fallbacks
├── run_web.py                        # Local development runner helper script
└── README.md                         # Updated with WebApp documentation & live link
```

---

## 4. Component Details

### 4.1. Web Worker & CAS Engine (`cas-worker.js` & `cas_bridge.py`)
- **Web Worker**: Initializes Pyodide via CDN (`v0.26.4`). Loads `sympy` and `numpy` packages.
- **Engine Mounting**: Loads the `cas_engine` Python modules into Pyodide's virtual filesystem (`/cas_engine/`).
- **Communication Protocol**:
  - Main thread posts `{ type: 'EVALUATE', id: cellId, expr: inputStr, precision: 6 }`.
  - Worker evaluates `cas_bridge.evaluate(expr, precision)` and responds with:
    ```json
    {
      "id": "cell_1",
      "exact_latex": "- \\sin^{2}{\\left(x \\right)} + \\cos^{2}{\\left(x \\right)}",
      "numeric_latex": "- \\sin^{2}{\\left(x \\right)} + \\cos^{2}{\\left(x \\right)}",
      "exact_text": "-sin(x)**2 + cos(x)**2",
      "numeric_text": "-sin(x)**2 + cos(x)**2",
      "is_plot": false,
      "plot_data": null,
      "execution_time_ms": 12.4,
      "error": null
    }
    ```
  - Worker catches Python exceptions cleanly and formats syntax/evaluation error messages without crashing.

### 4.2. Responsive User Interface

#### Themes
- **Slate Dark** (Default):
  - Background: `#1e222b`
  - Surface/Cards: `#282c37`
  - Borders: `#3a4150`
  - Primary Accent: `#38bdf8` (Cyan)
  - Text: `#f1f5f9`
- **Academic Light**:
  - Background: `#f8fafc`
  - Surface/Cards: `#ffffff`
  - Borders: `#e2e8f0`
  - Primary Accent: `#2563eb` (Blue)
  - Text: `#0f172a`

#### Desktop Mode (Screen Width >= 768px)
- Fixed top navigation with OpenMath branding, Exact/Numeric mode switch, digit precision selector (2 to 50), Clear Worksheet, Export (LaTeX, Markdown, Python, JSON), and Dark/Light theme toggle.
- Left-hand collapsible sidebar with accordion palettes:
  - **Templates**: $\frac{a}{b}$, $x^y$, $\sqrt{x}$, $\sqrt[n]{x}$, $|x|$, $\int$, $\int_a^b$, $\frac{d}{dx}$, $\lim$, $\sum$, $\prod$.
  - **Algebra**: `expand()`, `factor()`, `simplify()`, `solve()`, `apart()`, `together()`, `trigsimp()`.
  - **Calculus**: `diff()`, `integrate()`, `limit()`, `series()`, `dsolve()`.
  - **Linear Algebra**: Matrix Wizard button, Determinant, Inverse, Eigenvalues, Eigenvectors, RREF, Nullspace, Transpose.
  - **Symbols**: Greek lowercase/uppercase alphabet, mathematical constants ($\pi, e, \infty, i$).
  - **Embedded & Electronics**: `to_bin`, `to_hex`, `twos_comp`, `to_q`, `ubrr_calc`, `timer_calc`, `adc_volt`, `rc_cutoff`, `crc8`, etc.
- Central worksheet container displaying stacked `[In n]` input editors and `[Out n]` rendered KaTeX formula outputs.

#### Mobile / Phone Mode (Screen Width < 768px)
- Mobile header with compact controls (Menu hamburger, Exact/Numeric toggle, Theme button).
- Full-width scrollable worksheet with minimum 44px tap targets for easy cell operations (Run, Copy, Delete).
- Fixed bottom math dock:
  1. Input container with auto-expanding math input and one-tap `[ ⏎ ]` execution button.
  2. Scrollable quick-symbol row (`x`, `y`, `^`, `√`, `(`, `)`, `+`, `-`, `*`, `/`, `:=`, `π`).
  3. Expandable bottom drawer providing a full mobile math keyboard categorized into:
     - `123`: Numbers, common operations, variables ($x, y, z, t$).
     - `fx`: Algebraic functions and solve commands.
     - `calc`: Calculus operations ($d/dx, \int, \lim, \sum$).
     - `matrix`: Matrix generators, determinants, inverse.
     - `sym`: Full Greek letters and mathematical constants.
     - `embed`: Hardware calculation functions.

### 4.3. Plotting System (`plotter.js`)
- Supports single-function, multi-curve, parametric ($x(t), y(t)$), polar ($r(\theta)$), and polygon region inequalities (`polygonOmråde`, `LPplot`).
- Renders directly onto responsive HTML5 Canvas elements with responsive zoom and pan touch gestures.

### 4.4. GitHub Pages Deployment (`.github/workflows/pages.yml`)
- Trigger: `push` on branch `main` (and `workflow_dispatch`).
- Permissions: `pages: write`, `id-token: write`.
- Actions:
  - Check out repository.
  - Setup Pages (`actions/configure-pages@v5`).
  - Bundle `web/` and copy pure `cas_engine/` files into `web/cas_engine/`.
  - Upload Pages artifact (`actions/upload-pages-artifact@v3`).
  - Deploy to GitHub Pages (`actions/deploy-pages@v4`).

---

## 5. Implementation Steps
1. Create dedicated feature branch `feature/webapp-github-pages`.
2. Implement `web/` application shell, CSS styles (desktop + mobile responsive dock).
3. Implement `web/js/` modules: `app.js`, `worksheet.js`, `palette.js`, `mobile-dock.js`, `plotter.js`.
4. Implement `web/js/cas-worker.js` and `web/py/cas_bridge.py` linking directly to `cas_engine`.
5. Implement `.github/workflows/pages.yml` with automated packaging and deployment.
6. Create `run_web.py` for effortless local testing.
7. Update `README.md` with WebApp instructions, live site details, and badges.
8. Validate locally via browser testing and headless checks.
9. Commit all changes cleanly with descriptive git messages.
