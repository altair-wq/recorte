# Build prompt: Recorte (working name, rename freely)

Read `CLAUDE.md` first. Then read this file top to bottom before writing any code.

You are building a hackathon prototype today, Saturday Oct 31 2026, at Media Party Buenos Aires (Ciudad Cultural Konex). Final presentations are at roughly 18:00 ART. It is now about 14:00. Everything must be built from scratch today; open-source libraries and public APIs are allowed. Optimize for one flawless 90-second demo, not for completeness.

---

## 1. What we are building

An agent that turns long newsroom video (interviews, press conferences, debates, streams) into publish-ready vertical clips, where every clip is (a) checked for stripped context, (b) approved by a human editor before it renders, and (c) exported with a provenance record that travels with the clip.

Positioning in one sentence: "Overlap for newsrooms, with an editorial conscience." Overlap (YC S24) sells clipping agents to creators and marketers and optimizes for virality. We optimize for clips a newsroom can defend: no mid-sentence cuts, no missing qualifiers, mandatory editor sign-off, source and timestamp on every clip.

Judging criteria we are building against: (1) technical quality of the agentic architecture, (2) narrative innovation, (3) traceability and integrity with human judgment, (4) commercial viability. Criterion 3 is our differentiator; make it visible in the UI at every step.

---

## 2. The demo script (this must work on stage, offline if needed)

1. Home screen. Paste a YouTube URL of a Spanish-language interview or press conference (or pick the cached demo source). Progress: ingest → transcript → moments.
2. Workspace. The timeline lights up with 6-8 candidate moments colored by integrity score. Click one: headline, exact quote, why it matters, speaker, and an integrity flag such as "the cut drops the qualifier 'si se aprueba el presupuesto' spoken 4 s earlier. Extend?"
3. Review drawer. Editor clicks "Extend to include", then "Approve". Only now does render start. Clip plays: 9:16, burned-in captions, 2-second end card with source, timestamp and a QR code.
4. Export page. Shows the provenance manifest (JSON) and the audit log (who approved, when, source span, models used). The QR opens `/v/{clip_id}`, a public verification page.
5. Agent chat. "Encontrá cada vez que menciona la inflación" → the agent returns 3 moments and adds them as cards. This is the archive-search expansion story.

If any step cannot run live (network, API outage), DEMO_MODE must make the identical flow work from cached fixtures.

---

## 3. Non-negotiables (product rules, enforce in code)

- No clip renders without an explicit editor approval event. The render endpoint must reject unapproved moments.
- Cut points always snap to utterance boundaries. Never cut mid-sentence.
- Every candidate moment carries an integrity score (0-100) and a list of typed flags with evidence (the exact transcript text that triggered the flag and its timestamp).
- Every rendered clip has a provenance manifest and an end card. The manifest includes the SHA-256 of the source file and of the rendered clip.
- Transcript text shown to the editor is always the verbatim ASR output. The LLM may summarize, but quotes must be copied from the transcript, never paraphrased. Validate this in code: the `quote` field must be a substring of the concatenated utterance text (after whitespace normalization) or the moment is rejected.
- Spanish-first UI with an EN toggle. All UI strings live in one strings file.

---

## 4. Architecture

Pipeline (left to right), one human gate before render:

Ingest (yt-dlp, ffmpeg) → Transcribe (Deepgram, word timestamps) → Moment agent (Claude: find + flag) → Editor review (approve / adjust) → Render (ffmpeg 9:16 + captions + end card) → Export (clip + manifest + verify page)

Optional side input: key frames → vision model → "who is on screen" labels fed to the moment agent. Build this last; skip it if behind schedule.

Agent chat sits on top of the same transcript and can create new candidate moments through a tool call.

Stack:
- Backend: Python 3.11+, FastAPI, Pydantic v2, uvicorn, SQLite via SQLModel (or plain JSON files if faster), BackgroundTasks for jobs, `yt-dlp`, `ffmpeg` (system binary), `deepgram-sdk`, `anthropic`, `Pillow`, `qrcode`.
- Frontend: Vite + React 18 + TypeScript + Tailwind. No component library unless it saves real time (shadcn/ui is fine). HTML5 `<video>`.
- No auth, no multi-tenancy, no Docker, no cloud deploy. Localhost only. ngrok is optional for the QR code.

---

## 5. Repo layout

