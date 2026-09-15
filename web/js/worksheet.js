/**
 * OpenMath Interactive Worksheet View
 * Replicates ui/worksheet_view.py and ui/worksheet_cell.py:
 * Stacked execution cells with left bracket bar `[`, classic dark red prompt `[> `,
 * 2D/1D/Text modes, KaTeX formula outputs in royal blue `#0000aa`, equation labels `(1)`,
 * collapsible section headers with hierarchical tree guidelines `└───`, plots, and error suggestions.
 */

import { MathPlotter } from "./plotter.js";

// Unicode sub/superscript map matching ui/worksheet_cell.py
const SUPER_MAP = {
  '0': '⁰', '1': '¹', '2': '²', '3': '³', '4': '⁴',
  '5': '⁵', '6': '⁶', '7': '⁷', '8': '⁸', '9': '⁹',
  '+': '⁺', '-': '⁻', '=': '⁼', '(': '⁽', ')': '⁾',
  'a': 'ᵃ', 'b': 'ᵇ', 'c': 'ᶜ', 'd': 'ᵈ', 'e': 'ᵉ',
  'f': 'ᶠ', 'g': 'ᵍ', 'h': 'ʰ', 'i': 'ⁱ', 'j': 'ʲ',
  'k': 'ᵏ', 'l': 'ˡ', 'm': 'ᵐ', 'n': 'ⁿ', 'o': 'ᵒ',
  'p': 'ᵖ', 'r': 'ʳ', 's': 'ˢ', 't': 'ᵗ', 'u': 'ᵘ',
  'v': 'ᵛ', 'w': 'ʷ', 'x': 'ˣ', 'y': 'ʸ', 'z': 'ᶻ',
  '*': '·', '·': '·'
};

const SUB_MAP = {
  '0': '₀', '1': '₁', '2': '₂', '3': '₃', '4': '₄',
  '5': '₅', '6': '₆', '7': '₇', '8': '₈', '9': '₉',
  '+': '₊', '-': '₋', '=': '₌', '(': '₍', ')': '₎',
  'a': 'ₐ', 'b': 'ᵦ', 'e': 'ₑ', 'h': 'ₕ', 'i': 'ᵢ', 'j': 'ⱼ',
  'k': 'ₖ', 'l': 'ₗ', 'm': 'ₘ', 'n': 'ₙ', 'o': 'ₒ',
  'p': 'ₚ', 'r': 'ᵣ', 's': 'ₛ', 't': 'ₜ', 'u': 'ᵤ',
  'v': 'ᵥ', 'x': 'ₓ'
};

export function formatSubscriptsAndSuperscripts(text) {
  if (!text || (!text.includes('_') && !text.includes('^'))) return text;
  let formatted = text;
  // Superscripts ^2 or ^{abc}
  formatted = formatted.replace(/\^{([0-9a-zA-Z+-]+)}/g, (_, chars) => {
    return Array.from(chars).map(c => SUPER_MAP[c] || c).join('');
  });
  formatted = formatted.replace(/\^([0-9a-zA-Z])/g, (_, c) => SUPER_MAP[c] || `^${c}`);

  // Subscripts _1 or _{12}
  formatted = formatted.replace(/_([0-9a-zA-Z])/g, (_, c) => SUB_MAP[c] || `_${c}`);
  formatted = formatted.replace(/_{([0-9a-zA-Z+-]+)}/g, (_, chars) => {
    return Array.from(chars).map(c => SUB_MAP[c] || c).join('');
  });
  return formatted;
}

export class WorksheetView {
  constructor(app, container, docId, title = "Untitled-1.mw") {
    this.app = app;
    this.container = container;
    this.docId = docId;
    this.title = title;
    this.filePath = null;
    this.isEditable = true;
    this.zoom = 100;

    this.cells = [];
    this.activeCellId = null;
    this.executionCounter = 0;
    this.plotInstances = new Map();

    this.undoStack = [];
    this.redoStack = [];

    this.renderSkeleton();
    this.addCell(); // Default first empty cell
  }

