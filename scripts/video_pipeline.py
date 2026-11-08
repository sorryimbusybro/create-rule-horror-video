#!/usr/bin/env python3
"""Rule-horror video pipeline.

Beat-level project -> repaired narration -> captioned, graded, rendered MP4.

Commands
    init      scaffold a project (writes project.json, style-lock.txt, palette.json)
    audio     import user narration (recording / ElevenLabs / any mp3-wav) and repair it
    narrate   OPTIONAL text-to-speech, only when the user has no voiceover
    align     split one continuous voiceover file into beats
    validate  structural + asset checks
    timeline  per-beat table with durations and words-per-minute
    render    preview or final MP4
    qc        extract frames, measure loudness, detect dead air

Voice is never required. Uploaded audio is the first-class path.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import audio_ops  # noqa: E402

AUDIO_RATE = 48000
AUDIO_EXT = {".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg", ".opus", ".wma", ".aiff", ".aif"}


class PipelineError(RuntimeError):
    pass


# ---------------------------------------------------------------- styles

STYLES: dict[str, dict] = {
    "warm-flat": {
        "label": "Warm Flat — illustrated storybook, cinematic dusk",
        "palette": {
            "background": "#1B1418",
            "wall": "#6B5852",
            "shadow": "#3A2E30",
            "ink": "#241C22",
            "ivory": "#F4EAD8",
            "amber": "#E3A94E",
            "garment": "#E05F38",
            "sage": "#7C9270",
            "red": "#D6402F",
        },
        "grade": {"saturation": 1.04, "contrast": 1.05, "gamma": 0.99, "grain": 5, "vignette": 0.55},
        "style_lock": (
            "STYLE LOCK — WARM FLAT. Flat vector storybook illustration, 16:9, cinematic dusk lighting, "
            "large simple shapes with clean edges, matte finish, no photographic texture, one dominant warm "
            "light source with soft bloom, deep plum shadows, subtle film grain, a few floating dust motes, "
            "gentle vignette, generous negative space, lower 22 percent kept dark and uncluttered for captions. "
            "Palette: sky peach #F6D8A6, sun glow #FFEDBE, wall #6B5852, shadow #3A2E30, deep plum #241C22, "
            "garment #E05F38, accent gold #E3A94E, sage #7C9270. "
            "No text, no letters, no numbers, no logo, no watermark."
        ),
        "character": (
            "CHARACTER BLOCK — A friendly stylised cartoon figure. Circular head in deep charcoal-plum (#241C22), "
            "about one third of total body height. Two large white almond eyes with small dark pupils, one wide "
            "simple curved smile, no nose, no ears, no visible neck. Rounded trapezoid torso in a saturated "
            "garment colour with a visible sleeve seam, tapered capsule arms and legs with rounded ends, small "
            "circular hands, simple rounded shoes. Flat fills with two-tone shading, no outline stroke, no "
            "gradient on the face, no facial detail beyond eyes and mouth. Limbs are drawn as filled tapered "
            "shapes, never as single thin sticks."
        ),
        "negative": (
            "NEGATIVE — photorealistic, 3D render, stick figure, stickman, single-line limbs, wire limbs, "
            "empty flat background, floating unrelated shapes, text, letters, numbers, watermark, logo, "
            "signature, extra limbs, malformed hands, gore, blood, deformed face, blurry, low contrast, "
            "oversaturated, jpeg artifacts."
        ),
    },
    "noir-line": {
        "label": "Noir Line — monochrome analog-horror line art",
        "palette": {
            "background": "#050506",
            "wall": "#1A1C1D",
            "shadow": "#0C0D0E",
            "ink": "#0A0B0C",
            "ivory": "#E4E1D7",
            "amber": "#BE893E",
            "garment": "#2A2D30",
            "sage": "#5B6160",
            "red": "#BE2D28",
        },
        "grade": {"saturation": 0.92, "contrast": 1.08, "gamma": 1.0, "grain": 6, "vignette": 0.62},
        "style_lock": (
            "STYLE LOCK — NOIR LINE. Original minimalist 2D line animation, 16:9, matte near-black background, "
            "thin ivory-white contour lines of even weight, flat charcoal-grey fills, simple rounded characters "
            "with restrained expressions, one muted amber practical light casting a soft wedge, sparse domestic "
            "geometry, eerie negative space, restrained analog-horror mood, clean silhouettes, subtle texture, "
            "lower 22 percent dark and uncluttered for captions. "
            "No text, no letters, no numbers, no logo, no watermark."
        ),
        "character": (
            "CHARACTER BLOCK — A simple rounded figure built from filled shapes: egg-shaped head with a thin "
            "ivory contour, two dot eyes with small pupils, minimal brow, narrow torso, tapered limbs with "
            "rounded caps, no rendered fingers. Proportions stay consistent between shots."
        ),
        "negative": (
            "NEGATIVE — photorealistic, colour, 3D render, stick figure, thin wire limbs, text, letters, "
            "numbers, watermark, logo, gore, deformed face, blurry, cluttered composition."
        ),
    },
}

DEFAULT_STYLE = "warm-flat"


# ---------------------------------------------------------------- helpers


def run(command, capture=False):
    result = subprocess.run(
        [str(part) for part in command],
        stdout=subprocess.PIPE if capture else subprocess.DEVNULL,
        stderr=subprocess.PIPE if capture else subprocess.DEVNULL,
        text=True,
        errors="replace",
    )
    if result.returncode != 0:
        detail = ""
        if capture:
            output = (result.stderr or result.stdout or "").strip().splitlines()
            detail = "\n" + "\n".join(output[-14:])
        raise PipelineError(f"Command failed ({Path(str(command[0])).name}):{detail}")
    return result


def ffmpeg_executable() -> str:
    executable = shutil.which("ffmpeg")
    if executable:
        return executable
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except (ImportError, RuntimeError) as exc:
        raise PipelineError(
            "FFmpeg was not found. Install FFmpeg or imageio-ffmpeg after user approval."
        ) from exc


def media_duration(ffmpeg: str, path: Path) -> float:
    result = subprocess.run(
        [str(ffmpeg), "-hide_banner", "-i", str(path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        errors="replace",
    )
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", result.stderr or "")
    if not match:
        raise PipelineError(f"Cannot read media duration: {path}")
    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def load_project(value) -> tuple[Path, dict]:
    root = Path(value).expanduser().resolve()
    path = root / "project.json"
    if not path.is_file():
        raise PipelineError(f"Missing project file: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PipelineError(f"Cannot read {path}: {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("beats"), list):
        raise PipelineError("project.json must contain an object with a beats array")
    return root, data


def save_project(root: Path, data: dict) -> None:
    (root / "project.json").write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def asset_path(root: Path, value) -> Path:
    path = Path(str(value or ""))
    return path if path.is_absolute() else root / path


def resolve_sfx(root: Path, settings: dict, value) -> Path:
    """Resolve a beat's sfx value. ``lib:name.wav`` points at the shared library."""
    text = str(value or "").strip()
    if not text:
        return Path("")
    if text.startswith("lib:"):
        return sfx_library_path(root, settings or {}) / text[4:]
    return asset_path(root, text)


def beat_duration(ffmpeg: str, root: Path, beat: dict, settings: dict) -> float:
    """On-screen duration of one beat: narration + tail padding + explicit hold."""
    audio = beat.get("audio")
    length = 0.0
    if audio and asset_path(root, audio).is_file():
        length = media_duration(ffmpeg, asset_path(root, audio))
    tail = max(0.0, float(setting(settings, "tail_padding", 0.16)))
    return length + tail + max(0.0, float(beat.get("hold", 0.0) or 0.0))


def setting(settings: dict, key: str, default=None):
    """Read a dotted setting, tolerating flat v1 projects."""
    if key in settings:
        return settings[key]
    node = settings
    for part in key.split("."):
        if not isinstance(node, dict) or part not in node:
            return default
        node = node[part]
    return node


def words(text) -> list[str]:
    return re.findall(r"\b[\w']+\b", str(text), flags=re.UNICODE)


def beat_label(beat: dict, index: int) -> str:
    return str(beat.get("id", "")).strip() or f"position {index}"


# ---------------------------------------------------------------- init


