"""Sound-effect library preparation for create-rule-horror-video.

Turns a folder of downloaded effects into a role-named, level-matched,
trimmed library that ``video_pipeline.py sfx`` can place automatically.

    python sfx_ops.py scan   <library>
    python sfx_ops.py import <library> --from DIR [--map role=file ...] [--auto]
    python sfx_ops.py check  <library>

Naming contract: ``<role>__<NN>.<ext>`` where ``role`` is an id from
``assets/sfx-catalog.json``. The pipeline matches on the longest catalog term
found in the filename, so the role id always wins over a generic synonym.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

import audio_ops as ao

AUDIO_EXT = {".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg", ".opus", ".wma", ".aiff", ".aif"}
TARGET_RATE = 48000

# category -> (trim mode, target peak dBFS, tail threshold below peak, fade out s)
CATEGORY_PROFILE = {
    "transition": ("one-shot", -3.0, 34.0, 0.22),
    "stinger": ("one-shot", -3.0, 26.0, 0.45),
    "foley": ("one-shot", -6.0, 34.0, 0.12),
    "texture": ("loop", -9.0, 0.0, 0.02),
    "ambience": ("loop", -9.0, 0.0, 0.02),
}
DEFAULT_PROFILE = ("one-shot", -3.0, 30.0, 0.2)


# ---------------------------------------------------------------- environment


def skill_root() -> Path:
    return Path(__file__).resolve().parent.parent


def ffmpeg_executable() -> str:
    executable = shutil.which("ffmpeg")
    if executable:
        return executable
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except (ImportError, RuntimeError):
        raise SystemExit("FFmpeg not found. Install FFmpeg or imageio-ffmpeg.")


def load_catalog(path: Path | None = None) -> dict:
    candidates = [
        path,
        skill_root() / "assets" / "sfx-catalog.json",
        Path.cwd() / "assets" / "sfx" / "catalog.json",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            try:
                data = json.loads(Path(candidate).read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(data.get("roles"), list):
                return data
    raise SystemExit("No sfx catalog found (assets/sfx-catalog.json).")


def roles_by_id(catalog: dict) -> dict[str, dict]:
    return {role["id"]: role for role in catalog["roles"]}


def normalise(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(value).lower()).strip("-")


def detect_role(filename: str, catalog: dict) -> str | None:
    """Longest catalog term contained in the filename wins."""
    stem = normalise(Path(filename).stem)
    best_role, best_length = None, 0
    for role in catalog["roles"]:
        for term in [role["id"]] + list(role.get("match", [])):
            key = normalise(term)
            if key and key in stem and len(key) > best_length:
                best_role, best_length = role["id"], len(key)
    return best_role


# ---------------------------------------------------------------- analysis


def probe_channels(ffmpeg: str, source: Path) -> int:
    result = subprocess.run(
        [ffmpeg, "-hide_banner", "-i", str(source)],
        capture_output=True, text=True, errors="replace",
    )
    match = re.search(r"Stream #\d+:\d+.*?: Audio: .*?, (\d+) Hz, ([^,]+),", result.stderr or "")
    layout = match.group(2).strip() if match else "stereo"
    return {"mono": 1, "stereo": 2, "2.1": 3, "3.0": 3, "4.0": 4, "5.1": 6, "7.1": 8}.get(layout, 2)


def decode_audio(ffmpeg: str, source: Path) -> tuple[np.ndarray, np.ndarray, int]:
    """Return (mono for analysis, all channels for peak, sample rate).

    Decoded as float32 on purpose: a lossy file can decode above 0 dBFS, and a
    PCM16 decode would clip that peak and understate the gain needed.
    """
    channels = probe_channels(ffmpeg, source)
    result = subprocess.run(
        [
            ffmpeg, "-v", "error", "-i", str(source), "-vn",
            "-f", "f32le", "-ac", str(channels), "-ar", str(TARGET_RATE), "pipe:1",
        ],
        capture_output=True, check=True,
    )
    data = np.frombuffer(result.stdout, dtype="<f4")
    usable = (len(data) // channels) * channels
    data = data[:usable].reshape(-1, channels).astype(np.float32)
    data = np.nan_to_num(data, nan=0.0, posinf=0.0, neginf=0.0)
    return data.mean(axis=1), data, TARGET_RATE


def trim_window(samples: np.ndarray, rate: int, mode: str, tail_drop_db: float) -> tuple[float, float, dict]:
    """Return (start, end, stats) seconds for the useful part of the file."""
    total = len(samples) / rate
    if total <= 0.02:
        return 0.0, total, {}

    if mode == "loop":
        # Only strip real dead air; a bed must stay continuous, so no
        # threshold-relative trimming here.
        env = ao.envelope_db(samples, rate, hop=0.01)
        audible = np.where(env > -60.0)[0]
        if audible.size == 0:
            return 0.0, total, {}
        start = max(0.0, float(audible[0]) * 0.01 - 0.02)
        end = min(total, float(audible[-1]) * 0.01 + 0.05)
        return start, end, {"mode": "loop"}

    env = ao.envelope_db(samples, rate, hop=0.01)
    peak_db = float(20 * np.log10(max(np.max(np.abs(samples)), 1e-9)))
    onset_thr = peak_db - 45.0
    above = env > onset_thr
    if not above.any():
        return 0.0, total, {}
    first = int(np.argmax(above))
    start = max(0.0, first * 0.01 - 0.02)

    # Last frame still carrying energy: a click ends at 0.2 s, a cinematic hit
    # rings for five. Using the first dip would cut every transient to nothing.
    tail_thr = peak_db - tail_drop_db
    audible = np.where(env > tail_thr)[0]
    audible = audible[audible >= first]
    end = float(audible[-1]) * 0.01 if audible.size else total
    end = min(total, end + 0.15)
    if end - start < 0.05:
        end = min(total, start + 0.05)
    return start, end, {"mode": "one-shot", "peak_db": peak_db, "onset": start}


def window_levels(multi: np.ndarray, mono: np.ndarray, rate: int, start: float, end: float) -> tuple[float, float]:
    """Peak across every channel, RMS from the mono sum."""
    a, b = int(start * rate), int(end * rate)
    segment = multi[a:b]
    flat = mono[a:b]
    if segment.size == 0 or flat.size == 0:
        return -120.0, -120.0
    peak = float(20 * np.log10(max(float(np.max(np.abs(segment))), 1e-9)))
    rms = float(20 * np.log10(max(float(np.sqrt(np.mean(flat.astype(np.float64) ** 2))), 1e-9)))
    return peak, rms


# ---------------------------------------------------------------- preparation


def prepare(
    ffmpeg: str,
    source: Path,
    target: Path,
    role: dict,
    dry_run: bool = False,
) -> dict:
    """Trim, level, convert and write one effect. Returns its manifest entry."""
    mode, target_peak, tail_drop, fade_out = CATEGORY_PROFILE.get(
        str(role.get("category", "")), DEFAULT_PROFILE
    )
    mono, multi, rate = decode_audio(ffmpeg, source)
    channels = multi.shape[1]
    start, end, stats = trim_window(mono, rate, mode, tail_drop)
    peak_db, rms_db = window_levels(multi, mono, rate, start, end)
    duration = max(0.02, end - start)
    fade_out = min(fade_out, duration * 0.4)
    gain_db = target_peak - peak_db

    entry = {
        "file": target.name,
        "role": role["id"],
        "category": role.get("category", ""),
        "source": source.name,
        "duration": round(duration, 3),
        "trim": [round(start, 3), round(end, 3)],
        "gain_db": round(gain_db, 2),
        "peak_db": target_peak,
        "rms_db": round(rms_db + gain_db, 2),
        "mode": mode,
        "channels": channels,
    }
    if dry_run:
        return entry

    target.parent.mkdir(parents=True, exist_ok=True)
    filters = ["afade=t=in:st=0:d=0.006"]
    if fade_out > 0:
        filters.append(f"afade=t=out:st={duration - fade_out:.4f}:d={fade_out:.4f}")
    filters.append(f"volume={gain_db:.2f}dB")
    filters.append(f"aresample={TARGET_RATE}")
    # `-ac 2` on a mono source applies a -3 dB pan law; duplicate the channel
    # instead so the measured peak survives the conversion.
    layout = ["-ac", "2"] if channels > 1 else []
    if channels == 1:
        filters.append("pan=stereo|c0=c0|c1=c0")
    command = [
        ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
        "-ss", f"{start:.4f}", "-t", f"{duration:.4f}", "-i", str(source),
        "-vn", "-af", ",".join(filters), *layout, "-ar", str(TARGET_RATE),
        "-c:a", "pcm_s16le", str(target),
    ]
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        target.unlink(missing_ok=True)
        detail = (exc.stderr or "").strip().splitlines()
        raise SystemExit(
            f"FFmpeg failed on {source.name}: {detail[-1] if detail else exc.returncode}"
        )
    return entry


def next_name(library: Path, role_id: str, suffix: str = ".wav") -> Path:
    existing = [
        p for p in library.glob(f"{role_id}__*{suffix}")
        if p.is_file()
    ]
    numbers = []
    for path in existing:
        match = re.search(r"__(\d+)", path.stem)
        if match:
            numbers.append(int(match.group(1)))
    return library / f"{role_id}__{(max(numbers) + 1 if numbers else 1):02d}{suffix}"


def load_manifest(library: Path) -> dict:
    path = library / "library.json"
    if path.is_file():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
    return {"version": 1, "files": []}


def save_manifest(library: Path, manifest: dict) -> None:
    manifest["updated"] = datetime.now().isoformat(timespec="seconds")
    manifest["files"].sort(key=lambda item: (item["role"], item["file"]))
    (library / "library.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )


# ---------------------------------------------------------------- commands


def command_scan(args) -> int:
    library = Path(args.library).expanduser().resolve()
    catalog = load_catalog(Path(args.catalog) if args.catalog else None)
    roles = roles_by_id(catalog)
    manifest = load_manifest(library)
    known = {item["file"] for item in manifest["files"]}

    files = sorted(
        p for p in library.glob("*")
        if p.is_file() and p.suffix.lower() in AUDIO_EXT
    ) if library.is_dir() else []

    print(f"LIBRARY {library}")
    if not files:
        print("  (empty)")
    counts: dict[str, int] = {}
    unknown: list[str] = []
    for path in files:
        role = detect_role(path.name, catalog)
        if not role:
            unknown.append(path.name)
            continue
        counts[role] = counts.get(role, 0) + 1

    covered = [role for role in roles if counts.get(role)]
    missing = [role for role in roles if not counts.get(role)]
    for category in ["transition", "stinger", "texture", "foley", "ambience"]:
        entries = [r for r in covered if roles[r].get("category") == category]
        if not entries:
            continue
        print(f"  {category}")
        for role in sorted(entries):
            mark = "" if all(
                item["file"] in known for item in manifest["files"] if item["role"] == role
            ) else "  (unprepared)"
            print(f"    {role:<26} {counts[role]} file(s){mark}")
    if unknown:
        print("  unmatched (no catalog role in the filename)")
        for name in unknown:
            print(f"    {name}")
    print(f"\nCOVERAGE {len(covered)}/{len(roles)} roles")
    if missing:
        print("MISSING " + ", ".join(sorted(missing)))
    return 0


def command_check(args) -> int:
    library = Path(args.library).expanduser().resolve()
    catalog = load_catalog(Path(args.catalog) if args.catalog else None)
    roles = roles_by_id(catalog)
    ffmpeg = ffmpeg_executable()
    files = sorted(
        p for p in library.glob("*")
        if p.is_file() and p.suffix.lower() in AUDIO_EXT
    )
    if not files:
        print("Nothing to check.")
        return 1
    print(f"{'file':<30}{'role':<24}{'dur':>7}{'peak':>8}{'rms':>8}  flags")
    print("-" * 84)
    problems = 0
    for path in files:
        role_id = detect_role(path.name, catalog)
        role = roles.get(role_id or "", {})
        mode, target_peak, tail_drop, _ = CATEGORY_PROFILE.get(
            str(role.get("category", "")), DEFAULT_PROFILE
        )
        mono, multi, rate = decode_audio(ffmpeg, path)
        start, end, _ = trim_window(mono, rate, mode, tail_drop)
        peak, rms = window_levels(multi, mono, rate, start, end)
        # Dead air is judged at -60 dBFS absolute, not relative to peak: a
        # designed fade-out must not read as a silent tail.
        env = ao.envelope_db(mono, rate, hop=0.01)
        audible = np.where(env > -60.0)[0]
        head = float(audible[0]) * 0.01 if audible.size else 0.0
        tail = len(mono) / rate - (float(audible[-1]) * 0.01 if audible.size else 0.0)
        flags = []
        if role_id is None:
            flags.append("no-role")
        if head > 0.15:
            flags.append(f"head-silence {head:.2f}s")
        if tail > 0.35:
            flags.append(f"tail-silence {tail:.2f}s")
        if abs(peak - target_peak) > 1.5:
            flags.append(f"level {target_peak - peak:+.1f}dB")
        if rms < -45:
            flags.append("very quiet")
        if flags:
            problems += 1
        print(
            f"{path.name[:29]:<30}{(role_id or '-'):<24}{len(mono) / rate:7.2f}"
            f"{peak:8.1f}{rms:8.1f}  {', '.join(flags)}"
        )
    print("-" * 84)
    print(f"{problems} file(s) with flags, {len(files)} total")
    return 0


def command_import(args) -> int:
    source_dir = Path(args.source).expanduser().resolve()
    library = Path(args.library).expanduser().resolve()
    if not source_dir.is_dir():
        raise SystemExit(f"Not a folder: {source_dir}")
    catalog = load_catalog(Path(args.catalog) if args.catalog else None)
    roles = roles_by_id(catalog)
    ffmpeg = ffmpeg_executable()

    explicit: dict[str, str] = {}
    for item in args.map or []:
        if "=" not in item:
            raise SystemExit(f"--map expects role=file, got {item!r}")
        role_id, filename = item.split("=", 1)
        if role_id not in roles:
            raise SystemExit(f"Unknown role {role_id!r}")
        explicit[filename.strip()] = role_id.strip()

    files = sorted(
        p for p in source_dir.iterdir()
        if p.is_file() and p.suffix.lower() in AUDIO_EXT
    )
    if not files:
        raise SystemExit(f"No audio files in {source_dir}")

    manifest = load_manifest(library)
    planned = []
    skipped = []
    for path in files:
        role_id = explicit.get(path.name) or explicit.get(path.stem)
        if role_id is None:
            role_id = detect_role(path.name, catalog)
        if role_id is None:
            skipped.append((path.name, "no matching role"))
            continue
        planned.append((path, roles[role_id]))

    if not planned:
        print("Nothing matched. Use --map role=filename for each file.")
        for name, reason in skipped:
            print(f"  {name}: {reason}")
        return 1

    print(f"{'source':<46}{'role':<24}{'trim':>14}{'dur':>7}{'gain':>8}")
    print("-" * 100)
    entries = []
    for path, role in planned:
        target = next_name(library, role["id"])
        entry = prepare(ffmpeg, path, target, role, dry_run=args.dry_run)
        entries.append(entry)
        trim = f"{entry['trim'][0]:.2f}-{entry['trim'][1]:.2f}"
        print(
            f"{path.name[:45]:<46}{role['id']:<24}{trim:>14}"
            f"{entry['duration']:7.2f}{entry['gain_db']:+8.1f}"
        )
    print("-" * 100)
    for name, reason in skipped:
        print(f"SKIP {name}: {reason}")

    if args.dry_run:
        print(f"DRY RUN: {len(entries)} file(s) would be written to {library}")
        return 0

    library.mkdir(parents=True, exist_ok=True)
    manifest["files"] = [
        item for item in manifest["files"]
        if item["file"] not in {entry["file"] for entry in entries}
    ] + entries
    save_manifest(library, manifest)
    write_licenses(library, manifest)
    print(f"IMPORTED: {len(entries)} file(s) -> {library}")
    print(f"MANIFEST: {library / 'library.json'}")
    return 0


def write_licenses(library: Path, manifest: dict) -> None:
    """Keep a provenance sheet next to the audio; never overwrite user notes."""
    path = library / "licenses.txt"
    if path.is_file() and "# EDITED" in path.read_text(encoding="utf-8", errors="replace"):
        return
    lines = [
        "# Sound-effect provenance",
        "# Fill in the licence for each source before publishing. Keep receipts.",
        "",
    ]
    seen: set[str] = set()
    for item in manifest["files"]:
        if item["source"] in seen:
            continue
        seen.add(item["source"])
        lines.append(f"{item['source']}")
        lines.append(f"  used as : {item['role']} -> {item['file']}")
        lines.append("  source  : ")
        lines.append("  licence : ")
        lines.append("")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--catalog", help="Path to sfx-catalog.json")
    sub = parser.add_subparsers(dest="command", required=True)

    default_library = str(skill_root() / "assets" / "sfx")

    scan = sub.add_parser("scan", help="Show role coverage of a library")
    scan.add_argument("library", nargs="?", default=default_library)
    scan.set_defaults(func=command_scan)

    imp = sub.add_parser("import", help="Prepare and install effects from a folder")
    imp.add_argument("library", nargs="?", default=default_library)
    imp.add_argument("--from", dest="source", required=True, help="Folder of downloaded effects")
    imp.add_argument("--map", action="append", metavar="ROLE=FILE", help="Force a file to a role")
    imp.add_argument("--dry-run", action="store_true")
    imp.set_defaults(func=command_import)

    check = sub.add_parser("check", help="Audit levels, trims and roles")
    check.add_argument("library", nargs="?", default=default_library)
    check.set_defaults(func=command_check)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
