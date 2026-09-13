"""
Worksheet (.mw) File Format Importer and Exporter.
Allows seamless loading and saving of native XML (.mw) documents.
Supports:
- Hierarchical collapsible Sections (<Section>) with title font backgrounds and styles
- Document Mode (presentation=true) vs Worksheet Mode (presentation=false)
- Embedded Wheeler-compressed images (<Image>) converted to high-resolution PNGs
- 2D Math equations (<Equation input-equation="..." display="...">) decoded to readable math and LaTeX
- 1D text commands and formatted text paragraphs (<Text-field>)
- Output mathematical formulas (<Output>) cleanly decoded without base64 serialization artifacts
"""

import os
import re
import uuid
import base64
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional, Tuple

from .wheeler import decode_worksheet_image
from .typesetting_parser import batch_decode_displays, parse_typesetting


class WorksheetIO:
    """
    Parser and Serializer for native Worksheet (.mw) documents.
    """

    MODE_2D_MATH = 0
    MODE_1D_MATH = 1
    MODE_TEXT = 2
    MODE_NONEXEC_MATH = 3

    @classmethod
    def load_mw_file(cls, filepath: str) -> List[Dict[str, Any]]:
        """Load and parse a .mw XML file into worksheet cell dictionaries."""
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        return cls.load_mw_string(content)

    @classmethod
    def load_mw_string(cls, xml_str: str) -> List[Dict[str, Any]]:
        """
        Parse XML string of a Worksheet (.mw) and return a list of
        cell dictionaries compatible with WorksheetCell.from_dict().
        """
        cells_data: List[Dict[str, Any]] = []
        if not xml_str or not xml_str.strip():
            return cells_data

        stripped = xml_str.strip()
        if stripped.startswith('{'):
            import json
            try:
                data = json.loads(stripped)
                return data.get('cells', [])
            except Exception:
                pass

        try:
            root = ET.fromstring(xml_str)
        except ET.ParseError:
            sanitized = re.sub(r'&(?!amp;|lt;|gt;|apos;|quot;)', '&amp;', xml_str)
            try:
                root = ET.fromstring(sanitized)
            except Exception:
                return cells_data

        # Determine Document Mode vs Worksheet Mode from View-Properties
        vp = root.find('View-Properties')
        is_presentation = False
        if vp is not None:
            is_presentation = vp.attrib.get('presentation', 'false').lower() == 'true'

        # Batch-decode all <Equation display="..."> attributes for performance & precision
        all_displays = []
        display_to_idx = {}
        for eq in root.iter('Equation'):
            disp = eq.attrib.get('display', '')
            if disp and disp not in display_to_idx:
                display_to_idx[disp] = len(all_displays)
                all_displays.append(disp)

        decoded_pairs = batch_decode_displays(all_displays)

        def get_equation_math(eq_elem: ET.Element) -> Tuple[str, str]:
            inp_eq = eq_elem.attrib.get('input-equation', '').strip()
            if inp_eq and not cls._is_base64_mprintslash(inp_eq) and inp_eq != 'JSFH':
                return inp_eq, inp_eq
            disp = eq_elem.attrib.get('display', '')
            if disp in display_to_idx:
                idx = display_to_idx[disp]
                m_str, l_str = decoded_pairs[idx]
                if m_str.strip() and m_str != 'JSFH':
                    return m_str, l_str
            # Fallback to eq text if not raw base64 or JSFH
            t = ''.join(eq_elem.itertext()).strip()
            if t and not cls._is_base64_mprintslash(t) and t != 'JSFH':
                return t, t
            return "", ""

        exec_idx = 1

        def process_element(elem: ET.Element, depth: int = 0):
            nonlocal exec_idx
            tag = elem.tag

            if tag == 'Section':
                col = elem.attrib.get('collapsed', 'false').lower() == 'true'
                title_elem = elem.find('Title')
                title_text = ""
                bg_colors = []
                html_parts = []

                def _parse_worksheet_color(val: str):
                    if not val:
                        return None
                    val = str(val).strip()
                    m_rgb = re.search(r'\[(\d+),\s*(\d+),\s*(\d+)\]', val)
                    if m_rgb:
                        r, g, b = m_rgb.groups()
                        return f"rgb({r},{g},{b})"
                    if val.startswith('#') or val.startswith('rgb'):
                        return val
                    return None

                if title_elem is not None:
                    for tf in title_elem.iter('Text-field'):
                        fonts = list(tf.findall('Font'))
                        if fonts:
                            for font in fonts:
                                bg = font.attrib.get('background', '')
                                fg = font.attrib.get('foreground', '') or font.attrib.get('color', '')
                                ftxt = ''.join(font.itertext())
                                bg_val = _parse_worksheet_color(bg)
                                fg_val = _parse_worksheet_color(fg)
                                if bg_val:
                                    bg_colors.append(bg)
                                style_items = ["font-weight: bold;"]
                                if bg_val:
                                    style_items.append(f"background-color: {bg_val}; border-radius: 3px; padding: 2px 6px;")
                                if fg_val:
                                    style_items.append(f"color: {fg_val};")
                                elif bg_val:
                                    style_items.append("color: #000000;")
                                style_str = " ".join(style_items)
                                html_parts.append(f'<span style="{style_str}">{ftxt}</span>')
                                if font.tail:
                                    html_parts.append(f"<span>{font.tail}</span>")
                        else:
                            txt = ''.join(tf.itertext()).strip()
                            tf_bg = tf.attrib.get('background', '')
                            tf_fg = tf.attrib.get('foreground', '') or tf.attrib.get('color', '')
                            bg_val = _parse_worksheet_color(tf_bg)
                            fg_val = _parse_worksheet_color(tf_fg)
                            if bg_val:
                                bg_colors.append(tf_bg)
                            style_items = ["font-weight: bold;"]
                            if bg_val:
                                style_items.append(f"background-color: {bg_val}; border-radius: 3px; padding: 2px 6px;")
                            if fg_val:
                                style_items.append(f"color: {fg_val};")
                            elif bg_val:
                                style_items.append("color: #000000;")
                            style_str = " ".join(style_items)
                            if txt:
                                html_parts.append(f'<span style="{style_str}">{txt}</span>')
                        if tf.tail:
                            html_parts.append(f"<span>{tf.tail}</span>")
                    title_text = ''.join(title_elem.itertext()).strip()

                sec_cell = {
                    'cell_id': str(uuid.uuid4())[:8],
                    'execution_idx': exec_idx,
                    'input': title_text,
                    'input_mode': cls.MODE_TEXT,
                    'is_worksheet_mode': not is_presentation,
                    'is_section_header': True,
                    'section_title': title_text,
                    'section_level': depth,
                    'is_collapsed': col,
                    'section_bg_colors': bg_colors,
                    'section_html': "".join(html_parts) if html_parts else None,
                }
                cells_data.append(sec_cell)
                exec_idx += 1

                start_count = len(cells_data)
                for child in elem:
                    if child.tag != 'Title':
                        process_element(child, depth + 1)
                if not col and len(cells_data) == start_count:
                    empty_cell = {
                        'cell_id': str(uuid.uuid4())[:8],
                        'execution_idx': exec_idx,
                        'input': '',
                        'input_mode': cls.MODE_2D_MATH,
                        'is_worksheet_mode': not is_presentation,
                        'section_level': depth + 1,
                    }
                    cells_data.append(empty_cell)
                    exec_idx += 1
                return

            elif tag == 'Presentation-Block':
                imgs = elem.findall('.//Image')
                for img in imgs:
                    raw_img_text = img.text or ""
                    img_bytes = decode_worksheet_image(raw_img_text)
                    if img_bytes:
                        img_b64 = base64.b64encode(img_bytes).decode('ascii')
                        img_id = f"img_{uuid.uuid4().hex[:8]}"
                        raw_w = int(img.attrib.get('width', '500'))
                        raw_h = int(img.attrib.get('height', '350'))
                        max_w = 700
                        if raw_w > max_w:
                            img_h = max(20, int(raw_h * (max_w / raw_w)))
                            img_w = max_w
                        else:
                            img_w = raw_w
                            img_h = raw_h
                        img_tag = f'<img src="{img_id}" width="{img_w}" height="{img_h}"/>'
                        cell = {
                            'cell_id': str(uuid.uuid4())[:8],
                            'execution_idx': exec_idx,
                            'input': img_tag,
                            'input_mode': cls.MODE_TEXT,
                            'is_worksheet_mode': not is_presentation,
                            'embedded_images': {img_id: img_b64},
                            'section_level': depth,
                        }
                        cells_data.append(cell)
                        exec_idx += 1
                if imgs:
                    return

                groups = elem.findall('Group')
                has_inline = any(g.attrib.get('inline-output') == 'true' for g in groups)
                has_output = any(g.find('Output') is not None for g in groups)
                has_eq = any(g.find('.//Equation') is not None for g in groups)

                if has_inline or has_output or (len(groups) > 1 and has_eq):
                    spans = []
                    text_parts = []
                    for g in groups:
                        inp = g.find('Input')
                        out = g.find('Output')
                        if inp is not None:
                            for tf in inp.iter('Text-field'):
                                for eq in tf.findall('.//Equation'):
                                    m_str, l_str = get_equation_math(eq)
                                    if m_str and m_str != 'JSFH' and not cls._is_base64_mprintslash(m_str):
                                        is_not_exec = (eq.attrib.get('executable', 'true').lower() == 'false') or (tf.attrib.get('style', '') == 'Text' and not tf.attrib.get('prompt', '').strip())
                                        span_mode = 'nonexec_math' if is_not_exec else '2d_math'
                                        frac = cls._parse_fraction(m_str)
                                        if frac:
                                            spans.append({'type': 'fraction', 'num': cls._clean_math_symbols(frac[0]), 'den': cls._clean_math_symbols(frac[1]), 'mode': span_mode})
                                            text_parts.append(f"({frac[0]})/({frac[1]})")
                                        else:
                                            clean_m = cls._clean_math_symbols(m_str)
                                            spans.append({'type': 'text', 'text': clean_m, 'mode': span_mode})
                                            text_parts.append(clean_m)
                                tf_clean = cls._extract_tf_text(tf)
                                if tf_clean and not cls._is_base64_mprintslash(tf_clean):
                                    tf_bg = tf.attrib.get('background', '')
                                    if not tf_bg:
                                        for f in tf.findall('.//Font'):
                                            if f.attrib.get('background'):
                                                tf_bg = f.attrib.get('background')
                                                break
                                    if tf_bg:
                                        m_rgb = re.search(r'\[(\d+),\s*(\d+),\s*(\d+)\]', tf_bg)
                                        bg_col = f"#{int(m_rgb.group(1)):02x}{int(m_rgb.group(2)):02x}{int(m_rgb.group(3)):02x}" if m_rgb else "#00ff00"
                                        spans.append({'type': 'text', 'text': f" {tf_clean} ", 'bg_color': bg_col, 'color': '#000000', 'font_weight': 'bold', 'mode': 'text'})
                                    else:
                                        spans.append({'type': 'text', 'text': f" {tf_clean} ", 'mode': 'text'})
                                    text_parts.append(tf_clean)

                        if out is not None:
                            out_m = ""
                            for out_eq in out.iter('Equation'):
                                m_str, l_str = get_equation_math(out_eq)
                                if m_str and m_str != 'JSFH' and not cls._is_base64_mprintslash(m_str):
                                    out_m = m_str
                                    break
                            out_bg = ""
                            for out_elem in out.iter():
                                if out_elem.attrib.get('background'):
                                    out_bg = out_elem.attrib.get('background')
                                    break
                            if out_m:
                                spans.append({'type': 'text', 'text': ' = ', 'mode': 'text'})
                                text_parts.append(f"= {out_m}")
                                if out_bg:
                                    m_rgb = re.search(r'\[(\d+),\s*(\d+),\s*(\d+)\]', out_bg)
                                    bg_col = f"#{int(m_rgb.group(1)):02x}{int(m_rgb.group(2)):02x}{int(m_rgb.group(3)):02x}" if m_rgb else "#00ff00"
                                    spans.append({'type': 'text', 'text': f" {out_m} ", 'bg_color': bg_col, 'color': '#000000', 'font_weight': 'bold', 'mode': 'text'})
                                else:
                                    spans.append({'type': 'text', 'text': out_m, 'color': '#0000cc', 'font_weight': 'bold', 'mode': 'text'})

                    cleaned_spans = cls._normalize_spans(spans)
                    if cleaned_spans:
                        has_exec = any(s.get('mode') == '2d_math' for s in cleaned_spans)
                        cell = {
                            'cell_id': str(uuid.uuid4())[:8],
                            'execution_idx': exec_idx,
                            'input': " ".join(text_parts).strip(),
                            'spans': cleaned_spans,
                            'input_mode': cls.MODE_2D_MATH if has_exec else cls.MODE_NONEXEC_MATH,
                            'is_worksheet_mode': not is_presentation,
                            'section_level': depth,
                        }
                        cells_data.append(cell)
                        exec_idx += 1
                        return

                for child in elem:
                    process_element(child, depth)
                return

            elif tag in ('Group', 'Input'):
                inp = elem if tag == 'Input' else elem.find('Input')
                out = None if tag == 'Input' else elem.find('Output')

                # Extract Output result if present in group
                out_result = None
                if out is not None:
                    for out_eq in out.iter('Equation'):
                        out_m, out_l = get_equation_math(out_eq)
                        if out_m:
                            out_result = {
                                'exact_text': out_m,
                                'exact_latex': out_l or out_m,
                                'numeric_text': out_m,
                                'numeric_latex': out_l or out_m,
                                'result_type': 'Symbolic',
                                'is_plot': False,
                            }
                            break
                    if not out_result:
                        for out_tf in out.iter('Text-field'):
                            otxt = ''.join(out_tf.itertext()).strip()
                            if otxt and not cls._is_base64_mprintslash(otxt):
                                out_result = {
                                    'exact_text': otxt,
                                    'exact_latex': otxt,
                                    'numeric_text': otxt,
                                    'numeric_latex': otxt,
                                    'result_type': 'Symbolic',
                                    'is_plot': False,
                                }
                                break

                if inp is not None:
                    for tf in inp.iter('Text-field'):
                        prompt = tf.attrib.get('prompt', '')
                        style = tf.attrib.get('style', '')

                        # 1. Check for embedded images
                        imgs = tf.findall('.//Image')
                        for img in imgs:
                            raw_img_text = img.text or ""
                            img_bytes = decode_worksheet_image(raw_img_text)
                            if img_bytes:
                                img_b64 = base64.b64encode(img_bytes).decode('ascii')
                                img_id = f"img_{uuid.uuid4().hex[:8]}"
                                raw_w = int(img.attrib.get('width', '500'))
                                raw_h = int(img.attrib.get('height', '350'))
                                max_w = 700
                                if raw_w > max_w:
                                    img_h = max(20, int(raw_h * (max_w / raw_w)))
                                    img_w = max_w
                                else:
                                    img_w = raw_w
                                    img_h = raw_h
                                img_tag = f'<img src="{img_id}" width="{img_w}" height="{img_h}"/>'
                                cell = {
                                    'cell_id': str(uuid.uuid4())[:8],
                                    'execution_idx': exec_idx,
                                    'input': img_tag,
                                    'input_mode': cls.MODE_TEXT,
                                    'is_worksheet_mode': not is_presentation,
                                    'embedded_images': {img_id: img_b64},
                                    'section_level': depth,
                                }
                                cells_data.append(cell)
                                exec_idx += 1

                        # 2. Check for Math equations
                        eqs = tf.findall('.//Equation')
                        added_eq = False
                        if eqs:
                            for eq in eqs:
                                m_str, l_str = get_equation_math(eq)
                                if not m_str.strip() or m_str == 'JSFH' or cls._is_base64_mprintslash(m_str):
                                    continue  # Filter out empty placeholder lines (JSFH)
                                is_not_exec = (eq.attrib.get('executable', 'true').lower() == 'false') or (tf.attrib.get('style', '') == 'Text' and not tf.attrib.get('prompt', '').strip())
                                is_exec = not is_not_exec
                                cell = {
                                    'cell_id': str(uuid.uuid4())[:8],
                                    'execution_idx': exec_idx,
                                    'input': m_str,
                                    'input_mode': cls.MODE_2D_MATH if is_exec else cls.MODE_NONEXEC_MATH,
                                    'is_worksheet_mode': not is_presentation,
                                    'section_level': depth,
                                }
                                if out_result:
                                    cell['result'] = out_result
                                    out_result = None
                                cells_data.append(cell)
                                exec_idx += 1
                                added_eq = True

                        # 3. Formatted text
                        tf_clean = cls._extract_tf_text(tf)
                        if tf_clean and not cls._is_base64_mprintslash(tf_clean) and not imgs:
                            if added_eq and tf_clean == '=':
                                continue
                            prefix = "# " if style == 'Title' else ("## " if style == 'Heading 1' else "")
                            tf_bg = tf.attrib.get('background', '')
                            fonts = list(tf.findall('.//Font'))
                            html_pieces = []
                            has_font_bg = False
                            for font in fonts:
                                bg = font.attrib.get('background', '')
                                ftxt = ''.join(font.itertext()).strip()
                                ftxt = re.sub(r'\bJSFH\b', '', ftxt).strip()
                                if bg and ftxt:
                                    has_font_bg = True
                                    m_rgb = re.search(r'\[(\d+),\s*(\d+),\s*(\d+)\]', bg)
                                    if m_rgb:
                                        r_c, g_c, b_c = m_rgb.groups()
                                        html_pieces.append(f'<span style="background-color: rgb({r_c},{g_c},{b_c}); color: #000000; font-weight: bold; border-radius: 3px; padding: 2px 6px;">{ftxt}</span>')
                                    else:
                                        html_pieces.append(ftxt)
                                elif ftxt:
                                    html_pieces.append(ftxt)

                            if has_font_bg and html_pieces:
                                formatted_input = " ".join(html_pieces)
                            elif tf_bg:
                                m_rgb = re.search(r'\[(\d+),\s*(\d+),\s*(\d+)\]', tf_bg)
                                if m_rgb:
                                    r_c, g_c, b_c = m_rgb.groups()
                                    formatted_input = f'<span style="background-color: rgb({r_c},{g_c},{b_c}); color: #000000; font-weight: bold; border-radius: 3px; padding: 2px 6px;">{tf_clean}</span>'
                                else:
                                    formatted_input = prefix + tf_clean
                            else:
                                formatted_input = prefix + tf_clean

                            is_1d_input = (style in ('Maple Input', 'OpenMath Input', '1D Input')) or (prompt and prompt.strip() == '>')
                            cell = {
                                'cell_id': str(uuid.uuid4())[:8],
                                'execution_idx': exec_idx,
                                'input': formatted_input,
                                'input_mode': cls.MODE_1D_MATH if is_1d_input else cls.MODE_TEXT,
                                'is_worksheet_mode': not is_presentation,
                                'section_level': depth,
                            }
                            cells_data.append(cell)
                            exec_idx += 1
                return

            else:
                for child in elem:
                    process_element(child, depth)

        for child in root:
            if child.tag in ('Section', 'Presentation-Block', 'Group', 'Input'):
                process_element(child, 0)

        return cells_data

    @classmethod
    def _extract_tf_text(cls, tf: ET.Element) -> str:
        """Extract text from Text-field excluding Equation and Image children."""
        parts = []
        if tf.text:
            parts.append(tf.text)
        for child in tf:
            if child.tag not in ('Equation', 'Image'):
                parts.append(cls._extract_tf_text(child))
            if child.tail:
                parts.append(child.tail)
        raw = "".join(parts).strip()
        cleaned = re.sub(r'\bJSFH\b', '', raw).strip()
        cleaned = re.sub(r'LUkl[A-Za-z0-9+/=]+', '', cleaned).strip()
        return cleaned

    @classmethod
    def _parse_fraction(cls, s: str):
        if not s:
            return None
        m = re.match(r'^\s*\((.*?)\)\s*/\s*\((.*?)\)\s*$', s)
        if m:
            return m.group(1).strip(), m.group(2).strip()
        return None

    @classmethod
    def _clean_math_symbols(cls, s: str) -> str:
        if not s:
            return ""
        s = s.replace('&coloneq;', ':=').replace('&uminus0;', '-').replace('&ExponentialE;', 'e')
        s = s.replace('*', ' · ')
        s = re.sub(r'\((\d+)\)\^\((\d+)\)', r'\1^\2', s)
        s = re.sub(r'\((\d+)\)\^(\d+)', r'\1^\2', s)
        sup_map = {'0': '⁰', '1': '¹', '2': '²', '3': '³', '4': '⁴', '5': '⁵', '6': '⁶', '7': '⁷', '8': '⁸', '9': '⁹', '-': '⁻'}
        def replace_sup(m):
            return "".join(sup_map.get(d, d) for d in m.group(1))
        s = re.sub(r'\^(\-?\d+)', replace_sup, s)
        return s.strip()

    @classmethod
    def _normalize_spans(cls, spans: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        cleaned = []
        for sp in spans:
            if sp.get('type') == 'text':
                txt = sp.get('text', '')
                txt = re.sub(r'\bJSFH\b', '', txt).strip()
                txt = re.sub(r'LUkl[A-Za-z0-9+/=]+', '', txt).strip()
                if not txt:
                    continue
                if txt == '=' and cleaned and cleaned[-1].get('type') == 'text' and cleaned[-1].get('text', '').strip().endswith('='):
                    continue
                if txt == '=':
                    sp['text'] = ' = '
                elif not sp.get('bg_color'):
                    sp['text'] = f" {txt} " if not txt.startswith(' ') else txt
            cleaned.append(sp)
        return cleaned

    @classmethod
    def _is_base64_mprintslash(cls, s: str) -> bool:
        """Check if string is an encoded base64 mprintslash or serialized token string."""
        if not s:
            return False
        if s == 'JSFH' or s.startswith('JSFH'):
            return True
        if len(s) < 15:
            return False
        if s.startswith(('LUkl', 'Pkki', 'Pkkm', 'PjYk', 'LUk', 'QyQt', 'JClr', 'JClm', 'TUZP', 'TUFOV', 'TUZOV')):
            return True
        return False

    @classmethod
    def save_mw_string(cls, cells: List[Dict[str, Any]]) -> str:
        """Serialize cell dictionaries into a valid .mw XML document."""
        root = ET.Element("Worksheet")
        ver = ET.SubElement(root, "Version")
        ver.attrib["major"] = "2025"
        ver.attrib["minor"] = "0"

        vp = ET.SubElement(root, "View-Properties")
        vp.attrib["presentation"] = "true"
        vp.attrib["autoexpanding_sections"] = "true"

        # Organize by sections if section headers exist
        current_container = root
        active_sections = []

        for idx, cell in enumerate(cells, 1):
            is_sec = cell.get('is_section_header', False)
            if is_sec:
                sec_level = cell.get('section_level', 0)
                # Close deeper sections
                while len(active_sections) > sec_level:
                    active_sections.pop()

                sec_elem = ET.SubElement(active_sections[-1] if active_sections else root, "Section")
                sec_elem.attrib["collapsed"] = "true" if cell.get('is_collapsed') else "false"
                sec_elem.attrib["isCollapsible"] = "true"

                title_elem = ET.SubElement(sec_elem, "Title")
                tf_title = ET.SubElement(title_elem, "Text-field")
                tf_title.attrib["style"] = "Heading 1"
                tf_title.text = cell.get('section_title', cell.get('input', ''))

                active_sections.append(sec_elem)
                current_container = sec_elem
                continue

            parent = active_sections[-1] if active_sections else root
            group = ET.SubElement(parent, "Group")
            group.attrib["labelreference"] = f"L{idx}"

            inp_mode = cell.get("input_mode", cls.MODE_2D_MATH)
            input_text = cell.get("input", "").strip()
            embedded_imgs = cell.get("embedded_images", {})

            inp = ET.SubElement(group, "Input")

            if embedded_imgs:
                # Embedded image
                for img_id, b64_data in embedded_imgs.items():
                    tf = ET.SubElement(inp, "Text-field")
                    tf.attrib["style"] = "Text"
                    img_node = ET.SubElement(tf, "Image")
                    img_node.attrib["width"] = "480"
                    img_node.attrib["height"] = "320"
                    img_node.text = b64_data

            elif inp_mode == cls.MODE_TEXT:
                # Text cell
                tf = ET.SubElement(inp, "Text-field")
                tf.attrib["style"] = "Text"
                tf.attrib["layout"] = "Normal"
                tf.text = input_text

            else:
                # Math cell (1-D or 2-D)
                tf = ET.SubElement(inp, "Text-field")
                tf.attrib["prompt"] = "> " if cell.get("is_worksheet_mode", True) else ""
                tf.attrib["style"] = "Maple Input"
                tf.attrib["layout"] = "Normal"

                eq = ET.SubElement(tf, "Equation")
                eq.attrib["executable"] = "true"
                eq.attrib["style"] = "2D Input" if inp_mode == cls.MODE_2D_MATH else "Maple Input"
                eq.attrib["input-equation"] = input_text
                eq.text = input_text

                res = cell.get("result")
                if res and (res.get("exact_text") or res.get("exact_latex")):
                    out = ET.SubElement(group, "Output")
                    out_tf = ET.SubElement(out, "Text-field")
                    out_tf.attrib["style"] = "2D Output"
                    out_tf.attrib["layout"] = "Maple Output"
                    out_eq = ET.SubElement(out_tf, "Equation")
                    out_eq.attrib["executable"] = "false"
                    out_eq.attrib["style"] = "2D Output"
                    out_eq.text = res.get("exact_text") or res.get("exact_latex")

        xml_declaration = '<?xml version="1.0" encoding="UTF-8"?>\n'
        return xml_declaration + ET.tostring(root, encoding="utf-8").decode("utf-8")

    @classmethod
    def save_mw_file(cls, cells: List[Dict[str, Any]], filepath: str):
        """Save worksheet cells to a .mw file."""
        xml_content = cls.save_mw_string(cells)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(xml_content)
