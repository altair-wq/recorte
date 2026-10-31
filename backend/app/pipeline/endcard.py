"""End card: 1080x1920 PNG with headline, speaker, source, span, approver and a QR to the verify page."""
from __future__ import annotations

from pathlib import Path

import qrcode
from PIL import Image, ImageDraw, ImageFont

from .. import config
from .compact import mmss

PAPER = "#F7F5F0"
INK = "#1B1B1B"
INK2 = "#5A5853"
TEAL = "#0F6E56"
LINE = "#D9D5CB"


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(config.FONTS_DIR / ("Inter-SemiBold.ttf" if bold else "Inter-Regular.ttf")), size)


def _wrap(d: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, width: int, max_lines: int) -> list[str]:
    lines: list[str] = []
    cur = ""
    for w in text.split():
        t = (cur + " " + w).strip()
        if d.textlength(t, font=font) <= width:
            cur = t
        else:
            lines.append(cur)
            cur = w
            if len(lines) == max_lines:
                break
    if cur and len(lines) < max_lines:
        lines.append(cur)
    if len(lines) == max_lines and d.textlength(" ".join(text.split()), font=font) > width * max_lines:
        lines[-1] = lines[-1].rstrip(".,") + "…"
    return lines


def make_endcard(*, headline: str, speaker: str | None, source_title: str, start: float, end: float,
                 approved_by: str, verify_url: str, out: Path, score: int | None = None) -> Path:
    W, H = 1080, 1920
    img = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(img)
    x = 90
    y = 220
    d.rectangle([x, y, x + 120, y + 6], fill=TEAL)
    y += 50
    for ln in _wrap(d, headline, _font(66, True), W - 2 * x, 4):
        d.text((x, y), ln, font=_font(66, True), fill=INK)
        y += 82
    if speaker:
        y += 20
        d.text((x, y), speaker, font=_font(38), fill=INK2)
        y += 70
    y += 40
    d.line([x, y, W - x, y], fill=LINE, width=2)
    y += 50

    def row(label: str, value: str, lines: int = 2) -> None:
        nonlocal y
        d.text((x, y), label.upper(), font=_font(26, True), fill=TEAL)
        y += 40
        for ln in _wrap(d, value, _font(36), W - 2 * x, lines):
            d.text((x, y), ln, font=_font(36), fill=INK)
            y += 48
        y += 30

    row("Fuente", source_title, 3)
    row("Fragmento", f"{mmss(start)} – {mmss(end)}", 1)
    row("Aprobado por", approved_by, 1)
    if score is not None:
        row("Integridad", f"{score} / 100", 1)

    qr = qrcode.QRCode(box_size=10, border=1, error_correction=qrcode.constants.ERROR_CORRECT_M)
    qr.add_data(verify_url)
    qr.make(fit=True)
    qimg = qr.make_image(fill_color=INK, back_color=PAPER).convert("RGB")
    size = 420
    qimg = qimg.resize((size, size), Image.NEAREST)
    qy = H - size - 260
    img.paste(qimg, (W - x - size, qy))
    d.text((x, qy + 20), "Verificá este clip", font=_font(40, True), fill=INK)
    for i, ln in enumerate(_wrap(d, "Escaneá el código para ver la fuente, el fragmento exacto y quién lo aprobó.", _font(30), W - 2 * x - size - 40, 4)):
        d.text((x, qy + 90 + i * 40), ln, font=_font(30), fill=INK2)
    d.line([x, H - 180, W - x, H - 180], fill=LINE, width=2)
    d.text((x, H - 150), "Recorte · clip verificable", font=_font(30, True), fill=TEAL)
    d.text((x, H - 105), verify_url, font=_font(26), fill=INK2)
    img.save(out)
    return out
