/**
 * OpenMath Palette Sidebar Panel
 * Implements Palettes, Formulas, and Variables tabs with accordion sections matching ui/palette_panel.py.
 */

export class PaletteManager {
  constructor(app) {
    this.app = app;
    this.dockElement = document.getElementById("palette-dock");
    this.initPaletteTabs();
    this.initAccordions();
    this.initPaletteButtons();
  }

  initPaletteTabs() {
    const tabBtns = document.querySelectorAll(".dock-tab-btn");
    const contents = document.querySelectorAll(".dock-tab-content");

    tabBtns.forEach(btn => {
      btn.addEventListener("click", () => {
        tabBtns.forEach(b => b.classList.remove("active"));
        contents.forEach(c => c.style.display = "none");

        btn.classList.add("active");
        const targetId = btn.dataset.tab;
        const targetContent = document.getElementById(targetId);
        if (targetContent) {
          targetContent.style.display = "block";
          if (targetId === "dock-tab-variables") {
            this.refreshVariables();
          }
        }
      });
    });
  }

  initAccordions() {
    document.querySelectorAll(".accordion-header").forEach(header => {
      header.addEventListener("click", () => {
        const body = header.nextElementSibling;
        const arrow = header.querySelector(".accordion-arrow");
        if (body) {
          const isCollapsed = body.classList.toggle("collapsed");
          if (arrow) {
            arrow.textContent = isCollapsed ? "▶" : "▼";
          }
        }
      });
    });
  }

  initPaletteButtons() {
    // Buttons with data-insert attribute
    document.querySelectorAll(".palette-cell-btn[data-insert]").forEach(btn => {
      btn.addEventListener("click", () => {
        const template = btn.dataset.insert;
        if (template) {
          this.app.insertTemplateIntoActiveCell(template);
        }
      });
    });

    // Matrix wizard trigger
    const matrixWizardBtn = document.getElementById("btn-open-matrix-wizard");
    if (matrixWizardBtn) {
      matrixWizardBtn.addEventListener("click", () => {
        this.app.dialogManager.openDialog("dialog-matrix-wizard");
      });
    }

    // Formulas tab buttons
    document.querySelectorAll(".formula-insert-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        const formula = btn.dataset.formula;
        if (formula) {
          this.app.insertTemplateIntoActiveCell(formula);
        }
      });
    });

    // Clear variables button
    const clearVarsBtn = document.getElementById("btn-clear-variables");
    if (clearVarsBtn) {
      clearVarsBtn.addEventListener("click", () => {
        this.app.worker.postMessage({ type: "RESET" });
        setTimeout(() => this.refreshVariables(), 150);
      });
    }

    // Palette dock close button
    const closeBtn = document.getElementById("btn-close-palette-dock");
    if (closeBtn) {
      closeBtn.addEventListener("click", () => {
        this.dockElement.style.display = "none";
        this.app.updateViewMenuCheckmarks();
      });
    }
  }

  refreshVariables() {
    if (this.app.worker) {
      this.app.worker.postMessage({ type: "WHOS" });
    }
  }

  updateVariablesTable(varsObj) {
    const tableBody = document.getElementById("variables-table-body");
    if (!tableBody) return;

    if (!varsObj || Object.keys(varsObj).length === 0) {
      tableBody.innerHTML = `<tr><td colspan="2" style="text-align: center; color: var(--text-muted); padding: 12px;">No user variables defined.</td></tr>`;
      return;
    }

    let rowsHtml = "";
    for (const [name, val] of Object.entries(varsObj)) {
      rowsHtml += `
        <tr style="border-bottom: 1px solid var(--border-light); cursor: pointer;" title="Click to insert variable '${name}'">
          <td style="padding: 4px 8px; font-weight: bold; color: var(--accent);">${name}</td>
          <td style="padding: 4px 8px; font-family: monospace; color: var(--text-primary);">${val}</td>
        </tr>
      `;
    }
    tableBody.innerHTML = rowsHtml;

    tableBody.querySelectorAll("tr").forEach(tr => {
      tr.onclick = () => {
        const varName = tr.firstElementChild.textContent.trim();
        this.app.insertTemplateIntoActiveCell(varName);
      };
    });
  }
}
