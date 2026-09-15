"""
Function Guide and Examples Catalog for OpenMath CAS.
Provides comprehensive metadata, syntax specifications, descriptions,
and verified working examples for mathematical functions and commands.
Enables rich right-click context menu suggestions, error recovery,
autocomplete hints, and one-click example insertion.
"""

from dataclasses import dataclass
import re


@dataclass
class FunctionExample:
    label: str
    code: str


@dataclass
class FunctionInfo:
    name: str
    syntax: str
    category: str
    description: str
    examples: list[FunctionExample]

    @property
    def primary_example(self) -> str:
        return self.examples[0].code if self.examples else f"{self.name}()"


# Comprehensive registry of mathematical functions, syntax, and examples
CATALOG: list[FunctionInfo] = [
    # -------------------------------------------------------------
    # Linear Algebra (Matrices & Vectors)
    # -------------------------------------------------------------
    FunctionInfo(
        name="inv",
        syntax="inv(matrix)",
        category="Matrices & Vectors",
        description="Compute the inverse of an invertible square matrix.",
        examples=[
            FunctionExample("2×2 Matrix Inverse", "inv(Matrix([[1, 2], [3, 4]]))"),
            FunctionExample("3×3 Matrix Inverse", "inv(Matrix([[1, 0, 2], [2, -1, 3], [4, 1, 8]]))"),
            FunctionExample("Symbolic 2×2 Matrix", "inv(Matrix([[a, b], [c, d]]))"),
        ]
    ),
    FunctionInfo(
        name="det",
        syntax="det(matrix)",
        category="Matrices & Vectors",
        description="Compute the scalar determinant of a square matrix.",
        examples=[
            FunctionExample("2×2 Determinant", "det(Matrix([[1, 2], [3, 4]]))"),
            FunctionExample("3×3 Determinant", "det(Matrix([[1, 2, 3], [0, 1, 4], [5, 6, 0]]))"),
            FunctionExample("Symbolic Determinant", "det(Matrix([[a, b], [c, d]]))"),
        ]
    ),
    FunctionInfo(
        name="transpose",
        syntax="transpose(matrix)",
        category="Matrices & Vectors",
        description="Compute the transpose of a matrix (rows become columns).",
        examples=[
            FunctionExample("2×2 Transpose", "transpose(Matrix([[1, 2], [3, 4]]))"),
            FunctionExample("2×3 Transpose", "transpose(Matrix([[1, 2, 3], [4, 5, 6]]))"),
        ]
    ),
    FunctionInfo(
        name="Matrix",
        syntax="Matrix([[r1, ...], [r2, ...]])",
        category="Matrices & Vectors",
        description="Construct a 2D mathematical matrix.",
        examples=[
            FunctionExample("2×2 Matrix", "Matrix([[1, 2], [3, 4]])"),
            FunctionExample("3×3 Identity", "Matrix([[1, 0, 0], [0, 1, 0], [0, 0, 1]])"),
            FunctionExample("3×1 Column Vector", "Matrix([[1], [2], [3]])"),
        ]
    ),
    FunctionInfo(
        name="Vector",
        syntax="Vector([v1, v2, ...])",
        category="Matrices & Vectors",
        description="Construct a column vector.",
        examples=[
            FunctionExample("3D Column Vector", "Vector([1, 2, 3])"),
            FunctionExample("Symbolic Vector", "Vector([x, y, z])"),
        ]
    ),
    FunctionInfo(
        name="rref",
        syntax="rref(matrix)",
        category="Matrices & Vectors",
        description="Compute the Reduced Row Echelon Form of a matrix.",
        examples=[
            FunctionExample("2×3 Augmented Matrix", "rref(Matrix([[1, 2, -1], [2, 3, 1]]))"),
            FunctionExample("3×3 Matrix RREF", "rref(Matrix([[1, 2, 3], [4, 5, 6], [7, 8, 9]]))"),
        ]
    ),
    FunctionInfo(
        name="eigenvals",
        syntax="eigenvals(matrix)",
        category="Matrices & Vectors",
        description="Compute eigenvalues and algebraic multiplicities of a matrix.",
        examples=[
            FunctionExample("2×2 Eigenvalues", "eigenvals(Matrix([[1, 2], [3, 4]]))"),
            FunctionExample("Symmetric Matrix", "eigenvals(Matrix([[2, 1], [1, 2]]))"),
        ]
    ),
    FunctionInfo(
        name="eigenvects",
        syntax="eigenvects(matrix)",
        category="Matrices & Vectors",
        description="Compute eigenvectors, eigenvalues, and multiplicities.",
        examples=[
            FunctionExample("2×2 Eigenvectors", "eigenvects(Matrix([[1, 2], [3, 4]]))"),
            FunctionExample("Diagonal Matrix", "eigenvects(Matrix([[3, 0], [0, 5]]))"),
        ]
    ),
    FunctionInfo(
        name="rank",
        syntax="rank(matrix)",
        category="Matrices & Vectors",
        description="Compute the rank (number of linearly independent rows) of a matrix.",
        examples=[
            FunctionExample("Rank of 2×2 Matrix", "rank(Matrix([[1, 2], [2, 4]]))"),
            FunctionExample("Rank of 3×3 Matrix", "rank(Matrix([[1, 2, 3], [4, 5, 6], [7, 8, 9]]))"),
        ]
    ),
    FunctionInfo(
        name="trace",
        syntax="trace(matrix)",
        category="Matrices & Vectors",
        description="Compute the trace (sum of main diagonal elements) of a matrix.",
        examples=[
            FunctionExample("2×2 Trace", "trace(Matrix([[1, 2], [3, 4]]))"),
            FunctionExample("3×3 Trace", "trace(Matrix([[5, 0, 1], [2, 3, 4], [1, 1, 2]]))"),
        ]
    ),
    FunctionInfo(
        name="nullspace",
        syntax="nullspace(matrix)",
        category="Matrices & Vectors",
        description="Compute a basis for the null space (kernel) of a matrix.",
        examples=[
            FunctionExample("2×2 Null Space", "nullspace(Matrix([[1, 2], [2, 4]]))"),
            FunctionExample("2×3 Matrix Null Space", "nullspace(Matrix([[1, 1, 1], [2, 2, 2]]))"),
        ]
    ),
    FunctionInfo(
        name="eye",
        syntax="eye(n)",
        category="Matrices & Vectors",
        description="Generate an n × n identity matrix.",
        examples=[
            FunctionExample("3×3 Identity Matrix", "eye(3)"),
            FunctionExample("4×4 Identity Matrix", "eye(4)"),
        ]
    ),
    FunctionInfo(
        name="zeros",
        syntax="zeros(rows, cols)",
        category="Matrices & Vectors",
        description="Generate a matrix of all zeros.",
        examples=[
            FunctionExample("2×3 Zero Matrix", "zeros(2, 3)"),
            FunctionExample("3×3 Zero Matrix", "zeros(3, 3)"),
        ]
    ),

    # -------------------------------------------------------------
    # Calculus & Analysis
    # -------------------------------------------------------------
    FunctionInfo(
        name="diff",
        syntax="diff(f, x, [n])",
        category="Calculus & Analysis",
        description="Differentiate an expression with respect to a variable.",
        examples=[
            FunctionExample("Polynomial Derivative", "diff(x^3 - 5*x^2 + 2, x)"),
            FunctionExample("Trigonometric Product", "diff(sin(x)*exp(x), x)"),
            FunctionExample("Second Derivative", "diff(x^5, x, 2)"),
        ]
    ),
    FunctionInfo(
        name="integrate",
        syntax="integrate(f, x) or integrate(f, (x, a, b))",
        category="Calculus & Analysis",
        description="Compute indefinite or definite symbolic integrals.",
        examples=[
            FunctionExample("Indefinite Integral", "integrate(x^2 + 3*x, x)"),
            FunctionExample("Definite Integral", "integrate(sin(x), (x, 0, pi))"),
            FunctionExample("Improper Integral", "integrate(exp(-x), (x, 0, oo))"),
        ]
    ),
    FunctionInfo(
        name="limit",
        syntax="limit(f, x = c, [dir='+'|'-'])",
        category="Calculus & Analysis",
        description="Compute the limit of an expression as x approaches c.",
        examples=[
            FunctionExample("Standard Limit", "limit(sin(x)/x, x = 0)"),
            FunctionExample("Limit at Infinity", "limit((1 + 1/x)^x, x = oo)"),
            FunctionExample("One-sided Limit", "limit(1/x, x = 0, dir=\'+\')"),
        ]
    ),
    FunctionInfo(
        name="taylor",
        syntax="taylor(f, x = x0, order)",
        category="Calculus & Analysis",
        description="Compute the Taylor series expansion around x0.",
        examples=[
            FunctionExample("Taylor Series sin(x)", "taylor(sin(x), x = 0, 6)"),
            FunctionExample("Taylor Series exp(x)", "taylor(exp(x), x = 0, 5)"),
        ]
    ),
    FunctionInfo(
        name="series",
        syntax="series(f, x, x0, order)",
        category="Calculus & Analysis",
        description="Compute power series expansion of f.",
        examples=[
            FunctionExample("Series of cos(x)", "series(cos(x), x, 0, 6)"),
            FunctionExample("Series of ln(1 + x)", "series(ln(1 + x), x, 0, 5)"),
        ]
    ),
    FunctionInfo(
        name="Sum",
        syntax="Sum(expr, (n, a, b))",
        category="Calculus & Analysis",
        description="Represent or evaluate symbolic summations.",
        examples=[
            FunctionExample("Infinite Series (Basel Problem)", "Sum(1/n^2, (n, 1, oo))"),
            FunctionExample("Finite Arithmetic Sum", "Sum(k, (k, 1, 100))"),
        ]
    ),
    FunctionInfo(
        name="Product",
        syntax="Product(expr, (n, a, b))",
        category="Calculus & Analysis",
        description="Represent or evaluate symbolic products.",
        examples=[
            FunctionExample("Factorial Product", "Product(n, (n, 1, 5))"),
            FunctionExample("Infinite Product", "Product(1 - 1/n^2, (n, 2, oo))"),
        ]
    ),
    FunctionInfo(
        name="dsolve",
        syntax="dsolve(equation, y(x))",
        category="Calculus & Analysis",
        description="Solve ordinary differential equations symbolically.",
        examples=[
            FunctionExample("First Order ODE", "dsolve(diff(y(x), x) - y(x) = 0, y(x))"),
            FunctionExample("Harmonic Oscillator", "dsolve(diff(y(x), x, 2) + y(x) = 0, y(x))"),
        ]
    ),

    # -------------------------------------------------------------
    # Solvers & Algebra
    # -------------------------------------------------------------
    FunctionInfo(
        name="solve",
        syntax="solve(equation, var)",
        category="Solvers & Algebra",
        description="Solve equations or systems of equations symbolically.",
        examples=[
            FunctionExample("Quadratic Equation", "solve(x^2 - 5*x + 6 = 0, x)"),
            FunctionExample("Linear System", "solve([x + y = 10, x - y = 2], [x, y])"),
            FunctionExample("Trigonometric Equation", "solve(sin(x) = 1/2, x)"),
        ]
    ),
    FunctionInfo(
        name="fsolve",
        syntax="fsolve(equation, var = guess)",
        category="Solvers & Algebra",
        description="Solve equations numerically using high-precision root finding.",
        examples=[
            FunctionExample("Transcendental Root", "fsolve(cos(x) = x, x = 0.5)"),
            FunctionExample("Quintic Polynomial", "fsolve(x^5 - x - 1 = 0, x = 1.0)"),
        ]
    ),
    FunctionInfo(
        name="factor",
        syntax="factor(expr)",
        category="Solvers & Algebra",
        description="Factor polynomials into irreducible components.",
        examples=[
            FunctionExample("Cubic Polynomial", "factor(x^3 - 3*x^2 + 3*x - 1)"),
            FunctionExample("Difference of Squares", "factor(x^4 - 16)"),
            FunctionExample("Trigonometric Difference", "factor(sin(x)^2 - cos(x)^2)"),
        ]
    ),
    FunctionInfo(
        name="expand",
        syntax="expand(expr)",
        category="Solvers & Algebra",
        description="Expand products and powers into sums of monomials.",
        examples=[
            FunctionExample("Binomial Expansion", "expand((x + y)^3)"),
            FunctionExample("Polynomial Product", "expand((x - 1)*(x + 2)*(x - 3))"),
            FunctionExample("Trigonometric Expansion", "expand(sin(x + y), trig=True)"),
        ]
    ),
    FunctionInfo(
        name="simplify",
        syntax="simplify(expr)",
        category="Solvers & Algebra",
        description="Simplify mathematical expressions using algebraic identities.",
        examples=[
            FunctionExample("Trigonometric Identity", "simplify(sin(x)^2 + cos(x)^2)"),
            FunctionExample("Rational Expression", "simplify((x^2 - 1)/(x - 1))"),
            FunctionExample("Exponential Law", "simplify(exp(x)*exp(y))"),
        ]
    ),
    FunctionInfo(
        name="collect",
        syntax="collect(expr, var)",
        category="Solvers & Algebra",
        description="Collect terms with matching powers of a variable.",
        examples=[
            FunctionExample("Collect in x", "collect(x*y + x - 3 + 2*x^2, x)"),
        ]
    ),
    FunctionInfo(
        name="apart",
        syntax="apart(expr, [x])",
        category="Solvers & Algebra",
        description="Compute partial fraction decomposition of a rational function.",
        examples=[
            FunctionExample("Partial Fractions", "apart(1/((x + 1)*(x + 2)), x)"),
            FunctionExample("Rational Function", "apart((x^2 + 1)/(x*(x - 1)), x)"),
        ]
    ),
    FunctionInfo(
        name="together",
        syntax="together(expr)",
        category="Solvers & Algebra",
        description="Combine rational expressions over a common denominator.",
        examples=[
            FunctionExample("Combine Fractions", "together(1/x + 1/(x + 1))"),
        ]
    ),
    FunctionInfo(
        name="evalf",
        syntax="evalf(expr, [digits=10])",
        category="Solvers & Algebra",
        description="Evaluate expression numerically to arbitrary precision.",
        examples=[
            FunctionExample("Pi to 15 digits", "evalf(pi, 15)"),
            FunctionExample("Square Root of 2", "evalf(sqrt(2), 20)"),
        ]
    ),

    # -------------------------------------------------------------
    # Plots & Visualizations
    # -------------------------------------------------------------
    FunctionInfo(
        name="plot",
        syntax="plot(expr, x = a .. b)",
        category="Plots & Visualizations",
        description="Render a 2D function graph with coordinate axes.",
        examples=[
            FunctionExample("Single Function", "plot(sin(x), x = -2*pi .. 2*pi)"),
            FunctionExample("Multiple Curves", "plot([sin(x), cos(x)], x = -pi .. pi)"),
            FunctionExample("Rational Function", "plot(1/(x^2 + 1), x = -4 .. 4)"),
        ]
    ),
    FunctionInfo(
        name="plot3d",
        syntax="plot3d(expr, x = a..b, y = c..d)",
        category="Plots & Visualizations",
        description="Render an interactive 3D surface plot.",
        examples=[
            FunctionExample("Saddle Surface", "plot3d(x^2 - y^2, x = -2 .. 2, y = -2 .. 2)"),
            FunctionExample("Wave Surface", "plot3d(sin(x)*cos(y), x = -pi .. pi, y = -pi .. pi)"),
        ]
    ),
    FunctionInfo(
        name="polygonOmråde",
        syntax="polygonOmråde(inequalities, x = a..b, y = c..d)",
        category="Plots & Visualizations",
        description="Plot linear programming feasible polygon bounded by linear inequalities.",
        examples=[
            FunctionExample("Feasible Region", "polygonOmråde([x >= 0, y >= 0, x + y <= 5], x = 0 .. 6, y = 0 .. 6)"),
        ]
    ),

    # -------------------------------------------------------------
    # Embedded Systems & Bit Manipulation
    # -------------------------------------------------------------
    FunctionInfo(
        name="to_bin",
        syntax="to_bin(val, bits=8)",
        category="Embedded Systems",
        description="Format integer as a fixed-width binary literal.",
        examples=[
            FunctionExample("8-bit Binary", "to_bin(42, 8)"),
            FunctionExample("16-bit Binary", "to_bin(0xABCD, 16)"),
        ]
    ),
    FunctionInfo(
        name="to_hex",
        syntax="to_hex(val, bits=8)",
        category="Embedded Systems",
        description="Format integer as a fixed-width hexadecimal literal.",
        examples=[
            FunctionExample("8-bit Hex", "to_hex(255, 8)"),
            FunctionExample("32-bit Hex", "to_hex(1048576, 32)"),
        ]
    ),
    FunctionInfo(
        name="twos_comp",
        syntax="twos_comp(val, bits=8)",
        category="Embedded Systems",
        description="Compute two's complement integer representation.",
        examples=[
            FunctionExample("8-bit Two's Complement", "twos_comp(-5, 8)"),
            FunctionExample("16-bit Two's Complement", "twos_comp(-42, 16)"),
        ]
    ),
    FunctionInfo(
        name="bit_get",
        syntax="bit_get(val, bit_pos)",
        category="Embedded Systems",
        description="Read bit value (0 or 1) at specified index.",
        examples=[
            FunctionExample("Get bit 1", "bit_get(0b1010, 1)"),
            FunctionExample("Get bit 7", "bit_get(0x80, 7)"),
        ]
    ),
    FunctionInfo(
        name="bit_set",
        syntax="bit_set(val, bit_pos)",
        category="Embedded Systems",
        description="Set bit at specified index to 1.",
        examples=[
            FunctionExample("Set bit 3", "bit_set(0b0000, 3)"),
            FunctionExample("Set bit on register", "bit_set(reg, 2)"),
        ]
    ),
    FunctionInfo(
        name="bit_clear",
        syntax="bit_clear(val, bit_pos)",
        category="Embedded Systems",
        description="Clear bit at specified index to 0.",
        examples=[
            FunctionExample("Clear bit 2", "bit_clear(0b1111, 2)"),
            FunctionExample("Clear bit on register", "bit_clear(reg, 0)"),
        ]
    ),
    FunctionInfo(
        name="bit_toggle",
        syntax="bit_toggle(val, bit_pos)",
        category="Embedded Systems",
        description="Toggle/invert bit at specified index.",
        examples=[
            FunctionExample("Toggle bit 1", "bit_toggle(0b1010, 1)"),
        ]
    ),
    FunctionInfo(
        name="voltage_divider",
        syntax="voltage_divider(Vin, R1, R2)",
        category="Embedded Systems",
        description="Calculate output voltage of a resistive divider.",
        examples=[
            FunctionExample("Equal 10k Resistors", "voltage_divider(5, 10000, 10000)"),
            FunctionExample("3.3V to 1.8V Step Down", "voltage_divider(3.3, 1500, 1800)"),
        ]
    ),
    FunctionInfo(
        name="led_resistor",
        syntax="led_resistor(Vs, Vf, If)",
        category="Embedded Systems",
        description="Calculate current-limiting series resistor for an LED.",
        examples=[
            FunctionExample("5V Supply, Red LED (2V, 20mA)", "led_resistor(5, 2.0, 0.02)"),
            FunctionExample("3.3V Supply, Blue LED (3V, 15mA)", "led_resistor(3.3, 3.0, 0.015)"),
        ]
    ),
    FunctionInfo(
        name="rc_cutoff",
        syntax="rc_cutoff(R, C)",
        category="Embedded Systems",
        description="Calculate RC low-pass/high-pass filter -3dB cutoff frequency in Hz.",
        examples=[
            FunctionExample("1kΩ and 1µF Cutoff", "rc_cutoff(1000, 1e-6)"),
            FunctionExample("10kΩ and 100nF Cutoff", "rc_cutoff(10000, 100e-9)"),
        ]
    ),
]

