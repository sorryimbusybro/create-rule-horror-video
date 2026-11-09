// Runtime: builds one beat's scene, renders it deterministically at a given time,
// composites the type layer, and hands encoded frames to the Node driver.
import * as THREE from "../vendor/three.module.min.js";
import { LOCATIONS } from "./builders.js";
import { buildFigure, updateFigure } from "./figure.js";
import { attachHalos, updateMotes, applyFilmFinish } from "./fx.js";
import { drawOverlay } from "./overlay.js";
import { rng, clamp } from "./util.js";

const PALETTES = {
  "warm-flat": {
    background: "#1B1418", wall: "#6B5852", shadow: "#3A2E30", ink: "#241C22",
    ivory: "#F4EAD8", amber: "#E3A94E", garment: "#E05F38", sage: "#7C9270", red: "#D6402F",
  },
  "noir-line": {
    background: "#050506", wall: "#1A1C1D", shadow: "#0C0D0E", ink: "#0A0B0C",
    ivory: "#E4E1D7", amber: "#BE893E", garment: "#2A2D30", sage: "#5B6160", red: "#BE2D28",
  },
};

const state = {
  renderer: null,
  scene: null,
  camera: null,
  composite: null,
  ctx: null,
  width: 1920,
  height: 1080,
  spec: null,
  settings: {},
  duration: 6,
  fps: 30,
  motes: [],
  figure: null,
  keyLight: null,
  baseExposure: 1.0,
  encoder: null,
  queue: [],
  flushing: false,
  beatId: "",
  mode: "h264",
  framesSent: 0,
};

function makeRenderer(width, height) {
  const renderer = new THREE.WebGLRenderer({
    antialias: true,
    preserveDrawingBuffer: true,
    alpha: false,
    powerPreference: "high-performance",
  });
  renderer.setPixelRatio(1);
  renderer.setSize(width, height, false);
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFShadowMap;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 0.95;
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  return renderer;
}

