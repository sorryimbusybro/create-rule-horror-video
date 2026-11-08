# SFX Library

A downloaded pile of effects is useless until something knows which file belongs on which
beat. This skill ships a **role catalog** (`assets/sfx-catalog.json`), a **prepared shared
library** (`assets/sfx/`), a scanner, and an auto-placement command. Files carry role names;
the pipeline decides where they go and at what level.

## 1. Two folders

```
<skill>/assets/sfx/            shared library, used by every project
  stinger-hit__01.wav
  transition-dip__01.wav
  library.json                 what each file is, its trim, level and source
  licenses.txt                 provenance sheet — fill in before publishing

<project>/assets/sfx/          optional per-episode override
  foley-window-tap__01.wav     beats look here first
  catalog.json                 copied by `init`, editable per project
```

Resolution order: the project folder wins for any role it has a file for; every other role
falls back to the shared library. A project can point somewhere else entirely with
`settings.sfx_library`.

Beat references stay portable. A library file is stored as `lib:stinger-hit__01.wav`, not as
an absolute path, so a project folder can be moved or shared without breaking.

## 2. Naming contract

```
<role-id>__<variant>.<ext>
```

- `role-id` must be a catalog role, or contain one of its `match` terms. The **longest**
  matching term wins, so `texture-static__01` beats the generic `static`.
- `__01`, `__02` … are variants. With several, the pipeline picks one deterministically per
  beat: reproducible, but not the same sample twice.
- Matching is forgiving. `Door Creak 01.wav`, `door_creak_01.wav` and
  `foley-door-creak__01.wav` all classify correctly.

Files that match no role are ignored. That is deliberate: it stops a stray `boom-final.mp3`
from landing on a quiet line.

## 3. Installing a new pack

Do not hand-rename downloads. Run the importer — it trims the lead-in, removes the tail
silence, normalises the level per category, resamples to 48 kHz, and writes the manifest.

```bash
P=<python>
O=<skill>/scripts/sfx_ops.py

# see what a folder would become, nothing written
$P $O import --from "C:\Users\me\Downloads\sfx" --dry-run

# auto-detect roles from filenames and install
$P $O import --from "C:\Users\me\Downloads\sfx"

# force specific files onto specific roles
$P $O import --from "C:\Users\me\Downloads\sfx" \
  --map "foley-door-lock=lockingdoor1.wav" \
  --map "transition-dip=whoosh-cinematic-5.mp3"

# audit the library: levels, trims, missing roles
$P $O check
$P $O scan
```

What the importer does per file:

| Step | Detail |
|---|---|
| Decode | Any format FFmpeg reads, downmixed for analysis only |
| Trim head | Cut to 20 ms before the first frame within 45 dB of peak |
| Trim tail | Cut where the tail falls 26–34 dB below peak (category-dependent), +150 ms |
| Fade | 6 ms in, 120–450 ms out — no clicks at the join |
| Level | Peak-normalise to −3 dBFS (transitions, stingers), −6 (foley), −9 (beds) |
| Convert | 48 kHz, 16-bit, stereo PCM |
| Record | `library.json` entry + a line in `licenses.txt` |

Beds and textures (`texture-*`, `amb-*`) are treated as loops: only true digital silence is
stripped, so the file stays continuous.

## 4. What is installed

14 of 28 roles, and every structural one. Anything the format depends on is covered.

| File | Role | Length | Source |
|---|---|---:|---|
| `stinger-hit__01.wav` | rule reveal impact | 4.19 s | `stinger-hit.mp3` |
| `stinger-sub-drop__01.wav` | the twist | 2.59 s | **designed** from `stinger-hit` |
| `stinger-riser__01.wav` | build into a reveal | 2.11 s | `riser_649826.wav` (96 kHz source) |
| `stinger-heartbeat__01.wav` | case story | 21.39 s | `dragon-studio-heartbeat` |
| `transition-dip__01.wav` | section change | 1.81 s | `whoosh-cinematic-5` |
| `transition-whoosh__01.wav` | card in / out | 0.40 s | `simple-whoosh` |
| `transition-static-burst__01.wav` | tape splice | 0.85 s | **derived** from `texture-static` |
| `texture-static__01.wav` | analog unease bed | 5.59 s | `tv-static-noise` |
| `foley-door-creak__01.wav` | door moving | 2.61 s | `freesound door-creak` |
| `foley-door-lock__01.wav` | bolt, latch | 0.86 s | `soundbyter lockingdoor1` |
| `foley-light-switch__01.wav` | switch clicks | 0.27 s | `dragon-studio-light-switch` |
| `foley-footsteps-hall__01.wav` | approach | 4.03 s | `footsteps-on-wood` |
| `foley-footstep-single__01.wav` | one step behind you | 0.30 s | **derived** from the walk |
| `amb-room-tone-night__01.wav` | continuous bed | 44.81 s loop | `ambience-room-tone` |

