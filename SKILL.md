---
name: create-rule-horror-video
description: Produce complete long-form rule-based horror videos end to end — viral title hooks, retention-engineered scripts, illustrated characters and locations, optional or user-supplied voiceover with pause repair, captions, music, transitions, and a rendered MP4. Use for "If X ever happens... DON'T Y" videos, analog horror, supernatural survival-rule stories, Lullorin-style channels, or any narrated horror episode built from numbered rules.
---

# Create Rule Horror Video

## Overview

Deliver a finished, original episode — not an outline, not a prompt pack. Reproduce the
retention mechanics of the reference format while keeping every story, character, line and
plate original.

Two hard rules:

1. **The voice belongs to the user.** Uploaded narration (recording or ElevenLabs) is the
   first-class path. Text-to-speech is an opt-in fallback, never a silent default.
2. **Characters are illustrated, never stick figures.** Every plate is a composed scene
   with a designed character, layered background, one light source and atmosphere. See
   [references/visual-system.md](references/visual-system.md).

And one on sound: **effects are placed, not sprinkled.** A prepared library ships with the
skill and every file carries a role name, a trimmed head, a matched level and a cooldown, so
placement is a command rather than a judgement call. See
[references/sfx-library.md](references/sfx-library.md).

Never promise views or virality. Optimise for curiosity, clarity and watch time.

## Required reading

| Before | Read |
|---|---|
| Ideation and hooks | [references/format-dna.md](references/format-dna.md), [references/story-engine.md](references/story-engine.md) |
| Any image work | [references/visual-system.md](references/visual-system.md) |
| Any audio work | [references/audio-playbook.md](references/audio-playbook.md) |
| Sound design | [references/sfx-library.md](references/sfx-library.md) |
| Building or rendering | [references/production.md](references/production.md) |

## Workflow

### 0. Confirm the machine can render

```bash
python "<skill>/scripts/video_pipeline.py" doctor
```

The last line must say `READY`. If it reports a missing module, filter or structural sound
role, fix that before writing a script the user cannot render.

### 1. Establish direction

Ask one compact question: **"Do you have an idea, or should I create one — and if I create
it, what genre or topic, or may I choose?"**

If they want suggestions, offer five original premises across different fears (domestic,
technology, liminal, folkloric, institutional), each with a title and one-sentence
premise. Let them pick.

Defaults unless told otherwise: 10–14 minutes, 16:9, English, PG-13, calm delivery.
Do not interrogate. Ask only what changes production.

### 2. Build the hook package

Present three genuinely different options, each with:

- A title in the form **If [familiar subject] Ever [specific anomaly]... [urgent action]**
- A 1–3 sentence opening that repeats and escalates the title immediately
- The central mystery: what the entity wants, and why the rules matter

Recommend one and explain its curiosity gap in a sentence. Get approval before writing the
full script.

### 3. Engineer the story

Complete the private logic in `story-engine.md` — entity, goal, perception, invitation,
why each rule works, how it adapts, early clues, case-story consequence, inversion. Rules
must follow from that logic; arbitrary rules read as generated.

Plant three early details that turn darker later. Include one case story mid-episode. End
on a callback that makes an ordinary condition frightening.

Write the narration to `script.md`. Target 145–160 words per minute. Present tense, second
person, short sentences, concrete objects.

### 4. Choose the voice path — ask, do not assume

Ask: **"Do you have a voiceover (recording or ElevenLabs), or should I generate one?"**

- **User has audio** → collect it, one file per beat, named by beat ID. This is preferred.
- **User wants to record** → give the recording brief from `audio-playbook.md` first.
- **User wants generated voice** → `narrate --engine edge` if `edge-tts` is installed;
  otherwise ask before installing, or use the offline SAPI script. State clearly that the
  result is synthetic and that the user can replace any beat later.
- **No audio yet** → build everything else, leave `audio` empty, and say so.

If they supply one continuous file instead of per-beat files, use `align` rather than
guessing boundaries.

### 5. Plan visuals before generating

Pick one style preset (`warm-flat` default, or `noir-line`) and keep it for the episode.
`init` writes `style-lock.txt` and `palette.json` — paste the lock into every request.

Plan 15–30 unique plates for a 10–14 minute episode:

- one establishing plate per location
- one medium per recurring action
- object inserts: phone, lock, key, photograph, door gap, bedding
- two or three entity variations
- one plate for the final inversion

Reuse plates deliberately. Change one variable per return — light, framing, a moved
object, a new shadow. The renderer adds motion, grade, grain and vignette, so a reused
plate never looks identical.

### 6. Produce the assets

**Characters.** Generate one character sheet first (four views, three expressions), inspect
it, then use it as an image reference for every scene. Reject any sheet with stick limbs,
malformed hands, a drifting garment colour, or the wrong head-to-body ratio.

**Plates.** Generate at 16:9, text-free, with the lower 22% dark and uncluttered. Inspect
every unique image at full size. Regenerate rather than "fix it in the edit".

**Cost.** Image generation consumes credits. Tell the user before generating a large batch,
and state the approximate count. Never generate 30 plates before the style is approved —
lock the look on one sheet and one scene first.

**Watermarks.** If the generator stamps a corner mark, set
`settings.clean_edges: { "bottom": 0.075, "right": 0.02 }` and re-render.

**Branding.** Create an original channel mark and episode label. Never place another
creator's name or logo in the output.

**Music.** Use licensed or generated music and note the licence. Keep it under speech.