export function setup(payload) {
  const { spec, settings, width, height, duration, fps, beatId } = payload;
  if (!state.renderer) {
    state.renderer = makeRenderer(width, height);
    document.body.appendChild(state.renderer.domElement);
    const composite = document.createElement("canvas");
    composite.width = width;
    composite.height = height;
    state.composite = composite;
    state.ctx = composite.getContext("2d", { alpha: false });
  }
  state.renderer.setSize(width, height, false);
  state.composite.width = width;
  state.composite.height = height;
  state.width = width;
  state.height = height;
  state.spec = spec;
  state.settings = settings || {};
  state.duration = duration;
  state.fps = fps;
  state.beatId = beatId;
  state.framesSent = 0;
  state.queue = [];

  const palette = PALETTES[settings?.style] || PALETTES["warm-flat"];
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(palette.background);
  const fogDensity = spec.atmosphere?.fog ?? 0.035;
  scene.fog = new THREE.FogExp2(new THREE.Color(palette.background), fogDensity);

  const build = LOCATIONS[spec.place] || LOCATIONS.hallway;
  const seed = spec.seed ?? 1;
  const group = build(spec, { palette, seed });
  scene.add(group);
  state.group = group;
  state.motes = [];
  group.traverse((node) => {
    if (node.isPoints && node.userData.base) state.motes.push(node);
  });
  attachHalos(group, spec.halo ?? 1);

  const anchor = group.userData.camera || { pos: [0, 1.6, 4], target: [0, 1.4, 0] };
  const cameraSpec = spec.camera || {};
  const shot = cameraSpec.shot || "wide";
  const fov = cameraSpec.fov ?? 38;

  // Framing is driven by the subject, not by a fixed distance. Scaling the anchor
  // blindly is what puts a "close" camera inside the character's chest.
  const subject = spec.figure
    ? { x: spec.figure.x ?? 0, y: spec.figure.y ?? 0, z: spec.figure.z ?? 0, height: spec.figure.height ?? 1.68 }
    : { x: anchor.target[0], y: 0, z: anchor.target[2], height: spec.place === "object" ? 0.42 : 2.2 };
  const subjectHeight = subject.height;
  const fraction = cameraSpec.fraction
    ?? ({ wide: 0.30, medium: 0.50, close: 0.74, insert: 0.92 }[shot] ?? 0.30);
  const distance = cameraSpec.distance
    ?? (subjectHeight / fraction) / (2 * Math.tan(THREE.MathUtils.degToRad(fov) / 2));

  const focusY = spec.place === "object" ? 0.5 : shot === "close" ? 0.58 : 0.54;
  // A card occupies the top third, so aim higher and the subject sits lower.
  const cardLift = spec.text && spec.text.overlay ? subjectHeight * 0.16 : 0;
  const target = new THREE.Vector3(subject.x, subject.y + subjectHeight * focusY + cardLift, subject.z);
  const camera = new THREE.PerspectiveCamera(fov, width / height, 0.05, 160);

  if (cameraSpec.pos) {
    camera.position.set(...cameraSpec.pos);
    if (cameraSpec.target) target.set(...cameraSpec.target);
  } else if (!spec.figure) {
    // No character to frame: trust the authored anchor and only change how far back
    // we stand. Pushing in by a fraction of the anchor distance keeps a wide room wide.
    const base = new THREE.Vector3(...anchor.pos);
    const baseTarget = new THREE.Vector3(...anchor.target);
    const scale = { wide: 1.0, medium: 0.78, close: 0.58, insert: 0.42 }[shot] ?? 1.0;
    target.copy(baseTarget);
    camera.position.copy(baseTarget).addScaledVector(base.clone().sub(baseTarget), scale);
    camera.position.y = THREE.MathUtils.lerp(baseTarget.y, base.y, scale);
  } else {
    const direction = new THREE.Vector3(anchor.pos[0] - target.x, 0, anchor.pos[2] - target.z);
    if (direction.lengthSq() < 1e-4) direction.set(0, 0, 1);
    direction.normalize();
    camera.position.copy(target).addScaledVector(direction, distance);
    camera.position.y = target.y + subjectHeight * (cameraSpec.lift ?? 0.18);
    if (spec.place === "object") camera.position.y = target.y + 0.26;
  }
  if (cameraSpec.height !== undefined) camera.position.y = cameraSpec.height;

  // A camera outside the room sees the back of a wall, which renders as a black
  // rectangle. Keep it inside the shell whenever the location has one.
  const bounds = group.userData.bounds;
  if (bounds) {
    camera.position.x = clamp(camera.position.x, -bounds.w / 2 + 0.3, bounds.w / 2 - 0.3);
    camera.position.z = clamp(camera.position.z, -bounds.d / 2 + 0.3, bounds.d / 2 - 0.3);
    camera.position.y = clamp(camera.position.y, 0.5, bounds.h - 0.15);
    // Being shoved inside the room shrinks the distance and blows up the subject.
    // Widen the lens instead so the subject keeps the size the shot asked for.
    if (spec.figure) {
      const actual = camera.position.distanceTo(target);
      if (actual > 0.1 && actual < distance * 0.92) {
        const widened = THREE.MathUtils.radToDeg(
          2 * Math.atan((subjectHeight / fraction) / (2 * actual)),
        );
        camera.fov = clamp(widened, fov, 56);
        camera.updateProjectionMatrix();
      }
    }
  }
  camera.lookAt(target);
  scene.add(camera);

  // A whisper of fill from the camera side. Without it every foreground reads black
  // and the encoder turns the shadow into flat blocks.
  const fillDistance = Math.max(1.5, camera.position.distanceTo(target));
  const fillBase = spec.fill ?? 0.26;
  const fill = new THREE.PointLight(
    new THREE.Color("#C8B49A"),
    THREE.MathUtils.clamp(fillBase * fillDistance * fillDistance, 1.5, 42),
    fillDistance * 2.6,
    2,
  );
  fill.position.copy(camera.position).add(new THREE.Vector3(0, 0.5, 0));
  scene.add(fill);

  state.camera = camera;
  state.scene = scene;
  state.cameraStart = camera.position.clone();
  state.cameraTarget = target.clone();
  state.cameraOffset = camera.position.clone().sub(target);
  state.cameraSpec = cameraSpec;
  state.baseExposure = 0.95;
  state.renderer.toneMappingExposure = state.baseExposure;

  let keyLight = null;
  group.traverse((node) => {
    if ((node.isPointLight || node.isSpotLight) && (!keyLight || node.intensity > keyLight.intensity)) keyLight = node;
  });
  state.keyLight = keyLight;
  state.keyBase = keyLight ? keyLight.intensity : 0;

  if (spec.light?.off && keyLight) keyLight.intensity = 0;
  if (spec.light?.color && keyLight) keyLight.color = new THREE.Color(spec.light.color);

  if (spec.figure) {
    const figure = buildFigure({
      ...spec.figure,
      garment: spec.figure.garment || palette.garment,
      expression: spec.figure.expression || "neutral",
    });
    scene.add(figure);
    state.figure = figure;
    const rim = new THREE.PointLight(new THREE.Color("#8FA2C8"), spec.figure.rim ?? 1.4, 5.5, 2);
    rim.position.set(
      figure.position.x + (spec.figure.rimX ?? 0.8),
      figure.position.y + 2.0,
      figure.position.z - 1.7,
    );
    scene.add(rim);
  } else {
    state.figure = null;
  }

  if (spec.entity) {
    const entity = buildFigure({
      ...spec.entity,
      height: spec.entity.height ?? 2.15,
      silhouette: true,
      expression: "hidden",
      garment: "#08070A",
      skin: "#08070A",
    });
    scene.add(entity);
    state.entity = entity;
  } else {
    state.entity = null;
  }

  state.renderer.render(scene, camera);
  return { place: spec.place, shot, fogDensity };
}

