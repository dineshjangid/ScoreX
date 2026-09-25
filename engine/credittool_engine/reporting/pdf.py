"""The model development document as PDF (reportlab), rendered from the
shared structure in document.py so it matches the Word version section for
section.
"""
from __future__ import annotations

import io
import os
from typing import Any
from xml.sax.saxutils import escape

import matplotlib
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch, mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image,
    KeepTogether,
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from . import document as d
from .document import build_document

_FONT_DIR = os.path.join(os.path.dirname(matplotlib.__file__), "mpl-data", "fonts", "ttf")
_FONTS_REGISTERED = False

INK = colors.HexColor("#1f1d24")
MUTED = colors.HexColor("#6b6375")
RULE = colors.HexColor("#e5e4e7")
HEADER_BG = colors.HexColor("#f3f2f5")
ACCENT = colors.HexColor("#2a78d6")
NARRATIVE_BG = colors.HexColor("#f7f9fd")


def _register_fonts() -> None:
    # Standard PDF fonts can't draw ≥, α, −, ⚠ etc.; DejaVu Sans (shipped
    # with matplotlib) covers everything the document uses.
    global _FONTS_REGISTERED
    if _FONTS_REGISTERED:
        return
    for name, file in (("DejaVu", "DejaVuSans.ttf"), ("DejaVu-Bold", "DejaVuSans-Bold.ttf"), ("DejaVu-Oblique", "DejaVuSans-Oblique.ttf")):
        pdfmetrics.registerFont(TTFont(name, os.path.join(_FONT_DIR, file)))
    pdfmetrics.registerFontFamily("DejaVu", normal="DejaVu", bold="DejaVu-Bold", italic="DejaVu-Oblique")
    _FONTS_REGISTERED = True


def _styles() -> dict[str, ParagraphStyle]:
    base = ParagraphStyle("body", fontName="DejaVu", fontSize=9.5, leading=13.5, textColor=INK, spaceAfter=6)
    return {
        "title": ParagraphStyle("title", parent=base, fontName="DejaVu-Bold", fontSize=24, leading=30, spaceAfter=6),
        "subtitle": ParagraphStyle("subtitle", parent=base, fontSize=14, leading=18, textColor=MUTED, spaceAfter=18),
        "h1": ParagraphStyle("h1", parent=base, fontName="DejaVu-Bold", fontSize=14, leading=18, spaceBefore=16, spaceAfter=8),
        "h2": ParagraphStyle("h2", parent=base, fontName="DejaVu-Bold", fontSize=11, leading=15, spaceBefore=10, spaceAfter=5),
        "body": base,
        "note": ParagraphStyle("note", parent=base, fontName="DejaVu-Oblique", textColor=MUTED),
        "narrative": ParagraphStyle("narrative", parent=base, backColor=NARRATIVE_BG, borderPadding=(6, 8, 6, 8), leftIndent=2, spaceBefore=4, spaceAfter=10),
        "caption": ParagraphStyle("caption", parent=base, fontSize=8, leading=10, textColor=MUTED, spaceAfter=10),
        "cell": ParagraphStyle("cell", parent=base, fontSize=7.8, leading=9.6, spaceAfter=0),
        "cell_num": ParagraphStyle("cell_num", parent=base, fontSize=7.8, leading=9.6, spaceAfter=0, alignment=TA_RIGHT),
        "cell_head": ParagraphStyle("cell_head", parent=base, fontName="DejaVu-Bold", fontSize=7.8, leading=9.6, spaceAfter=0),
        "kv_key": ParagraphStyle("kv_key", parent=base, textColor=MUTED, spaceAfter=0),
        "kv_value": ParagraphStyle("kv_value", parent=base, spaceAfter=0),
    }


def _p(text: Any, style: ParagraphStyle) -> Paragraph:
    return Paragraph(escape("" if text is None else str(text)).replace("\n", "<br/>"), style)


def _column_widths(block: d.Table, width: float) -> list[float]:
    """Give every column room for its longest single word (so nothing breaks
    mid-word), then share the remaining width in proportion to how much
    more each column's full text would need."""
    pad = 12  # left + right cell padding

    def text_width(text: str, bold: bool = False) -> float:
        return pdfmetrics.stringWidth(text, "DejaVu-Bold" if bold else "DejaVu", 7.8)

    minimum, natural = [], []
    for i, header in enumerate(block.headers):
        cells = [(str(header), True)] + [("" if i >= len(row) or row[i] is None else str(row[i]), False) for row in block.rows]
        minimum.append(max(text_width(word, bold) for text, bold in cells for word in (text.split() or [""])) + pad)
        natural.append(max(text_width(text, bold) for text, bold in cells) + pad)

    if sum(minimum) >= width:
        return [width * m / sum(minimum) for m in minimum]
    spare = width - sum(minimum)
    extra = [n - m for n, m in zip(natural, minimum)]
    if sum(extra) <= spare:
        # Everything fits on one line; spread the leftover evenly.
        return [n + (spare - sum(extra)) / len(natural) for n in natural]
    return [m + spare * e / sum(extra) for m, e in zip(minimum, extra)]


