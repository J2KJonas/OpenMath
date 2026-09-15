/**
 * OpenMath Web 2D Canvas Plotter
 * High-performance, Retina-aware 2D plotting engine matching OpenMath Matplotlib styles.
 */

export class MathPlotter {
  constructor(canvas, plotData, options = {}) {
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d");
    this.data = plotData;
    this.options = {
      theme: options.theme || "light",
      padding: { top: 35, right: 25, bottom: 45, left: 55 },
      ...options
    };

    this.isLight = this.options.theme === "light";

    this.colors = this.isLight
      ? ["#2563eb", "#dc2626", "#16a34a", "#ea580c", "#9333ea", "#0284c7", "#ca8a04"]
      : ["#38bdf8", "#fb7185", "#34d399", "#fbbf24", "#c084fc", "#67e8f9", "#f43f5e"];

    this.bounds = this.calculateBounds();
    this.initEvents();
    this.render();
  }

  setTheme(theme) {
    this.options.theme = theme;
    this.isLight = theme === "light";
    this.colors = this.isLight
      ? ["#2563eb", "#dc2626", "#16a34a", "#ea580c", "#9333ea", "#0284c7", "#ca8a04"]
      : ["#38bdf8", "#fb7185", "#34d399", "#fbbf24", "#c084fc", "#67e8f9", "#f43f5e"];
    this.render();
  }

  calculateBounds() {
    let minX = Infinity, maxX = -Infinity;
    let minY = Infinity, maxY = -Infinity;

    if (this.data.x_lim && this.data.x_lim.length === 2) {
      minX = this.data.x_lim[0];
      maxX = this.data.x_lim[1];
    }
    if (this.data.y_lim && this.data.y_lim.length === 2) {
      minY = this.data.y_lim[0];
      maxY = this.data.y_lim[1];
    }

    // Inspect curves
    if (this.data.curves) {
      for (const curve of this.data.curves) {
        if (!curve.x || !curve.y) continue;
        for (let i = 0; i < curve.x.length; i++) {
          const x = curve.x[i];
          const y = curve.y[i];
          if (!isFinite(x) || !isFinite(y)) continue;
          if (x < minX) minX = x;
          if (x > maxX) maxX = x;
          if (y < minY) minY = y;
          if (y > maxY) maxY = y;
        }
      }
    }

    // Inspect regions
    if (this.data.regions) {
      for (const reg of this.data.regions) {
        if (!reg.x) continue;
        for (let i = 0; i < reg.x.length; i++) {
          const x = reg.x[i];
          const y1 = reg.y_min ? reg.y_min[i] : null;
          const y2 = reg.y_max ? reg.y_max[i] : null;
          if (isFinite(x)) {
            if (x < minX) minX = x;
            if (x > maxX) maxX = x;
          }
          if (y1 !== null && isFinite(y1)) {
            if (y1 < minY) minY = y1;
            if (y1 > maxY) maxY = y1;
          }
          if (y2 !== null && isFinite(y2)) {
            if (y2 < minY) minY = y2;
            if (y2 > maxY) maxY = y2;
          }
        }
      }
    }

    // Default bounds if none found
    if (!isFinite(minX) || !isFinite(maxX) || minX === maxX) {
      minX = -10; maxX = 10;
    }
    if (!isFinite(minY) || !isFinite(maxY) || minY === maxY) {
      minY = -10; maxY = 10;
    }

    const dx = (maxX - minX) * 0.08 || 1;
    const dy = (maxY - minY) * 0.08 || 1;

    return {
      minX: minX - dx,
      maxX: maxX + dx,
      minY: minY - dy,
      maxY: maxY + dy
    };
  }

  toScreenX(x) {
    const { minX, maxX } = this.bounds;
    const { left, right } = this.options.padding;
    const plotWidth = this.width - left - right;
    return left + ((x - minX) / (maxX - minX)) * plotWidth;
  }

  toScreenY(y) {
    const { minY, maxY } = this.bounds;
    const { top, bottom } = this.options.padding;
    const plotHeight = this.height - top - bottom;
    return this.height - bottom - ((y - minY) / (maxY - minY)) * plotHeight;
  }

  toMathX(screenX) {
    const { minX, maxX } = this.bounds;
    const { left, right } = this.options.padding;
    const plotWidth = this.width - left - right;
    return minX + ((screenX - left) / plotWidth) * (maxX - minX);
  }

  toMathY(screenY) {
    const { minY, maxY } = this.bounds;
    const { top, bottom } = this.options.padding;
    const plotHeight = this.height - top - bottom;
    return minY + ((this.height - bottom - screenY) / plotHeight) * (maxY - minY);
  }

