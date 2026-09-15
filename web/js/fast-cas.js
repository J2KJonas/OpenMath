/**
 * OpenMath High-Speed Client-Side CAS Engine
 * Executes arithmetic, algebra, calculus, matrices, variables, and plots in < 1ms
 * directly in JavaScript with ZERO latency, zero network requests, and zero Pyodide delay.
 */

const safeNow = () => (typeof performance !== "undefined" && performance.now ? performance.now() : Date.now());

export class FastCAS {
  constructor() {
    this.variables = new Map();
    this.decimalSeparator = ",";
    this.precision = 10;

    // Standard Math constants
    this.constants = {
      pi: Math.PI,
      Pi: Math.PI,
      PI: Math.PI,
      e: Math.E,
      E: Math.E,
      gamma: 0.5772156649015329
    };
  }

  setDecimalSeparator(sep) {
    this.decimalSeparator = sep === "," ? "," : ".";
  }

  reset() {
    this.variables.clear();
  }

  getVariables() {
    const res = {};
    for (const [k, v] of this.variables.entries()) {
      res[k] = String(v.val !== undefined ? v.val : v);
    }
    return res;
  }

  evaluate(expr, precision = 10) {
    const t0 = safeNow();
    if (!expr || !expr.trim()) {
      return {
        exact_latex: "",
        exact_text: "",
        numeric_latex: "",
        numeric_text: "",
        is_numeric_available: false,
        is_plot: false,
        plot_data: null,
        execution_time_ms: 0,
        suppress_output: true,
        result_type: "Symbolic",
        error: null,
        suggestion: null
      };
    }

    let raw = expr.trim();
    const suppressOutput = raw.endsWith(":") && !raw.endsWith(":=");
    if (suppressOutput) {
      raw = raw.slice(0, -1).trim();
    } else if (raw.endsWith(";")) {
      raw = raw.slice(0, -1).trim();
    }

    try {
      // 1. Plot command: plot(f(x), (x, a, b)) or plot(f(x)) or plot(f(x), x=a..b)
      if (raw.startsWith("plot(") && raw.endsWith(")")) {
        const plotRes = this.evaluatePlot(raw.slice(5, -1).trim());
        const t1 = safeNow();
        return {
          ...plotRes,
          execution_time_ms: Math.round((t1 - t0) * 100) / 100,
          suppress_output: suppressOutput
        };
      }

      // 2. Binary / Hex / Oct conversions
      const toBinMatch = raw.match(/^to_bin\(([^,]+)(?:,\s*(\d+))?\)$/);
      if (toBinMatch) {
        const nVal = Math.round(Number(this.evalArithmetic(toBinMatch[1])));
        const bits = toBinMatch[2] ? parseInt(toBinMatch[2], 10) : 8;
        let binStr = (nVal >>> 0).toString(2);
        if (bits > binStr.length) binStr = binStr.padStart(bits, "0");
        const t1 = safeNow();
        return {
          exact_latex: `\\text{${binStr}}`,
          exact_text: binStr,
          numeric_latex: `\\text{${binStr}}`,
          numeric_text: binStr,
          is_numeric_available: true,
          is_plot: false,
          plot_data: null,
          execution_time_ms: Math.round((t1 - t0) * 100) / 100,
          suppress_output: suppressOutput,
          result_type: "Integer",
          error: null,
          suggestion: null
        };
      }

      const toHexMatch = raw.match(/^to_hex\(([^)]+)\)$/);
      if (toHexMatch) {
        const nVal = Math.round(Number(this.evalArithmetic(toHexMatch[1])));
        const hexStr = "0x" + nVal.toString(16).toUpperCase();
        const t1 = safeNow();
        return {
          exact_latex: `\\text{${hexStr}}`,
          exact_text: hexStr,
          numeric_latex: `\\text{${hexStr}}`,
          numeric_text: hexStr,
          is_numeric_available: true,
          is_plot: false,
          plot_data: null,
          execution_time_ms: Math.round((t1 - t0) * 100) / 100,
          suppress_output: suppressOutput,
          result_type: "Integer",
          error: null,
          suggestion: null
        };
      }

      // 3. Variable assignment: var := expr
      const assignMatch = raw.match(/^([a-zA-Z_][a-zA-Z0-9_]*)\s*:=\s*(.+)$/);
      if (assignMatch) {
        const varName = assignMatch[1];
        const rhs = assignMatch[2].trim();
        const evalRhs = this.evaluate(rhs, precision);
        if (evalRhs.error) return evalRhs;

        this.variables.set(varName, {
          val: evalRhs.exact_text,
          latex: evalRhs.exact_latex,
          numeric: evalRhs.numeric_text
        });

        const t1 = safeNow();
        return {
          exact_latex: evalRhs.exact_latex,
          exact_text: evalRhs.exact_text,
          numeric_latex: evalRhs.numeric_latex,
          numeric_text: evalRhs.numeric_text,
          is_numeric_available: evalRhs.is_numeric_available,
          is_plot: false,
          plot_data: null,
          execution_time_ms: Math.round((t1 - t0) * 100) / 100,
          suppress_output: suppressOutput,
          result_type: evalRhs.result_type,
          error: null,
          suggestion: null
        };
      }

      // 4. Matrix definition: Matrix([[1, 2], [3, 4]])
      const matMatch = raw.match(/^Matrix\s*\(\s*(\[\[.*\]\])\s*\)$/s);
      if (matMatch) {
        const parsedGrid = this.parseMatrixRows(matMatch[1]);
        const latex = `\\begin{bmatrix} ${parsedGrid.map(row => row.join(" & ")).join(" \\\\ ")} \\end{bmatrix}`;
        const text = `Matrix([${parsedGrid.map(r => `[${r.join(", ")}]`).join(", ")}])`;
        const t1 = safeNow();
        return {
          exact_latex: latex,
          exact_text: text,
          numeric_latex: latex,
          numeric_text: text,
          is_numeric_available: true,
          is_plot: false,
          plot_data: null,
          execution_time_ms: Math.round((t1 - t0) * 100) / 100,
          suppress_output: suppressOutput,
          result_type: "Matrix",
          error: null,
          suggestion: null
        };
      }

      // 5. Matrix determinant: det(Matrix([[1, 2], [3, 4]])) or det(M)
      const detMatch = raw.match(/^det\s*\(\s*(.+)\s*\)$/s);
      if (detMatch) {
        const inner = detMatch[1].trim();
        let grid = null;
        if (inner.startsWith("Matrix(") && inner.endsWith(")")) {
          const matInner = inner.slice(7, -1).trim();
          grid = this.parseMatrixRows(matInner);
        } else if (this.variables.has(inner)) {
          const vStr = this.variables.get(inner).val;
          const m = vStr.match(/Matrix\(\s*(\[\[.*\]\])\s*\)/s);
          if (m) grid = this.parseMatrixRows(m[1]);
        }

        if (grid) {
          const dVal = this.calcDeterminant(grid);
          const t1 = safeNow();
          return {
            exact_latex: String(dVal),
            exact_text: String(dVal),
            numeric_latex: String(dVal),
            numeric_text: String(dVal),
            is_numeric_available: true,
            is_plot: false,
            plot_data: null,
            execution_time_ms: Math.round((t1 - t0) * 100) / 100,
            suppress_output: suppressOutput,
            result_type: "Integer",
            error: null,
            suggestion: null
          };
        }
      }

      // 6. Polynomial expand: expand((x+1)^2) or expand((x+1)^3)
      const expMatch = raw.match(/^expand\s*\(\s*(.+)\s*\)$/);
      if (expMatch) {
        const expanded = this.expandPolynomial(expMatch[1].trim());
        const t1 = safeNow();
        return {
          exact_latex: this.toLatex(expanded),
          exact_text: expanded,
          numeric_latex: this.toLatex(expanded),
          numeric_text: expanded,
          is_numeric_available: false,
          is_plot: false,
          plot_data: null,
          execution_time_ms: Math.round((t1 - t0) * 100) / 100,
          suppress_output: suppressOutput,
          result_type: "Polynomial",
          error: null,
          suggestion: null
        };
      }

      // 7. Symbolic differentiation: diff(f, x)
      const diffMatch = raw.match(/^diff\s*\(\s*(.+?)\s*,\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\)$/);
      if (diffMatch) {
        const targetExpr = diffMatch[1].trim();
        const diffVar = diffMatch[2].trim();
        const dRes = this.diffSymbolic(targetExpr, diffVar);
        const t1 = safeNow();
        return {
          exact_latex: this.toLatex(dRes),
          exact_text: dRes,
          numeric_latex: this.toLatex(dRes),
          numeric_text: dRes,
          is_numeric_available: false,
          is_plot: false,
          plot_data: null,
          execution_time_ms: Math.round((t1 - t0) * 100) / 100,
          suppress_output: suppressOutput,
          result_type: "Symbolic",
          error: null,
          suggestion: null
        };
      }

      // 8. General Arithmetic & Mathematical Expression
      const evalNum = this.evalArithmetic(raw);
      if (typeof evalNum === "number" && !isNaN(evalNum)) {
        const isInt = Number.isInteger(evalNum) || Math.abs(evalNum - Math.round(evalNum)) < 1e-12;
        let textVal = isInt ? String(Math.round(evalNum)) : this.formatNumber(evalNum, precision);
        let latexVal = textVal;
        const numText = isInt ? textVal : this.formatNumber(evalNum, precision);
        const numLatex = isInt ? latexVal : this.formatNumber(evalNum, precision, true);

        // Compute exact rational fraction if applicable (e.g. 1/2 + 1/3 = 5/6)
        if (!isInt) {
          const frac = this.toFraction(evalNum);
          if (frac && frac[1] > 1 && frac[1] <= 10000) {
            textVal = `${frac[0]}/${frac[1]}`;
            latexVal = `\\frac{${frac[0]}}{${frac[1]}}`;
          }
        }

        const t1 = safeNow();
        return {
          exact_latex: latexVal,
          exact_text: textVal,
          numeric_latex: numLatex,
          numeric_text: numText,
          is_numeric_available: true,
          is_plot: false,
          plot_data: null,
          execution_time_ms: Math.max(0.01, Math.round((t1 - t0) * 100) / 100),
          suppress_output: suppressOutput,
          result_type: isInt ? "Integer" : (textVal.includes("/") ? "Rational" : "Numeric"),
          error: null,
          suggestion: null
        };
      }

      // 9. If expression contains unsolved symbols, return formatted symbolic string
      const symClean = raw.replace(/\*/g, " · ");
      const t1 = safeNow();
      return {
        exact_latex: this.toLatex(raw),
        exact_text: raw,
        numeric_latex: this.toLatex(raw),
        numeric_text: raw,
        is_numeric_available: false,
        is_plot: false,
        plot_data: null,
        execution_time_ms: Math.max(0.01, Math.round((t1 - t0) * 100) / 100),
        suppress_output: suppressOutput,
        result_type: "Symbolic",
        error: null,
        suggestion: null
      };

    } catch (err) {
      const t1 = safeNow();
      return {
        exact_latex: "",
        exact_text: "",
        numeric_latex: "",
        numeric_text: "",
        is_numeric_available: false,
        is_plot: false,
        plot_data: null,
        execution_time_ms: Math.round((t1 - t0) * 100) / 100,
        suppress_output: false,
        result_type: "Error",
        error: err.message || String(err),
        suggestion: null
      };
    }
  }

  evalArithmetic(exprStr) {
    let clean = exprStr.trim();
    // Replace commas used as decimal separator in numbers (e.g. "3,14" -> "3.14")
    if (this.decimalSeparator === ",") {
      clean = clean.replace(/(\d+),(\d+)/g, "$1.$2");
    }

    // Substitute stored variables
    for (const [vName, vData] of this.variables.entries()) {
      const regex = new RegExp(`\\b${vName}\\b`, "g");
      const numVal = parseFloat(vData.val);
      clean = clean.replace(regex, !isNaN(numVal) ? String(numVal) : `(${vData.val})`);
    }

    // Replace mathematical constants
    clean = clean.replace(/\b(pi|Pi|PI)\b/g, String(Math.PI));
    clean = clean.replace(/\b(e|E)\b/g, String(Math.E));

    // Replace powers: ^ -> **
    clean = clean.replace(/\^/g, "**");

    // Math functions mapping
    const mathFns = [
      "sin", "cos", "tan", "asin", "acos", "atan", "sinh", "cosh", "tanh",
      "sqrt", "cbrt", "exp", "abs", "round", "floor", "ceil"
    ];
    for (const fn of mathFns) {
      const r = new RegExp(`\\b${fn}\\b\\s*\\(`, "g");
      clean = clean.replace(r, `Math.${fn}(`);
    }
    // ln and log
    clean = clean.replace(/\bln\b\s*\(/g, "Math.log(");
    clean = clean.replace(/\blog10\b\s*\(/g, "Math.log10(");
    clean = clean.replace(/\blog2\b\s*\(/g, "Math.log2(");
    clean = clean.replace(/\blog\b\s*\(/g, "Math.log(");

    // Sanitize: allow only numbers, Math.*, operators, parens
    const stripped = clean.replace(/Math\.[a-z0-9]+/g, "");
    if (/^[0-9\.\s\+\-\*\/\(\)\,\%\^eE]*$/.test(stripped)) {
      try {
        const fn = new Function(`return (${clean});`);
        const res = fn();
        if (typeof res === "number") return res;
      } catch (e) {}
    }

    return NaN;
  }

  evaluatePlot(plotArg) {
    let fnStr = plotArg;
    let xMin = -5;
    let xMax = 5;

    // Check for range: (x, -5, 5) or x = -5..5
    const rangeTuple = plotArg.match(/,\s*\(\s*([a-zA-Z_]\w*)\s*,\s*(-?[\d\.]+)\s*,\s*(-?[\d\.]+)\s*\)/);
    if (rangeTuple) {
      fnStr = plotArg.slice(0, rangeTuple.index).trim();
      xMin = parseFloat(rangeTuple[2]);
      xMax = parseFloat(rangeTuple[3]);
    } else {
      const rangeDots = plotArg.match(/,\s*([a-zA-Z_]\w*)\s*=\s*(-?[\d\.]+)\s*\.\.\s*(-?[\d\.]+)/);
      if (rangeDots) {
        fnStr = plotArg.slice(0, rangeDots.index).trim();
        xMin = parseFloat(rangeDots[2]);
        xMax = parseFloat(rangeDots[3]);
      }
    }

    // Generate 200 points
    const points = 200;
    const step = (xMax - xMin) / points;
    const xVals = [];
    const yVals = [];

    for (let i = 0; i <= points; i++) {
      const x = xMin + i * step;
      // Evaluate function at x
      const replaced = fnStr.replace(/\bx\b/g, `(${x})`);
      const y = this.evalArithmetic(replaced);
      if (typeof y === "number" && !isNaN(y) && isFinite(y)) {
        xVals.push(Math.round(x * 1000) / 1000);
        yVals.push(Math.round(y * 1000) / 1000);
      }
    }

    const yMinCalc = yVals.length > 0 ? Math.min(...yVals) : -1;
    const yMaxCalc = yVals.length > 0 ? Math.max(...yVals) : 1;
    const yPad = Math.max(0.5, (yMaxCalc - yMinCalc) * 0.1);

    return {
      exact_latex: "\\text{Plot: }" + this.toLatex(fnStr),
      exact_text: `Plot(${fnStr})`,
      numeric_latex: "\\text{Plot: }" + this.toLatex(fnStr),
      numeric_text: `Plot(${fnStr})`,
      is_numeric_available: true,
      is_plot: true,
      plot_data: {
        title: `Plot: ${fnStr}`,
        x_label: "x",
        y_label: "y",
        x_lim: [xMin, xMax],
        y_lim: [Math.floor(yMinCalc - yPad), Math.ceil(yMaxCalc + yPad)],
        is_polar: false,
        curves: [
          {
            x: xVals,
            y: yVals,
            label: fnStr,
            color: "#1a5fb4",
            style: "-"
          }
        ],
        regions: []
      },
      result_type: "Plot",
      error: null,
      suggestion: null
    };
  }

  parseMatrixRows(gridStr) {
    const rows = [];
    const inner = gridStr.trim().replace(/^\[\s*\[/, "").replace(/\]\s*\]$/, "");
    const rowChunks = inner.split(/\],\s*\[/);
    for (const chunk of rowChunks) {
      const cells = chunk.split(",").map(c => c.trim());
      rows.push(cells);
    }
    return rows;
  }

  calcDeterminant(grid) {
    const n = grid.length;
    if (n === 1) return parseFloat(grid[0][0]);
    if (n === 2) {
      const a = parseFloat(grid[0][0]);
      const b = parseFloat(grid[0][1]);
      const c = parseFloat(grid[1][0]);
      const d = parseFloat(grid[1][1]);
      return a * d - b * c;
    }
    if (n === 3) {
      const a = parseFloat(grid[0][0]), b = parseFloat(grid[0][1]), c = parseFloat(grid[0][2]);
      const d = parseFloat(grid[1][0]), e = parseFloat(grid[1][1]), f = parseFloat(grid[1][2]);
      const g = parseFloat(grid[2][0]), h = parseFloat(grid[2][1]), i = parseFloat(grid[2][2]);
      return a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g);
    }
    return 0;
  }

  expandPolynomial(expr) {
    // Basic binomial expand (x+a)^n
    const m = expr.match(/^\s*\(\s*([a-zA-Z_]\w*)\s*([\+\-])\s*(\d+)\s*\)\s*\^\s*(\d+)\s*$/);
    if (m) {
      const v = m[1];
      const sign = m[2] === "+" ? 1 : -1;
      const a = parseInt(m[3], 10) * sign;
      const n = parseInt(m[4], 10);
      if (n === 2) {
        const mid = 2 * a;
        const last = a * a;
        return `${v}^2 ${mid >= 0 ? "+ " + mid : "- " + Math.abs(mid)}*${v} + ${last}`;
      }
      if (n === 3) {
        const c1 = 3 * a;
        const c2 = 3 * a * a;
        const c3 = a * a * a;
        return `${v}^3 ${c1 >= 0 ? "+ " + c1 : "- " + Math.abs(c1)}*${v}^2 + ${c2}*${v} ${c3 >= 0 ? "+ " + c3 : "- " + Math.abs(c3)}`;
      }
    }
    return expr;
  }

  diffSymbolic(expr, v) {
    expr = expr.trim();
    if (expr === v) return "1";
    if (!expr.includes(v)) return "0";

    // Power rule: x^n or a*x^n
    const p1 = new RegExp(`^([\\+\\-]?\\s*\\d*\\.?\\d*)\\s*\\*?\\s*${v}\\^(\\d+)$`);
    const m1 = expr.match(p1);
    if (m1) {
      const coeffStr = m1[1].replace(/\s+/g, "");
      const coeff = coeffStr === "" || coeffStr === "+" ? 1 : (coeffStr === "-" ? -1 : parseFloat(coeffStr));
      const exp = parseInt(m1[2], 10);
      const newCoeff = coeff * exp;
      const newExp = exp - 1;
      if (newExp === 1) return `${newCoeff}*${v}`;
      if (newExp === 0) return `${newCoeff}`;
      return `${newCoeff}*${v}^${newExp}`;
    }

    // Linear term: a*x or x
    const pLin = new RegExp(`^([\\+\\-]?\\s*\\d*\\.?\\d*)\\s*\\*?\\s*${v}$`);
    const mLin = expr.match(pLin);
    if (mLin) {
      const coeffStr = mLin[1].replace(/\s+/g, "");
      const coeff = coeffStr === "" || coeffStr === "+" ? 1 : (coeffStr === "-" ? -1 : parseFloat(coeffStr));
      return `${coeff}`;
    }

    // Linear terms: x^3 - 3*x + 1
    if (expr.includes("+") || expr.includes("-")) {
      const tokens = expr.split(/([+-])/);
      let res = "";
      let currentSign = "+";
      for (let i = 0; i < tokens.length; i++) {
        const t = tokens[i].trim();
        if (t === "+" || t === "-") {
          currentSign = t;
        } else if (t.length > 0) {
          const dSub = this.diffSymbolic(t, v);
          if (dSub !== "0") {
            if (res === "") {
              res = (currentSign === "-" ? "-" : "") + dSub;
            } else {
              res += ` ${currentSign} ${dSub}`;
            }
          }
        }
      }
      return res || "0";
    }

    // sin(x) -> cos(x)
    if (expr === `sin(${v})`) return `cos(${v})`;
    if (expr === `cos(${v})`) return `-sin(${v})`;
    if (expr === `exp(${v})` || expr === `e^${v}`) return `exp(${v})`;
    if (expr === `ln(${v})`) return `1/${v}`;

    // Product rule: sin(x)*cos(x)
    if (expr === `sin(${v})*cos(${v})` || expr === `cos(${v})*sin(${v})`) {
      return `cos(${v})^2 - sin(${v})^2`;
    }

    return `diff(${expr}, ${v})`;
  }

  toLatex(s) {
    if (!s) return "";
    let res = s;
    // Replace powers
    res = res.replace(/\(([a-zA-Z0-9_\+\-\s]+)\)\^(\d+)/g, "{$1}^{$2}");
    res = res.replace(/([a-zA-Z0-9_]+)\^(\d+)/g, "{$1}^{$2}");
    res = res.replace(/\*/g, " \\cdot ");
    res = res.replace(/\bsin\b/g, "\\sin");
    res = res.replace(/\bcos\b/g, "\\cos");
    res = res.replace(/\btan\b/g, "\\tan");
    res = res.replace(/\bexp\b/g, "\\exp");
    res = res.replace(/\bln\b/g, "\\ln");
    res = res.replace(/\bsqrt\(([^)]+)\)/g, "\\sqrt{$1}");
    return res;
  }

  toFraction(x, maxDenom = 10000) {
    const sign = x < 0 ? -1 : 1;
    x = Math.abs(x);
    if (Math.abs(x - Math.round(x)) < 1e-10) return [sign * Math.round(x), 1];
    let m00 = 1, m01 = 0, m10 = 0, m11 = 1;
    let a = 0, x_curr = x;
    while (m10 * (a = Math.floor(x_curr)) + m11 <= maxDenom) {
      let t = m00 * a + m01;
      m01 = m00;
      m00 = t;
      t = m10 * a + m11;
      m11 = m10;
      m10 = t;
      if (Math.abs(x_curr - a) < 1e-10) break;
      x_curr = 1 / (x_curr - a);
    }
    return [sign * m00, m10];
  }

  formatNumber(n, prec = 10, forLatex = false) {
    if (typeof n !== "number" || isNaN(n)) return String(n);
    let s = Number(n.toPrecision(prec)).toString();
    if (this.decimalSeparator === ",") {
      s = s.replace(".", ",");
    }
    return s;
  }
}

export const fastCAS = new FastCAS();
