"""
Engineering and Electrical Units: definitions, conversion tables, and expression unit inference.
"""

import re
from typing import Dict, List, Optional, Tuple

UNIT_FAMILIES: Dict[str, Dict] = {
    'voltage': {
        'base': 'V',
        'display_name': 'Voltage',
        'units': [
            ('μV', 1e-6, 'uV'),
            ('mV', 1e-3, 'mV'),
            ('V', 1.0, 'V'),
            ('kV', 1e3, 'kV'),
            ('MV', 1e6, 'MV'),
        ]
    },
    'resistance': {
        'base': 'Ohm',
        'display_name': 'Resistance',
        'units': [
            ('Ω', 1.0, 'Ohm'),
            ('kΩ', 1e3, 'kOhm'),
            ('MΩ', 1e6, 'MOhm'),
            ('GΩ', 1e9, 'GOhm'),
        ]
    },
    'current': {
        'base': 'A',
        'display_name': 'Current',
        'units': [
            ('μA', 1e-6, 'uA'),
            ('mA', 1e-3, 'mA'),
            ('A', 1.0, 'A'),
            ('kA', 1e3, 'kA'),
            ('MA', 1e6, 'MA'),
        ]
    },
    'frequency': {
        'base': 'Hz',
        'display_name': 'Frequency',
        'units': [
            ('Hz', 1.0, 'Hz'),
            ('kHz', 1e3, 'kHz'),
            ('MHz', 1e6, 'MHz'),
            ('GHz', 1e9, 'GHz'),
        ]
    },
    'time': {
        'base': 's',
        'display_name': 'Time',
        'units': [
            ('ps', 1e-12, 'ps'),
            ('ns', 1e-9, 'ns'),
            ('μs', 1e-6, 'us'),
            ('ms', 1e-3, 'ms'),
            ('s', 1.0, 's'),
        ]
    },
    'capacitance': {
        'base': 'F',
        'display_name': 'Capacitance',
        'units': [
            ('pF', 1e-12, 'pF'),
            ('nF', 1e-9, 'nF'),
            ('μF', 1e-6, 'uF'),
            ('mF', 1e-3, 'mF'),
            ('F', 1.0, 'F'),
        ]
    },
    'power': {
        'base': 'W',
        'display_name': 'Power',
        'units': [
            ('μW', 1e-6, 'uW'),
            ('mW', 1e-3, 'mW'),
            ('W', 1.0, 'W'),
            ('kW', 1e3, 'kW'),
            ('MW', 1e6, 'MW'),
        ]
    }
}

