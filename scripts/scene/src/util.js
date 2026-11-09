// Small deterministic helpers and primitive builders shared by every location.
import * as THREE from "../vendor/three.module.min.js";

export function rng(seed) {
  let a = (seed >>> 0) || 1;
  return function next() {
    a |= 0; a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export const lerp = (a, b, t) => a + (b - a) * t;
export const clamp = (v, a, b) => Math.min(b, Math.max(a, v));

const cache = new Map();

/** Matte material, cached by colour so a location never allocates per instance. */
export function mat(color, opts = {}) {
  const key = `${color}|${JSON.stringify(opts)}`;
  if (cache.has(key)) return cache.get(key);
  const material = new THREE.MeshStandardMaterial({
    color: new THREE.Color(color),
    roughness: opts.roughness ?? 0.92,
    metalness: opts.metalness ?? 0.0,
    emissive: opts.emissive ? new THREE.Color(opts.emissive) : 0x000000,
    emissiveIntensity: opts.emissiveIntensity ?? 0,
    transparent: opts.opacity !== undefined && opts.opacity < 1,
    opacity: opts.opacity ?? 1,
    side: opts.side ?? THREE.FrontSide,
    flatShading: !!opts.flat,
  });
  cache.set(key, material);
  return material;
}

export function glow(color, intensity = 1.6) {
  return mat(color, { emissive: color, emissiveIntensity: intensity, roughness: 1 });
}

export function box(w, h, d, material, x = 0, y = 0, z = 0) {
  const mesh = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), material);
  mesh.position.set(x, y, z);
  mesh.castShadow = true;
  mesh.receiveShadow = true;
  return mesh;
}

export function plane(w, h, material, x = 0, y = 0, z = 0, rx = -Math.PI / 2) {
  const mesh = new THREE.Mesh(new THREE.PlaneGeometry(w, h), material);
  mesh.position.set(x, y, z);
  mesh.rotation.x = rx;
  mesh.receiveShadow = true;
  return mesh;
}

export function cylinder(rTop, rBottom, h, material, x = 0, y = 0, z = 0, segments = 18) {
  const mesh = new THREE.Mesh(new THREE.CylinderGeometry(rTop, rBottom, h, segments), material);
  mesh.position.set(x, y, z);
  mesh.castShadow = true;
  mesh.receiveShadow = true;
  return mesh;
}

/** Flat wall with rectangular holes punched through it, extruded so it has real depth. */
export function wallWithHoles(width, height, holes, material, thickness = 0.12) {
  const shape = new THREE.Shape();
  shape.moveTo(-width / 2, 0);
  shape.lineTo(width / 2, 0);
  shape.lineTo(width / 2, height);
  shape.lineTo(-width / 2, height);
  shape.closePath();
  for (const hole of holes) {
    const path = new THREE.Path();
    const x0 = hole.x - hole.w / 2;
    const x1 = hole.x + hole.w / 2;
    path.moveTo(x0, hole.y);
    path.lineTo(x1, hole.y);
    path.lineTo(x1, hole.y + hole.h);
    path.lineTo(x0, hole.y + hole.h);
    path.closePath();
    shape.holes.push(path);
  }
  const geometry = new THREE.ExtrudeGeometry(shape, { depth: thickness, bevelEnabled: false });
  geometry.translate(0, 0, -thickness / 2);
  const mesh = new THREE.Mesh(geometry, material);
  mesh.castShadow = true;
  mesh.receiveShadow = true;
  return mesh;
}

/**
 * A room shell. `openings` are given per side; each is centred on that wall.
 * Returns the group plus the anchor points the builders place props against.
 */
export function room(opts) {
  const {
    w = 5, d = 6, h = 2.7,
    wall = "#6B5852", floor = "#3A2E30", ceiling = "#221A1E",
    openings = [], ceilingVisible = true,
  } = opts;
  const group = new THREE.Group();
  group.add(plane(w, d, mat(floor, { roughness: 1 }), 0, 0, 0));

  if (ceilingVisible) {
    const cap = plane(w, d, mat(ceiling, { roughness: 1 }), 0, h, 0, Math.PI / 2);
    cap.castShadow = false;
    group.add(cap);
  }

  const sides = [
    { name: "back", pos: [0, 0, -d / 2], rot: 0, span: w },
    { name: "front", pos: [0, 0, d / 2], rot: Math.PI, span: w },
    { name: "left", pos: [-w / 2, 0, 0], rot: Math.PI / 2, span: d },
    { name: "right", pos: [w / 2, 0, 0], rot: -Math.PI / 2, span: d },
  ];
  for (const side of sides) {
    const holes = openings.filter((o) => o.side === side.name);
    const mesh = wallWithHoles(side.span, h, holes, mat(wall, { roughness: 1 }));
    mesh.position.set(...side.pos);
    mesh.rotation.y = side.rot;
    group.add(mesh);
  }
  return group;
}

