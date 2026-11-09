# Visual System

**No images are generated.** Every pixel is drawn by code. A headless Chrome or Edge builds
each beat as a three.js scene from geometry and lights, renders it to a canvas, composites
the grade, grain, vignette and type layer in 2D, and encodes H.264 through WebCodecs. There
is no image model, no plate file, no reference sheet and no prompt to paste anywhere.

The practical consequences are worth stating up front:

- A scene costs CPU time, not credits or tokens. Change it as often as you like.
- Continuity is structural. The same `place`, `seed` family and `garment` colour produce the
  same room and the same person in beat 1 and beat 120. There is no drift to correct.
- Anything you want on screen must be built in `scripts/scene/src/`. Adding a new prop or
  location means adding geometry, not writing a better sentence.

`doctor` checks the whole chain. Run it before promising a render.

## How one frame is made

```
scene block (JSON)
  -> builders.js      14 procedural locations: walls, floor, doors, props, practical light
  -> figure.js        character and optional entity, both built from tapered geometry
  -> runtime.js       subject-driven camera, fill light, rim light, fog, exposure
  -> WebGL render     ACES filmic tone mapping, soft shadows, sRGB output
  -> 2D composite     saturate / contrast / brightness, vignette, film grain
  -> overlay.js       HUD, caption, rule card — exact vector typography
  -> VideoEncoder     avc1.640028 Annex B H.264 streamed back to the Node driver
  -> FFmpeg           -c:v copy into a per-beat MP4
```

If the browser has no WebCodecs H.264 support, `runtime.js` falls back to streaming JPEG
frames; `visual_ops.py` muxes those with `libx264`. Either way the output is the same clip.

Frames are deterministic functions of time. `renderAt(t)` positions the camera, flickers the
light, moves the dust motes and sways the figure from `t` alone, so a still at the mid-point
of a beat matches the middle of the rendered clip.

## Two style presets

Pick one per series and never mix them inside an episode. `init --style <preset>` writes
`palette.json` and `scene-guide.txt` into the project.

| Preset | Look | Use when |
|---|---|---|
| `warm-flat` | Warm dusk interior, deep plum shadows, one amber practical, saturated garment | Default. Most readable at phone size |
| `noir-line` | Near-black rooms, cold key light, one amber source, heavy grain | Analog-horror channels |

| Token | `warm-flat` | `noir-line` | Use |
|---|---|---|---|
| `background` | `#1B1418` | `#050506` | clear colour and fog colour |
| `wall` | `#6B5852` | `#1A1C1D` | walls and doors |
| `shadow` | `#3A2E30` | `#0C0D0E` | floor and shadow planes |
| `ink` | `#241C22` | `#0A0B0C` | trim, frames, silhouettes |
| `ivory` | `#F4EAD8` | `#E4E1D7` | captions, paper, highlights |
| `amber` | `#E3A94E` | `#BE893E` | the practical light, rule cards |
| `garment` | `#E05F38` | `#2A2D30` | the character's clothing only |
| `sage` | `#7C9270` | `#5B6160` | plants, one secondary prop |
| `red` | `#D6402F` | `#BE2D28` | final warning only, at most twice an episode |

The character's skin is **not** the palette ink. It defaults to pale `#F4EDE0`. That is a
deliberate contrast decision: a dark head on a dark wall disappears, while pale skin, hands
and arms read clearly against a black environment. Keep it pale. The clothing stays as
specified by the style.

## Scene block reference

Every beat has a `scene` object. `visual_ops.normalise_scene()` validates and fills defaults,
so unknown values fall back rather than crashing a long render — but `validate` flags them.