```
recorte/
  CLAUDE.md
  PROMPT.md
  README.md                 # pitch bullets + how to run (write last)
  .env.example
  Makefile                  # setup, dev, smoke, fixtures
  backend/
    app/
      main.py               # FastAPI app, CORS, routers, static serving of /data
      config.py             # env, paths, DEMO_MODE
      models.py             # Pydantic/SQLModel models
      db.py
      routers/
        sources.py
        moments.py
        clips.py
        chat.py
        verify.py           # GET /v/{clip_id} HTML page
      pipeline/
        ingest.py           # yt-dlp download or local file, ffmpeg probe, audio extract, sha256
        transcribe.py       # Deepgram primary, fallbacks; normalize to Utterance[]
        compact.py          # transcript → compact text for LLM, chunking
        moments.py          # moment agent (find candidates)
        integrity.py        # deterministic pre-checks + LLM context check
        snap.py             # boundary snapping, duration clamps, dedupe
        captions.py         # words → SRT
        render.py           # ffmpeg crop/scale/captions, end card, concat
        endcard.py          # Pillow end card + QR
        manifest.py         # provenance manifest + hashes
        agent.py            # chat agent with tools
      prompts/
        moment_finder.md
        integrity_check.md
        chat_agent.md
    scripts/
      run_pipeline.py       # CLI: python -m scripts.run_pipeline <url|file> → prints moments, renders first approved
      make_fixtures.py      # pre-process the demo source into fixtures/demo/
      smoke.sh
    fixtures/demo/          # demo.mp4, transcript.json, moments.json, clips/
    data/                   # runtime: sources/{id}/..., clips/{id}/..., gitignored
    assets/fonts/           # Inter-Regular.ttf, Inter-SemiBold.ttf (OFL) for captions and end card
  frontend/
    src/
      api.ts
      strings.ts            # es + en
      pages/Home.tsx, Workspace.tsx, Export.tsx
      components/VideoPlayer.tsx, Timeline.tsx, MomentCard.tsx, ReviewDrawer.tsx, AgentChat.tsx, ProvenanceCard.tsx, IntegrityBadge.tsx
      lib/time.ts           # mm:ss helpers
```

---

## 6. Data model

```python
class Word(BaseModel):
    w: str; start: float; end: float

class Utterance(BaseModel):
    id: int; start: float; end: float; speaker: str | None; text: str; words: list[Word]

class Source(BaseModel):
    id: str; url: str | None; title: str; channel: str | None
    duration: float; file_path: str; audio_path: str | None; sha256: str
    status: Literal["queued","downloading","transcribing","finding_moments","ready","error"]
    error: str | None; created_at: datetime

class Transcript(BaseModel):
    source_id: str; language: str; asr_model: str; utterances: list[Utterance]

class Flag(BaseModel):
    type: Literal["mid_sentence_cut","missing_qualifier","missing_attribution",
                  "question_without_answer","hypothetical_or_sarcasm","needs_prior_context","speaker_change_at_edge"]
    evidence: str          # verbatim transcript text that triggered the flag
    at: float              # timestamp of the evidence
    suggestion: str | None # e.g. "extend start to 728.0"

class Integrity(BaseModel):
    score: int             # 0-100
    flags: list[Flag]
    suggested_start: float | None
    suggested_end: float | None
    checked_with: str      # model id

class Moment(BaseModel):
    id: str; source_id: str
    start: float; end: float          # current (editor may adjust)
    orig_start: float; orig_end: float
    start_utt: int; end_utt: int
    headline: str; summary: str; why: str
    quote: str                        # verbatim substring of utterance text
    speaker: str | None
    newsworthiness: int               # 1-5
    integrity: Integrity
    status: Literal["candidate","approved","rejected"]
    review: Review | None
    origin: Literal["agent","chat","manual"]

class Review(BaseModel):
    decision: Literal["approved","rejected"]; by: str; at: datetime; reason: str | None
    adjustments: list[dict]           # [{"field":"start","from":734.2,"to":728.0,"at":...}]

class Clip(BaseModel):
    id: str; moment_id: str; source_id: str
    file_path: str; thumb_path: str; manifest_path: str; sha256: str
    status: Literal["rendering","ready","error"]; created_at: datetime
```

Manifest (JSON written next to the clip, also returned by API):

