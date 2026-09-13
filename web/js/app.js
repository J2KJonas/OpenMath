/**
 * OpenMath Web Application Coordinator
 * Integrates Web Worker CAS runtime, interactive worksheet, palettes, and mobile touch dock.
 */

import { WorksheetManager } from "./worksheet.js";
import { PaletteManager } from "./palette.js";
import { MobileDockManager } from "./mobile-dock.js";

class OpenMathApp {
  constructor() {
    this.worker = null;
    this.worksheet = null;
    this.palette = null;
    this.mobileDock = null;
    this.theme = localStorage.getItem("openmath_theme") || "dark";
    this.pendingEvaluations = new Map();
  }

  init() {
    this.initTheme();
    this.initWorksheet();
    this.initPalette();
    this.initMobileDock();
    this.initWorker();
    this.bindHeaderEvents();
    this.bindExportModal();
  }

  initTheme() {
    this.applyTheme(this.theme);

    const themeToggleBtn = document.getElementById("theme-toggle-btn");
    if (themeToggleBtn) {
      themeToggleBtn.addEventListener("click", () => {
        const nextTheme = this.theme === "dark" ? "light" : "dark";
        this.applyTheme(nextTheme);
      });
    }
  }

  applyTheme(theme) {
    this.theme = theme;
    localStorage.setItem("openmath_theme", theme);
    document.body.className = `theme-${theme}`;
    document.documentElement.setAttribute("data-theme", theme);

    const moonIcon = document.getElementById("theme-icon-moon");
    const sunIcon = document.getElementById("theme-icon-sun");

    if (moonIcon && sunIcon) {
      if (theme === "dark") {
        moonIcon.style.display = "block";
        sunIcon.style.display = "none";
      } else {
        moonIcon.style.display = "none";
        sunIcon.style.display = "block";
      }
    }

    if (this.worksheet) {
      this.worksheet.setTheme(theme);
    }
  }

  initWorker() {
    const loadingOverlay = document.getElementById("loading-overlay");
    const loadingStatus = document.getElementById("loading-status");
    const statusText = document.getElementById("status-text");
    const statusDot = document.getElementById("status-indicator");
    const engineTag = document.getElementById("engine-version");

    try {
      this.worker = new Worker("./js/cas-worker.js");

      this.worker.onmessage = (e) => {
        const data = e.data;
        if (!data) return;

        switch (data.type) {
          case "STATUS":
            if (loadingStatus) loadingStatus.textContent = data.message;
            if (statusText) statusText.textContent = data.message;
            break;

          case "READY":
            if (loadingOverlay) {
              loadingOverlay.classList.add("hidden");
              setTimeout(() => {
                loadingOverlay.style.display = "none";
              }, 400);
            }
            if (statusDot) statusDot.className = "status-dot ready";
            if (statusText) statusText.textContent = "Ready (Pyodide CAS Engine)";
            if (engineTag && data.info) {
              engineTag.textContent = `SymPy ${data.info.sympy_version} • NumPy ${data.info.numpy_version}`;
            }
            break;

          case "RESULT":
            if (this.worksheet) {
              this.worksheet.handleResult(data.id, data);
            }
            break;

          case "ERROR":
            if (loadingStatus) loadingStatus.textContent = data.message;
            if (statusDot) statusDot.className = "status-dot error";
            if (statusText) statusText.textContent = data.message;
            break;
        }
      };

      // Start initialization
      this.worker.postMessage({ type: "INIT", basePath: "../" });
    } catch (err) {
      console.error("Failed to start Web Worker:", err);
      if (loadingStatus) loadingStatus.textContent = `Worker Error: ${err.message}`;
    }
  }

  initWorksheet() {
    const container = document.getElementById("worksheet-container");
    this.worksheet = new WorksheetManager(
      container,
      (cellId, expr, precision) => {
        if (this.worker) {
          this.worker.postMessage({
            type: "EVALUATE",
            id: cellId,
            expr: expr,
            precision: precision
          });
        }
      },
      { theme: this.theme }
    );

    // Initial default cell with an example calculation
    const firstCell = this.worksheet.addCell("diff(sin(x)*cos(x), x)", true);

    const addCellTopBtn = document.getElementById("btn-add-cell-top");
    const addCellBottomBtn = document.getElementById("btn-add-cell-bottom");

    if (addCellTopBtn) addCellTopBtn.addEventListener("click", () => this.worksheet.addCell("", true));
    if (addCellBottomBtn) addCellBottomBtn.addEventListener("click", () => this.worksheet.addCell("", true));
  }

  initPalette() {
    this.palette = new PaletteManager((text, cursorOffset) => {
      if (this.worksheet) {
        this.worksheet.insertTextAtCursor(text, cursorOffset);
      }
    });
    this.palette.init();
  }