```json
{
  "place": "hallway",
  "seed": 7,
  "depth": 11,
  "camera": {
    "shot": "medium",
    "move": "push",
    "amount": 0.24,
    "handheld": 0.2,
    "fov": 38,
    "fraction": 0.5,
    "distance": 4.2,
    "lift": 0.18,
    "height": 1.6,
    "pos": [0, 1.6, 4],
    "target": [0, 1.4, 0]
  },
  "figure": {
    "pose": "stand", "expression": "absent",
    "x": 0, "y": 0, "z": -3.2,
    "facing": 0, "height": 1.68,
    "garment": "#E05F38", "skin": "#F4EDE0", "trousers": "#4A3B52",
    "rim": 1.4, "rimX": 0.8, "sway": 0.0
  },
  "entity": { "pose": "stand", "x": 0.8, "y": 0, "z": -5.5, "facing": 0, "height": 2.15 },
  "light": { "flicker": 0.08, "pulse": 0, "off": false, "color": "#F2C079", "intensity": 6 },
  "atmosphere": { "fog": 0.035 },
  "fill": 0.26,
  "halo": 1,
  "item": "phone"
}
```

| Field | Meaning |
|---|---|
| `place` | Which procedural location to build. See the list below. |
| `seed` | Seeds prop placement, branches, motes and clutter. Stable per beat; reuse a seed family for one room. |
| `depth` | Corridor/room length where the location uses it. |
| `camera.shot` | `wide`, `medium`, `close`, `insert` — sets how much of the frame the subject fills. |
| `camera.move` | `static`, `push`, `pull`, `drift-left`, `drift-right`, `rise`, `crane`. |
| `camera.amount` | Travel over the beat, default `0.22`. Small values read as dread, not motion. |
| `camera.handheld` | Camera shake, `0`–`1`. A little goes a long way. |
| `camera.fov` / `fraction` / `distance` / `lift` / `height` | Manual overrides for the framing maths. Leave these alone unless a still proves you need them. |
| `camera.pos` / `target` | Absolute camera override; bypasses subject-driven framing entirely. |
| `figure` | Omit it for an empty room. Presence of `figure` switches framing to subject-driven. |
| `entity` | A tall near-black silhouette built by the same figure code with `silhouette: true` and a `hidden` face. Use sparingly. |
| `light` | `flicker` and `pulse` animate the strongest practical in the room; `off` kills it; `color` recolours it; `intensity` sets the base. |
| `atmosphere.fog` | `FogExp2` density, default `0.035`. Above `0.09` the room vanishes. |
| `fill` | Camera-side fill light strength, default `0.26`. Raise it if a foreground reads pure black. |
| `halo` | Multiplier for the soft light halos on practicals. `0` disables them. |
| `item` | For `place: "object"`: `phone`, `key`, `photo`, `lock`, `paper`. |

`scene` may also be a plain string (`"hallway"`), which becomes `{ place: "hallway" }`.
`camera.move` may sit on the beat instead of inside the scene. Legacy names `push-in`,
`pull-back`, `pan-left`, `pan-right` are aliased to the current moves.

## Locations

`visual_ops.py places` prints the live list. All 14 are built in `scripts/scene/src/builders.js`:

`hallway`, `bedroom`, `kitchen`, `living`, `bathroom`, `basement`, `attic`, `stairwell`,
`forest`, `road`, `field`, `void`, `object`.

Each builder returns a `THREE.Group` with an authored `userData.camera` anchor and, for
interiors, `userData.bounds` — the room shell. The runtime clamps the camera inside those
bounds so you never see the black back face of a wall. A few notes:

- `hallway` builds a lit corridor with skirting, door frames, spaced practical bulbs and a
  doorway offset to the right so its light strip does not cut through the character's head.
- `void` is an empty dark field used for full-screen rule cards. Put the text in `overlay`.
- `object` frames a single prop with an `insert` shot; it is the only place where the
  subject is 0.42 units tall, so do not add a `figure` there.
- `forest`, `road` and `field` are outdoors; fog does most of the depth work.

## Character construction

`figure.js` builds a real 3D body — no billboards, no stick lines.

| Part | Construction |
|---|---|
| Head | Sphere, pale skin, no neck; overlaps the torso slightly |
| Torso | Tapered rounded form, shoulders at `0.375 × H`, narrowed waist |
| Arms | Tapered filled cylinders, radii `0.105 × H` to `0.07 × H`, spherical joints and hands |
| Legs | Tapered filled cylinders, dark trousers `#4A3B52` |
| Garment | One saturated colour from the palette; a seam or fold gives the body volume |
| Eyes / mouth | Small flat shapes on the face plane; two almonds, pupils, one mouth stroke |

