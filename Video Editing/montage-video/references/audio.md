# Audio — VO, resserrage, musique, SFX, loudness

## 1. Voix off ElevenLabs — `pipeline.py:Project.vo(text, name="vo", pause=0.25, tempo=1.0)`

| Étape | Valeur réelle (code) |
|---|---|
| Modèle | `eleven_v4` obligatoire (`Project.__init__` : `assert tts.startswith("eleven_v4")`) |
| Endpoint | `POST https://api.elevenlabs.io/v1/text-to-speech/{voice}/with-timestamps?output_format=mp3_44100_128` |
| Réglage | `voice_settings: {"stability": 0.5}` |
| Voix par défaut | `yj30vwTGJxSHezdAGsv9` (Jessa) — à remplacer par celle du brief |
| Découpage | paragraphes (`\n\n`), morceaux ≤ 9 500 car., assert ≤ 10 000 ; concat `libmp3lame 128k` ; alignements décalés de la durée décodée |
| Fichiers | `vo.txt`, `vo.mp3`, `vo_alignment.json`, `vo_tight.wav`, `vo_words.json`, `vo_tempo.txt` |
| Mots | reconstruits depuis l'alignement caractère (espace = séparateur) → `[{"w","s","e"}]` |
| Tags `[...]` | retirés de la liste après `tighten` |
| `tempo` | ≤ 1.10 (assert) ; appliqué par `atempo` sur la piste resserrée, timings divisés d'autant |

`Project.tighten(src, ws, out, pause, tempo)` :
- `silencedetect=n=-38dB:d=0.12` sur le mp3 ;
- chaque silence qui commence avant `dernier_mot.e - 0.05` et dure plus de `pause + 0.05` est raccourci à `pause`
  en coupant son milieu (`m = début + pause/2`) ;
- morceaux gardés : `atrim` + `asetpts` + `afade in/out 10 ms`, `concat`, `atempo` si ≠ 1 ;
- fin = dernier mot + 0,12 s ;
- timings recalculés : `(t - silence retiré avant t) / tempo`.
**Jamais de coupe entre deux mots** (ça s'entend). Une vidéo trop longue se raccourcit en coupant des mots du
script, pas avec `tempo`.

Débit de référence pour estimer une durée : ~0,33 s/mot parlé (pauses comprises), ~0,40 s/mot chanté.

Banque de voix : `Claude brain/knowledge/auto-video-editing/voix/00-banque-voix.md` (choisir l'âge de la voix
comme celui du personnage ; Jessa validée narratrice).

## 2. Voix portée par les clips

`Project.tighten_clip(clip, also=None, gap=0.32, keep=0.10, speed=1.08)` → `<clip>_tight.mp4`
- STT du clip (`_stt`) → mots ;
- segments gardés : de `1er mot - 0.12` ; à chaque silence interne > `gap`, coupe à `mot.e + keep` et reprise à
  `mot_suivant.s - keep` ; fin à `dernier mot + 0.22` ;
- bornes arrondies à la **grille d'images du clip** (`r_frame_rate`) ;
- `trim`/`atrim` + `concat` (son et image coupés aux mêmes instants), puis `setpts=PTS/1.08` et `atempo=1.08` ;
- encodage `libx264 -crf 18`, `aac 192k 44100` ; `also` = jumeau muet détouré coupé sur les mêmes intervalles.

`Project.trim_speech(clip, pre=0.15, post=0.35, also=None)` : ancienne version, ne rogne que les bords.

`Project.vo_from_clips(clips, name="vo")` : concat demuxer des clips → `vo.mp3` (`-ar 44100 -b:a 192k`) → STT →
`vo.words.json`. Renvoie `(words, vo.mp3)`. ElevenLabs y sert de transcripteur, la voix reste celle des clips.

`Project._stt(path)` : `scribe_v1` (multipart), mots `type=="word"` ; cache `<path>.words.json` invalidé si le
média est plus récent ; repli `whisper-cli -m ~/.cache/whisper/ggml-small.en.bin -ml 1 -sow -oj` (Linux, 16 kHz
mono) ou `mlx-whisper large-v3-turbo` via `uv` (Mac).

## 3. Musique — graphe de `Project.edit`

```
[vo]  apad=whole_dur=TOTAL, asplit=2 [vo][key]
[mus] (-stream_loop -1) atrim=0:TOTAL, asetpts=PTS-STARTPTS, volume=MUSIC_VOLUME,
      afade=t=in:d=0.6, afade=t=out:st=TOTAL-2.0:d=2.0 [m]
[m][key] sidechaincompress=threshold=0.03:ratio=6:attack=15:release=350 [duck]
[vo][duck][sfx…] amix=inputs=N:duration=first:normalize=0, aresample=44100 [a]
```
- Musique seulement si `self.music` est un fichier existant ; sinon la voix part seule (`apad`, puis `amix` avec
  les SFX ou directement `aresample`).
- `-stream_loop -1` obligatoire : sans lui une musique plus courte que la vidéo laisse la fin muette (58 s sur un
  montage de 168 s), et aucun contrôle ne le voit.
- **Volume** : défaut de la fonction `music_volume=0.08` ; règle Kevin 2026-10-13 : **0.04** partout ; `0.0` ou
  `music=None` si la référence n'a pas de musique (UGC « filmé au téléphone »).
- Morceaux : `tools/auto-video/resources/musiques/` (banque : `knowledge/auto-video-editing/musiques/00-banque-musiques.md`).
  Liste le dossier, pas la table. `else_paris.MP3` = défaut validé sur registre sérieux ; pas de musique joyeuse
  sur un sujet de honte. On ne génère pas de musique ; on peut extraire celle d'une référence (Demucs
  `--two-stems=vocals -n htdemucs` → `no_vocals.wav` → loudnorm -16 LUFS → mp3 192k) quand Kevin le demande.

