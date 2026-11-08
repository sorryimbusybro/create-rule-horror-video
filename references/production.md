# Production Reference

## Toolchain

| Requirement | Notes |
|---|---|
| Python 3.10+ | The interpreter that has Pillow and numpy — not necessarily `python` on PATH |
| Pillow | Captions, HUD, cards, scrims |
| numpy | Audio analysis and repair |
| FFmpeg with libx264, aac, zoompan, vignette, noise, sidechaincompress, loudnorm | Found on PATH or via `imageio-ffmpeg` |
| `edge-tts` | Optional, only for generated narration |

Check before promising a render:

```bash
<python> -c "import PIL, numpy; print('ok')"
<python> -c "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())"
```

If Pillow or FFmpeg is missing, ask before installing. Never silently drop captions or
substitute a worse voice.

On Windows, the bundled `python` may lack these packages while a system install has them.
Resolve the real interpreter path first, then use it consistently.

## Commands

```bash
P=<python>
S=<skill>/scripts/video_pipeline.py

$P $S doctor
$P $S init     <project> --title "<title>" [--style warm-flat|noir-line] [--brand B] [--episode E]
$P $S audio    <project> --source <folder|file> [--max-pause 0.55] [--denoise] [--allow-proportional]
$P $S align    <project> --file <single-voiceover> [--engine silence|whisper] [--model base]
$P $S narrate  <project> [--engine edge|sapi] [--voice ...] [--rate ...] [--pitch ...] [--force]
$P $S validate <project> [--assets]
$P $S timeline <project>
$P $S sfx      <project> [--auto] [--dry-run] [--clear] [--force]
$P $S render   <project> [--preview N] [--force]
$P $S qc       <project> [--file final.mp4] [--fractions 0.02 0.3 0.6 0.95]

O=<skill>/scripts/sfx_ops.py
$P $O scan   [<library>]
$P $O import [<library>] --from <folder> [--map role=file ...] [--dry-run]
$P $O check  [<library>]
```

`init` creates `project.json`, `palette.json`, `style-lock.txt`, and the asset and render
directories. It refuses to overwrite unless `--force`.

## Project schema (v2)

```json
{
  "version": 2,
  "title": "If Your Hall Light Ever Turns On by Itself... DON'T LOOK UP",
  "style": "warm-flat",
  "settings": {
    "width": 1920,
    "height": 1080,
    "fps": 30,
    "font": "",
    "voice_mode": "upload",
    "audio": {
      "max_pause": 0.55,
      "min_pause": 0.16,
      "target_peak_db": -3.0,
      "denoise": false,
      "room_tone_db": -58.0
    },
    "caption": { "uppercase": true, "max_chars": 64, "position": 0.88, "band": true },
    "grade": { "saturation": 1.04, "contrast": 1.05, "gamma": 0.99, "grain": 5, "vignette": 0.55 },
    "transition": { "section": 0.45, "beat": 0.0 },
    "clean_edges": { "top": 0, "bottom": 0.075, "left": 0, "right": 0.02 },
    "tail_padding": 0.16,
    "music": "assets/music/score.mp3",
    "music_volume": 0.07,
    "music_duck": true,
    "ambience": "assets/music/room-tone.wav",
    "ambience_volume": 0.09,
    "target_lufs": -16,
    "true_peak": -1.5,
    "brand": "ORIGINAL SERIES",
    "episode": "NIGHT 01"
  },
  "beats": [
    {
      "id": "001-hook",
      "section": "HOOK",
      "narration": "If your hall light ever turns on by itself, don't look up.",
      "caption": "If your hall light turns on, don't look up.",
      "image": "assets/images/hall-dark.png",
      "audio": "assets/audio/001-hook.wav",
      "camera": "push-in",
      "overlay": "",
      "accent": "ivory",
      "emphasis": ["light"],
      "hold": 0.0,
      "sfx": "",
      "sfx_gain": 0.5,
      "visual_prompt": "Wide hallway, amber line under the door, no character"
    }
  ]
}
```

### Settings that matter

| Key | Effect |
|---|---|
| `grade.*` | Per-plate colour and texture; keeps plates from different generations looking like one film |
| `clean_edges` | Crops a fraction off each side before scaling — removes generator watermarks |
| `transition.section` | Dip-to-black length at section changes; `0` disables |
| `tail_padding` | Silence added after each beat's narration; 0.16 is tight, 0.25 is relaxed |
| `caption.*` | Uppercase, character budget, vertical position, legibility band |
| `music_duck` | Sidechain compression so the score drops under speech |
| `sfx_library` | Override the shared effect library path; empty means `<skill>/assets/sfx` |
| `target_lufs` / `true_peak` | Final loudness pass |

### Beat fields