def command_init(args) -> int:
    root = Path(args.project).expanduser().resolve()
    project_file = root / "project.json"
    if project_file.exists() and not args.force:
        raise PipelineError(f"Refusing to overwrite existing {project_file}")

    for directory in (
        "assets/images",
        "assets/audio",
        "assets/music",
        "assets/sfx",
        "assets/character",
        "render/beats",
        "render/overlays",
        "render/qc",
    ):
        (root / directory).mkdir(parents=True, exist_ok=True)

    style_key = args.style if args.style in STYLES else DEFAULT_STYLE
    style = STYLES[style_key]
    data = {
        "version": 2,
        "title": args.title,
        "style": style_key,
        "settings": {
            "width": 1920,
            "height": 1080,
            "fps": 30,
            "style": style_key,
            "font": "",
            "voice_mode": "upload",
            "voice": "en-US-ChristopherNeural",
            "rate": "-8%",
            "pitch": "-4Hz",
            "audio": {
                "max_pause": 0.55,
                "min_pause": 0.16,
                "target_peak_db": -3.0,
                "denoise": False,
                "room_tone_db": -58.0,
            },
            "caption": {
                "uppercase": True,
                "max_chars": 64,
                "position": 0.88,
                "band": True,
            },
            "grade": dict(style["grade"]),
            "transition": {"section": 0.45, "beat": 0.0},
            "clean_edges": {"top": 0.0, "bottom": 0.0, "left": 0.0, "right": 0.0},
            "tail_padding": 0.16,
            "music": "",
            "music_volume": 0.07,
            "music_duck": True,
            "ambience": "",
            "ambience_volume": 0.09,
            "sfx_library": "",
            "target_lufs": -16,
            "true_peak": -1.5,
            "brand": args.brand,
            "episode": args.episode,
        },
        "beats": [],
    }
    save_project(root, data)

    (root / "palette.json").write_text(
        json.dumps({"style": style_key, "label": style["label"], **style["palette"]}, indent=2)
        + "\n",
        encoding="utf-8",
    )
    catalog_source = Path(__file__).resolve().parent.parent / "assets" / "sfx-catalog.json"
    if catalog_source.is_file():
        shutil.copyfile(catalog_source, root / "assets" / "sfx" / "catalog.json")
    (root / "style-lock.txt").write_text(
        "\n\n".join([style["style_lock"], style["character"], style["negative"]]) + "\n",
        encoding="utf-8",
    )
    print(f"CREATED: {project_file}")
    print(f"STYLE:   {style['label']}")
    print(f"LOCKS:   {root / 'style-lock.txt'}  (paste into every image generation)")
    print(f"PALETTE: {root / 'palette.json'}")
    print("Next: add beats, import narration with `audio`, then `render`.")
    return 0


# ---------------------------------------------------------------- audio import


def to_wav(ffmpeg: str, source: Path, target: Path, denoise: bool) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    filters = ["highpass=f=60"]
    if denoise:
        filters.append("afftdn=nf=-28:tn=1")
    command = [
        ffmpeg,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        source,
        "-vn",
        "-ac",
        "1",
        "-ar",
        str(AUDIO_RATE),
        "-af",
        ",".join(filters),
        "-c:a",
        "pcm_s16le",
        target,
    ]
    run(command, capture=True)


def repair_take(wav: Path, cfg: dict) -> dict:
    samples, rate = audio_ops.read_wav(wav)
    repaired, report = audio_ops.process_narration(
        samples,
        rate,
        threshold_db=None,
        max_pause=float(cfg.get("max_pause", 0.55)),
        min_pause=float(cfg.get("min_pause", 0.16)),
        target_peak_db=float(cfg.get("target_peak_db", -3.0)),
        room_tone_db=float(cfg.get("room_tone_db", -58.0)),
    )
    audio_ops.write_wav(wav, repaired, rate)
    return report


def match_beat_files(directory: Path, beats: list[dict]) -> dict[str, Path]:
    """Map uploaded files to beats by ID prefix, then by sorted order."""
    files = sorted(
        [p for p in directory.iterdir() if p.is_file() and p.suffix.lower() in AUDIO_EXT],
        key=lambda p: p.name.lower(),
    )
    if not files:
        raise PipelineError(f"No audio files found in {directory}")
    mapping: dict[str, Path] = {}
    used: set[Path] = set()
    for beat in beats:
        beat_id = str(beat.get("id", "")).strip().lower()
        for path in files:
            if path in used:
                continue
            stem = path.stem.lower()
            if stem == beat_id or stem.startswith(beat_id) or beat_id.startswith(stem):
                mapping[beat_id] = path
                used.add(path)
                break
    remaining = [p for p in files if p not in used]
    for beat in beats:
        beat_id = str(beat.get("id", "")).strip().lower()
        if beat_id not in mapping and remaining:
            mapping[beat_id] = remaining.pop(0)
    if remaining:
        print(f"NOTE: {len(remaining)} uploaded file(s) unused (more files than beats)")
    return mapping


def split_by_silence(
    samples: np.ndarray, rate: int, expected: int, proportional_ok: bool, beat_words: list[int]
) -> list[tuple[float, float]]:
    silences = audio_ops.find_silences(samples, rate, None, min_duration=0.24)
    spans: list[tuple[float, float]] = []
    cursor = 0.0
    duration = len(samples) / rate
    for start, end in silences:
        if start - cursor > 0.12:
            spans.append((cursor, start))
        cursor = end
    if duration - cursor > 0.12:
        spans.append((cursor, duration))
    if len(spans) == expected:
        return spans
    if not proportional_ok:
        raise PipelineError(
            f"Found {len(spans)} speech segments but the project has {expected} beats. "
            "Supply one file per beat, or pass --allow-proportional to split by word count."
        )
    total_words = sum(beat_words) or expected
    boundaries = [0.0]
    position = 0.0
    for count in beat_words[:-1]:
        position += duration * count / total_words
        boundaries.append(position)
    boundaries.append(duration)
    print(f"WARNING: proportional split of {len(spans)} segments across {expected} beats")
    return [(boundaries[i], boundaries[i + 1]) for i in range(expected)]


def command_audio(args) -> int:
    root, data = load_project(args.project)
    beats = data["beats"]
    if not beats:
        raise PipelineError("Add beats before importing narration")
    ffmpeg = ffmpeg_executable()
    cfg = dict(setting(data.get("settings", {}), "audio", {}) or {})
    if args.max_pause is not None:
        cfg["max_pause"] = args.max_pause
    if args.target_peak is not None:
        cfg["target_peak_db"] = args.target_peak
    denoise = bool(args.denoise or cfg.get("denoise"))

    source = Path(args.source).expanduser().resolve()
    audio_dir = root / "assets" / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    work_dir = audio_dir / "_source"
    work_dir.mkdir(parents=True, exist_ok=True)

    plan: list[tuple[dict, Path]] = []
    if source.is_dir():
        mapping = match_beat_files(source, beats)
        for beat in beats:
            beat_id = str(beat.get("id", "")).strip().lower()
            if beat_id not in mapping:
                raise PipelineError(f"No uploaded audio matched beat {beat_id}")
            plan.append((beat, mapping[beat_id]))
    elif source.is_file():
        if source.suffix.lower() not in AUDIO_EXT:
            raise PipelineError(f"Unsupported audio file: {source.name}")
        master = work_dir / "master.wav"
        to_wav(ffmpeg, source, master, denoise)
        samples, rate = audio_ops.read_wav(master)
        counts = [max(1, len(words(beat.get("narration", "")))) for beat in beats]
        spans = split_by_silence(samples, rate, len(beats), args.allow_proportional, counts)
        for index, (beat, (start, end)) in enumerate(zip(beats, spans)):
            target = work_dir / f"cut-{index:03d}.wav"
            chunk = samples[int(start * rate) : int(end * rate)]
            audio_ops.write_wav(target, chunk, rate)
            plan.append((beat, target))
    else:
        raise PipelineError(f"Audio source not found: {source}")

    print(f"{'beat':<18}{'in':>7}{'out':>7}{'pauses':>8}{'removed':>9}{'wpm':>7}")
    print("-" * 56)
    total_out = 0.0
    total_removed = 0.0
    for beat, path in plan:
        beat_id = str(beat.get("id", "")).strip()
        wav = audio_dir / f"{beat_id}.wav"
        if path.resolve() != wav.resolve():
            to_wav(ffmpeg, path, wav, denoise)
        report = repair_take(wav, cfg)
        beat["audio"] = (Path("assets") / "audio" / f"{beat_id}.wav").as_posix()
        count = len(words(beat.get("narration", "")))
        duration = report["output_duration"]
        wpm = count / duration * 60.0 if duration else 0.0
        total_out += duration
        total_removed += report["removed"]
        print(
            f"{beat_id:<18}{report['input_duration']:>7.2f}{duration:>7.2f}"
            f"{report['capped']:>8}{report['removed']:>9.2f}{wpm:>7.0f}"
        )
    data.setdefault("settings", {})["voice_mode"] = "upload"
    save_project(root, data)
    print("-" * 56)
    print(
        f"Narration: {len(plan)} beats, {total_out/60:.2f} min, "
        f"{total_removed:.1f}s of dead air removed"
    )
    if total_out < 60:
        print("WARNING: under a minute of narration; a long-form video needs 9-14 minutes")
    return 0


