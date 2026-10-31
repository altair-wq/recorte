# Handoff: get Recorte running on localhost

Context for a local Claude Code session on this Mac. Read `CLAUDE.md` and `README.md` for the project; this file is only about getting it running right now.

## Current state of this machine

- Repo: `~/recorte`, branch `main`, in sync with `https://github.com/altair-wq/recorte.git`.
- `.env` exists (copied from `.env.example`); no API keys in it. That is fine: every LLM/ASR step has an offline fallback and the demo is designed to run with zero keys.
- `make setup` already ran successfully: Python deps installed into the Anaconda `base` env (`/opt/anaconda3`, Python 3.13) and `npm install` done in `frontend/`.
- **`ffmpeg` is NOT installed.** `make fixtures` failed with `FileNotFoundError: 'ffmpeg'`. Homebrew is not installed either (`zsh: command not found: brew`). Conda is available.
- Node and npm are installed (Vite 8 started fine).
- Nothing is currently running on ports 8000 or 5173.

## What to do

1. Install ffmpeg, preferably via conda (fastest, no Homebrew needed):
   ```bash
   conda install -y -c conda-forge ffmpeg
   ffmpeg -version | head -1
   ffmpeg -hide_banner -filters | grep -c subtitles   # 1 = build has libass, captions will burn in; 0 = app still works, no captions
   ```
   If conda fails, install Homebrew and then `brew install ffmpeg`.
2. Build the offline demo fixtures (synthetic fictional Spanish press conference + transcript + a pre-rendered fallback clip, ~45 s, no network):
   ```bash
   cd ~/recorte && make fixtures
   ```
   Expected output ends with `fallback clip → .../backend/fixtures/demo/clips/c_xxxx`.
3. Start both servers (backend :8000 + Vite :5173 in one process; Ctrl-C stops both):
   ```bash
   make dev
   ```
   Startup log should show `fixtures=True`. If it says `fixtures=False`, step 2 did not complete.
4. Open http://localhost:5173 and verify the demo flow:
   - Click **▶ Fuente de demo** → progress steps → Workspace with 8 moments on the timeline (red/amber/green).
   - Click the red moment "Promete inflación de un dígito mensual…" (score 36). The review drawer shows the flag *Falta un condicional* «Si se aprueba el presupuesto…».
   - Click **Extender para incluir** → score becomes 96. Click **Aprobar** → render starts (only now).
   - Click **Abrir exportación** → phone preview plays the 9:16 clip with captions and a 2 s end card with QR; provenance card, audit log and manifest JSON are shown. **Ver verificación** opens `http://localhost:8000/v/<clip_id>`.
   - Back in the Workspace, in the chat click **Encontrá cada vez que menciona la inflación** → reply with `[mm:ss]` timestamps and 3 new highlighted cards.
5. Optional sanity check in a second terminal: `cd ~/recorte && make smoke` must end with `SMOKE PASSED`.

## Gotchas

- Run `make` commands from inside `~/recorte`; `make dev` occupies its terminal, so use a second terminal tab for anything else.
- `make dev` uses `python3` from PATH; it must be the same interpreter `make setup` installed into (Anaconda base). If imports fail, run `conda activate base` first.
- Captions are burned as ASS via the ffmpeg `subtitles` filter; a build without libass just logs a warning and renders without captions.
- No keys needed for the demo. To use real models/sources later: add `ANTHROPIC_API_KEY` and `DEEPGRAM_API_KEY` to `.env`, then `make fixtures DEMO_URL=<youtube url>`.
- Commits must be authored by Altair Adilkhan (`git config user.name "Altair Adilkhan"`, `git config user.email altair.adilkhan@uni.minerva.edu`), no AI co-author trailers.
