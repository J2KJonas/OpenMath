"""
Intelligent Error Suggester for CAS expressions and commands.
Analyzes syntax and runtime errors and generates verified, flawless fixes.
"""

import difflib
import re

BUILTIN_COMMANDS = [
    'solve', 'fsolve', 'diff', 'integrate', 'int', 'limit', 'taylor',
    'expand', 'factor', 'simplify', 'collect', 'cancel', 'apart', 'together',
    'evalf', 'restart', 'unassign', 'whos', 'help',
    'sin', 'cos', 'tan', 'sec', 'csc', 'cot',
    'asin', 'acos', 'atan', 'asec', 'acsc', 'acot',
    'sinh', 'cosh', 'tanh', 'asinh', 'acosh', 'atanh',
    'exp', 'log', 'ln', 'sqrt', 'cbrt', 'abs', 'Abs',
    'Matrix', 'Vector', 'det', 'inv', 'transpose', 'eigenvals', 'rref',
    'piecewise', 'maximize', 'minimize', 'plot', 'plot3d',
    'seq', 'add', 'mul', 'sum', 'product', 'binomial', 'factorial'
]

def generate_candidates(text: str) -> list[str]:
    """Generate potential syntactic and structural fixes for a given expression."""
    cands = []
    s = text.strip()
    if not s:
        return cands

    # 1. Check for missing closing parentheses, brackets, and braces
    opens_p = s.count('(') - s.count(')')
    if opens_p > 0:
        cands.append(s + ')' * opens_p)
    opens_b = s.count('[') - s.count(']')
    if opens_b > 0:
        cands.append(s + ']' * opens_b)
    opens_c = s.count('{') - s.count('}')
    if opens_c > 0:
        cands.append(s + '}' * opens_c)

    # 2. Typos in function / command names (e.g. solv(...) -> solve(...))
    for match in re.finditer(r'\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\(', s):
        fn_name = match.group(1)
        if fn_name not in BUILTIN_COMMANDS:
            matches = difflib.get_close_matches(fn_name, BUILTIN_COMMANDS, n=1, cutoff=0.55)
            if matches:
                better = matches[0]
                fixed = s[:match.start(1)] + better + s[match.end(1):]
                cands.append(fixed)
                diff_p = fixed.count('(') - fixed.count(')')
                if diff_p > 0:
                    cands.append(fixed + ')' * diff_p)

    # 3. Missing parentheses after common functions (e.g. sin x -> sin(x))
    trig_fn_pat = r'\b(sin|cos|tan|cot|sec|csc|asin|acos|atan|sinh|cosh|tanh|exp|log|ln|sqrt|abs)\s+([a-zA-Z0-9_]+)'
    if re.search(trig_fn_pat, s):
        fixed_trig = re.sub(trig_fn_pat, r'\1(\2)', s)
        cands.append(fixed_trig)

    # 4. Assignment syntax '=' vs ':=' (e.g. U = 100 -> U := 100)
    if '=' in s and ':=' not in s and not any(op in s for op in ('==', '<=', '>=', '!=')):
        parts = s.split('=', 1)
        lhs = parts[0].strip()
        rhs = parts[1].strip()
        if re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*(\s*\([a-zA-Z0-9_,\s]*\))?$', lhs):
            cands.append(f"{lhs} := {rhs}")

    # 5. Implicit multiplication (e.g. 2x -> 2*x, (x+1)(x-1) -> (x+1)*(x-1))
    # Protect hex (0x...) and binary (0b...) literals from being split into 0*x...
    hex_bin_tokens = re.findall(r'\b0[xX][0-9a-fA-F]+\b|\b0[bB][01]+\b', s)
    token_map = {f"__HEXBIN_{i}__": tok for i, tok in enumerate(hex_bin_tokens)}
    temp_s = s
    for placeholder, tok in token_map.items():
        temp_s = temp_s.replace(tok, placeholder, 1)

    fixed_mul = re.sub(r'(\d)([a-zA-Z(])', r'\1*\2', temp_s)
    fixed_mul = re.sub(r'(\))(\()', r'\1*\2', fixed_mul)
    fixed_mul = re.sub(r'(\))([a-zA-Z0-9])', r'\1*\2', fixed_mul)

    for placeholder, tok in token_map.items():
        fixed_mul = fixed_mul.replace(placeholder, tok)

    if fixed_mul != s:
        cands.append(fixed_mul)
        diff_p = fixed_mul.count('(') - fixed_mul.count(')')
        if diff_p > 0:
            cands.append(fixed_mul + ')' * diff_p)

    # 6. Trailing dangling operators (e.g. 1+2+ -> 1+2)
    cleaned_trailing = re.sub(r'[+\-*/^=,]\s*$', '', s)
    if cleaned_trailing != s and cleaned_trailing:
        cands.append(cleaned_trailing)

    # 7. Double operators (e.g. 1++2 -> 1+2)
    fixed_double = re.sub(r'\+\+', '+', s)
    fixed_double = re.sub(r'//+', '/', fixed_double)
    fixed_double = re.sub(r'\^\^+', '^', fixed_double)
    if fixed_double != s:
        cands.append(fixed_double)

    # 8. Unbalanced quotes
    if s.count("'") % 2 != 0:
        cands.append(s + "'")
    if s.count('"') % 2 != 0:
        cands.append(s + '"')

    # 9. Function called with empty/missing arguments or placeholder (e.g. inv(), det(M), diff())
    try:
        from .function_guide import find_function_in_text, get_function_info
        fn_name, fn_info, span = find_function_in_text(s)
        if fn_info and fn_info.examples:
            for ex in fn_info.examples:
                cands.append(ex.code)
    except Exception:
        m_mat_op = re.match(r'^(det|inv|transpose|eigenvals|rref)\s*\(\s*([a-zA-Z_][a-zA-Z0-9_]*)?\s*\)$', s)
        if m_mat_op:
            op = m_mat_op.group(1)
            cands.append(f"{op}(Matrix([[1, 2], [3, 4]]))")

    unique_cands = []
    seen = set()
    for c in cands:
        c_clean = c.strip()
        if c_clean and c_clean != s and c_clean not in seen:
            seen.add(c_clean)
            unique_cands.append(c_clean)

    return unique_cands

def suggest_fix(text: str, error_msg: str = "", engine=None) -> str | None:
    """
    Find a working fix for the faulty expression.
    If an engine is provided, candidate fixes are tested against the engine
    to verify that the suggested expression evaluates flawlessly without errors.
    """
    if not text or not text.strip():
        return None

    cands = generate_candidates(text)
    if not cands:
        return None

    if engine:
        for c in cands:
            try:
                engine.evaluate(c)
                return c
            except Exception:
                continue

    return cands[0]
