// Procedural locations. Every room is assembled from the same primitives so the
// whole episode shares one construction language: true horizontals, thin dark
// mullions, one practical light, and something left empty for the eye to fill.
import * as THREE from "../vendor/three.module.min.js";
import {
  rng, mat, glow, box, plane, cylinder, room, doorFrame, windowFrame,
  lightShaft, dust, fogVolume,
} from "./util.js";

const T = (hex) => hex;

// spec.light is either a number or a block like { flicker: 0.1, intensity: 20 }.
// Passing the block straight into a light made every intensity NaN and killed the room.
function keyIntensity(spec, fallback) {
  const value = spec.light;
  if (typeof value === "number") return value;
  if (value && typeof value === "object" && typeof value.intensity === "number") return value.intensity;
  return fallback;
}

function practical(color, intensity = 12, distance = 12, shadow = true) {
  const light = new THREE.PointLight(new THREE.Color(color), intensity, distance, 2);
  light.castShadow = shadow;
  light.shadow.mapSize.set(1024, 1024);
  light.shadow.bias = -0.0012;
  light.shadow.camera.near = 0.1;
  light.shadow.camera.far = distance;
  return light;
}

function lampBulb(color = "#FFD9A0", radius = 0.05) {
  return new THREE.Mesh(new THREE.SphereGeometry(radius, 14, 12), glow(color, 2.6));
}

function chair(P, x, z, rot = 0) {
  const group = new THREE.Group();
  const wood = mat("#3A2B2C", { roughness: 0.95 });
  group.add(box(0.44, 0.05, 0.44, wood, 0, 0.45, 0));
  group.add(box(0.44, 0.55, 0.05, wood, 0, 0.72, -0.2));
  for (const [dx, dz] of [[-0.18, -0.18], [0.18, -0.18], [-0.18, 0.18], [0.18, 0.18]]) {
    group.add(box(0.05, 0.45, 0.05, wood, dx, 0.225, dz));
  }
  group.position.set(x, 0, z);
  group.rotation.y = rot;
  return group;
}

function table(P, x, z, w = 1.1, d = 0.7, h = 0.75) {
  const group = new THREE.Group();
  const wood = mat("#4A3630", { roughness: 0.95 });
  group.add(box(w, 0.05, d, wood, 0, h, 0));
  for (const [dx, dz] of [[-w / 2 + 0.06, -d / 2 + 0.06], [w / 2 - 0.06, -d / 2 + 0.06], [-w / 2 + 0.06, d / 2 - 0.06], [w / 2 - 0.06, d / 2 - 0.06]]) {
    group.add(box(0.06, h, 0.06, wood, dx, h / 2, dz));
  }
  group.position.set(x, 0, z);
  return group;
}

function shelfBooks(P, x, y, z, width = 1.2, seed = 3) {
  const random = rng(seed);
  const group = new THREE.Group();
  const colors = ["#6E4B3A", "#7C9270", "#8C5A46", "#3E4A52", "#A5734A"];
  let cursor = -width / 2;
  while (cursor < width / 2 - 0.06) {
    const w = 0.03 + random() * 0.04;
    const h = 0.16 + random() * 0.1;
    const book = box(w, h, 0.16, mat(colors[Math.floor(random() * colors.length)], { roughness: 1 }), cursor + w / 2, y + h / 2, 0);
    book.rotation.z = random() < 0.12 ? 0.12 : 0;
    group.add(book);
    cursor += w + 0.006;
  }
  group.position.set(x, 0, z);
  return group;
}

function plant(P, x, z, scale = 1) {
  const group = new THREE.Group();
  group.add(cylinder(0.13 * scale, 0.1 * scale, 0.24 * scale, mat("#8A5A44"), 0, 0.12 * scale, 0));
  const random = rng(19);
  for (let i = 0; i < 7; i++) {
    const leaf = new THREE.Mesh(new THREE.SphereGeometry(0.13 * scale, 10, 8), mat(P.sage, { roughness: 1 }));
    leaf.scale.set(0.42, 1, 0.22);
    leaf.position.set((random() - 0.5) * 0.3 * scale, (0.3 + random() * 0.35) * scale, (random() - 0.5) * 0.3 * scale);
    leaf.rotation.set((random() - 0.5) * 0.7, random() * 3, (random() - 0.5) * 0.7);
    leaf.castShadow = true;
    group.add(leaf);
  }
  group.position.set(x, 0, z);
  return group;
}

function windowLight(group, color, position, target, intensity = 2.4, angle = 0.5) {
  const light = new THREE.SpotLight(new THREE.Color(color), intensity, 16, angle, 0.85, 1.6);
  light.position.set(...position);
  light.target.position.set(...target);
  light.castShadow = true;
  light.shadow.mapSize.set(1024, 1024);
  light.shadow.bias = -0.0008;
  light.shadow.normalBias = 0.03;
  // A spot with the default 0.5 to 500 range burns its whole depth buffer on empty
  // air, which is what turned the far wall into a black slab.
  light.shadow.camera.near = 0.3;
  light.shadow.camera.far = 16;
  group.add(light);
  group.add(light.target);
  return light;
}

