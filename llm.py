"""Model calls (Fireworks, plus OpenRouter for audio only) and recording prep."""
import base64, json, subprocess, urllib.error, urllib.request
from pathlib import Path

FIREWORKS = "https://api.fireworks.ai/inference/v1"
OPENROUTER = "https://openrouter.ai/api/v1"
FRAME_EVERY, MAX_FRAMES, MAX_SECONDS = 5, 20, 300


def chat(key, model, messages, base=FIREWORKS, json_mode=False, effort=None, max_tokens=16000):
    body = {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": 0.2}
    if effort:  # reasoning models otherwise can spend the whole budget thinking and answer nothing
        body["reasoning_effort"] = effort
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    req = urllib.request.Request(f"{base}/chat/completions", json.dumps(body).encode(),
                                 {"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            d = json.load(r)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{model}: HTTP {e.code} {e.read().decode()[:300]}")
    return d["choices"][0]["message"].get("content") or "", d.get("usage", {})


def parse_json(text):
    """Models sometimes wrap JSON in prose or fences; take the outermost object."""
    return json.loads(text[text.index("{"): text.rindex("}") + 1])


def live_models(key):
    req = urllib.request.Request(f"{FIREWORKS}/models", headers={"Authorization": f"Bearer {key}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return {m["id"] for m in json.load(r)["data"]}


def image_part(path):
    data = base64.b64encode(Path(path).read_bytes()).decode()
    return {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{data}"}}


def audio_part(path):
    data = base64.b64encode(Path(path).read_bytes()).decode()
    return {"type": "input_audio", "input_audio": {"data": data, "format": "mp3"}}


def prepare(video, out):
    """Split a recording into mono audio and one screenshot every FRAME_EVERY seconds."""
    seconds = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                             "-of", "csv=p=0", str(video)]).strip())
    if seconds > MAX_SECONDS:
        raise ValueError(f"Recording is {seconds/60:.1f} minutes; the demo accepts 5 minutes at most.")
    run = lambda *a: subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(video), *a], check=True)
    run("-vn", "-ac", "1", "-ar", "16000", "-b:a", "32k", str(out / "audio.mp3"))
    run("-vf", f"fps=1/{FRAME_EVERY},scale=1280:-2", str(out / "frame_%03d.jpg"))
    frames = sorted(out.glob("frame_*.jpg"))
    step = max(1, -(-len(frames) // MAX_FRAMES))  # even subsample down to MAX_FRAMES
    return seconds, [(i * FRAME_EVERY, f) for i, f in enumerate(frames)][::step]
