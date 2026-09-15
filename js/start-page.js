/**
 * OpenMath Start Page View (Start.mw)
 * Exact 1:1 replica of ui/start_page.py with 'New Document' and 'Open Documents' actions.
 */

export class StartPageView {
  constructor(app, container) {
    this.app = app;
    this.container = container;
    this.render();
  }

  render() {
    this.container.innerHTML = `
      <div class="start-page-container">
        <div class="start-page-card">
          <div class="start-page-header">
            <h1 class="start-page-title">OpenMath</h1>
            <p class="start-page-subtitle">Desktop Symbolic & Numerical Computer Algebra System</p>
          </div>

          <hr class="start-page-sep" />

          <div class="start-page-actions">
            <button id="btn-start-new-doc" class="start-action-btn">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                <polyline points="14 2 14 8 20 8"/>
                <line x1="12" y1="18" x2="12" y2="12"/>
                <line x1="9" y1="15" x2="15" y2="15"/>
              </svg>
              <span>New Document</span>
            </button>

            <button id="btn-start-open-doc" class="start-action-btn">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
              </svg>
              <span>Open Documents</span>
            </button>
          </div>

          <p class="start-page-hint">
            Select 'New Document' to start an empty worksheet,<br>or 'Open Documents' to load a .mw project.
          </p>

          <hr class="start-page-sep" />

          <div class="start-page-dev-card">
            <span class="start-page-dev-title">Developed by</span>
            <div class="start-page-dev-links">
              <a href="https://github.com/J2KJonas" target="_blank" rel="noopener noreferrer" class="start-dev-btn">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor"><path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0 0 24 12c0-6.63-5.37-12-12-12z"/></svg>
                <span>J2KDevelop ↗</span>
              </a>

              <a href="https://github.com/elomarjc" target="_blank" rel="noopener noreferrer" class="start-dev-btn">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor"><path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0 0 24 12c0-6.63-5.37-12-12-12z"/></svg>
                <span>Elomarstudio ↗</span>
              </a>
            </div>
          </div>
        </div>
      </div>
    `;

    document.getElementById("btn-start-new-doc").onclick = () => {
      this.app.createNewWorksheet();
    };

    document.getElementById("btn-start-open-doc").onclick = () => {
      this.app.triggerFileOpenDialog();
    };
  }
}