# ---------------------------------------------------------------- tts (optional)


async def _edge_all(root: Path, data: dict, args) -> int:
    try:
        import edge_tts
    except ImportError as exc:
        raise PipelineError(
            "edge-tts is not installed. Either upload narration with `audio`, or approve "
            "`python -m pip install edge-tts`."
        ) from exc
    settings = data.get("settings", {})
    voice = args.voice or setting(settings, "voice", "en-US-ChristopherNeural")
    rate = args.rate or setting(settings, "rate", "-8%")
    pitch = args.pitch or setting(settings, "pitch", "-4Hz")
    beats = data.get("beats", [])
    if not beats:
        raise PipelineError("Add beats before generating narration")
    generated = skipped = 0
    for index, beat in enumerate(beats, start=1):
        beat_id = str(beat.get("id", "")).strip()
        narration = str(beat.get("narration", "")).strip()
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", beat_id):
            raise PipelineError(f"Invalid or missing beat ID at position {index}")
        if not narration:
            raise PipelineError(f"Missing narration for beat {beat_id}")
        relative = Path("assets") / "audio" / f"{beat_id}.mp3"
        output = root / relative
        output.parent.mkdir(parents=True, exist_ok=True)
        beat["audio"] = relative.as_posix()
        if output.exists() and not args.force:
            skipped += 1
            continue
        temporary = output.with_name(output.stem + ".partial.mp3")
        try:
            communicate = edge_tts.Communicate(narration, voice=voice, rate=rate, pitch=pitch)
            await communicate.save(str(temporary))
            temporary.replace(output)
        finally:
            if temporary.exists():
                temporary.unlink()
        generated += 1
        if generated % 10 == 0 or index == len(beats):
            print(f"Narration progress: {index}/{len(beats)} beats")
    settings.update({"voice": voice, "rate": rate, "pitch": pitch, "voice_mode": "tts"})
    save_project(root, data)
    print(f"TTS COMPLETE: {generated} generated, {skipped} reused, {len(beats)} total")
    print("Run `audio` with --source assets/audio to apply pause repair and levelling.")
    return 0


def command_narrate(args) -> int:
    root, data = load_project(args.project)
    engine = (args.engine or "edge").lower()
    if engine == "edge":
        return asyncio.run(_edge_all(root, data, args))
    if engine == "sapi":
        script = Path(__file__).resolve().parent / "tts_sapi.ps1"
        if not script.is_file():
            raise PipelineError(f"Missing {script}")
        result = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(script),
                "-ProjectRoot",
                str(root),
            ],
            capture_output=True,
            text=True,
        )
        print((result.stdout or "").strip())
        if result.returncode != 0:
            raise PipelineError(
                "SAPI narration failed; use uploaded narration instead: "
                + (result.stderr or "").strip()[:400]
            )
        return 0
    raise PipelineError(f"Unknown engine: {engine}")


# ---------------------------------------------------------------- align


def command_align(args) -> int:
    root, data = load_project(args.project)
    beats = data["beats"]
    if not beats:
        raise PipelineError("Add beats before aligning narration")
    ffmpeg = ffmpeg_executable()
    source = Path(args.file).expanduser().resolve()
    if not source.is_file():
        raise PipelineError(f"Audio not found: {source}")
    cfg = dict(setting(data.get("settings", {}), "audio", {}) or {})
    work = root / "assets" / "audio" / "_source"
    work.mkdir(parents=True, exist_ok=True)
    master = work / "master.wav"
    to_wav(ffmpeg, source, master, bool(cfg.get("denoise")))

    if args.engine == "whisper":
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise PipelineError(
                "faster-whisper is not installed. Approve `python -m pip install faster-whisper` "
                "for word-level alignment, or use --engine silence."
            ) from exc
        model = WhisperModel(args.model, device="cpu", compute_type="int8")
        segments, _ = model.transcribe(str(master), word_timestamps=True)
        timeline = []
        for segment in segments:
            for word in segment.words or []:
                token = re.sub(r"[^\w']", "", word.word.lower())
                if token:
                    timeline.append((token, word.start, word.end))
        print(f"Transcribed {len(timeline)} words")
        cursor = 0
        spans = []
        for beat in beats:
            target = [w.lower() for w in words(beat.get("narration", ""))]
            if not target:
                spans.append((0.0, 0.0))
                continue
            best_start = cursor
            for probe in range(cursor, min(cursor + 40, len(timeline))):
                if timeline[probe][0] == target[0]:
                    best_start = probe
                    break
            end = best_start
            matched = 0
            probe = best_start
            while probe < len(timeline) and matched < len(target):
                if timeline[probe][0] == target[matched]:
                    matched += 1
                    end = probe
                probe += 1
            start_time = timeline[best_start][1] if best_start < len(timeline) else 0.0
            end_time = timeline[end][2] if end < len(timeline) else start_time
            spans.append((start_time, end_time))
            cursor = max(cursor, end + 1)
    else:
        samples, rate = audio_ops.read_wav(master)
        counts = [max(1, len(words(beat.get("narration", "")))) for beat in beats]
        spans = split_by_silence(samples, rate, len(beats), args.allow_proportional, counts)

    samples, rate = audio_ops.read_wav(master)
    audio_dir = root / "assets" / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    for beat, (start, end) in zip(beats, spans):
        beat_id = str(beat.get("id", "")).strip()
        target = audio_dir / f"{beat_id}.wav"
        chunk = samples[int(start * rate) : int(end * rate)]
        audio_ops.write_wav(target, chunk, rate)
        repair_take(target, cfg)
        beat["audio"] = (Path("assets") / "audio" / f"{beat_id}.wav").as_posix()
        print(f"{beat_id:<18} {start:7.2f} -> {end:7.2f}  ({end - start:5.2f}s)")
    save_project(root, data)
    print(f"ALIGNED: {len(beats)} beats from {source.name}")
    return 0


# ---------------------------------------------------------------- validation


def validate_project(root: Path, data: dict, check_assets=False):
    errors: list[str] = []
    warnings: list[str] = []
    beats = data.get("beats", [])
    settings = data.get("settings", {}) or {}
    if not beats:
        errors.append("The beats array is empty")
    if not str(data.get("title", "")).strip():
        errors.append("Missing video title")
    for key, minimum, maximum in (("width", 320, 7680), ("height", 240, 4320), ("fps", 12, 60)):
        value = setting(settings, key)
        if not isinstance(value, (int, float)) or not minimum <= value <= maximum:
            errors.append(f"settings.{key} must be between {minimum} and {maximum}")

    max_chars = int(setting(settings, "caption.max_chars", 64))
    seen: set[str] = set()
    total_words = 0
    audio_seconds = 0.0
    ffmpeg = None
    if check_assets and beats:
        try:
            ffmpeg = ffmpeg_executable()
        except PipelineError as exc:
            errors.append(str(exc))

    for index, beat in enumerate(beats, start=1):
        if not isinstance(beat, dict):
            errors.append(f"Beat {index} is not an object")
            continue
        beat_id = str(beat.get("id", "")).strip()
        label = beat_label(beat, index)
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", beat_id):
            errors.append(f"Invalid beat ID: {label}")
        if beat_id in seen:
            errors.append(f"Duplicate beat ID: {beat_id}")
        seen.add(beat_id)
        narration = str(beat.get("narration", "")).strip()
        caption = str(beat.get("caption", "") or narration).strip()
        if not narration:
            errors.append(f"{label}: missing narration")
        if not str(beat.get("section", "")).strip():
            errors.append(f"{label}: missing section")
        if not str(beat.get("image", "")).strip():
            errors.append(f"{label}: missing image")
        if not str(beat.get("audio", "")).strip():
            errors.append(f"{label}: missing audio")
        if beat.get("camera", "static") not in {
            "static",
            "push-in",
            "pull-back",
            "drift-left",
            "drift-right",
        }:
            errors.append(f"{label}: unsupported camera move")
        narration_words = len(words(narration))
        total_words += narration_words
        if narration_words > 34:
            warnings.append(f"{label}: {narration_words} narration words may run long")
        if len(caption) > max_chars:
            warnings.append(f"{label}: caption {len(caption)} chars exceeds {max_chars}")
        if index == 1 and narration_words > 38:
            warnings.append("Opening beat is long; deliver the title premise faster")
        if check_assets:
            for field in ("image", "audio", "sfx"):
                value = beat.get(field)
                if not value:
                    continue
                resolved = (
                    resolve_sfx(root, data.get("settings", {}) or {}, value)
                    if field == "sfx"
                    else asset_path(root, value)
                )
                if not resolved.is_file():
                    errors.append(f"{label}: missing {field} file {value}")
            audio = beat.get("audio")
            if audio and asset_path(root, audio).is_file() and ffmpeg:
                try:
                    audio_seconds += media_duration(ffmpeg, asset_path(root, audio))
                except PipelineError as exc:
                    errors.append(str(exc))

    sections = {str(beat.get("section", "")).upper() for beat in beats if isinstance(beat, dict)}
    if beats and not any("TWIST" in section or "REVEAL" in section for section in sections):
        warnings.append("No REVEAL or TWIST section found")
    if total_words and total_words < 900:
        warnings.append(f"Script is short for long form ({total_words} words)")
    if audio_seconds and audio_seconds < 480:
        warnings.append(f"Narration is {audio_seconds/60:.1f} min; target 9-14 min")
    return errors, warnings, total_words, audio_seconds


