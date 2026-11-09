#!/usr/bin/env node
/**
 * Headless driver for the scene runtime.
 *
 * Starts a local static server, launches a browser once, then renders every job in
 * a batch by calling into the page. Frames never touch the disk: the page encodes
 * H.264 through WebCodecs and streams the elementary stream back over HTTP, or in
 * the fallback path streams JPEG frames as one MJPEG file.
 *
 * Usage:
 *   node driver.mjs --jobs jobs.json --out <dir> [--browser <path>] [--font <ttf>]
 *
 * Jobs file: { "width": 1920, "height": 1080, "fps": 30, "settings": {...}, "jobs": [ ... ] }
 * Each job: { "id": "...", "spec": {...}, "duration": 6.4, "start": 0 }
 * Prints one JSON line per event so the Python side can report progress.
 */
import { spawn, spawnSync } from "node:child_process";
import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import os from "node:os";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const args = process.argv.slice(2);
const option = (name, fallback = null) => {
  const index = args.indexOf(`--${name}`);
  return index >= 0 && args[index + 1] ? args[index + 1] : fallback;
};

const jobsFile = option("jobs");
const outDir = option("out");
if (!jobsFile || !outDir) {
  console.error("usage: node driver.mjs --jobs jobs.json --out dir");
  process.exit(2);
}

const batch = JSON.parse(fs.readFileSync(jobsFile, "utf8"));
const width = batch.width || 1920;
const height = batch.height || 1080;
const fps = batch.fps || 30;
const settings = batch.settings || {};
const jobs = batch.jobs || [];
fs.mkdirSync(outDir, { recursive: true });

const log = (payload) => process.stdout.write(`${JSON.stringify(payload)}\n`);

// ---------------------------------------------------------------- browser

function findBrowser() {
  const explicit = option("browser") || process.env.RULE_HORROR_BROWSER;
  if (explicit && fs.existsSync(explicit)) return explicit;
  const candidates = [
    "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
    "C:/Program Files/Microsoft/Edge/Application/msedge.exe",
    "C:/Program Files/Google/Chrome/Application/chrome.exe",
    "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  ];
  const local = process.env.LOCALAPPDATA;
  if (local) {
    candidates.push(path.join(local, "Google/Chrome/Application/chrome.exe"));
    const playwright = path.join(local, "ms-playwright");
    if (fs.existsSync(playwright)) {
      for (const entry of fs.readdirSync(playwright)) {
        if (!entry.startsWith("chromium")) continue;
        candidates.push(path.join(playwright, entry, "chrome-win", "chrome.exe"));
        candidates.push(path.join(playwright, entry, "chrome-linux", "chrome"));
      }
    }
  }
  return candidates.find((candidate) => fs.existsSync(candidate)) || null;
}

// ---------------------------------------------------------------- server

let currentStream = null;

const MIME = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".mjs": "text/javascript; charset=utf-8",
  ".json": "application/json",
  ".ttf": "font/ttf",
  ".otf": "font/otf",
  ".woff2": "font/woff2",
};

