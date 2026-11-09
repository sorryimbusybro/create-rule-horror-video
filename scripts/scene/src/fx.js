// Atmosphere and film finish. Bloom is faked with additive halos on the practical
// lights, which is cheap and survives a 4 core laptop; vignette and grain are
// applied once on the composite canvas, so the encoder never sees a filter graph.
import * as THREE from "../vendor/three.module.min.js";

let glowTexture = null;

export function makeGlowTexture() {
  if (glowTexture) return glowTexture;
  const size = 128;
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext("2d");
  const gradient = ctx.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
  gradient.addColorStop(0, "rgba(255,255,255,1)");
  gradient.addColorStop(0.25, "rgba(255,255,255,0.55)");
  gradient.addColorStop(0.55, "rgba(255,255,255,0.16)");
  gradient.addColorStop(1, "rgba(255,255,255,0)");
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, size, size);
  glowTexture = new THREE.CanvasTexture(canvas);
  glowTexture.colorSpace = THREE.SRGBColorSpace;
  return glowTexture;
}

/** Additive halo sprite on every light strong enough to bloom. */
export function attachHalos(group, scale = 1) {
  const lights = [];
  group.traverse((node) => {
    if (node.isPointLight || node.isSpotLight) lights.push(node);
  });
  for (const light of lights) {
    const strength = light.isSpotLight ? light.intensity * 0.5 : light.intensity;
    if (strength < 4) continue;
    const size = THREE.MathUtils.clamp(0.55 * Math.sqrt(strength) * scale, 0.4, 3.4);
    const sprite = new THREE.Sprite(new THREE.SpriteMaterial({
      map: makeGlowTexture(),
      color: light.color.clone(),
      transparent: true,
      opacity: THREE.MathUtils.clamp(0.10 + strength * 0.012, 0.1, 0.5),
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    }));
    sprite.position.copy(light.position);
    if (light.parent) light.parent.add(sprite);
    else group.add(sprite);
    sprite.scale.set(size, size, 1);
  }
}

export function updateMotes(points, t) {
  if (!points) return;
  const positions = points.geometry.getAttribute("position");
  const base = points.userData.base;
  const phases = points.userData.phases;
  if (!base || !phases) return;
  for (let i = 0; i < positions.count; i++) {
    const phase = phases[i];
    positions.array[i * 3] = base[i * 3] + Math.sin(t * 0.22 + phase) * 0.06;
    positions.array[i * 3 + 1] = base[i * 3 + 1] + Math.sin(t * 0.17 + phase * 1.7) * 0.05 + ((t * 0.01) % 0.3);
    positions.array[i * 3 + 2] = base[i * 3 + 2] + Math.cos(t * 0.19 + phase * 0.6) * 0.06;
  }
  positions.needsUpdate = true;
}

const grainCache = new Map();

function grainTile(index, size = 256) {
  const key = `${index}-${size}`;
  if (grainCache.has(key)) return grainCache.get(key);
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext("2d");
  const image = ctx.createImageData(size, size);
  for (let i = 0; i < image.data.length; i += 4) {
    const value = 128 + (Math.random() - 0.5) * 190;
    image.data[i] = value;
    image.data[i + 1] = value;
    image.data[i + 2] = value;
    image.data[i + 3] = 255;
  }
  ctx.putImageData(image, 0, 0);
  grainCache.set(key, canvas);
  return canvas;
}

const vignetteCache = new Map();

function vignettePattern(ctx, width, height, strength) {
  const key = `${width}x${height}-${strength}`;
  if (vignetteCache.has(key)) return vignetteCache.get(key);
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const vctx = canvas.getContext("2d");
  const gradient = vctx.createRadialGradient(
    width / 2, height * 0.48, Math.min(width, height) * 0.18,
    width / 2, height * 0.5, Math.max(width, height) * 0.78,
  );
  gradient.addColorStop(0, "rgba(0,0,0,0)");
  gradient.addColorStop(0.62, `rgba(0,0,0,${0.10 * strength})`);
  gradient.addColorStop(1, `rgba(0,0,0,${0.72 * strength})`);
  vctx.fillStyle = gradient;
  vctx.fillRect(0, 0, width, height);
  vignetteCache.set(key, canvas);
  return canvas;
}

/** Vignette plus per-frame grain, drawn straight onto the composite canvas. */
export function applyFilmFinish(ctx, width, height, frame, settings = {}) {
  const vignette = settings.vignette ?? 0.55;
  const grain = settings.grain ?? 5;
  if (vignette > 0) {
    ctx.save();
    ctx.globalCompositeOperation = "multiply";
    ctx.drawImage(vignettePattern(ctx, width, height, vignette), 0, 0);
    ctx.restore();
  }
  if (grain > 0) {
    // One pattern fill beats thirty five draw calls with a blend mode, and looks the same.
    const tile = grainTile(frame % 4);
    const pattern = ctx.createPattern(tile, "repeat");
    if (pattern) {
      ctx.save();
      ctx.globalCompositeOperation = "overlay";
      ctx.globalAlpha = Math.min(0.09, grain * 0.008);
      ctx.translate(-((frame * 37) % 256), -((frame * 71) % 256));
      ctx.fillStyle = pattern;
      ctx.fillRect(0, 0, width + 256, height + 256);
      ctx.restore();
    }
  }
}
