# PLAN — Recorte

Goal: one flawless 90 s demo (PROMPT.md §2). Vertical slice, phase by phase, `make smoke` green at each boundary.

- [x] Phase 0 — scaffold: Makefile, .env.example, .gitignore, requirements, app/{main,config,models,db}.py, Vite+React+TS+Tailwind, Inter fonts, smoke.sh, synthetic fixture (YouTube blocked in the build environment).
- [x] Phase 1 — CLI pipeline: ingest, transcribe (Deepgram → AssemblyAI → Whisper → Fixture behind a `Transcriber` protocol), compact, moments (Claude tool call or fixture), snap, captions, render. `scripts/run_pipeline.py demo --render-first`.
- [x] Phase 2 — API + Workspace: routers with BackgroundTasks + 1.5 s polling; Home, Workspace (player, timeline, cards), useJob.
- [x] Phase 3 — integrity (deterministic + Haiku, graceful fallback), ReviewDrawer (extend / ±1 utterance / approve / reject with reason), 409 on unapproved render, end card + QR, manifest with SHA-256s, `/v/{clip_id}`, Export page.
- [x] Phase 4 — chat agent with `search_transcript` / `propose_moment` tools (+ keyword fallback), ES/EN strings, J/K/E/A/Space/Esc shortcuts, editorial design.
- [x] Phase 5 — offline hardening, `chat.json`, pre-rendered fallback clip, README (pitch, criteria, run, decisions, cost), backup screen recording.

Not done (stretch): face-aware crop, key-frame vision labels.