**Contrast logic.** The figure reads the lightness of its own skin material with
`getHSL()`. When the skin is pale (luma > 0.55) the eyes, pupils and mouth switch to dark
ink `#221A20`; with dark skin they would be ivory. This is why the pale default keeps a
legible face on a black wall without any extra lighting.

**Face vocabulary** (`figure.expression`):

| Expression | Eyes | Mouth |
|---|---|---|
| `neutral` | almonds, centred pupils | soft curve |
| `uneasy` | pupils shifted toward one side | flat line |
| `wrong` | pupils fixed forward | wide crescent, too high |
| `afraid` | tall almonds, small pupils | small open oval |
| `absent` | solid almonds, no pupils | none |
| `hidden` | none | none (used for the entity) |

The last two do the horror work. A face that stops reacting is more frightening than a
monster.

**Poses** (`figure.pose`): `stand`, `sit`, `kneel`, `lie`, `walk`, `crouch`, `reach`,
`point`, `head-tilt`, `back-turn`. `facing` is degrees of Y rotation. `sway` adds a slow
breathing motion over the beat; keep it near `0` for a held, uncanny stillness.

`figure.garment`, `skin`, `trousers`, `rim`, `rimX` are per-beat overrides. Set them once
for the episode and leave them — the figure must read as one person.

## Camera and framing

Framing is computed from the **subject**, not from a fixed camera distance:

```
distance = (subjectHeight / fraction) / (2 * tan(fov / 2))
```

`fraction` is how much of the frame height the subject should occupy:

| Shot | Fraction |
|---|---|
| `wide` | 0.30 |
| `medium` | 0.50 |
| `close` | 0.74 |
| `insert` | 0.92 |

The camera looks at `figure.y + height × focusY`, where `focusY` is 0.54 normally and 0.58
for a close-up. When the beat has an `overlay` rule card, the target is lifted by
`height × 0.16` so the character sits below the card instead of behind it. Captions live at
`caption.position` (default 0.88) in the lower safe area.

If the computed camera would land outside an interior, `userData.bounds` clamps it and the
FOV is widened (up to 56°) to keep the subject the size the shot asked for. This is why
`close` shots do not put the camera inside the character's chest and why a small bedroom
still frames correctly.

Camera moves are eased linearly across the beat's duration:

| Move | Effect |
|---|---|
| `static` | Nothing; the scene still has light flicker, motes and sway |
| `push` / `pull` | Scale the camera-to-target offset by `1 ∓ amount × progress` |
| `drift-left` / `drift-right` | Lateral slide proportional to offset length |
| `rise` | Slow vertical lift |
| `crane` | Lift combined with a slight push |
| `handheld` | Two sine components on position and a tiny roll; independent of the move |

## Light, atmosphere and film finish

- Each location owns one **practical** light (a bulb, lamp or door gap). It is the strongest
  point/spot in the group; `runtime.js` finds it and uses it as the key. Shadow maps are
  1024² with `near 0.3 / far 16`, which keeps the depth buffer from burning out.
- A **fill** light sits just behind the camera. Its intensity scales with the square of the
  camera distance (`clamp(base × d², 1.5, 42)`), so a distant wide shot is not pitch black
  and a close shot is not blown out.
- A cool **rim** light behind the figure separates pale skin from a dark wall.
- `light.flicker` modulates the key with three summed sines (11.3, 4.1 and 27.7 Hz) so it
  never looks like a regular strobe. `light.pulse` is a slow 1.1 Hz breath.
- `FogExp2`, dust motes (`THREE.Points`) and light halos supply depth. Motes drift as a
  function of time, so they animate without any frame-to-frame state.
- The 2D pass applies `ctx.filter = saturate(...) contrast(...) brightness(...)` from
  `settings.grade`, then a radial vignette and a single `createPattern` grain fill. Grain is
  one `fillRect`, not dozens of draw calls — that change alone cut frame time sharply.
- Exposure is `0.95` with ACES filmic tone mapping and sRGB output.

Override the grade per project in `settings.grade`: `saturation`, `contrast`, `brightness`,
`grain`, `vignette`. All five are read by `visual_ops.driver_settings()`.

## Type layer

`overlay.js` draws all text on the 2D canvas after the 3D render, so typography is exact at
any resolution and no text is ever baked into geometry.