function applyCamera(t) {
  const spec = state.cameraSpec || {};
  const move = spec.move || "static";
  const amount = spec.amount ?? 0.22;
  const progress = state.duration > 0 ? Math.min(1, Math.max(0, t / state.duration)) : 0;
  const camera = state.camera;
  const target = state.cameraTarget;
  const offset = state.cameraOffset;

  let factor = 1;
  let lateral = 0;
  let vertical = 0;
  if (move === "push") factor = 1 - amount * progress;
  else if (move === "pull") factor = 1 + amount * progress;
  else if (move === "drift-left") lateral = -amount * progress;
  else if (move === "drift-right") lateral = amount * progress;
  else if (move === "rise") vertical = amount * 0.5 * progress;
  else if (move === "crane") { vertical = amount * 0.6 * progress; factor = 1 - amount * 0.3 * progress; }

  const position = target.clone().add(offset.clone().multiplyScalar(factor));
  position.x += lateral * offset.length();
  position.y += vertical * offset.length();
  position.y = Math.max(0.35, position.y);

  const shake = spec.handheld ?? 0;
  if (shake > 0) {
    const s = shake * 0.012;
    position.x += Math.sin(t * 1.7 + 0.6) * s + Math.sin(t * 3.1) * s * 0.4;
    position.y += Math.sin(t * 2.3 + 1.4) * s * 0.8;
  }
  camera.position.copy(position);
  camera.lookAt(target);
  if (shake > 0) {
    camera.rotation.z += Math.sin(t * 0.9) * shake * 0.0025;
  }
}

