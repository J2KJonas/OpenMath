/**
 * OpenMath Web Worksheet Manager & KaTeX Typeset Renderer
 * Manages calculation cells [In n] / [Out n], precision switches, and copy/export capabilities.
 */

import { MathPlotter } from "./plotter.js";

export class WorksheetManager {
  constructor(containerEl, onEvaluateRequest, options = {}) {
    this.container = containerEl;
    this.onEvaluate = onEvaluateRequest;
    this.theme = options.theme || "dark";
    this.globalPrecision = 6;
    this.globalMode = "exact"; // "exact" | "numeric"

    this.cells = [];
    this.cellCounter = 0;
    this.activeCellId = null;
  }

  setTheme(theme) {
    this.theme = theme;
    // Re-render any existing plots
    this.cells.forEach((cell) => {
      if (cell.result && cell.result.is_plot && cell.plotInstance) {
        cell.plotInstance.options.theme = theme;
        cell.plotInstance.render();
      }
    });
  }

  setGlobalPrecision(precision) {
    this.globalPrecision = parseInt(precision, 10);
  }

  setGlobalMode(mode) {
    this.globalMode = mode;
    this.cells.forEach((cell) => {
      if (cell.result && !cell.result.is_plot && !cell.result.error) {
        this.renderMathOutput(cell);
      }
    });
  }

  getActiveInput() {
    if (!this.activeCellId) {
      if (this.cells.length > 0) {
        return this.cells[this.cells.length - 1].inputEl;
      }
      return null;
    }
    const cell = this.cells.find((c) => c.id === this.activeCellId);
    return cell ? cell.inputEl : null;
  }

  insertTextAtCursor(text, cursorOffset = 0) {
    let inputEl = this.getActiveInput();
    if (!inputEl) {
      const newCell = this.addCell("", true);
      inputEl = newCell.inputEl;
    }

    const start = inputEl.selectionStart || inputEl.value.length;
    const end = inputEl.selectionEnd || inputEl.value.length;
    const val = inputEl.value;

    inputEl.value = val.substring(0, start) + text + val.substring(end);
    const newCursor = start + text.length + cursorOffset;
    inputEl.focus();
    inputEl.setSelectionRange(newCursor, newCursor);
  }

