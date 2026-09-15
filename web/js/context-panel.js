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

    const isMatrix = expr.includes("Matrix(") || expr.includes("[[");
    const isEquation = expr.includes("=") && !expr.includes(":=");
    const isInteger = /^-?\d+$/.test(expr) || /^0[xXbB][0-9a-fA-F]+$/.test(expr);

    const ops = [];

    // General Algebraic Operations
    ops.push({ label: "Simplify", cmd: `simplify(${expr})` });
    ops.push({ label: "Factor", cmd: `factor(${expr})` });
    ops.push({ label: "Expand", cmd: `expand(${expr})` });

    if (isEquation || expr.includes("x")) {
      ops.push({ label: "Solve for x", cmd: `solve(${expr}, x)` });
    }

    // Calculus
    ops.push({ label: "Differentiate (d/dx)", cmd: `diff(${expr}, x)` });
    ops.push({ label: "Integrate (∫ dx)", cmd: `integrate(${expr}, x)` });
    ops.push({ label: "Taylor Series (deg 5)", cmd: `taylor(${expr}, x, 0, 5)` });

    // Linear Algebra if matrix-like
    if (isMatrix) {
      ops.push({ label: "Determinant (det)", cmd: `det(${expr})` });
      ops.push({ label: "Inverse (inv)", cmd: `inv(${expr})` });
      ops.push({ label: "Transpose", cmd: `transpose(${expr})` });
      ops.push({ label: "Reduced Row Echelon (rref)", cmd: `rref(${expr})` });
      ops.push({ label: "Eigenvalues", cmd: `eigenvals(${expr})` });
    }

    // Hardware/Integer representation
    if (isInteger) {
      ops.push({ label: "Binary (8-bit)", cmd: `to_bin(${expr}, 8)` });
      ops.push({ label: "Hexadecimal (8-bit)", cmd: `to_hex(${expr}, 8)` });
      ops.push({ label: "Two's Complement Repr", cmd: `twos_comp_repr(${expr}, 8)` });
    }

    let html = `<div class="context-ops-grid">`;
    for (const op of ops) {
      html += `<button class="context-op-btn" data-cmd="${op.cmd.replace(/"/g, '&quot;')}">${op.label}</button>`;
    }
    html += `</div>`;

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
