"""QC mecanique d'une video livrable. A LANCER SUR CHAQUE FICHIER AVANT DE LE LIVRER, sans exception.

    python3 qc.py <projet>/ <video.mp4> [<projet>/ <video.mp4> ...]

Verifie ce qu'un oeil ne voit pas et ce qu'un rapport d'agent ne prouve pas :
  1. integrite du conteneur (ffmpeg -v error -f null)
  2. une piste audio existe, en 44,1 kHz (96 kHz = bug loudnorm, le son est joue 14% trop vite)
  3. autant d'audio DECODE que de video (le conteneur peut annoncer la bonne duree et ne rien avoir dedans)
  4. decalage voix off / montage par correlation d'enveloppe : doit etre a 0,00 s
  5. loudness a -14 LUFS +/- 0,5
  6. montage par segments (projet avec final/list.txt) : chaque segment parlant doit tomber a sa place dans la
     video finale, avec le MEME decalage partout. Un decalage qui grandit = derive son/image = lipsync faux.
     Le check 4 ne la voit pas : sa reference est extraite du montage deja derive (bug du 2026-10-07, 0,85 s).
  7. le verdict ecrit de la porte 2 (<projet>/porte2.md) existe : un lot sans controle plan par plan
     n'est pas livrable, c'est la porte qui bloque les plans qui meublent
Le QC visuel (plan par plan) reste a faire a cote, il ne remplace pas celui-la.
"""
import re, subprocess, sys
from pathlib import Path
import numpy as np
import autoad

autoad.env()
FF, FP = autoad.FFMPEG, autoad.FFPROBE


def probe(path, stream, field):
    out = subprocess.check_output([FP, "-v", "error", "-select_streams", stream, "-show_entries",
                                   f"stream={field}", "-of", "csv=p=0", str(path)], text=True).strip()
    return out.splitlines()[0] if out else ""