const server = http.createServer((req, res) => {
  const url = new URL(req.url, "http://127.0.0.1");
  if (req.method === "POST" && url.pathname === "/chunk") {
    const parts = [];
    req.on("data", (part) => parts.push(part));
    req.on("end", () => {
      const buffer = Buffer.concat(parts);
      if (process.env.RH_DEBUG) log({ event: "chunk", bytes: buffer.byteLength, stream: !!currentStream });
      if (currentStream) fs.appendFileSync(currentStream, buffer);
      res.writeHead(204).end();
    });
    return;
  }
  if (req.method === "POST" && url.pathname === "/jpeg") {
    const parts = [];
    req.on("data", (part) => parts.push(part));
    req.on("end", () => {
      const body = Buffer.concat(parts).toString();
      if (currentStream) fs.appendFileSync(currentStream, Buffer.from(body, "base64"));
      res.writeHead(204).end();
    });
    return;
  }
  if (url.pathname === "/health") {
    res.writeHead(200, { "content-type": "application/json" });
    res.end(JSON.stringify({ ok: true }));
    return;
  }
  if (url.pathname === "/font") {
    const fontFile = option("font");
    if (!fontFile || !fs.existsSync(fontFile)) { res.writeHead(404).end(); return; }
    res.writeHead(200, { "content-type": MIME[path.extname(fontFile)] || "font/ttf" });
    fs.createReadStream(fontFile).pipe(res);
    return;
  }
  const relative = url.pathname === "/" ? "index.html" : url.pathname.slice(1);
  const target = path.join(here, relative);
  if (!target.startsWith(here)) { res.writeHead(403).end(); return; }
  fs.readFile(target, (error, data) => {
    if (error) { res.writeHead(404).end("not found"); return; }
    res.writeHead(200, { "content-type": MIME[path.extname(target)] || "application/octet-stream" });
    res.end(data);
  });
});

await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
const port = server.address().port;

// ---------------------------------------------------------------- cdp

class Cdp {
  constructor(socket) {
    this.socket = socket;
    this.id = 0;
    this.pending = new Map();
    socket.addEventListener("message", (event) => {
      const message = JSON.parse(event.data);
      if (message.id && this.pending.has(message.id)) {
        this.pending.get(message.id)(message);
        this.pending.delete(message.id);
      }
    });
  }
  send(method, params = {}, sessionId) {
    return new Promise((resolve) => {
      const id = ++this.id;
      this.pending.set(id, resolve);
      this.socket.send(JSON.stringify({ id, method, params, sessionId }));
    });
  }
}

const browserPath = findBrowser();
if (!browserPath) {
  log({ event: "error", message: "no browser found; set RULE_HORROR_BROWSER" });
  process.exit(3);
}
log({ event: "browser", path: browserPath });

const debugPort = 9500 + Math.floor(Math.random() * 400);
const profile = fs.mkdtempSync(path.join(os.tmpdir(), "rule-horror-"));
const browser = spawn(browserPath, [
  "--headless=new",
  `--remote-debugging-port=${debugPort}`,
  `--user-data-dir=${profile}`,
  "--no-first-run",
  "--no-default-browser-check",
  "--disable-extensions",
  "--disable-background-timer-throttling",
  "--disable-renderer-backgrounding",
  "--disable-backgrounding-occluded-windows",
  "--hide-scrollbars",
  "--mute-audio",
  "--autoplay-policy=no-user-gesture-required",
  `--window-size=${width},${height}`,
  "about:blank",
], { stdio: ["ignore", "pipe", "pipe"] });
browser.stderr.on("data", () => {});

let wsUrl = null;
for (let attempt = 0; attempt < 160; attempt++) {
  await new Promise((resolve) => setTimeout(resolve, 100));
  try {
    const response = await fetch(`http://127.0.0.1:${debugPort}/json/version`);
    wsUrl = (await response.json()).webSocketDebuggerUrl;
    if (wsUrl) break;
  } catch { /* browser still starting */ }
}
if (!wsUrl) {
  log({ event: "error", message: "browser did not expose a debugging port" });
  shutdown(4);
}

// The browser spawns a dozen child processes; killing the parent alone leaks them
// and the next run runs out of memory. Always take the tree down.
function shutdown(code = 0) {
  try {
    if (browser && browser.pid) {
      spawnSync("taskkill", ["/pid", String(browser.pid), "/T", "/F"], { stdio: "ignore" });
    }
  } catch { /* already gone */ }
  try { server.close(); } catch { /* already closed */ }
  setTimeout(() => process.exit(code), 80);
}
process.on("SIGINT", () => shutdown(130));
process.on("SIGTERM", () => shutdown(143));
process.on("uncaughtException", (error) => {
  log({ event: "error", message: String(error && error.message ? error.message : error) });
  shutdown(1);
});

