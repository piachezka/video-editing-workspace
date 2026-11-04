# Recettes ffmpeg réellement utilisées (recopiées du code)

`ff(*args)` = `ffmpeg -y -v error …` avec `check=True` (`pipeline.py:ff`). `duration(p)` = ffprobe
`format=duration`. Toutes les valeurs ci-dessous sont celles du code ; `W=1080`, `H=1920`, `d` = durée du plan.

## Normalisation d'un plan (`pipeline.py:NORM`)
```
scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30,setsar=1,format=yuv420p
```
Rallonge de sécurité : `tpad=stop_mode=clone:stop_duration={d+1}` puis `-t {d:.3f}`.

## Segment `clip` (`Project.segment`)
```
ffmpeg -i SRC -an -vf "trim=0:{usable},setpts=PTS-STARTPTS,{reverse,}setpts={(d+0.05)/usable}*PTS,NORM,tpad=…" -t {d} OUT
# usable = min(durée(SRC), use_first, d*speed)
```

## Segment `still` (`Project.segment`)
```
ffmpeg -loop 1 -i PNG -vf "scale=2160:3840:force_original_aspect_ratio=increase,crop=2160:3840,
  zoompan=z='1+0.0005*on':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={n}:s=1080x1920:fps=30,format=yuv420p"
  -frames:v {n} OUT          # n = max(1, round(d*30))
```
Variante bornée des lots récents (`_lote.py:Lot.seg_zoom`, `maxz=0.05`) : `k = 0 if id in nozoom else
min(0.0005, maxz/n)` et `zoompan=z='1+{k}*on'` (même chaîne sinon).

## Segment `vsplit` / `split`
```
half_v = scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,crop=1080:960,fps=30,setsar=1
[0:v]setpts={sT}*PTS,half_v,tpad…[t];[1:v]setpts={sB}*PTS,half_v,tpad…[b];
[t][b]vstack,format=yuv420p,drawbox=x=0:y=957:w=1080:h=6:color=white:t=fill     -an -t {d}
# split : crop=540:1920, hstack, drawbox=x=537:y=0:w=6:h=1920 ; s = max(1, (d+0.05)/durée(source))
```

## Segment `avatar` (incrustation détourée)
```
[0:v]setpts={sb}*PTS,NORM,tpad…[b];                 # fond (option -ss bgoff)
[1:v]setpts={sa}*PTS,{crop|null},format=gray[al];   # masque BiRefNet (lossless)
[2:v]setpts={sa}*PTS,{crop|null}[c];                # couleurs (avatar_rgb)
[c][al]alphamerge,scale={int(1080*aw)}:-2[a];
[b][a]overlay=x={int(1080*ax)}-w/2:y=H-h:eof_action=pass,format=yuv420p      -an -t {d}
# aw=0.41, ax=0.34, fixed=True -> crop "null" ; sinon crop=subject_bbox(avatar, top=atop=0.52)
```

## Concat du corps (`Project.edit`)
```
segments/list.txt : file '<segment>' (une ligne par plan monté)
ffmpeg -f concat -safe 0 -i segments/list.txt -c copy body.mp4
```

## Graphe final (`Project.edit`) — ordre des entrées
`0` body · `1` captions (`-f concat -safe 0 -i captions/list.txt`) · `2..` cartes (`-loop 1 -framerate 30 -t TOTAL -i png`)
· puis overlays (même options) · puis VO · puis musique (`-stream_loop -1`) · puis SFX.
```
[1:v]format=rgba,fps=30[c];[0:v][c]overlay=0:0:eof_action=pass[v0];
# carte k (zoom in 0.25 s de 0.60 à 1, zoom out 0.20 s de 1 à 0.60) :
[2+k:v]format=rgba,scale=w='iw*(if(gt(t,Z-0.2), 1-0.40*(t-(Z-0.2))/0.2, min(1,0.60+0.40*(t-A)/0.25)))':h=-2:eval=frame[kK];
[last][kK]overlay=x={cx}*W-w/2:y={cy}*H-h/2:enable='gte(t,A)*lt(t,Z)'[cK];
# overlay k :
[i:v]format=rgba[oK];[last][oK]overlay=0:0:enable='gte(t,A)*lt(t,Z)'[vK+1];
# flash sur la coupe A d'un plan :
[last]drawbox=x=0:y=0:w=iw:h=ih:color=white@0.45:t=fill:enable='gte(t,A)*lt(t,A+1/30)',
      drawbox=x=0:y=0:w=iw:h=ih:color=white@0.20:t=fill:enable='gte(t,A+1/30)*lt(t,A+2/30)'[fK];
[last]format=yuv420p[v];
# audio avec musique :
[VO:a]apad=whole_dur=TOTAL,asplit=2[vo][key];
[MUS:a]atrim=0:TOTAL,asetpts=PTS-STARTPTS,volume=MV,afade=t=in:d=0.6,afade=t=out:st=TOTAL-2.0:d=2.0[m];
[m][key]sidechaincompress=threshold=0.03:ratio=6:attack=15:release=350[duck];
[SFXk:a]volume=V,adelay=MS|MS[sfxk];
[vo][duck][sfx…]amix=inputs=N:duration=first:normalize=0,aresample=44100[a]
# sans musique : [VO:a]apad=whole_dur=TOTAL[vo]; puis amix (si SFX) ou [vo]aresample=44100[a]
```
Sortie :
```
-map [v] -map [a] -c:v libx264 -crf 19 -preset medium -c:a aac -b:a 192k -ar 44100 -t TOTAL -movflags +faststart OUT
```
Recalages d'overlay : début dans `[coupe, coupe+0.25]` → `coupe - 1/60` ; fin à ±1 ms d'une coupe → `fin - 1/60`.

