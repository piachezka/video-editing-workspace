---
name: montage-video
description: À utiliser dès qu'il faut MONTER une ad vidéo verticale 1080x1920 à partir de plans déjà générés (images fixes ou clips) et d'une voix off ou d'une piste chantée : calage des plans sur la voix, captions, calques, musique, SFX, loudness -14 LUFS, export et QC — pas pour écrire le brief ni générer les images/clips.
---

# Montage vidéo (pipeline Kevin / auto-video)

Ce skill décrit **ce que fait le code** de `scripts/pipeline.py` (classe `Project`), `scripts/qc.py` et la partie
montage de `scripts/autoad.py`. Chaque règle cite `fichier:fonction`. Ne réinvente rien : appelle `Project`.
Détail par sujet dans `references/` : `captions.md`, `audio.md`, `recettes-ffmpeg.md`, `qc.md`, `exemple-build.md`.
Installation et dépendances : `scripts/README.md`.

## 0. Principes non négociables

1. **Une génération IA fait UNE chose.** Texte, badge, croix, carte b-roll, split, avant/après, CTA = montage
   (calques PNG), jamais demandés au modèle vidéo. Plan sans mouvement = image + `kind="still"`, 0 crédit.
2. **La voix off est l'horloge.** Chaque plan démarre sur le 1er mot de sa phrase d'ancrage
   (`pipeline.py:Project.timing`). On ne cale jamais un plan « à l'œil ».
3. **Rien n'est livré sans `qc.py` vert ET une planche regardée** (`qc.py:check`). Un bug de cette pipeline ne
   crashe pas : il livre une vidéo fausse (désynchro, son muet, caption brûlée).
4. **Le CTA de fin se relève sur la référence** (10 dernières secondes extraites en frames). Si la référence
   n'a pas d'end card, on n'en met pas. Jamais d'end card recyclée.
5. **Le goût (registre, couleur, musique, style de caption) vient de Kevin ou de la référence**, pas de toi.
6. **Ne lance jamais deux `edit()` en parallèle sur le même projet** : le mp4 sort corrompu en silence
   (`Invalid NAL unit size`), taille et durée justes.
7. **Ne lance aucune génération ni appel payant** sans accord explicite. Le montage lui-même coûte 0 crédit,
   sauf `vo()` (TTS ElevenLabs) et `_stt()` (Scribe) qui appellent l'API.

## 1. Entrées attendues (un dossier projet)

```
<projet>/
  build.py            # définit SCRIPT, ANCRES/shots, style de captions, calques ; appelle Project.edit
  frames/<id>.png     # plans fixes (kind="still")            -> Project.fr
  clips/<id>.mp4      # plans animés (kind="clip", défaut)    -> Project.cl
  segments/           # créé par edit() (cache par plan)      -> Project.seg
  captions/           # créé par captions() (PNG + list.txt, VIDÉ à chaque appel)
  porte2.md           # verdict écrit du contrôleur (exigé par qc.py check 7)
```
- `Project(here, voice=<voice_id>, music=<chemin mp3 | None>, tts="eleven_v4")` crée `frames/ clips/ segments/
  _review/` (`pipeline.py:Project.__init__`). `tts` ≠ `eleven_v4*` → AssertionError.
- Un plan = dict `{"id": "P01", "anchor": "<5 premiers mots EXACTS de sa phrase dans la VO>", "kind": ..., "src": ...}`.
- `kind` : `clip` (défaut), `still`, `split` (G/D), `vsplit` (H/B), `avatar` (fond + incrustation détourée).
  Options de plan : `src`, `srcL/srcR`, `srcT/srcB`, `use_first`, `speed`, `reverse`, `bg`, `avatar`,
  `avatar_rgb`, `aw`, `ax`, `bgoff`, `fixed`, `atop` (`pipeline.py:Project.segment`).

## 2. Voix off et alignement au mot

**Cas A — voix off ElevenLabs** : `words, tight = P.vo(SCRIPT, name="vo", pause=0.25, tempo=1.0)`
(`pipeline.py:Project.vo`).
- TTS `/v1/text-to-speech/{voice}/with-timestamps`, `mp3_44100_128`, `stability 0.5`, modèle `eleven_v4`.
- Script > 9 500 caractères → découpé **aux paragraphes** (`\n\n`), audio recollé, alignements décalés de la
  durée **décodée** de chaque morceau. Un paragraphe > 10 000 car. → assert.
