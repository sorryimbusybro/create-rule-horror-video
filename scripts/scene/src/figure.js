// The character. Assembled from filled volumes in head units, never from lines.
// Proportions follow references/visual-system.md: total 3.1 H, head 1.0 H,
// torso 1.15 H, arms 1.1 H, legs 0.95 H. The torso is an extruded silhouette so
// the shoulders and waist actually taper, which is what stops it reading as a cone.
import * as THREE from "../vendor/three.module.min.js";
import { mat } from "./util.js";

const FACE = {
  neutral: { eye: "almond", pupil: 1.0, mouth: "soft" },
  uneasy: { eye: "almond", pupil: 1.0, mouth: "flat", shift: 0.4 },
  wrong: { eye: "almond", pupil: 1.0, mouth: "wide" },
  afraid: { eye: "tall", pupil: 0.5, mouth: "open" },
  absent: { eye: "solid", pupil: 0, mouth: "none" },
  hidden: { eye: "none", pupil: 0, mouth: "none" },
};

function taperedLimb(length, rTop, rBottom, material, segments = 16) {
  const group = new THREE.Group();
  const body = new THREE.Mesh(new THREE.CylinderGeometry(rTop, rBottom, length, segments, 1), material);
  body.position.y = -length / 2;
  body.castShadow = true;
  body.receiveShadow = true;
  group.add(body);
  const capTop = new THREE.Mesh(new THREE.SphereGeometry(rTop, segments, 10), material);
  capTop.castShadow = true;
  group.add(capTop);
  const capBottom = new THREE.Mesh(new THREE.SphereGeometry(rBottom, segments, 10), material);
  capBottom.position.y = -length;
  capBottom.castShadow = true;
  group.add(capBottom);
  return group;
}

function torsoShape(H) {
  const shape = new THREE.Shape();
  const p = (x, y) => [x * H, y * H];
  const [x0, y0] = p(-0.20, 0);
  shape.moveTo(x0, y0);
  let [cx, cy] = p(-0.185, 0.40);
  let [nx, ny] = p(-0.30, 0.92);
  shape.quadraticCurveTo(cx, cy, nx, ny);
  [cx, cy] = p(-0.345, 1.07);
  [nx, ny] = p(-0.26, 1.15);
  shape.quadraticCurveTo(cx, cy, nx, ny);
  shape.lineTo(...p(0.26, 1.15));
  [cx, cy] = p(0.345, 1.07);
  [nx, ny] = p(0.30, 0.92);
  shape.quadraticCurveTo(cx, cy, nx, ny);
  [cx, cy] = p(0.185, 0.40);
  [nx, ny] = p(0.20, 0);
  shape.quadraticCurveTo(cx, cy, nx, ny);
  shape.quadraticCurveTo(0, -0.03 * H, x0, y0);
  return shape;
}

function mouthCurve(width, depth, y) {
  const curve = new THREE.QuadraticBezierCurve3(
    new THREE.Vector3(-width / 2, y, 0),
    new THREE.Vector3(0, y - depth, 0),
    new THREE.Vector3(width / 2, y, 0),
  );
  return curve;
}

/**
 * @param {object} spec garment, skin, height, pose, facing, expression, silhouette
 */
