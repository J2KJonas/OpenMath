/**
 * OpenMath Context Panel
 * Right dock widget with Math Editor Shortcuts table, Active Target expression summary,
 * and dynamic contextual mathematical operations matching ui/context_panel.py.
 */

export class ContextPanelManager {
  constructor(app) {
    this.app = app;
    this.dockElement = document.getElementById("context-dock");
    this.targetExprElement = document.getElementById("context-target-expr");
    this.opsContainer = document.getElementById("context-ops-container");
    this.currentExpr = "";
    this.initEvents();
  }

  initEvents() {
    const collapseBtn = document.getElementById("btn-collapse-context-panel");
    if (collapseBtn) {
      collapseBtn.addEventListener("click", () => {
        this.dockElement.classList.toggle("collapsed");
        this.app.updateViewMenuCheckmarks();
      });
    }
  }

  setTargetExpression(expr, resultObj = null) {
    this.currentExpr = (expr || "").trim();
    if (this.targetExprElement) {
      this.targetExprElement.textContent = this.currentExpr || "No expression selected";
    }
    this.updateOperations(this.currentExpr);
  }

  updateOperations(expr) {
    if (!this.opsContainer) return;

    if (!expr) {
      this.opsContainer.innerHTML = `<p style="color: var(--text-muted); font-size: 11px;">Focus or select an expression to see context operations.</p>`;
      return;
    }

    let target = expr.trim();
    if (target.includes(":=")) {
      target = target.split(":=")[1].trim();
    }

    const isMatrix = target.includes("Matrix(") || target.includes("[[") || target.startsWith("Vector(");
    const isEquation = target.includes("=") && !target.includes(":=") && !target.includes("<=") && !target.includes(">=") && !target.includes("!=") && !target.includes("==");
    const isInteger = /^-?\d+$/.test(target) || /^0[xXbB][0-9a-fA-F]+$/.test(target);
    const isNumber = /^-?\d+\.\d+$/.test(target);

    const groups = [];

    if (isMatrix) {
      groups.push({
        title: "Matrix & Linear Algebra",
        ops: [
          { label: "Determinant", cmd: `det(${target})`, desc: "Compute matrix determinant" },
          { label: "Inverse", cmd: `inv(${target})`, desc: "Compute matrix inverse" },
          { label: "Transpose", cmd: `transpose(${target})`, desc: "Transpose matrix" },
          { label: "Eigenvalues", cmd: `eigenvals(${target})`, desc: "Compute eigenvalues" },
          { label: "Eigenvectors", cmd: `eigenvects(${target})`, desc: "Compute eigenvectors" },
          { label: "Rank", cmd: `rank(${target})`, desc: "Compute matrix rank" },
          { label: "Trace", cmd: `trace(${target})`, desc: "Compute matrix trace" },
          { label: "Reduced Row Echelon (RREF)", cmd: `rref(${target})`, desc: "Compute RREF" },
          { label: "Characteristic Poly", cmd: `charpoly(${target})`, desc: "Characteristic polynomial" },
          { label: "LU Decomposition", cmd: `LUDecomposition(${target})`, desc: "LU matrix decomposition" },
          { label: "QR Decomposition", cmd: `QRDecomposition(${target})`, desc: "QR matrix decomposition" },
        ]
      });
      groups.push({
        title: "General Operations",
        ops: [
          { label: "Simplify Elements", cmd: `simplify(${target})`, desc: "Simplify all matrix entries" },
        ]
      });
    } else if (isEquation) {
      groups.push({
        title: "Equation Operations",
        ops: [
          { label: "Solve (Symbolic)", cmd: `solve(${target}, x)`, desc: "Solve equation symbolically for x" },
          { label: "Solve (Numerical)", cmd: `fsolve(${target}, x)`, desc: "Solve equation numerically" },
          { label: "Left-Hand Side (lhs)", cmd: `lhs(${target})`, desc: "Extract left-hand side" },
          { label: "Right-Hand Side (rhs)", cmd: `rhs(${target})`, desc: "Extract right-hand side" },
          { label: "Plot Equation", cmd: `plot(lhs(${target}) - rhs(${target}), (x, -10, 10))`, desc: "Plot root curve of equation" },
        ]
      });
      groups.push({
        title: "Algebra",
        ops: [
          { label: "Expand", cmd: `expand(${target})`, desc: "Expand both sides" },
          { label: "Simplify", cmd: `simplify(${target})`, desc: "Simplify equation" },
        ]
      });
    } else if (isInteger || isNumber) {
      groups.push({
        title: "Number Theory",
        ops: [
          { label: "Prime Factors (ifactor)", cmd: `ifactor(${target})`, desc: "Integer prime factorization" },
          { label: "Next Prime", cmd: `nextprime(${target})`, desc: "Next smallest prime" },
          { label: "Divisors", cmd: `divisors(${target})`, desc: "List all integer divisors" },
          { label: "Euler Totient (phi)", cmd: `euler_phi(${target})`, desc: "Euler's totient function" },
        ]
      });
      groups.push({
        title: "Digital Hardware Representations",
        ops: [
          { label: "Binary Repr (8-bit)", cmd: `to_bin(${target}, 8)`, desc: "Format integer as 8-bit binary nibbles" },
          { label: "Binary Repr (16-bit)", cmd: `to_bin(${target}, 16)`, desc: "Format integer as 16-bit binary" },
          { label: "Binary Repr (32-bit)", cmd: `to_bin(${target}, 32)`, desc: "Format integer as 32-bit binary" },
          { label: "Hex Repr (0x)", cmd: `to_hex(${target}, 8)`, desc: "Format integer as 8-bit hex" },
          { label: "Two's Comp Breakdown", cmd: `twos_comp_repr(${target}, 8)`, desc: "Analyze signed/unsigned integer range" },
          { label: "IEEE-754 Float Bitfield", cmd: `ieee754(${target})`, desc: "Decompose floating point number" },
        ]
      });
    } else {
      groups.push({
        title: "Algebra & Simplification",
        ops: [
          { label: "Factor", cmd: `factor(${target})`, desc: "Factor polynomial expression" },
          { label: "Expand", cmd: `expand(${target})`, desc: "Expand polynomial or trigonometric expression" },
          { label: "Simplify", cmd: `simplify(${target})`, desc: "Simplify mathematical expression" },
          { label: "Normal (Rational)", cmd: `normal(${target})`, desc: "Cancel common rational factors" },
          { label: "Partial Fractions", cmd: `convert(${target}, parfrac, x)`, desc: "Partial fraction decomposition" },
          { label: "Degree (w.r.t x)", cmd: `degree(${target}, x)`, desc: "Polynomial degree" },
          { label: "Solve roots (x)", cmd: `solve(${target} = 0, x)`, desc: "Solve for roots w.r.t x" },
        ]
      });
      groups.push({
        title: "Calculus",
        ops: [
          { label: "Differentiate (d/dx)", cmd: `diff(${target}, x)`, desc: "Differentiate with respect to x" },
          { label: "Integrate (∫ dx)", cmd: `integrate(${target}, x)`, desc: "Compute indefinite integral" },
          { label: "Taylor Series (x=0)", cmd: `taylor(${target}, x, 0, 6)`, desc: "Compute 6th-order Taylor series around 0" },
          { label: "Plot 2D", cmd: `plot(${target}, (x, -10, 10))`, desc: "Plot 2D curve" },
        ]
      });
      groups.push({
        title: "Optimization & Polygons",
        ops: [
          { label: "polygonOmråde", cmd: `polygonOmråde(Uligheder, x = -1 .. 13, y = -1 .. 12)`, desc: "Plot feasible polygon area" },
          { label: "LPplot Level Curves", cmd: `LPplot(${target}, Uligheder, [0, 120, 300])`, desc: "Plot linear programming level curves" },
        ]
      });
    }

    let html = "";
    for (const group of groups) {
      html += `
        <div class="context-group">
          <div class="context-group-title">${group.title}</div>
          <div class="context-ops-grid">
            ${group.ops.map(op => `<button class="context-op-btn" data-cmd="${op.cmd.replace(/"/g, '&quot;')}" title="${op.desc || op.label}">${op.label}</button>`).join("")}
          </div>
        </div>
      `;
    }

    this.opsContainer.innerHTML = html;

    this.opsContainer.querySelectorAll(".context-op-btn").forEach(btn => {
      btn.onclick = () => {
        const cmd = btn.dataset.cmd;
        if (cmd) {
          const ws = this.app.getActiveWorksheet();
          if (ws) {
            ws.addCellWithInput(cmd, true);
          }
        }
      };
    });
  }
}