def command_validate(args) -> int:
    root, data = load_project(args.project)
    errors, warnings, total_words, audio_seconds = validate_project(root, data, args.assets)
    for warning in warnings[:30]:
        print(f"WARNING: {warning}")
    if len(warnings) > 30:
        print(f"WARNING: {len(warnings) - 30} additional warnings suppressed")
    for error in errors[:50]:
        print(f"ERROR: {error}")
    if len(errors) > 50:
        print(f"ERROR: {len(errors) - 50} additional errors suppressed")
    print(f"Beats: {len(data.get('beats', []))}")
    print(f"Narration words: {total_words}")
    if audio_seconds:
        print(f"Narration duration: {audio_seconds:.1f} s ({audio_seconds/60:.2f} min)")
        print(f"Average pace: {total_words / (audio_seconds/60):.0f} wpm")
    if errors:
        print(f"INVALID: {len(errors)} errors, {len(warnings)} warnings")
        return 1
    print(f"VALID: 0 errors, {len(warnings)} warnings")
    return 0


def command_timeline(args) -> int:
    root, data = load_project(args.project)
    ffmpeg = ffmpeg_executable()
    beats = data["beats"]
    print(f"{'#':<4}{'id':<18}{'section':<14}{'dur':>6}{'words':>7}{'wpm':>6}  image")
    print("-" * 78)
    cursor = 0.0
    for index, beat in enumerate(beats, start=1):
        duration = beat_duration(ffmpeg, root, beat, data.get("settings", {}) or {})
        count = len(words(beat.get("narration", "")))
        wpm = count / duration * 60 if duration else 0
        print(
            f"{index:<4}{str(beat.get('id',''))[:17]:<18}{str(beat.get('section',''))[:13]:<14}"
            f"{duration:>6.2f}{count:>7}{wpm:>6.0f}  {Path(str(beat.get('image',''))).name}"
        )
        cursor += duration
    print("-" * 78)
    print(f"Total: {cursor/60:.2f} min across {len(beats)} beats")
    return 0


# ---------------------------------------------------------------- sfx placement

SFX_CATEGORY_ORDER = ["transition", "stinger", "texture", "foley", "ambience"]


