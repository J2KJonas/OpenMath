/**
 * OpenMath Web Application Coordinator
 * Exact 1:1 replica of ui/main_window.py Desktop CAS experience:
 * Menus, Toolbars, Document Tabs, Palette Dock, Context Panel, Status Bar, and Pyodide Web Worker.
 */

import { StartPageView } from "./start-page.js";
import { WorksheetView } from "./worksheet.js";
import { PaletteManager } from "./palette.js";
import { ContextPanelManager } from "./context-panel.js";
import { DialogManager } from "./dialogs.js";

class OpenMathApplication {
  constructor() {
    this.worker = null;
    this.theme = localStorage.getItem("openmath_theme") || "light";
    this.decimalSeparator = localStorage.getItem("openmath_decimal_sep") || ",";
    this.precision = parseInt(localStorage.getItem("openmath_precision") || "10", 10);
    this.currentFontFamily = "Times New Roman";
    this.currentFontSize = "12";

    this.documents = []; // Array of { id, title, type: 'start' | 'worksheet', instance, tabElement, pageElement }
    this.activeDocId = null;
    this.docCounter = 0;

    this.palette = null;
    this.contextPanel = null;
    this.dialogManager = null;
    this.helpCatalog = [];
  }

  init() {
    this.applyTheme(this.theme);
    this.initWorker();
    this.initLayoutComponents();
    this.initMenubar();
    this.initMainToolbar();
    this.initContextBar();
    this.initStatusBar();
    this.initGlobalShortcuts();
    window.addEventListener("resize", () => this.updateTabOverflow());

    // Start with Start.mw (default start page matching ui/main_window.py)
    this.createStartPageDocument();
  }

  // 1. Worker Setup
  initWorker() {
    const loadingOverlay = document.getElementById("loading-overlay");
    const loadingStatus = document.getElementById("loading-status");

    try {
      this.worker = new Worker("./js/cas-worker.js");

      this.worker.onmessage = (e) => {
        const data = e.data;
        if (!data) return;

        switch (data.type) {
          case "STATUS":
            if (loadingStatus) loadingStatus.textContent = data.message;
            this.updateStatusMessage(data.message);
            break;

          case "READY":
            if (loadingOverlay) {
              loadingOverlay.style.opacity = "0";
              setTimeout(() => { loadingOverlay.style.display = "none"; }, 300);
            }
            this.updateStatusMessage("Ready");
            // Request Help catalog and set decimal separator
            this.worker.postMessage({ type: "GET_HELP_CATALOG" });
            this.worker.postMessage({ type: "SET_DECIMAL_SEPARATOR", sep: this.decimalSeparator });
            break;

          case "RESULT":
            const targetWs = this.getWorksheetById(data.docId);
            if (targetWs) {
              targetWs.handleCellResult(data);
            }
            break;

          case "WHOS_RESULT":
            if (this.palette) {
              this.palette.updateVariablesTable(data.vars);
            }
            break;

          case "HELP_CATALOG":
            this.helpCatalog = data.catalog || [];
            this.updateHelpSearchAutocomplete();
            break;

          case "DOCUMENT_PARSED":
            if (data.error) {
              this.dialogManager.showAlert(`Could not parse document: ${data.error}`, "Import Error");
              this.updateStatusMessage(`Import error: ${data.error}`);
            } else if (data.cells && data.cells.length > 0) {
              const filename = data.filename || "Imported.mw";
              const currentWs = this.getActiveWorksheet();
              let targetWs;
              if (currentWs && currentWs.cells.length === 1 && (!currentWs.cells[0].input || currentWs.cells[0].input.trim() === "") && !currentWs.cells[0].result && !currentWs.filePath) {
                targetWs = currentWs;
                targetWs.title = filename;
                const doc = this.documents.find(d => d.id === targetWs.docId);
                if (doc) doc.title = filename;
                this.renderTabsToolbar();
              } else {
                targetWs = this.createNewWorksheet(filename);
              }
              targetWs.filePath = filename;
              targetWs.loadImportedCells(data.cells);
              this.setWindowTitle(filename);
              this.updateStatusPath(filename);
              this.updateStatusMessage(`Opened ${filename} (${data.cells.length} cells).`);
            } else {
              this.dialogManager.showAlert("The imported document contains no cells.", "Empty Document");
              this.updateStatusMessage("Imported document contains no cells.");
            }
            break;

          case "EXPORT_RESULT":
            this.downloadFile(data.filename || "Worksheet.mw", data.content);
            break;
        }
      };

      this.worker.postMessage({ type: "INIT", basePath: "../" });
    } catch (err) {
      console.error("Worker error:", err);
      if (loadingStatus) loadingStatus.textContent = `Worker Init Error: ${err.message}`;
    }
  }

