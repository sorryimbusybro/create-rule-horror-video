#!/usr/bin/env python3
"""Narration analysis and repair.

Everything here works on mono float32 PCM in the range [-1, 1]. The pipeline
converts mp3/m4a/flac to 48 kHz mono WAV with FFmpeg first, then calls in.

The point of this module is that a human voiceover recorded at home or exported
from ElevenLabs is never clean enough to drop straight onto a timeline: it has
dead air at the head, long pauses between sentences, uneven level, clicks where
the speaker cut a breath, and a noise floor that jumps. These helpers measure
all of that and repair it deterministically instead of by ear.
"""

from __future__ import annotations

import math
import wave
from pathlib import Path

import numpy as np


class AudioError(RuntimeError):
    pass


# ---------------------------------------------------------------- wav io


def read_wav(path: str | Path) -> tuple[np.ndarray, int]:
    path = Path(path)
    try:
        with wave.open(str(path), "rb") as handle:
            frames = handle.getnframes()
            channels = handle.getnchannels()
            width = handle.getsampwidth()
            rate = handle.getframerate()
            raw = handle.readframes(frames)
    except (wave.Error, OSError) as exc:
        raise AudioError(f"Cannot read WAV {path}: {exc}") from exc
    if width == 2:
        data = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    elif width == 4:
        data = np.frombuffer(raw, dtype="<i4").astype(np.float32) / 2147483648.0
    elif width == 1:
        data = (np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
    else:
        raise AudioError(f"Unsupported sample width {width} in {path}")
    if channels > 1:
        data = data.reshape(-1, channels).mean(axis=1)
    return np.ascontiguousarray(data, dtype=np.float32), rate


def write_wav(path: str | Path, samples: np.ndarray, rate: int) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    clipped = np.clip(samples, -1.0, 1.0)
    payload = (clipped * 32767.0).astype("<i2").tobytes()
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(payload)


# ---------------------------------------------------------------- measurement


def db(value: float) -> float:
    return 20.0 * math.log10(max(value, 1e-9))


def envelope_db(samples: np.ndarray, rate: int, hop: float = 0.01) -> np.ndarray:
    """Per-frame RMS in dBFS, 10 ms frames by default."""
    frame = max(1, int(round(rate * hop)))
    count = int(math.ceil(len(samples) / frame))
    if count == 0:
        return np.zeros(0, dtype=np.float32)
    padded = np.zeros(count * frame, dtype=np.float32)
    padded[: len(samples)] = samples
    blocks = padded.reshape(count, frame)
    rms = np.sqrt(np.mean(blocks * blocks, axis=1) + 1e-12)
    return (20.0 * np.log10(rms + 1e-9)).astype(np.float32)


def auto_threshold(env: np.ndarray) -> float:
    """Pick a silence threshold from the file's own noise floor.

    Fixed thresholds fail on real uploads: a take with a music bed or a noisy
    room sits around -40 dBFS in the gaps, so -42 dB finds nothing. We measure
    the quiet tenth percentile and place the gate a fraction of the way up to
    the loud percentile, then clamp it to a sane band.
    """
    if env.size == 0:
        return -42.0
    floor = float(np.percentile(env, 10))
    loud = float(np.percentile(env, 95))
    span = max(0.0, loud - floor)
    return float(min(-30.0, max(-55.0, floor + 0.38 * span)))


def find_silences(
    samples: np.ndarray,
    rate: int,
    threshold_db: float | None = -42.0,
    min_duration: float = 0.22,
    hop: float = 0.01,
) -> list[tuple[float, float]]:
    """Return (start, end) seconds for every quiet run at least min_duration long."""
    env = envelope_db(samples, rate, hop)
    if threshold_db is None:
        threshold_db = auto_threshold(env)
    if env.size == 0:
        return []
    quiet = env < threshold_db
    silences: list[tuple[float, float]] = []
    index = 0
    while index < len(quiet):
        if not quiet[index]:
            index += 1
            continue
        start = index
        while index < len(quiet) and quiet[index]:
            index += 1
        span = (index - start) * hop
        if span >= min_duration:
            silences.append((start * hop, index * hop))
    return silences


def analyze(samples: np.ndarray, rate: int, threshold_db: float | None = -42.0) -> dict:
    duration = len(samples) / rate if rate else 0.0
    if threshold_db is None:
        threshold_db = auto_threshold(envelope_db(samples, rate))
    if not len(samples):
        return {
            "duration": 0.0,
            "peak_db": -120.0,
            "rms_db": -120.0,
            "speech_ratio": 0.0,
            "silences": [],
            "longest_silence": 0.0,
            "head_silence": 0.0,
            "tail_silence": 0.0,
        }
    peak = float(np.max(np.abs(samples)))
    rms = float(np.sqrt(np.mean(samples.astype(np.float64) ** 2)))
    silences = find_silences(samples, rate, threshold_db)
    speech = max(0.0, duration - sum(end - start for start, end in silences))
    return {
        "duration": duration,
        "peak_db": db(peak),
        "rms_db": db(rms),
        "speech_ratio": speech / duration if duration else 0.0,
        "silences": silences,
        "longest_silence": max((end - start for start, end in silences), default=0.0),
        "head_silence": silences[0][0] if silences and silences[0][0] < 0.02 else 0.0,
        "tail_silence": (
            duration - silences[-1][1]
            if silences and silences[-1][1] > duration - 0.02
            else 0.0
        ),
    }


# ---------------------------------------------------------------- repair


def _fade(samples: np.ndarray, rate: int, fade_in: float, fade_out: float) -> np.ndarray:
    out = samples.copy()
    n_in = min(len(out), int(rate * fade_in))
    if n_in > 1:
        out[:n_in] *= np.linspace(0.0, 1.0, n_in, dtype=np.float32)
    n_out = min(len(out), int(rate * fade_out))
    if n_out > 1:
        out[-n_out:] *= np.linspace(1.0, 0.0, n_out, dtype=np.float32)
    return out


def trim_edges(
    samples: np.ndarray,
    rate: int,
    threshold_db: float | None = -42.0,
    keep: float = 0.06,
) -> tuple[np.ndarray, float, float]:
    """Strip dead air before the first word and after the last one."""
    env = envelope_db(samples, rate)
    if env.size == 0:
        return samples, 0.0, 0.0
    if threshold_db is None:
        threshold_db = auto_threshold(env)
    loud = np.where(env >= threshold_db)[0]
    if loud.size == 0:
        return samples, 0.0, 0.0
    hop = 0.01
    start = max(0.0, loud[0] * hop - keep)
    end = min(len(samples) / rate, (loud[-1] + 1) * hop + keep)
    head_removed = start
    tail_removed = len(samples) / rate - end
    return samples[int(start * rate) : int(end * rate)], head_removed, tail_removed


def cap_pauses(
    samples: np.ndarray,
    rate: int,
    max_pause: float = 0.55,
    min_pause: float = 0.16,
    threshold_db: float | None = -42.0,
    fade_ms: float = 6.0,
) -> tuple[np.ndarray, dict]:
    """Shorten every internal pause longer than max_pause.

    Long gaps are the single biggest reason uploaded narration feels amateur.
    We cut in the middle of the quiet run, so the join lands on the noise floor,
    then micro-fade both sides so the cut cannot click.
    """
    duration = len(samples) / rate if rate else 0.0
    if threshold_db is None:
        threshold_db = auto_threshold(envelope_db(samples, rate))
    silences = find_silences(samples, rate, threshold_db, min_duration=max_pause + 0.01)
    stats = {
        "capped": 0,
        "removed": 0.0,
        "longest_before": max((e - s for s, e in silences), default=0.0),
        "longest_after": 0.0,
    }
    if not silences:
        return samples, stats

    fade = max(2, int(rate * fade_ms / 1000.0))
    pieces: list[np.ndarray] = []
    cursor = 0
    for start, end in silences:
        if start <= 0.02 or end >= duration - 0.02:
            continue
        target = max(min_pause, min(max_pause, end - start))
        head = samples[cursor : int(start * rate)]
        if head.size:
            head = head.copy()
            head[-min(fade, head.size) :] *= np.linspace(1.0, 0.0, min(fade, head.size))
            pieces.append(head)
        gap = np.zeros(int(target * rate), dtype=np.float32)
        pieces.append(gap)
        cursor = int(end * rate)
        stats["capped"] += 1
        stats["removed"] += (end - start) - target
    tail = samples[cursor:]
    if tail.size:
        tail = tail.copy()
        tail[: min(fade, tail.size)] *= np.linspace(0.0, 1.0, min(fade, tail.size))
        pieces.append(tail)
    merged = np.concatenate(pieces) if pieces else samples
    stats["longest_after"] = max(
        (e - s for s, e in find_silences(merged, rate, threshold_db, 0.22)), default=0.0
    )
    return merged.astype(np.float32), stats


def highpass(samples: np.ndarray, rate: int, cutoff: float = 75.0) -> np.ndarray:
    """First-order high pass; removes desk rumble and proximity boom."""
    if len(samples) < 4:
        return samples
    dt = 1.0 / rate
    rc = 1.0 / (2.0 * math.pi * cutoff)
    alpha = rc / (rc + dt)
    out = np.empty_like(samples)
    previous_in = float(samples[0])
    previous_out = 0.0
    for index in range(len(samples)):
        current = float(samples[index])
        previous_out = alpha * (previous_out + current - previous_in)
        previous_in = current
        out[index] = previous_out
    return out


def compress(
    samples: np.ndarray,
    rate: int,
    threshold_db: float = -20.0,
    ratio: float = 2.2,
    attack_ms: float = 8.0,
    release_ms: float = 140.0,
) -> np.ndarray:
    """Gentle downward compression so quiet words survive phone speakers."""
    if not len(samples):
        return samples
    env = np.abs(samples)
    attack = math.exp(-1.0 / (rate * attack_ms / 1000.0))
    release = math.exp(-1.0 / (rate * release_ms / 1000.0))
    smoothed = np.empty_like(env)
    level = 0.0
    for index in range(len(env)):
        value = env[index]
        coefficient = attack if value > level else release
        level = coefficient * level + (1.0 - coefficient) * value
        smoothed[index] = level
    level_db = 20.0 * np.log10(smoothed + 1e-9)
    over = np.maximum(0.0, level_db - threshold_db)
    gain_db = -over * (1.0 - 1.0 / ratio)
    return (samples * (10.0 ** (gain_db / 20.0))).astype(np.float32)


def normalize(samples: np.ndarray, target_db: float = -3.0) -> tuple[np.ndarray, float]:
    peak = float(np.max(np.abs(samples))) if len(samples) else 0.0
    if peak <= 1e-6:
        return samples, 0.0
    gain_db = target_db - db(peak)
    return (samples * (10.0 ** (gain_db / 20.0))).astype(np.float32), gain_db


def add_room_tone(
    samples: np.ndarray, rate: int, level_db: float = -58.0, seed: int = 7
) -> np.ndarray:
    """Bed of very quiet dark noise; hides cut points between repaired pauses."""
    if level_db <= -90 or not len(samples):
        return samples
    rng = np.random.default_rng(seed)
    noise = rng.normal(0.0, 1.0, len(samples)).astype(np.float32)
    # one-pole low pass to keep it dull and room-like rather than hissy
    alpha = 0.03
    out = np.empty_like(noise)
    acc = 0.0
    for index in range(len(noise)):
        acc = alpha * float(noise[index]) + (1.0 - alpha) * acc
        out[index] = acc
    peak = float(np.max(np.abs(out))) or 1.0
    out *= (10.0 ** (level_db / 20.0)) / peak
    return (samples + out).astype(np.float32)


def process_narration(
    samples: np.ndarray,
    rate: int,
    *,
    threshold_db: float | None = None,
    max_pause: float = 0.55,
    min_pause: float = 0.16,
    target_peak_db: float = -3.0,
    do_highpass: bool = True,
    do_compress: bool = True,
    room_tone_db: float = -58.0,
) -> tuple[np.ndarray, dict]:
    """Full repair chain for one narration take."""
    if threshold_db is None:
        threshold_db = auto_threshold(envelope_db(samples, rate))
    report: dict = {"input_duration": len(samples) / rate if rate else 0.0}
    report["gate_db"] = threshold_db
    work, head, tail = trim_edges(samples, rate, threshold_db)
    report["trimmed_head"] = head
    report["trimmed_tail"] = tail
    work, pause_stats = cap_pauses(
        work, rate, max_pause=max_pause, min_pause=min_pause, threshold_db=threshold_db
    )
    report.update(pause_stats)
    if do_highpass:
        work = highpass(work, rate, 75.0)
    if do_compress:
        work = compress(work, rate)
    work, gain = normalize(work, target_peak_db)
    report["gain_db"] = gain
    work = add_room_tone(work, rate, room_tone_db)
    work = _fade(work, rate, 0.012, 0.03)
    report["output_duration"] = len(work) / rate if rate else 0.0
    return work.astype(np.float32), report


def speech_window(samples: np.ndarray, rate: int, threshold_db: float | None = None) -> float:
    """Seconds between the first and last loud frame."""
    env = envelope_db(samples, rate)
    if threshold_db is None:
        threshold_db = auto_threshold(env)
    loud = np.where(env >= threshold_db)[0]
    if loud.size == 0:
        return 0.0
    return (loud[-1] - loud[0] + 1) * 0.01


def words_per_minute(words: int, seconds: float) -> float:
    if seconds <= 0:
        return 0.0
    return words / seconds * 60.0
