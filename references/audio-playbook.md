# Audio Playbook

The voice is the product. Text-to-speech is a fallback, not the plan.

Default assumption: **the user has a voiceover, or wants to record one.** Ask once, early,
and route to the right path. Never silently substitute a synthetic voice.

## 1. Route the voice

| Situation | Path | Command |
|---|---|---|
| Has a recording (mic, phone, DAW export) | Import and repair | `audio --source <folder>` |
| Has an ElevenLabs or other TTS export | Import and repair | `audio --source <folder>` |
| Has one continuous file, not per-beat | Split, then repair | `align --file <file>` |
| Wants the skill to speak it | Optional TTS | `narrate --engine edge` |
| Has no audio and no budget | TTS, disclosed | `narrate`, then `audio` |

Ask which of these applies. If the user says "whatever you think", prefer the uploaded
path and offer TTS only as a stopgap.

## 2. Recording brief

Send this before they record. It prevents most repair work.

- Quiet room, soft furnishings, door closed. No fan, fridge, or keyboard within a metre.
- Mic 15–20 cm from the mouth, slightly off-axis, on a stand.
- Peak between −12 and −6 dBFS. Never touch 0.
- One file per beat, named exactly like the beat ID (`003-rule1.wav`).
- Leave half a second of silence at the head and tail of every take.
- Read the line twice if unsure; keep both, let the import pick.
- Calm and low. Do not perform fear; describe it.

## 3. ElevenLabs brief

- Model: a multilingual or narration model; stability mid-high, similarity mid.
- Output: MP3 192 kbps or WAV 44.1/48 kHz, one file per beat, beat ID as filename.
- Generate a single voice and reuse its ID for the whole series.
- Regenerate any take that clips, swallows a consonant, or ends mid-breath.
- Do not clone a real person's voice without their written consent.

## 4. What the repair actually does

`audio --source <folder>` converts everything to 48 kHz mono and then, per beat:

| Step | Purpose | Default |
|---|---|---|
| High pass | Removes desk rumble and proximity boom | 60–75 Hz |
| Adaptive gate | Finds each file's own noise floor instead of a fixed threshold | 10th percentile + 38% of range |
| Edge trim | Cuts dead air before the first word and after the last | keeps 60 ms |
| Pause cap | Shortens internal pauses so the read has momentum | 0.55 s max, 0.16 s min |
| Compression | Keeps quiet words audible on phone speakers | −20 dB, 2.2:1 |
| Peak normalise | Consistent level into the mix | −3 dBFS |
| Room tone | Very quiet noise bed that masks the cut points | −58 dB |
| Micro fades | 12 ms in, 30 ms out; no clicks at joins | — |

The gate is adaptive because fixed thresholds fail on real files: a take with a music bed
sits near −40 dBFS in the gaps, so a −42 dB gate finds nothing. The report prints input
duration, output duration, pauses capped, seconds removed and words per minute per beat.

Tune only when the report looks wrong:

- Pauses still feel long: `--max-pause 0.40`
- Cuts feel breathless: `--max-pause 0.70`
- Hiss or room hum: `--denoise`
- Levels low or hot: `--target-peak -2` or `--target-peak -4`

## 5. Pause design

Pauses are punctuation, and they should be authored, not accidental.

- **Inside a rule:** 0.3–0.5 s. The list should feel like instructions.
- **Before a consequence:** 0.6–0.8 s. Use the beat's `hold` field instead of leaving a
  long gap inside the file, so the silence lands exactly where the visual changes.
- **Before the final command:** 1.2–2.0 s of near-silence, music out, then the line.
- **After the final command:** 1.5 s of black before the title card.

`hold` adds silence after a beat without touching the narration file:

```json
{ "id": "089-twist", "hold": 1.6, "narration": "It was never the light that turned on." }
```

## 6. Transitions

Video and audio transitions are separate decisions.

**Audio**

- Beat joins: 30 ms fade in, 80 ms fade out, plus 0.16 s `tail_padding`. This removes the
  click that a hard cut at a waveform edge produces.
- Section joins: the music carries the change; narration does not fade. Silence plus a
  music swell is stronger than a crossfade.
- Ambience runs continuously underneath and never restarts per beat.

**Video**

- Section changes dip to black over 0.45 s (`transition.section`).
- Beat-to-beat inside a section: hard cut. Rule videos cut, they do not dissolve.
- Opening fades up from black over 0.8 s; the last beat fades out over 1.2 s.

## 7. Music and ambience

Two separate beds, both optional:

```json
{
  "music": "assets/music/drone.mp3",
  "music_volume": 0.07,
  "music_duck": true,
  "ambience": "assets/music/room-tone.wav",
  "ambience_volume": 0.09
}
```

- `music` is the score. It loops, ducks under speech via a sidechain compressor, and fades
  at both ends.
- `ambience` is room tone, wind, or a low hum. It sits lower and does not duck.
- Keep the score under speech at all times. If a viewer notices the music before the
  words, it is too loud.
- Use licensed or generated music. Note the licence in the release package.
- Cut the music entirely for the two seconds before the final command.

## 8. Loudness and delivery

| Target | Value |
|---|---|
| Integrated loudness | −16 LUFS |
| True peak | −1.5 dBTP |
| Loudness range | ~11 LU |
| Sample rate | 48 kHz |
| Channels | stereo |

The render applies `loudnorm` on the final pass, after the music mix, so the measurement is
of the finished file. `qc` reports the actual numbers; do not claim a target you have not
measured.

## 9. Listening checks

Automated checks cannot hear. Before delivery, listen to:

1. The first eight seconds — is the title premise clear and immediate?
2. Every section join — any click, drop-out, or double breath?
3. The case story — does the voice stay calm, or does it start performing?
4. The last twenty seconds — is the final command clean, and does the silence hold?

If you cannot listen, say so explicitly and report only the measured values.

## 10. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Clicks at beat joins | Cut on a non-zero sample | Already faded; if it persists, raise `tail_padding` to 0.25 |
| Words clipped at the start | Trim too aggressive | Lower `min_pause`, or re-export with 0.5 s head silence |
| Pumping, breathing level | Over-compression | Lower ratio; re-record with steadier distance |
| Hiss between words | Noisy room | `--denoise`; if severe, re-record |
| Plosives on P and B | Mic too close, on-axis | Re-record off-axis; high pass is already applied |
| Narration sounds rushed | Pause cap too tight | `--max-pause 0.70` |
| Music buries the voice | Volume too high | `music_volume` 0.04–0.06, keep ducking on |
| Different takes sound different | Different mic, room, or distance | Re-record together; match peak before importing |
| Dead air after the last word | Missing tail | Set `tail_padding`, add `hold` to the final beat |
