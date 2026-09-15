#!/usr/bin/env python3
"""
Utility script to bundle cas_engine and cas_bridge into web/cas_bundle.json
for single-request loading in the Pyodide Web Worker.
"""
import os
import json

def bundle_cas():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(base_dir, ".."))
    cas_engine_dir = os.path.join(project_root, "cas_engine")
    bridge_path = os.path.join(base_dir, "py", "cas_bridge.py")
    output_path = os.path.join(base_dir, "cas_bundle.json")

    bundle = {}

    # Read cas_engine files
    if os.path.isdir(cas_engine_dir):
        for fname in os.listdir(cas_engine_dir):
            if fname.endswith(".py"):
                fpath = os.path.join(cas_engine_dir, fname)
                with open(fpath, "r", encoding="utf-8") as f:
                    content = f.read()
                    if fname == "__init__.py":
                        content = '''"""CAS Engine Web Worker Entry"""
try:
    from .engine import CASEngine
    from .parser import MathParser, ParseResult
    from .formatter import MathFormatter, CASResult
    from .plot_engine import PlotEngine, PlotData, CurveData
    from .embedded import EmbeddedMath
    from .error_suggester import suggest_fix
    from .units import UNIT_FAMILIES, UNIT_LOOKUP
except ImportError:
    CASEngine = None

from .mw_importer import WorksheetIO
from .wheeler import decode_worksheet_image

__all__ = ['WorksheetIO', 'decode_worksheet_image', 'CASEngine']
'''
                    bundle[f"cas_engine/{fname}"] = content

    # Read cas_bridge.py
    if os.path.isfile(bridge_path):
        with open(bridge_path, "r", encoding="utf-8") as f:
            bundle["cas_bridge.py"] = f.read()

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(bundle, f)

    print(f"[+] Successfully bundled {len(bundle)} files into {output_path} ({os.path.getsize(output_path)} bytes)")

if __name__ == "__main__":
    bundle_cas()
