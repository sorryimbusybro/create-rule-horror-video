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
4. Builds a beat sheet with narration, captions, camera moves and art direction.
5. Writes image prompts that keep the same character and the same look across every shot.
6. Takes your voiceover, from a recording or from ElevenLabs, and repairs it.
7. Places sound effects by role, so the right hit lands on the right beat.
8. Renders the video, checks the audio levels and the frames, and gives you the files.

## What you need

You need three things on your computer.

Python 3.10 or newer. It must have Pillow and numpy installed.

FFmpeg. If it is not installed, the script will try to use the copy that comes with the
`imageio-ffmpeg` package.

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
the required filters are there, how many sounds are installed, and how many fonts it can
see. If anything is wrong it tells you what to fix. The last line should say `READY`.

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

That creates the project file, the style lock, the palette and the folders.

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

Check the project before you spend time rendering.

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
| `doctor` | Checks Python, Pillow, numpy, FFmpeg, fonts and the sound library |
| `init` | Creates a project, the style lock and the folders |
| `audio` | Imports and repairs one audio file per beat |
| `align` | Splits one long voiceover into beats |
| `narrate` | Optional. Makes a scratch voice with text to speech |
| `validate` | Checks the project file and the assets |
| `timeline` | Prints the beat by beat timing |
| `sfx` | Scans the sound library and places effects |
| `render` | Renders the beats, joins them, mixes the audio |
| `qc` | Extracts frames, measures loudness, finds dead air |

There is a second script for sounds.

| Command | What it does |
|---|---|
| `sfx_ops.py scan` | Shows which sound roles you have |
| `sfx_ops.py import` | Trims, levels, renames and installs a folder of sounds |
| `sfx_ops.py check` | Audits the library for bad levels and silent tails |

## The sound library

The skill comes with fourteen sound effects already prepared, so placement works out of the
box. Every file is named after its role, trimmed, levelled and converted to 48 kHz. Files sit
in `assets/sfx/`.

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
    visual-system.md       how the character is built, palettes, prompt blocks
    audio-playbook.md      voice recording, ElevenLabs, repair, transitions
    sfx-library.md         the sound roles, what is installed, what is missing
    production.md          the project file format and the full command reference
  scripts/
    video_pipeline.py      the main tool
    audio_ops.py           audio analysis and repair
    sfx_ops.py             the sound importer and auditor
    tts_sapi.ps1           optional offline voice for Windows
  assets/
    sfx-catalog.json       the list of sound roles
    sfx/                   the prepared sounds, plus library.json and licenses.txt
```

Each project you make looks like this.

```
my-episode/
  project.json             every beat, every setting
  style-lock.txt           paste this into every image generation
  palette.json             the colours for this episode
  assets/images/           the plates
  assets/audio/            one file per beat, after repair
  assets/music/            the score and the room tone
  assets/sfx/              optional, beats the shared library for that role
  render/                  intermediate files
  final.mp4                the finished video
  captions.srt
  chapters.txt
```

## Making the images

The skill writes the prompts, it does not generate the pictures for you unless your assistant
has an image tool connected. Every project gets a `style-lock.txt`. Paste it at the start of
every image request, then add the scene description. That is what keeps the character looking
like the same person in shot one and shot ninety.

The look is flat vector illustration with a designed character, layered backgrounds and one
warm light source. Not stick figures. The full construction rules are in
`references/visual-system.md`.

## Things that will trip you up

Renders take time. On a four core machine a twelve minute episode is roughly twenty five to
thirty five minutes. Always render a preview of ten beats first.

The `python` on your PATH might not have the packages. If you get a missing module error, use
the full path to the Python that does.

Text to speech is optional and sounds like text to speech. The intended path is your own
recording or an ElevenLabs export. The skill will not install a text to speech package
without asking.

Beat caching keys on the project file, not on the contents of the sound library. If you
replace a sound file, render with `--force`.

Nothing here promises views. The structure is built to hold attention, but the story and the
art still decide whether it works.

## Licences

The code is yours to use and change.

The sound files keep their own licences. They came from Freesound, Pixabay and similar
sources. `assets/sfx/licenses.txt` lists every file with empty lines for the source and the
licence. Fill those in before you publish anything, especially if you monetise. Some
libraries, like the BBC sound effects library, are for personal use only.

The music is not included. Use something you have the rights to.