# Lookup table: unit_string -> (family, scale_to_base, code_unit, display_label)
UNIT_LOOKUP: Dict[str, Tuple[str, float, str, str]] = {
    # Voltage
    'V': ('voltage', 1.0, 'V', 'V'),
    'mV': ('voltage', 1e-3, 'mV', 'mV'),
    'uV': ('voltage', 1e-6, 'uV', 'μV'),
    'μV': ('voltage', 1e-6, 'uV', 'μV'),
    'kV': ('voltage', 1e3, 'kV', 'kV'),
    'MV': ('voltage', 1e6, 'MV', 'MV'),
    'MegaVolt': ('voltage', 1e6, 'MV', 'MV'),
    'megavolt': ('voltage', 1e6, 'MV', 'MV'),

    # Resistance
    'Ohm': ('resistance', 1.0, 'Ohm', 'Ω'),
    'Ω': ('resistance', 1.0, 'Ohm', 'Ω'),
    'kOhm': ('resistance', 1e3, 'kOhm', 'kΩ'),
    'kΩ': ('resistance', 1e3, 'kOhm', 'kΩ'),
    'MOhm': ('resistance', 1e6, 'MOhm', 'MΩ'),
    'MΩ': ('resistance', 1e6, 'MOhm', 'MΩ'),
    'MegaOhm': ('resistance', 1e6, 'MOhm', 'MΩ'),
    'megaohm': ('resistance', 1e6, 'MOhm', 'MΩ'),
    'megohm': ('resistance', 1e6, 'MOhm', 'MΩ'),
    'GOhm': ('resistance', 1e9, 'GOhm', 'GΩ'),
    'GΩ': ('resistance', 1e9, 'GOhm', 'GΩ'),
    'GigaOhm': ('resistance', 1e9, 'GOhm', 'GΩ'),
    'gigaohm': ('resistance', 1e9, 'GOhm', 'GΩ'),

    # Current
    'A': ('current', 1.0, 'A', 'A'),
    'mA': ('current', 1e-3, 'mA', 'mA'),
    'uA': ('current', 1e-6, 'uA', 'μA'),
    'μA': ('current', 1e-6, 'uA', 'μA'),
    'kA': ('current', 1e3, 'kA', 'kA'),
    'MA': ('current', 1e6, 'MA', 'MA'),
    'MegaAmp': ('current', 1e6, 'MA', 'MA'),
    'megaamp': ('current', 1e6, 'MA', 'MA'),

    # Frequency
    'Hz': ('frequency', 1.0, 'Hz', 'Hz'),
    'kHz': ('frequency', 1e3, 'kHz', 'kHz'),
    'MHz': ('frequency', 1e6, 'MHz', 'MHz'),
    'GHz': ('frequency', 1e9, 'GHz', 'GHz'),
    'MegaHz': ('frequency', 1e6, 'MHz', 'MHz'),
    'megahertz': ('frequency', 1e6, 'MHz', 'MHz'),

    # Time
    'ps': ('time', 1e-12, 'ps', 'ps'),
    's': ('time', 1.0, 's', 's'),
    'ms': ('time', 1e-3, 'ms', 'ms'),
    'us': ('time', 1e-6, 'us', 'μs'),
    'μs': ('time', 1e-6, 'us', 'μs'),
    'ns': ('time', 1e-9, 'ns', 'ns'),

    # Capacitance
    'F': ('capacitance', 1.0, 'F', 'F'),
    'mF': ('capacitance', 1e-3, 'mF', 'mF'),
    'uF': ('capacitance', 1e-6, 'uF', 'μF'),
    'μF': ('capacitance', 1e-6, 'uF', 'μF'),
    'nF': ('capacitance', 1e-9, 'nF', 'nF'),
    'pF': ('capacitance', 1e-12, 'pF', 'pF'),

    # Power
    'W': ('power', 1.0, 'W', 'W'),
    'mW': ('power', 1e-3, 'mW', 'mW'),
    'uW': ('power', 1e-6, 'uW', 'μW'),
    'μW': ('power', 1e-6, 'uW', 'μW'),
    'kW': ('power', 1e3, 'kW', 'kW'),
    'MW': ('power', 1e6, 'MW', 'MW'),
    'MegaWatt': ('power', 1e6, 'MW', 'MW'),
    'megawatt': ('power', 1e6, 'MW', 'MW'),
}


def format_unit_value(val: float, unit: str, decimal_separator: str = ',') -> str:
    """Format a numeric float cleanly with the specified unit, respecting decimal separator."""
    if abs(val - round(val)) < 1e-9 and abs(val) < 1e15:
        num_str = str(int(round(val)))
    else:
        num_str = f"{val:.6g}"
        if 'e' not in num_str.lower():
            num_str = f"{val:.6f}".rstrip('0').rstrip('.')
    if decimal_separator == ',':
        num_str = num_str.replace('.', ',')
    return f"{num_str} {unit}"


def convert_value(val: float, from_unit: str, to_unit: str) -> float:
    """Convert numeric value between units in the same family."""
    if from_unit not in UNIT_LOOKUP or to_unit not in UNIT_LOOKUP:
        raise ValueError(f"Unknown unit conversion: {from_unit} -> {to_unit}")
    fam_from, scale_from, _, _ = UNIT_LOOKUP[from_unit]
    fam_to, scale_to, _, _ = UNIT_LOOKUP[to_unit]
    if fam_from != fam_to:
        raise ValueError(f"Cannot convert between different families: {fam_from} and {fam_to}")
    base = float(val) * scale_from
    return base / scale_to