_LOOKUP: dict[str, FunctionInfo] = {item.name.lower(): item for item in CATALOG}

# Synonyms and aliases
_ALIASES: dict[str, str] = {
    "determinant": "det",
    "inverse": "inv",
    "int": "integrate",
    "differentiate": "diff",
    "derivative": "diff",
    "integral": "integrate",
    "matrix": "Matrix",
    "vector": "Vector",
    "sum": "Sum",
    "product": "Product",
    "taylorseries": "taylor",
    "seriesexpansion": "series",
    "two_comp": "twos_comp",
    "two_comp_repr": "twos_comp",
    "twos_comp_repr": "twos_comp",
}


def get_function_info(name: str) -> FunctionInfo | None:
    """Look up function guide info by name or alias (case-insensitive)."""
    clean = name.strip().lower()
    target = _ALIASES.get(clean, clean)
    return _LOOKUP.get(target)


def get_categories_dict() -> dict[str, list[FunctionInfo]]:
    """Return all catalogued functions grouped by category."""
    grouped: dict[str, list[FunctionInfo]] = {}
    for item in CATALOG:
        grouped.setdefault(item.category, []).append(item)
    return grouped


def find_function_in_text(text: str, cursor_pos: int = -1) -> tuple[str, FunctionInfo | None, tuple[int, int]]:
    """
    Given an input string and optional cursor position, find the targeted function name,
    its FunctionInfo metadata, and the character span (start, end) of the call or token.
    If cursor_pos is -1 or out of range, scans text for the first recognized function call.
    """
    if not text:
        return "", None, (0, 0)

    # 1. If cursor is provided, try finding the word or function call around cursor
    if 0 <= cursor_pos <= len(text):
        # Check if cursor is on a word
        m_word = None
        for m in re.finditer(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', text):
            if m.start() <= cursor_pos <= m.end():
                m_word = m
                break

        if m_word:
            cand = m_word.group(0)
            info = get_function_info(cand)
            if info:
                # Check if immediately followed by parentheses: cand(...)
                rest = text[m_word.end():].lstrip()
                if rest.startswith('('):
                    paren_start = text.find('(', m_word.end())
                    # Find matching closing paren
                    depth = 0
                    paren_end = len(text)
                    for i in range(paren_start, len(text)):
                        if text[i] == '(':
                            depth += 1
                        elif text[i] == ')':
                            depth -= 1
                            if depth == 0:
                                paren_end = i + 1
                                break
                    return cand, info, (m_word.start(), paren_end)
                return cand, info, (m_word.start(), m_word.end())

        # Check if cursor is inside parentheses of a function call: fn(...)
        # Walk backwards from cursor to find opening paren
        for i in range(min(cursor_pos, len(text) - 1), -1, -1):
            if text[i] == '(':
                # Check what precedes '('
                prefix = text[:i].rstrip()
                m_fn = re.search(r'\b([a-zA-Z_][a-zA-Z0-9_]*)$', prefix)
                if m_fn:
                    cand = m_fn.group(1)
                    info = get_function_info(cand)
                    if info:
                        # Find matching closing paren
                        depth = 0
                        call_end = len(text)
                        for j in range(i, len(text)):
                            if text[j] == '(':
                                depth += 1
                            elif text[j] == ')':
                                depth -= 1
                                if depth == 0:
                                    call_end = j + 1
                                    break
                        return cand, info, (m_fn.start(), call_end)
                break

    # 2. General scan: find first recognized function call or token in text
    for m in re.finditer(r'\b([a-zA-Z_][a-zA-Z0-9_]*)\s*(\([^\)]*\))?', text):
        cand = m.group(1)
        info = get_function_info(cand)
        if info:
            return cand, info, (m.start(), m.end())

    return "", None, (0, 0)