  renderSkeleton() {
    this.container.innerHTML = `
      <div class="worksheet-scroll-container">
        <div class="worksheet-canvas" id="canvas-${this.docId}">
          <canvas class="scope-overlay-canvas" id="overlay-${this.docId}"></canvas>
          <div class="cells-list" id="cells-list-${this.docId}"></div>
          <div class="worksheet-click-spacer" id="spacer-${this.docId}"></div>
        </div>
      </div>
    `;

    this.cellsContainer = document.getElementById(`cells-list-${this.docId}`);
    this.scopeCanvas = document.getElementById(`overlay-${this.docId}`);
    this.spacer = document.getElementById(`spacer-${this.docId}`);

    // Click anywhere on bottom blank area to insert/focus cell
    this.spacer.addEventListener("click", () => {
      if (!this.isEditable) return;
      if (this.cells.length > 0) {
        const lastCell = this.cells[this.cells.length - 1];
        if (lastCell.input.trim() === "" && !lastCell.isSectionHeader) {
          this.focusCell(lastCell.id);
          return;
        }
      }
      this.addCell();
    });

    window.addEventListener("resize", () => this.drawScopeOverlay());
  }

  addCell(options = {}) {
    const id = "cell_" + Math.random().toString(36).substring(2, 9);
    const mode = options.mode || "2d_math"; // "2d_math", "1d_math", "text", "section"
    const isSection = options.isSectionHeader || mode === "section";
    const sectionLevel = options.sectionLevel || 0;
    const title = options.sectionTitle || "";
    const input = options.input || "";
    const insertAfterId = options.insertAfterId;

    const cellObj = {
      id,
      mode,
      isSectionHeader: isSection,
      sectionLevel,
      sectionTitle: title,
      isCollapsed: false,
      input,
      result: options.result || null,
      error: options.error || null,
      suggestion: options.suggestion || null,
      equationIndex: null,
      domElement: null
    };

    if (insertAfterId) {
      const idx = this.cells.findIndex(c => c.id === insertAfterId);
      if (idx !== -1) {
        this.cells.splice(idx + 1, 0, cellObj);
      } else {
        this.cells.push(cellObj);
      }
    } else {
      this.cells.push(cellObj);
    }

    this.renderCellDom(cellObj);
    this.focusCell(id);
    this.drawScopeOverlay();
    return cellObj;
  }

  addCellWithInput(expr, autoExecute = false) {
    const cell = this.addCell({ input: expr });
    if (autoExecute) {
      setTimeout(() => this.executeCell(cell.id), 50);
    }
  }

