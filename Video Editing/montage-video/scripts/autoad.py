#!/usr/bin/env python3
"""Auto ad: spec JSON -> first frames (kie) -> clips (kie) -> voice over (ElevenLabs) -> montage (ffmpeg).

Usage: python3 autoad.py spec.json            (outputs in ./out/<name>/)
Each step is skipped if its file already exists, so a rerun never re-spends credits.
Delete a file in out/<name>/ to regenerate just that piece.
"""
import base64, json, mimetypes, os, re, ssl, subprocess, sys, time, urllib.request, urllib.error
from pathlib import Path

BRAIN_ENV = Path(__file__).resolve().parents[2] / "Claude brain" / ".env"
KIE = "https://api.kie.ai/api/v1"
KIE_UPLOAD = "https://kieai.redpandaai.co/api/file-base64-upload"
# python.org builds ship without CA certs on macOS: use the system bundle
CTX = ssl.create_default_context(cafile="/etc/ssl/cert.pem" if Path("/etc/ssl/cert.pem").exists() else None)
# Kevin's rules (2026-10-01), see Claude brain/knowledge/auto-video-editing/modeles-et-couts.md.
# Ids confirmed on kie 2026-10-01; input field names per model still to check on the first run.
# Always max 1k / 720p, and no audio track in the clip unless the scene needs it.
MODELS = {
    "realiste": {"image": "gpt-image-2-5-flare-image-to-image", "video": "bytedance/seedance-2-5"},  # AI UGC, realistic b-roll (Seedance 2.5 = 63 cr/s at 720p, use sparingly)
    "anime":    {"image": "nano-banana-2", "video": "grok-imagine-video-1-5-preview"},               # animated / cartoon (Grok always adds audio, stripped at montage)
    "static":   {"image": "gpt-image-2-5-flare-image-to-image", "video": "bytedance/seedance-2-mini"}, # near-static b-roll, cheapest decent model
}
# ffmpeg-full (libass + freetype) for captions; falls back to whatever ffmpeg is on PATH
_FULL = Path("/opt/homebrew/opt/ffmpeg-full/bin")
FFMPEG = str(_FULL / "ffmpeg") if (_FULL / "ffmpeg").exists() else "ffmpeg"
FFPROBE = str(_FULL / "ffprobe") if (_FULL / "ffprobe").exists() else "ffprobe"
SIZES = {"9:16": (1080, 1920), "4:5": (1080, 1350), "1:1": (1080, 1080), "16:9": (1920, 1080)}


def env():
    for line in BRAIN_ENV.read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip("'\""))


def http(url, body=None, headers=None, raw=False):
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=120, context=CTX) as r:
            data = r.read()
    except urllib.error.HTTPError as e:
        sys.exit(f"HTTP {e.code} on {url}: {e.read()[:300]!r}")
    return data if raw else json.loads(data)


def kie_auth():
    return {"Authorization": f"Bearer {os.environ['KIE_API_KEY']}"}


def upload(path):
    mime = mimetypes.guess_type(path)[0] or "image/png"
    b64 = base64.b64encode(Path(path).read_bytes()).decode()
    r = http(KIE_UPLOAD, {"base64Data": f"data:{mime};base64,{b64}", "uploadPath": "autoad"}, kie_auth())
    if not r.get("success"):
        sys.exit(f"upload failed {path}: {r}")
    return r["data"].get("downloadUrl") or r["data"]["fileUrl"]


# 2026-10-09, deuxieme fois dans la journee : une commande de generation pipee dans `head` ferme stdout,
# python leve BrokenPipeError dans les threads et le run MEURT en silence -- 5 clips sur 37 jamais lances,
# sans un message d'erreur. Le progres part donc sur stderr, que `head`/`tail` ne ferment pas.
def _log(*a):
    print(*a, file=sys.stderr, flush=True)


FLOU = re.compile(r"shallow depth of field|bokeh|blurr?(?:ed|y)?\b|out of focus|soft focus|defocus", re.I)
POUCH = re.compile(r"\bpouch\b|feelora|packshot", re.I)


def kie_task(model, inp, dest):
    # Kevin 2026-10-26 : jamais de flou sur un pouch. 2e occurrence (porte 1 lot E n°09 : registre PIXAR avec
    # « shallow depth of field » sur les plans pouch) -> erreur levee avant la depense.
    p = str(inp.get("prompt", ""))
    if POUCH.search(p) and FLOU.search(p):
        raise ValueError(f"prompt avec pouch ET flou ({FLOU.search(p).group(0)!r}) : retirer la clause, "
                         f"le pouch reste net ({dest})")
    r = http(f"{KIE}/jobs/createTask", {"model": model, "input": inp}, kie_auth())
    if r.get("code") != 200:
        sys.exit(f"kie createTask {model}: {r}")
    tid, wait, t0 = r["data"]["taskId"], 3, time.time()
    _log(f"  kie {model} task {tid}")
    while time.time() - t0 < 15 * 60:
        time.sleep(wait)
        d = http(f"{KIE}/jobs/recordInfo?taskId={tid}", headers=kie_auth())["data"]
        if d["state"] == "success":
            url = json.loads(d["resultJson"])["resultUrls"][0]
            Path(dest).write_bytes(http(url, raw=True, headers={"Content-Type": ""}))
            _log(f"  -> {dest} ({d.get('creditsConsumed')} credits)")
            return url
        if d["state"] == "fail":
            sys.exit(f"kie {model} failed: {d.get('failCode')} {d.get('failMsg')}")
        wait = min(wait * 1.5, 20)
    sys.exit(f"kie {model} timeout, task {tid} (check kie.ai/logs)")