function openDoorGap(P, x, z, rot, height = 2.05, width = 0.95, gap = 0.18) {
  const group = new THREE.Group();
  const doorMat = mat("#2A2026", { roughness: 0.95 });
  const slab = box(width, height, 0.05, doorMat, width / 2 + gap / 2, height / 2, 0);
  group.add(slab);
  const gapPlane = new THREE.Mesh(
    new THREE.PlaneGeometry(gap, height * 0.97),
    new THREE.MeshBasicMaterial({ color: new THREE.Color("#D8A96A"), transparent: true, opacity: 0.55 }),
  );
  gapPlane.position.set(gap / 2, height * 0.485, -0.03);
  group.add(gapPlane);
  const spill = new THREE.Mesh(
    new THREE.PlaneGeometry(0.34, 1.1),
    new THREE.MeshBasicMaterial({ color: new THREE.Color("#E8B570"), transparent: true, opacity: 0.06, blending: THREE.AdditiveBlending, depthWrite: false }),
  );
  spill.rotation.x = -Math.PI / 2;
  spill.position.set(gap * 0.9, 0.012, 0.65);
  group.add(spill);
  group.position.set(x, 0, z);
  group.rotation.y = rot;
  return group;
}

function figureInDoorway(P, x, z, rot, opts = {}) {
  const group = new THREE.Group();
  const doorway = new THREE.Mesh(
    new THREE.PlaneGeometry(1.05, 2.1),
    new THREE.MeshBasicMaterial({ color: new THREE.Color("#C79A62"), transparent: true, opacity: 0.22, blending: THREE.AdditiveBlending, depthWrite: false }),
  );
  doorway.position.set(0, 1.05, -0.02);
  group.add(doorway);
  group.position.set(x, 0, z);
  group.rotation.y = rot;
  group.userData.doorway = doorway;
  return group;
}

function stairBlock(P, steps = 9, width = 1.05, rise = 0.19, run = 0.26) {
  const group = new THREE.Group();
  const material = mat("#4C3C38", { roughness: 1 });
  for (let i = 0; i < steps; i++) {
    group.add(box(width, rise, run, material, 0, rise / 2 + i * rise, -i * run));
  }
  return group;
}

