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
    this._isUndoRedo = false;
    this._typingUndoCaptured = false;
    this._typingDebounce = null;

    this.renderSkeleton();
    this.addCell({ _skipUndo: true }); // Default first empty cell
  }

  pushUndoState() {
    if (this._isUndoRedo || this._isLoading) return;
    const snapshot = {
      cells: JSON.parse(JSON.stringify(this.getSerializableCells())),
      activeCellId: this.activeCellId,
      activeCellIndex: this.cells.findIndex(c => c.id === this.activeCellId)
    };
    this.undoStack.push(snapshot);
    if (this.undoStack.length > 60) {
      this.undoStack.shift();
    }
    this.redoStack = [];
  }

  undo() {
    if (this.undoStack.length === 0) {
      document.execCommand("undo");
      return;
    }
    const currentSnapshot = {
      cells: JSON.parse(JSON.stringify(this.getSerializableCells())),
      activeCellId: this.activeCellId,
      activeCellIndex: this.cells.findIndex(c => c.id === this.activeCellId)
    };
    this.redoStack.push(currentSnapshot);
    const prevState = this.undoStack.pop();
    this._isUndoRedo = true;
    try {
      this.restoreFromSnapshot(prevState);
    } finally {
      this._isUndoRedo = false;
    }
    this.app.updateStatusMessage("Undo");
  }

  redo() {
    if (this.redoStack.length === 0) {
      document.execCommand("redo");
      return;
    }
    const currentSnapshot = {
      cells: JSON.parse(JSON.stringify(this.getSerializableCells())),
      activeCellId: this.activeCellId,
      activeCellIndex: this.cells.findIndex(c => c.id === this.activeCellId)
    };
    this.undoStack.push(currentSnapshot);
    const nextState = this.redoStack.pop();
    this._isUndoRedo = true;
    try {
      this.restoreFromSnapshot(nextState);
    } finally {
      this._isUndoRedo = false;
    }
    this.app.updateStatusMessage("Redo");
  }

  restoreFromSnapshot(snapshot) {
    if (!snapshot || !snapshot.cells) return;
    this.cellsContainer.innerHTML = "";
    this.cells = [];
    this.executionCounter = 0;
    this.plotInstances.clear();

    const cellsData = snapshot.cells;
    for (const c of cellsData) {
      const isSec = !!c.is_section_header;
      const mode = isSec ? "section" : (c.input_mode === 2 ? "text" : (c.input_mode === 1 ? "1d_math" : (c.input_mode === 3 ? "nonexec_math" : "2d_math")));
      this.addCell({
        id: c.cell_id,
        mode,
        isSectionHeader: isSec,
        sectionLevel: c.section_level || 0,
        sectionTitle: c.section_title || "",
        isCollapsed: !!c.is_collapsed,
        input: c.input || "",
        result: c.result || null,
        embeddedImages: c.embedded_images || null,
        _skipUndo: true
      });
    }

    if (this.cells.length === 0) {
      this.addCell({ _skipUndo: true });
    }

    this.initSectionFolding();
    this.drawScopeOverlay(true);

    let targetId = snapshot.activeCellId;
    if (!targetId && snapshot.activeCellIndex >= 0 && this.cells[snapshot.activeCellIndex]) {
      targetId = this.cells[snapshot.activeCellIndex].id;
    }
    if (targetId && this.cells.some(c => c.id === targetId)) {
      this.focusCell(targetId);
    } else if (this.cells.length > 0) {
      this.focusCell(this.cells[0].id);
    }
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

    const scrollContainer = this.container.querySelector(".worksheet-scroll-container");
    if (scrollContainer) {
      scrollContainer.addEventListener("scroll", () => this.drawScopeOverlay(), { passive: true });
    }

    window.addEventListener("resize", () => this.drawScopeOverlay());

    if (typeof ResizeObserver !== "undefined" && this.cellsContainer) {
      this._resizeObserver = new ResizeObserver(() => {
        this.drawScopeOverlay();
      });
      this._resizeObserver.observe(this.cellsContainer);
    }

    document.addEventListener("click", (e) => {
      if (!e.target.closest(".image-resize-wrapper")) {
        document.querySelectorAll(".image-resize-wrapper.image-selected").forEach(w => {
          w.classList.remove("image-selected");
        });
      }
    });
  }

  addCell(options = {}, insertIntoDom = true) {
    if (!this._isUndoRedo && !this._isLoading && this.cells.length > 0 && !options._skipUndo) {
      this.pushUndoState();
    }
    const id = options.id || ("cell_" + Math.random().toString(36).substring(2, 9));
    const mode = options.mode || "2d_math"; // "2d_math", "1d_math", "text", "section"
    const isSection = options.isSectionHeader || mode === "section";
    const insertAfterId = options.insertAfterId;

    let sectionLevel = options.sectionLevel !== undefined ? options.sectionLevel : 0;
    if (options.sectionLevel === undefined) {
      const prevCell = insertAfterId ? this.cells.find(c => c.id === insertAfterId) : (this.cells.length > 0 ? this.cells[this.cells.length - 1] : null);
      if (prevCell) {
        sectionLevel = prevCell.sectionLevel || 0;
      }
    }
    const title = cleanOctalEscapes(options.sectionTitle || "");
    const input = options.input || "";

    const cellObj = {
      id,
      mode,
      isSectionHeader: isSection,
      sectionLevel,
      sectionTitle: title,
      sectionHtml: options.sectionHtml || null,
      isCollapsed: bool(options.isCollapsed),
      input,
      isTable: !!options.isTable,
      result: options.result || null,
      error: options.error || null,
      suggestion: options.suggestion || null,
      equationIndex: options.equationIndex || null,
      embeddedImages: options.embeddedImages || null,
      domElement: null,
      _deferredOutput: !!options.deferredOutput
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

    this.renderCellDom(cellObj, insertIntoDom, options.initialHidden);
    if (insertIntoDom) {
      this.focusCell(id);
      this.drawScopeOverlay();
    }
    return cellObj;
  }

  addCellWithInput(expr, autoExecute = false) {
    const cell = this.addCell({ input: expr });
    if (autoExecute) {
      setTimeout(() => this.executeCell(cell.id), 50);
    }
  }

  renderCellDom(cell, insertIntoDom = true, initialHidden = false) {
    const cellDiv = document.createElement("div");
    const secLvl = Math.max(0, cell.sectionLevel || 0);
    const isTable = cell.isTable || cell.mode === "table";
    cellDiv.className = `worksheet-cell ${cell.isSectionHeader ? 'section-header-cell level-' + secLvl : ''} ${isTable ? 'table-cell' : ''}`;
    cellDiv.id = cell.id;
    if (initialHidden) {
      cellDiv.style.display = "none";
    }

    // Apply 26px indentation per section level matching desktop OpenMath
    const step = 26;
    const indent = secLvl * step;
    if (indent > 0) {
      cellDiv.style.marginLeft = `${indent}px`;
    }

    if (cell.isSectionHeader) {
      const cleanTitle = cleanOctalEscapes(cell.sectionTitle || cell.input || "");
      const titleContent = cell.sectionHtml ? cleanOctalEscapes(cell.sectionHtml) : cleanTitle;
      cellDiv.innerHTML = `
        <div class="section-row">
          <button class="section-toggle-btn" title="Toggle Section Collapse">${cell.isCollapsed ? '▶' : '▼'}</button>
          <div class="section-title-edit" contenteditable="${this.isEditable}" placeholder="Section Title...">${titleContent}</div>
        </div>
      `;

      const toggleBtn = cellDiv.querySelector(".section-toggle-btn");
      toggleBtn.onclick = (e) => {
        e.stopPropagation();
        this.onSectionToggled(cell.id);
      };

      const titleEdit = cellDiv.querySelector(".section-title-edit");
      titleEdit.oninput = () => {
        if (!this._typingUndoCaptured) {
          this.pushUndoState();
          this._typingUndoCaptured = true;
        }
        clearTimeout(this._typingDebounce);
        this._typingDebounce = setTimeout(() => {
          this._typingUndoCaptured = false;
        }, 700);

        cell.sectionTitle = titleEdit.innerText;
        cell.input = titleEdit.innerText;
        this.app.contextPanel.setTargetExpression(cell.sectionTitle);
      };
      titleEdit.onblur = () => {
        this._typingUndoCaptured = false;
      };
      titleEdit.onkeydown = (e) => {
        if (e.key === "Tab") {
          e.preventDefault();
          if (e.shiftKey) {
            this.outdentActiveCell();
          } else {
            this.indentActiveCell();
          }
        } else if (e.key === "Enter" && !e.shiftKey) {
          e.preventDefault();
          this.addCell({ insertAfterId: cell.id });
        }
      };
      titleEdit.onfocus = () => this.setActiveCell(cell.id);
    } else {
      // Regular execution group cell, table, or embedded image
      const hasImages = cell.embeddedImages && Object.keys(cell.embeddedImages).length > 0;
      const isText = cell.mode === "text" || isTable || hasImages;
      cellDiv.innerHTML = `
        <div class="cell-bracket-bar" style="display:none;"></div>
        <div class="cell-input-row">
          <span class="cell-prompt" style="display:none;"></span>
          <div class="cell-input-edit mode-${cell.mode === '1d_math' ? '1d' : (isText ? 'text' : '2d')}"
               contenteditable="${this.isEditable}"
               spellcheck="false"></div>
        </div>
        <div class="cell-output-container"></div>
      `;

      const inputEdit = cellDiv.querySelector(".cell-input-edit");

      if (isText) {
        let textContent = cleanOctalEscapes(cell.input || "");
        if (cell.embeddedImages && (textContent.includes('src="img_') || textContent.includes("src='img_"))) {
          for (const [imgId, b64] of Object.entries(cell.embeddedImages)) {
            if (!textContent.includes(imgId)) continue;
            const srcData = b64.startsWith("data:") ? b64 : `data:image/png;base64,${b64}`;
            textContent = textContent.split(`src="${imgId}"`).join(`src="${srcData}"`);
            textContent = textContent.split(`src='${imgId}'`).join(`src="${srcData}"`);
          }
        }
        if (/<(p|div|img|span|b|i|u|br|table|h[1-6])[\s>]/i.test(textContent)) {
          inputEdit.innerHTML = textContent;
        } else {
          inputEdit.innerText = textContent;
        }
      } else {
        inputEdit.innerText = cell.input || "";
      }

      inputEdit.onfocus = () => this.setActiveCell(cell.id);
      inputEdit.onblur = () => {
        this._typingUndoCaptured = false;
      };

      inputEdit.oninput = () => {
        if (!this._typingUndoCaptured) {
          this.pushUndoState();
          this._typingUndoCaptured = true;
        }
        clearTimeout(this._typingDebounce);
        this._typingDebounce = setTimeout(() => {
          this._typingUndoCaptured = false;
        }, 700);

        const isCurrentText = cell.mode === "text" || cell.isTable || (cell.embeddedImages && Object.keys(cell.embeddedImages).length > 0);
        cell.input = isCurrentText ? inputEdit.innerHTML : inputEdit.innerText;
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
        const isCurrentText = cell.mode === "text" || cell.isTable || cell.mode === "nonexec_math";
        if (e.key === "Tab" && !e.target.closest("td")) {
          e.preventDefault();
          if (e.shiftKey) {
            this.outdentActiveCell();
          } else {
            this.indentActiveCell();
          }
        } else if (e.key === "Enter" && !e.shiftKey) {
          if (isCurrentText) {
            // Text and non-executable math cells should NOT execute as math
            return;
          }
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
    this.setupCellInteractiveElements(cellDiv, cell);

    // Insert into DOM in order if requested
    if (insertIntoDom && this.cellsContainer) {
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
    }

    if ((cell.result || cell.error) && !cell._deferredOutput) {
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
    const nextMode = cell.mode === "2d_math" ? "1d_math" : (cell.mode === "1d_math" ? "text" : "2d_math");
    this.setCellMode(cellId, nextMode);
  }

  setCellMode(cellId, mode) {
    const cell = this.cells.find(c => c.id === cellId);
    if (!cell || cell.isSectionHeader) return;
    this.pushUndoState();

    cell.mode = mode;
    const isText = mode === "text";
    const editEl = cell.domElement?.querySelector(".cell-input-edit");
    const bracketBar = cell.domElement?.querySelector(".cell-bracket-bar");
    const promptEl = cell.domElement?.querySelector(".cell-prompt");

    if (editEl) {
      editEl.className = `cell-input-edit mode-${mode === '1d_math' ? '1d' : (isText ? 'text' : '2d')}`;
    }
    if (bracketBar) bracketBar.style.display = "none";
    if (promptEl) promptEl.style.display = "none";

    const outputContainer = cell.domElement?.querySelector(".cell-output-container");
    if (isText && outputContainer) {
      outputContainer.innerHTML = "";
      cell.result = null;
      cell.error = null;
    }

    this.app.updateContextBar(cell.mode);
    this.app.updateStatusMode(cell.mode);
  }

  executeCell(cellId) {
    const cell = this.cells.find(c => c.id === cellId);
    if (!cell || cell.isSectionHeader || cell.mode === "text" || cell.mode === "nonexec_math") return;
    this.pushUndoState();

    const input = (cell.input || "").trim();
    if (!input) {
      // Advance to next cell or create one
      this.advanceToNextCell(cellId);
      return;
    }

    // 1. Try FastCAS first for instant 0.1ms calculation without waiting for worker
    if (this.app.fastCAS) {
      const fastRes = this.app.fastCAS.evaluate(input, this.app.precision || 10);
      if (fastRes && !fastRes.error && (fastRes.result_type !== "Symbolic" || input.startsWith("diff") || input.startsWith("expand") || input.includes(":=") || !this.app.isPyodideReady)) {
        this.handleCellResult({
          id: cell.id,
          docId: this.docId,
          ...fastRes
        });
        // Sync expression to Pyodide in background if Pyodide is ready
        if (this.app.isPyodideReady && this.app.worker) {
          this.app.worker.postMessage({
            type: "EVALUATE",
            id: cell.id,
            docId: this.docId,
            expr: input,
            precision: this.app.precision || 10,
            syncOnly: true
          });
        }
        return;
      }
    }

    // 2. Delegate to Worker if needed
    const outContainer = cell.domElement && cell.domElement.querySelector(".cell-output-container");
    if (outContainer) {
      outContainer.innerHTML = `
        <div style="display:flex; justify-content:center; align-items:center; padding: 6px 0; color: var(--text-muted); font-size: 11px;">
          <span class="cas-init-spinner" style="width:11px; height:11px; border-width:2px; margin-right:6px;"></span>
          <span>${this.app.isPyodideReady ? "Evaluating..." : "Evaluating with CAS engine..."}</span>
        </div>
      `;
    }

    if (this.app.worker) {
      this.app.worker.postMessage({
        type: "EVALUATE",
        id: cell.id,
        docId: this.docId,
        expr: input,
        precision: this.app.precision || 10
      });
    }

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
    if (this.app.updateMemoryGauge) {
      this.app.updateMemoryGauge();
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
    this.pushUndoState();

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
    this.pushUndoState();
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

  initSectionFolding() {
    const collapsedDepthStack = [];
    for (const cell of this.cells) {
      const secLevel = Math.max(0, cell.sectionLevel || 0);
      const isSec = !!cell.isSectionHeader;

      if (isSec) {
        while (collapsedDepthStack.length > 0 && collapsedDepthStack[collapsedDepthStack.length - 1] >= secLevel) {
          collapsedDepthStack.pop();
        }
      } else if (cell._isOutsideSection) {
        collapsedDepthStack.length = 0;
      } else {
        while (collapsedDepthStack.length > 0 && collapsedDepthStack[collapsedDepthStack.length - 1] > secLevel) {
          collapsedDepthStack.pop();
        }
      }

      const isHidden = collapsedDepthStack.length > 0;
      if (cell.domElement) {
        cell.domElement.style.display = isHidden ? "none" : "flex";
      }

      if (!isHidden && cell._deferredOutput) {
        cell._deferredOutput = false;
        this.renderCellOutput(cell);
      }

      if (isSec) {
        const toggleBtn = cell.domElement?.querySelector(".section-toggle-btn");
        if (toggleBtn) {
          toggleBtn.textContent = cell.isCollapsed ? '▶' : '▼';
        }
        if (cell.isCollapsed) {
          collapsedDepthStack.push(secLevel);
        }
      }
    }
  }

  updateSectionFolding() {
    this.initSectionFolding();
  }

  onSectionToggled(sectionCellId) {
    const secCell = this.cells.find(c => c.id === sectionCellId);
    if (!secCell) return;
    this.pushUndoState();

    secCell.isCollapsed = !secCell.isCollapsed;
    this.initSectionFolding();
    this.drawScopeOverlay();
  }

  drawScopeOverlay(immediate = false) {
    if (immediate) {
      this._performDrawScopeOverlay();
      return;
    }
    if (this._scopeOverlayScheduled) return;
    this._scopeOverlayScheduled = true;
    requestAnimationFrame(() => {
      this._scopeOverlayScheduled = false;
      this._performDrawScopeOverlay();
    });
  }

  _performDrawScopeOverlay() {
    if (!this.scopeCanvas || !this.cellsContainer) return;
    const canvasRect = this.scopeCanvas.getBoundingClientRect();
    if (canvasRect.width === 0 || canvasRect.height === 0) return;

    const dpr = window.devicePixelRatio || 1;
    const targetW = Math.round(canvasRect.width * dpr);
    const targetH = Math.round(canvasRect.height * dpr);

    if (this.scopeCanvas.width !== targetW || this.scopeCanvas.height !== targetH) {
      this.scopeCanvas.width = targetW;
      this.scopeCanvas.height = targetH;
    }
    const ctx = this.scopeCanvas.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, canvasRect.width, canvasRect.height);

    const isLight = this.app.theme !== "dark";
    ctx.strokeStyle = isLight ? "#475569" : "#94a3b8";
    ctx.lineWidth = 1.5;
    ctx.lineCap = "square";

    for (let i = 0; i < this.cells.length; i++) {
      const cell = this.cells[i];
      if (!cell.isSectionHeader || cell.isCollapsed || !cell.domElement || cell.domElement.style.display === "none") {
        continue;
      }
      const btn = cell.domElement.querySelector(".section-toggle-btn");
      if (!btn) continue;

      const btnRect = btn.getBoundingClientRect();
      const startX = Math.floor(btnRect.left - canvasRect.left + btnRect.width / 2) + 0.5;
      const startY = Math.floor(btnRect.bottom - canvasRect.top - 2);
      const secLevel = cell.sectionLevel || 0;

      let lastCell = null;
      for (let j = i + 1; j < this.cells.length; j++) {
        const child = this.cells[j];
        if (!child.domElement || child.domElement.style.display === "none" || child.domElement.offsetHeight === 0) continue;

        const childLevel = child.sectionLevel || 0;
        if (child.isSectionHeader) {
          if (childLevel <= secLevel) break;
        } else {
          if (child._isOutsideSection || childLevel < secLevel) break;
        }
        lastCell = child;
      }

      if (lastCell && lastCell.domElement) {
        const lastRect = lastCell.domElement.getBoundingClientRect();
        const endY = Math.floor(lastRect.bottom - canvasRect.top - 4) + 0.5;
        if (endY > startY + 4) {
          ctx.beginPath();
          ctx.moveTo(startX, startY);
          ctx.lineTo(startX, endY);
          ctx.lineTo(startX + 10, endY);
          ctx.stroke();
        }
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

  insertTable(rows = 2, cols = 3) {
    const r = Math.max(1, Math.min(50, rows));
    const c = Math.max(1, Math.min(20, cols));

    const htmlRows = [];
    for (let i = 0; i < r; i++) {
      const htmlCols = [];
      for (let j = 0; j < c; j++) {
        htmlCols.push(`<td style="border: 1px solid var(--border); padding: 8px 12px; vertical-align: middle; background-color: var(--bg-cell); min-width: 60px;"><br/></td>`);
      }
      htmlRows.push(`<tr>${htmlCols.join("")}</tr>`);
    }

    const tableHtml = `<div class="table-interactive-wrapper"><table style="border-collapse: collapse; width: 100%; border: 1px solid var(--border); font-family: 'Times New Roman', serif; font-size: 12pt; line-height: 1.3;"><tbody>${htmlRows.join("")}</tbody></table></div>`;

    const activeCell = this.cells.find(cell => cell.id === this.activeCellId);
    if (activeCell && activeCell.domElement) {
      const editEl = activeCell.domElement.querySelector(".cell-input-edit");
      if (editEl && activeCell.mode === "text") {
        editEl.focus();
        document.execCommand("insertHTML", false, tableHtml);
        activeCell.input = editEl.innerHTML;
        this.initInteractiveResizers();
        this.drawScopeOverlay();
        return;
      }
    }

    const newCell = this.addCell({
      mode: "text",
      isTable: true,
      input: tableHtml,
      insertAfterId: this.activeCellId
    });
    this.initInteractiveResizers();
    this.drawScopeOverlay();
    return newCell;
  }

  indentActiveCell() {
    const cell = this.cells.find(c => c.id === this.activeCellId);
    if (!cell) return;
    this.pushUndoState();
    cell.sectionLevel = Math.min(3, (cell.sectionLevel || 0) + 1);
    if (cell.domElement) {
      if (cell.isSectionHeader) {
        cell.domElement.className = `worksheet-cell section-header-cell level-${cell.sectionLevel}`;
      }
      cell.domElement.style.marginLeft = `${cell.sectionLevel * 26}px`;
    }
    this.drawScopeOverlay();
  }

  outdentActiveCell() {
    const cell = this.cells.find(c => c.id === this.activeCellId);
    if (!cell) return;
    this.pushUndoState();
    cell.sectionLevel = Math.max(0, (cell.sectionLevel || 0) - 1);
    if (cell.domElement) {
      if (cell.isSectionHeader) {
        cell.domElement.className = `worksheet-cell section-header-cell level-${cell.sectionLevel}`;
      }
      cell.domElement.style.marginLeft = cell.sectionLevel > 0 ? `${cell.sectionLevel * 26}px` : "";
    }
    this.drawScopeOverlay();
  }

  loadImportedCells(cellList, progressCallback = null) {
    this.cellsContainer.innerHTML = "";
    this.cells = [];
    this.executionCounter = 0;
    this.plotInstances.clear();

    const loadToken = ++this._currentLoadToken || (this._currentLoadToken = 1);
    const totalCells = cellList.length;
    if (progressCallback) {
      progressCallback(0, totalCells, `Loading 0 of ${totalCells} elements...`);
    }

    // Fast visibility pre-pass (~0.5ms for 2000 cells)
    // Determines upfront which cells will start inside collapsed sections so we can
    // defer expensive DOM work and KaTeX rendering until sections are opened.
    const collapsedDepthStack = [];
    const isHiddenList = new Uint8Array(totalCells);
    for (let i = 0; i < totalCells; i++) {
      const c = cellList[i];
      const isSec = bool(c.is_section_header);
      const secLevel = Math.max(0, c.section_level || 0);

      if (isSec) {
        while (collapsedDepthStack.length > 0 && collapsedDepthStack[collapsedDepthStack.length - 1] >= secLevel) {
          collapsedDepthStack.pop();
        }
      } else if (c._isOutsideSection) {
        collapsedDepthStack.length = 0;
      } else {
        while (collapsedDepthStack.length > 0 && collapsedDepthStack[collapsedDepthStack.length - 1] > secLevel) {
          collapsedDepthStack.pop();
        }
      }

      if (collapsedDepthStack.length > 0) {
        isHiddenList[i] = 1;
      }

      if (isSec && bool(c.is_collapsed)) {
        collapsedDepthStack.push(secLevel);
      }
    }

    const batchSize = 400;
    let idx = 0;

    const processNextBatch = () => {
      if (this._currentLoadToken !== loadToken) return;

      const end = Math.min(idx + batchSize, totalCells);
      const batchFragment = document.createDocumentFragment();
      for (; idx < end; idx++) {
        const c = cellList[idx];
        const isSec = bool(c.is_section_header);
        const mode = isSec ? "section" : (c.input_mode === 2 ? "text" : (c.input_mode === 1 ? "1d_math" : (c.input_mode === 3 ? "nonexec_math" : "2d_math")));
        const isCollapsed = bool(c.is_collapsed);
        const hasResult = c.result && (c.result.exact_latex || c.result.numeric_latex || c.result.exact_text || c.result.numeric_text || c.result.is_plot || c.result.error);
        const eqIdx = hasResult ? ++this.executionCounter : null;
        const isHidden = isHiddenList[idx] === 1;

        const cellObj = this.addCell({
          mode,
          isSectionHeader: isSec,
          sectionLevel: c.section_level || 0,
          sectionTitle: cleanOctalEscapes(c.section_title || (isSec ? c.input : "")),
          sectionHtml: c.section_html || null,
          isCollapsed,
          input: cleanOctalEscapes(c.input || ""),
          isTable: !!c.is_table,
          result: c.result || null,
          error: c.result?.error || null,
          equationIndex: eqIdx,
          embeddedImages: c.embedded_images || c.embeddedImages || null,
          deferredOutput: isHidden,
          initialHidden: isHidden
        }, false);

        if (eqIdx && cellObj && cellObj.domElement) {
          cellObj.equationIndex = eqIdx;
          const eqLabel = cellObj.domElement.querySelector(".cell-equation-label");
          if (eqLabel) eqLabel.textContent = `(${eqIdx})`;
        }

        if (cellObj && cellObj.domElement) {
          batchFragment.appendChild(cellObj.domElement);
        }
      }

      this.cellsContainer.appendChild(batchFragment);

      if (progressCallback) {
        progressCallback(idx, totalCells, `Loading element ${idx} of ${totalCells}...`);
      }

      if (idx < totalCells) {
        requestAnimationFrame(processNextBatch);
      } else {
        // Complete all batches
        if (this.cells.length === 0) {
          this.addCell();
        } else {
          this.setActiveCell(this.cells[0].id);
        }

        // Initialize section folding from imported state
        this.initSectionFolding();

        requestAnimationFrame(() => {
          this.drawScopeOverlay();
          if (this.app.hideLoadingOverlay) {
            this.app.hideLoadingOverlay();
          }
        });
      }
    };

    processNextBatch();
  }

  initInteractiveResizers() {
    if (!this.cellsContainer) return;
    for (const cell of this.cells) {
      if (cell.domElement) {
        this._attachCellInteractions(cell.domElement, cell);
      }
    }
  }

  setupCellInteractiveElements(cellDiv, cell) {
    if (!cellDiv || cellDiv._hasResizerSetup) return;
    cellDiv._hasResizerSetup = true;

    // Lazily attach interactive elements on hover or focus to keep initial document load blazing fast
    const onInteract = () => {
      cellDiv.removeEventListener("mouseenter", onInteract);
      cellDiv.removeEventListener("focusin", onInteract);
      this._attachCellInteractions(cellDiv, cell);
    };

    cellDiv.addEventListener("mouseenter", onInteract, { passive: true, once: true });
    cellDiv.addEventListener("focusin", onInteract, { passive: true, once: true });
  }

  _attachCellInteractions(cellDiv, cell) {
    if (!cellDiv) return;
    const imgs = cellDiv.querySelectorAll("img");
    imgs.forEach(img => {
      this.attachImageInteractions(img, cell);
    });

    const tbls = cellDiv.querySelectorAll("table");
    tbls.forEach(tbl => {
      this.attachTableInteractions(tbl, cell);
    });
  }

  attachImageInteractions(img, cell) {
    if (img.dataset.hasInteractiveResize) return;
    img.dataset.hasInteractiveResize = "true";

    let wrapper = img.parentElement;
    if (!wrapper || !wrapper.classList.contains("image-resize-wrapper")) {
      wrapper = document.createElement("div");
      wrapper.className = "image-resize-wrapper";
      wrapper.contentEditable = "false";
      img.parentNode.insertBefore(wrapper, img);
      wrapper.appendChild(img);

      const corners = ["tl", "tr", "bl", "br"];
      corners.forEach(c => {
        const handle = document.createElement("div");
        handle.className = `image-resize-handle handle-${c}`;
        handle.dataset.corner = c;
        wrapper.appendChild(handle);
      });
    }

    img.draggable = true;
    img.style.cursor = "pointer";

    wrapper.onclick = (e) => {
      e.stopPropagation();
      document.querySelectorAll(".image-resize-wrapper.image-selected").forEach(w => {
        if (w !== wrapper) w.classList.remove("image-selected");
      });
      wrapper.classList.add("image-selected");
    };

    wrapper.querySelectorAll(".image-resize-handle").forEach(handle => {
      handle.onmousedown = (e) => {
        e.preventDefault();
        e.stopPropagation();

        const corner = handle.dataset.corner;
        const startX = e.clientX;
        const rect = img.getBoundingClientRect();
        const startW = rect.width;
        const startH = rect.height;
        const ratio = startH > 0 ? (startW / startH) : 1.33;

        const onMouseMove = (ev) => {
          const dx = ev.clientX - startX;
          let newW = startW;
          if (corner === "br" || corner === "tr") {
            newW = Math.max(50, Math.round(startW + dx));
          } else {
            newW = Math.max(50, Math.round(startW - dx));
          }
          const newH = Math.round(newW / ratio);
          img.style.width = `${newW}px`;
          img.style.height = `${newH}px`;
          img.width = newW;
          img.height = newH;
        };

        const onMouseUp = () => {
          document.removeEventListener("mousemove", onMouseMove);
          document.removeEventListener("mouseup", onMouseUp);
          const editEl = cell.domElement?.querySelector(".cell-input-edit");
          if (editEl) {
            cell.input = editEl.innerHTML;
          }
          this.drawScopeOverlay();
        };

        document.addEventListener("mousemove", onMouseMove);
        document.addEventListener("mouseup", onMouseUp);
      };
    });
  }

  attachTableInteractions(tbl, cell) {
    if (tbl.dataset.hasInteractiveResize) return;
    tbl.dataset.hasInteractiveResize = "true";

    let wrapper = tbl.parentElement;
    if (!wrapper || !wrapper.classList.contains("table-interactive-wrapper")) {
      wrapper = document.createElement("div");
      wrapper.className = "table-interactive-wrapper";
      wrapper.contentEditable = "false";
      tbl.parentNode.insertBefore(wrapper, tbl);
      wrapper.appendChild(tbl);

      // Move handle at top-left
      const moveHandle = document.createElement("div");
      moveHandle.className = "table-move-handle";
      moveHandle.title = "Drag table to move";
      moveHandle.draggable = true;
      moveHandle.innerHTML = '<span class="grip-dot"></span><span class="grip-dot"></span><span class="grip-dot"></span>';
      wrapper.appendChild(moveHandle);

      // Corner resize handle at bottom-right
      const cornerHandle = document.createElement("div");
      cornerHandle.className = "table-corner-handle";
      cornerHandle.title = "Drag to resize table";
      wrapper.appendChild(cornerHandle);

      cornerHandle.onmousedown = (e) => {
        e.preventDefault();
        e.stopPropagation();

        const startX = e.clientX;
        const startY = e.clientY;
        const rect = tbl.getBoundingClientRect();
        const startW = rect.width;
        const startH = rect.height;

        const onMouseMove = (ev) => {
          const dx = ev.clientX - startX;
          const dy = ev.clientY - startY;
          const newW = Math.max(100, Math.round(startW + dx));
          const newH = Math.max(40, Math.round(startH + dy));
          tbl.style.width = `${newW}px`;
          tbl.style.height = `${newH}px`;
        };

        const onMouseUp = () => {
          document.removeEventListener("mousemove", onMouseMove);
          document.removeEventListener("mouseup", onMouseUp);
          const editEl = cell.domElement?.querySelector(".cell-input-edit");
          if (editEl) {
            cell.input = editEl.innerHTML;
          }
          this.drawScopeOverlay();
        };

        document.addEventListener("mousemove", onMouseMove);
        document.addEventListener("mouseup", onMouseUp);
      };
    }

    // Column resizing inside table
    const cells = tbl.querySelectorAll("th, td");
    cells.forEach(td => {
      td.addEventListener("mousemove", (e) => {
        const rect = td.getBoundingClientRect();
        const isRightEdge = (rect.right - e.clientX) <= 6;
        td.style.cursor = isRightEdge ? "col-resize" : "";
      });

      td.addEventListener("mousedown", (e) => {
        const rect = td.getBoundingClientRect();
        const isRightEdge = (rect.right - e.clientX) <= 6;
        if (!isRightEdge) return;

        e.preventDefault();
        e.stopPropagation();

        const startX = e.clientX;
        const startW = rect.width;
        const colIdx = td.cellIndex;

        const guideline = document.createElement("div");
        guideline.className = "col-resize-guideline";
        const wrapperRect = wrapper.getBoundingClientRect();
        guideline.style.left = `${rect.right - wrapperRect.left}px`;
        guideline.style.height = `${wrapperRect.height}px`;
        wrapper.appendChild(guideline);

        let finalW = startW;
        const onMouseMove = (ev) => {
          const dx = ev.clientX - startX;
          finalW = Math.max(30, Math.round(startW + dx));
          guideline.style.left = `${rect.right - wrapperRect.left + dx}px`;
        };

        const onMouseUp = () => {
          document.removeEventListener("mousemove", onMouseMove);
          document.removeEventListener("mouseup", onMouseUp);
          if (guideline.parentNode) guideline.remove();

          const allRows = tbl.rows;
          for (let r = 0; r < allRows.length; r++) {
            const rowCell = allRows[r].cells[colIdx];
            if (rowCell) {
              rowCell.style.width = `${finalW}px`;
            }
          }

          const editEl = cell.domElement?.querySelector(".cell-input-edit");
          if (editEl) {
            cell.input = editEl.innerHTML;
          }
          this.drawScopeOverlay();
        };

        document.addEventListener("mousemove", onMouseMove);
        document.addEventListener("mouseup", onMouseUp);
      });
    });
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
      is_collapsed: c.isCollapsed,
      result: c.result,
      embedded_images: c.embeddedImages || {}
    }));
  }
}

function bool(v) {
  return v === true || v === "true" || v === 1;
}

export function cleanOctalEscapes(s) {
  if (!s || typeof s !== "string" || !s.includes("\\")) return s || "";
  return s.replace(/(?:\\[0-7]{3})+/g, (match) => {
    try {
      const octals = match.match(/\\([0-7]{3})/g);
      if (!octals) return match;
      const bytes = new Uint8Array(octals.map(o => parseInt(o.substring(1), 8)));
      if (typeof TextDecoder !== "undefined") {
        return new TextDecoder("utf-8").decode(bytes);
      }
      let binary = "";
      for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i]);
      return decodeURIComponent(escape(binary));
    } catch (e) {
      return match;
    }
  });
}