  addCell(initialText = "", focus = true) {
    this.cellCounter++;
    const idx = this.cellCounter;
    const cellId = `cell_${idx}`;

    const cellObj = {
      id: cellId,
      index: idx,
      mode: this.globalMode,
      precision: this.globalPrecision,
      result: null,
      plotInstance: null,
      dom: null,
      inputEl: null
    };

    const cellEl = document.createElement("div");
    cellEl.className = "worksheet-cell";
    cellEl.id = cellId;

    cellEl.innerHTML = `
      <div class="cell-header">
        <div class="cell-label"><span class="cell-in-tag">In [${idx}]</span></div>
        <div class="cell-controls">
          <button class="cell-btn btn-eval" title="Execute (Shift+Enter)">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"/></svg>
            <span>Run</span>
          </button>
          <button class="cell-btn btn-clear-cell" title="Clear cell content">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6L6 18M6 6l12 12"/></svg>
          </button>
        </div>
      </div>
      <div class="cell-input-row">
        <textarea class="cell-input" placeholder="Type a mathematical formula or command (e.g. diff(sin(x), x), solve(x^2 - 4 = 0), plot(sin(x)))..." rows="1">${initialText}</textarea>
      </div>
      <div class="cell-output-row" style="display: none;">
        <div class="output-header">
          <span class="cell-out-tag">Out [${idx}]</span>
          <div class="output-actions">
            <div class="mode-switch-pill" title="Toggle Exact vs Numeric evaluation">
              <button class="pill-btn mode-exact active">Exact</button>
              <button class="pill-btn mode-numeric">Numeric</button>
            </div>
            <button class="copy-btn copy-latex" title="Copy LaTeX formula">LaTeX</button>
            <button class="copy-btn copy-text" title="Copy Plain Text">Text</button>
            <span class="timing-badge"></span>
          </div>
        </div>
        <div class="output-content"></div>
      </div>
    `;

    const inputEl = cellEl.querySelector(".cell-input");
    cellObj.dom = cellEl;
    cellObj.inputEl = inputEl;

    // Auto-expand textarea
    const autoResize = () => {
      inputEl.style.height = "auto";
      inputEl.style.height = `${inputEl.scrollHeight}px`;
    };
    inputEl.addEventListener("input", autoResize);

    // Focus tracking
    inputEl.addEventListener("focus", () => {
      this.activeCellId = cellId;
      document.querySelectorAll(".worksheet-cell").forEach((c) => c.classList.remove("focused"));
      cellEl.classList.add("focused");
    });

    // Keyboard Shortcuts
    inputEl.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && (e.shiftKey || e.ctrlKey)) {
        e.preventDefault();
        this.evaluateCell(cellId);
      }
    });

    // Button event listeners
    const evalBtn = cellEl.querySelector(".btn-eval");
    evalBtn.addEventListener("click", () => this.evaluateCell(cellId));

    const clearBtn = cellEl.querySelector(".btn-clear-cell");
    clearBtn.addEventListener("click", () => this.deleteCell(cellId));

    // Mode toggles
    const exactBtn = cellEl.querySelector(".mode-exact");
    const numBtn = cellEl.querySelector(".mode-numeric");

    exactBtn.addEventListener("click", () => {
      cellObj.mode = "exact";
      exactBtn.classList.add("active");
      numBtn.classList.remove("active");
      this.renderMathOutput(cellObj);
    });

    numBtn.addEventListener("click", () => {
      cellObj.mode = "numeric";
      numBtn.classList.add("active");
      exactBtn.classList.remove("active");
      this.renderMathOutput(cellObj);
    });

    // Copy handlers
    const copyLatexBtn = cellEl.querySelector(".copy-latex");
    copyLatexBtn.addEventListener("click", () => {
      if (cellObj.result && (cellObj.result.exact_latex || cellObj.result.numeric_latex)) {
        const str = cellObj.mode === "numeric" ? cellObj.result.numeric_latex : cellObj.result.exact_latex;
        this.copyToClipboard(str, copyLatexBtn);
      }
    });

    const copyTextBtn = cellEl.querySelector(".copy-text");
    copyTextBtn.addEventListener("click", () => {
      if (cellObj.result && (cellObj.result.exact_text || cellObj.result.numeric_text)) {
        const str = cellObj.mode === "numeric" ? cellObj.result.numeric_text : cellObj.result.exact_text;
        this.copyToClipboard(str, copyTextBtn);
      }
    });

    this.container.appendChild(cellEl);
    this.cells.push(cellObj);

    if (focus) {
      inputEl.focus();
      this.activeCellId = cellId;
    }
    autoResize();
    return cellObj;
  }

  deleteCell(cellId) {
    const idx = this.cells.findIndex((c) => c.id === cellId);
    if (idx !== -1) {
      const cell = this.cells[idx];
      cell.dom.remove();
      this.cells.splice(idx, 1);
    }
    if (this.cells.length === 0) {
      this.addCell();
    }
  }

  clearWorksheet() {
    this.container.innerHTML = "";
    this.cells = [];
    this.cellCounter = 0;
    this.activeCellId = null;
    this.addCell();
  }

  loadImportedCells(cells) {
    if (!cells || !cells.length) return;
    this.container.innerHTML = "";
    this.cells = [];
    this.cellCounter = 0;
    this.activeCellId = null;

    cells.forEach((c) => {
      const inp = c.input !== undefined ? c.input : "";
      if (inp.trim() !== "") {
        this.addCell(inp, false);
      }
    });

    if (this.cells.length === 0) {
      this.addCell("", true);
    } else {
      this.activeCellId = this.cells[0].id;
      this.cells[0].dom.classList.add("focused");
    }
  }

  evaluateCell(cellId) {
    const cell = this.cells.find((c) => c.id === cellId);
    if (!cell) return;

    const expr = cell.inputEl.value.trim();
    if (!expr) return;

    const outputRow = cell.dom.querySelector(".cell-output-row");
    const outputContent = cell.dom.querySelector(".output-content");
    outputRow.style.display = "block";
    outputContent.innerHTML = `<div class="cell-calculating"><div class="spinner-sm"></div><span>Computing with CAS engine...</span></div>`;

    cell.dom.classList.add("calculating");

    this.onEvaluate(cellId, expr, this.globalPrecision);
  }

  evaluateAll() {
    this.cells.forEach((cell) => {
      if (cell.inputEl.value.trim()) {
        this.evaluateCell(cell.id);
      }
    });
  }

  handleResult(cellId, result) {
    const cell = this.cells.find((c) => c.id === cellId);
    if (!cell) return;

    cell.dom.classList.remove("calculating");
    cell.result = result;

    const outputRow = cell.dom.querySelector(".cell-output-row");
    const timingBadge = cell.dom.querySelector(".timing-badge");
    outputRow.style.display = "block";

    if (timingBadge && result.execution_time_ms !== undefined) {
      timingBadge.textContent = `${result.execution_time_ms} ms`;
    }

    if (result.error) {
      const outputContent = cell.dom.querySelector(".output-content");
      outputContent.innerHTML = `
        <div class="cell-error-banner">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
          <span>${this.escapeHtml(result.error)}</span>
        </div>
      `;
      return;
    }

    this.renderMathOutput(cell);

    // If this was the last cell and has non-empty input, auto-append a new cell for flow
    const cellIndex = this.cells.indexOf(cell);
    if (cellIndex === this.cells.length - 1) {
      this.addCell("", false);
    }
  }

  renderMathOutput(cell) {
    const res = cell.result;
    if (!res) return;

    const outputContent = cell.dom.querySelector(".output-content");
    outputContent.innerHTML = "";

    if (res.is_plot && res.plot_data) {
      // Render plot canvas
      const canvas = document.createElement("canvas");
      canvas.className = "plot-canvas";
      canvas.style.width = "100%";
      canvas.style.height = "360px";
      outputContent.appendChild(canvas);

      cell.plotInstance = new MathPlotter(canvas, res.plot_data, {
        theme: this.theme
      });
      return;
    }

    // Mathematical formula rendering via KaTeX
    const isNum = cell.mode === "numeric";
    const latexStr = isNum ? (res.numeric_latex || res.exact_latex) : (res.exact_latex || res.numeric_latex);
    const plainText = isNum ? (res.numeric_text || res.exact_text) : (res.exact_text || res.numeric_text);

    if (latexStr && typeof katex !== "undefined") {
      const mathEl = document.createElement("div");
      mathEl.className = "katex-rendered-output";
      try {
        katex.render(latexStr, mathEl, {
          throwOnError: false,
          displayMode: true
        });
        outputContent.appendChild(mathEl);
      } catch (err) {
        outputContent.textContent = plainText || latexStr;
      }
    } else {
      const preEl = document.createElement("pre");
      preEl.className = "plain-text-output";
      preEl.textContent = plainText || "";
      outputContent.appendChild(preEl);
    }
  }

  copyToClipboard(text, triggerBtn) {
    navigator.clipboard.writeText(text).then(() => {
      const origText = triggerBtn.textContent;
      triggerBtn.textContent = "Copied!";
      triggerBtn.classList.add("copied");
      setTimeout(() => {
        triggerBtn.textContent = origText;
        triggerBtn.classList.remove("copied");
      }, 1500);
    });
  }

  escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
  }

  exportDocument(format = "markdown") {
    let content = "";
    const date = new Date().toISOString().split("T")[0];

    if (format === "markdown") {
      content = `# OpenMath Worksheet Export\n*Exported on ${date}*\n\n---\n\n`;
      this.cells.forEach((cell) => {
        const inp = cell.inputEl.value.trim();
        if (!inp) return;
        content += `### In [${cell.index}]\n\`\`\`\n${inp}\n\`\`\`\n\n`;
        if (cell.result) {
          const out = cell.result.exact_text || cell.result.exact_latex;
          content += `### Out [${cell.index}]\n$$${cell.result.exact_latex || out}$$\n\n`;
        }
      });
      this.downloadFile(content, "worksheet.md", "text/markdown");
    } else if (format === "latex") {
      content = `\\documentclass{article}\n\\usepackage{amsmath}\n\\usepackage{amssymb}\n\\begin{document}\n\\title{OpenMath Worksheet}\n\\date{${date}}\n\\maketitle\n\n`;
      this.cells.forEach((cell) => {
        const inp = cell.inputEl.value.trim();
        if (!inp) return;
        content += `\\textbf{In [${cell.index}]:} \\texttt{${inp}}\\\\\n`;
        if (cell.result && cell.result.exact_latex) {
          content += `\\textbf{Out [${cell.index}]:} \\[ ${cell.result.exact_latex} \\]\n\\vspace{1em}\n\n`;
        }
      });
      content += "\\end{document}\n";
      this.downloadFile(content, "worksheet.tex", "application/x-latex");
    } else if (format === "json") {
      const data = this.cells.map((c) => ({
        index: c.index,
        input: c.inputEl.value,
        mode: c.mode,
        result: c.result
      }));
      content = JSON.stringify(data, null, 2);
      this.downloadFile(content, "worksheet.json", "application/json");
    }
  }

  downloadFile(content, filename, contentType) {
    const blob = new Blob([content], { type: contentType });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }
}