export const LOCATIONS = {
  hallway(spec, ctx) {
    const P = ctx.palette;
    const random = rng(ctx.seed);
    const w = 2.35;
    const d = spec.depth ?? 11;
    const h = 2.65;
    const group = new THREE.Group();
    const openings = [
      { side: "back", x: 0.42, y: 0, w: 1.02, h: 2.1 },
      { side: "left", x: -1.4, y: 0, w: 0.95, h: 2.05 },
      { side: "right", x: 1.6, y: 0, w: 0.95, h: 2.05 },
    ];
    group.add(room({ w, d, h, wall: P.wall, floor: P.shadow, ceiling: "#1B1418", openings }));
    group.userData.bounds = { w, d, h };
    group.add(plane(w - 0.1, d - 0.1, mat("#3A3034", { roughness: 1 }), 0, 0.002, 0));

    // Skirting and ceiling trim: thin dark lines are what make a corridor read as built.
    for (const side of [-1, 1]) {
      group.add(box(0.05, 0.13, d, mat("#1B1418"), side * (w / 2 - 0.03), 0.065, 0));
      group.add(box(0.04, 0.03, d, mat("#1B1418"), side * (w / 2 - 0.03), h - 0.02, 0));
    }

    for (const side of [-1, 1]) {
      const frame = doorFrame(0.95, 2.05, "#1E171C");
      frame.rotation.y = side > 0 ? -Math.PI / 2 : Math.PI / 2;
      frame.position.set(side * (w / 2 - 0.06), 0, side > 0 ? 1.6 : -1.4);
      group.add(frame);
      const dark = plane(0.92, 2.02, mat("#120E12", { roughness: 1 }), side * (w / 2 - 0.02), 1.01, side > 0 ? 1.6 : -1.4, 0);
      dark.rotation.y = side > 0 ? -Math.PI / 2 : Math.PI / 2;
      group.add(dark);
    }

    const back = doorFrame(1.02, 2.1, "#1E171C");
    back.position.set(0.42, 0, -d / 2 + 0.06);
    group.add(back);
    group.add(openDoorGap(P, 0.42, -d / 2 + 0.1, 0, 2.05, 0.98, spec.gap ?? 0.16));

    // One bulb every couple of metres. Two bulbs in an eleven metre corridor left the
    // near end black, which reads as a broken render rather than a dark hallway.
    const bulbCount = Math.max(3, Math.round(d / 2.6));
    for (let i = 0; i < bulbCount; i++) {
      const z = d / 2 - 0.9 - (i * (d - 1.8)) / (bulbCount - 1);
      const bulb = new THREE.Group();
      bulb.add(box(0.02, 0.24, 0.02, mat("#1B1418"), 0, h - 0.12, z));
      const glass = lampBulb("#FFD9A0", 0.055);
      glass.position.y = h - 0.26;
      bulb.add(glass);
      group.add(bulb);
      const light = practical(
        "#E3A94E",
        keyIntensity(spec, 15),
        9,
        i === Math.floor(bulbCount / 2),
      );
      light.position.set(0, h - 0.3, z);
      group.add(light);
    }

    group.add(new THREE.HemisphereLight(new THREE.Color("#4A5468"), new THREE.Color("#120E12"), 0.34));

    const motes = dust(90, { x: w * 0.8, y: h, z: d * 0.8 }, ctx.seed);
    group.add(motes);
    group.userData.motes = motes;
    group.userData.camera = { pos: [0.05, 1.55, d / 2 - 0.9], target: [0, 1.45, -d / 2 + 0.6] };
    return group;
  },

  bedroom(spec, ctx) {
    const P = ctx.palette;
    const w = 4.2;
    const d = 4.4;
    const h = 2.6;
    const group = new THREE.Group();
    group.add(room({
      w, d, h, wall: P.wall, floor: P.shadow, ceiling: "#1B1418",
      openings: [{ side: "right", x: 0.4, y: 0.95, w: 1.25, h: 1.15 }],
    }));
    group.userData.bounds = { w, d, h };

    const bedFrame = box(1.5, 0.34, 2.05, mat("#4A3630"), -0.9, 0.2, 0.35);
    group.add(bedFrame);
    group.add(box(1.44, 0.18, 1.95, mat("#8E8074", { roughness: 1 }), -0.9, 0.46, 0.35));
    group.add(box(1.3, 0.1, 1.2, mat("#6B5852", { roughness: 1 }), -0.9, 0.58, 0.72));
    group.add(box(1.5, 0.75, 0.08, mat("#3A2B2C"), -0.9, 0.5, -0.72));
    group.add(box(0.52, 0.14, 0.32, mat("#C9BCA8", { roughness: 1 }), -1.05, 0.6, -0.42));

    const wardrobe = box(0.62, 2.1, 1.3, mat("#3A2B2C"), -w / 2 + 0.35, 1.05, 1.1);
    group.add(wardrobe);
    group.add(box(0.02, 2.0, 0.02, mat("#120E12"), -w / 2 + 0.67, 1.05, 1.1));

    const win = windowFrame(1.25, 1.15, "#1B1418", 1);
    win.rotation.y = -Math.PI / 2;
    win.position.set(w / 2 - 0.05, 0.95, 0.4);
    group.add(win);
    const night = new THREE.Mesh(
      new THREE.PlaneGeometry(1.25, 1.15),
      new THREE.MeshBasicMaterial({ color: new THREE.Color("#2C2A46") }),
    );
    night.rotation.y = -Math.PI / 2;
    night.position.set(w / 2 + 0.02, 1.52, 0.4);
    group.add(night);

    windowLight(group, "#8FA0C8", [w / 2 + 0.6, 1.9, 0.4], [-0.6, 0.6, 0.2], keyIntensity(spec, 3.2), 0.62);
    const shaft = lightShaft("#9FB0D8", 1.6, 2.4, 0.07);
    shaft.rotation.y = -Math.PI / 2;
    shaft.position.set(w / 2 - 0.4, 1.4, 0.2);
    group.add(shaft);

    const lampBase = cylinder(0.12, 0.14, 0.28, mat("#8A5A44"), 0.55, 0.14, -1.35);
    group.add(lampBase);
    const shade = new THREE.Mesh(new THREE.CylinderGeometry(0.16, 0.22, 0.24, 16, 1, true), glow("#F2C079", 0.8));
    shade.position.set(0.55, 0.4, -1.35);
    group.add(shade);
    const lamp = practical("#F2C079", spec.lamp ?? 8, 6);
    lamp.position.set(0.55, 0.4, -1.35);
    group.add(lamp);

    group.add(new THREE.HemisphereLight(new THREE.Color("#6B5852"), new THREE.Color("#0E0A0E"), 0.28));
    const motes = dust(60, { x: w, y: h, z: d }, ctx.seed + 3);
    group.add(motes);
    group.userData.motes = motes;
    group.userData.camera = { pos: [1.85, 1.5, 0.15], target: [-0.85, 1.02, 0.5] };
    return group;
  },

  kitchen(spec, ctx) {
    const P = ctx.palette;
    const w = 4.4;
    const d = 3.8;
    const h = 2.55;
    const group = new THREE.Group();
    group.add(room({
      w, d, h, wall: P.wall, floor: "#4A3B36", ceiling: "#1B1418",
      openings: [{ side: "back", x: 0.9, y: 1.1, w: 1.3, h: 1.0 }],
    }));
    group.userData.bounds = { w, d, h };

    const counterMat = mat("#5C4A42", { roughness: 0.95 });
    group.add(box(w * 0.8, 0.9, 0.62, counterMat, -0.4, 0.45, -d / 2 + 0.34));
    group.add(box(w * 0.8, 0.06, 0.66, mat("#8A7A6A", { roughness: 0.8 }), -0.4, 0.92, -d / 2 + 0.34));
    for (let i = 0; i < 5; i++) {
      group.add(box(0.6, 0.7, 0.02, mat("#3A2B2C"), -1.7 + i * 0.66, 0.5, -d / 2 + 0.66));
    }
    group.add(box(w * 0.8, 0.7, 0.34, mat("#4A3A34"), -0.4, 1.95, -d / 2 + 0.2));
    group.add(box(0.62, 0.02, 0.52, mat("#B9B0A2"), 0.9, 0.96, -d / 2 + 0.36));

    const win = windowFrame(1.3, 1.0, "#1B1418", 1);
    win.position.set(0.9, 1.1, -d / 2 + 0.04);
    group.add(win);
    const sky = new THREE.Mesh(
      new THREE.PlaneGeometry(1.3, 1.0),
      new THREE.MeshBasicMaterial({ color: new THREE.Color("#1B2230") }),
    );
    sky.position.set(0.9, 1.6, -d / 2 - 0.03);
    group.add(sky);

    group.add(table(P, 0.1, 0.5, 1.2, 0.8, 0.76));
    group.add(chair(P, -0.5, 0.5, Math.PI / 2));
    group.add(chair(P, 0.7, 0.5, -Math.PI / 2));
    group.add(plant(P, -w / 2 + 0.4, d / 2 - 0.6, 1.1));
    const fridge = box(0.68, 1.75, 0.66, mat("#8E8A82", { roughness: 0.55, metalness: 0.15 }), w / 2 - 0.4, 0.88, -d / 2 + 0.36);
    group.add(fridge);
    group.add(box(0.02, 0.9, 0.02, mat("#3A3634"), w / 2 - 0.72, 1.25, -d / 2 + 0.36));
    group.add(box(0.42, 0.03, 0.22, mat("#4A3630"), w / 2 - 0.42, 1.36, d / 2 - 0.3));
    group.add(box(0.42, 0.03, 0.22, mat("#4A3630"), w / 2 - 0.42, 1.58, d / 2 - 0.3));

    const pendant = lampBulb("#FFD9A0", 0.06);
    pendant.position.set(0.1, h - 0.62, 0.4);
    group.add(pendant);
    group.add(box(0.015, 0.6, 0.015, mat("#1B1418"), 0.1, h - 0.31, 0.4));
    const key = practical("#FFD09A", keyIntensity(spec, 15), 10);
    key.position.set(0.1, h - 0.62, 0.4);
    group.add(key);
    group.add(new THREE.HemisphereLight(new THREE.Color("#7C6A5C"), new THREE.Color("#0E0A0E"), 0.3));

    const motes = dust(50, { x: w, y: h, z: d }, ctx.seed + 5);
    group.add(motes);
    group.userData.motes = motes;
    group.userData.camera = { pos: [-1.55, 1.62, 1.5], target: [0.65, 1.02, -1.35] };
    return group;
  },

  living(spec, ctx) {
    const P = ctx.palette;
    const w = 5.2;
    const d = 4.8;
    const h = 2.7;
    const group = new THREE.Group();
    group.add(room({
      w, d, h, wall: P.wall, floor: P.shadow, ceiling: "#1B1418",
      openings: [{ side: "back", x: -1.2, y: 0.9, w: 1.7, h: 1.35 }],
    }));
    group.userData.bounds = { w, d, h };

    const sofaMat = mat("#4E5A50", { roughness: 1 });
    group.add(box(2.1, 0.42, 0.85, sofaMat, -0.6, 0.25, 1.3));
    group.add(box(2.1, 0.55, 0.18, sofaMat, -0.6, 0.55, 1.66));
    group.add(box(0.18, 0.6, 0.85, sofaMat, -1.55, 0.42, 1.3));
    group.add(box(0.18, 0.6, 0.85, sofaMat, 0.35, 0.42, 1.3));

    group.add(box(1.05, 0.05, 0.6, mat("#4A3630"), -0.6, 0.42, 0.55));
    group.add(box(1.05, 0.34, 0.05, mat("#4A3630"), -0.6, 0.24, 0.55));

    const tv = box(1.15, 0.66, 0.05, mat("#0C0C0E", { roughness: 0.4 }), -0.6, 1.25, -d / 2 + 0.1);
    group.add(tv);
    const screen = new THREE.Mesh(
      new THREE.PlaneGeometry(1.05, 0.58),
      new THREE.MeshBasicMaterial({ color: new THREE.Color("#0A0D12") }),
    );
    screen.position.set(-0.6, 1.25, -d / 2 + 0.13);
    group.add(screen);

    const win = windowFrame(1.7, 1.35, "#1B1418", 2);
    win.position.set(-1.2, 0.9, -d / 2 + 0.04);
    group.add(win);
    const night = new THREE.Mesh(new THREE.PlaneGeometry(1.7, 1.35), new THREE.MeshBasicMaterial({ color: new THREE.Color("#20223A") }));
    night.position.set(-1.2, 1.575, -d / 2 - 0.02);
    group.add(night);
    windowLight(group, "#8C9CC4", [-1.2, 2.0, -d / 2 + 1.4], [-0.8, 0.4, 0.6], keyIntensity(spec, 2.6), 0.6);

    const floorLamp = new THREE.Group();
    floorLamp.add(cylinder(0.16, 0.18, 0.03, mat("#2A2026"), 0, 0.015, 0));
    floorLamp.add(cylinder(0.02, 0.02, 1.45, mat("#2A2026"), 0, 0.73, 0));
    const shade = new THREE.Mesh(new THREE.CylinderGeometry(0.18, 0.26, 0.28, 18, 1, true), glow("#EFBE78", 0.7));
    shade.position.y = 1.5;
    floorLamp.add(shade);
    floorLamp.position.set(1.75, 0, -1.1);
    group.add(floorLamp);
    const key = practical("#EFBE78", spec.lamp ?? 10, 8);
    key.position.set(1.75, 1.5, -1.1);
    group.add(key);

    group.add(shelfBooks(P, w / 2 - 0.12, 0.9, -0.2, 1.1, ctx.seed));
    group.add(new THREE.HemisphereLight(new THREE.Color("#6B5852"), new THREE.Color("#0E0A0E"), 0.26));

    const motes = dust(60, { x: w, y: h, z: d }, ctx.seed + 7);
    group.add(motes);
    group.userData.motes = motes;
    group.userData.camera = { pos: [1.95, 1.66, 1.95], target: [-1.05, 1.0, -1.45] };
    return group;
  },

  bathroom(spec, ctx) {
    const P = ctx.palette;
    const w = 2.6;
    const d = 3.2;
    const h = 2.45;
    const group = new THREE.Group();
    group.add(room({ w, d, h, wall: "#5E5A56", floor: "#3A3A3C", ceiling: "#1B1418" }));
    group.userData.bounds = { w, d, h };

    const tile = mat("#6E6A64", { roughness: 0.7 });
    for (let i = 0; i < 10; i++) {
      group.add(box(0.001, h, 0.002, mat("#4A4644"), -w / 2 + (i * w) / 10, h / 2, -d / 2 + 0.01));
    }
    group.add(box(w, 0.9, 0.02, tile, 0, 0.45, -d / 2 + 0.012));

    group.add(box(0.9, 0.12, 0.5, mat("#B7B0A6", { roughness: 0.5 }), -0.4, 0.86, -d / 2 + 0.3));
    group.add(box(0.12, 0.22, 0.14, mat("#9A948A"), -0.4, 0.98, -d / 2 + 0.18));
    const mirror = new THREE.Mesh(
      new THREE.PlaneGeometry(0.72, 0.9),
      new THREE.MeshStandardMaterial({ color: 0x1c2024, roughness: 0.15, metalness: 0.85 }),
    );
    mirror.position.set(-0.4, 1.55, -d / 2 + 0.03);
    group.add(mirror);

    group.add(box(1.6, 0.55, 0.72, mat("#CFC9BE", { roughness: 0.6 }), 0.3, 0.28, 0.9));
    group.add(box(1.5, 0.35, 0.62, mat("#B8B2A8", { roughness: 0.7 }), 0.3, 0.5, 0.9));

    const bulb = lampBulb("#F5D8AE", 0.05);
    bulb.position.set(0, h - 0.18, 0);
    group.add(bulb);
    const key = practical("#F5D8AE", keyIntensity(spec, 11), 7);
    key.position.set(0, h - 0.2, 0);
    group.add(key);
    group.add(new THREE.HemisphereLight(new THREE.Color("#7A726A"), new THREE.Color("#0C0A0C"), 0.3));

    const motes = dust(30, { x: w, y: h, z: d }, ctx.seed + 11);
    group.add(motes);
    group.userData.motes = motes;
    group.userData.camera = { pos: [0.62, 1.62, 1.3], target: [-0.42, 1.35, -1.35] };
    return group;
  },

  basement(spec, ctx) {
    const P = ctx.palette;
    const w = 4.6;
    const d = 5.2;
    const h = 2.3;
    const group = new THREE.Group();
    group.add(room({ w, d, h, wall: "#4A4440", floor: "#2E2A28", ceiling: "#161214" }));
    group.userData.bounds = { w, d, h };

    for (let i = 0; i < 4; i++) {
      const pipe = cylinder(0.055, 0.055, d, mat("#3E3A38", { metalness: 0.4, roughness: 0.7 }), -w / 2 + 0.3, h - 0.22 - i * 0.1, 0);
      pipe.rotation.x = Math.PI / 2;
      group.add(pipe);
    }
    group.add(stairBlock(P, 7, 1.0, 0.19, 0.27).translateX(w / 2 - 0.7).translateZ(d / 2 - 1.9));

    const random = rng(ctx.seed + 2);
    for (let i = 0; i < 7; i++) {
      const s = 0.35 + random() * 0.3;
      group.add(box(s, s * 0.8, s, mat("#6B5B48", { roughness: 1 }), (random() - 0.5) * 3.4, s * 0.4, (random() - 0.5) * 3.4));
    }

    const wire = box(0.01, 0.5, 0.01, mat("#1B1418"), 0, h - 0.25, -0.3);
    group.add(wire);
    const bulb = lampBulb("#FFD8A2", 0.055);
    bulb.position.set(0, h - 0.52, -0.3);
    group.add(bulb);
    const key = practical("#FFD8A2", keyIntensity(spec, 12), 9);
    key.position.set(0, h - 0.52, -0.3);
    group.add(key);
    group.add(new THREE.HemisphereLight(new THREE.Color("#4A4440"), new THREE.Color("#080608"), 0.22));

    const motes = dust(70, { x: w, y: h, z: d }, ctx.seed + 13);
    group.add(motes);
    group.userData.motes = motes;
    group.userData.camera = { pos: [0.6, 1.5, d / 2 - 0.7], target: [0, 1.1, -1.2] };
    return group;
  },

  attic(spec, ctx) {
    const P = ctx.palette;
    const w = 5.4;
    const d = 4.6;
    const h = 2.9;
    const group = new THREE.Group();
    group.add(room({ w, d, h, wall: "#4E423A", floor: "#3A302A", ceiling: "#171214" }));
    group.userData.bounds = { w, d, h };

    for (let i = 0; i < 5; i++) {
      const beam = box(w, 0.12, 0.1, mat("#3A2B22", { roughness: 1 }), 0, h - 0.12, -d / 2 + 0.6 + i * 0.95);
      group.add(beam);
    }
    for (const side of [-1, 1]) {
      group.add(box(0.1, h * 0.8, d, mat("#3A2B22"), side * (w / 2 - 0.3), h * 0.5, 0));
    }

    const random = rng(ctx.seed + 4);
    for (let i = 0; i < 9; i++) {
      const s = 0.3 + random() * 0.25;
      const b = box(s, s * 0.7, s, mat("#7A6248", { roughness: 1 }), (random() - 0.5) * 4, s * 0.35, (random() - 0.5) * 3.2);
      b.rotation.y = random() * 0.6;
      group.add(b);
    }

    const win = windowFrame(0.7, 0.7, "#241C22", 0);
    win.position.set(w / 2 - 0.04, 1.3, -0.6);
    win.rotation.y = -Math.PI / 2;
    group.add(win);
    const sky = new THREE.Mesh(new THREE.PlaneGeometry(0.7, 0.7), new THREE.MeshBasicMaterial({ color: new THREE.Color("#2A2A44") }));
    sky.rotation.y = -Math.PI / 2;
    sky.position.set(w / 2 + 0.03, 1.65, -0.6);
    group.add(sky);
    windowLight(group, "#8E9CC0", [w / 2 + 0.4, 1.9, -0.6], [-0.6, 0.5, 0.2], keyIntensity(spec, 2.4), 0.7);

    group.add(new THREE.HemisphereLight(new THREE.Color("#5A4A3E"), new THREE.Color("#0A0808"), 0.25));
    const motes = dust(120, { x: w, y: h, z: d }, ctx.seed + 17);
    group.add(motes);
    group.userData.motes = motes;
    group.userData.camera = { pos: [1.4, 1.55, 2.0], target: [-0.8, 1.1, -0.9] };
    return group;
  },

  stairwell(spec, ctx) {
    const P = ctx.palette;
    const w = 2.9;
    const d = 4.6;
    const h = 5.2;
    const group = new THREE.Group();
    group.add(room({ w, d, h, wall: P.wall, floor: P.shadow, ceiling: "#161214" }));
    group.userData.bounds = { w, d, h };

    const lower = stairBlock(P, 8, 1.2, 0.19, 0.27);
    lower.position.set(0, 0, d / 2 - 0.4);
    group.add(lower);
    const upper = stairBlock(P, 8, 1.2, 0.19, 0.27);
    upper.rotation.y = Math.PI;
    upper.position.set(0, 1.52, -d / 2 + 0.4);
    group.add(upper);

    for (let i = 0; i < 9; i++) {
      group.add(box(0.04, 0.9, 0.04, mat("#1B1418"), -0.62, 0.45 + i * 0.19, d / 2 - 0.4 - i * 0.27));
    }
    const rail = box(0.06, 0.05, 2.2, mat("#2A2026"), -0.62, 1.85, d / 2 - 1.5);
    rail.rotation.x = 0.62;
    group.add(rail);

    const sconce = lampBulb("#FFD39A", 0.05);
    sconce.position.set(-w / 2 + 0.12, 2.3, 0.2);
    group.add(sconce);
    const key = practical("#FFD39A", keyIntensity(spec, 13), 9);
    key.position.set(-w / 2 + 0.25, 2.3, 0.2);
    group.add(key);
    group.add(new THREE.HemisphereLight(new THREE.Color("#5E4E48"), new THREE.Color("#0A0808"), 0.24));

    const motes = dust(70, { x: w, y: h, z: d }, ctx.seed + 19);
    group.add(motes);
    group.userData.motes = motes;
    group.userData.camera = { pos: [0.5, 1.5, d / 2 - 0.5], target: [-0.2, 2.2, -d / 2 + 0.6] };
    return group;
  },

  forest(spec, ctx) {
    const P = ctx.palette;
    const group = new THREE.Group();
    const ground = plane(60, 60, mat("#2A2620", { roughness: 1 }), 0, 0, 0);
    group.add(ground);

    const random = rng(ctx.seed + 6);
    const trunkMat = mat("#241E1A", { roughness: 1 });
    for (let i = 0; i < 46; i++) {
      const angle = random() * Math.PI * 2;
      const radius = 2.5 + random() * 22;
      const height = 5 + random() * 6;
      const trunk = cylinder(0.08 + random() * 0.06, 0.16 + random() * 0.1, height, trunkMat,
        Math.cos(angle) * radius, height / 2, Math.sin(angle) * radius - 4);
      trunk.rotation.z = (random() - 0.5) * 0.08;
      group.add(trunk);
      for (let b = 0; b < 3; b++) {
        const length = 1.1 + random() * 1.6;
        const branch = cylinder(0.03, 0.06, length, trunkMat, 0, 0, 0);
        branch.position.set(0, height * (0.45 + b * 0.16), 0);
        branch.rotation.z = (random() < 0.5 ? -1 : 1) * (0.7 + random() * 0.5);
        branch.rotation.y = random() * Math.PI * 2;
        branch.position.y -= length * 0.35;
        trunk.add(branch);
      }
    }

    const moon = new THREE.DirectionalLight(new THREE.Color("#9FB0D8"), keyIntensity(spec, 1.1));
    moon.position.set(-6, 12, -8);
    moon.castShadow = true;
    moon.shadow.mapSize.set(1024, 1024);
    moon.shadow.camera.left = -12;
    moon.shadow.camera.right = 12;
    moon.shadow.camera.top = 12;
    moon.shadow.camera.bottom = -12;
    moon.shadow.bias = -0.002;
    group.add(moon);
    group.add(new THREE.HemisphereLight(new THREE.Color("#3A4258"), new THREE.Color("#0A0808"), 0.9));

    for (let i = 0; i < 5; i++) {
      const shaft = lightShaft("#9FB0D8", 1.4 + random() * 1.2, 7, 0.05);
      shaft.position.set(-4 + i * 2.2, 3.4, -6 - random() * 4);
      shaft.rotation.z = 0.22;
      group.add(shaft);
    }

    const haze = fogVolume("#5A6480", 14, 0.05);
    haze.position.set(0, 1.2, -6);
    group.add(haze);
    const motes = dust(140, { x: 18, y: 5, z: 18 }, ctx.seed + 23);
    group.add(motes);
    group.userData.motes = motes;
    group.userData.camera = { pos: [0, 1.6, 4.5], target: [0, 1.5, -6] };
    return group;
  },

  road(spec, ctx) {
    const P = ctx.palette;
    const group = new THREE.Group();
    group.add(plane(80, 80, mat("#22201F", { roughness: 1 }), 0, 0, 0));
    const asphalt = plane(8, 90, mat("#2C2A29", { roughness: 0.98 }), 0, 0.01, -20);
    group.add(asphalt);
    for (let i = 0; i < 14; i++) {
      group.add(plane(0.16, 2.4, mat("#B8A87E", { roughness: 1 }), 0, 0.02, 4 - i * 6));
    }
    for (const side of [-1, 1]) {
      group.add(box(0.12, 0.06, 90, mat("#4A4640"), side * 4.1, 0.03, -20));
      for (let i = 0; i < 5; i++) {
        const pole = cylinder(0.06, 0.09, 6.4, mat("#3A3634", { metalness: 0.3 }), side * 4.9, 3.2, 2 - i * 12);
        group.add(pole);
        const arm = box(1.1, 0.06, 0.06, mat("#3A3634"), side * 4.35, 6.3, 2 - i * 12);
        group.add(arm);
        const head = new THREE.Mesh(new THREE.SphereGeometry(0.14, 12, 10), glow("#FFCE8A", 2.2));
        head.position.set(side * 3.9, 6.2, 2 - i * 12);
        group.add(head);
      }
    }
    const random = rng(ctx.seed + 8);
    for (let i = 0; i < 26; i++) {
      const h = 4 + random() * 5;
      const tree = new THREE.Mesh(new THREE.ConeGeometry(1.1 + random(), h, 7), mat("#181614", { roughness: 1 }));
      tree.position.set((random() < 0.5 ? -1 : 1) * (9 + random() * 12), h / 2, 4 - random() * 60);
      group.add(tree);
    }
    const key = practical("#FFCE8A", keyIntensity(spec, 26), 22);
    key.position.set(-3.9, 6.2, -10);
    group.add(key);
    group.add(new THREE.HemisphereLight(new THREE.Color("#2A2C3A"), new THREE.Color("#080708"), 0.45));
    const haze = fogVolume("#4A4A5A", 18, 0.045);
    haze.position.set(0, 2, -18);
    group.add(haze);
    group.userData.camera = { pos: [1.2, 1.6, 6], target: [0, 1.4, -14] };
    return group;
  },

  field(spec, ctx) {
    const group = new THREE.Group();
    group.add(plane(120, 120, mat("#2A2A22", { roughness: 1 }), 0, 0, 0));
    const random = rng(ctx.seed + 10);
    const grass = new THREE.InstancedMesh(new THREE.ConeGeometry(0.05, 0.5, 4), mat("#33321F", { roughness: 1 }), 900);
    const dummy = new THREE.Object3D();
    for (let i = 0; i < 900; i++) {
      dummy.position.set((random() - 0.5) * 60, 0.25, (random() - 0.5) * 60 - 8);
      dummy.rotation.y = random() * 3;
      dummy.scale.setScalar(0.6 + random() * 0.9);
      dummy.updateMatrix();
      grass.setMatrixAt(i, dummy.matrix);
    }
    group.add(grass);

    const moon = new THREE.Mesh(new THREE.SphereGeometry(2.2, 24, 18), glow("#D8D2C4", 1.1));
    moon.position.set(-14, 16, -52);
    group.add(moon);
    const halo = new THREE.Mesh(new THREE.SphereGeometry(4.6, 20, 16), new THREE.MeshBasicMaterial({
      color: new THREE.Color("#8C8AA0"), transparent: true, opacity: 0.14, blending: THREE.AdditiveBlending, depthWrite: false,
    }));
    halo.position.copy(moon.position);
    group.add(halo);

    const key = new THREE.DirectionalLight(new THREE.Color("#A8B2CE"), keyIntensity(spec, 0.9));
    key.position.set(-10, 14, -20);
    group.add(key);
    group.add(new THREE.HemisphereLight(new THREE.Color("#2E3448"), new THREE.Color("#0A0A08"), 0.5));

    for (let i = 0; i < 7; i++) {
      const tree = new THREE.Mesh(new THREE.ConeGeometry(2 + random() * 2, 7 + random() * 4, 6), mat("#141614", { roughness: 1 }));
      tree.position.set(-30 + i * 9 + random() * 4, 4, -34 - random() * 8);
      group.add(tree);
    }
    const haze = fogVolume("#48506A", 26, 0.05);
    haze.position.set(0, 3, -30);
    group.add(haze);
    group.userData.camera = { pos: [0, 1.6, 6], target: [0, 2.2, -30] };
    return group;
  },

  void(spec, ctx) {
    const P = ctx.palette;
    const group = new THREE.Group();
    group.add(plane(40, 40, mat("#0A0A0C", { roughness: 1 }), 0, 0, 0));
    const wall = plane(40, 16, mat("#08080A", { roughness: 1 }), 0, 8, -12, 0);
    group.add(wall);

    const haze = fogVolume(P.amber, 7, 0.03);
    haze.position.set(0, 1.9, -7);
    group.add(haze);
    const floorGlow = lightShaft(P.amber, 5, 3.2, 0.05);
    floorGlow.position.set(0, 1.2, -6.5);
    group.add(floorGlow);
    const key = practical(P.amber, keyIntensity(spec, 8), 16);
    key.position.set(0, 2.2, -5);
    group.add(key);
    group.add(new THREE.HemisphereLight(new THREE.Color("#2A2430"), new THREE.Color("#050506"), 0.3));
    const motes = dust(90, { x: 14, y: 6, z: 14 }, ctx.seed + 29);
    group.add(motes);
    group.userData.motes = motes;
    group.userData.camera = { pos: [0, 1.55, 5], target: [0, 1.4, -4] };
    return group;
  },

  object(spec, ctx) {
    const P = ctx.palette;
    const group = new THREE.Group();
    group.add(plane(12, 12, mat("#1A1518", { roughness: 1 }), 0, 0, 0));
    const backdrop = plane(12, 8, mat("#120E12", { roughness: 1 }), 0, 4, -3.2, 0);
    group.add(backdrop);

    const item = spec.item || "phone";
    const surface = box(1.6, 0.08, 1.0, mat("#4A3630", { roughness: 0.9 }), 0, 0.72, 0);
    group.add(surface);
    for (const [dx, dz] of [[-0.7, -0.4], [0.7, -0.4], [-0.7, 0.4], [0.7, 0.4]]) {
      group.add(box(0.07, 0.72, 0.07, mat("#3A2B2C"), dx, 0.36, dz));
    }

    if (item === "phone") {
      group.add(box(0.16, 0.008, 0.32, mat("#0C0C10", { roughness: 0.3 }), -0.15, 0.765, 0.05));
      const screen = new THREE.Mesh(new THREE.PlaneGeometry(0.14, 0.29), glow("#B9C8D8", 0.55));
      screen.rotation.x = -Math.PI / 2;
      screen.position.set(-0.15, 0.772, 0.05);
      group.add(screen);
    } else if (item === "key") {
      group.add(box(0.03, 0.008, 0.16, mat("#8A8272", { metalness: 0.7, roughness: 0.4 }), 0, 0.765, 0));
      const ring = new THREE.Mesh(new THREE.TorusGeometry(0.035, 0.008, 8, 20), mat("#8A8272", { metalness: 0.7, roughness: 0.4 }));
      ring.rotation.x = -Math.PI / 2;
      ring.position.set(0, 0.765, -0.09);
      group.add(ring);
    } else if (item === "photo") {
      const frame = box(0.26, 0.008, 0.34, mat("#6B5852"), 0, 0.765, 0);
      frame.rotation.y = 0.1;
      group.add(frame);
      const face = new THREE.Mesh(new THREE.PlaneGeometry(0.22, 0.3), mat("#C9BCA8", { roughness: 1 }));
      face.rotation.x = -Math.PI / 2;
      face.rotation.z = 0.1;
      face.position.set(0, 0.772, 0);
      group.add(face);
    } else if (item === "lock") {
      group.add(box(0.14, 0.1, 0.16, mat("#8A8272", { metalness: 0.8, roughness: 0.35 }), 0, 0.82, 0));
      const shackle = new THREE.Mesh(new THREE.TorusGeometry(0.05, 0.012, 8, 18, Math.PI), mat("#8A8272", { metalness: 0.8, roughness: 0.35 }));
      shackle.position.set(0, 0.87, 0);
      group.add(shackle);
    } else {
      group.add(box(0.3, 0.012, 0.42, mat("#3A2B2C", { roughness: 0.9 }), 0, 0.766, 0));
    }

    const key = practical(P.amber, keyIntensity(spec, 7), 6);
    key.position.set(-0.5, 1.5, 0.7);
    group.add(key);
    const rim = new THREE.PointLight(new THREE.Color("#7C8CA8"), 2.2, 5, 2);
    rim.position.set(0.9, 1.2, -1.2);
    group.add(rim);
    group.add(new THREE.HemisphereLight(new THREE.Color("#2E2830"), new THREE.Color("#080608"), 0.35));

    const motes = dust(40, { x: 2, y: 1.6, z: 2 }, ctx.seed + 31);
    group.add(motes);
    group.userData.motes = motes;
    group.userData.camera = { pos: [0.0, 1.02, 0.52], target: [0, 0.78, 0] };
    return group;
  },
};

export const LOCATION_NAMES = Object.keys(LOCATIONS);
