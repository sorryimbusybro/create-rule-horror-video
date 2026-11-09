# Create Rule Horror Video

This is a skill for making long form rule based horror videos, the kind where a calm voice
tells you what to do if something impossible happens in your house.

You give it an idea, or ask it to invent one. It writes the script, plans every shot, fixes
your voice recording, places the sound effects, and renders a finished 1080p video with
captions. It also writes the title options, the description and the thumbnail direction.

It was built by studying four reference videos and one channel that gets millions of views,
then turning what they do into a repeatable process. Nothing from those videos is copied. The
skill only copies the structure: the title that states the threat, the rules that get worse,
the short case story, and the twist at the end.

## What it does

1. Asks if you have an idea or want one made, and what genre you want.
2. Gives you three title and opening hook options.
3. Writes the full script, ten to fourteen minutes, with five to seven rules.
4. Builds a beat sheet with narration, captions, camera moves and a scene block for each shot.
5. Draws every frame in code with three.js — rooms, the character, the lighting and the
   captions. **No images are generated**, there are no image prompts and no image tool is
   needed, so a hundred shots cost nothing but CPU time.
6. Takes your voiceover, from a recording or from ElevenLabs, and repairs it.
7. Places sound effects by role, so the right hit lands on the right beat.
8. Renders the video, checks the audio levels and the frames, and gives you the files.

## What you need

You need four things on your computer.

Python 3.10 or newer. It must have Pillow and numpy installed.

FFmpeg. If it is not installed, the script will try to use the copy that comes with the
`imageio-ffmpeg` package.

Node.js 20 or newer, plus Microsoft Edge or Google Chrome. The scene renderer runs three.js
in a headless browser. three.js itself is bundled in `scripts/scene/vendor/`, so there is no
npm install and nothing is downloaded at render time.

A terminal. On Windows use PowerShell or Git Bash.

Check your Python before you start. On Windows the `python` on your PATH is sometimes a
different install than the one with the packages, so run this and look for two `OK` lines.

```
python -c "import PIL, numpy; print('ok')"
python -c "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())"
```

If Pillow or numpy is missing, install them.

```
python -m pip install pillow numpy imageio-ffmpeg
```

## Setup

Step 1. Copy this folder somewhere permanent. Anywhere works. This guide uses
`C:\Skills\create-rule-horror-video`.

Step 2. Open a terminal in that folder.

Step 3. Run the setup check.

```
python scripts/video_pipeline.py doctor
```

It prints your Python version, the Pillow and numpy versions, which FFmpeg it found, whether
the required filters are there, how many sounds are installed, and whether Node, the browser
and the bundled three.js are available. If anything is wrong it tells you what to fix. The
last line should say `READY`.

Step 4. Install the skill so your assistant can find it. If you use WorkBuddy or Qoder, link
the folder into the skills directory.

On Windows, open Command Prompt as your normal user and run this, changing the paths if you
moved the folder.

```
mklink /J "%USERPROFILE%\.workbuddy-ai\skills\create-rule-horror-video" "C:\Skills\create-rule-horror-video"
```

That makes one link, so editing either path edits the same files.

Step 5. Restart your assistant, or run the skills reload command, then check that the skill
appears in the list.

## How to use it

Open a chat and invoke the skill.

```
/create-rule-horror-video
```

It will ask you one question first: do you have an idea, or should it make one, and if it
makes one, what genre or topic.

From there it works in order. You approve the idea, then the title, then the script. Then it
builds the project and starts producing.

If you want to drive it by hand, here are the commands it uses. Replace `<python>` with your
Python path and `<project>` with the folder for your episode.

Make a new project.

```
<python> scripts/video_pipeline.py init "<project>" --title "If Your Hall Light Ever Turns On by Itself... DON'T LOOK UP" --style warm-flat
```

That creates the project file, the scene guide (every location, shot, pose and expression),
the palette and the folders. There is no style lock to paste anywhere.

Import your voiceover. You can point it at a folder with one audio file per beat, named by
the beat id, or at one single file for the whole episode.

```
<python> scripts/video_pipeline.py audio "<project>" --source "C:\path\to\vo-folder"
<python> scripts/video_pipeline.py align "<project>" --file "C:\path\to\full-voice.wav"
```

The `audio` command repairs each take. It finds the noise floor, trims the dead air at the
start and the end, shortens any pause longer than 0.55 seconds, smooths the level, and adds a
quiet room tone so the cuts do not click. It prints a table so you can see what it changed.