  initMobileDock() {
    const mobileInput = document.getElementById("mobile-formula-input");

    this.mobileDock = new MobileDockManager(
      (text, cursorOffset) => {
        // If mobile input is focused, insert into it, otherwise worksheet cell
        if (document.activeElement === mobileInput) {
          const start = mobileInput.selectionStart || mobileInput.value.length;
          const end = mobileInput.selectionEnd || mobileInput.value.length;
          mobileInput.value = mobileInput.value.substring(0, start) + text + mobileInput.value.substring(end);
          const nextPos = start + text.length + cursorOffset;
          mobileInput.setSelectionRange(nextPos, nextPos);
        } else if (this.worksheet) {
          this.worksheet.insertTextAtCursor(text, cursorOffset);
        }
      },
      () => {
        // Execute active calculation
        if (mobileInput && mobileInput.value.trim()) {
          const cell = this.worksheet.addCell(mobileInput.value.trim(), true);
          this.worksheet.evaluateCell(cell.id);
          mobileInput.value = "";
        } else if (this.worksheet && this.worksheet.activeCellId) {
          this.worksheet.evaluateCell(this.worksheet.activeCellId);
        }
      },
      () => {
        // Backspace
        if (document.activeElement === mobileInput) {
          const start = mobileInput.selectionStart;
          if (start > 0) {
            mobileInput.value = mobileInput.value.substring(0, start - 1) + mobileInput.value.substring(start);
            mobileInput.setSelectionRange(start - 1, start - 1);
          }
        } else if (this.worksheet) {
          const inputEl = this.worksheet.getActiveInput();
          if (inputEl) {
            const start = inputEl.selectionStart;
            if (start > 0) {
              inputEl.value = inputEl.value.substring(0, start - 1) + inputEl.value.substring(start);
              inputEl.setSelectionRange(start - 1, start - 1);
            }
          }
        }
      }
    );
    this.mobileDock.init();
  }

  bindHeaderEvents() {
    // Mode Switch (Exact / Numeric)
    const exactBtn = document.getElementById("global-mode-exact");
    const numBtn = document.getElementById("global-mode-numeric");

    if (exactBtn && numBtn) {
      exactBtn.addEventListener("click", () => {
        exactBtn.classList.add("active");
        numBtn.classList.remove("active");
        if (this.worksheet) this.worksheet.setGlobalMode("exact");
      });

      numBtn.addEventListener("click", () => {
        numBtn.classList.add("active");
        exactBtn.classList.remove("active");
        if (this.worksheet) this.worksheet.setGlobalMode("numeric");
      });
    }

    // Precision selector
    const precSelect = document.getElementById("global-precision-select");
    if (precSelect) {
      precSelect.addEventListener("change", (e) => {
        if (this.worksheet) this.worksheet.setGlobalPrecision(e.target.value);
      });
    }

    // Clear All
    const clearBtn = document.getElementById("btn-clear-all");
    if (clearBtn) {
      clearBtn.addEventListener("click", () => {
        if (confirm("Clear all calculation cells in worksheet?")) {
          if (this.worksheet) this.worksheet.clearWorksheet();
        }
      });
    }

    // Mobile Sidebar Drawer Toggle
    const mobileMenuBtn = document.getElementById("mobile-menu-toggle");
    const closeSidebarBtn = document.getElementById("close-sidebar-btn");
    const sidebar = document.getElementById("app-sidebar");

    if (mobileMenuBtn && sidebar) {
      mobileMenuBtn.addEventListener("click", () => {
        sidebar.classList.toggle("open");
      });
    }

    if (closeSidebarBtn && sidebar) {
      closeSidebarBtn.addEventListener("click", () => {
        sidebar.classList.remove("open");
      });
    }
  }

  bindExportModal() {
    const exportBtn = document.getElementById("btn-export");
    const exportModal = document.getElementById("export-modal");
    const closeExportBtn = document.getElementById("close-export-modal");

    if (exportBtn && exportModal) {
      exportBtn.addEventListener("click", () => exportModal.classList.add("open"));
    }
    if (closeExportBtn && exportModal) {
      closeExportBtn.addEventListener("click", () => exportModal.classList.remove("open"));
    }

    document.querySelectorAll(".export-opt-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        const fmt = btn.dataset.format;
        if (this.worksheet) {
          this.worksheet.exportDocument(fmt);
        }
        if (exportModal) exportModal.classList.remove("open");
      });
    });
  }
}

// Instantiate and start OpenMath application on DOM load
window.addEventListener("DOMContentLoaded", () => {
  const app = new OpenMathApp();
  app.init();
});
