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


def start_app():
    from main import main
    main()


if __name__ == "__main__":
    if not ensure_environment():
        sys.exit(1)
    start_app()