### 7. Build the beat project

```bash
python "<skill>/scripts/video_pipeline.py" init "<project>" --title "<approved title>" --style warm-flat
```

Each beat is one caption and one narration unit, usually 8–22 words, 2–8 seconds. A
10–14 minute episode needs roughly 75–130 beats. Every beat gets an ID, section,
narration, caption, image, camera move, and — once audio exists — an audio path.

Optional beat fields that lift the edit:

- `hold`: extra silence after the beat (use before a consequence or the final command)
- `emphasis`: words drawn in the accent colour in the caption
- `overlay` / `overlay_style: "card"`: rule cards and final commands
- `sfx` / `sfx_gain`: a causally motivated sound
- `accent`: `ivory`, `amber`, `red` (red at most twice)

### 8. Import and repair the narration

```bash
python "<skill>/scripts/video_pipeline.py" audio "<project>" --source "<folder-or-file>"
python "<skill>/scripts/video_pipeline.py" align "<project>" --file "<single-file>"
```

Read the printed table. Every beat should land near the target pace; pauses over 0.55 s are
capped; dead air at head and tail is removed. If the numbers look wrong, adjust
`--max-pause`, `--denoise`, or `--target-peak` and re-run — do not hand-edit the WAVs.

### 9. Design the sound

A prepared library ships with the skill (`assets/sfx/`, 14 roles including every structural
one). Placement is one command and needs no files from the user:

```bash
python "<skill>/scripts/video_pipeline.py" sfx "<project>" --auto --dry-run
python "<skill>/scripts/video_pipeline.py" sfx "<project>" --auto
```

If the user has their own effects, never rename them by hand. Run the importer, which trims
the lead-in, cuts the tail, normalises the level per category, converts to 48 kHz and records
the source in `licenses.txt`:

```bash
python "<skill>/scripts/sfx_ops.py" import --from "<folder>" --dry-run
python "<skill>/scripts/sfx_ops.py" import --from "<folder>"
python "<skill>/scripts/sfx_ops.py" import --from "<folder>" --map "foley-door-lock=lockingdoor1.wav"
```

`sfx_ops.py scan` shows which of the 28 roles are covered; `check` flags files with a late
start, a long silent tail or a level that is off. Per-episode overrides go in
`<project>/assets/sfx/`, which beats the shared library for any role it contains.

`references/sfx-library.md` lists every role, its gain, its cooldown, the installed files and
the 14 roles still worth downloading. If the user has no effects at all, the video still
works — narration, music and silence are enough. Do not invent effect files.

Keep effects under the voice, one per beat, and leave the two seconds before the final
command empty.

### 10. Validate and preview

```bash
python "<skill>/scripts/video_pipeline.py" validate "<project>" --assets
python "<skill>/scripts/video_pipeline.py" render "<project>" --preview 10
```

Fix every error. Then inspect frames from the preview: caption fit, HUD position, character
continuity, grade, black levels, and whether the overlay collides with the subject.

### 11. Final render and QC

```bash
python "<skill>/scripts/video_pipeline.py" render "<project>"
python "<skill>/scripts/video_pipeline.py" qc "<project>"
```

Confirm duration, resolution, streams, loudness (−16 LUFS, true peak under −1.5 dBTP) and
dead air. Look at the extracted frames. Report exactly which checks were automated and which
were sampled — never claim to have watched or listened to a full video you only sampled.

### 12. Release package

Deliver:

- Final MP4 path, duration, resolution
- Three title options, chosen one first
- A description that preserves the mystery
- Three thumbnail directions: one familiar object, one impossible detail, ≤3 words
- Chapter timestamps from `chapters.txt`
- `script.md`, `captions.srt`, `project.json`, `style-lock.txt`
- Music and effect licence note — `assets/sfx/licenses.txt` in the library lists every source
- Any unresolved limitation

Do not upload, publish, or share without a separate explicit request.

## Quality bar

Revise until every answer is yes:

- Does the title promise something the first 15 seconds delivers?
- Is the entity's goal specific and internally consistent?
- Does every rule reveal new information rather than restate the threat?
- Are three payoff clues planted before the reveal?
- Is the voice the user's own, or clearly disclosed as synthetic?
- Does every plate have a designed character in a layered location?
- Are captions readable at phone size and clear of the threat?
- Do section transitions land on a visual change, not mid-sentence?
- Is the audio free of clicks, dead air, and clipped words?
- Is anything copied from the reference channel — names, rules, scenes, branding?

## Resources

- `references/format-dna.md` — measured patterns from the reference set
- `references/story-engine.md` — premises, hooks, rule logic, retention spine, rubric
- `references/visual-system.md` — character construction, palettes, prompt blocks, defects
- `references/audio-playbook.md` — voice routing, recording and ElevenLabs briefs, repair, transitions, loudness
- `references/sfx-library.md` — effect roles, installed files, importer, auto-placement, mixing levels
- `references/production.md` — project schema and full CLI reference
- `scripts/video_pipeline.py` — init, audio import, optional TTS, align, validate, timeline, sfx, render, qc
- `scripts/audio_ops.py` — silence detection, pause capping, levelling, room tone
- `scripts/sfx_ops.py` — effect importer: trim, level, convert, rename, manifest, audit
- `assets/sfx-catalog.json` — the role catalog copied into every project
- `assets/sfx/` — the prepared shared library (14 roles) plus `library.json` and `licenses.txt`
- `scripts/tts_sapi.ps1` — offline Windows voice, optional manual fallback