Four files are designed or derived from the supplied material, not downloaded:

- `stinger-sub-drop` — a falling 92 → 27 Hz sine with the attack of the real cinematic hit,
  saturated for weight. Verified descending, −3 dBFS peak.
- `transition-static-burst` — 0.85 s cut of the static with a hard decay.
- `foley-footstep-single` — one step lifted out of the walk.
- `amb-room-tone-night` — the 2-minute source trimmed to a 45 s loop.

Replacing any of them is fine: drop a better file in with the same role and rerun
`sfx_ops.py import`.

## 5. Still worth downloading

The 14 open roles are colour, not structure. Add them when a script calls for them; in
priority order:

| Priority | Role | Search term |
|---|---|---|
| 1 | `foley-knob-turn` | "doorknob rattle slow" |
| 2 | `foley-keys-jingle` | "keys jingle hand" |
| 3 | `foley-window-tap` | "tap on glass" |
| 4 | `foley-phone-buzz` | "phone vibrate table" |
| 5 | `texture-electric-hum` | "fluorescent hum" |
| 6 | `foley-clock-tick` | "clock ticking room" |
| 7 | `amb-house-settle` | "house settling creak" |
| 8 | `foley-bed-sheet` | "bedsheet movement" |
| 9 | `foley-breath-shaky` | "shaky breath close" |
| 10 | `foley-whisper-unclear` | "whisper unintelligible" |
| 11 | `amb-rain-window` | "rain on window" |
| 12 | `amb-wind-low` | "low wind outside" |
| 13 | `foley-phone-notification` | "message ping" |
| 14 | `transition-reverse-swell` | "reverse cymbal swell" |

## 6. Where to download

| Source | Good for | Licence note |
|---|---|---|
| **Freesound.org** | Deepest catalog; filter by CC0 | Check each file; prefer CC0 |
| **Pixabay Audio** | Clean UI, no attribution | Pixabay licence, no resale as-is |
| **Mixkit** | Short, well-produced stingers | Free, no attribution |
| **Zapsplat** | Huge foley library | Free with attribution, or paid |
| **Sonniss GDC bundles** | Multi-GB professional libraries | Royalty-free, redistribution forbidden |
| **99Sounds** | Texture, static, tape, drones | Usually CC0 |
| **BBC Sound Effects** | Real rooms, doors, weather | Personal/education only — **not** for monetised uploads |
| **YouTube Audio Library** | Ambience and music beds | Free, some need attribution |

`licenses.txt` in the library lists every source file with blank `source:` and `licence:`
lines. Fill it in before publishing. If you monetise, the BBC personal-use library and
anything marked "editorial only" must not be in the mix.

## 7. Role catalog

`gain` is applied on top of the normalised file level. `cooldown` is the minimum seconds
before the same role may fire again.

