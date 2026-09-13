# Dependency-Checking Application Launcher Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a robust run launcher that verifies all required dependencies (`PyQt6`, `sympy`, `matplotlib`, `numpy`) and Python version (>= 3.10) are installed, automatically installs any missing dependencies via pip, and then launches the CAS Calculator app.

**Architecture:** A shared dependency verification mechanism is implemented in `run.py` and native pre-flight checks are added to `run.bat` (Windows) and `run.sh` (macOS/Linux). When packages are missing, the scripts install them from `requirements.txt` before launching `main.py`. On subsequent launches, the verification takes < 100ms.

**Tech Stack:** Python 3.10+, Windows Batch (`run.bat`), Bash (`run.sh`), `pip`, `unittest`.

---

### Task 1: Add Unit Tests & Implementation for Dependency Verification in `run.py`

**Files:**
- Create: `tests/test_launcher.py`
- Modify: `run.py`

- [ ] **Step 1: Write the unit test for launcher dependency checking**

```python
# tests/test_launcher.py
import unittest
from unittest.mock import patch, MagicMock
import sys
import run

class TestLauncher(unittest.TestCase):
    def test_check_dependencies_all_present(self):
        # When all dependencies exist, check_dependencies returns True
        with patch.dict(sys.modules, {
            'PyQt6': MagicMock(),
            'sympy': MagicMock(),
            'matplotlib': MagicMock(),
            'numpy': MagicMock()
        }):
            self.assertTrue(run.check_dependencies())

    def test_check_dependencies_missing(self):
        # When any dependency is missing, check_dependencies returns False
        with patch('builtins.__import__', side_effect=ImportError("No module named 'PyQt6'")):
            self.assertFalse(run.check_dependencies())

    @patch('subprocess.run')
    def test_install_dependencies_invokes_pip(self, mock_subprocess):
        mock_subprocess.return_value = MagicMock(returncode=0)
        success = run.install_dependencies()
        self.assertTrue(success)
        mock_subprocess.assert_called_once()
        args = mock_subprocess.call_args[0][0]
        self.assertEqual(args[1:4], ["-m", "pip", "install"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests/test_launcher.py -v`
Expected: FAIL with `AttributeError: module 'run' has no attribute 'check_dependencies'`

- [ ] **Step 3: Implement dependency checking and auto-installation in `run.py`**

```python
#!/usr/bin/env python3
"""
Convenient launcher for the OpenMath CAS Calculator application.
Verifies Python version and dependencies before launching.
"""

import sys
import os
import subprocess

REQUIRED_PACKAGES = ["PyQt6", "sympy", "matplotlib", "numpy"]
MIN_PYTHON_VERSION = (3, 10)


def check_python_version() -> bool:
    return sys.version_info >= MIN_PYTHON_VERSION


def check_dependencies() -> bool:
    for pkg in REQUIRED_PACKAGES:
        try:
            __import__(pkg)
        except ImportError:
            return False
    return True


def install_dependencies(requirements_file: str = "requirements.txt") -> bool:
    req_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), requirements_file)
    print("[INFO] Missing dependencies detected. Installing required packages from requirements.txt...")
    cmd = [sys.executable, "-m", "pip", "install", "-r", req_path]
    res = subprocess.run(cmd)
    return res.returncode == 0


def ensure_environment() -> bool:
    if not check_python_version():
        print(
            f"[ERROR] Python {MIN_PYTHON_VERSION[0]}.{MIN_PYTHON_VERSION[1]}+ is required. "
            f"Current version is {sys.version}.",
            file=sys.stderr,
        )
        return False

    if not check_dependencies():
        if not install_dependencies():
            print(
                "[ERROR] Failed to install required packages. "
                "Please run 'pip install -r requirements.txt' manually.",
                file=sys.stderr,
            )
            return False
        print("[SUCCESS] Dependencies installed successfully!")
    return True


if __name__ == "__main__":
    if not ensure_environment():
        sys.exit(1)
    from main import main
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests/test_launcher.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_launcher.py run.py
git commit -m "feat: add dependency checking and auto-install to run.py"
```

---

### Task 2: Update `run.bat` for Windows Launcher

**Files:**
- Modify: `run.bat`

- [ ] **Step 1: Update `run.bat` with pre-flight check and auto-install**

