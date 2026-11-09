// Typography. The browser sets type better than an image pipeline ever did, so the
// HUD, rule cards and captions are drawn here, frame accurate, with no re-encode.
const DEFAULTS = {
  family: '"Segoe UI", "Inter", system-ui, sans-serif',
  captionSize: 50,
  overlaySize: 84,
  hudSize: 21,
};

function fitText(ctx, text, options) {
  const {
    maxWidth, maxLines, startSize, weight = 600, family = DEFAULTS.family, lineGap = 0.22,
  } = options;
  let size = startSize;
  for (let attempt = 0; attempt < 26; attempt++) {
    ctx.font = `${weight} ${size}px ${family}`;
    const lines = wrap(ctx, text, maxWidth);
    if (lines.length <= maxLines) {
      return { size, lines, lineHeight: size * (1 + lineGap), font: ctx.font };
    }
    size *= 0.92;
    if (size < 12) break;
  }
  ctx.font = `${weight} ${size}px ${family}`;
  return { size, lines: wrap(ctx, text, maxWidth).slice(0, maxLines), lineHeight: size * 1.22, font: ctx.font };
}

function wrap(ctx, text, maxWidth) {
  // A rule card is written with deliberate line breaks; keep them.
  const paragraphs = String(text).split(/\n+/);
  const lines = [];
  for (const paragraph of paragraphs) {
    const words = paragraph.split(/\s+/).filter(Boolean);
    let line = "";
    for (const word of words) {
      const candidate = line ? `${line} ${word}` : word;
      if (ctx.measureText(candidate).width <= maxWidth || !line) {
        line = candidate;
      } else {
        lines.push(line);
        line = word;
      }
    }
    if (line) lines.push(line);
  }
  return lines;
}

