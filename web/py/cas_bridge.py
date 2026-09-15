"""
Bridge between Pyodide WebAssembly worker and OpenMath cas_engine.
Serializes CASResult into JSON-compatible dictionaries.
"""
import sys
import os
import io
import zipfile
import base64
import traceback
import json
import uuid

# Ensure cas_engine is accessible on path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from cas_engine.engine import CASEngine
from cas_engine.plot_engine import PlotData

_engine = None

def get_engine() -> CASEngine:
    global _engine
    if _engine is None:
        _engine = CASEngine()
    return _engine

def set_decimal_separator(sep: str) -> dict:
    """Set the decimal separator character (',' or '.') in parser and formatter."""
    try:
        from cas_engine.formatter import MathFormatter
        from cas_engine.parser import MathParser
        MathFormatter.set_decimal_separator(sep)
        MathParser.set_decimal_separator(sep)
        return {"status": "success", "decimal_separator": sep}
    except Exception as e:
        return {"status": "error", "error": str(e)}

def evaluate_expression(expr: str, precision: int = 6) -> dict:
    """
    Evaluate mathematical expression using OpenMath CASEngine
    and return a clean JSON-serializable dictionary.
    """
    engine = get_engine()
    try:
        res = engine.evaluate(expr, precision=precision)
        plot_dict = None
        if getattr(res, 'is_plot', False) and getattr(res, 'plot_data', None):
            raw_pdata = res.plot_data
            p_data = raw_pdata.get('plot_obj', raw_pdata) if isinstance(raw_pdata, dict) else raw_pdata
            curves = []
            for c in getattr(p_data, 'curves', []):
                curves.append({
                    "x": [float(v) for v in c.x_vals if v is not None],
                    "y": [float(v) for v in c.y_vals if v is not None],
                    "label": str(getattr(c, 'label', '') or ''),
                    "color": getattr(c, 'color', None),
                    "style": getattr(c, 'style', '-')
                })
            regions = []
            for r in getattr(p_data, 'regions', []):
                regions.append({
                    "x": [float(v) for v in r.x_vals if v is not None],
                    "y_min": [float(v) for v in r.y_min_vals if v is not None],
                    "y_max": [float(v) for v in r.y_max_vals if v is not None],
                    "color": getattr(r, 'color', '#385a8a'),
                    "alpha": float(getattr(r, 'alpha', 0.5)),
                    "label": str(getattr(r, 'label', '') or '')
                })
            plot_dict = {
                "title": str(getattr(p_data, 'title', '') or ""),
                "x_label": str(getattr(p_data, 'x_label', '') or "x"),
                "y_label": str(getattr(p_data, 'y_label', '') or "y"),
                "x_lim": [float(v) for v in p_data.x_lim] if getattr(p_data, 'x_lim', None) else None,
                "y_lim": [float(v) for v in p_data.y_lim] if getattr(p_data, 'y_lim', None) else None,
                "is_polar": bool(getattr(p_data, 'is_polar', False)),
                "curves": curves,
                "regions": regions
            }

        return {
            "exact_latex": str(getattr(res, 'exact_latex', '') or ''),
            "numeric_latex": str(getattr(res, 'numeric_latex', '') or ''),
            "exact_text": str(getattr(res, 'exact_text', '') or ''),
            "numeric_text": str(getattr(res, 'numeric_text', '') or ''),
            "python_code": str(getattr(res, 'python_code', '') or ''),
            "is_numeric_available": bool(getattr(res, 'is_numeric_available', True)),
            "is_plot": bool(getattr(res, 'is_plot', False)),
            "plot_data": plot_dict,
            "execution_time_ms": round(float(getattr(res, 'execution_time_ms', 0.0)), 2),
            "suppress_output": bool(getattr(res, 'suppress_output', False)),
            "result_type": str(getattr(res, 'result_type', 'Symbolic') or 'Symbolic'),
            "error": None,
            "suggestion": None
        }
    except Exception as e:
        suggestion = None
        try:
            from cas_engine.error_suggester import generate_candidates
            cands = generate_candidates(expr)
            if cands:
                suggestion = cands[0]
        except Exception:
            pass

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
            "result_type": "Error",
            "error": f"{type(e).__name__}: {str(e)}",
            "suggestion": suggestion
        }

def reset_workspace() -> dict:
    """Reset the CAS engine namespace and history."""
    engine = get_engine()
    engine.reset()
    return {"status": "success", "message": "Workspace reset successfully."}

def get_variables_list() -> dict:
    """Return dictionary of user-defined variables."""
    engine = get_engine()
    vars_dict = {}
    try:
        for k, v in engine.get_variables().items():
            vars_dict[k] = str(v)
    except Exception:
        pass
    return vars_dict

