"""
Mathematical expression parser and preprocessor for the CAS Engine.
Supports shorthand math syntax (2x -> 2*x, ^ -> **, implicit multiplication),
assignments (:=), equations (= -> Eq), and calculus/algebra aliases.
"""

import re
import ast
import sympy as sp
from sympy.parsing.sympy_parser import (
    parse_expr,
    standard_transformations,
    split_symbols_custom,
    _token_splittable,
    implicit_multiplication,
    implicit_application,
    convert_xor,
    auto_symbol,
    function_exponentiation,
)
from sympy.utilities.exceptions import SymPyDeprecationWarning


class ParseResult:
    """Holds information about the parsed expression."""
    def __init__(self, raw_input: str, processed_str: str, sympy_expr=None,
                 is_assignment: bool = False, assign_var: str = None,
                 assign_args: list = None, is_plot: bool = False,
                 plot_args: dict = None, is_command: bool = False,
                 command_name: str = None, command_args: list = None,
                 suppress_output: bool = False):
        self.raw_input = raw_input
        self.processed_str = processed_str
        self.sympy_expr = sympy_expr
        self.is_assignment = is_assignment
        self.assign_var = assign_var
        self.assign_args = assign_args or []
        self.is_plot = is_plot
        self.plot_args = plot_args or {}
        self.is_command = is_command
        self.command_name = command_name
        self.command_args = command_args or []
        self.suppress_output = suppress_output


class SafeEq(sp.Eq):
    """
    Drop-in replacement for sp.Eq that safely handles operands returning strings,
    such as hex/binary representations (e.g. '0xFF', '0b1010') or non-SymPy objects,
    preventing SympifyError during equation evaluation.
    """
    def __new__(cls, lhs, rhs, **kwargs):
        def _to_sym(val):
            if isinstance(val, dict):
                return sp.Dict({sp.Symbol(str(k)): _to_sym(v) for k, v in val.items()})
            if isinstance(val, (list, tuple)):
                return sp.Tuple(*[_to_sym(x) for x in val])
            if isinstance(val, str):
                s = val.strip()
                clean_s = s.replace(' ', '')
                if clean_s.startswith(('0x', '0X', '0b', '0B', '0o', '0O')):
                    try:
                        return sp.Integer(int(clean_s, 0))
                    except Exception:
                        pass
                try:
                    return sp.sympify(s)
                except Exception:
                    return sp.Symbol(s)
            return val
        lhs = _to_sym(lhs)
        rhs = _to_sym(rhs)
        try:
            return super().__new__(cls, lhs, rhs, **kwargs)
        except Exception:
            if lhs == rhs:
                return sp.true
            return sp.Symbol(f"{lhs} = {rhs}")


def _can_split_symbol(symbol: str) -> bool:
    # Do not split indexed variable symbols ending in digits (e.g. R1, R2, V1, x1, a2) into multiplication
    if re.search(r'\d+$', symbol):
        return False
    return _token_splittable(symbol)


