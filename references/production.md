# Production Reference

## Toolchain

| Requirement | Notes |
|---|---|
| Python 3.10+ | The interpreter that has numpy — not necessarily `python` on PATH |
| numpy | Audio analysis and repair |
| Pillow | Installed for the QC/utility path; the scene renderer itself draws in-browser |
| FFmpeg with libx264, aac, sidechaincompress, loudnorm, alimiter, amix, afade | Found on PATH or via `imageio-ffmpeg` |
| Node.js 20+ | Runs `scripts/scene/driver.mjs`. Override with `RULE_HORROR_NODE` |
| Headless Edge or Chrome | Launched once per batch with a CDP debugging port. Override with `RULE_HORROR_BROWSER` |
| three.js | Vendored at `scripts/scene/vendor/three.module.min.js` — no npm install, no network |
| `edge-tts` | Optional, only for generated narration |

Check before promising a render:

```bash
<python> scripts/video_pipeline.py doctor
<python> scripts/visual_ops.py doctor
python -c "import numpy; print('ok')"
```

`doctor` prints Python, numpy, Pillow, the FFmpeg path and its required filters, the sound
library coverage, Node, the browser, the vendored three.js and the driver. The last line
must say `READY` / `SCENES READY`. If Pillow or FFmpeg is missing, ask before installing.
Never silently drop captions or substitute a worse voice.

On Windows, the bundled `python` may lack these packages while a system install has them.
Resolve the real interpreter path first, then use it consistently.

**No image tool is needed.** The toolchain has no image model, no API key and no asset
directory for pictures. All visuals come from the three.js scene renderer.

## Commands

```bash
P=<python>
S=<skill>/scripts/video_pipeline.py
V=<skill>/scripts/visual_ops.py

$P $S doctor
$P $S init     <project> --title "<title>" [--style warm-flat|noir-line] [--brand B] [--episode E]
$P $S audio    <project> --source <folder|file> [--max-pause 0.55] [--denoise] [--allow-proportional]
$P $S align    <project> --file <single-voiceover> [--engine silence|whisper] [--model base]
$P $S narrate  <project> [--engine edge|sapi] [--voice ...] [--rate ...] [--pitch ...] [--force]
$P $S validate <project> [--assets]
$P $S timeline <project>
$P $S sfx      <project> [--auto] [--dry-run] [--clear] [--force]
$P $S stills   <project> [--beats N] [--width 1920] [--height 1080]
$P $S render   <project> [--preview N] [--force]
$P $S qc       <project> [--file final.mp4] [--fractions 0.02 0.3 0.6 0.95]

$P $V doctor
$P $V places
$P $V still --scene <scene.json> --out <preview.png> [--width 1920] [--height 1080]

O=<skill>/scripts/sfx_ops.py
$P $O scan   [<library>]
$P $O import [<library>] --from <folder> [--map role=file ...] [--dry-run]
$P $O check  [<library>]
```

`init` creates `project.json`, `palette.json`, `scene-guide.txt`, the asset directories
(`assets/audio`, `assets/music`, `assets/sfx`) and the render directories (`render/beats`,
`render/clips`, `render/streams`, `render/stills`, `render/qc`). It refuses to overwrite
unless `--force`.

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
    "grade": { "saturation": 1.06, "contrast": 1.06, "brightness": 1.06, "grain": 5, "vignette": 0.45 },
    "transition": { "section": 0.45, "beat": 0.0 },
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
      "scene": {
        "place": "hallway",
        "seed": 1,
        "camera": { "shot": "wide", "move": "push", "amount": 0.2 },
        "light": { "flicker": 0.05 },
        "atmosphere": { "fog": 0.035 }
      },
      "audio": "assets/audio/001-hook.wav",
      "overlay": "",
      "accent": "ivory",
      "emphasis": ["light"],
      "hold": 0.0,
      "sfx": "",
      "sfx_gain": 0.5
    }
  ]
}
```

The complete `scene` field reference, camera maths and character construction are in
[visual-system.md](visual-system.md). `scene-guide.txt` in each project lists the live
vocabulary.

### Settings that matter

| Key | Effect |
|---|---|
| `grade.*` | `saturation`, `contrast`, `brightness`, `grain`, `vignette` applied in the browser's 2D composite |
| `style` | `warm-flat` or `noir-line`; selects the palette used by every location and the figure |
| `transition.section` | Dip-to-black length at section changes; `0` disables |
| `tail_padding` | Silence added after each beat's narration; 0.16 is tight, 0.25 is relaxed |
| `caption.*` | Uppercase, character budget, vertical position, legibility band |
| `font` | Optional TTF/OTF loaded into the browser as `EpisodeFont` for the type layer |
| `music_duck` | Sidechain compression so the score drops under speech |
| `sfx_library` | Override the shared effect library path; empty means `<skill>/assets/sfx` |
| `target_lufs` / `true_peak` | Final loudness pass |

### Beat fields

| Field | Required | Notes |
|---|---|---|
| `id` | yes | Filesystem-safe, zero-padded; also the audio and clip filename |
| `section` | yes | `HOOK`, `SCENARIO`, `RULE 1`, `CASE STORY`, `REVEAL`, `TWIST` |
| `narration` | yes | Exact spoken words, no stage directions |
| `caption` | no | Defaults to narration; 6–14 words reads best |
| `scene` | yes | Scene block or a bare place string; see visual-system.md |
| `audio` | yes | Filled by `audio`, `align`, or `narrate` |
| `overlay` | no | Centred text such as `RULE 1\nDON'T ANSWER`; `\n` starts a new paragraph |
| `overlay_style` | no | `card` draws a bordered card with a scrim |
| `accent` | no | `ivory`, `amber`, `red` |
| `emphasis` | no | Words drawn in the accent colour inside the caption |
| `hold` | no | Extra seconds of silence after the beat |
| `sfx` / `sfx_gain` | no | Beat-level sound effect and its gain; `lib:name.wav` for a shared-library file |
| `camera` | no | Legacy shorthand for `scene.camera.move`; prefer the scene block |

