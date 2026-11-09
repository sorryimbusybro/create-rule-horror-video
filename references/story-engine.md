# Story Engine

## 1. Find an original premise

Combine four elements:

- **Familiar subject:** a bed, mirror, phone, doorbell, baby monitor, elevator, hallway, pet, parent, photo, voicemail, smart speaker, or routine.
- **Small anomaly:** one impossible but observable deviation from normal behavior.
- **Urgent action:** a concrete response that creates a rule, not a vague warning such as “be careful.”
- **Hidden objective:** what the entity gains if the viewer ignores that action.

Prefer a premise that can be explained visually with one object and one changed detail. Avoid simply replacing the noun in an existing reference title. If a supplied idea resembles a reference too closely, change the mechanism, setting, entity goal, and final inversion.

Useful fear engines:

- Recognition: something is learning a face, voice, habits, or name.
- Replacement: a familiar person behaves almost correctly.
- Invitation: a harmless response grants access.
- Containment: the rules keep something in one place rather than protect the protagonist directly.
- Observation: looking, recording, or acknowledging makes the entity stronger.
- Routine: an ordinary repeated action creates an opportunity for the entity.

## 2. Build the hook package

Create three genuinely different title/opening pairs. A strong title is specific enough to visualize and incomplete enough to demand an explanation.

Title pattern:

> If Your [subject] Ever [anomaly]... [ACTION]

Opening pattern:

> If your [subject] ever [anomaly], [action]. Don't [second action]. Don't [third action]. [One concrete sensory sign that proves this is not normal].

Check that:

- The title's exact scenario appears immediately.
- The command is understandable but its reason is withheld.
- The stakes are implied by a concrete detail, not by “this will shock you.”
- The opening contains no greeting or production branding.
- The story can deliver the promised threat without misleading the viewer.

## 3. Define the hidden rule logic

Complete this private story logic before drafting:

```text
Entity:
Entity's goal:
How it perceives people:
What counts as acknowledgment or invitation:
Why the opening anomaly occurs:
Why each rule works:
Cost or limit of each rule:
How the entity adapts:
Early clues:
Case-story consequence:
Final inversion:
Final command:
```

Every rule needs a causal relationship to the entity. Arbitrary rules make the story feel generated. It is acceptable for the narrator's initial explanation to be incomplete, but the final reveal must make earlier behavior coherent.

## 4. Use the long-form retention spine

The timings below are proportional; adjust them to the approved duration.

| Portion | Function |
|---|---|
| 0–2% | Title premise, urgent command, two escalating prohibitions. |
| 2–9% | Eliminate mundane explanations, add sensory evidence, promise the rules. |
| 9–30% | Rules 1–2 establish immediate survival and the entity's basic mechanism. |
| 30–48% | Rules 3–4 complicate the mechanism and remove an apparent escape. |
| 48–65% | Case story or rule 5 demonstrates a concrete human consequence. |
| 65–82% | Remaining rules tighten the trap; early clues return with new meaning. |
| 82–94% | Recontextualize the rules and reveal the entity's actual goal. |
| 94–100% | Invert a normal condition, call back to the opening, land the final command. |

Use five to seven rules for most 9–14 minute videos. Fewer rules need more development; do not pad to reach a number.

### Inside each rule

Include most of these beats, not a rigid checklist:

1. State the rule in a short imperative.
2. Describe the instinct that makes it difficult to follow.
3. Give concrete physical actions.
4. Add one sensory consequence.
5. Explain the entity logic in one or two sentences.
6. Introduce a complication or exception.
7. End with a line that pulls into the next rule.

Vary section shape. One rule may be practical, another a miniature encounter, another an object close-up, and another the case story.

## 5. Write narration that sounds human

- Use “you” and present tense for the main encounter.
- Prefer concrete verbs and nouns over adjectives and abstractions.
- Alternate short commands with longer, controlled explanatory sentences.
- Describe exactly what the viewer sees, hears, or feels.
- Use repetition only for intentional callbacks or escalating commands.
- Let a frightening image remain simple: “The post was dated that same night,” not a paragraph explaining why it is frightening.
- Keep dialogue sparse and attributable.
- Avoid “little did they know,” “everything changed forever,” “in today's video,” fake evidence, and claims that fictional events are factual.
- Read the script aloud or synthesize a preview; revise tongue-twisters and unnatural punctuation.

## 6. Design the case story

The case story is evidence inside the fiction, not a detached second plot. Give the character one ordinary desire, one understandable mistake, and one irreversible discovery. Use two or three memorable objects rather than extensive biography. Connect the outcome directly to a later rule or the final inversion.

Do not copy the reference stories' names, deceased pet, missing schoolmate, sleeping photography, or alternate-face setup. Create a new consequence from the new entity's logic.

## 7. Land the final inversion

A strong ending satisfies all three tests:

- **Callback:** It reuses a phrase, object, or condition from the opening.
- **Reinterpretation:** It changes what earlier safety or danger meant.
- **Next fear:** It makes an unavoidable ordinary action feel threatening after the video ends.

Do not add an unrelated jump scare after the twist. End quickly on the final command, a short silence, and an original title card.

## 8. Storyboard as scene blocks

Visuals are drawn in code, so write each beat's staging as a `scene` object rather than a
description for an image model. See [visual-system.md](visual-system.md) for the full field
reference.

- Map each rule to a `place` and keep that place for the rule's section. Continuity is free:
  the same builder produces the same room every beat.
- Put object clues in `place: object` inserts (`phone`, `key`, `photo`, `lock`, `paper`) and
  deliver rule headings with `place: void` plus an `overlay` card.
- Escalate with one changed variable per return: `figure.expression`, `figure.pose`,
  `light.flicker`, `light.off`, `atmosphere.fog`, or a single `entity` silhouette in the
  dark. A changed detail is cheaper and more frightening than a new monster.
- Hold `camera.move: static` for dread and use `push` only when the narration closes a gap.
- Save `close` shots for the moment the entity's goal becomes clear.
- Check that every beat can be staged from the available places, shots, poses and
  expressions. If a story beat needs a location that does not exist, add a builder in
  `scripts/scene/src/builders.js` — do not substitute an image.

## 9. Story quality rubric

Revise until every answer is yes:

- Is the premise understandable from the title alone?
- Does the opening deliver it within 15 seconds?
- Is the entity's hidden objective specific and internally consistent?
- Does every rule reveal new information or a new complication?
- Are at least three final-payoff clues planted early?
- Does the case story change the viewer's understanding or stakes?
- Does the final inversion make earlier details more frightening?
- Can the visuals show the threat through concrete changed details?
- Is the script original rather than a noun-swapped reference script?
- Is the target word count appropriate for the chosen duration?
