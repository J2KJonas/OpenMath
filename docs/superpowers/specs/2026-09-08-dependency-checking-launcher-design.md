# Dependency-Checking Application Launcher Design

**Date**: 2026-09-08  
**Status**: Approved  
**Target Platform**: Windows (Primary: `run.bat`), Cross-Platform (`run.py`, `run.sh`)  

## 1. Motivation & Problem Statement
When running the CAS Calculator application on a fresh installation or without all virtual environment packages installed, attempting to launch directly via `run.bat` or `python main.py` causes an immediate crash with `ModuleNotFoundError` (e.g., `No module named 'PyQt6'`). Users must currently diagnose the missing packages manually and run `pip install -r requirements.txt`.

The goal is to enhance the launch scripts so they automatically detect missing dependencies, install them via `pip`, and launch the app seamlessly, while remaining fast (< 100ms) on subsequent launches when all requirements are satisfied.

## 2. Goals & Non-Goals
### Goals
- Automatically verify whether all required packages (`PyQt6`, `sympy`, `matplotlib`, `numpy`) are installed before attempting to start the GUI.
- Automatically execute `pip install -r requirements.txt` if any required package is missing.
- Launch `main.py` immediately without noticeable overhead when dependencies are already installed.
- Support Windows double-clicking via `run.bat` (and Windows desktop shortcuts) with a persistent console if an error occurs.
- Update `run.py` and `run.sh` to provide matching behavior for terminal and cross-platform users.
- Pass through any CLI arguments (such as `.cas` file paths) to `main.py`.

### Non-Goals
- Replacing `pip` with complex environment managers (Conda, Poetry, etc.).
- Modifying the core application logic in `main.py` or `cas_engine`.

## 3. Architecture & Flow

```
[Start Launcher] (run.bat / run.py / run.sh)
        │
        ▼
[1. Resolve Python Binary] (.venv -> venv -> python / py -3 / python3)
        │
   Found? ──No──► Display error: "Python 3.10+ required" ──► Pause / Exit 1
        │ Yes
        ▼
[2. Check Requirements]
   Check imports: PyQt6, sympy, matplotlib, numpy
        │
   All present?
   ├── Yes ──► (Fast Path)
   └── No  ──► [3. Auto-Install Dependencies]
                    Display: "[INFO] Missing dependencies detected. Installing..."
                    Run: <python> -m pip install -r requirements.txt
                    Success?
                    ├── No  ──► Display error: "[ERROR] Failed to install packages" ──► Pause / Exit 1
                    └── Yes ──► Display: "[SUCCESS] All dependencies ready!"
                                  │
                                  ▼
                     [4. Launch Application]
                     Run: <python> main.py [args...]
```

## 4. Detailed Component Design

### 4.1 `run.bat` (Windows Launcher)
1. **Python Detection**:
   - Check `.venv\Scripts\python.exe`
   - Check `venv\Scripts\python.exe`
   - Check `python` in PATH
   - Check `py -3`
   - Check `python3`
2. **Pre-flight Check**:
   - Executes a 1-line Python check:
     `%PYTHON_CMD% -c "import PyQt6, sympy, matplotlib, numpy" >nul 2>nul`
   - If errorlevel is 0: Proceed directly to launch.
   - If errorlevel is non-zero:
     - Echo `[INFO] Missing required packages. Installing from requirements.txt...`
     - `%PYTHON_CMD% -m pip install -r requirements.txt`
     - If errorlevel is non-zero:
       - Echo `[ERROR] Package installation failed.`
       - Echo `Please check your internet connection or run: pip install -r requirements.txt`
       - Pause and exit with code 1.
3. **Execution**:
   - `%PYTHON_CMD% main.py %*`
   - Pass exit code.

### 4.2 `run.py` (Python Launcher)
1. Performs Python version check (`sys.version_info >= (3, 10)`).
2. Tries to import `PyQt6`, `sympy`, `matplotlib`, `numpy`.
3. If `ImportError` or `ModuleNotFoundError`:
   - Prints info message.
   - Calls `subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], check=True)`.
4. Imports and runs `main()` from `main.py` with `sys.argv`.

### 4.3 `run.sh` (macOS / Linux Launcher)
1. Detects `python3` binary.
2. Checks imports via `$PYTHON_BIN -c "import PyQt6, sympy, matplotlib, numpy"`.
3. If non-zero, executes `$PYTHON_BIN -m pip install -r requirements.txt`.
4. Executes `$PYTHON_BIN main.py "$@"`.

## 5. Error Handling & Edge Cases
- **No Internet during first run**: If `pip install` fails, prints a clear error message and halts with a non-zero exit status, pausing in `run.bat` so the user can read the error before the console closes.
- **Python < 3.10**: Notifies user that Python 3.10 or higher is required.
- **File argument forwarding**: Ensures `%*`, `"$@"`, and `sys.argv` pass all flags or document paths down to `main.py`.

## 6. Verification Plan
1. **Trigger Auto-Install**:
   - Current state: `PyQt6` is not installed in global environment.
   - Run verification via the launcher logic and confirm packages install and verify successfully.
2. **Fast-Path Verification**:
   - Run the launcher a second time after packages are installed; confirm execution time is negligible and no `pip` network calls are made.
3. **Automated Test Suite**:
   - Run `python -m unittest discover -s tests` to ensure all 68 unit & UI tests continue to pass.