`validate` rejects an unknown `place`, camera move, pose or expression, a missing `scene`
block, a missing section, an invalid or duplicate ID and a missing audio path.

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

`render` does three things in order.

**1. One clip per beat.** `visual_ops.render_clips()` normalises every scene block, hashes
it with the beat text, duration, size, fps, style and relevant settings, and skips any clip
whose marker matches. For pending beats it writes a jobs file and calls
`node scripts/scene/driver.mjs`. The driver starts a local static server on 127.0.0.1,
launches headless Edge/Chrome once, attaches over CDP, and calls `window.RH.renderClip()`
for each job. In-page WebCodecs encodes `avc1.640028` Annex B H.264 and POSTs chunks back;
the driver appends them to `render/streams/<label>/<id>.h264`. If H.264 is unsupported the
page POSTs JPEG frames into an `.mjpeg` file instead. FFmpeg muxes either stream into
`render/clips/<label>/<id>.mp4` with `-c:v copy` (or `libx264 -crf 18` for the fallback).

The browser draws everything: geometry, lighting, grade, grain, vignette, HUD, caption and
rule card. No intermediate PNGs are written for video frames.

**2. One MP4 per beat with audio.** `mux_beat()` marries each clip to its repaired narration
and optional effect. Audio gets short fade-in/out, `apad` + `atrim` to the exact beat
duration, and `amix ... normalize=0` with the effect. Video is stream-copied unless a
section fade is needed — fades force one `libx264 -crf 19` re-encode, the only place pixels
are touched after the renderer finishes.

**3. Assembly.** Concat with `-c copy`, then optional music and ambience beds with
sidechain ducking, `loudnorm=I=-16:TP=-1.5:LRA=11`, and an `alimiter` with 0.5 dB of extra
headroom so the AAC encode stays under the true-peak ceiling. Final output is `final.mp4`
with `+faststart`, plus `captions.srt` and `chapters.txt`.

`--preview N` renders the first N beats at 960×540. Preview and final write to different
`render/clips/<label>` and `render/beats/<label>` directories, so a preview never poisons
the final render. `stills` renders one full-size PNG per beat into `render/stills/` — use it
to inspect the art before committing to a long render.

### Render time

Cost is dominated by WebGL frames: `duration × fps` frames per beat. Keep these properties
in mind:

- The browser is launched once per batch, not once per beat. Do not restructure the driver
  to spawn a browser per job.
- One browser renders all pending beats in a single process; cached beats are skipped
  entirely by their SHA-256 marker.
- The final FFmpeg passes copy video. Only beats with a section fade re-encode.
- Grain is a single `createPattern` + `fillRect`; grade is one `ctx.filter` assignment. Do
  not replace these with per-pixel JavaScript loops.
- `render_clips` streams encoded chunks straight to disk; frames never pile up in memory.

Preview first, iterate on a handful of beats with `stills`, then render the full episode once.

## QC

`qc` writes frames to `render/qc/`, reports measured LUFS and true peak, lists dead-air
gaps over 0.9 s, and prints stream details.

Read the frames. Check: captions inside frame and not covering the threat, HUD not clipped,
rule card legible and clear of the face, the pale character readable against the wall, the
room lit and layered, no black or frozen frames, and continuous geometry across returns to
the same location.

## Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| `ModuleNotFoundError: numpy` | Wrong interpreter | Use the interpreter that has the packages |
| `FFmpeg was not found` | Not on PATH | `pip install imageio-ffmpeg` |
| `SCENES NOT READY` | Node, browser, three.js or driver missing | Install Node 20+, Edge/Chrome; restore `scripts/scene/vendor/three.module.min.js` |
| `renderer produced no video stream` | Browser crashed or WebCodecs produced nothing | Re-run with `RH_DEBUG=1`; check the browser path; look at the JSON error events |
| Browser processes leak | Driver killed without its tree | `driver.mjs` uses `taskkill /T /F` on every exit path; do not bypass `shutdown()` |
| `Validation failed` on render | Missing audio, or an unknown place/move/pose/expression | Run `validate --assets`; check `visual_ops.py places` |
| Black frames | Camera outside the room shell, or `light.off` | Widen the shot, remove `light.off`, inspect a still |
| Character invisible | Dark skin override, or `fill` too low | Restore pale skin, raise `fill` |
| Beat renders are stale | Cached signature | `render --force` |
| Video shorter than audio | `tail_padding` too small | Raise to 0.25 |
| Captions cut off | Caption too long | Shorten `caption` or raise `max_chars` |
| Music too loud | Volume or ducking | Lower `music_volume`, keep `music_duck` |
| Render very slow | 1080p at high fps, many uncached beats | Preview first; let the cache work; render final once |
