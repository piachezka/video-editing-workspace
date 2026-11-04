# Exemple : un `build.py` de montage minimal

Tiré du montage réel `creatives/lot-2026-10-26e/nuvel-90-days/build.py` (animatique : 31 plans fixes, voix off
homme, captions `yellow`, titre du hook, badge de fin, sans musique) et de sa version animée
`nuvel-90-days/anim.py` + `lot-2026-10-26e/_anim_lote.py`. Le code des frames/clips (génération) est retiré :
on suppose `frames/P01.png…` et éventuellement `clips_anime/P01.mp4…` déjà là.
Les dépendances du lot (`_lote.py`) sont remplacées par leur équivalent inline.

```python
#!/usr/bin/env python3
"""python build.py vo       -> voix + table des plans (AUCUN montage, à lancer d'abord)
   python build.py montage  -> animatique.mp4 puis QC"""
import json, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
sys.path.insert(0, "/chemin/vers/montage-video/scripts")      # dossier contenant pipeline.py / autoad.py
import pipeline as pl                                          # noqa: E402
W, H = pl.W, pl.H

# --- 1. Texte de la VO = texte EXACT du brief (jamais réécrit de mémoire) -----------------------------
SCRIPT = Path(HERE / "script.txt").read_text().strip()
# --- 2. Ancres : (id, 5 premiers mots EXACTS de la phrase dans la VO), dans l'ordre -------------------
ANCRES = [("P01", "Here's what happens inside your"), ("P02", "..."), ...]   # recopiées du brief
IDS = [s for s, _ in ANCRES]
VOICE = "GZ4YZrWgGAq7vFJlJYlc"   # voix du brief (banque de voix)
MIN = {"*": 1.0}                 # seuil de plan court décidé UNE fois (ici : la réf coupe à ~1 s)
OV = HERE / "_overlays"


def project():
    # music=None : la référence n'a pas de musique. Sinon chemin du mp3 + music_volume=0.04.
    return pl.Project(HERE, voice=VOICE, music=None, tts="eleven_v4")


def segments():
    P = project()
    words, tight = P.vo(SCRIPT)                                   # tempo 1.0, pause 0.25 (défauts)
    assert len(words) == len(SCRIPT.split()), (len(words), len(SCRIPT.split()))
    fin = words[-1]["e"]
    # ~1 s de queue muette : un faux mot sert d'ancre de fin, les captions utiliseront `words` sans lui
    fake = words + [{"w": "FIN", "s": fin + 0.3, "e": fin + 0.7}]
    tm = pl.Project.timing([{"id": s, "anchor": a} for s, a in ANCRES], fake, min_shot=MIN)
    return P, words, fake, tight, tm


def vo():
    P, words, fake, tight, tm = segments()
    print(f"{len(words)} mots, voix {words[-1]['e']:.2f} s ; plans {len(tm)}/{len(IDS)}, absorbes {pl.Project.MERGED}")
    for sid, a in ANCRES:
        print(f"  {sid} {tm[sid][0]:6.2f} +{tm[sid][1]:5.2f} s  {a}" if sid in tm else f"  {sid}  ABSORBE  {a}")


def titre_png():
    """Calque du hook : 2 bandeaux (blanc/texte noir, rouge/texte blanc), texte centré sur l'ENCRE."""
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    f = ImageFont.truetype(str(pl.RES / "fonts/Montserrat-SemiBold.ttf"), 62)
    y = int(H * 0.165)
    for txt, fond, encre in (("What Happens Inside your", (255, 255, 255, 255), (0, 0, 0, 255)),
                             ("Face Over 90 Days", (226, 30, 36, 255), (255, 255, 255, 255))):
        bb = d.textbbox((0, 0), txt, font=f)               # boîte de l'encre, pas de l'origine
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
        px, py = 22, 14
        x0 = (W - tw) / 2 - px
        d.rectangle((x0, y, x0 + tw + 2 * px, y + th + 2 * py), fill=fond)
        d.text((x0 + px - bb[0], y + py - bb[1]), txt, font=f, fill=encre)
        y += th + 2 * py + 6
    out = OV / "titre.png"
    im.save(out)
    return out


def badge_png():
    """Badge rond « 90-DAY RISK-FREE » en haut à droite (relevé sur la fin de la référence)."""
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    cx, cy, R = W - 190, 250, 130
    d.ellipse((cx - R - 6, cy - R - 6, cx + R + 6, cy + R + 6), fill=(120, 70, 40, 255))
    for i in range(R, 0, -2):
        k = i / R
        d.ellipse((cx - i, cy - i, cx + i, cy + i), fill=(int(196 - 50 * k), int(130 - 40 * k), int(88 - 30 * k), 255))
    for txt, sz, dy in (("90-DAY", 58, -24), ("RISK-FREE", 34, 34)):
        d.text((cx, cy + dy), txt, font=ImageFont.truetype(pl.FONT_BLACK, sz), fill=(255, 246, 230, 255), anchor="mm")
    out = OV / "badge.png"
    im.save(out)
    return out


def seg_zoom(P, maxz=0.05):
    """Plans fixes : push-in centré BORNÉ (une étiquette n'est jamais coupée). Remplace P.segment pour les stills."""
    def segment(sh, d):
        out = P.seg / f"{sh['id']}.mp4"
        n = max(1, round(d * 30))                           # round, jamais ceil
        k = min(0.0005, maxz / n)
        pl.ff("-loop", "1", "-i", sh["src"], "-vf",
              f"scale={W * 2}:{H * 2}:force_original_aspect_ratio=increase,crop={W * 2}:{H * 2},"
              f"zoompan=z='1+{k:.6f}*on':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={n}:s={W}x{H}:fps=30,"
              f"format=yuv420p", "-frames:v", n, out)
        return out
    P.segment = segment          # ⚠ ce segment-là n'a PAS le cache de Project.segment : il refait tout


def montage(out_name="animatique.mp4"):
    P, words, fake, tight, tm0 = segments()
    assert len(tm0) == len(IDS), pl.Project.MERGED           # aucun plan absorbé par surprise
    for s in IDS:
        assert (HERE / "frames" / f"{s}.png").exists(), f"frame manquante {s}"
    seg_zoom(P)
    OV.mkdir(exist_ok=True)
    shots = [{"id": s, "anchor": a, "kind": "still", "src": HERE / "frames" / f"{s}.png"} for s, a in ANCRES]
    # Les bornes des calques se calculent sur la MÊME grille 30 i/s que edit()
    q = lambda t: round(t * 30) / 30
    tq = {s: (q(a), q(a + d) - q(a)) for s, (a, d) in tm0.items()}
    ov = [(titre_png(), 0.0, tq["P03"][0])]                  # titre sur P01-P02
    a, d = tq["P31"]
    ov.append((badge_png(), a + 0.30, a + d))                # badge posé 0,3 s après l'entrée de P31
    lufs, dur = P.edit(shots, fake, tight, HERE / out_name,
                       caption_style="yellow", ypos=lambda t: 0.71,   # style + hauteur relevés sur la réf
                       overlays=ov, music_volume=0.0,
                       min_shot=MIN,                                  # MÊME min_shot que timing()
                       caption_words=words)                           # captions sans le faux mot "FIN"
    (HERE / "plan_durees.json").write_text(json.dumps(tq, indent=1))  # sert à la planche et à la version animée
    print(f"{out_name} {dur:.2f} s, {lufs} LUFS, absorbes : {pl.Project.MERGED}")


if __name__ == "__main__":
    {"vo": vo, "montage": montage}[sys.argv[1]]()
```

