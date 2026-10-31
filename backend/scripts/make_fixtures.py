"""Build fixtures/demo/.

    python -m scripts.make_fixtures <youtube-url>   # real pipeline (needs network + keys), copies outputs
    python -m scripts.make_fixtures                 # offline: synthesize a fictional Spanish press conference

The synthetic source is a fictional press conference (no real people), rendered as a video with the spoken
text on screen, plus a hand-written transcript with word timestamps and a cached moment-agent output.
It exists so the full flow can be demoed with zero network access.
"""
from __future__ import annotations

import json
import pathlib
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from app import config
from app.models import Transcript, Utterance, Word

OUT = config.FIXTURES_DIR

# (speaker, text). Speaker 1 = periodistas, Speaker 2 = ministra (personaje ficticio).
SCRIPT: list[tuple[str, str]] = [
    ("Speaker 2", "Buenas tardes a todos y gracias por acompañarnos en esta conferencia de prensa."),
    ("Speaker 2", "Vamos a repasar los números del tercer trimestre y después abrimos a preguntas."),
    ("Speaker 2", "La inflación de septiembre fue del 3,2 por ciento, la más baja en veinte meses."),
    ("Speaker 2", "Es un dato que nos alienta, pero no nos conforma."),
    ("Speaker 2", "El objetivo del gobierno sigue siendo recuperar el poder adquisitivo de los salarios."),
    ("Speaker 1", "Ministra, ¿cuál es la meta concreta de inflación para el año que viene?"),
    ("Speaker 2", "Buena pregunta. Le respondo con una condición que es importante."),
    ("Speaker 2", "Si se aprueba el presupuesto en el Congreso antes de fin de año,"),
    ("Speaker 2", "vamos a bajar la inflación a un dígito mensual en el primer trimestre."),
    ("Speaker 2", "Eso significa menos del uno por ciento mensual hacia marzo o abril."),
    ("Speaker 2", "Y lo vamos a lograr sin congelar precios y sin tocar los salarios de los trabajadores."),
    ("Speaker 1", "¿Y si el presupuesto no se aprueba?"),
    ("Speaker 2", "Si no se aprueba, el escenario cambia y tendríamos que revisar esa meta."),
    ("Speaker 2", "Por eso estamos dialogando con todos los bloques, incluida la oposición."),
    ("Speaker 1", "Ministra, ¿van a aumentar las tarifas de luz y gas en enero?"),
    ("Speaker 1", "Hay versiones en varios medios que hablan de un aumento del cuarenta por ciento a partir de enero."),
    ("Speaker 2", "No hay ninguna decisión tomada sobre tarifas para enero."),
    ("Speaker 2", "Lo que sí puedo decir es que cualquier actualización va a proteger a los hogares de menores ingresos."),
    ("Speaker 2", "La tarifa social se mantiene y se amplía a doscientas mil familias más."),
    ("Speaker 1", "La oposición dice que el ajuste va a recaer sobre los jubilados."),
    ("Speaker 2", "Según la oposición, el ajuste va a recaer sobre los jubilados."),
    ("Speaker 2", "Eso es falso, y los números lo demuestran."),
    ("Speaker 2", "Las jubilaciones mínimas aumentaron un doce por ciento por encima de la inflación este año."),
    ("Speaker 2", "Ningún jubilado va a cobrar menos en términos reales el año que viene."),
    ("Speaker 1", "Algunos economistas dicen que la inflación puede bajar a cero rápidamente si se dolariza."),
    ("Speaker 2", "Claro, y mañana la inflación va a ser cero por decreto."),
    ("Speaker 2", "Eso es lo que dicen algunos, y sinceramente no es serio."),
    ("Speaker 2", "Bajar la inflación lleva tiempo, consistencia fiscal y acuerdos políticos."),
    ("Speaker 1", "¿Cuánto van a invertir en obra pública el año próximo?"),
    ("Speaker 2", "El presupuesto contempla ochocientos mil millones de pesos para obra pública."),
    ("Speaker 2", "Es un veinte por ciento más que este año en términos reales."),
    ("Speaker 2", "La prioridad son las rutas del norte y las obras de agua potable en el conurbano."),
    ("Speaker 2", "Vamos a publicar la lista completa de obras con sus montos en la página del ministerio."),
    ("Speaker 1", "¿Hay fecha para el acuerdo con los acreedores internacionales?"),
    ("Speaker 2", "Las negociaciones avanzan bien y esperamos cerrarlas antes de marzo."),
    ("Speaker 2", "No voy a adelantar detalles porque no quiero perjudicar la negociación."),
    ("Speaker 1", "¿Qué pasa con el empleo? Las pymes dicen que están despidiendo gente."),
    ("Speaker 2", "El empleo registrado creció cuarenta y cinco mil puestos en el último trimestre."),
    ("Speaker 2", "Entiendo la preocupación de las pymes y por eso lanzamos el programa de crédito a tasa cero."),
    ("Speaker 2", "Son cien mil millones de pesos disponibles desde el lunes para empresas de hasta cincuenta empleados."),
    ("Speaker 2", "Quiero ser muy clara con esto."),
    ("Speaker 2", "Ninguna pyme que mantenga su plantilla va a pagar intereses durante los primeros doce meses."),
    ("Speaker 1", "Ministra, ¿se va a quedar en el cargo si no se aprueba el presupuesto?"),
    ("Speaker 2", "Me voy a quedar hasta que el presidente decida lo contrario."),
    ("Speaker 2", "Mi trabajo es que el presupuesto se apruebe, y en eso estoy."),
    ("Speaker 1", "Una última pregunta sobre el dólar."),
    ("Speaker 1", "¿Van a mantener el esquema de bandas cambiarias?"),
    ("Speaker 2", "El esquema de bandas se mantiene sin cambios hasta fin de año."),
    ("Speaker 2", "No vamos a devaluar y no vamos a imponer nuevos controles."),
    ("Speaker 2", "Lo dije hace un mes y lo repito hoy con los mismos números sobre la mesa."),
    ("Speaker 2", "Muchas gracias a todos. Nos vemos en la próxima conferencia."),
]