  // 2. Document Management (Start.mw vs Worksheets)
  createStartPageDocument() {
    const docId = "doc_start";
    const title = "Start.mw";

    const pageContainer = document.createElement("div");
    pageContainer.className = "workspace-document-page active";
    pageContainer.id = `page-${docId}`;
    pageContainer.style.width = "100%";
    pageContainer.style.height = "100%";

    const stackContainer = document.getElementById("document-stack");
    stackContainer.appendChild(pageContainer);

    const startPage = new StartPageView(this, pageContainer);

    const docObj = {
      id: docId,
      title,
      type: "start",
      instance: startPage,
      pageElement: pageContainer,
      tabElement: null
    };

    this.documents.push(docObj);
    this.renderTabsToolbar();
    this.switchToDocument(docId);
  }

  createNewWorksheet(customTitle = null) {
    this.docCounter += 1;
    const docId = `doc_ws_${this.docCounter}`;
    const title = customTitle || `Untitled-${this.docCounter}.mw`;

    const pageContainer = document.createElement("div");
    pageContainer.className = "workspace-document-page";
    pageContainer.id = `page-${docId}`;
    pageContainer.style.width = "100%";
    pageContainer.style.height = "100%";

    const stackContainer = document.getElementById("document-stack");
    stackContainer.appendChild(pageContainer);

    const ws = new WorksheetView(this, pageContainer, docId, title);

    const docObj = {
      id: docId,
      title,
      type: "worksheet",
      instance: ws,
      pageElement: pageContainer,
      tabElement: null
    };

    this.documents.push(docObj);
    this.renderTabsToolbar();
    this.switchToDocument(docId);
    return ws;
  }

  switchToDocument(docId) {
    const doc = this.documents.find(d => d.id === docId);
    if (!doc) return;

    this.activeDocId = docId;

    // Toggle pages
    this.documents.forEach(d => {
      d.pageElement.style.display = d.id === docId ? "block" : "none";
      if (d.tabElement) {
        if (d.id === docId) d.tabElement.classList.add("active");
        else d.tabElement.classList.remove("active");
      }
    });

    // Update window title bar
    this.setWindowTitle(doc.title);

    // Update status bar mode and path
    if (doc.type === "start") {
      this.updateStatusMode("Start Page");
      this.updateStatusPath("");
    } else {
      const ws = doc.instance;
      this.updateStatusMode(ws.cells[0]?.mode || "Math Mode");
      this.updateStatusPath(ws.filePath || "Save Document");
      this.updateZoomLabel(`${ws.zoom}%`);
      ws.drawScopeOverlay();
    }
  }

  closeDocument(docId) {
    const idx = this.documents.findIndex(d => d.id === docId);
    if (idx === -1) return;

    const doc = this.documents[idx];
    if (doc.type === "start" && this.documents.length === 1) {
      // Don't close lone start page
      return;
    }

    if (doc.pageElement && doc.pageElement.parentNode) {
      doc.pageElement.parentNode.removeChild(doc.pageElement);
    }
    this.documents.splice(idx, 1);

    if (this.documents.length === 0) {
      this.createStartPageDocument();
    } else {
      const nextIdx = Math.max(0, idx - 1);
      this.renderTabsToolbar();
      this.switchToDocument(this.documents[nextIdx].id);
    }
  }

  renderTabsToolbar() {
    const tabsContainer = document.getElementById("document-tabs-list");
    if (!tabsContainer) return;

    tabsContainer.innerHTML = "";
    this.documents.forEach(doc => {
      const tabEl = document.createElement("div");
      tabEl.className = `doc-tab ${doc.id === this.activeDocId ? 'active' : ''}`;
      tabEl.innerHTML = `
        <span class="tab-title">${doc.title}</span>
        ${doc.type !== 'start' || this.documents.length > 1 ? '<button class="tab-close-btn" title="Close">✕</button>' : ''}
      `;

      tabEl.onclick = (e) => {
        if (e.target.classList.contains("tab-close-btn")) {
          e.stopPropagation();
          this.closeDocument(doc.id);
          return;
        }
        this.switchToDocument(doc.id);
      };

      doc.tabElement = tabEl;
      tabsContainer.appendChild(tabEl);
    });

    this.updateTabOverflow();
  }

  updateTabOverflow() {
    const tabsContainer = document.getElementById("document-tabs-list");
    const overflowBtn = document.getElementById("btn-tab-overflow");
    if (!tabsContainer || !overflowBtn) return;

    const hasOverflow = tabsContainer.scrollWidth > tabsContainer.clientWidth + 2;
    overflowBtn.style.display = (hasOverflow || this.documents.length > 1) ? "inline-flex" : "none";
  }

