# Recorte

**Clips verificables para redacciones.**

Recorte convierte video largo de redacción —conferencias de prensa, entrevistas, debates— en clips 9:16 listos para publicar que un medio puede defender. Un agente transcribe la fuente con marcas de tiempo por palabra, detecta 6–10 momentos noticiosos y le asigna a cada uno un puntaje de integridad (0–100), señalando contexto recortado con evidencia textual: un condicional perdido como "si se aprueba el presupuesto", una atribución ausente, una pregunta separada de su respuesta, ironía leída en serio. Los cortes caen siempre en límites de oración y las citas se validan como texto literal de la transcripción. Nada se renderiza hasta que un editor revisa el fragmento con 20 s de contexto, lo extiende con un clic y lo aprueba: el endpoint de render rechaza lo no aprobado. Cada clip lleva subtítulos, una placa final con fuente, minuto, aprobador y QR, y un manifiesto de procedencia con hashes SHA-256 de fuente y clip, respaldado por una página pública de verificación. Un chat busca en la transcripción y propone nuevos clips. En español, offline, ~US$0,06 por clip.

---

*English:* An agent that turns long newsroom video (interviews, press conferences, debates) into publish-ready 9:16 clips where every clip is (a) checked for stripped context, (b) approved by a human editor before it renders, and (c) exported with a provenance record that travels with the clip.

> Overlap for newsrooms, with an editorial conscience. Creator clipping tools optimize for virality; Recorte optimizes for clips a newsroom can defend: no mid-sentence cuts, no missing qualifiers, mandatory editor sign-off, source and timestamp on every clip.

Built from scratch at Media Party Buenos Aires, Oct 31 2026. MIT licensed.

## How it maps to the judging criteria

| Criterion | What Recorte does |
| --- | --- |
| **Traceability & human judgment** | Every candidate carries an integrity score (0–100) and typed flags with the *verbatim* transcript evidence and timestamp that triggered them. "Extender para incluir" applies the suggested fix and re-scores. **Nothing renders without an explicit approval event** (the render endpoint returns 409 otherwise). Each clip ships with a provenance manifest (SHA-256 of source and clip, span, approver, models used, editor adjustments), a 2 s end card with source/span/approver/QR, and a public `/v/{clip_id}` verification page that needs no frontend. |
| **Agentic architecture** | Pipeline of idempotent steps: ingest → ASR (Deepgram nova-3 → nova-2 → AssemblyAI → Whisper → fixture) → moment agent (Claude Sonnet, structured tool call) → deterministic snap/clamp/dedupe + verbatim-quote validation → integrity check (deterministic rules + Claude Haiku context check) → human gate → ffmpeg render → manifest. A chat agent with tools (`search_transcript`, `propose_moment`) sits on the same transcript and creates new candidate cards. Every LLM step degrades gracefully to fixtures/deterministic checks. |
| **Narrative innovation** | The integrity flag is the story: "the cut drops the qualifier *si se aprueba el presupuesto* spoken 4 s earlier. Extend?" The editor sees the span plus 20 s of muted context with the evidence highlighted, and the quote shown is always the raw ASR text (the LLM may summarize, never quote-paraphrase; enforced in code). |
| **Commercial viability** | Cost per clip is logged (`backend/data/logs.jsonl`: step, duration, model, estimated USD). Archive search via chat is the expansion path: the same transcript index answers "every time she mentions inflation" and turns hits into clips. |

## Try it online (deploy in one click)

The repo ships a `Dockerfile` (backend + built frontend + ffmpeg with libass + offline demo fixtures baked in) and a `render.yaml` Blueprint:

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/altair-wq/recorte)

Render's free plan is enough for the demo: `DEMO_MODE=1`, no API keys needed, verify URLs and QR codes use the public Render URL automatically (`RENDER_EXTERNAL_URL`). Expect a ~50 s cold start after 15 min idle and clip renders of 1–2 min on the free CPU. Add `ANTHROPIC_API_KEY` / `DEEPGRAM_API_KEY` in the Render dashboard to enable live models. Disk is ephemeral: uploaded sources and rendered clips disappear on redeploy, the demo fixture does not. Any Docker host works the same way (`docker build -t recorte . && docker run -p 8000:8000 recorte`).

## Run it locally

Requirements: Python 3.11+, Node 20+, `ffmpeg`/`ffprobe` on PATH (a build with libass for burned captions; degrades to no captions otherwise).

```bash
cp .env.example .env        # add ANTHROPIC_API_KEY / DEEPGRAM_API_KEY if you have them
make setup                  # pip + npm install
make fixtures               # builds the offline demo source (≈45 s, no network) and a pre-rendered fallback clip
make dev                    # backend :8000 + frontend :5173
```

