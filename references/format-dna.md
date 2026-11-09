# Reference Format DNA

## Observed source set

Analysis covered the four supplied MP4 files and transcripts, representative frames across each full timeline, and the public channel listing on 2026-11-08. View counts are only a historical snapshot, not a prediction.

| Reference | Duration | Rules | Structural payoff |
|---|---:|---:|---|
| Warm bed | 9:34 | 5 | Warmth means it is in bed; cold means it is standing elsewhere. |
| Sibling asks your name | 10:24 | 5 | A borrowed real name transfers the danger; identity and memory become unstable. |
| Repeated goodnight | 13:39 | 7 | The mother's voice is bait; the final voice may be the victim's own. |
| Face ID fails | 13:50 | 7 | The entity is learning the victim's face and gaining access, not merely following. |

All four are 16:9, 640×360 source video at 30 fps with H.264 video and AAC stereo audio. Render new projects at 1920×1080 rather than preserving the low source resolution. The complete warm-bed transcript runs at roughly 160–165 words per minute including its header; use 145–160 wpm as a comfortable production target, not a fixed rule.

The public channel listing showed nine videos built around the same title engine: familiar technology, pets, or family behavior becomes impossible, followed by a specific prohibition. Its visible tagline was “Every lullaby was a warning.” Do not reuse that branding.

## Narrative signature

1. **Immediate conditional threat:** The first sentence is the title premise and command. No logo animation, greeting, channel introduction, or backstory delays it.
2. **Rapid prohibition stack:** Two or three short commands create motion and urgency: do not answer, do not turn on the light, do not look back.
3. **Normal explanations eliminated:** The narrator explicitly rules out the dryer, a pet, a laptop, or another mundane cause. This makes the anomaly specific and prevents comment-section dismissal.
4. **Sensory confirmation:** Body warmth, a mattress slope, a voice without footsteps, an unblinking face, or a second digital face supplies evidence.
5. **Promise of a system:** The narrator announces five to seven rules. The numbered structure creates a measurable journey and open loop.
6. **Rules reveal mythology:** Each rule adds an instruction, a reason, a new sensory consequence, and sometimes an apparent escape that later fails.
7. **Case story:** A named child or ordinary person demonstrates the cost of breaking a rule. Specific objects and dates make it feel remembered rather than explained.
8. **Recontextualization:** The rules are revealed to contain, distract, or delay the entity rather than defeat it.
9. **Final inversion:** A previously safe or normal state becomes the worst state. The final command pays off the opening and often appears as a full-screen card.

## Retention mechanics

- The title creates the curiosity gap; the opening pays it immediately while opening a deeper question.
- Numbered rules give viewers progress markers and a reason to await the last rule.
- Each section answers one question and creates another. Avoid repeating the same threat with new adjectives.
- Apparent safety repeatedly becomes conditional: hard floors, silence, morning, a restored phone, or a cold bed.
- The final twist changes the meaning of earlier details instead of introducing an unrelated monster.
- There is no need to insert generic engagement requests. Let the story's open loop carry retention.

## Visual grammar

The bullets below describe the reference set, which is monochrome line art. These are
structural observations, **not** prompts. The skill draws its own frames in code with
three.js; no image model is involved. Two style presets ship with it (`warm-flat` and
`noir-line`), specified in [visual-system.md](visual-system.md); pick one per series and
never mix them.

Reference-set grammar, translated into scene-block terms:

- Pure or near-black background with abundant negative space → `noir-line` palette, `void` for full-screen cards, generous fog.
- Thin ivory-white outlines, flat charcoal fills, simple rounded characters, dot eyes, restrained faces → a pale-skinned figure on a dark wall, `expression: neutral | uneasy | absent`.
- One muted amber practical light, such as a bedside lamp or the gap under a door → every location owns one practical; animate it with `light.flicker`.
- Red reserved for the highest-stakes warning or final reveal → `accent: red` at most twice an episode.
- Wide master shots establish a room, medium shots show reactions, close-ups isolate objects → `camera.shot: wide | medium | close | insert`, plus `place: object` with an `item`.
- Full-screen rule cards and sparse typographic punches reset attention → `place: void` with `overlay` and `overlay_style: card`.
- A tiny original series label and episode mark create a surveillance-document feel → `settings.brand` and `settings.episode`, drawn by the type layer.
- Bottom-center uppercase captions, one or two short lines, inside a dark safe area → `caption` with `settings.caption.band`.
- Movement is economical: slow push-ins, lateral drift, blinking lights, a changed silhouette, a door opening, a shadow appearing → `camera.move`, `camera.handheld`, `light.flicker`, `light.pulse`, `entity`. The threat is one changed detail rather than constant animation.

## Translating a beat into a scene block

Write a `scene` object, not a sentence for a generator:

```json
{
  "place": "hallway",
  "seed": 7,
  "camera": { "shot": "wide", "move": "push", "amount": 0.18 },
  "figure": { "pose": "back-turn", "z": -3.2, "expression": "absent" },
  "light": { "flicker": 0.06 },
  "atmosphere": { "fog": 0.04 }
}
```

For an object insert, use `place: "object"`, `item: "phone"`, `camera.shot: "insert"`, and
omit `figure`. For a full-screen rule card, use `place: "void"`, put the words in `overlay`,
and set `overlay_style: "card"`. All text — captions, rule numbers, the HUD — is drawn by the
renderer's vector type layer; geometry never contains letters.

## Continuity rules

- Fix the palette (`style`) and the figure's `garment` colour before writing beats.
- Room geometry is code: one `place` is one builder. Reuse the same `place` and a seed
  family for a location and its geometry, door positions and props stay identical.
- The same `figure.js` code builds the character in every beat, so proportions cannot drift.
  Keep `skin`, `garment`, `trousers` and `height` constant.
- Change one meaningful variable per escalation: `light.flicker`, `atmosphere.fog`,
  `figure.expression`, `figure.pose`, `camera.shot`, or add an `entity`.
- Never bake words into geometry. Captions, messages, rule numbers, timecodes and the HUD
  are drawn by `overlay.js` on the 2D canvas.
- Inspect with `video_pipeline.py stills` before a full render; a bad spec value is a bug to
  fix, not a generation to retry.
- Do not copy the reference creator's name, exact title card, character design details, or signature final-frame layout.

## Audio direction

The references are narration-led. The narration source is normally the creator's own
recording or a paid voice model; synthetic TTS is a fallback. Whichever is used, deliver it
calmly and intimately rather than as a theatrical movie-trailer voice. Keep phonetic
phrasing natural, pause before an inversion, and avoid overdramatic shouting. Add restrained
room tone or low ambience and a few causally motivated effects. Silence immediately before
the last command is more effective than continuous music.

See [audio-playbook.md](audio-playbook.md) for import, pause repair, transitions and
loudness.


Target a final integrated loudness near -16 LUFS and true peak near -1.5 dBTP. These are delivery targets, not measured claims about the reference sources.