Puis :
```
python build.py vo                      # lire la table : tous les ids présents, durées plausibles
python build.py montage
python3 /chemin/vers/scripts/qc.py ./ ./animatique.mp4
```

## Version animée (même voix, mêmes durées, clips à la place de certaines images)

Logique de `_anim_lote.py:Anim.shots` / `Anim.brancher` / `Anim.verifier_durees` :
```python
def montage_anime():
    P, words, fake, tight, tm0 = segments()
    tq = {s: (round(a * 30) / 30, round((a + d) * 30) / 30 - round(a * 30) / 30) for s, (a, d) in tm0.items()}
    ref = {k: tuple(v) for k, v in json.loads((HERE / "plan_durees.json").read_text()).items()}
    assert all(abs(tq[s][0] - ref[s][0]) < 1e-6 and abs(tq[s][1] - ref[s][1]) < 1e-6 for s in ref), "durees != animatique"
    P.seg = HERE / "segments_anime"; P.seg.mkdir(exist_ok=True)       # ne pas écraser les segments de l'animatique
    seg_zoom(P)
    zoom = P.segment
    P.segment = lambda sh, d: pl.Project.segment(P, sh, d) if sh.get("kind") == "clip" else zoom(sh, d)
    shots = []
    for sid, a in ANCRES:
        c = HERE / "clips_anime" / f"{sid}.mp4"
        if c.exists():
            assert pl.duration(c) >= tq[sid][1] - 0.02, f"{sid} : clip plus court que le plan (ralenti interdit)"
            shots.append({"id": sid, "anchor": a, "kind": "clip", "src": c, "speed": 1.0})
        else:                                                          # produit/étiquette, escalier, clip refusé
            shots.append({"id": sid, "anchor": a, "kind": "still", "src": HERE / "frames" / f"{sid}.png"})
    ov = [(titre_png(), 0.0, tq["P03"][0]), (badge_png(), tq["P31"][0] + 0.30, sum(tq["P31"]))]
    lufs, dur = P.edit(shots, fake, tight, HERE / "anime.mp4", caption_style="yellow", ypos=lambda t: 0.71,
                       overlays=ov, music_volume=0.0, min_shot=MIN, caption_words=words)
```
Règles tirées du lot : plans produit/étiquette restent **fixes** (le modèle vidéo réécrit l'étiquette et change
le nombre de softgels) ; un clip se génère à `max(2, ceil(durée + 0.3))` s pour ne jamais être ralenti ; un
clip payé et validé doit être monté (assert dans `Anim.shots`) ; planche de la version animée :
`Anim.planche` (2 frames par plan à 15 % et 85 %).