  renderCellDom(cell) {
    const cellDiv = document.createElement("div");
    cellDiv.className = `worksheet-cell ${cell.isSectionHeader ? 'section-header-cell level-' + cell.sectionLevel : ''}`;
    cellDiv.id = cell.id;

    if (cell.isSectionHeader) {
      cellDiv.innerHTML = `
        <div class="section-row">
          <button class="section-toggle-btn" title="Toggle Section Collapse">${cell.isCollapsed ? '▶' : '▼'}</button>
          <div class="section-title-edit" contenteditable="${this.isEditable}" placeholder="Section Title...">${cell.sectionTitle || ''}</div>
        </div>
      `;

      const toggleBtn = cellDiv.querySelector(".section-toggle-btn");
      toggleBtn.onclick = (e) => {
        e.stopPropagation();
        cell.isCollapsed = !cell.isCollapsed;
        toggleBtn.textContent = cell.isCollapsed ? '▶' : '▼';
        this.updateSectionFolding();
        this.drawScopeOverlay();
      };

      const titleEdit = cellDiv.querySelector(".section-title-edit");
      titleEdit.oninput = () => {
        cell.sectionTitle = titleEdit.innerText;
      };
      titleEdit.onfocus = () => this.setActiveCell(cell.id);
    } else {
      // Regular execution group cell
      cellDiv.innerHTML = `
        <div class="cell-bracket-bar"></div>
        <div class="cell-input-row">
          <span class="cell-prompt">[&gt; </span>
          <div class="cell-input-edit mode-${cell.mode === '1d_math' ? '1d' : (cell.mode === 'text' ? 'text' : '2d')}"
               contenteditable="${this.isEditable}"
               spellcheck="false">${cell.input || ''}</div>
        </div>
        <div class="cell-output-container"></div>
      `;

      const inputEdit = cellDiv.querySelector(".cell-input-edit");

      inputEdit.onfocus = () => this.setActiveCell(cell.id);

      inputEdit.oninput = () => {
        cell.input = inputEdit.innerText;
        // In 2D Math mode, auto-convert _1 and ^2 to Unicode sub/superscript
        if (cell.mode === "2d_math") {
          const raw = inputEdit.innerText;
          const formatted = formatSubscriptsAndSuperscripts(raw);
          if (raw !== formatted) {
            const sel = window.getSelection();
            const offset = sel.focusOffset;
            inputEdit.innerText = formatted;
            // Restore caret
            try {
              const range = document.createRange();
              range.setStart(inputEdit.firstChild || inputEdit, Math.min(offset, inputEdit.innerText.length));
              range.collapse(true);
              sel.removeAllRanges();
              sel.addRange(range);
            } catch (e) {}
            cell.input = formatted;
          }
        }
        this.app.contextPanel.setTargetExpression(cell.input);
      };

      inputEdit.onkeydown = (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
          e.preventDefault();
          this.executeCell(cell.id);
        } else if (e.key === "F5") {
          e.preventDefault();
          this.toggleCellMode(cell.id);
        } else if (e.key === "Backspace" && inputEdit.innerText.trim() === "") {
          if (this.cells.length > 1) {
            e.preventDefault();
            this.deleteCell(cell.id);
          }
        } else if (e.key === "ArrowDown") {
          const idx = this.cells.findIndex(c => c.id === cell.id);
          if (idx < this.cells.length - 1) {
            this.focusCell(this.cells[idx + 1].id);
          }
        } else if (e.key === "ArrowUp") {
          const idx = this.cells.findIndex(c => c.id === cell.id);
          if (idx > 0) {
            this.focusCell(this.cells[idx - 1].id);
          }
        }
      };
    }

    cell.domElement = cellDiv;

    // Insert into DOM in order
    const idx = this.cells.findIndex(c => c.id === cell.id);
    if (idx === 0) {
      this.cellsContainer.prepend(cellDiv);
    } else {
      const prevDom = this.cells[idx - 1]?.domElement;
      if (prevDom && prevDom.parentNode) {
        prevDom.after(cellDiv);
      } else {
        this.cellsContainer.appendChild(cellDiv);
      }
    }