def _table(block: d.Table, styles: dict, width: float) -> list:
    head_style = styles["cell_head"]
    data = [[_p(h, head_style) for h in block.headers]]
    for row in block.rows:
        data.append([_p(v, styles["cell_num"] if i in block.numeric else styles["cell"]) for i, v in enumerate(row)])
    table = Table(data, repeatRows=1, colWidths=_column_widths(block, width))
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
                ("LINEBELOW", (0, 0), (-1, 0), 0.8, INK),
                ("LINEBELOW", (0, 1), (-1, -1), 0.4, RULE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    flow = [table]
    if block.caption:
        flow.append(_p(block.caption, styles["caption"]))
    else:
        flow.append(Spacer(1, 8))
    return flow


def _key_values(block: d.KeyValues, styles: dict, width: float) -> Table:
    table = Table(
        [[_p(k, styles["kv_key"]), _p(v, styles["kv_value"])] for k, v in block.items],
        colWidths=[width * 0.3, width * 0.7],
        hAlign="LEFT",
    )
    table.setStyle(
        TableStyle(
            [
                ("LINEBELOW", (0, 0), (-1, -1), 0.4, RULE),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LEFTPADDING", (0, 0), (0, -1), 0),
            ]
        )
    )
    return table


def _figure(block: d.Figure, styles: dict, width: float) -> list:
    reader = ImageReader(io.BytesIO(block.png))
    px_w, px_h = reader.getSize()
    w = min(block.width_in * inch, width)
    return [Image(io.BytesIO(block.png), width=w, height=w * px_h / px_w), _p(block.caption, styles["caption"])]


def _flowables(block: d.Block, styles: dict, width: float) -> tuple[list, bool]:
    """A block's flowables, and whether they should stay on one page
    together (figures with their caption, short tables)."""
    if isinstance(block, d.Paragraph):
        return [_p(block.text, styles.get(block.style, styles["body"]))], False
    if isinstance(block, d.Bullets):
        return [ListFlowable([ListItem(_p(item, styles["body"]), leftIndent=12) for item in block.items], bulletType="bullet", start="•", leftIndent=12)], False
    if isinstance(block, d.KeyValues):
        return [_key_values(block, styles, width), Spacer(1, 8)], False
    if isinstance(block, d.Table):
        return _table(block, styles, width), len(block.rows) <= 12
    if isinstance(block, d.Figure):
        return _figure(block, styles, width), True
    if isinstance(block, d.PageBreak):
        return [PageBreak()], False
    return [], False


def render_pdf(doc: d.Document) -> bytes:
    _register_fonts()
    styles = _styles()
    buffer = io.BytesIO()
    margin = 18 * mm

    def decorate(canvas, pdf_doc):
        canvas.saveState()
        canvas.setFont("DejaVu", 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(margin, 10 * mm, f"{doc.title} — {doc.subtitle}")
        canvas.drawRightString(A4[0] - margin, 10 * mm, f"Page {pdf_doc.page}")
        canvas.restoreState()

    pdf = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=margin, rightMargin=margin, topMargin=margin, bottomMargin=20 * mm, title=f"{doc.title} — {doc.subtitle}")
    width = A4[0] - 2 * margin

    story: list = [_p(doc.title, styles["title"]), _p(doc.subtitle, styles["subtitle"]), _key_values(d.KeyValues(doc.meta), styles, width), PageBreak()]
    pending_headings: list = []  # headings waiting to be kept with the block after them
    for block in doc.blocks:
        if isinstance(block, d.Heading):
            pending_headings.append(_p(block.text, styles["h1" if block.level == 1 else "h2"]))
            continue
        flows, keep = _flowables(block, styles, width)
        if not flows:
            continue
        # One flat KeepTogether per group: nesting them makes reportlab
        # treat the inner group as unsplittable and break the page early.
        if keep:
            story.append(KeepTogether([*pending_headings, *flows]))
        elif pending_headings:
            story.extend([KeepTogether([*pending_headings, flows[0]]), *flows[1:]])
        else:
            story.extend(flows)
        pending_headings = []
    story.extend(pending_headings)

    pdf.build(story, onFirstPage=decorate, onLaterPages=decorate)
    return buffer.getvalue()


def build_pdf_report(data: dict) -> bytes:
    return render_pdf(build_document(data))
