/**
 * OpenMath Web Mobile Math Dock & Virtual Keypad
 * Ergonomic, touch-friendly mobile bottom sheet with quick symbols and categorized math tabs.
 */

export class MobileDockManager {
  constructor(onInsertCallback, onRunCallback, onBackspaceCallback) {
    this.onInsert = onInsertCallback;
    this.onRun = onRunCallback;
    this.onBackspace = onBackspaceCallback;
    this.isOpen = false;
    this.currentTab = "123";
  }

  init() {
    this.bindDockElements();
  }

  bindDockElements() {
    const dockToggleBtn = document.getElementById("mobile-dock-toggle");
    const dockDrawer = document.getElementById("mobile-keypad-drawer");
    const mobileRunBtn = document.getElementById("mobile-run-btn");
    const mobileInput = document.getElementById("mobile-formula-input");

    if (dockToggleBtn && dockDrawer) {
      dockToggleBtn.addEventListener("click", (e) => {
        e.preventDefault();
        this.toggleDrawer();
      });
    }

    if (mobileRunBtn) {
      mobileRunBtn.addEventListener("click", (e) => {
        e.preventDefault();
        this.triggerHaptic();
        this.onRun();
      });
    }

    if (mobileInput) {
      mobileInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
          e.preventDefault();
          this.onRun();
        }
      });
    }

    // Tab buttons inside drawer
    const tabBtns = document.querySelectorAll(".keypad-tab-btn");
    tabBtns.forEach((btn) => {
      btn.addEventListener("click", () => {
        const targetTab = btn.dataset.tab;
        this.switchTab(targetTab);
      });
    });

    // Delegated click for all keypad insert buttons
    document.addEventListener("click", (e) => {
      const btn = e.target.closest(".key-btn");
      if (!btn) return;
      e.preventDefault();
      this.triggerHaptic();

      if (btn.dataset.action === "backspace") {
        this.onBackspace();
        return;
      }

      if (btn.dataset.action === "run") {
        this.onRun();
        return;
      }

      const text = btn.dataset.insert || btn.textContent.trim();
      const offset = parseInt(btn.dataset.cursorOffset || "0", 10);
      this.onInsert(text, offset);
    });
  }

  toggleDrawer(forceState) {
    const dockDrawer = document.getElementById("mobile-keypad-drawer");
    const toggleIcon = document.getElementById("mobile-dock-toggle-icon");
    if (!dockDrawer) return;

    this.isOpen = forceState !== undefined ? forceState : !this.isOpen;
    if (this.isOpen) {
      dockDrawer.classList.add("open");
      if (toggleIcon) toggleIcon.style.transform = "rotate(180deg)";
    } else {
      dockDrawer.classList.remove("open");
      if (toggleIcon) toggleIcon.style.transform = "rotate(0deg)";
    }
  }

  switchTab(tabId) {
    this.currentTab = tabId;
    document.querySelectorAll(".keypad-tab-btn").forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.tab === tabId);
    });

    document.querySelectorAll(".keypad-tab-content").forEach((content) => {
      content.classList.toggle("active", content.dataset.tabContent === tabId);
    });
  }

  triggerHaptic() {
    if (typeof navigator !== "undefined" && navigator.vibrate) {
      navigator.vibrate(10);
    }
  }
}