function animateLight(t) {
  const spec = state.spec?.light || {};
  const light = state.keyLight;
  if (!light) return;
  const flicker = spec.flicker ?? 0;
  if (flicker > 0) {
    const n = Math.sin(t * 11.3) * 0.5 + Math.sin(t * 4.1 + 1.2) * 0.3 + Math.sin(t * 27.7) * 0.2;
    light.intensity = Math.max(0, state.keyBase * (1 + n * flicker));
  }
  if (spec.off) light.intensity = 0;
  const pulse = spec.pulse ?? 0;
  if (pulse > 0) light.intensity = state.keyBase * (1 + Math.sin(t * 1.1) * pulse);
}

export function renderAt(t, frame) {
  const { renderer, scene, camera, ctx, width, height } = state;
  applyCamera(t);
  animateLight(t);
  for (const motes of state.motes) updateMotes(motes, t);
  if (state.figure) updateFigure(state.figure, t);
  if (state.entity) updateFigure(state.entity, t);

  renderer.render(scene, camera);
  ctx.globalAlpha = 1;
  ctx.globalCompositeOperation = "source-over";
  const grade = state.settings.grade || {};
  const saturation = grade.saturation ?? 1.04;
  const contrast = grade.contrast ?? 1.05;
  const brightness = grade.brightness ?? 1.0;
  if (saturation !== 1 || contrast !== 1 || brightness !== 1) {
    ctx.filter = `saturate(${saturation}) contrast(${contrast}) brightness(${brightness})`;
  }
  ctx.drawImage(renderer.domElement, 0, 0, width, height);
  ctx.filter = "none";
  applyFilmFinish(ctx, width, height, frame, {
    vignette: state.settings.vignette ?? 0.45,
    grain: state.settings.grain ?? 5,
  });
  drawOverlay(ctx, state.spec?.text || {}, {
    ...state.settings,
    brand: state.settings.brand,
    episode: state.settings.episode,
    captionPosition: state.settings.captionPosition ?? 0.88,
    captionUppercase: state.settings.captionUppercase !== false,
    captionBand: state.settings.captionBand !== false,
  }, { width, height, startSeconds: state.startSeconds || 0 });
}

async function drainQueue() {
  if (state.flushing) return;
  state.flushing = true;
  while (state.queue.length) {
    const batch = state.queue.splice(0, 8);
    let length = 0;
    for (const part of batch) length += part.byteLength;
    const merged = new Uint8Array(length);
    let cursor = 0;
    for (const part of batch) {
      merged.set(part, cursor);
      cursor += part.byteLength;
    }
    await fetch(`/chunk?beat=${encodeURIComponent(state.beatId)}`, { method: "POST", body: merged });
  }
  state.flushing = false;
}

async function createEncoder() {
  if (typeof VideoEncoder === "undefined") return false;
  const width = state.width;
  const height = state.height;
  const bitrate = Math.round(width * height * 0.006);
  // H.264 in Annex B is the only stream the driver can mux without a container.
  // Everything else falls back to JPEG frames, which always work.
  const configs = [
    { codec: "avc1.640028", width, height, bitrate, framerate: state.fps, avc: { format: "annexb" } },
    { codec: "avc1.4D4028", width, height, bitrate, framerate: state.fps, avc: { format: "annexb" } },
    { codec: "avc1.42E028", width, height, bitrate, framerate: state.fps, avc: { format: "annexb" } },
  ];
  for (const config of configs) {
    try {
      const support = await VideoEncoder.isConfigSupported(config);
      if (!support?.supported) continue;
      const chunks = [];
      const encoder = new VideoEncoder({
        output: (chunk) => {
          const buffer = new Uint8Array(chunk.byteLength);
          chunk.copyTo(buffer);
          state.queue.push(buffer);
          state.framesSent += 1;
          drainQueue();
        },
        error: (error) => { window.__encodeError = String(error); },
      });
      encoder.configure(config);
      state.encoder = encoder;
      state.codec = config.codec;
      state.mode = config.codec.startsWith("avc1") ? "h264" : "webm";
      return true;
    } catch (error) {
      window.__encodeError = String(error);
    }
  }
  return false;
}

