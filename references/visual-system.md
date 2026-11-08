# Visual System

The pictures carry half the retention. A plain figure on an empty background reads as
unfinished and viewers leave before the first rule lands. Every plate must be a
**composed illustration**: a designed character, a layered location, one light source,
and atmosphere.

Two presets ship with the skill. Pick one per series and never mix them inside an episode.

| Preset | Look | Use when |
|---|---|---|
| `warm-flat` | Illustrated flat-vector storybook, warm dusk, cute character in an unsettling world | Default for new channels; closest to the supplied reference frame |
| `noir-line` | Monochrome ivory line art on near-black, one amber practical light | Closest to the Lullorin-style references |

`init --style <preset>` writes `style-lock.txt` and `palette.json` into the project.
Paste `style-lock.txt` into **every** image request. Consistency comes from repeating the
same lock, not from hoping the model remembers.

## Warm Flat construction

### Canvas and layers

Build every plate as a stack, back to front. A plate missing layers 1–4 looks cheap.

1. **Sky / wall field.** Vertical gradient, two or three stops, warm at the horizon and
   deep plum above. Never a flat fill.
2. **Distance.** City skyline, tree line, corridor depth, or fence silhouette at 30–45%
   opacity, slightly hazier than the foreground.
3. **Architecture.** Window frames, door frames, shelves, skirting, floor plane. Thin
   dark mullions against the bright field give instant depth.
4. **Props.** Three to six readable objects: book spines, a lamp, a mug, a plant, a chair,
   a coat hook. Colour them from the accent range, not random hues.
5. **Character.** One figure, off-centre on a third.
6. **Light.** One warm key with soft bloom, a shadow wedge on the floor or wall, gentle
   falloff. Light direction stays the same across the episode.
7. **Atmosphere.** Eight to twenty dust motes, very soft vignette, fine grain.

### Character proportions

Measured in head-heights (H = head diameter). Total height ≈ 3.1 H.

| Part | Specification |
|---|---|
| Head | Perfect circle, 1.0 H, deep charcoal-plum `#241C22`, no neck |
| Torso | Rounded trapezoid, 1.15 H tall, shoulders 0.85 H wide, saturated garment colour |
| Arms | Tapered capsules, 1.1 H long, 0.20 H thick at shoulder tapering to 0.13 H |
| Hands | Circles of 0.16 H, same fill as head |
| Legs | Tapered capsules, 0.95 H long, 0.22 H thick |
| Shoes | Rounded rectangles, 0.30 H long, 0.12 H tall |
| Eyes | Two white almonds, each 0.30 H wide, 0.18 H apart |
| Pupils | Small dark ovals, 0.09 H, sitting slightly high |
| Mouth | One curved stroke or filled crescent, 0.34 H wide |

Rules that separate a designed character from a stick figure:

- Limbs are **filled tapered shapes**, never single lines.
- The torso overlaps the head slightly; there is no visible neck.
- Clothing has at least one seam or fold, so the body reads as a body.
- Hands are shapes, not dots at the end of a line.
- The character occupies 25–45% of frame height. A tiny figure on a huge empty field is
  a composition error, not minimalism.

### Face vocabulary

Keep the face to eyes and mouth. Emotion is carried by shape, not detail:

| Expression | Eyes | Mouth |
|---|---|---|
| Neutral | almonds, pupils centred | short soft curve |
| Uneasy | pupils shifted toward the threat, brows absent | flat line |
| Smiling wrong | pupils fixed forward, no eye movement | wide crescent, too high |
| Afraid | tall almonds, pupils small | small open oval |
| Absent | solid white almonds, no pupils | none |

The last two do the horror work. A cute face that stops reacting is more frightening than
a monster.

### Palette

| Token | Hex | Use |
|---|---|---|
| `ink` | `#241C22` | head, dark furniture, silhouettes |
| `wall` | `#6B5852` | walls, doors, muted architecture |
| `shadow` | `#3A2E30` | shadow planes, floor |
| `ivory` | `#F4EAD8` | captions, eyes, paper, highlights |
| `amber` | `#E3A94E` | practical light, rule cards, warmth |
| `garment` | `#E05F38` | the character's clothing only |
| `sage` | `#7C9270` | plants, one secondary prop |
| `red` | `#D6402F` | final warning only, at most twice per episode |

