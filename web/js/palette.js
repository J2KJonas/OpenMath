/**
 * OpenMath Web Math Palettes & Interactive Matrix Wizard
 * Provides categorized mathematical templates, symbols, functions, and dialogs.
 */

export class PaletteManager {
  constructor(onInsertCallback) {
    this.onInsert = onInsertCallback || (() => {});
    this.matrixRows = 2;
    this.matrixCols = 2;
  }

  init() {
    this.bindAccordionHeaders();
    this.bindPaletteButtons();
    this.initMatrixWizard();
  }

  bindAccordionHeaders() {
    const headers = document.querySelectorAll(".palette-section-header");
    headers.forEach((header) => {
      header.addEventListener("click", () => {
        const section = header.parentElement;
        const body = section.querySelector(".palette-section-body");
        const icon = header.querySelector(".chevron-icon");
        const isOpen = body.style.display !== "none";

        body.style.display = isOpen ? "none" : "grid";
        if (icon) {
          icon.style.transform = isOpen ? "rotate(0deg)" : "rotate(90deg)";
        }
      });
    });
  }

  bindPaletteButtons() {
    document.addEventListener("click", (e) => {
      const btn = e.target.closest("[data-insert]");
      if (!btn) return;
      e.preventDefault();
      const insertText = btn.getAttribute("data-insert");
      const offset = parseInt(btn.getAttribute("data-cursor-offset") || "0", 10);
      this.onInsert(insertText, offset);
    });
  }

  initMatrixWizard() {
    const openBtn = document.getElementById("open-matrix-wizard");
    const modal = document.getElementById("matrix-wizard-modal");
    const closeBtn = document.getElementById("close-matrix-wizard");
    const cancelBtn = document.getElementById("cancel-matrix-wizard");
    const applyBtn = document.getElementById("apply-matrix-wizard");
    const rowsInput = document.getElementById("matrix-rows");
    const colsInput = document.getElementById("matrix-cols");
    const presetSelect = document.getElementById("matrix-preset");

    if (!modal) return;

    const openModal = () => {
      modal.classList.add("open");
      this.renderMatrixGrid();
    };

    const closeModal = () => {
      modal.classList.remove("open");
    };

    if (openBtn) openBtn.addEventListener("click", openModal);
    if (closeBtn) closeBtn.addEventListener("click", closeModal);
    if (cancelBtn) cancelBtn.addEventListener("click", closeModal);

    if (rowsInput) {
      rowsInput.addEventListener("change", (e) => {
        this.matrixRows = Math.max(1, Math.min(6, parseInt(e.target.value || 2, 10)));
        this.renderMatrixGrid();
      });
    }

    if (colsInput) {
      colsInput.addEventListener("change", (e) => {
        this.matrixCols = Math.max(1, Math.min(6, parseInt(e.target.value || 2, 10)));
        this.renderMatrixGrid();
      });
    }

    if (presetSelect) {
      presetSelect.addEventListener("change", (e) => {
        this.applyPreset(e.target.value);
      });
    }

    if (applyBtn) {
      applyBtn.addEventListener("click", () => {
        const matrixStr = this.generateMatrixCode();
        this.onInsert(matrixStr, 0);
        closeModal();
      });
    }
  }

  renderMatrixGrid() {
    const container = document.getElementById("matrix-grid-container");
    if (!container) return;

    container.innerHTML = "";
    container.style.gridTemplateColumns = `repeat(${this.matrixCols}, minmax(45px, 1fr))`;

    for (let r = 0; r < this.matrixRows; r++) {
      for (let c = 0; c < this.matrixCols; c++) {
        const input = document.createElement("input");
        input.type = "text";
        input.className = "matrix-cell-input";
        input.dataset.row = r;
        input.dataset.col = c;
        input.value = r === c ? "1" : "0"; // default identity-like
        container.appendChild(input);
      }
    }
  }

  applyPreset(preset) {
    const inputs = document.querySelectorAll(".matrix-cell-input");
    inputs.forEach((input) => {
      const r = parseInt(input.dataset.row, 10);
      const c = parseInt(input.dataset.col, 10);

      if (preset === "identity") {
        input.value = r === c ? "1" : "0";
      } else if (preset === "zeros") {
        input.value = "0";
      } else if (preset === "ones") {
        input.value = "1";
      } else if (preset === "diagonal") {
        input.value = r === c ? `${r + 1}` : "0";
      }
    });
  }

  generateMatrixCode() {
    const rows = [];
    for (let r = 0; r < this.matrixRows; r++) {
      const rowVals = [];
      for (let c = 0; c < this.matrixCols; c++) {
        const input = document.querySelector(`.matrix-cell-input[data-row="${r}"][data-col="${c}"]`);
        const val = input ? input.value.trim() || "0" : "0";
        rowVals.push(val);
      }
      rows.push(`[${rowVals.join(", ")}]`);
    }
    return `Matrix([${rows.join(", ")}])`;
  }
}
