/**
 * OpenMath Web 2D Canvas Plotter
 * High-performance, Retina-aware 2D plotting engine for curves, polar plots, and filled regions.
 */

export class MathPlotter {
  constructor(canvas, plotData, options = {}) {
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d");
    this.data = plotData;
    this.options = {
      theme: options.theme || "dark",
      padding: { top: 40, right: 30, bottom: 45, left: 55 },
      ...options
    };

    this.colors = [
      "#38bdf8", // cyan
      "#f43f5e", // rose
      "#10b981", // emerald
      "#f59e0b", // amber
      "#a855f7", // purple
      "#06b6d4", // sky
      "#ec4899"  // pink
    ];

    this.bounds = this.calculateBounds();
    this.initEvents();
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

    // Add 8% margin
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
    this.height = rect.height || 360;

    this.canvas.width = Math.floor(this.width * dpr);
    this.canvas.height = Math.floor(this.height * dpr);
    this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  render() {
    this.resize();
    const ctx = this.ctx;
    const isDark = this.options.theme === "dark";

    const bgColor = isDark ? "#1e222b" : "#ffffff";
    const gridColor = isDark ? "rgba(255, 255, 255, 0.08)" : "rgba(0, 0, 0, 0.06)";
    const axisColor = isDark ? "rgba(255, 255, 255, 0.3)" : "rgba(0, 0, 0, 0.25)";
    const textColor = isDark ? "#94a3b8" : "#64748b";

    // Clear background
    ctx.fillStyle = bgColor;
    ctx.fillRect(0, 0, this.width, this.height);

    // Draw Grid & Ticks
    this.drawGridAndAxes(ctx, gridColor, axisColor, textColor);

    // Draw Filled Regions
    this.drawRegions(ctx);

    // Draw Curves
    this.drawCurves(ctx);

    // Draw Title & Labels
    this.drawLabels(ctx, isDark ? "#f1f5f9" : "#0f172a", textColor);

    // Draw Legend
    this.drawLegend(ctx, isDark);
  }

  drawGridAndAxes(ctx, gridColor, axisColor, textColor) {
    const { minX, maxX, minY, maxY } = this.bounds;
    const { left, top, right, bottom } = this.options.padding;
    const plotRight = this.width - right;
    const plotBottom = this.height - bottom;

    // Draw Axes if within view
    const zeroX = this.toScreenX(0);
    const zeroY = this.toScreenY(0);

    ctx.strokeStyle = axisColor;
    ctx.lineWidth = 1.5;

    // Y Axis (x = 0)
    if (zeroX >= left && zeroX <= plotRight) {
      ctx.beginPath();
      ctx.moveTo(zeroX, top);
      ctx.lineTo(zeroX, plotBottom);
      ctx.stroke();
    }

    // X Axis (y = 0)
    if (zeroY >= top && zeroY <= plotBottom) {
      ctx.beginPath();
      ctx.moveTo(left, zeroY);
      ctx.lineTo(plotRight, zeroY);
      ctx.stroke();
    }

    // Outer Border
    ctx.strokeStyle = gridColor;
    ctx.lineWidth = 1;
    ctx.strokeRect(left, top, plotRight - left, plotBottom - top);

    // Ticks & Numbers
    const numXTicks = Math.max(4, Math.floor((plotRight - left) / 80));
    const numYTicks = Math.max(4, Math.floor((plotBottom - top) / 50));

    ctx.fillStyle = textColor;
    ctx.font = "11px system-ui, -apple-system, sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "top";

    // X Ticks
    for (let i = 0; i <= numXTicks; i++) {
      const val = minX + (i / numXTicks) * (maxX - minX);
      const sx = this.toScreenX(val);
      if (sx < left || sx > plotRight) continue;

      // Grid line
      ctx.strokeStyle = gridColor;
      ctx.beginPath();
      ctx.moveTo(sx, top);
      ctx.lineTo(sx, plotBottom);
      ctx.stroke();

      // Tick label
      const label = Number(val.toFixed(2)).toString();
      ctx.fillText(label, sx, plotBottom + 8);
    }

    // Y Ticks
    ctx.textAlign = "right";
    ctx.textBaseline = "middle";
    for (let i = 0; i <= numYTicks; i++) {
      const val = minY + (i / numYTicks) * (maxY - minY);
      const sy = this.toScreenY(val);
      if (sy < top || sy > plotBottom) continue;

      ctx.strokeStyle = gridColor;
      ctx.beginPath();
      ctx.moveTo(left, sy);
      ctx.lineTo(plotRight, sy);
      ctx.stroke();

      const label = Number(val.toFixed(2)).toString();
      ctx.fillText(label, left - 8, sy);
    }
  }

  drawRegions(ctx) {
    if (!this.data.regions || !this.data.regions.length) return;
    const { left, top, right, bottom } = this.options.padding;

    ctx.save();
    // Clip to plot area
    ctx.beginPath();
    ctx.rect(left, top, this.width - left - right, this.height - top - bottom);
    ctx.clip();

    for (const reg of this.data.regions) {
      if (!reg.x || !reg.x.length || !reg.y_min || !reg.y_max) continue;
      const alpha = reg.alpha || 0.45;
      ctx.fillStyle = reg.color || `rgba(56, 189, 248, ${alpha})`;

      ctx.beginPath();
      // Forward path along y_max
      for (let i = 0; i < reg.x.length; i++) {
        const sx = this.toScreenX(reg.x[i]);
        const sy = this.toScreenY(reg.y_max[i]);
        if (i === 0) ctx.moveTo(sx, sy);
        else ctx.lineTo(sx, sy);
      }
      // Backward path along y_min
      for (let i = reg.x.length - 1; i >= 0; i--) {
        const sx = this.toScreenX(reg.x[i]);
        const sy = this.toScreenY(reg.y_min[i]);
        ctx.lineTo(sx, sy);
      }
      ctx.closePath();
      ctx.fill();
    }
    ctx.restore();
  }

  drawCurves(ctx) {
    if (!this.data.curves || !this.data.curves.length) return;
    const { left, top, right, bottom } = this.options.padding;

    ctx.save();
    ctx.beginPath();
    ctx.rect(left, top, this.width - left - right, this.height - top - bottom);
    ctx.clip();

    let colorIdx = 0;
    for (const curve of this.data.curves) {
      if (!curve.x || !curve.y || curve.x.length === 0) continue;
      const color = curve.color || this.colors[colorIdx % this.colors.length];
      colorIdx++;

      ctx.strokeStyle = color;
      ctx.lineWidth = 2.5;
      ctx.beginPath();

      let started = false;
      let lastY = null;
      const jumpThreshold = (this.height - top - bottom) * 0.7;

      for (let i = 0; i < curve.x.length; i++) {
        const x = curve.x[i];
        const y = curve.y[i];

        if (!isFinite(x) || !isFinite(y)) {
          started = false;
          continue;
        }

        const sx = this.toScreenX(x);
        const sy = this.toScreenY(y);

        // Detect vertical asymptote jump
        if (lastY !== null && Math.abs(sy - lastY) > jumpThreshold) {
          started = false;
        }

        if (!started) {
          ctx.moveTo(sx, sy);
          started = true;
        } else {
          ctx.lineTo(sx, sy);
        }
        lastY = sy;
      }
      ctx.stroke();
    }
    ctx.restore();
  }

  drawLabels(ctx, titleColor, labelColor) {
    const { left, top, right, bottom } = this.options.padding;

    // Title
    if (this.data.title) {
      ctx.fillStyle = titleColor;
      ctx.font = "bold 13px system-ui, -apple-system, sans-serif";
      ctx.textAlign = "center";
      ctx.textBaseline = "top";
      ctx.fillText(this.data.title, this.width / 2, 10);
    }

    // X Axis Label
    const xLabel = this.data.x_label || "x";
    ctx.fillStyle = labelColor;
    ctx.font = "italic 12px system-ui, -apple-system, sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "bottom";
    ctx.fillText(xLabel, (this.width - left - right) / 2 + left, this.height - 5);

    // Y Axis Label
    const yLabel = this.data.y_label || "y";
    ctx.save();
    ctx.translate(14, (this.height - top - bottom) / 2 + top);
    ctx.rotate(-Math.PI / 2);
    ctx.textAlign = "center";
    ctx.fillText(yLabel, 0, 0);
    ctx.restore();
  }

  drawLegend(ctx, isDark) {
    if (!this.data.curves || this.data.curves.length <= 1) return;
    const validCurves = this.data.curves.filter(c => c.label);
    if (!validCurves.length) return;

    const { right, top } = this.options.padding;
    const legendX = this.width - right - 130;
    const legendY = top + 10;

    ctx.fillStyle = isDark ? "rgba(30, 34, 43, 0.85)" : "rgba(255, 255, 255, 0.85)";
    ctx.strokeStyle = isDark ? "#3a4150" : "#e2e8f0";
    ctx.lineWidth = 1;
    ctx.fillRect(legendX, legendY, 120, validCurves.length * 20 + 8);
    ctx.strokeRect(legendX, legendY, 120, validCurves.length * 20 + 8);

    ctx.font = "11px system-ui, -apple-system, sans-serif";
    ctx.textAlign = "left";
    ctx.textBaseline = "middle";

    validCurves.forEach((curve, i) => {
      const cy = legendY + 12 + i * 20;
      ctx.strokeStyle = curve.color || this.colors[i % this.colors.length];
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(legendX + 8, cy);
      ctx.lineTo(legendX + 24, cy);
      ctx.stroke();

      ctx.fillStyle = isDark ? "#f1f5f9" : "#0f172a";
      ctx.fillText(curve.label, legendX + 30, cy);
    });
  }

  initEvents() {
    window.addEventListener("resize", () => {
      this.render();
    });
  }
}
