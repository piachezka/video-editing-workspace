"""Shared auto-video pipeline (born from two-moms/build.py). A project = a folder with a build.py that defines its shots.

Flow: vo() -> timing() -> frames (kie Nano Banana 2 here, or dropped in frames/ from Higgsfield) -> clips() (kie Grok)
-> edit(): segments + captions + overlays + voice + music -> loud_fix. Every step skips files that already exist.
"""
import base64, concurrent.futures as cf, json, math, os, re, ssl, subprocess, tempfile, urllib.request
from pathlib import Path
import autoad  # env, upload, kie_task, FFMPEG, FFPROBE

autoad.env()
W, H = 1080, 1920
RES = Path(__file__).resolve().parent / "resources"


def _font(path):
    """Repli macOS/Windows : chemin Linux /usr/share s'il existe, sinon le 1er fichier du meme nom trouve ici."""
    if Path(path).exists():
        return path
    name = Path(path).name
    for d in (RES / "fonts", Path.home() / "Library/Fonts", Path("/Library/Fonts"),
              Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft/Windows/Fonts", Path("C:/Windows/Fonts")):
        if (d / name).exists():
            return str(d / name)
    return path


# Les VRAIS fichiers Mac (copies sur le serveur dans /usr/local/share/fonts/mac) : une police libre "equivalente"
# change les metriques, donc le decoupage des captions. FONTS_DIR force un autre dossier.
_F = os.environ.get("FONTS_DIR") or next((d for d in ("/System/Library/Fonts/Supplemental", "/usr/local/share/fonts/mac")
                                          if Path(d, "Arial Black.ttf").exists()), "/System/Library/Fonts/Supplemental")
FONT_BLACK = f"{_F}/Arial Black.ttf"
FONT_BOLD = f"{_F}/Arial Bold.ttf"
FONT_IMPACT = f"{_F}/Impact.ttf"
WHITEBOX_FONT = _font("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf")
FILM_FONT = _font("/usr/share/fonts/truetype/liberation/LiberationSans-BoldItalic.ttf")  # captions « film » (brief lotb-05, copie Resilia)
UNMOT_FONT = str(RES / "fonts/Montserrat-SemiBold.ttf")  # captions « unmot » (brief lotc-04, copie Amua Pixar : grasse arrondie type Montserrat)
UNMOT_MAJ_FONT = str(RES / "fonts/Montserrat-VF.ttf")    # police variable OFL (google/fonts), instance ExtraBold : style « unmot_maj »
MONO_FONT = _font("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf")  # captions « mono » (brief nuit-02, copie Metabolae)  # sans-serif medium la plus proche installee (brief nuit-06)
CTX = autoad.CTX  # /etc/ssl/cert.pem n'existe que sur macOS
NORM = f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps=30,setsar=1,format=yuv420p"

# --- garde-fous Meta (Kevin 2026-10-03 : "la zone du ventre est entre 2 parties privees chez les femmes") ---
# A COLLER DANS TOUT PROMPT qui montre un ventre, une taille, une hanche ou une ceinture.
#
# ⚠ REECRITS EN POSITIF le 2026-10-04. La premiere version ENUMERAIT les interdits ("no groin, no crotch,
# no bikini line, no cleavage, no nudity") et c'est le garde-fou LUI-MEME qui faisait refuser l'image par le
# filtre de gpt-image : 2 frames sur 8 echouaient systematiquement, et la meme frame passait du premier coup
# sans le bloc. Un filtre lit les mots, pas l'intention. On decrit donc ce qui EST dans le cadre, habille,
# et jamais ce qui n'y est pas.
# La MARQUE D'ELASTIQUE, notre preuve visuelle n1. Kevin a du le dire deux fois le 2026-10-04, sur deux
# videos differentes : "les marques rouges sont bcp trop hautes, il faut qu'elles soient vraiment au
# niveau de la waistline". Par defaut les modeles la posent a mi-ventre, AU-DESSUS du nombril, ce qui ne
# correspond a aucune ceinture reelle et casse la credibilite du plan. Elle suit le bord du jean : donc
# SOUS le nombril. Et c'est une empreinte de tissu, pas un trait dessine.
# 2026-10-04, 2e passe : la constante existait mais n'etait pas collee aux prompts concernes, et sa
# formulation restait trop douce -- les deux frames sont ressorties avec la marque A MI-VENTRE. On ancre
# donc la position sur le BORD DU JEAN (un repere visible dans le cadre) plutot que sur le nombril (que le
# modele place ou il veut), et on decrit l'empreinte en positif : "ecrasee, gonflee, bords flous" porte,
# "jamais un trait dessine" ne porte pas.
WAISTLINE = (" The mark lies directly ON the waistband line: its lower edge touches the top of the closed jeans "
             "waistband and it follows that seam exactly across the lower belly, in the bottom part of the frame. "
             "The navel is well ABOVE the mark, higher up in the frame, with clear unmarked skin between them. "
             "It is a pressure imprint left in the flesh by a tight elastic band worn for hours: a wide band of "
             "skin several centimetres thick, flushed deep pink and slightly swollen, physically indented into the "
             "surface so it catches the light along its hollow, with soft blurred feathered edges that fade into "
             "the surrounding skin and the faint grain of the fabric weave printed inside it.")

# Le SLUDGE qui encrasse l'interieur du corps. Kevin, 2026-10-04 : "il faut que le sludge qui est montre
# dans les interieurs du corps soit JAUNE plutot que vert, et il faut qu'il soit bcp plus present, genre
# plus grossier, degeu, un peu liquide gras". Le vert lit comme une infection ; le jaune gras lit comme
# de la graisse et des dechets stagnants, ce qui est le propos. Et il doit DOMINER le plan : un depot
# discret ne fait pas peur, donc il ne fait pas agir.
SLUDGE = (" The whole inside is packed and overflowing with thick yellow sludge, the colour of old fat and "
          "rendered grease, glossy and heavy, clinging in lumpy clots and slow dripping strings that sag "
          "under their own weight. It is the dominant element of the picture and leaves almost no clear "
          "space, visibly greasy and unpleasant.")

# ⚠ LES FEMMES DE NOS B-ROLLS NE SONT PAS DES MANNEQUINS. Kevin, 2026-10-04 : "les femmes que tu montres
# sont trop jolies et parfaites pour des moms, il faut qu'elles soient plus realistes". Par defaut les
# modeles d'image sortent des visages de casting : peau lissee, corps tonique, coiffure faite. Une cible
# qui ne se reconnait pas ne s'arrete pas. A coller a TOUT prompt montrant une femme reelle.
VRAIE_FEMME = (
    " She is an ordinary woman, not a model and not a fitness influencer: an everyday face with visible "
    "pores, fine lines around the eyes, uneven skin tone and a few blemishes, no makeup or barely any, "
    "hair simply tied back and a little untidy. Her body is an ordinary real body, soft and untoned, with "
    "stretch marks, cellulite on the thighs and a little loose skin at the waist. Plain comfortable "
    "clothes that have been worn and washed. Candid, unflattering domestic lighting, as if photographed "
    "on a phone by a friend, not styled and not retouched."
) + (
    # Kevin 2026-10-07 (2e fois, C05 puis D4) : "elle fait trop enceinte". Un petit ventre doux sort en ventre de
    # grossesse par defaut. Colle ICI pour que toute femme generee l'ait, sans y penser.
    # ⚠ "low pouch" a ete remplace par "low belly roll" le 2026-10-12 : le mot "pouch" est dans
    # Project.PRODUIT, donc TOUTE frame utilisant VRAIE_FEMME sans reference produit levait
    # "ce prompt montre le PRODUIT mais ne passe aucune reference" — sur une frame de visage.
    # Le garde-fou lit le prompt, pas l'intention : une constante ne doit contenir aucun de ses mots.
    " NOT pregnant: any belly is a small, soft, low belly roll that sags slightly below the navel, never a high, round, "
    "firm dome. Her waist and ribs stay slim above it. Her hands never cradle the underside of the belly "
    "(that is a pregnancy pose); if she touches it, she pinches the soft roll with her fingers."
    # Kevin 2026-10-26 : un ventre nu pince est OK tant qu'aucune partie intime n'est visible. Condition ecrite ici.
    " If her belly is bare, her trousers or leggings stay fully up and fastened at the natural waist and her top "
    "covers her chest: no underwear, no groin, no breast visible."
)
assert "no groin" in VRAIE_FEMME
PAS_ENCEINTE = VRAIE_FEMME[VRAIE_FEMME.index(" NOT pregnant"):]
assert "NOT pregnant" in VRAIE_FEMME

SAFE_BODY = (" She is fully dressed in ordinary everyday clothes that cover her completely. Her trousers are worn normally and "
             "fully fastened at the natural waist, the waistband sitting flat and closed, with a plain t-shirt covering her torso. "
             # 2026-10-07 : bande de peau entre haut et ceinture sur 3 frames sur 4 -> phrase positive en constante.
             "Her top is full length and loose and falls over the waistband, covering the button and the waistband entirely: no skin visible anywhere around her waist. "
             "This is a plain documentary photograph of a clothed body, modest and matter of fact.")
# Variante des que le plan n'a aucune raison de descendre sous la ceinture (gros plan de marque, de pli, de ventre).
SAFE_CROP = (" The frame contains only the torso above the waist: the bottom edge of the image is the closed waistband itself, "
             "and everything below it is outside the picture." + SAFE_BODY)


def ff(*args):
    subprocess.run([autoad.FFMPEG, "-y", "-v", "error", *map(str, args)], check=True)


def duration(p):
    return float(subprocess.check_output([autoad.FFPROBE, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)]))


def run(jobs, n=6):
    """Run (fn, *args) jobs in parallel; a failed job is reported, not fatal (rerun the step to retry it)."""
    with cf.ThreadPoolExecutor(n) as ex:
        futs = {ex.submit(f, *a): a[1] if len(a) > 1 else a[0] for f, *a in jobs}
        for f in cf.as_completed(futs):
            try:
                f.result()
            except BaseException as e:
                print(f"  ❌ {futs[f]}: {e}")


# ---------------------------------------------------------------------------------------------------------
# Ligne basse d'etiquette : « Dietary Supplement | 60 Softgels »
# Mesure 2026-10-23 (lot D) : sur 3 videos, kie/nano-banana-2 a ecrit cette ligne de 5 px de haut de travers
# (Distary, Bistary, Batery, Softgeis, « 80 Softgels »), alors que le reste de l'etiquette sort juste. Un modele
# d'image ne tient pas un texte aussi petit : la ligne se REECRIT apres coup, en PIL, 0 credit.
# ---------------------------------------------------------------------------------------------------------
BOTTOM_LINE = "Dietary Supplement | 60 Softgels"


def text_bbox(png, window, thr=22):
    """Boite (x0, y0, x1, y1) de l'ENCRE d'une ligne de texte dans `window` = (x0, y0, x1, y1) de l'image.
    Robuste aux degrades (haute frequence = |luminance - mediane 9 px| > thr). Leve ValueError si rien n'est trouve."""
    from PIL import Image, ImageFilter
    import numpy as np
    im = Image.open(png).convert("L").crop(window)
    a = np.asarray(im).astype(int)
    hp = np.abs(a - np.asarray(im.filter(ImageFilter.MedianFilter(9))).astype(int))
    ys, xs = np.where(hp > thr)
    if not len(xs):
        raise ValueError(f"{png} : aucune encre dans {window}")
    return window[0] + int(xs.min()), window[1] + int(ys.min()), window[0] + int(xs.max()) + 1, window[1] + int(ys.max()) + 1


