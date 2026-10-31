# CLAUDE.md — Recorte

Project memory for Claude Code. Read this before every task. `PROMPT.md` holds the full build spec; this file holds the rules that must survive the whole session.

## What this is

A one-day hackathon prototype (Media Party Buenos Aires, Sat Oct 31 2026, demo ~18:00 ART). An agent that turns long newsroom video into vertical clips, with an integrity check on every candidate, a mandatory editor approval before render, and a provenance manifest plus end card on every clip. Spanish-first.

Judging criteria, in order of what we must prove: traceability and human judgment, technical quality of the agent architecture, narrative innovation, commercial viability. The demo script in `PROMPT.md` section 2 is the definition of done.

Hackathon rules we must respect: everything built today from scratch; open-source libraries and public APIs are fine; respect their licenses. License for this repo: MIT. Do not copy code from Overlap or any other product.

## Product rules (enforce in code, never relax for convenience)

1. No render without an explicit approval event on the moment. Render endpoint returns 409 otherwise.
2. Cuts snap to utterance boundaries. Never mid-sentence.
3. Every moment has an integrity score and typed flags with verbatim evidence and a timestamp.
4. Quotes are verbatim substrings of the transcript. Validate in code; reject the moment if not.
5. Every clip has a manifest (with SHA-256 of source and clip) and an end card with source, span, approver and QR to `/v/{clip_id}`.
6. UI strings live in `frontend/src/strings.ts`, Spanish default, English toggle.

## Stack

- Backend: Python 3.11+, FastAPI, Pydantic v2, uvicorn, SQLModel on SQLite (or JSON files), BackgroundTasks for jobs. `yt-dlp`, system `ffmpeg`/`ffprobe`, `deepgram-sdk`, `anthropic`, `Pillow`, `qrcode`.
- Models: `claude-sonnet-5-5` for moment finding and chat; `claude-haiku-5-5` for integrity checks. ASR: Deepgram `nova-3` with `language="es"` (fallback `nova-2`), then AssemblyAI, then OpenAI `whisper-1`.
- Frontend: Vite, React 18, TypeScript, Tailwind. HTML5 video. shadcn/ui allowed if it saves time.
- No auth, no multi-tenancy, no Docker, no cloud. Localhost. ngrok optional for the QR.

## Repo layout (see PROMPT.md section 5 for the full tree)

- `backend/app/pipeline/` one module per step: ingest, transcribe, compact, moments, integrity, snap, captions, render, endcard, manifest, agent.
- `backend/app/prompts/` prompt files as Markdown; load them at runtime, do not inline prompts in Python.
- `backend/app/routers/` sources, moments, clips, chat, verify.
- `backend/scripts/` `run_pipeline.py`, `make_fixtures.py`, `smoke.sh`.
- `backend/fixtures/demo/` cached demo source, transcript, moments, pre-rendered clip. Committed (video via git-lfs or gitignored with a download step, your call, note it in README).
- `backend/data/` runtime artifacts, gitignored.
- `frontend/src/` pages `Home`, `Workspace`, `Export`; components `VideoPlayer`, `Timeline`, `MomentCard`, `ReviewDrawer`, `AgentChat`, `ProvenanceCard`, `IntegrityBadge`.

## Commands

```
make setup      # python venv + pip install -r backend/requirements.txt; cd frontend && npm install
make dev        # backend :8000 (uvicorn --reload) + frontend :5173 (vite, proxy /api and /data to :8000)
make fixtures   # python -m scripts.make_fixtures $DEMO_URL  → backend/fixtures/demo/
make smoke      # backend/scripts/smoke.sh — pipeline on fixture + API assertions
make clip MOMENT=<id>   # approve + render a moment from the CLI
```

Backend runs from `backend/`: `uvicorn app.main:app --reload --port 8000`. Frontend from `frontend/`: `npm run dev`.

## Environment

`.env` (gitignored) at repo root, loaded by `backend/app/config.py`. `.env.example` lists every variable:

