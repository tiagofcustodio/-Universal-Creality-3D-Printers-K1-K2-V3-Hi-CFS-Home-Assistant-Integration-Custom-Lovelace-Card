/**
 * Creality Universal K-Series / Klipper Custom Lovelace Card (creality-k2-card)
 * Supports: Creality K1, K1C, K1 Max, K1 SE, K2 SE, K2 Pro, K2 Plus, Ender-3 V3, Creality Hi & CFS
 * Zero-configuration auto-discovery of entities (or optional prefix / host filter)
 */

class CrealityK2Card extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._step = 10;
    this._activeTab = "control"; // 'control' | 'cfs' | 'files'
    this._prefix = "";
    this._selectedFile = "";
    this._lastActiveThumbFile = "";
  }

  setConfig(config) {
    this._config = config || {};
    if (this._config.prefix) {
      this._prefix = this._config.prefix;
    }
    this._renderSkeleton();
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._initialized) {
      this._renderSkeleton();
    }
    this._updateContent();
  }

  getCardSize() {
    return 8;
  }

  /**
   * Auto-discovers any Creality entity by domain and suffix, even without configuring `prefix:`!
   */
  _st(domainAndSuffix) {
    if (!this._hass) return null;
    if (this._hass.states[domainAndSuffix]) {
      return this._hass.states[domainAndSuffix];
    }
    const dotIdx = domainAndSuffix.indexOf(".");
    if (dotIdx === -1) return null;
    const domain = domainAndSuffix.slice(0, dotIdx + 1);
    let suffix = domainAndSuffix.slice(dotIdx + 1);

    // Strip leading prefix if auto-discovering
    if (this._prefix && suffix.startsWith(this._prefix + "_")) {
      suffix = suffix.slice(this._prefix.length + 1);
    }

    for (const [eid, stateObj] of Object.entries(this._hass.states)) {
      if (!eid.startsWith(domain)) continue;
      if (this._prefix && eid.includes(this._prefix) && eid.endsWith(suffix)) {
        return stateObj;
      }
      if (eid.endsWith("_" + suffix) || eid === domain + suffix) {
        return stateObj;
      }
    }
    return null;
  }

  _eid(domain, keySuffix) {
    const query = this._prefix ? `${domain}.${this._prefix}_${keySuffix}` : `${domain}.${keySuffix}`;
    const s = this._st(query);
    return s ? s.entity_id : query;
  }

  _val(domain, keySuffix, fallback = "--") {
    const query = this._prefix ? `${domain}.${this._prefix}_${keySuffix}` : `${domain}.${keySuffix}`;
    const s = this._st(query);
    if (!s || s.state === "unavailable" || s.state === "unknown") return fallback;
    return s.state;
  }

  _attr(domain, keySuffix, attrName, fallback = "") {
    const query = this._prefix ? `${domain}.${this._prefix}_${keySuffix}` : `${domain}.${keySuffix}`;
    const s = this._st(query);
    if (!s || !s.attributes || s.attributes[attrName] === undefined) return fallback;
    return s.attributes[attrName];
  }

  _formatMinutes(minsStr) {
    const m = parseFloat(minsStr);
    if (isNaN(m) || m <= 0) return "0m";
    const hrs = Math.floor(m / 60);
    const remMins = Math.floor(m % 60);
    const secs = Math.round((m - Math.floor(m)) * 60);
    if (hrs > 0) return `${hrs}h ${remMins}m`;
    return `${remMins}m ${secs}s`;
  }

  _parsePosition(posStr) {
    const res = { x: "0.00", y: "0.00", z: "0.00" };
    if (!posStr || typeof posStr !== "string") return res;
    const mx = posStr.match(/X:\s*([-\d.]+)/i);
    const my = posStr.match(/Y:\s*([-\d.]+)/i);
    const mz = posStr.match(/Z:\s*([-\d.]+)/i);
    if (mx) res.x = parseFloat(mx[1]).toFixed(2);
    if (my) res.y = parseFloat(my[1]).toFixed(2);
    if (mz) res.z = parseFloat(mz[1]).toFixed(2);
    return res;
  }

  _callService(domain, service, data = {}) {
    if (!this._hass) return;
    this._hass.callService(domain, service, data);
  }

  _sendGcode(gcode) {
    this._callService("creality_k2", "send_gcode", { gcode });
  }

  _jogAxis(axis, dir) {
    const dist = (this._step * dir).toFixed(1);
    const feed = axis === "Z" ? 600 : 6000;
    const script = `G91\nG1 ${axis}${dist} F${feed}\nG90`;
    this._sendGcode(script);
  }

  _homeAxis(axes) {
    if (axes === "XYZ") {
      this._sendGcode("G28");
    } else {
      this._sendGcode(`G28 ${axes}`);
    }
  }

  _updateSelectedPreviewImage(filename) {
    if (!filename || filename === "Nenhum" || filename === "Nenhum ficheiro encontrado") return;
    this._selectedFile = filename;
    const imgEl = this.shadowRoot.getElementById("img-selected-thumb");
    const nameEl = this.shadowRoot.getElementById("lbl-selected-filename");
    if (imgEl) {
      imgEl.src = `/api/creality_k2/thumbnail?file=${encodeURIComponent(filename)}`;
    }
    if (nameEl) {
      nameEl.textContent = filename;
    }
  }

  _renderSkeleton() {
    if (this._initialized) return;
    this._initialized = true;

    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
          font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Oxygen, Ubuntu, sans-serif;
          color: #e6edf3;
          --k2-bg: #1c1e24;
          --k2-panel: #252830;
          --k2-card: #181a20;
          --k2-border: rgba(255, 255, 255, 0.08);
          --k2-accent: #1e96fc;
          --k2-accent-glow: rgba(30, 150, 252, 0.35);
          --k2-success: #2ea043;
          --k2-warn: #d29922;
          --k2-danger: #f85149;
          --k2-muted: #8b949e;
        }

        .k2-container {
          background: var(--k2-bg);
          border-radius: 16px;
          padding: 14px;
          box-sizing: border-box;
          border: 1px solid var(--k2-border);
          box-shadow: 0 8px 28px rgba(0, 0, 0, 0.45);
          display: flex;
          flex-direction: column;
          gap: 14px;
        }

        .k2-section {
          background: var(--k2-panel);
          border-radius: 12px;
          border: 1px solid var(--k2-border);
          overflow: hidden;
        }

        .k2-section-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 10px 14px;
          background: rgba(255, 255, 255, 0.03);
          border-bottom: 1px solid var(--k2-border);
          font-weight: 600;
          font-size: 0.95rem;
          gap: 8px;
          flex-wrap: wrap;
        }

        .k2-header-left {
          display: flex;
          align-items: center;
          gap: 8px;
        }

        .k2-badge {
          font-size: 0.72rem;
          text-transform: uppercase;
          letter-spacing: 0.06em;
          padding: 3px 9px;
          border-radius: 999px;
          font-weight: 700;
          background: rgba(30, 150, 252, 0.18);
          color: #58a6ff;
          border: 1px solid rgba(30, 150, 252, 0.4);
        }
        .k2-badge.printing {
          background: rgba(46, 160, 67, 0.2);
          color: #3fb950;
          border-color: rgba(46, 160, 67, 0.5);
        }
        .k2-badge.paused {
          background: rgba(210, 153, 34, 0.2);
          color: #e3b341;
          border-color: rgba(210, 153, 34, 0.5);
        }

        .k2-action-pills {
          display: flex;
          gap: 8px;
        }

        .k2-pill-btn {
          background: #323642;
          color: #e6edf3;
          border: 1px solid var(--k2-border);
          border-radius: 999px;
          padding: 5px 13px;
          font-size: 0.78rem;
          font-weight: 600;
          cursor: pointer;
          display: inline-flex;
          align-items: center;
          gap: 5px;
          transition: all 0.15s ease;
        }
        .k2-pill-btn:hover {
          background: var(--k2-accent);
          border-color: var(--k2-accent);
          color: #fff;
        }
        .k2-pill-btn.danger:hover {
          background: var(--k2-danger);
          border-color: var(--k2-danger);
        }

        /* Top Printing Grid */
        .k2-print-body {
          padding: 14px;
          display: grid;
          grid-template-columns: 120px 1fr auto;
          gap: 16px;
          align-items: center;
        }

        .k2-thumb-box {
          width: 120px;
          height: 120px;
          border-radius: 10px;
          background: radial-gradient(circle at center, #1f3a52 0%, #131c26 100%);
          border: 1px solid rgba(30, 150, 252, 0.3);
          overflow: hidden;
          display: flex;
          align-items: center;
          justify-content: center;
          position: relative;
        }
        .k2-thumb-box img {
          width: 100%;
          height: 100%;
          object-fit: contain;
        }

        .k2-print-info {
          display: flex;
          flex-direction: column;
          gap: 7px;
          min-width: 0;
        }

        .k2-meta-row {
          font-size: 0.85rem;
          color: var(--k2-muted);
          display: flex;
          gap: 8px;
          align-items: center;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }
        .k2-meta-row strong {
          color: #e6edf3;
          font-weight: 600;
          overflow: hidden;
          text-overflow: ellipsis;
        }

        .k2-progress-wrap {
          display: flex;
          align-items: center;
          gap: 10px;
          margin-top: 4px;
        }
        .k2-progress-bar {
          flex: 1;
          height: 8px;
          background: #14161b;
          border-radius: 999px;
          overflow: hidden;
          border: 1px solid var(--k2-border);
        }
        .k2-progress-fill {
          height: 100%;
          background: linear-gradient(90deg, #1e96fc, #00d2ff);
          border-radius: 999px;
          width: 0%;
          transition: width 0.4s ease;
        }
        .k2-progress-pct {
          font-weight: 700;
          font-size: 0.92rem;
          color: #fff;
          min-width: 42px;
          text-align: right;
        }

        .k2-time-stats {
          display: flex;
          flex-direction: column;
          gap: 6px;
          padding-left: 16px;
          border-left: 1px solid var(--k2-border);
          font-size: 0.83rem;
          min-width: 155px;
        }
        .k2-time-row {
          display: flex;
          justify-content: space-between;
          gap: 10px;
          color: var(--k2-muted);
        }
        .k2-time-row strong {
          color: #e6edf3;
        }

        /* Quick Temps Bar */
        .k2-temps-strip {
          display: grid;
          grid-template-columns: repeat(4, 1fr);
          gap: 8px;
          padding: 0 14px 14px 14px;
        }
        .k2-temp-pill {
          background: var(--k2-card);
          border: 1px solid var(--k2-border);
          border-radius: 9px;
          padding: 8px 10px;
          display: flex;
          flex-direction: column;
          gap: 2px;
        }
        .k2-temp-pill span {
          font-size: 0.72rem;
          color: var(--k2-muted);
        }
        .k2-temp-pill strong {
          font-size: 0.95rem;
          color: #fff;
        }

        /* Navigation Tabs */
        .k2-tabs {
          display: flex;
          gap: 6px;
          background: var(--k2-panel);
          padding: 6px;
          border-radius: 10px;
          border: 1px solid var(--k2-border);
        }
        .k2-tab {
          flex: 1;
          text-align: center;
          padding: 8px 10px;
          border-radius: 7px;
          font-size: 0.84rem;
          font-weight: 600;
          color: var(--k2-muted);
          cursor: pointer;
          border: none;
          background: transparent;
          transition: all 0.15s ease;
        }
        .k2-tab.active {
          background: var(--k2-accent);
          color: #fff;
          box-shadow: 0 2px 10px var(--k2-accent-glow);
        }

        /* Control Panel: Axis D-Pad + Coordinates + Step Buttons */
        .k2-control-grid {
          padding: 14px;
          display: grid;
          grid-template-columns: auto 1fr;
          gap: 20px;
          align-items: center;
        }

        .k2-dpad-wrapper {
          display: flex;
          gap: 14px;
          align-items: center;
          justify-content: center;
        }

        .k2-xy-pad {
          display: grid;
          grid-template-columns: repeat(3, 46px);
          grid-template-rows: repeat(3, 42px);
          gap: 6px;
        }
        .k2-z-pad {
          display: grid;
          grid-template-columns: 48px;
          grid-template-rows: repeat(3, 42px);
          gap: 6px;
        }

        .k2-jog-btn {
          background: var(--k2-accent);
          color: #fff;
          border: none;
          border-radius: 8px;
          font-weight: 700;
          font-size: 0.8rem;
          cursor: pointer;
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          line-height: 1.05;
          box-shadow: 0 2px 6px rgba(0, 0, 0, 0.3);
          transition: transform 0.1s ease, filter 0.15s ease;
          user-select: none;
        }
        .k2-jog-btn:active {
          transform: scale(0.93);
        }
        .k2-jog-btn:hover {
          filter: brightness(1.12);
        }
        .k2-jog-btn.home-btn {
          background: #3a3f4b;
          color: #fff;
          font-size: 1rem;
        }

        .k2-coords-panel {
          display: flex;
          flex-direction: column;
          gap: 12px;
        }

        .k2-coords-row {
          display: grid;
          grid-template-columns: repeat(3, 1fr);
          gap: 8px;
        }
        .k2-coord-box {
          background: var(--k2-card);
          border: 1px solid var(--k2-border);
          border-radius: 7px;
          padding: 7px 10px;
          display: flex;
          justify-content: space-between;
          align-items: center;
          font-size: 0.85rem;
        }
        .k2-coord-box span {
          color: var(--k2-muted);
          font-weight: 700;
        }
        .k2-coord-box strong {
          font-family: monospace;
          font-size: 0.92rem;
          color: #fff;
        }

        .k2-steps-row {
          display: grid;
          grid-template-columns: repeat(4, 1fr);
          gap: 8px;
        }
        .k2-step-btn {
          background: #343844;
          color: #d0d7de;
          border: 1px solid var(--k2-border);
          border-radius: 7px;
          padding: 8px 4px;
          font-size: 0.82rem;
          font-weight: 600;
          cursor: pointer;
          transition: all 0.15s ease;
        }
        .k2-step-btn.active {
          background: var(--k2-accent);
          color: #fff;
          border-color: var(--k2-accent);
        }

        .k2-speed-input-row {
          display: flex;
          align-items: center;
          gap: 10px;
          flex-wrap: wrap;
          font-size: 0.84rem;
          color: var(--k2-muted);
        }
        .k2-num-input {
          background: var(--k2-card);
          border: 1px solid var(--k2-border);
          color: #fff;
          border-radius: 6px;
          padding: 6px 10px;
          width: 68px;
          font-weight: 600;
          text-align: center;
        }

        /* 4 Fan & Light Subcards Grid */
        .k2-hw-grid {
          padding: 0 14px 14px 14px;
          display: grid;
          grid-template-columns: repeat(4, 1fr);
          gap: 10px;
        }
        .k2-hw-card {
          background: var(--k2-card);
          border: 1px solid var(--k2-border);
          border-radius: 10px;
          padding: 12px;
          display: flex;
          flex-direction: column;
          justify-content: space-between;
          gap: 10px;
        }
        .k2-hw-top {
          display: flex;
          justify-content: space-between;
          align-items: center;
          font-size: 0.84rem;
          font-weight: 600;
        }
        .k2-switch {
          position: relative;
          width: 40px;
          height: 22px;
          background: #3a3f4b;
          border-radius: 999px;
          cursor: pointer;
          transition: background 0.2s ease;
          border: none;
          padding: 0;
        }
        .k2-switch.on {
          background: var(--k2-accent);
        }
        .k2-switch::after {
          content: "";
          position: absolute;
          top: 3px;
          left: 3px;
          width: 16px;
          height: 16px;
          background: #fff;
          border-radius: 50%;
          transition: transform 0.2s ease;
        }
        .k2-switch.on::after {
          transform: translateX(18px);
        }
        .k2-hw-sub {
          font-size: 0.78rem;
          color: var(--k2-muted);
          display: flex;
          align-items: center;
          gap: 5px;
        }
        .k2-hw-sub strong {
          color: #fff;
        }
        .k2-slider {
          width: 100%;
          accent-color: var(--k2-accent);
          cursor: pointer;
          height: 5px;
        }

        /* CFS Multi-Color Spools Section */
        .k2-cfs-grid {
          padding: 14px;
          display: grid;
          grid-template-columns: repeat(4, 1fr);
          gap: 10px;
        }
        .k2-spool-card {
          background: var(--k2-card);
          border: 2px solid var(--k2-border);
          border-radius: 12px;
          padding: 12px 10px;
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 8px;
          cursor: pointer;
          transition: all 0.15s ease;
          position: relative;
        }
        .k2-spool-card.active {
          border-color: var(--k2-accent);
          box-shadow: 0 0 14px var(--k2-accent-glow);
        }
        .k2-spool-ring {
          width: 48px;
          height: 48px;
          border-radius: 50%;
          border: 6px solid #444;
          display: flex;
          align-items: center;
          justify-content: center;
          font-weight: 700;
          font-size: 0.76rem;
          color: #fff;
          text-shadow: 0 1px 3px rgba(0,0,0,0.9);
          box-shadow: inset 0 2px 5px rgba(0,0,0,0.5), 0 2px 8px rgba(0,0,0,0.4);
        }
        .k2-spool-mat {
          font-weight: 700;
          font-size: 0.9rem;
          color: #fff;
        }
        .k2-spool-tag {
          font-size: 0.7rem;
          padding: 2px 7px;
          border-radius: 99px;
          background: rgba(255,255,255,0.07);
          color: var(--k2-muted);
        }
        .k2-spool-card.active .k2-spool-tag {
          background: var(--k2-accent);
          color: #fff;
        }

        /* Stored Files Section */
        .k2-files-body {
          padding: 14px;
          display: grid;
          grid-template-columns: 160px 1fr;
          gap: 16px;
          align-items: center;
        }
        .k2-preview-large {
          width: 160px;
          height: 160px;
          border-radius: 12px;
          background: radial-gradient(circle at center, #1f3a52 0%, #131c26 100%);
          border: 1px solid rgba(30, 150, 252, 0.35);
          overflow: hidden;
          display: flex;
          align-items: center;
          justify-content: center;
        }
        .k2-preview-large img {
          width: 100%;
          height: 100%;
          object-fit: contain;
        }
        .k2-file-controls {
          display: flex;
          flex-direction: column;
          gap: 10px;
          min-width: 0;
        }
        .k2-select {
          width: 100%;
          background: var(--k2-card);
          color: #fff;
          border: 1px solid var(--k2-border);
          border-radius: 8px;
          padding: 10px;
          font-size: 0.88rem;
        }
        .k2-primary-btn {
          background: var(--k2-accent);
          color: #fff;
          border: none;
          border-radius: 8px;
          padding: 10px 16px;
          font-weight: 700;
          font-size: 0.88rem;
          cursor: pointer;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          gap: 8px;
          transition: filter 0.15s ease;
        }
        .k2-primary-btn:hover {
          filter: brightness(1.12);
        }

        /* Responsive Mobile & Small Tablet Rules */
        @media (max-width: 680px) {
          .k2-print-body {
            grid-template-columns: 96px 1fr;
          }
          .k2-thumb-box {
            width: 96px;
            height: 96px;
          }
          .k2-time-stats {
            grid-column: 1 / -1;
            flex-direction: row;
            justify-content: space-between;
            border-left: none;
            border-top: 1px solid var(--k2-border);
            padding-left: 0;
            padding-top: 10px;
          }
          .k2-temps-strip {
            grid-template-columns: repeat(2, 1fr);
          }
          .k2-control-grid {
            grid-template-columns: 1fr;
            justify-items: center;
          }
          .k2-coords-panel {
            width: 100%;
          }
          .k2-hw-grid {
            grid-template-columns: repeat(2, 1fr);
          }
          .k2-cfs-grid {
            grid-template-columns: repeat(2, 1fr);
          }
          .k2-files-body {
            grid-template-columns: 1fr;
            justify-items: center;
          }
          .k2-file-controls {
            width: 100%;
          }
        }
      </style>

      <div class="k2-container">
        <!-- 1. TOP PRINTING STATUS CARD -->
        <div class="k2-section">
          <div class="k2-section-header">
            <div class="k2-header-left">
              <span id="k2-printer-title">🖨️ Creality 3D Printer</span>
              <span id="k2-state-badge" class="k2-badge">STANDBY</span>
            </div>
            <div class="k2-action-pills">
              <button class="k2-pill-btn" id="btn-pause-resume">⏸ Pause</button>
              <button class="k2-pill-btn danger" id="btn-stop">⏹ Stop</button>
            </div>
          </div>

          <div class="k2-print-body">
            <div class="k2-thumb-box">
              <img id="img-active-thumb" src="" alt="3D Model" />
            </div>

            <div class="k2-print-info">
              <div class="k2-meta-row">
                <span>File:</span>
                <strong id="txt-filename">--</strong>
              </div>
              <div class="k2-meta-row">
                <span>Layer:</span>
                <strong id="txt-layer">0 / 0</strong>
                <span style="margin-left:auto" id="txt-speed">0 mm/s</span>
              </div>
              <div class="k2-progress-wrap">
                <div class="k2-progress-bar">
                  <div class="k2-progress-fill" id="bar-progress"></div>
                </div>
                <span class="k2-progress-pct" id="txt-progress">0%</span>
              </div>
            </div>

            <div class="k2-time-stats">
              <div class="k2-time-row">
                <span>Printing time:</span>
                <strong id="txt-elapsed">0m</strong>
              </div>
              <div class="k2-time-row">
                <span>Remaining:</span>
                <strong id="txt-remaining">0m</strong>
              </div>
            </div>
          </div>

          <!-- Quick Temperatures & Filament Strip -->
          <div class="k2-temps-strip">
            <div class="k2-temp-pill">
              <span>🔥 Bico (Nozzle)</span>
              <strong id="txt-nozzle-temp">0°C / 0°C</strong>
            </div>
            <div class="k2-temp-pill">
              <span>🛏️ Mesa (Bed)</span>
              <strong id="txt-bed-temp">0°C / 0°C</strong>
            </div>
            <div class="k2-temp-pill">
              <span>🎨 Bobine CFS</span>
              <strong id="txt-active-cfs">Nenhum</strong>
            </div>
            <div class="k2-temp-pill">
              <span>🧵 Filamento Usado</span>
              <strong id="txt-used-mat">0.0 m</strong>
            </div>
          </div>
        </div>

        <!-- NAVIGATION TABS -->
        <div class="k2-tabs">
          <button class="k2-tab active" data-tab="control">⚙️ Controlo & Ventoinhas</button>
          <button class="k2-tab" data-tab="cfs" id="tab-btn-cfs">🎨 CFS Multicor</button>
          <button class="k2-tab" data-tab="files">📂 Ficheiros 3D</button>
        </div>

        <!-- 2. CONTROL SECTION (XY/Z D-Pad + Coords + 4 Fan/LED Cards) -->
        <div class="k2-section" id="sec-control">
          <div class="k2-section-header">
            <span>⚙️ Controlo de Eixos, Temperaturas e Arrefecimento</span>
          </div>

          <div class="k2-control-grid">
            <div class="k2-dpad-wrapper">
              <!-- XY Pad -->
              <div class="k2-xy-pad">
                <div></div>
                <button class="k2-jog-btn" data-jog="Y:1"><span>Y+</span><span>▲</span></button>
                <div></div>
                <button class="k2-jog-btn" data-jog="X:-1"><span>X- ◀</span></button>
                <button class="k2-jog-btn home-btn" data-home="XY" title="Home XY">🏠</button>
                <button class="k2-jog-btn" data-jog="X:1"><span>▶ X+</span></button>
                <div></div>
                <button class="k2-jog-btn" data-jog="Y:-1"><span>Y-</span><span>▼</span></button>
                <div></div>
              </div>

              <!-- Z Pad -->
              <div class="k2-z-pad">
                <button class="k2-jog-btn" data-jog="Z:1"><span>Z+</span><span>▲</span></button>
                <button class="k2-jog-btn home-btn" data-home="Z" title="Home Z">🏠</button>
                <button class="k2-jog-btn" data-jog="Z:-1"><span>Z-</span><span>▼</span></button>
              </div>
            </div>

            <div class="k2-coords-panel">
              <div class="k2-coords-row">
                <div class="k2-coord-box"><span>X</span><strong id="pos-x">0.00</strong></div>
                <div class="k2-coord-box"><span>Y</span><strong id="pos-y">0.00</strong></div>
                <div class="k2-coord-box"><span>Z</span><strong id="pos-z">0.00</strong></div>
              </div>

              <div class="k2-steps-row">
                <button class="k2-step-btn" data-step="0.1">0.1mm</button>
                <button class="k2-step-btn" data-step="1">1mm</button>
                <button class="k2-step-btn active" data-step="10">10mm</button>
                <button class="k2-step-btn" data-step="100">100mm</button>
              </div>

              <div class="k2-speed-input-row">
                <span>Velocidade:</span>
                <input type="number" class="k2-num-input" id="inp-feedrate" min="10" max="300" step="5" value="100" />
                <span>%</span>
                <span style="margin-left:6px">Bico (°C):</span>
                <input type="number" class="k2-num-input" id="inp-nozzle" min="0" max="350" step="5" value="0" />
                <span style="margin-left:6px">Mesa (°C):</span>
                <input type="number" class="k2-num-input" id="inp-bed" min="0" max="120" step="5" value="0" />
              </div>
            </div>
          </div>

          <!-- 4 Hardware Sub-Cards (Model Fan, Back Fan, Side Fan, LED Light) -->
          <div class="k2-hw-grid">
            <!-- Model Fan -->
            <div class="k2-hw-card">
              <div class="k2-hw-top">
                <span>Model fan</span>
                <button class="k2-switch" id="sw-model-fan"></button>
              </div>
              <div class="k2-hw-sub">
                <span>💨 wind speed:</span>
                <strong id="lbl-model-fan">0%</strong>
              </div>
              <input type="range" class="k2-slider" id="rng-model-fan" min="0" max="100" step="5" value="0" />
            </div>

            <!-- Back / Case Fan -->
            <div class="k2-hw-card">
              <div class="k2-hw-top">
                <span>Back fan</span>
                <button class="k2-switch" id="sw-back-fan"></button>
              </div>
              <div class="k2-hw-sub">
                <span>💨 wind speed:</span>
                <strong id="lbl-back-fan">0%</strong>
              </div>
              <input type="range" class="k2-slider" id="rng-back-fan" min="0" max="100" step="5" value="0" />
            </div>

            <!-- Side / Aux Fan -->
            <div class="k2-hw-card">
              <div class="k2-hw-top">
                <span>Side fan</span>
                <button class="k2-switch" id="sw-aux-fan"></button>
              </div>
              <div class="k2-hw-sub">
                <span>💨 wind speed:</span>
                <strong id="lbl-aux-fan">0%</strong>
              </div>
              <input type="range" class="k2-slider" id="rng-aux-fan" min="0" max="100" step="5" value="0" />
            </div>

            <!-- LED Light -->
            <div class="k2-hw-card">
              <div class="k2-hw-top">
                <span>LED light</span>
                <button class="k2-switch" id="sw-led"></button>
              </div>
              <div class="k2-hw-sub">
                <span>💡 Iluminação Interna</span>
              </div>
              <div style="font-size:0.78rem; color:var(--k2-accent)" id="lbl-led-state">Ligada</div>
            </div>
          </div>
        </div>

        <!-- 3. CFS MULTI-COLOR SECTION -->
        <div class="k2-section" id="sec-cfs" style="display:none">
          <div class="k2-section-header">
            <span>🎨 Sistema Multicor CFS (Toque numa bobine para carregar)</span>
            <div class="k2-action-pills">
              <button class="k2-pill-btn" id="btn-cfs-refresh">🔄 Ler RFID</button>
              <button class="k2-pill-btn" id="btn-cfs-unload">⏏️ Retrair</button>
            </div>
          </div>
          <div class="k2-cfs-grid" id="cfs-spools-container"></div>
        </div>

        <!-- 4. STORED FILES & INSTANT 3D PREVIEW SECTION -->
        <div class="k2-section" id="sec-files" style="display:none">
          <div class="k2-section-header">
            <span>📂 Ficheiros Guardados na Impressora (Pré-visualização 3D Instantânea)</span>
          </div>
          <div class="k2-files-body">
            <div class="k2-preview-large">
              <img id="img-selected-thumb" src="" alt="Pré-visualização 3D" />
            </div>
            <div class="k2-file-controls">
              <label style="font-size:0.82rem; color:var(--k2-muted)">
                Escolha um ficheiro .gcode para ver a imagem 3D antes de imprimir:
              </label>
              <select class="k2-select" id="sel-gcode-file"></select>
              <div style="font-size:0.78rem; color:var(--k2-muted); overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">
                Selecionado: <strong style="color:#fff" id="lbl-selected-filename">--</strong>
              </div>
              <button class="k2-primary-btn" id="btn-start-selected">
                🚀 Iniciar Impressão deste Ficheiro
              </button>
            </div>
          </div>
        </div>
      </div>
    `;

    this._bindEvents();
  }

  _bindEvents() {
    const root = this.shadowRoot;

    // Tabs
    root.querySelectorAll(".k2-tab").forEach((btn) => {
      btn.addEventListener("click", () => {
        this._activeTab = btn.dataset.tab;
        root.querySelectorAll(".k2-tab").forEach((b) => b.classList.toggle("active", b === btn));
        root.getElementById("sec-control").style.display = this._activeTab === "control" ? "block" : "none";
        root.getElementById("sec-cfs").style.display = this._activeTab === "cfs" ? "block" : "none";
        root.getElementById("sec-files").style.display = this._activeTab === "files" ? "block" : "none";
      });
    });

    // Pause / Resume
    root.getElementById("btn-pause-resume").addEventListener("click", () => {
      const st = this._val("sensor", "estado_da_impressora", "standby");
      if (st === "paused") {
        this._callService("button", "press", { entity_id: this._eid("button", "retomar_impressao") });
      } else {
        this._callService("button", "press", { entity_id: this._eid("button", "pausar_impressao") });
      }
    });

    // Stop
    root.getElementById("btn-stop").addEventListener("click", () => {
      if (confirm("Tem a certeza que pretende cancelar/parar a impressão atual?")) {
        this._callService("button", "press", { entity_id: this._eid("button", "cancelar_parar_impressao") });
      }
    });

    // Step buttons
    root.querySelectorAll(".k2-step-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        this._step = parseFloat(btn.dataset.step);
        root.querySelectorAll(".k2-step-btn").forEach((b) => b.classList.toggle("active", b === btn));
      });
    });

    // Jog buttons
    root.querySelectorAll("[data-jog]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const [axis, dirStr] = btn.dataset.jog.split(":");
        this._jogAxis(axis, parseFloat(dirStr));
      });
    });

    // Home buttons
    root.querySelectorAll("[data-home]").forEach((btn) => {
      btn.addEventListener("click", () => {
        this._homeAxis(btn.dataset.home);
      });
    });

    // Speed, Nozzle & Bed inputs
    root.getElementById("inp-feedrate").addEventListener("change", (e) => {
      this._callService("number", "set_value", {
        entity_id: this._eid("number", "velocidade_de_impressao"),
        value: parseFloat(e.target.value),
      });
    });
    root.getElementById("inp-nozzle").addEventListener("change", (e) => {
      this._callService("number", "set_value", {
        entity_id: this._eid("number", "temperatura_alvo_do_bico"),
        value: parseFloat(e.target.value),
      });
    });
    root.getElementById("inp-bed").addEventListener("change", (e) => {
      this._callService("number", "set_value", {
        entity_id: this._eid("number", "temperatura_alvo_da_mesa"),
        value: parseFloat(e.target.value),
      });
    });

    // Model Fan
    root.getElementById("sw-model-fan").addEventListener("click", () => {
      const cur = parseFloat(this._val("number", "ventoinha_de_peca_part_fan", "0"));
      this._callService("number", "set_value", {
        entity_id: this._eid("number", "ventoinha_de_peca_part_fan"),
        value: cur > 0 ? 0 : 100,
      });
    });
    root.getElementById("rng-model-fan").addEventListener("change", (e) => {
      this._callService("number", "set_value", {
        entity_id: this._eid("number", "ventoinha_de_peca_part_fan"),
        value: parseFloat(e.target.value),
      });
    });

    // Back / Case Fan (falls back to flowrate if case fan entity not yet loaded)
    root.getElementById("sw-back-fan").addEventListener("click", () => {
      const backEntity = this._st("number.ventoinha_traseira_exaustao_back_fan");
      if (backEntity) {
        const cur = parseFloat(backEntity.state) || 0;
        this._callService("number", "set_value", {
          entity_id: backEntity.entity_id,
          value: cur > 0 ? 0 : 100,
        });
      }
    });
    root.getElementById("rng-back-fan").addEventListener("change", (e) => {
      const backEntity = this._st("number.ventoinha_traseira_exaustao_back_fan");
      if (backEntity) {
        this._callService("number", "set_value", {
          entity_id: backEntity.entity_id,
          value: parseFloat(e.target.value),
        });
      }
    });

    // Aux / Side Fan
    root.getElementById("sw-aux-fan").addEventListener("click", () => {
      const cur = parseFloat(this._val("number", "ventoinha_auxiliar_lateral", "0"));
      this._callService("number", "set_value", {
        entity_id: this._eid("number", "ventoinha_auxiliar_lateral"),
        value: cur > 0 ? 0 : 100,
      });
    });
    root.getElementById("rng-aux-fan").addEventListener("change", (e) => {
      this._callService("number", "set_value", {
        entity_id: this._eid("number", "ventoinha_auxiliar_lateral"),
        value: parseFloat(e.target.value),
      });
    });

    // LED Light
    root.getElementById("sw-led").addEventListener("click", () => {
      this._callService("light", "toggle", {
        entity_id: this._eid("light", "luz_led_da_impressora"),
      });
    });

    // CFS actions
    root.getElementById("btn-cfs-refresh").addEventListener("click", () => {
      this._callService("button", "press", { entity_id: this._eid("button", "cfs_atualizar_slots_rfid") });
    });
    root.getElementById("btn-cfs-unload").addEventListener("click", () => {
      this._callService("button", "press", { entity_id: this._eid("button", "cfs_retrair_descarregar_filamento") });
    });

    // File selector: INSTANTLY updates the 3D preview image without starting print!
    root.getElementById("sel-gcode-file").addEventListener("change", (e) => {
      const chosenFile = e.target.value;
      this._updateSelectedPreviewImage(chosenFile);

      const previewSelectObj = this._st("select.selecionar_ficheiro_g_code_guardado");
      if (previewSelectObj) {
        this._callService("select", "select_option", {
          entity_id: previewSelectObj.entity_id,
          option: chosenFile,
        });
      }
    });

    // Start print button
    root.getElementById("btn-start-selected").addEventListener("click", () => {
      const sel = root.getElementById("sel-gcode-file").value;
      if (!sel) return;
      if (confirm(`Iniciar impressão do ficheiro:\n${sel}?`)) {
        this._callService("creality_k2", "start_print", { filename: sel });
      }
    });
  }

  _updateContent() {
    if (!this._hass) return;
    const root = this.shadowRoot;

    const status = this._val("sensor", "estado_da_impressora", "standby");
    const hostname = this._attr("sensor", "estado_da_impressora", "hostname", "");
    const progress = parseFloat(this._val("sensor", "progresso_de_impressao", "0")) || 0;
    const filename = this._val("sensor", "ficheiro_atual", "Nenhum");
    const layer = this._val("sensor", "camada_atual", "0 / 0");
    const speed = this._val("sensor", "velocidade_em_tempo_real", "0");
    const elapsedMins = this._val("sensor", "tempo_decorrido", "0");
    const remainMins = this._val("sensor", "tempo_restante", "0");

    if (hostname) {
      root.getElementById("k2-printer-title").textContent = `🖨️ Creality (${hostname})`;
    }

    // Badge & Pause Button
    const badge = root.getElementById("k2-state-badge");
    badge.textContent = status.toUpperCase();
    badge.className = `k2-badge ${status}`;
    root.getElementById("btn-pause-resume").textContent = status === "paused" ? "▶ Resume" : "⏸ Pause";

    // Print telemetry
    root.getElementById("txt-filename").textContent = filename;
    root.getElementById("txt-layer").textContent = layer;
    root.getElementById("txt-speed").textContent = `${speed} mm/s`;
    root.getElementById("bar-progress").style.width = `${Math.min(100, Math.max(0, progress))}%`;
    root.getElementById("txt-progress").textContent = `${progress}%`;
    root.getElementById("txt-elapsed").textContent = this._formatMinutes(elapsedMins);
    root.getElementById("txt-remaining").textContent = this._formatMinutes(remainMins);

    // Quick strip
    const nozTemp = this._val("sensor", "temperatura_do_bico", "0");
    const nozTarget = this._val("number", "temperatura_alvo_do_bico", "0");
    const bedTemp = this._val("sensor", "temperatura_da_mesa", "0");
    const bedTarget = this._val("number", "temperatura_alvo_da_mesa", "0");
    const activeCfs = this._val("sensor", "cfs_slot_ativo", "Nenhum");
    const usedMat = this._val("sensor", "filamento_usado_na_impressao", "0");

    root.getElementById("txt-nozzle-temp").textContent = `${nozTemp}°C / ${nozTarget}°C`;
    root.getElementById("txt-bed-temp").textContent = `${bedTemp}°C / ${bedTarget}°C`;
    root.getElementById("txt-active-cfs").textContent = activeCfs;
    root.getElementById("txt-used-mat").textContent = `${usedMat} m`;

    // Coordinates
    const posStr = this._attr("sensor", "estado_da_impressora", "position", "X:0 Y:0 Z:0");
    const coords = this._parsePosition(posStr);
    root.getElementById("pos-x").textContent = coords.x;
    root.getElementById("pos-y").textContent = coords.y;
    root.getElementById("pos-z").textContent = coords.z;

    // Inputs
    const feedPct = parseFloat(this._val("number", "velocidade_de_impressao", "100")) || 100;
    if (root.activeElement !== root.getElementById("inp-feedrate")) {
      root.getElementById("inp-feedrate").value = feedPct;
    }
    if (root.activeElement !== root.getElementById("inp-nozzle")) {
      root.getElementById("inp-nozzle").value = parseFloat(nozTarget) || 0;
    }
    if (root.activeElement !== root.getElementById("inp-bed")) {
      root.getElementById("inp-bed").value = parseFloat(bedTarget) || 0;
    }

    // Fans & LED
    const modelFan = parseFloat(this._val("number", "ventoinha_de_peca_part_fan", "0")) || 0;
    const auxFan = parseFloat(this._val("number", "ventoinha_auxiliar_lateral", "0")) || 0;
    const backFan = parseFloat(this._val("number", "ventoinha_traseira_exaustao_back_fan", "0")) || 0;
    const ledOn = this._val("light", "luz_led_da_impressora", "off") === "on";

    root.getElementById("sw-model-fan").classList.toggle("on", modelFan > 0);
    root.getElementById("lbl-model-fan").textContent = `${modelFan}%`;
    root.getElementById("rng-model-fan").value = modelFan;

    root.getElementById("sw-back-fan").classList.toggle("on", backFan > 0);
    root.getElementById("lbl-back-fan").textContent = `${backFan}%`;
    root.getElementById("rng-back-fan").value = backFan;

    root.getElementById("sw-aux-fan").classList.toggle("on", auxFan > 0);
    root.getElementById("lbl-aux-fan").textContent = `${auxFan}%`;
    root.getElementById("rng-aux-fan").value = auxFan;

    root.getElementById("sw-led").classList.toggle("on", ledOn);
    root.getElementById("lbl-led-state").textContent = ledOn ? "Ligada (ON)" : "Desligada (OFF)";

    // Top Active Print Thumbnail
    if (filename && filename !== "Nenhum" && filename !== this._lastActiveThumbFile) {
      this._lastActiveThumbFile = filename;
      root.getElementById("img-active-thumb").src = `/api/creality_k2/thumbnail?file=${encodeURIComponent(filename)}`;
    } else if (!filename || filename === "Nenhum") {
      const activeCamObj =
        this._st("camera.camara_imagem_da_impressao_atual") ||
        this._st("camera.camara_pre_visualizacao_3d");
      if (activeCamObj && activeCamObj.attributes.entity_picture) {
        root.getElementById("img-active-thumb").src = activeCamObj.attributes.entity_picture;
      }
    }

    // Stored G-code files dropdown & Instant Selected File Preview
    const fileSelectEntity =
      this._st("select.selecionar_ficheiro_g_code_guardado") ||
      this._st("select.iniciar_ficheiro_g_code_guardado");
    if (fileSelectEntity && fileSelectEntity.attributes.options) {
      const selEl = root.getElementById("sel-gcode-file");
      const opts = fileSelectEntity.attributes.options;
      if (selEl.options.length !== opts.length) {
        const initialFile = this._selectedFile || fileSelectEntity.state || opts[0];
        selEl.innerHTML = opts
          .map((o) => `<option value="${o}" ${o === initialFile ? "selected" : ""}>${o}</option>`)
          .join("");
        if (!this._selectedFile && initialFile) {
          this._updateSelectedPreviewImage(initialFile);
        }
      }
    }

    // CFS Spools (supports 4, 8, 12, or 16 slots automatically)
    const cfsContainer = root.getElementById("cfs-spools-container");
    const allSlots = [];
    for (let u = 1; u <= 4; u++) {
      for (const letter of ["a", "b", "c", "d"]) {
        const num = (u - 1) * 4 + (letter.charCodeAt(0) - 96);
        const id = `t${u}${letter}`;
        const label = id.toUpperCase();
        const stObj = this._st(`sensor.cfs_slot_${num}_${id}`);
        if (stObj || u === 1) {
          allSlots.push({ id, label, num });
        }
      }
    }

    cfsContainer.innerHTML = allSlots
      .map((s) => {
        const keySuffix = `cfs_slot_${s.num}_${s.id}`;
        const mat = this._attr("sensor", keySuffix, "material", "Vazio");
        const hex = this._attr("sensor", keySuffix, "color_hex", "#808080");
        const loaded = this._attr("sensor", keySuffix, "loaded", false) || activeCfs === s.label;
        return `
          <div class="k2-spool-card ${loaded ? "active" : ""}" data-slot="${s.label}">
            <div class="k2-spool-ring" style="background:${hex}">
              ${s.label}
            </div>
            <div class="k2-spool-mat">${mat}</div>
            <div class="k2-spool-tag">${loaded ? "Em Uso no Extrusor" : "Toque p/ Carregar"}</div>
          </div>
        `;
      })
      .join("");

    cfsContainer.querySelectorAll(".k2-spool-card").forEach((card) => {
      card.addEventListener("click", () => {
        const slot = card.dataset.slot;
        if (confirm(`Carregar bobine ${slot} no extrusor?`)) {
          this._callService("creality_k2", "cfs_load_slot", { slot });
        }
      });
    });
  }
}

if (!customElements.get("creality-k2-card")) {
  customElements.define("creality-k2-card", CrealityK2Card);
}

window.customCards = window.customCards || [];
window.customCards.push({
  type: "creality-k2-card",
  name: "Creality Universal 3D Printer Card (K1 / K2 / V3 / Hi + CFS)",
  description: "All-in-One responsive card for Creality 3D printers with XY/Z Jog, Fans/LED, CFS Multi-Color Spools, and Instant 3D File Preview.",
});