  resize() {
    const rect = this.canvas.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    this.width = rect.width || 600;
    this.height = rect.height || 320;

    this.canvas.width = Math.floor(this.width * dpr);
    this.canvas.height = Math.floor(this.height * dpr);
    this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  render() {
    this.resize();
    const ctx = this.ctx;
    const isLight = this.isLight;

    const bgColor = isLight ? "#ffffff" : "#16202c";
    const gridColor = isLight ? "#cbd5e1" : "#334155";
    const axisColor = isLight ? "#64748b" : "#475569";
    const zeroLineColor = isLight ? "#334155" : "#94a3b8";
    const textColor = isLight ? "#1e293b" : "#f8fafc";

    // Clear background
    ctx.fillStyle = bgColor;
    ctx.fillRect(0, 0, this.width, this.height);

    const { left, right, top, bottom } = this.options.padding;
    const plotWidth = this.width - left - right;
    const plotHeight = this.height - top - bottom;

    // Draw Title if available
    if (this.data.title) {
      ctx.fillStyle = textColor;
      ctx.font = "bold 13px -apple-system, sans-serif";
      ctx.textAlign = "center";
      ctx.fillText(this.data.title, left + plotWidth / 2, 20);
    }

    // Grid ticks calculation
    const xTicks = this.calculateTicks(this.bounds.minX, this.bounds.maxX, 8);
    const yTicks = this.calculateTicks(this.bounds.minY, this.bounds.maxY, 6);

    // Draw Grid
    ctx.strokeStyle = gridColor;
    ctx.lineWidth = 1;
    ctx.setLineDash([4, 4]);

    for (const xt of xTicks) {
      const sx = this.toScreenX(xt);
      if (sx >= left && sx <= left + plotWidth) {
        ctx.beginPath();
        ctx.moveTo(sx, top);
        ctx.lineTo(sx, top + plotHeight);
        ctx.stroke();
      }
    }

    for (const yt of yTicks) {
      const sy = this.toScreenY(yt);
      if (sy >= top && sy <= top + plotHeight) {
        ctx.beginPath();
        ctx.moveTo(left, sy);
        ctx.lineTo(left + plotWidth, sy);
        ctx.stroke();
      }
    }

    ctx.setLineDash([]);

    // Draw 0 axes if within bounds
    ctx.strokeStyle = zeroLineColor;
    ctx.lineWidth = 1.5;

    if (this.bounds.minX <= 0 && this.bounds.maxX >= 0) {
      const sx0 = this.toScreenX(0);
      ctx.beginPath();
      ctx.moveTo(sx0, top);
      ctx.lineTo(sx0, top + plotHeight);
      ctx.stroke();
    }

    if (this.bounds.minY <= 0 && this.bounds.maxY >= 0) {
      const sy0 = this.toScreenY(0);
      ctx.beginPath();
      ctx.moveTo(left, sy0);
      ctx.lineTo(left + plotWidth, sy0);
      ctx.stroke();
    }

    // Draw Outer Box Border
    ctx.strokeStyle = axisColor;
    ctx.lineWidth = 1;
    ctx.strokeRect(left, top, plotWidth, plotHeight);

    // Tick labels
    ctx.fillStyle = textColor;
    ctx.font = "10px -apple-system, sans-serif";

    // X-axis ticks
    ctx.textAlign = "center";
    for (const xt of xTicks) {
      const sx = this.toScreenX(xt);
      if (sx >= left && sx <= left + plotWidth) {
        ctx.fillText(this.formatNumber(xt), sx, top + plotHeight + 16);
      }
    }

    // Y-axis ticks
    ctx.textAlign = "right";
    for (const yt of yTicks) {
      const sy = this.toScreenY(yt);
      if (sy >= top && sy <= top + plotHeight) {
        ctx.fillText(this.formatNumber(yt), left - 6, sy + 3);
      }
    }

    // Axis Labels
    ctx.font = "italic 11px 'Times New Roman', serif";
    ctx.textAlign = "center";
    ctx.fillText(this.data.x_label || "x", left + plotWidth / 2, this.height - 8);

    ctx.save();
    ctx.translate(14, top + plotHeight / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.fillText(this.data.y_label || "y", 0, 0);
    ctx.restore();

    // Clip rendering to plot area
    ctx.save();
    ctx.beginPath();
    ctx.rect(left, top, plotWidth, plotHeight);
    ctx.clip();

    // Render Regions (Inequalities)
    if (this.data.regions) {
      for (const reg of this.data.regions) {
        if (!reg.x || !reg.y_min || !reg.y_max || reg.x.length === 0) continue;
        ctx.fillStyle = reg.color || (isLight ? "rgba(37, 99, 235, 0.2)" : "rgba(56, 189, 248, 0.25)");
        ctx.beginPath();

        // Top edge
        let first = true;
        for (let i = 0; i < reg.x.length; i++) {
          const sx = this.toScreenX(reg.x[i]);
          const sy = this.toScreenY(reg.y_max[i]);
          if (first) {
            ctx.moveTo(sx, sy);
            first = false;
          } else {
            ctx.lineTo(sx, sy);
          }
        }

        // Bottom edge backwards
        for (let i = reg.x.length - 1; i >= 0; i--) {
          const sx = this.toScreenX(reg.x[i]);
          const sy = this.toScreenY(reg.y_min[i]);
          ctx.lineTo(sx, sy);
        }

        ctx.closePath();
        ctx.fill();
      }
    }

    // Render Curves
    if (this.data.curves) {
      for (let cIdx = 0; cIdx < this.data.curves.length; cIdx++) {
        const curve = this.data.curves[cIdx];
        if (!curve.x || !curve.y || curve.x.length === 0) continue;

        const curveColor = curve.color || this.colors[cIdx % this.colors.length];
        ctx.strokeStyle = curveColor;
        ctx.lineWidth = 2;

        ctx.beginPath();
        let isDrawing = false;

        for (let i = 0; i < curve.x.length; i++) {
          const x = curve.x[i];
          const y = curve.y[i];

          if (!isFinite(x) || !isFinite(y) || isNaN(x) || isNaN(y)) {
            isDrawing = false;
            continue;
          }

          const sx = this.toScreenX(x);
          const sy = this.toScreenY(y);

          if (!isDrawing) {
            ctx.moveTo(sx, sy);
            isDrawing = true;
          } else {
            ctx.lineTo(sx, sy);
          }
        }
        ctx.stroke();
      }
    }

    ctx.restore();

    // Render Legend if multiple curves exist or labeled
    const labeled = (this.data.curves || []).filter(c => c.label && c.label.trim() !== "");
    if (labeled.length > 0) {
      let legendX = left + plotWidth - 10;
      let legendY = top + 15;
      ctx.font = "10px -apple-system, sans-serif";

      for (let i = 0; i < labeled.length; i++) {
        const c = labeled[i];
        const color = c.color || this.colors[i % this.colors.length];

        ctx.textAlign = "right";
        ctx.fillStyle = textColor;
        ctx.fillText(c.label, legendX, legendY);

        ctx.strokeStyle = color;
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(legendX - ctx.measureText(c.label).width - 18, legendY - 3);
        ctx.lineTo(legendX - ctx.measureText(c.label).width - 4, legendY - 3);
        ctx.stroke();

        legendY += 16;
      }
    }
  }

  calculateTicks(min, max, count) {
    const span = max - min;
    const step = Math.pow(10, Math.floor(Math.log10(span / count)));
    const possibleSteps = [step, step * 2, step * 5, step * 10];
    let bestStep = possibleSteps[0];
    let minDiff = Infinity;

    for (const s of possibleSteps) {
      const diff = Math.abs(span / s - count);
      if (diff < minDiff) {
        minDiff = diff;
        bestStep = s;
      }
    }

    const firstTick = Math.ceil(min / bestStep) * bestStep;
    const ticks = [];
    for (let t = firstTick; t <= max; t += bestStep) {
      ticks.push(t);
    }
    return ticks;
  }

  formatNumber(val) {
    if (Math.abs(val) < 1e-9) return "0";
    if (Math.abs(val) >= 10000 || Math.abs(val) < 0.01) {
      return val.toExponential(1);
    }
    return parseFloat(val.toFixed(2)).toString();
  }

  initEvents() {
    let isPanning = false;
    let startX = 0, startY = 0;
    let initialBounds = null;

    this.canvas.addEventListener("mousedown", (e) => {
      isPanning = true;
      startX = e.clientX;
      startY = e.clientY;
      initialBounds = { ...this.bounds };
      this.canvas.style.cursor = "grabbing";
    });

    window.addEventListener("mousemove", (e) => {
      if (!isPanning || !initialBounds) return;
      const dx = e.clientX - startX;
      const dy = e.clientY - startY;

      const { left, right, top, bottom } = this.options.padding;
      const plotWidth = this.width - left - right;
      const plotHeight = this.height - top - bottom;

      const xSpan = initialBounds.maxX - initialBounds.minX;
      const ySpan = initialBounds.maxY - initialBounds.minY;

      const mathDx = -(dx / plotWidth) * xSpan;
      const mathDy = (dy / plotHeight) * ySpan;

      this.bounds.minX = initialBounds.minX + mathDx;
      this.bounds.maxX = initialBounds.maxX + mathDx;
      this.bounds.minY = initialBounds.minY + mathDy;
      this.bounds.maxY = initialBounds.maxY + mathDy;

      this.render();
    });

    window.addEventListener("mouseup", () => {
      if (isPanning) {
        isPanning = false;
        this.canvas.style.cursor = "default";
      }
    });

    // Zoom on wheel
    this.canvas.addEventListener("wheel", (e) => {
      e.preventDefault();
      const zoomFactor = e.deltaY < 0 ? 0.9 : 1.1;

      const rect = this.canvas.getBoundingClientRect();
      const mouseX = e.clientX - rect.left;
      const mouseY = e.clientY - rect.top;

      const centerMathX = this.toMathX(mouseX);
      const centerMathY = this.toMathY(mouseY);

      this.bounds.minX = centerMathX + (this.bounds.minX - centerMathX) * zoomFactor;
      this.bounds.maxX = centerMathX + (this.bounds.maxX - centerMathX) * zoomFactor;
      this.bounds.minY = centerMathY + (this.bounds.minY - centerMathY) * zoomFactor;
      this.bounds.maxY = centerMathY + (this.bounds.maxY - centerMathY) * zoomFactor;

      this.render();
    }, { passive: false });
  }
}
