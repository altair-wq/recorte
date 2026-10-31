"""GET /v/{clip_id}: server-rendered verification page. No JS, works without the frontend."""
from __future__ import annotations

import html
import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from .. import db
from ..pipeline.compact import mmss

router = APIRouter(tags=["verify"])

CSS = """
body{margin:0;background:#F7F5F0;color:#1B1B1B;font:16px/1.5 Inter,system-ui,sans-serif}
main{max-width:720px;margin:0 auto;padding:40px 20px 80px}
h1{font-family:Newsreader,Georgia,serif;font-weight:500;font-size:34px;line-height:1.15;margin:8px 0 6px}
.eyebrow{color:#0F6E56;font-weight:600;letter-spacing:.08em;font-size:12px;text-transform:uppercase}
.card{background:#fff;border:1px solid #D9D5CB;border-radius:12px;padding:20px 22px;margin:18px 0}
blockquote{font-family:Newsreader,Georgia,serif;font-size:22px;margin:0;padding-left:16px;border-left:3px solid #0F6E56}
dl{display:grid;grid-template-columns:150px 1fr;gap:8px 16px;margin:0}dt{color:#5A5853;font-size:13px;text-transform:uppercase;letter-spacing:.05em}dd{margin:0;word-break:break-all}
.score{display:inline-block;padding:3px 10px;border-radius:999px;font-weight:600;font-size:13px}
.g{background:#DCEDE6;color:#0F6E56}.a{background:#F6E7C8;color:#8a5a12}.r{background:#F4D4D0;color:#B42318}
video{width:100%;max-width:300px;border-radius:12px;background:#000;display:block}
a{color:#0F6E56}.muted{color:#5A5853;font-size:13px}code{font-size:12px}
.flag{border-left:3px solid #B7791F;padding:6px 10px;margin:6px 0;background:#FBF6EA;border-radius:0 6px 6px 0;font-size:14px}
"""


def _cls(score: int) -> str:
    return "g" if score >= 80 else "a" if score >= 50 else "r"


@router.get("/v/{clip_id}", response_class=HTMLResponse)
def verify_page(clip_id: str) -> str:
    c = db.get_clip(clip_id)
    if c is None:
        raise HTTPException(404, "clip not found")
    m = db.get_moment(c.moment_id)
    s = db.get_source(c.source_id)
    if m is None or s is None:
        raise HTTPException(404, "clip incomplete")
    man = json.loads(Path(c.manifest_path).read_text(encoding="utf-8")) if c.manifest_path and Path(c.manifest_path).exists() else None
    e = html.escape
    src_link = e(s.title)
    if s.url and "youtu" in s.url:
        sep = "&" if "?" in s.url else "?"
        src_link = f'<a href="{e(s.url)}{sep}t={int(m.start)}">{e(s.title)}</a>'
    elif s.url:
        src_link = f'<a href="{e(s.url)}">{e(s.title)}</a>'
    flags = "".join(
        f'<div class="flag"><b>{e(f.type)}</b> · [{mmss(f.at)}] «{e(f.evidence)}»' + (f' — {e(f.suggestion)}' if f.suggestion else "") + "</div>"
        for f in m.integrity.flags
    ) or '<p class="muted">Sin alertas de integridad.</p>'
    adjustments = "".join(
        f'<li>{e(a.get("field",""))}: {mmss(float(a.get("from",0)))} → {mmss(float(a.get("to",0)))} <span class="muted">({e(str(a.get("by","")))})</span></li>'
        for a in m.adjustments
    )
    video = f'<video controls src="/data/clips/{e(c.id)}/clip.mp4" poster="/data/clips/{e(c.id)}/thumb.jpg"></video>' if c.status == "ready" else f'<p class="muted">Estado del clip: {e(c.status)}</p>'
    approval = m.review
    return f"""<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Recorte · verificación {e(c.id)}</title><style>{CSS}</style></head><body><main>
<div class="eyebrow">Recorte · clip verificable</div>
<h1>{e(m.headline)}</h1>
<p class="muted">{e(m.speaker or "")} · {mmss(m.start)} – {mmss(m.end)} de la fuente · <span class="score {_cls(m.integrity.score)}">Integridad {m.integrity.score}/100</span></p>
<div class="card">{video}</div>
<div class="card"><div class="eyebrow">Cita textual (ASR, sin edición)</div><blockquote>«{e(m.quote)}»</blockquote></div>
<div class="card"><dl>
<dt>Fuente</dt><dd>{src_link}{(' · ' + e(s.channel)) if s.channel else ''}</dd>
<dt>Fragmento</dt><dd>{mmss(m.start)} – {mmss(m.end)} (utterances u{m.start_utt}–u{m.end_utt})</dd>
<dt>Aprobado por</dt><dd>{e(approval.by) if approval else '—'} · {e(approval.at.isoformat(timespec="seconds")) if approval else ''}</dd>
<dt>Transcripción</dt><dd>{e(man["pipeline"]["asr"]) if man else ''}</dd>
<dt>Modelos</dt><dd>{e(man["pipeline"]["llm"]) if man else ''} · integridad: {e(m.integrity.checked_with)}</dd>
<dt>SHA-256 fuente</dt><dd><code>{e(s.sha256)}</code></dd>
<dt>SHA-256 clip</dt><dd><code>{e(c.sha256)}</code></dd>
<dt>Manifiesto</dt><dd><a href="/api/clips/{e(c.id)}/manifest">manifest.json</a></dd>
</dl></div>
<div class="card"><div class="eyebrow">Alertas de integridad</div>{flags}
{('<div class="eyebrow" style="margin-top:12px">Ajustes del editor</div><ul>' + adjustments + '</ul>') if adjustments else ''}</div>
<p class="muted">Este clip fue recortado de una fuente más larga con aprobación editorial explícita. Los cortes caen en límites de oración y la cita es texto literal de la transcripción.</p>
</main></body></html>"""