Sky peach `#F6D8A6` and sun glow `#FFEDBE` belong to the light, not to objects.

### Horror modulation

The style is warm and cute; the fear comes from three adjustments:

1. **Desaturate 10–20%** and push shadows toward plum, so the warmth reads as dusk rather
   than daylight.
2. **Empty the middle.** Leave one large area with nothing in it, and put the anomaly
   there — an open door, a chair facing the wall, a shape at the window.
3. **Break the light logic once.** A lamp that is off but still casting light, a shadow
   pointing at the wrong wall, a window showing a sky that does not match the room.

## Noir Line construction

Same layering, different rendering: near-black field, even-weight ivory contour lines,
flat charcoal fills, a single amber practical light, no colour except one red accent at
the reveal. Character is an egg-shaped head with dot eyes, narrow torso, tapered limbs,
no fingers. Keep line weight constant across the episode.

## Prompt assembly

Every plate is five blocks, in this order. Keep the wording identical between shots; only
the `SCENE` block changes.

```text
[STYLE LOCK]      exact text from style-lock.txt, first line
[CHARACTER]       exact text from style-lock.txt, second block
[SCENE]           location, action, framing, what changed since the last plate
[COMPOSITION]     16:9, character on the left/right third, lower 22% dark and clear
[NEGATIVE]        exact text from style-lock.txt, third block
```

Example `SCENE` block:

> The same character stands at the end of a hallway, back to the viewer, facing a door
> that is open exactly one hand's width. A thin amber line of light falls across the
> floor from the gap. No other light source. Medium-wide shot, character on the right
> third, a long empty hallway filling the left two thirds.

Do not ask the model for text, numbers, labels, or signage. Rule cards, timecodes and
captions are drawn by the renderer, where typography is exact.

## Character sheet workflow

1. Generate one reference sheet: four full-body views (front, three-quarter, side, back)
   plus three head expressions, on a plain deep-plum field, no text.
2. Inspect it. Reject and regenerate if limbs are sticks, the head is the wrong size, the
   garment colour drifts, or hands are malformed.
3. Save it as `assets/character/character-sheet.png` and treat it as canon.
4. For every subsequent plate, pass the sheet as an image reference (image-to-image) with
   high input fidelity, and repeat the `CHARACTER` block in the prompt.
5. Keep the same seed or reference across an episode. If a plate drifts, regenerate it
   from the sheet rather than from the previous plate, so errors do not accumulate.

## Plate budget and reuse

A 10–14 minute episode needs **15–30 unique plates**, not one per sentence.

- One wide establishing plate per location.
- One medium per recurring action.
- Object inserts for phones, locks, keys, photographs, door gaps, bedding.
- Two or three entity variations: a changed silhouette, an extra shape in the dark, a
  face that has lost its pupils.
- One final plate for the inversion.

Reuse is correct. Change one variable per return: light state, framing, a moved object, a
new shadow. The renderer adds motion, grade, grain and vignette, so a reused plate never
looks identical twice.

## Composition rules

- Character on a third, never dead centre, unless the beat is a deliberate stare.
- Keep the bottom 22% dark and uncluttered; captions live there.
- Leave the top 8% quiet; the HUD sits there.
- One idea per plate. If two things compete, split into two beats.
- Horizontals and verticals should be true; a tilted frame reads as an accident.

## Generated-image defects and fixes

| Defect | Fix |
|---|---|
| Stick limbs, wire arms | Repeat "filled tapered shapes, never single thin sticks"; regenerate |
| Corner watermark or logo | Set `settings.clean_edges` (`bottom: 0.075, right: 0.02`) and re-render |
| Text or letters baked into the plate | Add "no text, no letters, no numbers" first in the negative; regenerate |
| Head too small / body too tall | Restate the head-height ratio; regenerate from the character sheet |
| Flat empty background | Name the layers explicitly: sky, distance, architecture, props |
| Garment colour drifts | Quote the hex in every prompt; do not describe it as "orange" |
| Extra fingers or fused hands | Simplify to "small circular hands, no fingers" |
| Inconsistent room geometry | Keep a single establishing plate and derive inserts from it |

Never ship a plate you have not looked at full size. Malformed hands and stray text are
the two defects that get a video mocked in the comments.
