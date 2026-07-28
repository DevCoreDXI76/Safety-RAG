"""
저장된 프로젝트 기록(record["draft"]의 Markdown 텍스트)을 파싱해
reportlab으로 PDF 바이트를 반환한다.

한글은 reportlab 내장 CID 폰트(HYSMyeongJo-Medium)로 렌더링한다 — 별도
TTF 폰트 파일을 저장소에 넣지 않아도 Railway(Linux) 환경에서 그대로
동작한다(docs/superpowers/specs/2026-07-28-hwpx-pdf-export-design.md에서
로컬 렌더링 + pypdf 텍스트 추출로 확인 완료).
"""

import io
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from markdown_tables import parse_markdown_tables

_FONT_NAME = "HYSMyeongJo-Medium"
pdfmetrics.registerFont(UnicodeCIDFont(_FONT_NAME))

_TITLE_STYLE = ParagraphStyle("title", fontName=_FONT_NAME, fontSize=14, leading=18, spaceAfter=12)
_BODY_STYLE = ParagraphStyle("body", fontName=_FONT_NAME, fontSize=10.5, leading=15)

_TABLE_STYLE = TableStyle([
    ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
    ("FONTNAME", (0, 0), (-1, -1), _FONT_NAME),
    ("FONTSIZE", (0, 0), (-1, -1), 9),
    ("VALIGN", (0, 0), (-1, -1), "TOP"),
])


def record_to_pdf_bytes(record):
    """
    record["draft"]에서 Markdown 표를 순서대로 파싱해 표로 채운다.
    표가 없으면 draft 원문을 문단 하나로 그대로 넣는다(XLSX/HWPX와 동일 규칙).
    표 셀은 Table이 리터럴로 그리므로 이스케이프하지 않지만, 문단(Paragraph)은
    내부적으로 미니 XML을 해석하므로 원문을 그대로 넣기 전에 escape()한다.
    """
    tables = parse_markdown_tables(record["draft"])

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4))
    elements = [Paragraph(escape(record["document_type"]), _TITLE_STYLE), Spacer(1, 12)]

    if not tables:
        body_text = escape(record["draft"]).replace("\n", "<br/>")
        elements.append(Paragraph(body_text, _BODY_STYLE))
    else:
        for table in tables:
            elements.append(Table(table, style=_TABLE_STYLE))
            elements.append(Spacer(1, 12))

    doc.build(elements)
    return buffer.getvalue()
