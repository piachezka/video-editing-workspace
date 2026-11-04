# Setup prompt (paste into Claude Code, opened in the folder that contains `montage-video/`)

Works on macOS and Windows; Claude detects which one and follows that branch.
Requirement: an ElevenLabs API key (elevenlabs.io → Profile → API keys). It's used to get the exact time of
every word in the voiceover/song so cuts and captions land on the voice. Claude asks for it right at the start;
you paste it into a file yourself, never into the chat.

---

You are setting up a video-editing workspace from scratch. The only thing provided is the `montage-video/` folder
in the current directory. This workspace does **video editing only**: it never generates voices, images or clips.
ElevenLabs is used only as a transcriber (word timings). Do every step below yourself, verify each one, and stop
to ask me only where it says so. Never print, echo or log an API key.

**0. Detect the OS** (macOS or Windows) and follow only that OS's lines below. On Windows: use `py` or `python`
instead of `python3` (whichever works), and set `PYTHONUTF8=1` as a user environment variable (the scripts print
✅/⛔, which crash a cp1252 console).

**1. First thing: the env file and the ElevenLabs key.** Before anything else, create the file the scripts
require: `<parent of montage-video>/Claude brain/.env` (`autoad.py` reads
`Path(autoad.py).resolve().parents[2] / "Claude brain" / ".env"`; if it's missing, every import crashes). Use this
exact content (macOS: `chmod 600` it):
```
# ElevenLabs: speech-to-text (Scribe) for word timings. Required.
ELEVENLABS_API_KEY=
# Kie: image/clip generation only, not used here. Leave empty (the line must exist).
KIE_API_KEY=
```
Then **STOP and ask me to add my ElevenLabs API key.** Give me the file's full absolute path, open it in a text
editor for me (macOS: `open -e "<path>"`, Windows: `notepad "<path>"`), and tell me exactly what to do: paste the
key after `ELEVENLABS_API_KEY=` on the same line, with no quotes or spaces, save, close, and reply "done". Remind
me never to paste the key in the chat. Wait for my reply; do nothing else until then.

After I say it's done, check without printing anything secret: the key is non-empty (a Python one-liner that
reads the file and prints only `set`/`empty`; if it's empty, ask me again). Then make one free authenticated
call, `GET https://api.elevenlabs.io/v1/user` with header `xi-api-key`, and report only the HTTP status and the
remaining character quota. On a 401, tell me the key was rejected and ask me to fix it in the file.

**2. Read the workflow.** Read `montage-video/SKILL.md`, `montage-video/scripts/README.md` and every file in
`montage-video/references/` in full. They are the rules for all future edits: edits go through
`scripts/pipeline.py` (`Project`, `timing`, `edit`, `loud_fix`) and `scripts/qc.py`, never hand-made ffmpeg
finals. ElevenLabs is used only through `Project._stt()` (word timings). Out of scope, never to be called:
`Project.vo()` (ElevenLabs text-to-speech) and anything that generates images or clips (`autoad.py` generation,
Kie). The voice is always provided: a voiceover file, a song, or speech inside the clips.

**3. System dependencies.** Install only what's missing. Ask me before installing a package manager or anything
that needs admin rights.
- **ffmpeg + ffprobe** on PATH. macOS: `brew install ffmpeg`. Windows: `winget install Gyan.FFmpeg` (full
  build), then open a new shell so PATH updates. Check the filters exist:
  `ffmpeg -hide_banner -filters` must list `zoompan`, `sidechaincompress`, `alphamerge`, `ebur128`, `alimiter`.
- **Python ≥ 3.9** with `Pillow` and `numpy`. macOS: `python3 -m pip install --user Pillow numpy` (add
  `--break-system-packages` if pip refuses). Windows: `winget install Python.Python.3.12`, then
  `py -m pip install Pillow numpy`. Check with `import PIL, numpy`.
- **Local speech-to-text fallback.** The code uses it automatically when ElevenLabs fails (out of credits, no
  network). It picks the tool by OS:
  - macOS (Apple Silicon): `brew install uv`. The code runs `mlx-whisper` through it; the model downloads on
    first use.
  - Windows: the code calls `whisper-cli` with `%USERPROFILE%\.cache\whisper\ggml-small.en.bin`. Download the
    latest Windows release of whisper.cpp from github.com/ggml-org/whisper.cpp/releases (CPU build), unzip it
    into `%USERPROFILE%\whisper.cpp`, add that folder to the user PATH, check `whisper-cli --help` runs, then
    download `ggml-small.en.bin` from huggingface.co/ggerganov/whisper.cpp into
    `%USERPROFILE%\.cache\whisper\`. Ask me before these downloads (name, source, size).

**4. Fonts.** Captions must use the real font files: a look-alike font changes the measurements, so the text
wraps differently.
- **Arial Black, Arial Bold, Impact.** macOS: already in `/System/Library/Fonts/Supplemental/`, nothing to do.
  Windows: the code looks for the names `Arial Black.ttf`, `Arial Bold.ttf`, `Impact.ttf` in `FONTS_DIR`, while
  Windows calls them `ariblk.ttf`, `arialbd.ttf`, `impact.ttf`. Copy them from `C:\Windows\Fonts\` into
  `montage-video/scripts/resources/fonts/win/` under the Mac names, and add
  `FONTS_DIR=<absolute path of that folder>` to the `.env` file from step 1 (don't touch the key line). It's read
  before the fonts are resolved.
- **Liberation Sans and DejaVu Sans Mono** (caption styles `whitebox`, `capsbox`, `lowbox`, `blackbox`, `film`,
  `majligne`, `karaoke`, `sitcom`, `mono`). macOS: `brew install --cask font-liberation font-dejavu`. Windows:
  download the latest TTF releases from github.com/liberationfonts/liberation-fonts and
  github.com/dejavu-fonts/dejavu-fonts (ask me first), and copy `LiberationSans-Regular.ttf`,
  `LiberationSans-Bold.ttf`, `LiberationSans-BoldItalic.ttf` and `DejaVuSansMono.ttf` into
  `montage-video/scripts/resources/fonts/`.
- **Patch `pipeline.py`.** It hard-codes these fonts under `/usr/share/fonts/...` (Linux only). Patch only
  those paths: the constants `WHITEBOX_FONT`, `FILM_FONT`, `MONO_FONT` and the two literal
  `LiberationSans-Regular.ttf` paths. Each should use the `/usr/share` path if it exists, otherwise the first
  file with the same name found in: `RES / "fonts"`, `~/Library/Fonts`, `/Library/Fonts`,
  `%LOCALAPPDATA%\Microsoft\Windows\Fonts`, `C:\Windows\Fonts`. Use one small helper function and add a
  comment that it's the macOS/Windows fallback.
- **Patch `/tmp`.** `Project.sheet()` writes its thumbnails to `Path("/tmp")`, which doesn't exist on Windows.
  Replace it with `Path(tempfile.gettempdir())`; that also works on macOS.
- Then confirm that every font path these constants resolve to exists.

**5. Import check.** From `montage-video/scripts`:
`python -c "import pipeline as pl, qc; print(pl.W, pl.H, pl.FONT_BLACK, pl.WHITEBOX_FONT, pl.MONO_FONT)"` must
print `1080 1920` and font paths that exist.

**6. Smoke test.** In a scratch project folder outside `montage-video/`:
- generate 3 test stills (`frames/P01.png…P03.png`, 1080x1920, different solid colours with a big number),
  one 4-second test clip (`clips/P04.mp4`, ffmpeg `testsrc2`), and a ~12 s voice track of four short
  sentences, converted to `vo.mp3` (44.1 kHz). macOS: `say -o`. Windows: PowerShell
  `System.Speech.Synthesis.SpeechSynthesizer` → `SetOutputToWaveFile`.
- get word timings with `Project._stt` (one small ElevenLabs Scribe call, a few seconds of audio). Confirm it
  came from Scribe, not the fallback, and that the words match the sentences. Then delete the `.words.json`
  cache, temporarily run `_stt` with the key unset in the process environment only (never edit the file), and
  confirm the local fallback works too.
- write a `build.py` following `references/exemple-build.md`, but with the provided voice in place of
  `P.vo()`: words from `_stt`, the voice file as the voice track (as in `vo_from_clips`). Use four shots
  anchored on the first words of each sentence, `caption_style="box"`, `music=None`, and pass the same
  `min_shot` to `timing()` and `edit()`. Print the timing table and `MERGED`, then run `edit()`.
- run `qc.py` on it. It will fail check 7 (no `porte2.md`). Look at a contact sheet (`P.sheet`) and the frames
  at each cut yourself; only if they're correct, write `porte2.md` with the verdict `FEU VERT` and rerun
  `qc.py` until it ends with `✅ tout est livrable`.
- also render one frame of each caption style that uses Liberation or DejaVu (`whitebox`, `film`, `mono`) and
  look at them to confirm the fonts load.
Show me the final test video and the contact sheet, then delete the scratch project.

**7. Remember the setup.** Save a short memory note: the OS, where the workspace and `Claude brain/.env` are,
that the ElevenLabs key is set (never its value) and used only for word timings, that it's editing only (no
`vo()`, no generation), the font and `/tmp` patches, and that edits follow `montage-video/SKILL.md` through
`pipeline.py` + `qc.py`.

**8. Report.** Give me a checklist: each dependency ✅/❌ with its version, the ElevenLabs key status (valid +
remaining quota, never the value), the smoke-test duration and LUFS, and anything that still doesn't work. Then
tell me exactly what to send for a real edit: clips/stills, the voiceover or song file, which shot goes with
which line (first 5 exact words), the reference ad (caption style, music, end card), and the music file or "none".