def pcm(path, sr=8000):
    d = subprocess.run([FF, "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(sr), "-f", "s16le", "-"],
                       capture_output=True).stdout
    return np.frombuffer(d, "<i2").astype(float)


def lag(vo, vid):
    """Decalage du montage par rapport a la voix off, en secondes. Positif = le son arrive en retard.
    On correle sur les 10 premieres secondes seulement : sur toute la longueur, le fondu de la musique
    tire le pic de correlation et sort un faux decalage de 0,3 s."""
    a, b = pcm(vo), pcm(vid)
    n = min(len(a), len(b), 10 * 8000)
    env = lambda x: np.convolve(np.abs(x), np.ones(200) / 200, "same")[::20]
    ea, eb = env(a[:n]), env(b[:n])
    ea -= ea.mean(); eb -= eb.mean()
    return (np.correlate(eb, ea, "full").argmax() - (len(ea) - 1)) * 20 / 8000, len(a) / 8000, len(b) / 8000


def lag_fenetres(vo, vid, win=10, sr=8000):
    """Decalage voix / montage mesure par FENETRES de `win` s sur TOUT le fichier (pas seulement les 10 premieres
    secondes). Une derive son/image qui grandit (concat AAC -c copy : +28 ms par segment, lotb-06 2026-10-21, +1,95 s en
    fin de video) est invisible dans la 1re fenetre et saute aux yeux dans la derniere. Renvoie [(t, decalage_s)]."""
    a, b = pcm(vo, sr), pcm(vid, sr)
    env = lambda x: np.convolve(np.abs(x), np.ones(200) / 200, "same")[::20]
    out, n = [], min(len(a), len(b))
    for i in range(0, n - win * sr + 1, win * sr):
        ea, eb = env(a[i:i + win * sr]), env(b[i:i + win * sr])
        if ea.std() < 1e-6 or eb.std() < 1e-6:
            continue
        ea = ea - ea.mean(); eb = eb - eb.mean()
        # fenetre +-1 s autour de la position attendue : on cherche un decalage, pas une autre phrase
        c = np.correlate(eb, ea, "full")
        mid = len(ea) - 1
        k = int(1.0 * sr / 20)
        j = mid - k + int(np.argmax(c[mid - k: mid + k + 1]))
        out.append((i / sr, (j - mid) * 20 / sr))
    return out


def figes(vid, fps=4, span=2.5, frac=0.2):
    """(debut, fin) des passages ou moins de `frac` des pixels changent en `span` s (image 90x160 en gris)."""
    import numpy as np
    w, h = 90, 160
    raw = subprocess.run([FF, "-v", "error", "-i", str(vid), "-vf", f"fps={fps},scale={w}:{h},format=gray",
                          "-f", "rawvideo", "-"], capture_output=True).stdout
    f = np.frombuffer(raw, np.uint8).reshape(-1, h, w).astype(np.int16)
    k = int(span * fps)
    mov = [(np.abs(f[i + k] - f[i]) > 8).mean() for i in range(len(f) - k)]
    out, i = [], 0
    while i < len(mov):
        if mov[i] < frac:
            j = i
            while j + 1 < len(mov) and mov[j + 1] < frac:
                j += 1
            out.append((i / fps, (j + k) / fps))
            i = j + 1
        else:
            i += 1
    return out


def check(proj, vid):
    proj, vid = Path(proj), Path(vid)
    ok = True
    say = lambda good, msg: (print(("  ✅ " if good else "  ❌ ") + msg), good)[1]

    # 7. Porte 2 ([[trois-portes]]) : un lot sans verdict ecrit du controleur n'est PAS livrable. Kevin,
    # 2026-10-16 : « les shots ont encore une fois aucune vraie signification ils font que meubler ».
    # La porte 2 est exactement la qui bloque « plan sans objet concret ». Je l'avais sautee sur
    # lot-gym-belly, et la regle en prose n'a pas tenu -- donc elle devient un check.
    # Le fichier ne suffit pas : ua02-ref3 (2026-10-20) affichait « livrable » avec un porte2.md qui
    # disait ⛔ NE PAS CONTINUER. On lit le DERNIER verdict ecrit (les passes s'empilent dans le fichier).
    p2 = proj / "porte2.md"
    verdicts = re.findall(r"NE PAS CONTINUER|FEU VERT|animation autoris", p2.read_text(), re.I) if p2.exists() else []
    vert = bool(verdicts) and not verdicts[-1].upper().startswith("NE PAS")
    ok &= say(vert, f"verdict porte 2 : {proj.name}/porte2.md"
              + ("" if vert else "  <- ABSENT, faire passer le controleur-video" if not p2.exists()
                 else "  <- dernier verdict ⛔ (ou illisible) : reprendre les frames bloquees"))

    err = subprocess.run([FF, "-v", "error", "-i", str(vid), "-f", "null", "-"], capture_output=True, text=True).stderr
    ok &= say(not err.strip(), f"integrite : {err.strip()[:120] or 'aucune erreur de decodage'}")

    sr = probe(vid, "a", "sample_rate")
    ok &= say(sr == "44100", f"piste audio en {sr or 'AUCUNE'} Hz" + ("" if sr == "44100" else "  <- loudnorm non resample"))

    dv = float(probe(vid, "v", "duration") or 0)
    # La piste de reference depend du type de projet : vo_tight.wav quand ElevenLabs porte la voix,
    # vo_<tag>.mp3 quand ce sont les clips Kling qui la portent (vo_from_clips).
    # voix.wav = piste voix MIXTE deja montee (Omni face cam + ElevenLabs b-rolls, lot-ua-02/ref2 final.py) : c'est
    # elle que le montage porte. vo_tight.wav y reste la VO ElevenLabs SOURCE, dont on ne garde que des morceaux :
    # la comparer au montage annoncait -1,25 s sur une video calee a +0,015 s (porte 3, 2026-10-20).
    ref = proj / "voix.wav" if (proj / "voix.wav").exists() else proj / "vo_tight.wav"
    # Version ANIMEE d'une face cam (Kling 3 + voix unifiee, lot B 2026-10-21 n°6) : la voix est celle des clips montes
    # (voix_k.wav), pas la VO ElevenLabs de l'animatique (vo_tight.wav) : les comparer annoncait +0,60 s.
    if vid.stem == "anime" and (proj / "voix_k.wav").exists():
        ref = proj / "voix_k.wav"
    if not ref.exists():
        # ⚠ les _tight.wav D'ABORD. Un projet multi-variantes nomme sa voix vo_<tag>_tight.wav, donc le
        # garde-fou `vo_tight.wav` ci-dessus le rate, et le tri alphabetique mettait vo_<tag>.mp3 -- la voix
        # AVANT raccourcissement des pauses -- en tete. On comparait alors le montage a une piste qui n'a
        # jamais ete montee : -1,22 s annonces sur une pixar-hook6 mesuree a +0,02 s (2026-10-04).
        # Les projets vo_from_clips n'ont pas de _tight.wav, leur selection ne bouge pas.
        cands = sorted(proj.glob("vo*_tight.wav")) + sorted(proj.glob("vo*.mp3")) + sorted(proj.glob("vo*.wav"))
        # ⛔ Un lot AI Song n'a pas de voix off : la CHANSON porte la voix et la musique a la fois, et
        # le montage s'y ancre par whisper (lot-song-ora-01). Sans cette ligne le check 4 ne tournait
        # pas du tout, et une verification qui ne peut pas tourner est une verification absente.
        cands += sorted(proj.glob("chanson*.wav"))
        # Format MUET (text-led, musique seule, lot B 2026-10-21 n°9) : aucune voix, c'est la musique montee
        # (musique_montee.wav) qui sert de reference au decalage et a la duree.
        cands += sorted(proj.glob("musique_montee.wav"))
        if not cands:
            return say(False, f"aucune piste de voix off trouvee dans {proj}")
        # Un projet rend plusieurs variantes (vo_hook1, vo_hook5...). Prendre cands[0] comparait la
        # hook5 a la voix de la hook1 et annoncait +0,32 s de decalage sur une video saine.
        tag = vid.stem.split("-")[-1]
        ref = next((c for c in cands if tag and tag in c.stem), cands[0])
    l, dvo, da = lag(ref, vid)
    ok &= say(abs(da - dv) < 0.6, f"audio decode {da:.2f}s pour {dv:.2f}s de video")
    ok &= say(abs(l) < 0.15, f"decalage voix off / montage : {l:+.2f}s")

    # Version ANIMEE d'une face cam (voix_k.wav = la voix des clips montes). La reference n'est un VRAI controle que si
    # (a) elle dure autant que la video (±0,1 s) : un audio plus long que l'image = derive de priming AAC ou fin coupee,
    # (b) la correlation tourne sur TOUTE la duree par fenetres de 10 s (la 1re fenetre ne voit pas une derive qui grandit).
    # Avant (2026-10-21) : 10 premieres secondes seulement et reference extraite du meme montage derive = tautologie,
    # « decalage +0,01 s » annonce sur une video qui derivait de 1,95 s.
    if vid.stem == "anime" and (proj / "voix_k.wav").exists():
        dref = float(probe(ref, "a", "duration") or 0) or len(pcm(ref)) / 8000
        ok &= say(abs(dref - dv) < 0.1, f"duree voix des clips {dref:.2f}s pour {dv:.2f}s de video (±0,1 s)")
        fen = lag_fenetres(ref, vid)
        if fen:
            pire = max(fen, key=lambda f: abs(f[1]))
            ok &= say(abs(pire[1]) < 0.06, f"decalage voix / montage sur {len(fen)} fenetres de 10 s : pire {pire[1]*1000:+.0f} ms"
                      f" a {pire[0]:.0f} s (max 60 ms)")

    for seg_list in (proj / "final" / "list.txt", proj / "segments_k" / "list.txt"):
        if seg_list.exists():
            ok &= sync_segments(seg_list, vid, say)

    # Lot E 2026-10-26, 3e occurrence (01 P28/P29, 06 P08/P28, 09 P31) : plans FIGES de 3-8 s dans une animatique
    # en push-in, vus seulement a la porte 3. freezedetect ne les voit pas (les captions bougent) : on mesure la part
    # de pixels qui changent en 2,5 s. ALERTE seulement (un push-in lent sur une macro sombre peut sortir ici) :
    # la porte 3 regarde ces timecodes en premier.
    fig = figes(vid)
    print(("  ⚠ " if fig else "  ✅ ") + "plans figes >= 2,5 s : "
          + (", ".join(f"{a:.1f}-{b:.1f}s" for a, b in fig) + "  <- a regarder" if fig else "aucun"))

    i = float(subprocess.run([FF, "-hide_banner", "-i", str(vid), "-vn", "-af", "ebur128", "-f", "null", "-"],
                             capture_output=True, text=True).stderr.rsplit("I:", 1)[1].split("LUFS")[0])
    ok &= say(abs(i + 14) < 0.7, f"loudness {i:.1f} LUFS")
    return ok


def sync_segments(seg_list, vid, say, sr=16000):
    """Position attendue de chaque segment = somme des images des segments precedents / 30. On correle les
    3 premieres secondes du son du segment avec le son final autour de cette position. Ecart max - min < 40 ms."""
    segs = [Path(l.split("'")[1]) for l in seg_list.read_text().splitlines() if l.startswith("file")]
    X, t, lags = pcm(vid, sr), 0.0, []
    for s in segs:
        n = int(subprocess.check_output([FP, "-v", "error", "-select_streams", "v", "-count_frames", "-show_entries",
                                         "stream=nb_read_frames", "-of", "csv=p=0", str(s)], text=True)) / 30
        ref = pcm(s, sr)[: 3 * sr]
        if len(ref) > sr and np.abs(ref).mean() > 200:  # segment avec du son (pas l'end card muette)
            i0 = max(0, int((t - 1) * sr)); x = X[i0: i0 + int((n + 2) * sr)]
            if len(x) > len(ref):
                m = len(x) + len(ref)
                c = np.fft.irfft(np.fft.rfft(x, m) * np.conj(np.fft.rfft(ref, m)), m)[: len(x) - len(ref) + 1]
                lags.append(np.argmax(c) / sr - (t - i0 / sr))
        t += n
    if not lags:
        return True
    spread = max(lags) - min(lags)
    return say(spread < 0.04, f"synchro {len(lags)} segments : decalage {min(lags)*1000:+.0f} a {max(lags)*1000:+.0f} ms "
                              f"(ecart {spread*1000:.0f} ms, max 40)")


if __name__ == "__main__":
    args = sys.argv[1:]
    bad = [v for p, v in zip(args[::2], args[1::2]) if (print(f"\n=== {Path(v).name}"), not check(p, v))[1]]
    print("\n" + ("⛔ A NE PAS LIVRER : " + ", ".join(Path(b).name for b in bad) if bad else "✅ tout est livrable"))
    sys.exit(1 if bad else 0)