export function doorFrame(w = 0.95, h = 2.05, color = "#2E2429") {
  const group = new THREE.Group();
  const t = 0.09;
  group.add(box(t, h + t, 0.22, mat(color), -w / 2 - t / 2, (h + t) / 2, 0));
  group.add(box(t, h + t, 0.22, mat(color), w / 2 + t / 2, (h + t) / 2, 0));
  group.add(box(w + t * 2, t, 0.22, mat(color), 0, h + t / 2, 0));
  return group;
}

export function windowFrame(w = 1.2, h = 1.1, color = "#241C22", mullions = 2) {
  const group = new THREE.Group();
  const t = 0.07;
  group.add(box(t, h, 0.16, mat(color), -w / 2, h / 2, 0));
  group.add(box(t, h, 0.16, mat(color), w / 2, h / 2, 0));
  group.add(box(w, t, 0.16, mat(color), 0, h, 0));
  group.add(box(w, t, 0.16, mat(color), 0, 0, 0));
  for (let i = 1; i <= mullions; i++) {
    group.add(box(t * 0.6, h, 0.12, mat(color), -w / 2 + (w * i) / (mullions + 1), h / 2, 0));
  }
  group.add(box(w, t * 0.6, 0.12, mat(color), 0, h * 0.55, 0));
  return group;
}

let shaftTexture = null;

/** Soft edged gradient used by every light shaft, so no quad ever shows an edge. */
function makeShaftTexture() {
  if (shaftTexture) return shaftTexture;
  const canvas = document.createElement("canvas");
  canvas.width = 64;
  canvas.height = 256;
  const ctx = canvas.getContext("2d");
  const horizontal = ctx.createLinearGradient(0, 0, 64, 0);
  horizontal.addColorStop(0, "rgba(255,255,255,0)");
  horizontal.addColorStop(0.5, "rgba(255,255,255,1)");
  horizontal.addColorStop(1, "rgba(255,255,255,0)");
  ctx.fillStyle = horizontal;
  ctx.fillRect(0, 0, 64, 256);
  const vertical = ctx.createLinearGradient(0, 0, 0, 256);
  vertical.addColorStop(0, "rgba(0,0,0,0.85)");
  vertical.addColorStop(0.35, "rgba(0,0,0,0.15)");
  vertical.addColorStop(1, "rgba(0,0,0,0)");
  ctx.globalCompositeOperation = "destination-out";
  ctx.fillStyle = vertical;
  ctx.fillRect(0, 0, 64, 256);
  shaftTexture = new THREE.CanvasTexture(canvas);
  shaftTexture.colorSpace = THREE.SRGBColorSpace;
  return shaftTexture;
}

/** Vertical soft shaft of light, additive, used for windows and door gaps. */
export function lightShaft(color = "#E3A94E", width = 1, height = 2.2, opacity = 0.14) {
  const geometry = new THREE.PlaneGeometry(width, height);
  const material = new THREE.MeshBasicMaterial({
    color: new THREE.Color(color),
    map: makeShaftTexture(),
    transparent: true,
    opacity,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
    side: THREE.DoubleSide,
  });
  const mesh = new THREE.Mesh(geometry, material);
  mesh.userData.baseOpacity = opacity;
  return mesh;
}

export function dust(count, bounds, seed = 7, color = "#F4EAD8") {
  const random = rng(seed);
  const positions = new Float32Array(count * 3);
  const phases = new Float32Array(count);
  for (let i = 0; i < count; i++) {
    positions[i * 3] = (random() - 0.5) * bounds.x;
    positions[i * 3 + 1] = random() * bounds.y;
    positions[i * 3 + 2] = (random() - 0.5) * bounds.z;
    phases[i] = random() * Math.PI * 2;
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  const material = new THREE.PointsMaterial({
    color: new THREE.Color(color),
    size: 0.018,
    sizeAttenuation: true,
    transparent: true,
    opacity: 0.55,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
  });
  const points = new THREE.Points(geometry, material);
  points.userData.phases = phases;
  points.userData.base = positions.slice();
  return points;
}

export function fogVolume(color = "#E3A94E", size = 6, opacity = 0.06) {
  const material = new THREE.MeshBasicMaterial({
    color: new THREE.Color(color),
    transparent: true,
    opacity,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
  });
  const mesh = new THREE.Mesh(new THREE.SphereGeometry(size, 16, 12), material);
  mesh.userData.baseOpacity = opacity;
  return mesh;
}
