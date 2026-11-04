# QC — `scripts/qc.py`

## Lancer
```
python3 scripts/qc.py <projet>/ <projet>/<video>.mp4 [<projet2>/ <video2>.mp4 ...]
```
Sortie : une ligne ✅/❌ par contrôle, puis `✅ tout est livrable` (exit 0) ou `⛔ A NE PAS LIVRER : …` (exit 1).
Il importe `autoad` (donc lit `BRAIN_ENV`, voir `scripts/README.md`) et `numpy`. Il ne coûte rien.
**Il ne voit pas l'image** : le QC visuel se fait en plus, jamais à la place.

## Ce que vérifie `qc.py:check(proj, vid)`

| # | Contrôle | Seuil | Pourquoi |
|---|---|---|---|
| 7 | `<projet>/porte2.md` existe et son **dernier** verdict (`NE PAS CONTINUER` / `FEU VERT` / `animation autoris…`) n'est pas ⛔ | présent et vert | un lot sans contrôle plan par plan n'est pas livrable |
| 1 | intégrité : `ffmpeg -v error -i vid -f null -` ne renvoie rien | 0 erreur | un `edit` concurrent corrompt le mp4 en silence |
| 2 | fréquence de la piste audio | **44 100 Hz** | 96 kHz = bug `loudnorm`, son 14 % trop rapide |
| 3 | audio **décodé** (PCM 8 kHz) vs durée vidéo | écart < 0,6 s | le conteneur peut annoncer une durée sans son dedans |
| 4 | décalage VO / montage par corrélation d'enveloppe, 10 premières s | \|lag\| < 0,15 s | désynchro globale |
| 4b | version `anime.mp4` avec `voix_k.wav` : durée de la voix des clips | ±0,1 s | dérive de priming AAC / fin coupée |
| 4c | idem, décalage par **fenêtres de 10 s** sur tout le fichier (`lag_fenetres`) | pire < 60 ms | dérive qui grandit, invisible dans la 1re fenêtre |
| 6 | `final/list.txt` ou `segments_k/list.txt` présent : chaque segment parlant retrouvé à sa place (`sync_segments`, corrélation FFT des 3 premières s) | écart max-min < 40 ms | lipsync qui dérive segment après segment |
| — | plans figés : < 20 % des pixels (90x160 gris, 4 i/s) changent en 2,5 s (`figes`) | alerte ⚠ seulement | animatique figée 3-8 s ; regarder ces timecodes en premier |
| 5 | loudness `ebur128` intégrée | -14 ± 0,7 LUFS | norme de livraison |

### Choix de la piste de référence (check 4)
1. `<projet>/voix.wav` (piste voix mixte déjà montée) s'il existe, sinon `vo_tight.wav` ;
2. pour `anime.mp4` : `voix_k.wav` s'il existe ;
3. sinon, dans l'ordre : `vo*_tight.wav`, `vo*.mp3`, `vo*.wav`, `chanson*.wav` (AI Song), `musique_montee.wav`
   (format muet) ; on prend celle dont le nom contient le dernier segment `-xxx` du nom de la vidéo, sinon la 1re.
   Aucune → ❌ « aucune piste de voix off ».
**Nomme donc tes pistes selon ces conventions**, sinon le check compare à la mauvaise piste (faux décalage).

### Limites à connaître
- Le check 6 ne tourne **pas** sur un montage `Project.edit()` standard (il écrit `segments/list.txt`, muets) :
  une dérive de coupes y reste invisible. Contrôle manuel : coupes détectées
  (`select='gt(scene,0.25)'`) vs `plan_durees.json`, écart > 0,1 s = dérive.
- Le check 4 corrèle la VO avec le mix (musique comprise) sur 10 s ; il ne voit pas une dérive tardive.
- Le check 7 bloque tout projet hors de notre protocole : sans `porte2.md`, crée-le seulement si un contrôle plan
  par plan a réellement été fait (verdict écrit `FEU VERT`).
- La docstring annonce -14 ± 0,5 LUFS ; le code accepte ± 0,7.

## QC visuel (à faire soi-même, après `qc.py`)
1. Planche finale : 2 frames par plan (à 20 % et 80 % de sa durée) — `_lote.py:Lot.planche` ou
   `Project.sheet(files, out)`. La regarder.
2. Frames **aux coupes** (t et t+1/30) et aux bornes de chaque calque : rien ne fuit d'un plan sur l'autre.
3. Captions : orthographe = script (faute d'écoute mineure qui sonne pareil tolérée ; seuls comptent noms de marque/produit, chiffres et mots qui changent le sens), aucun `[tag]`, rien hors cadre ; dans un fond, pad haut = pad bas ±1 px.
4. Captions vs image : sur la planche finale, aucune caption sur un visage, un produit/étiquette/prix ou le sujet
   du plan (règle et procédure `P.zones()` : `captions.md`, Règles d'usage).
5. Plans signalés « figés » regardés en premier.
6. Hook : le visuel joue le texte du hook. Fin : CTA = celui relevé sur la référence.
7. Musique plus courte que la vidéo : mesurer le niveau dans un silence de voix après sa fin (1,5-2 dB attendus).
8. Dossier de livraison :
```sh
for f in *.mp4; do
  a=$(ffprobe -v error -select_streams a -show_entries stream=codec_type -of csv=p=0 "$f" | wc -l)
  v=$(ffmpeg -v info -i "$f" -af volumedetect -f null - 2>&1 | grep -o 'mean_volume.*')
  echo "$f  audio=$a  $v"
done
```
`audio=0` ou pas de `mean_volume` → ce n'est pas une vidéo finale.

## Points de QC de Kevin (contenu, `knowledge/auto-video-editing/QC.md`)
Chaque plan apporte quelque chose que la voix ne dit pas (son coupé, l'image dit-elle encore la phrase ?) ;
pauses raccourcies seulement entre phrases ; hook visuel = texte du hook ; plans lisibles, pas trop zoomés ;
captions centrées dans leur fond ; pas de plan < 2 s (sauf réf qui coupe plus vite) ; split vertical pour deux
personnes ; produit nommé = vrai produit à l'écran ; carton qui tient dans le cadre.