# Cached "moment agent" output. Same shape as the LLM tool call; goes through snap + validation like a live run.
FIXTURE_MOMENTS = [
    {"start_utt": 8, "end_utt": 10, "headline": "Promete inflación de un dígito mensual en el primer trimestre",
     "summary": "La ministra fija una meta de inflación por debajo del uno por ciento mensual hacia marzo o abril, sin congelar precios ni tocar salarios.",
     "why": "Es la meta cuantitativa más fuerte de la conferencia y compromete al gobierno con un plazo.",
     "quote": "vamos a bajar la inflación a un dígito mensual en el primer trimestre.", "speaker": "Speaker 2", "newsworthiness": 5},
    {"start_utt": 14, "end_utt": 15, "headline": "Periodista: ¿aumentan luz y gas un 40 % en enero?",
     "summary": "Un periodista pregunta por versiones de un aumento del cuarenta por ciento en tarifas de luz y gas.",
     "why": "La pregunta instala el tema de tarifas, uno de los más sensibles para la audiencia.",
     "quote": "¿van a aumentar las tarifas de luz y gas en enero?", "speaker": "Speaker 1", "newsworthiness": 3},
    {"start_utt": 21, "end_utt": 23, "headline": "“Ningún jubilado va a cobrar menos en términos reales”",
     "summary": "La ministra califica de falsa una afirmación y asegura que las jubilaciones mínimas subieron doce puntos por encima de la inflación.",
     "why": "Desmentida directa con un número verificable sobre jubilaciones.",
     "quote": "Ningún jubilado va a cobrar menos en términos reales el año que viene.", "speaker": "Speaker 2", "newsworthiness": 4},
    {"start_utt": 25, "end_utt": 27, "headline": "Dolarización: “Mañana la inflación va a ser cero por decreto… no es serio”",
     "summary": "Ironiza sobre quienes prometen inflación cero con una dolarización y sostiene que bajarla lleva tiempo y acuerdos políticos.",
     "why": "Toma de posición clara frente a una propuesta económica en debate.",
     "quote": "Bajar la inflación lleva tiempo, consistencia fiscal y acuerdos políticos.", "speaker": "Speaker 2", "newsworthiness": 3},
    {"start_utt": 29, "end_utt": 32, "headline": "Obra pública: 800 mil millones, un 20 % más en términos reales",
     "summary": "El presupuesto destina ochocientos mil millones de pesos a obra pública, con prioridad en rutas del norte y agua potable en el conurbano.",
     "why": "Cifra concreta y verificable con prioridades territoriales.",
     "quote": "El presupuesto contempla ochocientos mil millones de pesos para obra pública.", "speaker": "Speaker 2", "newsworthiness": 4},
    {"start_utt": 37, "end_utt": 41, "headline": "Crédito a tasa cero para pymes que mantengan empleo",
     "summary": "Anuncia cien mil millones de pesos en crédito a tasa cero desde el lunes para empresas de hasta cincuenta empleados que mantengan su plantilla.",
     "why": "Anuncio de política con monto, fecha y condición clara.",
     "quote": "Ninguna pyme que mantenga su plantilla va a pagar intereses durante los primeros doce meses.", "speaker": "Speaker 2", "newsworthiness": 5},
    {"start_utt": 43, "end_utt": 44, "headline": "“Me voy a quedar hasta que el presidente decida lo contrario”",
     "summary": "Consultada sobre su continuidad si no se aprueba el presupuesto, la ministra dice que se queda hasta que el presidente decida lo contrario.",
     "why": "Respuesta política directa sobre su continuidad en el cargo.",
     "quote": "Me voy a quedar hasta que el presidente decida lo contrario.", "speaker": "Speaker 2", "newsworthiness": 4},
    {"start_utt": 47, "end_utt": 49, "headline": "Dólar: “No vamos a devaluar y no vamos a imponer nuevos controles”",
     "summary": "Ratifica el esquema de bandas cambiarias hasta fin de año y descarta una devaluación o nuevos controles.",
     "why": "Compromiso explícito sobre el tipo de cambio, el tema que más mueve mercados.",
     "quote": "No vamos a devaluar y no vamos a imponer nuevos controles.", "speaker": "Speaker 2", "newsworthiness": 5},
]

