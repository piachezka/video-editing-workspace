# Captions — `pipeline.py:Project.captions`

Signature : `captions(words, total, style="box", ypos=lambda t: 0.56, size=58, mute=(), cuts=())`.
Appelée par `Project.edit` (avec `mute` et `cuts` calculés) et `Project.edit_prebuilt` (sans `mute` ni `cuts`).
Sortie : `captions/c<chunk>_<mot>.png` (1080x1920 RGBA) + `captions/blank.png` + `captions/list.txt` au format
`ffconcat version 1.0` (`file` / `duration`). **Le dossier `captions/*.png` est vidé à chaque appel.**
Le montage pose cette séquence par `[1:v]format=rgba,fps=30[c];[0:v][c]overlay=0:0:eof_action=pass`.

## Mécanique commune

1. **Garde-fou crochets** : si un mot contient `[` ou `]` → `SystemExit` (un tag d'intonation burné ne se
   rattrape pas). `vo()` les retire déjà ; la liste peut venir d'un STT ou d'un fichier édité.
2. **Transformation du mot** `up(s)` selon le style (casse, ponctuation) — tableau plus bas.
3. **Découpage en chunks** (boucle sur les mots) :
   - nouveau chunk si `ypos(mot.s) != ypos(1er mot du chunk)` (jamais à cheval sur un changement de position) ;
   - si la largeur rendue du chunk dépasse **0,86 × 1080** px, le dernier mot part dans un nouveau chunk
     (sauf styles `ligne`, qui se replient sur plusieurs lignes) ;
   - fin de chunk si nombre de mots atteint, ou longueur brute (caractères joints) dépassée — le mot qui dépasse
     reste dans le chunk —, ou mot finissant par `. , ? ! :` ;
   - styles à vers (`ligne`, `film`, `ligne_ombre`, `majligne`, `sitcom`) : fin de chunk **uniquement** sur un mot
     qui se termine par **U+2063** (séparateur invisible posé par l'appelant) ; `karaoke` coupe sur U+2063 en plus
     de la règle générale.
4. **Durées** : `chunk_end` = début du chunk suivant (ou `total`), **borné à la 1re coupe de plan > début du
   dernier mot** (`cuts`). Styles karaoké (une image par mot) : chaque image dure jusqu'au mot suivant ; la
   dernière jusqu'à `min(chunk_end, fin du dernier mot + 0,4 s)`. Styles statiques (une image par chunk) :
   `min(chunk_end, fin du dernier mot + 0,4 s)`. Durée mini 0,04 s. Les trous sont remplis par `blank.png`.
5. **Position** : `y = int(1920 × ypos(début du chunk))` = origine PIL du texte (haut de l'ascendante), centré
   horizontalement. Ce n'est PAS le centre du texte.
6. **mute** : `[(a, z)]` → l'image du chunk qui démarre dans la plage est remplacée par `blank.png` (la place
   dans la timeline est gardée). `edit(caption_mute=[id_plan | (a, z)])` le construit.
7. **Fond** (native, pill, violet, whitebox et variantes) : `rounded_rectangle((x-24, ink_top-18, x+largeur+24,
   ink_bottom+18))` où `ink = textbbox(...)` = l'**encre** réelle. Jamais un pad calculé sur `y`.

## Tailles par défaut

`size=58` partout, sauf : `red1` → **95** (si 58 passé), `unmot`/`unmot_maj` → **92** (si 58 passé),
`sitcom` → **56 fixe** (ignore `size`). Interligne des styles à vers : `1.2 × size`.

## Polices (constantes en tête de `pipeline.py`)

| Constante | Fichier | Styles |
|---|---|---|
| `FONT_BLACK` | `$FONTS_DIR/Arial Black.ttf` | box, plain, yellow, native, key, pill, rose, teal, ionix, pixar, violet (+ `pov_png`, `bandeau_png`, `cta_meta_png`) |
| `FONT_BOLD` | `$FONTS_DIR/Arial Bold.ttf` | thin, phrase, ligne, ligne_ombre, vert |
| `FONT_IMPACT` | `$FONTS_DIR/Impact.ttf` | red, red1 |
| `WHITEBOX_FONT` | `/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf` | whitebox, whitebox3, capsbox, lowbox, blackbox |
| `FILM_FONT` | `.../liberation/LiberationSans-BoldItalic.ttf` | film, majligne, karaoke |
| `UNMOT_FONT` | `resources/fonts/Montserrat-SemiBold.ttf` | unmot |
| `UNMOT_MAJ_FONT` | `resources/fonts/Montserrat-VF.ttf`, instance `ExtraBold` | unmot_maj |
| `MONO_FONT` | `/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf` | mono |
| (en dur) | `.../liberation/LiberationSans-Regular.ttf` | sitcom |

`FONTS_DIR` : variable d'env, sinon `/System/Library/Fonts/Supplemental` (Mac) ou `/usr/local/share/fonts/mac`
(copies des fichiers Mac sur le serveur). Une police libre « équivalente » change les métriques, donc le découpage.

## Les styles

Légende : **K** = karaoké (une image par mot, le mot actif marqué) ; **S** = statique (chunk entier d'un coup).
Mots max / caractères max = règle de fin de chunk. Contour = `stroke_width` noir sauf mention.

| Style | Rendu | Casse / ponctuation | Chunk | Contour, ombre, fond |
|---|---|---|---|---|
| `box` (défaut `edit`) | K, mot actif dans un pavé violet `(124,58,237)` contour blanc 4 px, rayon 14 | MAJ, `.,?!:;"“”` retirés | 4 mots / 20 car. | contour 5 |
| `teal` | K, mot actif sur pavé dégradé bleu→teal, rayon 14 | MAJ, sans ponct. | 4 / 20 | contour 5 |
| `yellow` | K, mot actif en jaune `(255,232,0)` | MAJ, sans ponct. | 4 / 20 | contour 5 |
| `red` | K, mot actif sur pavé rouge `(229,25,35)` rayon 8, Impact | MAJ, sans ponct. | 4 / 20 | contour 5 |
| `red1` | comme `red`, **1 mot à l'écran**, 95 px | MAJ | 1 | contour 5 |
| `ionix` | K, mot actif sur pavé violet `(116,8,224)` rayon 12 | MAJ, sans ponct. | 6 / 34 | pas de contour, ombre +3 px α120 |
| `pixar` | **1 mot**, rose bonbon `(255,94,162)` cerné de **blanc** 7 px | MAJ, sans ponct. | 1 | contour blanc 7 |
| `plain` (défaut `edit_prebuilt`) | S, blanc | MAJ, sans ponct. | 3 / 20 | contour 5 |
| `key` | S, blanc ; le 1er mot présent dans `P.keys` en jaune `(255,228,0)` | MAJ, sans ponct. | 3 / 20 | contour 5 |
| `rose` | S, MAJ blanches ; le 1er mot contenant un **chiffre** sur pavé magenta `(236,0,140)` | MAJ, sans ponct. | 4 / 20 | contour 5 (0 sur le mot surligné) |
| `native` | S, texte noir dans un pavé **blanc opaque**, rayon 8 | MAJ, sans ponct. | 4 / 20 | aucun |
| `pill` | S, texte blanc dans une pilule **noire** α235, rayon 26 | MAJ, sans ponct. | 4 / 20 | aucun |
| `violet` | S, pilule blanche, texte `#CF00FF` | minuscules, sans ponct. | 4 / 20 | aucun |
| `thin` | S, petit blanc fin | minuscules, sans ponct. | 4 / 20 | contour 1, ombre α170 |
| `phrase` | S, blanc gras | **casse et ponctuation gardées** (guillemets retirés) | 3 / 20 | aucun contour, ombre α120 |
| `whitebox` | S, texte noir dans **sa** boîte blanche rayon 16 ; un mot peut porter sa couleur via `{"c": (r,g,b)}` | casse et ponct. gardées | 5 / 28 | aucun |
| `whitebox3` | `whitebox` en groupes courts | idem | 3 / 20 | aucun |
| `capsbox` | `whitebox3` en MAJUSCULES, ponctuation gardée | MAJ | 3 / 20 | aucun |
| `lowbox` | `whitebox` en minuscules (`GLP…` gardé), seul `?` gardé | min. | 5 / 28 | aucun |
| `blackbox` | texte **blanc** dans une boîte **noire** α191, rayon 16 | casse et ponct. gardées | 4 / 24 | aucun |
| `mono` | S, DejaVu Sans Mono blanc | minuscules, `.,;:"` retirés (`?!` gardés) | 6 / 34 | ombre α170 |
| `vert` | K, mot dit en vert `(120,230,105)` | minuscules sauf `P.keys`/« I » | 3 / 20 | ombre α120 |
| `karaoke` | K, italique gras blanc, mot chanté en jaune `(255,232,0)` | minuscules sauf `P.keys`/« I » | 4 / 20 + U+2063 | contour 3, ombre α120 |
| `unmot` | **1 mot**, Montserrat SemiBold blanc 92 px | minuscules sauf `P.keys`/« I » | 1 | contour 4, ombre α120 |
| `unmot_maj` | **1 mot**, Montserrat ExtraBold MAJ 92 px | ponctuation retirée en tête/queue seulement (« 50% », « 90-DAY » entiers) | 1 | pas de contour, triple ombre (7,α90)(5,α150)(3,α200) |
| `sitcom` | S, Liberation Regular 56 px, une ligne | minuscules sauf `P.keys`/« I » | U+2063 + largeur | ombre α170 |
| `ligne` | S, un vers par caption, **replié** sur 2+ lignes | casse, ponct., MAJ d'insistance gardées | U+2063 | contour noir 2 |
| `ligne_ombre` | `ligne` sans contour, ombre douce | idem | U+2063 | ombre +3 px α140 |
| `film` | `ligne` en italique gras blanc | minuscules sans ponct. sauf « I », `P.keys` | U+2063 | ombre +3 px α140 |
| `majligne` | `ligne` en MAJ italique | MAJ, `.,;:` retirés | U+2063 | contour 3 + ombre +4 px α150 |

Repli des styles `ligne` : mots ajoutés tant que la ligne ≤ 0,86 W ; si la dernière ligne n'a qu'un mot et la
précédente plus de 2, un mot redescend (pas d'orphelin). Bloc centré verticalement autour de `y`.

## Règles d'usage

- Le style, la taille et la position se **relèvent sur la référence** (frame mesurée), ils ne se choisissent pas.
- `ypos` est une fonction : `lambda t: 0.40 if t < tm["P30"][0] else 0.71` remonte les captions sur un plan
  produit. Exemple réel (nuvel) : `yellow`, `ypos=lambda t: 0.71`.
- **Règle : une caption ne cache jamais ce qui compte** — visage (yeux, bouche), produit, étiquette, prix, et le
  sujet de la phrase (geste, zone du corps montrée, fuite, objet désigné). La hauteur relevée sur la référence est
  le point de départ ; elle bouge **plan par plan** dès qu'elle tomberait sur l'un de ces éléments.
  Procédure :
  1. après un premier `edit()` (ou `segment()`), `P.zones(ids, "_review/zones.jpg")` : 2 images par plan
     (20 %/80 %) avec la bande de chaque ypos candidat (0,14 / 0,30 / 0,42 / 0,56 / 0,70 / 0,82 par défaut) ;
  2. pour chaque plan, garde un ypos dont la bande est libre **sur les deux images** (le sujet d'un clip bouge) ;
     une caption centrée occupe ~25-75 % de la largeur, vérifie aussi les bords ;
  3. `YPOS = {"P01": 0.36, …}` dans `build.py` (un commentaire court par choix non évident), puis
     `ypos=lambda t: next((YPOS[s] for s, (a, d) in tq.items() if a <= t < a + d), 0.56)` avec `tq` calé sur la
     grille 30 i/s (comme `edit`) ;
  4. planche finale (avec captions) regardée plan par plan ; une caption qui touche un menton ou un objet → corrige.
  Zones libres typiques : t-shirt sous le visage, ciel/mur au-dessus des têtes, table/sol sous un sachet, couche
  de peau en haut d'un schéma. Le chunk ne chevauche jamais un changement de position : la caption change de
  place aux coupes, ce qui donne du rythme sans sauter au milieu d'un plan.
- Noms propres et mots en jaune : `P.keys = {"Ora", "GLP-1"}` (comparés au mot **déjà transformé** par `up`).
- Texte des captions ≠ texte d'ancrage possible : `edit(..., caption_words=words_du_script)`.
- Chanson / vers : poser `"⁣"` à la fin du dernier mot de chaque vers dans la liste de mots.
- Vérifier sur frame : centrage vertical dans le fond (pad haut = pad bas ±1 px), aucune caption hors cadre,
  aucune caption sur l'image suivant une coupe, orthographe = script (faute d'écoute mineure qui sonne pareil tolérée ; seuls comptent noms de marque/produit, chiffres et mots qui changent le sens).