    if (cell.result || cell.error) {
      this.renderCellOutput(cell);
    }
  }

  focusCell(cellId) {
    this.setActiveCell(cellId);
    const cell = this.cells.find(c => c.id === cellId);
    if (!cell || !cell.domElement) return;

    const editable = cell.domElement.querySelector(".cell-input-edit, .section-title-edit");
    if (editable) {
      editable.focus();
      // Place cursor at end
      try {
        const range = document.createRange();
        range.selectNodeContents(editable);
        range.collapse(false);
        const sel = window.getSelection();
        sel.removeAllRanges();
        sel.addRange(range);
      } catch (e) {}
    }
  }

  setActiveCell(cellId) {
    this.activeCellId = cellId;
    this.cells.forEach(c => {
      if (c.domElement) {
        if (c.id === cellId) {
          c.domElement.classList.add("active");
        } else {
          c.domElement.classList.remove("active");
        }
      }
    });

    const active = this.cells.find(c => c.id === cellId);
    if (active) {
      this.app.updateContextBar(active.mode);
      this.app.contextPanel.setTargetExpression(active.input || active.sectionTitle);
      this.app.updateStatusMode(active.mode);
    }
  }

  toggleCellMode(cellId) {
    const cell = this.cells.find(c => c.id === cellId);
    if (!cell || cell.isSectionHeader) return;

    // Cycle 2d_math -> 1d_math -> text -> 2d_math
    if (cell.mode === "2d_math") cell.mode = "1d_math";
    else if (cell.mode === "1d_math") cell.mode = "text";
    else cell.mode = "2d_math";

    const editEl = cell.domElement?.querySelector(".cell-input-edit");
    if (editEl) {
      editEl.className = `cell-input-edit mode-${cell.mode === '1d_math' ? '1d' : (cell.mode === 'text' ? 'text' : '2d')}`;
    }
    this.app.updateContextBar(cell.mode);
    this.app.updateStatusMode(cell.mode);
  }

  setCellMode(cellId, mode) {
    const cell = this.cells.find(c => c.id === cellId);
    if (!cell || cell.isSectionHeader) return;

    cell.mode = mode;
    const editEl = cell.domElement?.querySelector(".cell-input-edit");
    if (editEl) {
      editEl.className = `cell-input-edit mode-${mode === '1d_math' ? '1d' : (mode === 'text' ? 'text' : '2d')}`;
    }
    this.app.updateContextBar(cell.mode);
    this.app.updateStatusMode(cell.mode);
  }

  executeCell(cellId) {
    const cell = this.cells.find(c => c.id === cellId);
    if (!cell || cell.isSectionHeader) return;

    const input = (cell.input || "").trim();
    if (!input) {
      // Advance to next cell or create one
      this.advanceToNextCell(cellId);
      return;
    }

    this.app.worker.postMessage({
      type: "EVALUATE",
      id: cell.id,
      docId: this.docId,
      expr: input,
      precision: this.app.precision || 10
    });

    this.app.updateStatusMessage("Evaluating...");
  }

  handleCellResult(resultData) {
    const cell = this.cells.find(c => c.id === resultData.id);
    if (!cell) return;

    cell.error = resultData.error || null;
    cell.suggestion = resultData.suggestion || null;
    cell.result = resultData;

    if (!cell.error) {
      this.executionCounter += 1;
      cell.equationIndex = this.executionCounter;
    } else {
      cell.equationIndex = null;
    }

    this.renderCellOutput(cell);
    this.advanceToNextCell(cell.id);
    this.drawScopeOverlay();

    this.app.palette.refreshVariables();
    if (resultData.execution_time_ms) {
      this.app.updateExecutionTime(resultData.execution_time_ms / 1000);
    }
    this.app.updateStatusMessage("Ready");
  }

  renderCellOutput(cell) {
    if (!cell.domElement) return;
    const outputContainer = cell.domElement.querySelector(".cell-output-container");
    if (!outputContainer) return;

    outputContainer.innerHTML = "";

    // If there is an error
    if (cell.error) {
      const errBox = document.createElement("div");
      errBox.className = "cell-error-box";
      errBox.innerHTML = `
        <span class="error-title">Error:</span>
        <span>${cell.error}</span>
        ${cell.suggestion ? `<button class="error-suggestion-btn">Did you mean: <code>${cell.suggestion}</code>?</button>` : ''}
      `;

      if (cell.suggestion) {
        const suggBtn = errBox.querySelector(".error-suggestion-btn");
        suggBtn.onclick = () => {
          cell.input = cell.suggestion;
          const editEl = cell.domElement.querySelector(".cell-input-edit");
          if (editEl) editEl.innerText = cell.suggestion;
          this.executeCell(cell.id);
        };
      }
      outputContainer.appendChild(errBox);
      return;
    }

    const res = cell.result;
    if (!res || res.suppress_output) return;

    // If plot
    if (res.is_plot && res.plot_data) {
      const plotBox = document.createElement("div");
      plotBox.className = "cell-plot-container";
      const canvas = document.createElement("canvas");
      canvas.className = "cell-plot-canvas";
      plotBox.appendChild(canvas);
      outputContainer.appendChild(plotBox);

      // Create MathPlotter instance
      setTimeout(() => {
        const plotter = new MathPlotter(canvas, res.plot_data, { theme: this.app.theme });
        this.plotInstances.set(cell.id, plotter);
      }, 0);
      return;
    }

    // Formula KaTeX Output
    const outBox = document.createElement("div");
    outBox.className = "cell-output-box";

    const mathEl = document.createElement("div");
    mathEl.className = "cell-output-math";

    const latex = res.exact_latex || res.numeric_latex || "";
    const plainText = res.exact_text || res.numeric_text || "";

    if (latex && window.katex) {
      try {
        window.katex.render(latex, mathEl, { displayMode: true, throwOnError: false });
      } catch (e) {
        mathEl.textContent = plainText;
      }
    } else {
      mathEl.textContent = plainText;
    }

    const eqLabel = document.createElement("div");
    eqLabel.className = "cell-equation-label";
    if (cell.equationIndex) {
      eqLabel.textContent = `(${cell.equationIndex})`;
    }

    outBox.appendChild(mathEl);
    outBox.appendChild(eqLabel);
    outputContainer.appendChild(outBox);
  }

  advanceToNextCell(currentCellId) {
    const idx = this.cells.findIndex(c => c.id === currentCellId);
    if (idx !== -1 && idx < this.cells.length - 1) {
      this.focusCell(this.cells[idx + 1].id);
    } else {
      const newCell = this.addCell();
      this.focusCell(newCell.id);
    }
  }

  deleteCell(cellId) {
    const idx = this.cells.findIndex(c => c.id === cellId);
    if (idx === -1) return;

    const cell = this.cells[idx];
    if (cell.domElement && cell.domElement.parentNode) {
      cell.domElement.parentNode.removeChild(cell.domElement);
    }
    this.cells.splice(idx, 1);

    if (this.cells.length === 0) {
      this.addCell();
    } else {
      const nextIdx = Math.max(0, idx - 1);
      this.focusCell(this.cells[nextIdx].id);
    }
    this.drawScopeOverlay();
  }

  runAllCells() {
    for (const c of this.cells) {
      if (!c.isSectionHeader && c.input && c.input.trim()) {
        this.executeCell(c.id);
      }
    }
  }

  clearWorksheet() {
    this.cellsContainer.innerHTML = "";
    this.cells = [];
    this.executionCounter = 0;
    this.plotInstances.clear();
    this.addCell();
    this.drawScopeOverlay();
    this.app.worker.postMessage({ type: "RESET" });
    this.app.updateStatusMessage("Worksheet cleared.");
  }

  setZoom(percent) {
    this.zoom = percent;
    const canvas = document.getElementById(`canvas-${this.docId}`);
    if (canvas) {
      canvas.style.transform = `scale(${percent / 100})`;
      canvas.style.transformOrigin = "top center";
    }
    this.app.updateZoomLabel(`${percent}%`);
  }

  setEditable(editable) {
    this.isEditable = editable;
    this.cells.forEach(c => {
      if (c.domElement) {
        const ed = c.domElement.querySelector(".cell-input-edit, .section-title-edit");
        if (ed) ed.contentEditable = editable;
      }
    });
  }

  updateSectionFolding() {
    let currentFoldLevel = -1;
    let isFolding = false;

    for (const cell of this.cells) {
      if (cell.isSectionHeader) {
        if (isFolding && cell.sectionLevel <= currentFoldLevel) {
          isFolding = false;
        }
        if (cell.isCollapsed) {
          isFolding = true;
          currentFoldLevel = cell.sectionLevel;
        }
        if (cell.domElement) cell.domElement.style.display = "flex";
      } else {
        if (cell.domElement) {
          cell.domElement.style.display = isFolding ? "none" : "flex";
        }
      }
    }
  }

  drawScopeOverlay() {
    if (!this.scopeCanvas) return;
    const ctx = this.scopeCanvas.getContext("2d");
    const rect = this.cellsContainer.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;

    this.scopeCanvas.width = rect.width * dpr;
    this.scopeCanvas.height = rect.height * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, rect.width, rect.height);

    const isLight = this.app.theme === "light";
    ctx.strokeStyle = isLight ? "#8e9aaf" : "#64748b";
    ctx.lineWidth = 1;

    // Draw hierarchical vertical lines from disclosure buttons
    for (let i = 0; i < this.cells.length; i++) {
      const cell = this.cells[i];
      if (!cell.isSectionHeader || cell.isCollapsed || !cell.domElement || cell.domElement.style.display === "none") {
        continue;
      }

      const btn = cell.domElement.querySelector(".section-toggle-btn");
      if (!btn) continue;

      const btnRect = btn.getBoundingClientRect();
      const startX = btnRect.left - rect.left + btnRect.width / 2;
      const startY = btnRect.bottom - rect.top;

      let lastY = startY;
      for (let j = i + 1; j < this.cells.length; j++) {
        const child = this.cells[j];
        if (!child.domElement || child.domElement.style.display === "none") continue;
        if (child.isSectionHeader && child.sectionLevel <= cell.sectionLevel) break;

        const childRect = child.domElement.getBoundingClientRect();
        lastY = childRect.bottom - rect.top - 4;
      }

      if (lastY > startY + 10) {
        ctx.beginPath();
        ctx.moveTo(startX, startY);
        ctx.lineTo(startX, lastY);
        ctx.lineTo(startX + 8, lastY); // Horizontal tick └───
        ctx.stroke();
      }
    }
  }

  insertSection(level = 0) {
    const activeId = this.activeCellId;
    this.addCell({
      mode: "section",
      isSectionHeader: true,
      sectionLevel: level,
      sectionTitle: level === 0 ? "Problem / Section" : "Subproblem",
      insertAfterId: activeId
    });
  }

  indentActiveCell() {
    const cell = this.cells.find(c => c.id === this.activeCellId);
    if (!cell) return;
    if (cell.isSectionHeader) {
      cell.sectionLevel = Math.min(3, cell.sectionLevel + 1);
      if (cell.domElement) {
        cell.domElement.className = `worksheet-cell section-header-cell level-${cell.sectionLevel}`;
      }
      this.drawScopeOverlay();
    }
  }

  outdentActiveCell() {
    const cell = this.cells.find(c => c.id === this.activeCellId);
    if (!cell) return;
    if (cell.isSectionHeader) {
      cell.sectionLevel = Math.max(0, cell.sectionLevel - 1);
      if (cell.domElement) {
        cell.domElement.className = `worksheet-cell section-header-cell level-${cell.sectionLevel}`;
      }
      this.drawScopeOverlay();
    }
  }

  loadImportedCells(cellList) {
    this.cellsContainer.innerHTML = "";
    this.cells = [];
    this.executionCounter = 0;
    this.plotInstances.clear();

    for (const c of cellList) {
      this.addCell({
        mode: c.is_section_header ? "section" : (c.input_mode === 2 ? "text" : (c.input_mode === 1 ? "1d_math" : "2d_math")),
        isSectionHeader: bool(c.is_section_header),
        sectionLevel: c.section_level || 0,
        sectionTitle: c.section_title || "",
        input: c.input || "",
        result: c.result || null
      });
    }

    this.drawScopeOverlay();
  }

  getSerializableCells() {
    return this.cells.map((c, idx) => ({
      cell_id: c.id,
      execution_idx: idx + 1,
      input: c.input,
      input_mode: c.mode === "text" ? 2 : (c.mode === "1d_math" ? 1 : 0),
      is_section_header: c.isSectionHeader,
      section_title: c.sectionTitle,
      section_level: c.sectionLevel,
      result: c.result
    }));
  }
}

function bool(v) {
  return v === true || v === "true" || v === 1;
}
