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
_CELL_STYLE = ParagraphStyle("cell", fontName=_FONT_NAME, fontSize=9, leading=11)

_TABLE_STYLE = TableStyle([
    ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
    ("FONTNAME", (0, 0), (-1, -1), _FONT_NAME),
    ("FONTSIZE", (0, 0), (-1, -1), 9),
    ("VALIGN", (0, 0), (-1, -1), "TOP"),
])


def _build_table_element(table, frame_width):
    """
    Markdown에서 파싱한 표 1개(list[list[str]])를 프레임 폭에 맞춰 wrap되는
    Table 플로어블로 만든다. 셀을 Paragraph로 감싸 텍스트를 줄바꿈하고,
    colWidths를 frame_width에 맞춰 명시적으로 지정해 표가 페이지 폭을
    넘어가지 않게 한다(콘텐츠 폭을 넘기면 reportlab이 원본 문자열 폭 그대로
    렌더링해 좌우가 잘려나가는 문제 방지).
    """
    ncols = max(len(row) for row in table)
    col_width = frame_width / ncols
    data = [
        [Paragraph(escape(c), _CELL_STYLE) for c in row]
        + [Paragraph("", _CELL_STYLE)] * (ncols - len(row))
        for row in table
    ]
    return Table(data, colWidths=[col_width] * ncols, style=_TABLE_STYLE)


def record_to_pdf_bytes(record):
    """
    record["draft"]에서 Markdown 표를 순서대로 파싱해 표로 채운다.
    표가 없으면 draft 원문을 문단 하나로 그대로 넣는다(XLSX/HWPX와 동일 규칙).
    표 셀은 Paragraph로 감싸 렌더링하므로 원문을 그대로 넣기 전에 escape()한다.
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
            elements.append(_build_table_element(table, doc.width))
            elements.append(Spacer(1, 12))

    doc.build(elements)
    return buffer.getvalue()