`Project.edit_prebuilt` (corps déjà monté) : musique `aresample=44100,volume=…,afade=t=out:st=total-2:d=2`,
`amix=inputs=2:duration=first:normalize=0` — **sans ducking ni fondu d'entrée**.

## 4. SFX

`edit(..., sfx=[(fichier, t_secondes, volume)])` → `[i:a]volume=V,adelay=MS|MS[sfxK]`, ajouté au `amix`.
Seulement si la référence en utilise ou si Kevin le demande (exemple de la docstring : buzzer sur un mot barré).
Règle par défaut des vidéos voix off : voix + musique, pas de bruitages.

## 5. Loudness — `Project.loud_fix(path)`

```
mesure : ffmpeg -i OUT -vn -af ebur128 -f null -   → dernière valeur "I: x LUFS"
boucle (3 max, tant que |I + 14| > 0.4) :
  -c:v copy -af "volume=(-14-I)dB,alimiter=limit=0.95:level=false" -c:a aac -b:a 192k -ar 44100 -movflags +faststart
final : -c:v copy -af "alimiter=limit=0.89:level=false" -c:a aac -b:a 192k -ar 44100 -movflags +faststart
renvoie la mesure finale
```
- **Jamais `loudnorm` dans le graphe du montage** : son tampon avale ~3 s de voix et il sort en 192 kHz,
  ré-échantillonné en 96 kHz pour l'AAC → son joué 14 % trop vite. `qc.py` refuse tout autre que 44 100 Hz.
- Tolérance au QC : -14 ± 0,7 LUFS (`qc.py:check`).

## 6. Synchro son/image : ce qui la casse

- arrondir chaque plan séparément au lieu de caler sur la grille 30 i/s absolue (`edit`) ;
- `ceil` au lieu de `round` sur le nombre d'images d'un plan fixe (`segment`) ;
- concat `-c copy` de segments **avec** audio AAC (+28 ms/segment) — concaténer l'audio par filtre ;
- `select/aselect` pour couper un clip parlant (trames AAC 23 ms ≠ images 42 ms) — utiliser `trim/atrim` ;
- `xfade` entre plans (consomme de la durée) — utiliser `flash` (dessiné, durée nulle).