```json
{
  "clip_id": "c_8f2a",
  "created_at": "2026-10-31T19:12:03-03:00",
  "source": {"url": "...", "title": "...", "channel": "...", "duration": 3721.4, "sha256": "..."},
  "span": {"start": 728.0, "end": 768.9, "start_utt": 11, "end_utt": 15},
  "quote": "verbatim transcript text",
  "speaker": "...",
  "moment": {"headline": "...", "summary": "..."},
  "integrity": {"score": 91, "flags": [], "adjustments": [{"field": "start", "from": 734.2, "to": 728.0}]},
  "approval": {"by": "editor@demo", "at": "...", "reason": null},
  "pipeline": {"asr": "deepgram/nova-3", "llm": "claude-sonnet-5-5", "app_version": "0.1.0"},
  "render": {"aspect": "9:16", "captions": true, "endcard": true, "sha256": "..."},
  "verify_url": "http://localhost:8000/v/c_8f2a"
}
```

---

## 7. Backend API

Job pattern: POST creates the record and schedules a BackgroundTask; the client polls GET every 1.5 s. Keep status strings in sync with the frontend.

- `POST /api/sources` body `{url}` or multipart file → `{id, status}`. Runs ingest → transcribe → moments.
- `GET /api/sources/{id}` → Source with status and (when ready) counts.
- `GET /api/sources/{id}/transcript` → Transcript.
- `GET /api/sources/{id}/moments` → Moment[] ordered by start.
- `POST /api/sources/{id}/moments/rerun` → re-run moment agent (for demos after tweaking prompts).
- `GET /api/moments/{id}`
- `PATCH /api/moments/{id}` body `{start?, end?}` → re-snaps to utterance boundaries, records an adjustment, re-runs integrity check for the new span, returns updated Moment.
- `POST /api/moments/{id}/approve` body `{by, reason?}` → status approved, schedules render, returns `{clip_id}`.
- `POST /api/moments/{id}/reject` body `{by, reason}`.
- `GET /api/clips/{id}` → Clip (+ `file_url`, `thumb_url`, `manifest_url`).
- `GET /api/clips/{id}/manifest` → manifest JSON.
- `POST /api/sources/{id}/chat` body `{messages:[...]}` → `{reply, created_moment_ids: []}`.
- `GET /v/{clip_id}` → server-rendered HTML verification page (no JS needed): source title linked with `?t=<start>` for YouTube, quote, span, approver, hashes, link to manifest.
- Static: serve `backend/data` under `/data` so the frontend can play source video and clips.

Render must `409` if the moment is not approved.

---

## 8. Pipeline details

### 8.1 Ingest
- URL: `yt-dlp -f "bv*[height<=720]+ba/b[height<=720]" --merge-output-format mp4 -o data/sources/{id}/source.mp4 <url>`. Also fetch title/channel/duration via `yt-dlp -J`.
- Local file: copy into the same path.
- Probe with `ffprobe -v error -show_entries format=duration -of json`.
- Extract audio for ASR: `ffmpeg -y -i source.mp4 -vn -ac 1 -ar 16000 -b:a 48k audio.mp3`.
- Compute SHA-256 of `source.mp4`.
- Make a 1 fps contact strip of thumbnails for the timeline? Skip. One poster frame at 10 s is enough: `ffmpeg -ss 10 -i source.mp4 -frames:v 1 poster.jpg`.

### 8.2 Transcribe
Primary: Deepgram prerecorded on `audio.mp3` with `model="nova-3"`, `language="es"`, `smart_format=True`, `punctuate=True`, `utterances=True`, `diarize=True`. If the API rejects nova-3 with `es`, retry with `model="nova-2"`. Fallbacks, env-driven: AssemblyAI (`language_code="es"`, word timestamps on), then OpenAI `whisper-1` with `response_format="verbose_json"` and `timestamp_granularities=["word","segment"]` (chunk audio into ≤ 20 MB pieces if needed).

Normalize everything into `Utterance[]` with word timestamps. Assign speakers as `"Speaker 1"`, `"Speaker 2"` when diarization exists. Cache the transcript to `data/sources/{id}/transcript.json` and never re-transcribe if it exists.

### 8.3 Compact transcript for the LLM
One line per utterance: `[u{id} mm:ss-mm:ss] Speaker 1: text`. Chunk into ~12-minute windows with 60 s overlap. An hour of Spanish speech is roughly 12-15k tokens; a single call is fine for ≤ 45 min, otherwise chunk and merge.

### 8.4 Moment agent (prompts/moment_finder.md)
Model: `claude-sonnet-5-5`. Temperature 0.3. Ask for 6-10 candidates per hour of video, each 12-75 s, self-contained, newsworthy for a general audience, with a preference for claims, commitments, numbers, confrontations, and clear statements over banter. Return strict JSON (use a JSON schema / tool call for structured output):