def relabel_bottom_line(png_in, png_out, bbox, text=BOTTOM_LINE, angle=0.0, ink=None, strength=0.9, pad=3):
    """Efface la ligne basse d'une etiquette generee et RECRIT le texte exact en PIL (0 credit, aucune generation).

    png_in / png_out : image source (jamais modifiee) / image corrigee (peut etre le meme chemin si png_in est une copie).
    bbox  : (x0, y0, x1, y1) en pixels de png_in = l'encre de la ligne fautive ; si la ligne est inclinee, la boite
            englobante de toute la ligne (voir text_bbox(png, window) pour la mesurer).
    text  : texte a ecrire (defaut « Dietary Supplement | 60 Softgels », le texte du packshot ; le separateur « | » est
            entoure de deux espaces au rendu).
    angle : degres, sens ANTI-horaire (positif = la ligne monte vers la droite), 0 pour une ligne horizontale.
    ink   : (r, g, b) de l'encre ; None = mesuree sur l'encre existante (percentile sombre de la boite).
    strength : opacite de l'encre (0,9 : la ligne du packshot est un gris fonce, pas un noir).
    pad   : marge (px) autour de la boite effacee.
    Le fond efface est un degrade entre les 3 px au-dessus et les 3 px en dessous de la boite (la pouche est lisse).
    Retourne png_out. Verifier ensuite A L'OEIL un crop zoome : le helper ne lit pas le resultat."""
    from PIL import Image, ImageDraw, ImageFont
    import numpy as np
    img = Image.open(png_in).convert("RGB")
    a = np.asarray(img).astype(float)
    x0, y0, x1, y1 = [int(v) for v in bbox]
    x0, y0, x1, y1 = x0 - pad, y0 - pad, x1 + pad, y1 + pad
    if ink is None:
        reg = a[y0:y1, x0:x1].reshape(-1, 3)
        lum = reg.mean(axis=1)
        ink = tuple(reg[lum <= np.percentile(lum, 12)].mean(axis=0))
    top = a[max(0, y0 - 5):y0 - 2, x0:x1].mean(axis=0)
    bot = a[y1 + 2:y1 + 5, x0:x1].mean(axis=0)
    for r in range(y0, y1):
        f = (r - y0) / max(1, y1 - y0 - 1)
        a[r, x0:x1] = top * (1 - f) + bot * f
    # texte a 4x, largeur cible = largeur de la boite (corrigee de l'inclinaison), puis rotation et reduction
    import math
    rad = math.radians(abs(angle))
    tw_target = ((x1 - x0) - 2 * pad) / max(0.2, math.cos(rad)) - (y1 - y0) * math.sin(rad)
    shown = text.replace(" | ", "  |  ")
    path = _font("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf")
    f = ImageFont.truetype(path, 40)
    probe = ImageDraw.Draw(Image.new("L", (10, 10)))
    f = ImageFont.truetype(path, max(8, int(40 * tw_target * 4 / probe.textlength(shown, font=f))))
    wbig = int(probe.textlength(shown, font=f)) + 16
    hbig = int(f.size * 1.5)
    big = Image.new("L", (wbig, hbig), 0)
    ImageDraw.Draw(big).text((wbig / 2, hbig / 2), shown, font=f, fill=255, anchor="mm")
    if angle:
        big = big.rotate(angle, resample=Image.BICUBIC, expand=True)
    sw, sh = max(1, big.width // 4), max(1, big.height // 4)
    cov = np.asarray(big.resize((sw, sh), Image.LANCZOS)).astype(float) / 255 * strength
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    tx0, ty0 = cx - sw // 2, cy - sh // 2
    ys0, xs0 = max(0, ty0), max(0, tx0)
    ys1, xs1 = min(a.shape[0], ty0 + sh), min(a.shape[1], tx0 + sw)
    c = cov[ys0 - ty0:ys1 - ty0, xs0 - tx0:xs1 - tx0, None]
    a[ys0:ys1, xs0:xs1] = a[ys0:ys1, xs0:xs1] * (1 - c) + np.array(ink, float) * c
    Image.fromarray(np.clip(a, 0, 255).astype("uint8")).save(png_out)
    return png_out


class Project:
    def __init__(self, here, voice="yj30vwTGJxSHezdAGsv9", music=None, tts="eleven_v4"):
        self.here = Path(here)
        self.fr, self.cl, self.seg = self.here / "frames", self.here / "clips", self.here / "segments"
        for d in (self.fr, self.cl, self.seg, self.here / "_review"):
            d.mkdir(parents=True, exist_ok=True)
        # tts : eleven_v4 par defaut. Kevin, 2026-10-12 : « toujours eleven v4 frere pas eleven v3 ».
        # La v3 etait la regle du 2026-10-01 ; elle est perimee. Le defaut avait survecu a la bascule
        # (lot.py passait deja tts="eleven_v4" projet par projet), donc tout projet qui ne le passait
        # PAS repartait en v3 en silence. Le defaut est la seule chose qu'on n'ecrit pas, donc la seule
        # qu'on oublie : il porte la regle.
        assert tts.startswith("eleven_v4"), f"VO : eleven_v4 obligatoire (recu {tts})"
        self.voice, self.music, self.tts = voice, music, tts
        self._refs = {}
        self.keys = set()  # mots en jaune du style "key" (MAJUSCULES, sans ponctuation)

    # ---------- voice ----------
    def vo(self, text, name="vo", pause=0.25, tempo=1.0):
        """ElevenLabs v3 + word timings, then only the real pauses are shortened (silencedetect). Cached per text."""
        # tempo > 1 = on accelere la voix. Kevin 2026-10-03 : "il faut ajuster le voiceover qui est bcp trop rapide".
        # C'est devenu le bouton pour tenir la duree cible d'un brief (1.28 sur quarante-cinq-minutes) : interdit.
        # Une video trop longue se raccourcit en COUPANT DES MOTS, jamais en accelerant la diction.
        # 2026-10-09 : Kevin autorise une acceleration LEGERE ("t'as juste a accelerer un petit peu l'audio").
        # Le defaut qu'il avait refuse etait 1.28, pas 1.05. Plafond a 1.10 : au-dela on coupe des mots.
        assert tempo <= 1.10, f"tempo={tempo} : au-dela de 1.10 on ne tient pas une duree a l'atempo. Coupe des mots."
        raw, tight, words_f = self.here / f"{name}.mp3", self.here / f"{name}_tight.wav", self.here / f"{name}_words.json"
        txt = self.here / f"{name}.txt"
        if not txt.exists() or txt.read_text() != text or not raw.exists():
            # ⛔ ElevenLabs refuse au-dela de 10 000 caracteres :
            # "Request text length exceeds the maximum text length of 10000 characters" (mesure 2026-10-11
            # sur un script de 13 376). Un VSL long depasse forcement. On decoupe sur les PARAGRAPHES —
            # jamais au milieu d'une phrase, sinon la diction casse a la jointure — puis on recolle l'audio
            # et on DECALE les alignements de la duree reellement decodee de chaque morceau, pas d'une
            # estimation : un decalage de 50 ms sur le 1er morceau desynchronise tout ce qui suit.
            parts, cur = [], ""
            for para in text.split("\n\n"):
                if len(cur) + len(para) + 2 > 9500 and cur:
                    parts.append(cur.strip()); cur = ""
                cur += para + "\n\n"
            parts.append(cur.strip())
            assert all(len(x) <= 10000 for x in parts), "un paragraphe depasse 10 000 caracteres a lui seul"
            if len(parts) > 1:
                print(f"  voix : script de {len(text)} caracteres -> {len(parts)} appels")
            chunks, align = [], {"characters": [], "character_start_times_seconds": [], "character_end_times_seconds": []}
            off = 0.0
            for k, part in enumerate(parts):
                body = {"text": part, "model_id": self.tts, "voice_settings": {"stability": 0.5}}
                req = urllib.request.Request(f"https://api.elevenlabs.io/v1/text-to-speech/{self.voice}/with-timestamps?output_format=mp3_44100_128",
                                             data=json.dumps(body).encode(),
                                             headers={"xi-api-key": autoad.os.environ["ELEVENLABS_API_KEY"], "Content-Type": "application/json"})
                r = json.load(urllib.request.urlopen(req, timeout=300, context=CTX))
                f = self.here / f"{name}_part{k}.mp3"
                f.write_bytes(base64.b64decode(r["audio_base64"]))
                chunks.append(f)
                a = r["alignment"]
                align["characters"] += a["characters"] + ([" "] if k + 1 < len(parts) else [])
                d = duration(f)
                align["character_start_times_seconds"] += [x + off for x in a["character_start_times_seconds"]] + ([off + d] if k + 1 < len(parts) else [])
                align["character_end_times_seconds"] += [x + off for x in a["character_end_times_seconds"]] + ([off + d] if k + 1 < len(parts) else [])
                off += d
            if len(chunks) == 1:
                raw.write_bytes(chunks[0].read_bytes())
            else:
                ins = sum([["-i", str(f)] for f in chunks], [])  # ff() pose deja -y et -v error
                ff(*ins, "-filter_complex",
                   "".join(f"[{i}:a]" for i in range(len(chunks))) + f"concat=n={len(chunks)}:v=0:a=1[a]",
                   "-map", "[a]", "-c:a", "libmp3lame", "-b:a", "128k", str(raw))
            for f in chunks:
                f.unlink(missing_ok=True)
            (self.here / f"{name}_alignment.json").write_text(json.dumps(align))
            txt.write_text(text)
            tight.unlink(missing_ok=True)
        # Le cache de la piste resserree ne portait PAS le tempo : changer tempo=1.0 -> 1.05 renvoyait
        # silencieusement l'ancienne piste ET les anciens timings. 2026-10-09, un sidecar suffit.
        tf = self.here / f"{name}_tempo.txt"
        if tight.exists() and (not tf.exists() or tf.read_text() != f"{pause}/{tempo}"):
            tight.unlink()
        tf.write_text(f"{pause}/{tempo}")
        if not tight.exists():
            a = json.loads((self.here / f"{name}_alignment.json").read_text())
            ws, cur, s0 = [], "", None
            for c, t0, t1 in zip(a["characters"], a["character_start_times_seconds"], a["character_end_times_seconds"]):
                if c.isspace():
                    if cur: ws.append({"w": cur, "s": s0, "e": prev}); cur = ""
                    continue
                if not cur: s0 = t0
                cur += c; prev = t1
            if cur: ws.append({"w": cur, "s": s0, "e": prev})
            new = self.tighten(raw, ws, tight, pause, tempo)
            # ⛔ 2026-10-11, Kevin : « t'as gardé les choses entre crochets dans le script dans les
            # captions ». Un tag d'intonation ([slowly], [calm]) n'est PAS prononce — verifie en STT — mais
            # il revient quand meme dans l'alignement caractere par caractere, donc dans la liste de mots,
            # donc **incruste dans les captions** et dans les ancres de timing(). Il saute ici, une fois,
            # pour tous les projets : c'est la seule place ou la liste de mots se fabrique.
            new = [w for w in new if not re.fullmatch(r"\[[^\]]*\]", w["w"].strip())]
            words_f.write_text(json.dumps(new))
        return json.loads(words_f.read_text()), tight

    def trim_speech(self, clip, pre=0.15, post=0.35, also=None):
        """Rogne un clip Kling sur sa PAROLE. Kling rend toujours la duree demandee et bourre de silence :
        mesure du 2026-10-04, 7 clips = 77,3 s pour 61 s de parole, soit 16 s de blanc. Sans ca le montage
        traine et la video depasse la cible du brief. Cache a cote du clip."""
        clip = Path(clip)
        out = clip.with_name(clip.stem + "_trim.mp4")
        # `also` : un jumeau MUET du clip (la version detouree sortie du matting video) a rogner
        # exactement sur la meme fenetre. Il n'a pas d'audio, donc il ne peut pas se mesurer tout seul.
        twin = Path(also).with_name(Path(also).stem + "_trim.mp4") if also else None
        if out.exists() and (twin is None or twin.exists()):
            return out
        w = self._stt(clip)
        if not w:
            return clip
        a, z = max(0.0, w[0]["s"] - pre), min(duration(clip), w[-1]["e"] + post)
        if not out.exists():
            ff("-ss", f"{a:.3f}", "-i", str(clip), "-t", f"{z - a:.3f}",
               "-c:v", "libx264", "-crf", "18", "-c:a", "aac", "-b:a", "192k", "-ar", "44100", str(out))
        if twin is not None and not twin.exists():
            ff("-ss", f"{a:.3f}", "-i", str(also), "-t", f"{z - a:.3f}", "-an",
               "-c:v", "libx264", "-crf", "18", str(twin))
        print(f"  trim {clip.name}: {duration(clip):.2f}s -> {duration(out):.2f}s")
        return out

    def tighten_clip(self, clip, also=None, gap=0.32, keep=0.10, speed=1.08):
        """Resserre un clip Kling sur sa parole : coupe les blancs INTERNES et accelere un peu.

        Kevin, 2026-10-04 : "elle parle super lentement tu peux pas accelerer un petit peu et faire des
        petits cuts entre les pauses de ses phrases ?". Deux problemes distincts :
          - Kling laisse 0,4 a 1,2 s de silence entre deux phrases. On garde `keep` seconde et on jette
            le reste -> un jump cut, qui est le look recherche, pas un defaut.
          - Le debit lui-meme est lent. `speed` accelere image ET son du meme facteur, donc rien a recaler.
        Remplace trim_speech, qui ne rognait que les bords. `also` = le jumeau MUET detoure, coupe sur
        exactement les memes intervalles (il n'a pas d'audio, il ne peut pas se mesurer tout seul)."""
        clip = Path(clip)
        out = clip.with_name(clip.stem + "_tight.mp4")
        twin = Path(also).with_name(Path(also).stem + "_tight.mp4") if also else None
        if out.exists() and (twin is None or twin.exists()):
            return out
        w = self._stt(clip)
        if not w:
            return clip
        d = duration(clip)
        segs, a = [], max(0.0, w[0]["s"] - 0.12)
        for i in range(len(w) - 1):
            if w[i + 1]["s"] - w[i]["e"] > gap:
                segs.append((a, min(d, w[i]["e"] + keep)))
                a = max(0.0, w[i + 1]["s"] - keep)
        segs.append((a, min(d, w[-1]["e"] + 0.22)))
        # Kevin 2026-10-07 : lipsync decale. select/aselect coupait l'audio par TRAME AAC (~23 ms) et l'image par
        # frame (42 ms a 24 i/s) : chaque cut decalait un peu son et image, et ca se cumulait dans le clip.
        # trim/atrim + concat coupent les DEUX aux memes instants exacts. Coupes calees sur la grille d'images.
        fps = float(eval(subprocess.check_output([autoad.FFPROBE, "-v", "error", "-select_streams", "v",
                    "-show_entries", "stream=r_frame_rate", "-of", "csv=p=0", str(clip)]).decode().strip()))
        segs = [(round(x * fps) / fps, round(y * fps) / fps) for x, y in segs]
        kept = sum(y - x for x, y in segs)
        def graph(audio):
            g = "".join(f"[0:v]trim={x:.4f}:{y:.4f},setpts=PTS-STARTPTS[v{i}];" for i, (x, y) in enumerate(segs))
            if audio:
                g += "".join(f"[0:a]atrim={x:.4f}:{y:.4f},asetpts=PTS-STARTPTS[a{i}];" for i, (x, y) in enumerate(segs))
                g += "".join(f"[v{i}][a{i}]" for i in range(len(segs))) + f"concat=n={len(segs)}:v=1:a=1[vc][ac];"
                return g + f"[vc]setpts=PTS/{speed}[v];[ac]atempo={speed}[a]"
            g += "".join(f"[v{i}]" for i in range(len(segs))) + f"concat=n={len(segs)}:v=1:a=0[vc];"
            return g + f"[vc]setpts=PTS/{speed}[v]"
        if not out.exists():
            ff("-i", str(clip), "-filter_complex", graph(True), "-map", "[v]", "-map", "[a]",
               "-c:v", "libx264", "-crf", "18", "-c:a", "aac", "-b:a", "192k", "-ar", "44100", str(out))
        if twin is not None and not twin.exists():
            ff("-i", str(also), "-filter_complex", graph(False), "-map", "[v]",
               "-c:v", "libx264", "-crf", "18", str(twin))
        print(f"  tighten {clip.name}: {d:.2f}s -> {kept:.2f}s de parole -> {duration(out):.2f}s "
              f"({len(segs) - 1} cut{'s' if len(segs) > 2 else ''}, x{speed})")
        return out

    def _stt(self, path):
        """ElevenLabs scribe_v1 -> [{w,s,e}]. Sert de TRANSCRIPTEUR, jamais de voix. Cache en .words.json."""
        cache = Path(path).with_suffix(".words.json")
        # 2026-10-14 : un clip refait gardait la transcription de l'ancien -> faux « hook manquant ». Cache perime = ignore.
        if cache.exists() and cache.stat().st_mtime >= Path(path).stat().st_mtime:
            return json.loads(cache.read_text())
        b = "----x"
        payload = (f"--{b}\r\nContent-Disposition: form-data; name=\"model_id\"\r\n\r\nscribe_v1\r\n"
                   f"--{b}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"a.mp4\"\r\n"
                   f"Content-Type: video/mp4\r\n\r\n").encode() + Path(path).read_bytes() + f"\r\n--{b}--\r\n".encode()
        req = urllib.request.Request("https://api.elevenlabs.io/v1/speech-to-text", data=payload,
            headers={"xi-api-key": autoad.os.environ["ELEVENLABS_API_KEY"],
                     "Content-Type": f"multipart/form-data; boundary={b}"})
        try:
            with urllib.request.urlopen(req, timeout=300, context=autoad.CTX) as r:
                tr = json.loads(r.read())
            w = [{"w": x["text"], "s": x["start"], "e": x["end"]} for x in tr["words"] if x.get("type", "word") == "word"]
        except Exception as ex:  # quota Scribe a 0 (2026-10-07) -> repli local mlx-whisper (via uv), meme format
            import platform
            if platform.system() != "Darwin":  # serveur Linux : mlx n'existe pas -> whisper.cpp, un segment par mot
                print("scribe KO, repli whisper-cli :", ex)
                wav = Path(path).with_suffix(".stt.wav")
                subprocess.run([autoad.FFMPEG, "-y", "-v", "error", "-i", str(path), "-ar", "16000", "-ac", "1", str(wav)], check=True)
                subprocess.run(["whisper-cli", "-m", str(Path.home() / ".cache/whisper/ggml-small.en.bin"), "-f", str(wav),
                                "-ml", "1", "-sow", "-oj", "-of", str(wav.with_suffix("")), "-np"], check=True, capture_output=True)
                js = wav.with_suffix(".json")
                w = [{"w": t["text"].strip(), "s": t["offsets"]["from"] / 1000, "e": t["offsets"]["to"] / 1000}
                     for t in json.loads(js.read_text())["transcription"] if t["text"].strip()]
                wav.unlink(); js.unlink()
                assert w and all(set(x) == {"w", "s", "e"} and x["s"] <= x["e"] for x in w), "format _stt invalide"
                cache.write_text(json.dumps(w))
                return w
            print("scribe KO, repli mlx-whisper :", ex)
            code =("import sys,json,mlx_whisper as m;t=m.transcribe(sys.argv[1],path_or_hf_repo='mlx-community/whisper-large-v3-turbo',"
                    "word_timestamps=True);print(json.dumps([{'w':x['word'].strip(),'s':float(x['start']),'e':float(x['end'])} for s in t['segments'] for x in s['words']]))")
            env = dict(os.environ, PATH="/opt/homebrew/opt/ffmpeg-full/bin:" + os.environ["PATH"])  # ffmpeg brew casse (x265)
            out = subprocess.run(["uv", "run", "-q", "--no-project", "--with", "mlx-whisper", "python", "-c", code, str(path)],
                                 capture_output=True, text=True, env=env, check=True).stdout
            w = json.loads(out.strip().splitlines()[-1])
        assert w and all(set(x) == {"w", "s", "e"} and x["s"] <= x["e"] for x in w), "format _stt invalide"
        cache.write_text(json.dumps(w))
        return w

    @staticmethod
    def subject_bbox(clip, pad=12, top=1.0):
        """Boite englobante du sujet sur un clip DETOURE (fond noir) -> filtre crop= ffmpeg.
        Mesuree sur 3 frames reparties, on garde l'union (la personne bouge les bras).

        ⚠ 2026-10-04 : on ne genere plus jamais sur fond vert. Le sujet est tourne DANS le decor
        (image de depart = swap sur une frame de la reference) puis detoure par le matting video
        de Higgsfield (`remove_background`, media_type video), qui rend le sujet sur NOIR pur.
        Mesure comparative sur une frame, pixels en alpha partiel / opaques :
          colorkey sur vert genere ... 196 991 / 274 789  (sujet semi-transparent, "degeulasse")
          chromakey+despill+erosion ..  19 003 / 460 764  (acceptable, cheveux encore ronges)
          matting video + cle du noir .   1 104 / 428 259  (0,12 % de bord doux : la bonne piste)"""
        import numpy as np
        from PIL import Image
        d = duration(clip)
        xs0, ys0, xs1, ys1 = W, H, 0, 0
        for t in (d * 0.2, d * 0.5, d * 0.8):
            tmp = Path(str(clip) + f".bb{t:.1f}.png")
            ff("-ss", f"{t:.2f}", "-i", str(clip), "-frames:v", "1", str(tmp))
            a = np.array(Image.open(tmp).convert("RGB")).astype(int)
            tmp.unlink(missing_ok=True)
            fond = a.max(axis=2) < 16            # noir pur = fond
            suj = ~fond
            ys, xs = np.where(suj)
            if len(xs) == 0:
                continue
            xs0, ys0 = min(xs0, xs.min()), min(ys0, ys.min())
            xs1, ys1 = max(xs1, xs.max()), max(ys1, ys.max())
            iw, ih = a.shape[1], a.shape[0]
        x0, y0 = max(0, xs0 - pad), max(0, ys0 - pad)
        x1, y1 = min(iw, xs1 + pad), min(ih, ys1 + pad)
        y1 = y0 + max(2, int((y1 - y0) * top))   # top=0.62 -> buste
        return f"crop={x1 - x0}:{y1 - y0}:{x0}:{y0}"

    def vo_from_clips(self, clips, name="vo"):
        """Voix off EXTRAITE des clips Kling, pour les formats ou un personnage parle a l'ecran.

        Regle Kevin (modeles-et-couts §83) : une bouche qui articule => Kling genere l'image ET le son,
        jamais ElevenLabs. Mais toute la pipeline (timing, at, captions) tourne sur des timings au mot.
        Donc : on concatene l'audio des clips, on le transcrit avec ElevenLabs STT (scribe_v1, qui rend
        les timings par mot), et on renvoie EXACTEMENT la meme structure `words` que vo().
        ElevenLabs sert ici de transcripteur, pas de voix : la voix reste celle de Kling.

        clips: [Path] dans l'ordre du montage. Renvoie (words, piste_audio).
        """
        dest = self.here / f"{name}.mp3"
        if not dest.exists():
            lst = self.here / "_vo_concat.txt"
            lst.write_text("".join(f"file '{Path(c).resolve()}'\n" for c in clips))
            ff("-f", "concat", "-safe", "0", "-i", str(lst), "-vn", "-ar", "44100", "-b:a", "192k", str(dest))
        cache = self.here / f"{name}.words.json"
        if cache.exists():
            return json.loads(cache.read_text()), dest
        words = self._stt(dest)
        cache.write_text(json.dumps(words))
        print(f"  vo_from_clips: {len(clips)} clips, {len(words)} mots, {duration(dest):.2f}s")
        return words, dest

    @staticmethod
    def tighten(src, ws, out, pause, tempo):
        """Cut the middle of each real silence down to `pause` s; words are never touched (Kevin: no cuts between words)."""
        log = subprocess.run([autoad.FFMPEG, "-hide_banner", "-i", str(src), "-af", "silencedetect=n=-38dB:d=0.12", "-f", "null", "-"],
                             capture_output=True, text=True).stderr
        st = [float(x) for x in re.findall(r"silence_start: ([0-9.]+)", log)]
        en = [float(x) for x in re.findall(r"silence_end: ([0-9.]+)", log)]
        cuts = []
        for a, z in zip(st, en):
            if a < ws[-1]["e"] - 0.05 and z - a > pause + 0.05:
                m = a + pause / 2
                cuts.append((m, m + (z - a) - pause))
        end = ws[-1]["e"] + 0.12
        keep, t = [], 0.0
        for a, z in cuts:
            keep.append((t, a)); t = z
        keep.append((t, end))
        removed = lambda x: sum(z - a for a, z in cuts if z <= x)
        fl = "".join(f"[0:a]atrim={a:.3f}:{z:.3f},asetpts=PTS-STARTPTS,afade=t=in:d=0.01,afade=t=out:st={max(z - a - 0.01, 0):.3f}:d=0.01[p{i}];"
                     for i, (a, z) in enumerate(keep))
        fl += "".join(f"[p{i}]" for i in range(len(keep))) + f"concat=n={len(keep)}:v=0:a=1" + (f",atempo={tempo}" if tempo != 1 else "") + "[a]"
        ff("-i", src, "-filter_complex", fl, "-map", "[a]", out)
        print(f"  voix : {len(cuts)} pauses raccourcies à {pause}s")
        return [{"w": w["w"], "s": (w["s"] - removed(w["s"])) / tempo, "e": (w["e"] - removed(w["e"])) / tempo} for w in ws]

    MERGED = {}
    MIN_SHOT = 2.0

    @staticmethod
    def at(words, phrase):
        """Instant ou commence `phrase` dans la voix off. A utiliser pour caler un carton (DAY 7, PHASE 2) :
        un carton doit tomber sur la phrase prononcee, pas sur le debut du plan qui la contient. Un plan peut avoir
        ete absorbe par la fusion des plans < 2 s, et son voisin commence plus tot."""
        norm = lambda x: re.sub(r"[^a-z0-9-]", "", x.lower())
        seq = [norm(w["w"]) for w in words]
        toks = [norm(x) for x in phrase.split()]
        for i in range(len(seq)):
            if seq[i:i + len(toks)] == toks:
                return words[i]["s"]
        raise KeyError(phrase)  # Kevin 2026-10-02 : jamais un plan de moins de 2 s, ca fait une cassure et on ne voit rien

    @staticmethod
    def timing(shots, words, tail=0.5, min_shot=None):
        """Shot start = first word of its anchor phrase. Returns {sid: (start, dur)}.
        Tout plan plus court que MIN_SHOT est absorbe par son voisin : il ne sort pas du tout. `edit` et `clips`
        n'ont alors plus rien a generer pour lui, donc la regle s'applique sans toucher aux build.py."""
        min_shot = Project.MIN_SHOT if min_shot is None else min_shot
        # min_shot peut etre un dict {id: seuil, "*": seuil par defaut} : la regle « 2 s, sauf la ou la ref coupe
        # elle-meme plus vite » (QC.md § 6) se decide PLAN PAR PLAN. Un min_shot=0.9 global laissait passer des plans
        # de 1,5 s que la ref tient 6 s (porte 2 lot B n°8, 2026-10-21, apres la meme derive sur la nuit).
        seuil = (lambda sid: min_shot.get(sid, min_shot.get("*", Project.MIN_SHOT))) if isinstance(min_shot, dict) \
            else (lambda sid: min_shot)
        norm = lambda s: re.sub(r"[^a-z0-9-]", "", s.lower())
        seq = [norm(w["w"]) for w in words]
        starts, i0 = [], 0
        for sh in shots:
            a = [norm(x) for x in sh["anchor"].split()]
            # ⛔ Un `next()` nu levait un StopIteration muet : impossible de savoir QUEL plan, ni
            # pourquoi. La cause est toujours la meme -- l'ancre du brief n'existe pas telle quelle
            # dans la VO, ou elle chevauche l'ancre du plan precedent, qui a deja consomme ces mots.
            i = next((i for i in range(i0, len(seq)) if seq[i:i + len(a)] == a), None)
            if i is None:
                deja = " ".join(seq[max(0, i0 - 6):i0 + 1])
                raise SystemExit(
                    f"\n⛔ plan {sh['id']} : l'ancre \"{sh['anchor']}\" est introuvable dans la VO "
                    f"apres le plan precedent.\n   Derniers mots deja consommes : ...{deja}\n"
                    f"   -> soit l'ancre n'est pas le texte exact de la VO, soit elle recouvre celle "
                    f"du plan d'avant. Corrige le tableau du Decoupage dans le brief.")
            starts.append(0.0 if not starts else words[i]["s"] - 0.05)
            i0 = i
        end = words[-1]["e"] + tail
        ids = [sh["id"] for sh in shots]
        Project.MERGED = {}  # {plan absorbe: plan qui l'absorbe}, pour que les overlays suivent
        # fusion des plans trop courts : on supprime leur borne de depart, le plan precedent couvre la periode
        while len(starts) > 1:
            durs = [(starts[k + 1] if k + 1 < len(starts) else end) - starts[k] for k in range(len(starts))]
            short = [k for k, d in enumerate(durs) if d < seuil(ids[k])]
            if not short:
                break
            k = min(short, key=lambda k: durs[k])
            drop = k if k > 0 else 1  # le 1er plan ne peut pas disparaitre : c'est le hook
            host = ids[drop - 1]
            for a, b in list(Project.MERGED.items()):
                if b == ids[drop]:
                    Project.MERGED[a] = host
            Project.MERGED[ids[drop]] = host
            if drop == 1 and k == 0:
                Project.MERGED[ids[drop]] = ids[0]
            starts.pop(drop); ids.pop(drop)
        return {sid: (s, (starts[k + 1] if k + 1 < len(starts) else end) - s) for k, (sid, s) in enumerate(zip(ids, starts))}

    # ---------- generation (kie) ----------
    def ref(self, path):
        # Les URL d'upload kie EXPIRENT (bug du 2026-10-03 : "400 image fetch failed" sur toutes les frames a reference,
        # parce que refs_urls.json gardait une URL uploadee la veille). On ne cache donc plus sur disque, juste en memoire
        # pour la duree du run. Un upload de plus par run, et plus d'echec silencieux a J+1.
        path = str(Path(path))
        if path not in self._refs:
            self._refs[path] = autoad.upload(path)
        return self._refs[path]

    # Tout ce qui, dans un prompt, designe le PRODUIT. Si l'un de ces mots apparait, l'image doit partir
    # du vrai packshot : sinon le modele redessine un sachet plausible mais faux (logo illisible, pose a
    # l'envers, couleurs approchantes). Kevin l'a signale deux fois le 2026-10-04 :
    # "encore une fois ya un souci de pouch, fais en sorte que ca n'arrive plus jamais".
    # 2026-10-09 : les sous-chaines "ora " / " ora" faisaient matcher "oranges" (l'albedo des oranges est la
    # SOURCE de l'hesperidine, il revient dans une dizaine de prompts LEGO) -> 8 frames sans produit etaient
    # refusees. On passe en mot entier : "ora" oui, "oranges" non.
    PRODUIT = r"\b(pouch|sachet|gummy|gummies|ora|packshot|label|wordmark)\b"
    PACKSHOT = RES / "brolls/produit/packshot-pouch-gummies.png"
    POUCH_BLANC = False

    def image(self, prompt, dest, refs=(), model="nano-banana-2"):
        if Path(dest).exists():
            return
        # Kevin, 2026-10-12 : « osef des packshots en lego il faut juste que ca soit un pouch blanc ».
        # Un lot LEGO pose POUCH_BLANC = True dans son conf.py : le produit y est un sachet blanc uni, sans packshot.
        if re.search(self.PRODUIT, prompt.lower()) and not self.POUCH_BLANC:
            # Deux conditions, pas une. La reference ne suffit pas : passee a un modele kie, elle donne un
            # sachet a la bonne charte mais SANS AUCUN TEXTE. Kevin, 2026-10-04, deuxieme signalement :
            # "les sachets ora pour la video pixar ont 0 textes". Seul Nano Banana Pro (Higgsfield, 2k)
            # tient l'etiquette au mot pres, y compris dans un rendu stylise.
            if not refs:
                raise ValueError(
                    f"{Path(dest).name} : ce prompt montre le PRODUIT mais ne passe aucune reference.\n"
                    f"  Passer refs=(pl.Project.PACKSHOT,).")
            raise ValueError(
                f"{Path(dest).name} : ce prompt montre le PRODUIT, il ne se genere pas via kie.\n"
                f"  Un modele kie reprend la charte mais rend une etiquette VIDE, sans un mot dessus.\n"
                f"  Generer avec Nano Banana Pro (Higgsfield, model='nano_banana_pro', resolution='2k'),\n"
                f"  packshot en image_references, puis deposer la frame dans frames/ a la main.")
        inp = {"prompt": prompt, "aspect_ratio": "9:16", "resolution": "1K", "output_format": "png"}
        if refs:
            inp["image_input"] = [self.ref(r) for r in refs]
        autoad.kie_task(model, inp, dest)

    def clip(self, src, dest, motion, seconds, mode="normal", ar="9:16"):
        # ⛔ Le defaut etait "fun", et c'etait a l'envers. Kevin, 2026-10-18 (enieme fois) : « on avait dit
        # plusieurs fois d'utiliser grok normal pour la plupart des shots sauf ceux qui ont besoin d'un
        # outcome tres anime genre le hook ou elle fait les crunch. Il faut tout refaire, c'est trop
        # bizarre. » En "fun" le modele rend les visages goofy (bras en l'air, yeux exorbites), deforme
        # le lettrage d'une etiquette et rabote le corps. "fun" est l'EXCEPTION, reservee a un gag
        # physique assume ; il se demande, il ne s'herite pas.
        # ar : "1:1" pour la moitie b-roll d'un split UGC (ugc_omni.py), la frame source y est carree.
        if Path(dest).exists():
            return
        autoad.kie_task("grok-imagine-video-1-5-preview", {"image_urls": [autoad.upload(src)], "prompt": motion, "duration": str(seconds),
                                                           "resolution": "720p", "aspect_ratio": ar, "mode": mode}, dest)

    def clip_ugc(self, src, dest, line, seconds=6, resolution="720p", voice=""):
        """UGC qui parle face camera -> Gemini Omni 1.1 Flash. Kevin, 2026-10-14 : « le modele est top,
        pour les ugc on va utiliser ca maintenant. » Remplace Kling 3.0 ET la VO ElevenLabs : l'audio est
        natif et synchrone, donc plus d'alignement ni de captions-sur-VO sur ces plans.

        `line` est la REPLIQUE, pas un mouvement : elle part telle quelle entre guillemets dans le prompt.
        720p : 63/84/105/126 credits pour 4/6/8/10 s (84 cr = $0,42 mesure le 2026-10-14).
        -> 4 s minimum, donc jamais sur un b-roll court : Grok reste le modele des plans de 2-3 s."""
        if Path(dest).exists():
            return
        # Les durees libres n'existent pas chez Omni, kie renvoie une 422 et on perd le run.
        assert seconds in (4, 6, 8, 10), f"Omni n'accepte que 4/6/8/10 s, pas {seconds}"
        # ~3 mots/s mesure : au-dela la replique est tronquee en fin de clip et le plan est a jeter.
        assert len(line.split()) <= 3.5 * seconds, f"{len(line.split())} mots ne tiennent pas en {seconds} s"
        # first_frame_url EXCLUT image_urls / character_ids / audio_ids / video_list (doc kie) : on part
        # de la frame, donc pas de voix persistante ni de personnage sur cet appel.
        autoad.kie_task("google/gemini-omni-flash-1-1", {
            "first_frame_url": autoad.upload(src),
            "prompt": (f'Vertical selfie video, handheld phone at arm\'s length, the person from the image talking'
                       f' straight into the lens. They say, out loud, at a normal conversational pace: "{line}"'
                       " Their mouth articulates every word. Slight natural handheld wobble, no camera move, no zoom,"
                       " no cut. EXACTLY the same person as in the image: same face, same hair, same clothes, same room."
                       " Only their voice and quiet room tone, no music, no other speaker."
                       # voice : meme description de voix sur tous les clips d'un lot. Omni n'a pas de voix
                       # persistante en mode first_frame, c'est le seul levier pour la tenir d'un clip a l'autre.
                       + (f" Their voice, identical in every clip: {voice}" if voice else "")),
            "duration": str(seconds), "resolution": resolution, "aspect_ratio": "9:16"}, dest)

    def clip_seedance(self, src, dest, motion, seconds, resolution="720p"):
        """Seedance 2.5 : le realisme humain que Grok ne tient pas (mains, visages, objets manipules).
        ATTENTION 63 cr/s en 720p, soit ~14x le prix de Grok. Un plan de 4 s coute 252 cr ($1,26).
        -> on ne l'appelle que sur les plans ou le realisme EST le message, et jamais sans avoir valide la frame avant."""
        if Path(dest).exists():
            return
        # generate_audio=False : Seedance 2.5 sort une piste audio IA par defaut et le controle de kie la refuse
        # ("400 Content security audit did not pass ... output audio may be related to copyright restrictions", 2026-10-03).
        # Le montage jette l'audio des clips de toute facon.
        # first_frame_url, PAS image_urls : seedance-2-5 ignore silencieusement image_urls et part en text-to-video,
        # on paie plein tarif un plan qui n'a plus rien a voir avec la frame (2026-10-03, 5 clips perdus).
        autoad.kie_task("bytedance/seedance-2-5", {"first_frame_url": autoad.upload(src), "prompt": motion,
                                                   "duration": str(seconds), "resolution": resolution,
                                                   # "adaptive" obligatoire des qu'on donne une first_frame (422 sinon) :
                                                   # le clip reprend le ratio de la frame, qui est deja en 9:16.
                                                   "aspect_ratio": "adaptive", "generate_audio": False}, dest)

    # ---------- edit ----------
    def segment(self, sh, d):
        """One shot -> exact duration, 1080x1920, no audio.
        Kinds: clip (default), still (image + slow zoom), split (L/R), vsplit (T/B), avatar (fond + incruste detoure au chroma)."""
        out = self.seg / f"{sh['id']}.mp4"
        pad = f"tpad=stop_mode=clone:stop_duration={d + 1}"
        kind = sh.get("kind", "clip")
        # Le cache est par nom de fichier. Il est faux dans deux cas, et les deux sont silencieux :
        # 1. la duree demandee a change (re-ancrage, fusion des plans < 2 s) -> la video se desynchronise ;
        # 2. le clip source a ete regenere mais dure pareil -> on remonte l'ancien plan (bug du 2026-10-02, hook refait 2 fois).
        srcs = ([sh.get("src") or self.fr / f"{sh['id']}.png"] if kind == "still" else
                [sh.get(f"src{x}") or self.cl / f"{sh['id']}_{x}.mp4" for x in ("T", "B")] if kind == "vsplit" else
                [sh.get(f"src{x}") or self.cl / f"{sh['id']}_{x}.mp4" for x in ("L", "R")] if kind == "split" else
                [sh.get("src") or self.cl / f"{sh['id']}.mp4"])
        # 3. la SOURCE a change sans changer de duree ni etre plus recente : un plan anime repasse en fixe (la frame png
        #    est plus vieille que le segment). Vu 2 fois le 2026-10-21 (n°05 p15/p25, puis regle « deplacer les segments
        #    perimes » ecrite dans PLAN.md) -> la cle du cache porte aussi le type, les sources et la vitesse.
        # Tous les reglages du plan (speed, reverse, use_first, avatar, aw…) sauf l'ancre : un reglage oublie ici = un
        # segment perime remonte en silence (use_first manquait, signale par le fork n°01 le 2026-10-21).
        cle = json.dumps([kind, [str(x) for x in srcs],
                          sorted((k, str(v)) for k, v in sh.items() if k not in ("id", "anchor"))])
        tag = out.with_suffix(".src")
        if out.exists():
            try:
                fresh = all(Path(x).stat().st_mtime <= out.stat().st_mtime for x in srcs)
                same = tag.exists() and tag.read_text() == cle
                if fresh and same and abs(duration(out) - d) < 1 / 30 + 1e-3:
                    return out
            except Exception:
                pass
            out.unlink()
        tag.write_text(cle)
        if kind == "still":
            # ⛔ round, jamais ceil (2026-10-12, LEGO Karen) : edit() passe un d deja cale sur la grille 30 i/s,
            # mais d*30 sort a 70.0000000001 en flottant et ceil ajoutait UNE IMAGE a ~70 % des plans fixes.
            # Mesure : +1,6 s de retard image/voix a la fin d'un montage de 121 plans, invisible pour qc.py
            # (son check 6 n'existe que pour les projets a final/list.txt). Tous les lots LEGO longs l'avaient.
            n = max(1, round(d * 30))
            src = sh.get("src") or self.fr / f"{sh['id']}.png"
            ff("-loop", "1", "-i", src, "-vf",
               f"scale={W * 2}:{H * 2}:force_original_aspect_ratio=increase,crop={W * 2}:{H * 2},"
               f"zoompan=z='1+0.0005*on':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={n}:s={W}x{H}:fps=30,format=yuv420p", "-frames:v", n, out)
        elif kind == "vsplit":
            # QC Kevin 2026-10-02 : en 9:16 un split horizontal crope chaque moitie a 50% de LARGEUR et tue la lisibilite
            # des que la scene contient une personne. Le split vertical garde toute la largeur a chacune.
            half = f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},crop={W}:{H // 2},fps=30,setsar=1"
            srcs = [sh.get("srcT") or self.cl / f"{sh['id']}_T.mp4", sh.get("srcB") or self.cl / f"{sh['id']}_B.mp4"]
            slows = [max(1.0, (d + 0.05) / duration(s)) for s in srcs]
            ff("-i", srcs[0], "-i", srcs[1], "-filter_complex",
               f"[0:v]setpts={slows[0]:.4f}*PTS,{half},{pad}[t];[1:v]setpts={slows[1]:.4f}*PTS,{half},{pad}[b];"
               f"[t][b]vstack,format=yuv420p,drawbox=x=0:y={H // 2 - 3}:w={W}:h=6:color=white:t=fill", "-an", "-t", f"{d:.3f}", out)
        elif kind == "split":
            half = f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},crop={W // 2}:{H},fps=30,setsar=1"
            srcs = [sh.get("srcL") or self.cl / f"{sh['id']}_L.mp4", sh.get("srcR") or self.cl / f"{sh['id']}_R.mp4"]
            slows = [max(1.0, (d + 0.05) / duration(s)) for s in srcs]
            ff("-i", srcs[0], "-i", srcs[1], "-filter_complex",
               f"[0:v]setpts={slows[0]:.4f}*PTS,{half},{pad}[l];[1:v]setpts={slows[1]:.4f}*PTS,{half},{pad}[r];"
               f"[l][r]hstack,format=yuv420p,drawbox=x={W // 2 - 3}:y=0:w=6:h={H}:color=white:t=fill", "-an", "-t", f"{d:.3f}", out)
        elif kind == "avatar":
            # On recadre d'abord le clip vert sur le SUJET. Sans ca on met a l'echelle toute la frame Kling
            # (720 de large dont la femme n'occupe que le tiers central) et l'incrustation sort minuscule
            # (bug du 2026-10-04 : avatar a ~15% de la largeur au lieu de 41%).
            # ⛔ PLUS AUCUN RECADRAGE AUTOMATIQUE par defaut. subject_bbox remesurait le sujet sur
            # CHAQUE segment : l'incrustation changeait donc de taille et de place a chaque plan.
            # Kevin, 2026-10-04 : "le zoom / la position de la meuf qui parle en bas change tout le
            # temps, au lieu de rester fixe au maximum" puis "tu la fixe a un endroit, tu fais le
            # detouring, et tu superpose a la video de base".
            # Le cadrage se decide dans la FIRST FRAME (plan 1:1 au buste), donc le clip entier se
            # pose tel quel : largeur fixe, position fixe, pour toute la video.
            crop = "null" if sh.get("fixed", True) else \
                self.subject_bbox(sh["avatar"], top=sh.get("atop", 0.52))
            # Un plan de fond + un clip tourne sur FOND VERT, detoure et pose en bas de cadre.
            # Geometrie relevee au pixel sur l'ad Solniera 1649419079904693 (cf. solniera-lot-c) :
            # largeur 0,41 W, hauteur 0,47 H, cale sur le bas, centre sur x = 0,34 W.
            bg, av = sh["bg"], sh["avatar"]
            aw, ax = int(W * sh.get("aw", 0.41)), sh.get("ax", 0.34)
            # bgoff : un b-roll qui CONTINUE d'un plan a l'autre reprend la ou il s'est arrete.
            # Sans ca, un clip coupe en deux par une frontiere de clip Kling repartait de sa premiere
            # image : a l'ecran ca se voit comme le meme plan joue deux fois de suite (Kevin, 2026-10-04 :
            # "a 4 et 8 secondes tu fais tourner 2 fois le meme clip").
            bgoff = sh.get("bgoff", 0.0)
            reste = max(0.3, duration(bg) - bgoff)
            sb = max(1.0, (d + 0.05) / reste)
            sa = max(1.0, (d + 0.05) / duration(av))
            # sh["avatar"] est un MASQUE en niveaux de gris sorti de BiRefNet (`tools/auto-video/matte.py`),
            # encode en lossless. On l'utilise tel quel : c'est deja un alpha continu, entraine pour les
            # cheveux. Historique des trois generations de detourage, mesure en pixels sur une frame :
            #   chromakey sur vert genere ......... 196 991 partiels / 274 789 opaques, sujet transparent
            #   seuil + fermeture sur matte h264 ..   2 311 TROUS dans le sujet (blocs de jean dans les
            #                                        cheveux) + ~8 200 px de ringing en halo blanc
            #   masque BiRefNet ................... pas de seuil du tout, donc ni trou ni halo
            # On ne reseuille PAS un masque continu : le seuil est precisement ce qui fabriquait les trous.
            MASK = "format=gray"
            rgb = sh.get("avatar_rgb", av)   # memes dimensions et memes frames que la matte
            ff(*(("-ss", f"{bgoff:.3f}") if bgoff else ()), "-i", bg, "-i", av, "-i", rgb, "-filter_complex",
               f"[0:v]setpts={sb:.4f}*PTS,{NORM},{pad}[b];"
               f"[1:v]setpts={sa:.4f}*PTS,{crop},{MASK}[al];"
               f"[2:v]setpts={sa:.4f}*PTS,{crop}[c];"
               f"[c][al]alphamerge,scale={aw}:-2[a];"
               f"[b][a]overlay=x={int(W * ax)}-w/2:y=H-h:eof_action=pass,format=yuv420p",
               "-an", "-t", f"{d:.3f}", out)
        else:
            src = sh.get("src") or self.cl / f"{sh['id']}.mp4"
            usable = min(duration(src), sh.get("use_first", 1e9))  # use_first: keep only the clean start of a clip
            # speed (2026-10-12, réf Aurivita) : la réf joue ses clips accélérés pour le rythme. On prend
            # d*speed secondes de clip et on les joue en d. Clip trop court -> on accélère moins, jamais de gel.
            usable = min(usable, d * sh.get("speed", 1.0))
            slow = (d + 0.05) / usable
            rev = "reverse," if sh.get("reverse") else ""
            ff("-i", src, "-an", "-vf", f"trim=0:{usable:.3f},setpts=PTS-STARTPTS,{rev}setpts={slow:.4f}*PTS,{NORM},{pad}", "-t", f"{d:.3f}", out)
        return out

    def captions(self, words, total, style="box", ypos=lambda t: 0.56, size=58, mute=(), cuts=()):
        """Captions as transparent PNGs. style: box (active word in a purple box, centred on the glyphs), plain (white caps only),
        yellow (active word in yellow), native (whole chunk in an opaque white pad, black text - le code des ads natives).
        Chunks never straddle a caption-position change and never exceed the screen width."""
        from PIL import Image, ImageDraw, ImageFont
        # ⛔ Garde-fou, pas une prose : rien entre crochets ne s'incruste JAMAIS a l'ecran. Les tags
        # d'intonation sont deja retires dans vo(), mais une liste de mots peut venir d'ailleurs (STT,
        # fichier edite a la main) et un `[slowly]` burne dans la video ne se rattrape pas apres coup.
        # whitebox3 : meme rendu que whitebox, mais 1 a 3 mots (copie Metabolae, brief lotb-02 : pave blanc arrondi,
        # texte noir, casse normale, groupes de 1 a 3 mots, ~20 caracteres)
        # capsbox : whitebox3 en CAPITALES, ponctuation gardee (copie Metabolae, brief lotb-07 : pastille blanche,
        # texte noir capitales, 1 a 3 mots, y ~0,77)
        caps = style == "capsbox"
        wb3 = style in ("whitebox3", "capsbox")
        if wb3:
            style = "whitebox"
        # lowbox : whitebox (1 a 5 mots, coupe sur la ponctuation) mais affiche en minuscules sans ponctuation sauf « ? »
        # (copie Amua TikTok, brief lotb-04 : boite blanche, texte noir minuscule, y ~0,65)
        low = style == "lowbox"
        if low:
            style = "whitebox"
        # blackbox : whitebox inverse (copie Metabolae journal, brief lotE-06) -- texte BLANC dans une boite NOIRE
        # semi-opaque (~75 %) serree, casse de phrase et ponctuation gardees, 2 a 4 mots, centre sur l'encre.
        blk = style == "blackbox"
        if blk:
            style = "whitebox"
        # film : copie Resilia court-metrage (brief lotb-05) -- la replique entiere (fin marquee U+2063 comme `ligne`,
        # repliee sur 2 lignes), minuscules sans ponctuation (sauf « I » et les noms propres de self.keys),
        # sans-serif grasse ITALIQUE blanche, ombre portee douce, aucun contour ni fond.
        film = style == "film"
        if film:
            style = "ligne"
        # ligne_ombre : copie Ionix chantee (brief lotb-10) -- `ligne` (une ligne de paroles, repliee, casse et
        # ponctuation gardees) mais blanc gras DROIT a ombre portee douce, sans contour, comme `film` sans l'italique.
        ombre = style == "ligne_ombre"
        if ombre:
            style = "ligne"
        # majligne : copie Melanix chantee (brief lotc-02) -- `ligne` (un demi-vers de paroles, replie, fin U+2063) en
        # MAJUSCULES, sans-serif grasse ITALIQUE blanche, contour noir fin + ombre portee, pas de karaoke.
        maj = style == "majligne"
        if maj:
            style = "ligne"
        if style == "red1" and size == 58:
            size = 95   # porte 2 nuit-05 : un mot seul doit se lire de loin, pave ~116 px comme la ref
        # unmot : copie Amua Pixar (brief lotc-04) -- UN mot a la fois, bas de casse sans ponctuation (noms propres de
        # self.keys gardes), blanc Montserrat SemiBold, contour noir fin + ombre legere, sans boite ni couleur.
        # Taille mesuree sur la ref (full_1.jpg : x-height ~50 px sur 1080) -> 92 px, pas les 58 par defaut.
        # unmot_maj : copie Cellumove 3D (brief lotE-08, releve § 5) -- `unmot` (UN mot a la fois) mais en MAJUSCULES,
        # Montserrat ExtraBold, blanc a OMBRE PORTEE sombre marquee, sans contour ni boite. Ponctuation retiree en tete et
        # en queue seulement (« 250,000 », « 50% », « 90-DAY », « DOESN'T » restent entiers). Ajout pur : `unmot` inchange.
        umaj = style == "unmot_maj"
        if umaj:
            style = "unmot"
        if style == "unmot" and size == 58:
            size = 92
        bad =[w["w"] for w in words if "[" in w["w"] or "]" in w["w"]]
        if bad:
            raise SystemExit(f"captions : {len(bad)} mot(s) entre crochets, ils seraient incrustes a "
                             f"l'ecran -> {bad[:6]}. Un tag d'intonation ne se capture pas.")
        # thin : style FreshBro (petit, minuscule, blanc fin + ombre, sans boite), brief copie freshbro 2026-10-07
        # phrase : copie Onset (brief ua02-ref3) -- blanc pur gras, casse de PHRASE et ponctuation gardees,
        # 1 a 3 mots, ombre tres legere, aucun fond, aucun contour.
        # red : copie ClarityMD (brief nuit-07) -- capitales condensees blanches a liseré noir, mot actif sur pave rouge
        # red1 : meme rendu que red, mais UN SEUL mot a l'ecran a la fois (copie ClarityMD, brief nuit-05)
        # whitebox : copie ClarityMD (brief nuit-06) -- chaque chunk dans SA boite blanche arrondie, texte noir medium,
        # casse de phrase et ponctuation gardees, 2 a 5 mots, pas de karaoke.
        # mono : copie Metabolae (brief nuit-02) -- DejaVu Sans Mono blanc, ombre douce, sans fond ni contour, bas de casse,
        # chunk entier (pas de karaoke), 2 a 6 mots.
        font = ImageFont.truetype(MONO_FONT if style == "mono" else WHITEBOX_FONT if style == "whitebox" else (FONT_BOLD if style in ("thin", "phrase", "ligne") else (FONT_IMPACT if style in ("red", "red1") else FONT_BLACK)), size)
        if film:
            font = ImageFont.truetype(FILM_FONT, size)
        if maj:
            font = ImageFont.truetype(FILM_FONT, size)
        if style == "unmot":
            font = ImageFont.truetype(UNMOT_FONT, size)
        if umaj:
            font = ImageFont.truetype(UNMOT_MAJ_FONT, size)
            font.set_variation_by_name("ExtraBold")
        # karaoke : copie Amua (brief lotb-01, AI Song) -- 2 a 4 mots, sans-serif grasse ITALIQUE blanche a contour noir
        # fin + ombre, le mot chante passe en jaune vif, bas de casse sauf les noms propres de self.keys
        # sitcom : copie Tradesman « Shred » (brief lotc-03, AI Song 2D) -- blanc, sans-serif REGULAR, fine ombre portee,
        # sans contour ni fond, une ligne, chunk entier (pas de karaoke), bas de casse sauf I et self.keys. La coupe des
        # demi-vers est marquee par l'appelant avec U+2063 (comme karaoke). Petit : ~27 px de capitale sur 720.
        if style == "sitcom":
            font = ImageFont.truetype(_font("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"), 56)
        if style == "karaoke":
            font = ImageFont.truetype(FILM_FONT, size)
        # vert : copie Metabolae face cam (brief lotb-08) -- 2-3 mots en minuscules (noms propres de self.keys gardes),
        # sans-serif grasse blanche a ombre portee douce, sans contour ni fond, le mot dit passe en vert Feelora.
        if style == "vert":
            font = ImageFont.truetype(FONT_BOLD, size)
        cap = self.here / "captions"
        cap.mkdir(exist_ok=True)
        for p in cap.glob("*.png"):
            p.unlink()
        # Guillemets retires aussi (2026-10-12, Lisa) : une replique entre guillemets laissait `CHEMO"` a l'ecran.
        # violet : releve AI Song UA 02 ref 1 (Resilia) -- pilule blanche, texte #CF00FF gras, bas de casse, une ligne
        # ponctuation retiree, sauf . et , entre deux chiffres (« $39.90 » ne doit pas devenir « $3990 »)
        P_ = r"[.,](?!\d)|(?<!\d)[.,]|[?!:;\"\u201c\u201d]"
        up = lambda s: re.sub(P_, "", s).lower() if style in ("thin", "violet") else re.sub(P_, "", s).upper()
        if style in ("phrase", "whitebox"):
            up = lambda s: re.sub(r"[\"\u201c\u201d]", "", s).upper() if caps else re.sub(r"[\"\u201c\u201d]", "", s)
            if low:
                up = lambda s: (lambda r: r if r.upper().startswith("GLP") else r.lower())(re.sub(r"[.,!:;\"\u201c\u201d]", "", s))
        if style == "mono":
            up = lambda s: re.sub(r"[.,;:\"\u201c\u201d]", "", s).lower()
        # ligne : copie Resilia (brief nuit-01) -- UNE ligne de paroles par caption, blanc gras a contour noir fin,
        # casse de la phrase, ponctuation et MAJUSCULES d'insistance gardees, pas de karaoke. La fin de ligne est
        # marquee par l'appelant avec U+2063 (separateur invisible) sur le dernier mot.
        if style == "ligne":
            up = lambda s: re.sub(r"[\"\u201c\u201d\u2063]", "", s)
        if maj:
            up = lambda s: re.sub(r"[.,;:\"\u201c\u201d\u2063]", "", s).upper()
        if film:
            def up(s):
                s = re.sub(r"[.,?!:;\"\u201c\u201d\u2063\u2026]", "", s)
                return s if s == "I" or s.startswith("I'") or s in self.keys else s.lower()
        if style in ("karaoke", "vert", "unmot", "sitcom"):
            def up(s):
                s = re.sub(r"[.,?!:;\"\u201c\u201d\u2063]", "", s)
                return s if s in self.keys or s == "I" or s.startswith("I'") else s.lower()
        if umaj:
            up = lambda s: re.sub(r"^[^\w%]+|[^\w%]+$", "", s.replace("⁣", "")).upper()
        muted =lambda s: any(a <= s < z for a, z in mute)  # plages sans caption (carton POV sur le hook)
        chunks, cur = [], []
        for w in words:
            if cur and ypos(w["s"]) != ypos(cur[0]["s"]):
                chunks.append(cur); cur = []
            cur.append(w)
            if style != "ligne" and len(cur) > 1 and font.getlength(" ".join(up(x["w"]) for x in cur)) > W * 0.86:
                cur.pop(); chunks.append(cur); cur = [w]
            # "pixar" : UN SEUL mot a l'ecran a la fois. C'est la signature du format narre (brief 11),
            # elle ne doit ressembler a aucune de nos autres videos.
            # ionix : copie Ionix Labs (brief nuit-09) -- jusqu'a 6 mots sur UNE ligne, pave violet #7408E0 sous le mot actif
            if style == "ligne":
                if w["w"].endswith("\u2063"):
                    chunks.append(cur); cur = []
                continue
            # karaoke (porte 2 lot B n°1) : une caption ne chevauche jamais deux lignes de paroles ; l'ad-lib reste seul
            if style == "sitcom":          # brief lotc-03 : coupe UNIQUEMENT aux demi-vers (U+2063) et a la largeur
                if w["w"].endswith("\u2063"):
                    chunks.append(cur); cur = []
                continue
            if style == "karaoke" and w["w"].endswith("\u2063"):
                chunks.append(cur); cur = []
                continue
            if style in ("pixar", "red1", "unmot") or len(cur) >= (3 if style in ("plain", "key", "phrase", "vert") else (6 if style in ("ionix", "mono") else ((3 if wb3 else (4 if blk else 5)) if style == "whitebox" else 4))) or len(" ".join(x["w"] for x in cur)) > (34 if style in ("ionix", "mono") else ((20 if wb3 else (24 if blk else 28)) if style == "whitebox" else 20)) or re.search(r"[.,?!:]$", w["w"]):
                chunks.append(cur); cur = []
        if cur:
            chunks.append(cur)
        blank = cap / "blank.png"
        Image.new("RGBA", (W, H), (0, 0, 0, 0)).save(blank)
        lines, t = [], 0.0
        for ci, ch in enumerate(chunks):
            y = int(H * ypos(ch[0]["s"]))
            toks = [up(x["w"]) for x in ch]
            chunk_end = chunks[ci + 1][0]["s"] if ci + 1 < len(chunks) else total
            # porte 3 lot E n°07 (2026-10-26) : la queue du chunk debordait sur le plan suivant (3 frames sur l'etiquette).
            # Une caption s'arrete a la premiere coupe apres son dernier mot.
            chunk_end = min([chunk_end] + [c for c in cuts if c > ch[-1]["s"]])
            frames = range(len(ch)) if style not in ("plain", "native", "thin", "key", "pill", "rose", "phrase", "violet", "whitebox", "mono", "ligne", "sitcom") else [0]
            # ⛔ `rose` (reference 2 du releve AI Song) : MAJUSCULES blanches + UN mot dans un bloc
            # rose/magenta. Lequel ? Le brief 02 ne documente qu'un seul cas, et il est chiffre :
            # « le mot 48 sur-ligne rose ». On sur-ligne donc le CHIFFRE, et rien d'autre : inventer
            # une heuristique d'emphase serait decider du gout a la place de Kevin.
            # ⚠️ ECART MESURE ET ASSUME : sur le lot 02, cette regle ne s'allume que sur 10 captions
            # sur 241 (4,1 %), alors que la reference en fait son marqueur visuel n°1 et le pose
            # bien plus souvent. Le releve ne donne que 3 exemples, dont un sans surlignage : il ne
            # permet pas de deduire la vraie regle. Combler l'ecart demande soit un relevé image par
            # image de la reference, soit un mot de Kevin sur quoi sur-ligner. En attendant, on
            # sur-ligne peu mais JUSTE, plutot que souvent et au hasard.
            rose_i = next((j for j, x in enumerate(toks) if re.search(r"\d", x)), -1)
            for wi in frames:
                start = ch[wi]["s"]
                # native, comme plain, affiche le chunk entier d'un coup : sa duree est celle du CHUNK, pas du premier mot
                stop = (ch[wi + 1]["s"] if wi + 1 < len(ch) and style not in ("plain", "native", "thin", "key", "pill", "rose", "phrase", "violet", "whitebox", "mono", "ligne", "sitcom")
                        else min(chunk_end, ch[-1]["e"] + 0.4))
                if start > t:
                    lines += [f"file '{blank}'", f"duration {start - t:.3f}"]
                im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
                dr = ImageDraw.Draw(im)
                sp = dr.textlength(" ", font=font)
                # ligne : la caption se REPLIE sur 2 lignes (ou plus) au lieu d'etre coupee a la largeur -- porte 2 nuit-01 :
                # couper donnait des captions orphelines d'un mot (« came », « going », « my hand »).
                if style == "ligne":
                    rangs = [[]]
                    for tok in toks:
                        if rangs[-1] and dr.textlength(" ".join(rangs[-1] + [tok]), font=font) > W * 0.86:
                            rangs.append([tok])
                        else:
                            rangs[-1].append(tok)
                    if len(rangs) > 1 and len(rangs[-1]) == 1 and len(rangs[-2]) > 2:   # pas de mot seul en 2e ligne
                        rangs[-1].insert(0, rangs[-2].pop())
                    lh = int(size * 1.2)
                    for n, rg in enumerate(rangs):
                        s_ = " ".join(rg)
                        if maj:
                            xm, ym = (W - dr.textlength(s_, font=font)) / 2, y - (len(rangs) - 1) * lh // 2 + n * lh
                            dr.text((xm + 4, ym + 4), s_, font=font, fill=(0, 0, 0, 150), stroke_width=3, stroke_fill=(0, 0, 0, 150))
                            dr.text((xm, ym), s_, font=font, fill="white", stroke_width=3, stroke_fill="black")
                            continue
                        dr.text(((W - dr.textlength(s_, font=font)) / 2, y - (len(rangs) - 1) * lh // 2 + n * lh), s_,
                                font=font, fill="white", stroke_width=0 if film else 2, stroke_fill="black") if not (film or ombre) else (
                            dr.text(((W - dr.textlength(s_, font=font)) / 2 + 3, y - (len(rangs) - 1) * lh // 2 + n * lh + 3),
                                    s_, font=font, fill=(0, 0, 0, 140)),
                            dr.text(((W - dr.textlength(s_, font=font)) / 2, y - (len(rangs) - 1) * lh // 2 + n * lh), s_,
                                    font=font, fill="white"))
                widths = [] if style == "ligne" else [dr.textlength(x, font=font) for x in toks]
                x = (W - (sum(widths) + sp * (len(toks) - 1))) / 2
                if style in ("native", "pill", "violet", "whitebox"):
                    tot = sum(widths) + sp * (len(toks) - 1)
                    # PIL dessine depuis l'ASCENDANTE, pas depuis l'encre. Un pad calcule sur y (l'origine) donnait
                    # 37 px de blanc au-dessus du texte et 2 px en dessous : un gros rectangle blanc avec le texte
                    # colle en bas (bug du 2026-10-03, assiette-temoin). Kevin : "toujours centrer verticalement
                    # les captions si elles sont dans un background". On mesure l'encre reelle et on pad symetrique.
                    ink = dr.textbbox((x, y), " ".join(toks), font=font)
                    fond = (0, 0, 0, 191) if blk else ((255, 255, 255, 255) if style in ("native", "violet", "whitebox") else (0, 0, 0, 235))
                    rayon = 8 if style == "native" else (16 if style == "whitebox" else 26)
                    dr.rounded_rectangle((x - 24, ink[1] - 18, x + tot + 24, ink[3] + 18), rayon, fill=fond)
                for k, (tok, tw) in enumerate(zip(toks, widths)):
                    color = (255, 255, 255) if blk else (0, 0, 0) if style in ("native", "whitebox") else ((255, 94, 162) if style == "pixar" else
                             ((207, 0, 255) if style == "violet" else "white"))
                    # lot E 07 (copie Sorviq) : mots-cles colores dans le pave blanc -- le mot porte sa couleur
                    # ("c": (r, g, b)), posee par l'appelant. Sans cle "c", rendu inchange.
                    if style == "whitebox" and ch[k].get("c"):
                        color = tuple(ch[k]["c"])
                    if k == wi and style in ("box", "teal"):
                        l, t_, r, bt = dr.textbbox((x, y), tok, font=font, stroke_width=5)
                        # teal : pave bleu -> teal sans contour (copie ionix plage, brief 2026-10-07)
                        if style == "teal":
                            box = (int(l - 12), int(t_ - 10), int(r + 12), int(bt + 10))
                            g = Image.new("RGBA", (box[2] - box[0], box[3] - box[1]))
                            gd = ImageDraw.Draw(g)
                            for gx in range(g.width):
                                f_ = gx / max(1, g.width - 1)
                                gd.line((gx, 0, gx, g.height), fill=(int(30 + f_ * 0), int(110 + f_ * 90), int(240 - f_ * 50), 255))
                            m = Image.new("L", g.size, 0); ImageDraw.Draw(m).rounded_rectangle((0, 0, g.width - 1, g.height - 1), 14, fill=255)
                            im.paste(g, box[:2], m)
                        else:
                            dr.rounded_rectangle((l - 12, t_ - 10, r + 12, bt + 10), 14, fill=(124, 58, 237, 255), outline=(255, 255, 255, 255), width=4)
                    if k == wi and style == "ionix":
                        l, t_, r, bt = dr.textbbox((x, y), tok, font=font)
                        dr.rounded_rectangle((l - 12, t_ - 10, r + 12, bt + 10), 12, fill=(116, 8, 224, 255))
                    if k == wi and style in ("red", "red1"):
                        l, t_, r, bt = dr.textbbox((x, y), tok, font=font, stroke_width=4)
                        dr.rounded_rectangle((l - 10, t_ - 8, r + 10, bt + 8), 8, fill=(229, 25, 35, 255))
                    if k == wi and style in ("yellow", "karaoke"):
                        color = (255, 232, 0)
                    if k == wi and style == "vert":
                        # vert de la feuille du logo, eclairci : le vert du logo (63,163,77) disparaissait sur un pull olive
                        color = (120, 230, 105)
                    if style == "rose" and k == rose_i:
                        l, t_, r, bt = dr.textbbox((x, y), tok, font=font, stroke_width=5)
                        dr.rounded_rectangle((l - 14, t_ - 10, r + 14, bt + 10), 12,
                                             fill=(236, 0, 140, 255))
                    # key : chunk entier blanc, UN mot cle fixe en jaune (self.keys), copie cellumove 2026-10-07
                    if style == "key" and k == next((j for j, x in enumerate(toks) if x in self.keys), -1):
                        color = (255, 228, 0)
                    # pixar : rose bonbon cerne de BLANC, pas de noir -- sur un rendu anime clair, un contour
                    # noir fait sale ; le blanc detache le mot sans l'alourdir.
                    sw = 0 if style in ("native", "pill", "phrase", "violet", "ionix", "whitebox", "mono", "vert", "sitcom") or (style == "rose" and k == rose_i) \
                        else (7 if style == "pixar" else (1 if style == "thin" else (2 if style == "ligne" else (3 if style == "karaoke" else (4 if style == "unmot" else 5)))))
                    if umaj:
                        sw = 0
                        for o, a_ in ((7, 90), (5, 150), (3, 200)):   # ombre portee marquee, sans contour (releve § 5)
                            dr.text((x + o, y + o), tok, font=font, fill=(0, 0, 0, a_))
                    elif style in ("thin", "phrase", "ionix", "mono", "karaoke", "vert", "unmot", "sitcom"):
                        dr.text((x + 3, y + 3), tok, font=font, fill=(0, 0, 0, 170 if style in ("thin", "mono", "sitcom") else 120))
                    dr.text((x, y), tok, font=font, fill=color, stroke_width=sw,
                            stroke_fill=(255, 255, 255) if style == "pixar" else "black")
                    x += tw + sp
                p = cap / f"c{ci:03d}_{wi}.png"
                if muted(start):
                    p = blank          # la place dans la timeline est gardee, le texte n'est pas dessine
                else:
                    im.save(p)
                dur = max(stop - start, 0.04)
                lines += [f"file '{p}'", f"duration {dur:.3f}"]
                t = start + dur
        if total > t:
            lines += [f"file '{blank}'", f"duration {total - t:.3f}"]
        lines.append(f"file '{blank}'")
        # Un PNG seul se lit a 25 i/s (base de temps 1/25 s) : chaque borne de caption glissait sur une grille de 0,04 s
        # et la caption precedente debordait d'une image sur le plan suivant (2026-11-02, montage-b-smooth). 30 i/s = la grille du montage.
        lines = [x for l in lines for x in ([l, "option framerate 30"] if l.startswith("file ") else [l])]
        (cap / "list.txt").write_text("ffconcat version 1.0\n" + "\n".join(lines) + "\n")
        return cap / "list.txt"

    @staticmethod
    def pov_png(path, text, size=62, y=0.40, pad=26):
        """Carton POV facon Herbies : boite blanche opaque, texte noir centre, retour a la ligne automatique.
        C'est le device qui porte le hook quand les captions sont muselees dessus."""
        from PIL import Image, ImageDraw, ImageFont
        f = ImageFont.truetype(FONT_BLACK, size)
        im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        dr = ImageDraw.Draw(im)
        lines, cur = [], ""
        for word in text.split():
            trial = f"{cur} {word}".strip()
            if dr.textlength(trial, font=f) > W * 0.78 and cur:
                lines.append(cur); cur = word
            else:
                cur = trial
        lines.append(cur)
        lh = int(size * 1.22)
        # Meme garde-fou que les captions native : on cale la boite sur l'ENCRE du bloc, pas sur l'origine
        # d'ecriture de PIL, sinon le texte n'est pas centre verticalement dans le fond blanc.
        ink_top = dr.textbbox((0, 0), lines[0], font=f)[1]
        ink_bot = dr.textbbox((0, 0), lines[-1], font=f)[3] + lh * (len(lines) - 1)
        bw = max(dr.textlength(l, font=f) for l in lines) + pad * 2
        bh = (ink_bot - ink_top) + pad * 2
        x0, y0 = (W - bw) / 2, H * y
        dr.rectangle((x0, y0, x0 + bw, y0 + bh), fill=(255, 255, 255, 255))
        for i, l in enumerate(lines):
            dr.text(((W - dr.textlength(l, font=f)) / 2, y0 + pad - ink_top + i * lh), l, font=f, fill=(0, 0, 0, 255))
        im.save(path)
        return path

    @staticmethod
    def text_png(path, items):
        """items: [(text, font_path, size, (x|'center', y), fill, stroke)] -> transparent 1080x1920 PNG."""
        from PIL import Image, ImageDraw, ImageFont
        im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        dr = ImageDraw.Draw(im)
        for text, fp, size, (x, y), fill, stroke in items:
            f = ImageFont.truetype(fp, size)
            if x == "center":
                x = (W - dr.textlength(text, font=f)) / 2
            dr.text((x, y), text, font=f, fill=fill, stroke_width=stroke, stroke_fill="black")
        im.save(path)
        return path

    @staticmethod
    def cta_meta_png(path, pill, button):
        """Fausse UI Meta en haut a gauche : pastille blanche arrondie + bouton bleu marine.
        C'est le CTA de l'ad Solniera 1649419079904693, releve en frames (cf. solniera-lot-c)."""
        from PIL import Image, ImageDraw, ImageFont
        im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        dr = ImageDraw.Draw(im)
        f1 = ImageFont.truetype(FONT_BLACK, 38)
        f2 = ImageFont.truetype(FONT_BLACK, 40)
        x, y, pad = int(W * 0.04), int(H * 0.055), 22
        ink = dr.textbbox((x + pad, y + pad), pill, font=f1)
        dr.rounded_rectangle((x, y, ink[2] + pad, ink[3] + pad), 18, fill=(255, 255, 255, 240))
        dr.text((x + pad, y + pad), pill, font=f1, fill=(20, 20, 20, 255))
        y2 = ink[3] + pad + 18
        ink2 = dr.textbbox((x + pad + 8, y2 + pad), button, font=f2)
        dr.rounded_rectangle((x, y2, ink2[2] + pad + 8, ink2[3] + pad), 18, fill=(28, 42, 92, 255))
        dr.text((x + pad + 8, y2 + pad), button, font=f2, fill=(255, 255, 255, 255))
        im.save(path)
        return path

    def edit_prebuilt(self, body, words, vo_audio, out, caption_style="plain", ypos=lambda t: 0.78,
                      overlays=(), music_volume=0.08):
        """Montage final quand le CORPS est deja assemble (cas des videos ou Kling porte la voix :
        la timeline est imposee par les clips, pas par timing()). Pose captions + overlays + son."""
        total = duration(body)
        caps = self.captions(words, total, caption_style, ypos)
        inputs = ["-i", str(body), "-f", "concat", "-safe", "0", "-i", str(caps)]
        fl = "[1:v]format=rgba,fps=30[c];[0:v][c]overlay=0:0:eof_action=pass[v0];"
        last = "v0"
        for k, (png, a, z) in enumerate(overlays):
            inputs += ["-i", str(png)]
            fl += f"[{k + 2}:v]format=rgba[o{k}];[{last}][o{k}]overlay=0:0:enable='gte(t,{a:.3f})*lt(t,{z:.3f})'[v{k + 1}];"
            last = f"v{k + 1}"
        fl += f"[{last}]format=yuv420p[v];"
        vi = len(overlays) + 2
        inputs += ["-i", str(vo_audio)]
        n = vi + 1
        if self.music and Path(self.music).exists():
            inputs += ["-stream_loop", "-1", "-i", str(self.music)]
            fl += (f"[{vi}:a]aresample=44100[va];[{n}:a]aresample=44100,volume={music_volume},"
                   f"afade=t=out:st={max(0, total - 2):.2f}:d=2[ma];[va][ma]amix=inputs=2:duration=first:normalize=0,"
                   f"aresample=44100[a]")
        else:
            fl += f"[{vi}:a]aresample=44100[a]"
        ff(*inputs, "-filter_complex", fl, "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-crf", "19",
           "-preset", "medium", "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-t", f"{total:.3f}",
           "-movflags", "+faststart", str(out))
        return self.loud_fix(out)

    @staticmethod
    def bandeau_png(path, texte, hauteur=0.16, fond=(206, 26, 26, 255), size=62, contour=0):
        """Le carton-titre d'ouverture : bandeau plein en HAUT du cadre, texte blanc centre.

        ⛔ Releve sur la reference 2 (`ai-song-releve-1`, section F) : « bandeau rouge en haut,
        texte blanc, par-dessus le plan du telephone ». Les references 1 et 4 ne l'ont pas. Le
        texte ne s'invente pas : il est ecrit verbatim dans le brief du lot.
        """
        from PIL import Image, ImageDraw, ImageFont
        im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        dr = ImageDraw.Draw(im)
        bas = int(H * hauteur)
        # fond transparent = pas de bandeau, juste le texte : c'est le « titre brule » du format
        # historical (blanc gras majuscules, 3 lignes), qui n'a pas de bande derriere lui.
        if fond[3]:
            dr.rectangle((0, 0, W, bas), fill=fond)
        # Le titre de la reference tient sur plusieurs lignes : on replie sur la largeur utile.
        font = ImageFont.truetype(FONT_BLACK, size)
        mots, lignes, cur = texte.upper().split(), [], ""
        for m in mots:
            essai = (cur + " " + m).strip()
            if dr.textlength(essai, font=font) > W * 0.90 and cur:
                lignes.append(cur); cur = m
            else:
                cur = essai
        lignes.append(cur)
        h = size * 1.18
        y = (bas - h * len(lignes)) / 2
        for l in lignes:
            dr.text(((W - dr.textlength(l, font=font)) / 2, y), l, font=font, fill="white",
                    stroke_width=contour, stroke_fill="black")
            y += h
        im.save(path)   # `im` est deja du plein cadre transparent : pas de composite a faire
        return path

    @staticmethod
    def card_png(path, src, w=0.42, radius=36):
        """Une frame d'un clip (ou une image) transformee en CARTE a coins arrondis, fond transparent.
        C'est la brique des incrustations b-roll de l'ad Solniera 1103561988821792 (cf. solniera-lot-c) :
        le plan de fond continue de tourner, la carte arrive en zoom in et repart en zoom out."""
        from PIL import Image, ImageDraw
        if str(src).endswith(".mp4"):
            tmp = Path(str(path) + ".src.png")
            ff("-ss", "0.5", "-i", str(src), "-frames:v", "1", str(tmp))
            src = tmp
        im = Image.open(src).convert("RGBA")
        cw = int(W * w)
        im = im.resize((cw, int(im.height * cw / im.width)), Image.LANCZOS)
        mask = Image.new("L", im.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, im.width - 1, im.height - 1), radius, fill=255)
        im.putalpha(mask)
        im.save(path)
        return path

    def edit(self, shots, words, vo_audio, out, caption_style="box", ypos=lambda t: 0.56, overlays=(), music_volume=0.08, sfx=(),
             caption_mute=(), cards=(), flash=(), min_shot=None, caption_words=None):
        """overlays: [(png, start, end)] or [(png, shot_id)] laid over the video (titles, effect words).
        sfx: [(audio, time, volume)] sound effects, only when the reference uses them or Kevin asks (e.g. buzzer on a crossed word).
        caption_mute: [shot_id] or [(start, end)] where the captions are suppressed (a POV card over the hook, for instance).
        flash: [shot_id] -> un flash blanc de 2 frames sur la COUPE d'entree de ce plan (Kevin 2026-10-09 :
          "des petits effets entre les transitions, pas obligé que ça soit toutes"). Le flash se DESSINE sur
          l'image, il ne fond pas deux plans l'un dans l'autre : un xfade consomme de la duree et decalerait
          toute la voix off, qui est ancree au mot."""
        # ⛔ `edit()` IGNORAIT le min_shot du lot : il rappelait timing() a vide, donc avec MIN_SHOT=2.0,
        # alors que le projet avait decide 1,6 s. Mesure le 2026-10-19 sur lot-song-ora-01 : le lot
        # croyait monter 87 plans, le montage en a pose 77. 13 CLIPS PAYES ET JAMAIS MONTES, dont le
        # plan de la robe bleue (« I put it on and cried »). Et rien ne le signalait : la ligne de
        # resultat affiche le nombre de plans ENVOYES, pas le nombre de plans montes.
        # La regle des plans courts doit se decider UNE fois par lot, pas deux fois avec deux valeurs.
        tm = self.timing(shots, words, min_shot=min_shot)
        # cut points snapped to the 30 fps grid on the absolute timeline, so rounding never accumulates (QC: 0.4 s drift on 24 shots)
        q = lambda t: round(t * 30) / 30
        tm = {sid: (q(a), q(a + d) - q(a)) for sid, (a, d) in tm.items()}
        shots = [sh for sh in shots if sh["id"] in tm]  # les plans absorbes (< MIN_SHOT) ne sont pas montes
        segs = [self.segment(sh, tm[sh["id"]][1]) for sh in shots]
        (self.seg / "list.txt").write_text("".join(f"file '{p}'\n" for p in segs))
        body = self.here / "body.mp4"
        ff("-f", "concat", "-safe", "0", "-i", self.seg / "list.txt", "-c", "copy", body)
        total = sum(d for _, d in tm.values())
        mute = [(tm[m][0], tm[m][0] + tm[m][1]) if isinstance(m, str) else m for m in caption_mute]
        # ⛔ Le TIMING peut venir d'un STT, le TEXTE doit venir du script. Sur un lot chante, les mots
        # sont reconstruits par whisper. `caption_words` porte le texte juste aux memes
        # instants ; `words` reste la liste qui ancre les plans.
        cuts = sorted(a for a, _ in tm.values() if a > 0)
        caps = self.captions(caption_words or words, total, caption_style, ypos, mute=mute, cuts=cuts)
        # setpts=N/30 : le concat -c copy laisse des horodatages a -0,3 ms de la grille (2.533008 au lieu de 2.533333) ;
        # l'image de la coupe prenait alors la caption PRECEDENTE (1 image sur le plan suivant, 2026-11-02 montage-b-smooth).
        inputs, fl, last = ["-i", body, "-f", "concat", "-safe", "0", "-i", caps], "[1:v]format=rgba,fps=30[c];[0:v]setpts=N/30/TB[b];[b][c]overlay=0:0:eof_action=pass[v0];", "v0"
        overlays = [(o[0], tm[o[1]][0], tm[o[1]][0] + tm[o[1]][1]) if len(o) == 2 else o for o in overlays]  # (png, shot_id) allowed
        # Un carton cale avec at() part au 1er MOT de la phrase, alors que le plan qu'il recouvre commence 0,05 s avant
        # (timing() prend words[i].s - 0.05). Resultat : une a deux frames du nouveau plan clignotent avant le carton noir
        # (Kevin 2026-10-03, "juste avant pendant une demi seconde c'est degeu"). On recale sur la coupe du plan.
        bounds = sorted(a for a, _ in tm.values())
        # -1/60 : on recale UNE DEMI-FRAME avant la coupe. Pile sur la borne, between(t,a,z) rate encore la premiere
        # frame (207/30 ne tombe pas juste en binaire) et il reste un eclair du plan suivant.
        snap = lambda t: next((b - 1 / 60 for b in bounds if 0 <= t - b <= 0.25), t)
        overlays = [(png, snap(a), z) for png, a, z in overlays]
        # ⛔ 2026-10-26 (lot D, 3e chevauchement du lot : calques 02, captions 02, captions 07) : tout `enable` de
        # calque / carte / flash est desormais l'intervalle SEMI-OUVERT gte(t,a)*lt(t,z), jamais between(t,a,z)
        # (inclusif : deux calques consecutifs se dessinaient ensemble sur l'image de la borne). Le recalage ci-dessous
        # (fin - 1/60 sur une coupe) reste valable et sans effet de bord.
        # ⛔ lot D 2026-10-23 (porte 3) : `between(t,a,z)` est INCLUSIF. Un calque dont la fin tombe pile sur une coupe
        # (fin = debut du plan suivant) restait affiche sur la 1re image du plan suivant (33 ms). On ferme une demi-image
        # avant la coupe. Ne touche que les fins qui coincident avec une coupe : le rendu des autres calques est inchange.
        _cut = lambda z: next((b for b in bounds if abs(z - b) < 1e-3), None)
        overlays = [(png, a, (z - 1 / 60 if _cut(z) is not None else z)) for png, a, z in overlays]
        assert all(z > a for _, a, z in overlays), "overlay vide apres clamp a la coupe"
        # cards: [(png, x, y, start, end)] en ratios -> carte posee avec zoom in a l'entree, zoom out a la sortie.
        # Kevin 2026-10-04 : "les b-rolls arrivent avec un effet de zoom in et repartent avec un effet de zoom out,
        # par dessus le shot de base qui continue d'etre en arriere plan".
        for k, (png, cx, cy, a, z) in enumerate(cards):
            # ⛔ les cartes sont ajoutees aux inputs AVANT les overlays (0 body, 1 captions, 2.. cartes) : l'ancien
            # `len(overlays) + 2 + k` pointait sur un overlay des qu'il y en avait un (lotb-07, badge + mention).
            idx = 2 + k
            # ⛔ lotb-07 : sans -loop l'image n'a qu'UNE frame, `t` reste a 0 et le zoom ne joue jamais ; et
            # l'expression non quotee cassait le filtre sur ses virgules. Les cartes n'avaient jamais tourne.
            inputs += ["-loop", "1", "-framerate", "30", "-t", f"{total:.3f}", "-i", str(png)]
            IN, OUT = 0.25, 0.20  # durees des deux effets, relevees sur la reference
            # ease: 0.60 -> 1.00 a l'entree, 1.00 -> 0.60 a la sortie, lineaire (suffit a cette echelle)
            e = (f"min(1,0.60+0.40*(t-{a:.3f})/{IN})" if z - a > IN + OUT else "1")
            e = f"if(gt(t,{z - OUT:.3f}), 1-0.40*(t-{z - OUT:.3f})/{OUT}, {e})"
            fl += (f"[{idx}:v]format=rgba,scale=w='iw*({e})':h=-2:eval=frame[k{k}];"
                   f"[{last}][k{k}]overlay=x={cx}*W-w/2:y={cy}*H-h/2:enable='gte(t,{a:.3f})*lt(t,{z:.3f})'[c{k}];")
            last = f"c{k}"
        for k, (png, a, z) in enumerate(overlays):
            # ⛔ lot C 2026-10-23 (06) : sans -framerate le PNG tourne a 25 i/s sur une video a 30 i/s, et autour des
            # coupes l'overlay (croix rouges, badges) apparait ou disparait une frame trop tot ou trop tard.
            inputs += ["-loop", "1", "-framerate", "30", "-t", f"{total:.3f}", "-i", png]
            fl += f"[{k + len(cards) + 2}:v]format=rgba[o{k}];[{last}][o{k}]overlay=0:0:enable='gte(t,{a:.3f})*lt(t,{z:.3f})'[v{k + 1}];"
            last = f"v{k + 1}"
        for k, sid in enumerate(flash):
            # un plan < MIN_SHOT a ete absorbe par son voisin : le flash suit l'hote, comme les overlays
            while sid in Project.MERGED:
                sid = Project.MERGED[sid]
            a = tm[sid][0]
            if a <= 0:   # pas de flash sur la premiere image : il mangerait le hook
                continue
            fl += (f"[{last}]drawbox=x=0:y=0:w=iw:h=ih:color=white@0.45:t=fill:enable='gte(t,{a:.3f})*lt(t,{a + 1 / 30:.3f})',"
                   f"drawbox=x=0:y=0:w=iw:h=ih:color=white@0.20:t=fill:enable='gte(t,{a + 1 / 30:.3f})*lt(t,{a + 2 / 30:.3f})'[f{k}];")
            last = f"f{k}"
        vi, mi = len(overlays) + len(cards) + 2, len(overlays) + len(cards) + 3
        # -stream_loop -1 : sans lui la musique s'arrete net quand le fichier se termine et la fin de la
        # video part en silence. Mesure le 2026-10-11 : positive_beat fait 110,4 s, LEGO 2 en fait 168,5 —
        # 58 s muettes, et rien ne le signale puisque atrim ne peut pas rallonger une source trop courte.
        # montage() bouclait deja (l.734), edit() non : le defaut etait dans UNE des deux fonctions.
        # Une ad peut n'avoir AUCUNE musique : la reference UGC yapper SayBeam n'en a pas, et une nappe
        # posee la-dessus casse le registre "filme au telephone". edit() ouvrait self.music sans condition
        # et plantait sur None, alors que edit_prebuilt() gere deja le cas (l.785). Meme divergence entre
        # les deux fonctions de montage que le -stream_loop ci-dessous : corrigee aux deux endroits.
        musique = bool(self.music and Path(self.music).exists())
        inputs += ["-i", vo_audio]
        if musique:
            inputs += ["-stream_loop", "-1", "-i", str(self.music)]
        fl += f"[{last}]format=yuv420p[v];"
        if musique:
            fl += (f"[{vi}:a]apad=whole_dur={total:.3f},asplit=2[vo][key];"
                   f"[{mi}:a]atrim=0:{total:.3f},asetpts=PTS-STARTPTS,volume={music_volume},afade=t=in:d=0.6,afade=t=out:st={total - 2.0:.3f}:d=2.0[m];"
                   f"[m][key]sidechaincompress=threshold=0.03:ratio=6:attack=15:release=350[duck];")
            mixin, nmix = "[vo][duck]", 2
            isfx = mi + 1
        else:
            fl += f"[{vi}:a]apad=whole_dur={total:.3f}[vo];"
            mixin, nmix = "[vo]", 1
            isfx = mi
        for k, (snd, t0, vol) in enumerate(sfx):
            inputs += ["-i", snd]
            ms = int(t0 * 1000)
            fl += f"[{isfx + k}:a]volume={vol},adelay={ms}|{ms}[sfx{k}];"
            mixin += f"[sfx{k}]"
        # PAS DE loudnorm ICI. Deux degats, mesures le 2026-10-03 sur assiette-temoin et fondateur-ecoeure :
        #  - son tampon d'analyse avale ~3 s : la piste finale ne contenait que 17,4 s de son pour 20,4 s d'image,
        #    la voix off finissait 3 s avant la fin et tout le montage paraissait decale ;
        #  - il sort en 192 kHz, ffmpeg rebascule en 96 kHz pour l'AAC et les paquets restent espaces a 81 920 Hz.
        # loud_fix() fait deja le -14 LUFS en mesurant puis en appliquant un gain fixe, sans toucher a la duree.
        fl += (f"{mixin}amix=inputs={nmix + len(sfx)}:duration=first:normalize=0,aresample=44100[a]"
               if nmix + len(sfx) > 1 else f"{mixin}aresample=44100[a]")
        ff(*inputs, "-filter_complex", fl, "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-crf", "19", "-preset", "medium",
           "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-t", f"{total:.3f}", "-movflags", "+faststart", out)
        return self.loud_fix(out), total

    @staticmethod
    def loud_fix(path):
        meas = lambda: float(re.findall(r"I:\s+(-?[0-9.]+) LUFS", subprocess.run([autoad.FFMPEG, "-hide_banner", "-i", str(path), "-vn", "-af",
                                         "ebur128", "-f", "null", "-"], capture_output=True, text=True).stderr)[-1])
        i = meas()
        for _ in range(3):
            if abs(i + 14) <= 0.4:
                break
            tmp = Path(path).with_suffix(".tmp.mp4")
            ff("-i", path, "-c:v", "copy", "-af", f"volume={-14 - i:.2f}dB,alimiter=limit=0.95:level=false", "-c:a", "aac", "-b:a", "192k", "-ar", "44100",
               "-movflags", "+faststart", tmp)
            tmp.replace(path)
            i = meas()
        tmp = Path(path).with_suffix(".tmp.mp4")
        ff("-i", path, "-c:v", "copy", "-af", "alimiter=limit=0.89:level=false", "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-movflags", "+faststart", tmp)
        tmp.replace(path)
        return meas()

    def zones(self, ids, out, ys=(0.14, 0.30, 0.42, 0.56, 0.70, 0.82), cols=12, w=270):
        """Planche de choix du ypos : 2 images par plan (20 % / 80 %, segments/<id>.mp4 deja rendus) avec la bande que
        chaque caption occuperait a chaque ypos. Regle (2026-11-02) : la caption ne couvre jamais un visage, le produit,
        l'etiquette ni le sujet du plan ; on choisit le ypos plan par plan sur cette planche, AVANT le montage final."""
        from PIL import Image, ImageDraw
        h = int(w * 16 / 9)
        tiles = []
        for sid in ids:
            seg = self.seg / f"{sid}.mp4"
            for k in (0.2, 0.8):
                tmp = Path(tempfile.gettempdir()) / f"zones_{sid}_{k}.png"
                ff("-ss", f"{duration(seg) * k:.3f}", "-i", seg, "-frames:v", "1", "-vf", f"scale={w}:{h}", tmp)
                im = Image.open(tmp).convert("RGB")
                dr = ImageDraw.Draw(im, "RGBA")
                for y in ys:  # bande = encre + fond d'une caption 58 px (origine PIL a y, ~4 % de H en dessous)
                    dr.rectangle((0, y * h - 2, w, (y + 0.042) * h), fill=(0, 255, 255, 60), outline=(0, 255, 255, 255))
                    dr.text((3, y * h), f"{y:.2f}", fill=(0, 0, 0))
                dr.text((w - 40, 3), f"{sid}{'ab'[k > 0.5]}", fill=(255, 255, 0))
                tiles.append(im)
        rows = math.ceil(len(tiles) / cols)
        sh = Image.new("RGB", (cols * w, rows * h), "white")
        for i, im in enumerate(tiles):
            sh.paste(im, ((i % cols) * w, (i // cols) * h))
        sh.save(out, quality=82)
        return out

    def sheet(self, files, out, cols=6, w=240):
        """Review contact sheet of images (PNG/JPG) or the first frame of clips."""
        from PIL import Image, ImageDraw
        files = [Path(f) for f in files]
        h = int(w * 16 / 9)
        rows = math.ceil(len(files) / cols)
        im = Image.new("RGB", (cols * w, rows * (h + 18)), "white")
        dr = ImageDraw.Draw(im)
        for i, f in enumerate(files):
            if f.suffix == ".mp4":
                tmp = Path(tempfile.gettempdir()) / f"sheet_{f.stem}.jpg"
                ff("-sseof", "-0.3", "-i", f, "-frames:v", "1", tmp)
                f2 = tmp
            else:
                f2 = f
            th = Image.open(f2).convert("RGB").resize((w, h))
            x, y = (i % cols) * w, (i // cols) * (h + 18)
            im.paste(th, (x, y + 18))
            dr.text((x + 3, y + 2), f.stem, fill="black")
        im.save(out, quality=85)
        return out


# 2026-10-26, lot E, 3 videos sur 10 : une constante d'IDENTITE (W_ID, MEME, maitresse) qui porte un etat
# (« hollow cheeks », « NOT a slimmer-faced woman ») empeche l'« apres » de se lire. Tout runner avant/apres appelle
# verifier_identite(W_ID, MEME, ...) ; l'etat vient d'une constante AVANT/APRES separee.
ETAT = re.compile(r"hollow|gaunt|sunken|full(?:er)? cheeks|plump|dark circles|eye bags|slimm?(?:er)?|thin(?:ner)?"
                  r"|deflated|sagging|flat (?:butt|bottom)|round(?:ed)? (?:butt|bottom)", re.I)


def verifier_identite(*constantes):
    for c in constantes:
        m = ETAT.search(c)
        assert not m, f"constante d'identite avec un mot d'etat ({m.group(0)!r}) : le sortir dans AVANT/APRES"