## `Project.edit_prebuilt` (corps déjà assemblé)
```
-i BODY -f concat -safe 0 -i captions/list.txt [-i png …] -i VO [-stream_loop -1 -i MUSIQUE]
[1:v]format=rgba,fps=30[c];[0:v][c]overlay=0:0:eof_action=pass[v0];
[k+2:v]format=rgba[oK];[last][oK]overlay=0:0:enable='gte(t,A)*lt(t,Z)'[vK+1];
[VO:a]aresample=44100[va];[M:a]aresample=44100,volume=MV,afade=t=out:st=TOTAL-2:d=2[ma];
[va][ma]amix=inputs=2:duration=first:normalize=0,aresample=44100[a]
→ mêmes options de sortie (crf 19…) puis loud_fix
```
⚠ Ici les PNG d'overlay sont passés **sans** `-loop 1 -framerate 30` (corrigé dans `edit` seulement).

## Loudness (`Project.loud_fix`)
```
ffmpeg -hide_banner -i OUT -vn -af ebur128 -f null -                                # mesure I
ffmpeg -i OUT -c:v copy -af "volume={-14-I:.2f}dB,alimiter=limit=0.95:level=false" -c:a aac -b:a 192k -ar 44100 -movflags +faststart TMP
ffmpeg -i OUT -c:v copy -af "alimiter=limit=0.89:level=false" -c:a aac -b:a 192k -ar 44100 -movflags +faststart TMP
```

## Voix
```
# raccourcir les silences (Project.tighten)
ffmpeg -hide_banner -i vo.mp3 -af silencedetect=n=-38dB:d=0.12 -f null -
[0:a]atrim=A:Z,asetpts=PTS-STARTPTS,afade=t=in:d=0.01,afade=t=out:st={Z-A-0.01}:d=0.01[pK]; … concat=n=N:v=0:a=1[,atempo=T][a]
# recoller des morceaux TTS (Project.vo)
[0:a][1:a]…concat=n=N:v=0:a=1[a]  -c:a libmp3lame -b:a 128k
# resserrer un clip parlant (Project.tighten_clip)
[0:v]trim=A:Z,setpts=PTS-STARTPTS[vK];[0:a]atrim=A:Z,asetpts=PTS-STARTPTS[aK];
[v0][a0]…concat=n=N:v=1:a=1[vc][ac];[vc]setpts=PTS/1.08[v];[ac]atempo=1.08[a]
-c:v libx264 -crf 18 -c:a aac -b:a 192k -ar 44100
# rogner un clip sur sa parole (Project.trim_speech)
ffmpeg -ss A -i CLIP -t {Z-A} -c:v libx264 -crf 18 -c:a aac -b:a 192k -ar 44100 OUT
# voix des clips (Project.vo_from_clips)
ffmpeg -f concat -safe 0 -i _vo_concat.txt -vn -ar 44100 -b:a 192k vo.mp3
```

## Contrôles
```
ffmpeg -v error -i OUT.mp4 -f null -                       # intégrité (qc check 2)
ffprobe -v error -select_streams a -show_entries stream=sample_rate -of csv=p=0 OUT.mp4   # 44100
ffmpeg -v info -i OUT.mp4 -af volumedetect -f null -       # mean_volume présent = vrai son
ffmpeg -i OUT.mp4 -vf "select='gt(scene,0.25)',showinfo" -f null -   # coupes réelles vs durées attendues
ffmpeg -ss T -i OUT.mp4 -frames:v 1 frame.png              # frame à une coupe / un calque
# planche d'un clip (_anim_lote.py:Anim.strip)
ffmpeg -i CLIP -vf "fps=3,scale=240:-2,drawtext=text='ID %{pts\:hms}':x=4:y=4:fontsize=18:fontcolor=yellow:box=1,tile=6xR" -frames:v 1 strip.png
```
`Project.sheet(files, out, cols=6, w=240)` : planche PIL (images, ou **dernière** image d'un mp4 via
`-sseof -0.3`, écrite dans `/tmp`).

## Montage v0 de `autoad.py:main` (référence, ne pas livrer avec)
```
[i:v]scale=W:H:force_original_aspect_ratio=increase,crop=W:H,fps=30,setsar=1,format=yuv420p[vi]; … concat=n=N:v=1:a=0[v]
[m] volume={music_volume=0.15} ; [vo][m]amix=inputs=2:duration=first:normalize=0,loudnorm=I=-14:TP=-1,apad[a]
-c:a aac -b:a 192k -shortest -c:v libx264 -crf 20 -preset medium -movflags +faststart
```
Contient le `loudnorm` interdit dans `pipeline.py` et aucun `aresample` : risque 96 kHz / voix coupée.
