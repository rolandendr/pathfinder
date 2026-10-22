"""Pathfinder - a local web app. Run `python3 app.py`, then open http://localhost:8765"""
import json, os, re, shutil, time, traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).parent
for line in (HERE / ".env").read_text().splitlines() if (HERE / ".env").exists() else []:
    k, _, v = line.partition("=")
    os.environ.setdefault(k.strip(), v.strip())
import pipeline, recorder  # noqa: E402  (after .env, so OBS settings are visible)

RUNS = Path(os.environ.get("PATHFINDER_RUNS", HERE / "runs"))


def load(run_id):
    if not re.fullmatch(r"[0-9-]+", run_id):
        raise ValueError("bad run id")
    return json.loads((RUNS / run_id / "state.json").read_text())


def save(run):  # API keys are never part of `run`, so they never reach disk
    (RUNS / run["id"] / "state.json").write_text(json.dumps(run, indent=1))


def start(body):
    run_id = time.strftime("%Y%m%d-%H%M%S")
    (RUNS / run_id).mkdir(parents=True, exist_ok=True)
    run = {"id": run_id, "title": body["title"], "description": body["description"],
           "log": [], "qa": [], "chat": []}
    recorder.start()
    save(run)
    return run


def stop(run, body):
    src = recorder.stop()
    dst = RUNS / run["id"] / f"recording{src.suffix}"
    shutil.move(src, dst)
    run["video"] = str(dst)
    return {"stage": "recorded"}


def rerecord(run, body):
    Path(run.pop("video", "")).unlink(missing_ok=True)
    recorder.start()
    return {"stage": "recording"}


ACTIONS = {
    "stop": stop, "rerecord": rerecord,
    "submit": lambda run, b: pipeline.analyze(run, b["keys"], RUNS / run["id"]),
    "answer": lambda run, b: pipeline.classify(run, b["keys"], b["answers"]),
    "chat": lambda run, b: pipeline.chat(run, b["keys"], b["message"]),
}


class Handler(BaseHTTPRequestHandler):
    def reply(self, code, body, kind="application/json"):
        self.send_response(code)
        self.send_header("Content-Type", kind)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self.reply(200, (HERE / "static" / "index.html").read_bytes(), "text/html; charset=utf-8")

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        name = self.path.rsplit("/", 1)[-1]
        try:
            if name == "start":
                run, out = start(body), {"stage": "recording"}
            else:
                run = load(body["run"])
                out = ACTIONS[name](run, body)
                save(run)
            out.update(run=run["id"], cost=sum(s["usd"] for s in run["log"]))
            self.reply(200, json.dumps(out).encode())
        except Exception as e:
            traceback.print_exc()
            self.reply(500, json.dumps({"error": f"{type(e).__name__}: {e}"}).encode())

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    port = int(os.environ.get("PATHFINDER_PORT", 8765))
    print(f"Pathfinder running: open http://localhost:{port}")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