```json
{"moments":[{"start_utt":11,"end_utt":15,"headline":"...","summary":"...","why":"...","quote":"...","speaker":"...","newsworthiness":4}]}
```

Rules in the prompt: headline and summary in Spanish (or `lang` param), max 80 chars headline, `quote` must be copied verbatim from the transcript lines provided, `start_utt`/`end_utt` must reference real utterance ids, never invent facts not present in the transcript.

Post-processing in code (`snap.py`):
- Resolve `start`/`end` from utterance ids (start of `start_utt`, end of `end_utt`).
- Clamp to 12-75 s; if the LLM range is longer, keep the utterances containing the quote and trim from the edges.
- Dedupe candidates overlapping > 50 % (keep higher newsworthiness).
- Validate `quote` is a substring of the joined utterance text (normalize whitespace, case-sensitive). Reject otherwise and log.

### 8.5 Integrity check (prompts/integrity_check.md + deterministic checks)
Deterministic pre-checks (no LLM):
- `mid_sentence_cut`: start/end not on an utterance boundary (should never happen after snapping; keep as a guard).
- `speaker_change_at_edge`: the utterance right before `start` or right after `end` is the same speaker continuing within < 0.6 s gap (likely a split thought).
- `question_without_answer`: the first utterance in the span ends with `?` and the span ends before the next speaker's utterance.

LLM check (`claude-haiku-5-5`, temperature 0): give it the span text plus 20 s of context before and after, each line tagged `[u{id}]` and marked IN or CONTEXT. Ask: does the surrounding context change the meaning of the span? Look for conditions ("si", "en caso de", "siempre que"), negations ("no", "nunca", "tampoco"), attributions ("según", "dijo que", "según la oposición"), hypotheticals and irony, and references to something said earlier ("eso", "lo que dije antes"). Return:

```json
{"score": 0-100, "flags":[{"type":"missing_qualifier","evidence":"si se aprueba el presupuesto","at_utt":10,"suggestion":"extend start to u10"}], "suggested_start_utt": 10, "suggested_end_utt": 15, "rationale":"one sentence"}
```

Score guidance in the prompt: 90-100 self-contained; 70-89 minor context helps; 40-69 meaning shifts without context; < 40 misleading as cut. Map `at_utt` to timestamps in code. If the LLM call fails, score 50 with a `needs_prior_context` flag and `evidence: "check unavailable"`, never crash the pipeline.

### 8.6 Captions (`captions.py`)
Build SRT from words: groups of ≤ 4 words or ≤ 1.6 s, break at punctuation. Sentence case, keep accents and ñ. Offset timestamps by the clip start.

### 8.7 Render (`render.py`)
Cut, crop to 9:16 (center crop by default), scale to 1080x1920, burn captions:

```
ffmpeg -y -ss {start} -to {end} -i source.mp4 \
  -vf "crop=ih*9/16:ih:(iw-ih*9/16)/2:0,scale=1080:1920,subtitles=captions.srt:fontsdir=assets/fonts:force_style='FontName=Inter,FontSize=15,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,Outline=2,Shadow=0,Alignment=2,MarginV=420'" \
  -r 30 -c:v libx264 -preset veryfast -crf 22 -pix_fmt yuv420p -c:a aac -b:a 128k -ar 48000 clip_body.mp4
```

Check once at startup that the ffmpeg build has the `subtitles` filter (`ffmpeg -filters | grep subtitles`); if not, render without captions and log a warning rather than failing.

End card (`endcard.py`): 1080x1920 PNG with Pillow: dark paper background, headline, speaker, "Fuente:" + source title, span as `mm:ss - mm:ss`, "Aprobado por" + editor, QR (`qrcode` lib) to `verify_url`, small line "Recorte · clip verificable". Then:

```
ffmpeg -y -loop 1 -i endcard.png -f lavfi -i anullsrc=r=48000:cl=stereo -t 2 -r 30 -c:v libx264 -pix_fmt yuv420p -c:a aac -b:a 128k -shortest endcard.mp4
ffmpeg -y -i clip_body.mp4 -i endcard.mp4 -filter_complex "[0:v][0:a][1:v][1:a]concat=n=2:v=1:a=1[v][a]" -map "[v]" -map "[a]" -c:v libx264 -preset veryfast -crf 22 -pix_fmt yuv420p -c:a aac clip.mp4
ffmpeg -y -ss 1 -i clip.mp4 -frames:v 1 thumb.jpg
```

