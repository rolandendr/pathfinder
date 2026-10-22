"""The Pathfinder pipeline: extract -> classify/question -> research -> write -> verify, plus chat."""
import json, time
from pathlib import Path
import llm

HERE = Path(__file__).parent
CATALOG = json.loads((HERE / "catalog.json").read_text())
MODELS = CATALOG["pathfinder_models"]
MAX_ROUNDS = 2


def prompt(name):
    return (HERE / "prompts" / f"{name}.md").read_text()


def call(run, step, keys, messages, json_mode=False):
    """One model call for one pipeline step; logs tokens and cost into the run."""
    m = MODELS[step]
    openrouter = m.get("via") == "openrouter"
    text, usage = llm.chat(keys["openrouter" if openrouter else "fireworks"], m["id"], messages,
                           base=llm.OPENROUTER if openrouter else llm.FIREWORKS, json_mode=json_mode,
                           effort=m.get("effort"))
    usd = (usage.get("prompt_tokens", 0) * m["in"] + usage.get("completion_tokens", 0) * m["out"]) / 1e6
    run["log"].append({"step": step, "model": m["id"], "usage": usage, "usd": round(usd, 5),
                       "at": time.strftime("%H:%M:%S")})
    return llm.parse_json(text) if json_mode else text.strip()


def ask(run, step, keys, user, json_mode=False):
    return call(run, step, keys, [{"role": "system", "content": prompt(step)},
                                  {"role": "user", "content": user}], json_mode)


def analyze(run, keys, folder):
    """Recording -> transcript (OpenRouter) -> structured task (Fireworks vision) -> classify."""
    run["qa"], run["chat"] = [], []  # a re-submitted recording starts its questions afresh
    seconds, frames = llm.prepare(run["video"], folder)
    run["transcript"] = call(run, "transcribe", keys, [{"role": "user", "content": [
        {"type": "text", "text": f"{prompt('transcribe')}\nContext, for spelling names: {run['title']}. "
         f"{run['description']}"}, llm.audio_part(folder / "audio.mp3")]}])
    parts = [{"type": "text", "text": f"{prompt('extract')}\n\nTITLE: {run['title']}\nDESCRIPTION: "
              f"{run['description']}\nRECORDING LENGTH: {seconds:.0f}s\nNARRATION TRANSCRIPT:\n{run['transcript']}"}]
    for t, f in frames:
        parts += [{"type": "text", "text": f"Screenshot at {t // 60}:{t % 60:02d}"}, llm.image_part(f)]
    run["task"] = call(run, "extract", keys, [{"role": "user", "content": parts}], json_mode=True)
    return classify(run, keys)


def classify(run, keys, answers=None):
    """Classify against Fireworks' categories; ask questions until confident or out of rounds."""
    if answers:
        run["qa"].append(answers)
    c = ask(run, "classify", keys, json.dumps({
        "task": run["task"], "categories": CATALOG["categories"], "latency_budget": CATALOG["latency_budget"],
        "answers_so_far": run["qa"], "rounds_left": MAX_ROUNDS - len(run["qa"])}, indent=1), json_mode=True)
    run["classification"] = c
    if c.get("questions") and len(run["qa"]) < MAX_ROUNDS:
        return {"stage": "questions", "summary": c.get("summary"), "questions": c["questions"][:4]}
    return recommend(run, keys)


def recommend(run, keys):
    """Research (catalog checked against the live model list) -> write -> verify, one retry."""
    live = llm.live_models(keys["fireworks"])
    brief = json.dumps({
        "task": run["task"], "classification": run["classification"], "answers": run["qa"],
        "candidates": [c for c in CATALOG["candidates"] if c["id"] in live],
        "closed_to_open": CATALOG["closed_to_open"], "follow_up_chat": run["chat"]}, indent=1)
    text = ask(run, "write", keys, brief)
    for attempt in (1, 2):
        verdict = ask(run, "verify", keys, f"{brief}\n\nRECOMMENDATION TO CHECK:\n{text}", json_mode=True)
        if verdict.get("ok") or attempt == 2:
            break
        text = ask(run, "write", keys, f"{brief}\n\nA REVIEWER REJECTED YOUR PREVIOUS DRAFT FOR THESE "
                   f"REASONS - FIX THEM:\n{json.dumps(verdict.get('problems'))}\n\nPREVIOUS DRAFT:\n{text}")
    run["recommendation"], run["verdict"] = text, verdict
    return {"stage": "result", "summary": run["classification"].get("summary"), "markdown": text,
            "warning": None if verdict.get("ok") else verdict.get("problems")}


def chat(run, keys, message):
    """Follow-up questions; a change in requirements re-runs the recommendation."""
    run["chat"].append({"role": "user", "content": message})
    context = json.dumps({"task": run["task"], "classification": run["classification"], "answers": run["qa"],
                          "candidates": CATALOG["candidates"], "recommendation": run.get("recommendation")})
    reply = call(run, "chat", keys, [{"role": "system", "content": f"{prompt('chat')}\n\nCONTEXT:\n{context}"},
                                     *run["chat"]])
    revise = reply.startswith("REVISE")
    reply = reply.removeprefix("REVISE").strip()
    run["chat"].append({"role": "assistant", "content": reply})
    return {**(recommend(run, keys) if revise else {"stage": "chat"}), "reply": reply}