export async function capabilities() {
  if (typeof VideoEncoder === "undefined") return { h264: false, any: false };
  const probe = async (codec) => {
    try {
      const support = await VideoEncoder.isConfigSupported({ codec, width: 1920, height: 1080, bitrate: 8000000, framerate: 30 });
      return !!support?.supported;
    } catch { return false; }
  };
  const h264 = await probe("avc1.640028");
  const vp9 = await probe("vp09.00.10.08");
  return { h264, vp9, any: h264 || vp9 };
}

export async function renderClip(payload) {
  const { fps, beatId } = payload;
  const frames = Math.max(1, Math.round((payload.duration || 4) * fps));
  setup(payload);
  const ok = await createEncoder();
  state.mode = ok ? state.mode : "jpeg";
  const step = 1 / fps;
  for (let i = 0; i < frames; i++) {
    const t = i * step;
    renderAt(t, i);
    if (ok) {
      const frame = new VideoFrame(state.composite, {
        timestamp: Math.round((i / fps) * 1e6),
        duration: Math.round(1e6 / fps),
      });
      state.encoder.encode(frame, { keyFrame: i % Math.max(1, Math.round(fps * 2)) === 0 });
      frame.close();
      if (state.encoder.encodeQueueSize > 24) {
        await new Promise((resolve) => setTimeout(resolve, 0));
      }
    } else {
      const data = state.composite.toDataURL("image/jpeg", 0.94).split(",")[1];
      await fetch(`/jpeg?beat=${encodeURIComponent(beatId)}&frame=${i}`, { method: "POST", body: data });
    }
  }
  if (ok) {
    await state.encoder.flush();
    state.encoder.close();
    while (state.queue.length || state.flushing) {
      await new Promise((resolve) => setTimeout(resolve, 12));
    }
  }
  return { mode: ok ? state.mode : "jpeg", codec: state.codec || null, frames, error: window.__encodeError || null, sent: state.framesSent };
}

export function still(payload) {
  const t0 = performance.now();
  setup(payload);
  const t1 = performance.now();
  renderAt(payload.time ?? 0, payload.frame ?? 0);
  const t2 = performance.now();
  const data = state.composite.toDataURL("image/png").split(",")[1];
  const t3 = performance.now();
  window.__timing = { setup: Math.round(t1 - t0), render: Math.round(t2 - t1), encode: Math.round(t3 - t2) };
  return data;
}

export function dispose() {
  if (state.scene) {
    state.scene.traverse((node) => {
      if (node.geometry) node.geometry.dispose();
    });
  }
}

window.RH = { setup, renderAt, renderClip, still, capabilities, dispose, state };

window.RH.debugEncode = async () => {
  const report = { steps: [] };
  const canvas = state.composite || document.createElement("canvas");
  canvas.width = 320; canvas.height = 180;
  const ctx = canvas.getContext("2d");
  ctx.fillStyle = "#804020"; ctx.fillRect(0, 0, 320, 180);
  const config = { codec: "avc1.640028", width: 320, height: 180, bitrate: 800000, framerate: 30, avc: { format: "annexb" } };
  report.support = await VideoEncoder.isConfigSupported(config);
  let count = 0;
  let err = null;
  const encoder = new VideoEncoder({
    output: () => { count += 1; },
    error: (e) => { err = String(e); },
  });
  encoder.configure(config);
  for (let i = 0; i < 8; i++) {
    const frame = new VideoFrame(canvas, { timestamp: Math.round((i / 30) * 1e6), duration: 33333 });
    encoder.encode(frame, { keyFrame: i === 0 });
    frame.close();
  }
  report.queued = encoder.encodeQueueSize;
  await encoder.flush();
  report.count = count;
  report.error = err;
  report.state = encoder.state;
  encoder.close();
  return report;
};
window.__ready = true;