Stretch only: face-aware crop. Sample 5 frames across the span, detect faces with OpenCV Haar cascade, average the x-center, crop around it. Skip unless everything else is done.

### 8.8 Manifest (`manifest.py`)
Write the JSON in section 6 to `data/clips/{id}/manifest.json`, including SHA-256 of `clip.mp4`. `verify_url` uses `PUBLIC_BASE_URL` from env (default `http://localhost:8000`).

### 8.9 Agent chat (`agent.py`, prompts/chat_agent.md)
Model `claude-sonnet-5-5` with tool use. System prompt: you are a newsroom research assistant with access to the full transcript (compact form, included in context for ≤ 45 min sources; otherwise chunk-search first). Tools:
- `search_transcript(query: str) -> [{utt_id, start, text}]`: simple case-insensitive and accent-insensitive substring and keyword match over utterances, top 15.
- `propose_moment(start_utt: int, end_utt: int, headline: str, why: str) -> Moment`: runs snap + integrity and creates a `candidate` with `origin="chat"`.
The reply must cite utterance timestamps as `[mm:ss]`. Return `created_moment_ids` so the UI can highlight new cards.

---

## 9. Frontend

Pages:
- `Home`: paste URL or pick "Demo source" (visible only when DEMO_MODE or fixtures exist). Shows job status steps with checkmarks. Routes to Workspace when ready.
- `Workspace` (`/s/:sourceId`): three regions. Left 60 %: `VideoPlayer` on top, `Timeline` beneath. Right 40 %: `MomentCard` list (sorted by time, filter chips: Todos / Pendientes / Aprobados), `AgentChat` collapsible at the bottom. Clicking a card seeks the player and opens `ReviewDrawer`.
- `Export` (`/c/:clipId`): clip preview (9:16 in a phone frame), `ProvenanceCard`, manifest JSON viewer, audit log, copy-link and download buttons, link to `/v/{clip_id}`.

Components:
- `Timeline`: full-width bar, segments positioned by `start/duration`, colored by integrity (green ≥ 80, amber 50-79, red < 50), approved segments get a check icon, playhead synced to the video, click to seek, hover tooltip with headline.
- `MomentCard`: headline, speaker, `mm:ss-mm:ss`, `IntegrityBadge`, first flag as one line, status pill.
- `ReviewDrawer`: transcript of the span plus 20 s context before/after in muted text; flagged evidence highlighted; buttons: "Extender para incluir" (applies `suggested_start/end`), fine-adjust ±1 utterance, "Aprobar", "Rechazar" (requires a reason), editor name field persisted in localStorage. Show the verbatim quote prominently.
- `AgentChat`: message list, input, "suggested prompts" chips, new moments announced inline with a link to the card.
- `ProvenanceCard`: the end-card content rendered as HTML plus the QR.

Keyboard: `J/K` previous/next moment, `A` approve, `E` extend, `Space` play/pause.

Polling: `useJob(sourceId)` polls every 1.5 s until `ready` or `error`. Render polling the same for clips.

Strings (`strings.ts`): `es` default, `en` toggle in the header. Core Spanish copy to use: "Pegá un enlace de YouTube", "Momentos", "Pendientes", "Aprobados", "Integridad", "Extender para incluir", "Aprobar", "Rechazar", "Motivo", "Fuente", "Aprobado por", "Clip verificable", "Exportar", "Descargar clip", "Ver verificación", "Buscar en la transcripción".

---

## 10. Visual design direction

Editorial desk, not creator tool. Light paper background (`#F7F5F0`), ink text (`#1B1B1B`), one accent (deep teal `#0F6E56`) for approvals, amber for warnings, red for low integrity. Headlines in a serif (Newsreader or Fraunces from Google Fonts), body in Inter. Generous whitespace, 12 px radius cards, hairline borders, no gradients, no glassmorphism, no neon. The integrity badge is the most prominent UI element after the video. Phone-frame preview for the clip on the Export page.

---

## 11. Demo mode and fixtures