Open http://localhost:5173, click **Fuente de demo**, pick the red moment, **Extender para incluir**, **Aprobar**, open the export.

Other commands:

```bash
make smoke                  # pipeline + API assertions (every acceptance criterion in PROMPT.md §13)
make fixtures DEMO_URL=https://www.youtube.com/watch?v=...   # real source (needs network + keys)
make clip MOMENT=m_xxxx     # approve + render from the CLI
make lint                   # ruff + tsc
cd backend && python -m scripts.run_pipeline demo --render-first   # CLI safety net, no UI needed
DEMO_MODE=1 make dev        # same flow, fully offline
```

The demo video and audio in `backend/fixtures/demo/` are gitignored; `make fixtures` regenerates them deterministically. The hand-written transcript and cached moment-agent output are committed.

## Demo script (90 s)

1. Home → **Fuente de demo** → progress → Workspace with 8 moments colored by integrity.
2. Click the red one (36): "Promete inflación de un dígito mensual". Flag: *Falta un condicional* «Si se aprueba el presupuesto en el Congreso antes de fin de año,» [00:44].
3. **Extender para incluir** → re-scored 96. **Aprobar** → render starts only now.
4. Export: 9:16 clip with captions and end card, provenance card with QR, audit log, manifest JSON. QR → `/v/{clip_id}`.
5. Chat: "Encontrá cada vez que menciona la inflación" → 3 timestamps, 3 new candidate cards.

Fallbacks: `backend/fixtures/demo/clips/` holds a pre-rendered approved clip; `backend/fixtures/demo/backup.mp4` is a screen recording of the happy path.

## Decisions

- **Standalone repo.** Recorte lives in its own repository; commits are authored by the team, not the tooling.
- **Synthetic fixture.** The build environment had no YouTube, no TTS and no API keys, so the demo source is a *fictional* Spanish press conference (no real people) rendered as video with the spoken text on screen and room tone as audio, plus a hand-written transcript with word timestamps. `make fixtures DEMO_URL=…` swaps in a real source on a machine with network and keys; nothing else changes.
- **Every LLM step has a non-LLM fallback.** Moment agent → cached `moments.json`; integrity → deterministic rules (conditions, attribution, demonstratives, trailing commas, unanswered questions, same-speaker continuation); chat → accent-insensitive keyword search that still creates moments through the same `propose_moment` path. The UI shows which checker scored each moment (`checked_with`).
- **JSON files instead of SQLite.** One `source.json` / `moments.json` per source and `clip.json` per clip under `backend/data/`; every pipeline step is re-runnable from the CLI.
- **Captions are burned as ASS, not SRT**, with an explicit 1080×1920 PlayRes so margins and font sizes are in output pixels (libass renders SRT at 384×288 and `MarginV=420` would push captions off-frame). An SRT is exported next to each clip anyway.
- **QR codes are generated locally** (`/api/clips/{id}/qr.png` and on the end card); no third-party QR service, so the export page works on venue Wi-Fi.
- **12–75 s clip bounds** are enforced by the snap/clamp step; a too-short span is extended forward over utterance boundaries, keeping the quote.
- **Ruff config** ignores line length; no tests beyond `smoke.sh` as specified.
- Face-aware crop and key-frame vision were stretch items and were skipped.

## Cost per clip

From `backend/data/logs.jsonl` with live models (estimates at list prices): moment finding for a 1 h source ≈ 15k input + 2k output tokens on Sonnet ≈ **$0.08**; one integrity check on Haiku ≈ 1.5k tokens ≈ **$0.002**; Deepgram nova-3 ≈ **$0.0077/min** of audio; ffmpeg render is local. Order of magnitude: **~$0.50 per hour of source, ≈ $0.06 per published clip** including re-checks after edits. In demo mode all LLM/ASR costs are zero and the log records `fixture` as the model.

## Layout

```
backend/app/pipeline/   ingest, transcribe, compact, moments, snap, integrity, captions, render, endcard, manifest, agent, jobs
backend/app/routers/    sources, moments, clips, chat, verify
backend/app/prompts/    moment_finder.md, integrity_check.md, chat_agent.md
backend/scripts/        run_pipeline.py, make_fixtures.py, smoke.sh
backend/fixtures/demo/  transcript.json, moments.json, meta.json, chat.json (+ generated demo.mp4, clips/, backup.mp4)
frontend/src/           pages Home/Workspace/Export, components, hooks/useJob, strings.ts (es/en)
```