| Field | Required | Notes |
|---|---|---|
| `id` | yes | Filesystem-safe, zero-padded; also the audio filename |
| `section` | yes | `HOOK`, `SCENARIO`, `RULE 1`, `CASE STORY`, `REVEAL`, `TWIST` |
| `narration` | yes | Exact spoken words, no stage directions |
| `caption` | no | Defaults to narration; 6–14 words reads best |
| `image` | yes | Project-relative plate; many beats may share one |
| `audio` | yes | Filled by `audio`, `align`, or `narrate` |
| `camera` | no | `static`, `push-in`, `pull-back`, `drift-left`, `drift-right` |
| `overlay` | no | Centred text such as `RULE 1\nDON'T ANSWER` |
| `overlay_style` | no | `card` draws a bordered card with a scrim |
| `accent` | no | `ivory`, `amber`, `red` |
| `emphasis` | no | Words drawn in the accent colour inside the caption |
| `hold` | no | Extra seconds of silence after the beat |
| `sfx` / `sfx_gain` | no | Beat-level sound effect and its gain; `lib:name.wav` for a shared-library file |
| `visual_prompt` | no | Generation direction kept for reuse |

## Narration import

`audio --source <folder>` matches files to beats by ID prefix, then by sorted order. It
converts to 48 kHz mono, repairs each take, writes `assets/audio/<id>.wav`, and prints a
table with input length, output length, pauses capped, seconds removed, and words per
minute.

`audio --source <file>` (or `align --file`) treats one continuous file as the whole
voiceover. It splits at silences; if the segment count does not match the beat count it
stops and reports both numbers. `--allow-proportional` splits by word count instead, which
is approximate and can cut mid-word — use only when silence splitting fails.

`align --engine whisper` uses `faster-whisper` word timestamps to cut on real word
boundaries. It requires the package; ask before installing.

## Sound effects

`sfx <project>` reports which roles are populated, scanning the project folder first and the
shared library second. `--auto` assigns one effect per beat from the catalog, respecting
per-role cooldowns, and writes `sfx` plus `sfx_gain` into the project. `--dry-run` prints the
plan without writing. `--clear` removes every placement. The `at` column uses the same
narration + `tail_padding` + `hold` arithmetic as the render, so it matches the finished file.

Files are classified by the longest catalog term found in the filename, so
`foley-door-creak__02.wav` and `Door Creak 02.wav` both resolve to `foley-door-creak`.
Unmatched files are ignored rather than guessed at.

A beat referencing a shared-library file stores `lib:stinger-hit__01.wav`, which keeps the
project portable; `settings.sfx_library` relocates the library if needed.

Do not hand-rename a new download. `scripts/sfx_ops.py import` trims the lead-in, cuts the
tail, peak-normalises per category, converts to 48 kHz stereo and records the source in
`assets/sfx/library.json` and `licenses.txt`. `scan` reports role coverage; `check` flags
late starts, long silent tails and wrong levels.

Each beat's effect is mixed under its narration with `amix ... normalize=0`, so gain values
in the catalog are absolute relative to a −3 dBFS narration peak. Full role table, installed
files and mixing rules: [sfx-library.md](sfx-library.md).

## Rendering

Per beat: crop for clean edges → scale and crop to frame → camera move → grade → grain →
vignette → overlay (HUD, card, caption) → fades → H.264.

Then: concat → optional music and ambience with sidechain ducking → `loudnorm` → MP4 with
`+faststart`, plus `captions.srt` and `chapters.txt`.

Renders are cached by a signature of the beat, relevant settings, and asset timestamps.
Use `--force` after changing overlays, grade, or audio.

`--preview N` renders the first N beats at 960×540 with a fast preset. Preview and final
write to different directories, so a preview never poisons the final render.

### Render time

Expect roughly 2–3× realtime on a 4-core laptop at 1080p, so a 12-minute episode takes
about 25–35 minutes. Three things keep that down and should not be undone casually:

- Grade, grain and vignette are baked into the plate once per unique image, not applied
  per frame. Grain inside the encoder tripled render time and pushed bitrate past 40 Mbps.
- Beats with `camera: "static"` are flattened to a single frame in PIL and encoded as a
  still, skipping per-frame compositing entirely.
- The final pass copies video and only re-encodes audio. Music mixing does not touch video.

Preview first, iterate on a handful of beats, then render the full episode once.


## QC

`qc` writes frames to `render/qc/`, reports measured LUFS and true peak, lists dead-air
gaps over 0.9 s, and prints stream details.

Read the frames. Check: captions inside frame and not covering the threat, HUD not clipped,
card legible over the plate, no watermark, no malformed hands, consistent character, no
black or frozen frames.

## Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| `ModuleNotFoundError: PIL` | Wrong interpreter | Use the interpreter that has Pillow |
| `FFmpeg was not found` | Not on PATH | `pip install imageio-ffmpeg` |
| `Validation failed` on render | Missing image or audio | Run `validate --assets` |
| Beat renders are stale | Cached signature | `render --force` |
| Video shorter than audio | `tail_padding` too small | Raise to 0.25 |
| Captions cut off | Caption too long | Shorten `caption` or raise `max_chars` |
| Music too loud | Volume or ducking | Lower `music_volume`, keep `music_duck` |
| Render very slow | 1080p with grain on many beats | Preview first; render final once |