def get_system_info() -> dict:
    """Return runtime metadata."""
    import sympy
    import numpy
    return {
        "sympy_version": sympy.__version__,
        "numpy_version": numpy.__version__,
        "python_version": sys.version
    }

def get_help_catalog() -> list:
    """Return list of functions, categories, syntax, and examples from Function Guide."""
    try:
        from cas_engine.function_guide import CATALOG
        result = []
        for fn in CATALOG:
            examples = [{"label": ex.label, "code": ex.code} for ex in fn.examples]
            result.append({
                "name": fn.name,
                "syntax": fn.syntax,
                "category": fn.category,
                "description": fn.description,
                "examples": examples,
                "primary_example": fn.primary_example
            })
        return result
    except Exception as e:
        return []

def parse_worksheet_document(content: str, filename: str = None) -> dict:
    """
    Parse .mw, .mv, .json, or plain text worksheet file content.
    Supports zip-packaged .mw archives (content.xml), native XML, JSON, and text.
    Returns dictionary with extracted calculation cells and formatting.
    """
    if not content or not content.strip():
        return {"cells": [], "error": "Document is empty"}

    # Check if content is a base64 encoded zip archive or binary zip
    if content.startswith("BASE64_ZIP:"):
        try:
            b64_str = content.split(":", 1)[1]
            raw_bytes = base64.b64decode(b64_str)
            if zipfile.is_zipfile(io.BytesIO(raw_bytes)):
                with zipfile.ZipFile(io.BytesIO(raw_bytes), 'r') as zf:
                    names = zf.namelist()
                    target = next((n for n in ['content.xml', 'document.xml'] if n in names), None)
                    if not target:
                        target = next((n for n in names if n.endswith('.mw') or n.endswith('.xml')), None)
                    if target:
                        content = zf.read(target).decode('utf-8', errors='replace')
        except Exception:
            pass
    elif content.startswith("PK\x03\x04"):
        try:
            raw_bytes = content.encode('latin1')
            if zipfile.is_zipfile(io.BytesIO(raw_bytes)):
                with zipfile.ZipFile(io.BytesIO(raw_bytes), 'r') as zf:
                    names = zf.namelist()
                    target = next((n for n in ['content.xml', 'document.xml'] if n in names), None)
                    if not target:
                        target = next((n for n in names if n.endswith('.mw') or n.endswith('.xml')), None)
                    if target:
                        content = zf.read(target).decode('utf-8', errors='replace')
        except Exception:
            pass

    stripped = content.strip()

    # JSON worksheet support
    if stripped.startswith('[') or stripped.startswith('{'):
        try:
            data = json.loads(stripped)
            cell_list = data if isinstance(data, list) else data.get('cells', [])
            parsed = []
            for c in cell_list:
                inp = c.get("input", "")
                is_sec = bool(c.get("is_section_header", False))
                mode_val = c.get("input_mode", 2 if c.get("mode") == "text" else 0)
                parsed.append({
                    "cell_id": c.get("cell_id") or str(uuid.uuid4())[:8],
                    "execution_idx": c.get("execution_idx", len(parsed) + 1),
                    "input": inp,
                    "input_mode": mode_val,
                    "mode": "section" if is_sec else ("text" if mode_val == 2 else "math"),
                    "is_section_header": is_sec,
                    "section_title": c.get("section_title", inp if is_sec else ""),
                    "section_level": c.get("section_level", 0),
                    "section_html": c.get("section_html", ""),
                    "is_collapsed": bool(c.get("is_collapsed", False)),
                    "result": c.get("result"),
                    "embedded_images": c.get("embedded_images", {}),
                })
            if parsed:
                return {"cells": parsed, "error": None}
        except Exception:
            pass

    # Native .mw / .mv XML worksheet support
    try:
        from cas_engine.mw_importer import WorksheetIO
        raw_cells = WorksheetIO.load_mw_string(content)
        parsed = []
        for c in raw_cells:
            inp = (c.get('input', '') or '').strip()
            is_sec = bool(c.get('is_section_header', False))
            title = (c.get('section_title', '') or '').strip()
            mode_val = c.get('input_mode', 0)
            mode_str = "section" if is_sec else ("text" if mode_val == 2 else "math")

            res_dict = c.get('result')
            clean_res = None
            if res_dict:
                exact_latex = res_dict.get('exact_latex') or ''
                exact_text = res_dict.get('exact_text') or ''
                if not exact_latex and exact_text:
                    exact_latex = exact_text
                numeric_latex = res_dict.get('numeric_latex') or exact_latex
                numeric_text = res_dict.get('numeric_text') or exact_text
                clean_res = {
                    'exact_latex': exact_latex,
                    'exact_text': exact_text,
                    'numeric_latex': numeric_latex,
                    'numeric_text': numeric_text,
                    'is_plot': bool(res_dict.get('is_plot', False)),
                    'result_type': res_dict.get('result_type', 'Symbolic')
                }

            parsed.append({
                'cell_id': c.get('cell_id') or str(uuid.uuid4())[:8],
                'execution_idx': c.get('execution_idx', len(parsed) + 1),
                'input': inp,
                'input_mode': mode_val,
                'mode': mode_str,
                'is_section_header': is_sec,
                'section_title': title or inp,
                'section_level': c.get('section_level', 0),
                'is_collapsed': bool(c.get('is_collapsed', False)),
                'section_bg_colors': c.get('section_bg_colors', []),
                'section_html': c.get('section_html', ''),
                'embedded_images': c.get('embedded_images', {}),
                'result': clean_res,
                'error': c.get('error')
            })

        if parsed:
            return {"cells": parsed, "error": None}
    except Exception:
        pass

    # Plain text fallback: line by line or markdown headers
    lines = [line.strip() for line in stripped.splitlines() if line.strip()]
    fallback_cells = []
    for line in lines:
        if line.startswith("#"):
            is_sec = line.startswith("# ") or line.startswith("## ")
            sec_title = line.lstrip("# ")
            fallback_cells.append({
                "cell_id": str(uuid.uuid4())[:8],
                "execution_idx": len(fallback_cells) + 1,
                "input": line,
                "input_mode": 2,
                "mode": "section" if is_sec else "text",
                "is_section_header": is_sec,
                "section_title": sec_title,
                "section_level": 0 if line.startswith("# ") else 1,
                "result": None
            })
        elif not line.startswith("//"):
            fallback_cells.append({
                "cell_id": str(uuid.uuid4())[:8],
                "execution_idx": len(fallback_cells) + 1,
                "input": line,
                "input_mode": 0,
                "mode": "math",
                "is_section_header": False,
                "result": None
            })
    if fallback_cells:
        return {"cells": fallback_cells, "error": None}
    return {"cells": [], "error": "No calculation cells found in document"}