  showTabOverflowMenu() {
    let menu = document.getElementById("tab-overflow-menu");
    if (!menu) {
      menu = document.createElement("div");
      menu.id = "tab-overflow-menu";
      menu.className = "dropdown-menu";
      document.body.appendChild(menu);

      document.addEventListener("click", (e) => {
        if (!menu.contains(e.target) && e.target.id !== "btn-tab-overflow") {
          menu.style.display = "none";
        }
      });
    }

    menu.innerHTML = "";
    this.documents.forEach(doc => {
      const item = document.createElement("button");
      item.className = "menu-action";
      const isActive = doc.id === this.activeDocId;
      item.innerHTML = `
        <span style="display: flex; align-items: center; gap: 8px; width: 100%;">
          <span style="width: 14px; text-align: center; font-weight: bold; color: var(--accent);">${isActive ? "✓" : ""}</span>
          <span style="flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${doc.title}</span>
          <span style="font-size: 10px; color: var(--text-muted);">${doc.type === 'start' ? 'Start' : 'MW'}</span>
        </span>
      `;
      item.onclick = (e) => {
        e.stopPropagation();
        menu.style.display = "none";
        this.switchToDocument(doc.id);
      };
      menu.appendChild(item);
    });

    const overflowBtn = document.getElementById("btn-tab-overflow");
    if (overflowBtn) {
      const rect = overflowBtn.getBoundingClientRect();
      menu.style.position = "fixed";
      menu.style.top = `${rect.bottom + 4}px`;
      menu.style.left = `${Math.max(10, rect.right - 220)}px`;
      menu.style.display = "block";
      menu.style.zIndex = "3000";
    }
  }

  getActiveWorksheet() {
    const activeDoc = this.documents.find(d => d.id === this.activeDocId);
    if (activeDoc && activeDoc.type === "worksheet") {
      return activeDoc.instance;
    }
    // If currently on Start Page, create new worksheet
    return this.createNewWorksheet();
  }

  getWorksheetById(docId) {
    const doc = this.documents.find(d => d.id === docId);
    return doc && doc.type === "worksheet" ? doc.instance : null;
  }