| Role | Category | When it fires | Gain | Cooldown | In library |
|---|---|---|---:|---:|:--:|
| `transition-dip` | transition | First beat of a new section | 0.55 | 20 s | yes |
| `transition-whoosh` | transition | Card enters or leaves | 0.45 | 12 s | yes |
| `transition-static-burst` | transition | Analog splice | 0.34 | 25 s | yes |
| `transition-reverse-swell` | transition | Two seconds before the reveal | 0.42 | 60 s | — |
| `stinger-hit` | stinger | Rule card reveal | 0.50 | 15 s | yes |
| `stinger-sub-drop` | stinger | Final inversion, once only | 0.60 | 120 s | yes |
| `stinger-riser` | stinger | Last beats of a section | 0.40 | 60 s | yes |
| `stinger-heartbeat` | stinger | Case story, first two beats | 0.33 | 45 s | yes |
| `texture-static` | texture | Under a reveal | 0.20 | 30 s | yes |
| `texture-electric-hum` | texture | Light or appliance anomaly | 0.24 | 30 s | — |
| `foley-door-creak` | foley | Narration says door | 0.45 | 20 s | yes |
| `foley-door-lock` | foley | Narration says lock, bolt, chain | 0.50 | 20 s | yes |
| `foley-knob-turn` | foley | Narration says knob, handle | 0.45 | 25 s | — |
| `foley-light-switch` | foley | Narration says light, lamp, switch | 0.50 | 20 s | yes |
| `foley-keys-jingle` | foley | Narration says key | 0.40 | 30 s | — |
| `foley-footstep-single` | foley | Narration says step, behind | 0.40 | 15 s | yes |
| `foley-footsteps-hall` | foley | Narration says hallway, corridor | 0.34 | 30 s | yes |
| `foley-bed-sheet` | foley | Narration says bed, blanket, sheet | 0.34 | 25 s | — |
| `foley-phone-buzz` | foley | Narration says phone, vibrate | 0.45 | 30 s | — |
| `foley-phone-notification` | foley | Narration says message, notification | 0.40 | 30 s | — |
| `foley-breath-shaky` | foley | Narration says breath | 0.32 | 30 s | — |
| `foley-whisper-unclear` | foley | Narration says whisper, voice | 0.28 | 45 s | — |
| `foley-window-tap` | foley | Narration says window, glass, knock | 0.45 | 30 s | — |
| `foley-clock-tick` | foley | Narration says clock, minute | 0.24 | 40 s | — |
| `amb-room-tone-night` | ambience | Whole episode via `settings.ambience` | 0.18 | — | yes |
| `amb-house-settle` | ambience | Punctuates a quiet line | 0.22 | 45 s | — |
| `amb-rain-window` | ambience | Whole episode or a scene | 0.20 | — | — |
| `amb-wind-low` | ambience | Whole episode | 0.20 | — | — |

## 8. Placing them

```bash
P=<python>
S=<skill>/scripts/video_pipeline.py

# 1. see what the scanner found, project folder + shared library
$P $S sfx "<project>"

# 2. preview the plan without writing anything
$P $S sfx "<project>" --auto --dry-run

# 3. commit it
$P $S sfx "<project>" --auto

# overwrite manual choices
$P $S sfx "<project>" --auto --force

# remove everything and start again
$P $S sfx "<project>" --clear
```

Decision order, first match wins:

1. Beat already has a manual `sfx` → leave it alone (unless `--force`).
2. First beat of the episode → never scored; the hook should be clean.
3. `TWIST` or `REVEAL` first beat → `stinger-sub-drop`.
4. Beat has an `overlay` card → `stinger-hit` inside a rule, else `transition-whoosh`.
5. First beat of any other section → `transition-dip`.
6. First two beats of `CASE STORY` → `stinger-heartbeat`.
7. Narration word matches a role's `keywords` → that foley role.

Cooldowns are enforced globally across the episode. One effect per beat, maximum.

The `at` column prints the same clock the render uses — narration plus tail padding plus
`hold` — so a time printed there is the time in the finished file.

## 9. Mixing rules

- Effects sit **under** the voice. If a viewer notices the effect before the word, it is
  too loud — drop the gain by 0.1.
- The two seconds before the final command should be free of effects. Silence is the
  strongest transition available.
- Do not stack: one effect per beat. If a rule card needs a hit, the section dip belongs on
  the beat before it, not the same beat.
- Ambience is set once in `settings.ambience` and loops continuously; it does not restart
  per beat. Never place an ambience role per beat.
- `stinger-sub-drop` fires once. A second drop cancels the first.
- Replace a library file, then render with `--force`: beat caching keys on the beat data,
  not on the contents of the library.

## 10. Quality checks

Before rendering:

- `validate --assets` passes, so every referenced effect resolves.
- `sfx_ops.py check` reports no `head-silence`, `level` or `very quiet` flags.
- Play the beats around each card and section change: no double hit, no clipped tail.
- Confirm `licenses.txt` covers every file in the library.

After rendering:

- `qc` reports loudness; true peak must stay under −1 dBTP. The limiter is set with 0.5 dB
  of headroom for the AAC overshoot, so a −1.8 dBTP reading is expected.
- If the mix sounds crowded, remove every foley effect and keep only transitions and
  stingers. Rule videos survive on restraint.
