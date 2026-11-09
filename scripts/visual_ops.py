#!/usr/bin/env python3
"""Procedural scene rendering.

Every frame is drawn by code in a headless browser running three.js. Nothing here
generates an image with a model, so a hundred beats cost nothing but electricity.

The browser draws the scene, the type layer and the film finish, encodes H.264 through
WebCodecs, and streams the elementary stream back to the Node driver, which writes it
to disk. This module turns those streams into normal MP4 clips that the pipeline then
marries to the narration.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCENE_DIR = Path(__file__).resolve().parent / "scene"
DRIVER = SCENE_DIR / "driver.mjs"

PLACES = [
    "hallway", "bedroom", "kitchen", "living", "bathroom", "basement",
    "attic", "stairwell", "forest", "road", "field", "void", "object",
]

SHOTS = ["wide", "medium", "close", "insert"]
MOVES = ["static", "push", "pull", "drift-left", "drift-right", "rise", "crane"]
POSES = ["stand", "sit", "kneel", "lie", "walk", "crouch", "reach", "point", "head-tilt", "back-turn"]
EXPRESSIONS = ["neutral", "uneasy", "wrong", "afraid", "absent", "hidden"]
ITEMS = ["phone", "key", "photo", "lock", "paper"]

CAMERA_ALIASES = {
    "push-in": "push",
    "pull-back": "pull",
    "pan-left": "drift-left",
    "pan-right": "drift-right",
}


class SceneError(RuntimeError):
    pass


# ---------------------------------------------------------------- environment


def node_executable() -> str:
    for candidate in (
        os.environ.get("RULE_HORROR_NODE"),
        shutil.which("node"),
        shutil.which("node.exe"),
        r"C:\Program Files\nodejs\node.exe",
    ):
        if candidate and Path(candidate).is_file():
            return candidate
    raise SceneError(
        "Node.js not found. Install Node 20 or newer, or set RULE_HORROR_NODE to node.exe."
    )


def browser_executable() -> str | None:
    explicit = os.environ.get("RULE_HORROR_BROWSER")
    if explicit and Path(explicit).is_file():
        return explicit
    local = os.environ.get("LOCALAPPDATA", "")
    candidates = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        "/usr/bin/google-chrome",
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    ]
    if local:
        candidates.append(str(Path(local) / "Google/Chrome/Application/chrome.exe"))
        playwright = Path(local) / "ms-playwright"
        if playwright.is_dir():
            for entry in sorted(playwright.iterdir(), reverse=True):
                if not entry.name.startswith("chromium"):
                    continue
                candidates.append(str(entry / "chrome-win" / "chrome.exe"))
                candidates.append(str(entry / "chrome-linux" / "chrome"))
    for candidate in candidates:
        if Path(candidate).is_file():
            return candidate
    return None


def doctor_report() -> dict:
    report = {"node": None, "browser": None, "three": False, "driver": DRIVER.is_file()}
    try:
        report["node"] = node_executable()
    except SceneError:
        pass
    report["browser"] = browser_executable()
    report["three"] = (SCENE_DIR / "vendor" / "three.module.min.js").is_file()
    return report


# ---------------------------------------------------------------- scene specs


def normalise_scene(beat: dict) -> dict:
    """Accept the loose form an author writes and return something the runtime trusts."""
    raw = beat.get("scene") or {}
    if isinstance(raw, str):
        raw = {"place": raw}
    if not isinstance(raw, dict):
        raw = {}
    place = str(raw.get("place") or raw.get("location") or "hallway").strip().lower()
    if place not in PLACES:
        place = "hallway"

    camera = dict(raw.get("camera") or {})
    move = str(camera.get("move") or beat.get("camera") or "static").strip().lower()
    camera["move"] = CAMERA_ALIASES.get(move, move if move in MOVES else "static")
    shot = str(camera.get("shot") or "wide").strip().lower()
    camera["shot"] = shot if shot in SHOTS else "wide"
    if camera.get("amount") is None:
        camera["amount"] = 0.22

    scene = {
        "place": place,
        "seed": int(raw.get("seed") or beat.get("seed") or abs(hash(beat.get("id", "x"))) % 9973),
        "camera": camera,
        "atmosphere": dict(raw.get("atmosphere") or {}),
    }
    if raw.get("depth"):
        scene["depth"] = float(raw["depth"])
    if raw.get("item"):
        scene["item"] = str(raw["item"])
    if raw.get("light"):
        scene["light"] = dict(raw["light"]) if isinstance(raw["light"], dict) else {"intensity": float(raw["light"])}
    if raw.get("fill") is not None:
        scene["fill"] = float(raw["fill"])

    figure = raw.get("figure")
    if isinstance(figure, dict):
        pose = str(figure.get("pose") or "stand").lower()
        expression = str(figure.get("expression") or "neutral").lower()
        scene["figure"] = {
            "pose": pose if pose in POSES else "stand",
            "expression": expression if expression in EXPRESSIONS else "neutral",
            "x": float(figure.get("x", 0) or 0),
            "y": float(figure.get("y", 0) or 0),
            "z": float(figure.get("z", 0) or 0),
            "facing": float(figure.get("facing", 0) or 0),
            "height": float(figure.get("height", 1.68) or 1.68),
        }
        for key in ("garment", "skin", "trousers", "rim", "rimX", "sway"):
            if figure.get(key) is not None:
                scene["figure"][key] = figure[key]
    elif figure:
        scene["figure"] = {"pose": "stand", "expression": "neutral", "x": 0, "y": 0, "z": 0, "facing": 0, "height": 1.68}

    entity = raw.get("entity")
    if isinstance(entity, dict):
        scene["entity"] = {
            "pose": str(entity.get("pose") or "stand"),
            "x": float(entity.get("x", 0) or 0),
            "y": float(entity.get("y", 0) or 0),
            "z": float(entity.get("z", 0) or 0),
            "facing": float(entity.get("facing", 0) or 0),
            "height": float(entity.get("height", 2.15) or 2.15),
        }
    return scene


def driver_settings(data: dict, font: str = "") -> dict:
    settings = data.get("settings", {}) or {}
    style = str(data.get("style") or settings.get("style") or "warm-flat")
    grade = settings.get("grade") or {}
    payload = {
        "style": style,
        "brand": str(settings.get("brand", "") or ""),
        "episode": str(settings.get("episode", "") or ""),
        "captionPosition": float((settings.get("caption") or {}).get("position", 0.88)),
        "captionUppercase": bool((settings.get("caption") or {}).get("uppercase", True)),
        "captionBand": bool((settings.get("caption") or {}).get("band", True)),
        "vignette": float(grade.get("vignette", 0.55)),
        "grain": float(grade.get("grain", 5)),
        "grade": {
            "saturation": float(grade.get("saturation", 1.04)),
            "contrast": float(grade.get("contrast", 1.05)),
            "brightness": float(grade.get("brightness", 1.0)),
        },
    }
    if font:
        payload["fontFamily"] = "EpisodeFont"
    return payload


def beat_text(beat: dict) -> dict:
    return {
        "caption": str(beat.get("caption", "") or ""),
        "narration": str(beat.get("narration", "") or ""),
        "overlay": str(beat.get("overlay", "") or ""),
        "overlay_style": str(beat.get("overlay_style", "") or ""),
        "accent": str(beat.get("accent", "ivory") or "ivory"),
        "section": str(beat.get("section", "") or ""),
        "emphasis": list(beat.get("emphasis") or []),
    }


def signature(data: dict, beat: dict, duration: float, width: int, height: int, fps: int) -> str:
    import hashlib

    payload = {
        "scene": normalise_scene(beat),
        "text": beat_text(beat),
        "duration": round(duration, 3),
        "size": [width, height],
        "fps": fps,
        "style": data.get("style"),
        "settings": {
            key: (data.get("settings", {}) or {}).get(key)
            for key in ("brand", "episode", "grade", "caption", "font")
        },
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


# ---------------------------------------------------------------- driver


def run_driver(jobs: list[dict], out_dir: Path, width: int, height: int, fps: int,
               settings: dict, font: str = "", stills: Path | None = None,
               on_event=None) -> list[dict]:
    out_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as handle:
        json.dump(
            {"width": width, "height": height, "fps": fps, "settings": settings, "jobs": jobs},
            handle,
            ensure_ascii=False,
        )
        jobs_file = handle.name

    command = [node_executable(), str(DRIVER), "--jobs", jobs_file, "--out", str(out_dir)]
    if stills:
        stills.mkdir(parents=True, exist_ok=True)
        command += ["--stills", str(stills)]
    if font:
        command += ["--font", font]
    browser = browser_executable()
    if browser:
        command += ["--browser", browser]

    events: list[dict] = []
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(SCENE_DIR),
    )
    assert process.stdout is not None
    for line in process.stdout:
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        events.append(event)
        if on_event:
            on_event(event)
    stderr = process.stderr.read() if process.stderr else ""
    code = process.wait()
    Path(jobs_file).unlink(missing_ok=True)
    if code != 0:
        message = next((e.get("message") for e in events if e.get("event") == "error"), "")
        detail = message or stderr.strip().splitlines()[-1] if stderr.strip() else message
        raise SceneError(f"scene renderer failed ({code}): {detail}")
    return events


# ---------------------------------------------------------------- clips


def stream_to_clip(ffmpeg: str, stream: Path, target: Path, fps: int) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if stream.suffix == ".h264":
        command = [
            ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
            "-fflags", "+genpts", "-r", str(fps), "-i", str(stream),
            "-c:v", "copy", "-pix_fmt", "yuv420p", str(target),
        ]
    else:
        command = [
            ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
            "-f", "mjpeg", "-framerate", str(fps), "-i", str(stream),
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
            "-pix_fmt", "yuv420p", str(target),
        ]
    subprocess.run(command, check=True, capture_output=True)


def render_clips(
    root: Path,
    data: dict,
    ffmpeg: str,
    durations: list[float],
    width: int,
    height: int,
    fps: int,
    beats: list[dict] | None = None,
    force: bool = False,
    label: str = "final",
    on_event=None,
) -> dict[str, Path]:
    """Render one video clip per beat. Returns beat id to clip path."""
    beats = beats if beats is not None else data["beats"]
    clip_dir = root / "render" / "clips" / label
    stream_dir = root / "render" / "streams" / label
    clip_dir.mkdir(parents=True, exist_ok=True)
    stream_dir.mkdir(parents=True, exist_ok=True)

    settings = data.get("settings", {}) or {}
    font = str(settings.get("font", "") or "")
    font_path = str(asset_path_font(root, font)) if font else ""

    pending: list[dict] = []
    results: dict[str, Path] = {}
    for beat, duration in zip(beats, durations):
        beat_id = beat["id"]
        target = clip_dir / f"{beat_id}.mp4"
        marker = clip_dir / f"{beat_id}.json"
        digest = signature(data, beat, duration, width, height, fps)
        if not force and target.is_file() and marker.is_file():
            try:
                if marker.read_text(encoding="utf-8") == digest:
                    results[beat_id] = target
                    continue
            except OSError:
                pass
        pending.append({
            "id": beat_id,
            "duration": max(0.4, float(duration)),
            "spec": normalise_scene(beat),
            "text": beat_text(beat),
            "digest": digest,
        })

    if pending:
        total = len(pending)
        def report(event):
            if event.get("event") == "beat":
                seconds = event.get("seconds", 0)
                print(
                    f"Scene {event.get('done')}/{total}: {event.get('id')} "
                    f"{event.get('frames')} frames in {seconds}s ({event.get('mode')})",
                    flush=True,
                )
            elif event.get("event") == "error":
                print(f"SCENE ERROR: {event.get('message')}", flush=True)
            if on_event:
                on_event(event)

        run_driver(
            [{"id": job["id"], "duration": job["duration"], "spec": job["spec"], "text": job["text"]} for job in pending],
            stream_dir, width, height, fps,
            driver_settings(data, font_path), font_path,
            on_event=report,
        )
        for job in pending:
            beat_id = job["id"]
            h264 = stream_dir / f"{beat_id}.h264"
            mjpeg = stream_dir / f"{beat_id}.mjpeg"
            stream = h264 if h264.is_file() else mjpeg
            if not stream.is_file() or stream.stat().st_size == 0:
                raise SceneError(f"{beat_id}: renderer produced no video stream")
            target = clip_dir / f"{beat_id}.mp4"
            stream_to_clip(ffmpeg, stream, target, fps)
            (clip_dir / f"{beat_id}.json").write_text(job["digest"], encoding="utf-8")
            results[beat_id] = target
            stream.unlink(missing_ok=True)
    return results


def asset_path_font(root: Path, value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    candidate = root / value
    if candidate.is_file():
        return candidate
    return Path(value)


def render_stills(root: Path, data: dict, beats: list[dict], durations: list[float],
                  width: int, height: int, fps: int, target: Path) -> list[Path]:
    settings = data.get("settings", {}) or {}
    font = str(settings.get("font", "") or "")
    font_path = str(asset_path_font(root, font)) if font else ""
    jobs = []
    for beat, duration in zip(beats, durations):
        jobs.append({
            "id": beat["id"],
            "duration": max(0.4, float(duration)),
            "time": max(0.1, float(duration) * 0.5),
            "spec": normalise_scene(beat),
            "text": beat_text(beat),
        })
    if not jobs:
        return []
    events = run_driver(
        jobs, root / "render" / "streams" / "stills", width, height, fps,
        driver_settings(data, font_path), font_path, stills=target,
    )
    return [Path(e["file"]) for e in events if e.get("event") == "still"]


# ---------------------------------------------------------------- cli


def main(argv: list[str]) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Procedural scene renderer for rule horror videos")
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("doctor", help="report node, browser and vendored three.js")
    check.set_defaults(func=lambda args: _doctor())

    places = sub.add_parser("places", help="list locations, shots, poses and expressions")
    places.set_defaults(func=lambda args: _places())

    still = sub.add_parser("still", help="render one PNG from a scene json file")
    still.add_argument("--scene", required=True, help="path to a json file holding one scene spec")
    still.add_argument("--out", required=True)
    still.add_argument("--width", type=int, default=1920)
    still.add_argument("--height", type=int, default=1080)
    still.add_argument("--duration", type=float, default=3.0)
    still.set_defaults(func=_still)

    args = parser.parse_args(argv)
    return args.func(args)


def _doctor() -> int:
    report = doctor_report()
    print(f"node:     {report['node'] or 'MISSING'}")
    print(f"browser:  {report['browser'] or 'MISSING'}")
    print(f"three.js: {'ok' if report['three'] else 'MISSING'}")
    print(f"driver:   {'ok' if report['driver'] else 'MISSING'}")
    ok = report["node"] and report["browser"] and report["three"] and report["driver"]
    print("SCENES READY" if ok else "SCENES NOT READY")
    return 0 if ok else 1


def _places() -> int:
    print("places:      " + ", ".join(PLACES))
    print("shots:       " + ", ".join(SHOTS))
    print("moves:       " + ", ".join(MOVES))
    print("poses:       " + ", ".join(POSES))
    print("expressions: " + ", ".join(EXPRESSIONS))
    print("items:       " + ", ".join(ITEMS))
    return 0


def _still(args) -> int:
    payload = json.loads(Path(args.scene).read_text(encoding="utf-8"))
    beat = {
        "id": payload.get("id", "still"),
        "scene": payload.get("scene", payload),
        "caption": payload.get("caption", ""),
        "narration": payload.get("narration", ""),
        "section": payload.get("section", ""),
        "overlay": payload.get("overlay", ""),
        "overlay_style": payload.get("overlay_style", ""),
        "accent": payload.get("accent", "ivory"),
        "emphasis": payload.get("emphasis", []),
    }
    data = {"style": payload.get("style", "warm-flat"), "settings": payload.get("settings", {})}
    from video_pipeline import ffmpeg_executable

    paths = render_stills(
        Path(args.out).parent, data, [beat], [args.duration],
        args.width, args.height, 30, Path(args.out).parent,
    )
    if not paths:
        raise SceneError("no still produced")
    source = paths[0]
    target = Path(args.out)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    print(f"STILL: {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