function keyWords(list) {
  return new Set((list || []).map((word) => String(word).toLowerCase().replace(/[^\w']/g, "")));
}

function drawEmphasisLine(ctx, line, x, y, baseColor, accentColor, emphasis) {
  const words = line.split(" ");
  const space = ctx.measureText(" ").width;
  let cursor = x;
  for (const word of words) {
    const clean = word.toLowerCase().replace(/[^\w']/g, "");
    ctx.fillStyle = emphasis.has(clean) ? accentColor : baseColor;
    ctx.fillText(word, cursor, y);
    cursor += ctx.measureText(word).width + space;
  }
}

/**
 * @param {CanvasRenderingContext2D} ctx
 * @param {object} beat      caption, overlay, overlay_style, accent, section, emphasis
 * @param {object} settings  brand, episode, caption settings, colours
 * @param {object} layout    width, height, startSeconds
 */
export function drawOverlay(ctx, beat, settings, layout) {
  const { width, height, startSeconds = 0 } = layout;
  const scale = height / 1080;
  const family = settings.fontFamily || DEFAULTS.family;
  const colors = settings.colors || {};
  const ivory = colors.ivory || "#F4EAD8";
  const amber = colors.amber || "#E3A94E";
  const red = colors.red || "#D6402F";
  const accent = { ivory, amber, red }[String(beat.accent || "ivory").toLowerCase()] || ivory;
  const captionsOn = settings.captionBand !== false;

  if (captionsOn) {
    const bandTop = height * 0.70;
    const gradient = ctx.createLinearGradient(0, bandTop, 0, height);
    gradient.addColorStop(0, "rgba(4,4,5,0)");
    gradient.addColorStop(1, "rgba(4,4,5,0.62)");
    ctx.fillStyle = gradient;
    ctx.fillRect(0, bandTop, width, height - bandTop);
  }

  const hudText = [settings.brand, settings.episode, beat.section]
    .map((part) => String(part || "").trim())
    .filter(Boolean)
    .join("  •  ");
  const hudSize = Math.max(14, Math.round(DEFAULTS.hudSize * scale));
  ctx.font = `500 ${hudSize}px ${family}`;
  ctx.fillStyle = "rgba(206,202,194,0.82)";
  ctx.textBaseline = "top";
  if (hudText) {
    ctx.fillText(hudText.slice(0, 90), width * 0.035, height * 0.045);
  }
  const timecode = `${String(Math.floor(startSeconds / 60)).padStart(2, "0")}:${String(Math.floor(startSeconds % 60)).padStart(2, "0")}`;
  const timeWidth = ctx.measureText(timecode).width;
  const right = width * 0.965;
  ctx.fillText(timecode, right - timeWidth, height * 0.045);
  ctx.fillStyle = red;
  ctx.beginPath();
  ctx.arc(right - timeWidth - 20 * scale, height * 0.045 + 9 * scale, 4.5 * scale, 0, Math.PI * 2);
  ctx.fill();

  const overlayText = String(beat.overlay || "").trim();
  if (overlayText) {
    const fitted = fitText(ctx, overlayText, {
      maxWidth: width * 0.80,
      maxLines: 3,
      startSize: Math.round(DEFAULTS.overlaySize * scale * 0.88),
      weight: 700,
      family,
      lineGap: 0.18,
    });
    ctx.font = fitted.font;
    ctx.textBaseline = "top";
    const widest = Math.max(...fitted.lines.map((line) => ctx.measureText(line).width));
    const blockHeight = fitted.lines.length * fitted.lineHeight;
    const top = height * 0.12;
    const bandTop = Math.max(0, top - blockHeight * 0.55);
    const bandBottom = Math.min(height, top + blockHeight * 1.45);
    const gradient = ctx.createLinearGradient(0, bandTop, 0, bandBottom);
    gradient.addColorStop(0, "rgba(4,4,6,0)");
    gradient.addColorStop(0.5, "rgba(4,4,6,0.80)");
    gradient.addColorStop(1, "rgba(4,4,6,0)");
    ctx.fillStyle = gradient;
    ctx.fillRect(0, bandTop, width, bandBottom - bandTop);

    if (String(beat.overlay_style || "").toLowerCase() === "card") {
      ctx.strokeStyle = accent;
      ctx.lineWidth = Math.max(1, 2 * scale);
      const left = (width - widest) / 2;
      const rightEdge = (width + widest) / 2;
      ctx.beginPath();
      ctx.moveTo(left, top - 26 * scale);
      ctx.lineTo(rightEdge, top - 26 * scale);
      ctx.moveTo(left, top + blockHeight + 10 * scale);
      ctx.lineTo(rightEdge, top + blockHeight + 10 * scale);
      ctx.stroke();
    }
    ctx.shadowColor = "rgba(0,0,0,0.75)";
    ctx.shadowBlur = 12 * scale;
    ctx.fillStyle = accent;
    ctx.textAlign = "center";
    fitted.lines.forEach((line, index) => {
      ctx.fillText(line, width / 2, top + index * fitted.lineHeight);
    });
    ctx.shadowBlur = 0;
    ctx.textAlign = "left";
  }

  let caption = String(beat.caption || beat.narration || "").trim();
  if (settings.captionUppercase !== false) caption = caption.toUpperCase();
  if (caption) {
    const fitted = fitText(ctx, caption, {
      maxWidth: width * 0.82,
      maxLines: 2,
      startSize: Math.round(DEFAULTS.captionSize * scale),
      weight: 600,
      family,
      lineGap: 0.24,
    });
    ctx.font = fitted.font;
    ctx.textBaseline = "alphabetic";
    const total = fitted.lines.length * fitted.lineHeight;
    const baseline = height * (settings.captionPosition ?? 0.88) - total + fitted.lineHeight * 0.78;
    const emphasis = keyWords(beat.emphasis);
    ctx.shadowColor = "rgba(0,0,0,0.85)";
    ctx.shadowBlur = 10 * scale;
    fitted.lines.forEach((line, index) => {
      const lineWidth = ctx.measureText(line).width;
      const x = (width - lineWidth) / 2;
      const y = baseline + index * fitted.lineHeight;
      if (emphasis.size) drawEmphasisLine(ctx, line, x, y, ivory, accent, emphasis);
      else {
        ctx.fillStyle = ivory;
        ctx.fillText(line, x, y);
      }
    });
    ctx.shadowBlur = 0;
  }
  ctx.textBaseline = "alphabetic";
}
