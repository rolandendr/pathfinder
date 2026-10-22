# Pathfinder

**Show it the task. It tells you which open model on Fireworks AI to run it on, and why.**

Pathfinder is a prototype built for a Fireworks AI interview prompt: *it is hard for companies to move from closed models (GPT, Claude, Gemini) to open models on Fireworks.* The difficulty it targets is **choosing**. Dozens of models trade off cost, speed, accuracy and modality, and many of the people automating work today are not programmers and could not describe their task to a model-selection guide even if they read one.

So instead of describing the task, you **show it**. You record yourself doing it the way you normally do — narrating as you go — and Pathfinder works out what the task is, asks you a few multiple-choice questions where it is unsure, and recommends a model, with a comparison of the alternatives and an estimated monthly cost. Then you can ask it questions or push back.

## How it works

| Step | What happens | Model |
|---|---|---|
| Record | Pathfinder drives OBS (screen + microphone), max 5 minutes | — |
| Transcribe | The narration is transcribed | Gemini 3.5 Flash-Lite via OpenRouter (the only non-Fireworks call: Fireworks has no serverless speech-to-text) |
| Extract | Transcript + a screenshot every 5 s become a structured task description | DeepSeek V4.1 Flash 1017 (Fireworks, vision) |
| Classify + ask | The task is placed in Fireworks' own categories from its [*Which model should I use?*](https://docs.fireworks.ai/guides/recommended-models) guide; up to 2 rounds of multiple-choice questions | DeepSeek V4.1 Flash 1017 |
| Research | A curated shortlist of 8 serverless models (`catalog.json`) is checked against Fireworks' live model list | — |
| Write | One recommendation, a comparison table (fit, speed, est. cost per run and per month, context), trade-offs, how to switch | Kimi K3 |
| Verify | A different model family checks models, prices, arithmetic and context limits; one rewrite, then a visible warning | Qwen 3.8 Max |
| Chat | Follow-up questions; a change in priorities re-runs the recommendation | Kimi K3 |

Pathfinder right-sizes its own models: cheap and fast for routine steps, strong for the answer, an independent family to check it. A whole run typically costs a few US cents to a few tens of cents; the page shows the running cost.

## Setup (Ubuntu 24.04+, tested on 26.04 / GNOME Wayland)

1. Install OBS and ffmpeg: `sudo apt install obs-studio ffmpeg python3-venv`
2. Open OBS once and make a scene with **Screen Capture (PipeWire)** and **Audio Input Capture** (your microphone). Pick your screen when asked.
3. In OBS: **Tools → WebSocket Server Settings** → tick *Enable WebSocket server*, note the port (4455) and password. Close OBS.
4. Get the code and its one dependency:
   ```
   git clone https://github.com/rolandendr/pathfinder && cd pathfinder
   python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
   printf 'OBS_PORT=4455\nOBS_PASSWORD=your-obs-websocket-password\n' > .env
   ```
5. Run it: `.venv/bin/python app.py`, then open http://localhost:8765

You need a **Fireworks API key** and an **OpenRouter API key**. Paste them on the first screen, or put them in `.env` once (`FIREWORKS_API_KEY=…` and `OPENROUTER_API_KEY=…`) and leave the boxes blank. Pathfinder never writes them into a run.

If a step fails (a rejected key, a network error), the recording is kept: open `http://localhost:8765/?run=<run id>` to submit it again.

## Using it

Fill in a title and a short description, press **Record**, do the task while describing it out loud, come back and press **Stop**, then **Submit task**. Answer any questions (recommended answer first; "Other" for your own words). Read the recommendation, ask follow-ups in the chat, or press **Demonstrate a new process**.

Each run is saved under `runs/<timestamp>/` — the recording, transcript, screenshots, structured task, questions and answers, recommendation, chat, and a log of every model call with its token count and cost. `runs/` is not in git.

## Files

```
app.py          local web server and run storage
pipeline.py     extract -> classify/ask -> research -> write -> verify, and chat
llm.py          Fireworks / OpenRouter calls, recording -> audio + screenshots
recorder.py     OBS control over its WebSocket
static/index.html   the page
prompts/*.md    the instructions each step follows
catalog.json    Fireworks categories, candidate models, prices, and which model each step uses
```

Code is kept under 500 lines (Python + HTML + JS); prompts and the catalog are data.

## Limits and what comes next

- One short, discrete task at a time; multi-step workflows and system design advice are the next step.
- Speeds in the catalog are relative (from model class), not measured; prices are Fireworks' published serverless rates, read October 2026.
- With enough runs, real tasks and outcomes could feed a self-improvement loop for the recommendations.
- Fireworks' Nexus Auto router is deliberately not recommended: Pathfinder names specific models, for predictable cost and quality on one job.

Comments to ajb@andrewbenard.com.