```
ANTHROPIC_API_KEY=
DEEPGRAM_API_KEY=
ASSEMBLYAI_API_KEY=        # optional fallback
OPENAI_API_KEY=            # optional fallback
PUBLIC_BASE_URL=http://localhost:8000
DEMO_MODE=0
DEMO_URL=                  # YouTube URL used by make fixtures
EDITOR_DEFAULT_NAME=editor@demo
```

Never print or commit keys. If a key is missing, degrade (fixtures, cached results) and log a warning; never crash the demo path.

## Conventions

Python
- Type hints everywhere, Pydantic models for all API payloads and files on disk.
- Pipeline steps are functions `step(source_id) -> Model` that read and write under `data/sources/{id}/`; each step is idempotent and skips work if its output file exists (pass `force=True` to redo).
- External calls go through thin wrappers in the step module; log `{step, duration_ms, model, est_cost_usd}` to `data/logs.jsonl`.
- Errors: raise `PipelineError(step, message)`; the job runner catches it, sets `status="error"`, stores the message on the Source.
- Timestamps are floats in seconds; format for display only in the frontend.
- `ruff` clean. No tests beyond `smoke.sh`.

TypeScript
- `strict: true`, functional components, hooks in `src/hooks/`. API client in `src/api.ts` with typed responses mirroring the Pydantic models (hand-written types are fine).
- Polling hook `useJob` at 1.5 s. No global state library; lift state to `Workspace`.
- All user-visible text through `t("key")` from `strings.ts`.
- Tailwind only; design tokens in `tailwind.config` (paper `#F7F5F0`, ink `#1B1B1B`, teal `#0F6E56`, amber, red). Serif headlines (Newsreader), Inter body. No gradients, no neon.

Naming
- IDs: `src_xxxx`, `m_xxxx`, `c_xxxx` (8 hex chars).
- Moment status: `candidate | approved | rejected`. Source status: `queued | downloading | transcribing | finding_moments | ready | error`. Clip status: `rendering | ready | error`. Keep these literal strings identical in Python and TS.

## Working style for this session

- Vertical slice first. Phase order and timeboxes are in `PROMPT.md` section 12; do not skip ahead.
- Keep the happy path green. If a change breaks `make smoke`, revert before continuing.
- Blocked > 15 min on a dependency: stub it behind a small interface (e.g. `Transcriber` protocol with `DeepgramTranscriber` and `FixtureTranscriber`) and move on. Note it in `README.md` under "Decisions".
- Commit at every phase boundary with the phase name. Small commits in between are fine.
- Report at phase boundaries in ≤ 6 lines: works / stubbed / next. Ask the team only when a decision changes what the demo shows. Otherwise decide, and record the decision in README.
- Prefer boring libraries already in `requirements.txt` / `package.json`. No new frameworks mid-build.
- Do not add features not in `PROMPT.md` without being asked. Face-aware crop and key-frame vision are stretch items, last.

## Do not

- Do not render or publish anything for an unapproved moment.
- Do not paraphrase transcript text into the `quote` field.
- Do not use `-c copy` for ffmpeg cuts (inaccurate); re-encode.
- Do not block the event loop with ffmpeg or network calls inside request handlers; use BackgroundTasks or `run_in_executor`.
- Do not put prompts inline in Python; keep them in `app/prompts/*.md`.
- Do not hardcode `localhost` in the frontend; use the Vite proxy and relative `/api`, `/data` paths.
- Do not spend time on auth, deployment, tests, or mobile layout.

## Demo checklist (run before 17:45)

- `DEMO_MODE=1 make dev` boots with no network and the demo source loads from fixtures.
- Approve → clip renders with captions and end card; `/v/{clip_id}` opens from the QR.
- Agent chat answers one Spanish query from `fixtures/demo/chat.json` when offline.
- `fixtures/demo/backup.mp4` screen recording exists.
- README has: one-paragraph pitch, the four judging criteria mapped to features, how to run, decisions, cost per clip from `logs.jsonl`.