def load_catalog(root: Path) -> dict:
    candidates = [
        root / "assets" / "sfx" / "catalog.json",
        Path(__file__).resolve().parent.parent / "assets" / "sfx-catalog.json",
    ]
    for candidate in candidates:
        if candidate.is_file():
            try:
                data = json.loads(candidate.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(data.get("roles"), list):
                return data
    return {"roles": []}


def normalise_stem(path: Path) -> str:
    return re.sub(r"[^a-z0-9]+", "-", path.stem.lower()).strip("-")


def sfx_library_path(root: Path, settings: dict) -> Path:
    """Shared effect library. A project can override it with settings.sfx_library."""
    configured = str(setting(settings, "sfx_library", "") or "").strip()
    if configured:
        candidate = Path(configured).expanduser()
        return candidate if candidate.is_absolute() else (root / candidate)
    return Path(__file__).resolve().parent.parent / "assets" / "sfx"


def match_role(path: Path, catalog: dict) -> str | None:
    stem = normalise_stem(path)
    best_role = None
    best_length = 0
    for role in catalog["roles"]:
        for term in [role["id"]] + list(role.get("match", [])):
            key = normalise_stem(Path(term))
            if key and key in stem and len(key) > best_length:
                best_role = role["id"]
                best_length = len(key)
    return best_role


def scan_sfx(root: Path, catalog: dict, library: Path | None = None) -> dict[str, list[Path]]:
    """Project files first, then the shared library for any role still empty."""
    index: dict[str, list[Path]] = {}
    folders = [root / "assets" / "sfx"]
    if library and library.is_dir() and library.resolve() != (root / "assets" / "sfx").resolve():
        folders.append(library)
    for position, folder in enumerate(folders):
        if not folder.is_dir():
            continue
        for path in sorted(folder.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in AUDIO_EXT:
                continue
            role_id = match_role(path, catalog)
            if not role_id:
                continue
            if position > 0 and role_id in index:
                continue
            index.setdefault(role_id, []).append(path)
    for role_id in index:
        index[role_id].sort()
    return index


def choose_sfx_role(beat: dict, first_of_section: bool, section_age: int, narration: str, catalog: dict) -> str | None:
    section = str(beat.get("section", "")).upper()
    has_overlay = bool(str(beat.get("overlay", "") or "").strip())
    if "TWIST" in section or "REVEAL" in section:
        return "stinger-sub-drop" if first_of_section else None
    if has_overlay:
        return "stinger-hit" if "RULE" in section else "transition-whoosh"
    if first_of_section:
        return "transition-dip"
    if "CASE" in section and section_age <= 2:
        return "stinger-heartbeat"
    words_lower = {w.lower() for w in words(narration)}
    best_role = None
    best_score = 0
    for role in catalog["roles"]:
        hits = sum(1 for key in role.get("keywords", []) if key.lower() in words_lower)
        if hits > best_score:
            best_role = role["id"]
            best_score = hits
    return best_role


def command_sfx(args) -> int:
    root, data = load_project(args.project)
    beats = data["beats"]
    if not beats:
        raise PipelineError("Add beats before placing sound effects")
    catalog = load_catalog(root)
    if not catalog["roles"]:
        raise PipelineError("No SFX catalog found")
    roles = {role["id"]: role for role in catalog["roles"]}

    if args.clear:
        cleared = 0
        for beat in beats:
            if beat.get("sfx"):
                beat["sfx"] = ""
                beat.pop("sfx_gain", None)
                cleared += 1
        save_project(root, data)
        print(f"CLEARED: {cleared} beats")
        return 0

    index = scan_sfx(root, catalog, sfx_library_path(root, data.get("settings", {}) or {}))
    if not index:
        print(f"No usable files in {root / 'assets' / 'sfx'} or the shared library")
        print("Name files after a role id or one of its match terms, e.g. door-creak__01.wav")
        print("Roles: " + ", ".join(sorted(roles)))
        return 1

    print(f"SFX library  ({sfx_library_path(root, data.get('settings', {}) or {})})")
    for category in SFX_CATEGORY_ORDER:
        entries = [
            (role_id, files)
            for role_id, files in sorted(index.items())
            if roles.get(role_id, {}).get("category") == category
        ]
        if not entries:
            continue
        print(f"  {category}")
        for role_id, files in entries:
            print(f"    {role_id:<26} {len(files)} file(s)  e.g. {files[0].name}")

    if not args.auto:
        print("\nRun again with --auto to place them, or --auto --dry-run to preview.")
        return 0

    ffmpeg = ffmpeg_executable()
    sections = [str(beat.get("section", "")).strip() for beat in beats]
    last_used: dict[str, float] = {}
    cursor = 0.0
    planned = 0
    print(f"\n{'beat':<18}{'role':<24}{'gain':>6}{'at':>8}  file")
    print("-" * 86)
    for index_number, beat in enumerate(beats):
        duration = beat_duration(ffmpeg, root, beat, data.get("settings", {}) or {})
        start = cursor
        cursor += duration

        if beat.get("sfx") and not args.force:
            continue
        if index_number == 0:
            continue
        first_of_section = index_number == 0 or sections[index_number - 1] != sections[index_number]
        section_age = 0
        for probe in range(index_number, -1, -1):
            if sections[probe] != sections[index_number]:
                break
            section_age = index_number - probe
        role_id = choose_sfx_role(
            beat, first_of_section, section_age, str(beat.get("narration", "")), catalog
        )
        if not role_id or role_id not in index:
            continue
        role = roles.get(role_id, {})
        cooldown = float(role.get("cooldown", 0))
        if role_id in last_used and start - last_used[role_id] < cooldown:
            continue
        files = index[role_id]
        pick = files[hash(str(beat.get("id", ""))) % len(files)]
        gain = float(role.get("gain", 0.4))
        print(
            f"{str(beat.get('id', '')):<18}{role_id:<24}{gain:>6.2f}{start:>8.1f}  {pick.name}"
        )
        if not args.dry_run:
            try:
                beat["sfx"] = pick.relative_to(root).as_posix()
            except ValueError:
                # Shared-library file: store a portable reference, not an absolute path.
                beat["sfx"] = f"lib:{pick.name}"
            beat["sfx_gain"] = round(gain, 3)
        last_used[role_id] = start
        planned += 1
    print("-" * 86)
    if args.dry_run:
        print(f"DRY RUN: {planned} effects would be placed; nothing written")
    else:
        save_project(root, data)
        print(f"PLACED: {planned} effects across {len(beats)} beats")
    return 0


# ---------------------------------------------------------------- overlays


def font_path(settings: dict) -> str | None:
    candidates = [
        setting(settings, "font", ""),
        "C:/Windows/Fonts/segoeuib.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return str(candidate)
    return None


def load_font(settings: dict, size: int):
    from PIL import ImageFont

    path = font_path(settings)
    if path:
        return ImageFont.truetype(path, size=size)
    try:
        return ImageFont.truetype("DejaVuSans-Bold.ttf", size=size)
    except OSError as exc:
        raise PipelineError("No usable bold font found; set settings.font") from exc


def wrap_words(draw, text: str, font, max_width: float) -> list[str]:
    lines: list[str] = []
    for source_line in str(text).splitlines() or [""]:
        current = ""
        for word in source_line.split():
            candidate = f"{current} {word}".strip()
            if current and draw.textlength(candidate, font=font) > max_width:
                lines.append(current)
                current = word
            else:
                current = candidate
        lines.append(current)
    return lines


def fit_text(draw, text: str, settings: dict, width: int, start: int, max_lines: int, ratio: float = 0.84):
    size = start
    while size >= 22:
        font = load_font(settings, size)
        lines = wrap_words(draw, text, font, width * ratio)
        if len(lines) <= max_lines:
            return font, lines
        size -= 2
    font = load_font(settings, 22)
    return font, wrap_words(draw, text, font, width * ratio)


def draw_line_emphasis(draw, line: str, font, x: float, y: float, base, accent, emphasis: set[str]):
    """Draw one caption line word by word so key words can take the accent colour."""
    space = draw.textlength(" ", font=font)
    cursor = x
    for word in line.split():
        colour = accent if re.sub(r"[^\w']", "", word.lower()) in emphasis else base
        draw.text((cursor, y), word, font=font, fill=colour)
        cursor += draw.textlength(word, font=font) + space


def palette_for(data: dict) -> dict:
    settings = data.get("settings", {}) or {}
    key = str(data.get("style") or setting(settings, "style", DEFAULT_STYLE))
    return STYLES.get(key, STYLES[DEFAULT_STYLE])["palette"]


def rgba(hex_value: str, alpha: int = 255) -> tuple[int, int, int, int]:
    hex_value = hex_value.lstrip("#")
    return (
        int(hex_value[0:2], 16),
        int(hex_value[2:4], 16),
        int(hex_value[4:6], 16),
        alpha,
    )


def create_overlay(root: Path, data: dict, beat: dict, path: Path, width: int, height: int, start_seconds: float):
    from PIL import Image, ImageDraw, ImageFilter

    settings = data.get("settings", {}) or {}
    palette = palette_for(data)
    colours = {
        "ivory": rgba(palette["ivory"]),
        "amber": rgba(palette["amber"]),
        "red": rgba(palette["red"]),
    }
    accent = colours.get(str(beat.get("accent", "ivory")).lower(), colours["ivory"])
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    scale = height / 1080

    if setting(settings, "caption.band", True):
        band_top = int(height * 0.70)
        steps = 48
        for step in range(steps):
            alpha = int(150 * (step / steps) ** 1.4)
            y0 = band_top + int((height - band_top) * step / steps)
            y1 = band_top + int((height - band_top) * (step + 1) / steps)
            draw.rectangle((0, y0, width, y1), fill=(4, 4, 5, alpha))

    hud_font = load_font(settings, max(14, round(21 * scale)))
    brand = str(setting(settings, "brand", "") or "").strip()
    episode = str(setting(settings, "episode", "") or "").strip()
    section = str(beat.get("section", "")).strip()
    hud = "  •  ".join(part for part in (brand, episode, section) if part)
    if hud:
        draw.text((width * 0.035, height * 0.045), hud[:90], font=hud_font, fill=(206, 202, 194, 210))
    timecode = f"{int(start_seconds // 60):02d}:{int(start_seconds % 60):02d}"
    time_width = draw.textlength(timecode, font=hud_font)
    right = width * 0.965
    draw.text((right - time_width, height * 0.045), timecode, font=hud_font, fill=(206, 202, 194, 210))
    dot_x = right - time_width - 24 * scale
    draw.ellipse(
        (dot_x, height * 0.045 + 9 * scale, dot_x + 9 * scale, height * 0.045 + 18 * scale),
        fill=colours["red"],
    )

    overlay = str(beat.get("overlay", "") or "").strip()
    if overlay:
        overlay_font, overlay_lines = fit_text(
            draw, overlay, settings, width, round(84 * scale), 4, ratio=0.80
        )
        line_height = overlay_font.getbbox("Ag")[3] - overlay_font.getbbox("Ag")[1]
        top = height * 0.26
        widest = max(draw.textlength(line, font=overlay_font) for line in overlay_lines)
        block_h = len(overlay_lines) * (line_height + 14 * scale)
        pad = 40 * scale

        # Full-width feathered band instead of a box: no vertical edges can ever
        # show, so the card sits in the image rather than on top of it.
        band_top = max(0.0, top - block_h * 0.55)
        band_bottom = min(float(height), top + block_h + block_h * 0.45)
        steps = 56
        for step in range(steps):
            u = (step + 0.5) / steps
            alpha = int(205 * (math.sin(math.pi * u) ** 0.65))
            y0 = int(band_top + (band_bottom - band_top) * step / steps)
            y1 = int(band_top + (band_bottom - band_top) * (step + 1) / steps) + 1
            draw.rectangle((0, y0, width, y1), fill=(4, 4, 6, alpha))

        if str(beat.get("overlay_style", "")).lower() == "card":
            # Typographic rules above and below the block; no rectangle to fight the art.
            left, right = (width - widest) / 2, (width + widest) / 2
            draw.line((left, top - 24 * scale, right, top - 24 * scale),
                      fill=accent, width=max(1, round(2 * scale)))
            draw.line((left, top + block_h + 12 * scale, right, top + block_h + 12 * scale),
                      fill=accent, width=max(1, round(2 * scale)))
        for index, line in enumerate(overlay_lines):
            line_width = draw.textlength(line, font=overlay_font)
            draw.text(
                ((width - line_width) / 2, top + index * (line_height + 14 * scale)),
                line,
                font=overlay_font,
                fill=accent,
                stroke_width=max(1, round(2 * scale)),
                stroke_fill=(0, 0, 0, 160),
            )

    caption = str(beat.get("caption", "") or beat.get("narration", "")).strip()
    if setting(settings, "caption.uppercase", True):
        caption = caption.upper()
    if caption:
        caption_font, caption_lines = fit_text(
            draw, caption, settings, width, round(50 * scale), 2, ratio=0.82
        )
        line_height = caption_font.getbbox("Ag")[3] - caption_font.getbbox("Ag")[1]
        spacing = 12 * scale
        total_height = len(caption_lines) * line_height + (len(caption_lines) - 1) * spacing
        position = float(setting(settings, "caption.position", 0.88))
        top = height * position - total_height
        emphasis = {
            re.sub(r"[^\w']", "", str(word).lower()) for word in (beat.get("emphasis") or [])
        }
        for index, line in enumerate(caption_lines):
            line_width = draw.textlength(line, font=caption_font)
            y = top + index * (line_height + spacing)
            if emphasis:
                draw_line_emphasis(
                    draw, line, caption_font, (width - line_width) / 2, y,
                    colours["ivory"], accent, emphasis,
                )
            else:
                draw.text(
                    ((width - line_width) / 2, y),
                    line,
                    font=caption_font,
                    fill=colours["ivory"],
                    stroke_width=max(1, round(2 * scale)),
                    stroke_fill=(0, 0, 0, 200),
                )
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


# ---------------------------------------------------------------- render


def prepare_plate(root: Path, image_path: Path, settings: dict, width: int, height: int, cache_dir: Path) -> Path:
    """Bake clean-edge crop, grade, vignette and grain into one oversized plate.

    Doing this in the encoder cost more than twice the render time on a 4-core
    machine, because grain is expensive to encode. Baked once per unique plate it
    is nearly free, and every beat then reuses the same look.
    """
    from PIL import Image, ImageEnhance, ImageOps

    clean = setting(settings, "clean_edges", {}) or {}
    grade = {
        "saturation": float(setting(settings, "grade.saturation", 1.04)),
        "contrast": float(setting(settings, "grade.contrast", 1.05)),
        "gamma": float(setting(settings, "grade.gamma", 0.99)),
        "grain": int(setting(settings, "grade.grain", 5) or 0),
        "vignette": float(setting(settings, "grade.vignette", 0.55) or 0),
    }
    payload = {
        "image": [image_path.as_posix(), image_path.stat().st_size, image_path.stat().st_mtime_ns],
        "clean": clean,
        "grade": grade,
        "size": [width, height],
    }
    key = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]
    target = cache_dir / f"{key}.png"
    if target.is_file() and target.stat().st_size > 0:
        return target

    image = Image.open(image_path).convert("RGB")
    source_w, source_h = image.size
    left = float(clean.get("left", 0) or 0)
    right = float(clean.get("right", 0) or 0)
    top = float(clean.get("top", 0) or 0)
    bottom = float(clean.get("bottom", 0) or 0)
    if left or right or top or bottom:
        box = (
            int(source_w * left),
            int(source_h * top),
            int(source_w * (1 - right)),
            int(source_h * (1 - bottom)),
        )
        if box[2] - box[0] > 16 and box[3] - box[1] > 16:
            image = image.crop(box)

    headroom = 1.15  # extra pixels so camera moves never upscale
    image = ImageOps.fit(
        image,
        (round(width * headroom), round(height * headroom)),
        method=Image.LANCZOS,
        centering=(0.5, 0.45),
    )
    if abs(grade["saturation"] - 1.0) > 0.001:
        image = ImageEnhance.Color(image).enhance(grade["saturation"])
    if abs(grade["contrast"] - 1.0) > 0.001:
        image = ImageEnhance.Contrast(image).enhance(grade["contrast"])

    array = np.asarray(image).astype(np.float32) / 255.0
    if abs(grade["gamma"] - 1.0) > 0.001:
        array = np.power(np.clip(array, 0.0, 1.0), grade["gamma"])

    plate_h, plate_w = array.shape[:2]
    if grade["vignette"] > 0:
        strength = min(0.72, grade["vignette"] * 0.62)
        yy, xx = np.mgrid[0:plate_h, 0:plate_w].astype(np.float32)
        cx, cy = plate_w / 2.0, plate_h / 2.0
        radius = np.sqrt(((xx - cx) / cx) ** 2 + ((yy - cy) / cy) ** 2) / 1.4142
        mask = np.clip(1.0 - strength * np.power(radius, 2.1), 0.0, 1.0)[..., None]
        array = array * mask

    if grade["grain"] > 0:
        rng = np.random.default_rng(11)
        amplitude = grade["grain"] * 0.0038
        array = array + rng.normal(0.0, amplitude, array.shape).astype(np.float32)

    result = Image.fromarray(np.clip(array * 255.0, 0, 255).astype(np.uint8), "RGB")
    cache_dir.mkdir(parents=True, exist_ok=True)
    result.save(target, optimize=False)
    return target


def camera_filter(camera: str, width: int, height: int, fps: int, frames: int) -> str:
    center_x = "iw/2-(iw/zoom/2)"
    center_y = "ih/2-(ih/zoom/2)"
    zoom = "1.0"
    x = center_x
    y = center_y
    span = max(frames, 1)
    if camera == "push-in":
        zoom = f"min(1.0+on*0.10/{span},1.10)"
    elif camera == "pull-back":
        zoom = f"max(1.10-on*0.10/{span},1.0)"
    elif camera == "drift-left":
        zoom = "1.12"
        x = f"(iw-iw/zoom)*on/{span}"
    elif camera == "drift-right":
        zoom = "1.12"
        x = f"(iw-iw/zoom)*(1-on/{span})"
    return f"zoompan=z='{zoom}':x='{x}':y='{y}':d=1:s={width}x{height}:fps={fps}"


def beat_signature(data: dict, beat: dict, image: Path, audio: Path, width: int, height: int) -> str:
    settings = data.get("settings", {}) or {}
    relevant = {
        key: setting(settings, key)
        for key in (
            "fps", "font", "brand", "episode", "caption", "grade",
            "transition", "tail_padding", "clean_edges",
        )
    }
    payload = {
        "beat": beat,
        "settings": relevant,
        "style": data.get("style"),
        "width": width,
        "height": height,
        "image": [image.stat().st_size, image.stat().st_mtime_ns],
        "audio": [audio.stat().st_size, audio.stat().st_mtime_ns],
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def srt_timestamp(seconds: float) -> str:
    milliseconds = max(0, round(seconds * 1000))
    hours, remainder = divmod(milliseconds, 3600000)
    minutes, remainder = divmod(remainder, 60000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def chapter_timestamp(seconds: float) -> str:
    total = max(0, int(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}" if hours else f"{minutes:02d}:{secs:02d}"


def write_timed_documents(root: Path, beats: list[dict], durations: list[float]) -> None:
    cursor = 0.0
    captions = []
    chapters = []
    previous = None
    for index, (beat, duration) in enumerate(zip(beats, durations), start=1):
        text = str(beat.get("caption", "") or beat.get("narration", "")).strip()
        captions.append(
            f"{index}\n{srt_timestamp(cursor)} --> {srt_timestamp(cursor + duration)}\n{text}\n"
        )
        section = str(beat.get("section", "UNTITLED")).strip()
        if section != previous:
            chapters.append(f"{chapter_timestamp(cursor)} {section}")
            previous = section
        cursor += duration
    (root / "captions.srt").write_text("\n".join(captions), encoding="utf-8")
    (root / "chapters.txt").write_text("\n".join(chapters) + "\n", encoding="utf-8")


def composite_static(plate: Path, overlay: Path, width: int, height: int, target: Path) -> None:
    """Flatten plate and overlay into one frame for beats that do not move.

    A static beat has no reason to composite two full-resolution layers per frame;
    doing it once in PIL and encoding a still is several times faster.
    """
    from PIL import Image

    base = Image.open(plate).convert("RGBA")
    # match zoompan at zoom 1.0 exactly: the whole plate, scaled to frame
    if base.size != (width, height):
        base = base.resize((width, height), Image.LANCZOS)
    layer = Image.open(overlay).convert("RGBA")
    base.alpha_composite(layer)
    target.parent.mkdir(parents=True, exist_ok=True)
    base.convert("RGB").save(target)


def render_beat(
    ffmpeg: str,
    root: Path,
    data: dict,
    beat: dict,
    duration: float,
    width: int,
    height: int,
    fps: int,
    start_seconds: float,
    output: Path,
    overlay_dir: Path,
    fades: tuple[float, float],
):
    settings = data.get("settings", {}) or {}
    image_path = asset_path(root, beat["image"])
    audio_path = asset_path(root, beat["audio"])
    overlay = overlay_dir / f"{beat['id']}.png"
    create_overlay(root, data, beat, overlay, width, height, start_seconds)
    plate = prepare_plate(
        root, image_path, settings, width, height, root / "render" / "plates"
    )

    frames = max(1, round(duration * fps))
    camera = str(beat.get("camera", "static"))
    fade_in, fade_out = fades
    fade_chain = []
    if fade_in > 0:
        fade_chain.append(f"fade=t=in:st=0:d={fade_in:.3f}")
    if fade_out > 0:
        fade_chain.append(f"fade=t=out:st={max(0.0, duration - fade_out):.3f}:d={fade_out:.3f}")
    tail = ("," + ",".join(fade_chain)) if fade_chain else ""

    if camera == "static":
        frame = root / "render" / "frames" / f"{beat['id']}.png"
        composite_static(plate, overlay, width, height, frame)
        video_parts = [f"[0:v]fps={fps}{tail},format=yuv420p[v]"]
        inputs = [
            "-loop", "1", "-framerate", "1", "-t", f"{duration:.3f}", "-i", str(frame),
            "-i", str(audio_path),
        ]
        audio_index = 1
    else:
        motion = camera_filter(camera, width, height, fps, frames)
        video_parts = [
            f"[0:v]loop=loop=-1:size=1:start=0,fps={fps},{motion}[bg]",
            f"[1:v]loop=loop=-1:size=1:start=0,fps={fps},format=rgba[ov]",
            f"[bg][ov]overlay=0:0:format=auto{tail},format=yuv420p[v]",
        ]
        inputs = ["-i", str(plate), "-i", str(overlay), "-i", str(audio_path)]
        audio_index = 2

    audio_parts = [
        f"[{audio_index}:a]afade=t=in:st=0:d=0.03,"
        f"afade=t=out:st={max(0.0, duration - 0.08):.3f}:d=0.08,"
        f"apad=pad_dur={duration:.3f},atrim=0:{duration:.3f}[na]"
    ]
    sfx = str(beat.get("sfx", "") or "").strip()
    sfx_file = resolve_sfx(root, settings, sfx) if sfx else Path("")
    if sfx and sfx_file.is_file():
        inputs.extend(["-i", str(sfx_file)])
        gain = float(beat.get("sfx_gain", 0.5))
        audio_parts.append(f"[{audio_index + 1}:a]volume={gain:.3f},apad=pad_dur={duration:.3f}[fx]")
        audio_parts.append("[na][fx]amix=inputs=2:duration=first:normalize=0[a]")
    else:
        audio_parts.append("[na]anull[a]")

    command = [
        ffmpeg,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        *inputs,
        "-filter_complex",
        ";".join(video_parts + audio_parts),
        "-map",
        "[v]",
        "-map",
        "[a]",
        "-t",
        f"{duration:.3f}",
        "-r",
        str(fps),
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "19",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-ar",
        str(AUDIO_RATE),
        "-ac",
        "2",
        output,
    ]
    run(command, capture=True)


def command_render(args) -> int:
    root, data = load_project(args.project)
    errors, warnings, _, _ = validate_project(root, data, check_assets=True)
    if errors:
        for error in errors[:30]:
            print(f"ERROR: {error}")
        raise PipelineError(f"Validation failed with {len(errors)} errors")
    if warnings:
        print(f"Validation passed with {len(warnings)} warnings; run validate for details")

    ffmpeg = ffmpeg_executable()
    settings = data.get("settings", {}) or {}
    preview = args.preview is not None
    beats = data["beats"][: args.preview] if preview else data["beats"]
    if not beats:
        raise PipelineError("No beats selected for rendering")
    width = 960 if preview else int(setting(settings, "width", 1920))
    height = 540 if preview else int(setting(settings, "height", 1080))
    fps = int(setting(settings, "fps", 30))
    tail = max(0.0, float(setting(settings, "tail_padding", 0.16)))
    section_fade = float(setting(settings, "transition.section", 0.45))
    stem = "preview" if preview else "final"
    beat_dir = root / "render" / "beats" / stem
    overlay_dir = root / "render" / "overlays" / stem
    beat_dir.mkdir(parents=True, exist_ok=True)
    overlay_dir.mkdir(parents=True, exist_ok=True)

    outputs: list[Path] = []
    durations: list[float] = []
    cursor = 0.0
    sections = [str(beat.get("section", "")).strip() for beat in beats]
    for index, beat in enumerate(beats, start=1):
        beat_id = beat["id"]
        started = time.perf_counter()
        audio_path = asset_path(root, beat["audio"])
        duration = beat_duration(ffmpeg, root, beat, settings)
        output = beat_dir / f"{beat_id}.mp4"
        signature_file = beat_dir / f"{beat_id}.json"
        signature = beat_signature(
            data, beat, asset_path(root, beat["image"]), audio_path, width, height
        )
        fresh = (
            not args.force
            and output.is_file()
            and signature_file.is_file()
            and signature_file.read_text(encoding="utf-8") == signature
        )
        if not fresh:
            opens_section = index == 1 or sections[index - 1] != sections[index - 2]
            closes_section = index == len(beats) or sections[index - 1] != sections[index]
            fade_in = section_fade if (opens_section and section_fade > 0) else 0.0
            fade_out = section_fade if (closes_section and section_fade > 0) else 0.0
            if index == 1:
                fade_in = max(fade_in, 0.8)
            if index == len(beats):
                fade_out = max(fade_out, 1.2)
            render_beat(
                ffmpeg, root, data, beat, duration, width, height, fps, cursor,
                output, overlay_dir, (fade_in, fade_out),
            )
            signature_file.write_text(signature, encoding="utf-8")
        outputs.append(output)
        durations.append(duration)
        cursor += duration
        if index % 10 == 0 or index == len(beats) or index == 1:
            elapsed = time.perf_counter() - started
            print(f"Render progress: {index}/{len(beats)} beats  (last {elapsed:.1f}s)")

    concat_file = root / "render" / f"{stem}-concat.txt"
    concat_file.write_text(
        "".join(f"file '{path.resolve().as_posix()}'\n" for path in outputs), encoding="utf-8"
    )
    joined = root / "render" / f"{stem}-joined.mp4"
    run(
        [ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0",
         "-i", concat_file, "-c", "copy", joined],
        capture=True,
    )

    total_duration = sum(durations)
    output = root / f"{stem}.mp4"
    music_setting = str(setting(settings, "music", "") or "")
    ambience_setting = str(setting(settings, "ambience", "") or "")
    music = resolve_sfx(root, settings, music_setting) if music_setting else None
    ambience = resolve_sfx(root, settings, ambience_setting) if ambience_setting else None
    for candidate in (music, ambience):
        if candidate and not candidate.is_file():
            raise PipelineError(f"Missing audio bed: {candidate}")

    target_lufs = float(setting(settings, "target_lufs", -16))
    true_peak = float(setting(settings, "true_peak", -1.5))
    # A sample limiter alone overshoots after AAC; -0.5 dB of extra headroom
    # keeps measured true peak under the requested ceiling (verified -1.6 dBTP).
    ceiling = 10 ** ((min(true_peak, -2.0) - 0.5) / 20.0)
    limiter = f"alimiter=limit={ceiling:.4f}:attack=0.5:release=40:level=disabled"
    fade_out_start = max(0.0, total_duration - 3.0)

    if music or ambience:
        inputs = ["-i", str(joined)]
        chains: list[str] = ["[0:a]asplit=2[voice][sc]"]
        mix_labels = ["[voice]"]
        index = 1
        if music:
            inputs += ["-stream_loop", "-1", "-i", str(music)]
            volume = float(setting(settings, "music_volume", 0.07))
            chains.append(
                f"[{index}:a]atrim=0:{total_duration:.3f},volume={volume:.4f},"
                f"afade=t=in:st=0:d=2,afade=t=out:st={fade_out_start:.3f}:d=3[mus]"
            )
            if setting(settings, "music_duck", True):
                chains.append(
                    "[mus][sc]sidechaincompress=threshold=0.04:ratio=6:attack=20:release=420[musd]"
                )
            else:
                chains.append("[mus]anull[musd]")
            mix_labels.append("[musd]")
            index += 1
        if ambience:
            inputs += ["-stream_loop", "-1", "-i", str(ambience)]
            volume = float(setting(settings, "ambience_volume", 0.09))
            chains.append(
                f"[{index}:a]atrim=0:{total_duration:.3f},volume={volume:.4f},"
                f"afade=t=in:st=0:d=2,afade=t=out:st={fade_out_start:.3f}:d=3[amb]"
            )
            mix_labels.append("[amb]")
            index += 1
        chains.append(
            f"{''.join(mix_labels)}amix=inputs={len(mix_labels)}:duration=first:"
            f"dropout_transition=0:normalize=0[mixed]"
        )
        chains.append(
            f"[mixed]loudnorm=I={target_lufs}:TP={true_peak}:LRA=11,"
            f"{limiter}[a]"
        )
        command = [
            ffmpeg, "-y", "-hide_banner", "-loglevel", "error", *inputs,
            "-filter_complex", ";".join(chains),
            "-map", "0:v:0", "-map", "[a]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", str(AUDIO_RATE), "-ac", "2",
            "-t", f"{total_duration:.3f}", "-movflags", "+faststart", output,
        ]
    else:
        command = [
            ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-i", str(joined),
            "-c:v", "copy", "-af",
            f"loudnorm=I={target_lufs}:TP={true_peak}:LRA=11,{limiter}",
            "-c:a", "aac", "-b:a", "192k", "-ar", str(AUDIO_RATE), "-ac", "2",
            "-movflags", "+faststart", output,
        ]
    run(command, capture=True)
    write_timed_documents(root, beats, durations)
    actual = media_duration(ffmpeg, output)
    print(f"DONE: {output}")
    print(f"Duration: {actual:.2f} s ({actual/60:.2f} min)")
    print(f"Resolution: {width}x{height} at {fps} fps")
    print(f"Captions: {root / 'captions.srt'}")
    print(f"Chapters: {root / 'chapters.txt'}")
    return 0


# ---------------------------------------------------------------- qc


def command_qc(args) -> int:
    root, _data = load_project(args.project)
    ffmpeg = ffmpeg_executable()
    video = root / args.file
    if not video.is_file():
        raise PipelineError(f"Missing rendered file: {video}")
    qc_dir = root / "render" / "qc"
    qc_dir.mkdir(parents=True, exist_ok=True)
    duration = media_duration(ffmpeg, video)
    print(f"File: {video.name}  {duration:.2f} s  {video.stat().st_size/1e6:.1f} MB")

    for fraction in args.fractions:
        moment = max(0.2, duration * fraction)
        target = qc_dir / f"frame-{int(fraction*100):02d}.png"
        run(
            [ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-ss", f"{moment:.2f}",
             "-i", str(video), "-frames:v", "1", str(target)],
            capture=True,
        )
    print(f"Frames: {len(args.fractions)} written to {qc_dir}")

    loudness = subprocess.run(
        [ffmpeg, "-hide_banner", "-i", str(video), "-af", "loudnorm=print_format=json",
         "-f", "null", "-"],
        capture_output=True, text=True, errors="replace",
    )
    payload = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", loudness.stderr or "", re.S)
    if payload:
        try:
            values = json.loads(payload.group(0))
            print(
                f"Loudness: {float(values['input_i']):.1f} LUFS, "
                f"true peak {float(values['input_tp']):.1f} dBTP, "
                f"LRA {float(values['input_lra']):.1f}"
            )
        except (ValueError, KeyError):
            print("Loudness: unreadable")

    silence = subprocess.run(
        [ffmpeg, "-hide_banner", "-i", str(video), "-af",
         "silencedetect=noise=-45dB:d=0.9", "-f", "null", "-"],
        capture_output=True, text=True, errors="replace",
    )
    gaps = [float(value) for value in re.findall(r"silence_duration:\s*([0-9.]+)", silence.stderr or "")]
    if gaps:
        print(f"Dead air: {len(gaps)} gap(s) over 0.9 s, longest {max(gaps):.2f} s")
    else:
        print("Dead air: none over 0.9 s")

    stream = subprocess.run(
        [ffmpeg, "-hide_banner", "-i", str(video)],
        capture_output=True, text=True, errors="replace",
    )
    for line in (stream.stderr or "").splitlines():
        if "Stream #" in line:
            print("Stream:" + line.split("Stream #")[1].strip())
    return 0


# ---------------------------------------------------------------- doctor


def command_doctor(args) -> int:
    """Report whether this machine can actually render, and what is missing."""
    ok = True
    print(f"Python      {sys.version.split()[0]}  ({sys.executable})")
    if sys.version_info < (3, 10):
        print("            needs 3.10 or newer")
        ok = False

    for module in ("PIL", "numpy"):
        try:
            imported = __import__(module)
            version = getattr(imported, "__version__", "?")
            print(f"{module:<11} {version}")
        except ImportError:
            print(f"{module:<11} MISSING   run: {Path(sys.executable).name} -m pip install {module.lower()}")
            ok = False

    try:
        ffmpeg = ffmpeg_executable()
        result = subprocess.run([ffmpeg, "-version"], capture_output=True, text=True, errors="replace")
        first = (result.stdout or "").splitlines()[0] if result.stdout else "ffmpeg"
        print(f"FFmpeg      {first[:70]}")
        print(f"            {ffmpeg}")
        needed = ["zoompan", "xfade", "sidechaincompress", "loudnorm", "alimiter", "vignette", "noise"]
        listed = subprocess.run(
            [ffmpeg, "-hide_banner", "-filters"], capture_output=True, text=True, errors="replace"
        )
        text = listed.stdout or ""
        missing = [name for name in needed if f" {name} " not in text]
        if missing:
            print("            missing filters: " + ", ".join(missing))
            ok = False
        else:
            print("            all required filters present")
    except PipelineError as exc:
        print(f"FFmpeg      MISSING   {exc}")
        ok = False

    library = Path(__file__).resolve().parent.parent / "assets" / "sfx"
    catalog = load_catalog(Path("."))
    index = scan_sfx(Path("."), catalog, library) if catalog.get("roles") else {}
    roles = catalog.get("roles", [])
    print(f"SFX library {library}")
    print(f"            {sum(len(v) for v in index.values())} files, {len(index)}/{len(roles)} roles covered")
    structural = ["stinger-hit", "stinger-sub-drop", "transition-dip", "transition-whoosh", "amb-room-tone-night"]
    absent = [role for role in structural if role not in index]
    if absent:
        print("            structural roles missing: " + ", ".join(absent))
        ok = False

    fonts = sorted(Path("C:/Windows/Fonts").glob("*.ttf")) if Path("C:/Windows/Fonts").is_dir() else []
    print(f"Fonts       {len(fonts)} ttf files found")
    if not fonts:
        print("            no TrueType fonts; captions will fall back to the default")
        ok = False

    print("")
    print("READY" if ok else "NOT READY, fix the lines marked above")
    return 0 if ok else 1


# ---------------------------------------------------------------- cli


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build captioned rule-horror videos.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init = subparsers.add_parser("init", help="Create a new project scaffold")
    init.add_argument("project")
    init.add_argument("--title", required=True)
    init.add_argument("--style", default=DEFAULT_STYLE, choices=sorted(STYLES))
    init.add_argument("--brand", default="ORIGINAL SERIES")
    init.add_argument("--episode", default="NIGHT 01")
    init.add_argument("--force", action="store_true")
    init.set_defaults(func=command_init)

    audio = subparsers.add_parser("audio", help="Import and repair user narration")
    audio.add_argument("project")
    audio.add_argument("--source", required=True, help="folder of per-beat files, or one file")
    audio.add_argument("--max-pause", type=float, default=None)
    audio.add_argument("--target-peak", type=float, default=None)
    audio.add_argument("--denoise", action="store_true")
    audio.add_argument("--allow-proportional", action="store_true")
    audio.set_defaults(func=command_audio)

    narrate = subparsers.add_parser("narrate", help="Optional TTS narration")
    narrate.add_argument("project")
    narrate.add_argument("--engine", default="edge", choices=["edge", "sapi"])
    narrate.add_argument("--voice")
    narrate.add_argument("--rate")
    narrate.add_argument("--pitch")
    narrate.add_argument("--force", action="store_true")
    narrate.set_defaults(func=command_narrate)

    align = subparsers.add_parser("align", help="Split one continuous voiceover into beats")
    align.add_argument("project")
    align.add_argument("--file", required=True)
    align.add_argument("--engine", default="silence", choices=["silence", "whisper"])
    align.add_argument("--model", default="base")
    align.add_argument("--allow-proportional", action="store_true")
    align.set_defaults(func=command_align)

    validate = subparsers.add_parser("validate", help="Validate project structure and assets")
    validate.add_argument("project")
    validate.add_argument("--assets", action="store_true")
    validate.set_defaults(func=command_validate)

    timeline = subparsers.add_parser("timeline", help="Print the per-beat timeline")
    timeline.add_argument("project")
    timeline.set_defaults(func=command_timeline)

    sfx = subparsers.add_parser("sfx", help="Scan the SFX folder and place effects")
    sfx.add_argument("project")
    sfx.add_argument("--auto", action="store_true", help="Assign effects to beats")
    sfx.add_argument("--dry-run", action="store_true", help="Preview assignments only")
    sfx.add_argument("--clear", action="store_true", help="Remove all placed effects")
    sfx.add_argument("--force", action="store_true", help="Overwrite existing manual effects")
    sfx.set_defaults(func=command_sfx)

    render = subparsers.add_parser("render", help="Render preview or final MP4")
    render.add_argument("project")
    render.add_argument("--preview", type=int, metavar="BEATS")
    render.add_argument("--force", action="store_true")
    render.set_defaults(func=command_render)

    qc = subparsers.add_parser("qc", help="Extract frames and measure the rendered file")
    qc.add_argument("project")
    qc.add_argument("--file", default="final.mp4")
    qc.add_argument(
        "--fractions", type=float, nargs="+",
        default=[0.02, 0.12, 0.28, 0.45, 0.62, 0.8, 0.95],
    )
    qc.set_defaults(func=command_qc)

    doctor = subparsers.add_parser("doctor", help="Check the toolchain and the sound library")
    doctor.set_defaults(func=command_doctor)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if getattr(args, "preview", None) is not None and args.preview < 1:
        parser.error("--preview must be at least 1")
    try:
        return args.func(args)
    except KeyboardInterrupt:
        print("CANCELLED: interrupted; completed intermediates were kept")
        return 130
    except (PipelineError, audio_ops.AudioError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