- Cache : `vo.txt` (texte), `vo.mp3`, `vo_alignment.json`, `vo_tight.wav`, `vo_words.json`, `vo_tempo.txt`
  (`"{pause}/{tempo}"`). Texte, pause ou tempo changé → recalcul. Sinon rien n'est rappelé.
- `tighten()` raccourcit **seulement les vrais silences** (`silencedetect=n=-38dB:d=0.12`) à `pause` s en
  coupant leur milieu, fondus 10 ms, **jamais entre deux mots**. Fin = dernier mot + 0,12 s.
- `tempo` ≤ **1.10** (assert). Au-delà : **coupe des mots**, n'accélère pas.
- Les jetons `[...]` (tags d'intonation) sont retirés de `words` ; `captions()` lève une erreur s'il en reste.
- Contrôle immédiat : `assert len(words) == len(SCRIPT.split())` (fait dans l'exemple réel).

**Cas B — la voix est dans les clips** (personnage qui parle, Kling/Omni) :
1. Resserrer chaque clip : `P.tighten_clip(clip, also=<jumeau détouré>, gap=0.32, keep=0.10, speed=1.08)`
   (`pipeline.py:Project.tighten_clip`) → silences internes > 0,32 s ramenés à 0,10 s (jump cut voulu),
   image+son ×1,08, coupes calées sur la grille d'images, trim/atrim+concat (jamais select/aselect).
   `trim_speech()` (bords seulement) est l'ancienne version.
2. `words, voix = P.vo_from_clips(clips)` (`pipeline.py:Project.vo_from_clips`) : concat audio → STT → même
   structure `words` que `vo()`.
3. Corps déjà assemblé → `P.edit_prebuilt(body, words, voix, out, ...)`.

**Cas C — chanson (AI Song)** : la chanson porte voix + musique, ancrée par whisper. Le **timing** peut venir du
STT, le **texte** des captions doit venir du script : passe `caption_words=` à `edit()`.
Lis les ancres dans un `captions.json` déjà aligné sur le brief, ne les cherche pas en
flou dans la sortie whisper (cascade de faux positifs). Débit chanté ≈ 0,40 s/mot (parlé ≈ 0,33).

STT (`pipeline.py:Project._stt`) : ElevenLabs `scribe_v1`, cache `<fichier>.words.json` invalidé si le média est
plus récent ; repli `whisper-cli` + `~/.cache/whisper/ggml-small.en.bin` (Linux) ou mlx-whisper (Mac).

## 3. Ancres et durées de plans

`tm = Project.timing(shots, words, tail=0.5, min_shot=...)` (`pipeline.py:Project.timing`) → `{id: (début, durée)}`.
- Début du 1er plan = 0 ; des suivants = `words[i].s - 0.05` (i = 1er mot de l'ancre, recherche **après** l'ancre
  précédente, comparaison normalisée `[^a-z0-9-]` supprimé, minuscules).
- Ancre introuvable → `SystemExit` qui nomme le plan : l'ancre n'est pas le texte exact de la VO ou chevauche
  la précédente. Corrige le brief, pas le code.
- Fin = dernier mot + `tail` (0,5 s). Pour une queue muette plus longue, l'exemple réel ajoute un faux mot
  `{"w":"FIN","s":fin+0.3,"e":fin+0.7}` à la liste d'ancrage et passe les vrais mots en `caption_words`.
- **`MIN_SHOT = 2.0` s** : tout plan plus court est **absorbé par le précédent** (le 1er plan, le hook, ne
  disparaît jamais : c'est le 2e qui est absorbé). `Project.MERGED = {absorbé: hôte}`. L'absorption se propage.
- `min_shot` accepte un dict `{"*": défaut, "P07": 1.2}` : décide **plan par plan**, d'après la cadence mesurée
  de la référence (la règle des 2 s ne vaut pas pour un VSL long ou une réf qui coupe à 1 s).
- **Passe le MÊME `min_shot` à `timing()` et à `edit()`** : `edit()` rappelle `timing()` ; sans le paramètre il
  repart à 2,0 s et monte moins de plans que prévu (13 clips payés jamais montés, 2026-10-19).
- Avant tout montage : imprime la table id/début/durée et `MERGED` ; un id absent n'existera pas à l'écran.
- `Project.at(words, "phrase")` → instant du 1er mot d'une phrase, pour caler un carton/calque sur la parole.

## 4. Segments 1080x1920 (un fichier par plan)

`edit()` cale chaque coupe sur la **grille 30 i/s en temps absolu** : `q(t)=round(t*30)/30`, durée = `q(a+d)-q(a)`
(sinon dérive 0,4 s sur 24 plans), puis `segment(sh, d)` (`pipeline.py:Project.segment`). Sortie : sans audio,
`-t d`, normalisée par `NORM = scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30,setsar=1,format=yuv420p`.
- **clip** : `trim=0:usable`, `usable = min(durée clip, use_first, d*speed)`, `setpts=(d+0.05)/usable*PTS`,
  `reverse` optionnel, `tpad=stop_mode=clone`. Clip plus court que le plan = **ralenti** : à éviter, génère
  le clip ≥ plan + 0,3 s (`_anim_lote.py:secs` = `max(2, ceil(d+0.3))`, assert dans `Anim.shots`).
  `use_first` garde le début propre d'un clip qui dérape (texte inventé, fin qui contredit le hook).
  `speed` > 1 joue `d*speed` s de clip en `d` (réf qui accélère ses clips).
- **still** : `n = max(1, round(d*30))` images (**round, jamais ceil** : +1,6 s de dérive sur 121 plans),
  upscale ×2 puis `zoompan=z='1+0.0005*on'` centré, `fps=30`. Les lots récents bornent le push-in pour ne
  jamais couper une étiquette (`_lote.py:Lot.seg_zoom`, `maxz=0.05`, `nozoom=` pour les plans fixes purs).
- **vsplit** (haut/bas) pour comparer deux personnes, **jamais split G/D avec une personne** (crop 50 % de
  largeur illisible). Séparateur blanc 6 px. Les sources ne sont que ralenties (`max(1, …)`).
- **avatar** : fond `bg` (+`bgoff` pour reprendre un b-roll là où il s'est arrêté) + masque `avatar` (gris,
  BiRefNet, `format=gray`, jamais re-seuillé) + couleurs `avatar_rgb` → `alphamerge`, largeur `aw=0.41 W`,
  centrée `ax=0.34 W`, calée en bas (`y=H-h`). `fixed=True` par défaut : **aucun recadrage auto**, même taille
  et même place sur tous les plans. Le cadrage (buste, rien sous la taille) se décide dans la first frame.
- **Cache** : réutilisé seulement si sources pas plus récentes + même clé (`kind`, sources, tous les réglages
  sauf `anchor`, écrite dans `<id>.src`) + durée à 1/30 s près. Sinon supprimé et refait. Après un changement
  de code de segment, supprime `segments/*.mp4` toi-même.
- Version animée d'une animatique : segments dans un autre dossier (`segments_anime/`), durées identiques à
  l'animatique (`_anim_lote.py:Anim.brancher`, `Anim.verifier_durees`).

## 5. Concat

`segments/list.txt` → `ffmpeg -f concat -safe 0 -i list.txt -c copy body.mp4` (`Project.edit`). Les segments sont
muets et homogènes (30 i/s, yuv420p, 1080x1920) : `-c copy` est sûr ici. **Ne concatène jamais en `-c copy`
des segments AVEC audio AAC** (+28 ms par segment, 1,95 s de dérive en fin de vidéo, `qc.py:lag_fenetres`).
`total = Σ durées calées`. Les plans absorbés ne sont pas montés.

## 6. Captions

`P.captions(words, total, style, ypos, size=58, mute=(), cuts=())` (`pipeline.py:Project.captions`), appelée par
`edit()` : un PNG 1080x1920 transparent par chunk (ou par mot pour les styles karaoké) + `captions/list.txt`
(`ffconcat` avec durées), posé en `overlay` sur `body`. Détail de chaque style : `references/captions.md`.
- Style = celui **relevé sur la référence** (28 styles : `box`, `yellow`, `karaoke`, `whitebox`, `unmot`…).
  Défaut `edit()` : `box`, `ypos=0.56` ; `edit_prebuilt()` : `plain`, `ypos=0.78`.
- `ypos(t)` est une fonction du temps : un chunk ne chevauche jamais un changement de position.
- **Une caption ne cache JAMAIS ce qui compte dans le plan** : visage, regard, bouche, produit/étiquette/prix,
  et le sujet de la phrase (le geste, la zone du corps montrée, la fuite, l'objet qu'on désigne). Le `ypos` se
  choisit **plan par plan**, avant le montage final, sur la planche `P.zones(ids, out)`
  (`pipeline.py:Project.zones` : 2 images par plan à 20 %/80 %, bandes des ypos candidats) — les sujets bougent
  dans un clip, regarde les deux images. Table `YPOS = {"P01": 0.36, …}` dans `build.py`, puis
  `ypos=lambda t: next((YPOS[s] for s, (a, d) in tq.items() if a <= t < a + d), défaut)` (`tq` = durées calées).
  Zones libres typiques : poitrine/t-shirt sous le visage, ciel/mur au-dessus des têtes, table/sol sous un sachet.
  Une position qui change aux coupes donne du rythme ; jamais de changement au milieu d'un plan.
- Un chunk ne dépasse jamais 0,86 W ; se coupe sur `. , ? ! :` ; `ligne`/`film`/`majligne`/`sitcom`/`karaoke`
  coupent sur le marqueur invisible **U+2063** posé par l'appelant en fin de vers.
- Une caption s'arrête à la **1re coupe de plan après son dernier mot** (`cuts`, fourni par `edit()`).
- `caption_mute=[id | (a, z)]` : plages sans texte (carton POV sur le hook) ; la place dans la timeline reste.
- Texte dans un fond (native, whitebox, pill, violet, pov) : boîte calée sur l'**encre** (`textbbox`), jamais
  sur l'origine PIL (sinon 37 px au-dessus, 2 px dessous). Vérifie pad haut = pad bas à 1 px.
- `P.keys` = noms propres gardés en casse d'origine (styles bas de casse) ou mot jaune (style `key`).
- Polices = les **vrais** fichiers (Arial Black/Bold, Impact Mac, Liberation, DejaVu, Montserrat) : une police
  « équivalente » change les métriques donc le découpage.

## 7. Calques (overlays), cartes, flashs, CTA

`edit(..., overlays=[...], cards=[...], flash=[...])` (`pipeline.py:Project.edit`).
- **overlays** : `(png, début, fin)` ou `(png, id_plan)`. PNG plein cadre 1080x1920 transparent, entrée
  `-loop 1 -framerate 30`, `overlay=0:0:enable='gte(t,a)*lt(t,z)'` (semi-ouvert, jamais `between`).
  Début tombant ≤ 0,25 s après une coupe → recalé à `coupe - 1/60` ; fin pile sur une coupe → `fin - 1/60`.
  ⚠ `(png, id)` sur un plan absorbé → KeyError (les overlays ne suivent pas `MERGED`) : vérifie `MERGED` avant.
- **cards** : `(png, cx, cy, a, z)` en ratios W/H, carte b-roll à coins arrondis (`card_png(path, src, w=0.42,
  radius=36)`) qui entre en zoom 0,60→1 en 0,25 s et sort 1→0,60 en 0,20 s, par-dessus le plan qui continue.
- **flash** : `[id]` → flash blanc 2 images (45 % puis 20 %) sur la coupe d'entrée ; jamais sur t=0 ; suit
  `MERGED`. Pas de `xfade` : il consomme de la durée et décale toute la voix ancrée au mot.
- Générateurs PNG (0 crédit) : `pov_png` (carton blanc texte noir, Arial Black 62, y=0,40, pad 26),
  `text_png` (textes libres), `bandeau_png` (bandeau titre haut, 16 % H, rouge `(206,26,26)` par défaut, texte
  blanc MAJUSCULES, texte **verbatim du brief**), `cta_meta_png` (fausse UI Meta : pastille blanche + bouton
  marine `(28,42,92)`, haut gauche), `card_png`. Calques maison : dessine en PIL, centre sur l'encre.
- Un calque en ouverture se cale sur `tm[id][0]` calé grille ; un calque sur la parole sur `Project.at()`.

## 8. Audio : voix, musique, SFX

Graphe audio de `edit()` (détail et valeurs : `references/audio.md`) :
- Voix `apad=whole_dur=total`. Musique (si `self.music` existe) : `-stream_loop -1` (sinon fin muette),
  `atrim=0:total`, `volume=music_volume`, `afade in 0.6 s`, `afade out` 2,0 s finales, **ducking**
  `sidechaincompress=threshold=0.03:ratio=6:attack=15:release=350` déclenché par la voix.
- `music_volume` : défaut code 0,08 ; **règle Kevin depuis 2026-10-13 : 0,04** ; `0.0`/`music=None` si la
  référence n'a pas de musique (UGC « filmé au téléphone »). Choix du morceau : banque validée (else_paris
  pour le sérieux), jamais une musique joyeuse sur un sujet de honte. La musique n'est jamais générée.
- **SFX** : `sfx=[(fichier, t, volume)]` → `volume`, `adelay`. Seulement si la référence en a ou si Kevin le
  demande (règle par défaut : voix + musique, pas de bruitages).
- Mix : `amix=...:duration=first:normalize=0,aresample=44100`. **Jamais `loudnorm` dans le graphe** (avale ~3 s
  de voix, sort en 192/96 kHz, son joué 14 % trop vite : 22 vidéos livrées fausses).

## 9. Loudness et export

- Encodage `edit()` : `libx264 -crf 19 -preset medium`, `aac 192k 44100 Hz`, `-t total`, `-movflags +faststart`.
- Puis `Project.loud_fix(out)` : mesure `ebur128`, jusqu'à 3 passes `volume=(-14-I)dB,alimiter=limit=0.95` tant
  que |I+14| > 0,4, puis `alimiter=limit=0.89` final, vidéo en `-c:v copy`. Renvoie les LUFS mesurés.
  `edit()` renvoie `(lufs, total)`, `edit_prebuilt()` renvoie `lufs`.
- Un livrable sort **toujours** de `build.py montage` (= `edit`). Ne copie jamais `body.mp4`, un segment ou un
  clip comme final : bonne durée, **aucun son, aucune caption**.
- `scripts/autoad.py:main` a un montage v0 (concat + `loudnorm=I=-14:TP=-1`, crf 20) : **ne l'utilise pas** pour
  livrer, il contient exactement le loudnorm interdit.

## 10. QC (obligatoire, détail `references/qc.md`)

```
python3 scripts/qc.py <projet>/ <projet>/<video>.mp4      # autant de paires que de vidéos
```
Doit finir sur `✅ tout est livrable` (exit 0). Vérifie : porte2.md (dernier verdict non ⛔), intégrité décodage,
audio 44 100 Hz, audio décodé = durée vidéo ±0,6 s, décalage VO/montage < 0,15 s (10 premières s), version
`anime` : durée ±0,1 s et pire fenêtre < 60 ms, synchro par segments (`final/list.txt`, `segments_k/list.txt`)
écart < 40 ms, plans figés ≥ 2,5 s (alerte), loudness -14 ±0,7 LUFS.
Puis QC visuel, **toi-même** :
- planche : 2 frames par plan (20 % et 80 %) depuis `plan_durees.json` (`_lote.py:Lot.planche`) ou
  `P.sheet(files, out)` ; regarde-la vraiment ;
- frames **aux coupes** et aux bornes de chaque calque : aucun calque/caption ne déborde d'une image sur le
  plan voisin, aucune frame du plan suivant ne fuit avant un carton ;
- captions : orthographe = script (faute d'écoute mineure qui sonne pareil tolérée ; seuls comptent noms de marque/produit, chiffres et mots qui changent le sens), aucun `[tag]`, rien hors cadre, centrage dans le fond ;
- captions : sur la planche finale, **aucune** ne couvre un visage, un produit/étiquette ou le sujet du plan
  (sinon corrige `YPOS` et remonte) ;
- coupes détectées (`select='gt(scene,0.25)'`) vs durées attendues : écart > 0,1 s = dérive ;
- timecodes signalés « figés » regardés en premier ;
- fin = CTA relevé sur la référence ; si la musique est plus courte que la vidéo, mesure le niveau dans un
  silence de voix après sa fin (lit musical présent ≈ 1,5-2 dB).
- dossier de livraison : chaque `.mp4` a une piste audio et un `mean_volume` (`volumedetect`).

## 11. Pièges connus → parade

| Piège | Parade (code) |
|---|---|
| Cache de segment périmé (durée/source/réglage changé) | clé `.src` + mtime + durée (`segment`) ; sinon `rm segments/*.mp4` |
| Cache STT d'un clip refait | invalidé par mtime (`_stt`) |
| Cache VO servi après changement de tempo | sidecar `vo_tempo.txt` (`vo`) |
| `[slowly]` brûlé à l'écran | filtré dans `vo`, erreur dans `captions` |
| Plan demandé absorbé par la règle des 2 s | imprimer `timing` + `MERGED` avant ; même `min_shot` partout |
| Calque qui clignote 1 frame sur la coupe | `gte*lt`, recalage ±1/60 (`edit`) ; PNG en `-framerate 30` |
| Caption qui déborde sur le plan suivant | `cuts` (`captions`, via `edit`) |
| Dérive image/voix qui grandit | grille 30 i/s absolue + `round` (`edit`, `segment`) ; contrôle des coupes |
| Musique qui s'arrête avant la fin | `-stream_loop -1` (`edit`, `edit_prebuilt`) |
| Pas de musique → crash | `music=None` géré (`edit`) |
| Son 96 kHz / 3 s de voix perdues | pas de `loudnorm` dans le graphe ; `loud_fix` |
| Mauvais mots STT incrustés (chanson) | `caption_words=` texte du script |
| Incrustation qui « respire » | `fixed=True`, aucun `subject_bbox` par plan |
| Détourage troué/halo | masque BiRefNet continu en `alphamerge`, jamais `colorkey`/re-seuil |
| Lipsync qui dérive dans un clip resserré | `trim/atrim+concat` sur la grille d'images (`tighten_clip`) |
| `edit` concurrents → mp4 corrompu | un seul `edit` à la fois ; `ffmpeg -v error -f null` |
| Caption qui couvre un visage / le produit / le sujet | `YPOS` plan par plan choisi sur `P.zones()` ; planche finale |
| Caption de la phrase précédente sur la 1re image du plan suivant | `option framerate 30` dans `captions/list.txt` (`captions`) + `setpts=N/30/TB` sur le corps (`edit` ; **pas encore dans `edit_prebuilt`**) |
| Prix « $39.90 » affiché « $3990 » | `.`/`,` entre deux chiffres gardés par le retrait de ponctuation (`captions`) |
| `edit_prebuilt` diverge d'`edit` | pas de ducking/fade-in, overlays sans `-loop/-framerate`, captions sans `cuts` : relis les deux quand tu touches l'audio |

## 12. Checklist finale (toutes cochées avant de dire « livré »)

- [ ] `len(words) == len(SCRIPT.split())`, aucun mot entre crochets.
- [ ] Table `timing` imprimée : nombre de plans montés = attendu, `MERGED` compris et voulu.
- [ ] Même `min_shot` passé à `timing()` et `edit()`.
- [ ] Aucun clip plus court que son plan (pas de ralenti) ; `use_first` sur les fins qui dérapent.
- [ ] Style et taille des captions = relevé de la référence ; texte des captions = script.
- [ ] `ypos` choisi plan par plan sur `P.zones()` : aucune caption sur un visage, un produit/étiquette ou le sujet
      du plan, vérifié sur la planche finale.
- [ ] Calques PNG plein cadre, texte centré sur l'encre, texte verbatim du brief ; CTA = celui de la référence.
- [ ] Musique : morceau validé, `music_volume` 0,04 (ou 0 si la réf n'en a pas), bouclée ; SFX seulement si réf.
- [ ] Sortie produite par `edit()`/`edit_prebuilt()` + `loud_fix` (≈ -14 LUFS), jamais un intermédiaire.
- [ ] `qc.py` → `✅ tout est livrable`.
- [ ] Planche finale + frames aux coupes regardées ; passages figés vérifiés.
- [ ] Livrable rangé avec un nom explicite ; récap : durée, LUFS, plans montés/absorbés, écarts signalés.