  // 3. Menubar & Dropdowns
  initMenubar() {
    const menuItems = document.querySelectorAll(".menu-item");

    menuItems.forEach(item => {
      const trigger = item.querySelector(".menu-trigger");
      trigger.addEventListener("click", (e) => {
        e.stopPropagation();
        const wasActive = item.classList.contains("active");
        menuItems.forEach(m => m.classList.remove("active"));
        if (!wasActive) item.classList.add("active");
      });

      item.addEventListener("mouseenter", () => {
        const anyActive = Array.from(menuItems).some(m => m.classList.contains("active"));
        if (anyActive) {
          menuItems.forEach(m => m.classList.remove("active"));
          item.classList.add("active");
        }
      });
    });

    document.addEventListener("click", () => {
      menuItems.forEach(m => m.classList.remove("active"));
    });

    // Menubar action clicks
    document.querySelectorAll(".menu-action[data-action]").forEach(btn => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        menuItems.forEach(m => m.classList.remove("active"));
        this.executeAction(btn.dataset.action, btn.dataset.arg);
      });
    });
  }

  executeAction(action, arg) {
    const ws = this.getActiveWorksheet();

    switch (action) {
      case "new":
        this.createNewWorksheet();
        break;
      case "open":
        this.triggerFileOpenDialog();
        break;
      case "save":
        this.saveActiveDocument();
        break;
      case "save_as":
        this.saveActiveDocumentAs();
        break;
      case "print":
      case "export_pdf":
        this.dialogManager.openDialog("dialog-export-pdf");
        this.dialogManager.setupExportPdf();
        break;
      case "export_tex":
        this.exportDocument("tex");
        break;
      case "export_md":
        this.exportDocument("md");
        break;
      case "export_json":
        this.exportDocument("json");
        break;
      case "close_tab":
        if (this.activeDocId) this.closeDocument(this.activeDocId);
        break;
      case "undo":
        document.execCommand("undo");
        break;
      case "redo":
        document.execCommand("redo");
        break;
      case "cut":
        document.execCommand("cut");
        break;
      case "copy":
        document.execCommand("copy");
        break;
      case "paste":
        document.execCommand("paste");
        break;
      case "select_all":
        document.execCommand("selectAll");
        break;
      case "clear_worksheet":
        if (ws) ws.clearWorksheet();
        break;
      case "toggle_palettes":
        this.toggleDock("palette-dock");
        break;
      case "toggle_context":
        this.toggleDock("context-dock");
        break;
      case "zoom_in":
        this.zoomWorksheet(1);
        break;
      case "zoom_out":
        this.zoomWorksheet(-1);
        break;
      case "zoom_reset":
        if (ws) ws.setZoom(100);
        break;
      case "zoom_set":
        if (ws && arg) ws.setZoom(parseInt(arg, 10));
        break;
      case "insert_cell_after":
        if (ws) ws.addCell({ insertAfterId: ws.activeCellId });
        break;
      case "insert_cell_before":
        if (ws) {
          const idx = ws.cells.findIndex(c => c.id === ws.activeCellId);
          const prevId = idx > 0 ? ws.cells[idx - 1].id : null;
          ws.addCell({ insertAfterId: prevId });
        }
        break;
      case "insert_section":
        if (ws) ws.insertSection(parseInt(arg || "0", 10));
        break;
      case "toggle_mode_f5":
        if (ws && ws.activeCellId) ws.toggleCellMode(ws.activeCellId);
        break;
      case "matrix_wizard":
        this.dialogManager.openDialog("dialog-matrix-wizard");
        break;
      case "insert_template":
        if (arg) this.insertTemplateIntoActiveCell(arg);
        break;
      case "set_mode":
        if (ws && ws.activeCellId) ws.setCellMode(ws.activeCellId, arg);
        break;
      case "indent_section":
        if (ws) ws.indentActiveCell();
        break;
      case "outdent_section":
        if (ws) ws.outdentActiveCell();
        break;
      case "set_line_spacing":
        this.setLineSpacing(arg);
        break;
      case "set_decimal_sep":
        this.setDecimalSeparator(arg);
        break;
      case "execute_active":
        if (ws && ws.activeCellId) ws.executeCell(ws.activeCellId);
        break;
      case "execute_all":
        if (ws) ws.runAllCells();
        break;
      case "stop_execution":
        this.updateStatusMessage("Execution stopped.");
        break;
      case "restart_kernel":
        this.worker.postMessage({ type: "RESET" });
        if (ws) ws.clearWorksheet();
        break;
      case "options":
        this.dialogManager.openDialog("dialog-options");
        break;
      case "set_theme":
        this.applyTheme(arg);
        break;
      case "restore_layout":
        this.restoreDefaultLayout();
        break;
      case "help_topics":
        this.dialogManager.openDialog("dialog-help-topics");
        break;
      case "about":
        this.dialogManager.openDialog("dialog-about");
        break;
    }
  }

  // 4. Main Toolbar
  initMainToolbar() {
    document.getElementById("tb-btn-new").onclick = () => this.createNewWorksheet();
    document.getElementById("tb-btn-open").onclick = () => this.triggerFileOpenDialog();
    document.getElementById("tb-btn-save").onclick = () => this.saveActiveDocument();
    document.getElementById("tb-btn-print").onclick = () => this.executeAction("print");

    document.getElementById("tb-btn-undo").onclick = () => document.execCommand("undo");
    document.getElementById("tb-btn-redo").onclick = () => document.execCommand("redo");

    document.getElementById("tb-btn-eval").onclick = () => this.executeAction("execute_active");
    document.getElementById("tb-btn-eval-all").onclick = () => this.executeAction("execute_all");
    document.getElementById("tb-btn-stop").onclick = () => this.executeAction("stop_execution");
    document.getElementById("tb-btn-restart").onclick = () => this.executeAction("restart_kernel");

    document.getElementById("tb-btn-zoom-in").onclick = () => this.zoomWorksheet(1);
    document.getElementById("tb-btn-zoom-out").onclick = () => this.zoomWorksheet(-1);

    document.getElementById("btn-tab-add").onclick = () => this.createNewWorksheet();

    const overflowBtn = document.getElementById("btn-tab-overflow");
    if (overflowBtn) {
      overflowBtn.onclick = (e) => {
        e.stopPropagation();
        this.showTabOverflowMenu();
      };
    }

    // Help Search Input & Autocomplete
    const searchInput = document.getElementById("tb-search-input");
    const autoList = document.getElementById("tb-search-autocomplete");

    searchInput.addEventListener("input", () => {
      const q = searchInput.value.trim().toLowerCase();
      if (!q) {
        autoList.classList.remove("open");
        return;
      }
      const matches = this.helpCatalog.filter(h => h.name.toLowerCase().includes(q)).slice(0, 10);
      if (matches.length > 0) {
        autoList.innerHTML = matches.map(m => `<div class="autocomplete-item" data-topic="${m.name}">🔍 ${m.name} (${m.category})</div>`).join("");
        autoList.classList.add("open");

        autoList.querySelectorAll(".autocomplete-item").forEach(item => {
          item.onclick = () => {
            searchInput.value = "";
            autoList.classList.remove("open");
            this.dialogManager.openDialog("dialog-help-topics");
            setTimeout(() => {
              const searchBox = document.getElementById("help-topics-search");
              if (searchBox) {
                searchBox.value = item.dataset.topic;
                searchBox.dispatchEvent(new Event("input"));
              }
            }, 50);
          };
        });
      } else {
        autoList.classList.remove("open");
      }
    });

    searchInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && searchInput.value.trim()) {
        const val = searchInput.value.trim();
        searchInput.value = "";
        autoList.classList.remove("open");
        this.dialogManager.openDialog("dialog-help-topics");
        setTimeout(() => {
          const searchBox = document.getElementById("help-topics-search");
          if (searchBox) {
            searchBox.value = val;
            searchBox.dispatchEvent(new Event("input"));
          }
        }, 50);
      }
    });

    document.addEventListener("click", (e) => {
      if (!searchInput.contains(e.target) && !autoList.contains(e.target)) {
        autoList.classList.remove("open");
      }
    });
  }

  // 5. Context Bar Toolbar
  initContextBar() {
    // Mode buttons
    const modePills = {
      "text": document.getElementById("pill-mode-text"),
      "nonexec_math": document.getElementById("pill-mode-nonexec"),
      "2d_math": document.getElementById("pill-mode-math"),
      "1d_math": document.getElementById("pill-mode-c")
    };

    Object.entries(modePills).forEach(([mode, btn]) => {
      if (btn) {
        btn.onclick = () => {
          const ws = this.getActiveWorksheet();
          if (ws && ws.activeCellId) {
            ws.setCellMode(ws.activeCellId, mode);
          }
        };
      }
    });

    // Font Family & Size combos
    const fontCombo = document.getElementById("context-font-combo");
    if (fontCombo) {
      fontCombo.onchange = () => this.setFontFamily(fontCombo.value);
    }
    const fontSizeCombo = document.getElementById("context-font-size-combo");
    if (fontSizeCombo) {
      fontSizeCombo.onchange = () => this.setFontSize(fontSizeCombo.value);
    }

    // Formatting: Bold, Italic, Underline
    document.getElementById("btn-fmt-bold").onclick = () => document.execCommand("bold");
    document.getElementById("btn-fmt-italic").onclick = () => document.execCommand("italic");
    document.getElementById("btn-fmt-underline").onclick = () => document.execCommand("underline");

    // Alignments
    document.getElementById("btn-align-left").onclick = () => document.execCommand("justifyLeft");
    document.getElementById("btn-align-center").onclick = () => document.execCommand("justifyCenter");
    document.getElementById("btn-align-right").onclick = () => document.execCommand("justifyRight");

    // Indent / Outdent
    document.getElementById("btn-outdent").onclick = () => this.executeAction("outdent_section");
    document.getElementById("btn-indent").onclick = () => this.executeAction("indent_section");

    // Line Spacing Dropdown Button
    const lineSpacingBtn = document.getElementById("btn-line-spacing");
    const lineSpacingMenu = document.getElementById("line-spacing-popup");
    if (lineSpacingBtn && lineSpacingMenu) {
      lineSpacingBtn.onclick = (e) => {
        e.stopPropagation();
        lineSpacingMenu.classList.toggle("open");
      };
      lineSpacingMenu.querySelectorAll(".menu-action").forEach(a => {
        a.onclick = () => {
          this.setLineSpacing(a.dataset.spacing);
          lineSpacingMenu.classList.remove("open");
        };
      });
    }

    // Swatches: Text Color and Highlight Marker
    this.initColorSwatches();

    // Section Dropdown Split Button
    const secMainBtn = document.getElementById("btn-sec-main");
    const secArrowBtn = document.getElementById("btn-sec-arrow");
    const secMenu = document.getElementById("sec-dropdown-menu");

    if (secMainBtn) {
      secMainBtn.onclick = () => this.executeAction("insert_section", "0");
    }
    if (secArrowBtn && secMenu) {
      secArrowBtn.onclick = (e) => {
        e.stopPropagation();
        secMenu.classList.toggle("open");
      };
      secMenu.querySelectorAll(".menu-action").forEach(a => {
        a.onclick = () => {
          this.executeAction(a.dataset.action, a.dataset.arg);
          secMenu.classList.remove("open");
        };
      });
    }

    document.addEventListener("click", () => {
      if (lineSpacingMenu) lineSpacingMenu.classList.remove("open");
      if (secMenu) secMenu.classList.remove("open");
    });
  }

  initColorSwatches() {
    const textColorBtn = document.getElementById("btn-text-color-swatch");
    const textPopup = document.getElementById("text-color-popup");
    const highlightBtn = document.getElementById("btn-highlight-swatch");
    const highlightPopup = document.getElementById("highlight-color-popup");

    const setupPopup = (btn, popup, isHighlight) => {
      btn.onclick = (e) => {
        e.stopPropagation();
        popup.classList.toggle("open");
      };

      popup.querySelectorAll(".color-cell").forEach(cell => {
        cell.onclick = () => {
          const col = cell.dataset.color;
          if (isHighlight) {
            document.execCommand("hiliteColor", false, col);
            document.querySelector(".highlight-swatch-bar").style.backgroundColor = col;
          } else {
            document.execCommand("foreColor", false, col);
            document.querySelector(".swatch-color-bar").style.backgroundColor = col;
          }
          popup.classList.remove("open");
        };
      });

      const resetBtn = popup.querySelector(".reset-color-btn");
      if (resetBtn) {
        resetBtn.onclick = () => {
          if (isHighlight) {
            document.execCommand("hiliteColor", false, "transparent");
            document.querySelector(".highlight-swatch-bar").style.backgroundColor = "transparent";
          } else {
            document.execCommand("foreColor", false, "#000000");
            document.querySelector(".swatch-color-bar").style.backgroundColor = "#000000";
          }
          popup.classList.remove("open");
        };
      }
    };

    if (textColorBtn && textPopup) setupPopup(textColorBtn, textPopup, false);
    if (highlightBtn && highlightPopup) setupPopup(highlightBtn, highlightPopup, true);

    document.addEventListener("click", () => {
      if (textPopup) textPopup.classList.remove("open");
      if (highlightPopup) highlightPopup.classList.remove("open");
    });
  }

  // 6. Status Bar
  initStatusBar() {
    const editableChk = document.getElementById("status-editable-chk");
    if (editableChk) {
      editableChk.onchange = () => {
        const ws = this.getActiveWorksheet();
        if (ws) ws.setEditable(editableChk.checked);
        this.updateStatusMessage(editableChk.checked ? "Editable Mode." : "View Mode (Read-Only).");
      };
    }

    const decimalSeg = document.getElementById("status-decimal-seg");
    if (decimalSeg) {
      decimalSeg.onclick = () => {
        const next = this.decimalSeparator === "," ? "." : ",";
        this.setDecimalSeparator(next);
      };
    }

    const zoomSeg = document.getElementById("status-zoom-seg");
    if (zoomSeg) {
      zoomSeg.onclick = () => {
        const ws = this.getActiveWorksheet();
        if (ws) ws.setZoom(100);
      };
    }

    const pathSeg = document.getElementById("status-path-seg");
    if (pathSeg) {
      pathSeg.onclick = () => this.saveActiveDocument();
    }

    // Simulate memory reporting
    setInterval(() => {
      const memEl = document.getElementById("status-memory-seg");
      if (memEl) {
        const mem = (120 + Math.random() * 5).toFixed(2);
        memEl.textContent = `Memory: ${mem}M`;
      }
    }, 4000);
  }

  // 7. Global Shortcuts
  initGlobalShortcuts() {
    window.addEventListener("keydown", (e) => {
      const isCtrlOrMeta = e.ctrlKey || e.metaKey;

      if (isCtrlOrMeta && e.key.toLowerCase() === "n") {
        e.preventDefault();
        this.createNewWorksheet();
      } else if (isCtrlOrMeta && e.key.toLowerCase() === "o") {
        e.preventDefault();
        this.triggerFileOpenDialog();
      } else if (isCtrlOrMeta && e.key.toLowerCase() === "s") {
        e.preventDefault();
        this.saveActiveDocument();
      } else if (isCtrlOrMeta && e.key.toLowerCase() === "p") {
        e.preventDefault();
        this.executeAction("print");
      } else if (isCtrlOrMeta && e.key.toLowerCase() === "m") {
        e.preventDefault();
        this.dialogManager.openDialog("dialog-matrix-wizard");
      } else if (isCtrlOrMeta && e.key.toLowerCase() === "j") {
        e.preventDefault();
        this.executeAction("insert_cell_after");
      } else if (isCtrlOrMeta && e.key.toLowerCase() === "k") {
        e.preventDefault();
        this.executeAction("insert_cell_before");
      } else if (isCtrlOrMeta && (e.key === "+" || e.key === "=")) {
        e.preventDefault();
        this.zoomWorksheet(1);
      } else if (isCtrlOrMeta && (e.key === "-" || e.key === "_")) {
        e.preventDefault();
        this.zoomWorksheet(-1);
      } else if (isCtrlOrMeta && e.key === "0") {
        e.preventDefault();
        const ws = this.getActiveWorksheet();
        if (ws) ws.setZoom(100);
      } else if (isCtrlOrMeta && e.key === ",") {
        e.preventDefault();
        this.dialogManager.openDialog("dialog-options");
      } else if (e.key === "F5") {
        e.preventDefault();
        const ws = this.getActiveWorksheet();
        if (ws && ws.activeCellId) ws.toggleCellMode(ws.activeCellId);
      }
    });
  }

  // 8. Layout & Docks
  initLayoutComponents() {
    this.palette = new PaletteManager(this);
    this.contextPanel = new ContextPanelManager(this);
    this.dialogManager = new DialogManager(this);
  }

  toggleDock(dockId) {
    const dock = document.getElementById(dockId);
    if (dock) {
      if (dock.style.display === "none") {
        dock.style.display = "flex";
      } else {
        dock.style.display = "none";
      }
      this.updateViewMenuCheckmarks();
    }
  }

  updateViewMenuCheckmarks() {
    const palDock = document.getElementById("palette-dock");
    const ctxDock = document.getElementById("context-dock");
    const palChk = document.getElementById("chk-menu-palettes");
    const ctxChk = document.getElementById("chk-menu-context");

    if (palChk) palChk.textContent = palDock && palDock.style.display !== "none" ? "✓" : "";
    if (ctxChk) ctxChk.textContent = ctxDock && ctxDock.style.display !== "none" && !ctxDock.classList.contains("collapsed") ? "✓" : "";
  }

  restoreDefaultLayout() {
    const palDock = document.getElementById("palette-dock");
    const ctxDock = document.getElementById("context-dock");
    if (palDock) palDock.style.display = "flex";
    if (ctxDock) ctxDock.style.display = "none";
    this.updateViewMenuCheckmarks();
  }

  // Helper State Setters
  applyTheme(theme) {
    this.theme = theme;
    localStorage.setItem("openmath_theme", theme);
    document.body.className = `theme-${theme}`;
    document.documentElement.setAttribute("data-theme", theme);

    document.querySelectorAll(".theme-menu-chk").forEach(chk => {
      chk.textContent = chk.dataset.theme === theme ? "✓" : "";
    });

    // Update canvas plots
    this.documents.forEach(d => {
      if (d.type === "worksheet") {
        d.instance.plotInstances.forEach(p => p.setTheme(theme));
        d.instance.drawScopeOverlay();
      }
    });
  }

  setDecimalSeparator(sep) {
    this.decimalSeparator = sep;
    localStorage.setItem("openmath_decimal_sep", sep);
    if (this.worker) {
      this.worker.postMessage({ type: "SET_DECIMAL_SEPARATOR", sep });
    }
    const decSeg = document.getElementById("status-decimal-seg");
    if (decSeg) {
      decSeg.innerHTML = `Decimal: <strong>${sep}</strong>`;
    }
    document.querySelectorAll(".dec-menu-chk").forEach(chk => {
      chk.textContent = chk.dataset.sep === sep ? "✓" : "";
    });
  }

  setPrecision(prec) {
    this.precision = prec;
    localStorage.setItem("openmath_precision", prec);
  }

  setFontFamily(font) {
    this.currentFontFamily = font;
    document.querySelectorAll(".cell-input-edit:not(.mode-1d)").forEach(el => {
      el.style.fontFamily = font;
    });
  }

  setFontSize(size) {
    this.currentFontSize = size;
    document.querySelectorAll(".cell-input-edit").forEach(el => {
      el.style.fontSize = `${size}px`;
    });
  }

  setLineSpacing(val) {
    const lineHeightMap = { "1.0": "1.2", "1.15": "1.35", "1.25": "1.45", "1.5": "1.7", "2.0": "2.2", "2.5": "2.7", "3.0": "3.2" };
    const lh = lineHeightMap[val] || "1.4";
    document.querySelectorAll(".cell-input-edit").forEach(el => {
      el.style.lineHeight = lh;
    });
  }

  setWindowTitle(title) {
    const textEl = document.getElementById("window-title-text");
    const full = `${title} - [Server 3] - OpenMath`;
    if (textEl) textEl.textContent = full;
    document.title = full;
  }

  updateStatusMessage(msg) {
    const msgEl = document.getElementById("status-msg-seg");
    if (msgEl) msgEl.textContent = msg;
  }

  updateStatusMode(mode) {
    const modeEl = document.getElementById("status-mode-seg");
    if (modeEl) {
      const names = { "start": "Start Page", "2d_math": "Math Mode", "1d_math": "1D Math", "text": "Text Mode", "section": "Section" };
      modeEl.textContent = names[mode] || mode;
    }
  }

  updateStatusPath(path) {
    const pathEl = document.getElementById("status-path-seg");
    if (pathEl) {
      pathEl.textContent = path || "Save Document";
      pathEl.style.color = path ? "var(--text-secondary)" : "#dc2626";
      pathEl.style.fontWeight = path ? "normal" : "bold";
    }
  }

  updateZoomLabel(txt) {
    const zoomEl = document.getElementById("status-zoom-seg");
    if (zoomEl) zoomEl.textContent = `Zoom: ${txt}`;
  }

  updateExecutionTime(seconds) {
    const timeEl = document.getElementById("status-time-seg");
    if (timeEl) timeEl.textContent = `Time: ${seconds.toFixed(2)}s`;
  }

  updateContextBar(mode) {
    const pills = {
      "text": document.getElementById("pill-mode-text"),
      "nonexec_math": document.getElementById("pill-mode-nonexec"),
      "2d_math": document.getElementById("pill-mode-math"),
      "1d_math": document.getElementById("pill-mode-c")
    };
    Object.entries(pills).forEach(([m, btn]) => {
      if (btn) {
        if (m === mode) btn.classList.add("active");
        else btn.classList.remove("active");
      }
    });
  }

  zoomWorksheet(delta) {
    const ws = this.getActiveWorksheet();
    if (ws) {
      const newZoom = Math.max(50, Math.min(300, ws.zoom + delta * 25));
      ws.setZoom(newZoom);
    }
  }

  insertTemplateIntoActiveCell(template) {
    const ws = this.getActiveWorksheet();
    if (!ws) return;

    if (!ws.activeCellId) {
      ws.addCell();
    }
    const cell = ws.cells.find(c => c.id === ws.activeCellId);
    if (!cell || !cell.domElement) return;

    const editEl = cell.domElement.querySelector(".cell-input-edit");
    if (editEl) {
      editEl.focus();
      document.execCommand("insertText", false, template);
      cell.input = editEl.innerText;
      this.contextPanel.setTargetExpression(cell.input);
    }
  }

  // 9. File I/O
  triggerFileOpenDialog() {
    const fileInput = document.createElement("input");
    fileInput.type = "file";
    fileInput.accept = ".mw,.mv,.json,.txt,.zip";
    fileInput.onchange = (e) => {
      const file = e.target.files[0];
      if (file) {
        this.updateStatusMessage(`Loading ${file.name}...`);
        const reader = new FileReader();
        reader.onload = (re) => {
          const buffer = re.target.result;
          const uint8 = new Uint8Array(buffer);
          let content;
          // Check for zip magic header: PK\x03\x04 (0x50, 0x4B, 0x03, 0x04)
          if (uint8.length >= 4 && uint8[0] === 0x50 && uint8[1] === 0x4B && uint8[2] === 0x03 && uint8[3] === 0x04) {
            let binary = "";
            const chunkSize = 16384;
            for (let i = 0; i < uint8.length; i += chunkSize) {
              binary += String.fromCharCode.apply(null, uint8.subarray(i, i + chunkSize));
            }
            content = "BASE64_ZIP:" + btoa(binary);
          } else {
            const decoder = new TextDecoder("utf-8");
            content = decoder.decode(buffer);
          }
          this.worker.postMessage({
            type: "PARSE_DOCUMENT",
            filename: file.name,
            content
          });
        };
        reader.readAsArrayBuffer(file);
      }
    };
    fileInput.click();
  }

  saveActiveDocument() {
    const ws = this.getActiveWorksheet();
    if (!ws) return;
    this.exportDocument("mw", ws.title);
    this.updateStatusPath(ws.title);
  }

  saveActiveDocumentAs() {
    const ws = this.getActiveWorksheet();
    if (!ws) return;
    this.dialogManager.showPrompt("Enter file name:", ws.title || "Worksheet.mw", (newName) => {
      if (newName && newName.trim()) {
        const trimmed = newName.trim();
        ws.title = trimmed.endsWith(".mw") ? trimmed : `${trimmed}.mw`;
        const doc = this.documents.find(d => d.id === ws.docId);
        if (doc) doc.title = ws.title;
        this.renderTabsToolbar();
        this.setWindowTitle(ws.title);
        this.saveActiveDocument();
      }
    }, "Save Document As");
  }

  exportDocument(format, filename = null) {
    const ws = this.getActiveWorksheet();
    if (!ws) return;
    const exportName = filename || `${ws.title.replace(/\.[^.]+$/, '')}.${format}`;
    const cells = ws.getSerializableCells();
    this.worker.postMessage({
      type: "EXPORT_DOCUMENT",
      format,
      cells,
      filename: exportName
    });
  }

  executeExportPdf(unfoldSections) {
    if (unfoldSections) {
      const ws = this.getActiveWorksheet();
      if (ws) {
        ws.cells.forEach(c => {
          if (c.isSectionHeader) c.isCollapsed = false;
        });
        ws.updateSectionFolding();
        ws.drawScopeOverlay();
      }
    }
    window.print();
  }

  downloadFile(filename, content) {
    const blob = new Blob([content], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    this.updateStatusMessage(`Saved ${filename}`);
  }
}

// Instantiate and launch when DOM is ready
window.addEventListener("DOMContentLoaded", () => {
  window.openMathApp = new OpenMathApplication();
  window.openMathApp.init();
});