def export_worksheet_document(cells_data: list, format_type: str = 'mw') -> str:
    """
    Serialize cell list to .mw, .json, .tex, or .md string.
    """
    if format_type == 'json':
        return json.dumps(cells_data, indent=2)

    if format_type == 'mw':
        try:
            from cas_engine.mw_importer import WorksheetIO
            return WorksheetIO.save_mw_string(cells_data)
        except Exception as e:
            return json.dumps(cells_data, indent=2)

    if format_type == 'tex':
        tex_lines = [
            r"\documentclass{article}",
            r"\usepackage{amsmath}",
            r"\usepackage{amsfonts}",
            r"\usepackage{geometry}",
            r"\geometry{a4paper, margin=1in}",
            r"\begin{document}",
            r"\title{OpenMath Worksheet}",
            r"\maketitle",
            ""
        ]
        for c in cells_data:
            if c.get("is_section_header"):
                level = c.get("section_level", 0)
                cmd = r"\section" if level == 0 else r"\subsection"
                tex_lines.append(f"{cmd}{{{c.get('section_title', '')}}}\n")
            elif c.get("input_mode") == 2:
                tex_lines.append(f"{c.get('input', '')}\n")
            else:
                inp = c.get("input", "")
                res = c.get("result") or {}
                ltx = res.get("exact_latex") or res.get("exact_text") or ""
                tex_lines.append(r"\begin{align*}")
                tex_lines.append(f"\\text{{[> }} & {inp} \\\\")
                if ltx:
                    tex_lines.append(f"& = {ltx}")
                tex_lines.append(r"\end{align*}")
                tex_lines.append("")
        tex_lines.append(r"\end{document}")
        return "\n".join(tex_lines)

    if format_type == 'md':
        md_lines = ["# OpenMath Worksheet\n"]
        for c in cells_data:
            if c.get("is_section_header"):
                level = c.get("section_level", 0)
                prefix = "#" * (level + 2)
                md_lines.append(f"{prefix} {c.get('section_title', '')}\n")
            elif c.get("input_mode") == 2:
                md_lines.append(f"{c.get('input', '')}\n")
            else:
                inp = c.get("input", "")
                res = c.get("result") or {}
                txt = res.get("exact_text") or ""
                md_lines.append(f"```openmath\n> {inp}\n```")
                if txt:
                    md_lines.append(f"**Result:** `{txt}`\n")
        return "\n".join(md_lines)

    return json.dumps(cells_data, indent=2)
