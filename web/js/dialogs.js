/**
 * OpenMath Modal Dialogs
 * Matrix Wizard, Options & Preferences, About OpenMath, Help Topics, and Export PDF.
 */

export class DialogManager {
  constructor(app) {
    this.app = app;
    this.activeDialog = null;
    this.initDialogs();
  }

  initDialogs() {
    // Backdrop click dismiss
    const backdrop = document.getElementById("modal-backdrop");
    if (backdrop) {
      backdrop.addEventListener("mousedown", (e) => {
        if (e.target === backdrop) {
          this.closeCurrentDialog();
        }
      });
    }

    // Escape key dismiss
    window.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && this.activeDialog) {
        this.closeCurrentDialog();
      }
    });

    // Close buttons on dialogs
    document.querySelectorAll(".modal-close-btn, .dialog-cancel-btn").forEach(btn => {
      btn.addEventListener("click", () => this.closeCurrentDialog());
    });
  }

  openDialog(dialogId) {
    const backdrop = document.getElementById("modal-backdrop");
    const dialog = document.getElementById(dialogId);
    if (!backdrop || !dialog) return;

    // Hide all dialogs first
    document.querySelectorAll(".modal-dialog").forEach(d => d.style.display = "none");

    dialog.style.display = "flex";
    backdrop.classList.add("open");
    this.activeDialog = dialogId;

    if (dialogId === "dialog-matrix-wizard") {
      this.setupMatrixWizard();
    } else if (dialogId === "dialog-options") {
      this.setupOptionsDialog();
    } else if (dialogId === "dialog-help-topics") {
      this.setupHelpTopics();
    }
  }

  closeCurrentDialog() {
    const backdrop = document.getElementById("modal-backdrop");
    if (backdrop) {
      backdrop.classList.remove("open");
    }
    document.querySelectorAll(".modal-dialog").forEach(d => d.style.display = "none");
    this.activeDialog = null;
  }

  // 1. Matrix Wizard Dialog
  setupMatrixWizard() {
    const rowsSelect = document.getElementById("matrix-rows-select");
    const colsSelect = document.getElementById("matrix-cols-select");
    const gridContainer = document.getElementById("matrix-grid-container");
    const insertBtn = document.getElementById("btn-matrix-insert");

    const renderGrid = () => {
      const rows = parseInt(rowsSelect.value, 10) || 3;
      const cols = parseInt(colsSelect.value, 10) || 3;

      let html = `<table class="matrix-table">`;
      for (let r = 0; r < rows; r++) {
        html += `<tr>`;
        for (let c = 0; c < cols; c++) {
          html += `<td><input type="text" class="matrix-cell-input" data-row="${r}" data-col="${c}" value="0" /></td>`;
        }
        html += `</tr>`;
      }
      html += `</table>`;
      gridContainer.innerHTML = html;

      // Setup arrow navigation inside grid
      gridContainer.querySelectorAll(".matrix-cell-input").forEach(input => {
        input.addEventListener("focus", () => input.select());
        input.addEventListener("keydown", (e) => {
          const r = parseInt(input.dataset.row, 10);
          const c = parseInt(input.dataset.col, 10);
          if (e.key === "ArrowRight" && input.selectionEnd === input.value.length) {
            const next = gridContainer.querySelector(`.matrix-cell-input[data-row="${r}"][data-col="${c + 1}"]`);
            if (next) { next.focus(); e.preventDefault(); }
          } else if (e.key === "ArrowLeft" && input.selectionStart === 0) {
            const prev = gridContainer.querySelector(`.matrix-cell-input[data-row="${r}"][data-col="${c - 1}"]`);
            if (prev) { prev.focus(); e.preventDefault(); }
          } else if (e.key === "ArrowDown" || e.key === "Enter") {
            const down = gridContainer.querySelector(`.matrix-cell-input[data-row="${r + 1}"][data-col="${c}"]`);
            if (down) { down.focus(); e.preventDefault(); }
          } else if (e.key === "ArrowUp") {
            const up = gridContainer.querySelector(`.matrix-cell-input[data-row="${r - 1}"][data-col="${c}"]`);
            if (up) { up.focus(); e.preventDefault(); }
          }
        });
      });
    };

    rowsSelect.onchange = renderGrid;
    colsSelect.onchange = renderGrid;
    renderGrid();

    // Preset buttons
    const fillPreset = (type) => {
      const rows = parseInt(rowsSelect.value, 10);
      const cols = parseInt(colsSelect.value, 10);
      gridContainer.querySelectorAll(".matrix-cell-input").forEach(input => {
        const r = parseInt(input.dataset.row, 10);
        const c = parseInt(input.dataset.col, 10);
        if (type === "identity") {
          input.value = r === c ? "1" : "0";
        } else if (type === "zeros") {
          input.value = "0";
        } else if (type === "ones") {
          input.value = "1";
        } else if (type === "diagonal") {
          input.value = r === c ? `${r + 1}` : "0";
        } else if (type === "clear") {
          input.value = "";
        }
      });
    };

    document.querySelectorAll(".matrix-preset-btn").forEach(btn => {
      btn.onclick = () => fillPreset(btn.dataset.preset);
    });

    insertBtn.onclick = () => {
      const rows = parseInt(rowsSelect.value, 10);
      const cols = parseInt(colsSelect.value, 10);
      const matrixData = [];
      for (let r = 0; r < rows; r++) {
        const rowVals = [];
        for (let c = 0; c < cols; c++) {
          const input = gridContainer.querySelector(`.matrix-cell-input[data-row="${r}"][data-col="${c}"]`);
          rowVals.push(input ? (input.value.trim() || "0") : "0");
        }
        matrixData.push(`[${rowVals.join(", ")}]`);
      }
      const expr = `Matrix([${matrixData.join(", ")}])`;
      this.closeCurrentDialog();
      this.app.insertTemplateIntoActiveCell(expr);
    };
  }

  // 2. Options & Preferences Dialog
  setupOptionsDialog() {
    const tabs = document.querySelectorAll("#dialog-options .dialog-tab-btn");
    const panes = document.querySelectorAll("#dialog-options .dialog-tab-pane");

    tabs.forEach(tab => {
      tab.onclick = () => {
        tabs.forEach(t => t.classList.remove("active"));
        panes.forEach(p => p.classList.remove("active"));
        tab.classList.add("active");
        const targetPane = document.getElementById(tab.dataset.pane);
        if (targetPane) targetPane.classList.add("active");
      };
    });

    // Populate current values
    const themeRadio = document.querySelector(`input[name="opt-theme"][value="${this.app.theme}"]`);
    if (themeRadio) themeRadio.checked = true;

    const decRadio = document.querySelector(`input[name="opt-decimal"][value="${this.app.decimalSeparator}"]`);
    if (decRadio) decRadio.checked = true;

    const precisionInput = document.getElementById("opt-precision");
    if (precisionInput) precisionInput.value = this.app.precision;

    const fontSelect = document.getElementById("opt-font-family");
    if (fontSelect) fontSelect.value = this.app.currentFontFamily;

    const fontSizeSelect = document.getElementById("opt-font-size");
    if (fontSizeSelect) fontSizeSelect.value = this.app.currentFontSize;

    // Apply button
    const applyBtn = document.getElementById("btn-options-apply");
    if (applyBtn) {
      applyBtn.onclick = () => {
        const selTheme = document.querySelector('input[name="opt-theme"]:checked')?.value || "light";
        const selDec = document.querySelector('input[name="opt-decimal"]:checked')?.value || ",";
        const selPrec = parseInt(precisionInput?.value || "10", 10);
        const selFont = fontSelect?.value || "Times New Roman";
        const selSize = fontSizeSelect?.value || "12";

        this.app.applyTheme(selTheme);
        this.app.setDecimalSeparator(selDec);
        this.app.setPrecision(selPrec);
        this.app.setFontFamily(selFont);
        this.app.setFontSize(selSize);

        this.closeCurrentDialog();
      };
    }

    // Reset Defaults button
    const resetBtn = document.getElementById("btn-options-defaults");
    if (resetBtn) {
      resetBtn.onclick = () => {
        const lightTheme = document.querySelector('input[name="opt-theme"][value="light"]');
        if (lightTheme) lightTheme.checked = true;
        const commaDec = document.querySelector('input[name="opt-decimal"][value=","]');
        if (commaDec) commaDec.checked = true;
        if (precisionInput) precisionInput.value = "10";
        if (fontSelect) fontSelect.value = "Times New Roman";
        if (fontSizeSelect) fontSizeSelect.value = "12";
      };
    }
  }

  // 3. Help Topics Dialog
  setupHelpTopics() {
    const listContainer = document.getElementById("help-topics-list");
    const detailContainer = document.getElementById("help-topic-detail");
    const searchInput = document.getElementById("help-topics-search");

    const topics = this.app.helpCatalog || [
      { name: "diff", syntax: "diff(f, x) or diff(f, x, n)", description: "Calculates the symbolic derivative of f with respect to x.", primary_example: "diff(x^3 + sin(x), x)" },
      { name: "integrate", syntax: "integrate(f, x) or integrate(f, (x, a, b))", description: "Computes indefinite or definite symbolic integral of f.", primary_example: "integrate(x^2 * exp(x), (x, 0, 1))" },
      { name: "solve", syntax: "solve(equation, x) or solve([eq1, eq2], [x, y])", description: "Solves algebraic equations or systems for unknown variables.", primary_example: "solve(x^2 - 4 = 0, x)" },
      { name: "limit", syntax: "limit(f, x, a)", description: "Computes mathematical limit of f as x approaches a.", primary_example: "limit(sin(x)/x, x, 0)" },
      { name: "taylor", syntax: "taylor(f, x, x0, n)", description: "Computes Taylor polynomial of degree n around point x0.", primary_example: "taylor(exp(x), x, 0, 5)" },
      { name: "plot", syntax: "plot(f(x), (x, a, b))", description: "Renders a dynamic 2D function plot over interval [a, b].", primary_example: "plot(sin(x) * exp(-x/5), (x, -10, 10))" },
      { name: "polygonOmråde", syntax: "polygonOmråde([inequalities], x=xmin..xmax, y=ymin..ymax)", description: "Visualizes the feasible polygonal region bounded by linear inequalities.", primary_example: "polygonOmråde([x >= 0, y >= 0, x + y <= 10], x = 0..12, y = 0..12)" },
      { name: "LPplot", syntax: "LPplot(objective, [constraints], [levels])", description: "Plots objective level curves along with feasible polygon region.", primary_example: "LPplot(30*x + 20*y, [x >= 0, y >= 0, x + y <= 10], [100, 200, 300])" },
      { name: "to_bin", syntax: "to_bin(val, bits=8)", description: "Formats an integer as spaced nibble binary string.", primary_example: "to_bin(0xA5, 8)" },
      { name: "to_hex", syntax: "to_hex(val, bits=8)", description: "Formats an integer into standard hexadecimal notation.", primary_example: "to_hex(255, 8)" },
      { name: "twos_comp_repr", syntax: "twos_comp_repr(val, bits=8)", description: "Calculates signed/unsigned two's complement breakdown.", primary_example: "twos_comp_repr(-5, 8)" },
      { name: "Matrix", syntax: "Matrix([[a, b], [c, d]])", description: "Constructs a symbolic or numerical matrix.", primary_example: "Matrix([[1, 2], [3, 4]])" },
      { name: "simplify", syntax: "simplify(expr)", description: "Applies symbolic transformations to simplify mathematical expressions.", primary_example: "simplify((x^2 - 1)/(x - 1))" },
      { name: "factor", syntax: "factor(expr)", description: "Factors a polynomial into irreducible algebraic components.", primary_example: "factor(x^2 - 5*x + 6)" },
      { name: "expand", syntax: "expand(expr)", description: "Expands products and powers of polynomial expressions.", primary_example: "expand((x + 2)^3)" }
    ];

    const renderList = (filter = "") => {
      const q = filter.toLowerCase().trim();
      const filtered = topics.filter(t => t.name.toLowerCase().includes(q) || t.description.toLowerCase().includes(q));
      listContainer.innerHTML = filtered.map(t => `<div class="help-topic-item" data-topic="${t.name}">${t.name}</div>`).join("");

      listContainer.querySelectorAll(".help-topic-item").forEach(item => {
        item.onclick = () => {
          listContainer.querySelectorAll(".help-topic-item").forEach(i => i.classList.remove("active"));
          item.classList.add("active");
          const found = topics.find(t => t.name === item.dataset.topic);
          if (found) showDetail(found);
        };
      });

      if (filtered.length > 0) {
        listContainer.firstElementChild.classList.add("active");
        showDetail(filtered[0]);
      } else {
        detailContainer.innerHTML = `<p style="color: var(--text-muted);">No matching topics found.</p>`;
      }
    };

    const showDetail = (topic) => {
      detailContainer.innerHTML = `
        <h3 style="color: var(--text-primary); font-size: 15px; margin-bottom: 4px;">${topic.name}</h3>
        <div style="background: var(--bg-input); border: 1px solid var(--border); border-radius: 4px; padding: 6px 10px; font-family: monospace; font-size: 11px;">
          ${topic.syntax}
        </div>
        <p style="color: var(--text-secondary); line-height: 1.4; font-size: 12px;">${topic.description}</p>
        <div style="margin-top: 8px;">
          <strong style="font-size: 11px;">Example:</strong>
          <div style="display: flex; align-items: center; justify-content: space-between; background: var(--bg-surface); border: 1px solid var(--border); border-radius: 4px; padding: 6px 10px; margin-top: 4px;">
            <code style="font-family: monospace; font-size: 12px; color: var(--accent);">${topic.primary_example || topic.syntax}</code>
            <button id="btn-insert-example" class="dialog-btn primary" style="min-width: 60px; height: 24px; padding: 2px 8px; font-size: 11px;">Insert</button>
          </div>
        </div>
      `;

      const insertBtn = document.getElementById("btn-insert-example");
      if (insertBtn) {
        insertBtn.onclick = () => {
          this.closeCurrentDialog();
          this.app.insertTemplateIntoActiveCell(topic.primary_example || topic.syntax);
        };
      }
    };

    searchInput.oninput = () => renderList(searchInput.value);
    renderList();
  }

  // 4. Export PDF Dialog
  setupExportPdf() {
    const unfoldCheckbox = document.getElementById("chk-unfold-exercises");
    const exportBtn = document.getElementById("btn-confirm-export-pdf");

    if (exportBtn) {
      exportBtn.onclick = () => {
        const shouldUnfold = unfoldCheckbox ? unfoldCheckbox.checked : true;
        this.closeCurrentDialog();
        this.app.executeExportPdf(shouldUnfold);
      };
    }
  }
}