def tts(text, voice, dest, model="eleven_v4"):
    audio = http(f"https://api.elevenlabs.io/v1/text-to-speech/{voice}?output_format=mp3_44100_128",
                 {"text": text, "model_id": model}, {"xi-api-key": os.environ["ELEVENLABS_API_KEY"]}, raw=True)
    Path(dest).write_bytes(audio)
    print(f"  -> {dest}")


def dur(path):
    return float(subprocess.check_output([FFPROBE, "-v", "error", "-show_entries", "format=duration",
                                          "-of", "csv=p=0", str(path)]).strip())


def main(spec_path):
    env()
    spec = json.loads(Path(spec_path).read_text())
    base = Path(spec_path).resolve().parent
    out = Path(__file__).resolve().parent / "out" / spec["name"]
    out.mkdir(parents=True, exist_ok=True)
    W, H = SIZES[spec.get("ratio", "9:16")]
    ref_urls = {}

    clips = []
    for i, sc in enumerate(spec["scenes"], 1):
        print(f"scene {i}")
        kind = MODELS[sc.get("type", spec.get("type", "realiste"))]
        img_model = sc.get("image_model", spec.get("image_model", kind["image"]))
        vid_model = sc.get("video_model", spec.get("video_model", kind["video"]))  # null = still + slow zoom
        frame = out / f"frame_{i}.png"
        if sc.get("image"):  # bring your own first frame
            frame = (base / sc["image"]).resolve()
        elif not frame.exists():
            refs = [ref_urls.setdefault(p, upload(base / p)) for p in sc.get("refs", spec.get("refs", []))]
            ratio = spec.get("ratio", "9:16")
            model = img_model
            if img_model.startswith("nano-banana-2"):
                inp = {"prompt": sc["image_prompt"], "aspect_ratio": ratio, "resolution": "1K", "output_format": "png"}
                if refs:
                    inp["image_input"] = refs
            elif img_model.startswith("gpt-image-2"):
                if not refs:
                    model = img_model.replace("image-to-image", "text-to-image")
                inp = {"prompt": sc["image_prompt"], "aspect_ratio": ratio, "resolution": "1K"}
                if refs:
                    inp["input_urls"] = refs
            else:  # google/nano-banana(-edit) style
                inp = {"prompt": sc["image_prompt"], "output_format": "png", "image_size": ratio}
                if refs:
                    inp["image_urls"] = refs
                else:
                    model = img_model.replace("-edit", "")
            kie_task(model, {**inp, **spec.get("image_input", {})}, frame)

        clip = out / f"clip_{i}.mp4"
        seconds = str(sc.get("duration", "5"))
        if not clip.exists():
            if vid_model:
                url = upload(frame)
                inp = {"prompt": sc.get("video_prompt", sc.get("image_prompt", "")), "duration": seconds}
                if vid_model.startswith(("wan/", "grok-imagine")):
                    inp["image_urls"] = [url]
                    inp["resolution"] = "720p"  # Kevin's rule: never above 1k
                else:
                    inp["image_url"] = url
                kie_task(vid_model, {**inp, **spec.get("video_input", {})}, clip)
            else:
                n = int(float(seconds) * 30)
                subprocess.run([FFMPEG, "-y", "-v", "error", "-loop", "1", "-i", str(frame), "-vf",
                                f"scale={W*2}:{H*2}:force_original_aspect_ratio=increase,crop={W*2}:{H*2},"
                                f"zoompan=z='1+0.0008*on':d={n}:s={W}x{H}:fps=30",
                                "-frames:v", str(n), "-pix_fmt", "yuv420p", str(clip)], check=True)
        clips.append(clip)

    vo = None
    if spec.get("voiceover"):
        vo = out / "vo.mp3"
        if not vo.exists():
            print("voice over")
            tts(spec["voiceover"], spec["voice_id"], vo, spec.get("voice_model", "eleven_v4"))

    # montage: normalise every clip, concat, lay voice over (+ optional music bed)
    final = out / f"{spec['name']}.mp4"
    cmd = [FFMPEG, "-y", "-v", "error"]
    for c in clips:
        cmd += ["-i", str(c)]
    norm = "".join(f"[{i}:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps=30,setsar=1,"
                   f"format=yuv420p[v{i}];" for i in range(len(clips)))
    graph = norm + "".join(f"[v{i}]" for i in range(len(clips))) + f"concat=n={len(clips)}:v=1:a=0[v]"
    maps = ["-map", "[v]"]
    labels, idx = [], len(clips)
    if vo:
        cmd += ["-i", str(vo)]
        labels.append(f"[{idx}:a]")
        idx += 1
    if spec.get("music"):
        cmd += ["-i", str(base / spec["music"])]
        graph += f";[{idx}:a]volume={spec.get('music_volume', 0.15)}[m]"
        labels.append("[m]")
    if labels:
        mix = "amix=inputs=2:duration=first:normalize=0," if len(labels) == 2 else ""
        # apad + -shortest: the video length always wins
        graph += f";{''.join(labels)}{mix}loudnorm=I=-14:TP=-1,apad[a]"
        maps += ["-map", "[a]", "-c:a", "aac", "-b:a", "192k", "-shortest"]
    cmd += ["-filter_complex", graph, *maps, "-c:v", "libx264", "-crf", "20", "-preset", "medium",
            "-movflags", "+faststart", str(final)]
    subprocess.run(cmd, check=True)
    vlen = sum(dur(c) for c in clips)
    if vo and dur(vo) > vlen + 0.3:
        print(f"⚠ voice over {dur(vo):.1f}s > video {vlen:.1f}s : la fin du VO est coupée, ajoute une scène ou du temps")
    print(f"✅ {final} ({dur(final):.1f}s)")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else sys.exit(__doc__))