- **HUD**: small `brand` label top left, `episode` top right. Keep the top 8% quiet.
- **Caption**: `beat.caption` (falls back to narration), uppercase if
  `settings.caption.uppercase`, positioned by `settings.caption.position`, with an optional
  dark legibility band. `emphasis` words are drawn in the beat's `accent` colour.
- **Rule card**: `beat.overlay` with `overlay_style: "card"`. The card starts at 12% from
  the top, wraps `\n` into paragraphs, and caps itself at three lines with an automatic
  font-size reduction. It never covers the subject's face because the camera lifts its
  target whenever an overlay is present.

Use `void` + `overlay` for full-screen rule cards. Use `red` at most twice per episode.

## Planning a sequence

A 10–14 minute episode has 75–130 beats but only a handful of rooms. That is fine: the
renderer rebuilds the room per beat, so repetition is a framing and lighting question, not
an asset question.

- One `wide` establishing beat per location, usually with no `figure`.
- `medium` for reactions; change `figure.expression` and `figure.pose` as the rules tighten.
- `close` for the moment the entity is understood, not before.
- `insert` / `object` for phones, keys, locks, photographs and paper.
- `void` with a card at each rule heading and at the final command.
- `entity` in two or three beats only; it is most effective when it is an extra shape in
  the dark of an otherwise familiar room.
- Change **one** variable per return to a location: light state, shot, a moved figure, a
  new pose, denser fog. The last beat inverts a normal condition rather than introducing a
  new monster.

Prefer a single idea per beat. If two things compete, split into two beats — it costs
nothing but render time.

## Inspect with stills

```bash
python "<skill>/scripts/video_pipeline.py" stills "<project>" --beats 10
python "<skill>/scripts/visual_ops.py" places
python "<skill>/scripts/visual_ops.py" still --scene scene.json --out preview.png
```

`stills` writes one PNG per beat at the mid-point of its duration. Open them full size. The
renderer is code, so a defect is a bug or a bad spec value, never a random generation
artifact — fix the `scene` block or the builder and re-run.

| Defect | Cause | Fix |
|---|---|---|
| Completely black frame | Camera clamped outside the room shell, or key light disabled | Check `light.off`; use a wider `shot`; verify `userData.bounds` for that place |
| Character invisible against the wall | Skin overridden to a dark colour | Restore pale `skin` (default `#F4EDE0`) or raise `fill` |
| Room blown out / flat white slabs | Fill or key intensity far too high | Lower `fill`, lower `light.intensity`; exposure is `0.95` |
| Camera inside the character's head | Hand-set `camera.distance` or `camera.pos` too close | Remove the overrides and let `shot` compute the distance |
| Rule card sits over the face | Hand-set `camera.target` overriding the card lift | Remove the target override, or set `camera.lift` |
| Caption cut off | Caption longer than `settings.caption.max_chars` | Shorten the caption or raise the limit |
| Grain / banding in dark areas | `grade.grain` or `vignette` too strong for the encoder | Reduce `grade.grain`; `vignette` default is 0.45–0.62 |
| Hard shadow rectangle across the scene | Shadow camera `far` too large | Shadow near/far are `0.3 / 16`; do not widen without a reason |
| Bright "smear" beams across the room | Light shaft planes | These were removed; do not re-add transparent shaft quads |
| Same room looks like a different room | Different `seed` each visit | Reuse a seed family per location, change only light/shot/pose |

## Performance notes

- The browser starts once per batch; every beat reuses the same WebGL context. Do not
  launch one browser per beat.
- H.264 chunks are POSTed to the Node driver and appended to an elementary stream; the
  driver's `taskkill /T` shutdown takes the whole browser tree down so long runs do not
  leak processes.
- Clip caching is a SHA-256 of the normalised scene, text, duration, size, fps, style and
  relevant settings. Change any of those and only that beat re-renders. `render --force`
  bypasses it.
- Grade and grain are one filter plus one pattern fill per frame — cheap enough to keep
  in-page. The final FFmpeg pass copies video and only re-encodes audio.
- Preview at 960×540 first. Render the full episode once the stills and the ten-beat
  preview are right.