export function buildFigure(spec = {}) {
  const height = spec.height ?? 1.68;
  const H = height / 3.1;
  const garment = spec.garment || "#E05F38";
  // Pale skin by default. A near black head disappears the moment the room is dark,
  // and the character has to stay readable in a black frame.
  const skin = spec.skin || "#F4EDE0";
  const silhouette = !!spec.silhouette;
  const bodyMat = mat(silhouette ? "#0B0A0D" : garment, { roughness: 0.86 });
  const skinMat = mat(silhouette ? "#0B0A0D" : skin, { roughness: 0.78 });
  const legMat = mat(silhouette ? "#0B0A0D" : spec.trousers || "#4A3B52", { roughness: 0.9 });
  const skinHsl = { h: 0, s: 0, l: 0 };
  new THREE.Color(skin).getHSL(skinHsl);
  const skinLuma = skinHsl.l;

  const root = new THREE.Group();
  const body = new THREE.Group();
  body.position.y = 0.95 * H;
  root.add(body);

  const torsoHeight = 1.15 * H;
  const torso = new THREE.Group();
  body.add(torso);

  const torsoMesh = new THREE.Mesh(
    new THREE.ExtrudeGeometry(torsoShape(H), {
      depth: 0.30 * H,
      bevelEnabled: true,
      bevelThickness: 0.05 * H,
      bevelSize: 0.04 * H,
      bevelSegments: 4,
      curveSegments: 12,
    }),
    bodyMat,
  );
  torsoMesh.position.z = -0.15 * H - 0.02 * H;
  torsoMesh.castShadow = true;
  torsoMesh.receiveShadow = true;
  torso.add(torsoMesh);

  // A single seam reads as clothing instead of a solid mass.
  const seam = new THREE.Mesh(
    new THREE.BoxGeometry(0.012 * H, torsoHeight * 0.62, 0.008 * H),
    mat("#000000", { roughness: 1 }),
  );
  seam.position.set(0.10 * H, torsoHeight * 0.42, 0.165 * H);
  torso.add(seam);

  const head = new THREE.Group();
  head.position.y = torsoHeight + 0.40 * H;
  torso.add(head);
  const headMesh = new THREE.Mesh(new THREE.SphereGeometry(0.5 * H, 30, 24), skinMat);
  headMesh.scale.set(1, 0.99, 0.94);
  headMesh.castShadow = true;
  head.add(headMesh);

  const face = FACE[spec.expression] || FACE.neutral;
  const lightSkin = skinLuma > 0.55;
  const inkEye = lightSkin ? "#221A20" : "#F4EAD8";
  if (face.eye !== "none") {
    const eyeW = 0.31 * H;
    const eyeH = face.eye === "tall" ? 0.27 * H : 0.185 * H;
    const eyeMat = mat(inkEye, { emissive: inkEye, emissiveIntensity: lightSkin ? 0.02 : 0.14, roughness: 0.45 });
    for (const side of [-1, 1]) {
      const eye = new THREE.Mesh(new THREE.SphereGeometry(1, 20, 16), eyeMat);
      eye.scale.set(eyeW / 2, eyeH / 2, 0.05 * H);
      eye.position.set(side * 0.185 * H, 0.055 * H, 0.445 * H);
      head.add(eye);
      if (face.pupil > 0) {
        const pupil = new THREE.Mesh(
          new THREE.SphereGeometry(0.085 * H * face.pupil, 16, 12),
          mat(lightSkin ? "#FBF6EC" : "#0E0A0E", { roughness: 0.4 }),
        );
        pupil.scale.z = 0.35;
        pupil.position.set(
          side * 0.185 * H + (face.shift || 0) * 0.05 * H,
          0.07 * H,
          0.482 * H,
        );
        head.add(pupil);
      }
    }
  }

  if (face.mouth !== "none") {
    const mouthMat = mat(lightSkin ? "#2A2028" : "#0E0A0E", { roughness: 0.9 });
    if (face.mouth === "open") {
      const mouth = new THREE.Mesh(new THREE.SphereGeometry(1, 18, 14), mouthMat);
      mouth.scale.set(0.07 * H, 0.085 * H, 0.025 * H);
      mouth.position.set(0, -0.13 * H, 0.452 * H);
      head.add(mouth);
    } else {
      const width = face.mouth === "wide" ? 0.46 * H : 0.30 * H;
      const depth = face.mouth === "wide" ? 0.17 * H : face.mouth === "flat" ? 0.005 * H : 0.09 * H;
      const tube = new THREE.Mesh(
        new THREE.TubeGeometry(mouthCurve(width, depth, -0.10 * H), 16, 0.017 * H, 6, false),
        mouthMat,
      );
      tube.position.z = 0.448 * H;
      head.add(tube);
    }
  }

  const armLength = 1.05 * H;
  const arms = {};
  for (const side of [-1, 1]) {
    const shoulder = new THREE.Group();
    shoulder.position.set(side * 0.375 * H, 1.05 * H, 0);
    const limb = taperedLimb(armLength, 0.105 * H, 0.07 * H, bodyMat);
    shoulder.add(limb);
    const hand = new THREE.Mesh(new THREE.SphereGeometry(0.072 * H, 16, 12), skinMat);
    hand.position.y = -armLength;
    hand.castShadow = true;
    shoulder.add(hand);
    shoulder.rotation.z = side * 0.12;
    torso.add(shoulder);
    arms[side < 0 ? "left" : "right"] = { shoulder, limb, hand };
  }

  const legLength = 0.92 * H;
  const legs = {};
  for (const side of [-1, 1]) {
    const hip = new THREE.Group();
    hip.position.set(side * 0.135 * H, 0, 0);
    const limb = taperedLimb(legLength, 0.105 * H, 0.075 * H, legMat);
    hip.add(limb);
    const shoe = new THREE.Mesh(new THREE.BoxGeometry(0.145 * H, 0.075 * H, 0.27 * H), skinMat);
    shoe.position.set(0, -legLength - 0.02 * H, 0.045 * H);
    shoe.castShadow = true;
    hip.add(shoe);
    body.add(hip);
    legs[side < 0 ? "left" : "right"] = { hip, limb, shoe };
  }

  const poses = {
    stand: () => {},
    "back-turn": () => { head.rotation.y = Math.PI; },
    "head-tilt": () => { head.rotation.z = 0.3; head.rotation.y = 0.12; },
    lean: () => { torso.rotation.x = 0.15; body.rotation.x = 0.08; },
    reach: () => {
      arms.right.shoulder.rotation.x = -1.5;
      arms.right.shoulder.rotation.z = -0.16;
      torso.rotation.x = 0.1;
    },
    sit: () => {
      body.position.y = 0.5 * H;
      for (const side of ["left", "right"]) {
        legs[side].hip.rotation.x = -1.5;
        legs[side].hip.position.z = 0.2 * H;
      }
      arms.left.shoulder.rotation.x = -0.45;
      arms.right.shoulder.rotation.x = -0.45;
    },
    kneel: () => {
      body.position.y = 0.52 * H;
      legs.left.hip.rotation.x = -0.25;
      legs.right.hip.rotation.x = -1.6;
      legs.right.hip.position.z = -0.08 * H;
      torso.rotation.x = 0.12;
    },
    lie: () => {
      root.rotation.x = -Math.PI / 2;
      root.position.y = 0.32;
      body.position.y = 0.15 * H;
      arms.left.shoulder.rotation.x = 0.55;
      arms.right.shoulder.rotation.x = 0.35;
    },
    walk: () => {
      legs.left.hip.rotation.x = 0.4;
      legs.right.hip.rotation.x = -0.4;
      arms.left.shoulder.rotation.x = -0.3;
      arms.right.shoulder.rotation.x = 0.3;
    },
    crouch: () => {
      body.position.y = 0.4 * H;
      legs.left.hip.rotation.x = -1.15;
      legs.right.hip.rotation.x = -1.15;
      torso.rotation.x = 0.32;
    },
    point: () => {
      arms.right.shoulder.rotation.x = -1.62;
      arms.right.shoulder.rotation.z = -0.05;
    },
  };
  (poses[spec.pose] || poses.stand)();

  root.rotation.y = THREE.MathUtils.degToRad(spec.facing ?? 0);
  root.position.set(spec.x ?? 0, spec.y ?? 0, spec.z ?? 0);
  root.userData.joints = { body, torso, head, arms, legs };
  root.userData.sway = spec.sway ?? 0.0;
  root.userData.phase = spec.phase ?? 0;
  root.userData.height = height;
  return root;
}

/** Idle life: a breath and a slow weight shift, never enough to read as animation. */
export function updateFigure(figure, t) {
  const joints = figure.userData.joints;
  if (!joints) return;
  const amp = figure.userData.sway;
  const phase = figure.userData.phase;
  joints.torso.rotation.z = Math.sin(t * 0.55 + phase) * 0.012 * (amp + 0.35);
  joints.head.rotation.z += Math.sin(t * 0.31 + phase) * 0.0035;
  joints.body.position.y += Math.sin(t * 0.9 + phase) * 0.0035 * (amp + 0.2);
}