class MathParser:
    """
    Parser for natural mathematical expressions and CAS commands.
    """

    TRANSFORMATIONS = standard_transformations + (
        convert_xor,
        split_symbols_custom(_can_split_symbol),
        implicit_multiplication,
        implicit_application,
        function_exponentiation,
    )

    # Built-in symbol aliases
    BUILTIN_ALIASES = {
        'Eq': SafeEq,
        'Pi': sp.pi,
        'pi': sp.pi,
        'PI': sp.pi,
        'E': sp.E,
        'e': sp.E,
        'I': sp.Symbol('I'),
        'i': sp.I,
        'j': sp.I,
        'oo': sp.oo,
        'inf': sp.oo,
        'infinity': sp.oo,
        'Infinity': sp.oo,
        'NAN': sp.nan,
        'nan': sp.nan,
        'eval': sp.Function('eval'),
        'subs': sp.Function('subs'),
        'lhs': sp.Function('lhs'),
        'rhs': sp.Function('rhs'),
        'normal': sp.Function('normal'),
        'coeff': sp.Function('coeff'),
        'degree': sp.Function('degree'),
        'convert': sp.Function('convert'),
        'nops': sp.Function('nops'),
        'op': sp.Function('op'),
        'map': sp.Function('map'),
        'select': sp.Function('select'),
        'remove': sp.Function('remove'),
        'DotProduct': sp.Function('DotProduct'),
        'CrossProduct': sp.Function('CrossProduct'),
        'Norm': sp.Function('Norm'),
        'VectorAngle': sp.Function('VectorAngle'),
        'Row': sp.Function('Row'),
        'Column': sp.Function('Column'),
        'MatrixAdd': sp.Function('MatrixAdd'),
        'MatrixMatrixMultiply': sp.Function('MatrixMatrixMultiply'),
        'LUDecomposition': sp.Function('LUDecomposition'),
        'QRDecomposition': sp.Function('QRDecomposition'),
        'GaussianElimination': sp.Function('GaussianElimination'),
        'Mean': sp.Function('Mean'),
        'Median': sp.Function('Median'),
        'Variance': sp.Function('Variance'),
        'StandardDeviation': sp.Function('StandardDeviation'),
        'Quantile': sp.Function('Quantile'),
        'laplace': sp.Function('laplace'),
        'invlaplace': sp.Function('invlaplace'),
        'fourier': sp.Function('fourier'),
        'invfourier': sp.Function('invfourier'),
        'ifactor': sp.Function('ifactor'),
        'igcd': sp.Function('igcd'),
        'ilcm': sp.Function('ilcm'),
        'nextprime': sp.Function('nextprime'),
        'prevprime': sp.Function('prevprime'),
        'ithprime': sp.Function('ithprime'),
        'divisors': sp.Function('divisors'),
        'euler_phi': sp.Function('euler_phi'),
        'modp': sp.Function('modp'),
        'Int': sp.Integral,
        'Diff': sp.Derivative,
        'Limit': sp.Limit,
        'value': sp.Function('value'),
        'Mod': sp.Mod,
        'ans': sp.Symbol('ans'),
        '_ans_1': sp.Symbol('_ans_1'),
        '_ans_2': sp.Symbol('_ans_2'),
        '_ans_3': sp.Symbol('_ans_3'),
        'parfrac': sp.Symbol('parfrac'),
        'apart': sp.Symbol('apart'),
        'sincos': sp.Symbol('sincos'),
        'fraction': sp.Symbol('fraction'),
        'rational': sp.Symbol('rational'),
        'degrees': sp.Symbol('degrees'),
        'radians': sp.Symbol('radians'),
        'reg': sp.Symbol('reg'),
        'Q': sp.Symbol('Q'),
        'EmptySet': sp.S.EmptySet,
        'Complexes': sp.S.Complexes,
        'Reals': sp.S.Reals,
        'Naturals': sp.S.Naturals,
        'Integers': sp.S.Integers,
        'Rationals': sp.S.Rationals,
        'Contains': sp.Contains,
        'Subset': sp.Function('Subset'),
        'Superset': sp.Function('Superset'),
        'Intersection': sp.Intersection,
        'Union': sp.Union,
        'Implies': sp.Implies,
        'Equivalent': sp.Equivalent,
        'Not': sp.Not,
        'And': sp.And,
        'Or': sp.Or,
        'Exists': sp.Function('Exists'),
        'ForAll': sp.Function('ForAll'),
        # Embedded Systems & Hardware Engineering Functions
        'to_bin': sp.Function('to_bin'),
        'to_hex': sp.Function('to_hex'),
        'twos_comp': sp.Function('twos_comp'),
        'twos_comp_repr': sp.Function('twos_comp_repr'),
        'two_comp': sp.Function('two_comp'),
        'two_comp_repr': sp.Function('two_comp_repr'),
        'bit_get': sp.Function('bit_get'),
        'bit_set': sp.Function('bit_set'),
        'bit_clear': sp.Function('bit_clear'),
        'bit_toggle': sp.Function('bit_toggle'),
        'bit_mask': sp.Function('bit_mask'),
        'bit_field': sp.Function('bit_field'),
        'extract_bitfield': sp.Function('extract_bitfield'),
        'to_q': sp.Function('to_q'),
        'from_q': sp.Function('from_q'),
        'to_qformat': sp.Function('to_qformat'),
        'from_qformat': sp.Function('from_qformat'),
        'ieee754': sp.Function('ieee754'),
        'ubrr_calc': sp.Function('ubrr_calc'),
        'baud_rate': sp.Function('baud_rate'),
        'uart_baud': sp.Function('uart_baud'),
        'uart_baud_div': sp.Function('uart_baud_div'),
        'uart_baud_rate': sp.Function('uart_baud_rate'),
        'timer_calc': sp.Function('timer_calc'),
        'timer_arr': sp.Function('timer_arr'),
        'timer_arr_prescaler': sp.Function('timer_arr_prescaler'),
        'pwm_duty': sp.Function('pwm_duty'),
        'adc_raw': sp.Function('adc_raw'),
        'adc_volt': sp.Function('adc_volt'),
        'adc_count_to_volt': sp.Function('adc_count_to_volt'),
        'adc_volt_to_count': sp.Function('adc_volt_to_count'),
        'adc_resolution': sp.Function('adc_resolution'),
        'voltage_divider': sp.Function('voltage_divider'),
        'voltage_divider_r1': sp.Function('voltage_divider_r1'),
        'led_resistor': sp.Function('led_resistor'),
        'rc_cutoff': sp.Function('rc_cutoff'),
        'crc8': sp.Function('crc8'),
        'crc16': sp.Function('crc16'),
        # SI & Engineering Units
        'V': sp.Symbol('V'),
        'mV': sp.Symbol('mV'),
        'uV': sp.Symbol('uV'),
        'kV': sp.Symbol('kV'),
        'MV': sp.Symbol('MV'),
        'MegaVolt': sp.Symbol('MV'),
        'megavolt': sp.Symbol('MV'),
        'Hz': sp.Symbol('Hz'),
        'kHz': sp.Symbol('kHz'),
        'MHz': sp.Symbol('MHz'),
        'GHz': sp.Symbol('GHz'),
        'MegaHz': sp.Symbol('MHz'),
        'megahertz': sp.Symbol('MHz'),
        's': sp.Symbol('s'),
        'ms': sp.Symbol('ms'),
        'us': sp.Symbol('us'),
        'ns': sp.Symbol('ns'),
        'ps': sp.Symbol('ps'),
        'Ohm': sp.Symbol('Ohm'),
        'kOhm': sp.Symbol('kOhm'),
        'MOhm': sp.Symbol('MOhm'),
        'MegaOhm': sp.Symbol('MOhm'),
        'megaohm': sp.Symbol('MOhm'),
        'megohm': sp.Symbol('MOhm'),
        'GOhm': sp.Symbol('GOhm'),
        'GΩ': sp.Symbol('GOhm'),
        'F': sp.Symbol('F'),
        'mF': sp.Symbol('mF'),
        'uF': sp.Symbol('uF'),
        'nF': sp.Symbol('nF'),
        'pF': sp.Symbol('pF'),
        'A': sp.Symbol('A'),
        'mA': sp.Symbol('mA'),
        'uA': sp.Symbol('uA'),
        'kA': sp.Symbol('kA'),
        'MA': sp.Symbol('MA'),
        'MegaAmp': sp.Symbol('MA'),
        'megaamp': sp.Symbol('MA'),
        'W': sp.Symbol('W'),
        'mW': sp.Symbol('mW'),
        'uW': sp.Symbol('uW'),
        'kW': sp.Symbol('kW'),
        'MW': sp.Symbol('MW'),
        'MegaWatt': sp.Symbol('MW'),
        'megawatt': sp.Symbol('MW'),
    }

    decimal_separator: str = ','

    @classmethod
    def set_decimal_separator(cls, sep: str):
        """Set active decimal separator (',' or '.')."""
        if sep in (',', '.'):
            cls.decimal_separator = sep

    @classmethod
    def preprocess_string(cls, text: str, local_dict: dict = None) -> str:
        r"""
        Preprocess text input:
        - Convert decimal comma notation (e.g., 3,14 -> 3.14)
        - Handle caret ^ as power ** (if not handled by parser)
        - Clean unicode mathematical symbols
        - Handle calculus operators (e.g., d/dx, \int)
        """
        s = text.strip()
        if not s:
            return s

        # Strip template placeholders ⟦...⟧ so unedited slots evaluate safely as symbols
        s = re.sub(r'[⟦⟧]', '', s)

        # Early normalization of Unicode subscripts (including subscript parentheses ₍ ₎ and digits ₀-₉)
        _EARLY_SUB_MAP = {
            '₀': '0', '₁': '1', '₂': '2', '₃': '3', '₄': '4',
            '₅': '5', '₆': '6', '₇': '7', '₈': '8', '₉': '9',
            '₊': '+', '₋': '-', '₌': '=', '₍': '(', '₎': ')',
            'ₐ': 'a', 'ᵦ': 'b', 'ₑ': 'e', 'ₕ': 'h', 'ᵢ': 'i', 'ⱼ': 'j',
            'ₖ': 'k', 'ₗ': 'l', 'ₘ': 'm', 'ₙ': 'n', 'ₒ': 'o',
            'ₚ': 'p', 'ᵣ': 'r', 'ᵤ': 'u', 'ᵥ': 'v', 'ₓ': 'x',
            'ₛ': 's', 'ₜ': 't',
        }
        all_early_sub = ''.join(_EARLY_SUB_MAP.keys())
        if any(c in s for c in all_early_sub):
            s = re.sub(rf'(?<=[a-zA-Z_])([{re.escape(all_early_sub)}]+)',
                       lambda m: '_' + ''.join(_EARLY_SUB_MAP.get(c, c) for c in m.group(1)), s)
            s = re.sub(rf'[{re.escape(all_early_sub)}]+',
                       lambda m: ''.join(_EARLY_SUB_MAP.get(c, c) for c in m.group(0)), s)

        # Compact nibble-spaced binary literals: e.g. 0b0101 1010 -> 0b01011010
        s = re.sub(r'\b(0[bB][01]+(?:\s+[01]+)+)\b', lambda m: m.group(0).replace(' ', ''), s)

        # Normalize scientific notation literals: e.g. 4e - 06 -> 4e-6, 1e + 03 -> 1e+3
        def _norm_sci_parser(m):
            return f"{m.group(1)}e{m.group(2)}{int(m.group(3))}"
        s = re.sub(r'\b(\d+(?:\.\d+)?)[eE]\s*([+-])\s*(\d+)\b', _norm_sci_parser, s)

        # Normalize Unicode engineering units to ASCII equivalents (e.g. kΩ -> kOhm, μF -> uF)
        s = re.sub(r'\bGΩ\b', 'GOhm', s)
        s = re.sub(r'\bkΩ\b', 'kOhm', s)
        s = re.sub(r'\bMΩ\b', 'MOhm', s)
        s = re.sub(r'\bΩ\b', 'Ohm', s)
        s = re.sub(r'[μµ]([a-zA-Z]+)', r'u\1', s)
        # Normalize spoken/textual unit variants: e.g. "mega ohm" -> "MOhm", "kilo ohm" -> "kOhm"
        s = re.sub(r'\bmega[\s_-]?ohms?\b', 'MOhm', s, flags=re.IGNORECASE)
        s = re.sub(r'\bmegohms?\b', 'MOhm', s, flags=re.IGNORECASE)
        s = re.sub(r'\bkilo[\s_-]?ohms?\b', 'kOhm', s, flags=re.IGNORECASE)
        s = re.sub(r'\bgiga[\s_-]?ohms?\b', 'GOhm', s, flags=re.IGNORECASE)
        s = re.sub(r'\bmega[\s_-]?volts?\b', 'MV', s, flags=re.IGNORECASE)
        s = re.sub(r'\bmega[\s_-]?watts?\b', 'MW', s, flags=re.IGNORECASE)
        s = re.sub(r'\bmega[\s_-]?amps?\b', 'MA', s, flags=re.IGNORECASE)
        s = re.sub(r'\bmega[\s_-]?hertz\b', 'MHz', s, flags=re.IGNORECASE)

        # Convert decimal comma notation when comma mode is active
        if getattr(cls, 'decimal_separator', ',') == ',':
            # 1. Leading comma: ,5 -> 0.5 when preceded by operator, bracket, or string start
            s = re.sub(r'(^|(?<=[\s+\-*/=([<{]))\s*,\s*(\d+)', r'\g<1>0.\2', s)
            # 2. Number decimal comma between digits without spaces: 30,4 -> 30.4
            s = re.sub(r'(?<=\d),(?=\d)', '.', s)
            # 3. Decimal comma with spaces at top-level (outside brackets and parentheses):
            # e.g., '30, 4' -> '30.4', 'x := 30, 4' -> 'x := 30.4'
            chars = []
            depth = 0
            i = 0
            n = len(s)
            while i < n:
                ch = s[i]
                if ch in '([{':
                    depth += 1
                    chars.append(ch)
                    i += 1
                elif ch in ')]}':
                    depth = max(0, depth - 1)
                    chars.append(ch)
                    i += 1
                elif depth == 0 and ch == ',' and i > 0 and s[i - 1].isdigit():
                    m = re.match(r'^\s*(\d+)', s[i + 1:])
                    if m:
                        chars.append('.' + m.group(1))
                        i += 1 + len(m.group(0))
                    else:
                        chars.append(ch)
                        i += 1
                else:
                    chars.append(ch)
                    i += 1
            s = ''.join(chars)
            # 4. European argument/item separator semicolon ';' inside expressions:
            # e.g., [1,2; 3,4] -> [1.2, 3.4], solve(x^2=4; x) -> solve(x^2=4, x)
            s = re.sub(r';\s*(?!\s*$)', ', ', s)

        # Convert common LaTeX math commands into CAS expressions
        # \frac{num}{den} -> ((num)/(den))
        frac_pattern = r'\\frac\s*\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}\s*\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}'
        prev_s = None
        while prev_s != s:
            prev_s = s
            s = re.sub(frac_pattern, r'((\1)/(\2))', s)

        # \sqrt[n]{x} and \sqrt{x}
        s = re.sub(r'\\sqrt\s*\[(.*?)\]\s*\{(.*?)\}', r'root(\2, \1)', s)
        s = re.sub(r'\\sqrt\s*\{(.*?)\}', r'sqrt(\1)', s)

        # Remove \left and \right
        s = s.replace(r'\left', '').replace(r'\right', '')

        # Standard LaTeX operators & symbols
        s = s.replace(r'\cdot', '*').replace(r'\times', '*')
        s = s.replace(r'\pi', 'pi').replace(r'\infty', 'oo')
        s = s.replace(r'\ln', 'log').replace(r'\log', 'log')
        s = s.replace(r'\sin', 'sin').replace(r'\cos', 'cos').replace(r'\tan', 'tan')
        s = s.replace(r'\int', 'integrate').replace(r'\sum', 'Sum').replace(r'\prod', 'Product')

        _SUPERSCRIPT_MAP = {
            '⁰': '0', '¹': '1', '²': '2', '³': '3', '⁴': '4',
            '⁵': '5', '⁶': '6', '⁷': '7', '⁸': '8', '⁹': '9',
            '⁺': '+', '⁻': '-', '⁼': '=', '⁽': '(', '⁾': ')',
            'ᵃ': 'a', 'ᵇ': 'b', 'ᶜ': 'c', 'ᵈ': 'd', 'ᵉ': 'e',
            'ᶠ': 'f', 'ᵍ': 'g', 'ʰ': 'h', 'ⁱ': 'i', 'ʲ': 'j',
            'ᵏ': 'k', 'ˡ': 'l', 'ᵐ': 'm', 'ⁿ': 'n', 'ᵒ': 'o',
            'ᵖ': 'p', 'ʳ': 'r', 'ˢ': 's', 'ᵗ': 't', 'ᵘ': 'u',
            'ᵛ': 'v', 'ʷ': 'w', 'ˣ': 'x', 'ʸ': 'y', 'ᶻ': 'z',
            '·': '*', '⋅': '*',
        }
        sup_chars = ''.join(c for c in _SUPERSCRIPT_MAP.keys() if c not in ('·', '⋅'))

        _SUB_DIGITS = {
            '₀': '0', '₁': '1', '₂': '2', '₃': '3', '₄': '4',
            '₅': '5', '₆': '6', '₇': '7', '₈': '8', '₉': '9'
        }
        sub_chars = ''.join(_SUB_DIGITS.keys())

        # 1. Nth root with superscript: e.g. ³√(8) or ⁿ√(x)
        def _nth_root_repl(m):
            n = ''.join(_SUPERSCRIPT_MAP.get(c, c) for c in m.group(1))
            arg = m.group(2) or m.group(3)
            return f"root({arg}, {n})"
        s = re.sub(rf'([{re.escape(sup_chars)}]+)√\s*(?:\((.*?)\)|([a-zA-Z0-9]+))', _nth_root_repl, s)

        # 2. Square root: e.g. √(x) or √x
        s = re.sub(r'√\s*\((.*?)\)', r'sqrt(\1)', s)
        s = re.sub(r'√\s*([a-zA-Z0-9]+)', r'sqrt(\1)', s)
        s = s.replace('√', 'sqrt')

        # 3. Logarithm with subscript base: e.g. log₁₀(x) -> log(x, 10), log₂(x) -> log(x, 2)
        def _log_sub_repl(m):
            base = ''.join(_SUB_DIGITS.get(c, c) for c in m.group(1))
            arg = m.group(2)
            return f"log({arg}, {base})"
        s = re.sub(rf'log([{re.escape(sub_chars)}]+)\s*\((.*?)\)', _log_sub_repl, s)
        s = re.sub(r'\blog10\s*\((.*?)\)', r'log(\1, 10)', s)
        s = re.sub(r'\blog_10\s*\((.*?)\)', r'log(\1, 10)', s)
        s = re.sub(r'\blog2\s*\((.*?)\)', r'log(\1, 2)', s)
        s = re.sub(r'\blog_2\s*\((.*?)\)', r'log(\1, 2)', s)

        # 4. Handle Differentiation:
        # Matches ((d)/(dx)) (expr), ((d²)/(dx²)) (expr), d/dx(expr), d²/dx²(expr), etc.
        diff_p = re.compile(
            r'(?:'
            r'\(?\s*\(?\s*[d∂](?:([²³⁴⁵⁶⁷⁸⁹])|\^(\d+))?\s*\)?\s*/\s*\(?\s*[d∂]([a-zA-Z])(?:[²³⁴⁵⁶⁷⁸⁹]|\^\d+)?\s*\)?\s*\)?'
            r'|'
            r'\b[d∂](?:([²³⁴⁵⁶⁷⁸⁹])|\^(\d+))?/[d∂]([a-zA-Z])(?:[²³⁴⁵⁶⁷⁸⁹]|\^\d+)?'
            r')\s*\*?\s*'
        )
        _ord_map = {'²': 2, '³': 3, '⁴': 4, '⁵': 5, '⁶': 6, '⁷': 7, '⁸': 8, '⁹': 9}
        while True:
            m = diff_p.search(s)
            if not m:
                break
            var = m.group(3) or m.group(6)
            order_c = m.group(1) or m.group(4)
            order_n = m.group(2) or m.group(5)
            order = _ord_map.get(order_c) if order_c else (int(order_n) if order_n else 1)
            diff_call_fmt = f"diff({{inner}}, {var}, {order})" if order > 1 else f"diff({{inner}}, {var})"

            rest = s[m.end():].lstrip()
            if not rest:
                break
            if rest.startswith('('):
                depth = 0
                end_idx = -1
                for idx, ch in enumerate(rest):
                    if ch == '(':
                        depth += 1
                    elif ch == ')':
                        depth -= 1
                        if depth == 0:
                            end_idx = idx
                            break
                if end_idx != -1:
                    inner = rest[1:end_idx]
                    s = s[:m.start()] + diff_call_fmt.format(inner=inner) + rest[end_idx + 1:]
                    continue
            tok_m = re.match(r'([a-zA-Z0-9_²³⁴⁵⁶⁷⁸⁹⁺⁻]+)', rest)
            if tok_m:
                inner = tok_m.group(1)
                s = s[:m.start()] + diff_call_fmt.format(inner=inner) + rest[tok_m.end():]
                continue
            break

        # 5. Convert all Unicode superscripts into ^(...)
        sup_pattern = re.compile(rf'[{re.escape(sup_chars)}](?:[{re.escape(sup_chars + "·⋅")}]+(?<=[{re.escape(sup_chars)}]))?')
        def _sup_repl(m):
            inner = ''.join(_SUPERSCRIPT_MAP.get(c, c) for c in m.group(0))
            return f"^({inner})"
        s = sup_pattern.sub(_sup_repl, s)

        # 5b. Convert Unicode subscripts into _digits/characters (e.g. V₁ -> V_1, x₀ -> x_0, aₙ -> a_n)
        _SUB_MAP = {
            '₀': '0', '₁': '1', '₂': '2', '₃': '3', '₄': '4',
            '₅': '5', '₆': '6', '₇': '7', '₈': '8', '₉': '9',
            '₊': '+', '₋': '-', '₌': '=', '₍': '(', '₎': ')',
            'ₐ': 'a', 'ᵦ': 'b', 'ₑ': 'e', 'ₕ': 'h', 'ᵢ': 'i', 'ⱼ': 'j',
            'ₖ': 'k', 'ₗ': 'l', 'ₘ': 'm', 'ₙ': 'n', 'ₒ': 'o',
            'ₚ': 'p', 'ᵣ': 'r', 'ᵤ': 'u', 'ᵥ': 'v', 'ₓ': 'x',
            'ₛ': 's', 'ₜ': 't',
        }
        all_sub_chars = ''.join(_SUB_MAP.keys())
        s = re.sub(rf'(?<=[a-zA-Z_])([{re.escape(all_sub_chars)}]+)',
                   lambda m: '_' + ''.join(_SUB_MAP.get(c, c) for c in m.group(1)), s)
        s = re.sub(rf'[{re.escape(all_sub_chars)}]+',
                   lambda m: ''.join(_SUB_MAP.get(c, c) for c in m.group(0)), s)

        # 6. Handle Integrals (definite and indefinite)
        # Definite integral with _a^b: e.g. ∫_0^1 (x²) dx or ∫_a^b f dx
        s = re.sub(r'∫_([a-zA-Z0-9.]+)\^([a-zA-Z0-9.]+)\s*(?:\((.*?)\)|(.*?))\s*d([a-zA-Z])\b',
                   lambda m: f'integrate({m.group(3) or m.group(4)}, ({m.group(5)}, {m.group(1)}, {m.group(2)}))', s)
        # Definite integral with range: ∫(f, x = a..b) or integrate(f, x = a..b)
        s = re.sub(r'∫\s*\((.*?),\s*([a-zA-Z])\s*=\s*(.*?)\.\.(.*?)\)', r'integrate(\1, (\2, \3, \4))', s)
        s = re.sub(r'\bintegrate\s*\((.*?),\s*([a-zA-Z])\s*=\s*(.*?)\.\.(.*?)\)', r'integrate(\1, (\2, \3, \4))', s)
        # Definite integral with tuple: ∫(f, (x, a, b))
        s = re.sub(r'∫\s*\((.*?),\s*\(([a-zA-Z]),\s*(.*?),\s*(.*?)\)\)', r'integrate(\1, (\2, \3, \4))', s)
        # Indefinite integral: ∫(f) dx
        s = re.sub(r'∫\s*\((.*?)\)\s*d([a-zA-Z])\b', r'integrate(\1, \2)', s)
        # Indefinite integral: ∫ f dx
        s = re.sub(r'∫\s*(.*?)\s*d([a-zA-Z])\b', r'integrate(\1, \2)', s)
        # Standard 2-arg: ∫(f, x)
        s = re.sub(r'∫\s*\((.*?),\s*([a-zA-Z])\)', r'integrate(\1, \2)', s)

        # 7. Handle Summation & Product with range notation
        def _summation_repl(m):
            body, var, start, end = m.group(1).strip(), m.group(2).strip(), m.group(3).strip(), m.group(4).strip()
            if local_dict and body in local_dict and callable(local_dict[body]):
                body = f"{body}({var})"
            return f"summation({body}, ({var}, {start}, {end}))"

        def _product_repl(m):
            body, var, start, end = m.group(1).strip(), m.group(2).strip(), m.group(3).strip(), m.group(4).strip()
            if local_dict and body in local_dict and callable(local_dict[body]):
                body = f"{body}({var})"
            return f"product({body}, ({var}, {start}, {end}))"

        s = re.sub(r'∑\s*\((.*?),\s*([a-zA-Z])\s*=\s*(.*?)\.\.(.*?)\)', _summation_repl, s)
        s = re.sub(r'∏\s*\((.*?),\s*([a-zA-Z])\s*=\s*(.*?)\.\.(.*?)\)', _product_repl, s)
        s = re.sub(r'\bSum\s*\((.*?),\s*([a-zA-Z])\s*=\s*(.*?)\.\.(.*?)\)', _summation_repl, s)
        s = re.sub(r'\bProduct\s*\((.*?),\s*([a-zA-Z])\s*=\s*(.*?)\.\.(.*?)\)', _product_repl, s)

        # 8. Handle function mapping notation: f : x -> y or f : x → y
        s = s.replace('→', '->')
        fn_map_match = re.match(r'^\s*([a-zA-Z_]\w*)\s*:\s*([a-zA-Z_]\w*|\(.*?\))\s*->\s*(.*)$', s)
        if fn_map_match:
            s = f"{fn_map_match.group(1)} := {fn_map_match.group(2)} -> {fn_map_match.group(3)}"

        # 9. Handle vertical bars |expr| for absolute value
        bar_pattern = re.compile(r'\|([^|]+)\|')
        while bar_pattern.search(s):
            s = bar_pattern.sub(r'Abs(\1)', s)

        replacements = {
            '×': '*',
            '÷': '/',
            '−': '-',
            '–': '-',
            'π': 'pi',
            '∞': 'oo',
            '½': '(1/2)',
            '¼': '(1/4)',
            '≤': '<=',
            '≥': '>=',
            '≠': '!=',
            '·': '*',
            '⋅': '*',
            '∫': 'integrate',
            '∑': 'summation',
            '∏': 'product',
            '∂': 'diff',
            'ℂ': 'Complexes',
            'ℝ': 'Reals',
            'ℕ': 'Naturals',
            'ℤ': 'Integers',
            'ℚ': 'Rationals',
            '∅': 'EmptySet',
        }
        for u_char, asc in replacements.items():
            s = s.replace(u_char, asc)

        # Normalize standalone Pi to pi (sp.pi)
        s = re.sub(r'\bPi\b', 'pi', s)

        # Quantifiers: ∃, ∀
        s = re.sub(r'∃\s*([a-zA-Z_]\w*)\s*:\s*(.*)', r'Exists(\1, \2)', s)
        s = re.sub(r'∀\s*([a-zA-Z_]\w*)\s*:\s*(.*)', r'ForAll(\1, \2)', s)
        s = s.replace('∃', 'Exists')
        s = s.replace('∀', 'ForAll')

        # Logic operators
        s = s.replace('¬', ' ~ ')
        s = s.replace('∧', ' & ')
        s = s.replace('∨', ' | ')

        # Handle d/dx(f), ∂/∂x(f), d/dt(f) shorthand -> diff(f, x)
        d_dx_match = re.match(r'^(?:[d∂]/[d∂]([a-zA-Z]))\s*\((.*)\)$', s)
        if d_dx_match:
            var_name = d_dx_match.group(1)
            inner_expr = d_dx_match.group(2)
            s = f"diff({inner_expr}, {var_name})"

        # Handle diff notation like diff(f, x$2) -> diff(f, x, 2)
        s = re.sub(r'\$([0-9]+)', r', \1', s)

        # Replace ln with log (standard in SymPy)
        # But be careful not to replace inside words
        s = re.sub(r'\bln\b', 'log', s)

        # Replace arcsin, arccos, arctan, etc.
        s = re.sub(r'\barcsin\b', 'asin', s)
        s = re.sub(r'\barccos\b', 'acos', s)
        s = re.sub(r'\barctan\b', 'atan', s)
        s = re.sub(r'\barcsec\b', 'asec', s)
        s = re.sub(r'\barccsc\b', 'acsc', s)
        s = re.sub(r'\barccot\b', 'acot', s)

        # Taylor alias: taylor(f, x=a, n) -> series(f, x, a, n)
        taylor_match = re.match(r'^taylor\s*\((.*)\)$', s)
        if taylor_match:
            args_str = taylor_match.group(1)
            s = f"series({args_str})"

        # int alias: int(...) -> integrate(...)
        if re.match(r'^int\s*\(', s):
            s = 'integrate' + s[3:]

        # Transform limit(expr, x = a, [dir]) and lim(...) -> limit(expr, x, a, [dir])
        limit_pattern = re.compile(r'\b(limit|lim)\s*\(')
        for _ in range(5):
            found_any = False
            start_pos = 0
            while True:
                m = limit_pattern.search(s, start_pos)
                if not m:
                    break
                open_paren_idx = m.end() - 1
                depth = 0
                close_paren_idx = -1
                for i in range(open_paren_idx, len(s)):
                    ch = s[i]
                    if ch == '(':
                        depth += 1
                    elif ch == ')':
                        depth -= 1
                        if depth == 0:
                            close_paren_idx = i
                            break
                if close_paren_idx == -1:
                    start_pos = m.end()
                    continue

                inner = s[open_paren_idx + 1:close_paren_idx]
                args = []
                arg_start = 0
                d = 0
                for i, ch in enumerate(inner):
                    if ch in '([{':
                        d += 1
                    elif ch in ')]}':
                        d -= 1
                    elif ch == ',' and d == 0:
                        args.append(inner[arg_start:i].strip())
                        arg_start = i + 1
                args.append(inner[arg_start:].strip())

                transformed = None
                if len(args) == 2 and '=' in args[1]:
                    v, val = args[1].split('=', 1)
                    transformed = f"limit({args[0]}, {v.strip()}, {val.strip()})"
                elif len(args) == 3 and '=' in args[1]:
                    v, val = args[1].split('=', 1)
                    direction = args[2].strip()
                    if 'left' in direction or '-' in direction:
                        d_str = "'-'"
                    elif 'right' in direction or '+' in direction:
                        d_str = "'+'"
                    else:
                        d_str = direction
                    transformed = f"limit({args[0]}, {v.strip()}, {val.strip()}, {d_str})"
                elif m.group(1) == 'lim':
                    transformed = f"limit({inner})"

                if transformed is not None and transformed != s[m.start():close_paren_idx + 1]:
                    s = s[:m.start()] + transformed + s[close_paren_idx + 1:]
                    found_any = True
                    break
                else:
                    start_pos = m.end()
            if not found_any:
                break

        # Protect index variable 'i' from becoming imaginary unit I in seq, add, mul, sum
        def _protect_i_index(m):
            cmd = m.group(1)
            inner = m.group(2)
            if re.search(r'\bi\s*=', inner) or re.search(r',\s*i\s*,', inner):
                inner = re.sub(r'\bi\b', '_i_var', inner)
            return f"{cmd}({inner})"

        s = re.sub(r'\b(seq|add|mul|sum|product)\s*\((.*?)\)', _protect_i_index, s)

        # Range syntax: var = a .. b -> (var, a, b) and a .. b -> (a, b)
        s = cls._transform_ranges(s)

        # mod syntax: a mod b -> Mod(a, b)
        s = re.sub(r'(\b[a-zA-Z0-9_.]+|\))\s+mod\s+(\b[a-zA-Z0-9_.]+|\()', r'Mod(\1, \2)', s)

        # Ditto operators: %%% -> _ans_3, %% -> _ans_2, % -> ans
        s = s.replace('%%%', '_ans_3')
        s = s.replace('%%', '_ans_2')
        s = re.sub(r'%(?!%|[a-zA-Z0-9_])', 'ans', s)

        return s

    @classmethod
    def _transform_ranges(cls, s: str) -> str:
        """
        Transform Maple-style range syntax into SymPy tuples:
          var = a .. b  -> (var, a, b)
          a .. b        -> (a, b)
        Supports general expressions with variables, constants (e.g. pi), parentheses, etc.
        """
        if '..' not in s:
            return s

        out = []
        while True:
            idx = s.find('..')
            if idx == -1:
                break
            # Ignore if part of ellipsis '...'
            if (idx > 0 and s[idx - 1] == '.') or (idx + 2 < len(s) and s[idx + 2] == '.'):
                out.append(s[:idx + 1])
                s = s[idx + 1:]
                continue

            depth_paren = 0
            depth_bracket = 0
            depth_brace = 0
            start_idx = 0
            eq_pos = -1

            for b in range(idx - 1, -1, -1):
                ch = s[b]
                if ch == ')':
                    depth_paren += 1
                elif ch == '(':
                    if depth_paren > 0:
                        depth_paren -= 1
                    else:
                        start_idx = b + 1
                        break
                elif ch == ']':
                    depth_bracket += 1
                elif ch == '[':
                    if depth_bracket > 0:
                        depth_bracket -= 1
                    else:
                        start_idx = b + 1
                        break
                elif ch == '}':
                    depth_brace += 1
                elif ch == '{':
                    if depth_brace > 0:
                        depth_brace -= 1
                    else:
                        start_idx = b + 1
                        break
                elif depth_paren == 0 and depth_bracket == 0 and depth_brace == 0:
                    if ch in (',', ';'):
                        start_idx = b + 1
                        break
                    elif ch == '=' and eq_pos == -1:
                        prev_ch = s[b - 1] if b > 0 else ''
                        next_ch = s[b + 1] if b + 1 < idx else ''
                        if prev_ch not in ('=', '<', '>', '!', ':') and next_ch != '=':
                            eq_pos = b

            depth_paren = 0
            depth_bracket = 0
            depth_brace = 0
            end_idx = len(s)

            for f in range(idx + 2, len(s)):
                ch = s[f]
                if ch == '(':
                    depth_paren += 1
                elif ch == ')':
                    if depth_paren > 0:
                        depth_paren -= 1
                    else:
                        end_idx = f
                        break
                elif ch == '[':
                    depth_bracket += 1
                elif ch == ']':
                    if depth_bracket > 0:
                        depth_bracket -= 1
                    else:
                        end_idx = f
                        break
                elif ch == '{':
                    depth_brace += 1
                elif ch == '}':
                    if depth_brace > 0:
                        depth_brace -= 1
                    else:
                        end_idx = f
                        break
                elif depth_paren == 0 and depth_bracket == 0 and depth_brace == 0:
                    if ch in (',', ';'):
                        end_idx = f
                        break

            lhs = s[start_idx:idx]
            rhs = s[idx + 2:end_idx]
            leading_ws = lhs[:len(lhs) - len(lhs.lstrip())]

            if eq_pos != -1 and eq_pos > start_idx:
                var_part = s[start_idx:eq_pos].strip()
                if re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', var_part):
                    val_start = s[eq_pos + 1:idx].strip()
                    val_end = rhs.strip()
                    replacement = f'{leading_ws}({var_part}, {val_start}, {val_end})'
                else:
                    replacement = f'{leading_ws}({lhs.strip()}, {rhs.strip()})'
            else:
                replacement = f'{leading_ws}({lhs.strip()}, {rhs.strip()})'

            s = s[:start_idx] + replacement + s[end_idx:]

        return ''.join(out) + s

    @classmethod
    def check_assignment(cls, text: str):
        """
        Detect assignment syntax:
        - `x := expr`
        - `f(x) := expr` or `f(x, y) := expr`
        - `x = expr` (if LHS is pure variable name and RHS has no equation meaning)
        Returns (is_assign, var_name, args, rhs_str)
        """
        s = text.strip()
        # Pre-convert subscripts in identifier positions: e.g. V₁ -> V_1
        _SUB_MAP = {
            '₀': '0', '₁': '1', '₂': '2', '₃': '3', '₄': '4',
            '₅': '5', '₆': '6', '₇': '7', '₈': '8', '₉': '9',
            '₊': '+', '₋': '-', '₌': '=', '₍': '(', '₎': ')',
            'ₐ': 'a', 'ᵦ': 'b', 'ₑ': 'e', 'ₕ': 'h', 'ᵢ': 'i', 'ⱼ': 'j',
            'ₖ': 'k', 'ₗ': 'l', 'ₘ': 'm', 'ₙ': 'n', 'ₒ': 'o',
            'ₚ': 'p', 'ᵣ': 'r', 'ᵤ': 'u', 'ᵥ': 'v', 'ₓ': 'x',
            'ₛ': 's', 'ₜ': 't',
        }
        all_sub_chars = ''.join(_SUB_MAP.keys())
        if any(c in s for c in all_sub_chars):
            s = re.sub(rf'(?<=[a-zA-Z_])([{re.escape(all_sub_chars)}]+)',
                       lambda m: '_' + ''.join(_SUB_MAP.get(c, c) for c in m.group(1)), s)

        # Check explicit := assignment
        if ':=' in s:
            parts = s.split(':=', 1)
            lhs = parts[0].strip()
            rhs = parts[1].strip()
            return cls._parse_lhs_assignment(lhs, rhs)

        # Check '=' assignment vs equation
        if '=' in s and not any(op in s for op in ['==', '<=', '>=', '!=', ':=']):
            # If inside parentheses, it's likely a keyword arg or equation in solve()
            # Check if top-level '=' exists
            bracket_depth = 0
            equal_pos = -1
            for i, ch in enumerate(s):
                if ch in '([{':
                    bracket_depth += 1
                elif ch in ')]}':
                    bracket_depth -= 1
                elif ch == '=' and bracket_depth == 0:
                    equal_pos = i
                    break

            if equal_pos != -1:
                lhs = s[:equal_pos].strip()
                rhs = s[equal_pos + 1:].strip()
                # If LHS is a simple identifier or simple function def f(x)
                if re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', lhs) or re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*\s*\([a-zA-Z0-9_,\s]*\)$', lhs):
                    # Check if RHS has variables matching LHS or if it looks like an equation to solve
                    # By convention in CAS: `a = 5` is assignment, `x^2 = 4` is equation.
                    # If LHS is single var and user typed `a = expr`, treat as assignment
                    return cls._parse_lhs_assignment(lhs, rhs)

        return False, None, [], s

    @classmethod
    def _parse_lhs_assignment(cls, lhs: str, rhs: str):
        # Check if RHS has arrow operator '->' (e.g. x -> x^2 or (x, y) -> x + y)
        if '->' in rhs:
            arrow_parts = rhs.split('->', 1)
            args_part = arrow_parts[0].strip().strip('()')
            actual_rhs = arrow_parts[1].strip()
            args = [a.strip() for a in args_part.split(',') if a.strip()]
            var_name = lhs.strip()
            if re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', var_name):
                return True, var_name, args, actual_rhs

        func_match = re.match(r'^([a-zA-Z_][a-zA-Z0-9_]*)\s*\((.*?)\)$', lhs)
        if func_match:
            var_name = func_match.group(1)
            raw_args = func_match.group(2).split(',')
            args = [a.strip() for a in raw_args if a.strip()]
            if all(re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', a) for a in args) and args:
                return True, var_name, args, rhs
            return False, None, [], rhs
        elif re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', lhs):
            return True, lhs, [], rhs
        return False, None, [], rhs

    @classmethod
    def convert_equations_to_eq(cls, text: str) -> str:
        """
        Converts top-level and nested equations `expr1 = expr2` to `Eq(expr1, expr2)`.
        Leaves alone `<=`, `>=`, `!=`, `==`, `:=`.
        """
        s = text.strip()
        if ':=' in s:
            return s

        def _process_segment(seg: str) -> str:
            seg = seg.strip()
            if not seg:
                return seg

            # Tokenize by brackets and commas while preserving inner structures
            out = []
            i = 0
            n = len(seg)
            buf = []
            depth = 0

            # First recursively process bracket contents
            while i < n:
                ch = seg[i]
                if ch in '([{':
                    # Find matching closing bracket
                    close_ch = ')' if ch == '(' else (']' if ch == '[' else '}')
                    start_i = i
                    b_depth = 1
                    i += 1
                    while i < n and b_depth > 0:
                        if seg[i] == ch:
                            b_depth += 1
                        elif seg[i] == close_ch:
                            b_depth -= 1
                        i += 1
                    inner = seg[start_i + 1:i - 1]
                    processed_inner = _process_comma_list(inner)
                    buf.append(ch + processed_inner + close_ch)
                else:
                    buf.append(ch)
                    i += 1

            reconstructed = "".join(buf)

            # Check if this reconstructed segment has a top-level '=' (not part of ==, !=, <=, >=)
            # Find '=' at depth 0
            eq_pos = -1
            b_depth = 0
            for idx, c in enumerate(reconstructed):
                if c in '([{':
                    b_depth += 1
                elif c in ')]}':
                    b_depth -= 1
                elif c == '=' and b_depth == 0:
                    # Check not ==, <=, >=, !=
                    prev_c = reconstructed[idx - 1] if idx > 0 else ''
                    next_c = reconstructed[idx + 1] if idx + 1 < len(reconstructed) else ''
                    if prev_c not in ('=', '<', '>', '!', ':') and next_c not in ('=',):
                        eq_pos = idx
                        break

            if eq_pos != -1:
                lhs = reconstructed[:eq_pos].strip()
                rhs = reconstructed[eq_pos + 1:].strip()
                return f"Eq({lhs}, {rhs})"

            return reconstructed

        def _process_comma_list(content: str) -> str:
            # Split by comma at top level
            parts = []
            curr = []
            depth = 0
            for ch in content:
                if ch in '([{':
                    depth += 1
                    curr.append(ch)
                elif ch in ')]}':
                    depth -= 1
                    curr.append(ch)
                elif ch == ',' and depth == 0:
                    parts.append("".join(curr))
                    curr = []
                else:
                    curr.append(ch)
            if curr:
                parts.append("".join(curr))

            processed_parts = [_process_segment(p) for p in parts]
            return ", ".join(processed_parts)

        return _process_segment(s)

    @classmethod
    def _transform_logic_set_ops(cls, text: str) -> str:
        """
        Recursively transform infix logic and set operations into SymPy function calls.
        e.g., A ∩ B -> Intersection(A, B)
              A ∪ B -> Union(A, B)
              x ∈ ℝ -> Contains(x, Reals)
              x ∉ ℝ -> Not(Contains(x, Reals))
              A ⊂ B -> Subset(A, B)
              A ⊃ B -> Superset(A, B)
              P ⇒ Q -> Implies(P, Q)
              x ≡ y -> Eq(x, y)
        """
        ops = [
            ('⇒', lambda parts: f'Implies({parts[0]}, {parts[1]})' if len(parts) == 2 else ' ⇒ '.join(parts)),
            ('≡', lambda parts: f'Eq({parts[0]}, {parts[1]})' if len(parts) == 2 else ' ≡ '.join(parts)),
            ('∈', lambda parts: f'Contains({parts[0]}, {parts[1]})' if len(parts) == 2 else ' ∈ '.join(parts)),
            ('∉', lambda parts: f'Not(Contains({parts[0]}, {parts[1]}))' if len(parts) == 2 else ' ∉ '.join(parts)),
            ('⊂', lambda parts: f'Subset({parts[0]}, {parts[1]})' if len(parts) == 2 else ' ⊂ '.join(parts)),
            ('⊃', lambda parts: f'Superset({parts[0]}, {parts[1]})' if len(parts) == 2 else ' ⊃ '.join(parts)),
            ('∪', lambda parts: 'Union(' + ', '.join(parts) + ')'),
            ('∩', lambda parts: 'Intersection(' + ', '.join(parts) + ')'),
        ]

        def split_top_level(t, op):
            parts = []
            depth = 0
            cur = []
            i = 0
            n = len(t)
            op_len = len(op)
            while i < n:
                ch = t[i]
                if ch in '([{':
                    depth += 1
                    cur.append(ch)
                    i += 1
                elif ch in ')]}':
                    depth = max(0, depth - 1)
                    cur.append(ch)
                    i += 1
                elif depth == 0 and t[i:i+op_len] == op:
                    parts.append(''.join(cur).strip())
                    cur = []
                    i += op_len
                else:
                    cur.append(ch)
                    i += 1
            parts.append(''.join(cur).strip())
            return parts

        def strip_outer_parens(t):
            t = t.strip()
            if t.startswith('(') and t.endswith(')'):
                depth = 0
                has_top_comma = False
                for i, c in enumerate(t):
                    if c == '(': depth += 1
                    elif c == ')': depth -= 1
                    elif c == ',' and depth == 1:
                        has_top_comma = True
                    if depth == 0 and i < len(t) - 1:
                        return t
                if not has_top_comma and depth == 0:
                    return strip_outer_parens(t[1:-1])
            return t

        def recurse(t):
            t = strip_outer_parens(t)
            for op, formatter in ops:
                parts = split_top_level(t, op)
                if len(parts) > 1:
                    transformed_parts = [recurse(p) for p in parts]
                    return formatter(transformed_parts)

            # Check if t contains bracketed/parenthesized expressions
            has_bracket = any(c in t for c in '([{')
            if has_bracket:
                result = []
                i = 0
                n = len(t)
                while i < n:
                    ch = t[i]
                    if ch in '([{':
                        close_ch = ')' if ch == '(' else (']' if ch == '[' else '}')
                        depth = 1
                        j = i + 1
                        while j < n and depth > 0:
                            if t[j] == ch:
                                depth += 1
                            elif t[j] == close_ch:
                                depth -= 1
                            j += 1
                        inner = t[i+1:j-1]
                        inner_items = split_top_level(inner, ',')
                        if len(inner_items) > 1:
                            inner_transformed = ', '.join(recurse(item) for item in inner_items)
                        else:
                            inner_transformed = recurse(inner)
                        result.append(ch + inner_transformed + (close_ch if depth == 0 else ''))
                        i = j
                    else:
                        result.append(ch)
                        i += 1
                return ''.join(result)
            return t

        return recurse(text)

    @classmethod
    def parse(cls, input_str: str, local_dict: dict = None) -> ParseResult:
        """
        Main parse method. Converts user text into a ParseResult containing SymPy expression or command info.
        """
        raw = input_str.strip()
        if not raw:
            return ParseResult(raw, "")

        # Check for help query: ? topic
        if raw.startswith('?'):
            topic = raw[1:].strip()
            return ParseResult(raw, raw, is_command=True, command_name='help', command_args=[topic])

        # Check for system commands e.g. clear, reset, whos, help
        if raw in ('clear', 'reset', 'restart'):
            return ParseResult(raw, raw, is_command=True, command_name='reset')
        if raw in ('whos', 'vars', 'symbols'):
            return ParseResult(raw, raw, is_command=True, command_name='whos')

        # Clean trailing colon (suppress output) or semicolon
        clean_raw = raw
        suppress_output = False
        if clean_raw.endswith(':'):
            suppress_output = True
            clean_raw = clean_raw[:-1].strip()
        elif clean_raw.endswith(';'):
            clean_raw = clean_raw[:-1].strip()

        # Check for with(Package) command e.g. with(LinearAlgebra) or with(Student[Calculus1])
        with_match = re.match(r'^with\s*\(\s*([a-zA-Z0-9_\[\]]+)\s*\)$', clean_raw)
        if with_match:
            pkg_name = with_match.group(1)
            return ParseResult(raw, raw, is_command=True, command_name='with', command_args=[pkg_name], suppress_output=suppress_output)

        # Check for unassign('x') or unassign(x)
        unassign_match = re.match(r'^unassign\s*\((.*?)\)$', clean_raw)
        if unassign_match:
            vars_str = unassign_match.group(1)
            var_names = [v.strip().strip("'\"") for v in vars_str.split(',') if v.strip()]
            return ParseResult(raw, raw, is_command=True, command_name='unassign', command_args=var_names, suppress_output=suppress_output)

        # Preprocess
        preprocessed = cls.preprocess_string(clean_raw, local_dict=local_dict)

        # Check for assignment
        is_assign, assign_var, assign_args, rhs_str = cls.check_assignment(preprocessed)

        # Check for equation in RHS or standalone
        if is_assign:
            rhs_str = cls._transform_logic_set_ops(rhs_str)
            expr_to_parse = cls.convert_equations_to_eq(rhs_str)
        else:
            preprocessed = cls._transform_logic_set_ops(preprocessed)
            expr_to_parse = cls.convert_equations_to_eq(preprocessed)

        # Prepare context
        context = dict(cls.BUILTIN_ALIASES)
        if local_dict:
            context.update(local_dict)
        context['Eq'] = SafeEq

        # If 'i' or 'j' is used as a dummy variable in summation/product/diff/integrate limits,
        # treat it as a Symbol rather than the imaginary constant sp.I
        if re.search(r'\b(?:summation|Sum|product|Product|integrate|diff)\b.*?\(\s*[ij]\b|\b[ij]\s*=', expr_to_parse):
            if not local_dict or 'i' not in local_dict:
                context['i'] = sp.Symbol('i')
            if not local_dict or 'j' not in local_dict:
                context['j'] = sp.Symbol('j')

        # Auto-register any function call with comma-separated arguments (e.g. f(a, b) or two_comp_repr(-5, 8))
        # as a Function to prevent implicit_multiplication_application from constructing Mul(Symbol, Tuple)
        # which causes SymPyDeprecationWarning: "Using non-Expr arguments in Mul is deprecated (Tuple)".
        for fn_candidate in re.findall(r'\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\([^)]*,', expr_to_parse):
            if fn_candidate not in context and not hasattr(sp, fn_candidate):
                context[fn_candidate] = sp.Function(fn_candidate)

        # Parse with SymPy
        # Suppress SymPyDeprecationWarning: implicit_multiplication_application can produce
        # Pow(Symbol, Tuple) for multi-arg calls like f(a, b)^n — this is a known SymPy
        # transformer edge case. We suppress rather than crash.
        import warnings as _warnings
        try:
            with _warnings.catch_warnings():
                # Suppress SymPyDeprecationWarning: implicit_multiplication_application can produce
                # Pow(Symbol, Tuple) or Mul(Symbol, Tuple) for multi-arg calls like f(a, b)^n
                _warnings.filterwarnings('ignore', category=SymPyDeprecationWarning)
                _warnings.filterwarnings('ignore', message='.*non-Expr.*')
                _warnings.filterwarnings('ignore', category=DeprecationWarning)
                sympy_expr = parse_expr(
                    expr_to_parse,
                    local_dict=context,
                    transformations=cls.TRANSFORMATIONS,
                    evaluate=True
                )
                if sympy_expr in (sp.true, sp.false) and 'Eq(' in expr_to_parse:
                    try:
                        sympy_expr = parse_expr(
                            expr_to_parse,
                            local_dict=context,
                            transformations=cls.TRANSFORMATIONS,
                            evaluate=False
                        )
                    except Exception:
                        pass
        except Exception as e:
            # Try without evaluate in case it's a raw un-evaluated object or special structure
            try:
                with _warnings.catch_warnings():
                    _warnings.filterwarnings('ignore', category=SymPyDeprecationWarning)
                    _warnings.filterwarnings('ignore', message='.*non-Expr.*')
                    _warnings.filterwarnings('ignore', category=DeprecationWarning)
                    sympy_expr = parse_expr(
                        expr_to_parse,
                        local_dict=context,
                        transformations=cls.TRANSFORMATIONS,
                        evaluate=False
                    )
            except Exception:
                # Re-raise original exception for clear error reporting
                raise e

        # Check if this expression is a plot command
        is_plot = False
        plot_args = {}
        if isinstance(sympy_expr, sp.Function) and sympy_expr.func.__name__ in ('plot', 'plot_parametric', 'plot_polar'):
            is_plot = True
            plot_args = {'type': sympy_expr.func.__name__, 'args': sympy_expr.args}
        elif hasattr(sympy_expr, '__class__') and 'Plot' in sympy_expr.__class__.__name__:
            is_plot = True
            plot_args = {'plot_obj': sympy_expr}

        return ParseResult(
            raw_input=raw,
            processed_str=expr_to_parse,
            sympy_expr=sympy_expr,
            is_assignment=is_assign,
            assign_var=assign_var,
            assign_args=assign_args,
            is_plot=is_plot,
            plot_args=plot_args,
            suppress_output=suppress_output
        )