# Deterministic timing: ~0.36 s per word, small gaps; speaker changes get a longer pause.
WORD_S = 0.36
GAP_S = 0.7
TURN_GAP_S = 1.3


def build_transcript() -> Transcript:
    t = 1.5
    utts: list[Utterance] = []
    prev_speaker = None
    for i, (spk, text) in enumerate(SCRIPT):
        if prev_speaker is not None:
            t += TURN_GAP_S if spk != prev_speaker else GAP_S
        words: list[Word] = []
        for w in text.split():
            dur = WORD_S * (0.6 + min(len(w), 12) / 12)
            words.append(Word(w=w, start=round(t, 2), end=round(t + dur, 2)))
            t += dur + 0.05
        utts.append(Utterance(id=i, start=words[0].start, end=words[-1].end, speaker=spk, text=text, words=words))
        prev_speaker = spk
    return Transcript(source_id="demo", language="es", asr_model="fixture/synthetic", utterances=utts)


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    name = "Inter-SemiBold.ttf" if bold else "Inter-Regular.ttf"
    return ImageFont.truetype(str(config.FONTS_DIR / name), size)


def _wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, width: int) -> list[str]:
    lines, cur = [], ""
    for w in text.split():
        trial = (cur + " " + w).strip()
        if draw.textlength(trial, font=font) <= width:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def render_frame(utt: Utterance | None, path: Path, w: int = 1280, h: int = 720) -> None:
    img = Image.new("RGB", (w, h), "#2A2E35")
    d = ImageDraw.Draw(img)
    # backdrop panel + "podium"
    d.rectangle([0, 0, w, 90], fill="#1E2126")
    d.text((40, 30), "CONFERENCIA DE PRENSA · MINISTERIO DE ECONOMÍA (FICTICIO)", font=_font(22, True), fill="#C9CDD4")
    d.rectangle([w - 150, 32, w - 40, 62], fill="#B42318")
    d.text((w - 128, 36), "EN VIVO", font=_font(18, True), fill="white")
    d.rectangle([0, h - 110, w, h], fill="#1E2126")
    d.text((40, h - 80), "Demo sintética para Recorte · sin personas reales", font=_font(20), fill="#8A9099")
    # speaker "avatar"
    cx, cy, r = w // 2, 420, 150
    speaking = utt is not None
    col = "#0F6E56" if (utt and utt.speaker == "Speaker 2") else "#6B4F9E"
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=col if speaking else "#3A3F47")
    initials = "LF" if (utt and utt.speaker == "Speaker 2") else "P"
    f = _font(110, True)
    tw = d.textlength(initials, font=f)
    d.text((cx - tw / 2, cy - 70), initials, font=f, fill="white")
    if utt:
        label = "Lucía Ferreyra · Ministra (personaje ficticio)" if utt.speaker == "Speaker 2" else "Periodista acreditado"
        f2 = _font(26, True)
        tw = d.textlength(label, font=f2)
        d.rectangle([cx - tw / 2 - 20, 585, cx + tw / 2 + 20, 630], fill="#1E2126")
        d.text((cx - tw / 2, 593), label, font=f2, fill="white")
        f3 = _font(34)
        lines = _wrap(d, utt.text, f3, w - 160)
        y = 120
        for ln in lines[:4]:
            tw = d.textlength(ln, font=f3)
            d.text((cx - tw / 2, y), ln, font=f3, fill="#F7F5F0")
            y += 44
    img.save(path, quality=90)