Place the sound effects.

```
<python> scripts/video_pipeline.py sfx "<project>" --auto --dry-run
<python> scripts/video_pipeline.py sfx "<project>" --auto
```

The first line shows you the plan. The second one writes it.

Look at the pictures before you spend time rendering.

```
<python> scripts/video_pipeline.py stills "<project>" --beats 10
```

That writes one PNG per beat into `render/stills/`. Check that the pale character is visible
against the dark room, the room is lit, and the rule cards clear the head. Change the beat's
`scene` block and run it again — stills are cheap.

Then check the project and render a short preview.

```
<python> scripts/video_pipeline.py validate "<project>" --assets
<python> scripts/video_pipeline.py render "<project>" --preview 10
```

The preview renders the first ten beats at half size. Watch it before you render the whole
thing.

Render the final video.

```
<python> scripts/video_pipeline.py render "<project>"
<python> scripts/video_pipeline.py qc "<project>"
```

The render writes `final.mp4`, `captions.srt` and `chapters.txt` into the project folder. The
`qc` command pulls frames out, measures the loudness and reports any dead air.

## The commands in one place

| Command | What it does |
|---|---|
| `doctor` | Checks Python, Pillow, numpy, FFmpeg, Node, the browser, three.js and the sound library |
| `init` | Creates a project, the scene guide, the palette and the folders |
| `audio` | Imports and repairs one audio file per beat |
| `align` | Splits one long voiceover into beats |
| `narrate` | Optional. Makes a scratch voice with text to speech |
| `validate` | Checks the project file, the scene blocks and the assets |
| `timeline` | Prints the beat by beat timing with place and shot |
| `sfx` | Scans the sound library and places effects |
| `stills` | Renders one PNG per beat so you can inspect the scene |
| `render` | Draws the scenes, joins the beats, mixes the audio |
| `qc` | Extracts frames, measures loudness, finds dead air |

There is a second script for the scenes.

| Command | What it does |
|---|---|
| `visual_ops.py doctor` | Checks Node, the browser, three.js and the driver |
| `visual_ops.py places` | Lists locations, shots, moves, poses, expressions and items |
| `visual_ops.py still` | Renders one PNG from a standalone scene JSON file |

And one for sounds.

| Command | What it does |
|---|---|
| `sfx_ops.py scan` | Shows which sound roles you have |
| `sfx_ops.py import` | Trims, levels, renames and installs a folder of sounds |
| `sfx_ops.py check` | Audits the library for bad levels and silent tails |

## The sound library

The skill comes with fourteen sound effects already prepared, so placement works out of the
box. Every file is named after its role, trimmed and levelled. Short effects are PCM WAV, the
longer ones are MP3 at 96 kbps so the whole library stays near 2 MB. Files sit in `assets/sfx/`.

To add your own, put the downloads in a folder and run the importer. Do not rename them by
hand, the importer does it properly.

```
<python> scripts/sfx_ops.py import --from "C:\Users\you\Downloads\sfx" --dry-run
<python> scripts/sfx_ops.py import --from "C:\Users\you\Downloads\sfx"
```

If a file name does not make the role obvious, tell it directly.

```
<python> scripts/sfx_ops.py import --from "C:\Users\you\Downloads\sfx" --map "foley-door-lock=lockingdoor1.wav"
```

The importer trims the silence before the first sound, cuts the silent tail, fades the edges,
sets the peak level for that type of sound, and writes the source into `licenses.txt`.

Fourteen of the twenty eight roles are filled. The missing ones are extra colour like keys,
a window tap, a phone buzz and rain. The list is in `references/sfx-library.md` if you want to
fill them.

Some of the included sounds are built rather than downloaded. The sub drop, the static burst,
the single footstep and the short room tone loop were made from the other files. They are
marked as derived in `library.json` and in `licenses.txt`.

## Folder layout

```
create-rule-horror-video/
  SKILL.md                 the instructions the assistant reads
  references/
    format-dna.md          what the reference videos actually do
    story-engine.md        premises, hooks, rule logic, the quality rubric
    visual-system.md       scene blocks, procedural geometry, palettes, framing
    audio-playbook.md      voice recording, ElevenLabs, repair, transitions
    sfx-library.md         the sound roles, what is installed, what is missing
    production.md          the project file format and the full command reference
  scripts/
    video_pipeline.py      the main tool
    visual_ops.py          scene specs, the browser driver, clip and still rendering
    audio_ops.py           audio analysis and repair
    sfx_ops.py             the sound importer and auditor
    tts_sapi.ps1           optional offline voice for Windows
    scene/
      driver.mjs           headless browser, local server, H.264 stream collector
      index.html           the page that loads the runtime
      vendor/              bundled three.js, no install needed
      src/                 locations, character, camera, overlays, film finish
  assets/
    sfx-catalog.json       the list of sound roles
    sfx/                   the prepared sounds, plus library.json and licenses.txt
```

