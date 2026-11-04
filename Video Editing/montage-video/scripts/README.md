# scripts/ — copies conformes du code de montage

`pipeline.py`, `qc.py`, `autoad.py` sont des **copies non modifiées** de `/srv/ecom/tools/auto-video/` (2026-10-28).
`resources/fonts/` = `Montserrat-SemiBold.ttf`, `Montserrat-VF.ttf`, `DMSerifDisplay-Regular.ttf`.
Aucune clé n'est écrite dans ces fichiers : elles sont lues dans l'environnement (`os.environ`).
Sur notre serveur, utiliser les originaux de `tools/auto-video/` (ce sont eux qui évoluent).

## Dépendances

| Quoi | Utilisé par | Note |
|---|---|---|
| `ffmpeg` + `ffprobe` (PATH) | tout | filtres utilisés : `zoompan`, `tpad`, `alphamerge`, `overlay`, `drawbox`, `sidechaincompress`, `amix`, `silencedetect`, `atempo`, `alimiter`, `ebur128`, `concat`. **libass n'est pas nécessaire** : les captions sont des PNG PIL. `drawtext` (libfreetype) seulement pour les bandes de contrôle de `_anim_lote.py`. `autoad.py` préfère `/opt/homebrew/opt/ffmpeg-full/bin` s'il existe (Mac). |
| Python ≥ 3.9 | tout | stdlib + ci-dessous |
| `Pillow` | `pipeline.py` (captions, calques, planches, `text_bbox`) | importé dans les fonctions |
| `numpy` | `qc.py` (import au chargement), `pipeline.py` (`subject_bbox`, `text_bbox`, `relabel_bottom_line`) | |
| `whisper-cli` + `~/.cache/whisper/ggml-small.en.bin` | `Project._stt` (repli Linux si Scribe échoue) | optionnel |
| `uv` + `mlx-whisper` | `Project._stt` (repli Mac) | optionnel |

Sur le serveur : `/srv/ecom/.venv/bin/python` a Pillow 12.3 et numpy 2.5 (le `python3` système n'a pas PIL).

## Polices (chemins en dur dans `pipeline.py`)

| Fichier | Où le code le cherche | Comment l'avoir |
|---|---|---|
| `Arial Black.ttf`, `Arial Bold.ttf`, `Impact.ttf` | `$FONTS_DIR`, sinon `/System/Library/Fonts/Supplemental` (Mac), sinon `/usr/local/share/fonts/mac` | polices Apple/Microsoft, **non fournies ici** (licence). Les copier depuis un Mac et pointer `FONTS_DIR` dessus. Pas de substitut « équivalent » : les métriques changent le découpage des captions. |
| `LiberationSans-Bold/-BoldItalic/-Regular.ttf` | `/usr/share/fonts/truetype/liberation/` | paquet `fonts-liberation` (Debian/Ubuntu) |
| `DejaVuSansMono.ttf` | `/usr/share/fonts/truetype/dejavu/` | paquet `fonts-dejavu-core` |
| `Montserrat-SemiBold.ttf`, `Montserrat-VF.ttf` | `<dossier de pipeline.py>/resources/fonts/` (`pipeline.RES`) | fournies ici |

## Variables d'environnement

| Variable | Requise pour | 
|---|---|
| `ELEVENLABS_API_KEY` | `Project.vo()` (TTS) et `Project._stt()` (Scribe : `tighten_clip`, `trim_speech`, `vo_from_clips`). **Pas** pour `edit`, `captions`, `loud_fix`, `qc.py`. |
| `KIE_API_KEY` | génération uniquement (`image`, `clip`, `autoad.upload/kie_task`) — hors montage |
| `FONTS_DIR` | dossier des polices Arial/Impact (voir ci-dessus) |

## ⚠ `BRAIN_ENV` : le piège à l'import

`import pipeline` et `qc.py` appellent `autoad.env()`, qui **lit obligatoirement** le fichier
`Path(autoad.py).resolve().parents[2] / "Claude brain" / ".env"` et lève `FileNotFoundError` s'il n'existe pas.
Sur le serveur : `/srv/ecom/Claude brain/.env`. Ailleurs (ce dossier `scripts/` installé en
`<X>/montage-video/scripts/`), le fichier attendu est `<X>/Claude brain/.env` :
```sh
mkdir -p "<X>/Claude brain" && touch "<X>/Claude brain/.env"   # peut rester vide
export ELEVENLABS_API_KEY=...                                    # l'environnement a priorité (setdefault)
```
Format du fichier : `CLE=valeur` par ligne, `#` = commentaire.

## Autres chemins propres à notre serveur

- `Project.PACKSHOT` (`resources/brolls/produit/…`) : génération seulement, absent ici, sans effet sur le montage.
- `Project.sheet()` écrit ses vignettes de clips dans `/tmp`.
- `qc.py` exige `<projet>/porte2.md` avec un verdict vert (check 7, protocole interne) : sans lui, ❌.
- `autoad.py:main` (spec JSON → `tools/auto-video/out/<nom>/`) : pipeline v0, ne pas l'utiliser pour livrer
  (il met `loudnorm` dans le graphe).

## Utilisation

```sh
cd <projet>                       # build.py sur le modèle de references/exemple-build.md
python build.py vo && python build.py montage
python /chemin/vers/scripts/qc.py ./ ./animatique.mp4
```
Dans un `build.py` : `sys.path.insert(0, "/chemin/vers/scripts"); import pipeline as pl`.