const socket = new WebSocket(wsUrl);
await new Promise((resolve) => socket.addEventListener("open", resolve));
const cdp = new Cdp(socket);

const { result: target } = await cdp.send("Target.createTarget", { url: `http://127.0.0.1:${port}/` });
const { result: attached } = await cdp.send("Target.attachToTarget", { targetId: target.targetId, flatten: true });
const sessionId = attached.sessionId;
await cdp.send("Runtime.enable", {}, sessionId);
await cdp.send("Page.enable", {}, sessionId);

async function evaluate(expression, awaitPromise = true) {
  const response = await cdp.send("Runtime.evaluate", {
    expression, awaitPromise, returnByValue: true,
  }, sessionId);
  if (response.result?.exceptionDetails) {
    throw new Error(response.result.exceptionDetails.exception?.description || "page error");
  }
  return response.result?.result?.value;
}

let ready = false;
for (let attempt = 0; attempt < 200; attempt++) {
  await new Promise((resolve) => setTimeout(resolve, 100));
  try {
    ready = await evaluate("window.__ready === true", false);
    if (ready) break;
  } catch { /* still loading */ }
}
if (!ready) {
  log({ event: "error", message: "scene runtime never became ready" });
  shutdown(5);
}

const fontFile = option("font");
if (fontFile && fs.existsSync(fontFile)) {
  await evaluate(`(async () => {
    const face = new FontFace("EpisodeFont", "url(/font)");
    await face.load();
    document.fonts.add(face);
    return true;
  })()`);
  settings.fontFamily = '"EpisodeFont", sans-serif';
}

if (process.env.RH_DEBUG) {
  const probe = await evaluate("window.RH.debugEncode()");
  log({ event: "probe", probe });
}
const capabilities = await evaluate("window.RH.capabilities()");
log({ event: "capabilities", ...capabilities });

// ---------------------------------------------------------------- render

const stillsMode = option("stills");
if (stillsMode) {
  fs.mkdirSync(stillsMode, { recursive: true });
  for (const job of jobs) {
    const payload = {
      spec: { ...job.spec, text: job.text || {} },
      settings, width, height, fps,
      duration: job.duration || 4,
      beatId: job.id,
      startSeconds: job.start || 0,
      time: job.time ?? (job.duration || 4) * 0.5,
    };
    const data = await evaluate(`window.RH.still(${JSON.stringify(payload)})`);
    const file = path.join(stillsMode, `${job.id}.png`);
    fs.writeFileSync(file, Buffer.from(data, "base64"));
    const timing = await evaluate("window.__timing");
    log({ event: "still", id: job.id, file, timing });
  }
  log({ event: "done", beats: jobs.length });
  socket.close();
  shutdown(0);
}

let rendered = 0;
for (const job of jobs) {
  const started = Date.now();
  const frames = Math.max(1, Math.round((job.duration || 4) * fps));
  const streamPath = path.join(outDir, `${job.id}.stream`);
  fs.writeFileSync(streamPath, Buffer.alloc(0));
  currentStream = streamPath;

  const payload = {
    spec: { ...job.spec, text: job.text || {} },
    settings,
    width, height, fps,
    duration: job.duration || 4,
    beatId: job.id,
    startSeconds: job.start || 0,
  };

  const result = await evaluate(`window.RH.renderClip(${JSON.stringify(payload)})`);
  currentStream = null;

  const extension = result.mode === "h264" ? "h264" : "mjpeg";
  const finalPath = path.join(outDir, `${job.id}.${extension}`);
  fs.renameSync(streamPath, finalPath);
  rendered += 1;
  log({
    event: "beat",
    id: job.id,
    frames,
    mode: result.mode,
    codec: result.codec,
    file: finalPath,
    seconds: Number(((Date.now() - started) / 1000).toFixed(2)),
    done: rendered,
    total: jobs.length,
    detail: result,
  });
}

log({ event: "done", beats: rendered });
socket.close();
shutdown(0);