Update `run.bat` to detect the python binary, perform the pre-flight import check, run `pip install` on failure, and launch `main.py` forwarding all arguments:

```bat
@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"

REM 1. Detect Python binary
set "PYTHON_BIN="

if exist ".venv\Scripts\python.exe" (
    set "PYTHON_BIN=.venv\Scripts\python.exe"
) else if exist "venv\Scripts\python.exe" (
    set "PYTHON_BIN=venv\Scripts\python.exe"
) else (
    where python >nul 2>nul
    if !ERRORLEVEL! equ 0 (
        set "PYTHON_BIN=python"
    ) else (
        where py >nul 2>nul
        if !ERRORLEVEL! equ 0 (
            set "PYTHON_BIN=py -3"
        ) else (
            where python3 >nul 2>nul
            if !ERRORLEVEL! equ 0 (
                set "PYTHON_BIN=python3"
            )
        )
    )
)

if not defined PYTHON_BIN (
    echo [ERROR] Python 3 was not found in your system PATH.
    echo Please install Python 3.10+ from https://www.python.org or the Microsoft Store.
    pause
    exit /b 1
)

REM 2. Check dependencies (fast import check)
%PYTHON_BIN% -c "import PyQt6, sympy, matplotlib, numpy" >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [INFO] Missing required packages detected.
    echo Installing dependencies from requirements.txt...
    %PYTHON_BIN% -m pip install -r "%~dp0requirements.txt"
    if !ERRORLEVEL! neq 0 (
        echo [ERROR] Failed to install required packages.
        echo Please check your internet connection or run:
        echo   pip install -r requirements.txt
        pause
        exit /b 1
    )
    echo [SUCCESS] Dependencies installed successfully!
)

REM 3. Launch Application
%PYTHON_BIN% main.py %*
exit /b %ERRORLEVEL%
```

- [ ] **Step 2: Test `run.bat` syntax and error handling**

Run: `cmd.exe /c "run.bat --help"` (or verify with dry run / check script)
Expected: Identifies Python and starts checking/installing requirements.

- [ ] **Step 3: Commit**

```bash
git add run.bat
git commit -m "feat: add dependency verification and auto-install to run.bat"
```

---

### Task 3: Update `run.sh` for macOS / Linux Launcher

**Files:**
- Modify: `run.sh`

- [ ] **Step 1: Update `run.sh` with dependency verification and auto-install**

Update `run.sh` so macOS and Linux users have matching pre-flight checks:

```bash
# Check dependencies (fast import check)
if ! "$PYTHON_BIN" -c "import PyQt6, sympy, matplotlib, numpy" >/dev/null 2>&1; then
    echo "[INFO] Missing required packages detected."
    echo "Installing dependencies from requirements.txt..."
    if ! "$PYTHON_BIN" -m pip install -r "$SCRIPT_DIR/requirements.txt"; then
        echo "[ERROR] Failed to install required packages." >&2
        echo "Please run: pip install -r requirements.txt" >&2
        exit 1
    fi
    echo "[SUCCESS] Dependencies installed successfully!"
fi
```

- [ ] **Step 2: Verify `run.sh` syntax**

Run: `bash -n run.sh` (or check syntax via bash if available)

- [ ] **Step 3: Commit**

```bash
git add run.sh
git commit -m "feat: add dependency verification and auto-install to run.sh"
```

---

### Task 4: Full Verification and Installation

**Files:**
- Run: `run.bat` / `python run.py` / `python -m unittest discover -s tests`

- [ ] **Step 1: Execute `run.py` to trigger installation and verify requirements install cleanly**

Run: `python run.py` or install requirements via `pip install -r requirements.txt`
Expected: Dependencies (`PyQt6`, `sympy`, `matplotlib`, `numpy`) install successfully.

- [ ] **Step 2: Run full test suite**

Run: `python -m unittest discover -s tests`
Expected: All unit & UI tests pass (68+ tests).

- [ ] **Step 3: Verify fast path (< 100ms)**

Run: `python -c "import time, run; t0=time.time(); run.check_dependencies(); print(f'Elapsed: {time.time()-t0:.4f}s')"`
Expected: Elapsed time is < 0.1s.

- [ ] **Step 4: Final commit and documentation updates if needed**

```bash
git add -A
git commit -m "chore: verify full test suite passes with auto-installer"
```