- `scripts/make_fixtures.py <url>`: runs the full pipeline once for the chosen demo source and copies `source.mp4`, `audio.mp3`, `transcript.json`, `moments.json` into `fixtures/demo/`.
- `DEMO_MODE=1`: the Home page shows a "Demo source" button that loads from fixtures without network; transcription and moment-finding read from the cached JSON; render still runs ffmpeg locally (it is fast and offline). If `ANTHROPIC_API_KEY` is missing, integrity re-checks after adjustments return the cached result and the chat returns a canned reply from `fixtures/demo/chat.json`.
- Pre-render one approved clip into `fixtures/demo/clips/` as the ultimate fallback.

---

## 12. Build order and timeboxes (strict)

Work in a vertical slice. Do not start a later phase before the smoke test of the current phase passes. Commit at the end of each phase with the phase name.

- Phase 0 (until 14:20): repo scaffold, `Makefile`, `.env.example`, backend and frontend boot, fonts in `assets/fonts`, `smoke.sh` skeleton, download the demo source into `fixtures/demo/`.
- Phase 1 (until 15:00): `scripts/run_pipeline.py` works end to end on the fixture: ingest → transcript → moments (no integrity yet) → render the first candidate to `clip.mp4` with captions. CLI only. This is the safety net; if everything else fails we demo the CLI.
- Phase 2 (until 15:45): FastAPI endpoints with job polling; Workspace page with player, timeline, moment cards from the API; Home page with URL input and demo button.
- Phase 3 (until 16:30): integrity checks (deterministic + LLM), ReviewDrawer with extend/approve/reject, render gated on approval, end card, manifest, `/v/{clip_id}`, Export page.
- Phase 4 (until 17:15): agent chat with tools, ES/EN strings, keyboard shortcuts, design polish, poster thumbnails.
- Phase 5 (until 17:45): DEMO_MODE hardening, pre-rendered fallback clip, README with pitch bullets and run instructions, 60-second screen recording of the happy path saved to `fixtures/demo/backup.mp4`.

At each phase boundary: run `make smoke`, then report in at most 6 lines (what works, what is stubbed, next phase). Ask the team a question only if a decision changes what the demo shows; otherwise decide and note it in `README.md` under "Decisions".

---

## 13. Acceptance criteria

- `make dev` starts backend on :8000 and frontend on :5173 with one command.
- `make smoke` runs the pipeline on the fixture and asserts: transcript has > 0 utterances with words; ≥ 4 moments; every moment's quote is a verbatim substring; every moment start/end is on utterance boundaries; rendering an unapproved moment returns 409; approving renders a clip with a manifest whose `render.sha256` matches the file.
- Workspace loads the demo source in < 3 s from fixtures.
- Approve → clip ready in < 30 s for a 60-second span on a laptop.
- `/v/{clip_id}` renders without the frontend running.
- Integrity flags include evidence text and a timestamp; "Extender para incluir" changes the span and re-scores.
- Chat query in Spanish returns timestamps and can create a moment card.

---

## 14. Known pitfalls

- YouTube may block yt-dlp on venue Wi-Fi (bot checks). Keep the fixture downloaded early and support local file upload.
- `subtitles` filter requires an ffmpeg build with libass. Check at startup; degrade gracefully.
- Spanish accents in captions need a real TTF with Latin Extended glyphs; ship Inter in `assets/fonts` and pass `fontsdir`.
- Deepgram diarization sometimes merges speakers; never rely on speaker labels for logic, only for display.
- Claude JSON: use structured output or a tool call for the schema; still validate with Pydantic and retry once on failure.
- Long videos: chunk the compact transcript; dedupe moments across chunk overlaps.
- ffmpeg `-ss` before `-i` with re-encoding is frame-accurate enough; do not use `-c copy` for cuts.
- Keep API keys out of the repo; `.env` is gitignored, `.env.example` lists every variable.

---

## 15. How to work

- Start by writing a 15-line plan to `PLAN.md` with the file list for Phase 0 and Phase 1, then build. Do not ask for approval of the plan.
- Prefer boring, well-known libraries. No new frameworks mid-build.
- Keep the happy path green at all times; if a change breaks it, revert first.
- If blocked for more than 15 minutes on a dependency, stub it behind an interface (e.g., `Transcriber` protocol with `DeepgramTranscriber`, `FixtureTranscriber`) and move on.
- Log every external call with duration and cost estimate to `data/logs.jsonl`; the pitch wants "cost per clip".
- No tests beyond `smoke.sh`. No linters beyond `ruff` and `tsc --noEmit`.
- Write small functions with type hints. Every pipeline step is a pure-ish function that reads and writes files under `data/sources/{id}/`, so steps can be re-run independently from the CLI.