def synth_video(tr: Transcript, out_mp4: Path) -> None:
    work = OUT / "_frames"
    work.mkdir(parents=True, exist_ok=True)
    concat = []
    cursor = 0.0
    idle = work / "idle.jpg"
    render_frame(None, idle)
    for u in tr.utterances:
        if u.start > cursor + 0.01:
            concat.append((idle, u.start - cursor))
        p = work / f"u{u.id:03d}.jpg"
        render_frame(u, p)
        concat.append((p, u.end - u.start))
        cursor = u.end
    concat.append((idle, 3.0))
    total = cursor + 3.0
    lst = work / "list.txt"
    with lst.open("w") as f:
        for p, dur in concat:
            f.write(f"file '{p.name}'\nduration {dur:.3f}\n")
        f.write(f"file '{concat[-1][0].name}'\n")
    # soft brown noise stands in for room tone; no real speech (no TTS offline)
    cmd = [
        config.FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
        "-f", "lavfi", "-i", "anoisesrc=color=brown:amplitude=0.03:r=48000,lowpass=f=400",
        "-t", f"{total:.3f}", "-r", "30", "-vf", "format=yuv420p,scale=1280:720",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "24", "-c:a", "aac", "-b:a", "96k", "-shortest", str(out_mp4),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    shutil.rmtree(work, ignore_errors=True)


def synth() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    tr = build_transcript()
    (OUT / "transcript.json").write_text(tr.model_dump_json(indent=2), encoding="utf-8")
    (OUT / "moments.json").write_text(json.dumps({"moments": FIXTURE_MOMENTS}, indent=2, ensure_ascii=False), encoding="utf-8")
    meta = {
        "title": "Conferencia de prensa: presupuesto, inflación y tarifas (demo ficticia)",
        "channel": "Recorte demo",
        "url": None,
        "language": "es",
    }
    (OUT / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"transcript: {len(tr.utterances)} utterances, {tr.utterances[-1].end:.1f}s")
    synth_video(tr, OUT / "demo.mp4")
    subprocess.run([config.FFMPEG, "-y", "-i", str(OUT / "demo.mp4"), "-vn", "-ac", "1", "-ar", "16000", "-b:a", "48k", str(OUT / "audio.mp3")], check=True, capture_output=True)
    print(f"wrote {OUT / 'demo.mp4'}")
    prerender_fallback()


def prerender_fallback() -> None:
    """Run the offline pipeline once and keep one approved clip under fixtures/demo/clips/ as the last-resort fallback."""
    import os
    import tempfile

    from scripts import run_pipeline

    with tempfile.TemporaryDirectory() as tmp:
        os.environ["DATA_DIR"] = tmp
        import importlib

        from app import config as cfg
        importlib.reload(cfg)
        from app import db
        from app.models import Source, new_id
        from app.pipeline import jobs

        sid = new_id("src")
        db.save_source(Source(id=sid, status="queued", title="Demo"))
        src = jobs.run_source_pipeline(sid, demo=True)
        if src.status != "ready":
            print("fallback clip skipped:", src.error)
            return
        ms = db.list_moments(sid)
        target = next((m for m in ms if m.integrity.score >= 80), ms[0])
        cid = run_pipeline.approve_and_render(target.id, "editor@demo")
        dst = OUT / "clips"
        shutil.rmtree(dst, ignore_errors=True)
        shutil.copytree(pathlib.Path(tmp) / "clips" / cid, dst / cid)
        print(f"fallback clip → {dst / cid}")


def from_url(url: str) -> None:
    from app import db
    from app.models import Source, new_id
    from app.pipeline import ingest, moments, transcribe

    sid = new_id("src")
    src = Source(id=sid, url=url, status="queued")
    db.save_source(src)
    src = ingest.ingest(sid)
    tr = transcribe.transcribe(sid)
    raw = moments.find_moments_raw(sid, tr)
    OUT.mkdir(parents=True, exist_ok=True)
    shutil.copy(src.file_path, OUT / "demo.mp4")
    if src.audio_path:
        shutil.copy(src.audio_path, OUT / "audio.mp3")
    (OUT / "transcript.json").write_text(tr.model_dump_json(indent=2), encoding="utf-8")
    (OUT / "moments.json").write_text(json.dumps({"moments": raw}, indent=2, ensure_ascii=False), encoding="utf-8")
    (OUT / "meta.json").write_text(json.dumps({"title": src.title, "channel": src.channel, "url": url, "language": tr.language}, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"fixtures written to {OUT} from {sid}")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a.strip()]
    if args:
        from_url(args[0])
    else:
        synth()