Each project you make looks like this.

```
my-episode/
  project.json             every beat, every scene block, every setting
  scene-guide.txt          every location, shot, move, pose and expression
  palette.json             the colours for this episode
  assets/audio/            one file per beat, after repair
  assets/music/            the score and the room tone
  assets/sfx/              optional, beats the shared library for that role
  render/
    stills/                inspection PNGs
    clips/                 one MP4 per beat, drawn by three.js
    streams/               raw H.264 or MJPEG from the browser
    beats/                 beat clips married to their audio
    qc/                    extracted frames
  final.mp4                the finished video
  captions.srt
  chapters.txt
```

## How the pictures are made

Nothing is generated as an image. Each beat carries a `scene` block like this:

```json
"scene": {
  "place": "hallway",
  "seed": 7,
  "camera": { "shot": "medium", "move": "push", "amount": 0.24 },
  "figure": { "pose": "stand", "z": -3.2, "expression": "absent" },
  "light": { "flicker": 0.08 },
  "atmosphere": { "fog": 0.035 }
}
```

A headless browser builds that room out of three.js geometry, places a pale-skinned figure
with a saturated garment, lights it with one practical plus a fill and a rim, and draws the
grade, grain, vignette, HUD, captions and rule cards on a 2D canvas. WebCodecs encodes the
frames to H.264 and the Node driver streams them to disk. FFmpeg then marries each clip to
its narration.

Because it is all code, the character cannot drift between shot one and shot ninety, a new
shot costs no credits or tokens, and any defect is a value you can fix. Fourteen locations,
four shots, seven camera moves, ten poses and six expressions are built in. The full field
reference is in `references/visual-system.md`, and `visual_ops.py places` prints the live
list. Run `stills` to look at the result before rendering the whole episode.

The character's skin is deliberately pale so it reads against black rooms; the clothes come
from the chosen style palette. The face is two eyes and a mouth, no detail — a face that
stops reacting does the horror work.

To add a new room or prop, add geometry to `scripts/scene/src/builders.js`. Do not add an
image model.

## Things that will trip you up

Renders take time. Every frame is drawn by WebGL, so a twelve minute episode at 1080p30 is
roughly twenty to thirty five minutes on a four core machine, plus a few seconds once per
batch to start the browser. Run `stills` and a ten beat preview first; both are cheap and
catch almost everything.

The `python` on your PATH might not have the packages. If you get a missing module error, use
the full path to the Python that does.

Node or the browser may not be where the script looks. Set `RULE_HORROR_NODE` or
`RULE_HORROR_BROWSER` to an explicit path. `visual_ops.py doctor` prints what it found.

Text to speech is optional and sounds like text to speech. The intended path is your own
recording or an ElevenLabs export. The skill will not install a text to speech package
without asking.

Beat caching is a hash of the scene block, the text, the duration, the frame size, the fps,
the style and the relevant settings. Change any of those and only that beat re-renders. The
hash does not include the sound library, so if you replace an effect file, render with
`--force`.

The first render of a batch starts one headless browser and reuses it for every beat. If a
run is killed hard, the driver's shutdown handler takes the browser tree down with it; if
you kill it from outside, check Task Manager for leftover `msedge` or `chrome` processes.

Nothing here promises views. The structure is built to hold attention, but the story and the
art still decide whether it works.

## Licence

The code is under the MIT licence. See the `LICENSE` file for the full text.

In plain words, you can use it, change it, sell what you make with it, and share it. You do
not have to credit me, but you do have to keep the copyright line in the `LICENSE` file. It
comes with no warranty, so if a render eats your weekend that is on you.

The sound files keep their own licences. They came from Freesound, Pixabay and similar
sources. `assets/sfx/licenses.txt` lists every file with empty lines for the source and the
licence. Fill those in before you publish anything, especially if you monetise. Some
libraries, like the BBC sound effects library, are for personal use only.

The music is not included. Use something you have the rights to.