def get_unit_conversions(val: float, current_unit: str, decimal_separator: str = ',') -> List[Dict]:
    """
    Generate conversion options for all units within the current unit's family.
    Returns list of dicts with:
    {'label': str, 'code_unit': str, 'value': float, 'display_text': str, 'code_text': str, 'is_current': bool}
    """
    if current_unit not in UNIT_LOOKUP:
        return []

    fam_name, cur_scale, cur_code, cur_label = UNIT_LOOKUP[current_unit]
    family = UNIT_FAMILIES[fam_name]
    base_val = float(val) * cur_scale

    options = []
    for label, scale, code_unit in family['units']:
        conv_val = base_val / scale
        disp_txt = format_unit_value(conv_val, label, decimal_separator)
        code_txt = format_unit_value(conv_val, code_unit, decimal_separator)
        is_cur = (code_unit == current_unit or label == current_unit or code_unit == cur_code)
        options.append({
            'label': label,
            'code_unit': code_unit,
            'value': conv_val,
            'display_text': disp_txt,
            'code_text': code_txt,
            'is_current': is_cur
        })
    return options


def get_family_conversions_for_raw_value(val: float, family_name: str, decimal_separator: str = ',') -> List[Dict]:
    """Generate conversion options assuming val is already in base units of family_name."""
    if family_name not in UNIT_FAMILIES:
        return []
    family = UNIT_FAMILIES[family_name]
    options = []
    for label, scale, code_unit in family['units']:
        conv_val = float(val) / scale
        disp_txt = format_unit_value(conv_val, label, decimal_separator)
        code_txt = format_unit_value(conv_val, code_unit, decimal_separator)
        options.append({
            'label': label,
            'code_unit': code_unit,
            'value': conv_val,
            'display_text': disp_txt,
            'code_text': code_txt,
            'is_current': (scale == 1.0)
        })
    return options


def infer_unit_from_expression(expr_str: str) -> Optional[str]:
    """
    Infer the expected unit for an expression.
    Handles embedded functions (voltage_divider -> V, etc.) and dimensional expressions.
    """
    s = expr_str.strip()
    if not s:
        return None

    # 1. Hardware & Electronics calculations
    # Voltage divider: output is voltage. Prefer unit of v_in if given (e.g. mV -> mV, MV -> MV)
    if re.search(r'\b(?:voltage_divider|voltagedivider)\b', s):
        m = re.search(r'\b(?:voltage_divider|voltagedivider)\s*\(\s*[^,]*?\b(MV|MegaVolt|kV|mV|uV|μV|V)\b', s)
        return m.group(1) if m else 'V'

    # ADC Voltage conversion
    if re.search(r'\b(?:adc_volt|adc_count_to_volt)\b', s):
        return 'V'

    # Voltage divider R1 calculation: output is resistance
    if re.search(r'\bvoltage_divider_r1\b', s):
        m = re.search(r'\b(GOhm|GΩ|MegaOhm|MOhm|kOhm|Ohm|kΩ|MΩ|Ω)\b', s)
        return m.group(1) if m else 'kOhm'

    # 2. Check for units present in the expression
    # Find all units in the expression
    tokens = re.findall(r'\b([a-zA-ZΩμµ]+)\b', s)
    present_units = [t for t in tokens if t in UNIT_LOOKUP]

    if not present_units:
        return None

    # Determine unique families
    families = [UNIT_LOOKUP[u][0] for u in present_units]
    unique_families = set(families)

    if len(unique_families) == 1:
        # Single family arithmetic: e.g. 5 V + 200 mV -> V, 10 kOhm + 2.5 kOhm -> kOhm
        fam = families[0]
        # Return dominant unit (first one mentioned or standard unit)
        return present_units[0]

    # Cross-family combinations
    if 'voltage' in unique_families and 'resistance' in unique_families:
        # V / Ohm -> Current (mA or A)
        if '/' in s:
            return 'mA'
    if 'current' in unique_families and 'resistance' in unique_families:
        # A * Ohm -> Voltage (V)
        if '*' in s or '·' in s or ' ' in s:
            return 'V'
    if 'voltage' in unique_families and 'current' in unique_families:
        # V * A -> Power (W or mW)
        if '*' in s or '·' in s or ' ' in s:
            return 'W'
        elif '/' in s:
            return 'Ohm'

    return present_units[0]
