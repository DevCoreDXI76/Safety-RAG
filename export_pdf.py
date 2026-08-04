"""
저장된 프로젝트 기록(record["draft"]의 Markdown 텍스트)을 파싱해
reportlab으로 PDF 바이트를 반환한다.

한글은 reportlab 내장 CID 폰트(HYSMyeongJo-Medium)로 렌더링한다 — 별도
TTF 폰트 파일을 저장소에 넣지 않아도 Railway(Linux) 환경에서 그대로
동작한다(docs/superpowers/specs/2026-07-28-hwpx-pdf-export-design.md에서
로컬 렌더링 + pypdf 텍스트 추출로 확인 완료).

셀 스타일(열너비 비율/헤더·위험등급 배경색/헤더별 정렬)은 document_styles.py의
문서유형별 스펙을 XLSX(export_xlsx.py)·HWPX(export_hwpx.py)와 공유한다
(docs/superpowers/specs/2026-07-31-공유-스타일-스펙-design.md). 볼드체·헤더
흰 글자는 CID 폰트에 검증된 볼드 변형이 없어 이번 스코프에서 제외했다 —
배경색·열비율·정렬만 XLSX와 맞춘다.
"""

import io
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from document_styles import (
    AI_SCORE_FOOTNOTE, base_header, cell_style_decision, get_style,
    parse_ai_score_cell, resolve_column_weights, risk_grade_column_indices,
)
from markdown_tables import parse_markdown_tables

_FONT_NAME = "HYSMyeongJo-Medium"
pdfmetrics.registerFont(UnicodeCIDFont(_FONT_NAME))

_TITLE_STYLE = ParagraphStyle("title", fontName=_FONT_NAME, fontSize=14, leading=18, spaceAfter=12)
_BODY_STYLE = ParagraphStyle("body", fontName=_FONT_NAME, fontSize=10.5, leading=15)
_CELL_STYLE_LEFT = ParagraphStyle("cell_left", fontName=_FONT_NAME, fontSize=9, leading=11, alignment=TA_LEFT)
_CELL_STYLE_CENTER = ParagraphStyle("cell_center", fontName=_FONT_NAME, fontSize=9, leading=11, alignment=TA_CENTER)
_FOOTNOTE_STYLE = ParagraphStyle("footnote", fontName=_FONT_NAME, fontSize=8, leading=10, textColor=colors.grey)

_BASE_TABLE_STYLE_COMMANDS = [
    ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
    ("FONTNAME", (0, 0), (-1, -1), _FONT_NAME),
    ("FONTSIZE", (0, 0), (-1, -1), 9),
    ("VALIGN", (0, 0), (-1, -1), "TOP"),
]

# 셀 하나가 페이지 하나보다 커지는 걸 막는 안전 상한(줄 수). document_styles의
# 열비율은 특정 열 개수를 염두에 두고 정한 값이라, 그 열 개수를 벗어나는 표
# (예: 4열 기준 스펙에 12열 표가 들어오면 8개 열이 DEFAULT_COLUMN_WIDTH로
# 채워지며 1열이 극도로 좁아짐)에서 셀 텍스트가 조금만 길어도 reportlab이
# LayoutError로 PDF 생성 자체를 실패시킨다(2026-08-04 베타1 실기기 테스트에서
# 실제 발생·재현·확인, test_export_pdf.py 참고).
_MAX_CELL_LINES = 24


def _hex_color(hex_str):
    return colors.HexColor("#" + hex_str)


def _fit_cell_text(text, col_width, font_size):
    """
    셀 폭 대비 텍스트가 _MAX_CELL_LINES줄을 넘어갈 만큼 길면 잘라낸다.
    CID 폰트(한글 완전폭)에서 글자당 폭 ≈ font_size이므로 이를 그대로
    글자당 폭 근사치로 쓴다.
    """
    chars_per_line = max(1, int(col_width / font_size))
    max_chars = chars_per_line * _MAX_CELL_LINES
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"


def _build_table_element(table, frame_width, document_type):
    """
    Markdown에서 파싱한 표 1개(list[list[str]])를 프레임 폭에 맞춰 wrap되는
    Table 플로어블로 만든다. document_styles의 문서유형별 열비율·헤더/위험등급
    배경색·헤더별 정렬을 적용하고, AI 제안값이 하나라도 있었는지 함께 반환한다.
    """
    ncols = max(len(row) for row in table)
    style = get_style(document_type)

    weights = resolve_column_weights(style, ncols)
    total_weight = sum(weights)
    col_widths = [frame_width * w / total_weight for w in weights]

    is_kv_table = ncols == 2
    headers_base = [base_header(h) for h in table[0]]
    risk_cols = [] if is_kv_table else risk_grade_column_indices(style, headers_base)

    table_style_commands = list(_BASE_TABLE_STYLE_COMMANDS)
    data = []
    ai_value_present = False

    for row_index, row in enumerate(table):
        is_header_row = row_index == 0
        row_cells = []
        for col_index in range(ncols):
            raw = row[col_index] if col_index < len(row) else ""
            value, note = parse_ai_score_cell(raw)
            text = str(value) if value is not None else raw
            if note:
                ai_value_present = True

            center, fill_hex = cell_style_decision(
                style, headers_base, risk_cols, is_kv_table, is_header_row, col_index, text
            )
            cell_style = _CELL_STYLE_CENTER if center else _CELL_STYLE_LEFT
            safe_text = _fit_cell_text(text, col_widths[col_index], cell_style.fontSize)
            row_cells.append(Paragraph(escape(safe_text), cell_style))

            if fill_hex:
                table_style_commands.append(
                    ("BACKGROUND", (col_index, row_index), (col_index, row_index), _hex_color(fill_hex))
                )
        data.append(row_cells)

    # repeatRows=1: 표가 페이지 경계를 넘어가면 0번째 행(헤더)을 다음
    # 페이지에도 반복해서 그린다.
    table_flowable = Table(
        data, colWidths=col_widths, style=TableStyle(table_style_commands), repeatRows=1
    )
    return table_flowable, ai_value_present


def record_to_pdf_bytes(record):
    """
    record["draft"]에서 Markdown 표를 순서대로 파싱해 표로 채운다.
    표가 없으면 draft 원문을 문단 하나로 그대로 넣는다(XLSX/HWPX와 동일 규칙).
    표 셀은 Paragraph로 감싸 렌더링하므로 원문을 그대로 넣기 전에 escape()한다.
    """
    tables = parse_markdown_tables(record["draft"])
    document_type = record["document_type"]

    buffer = io.BytesIO()
    # title/author: reportlab이 PDF 메타데이터(Author/Title)에 그대로 채워
    # 넣는 표준 생성자 인자 — 이전 QA에서 지적된 "메타데이터 공란" 문제 해결.
    doc = SimpleDocTemplate(
        buffer, pagesize=landscape(A4),
        title=document_type, author="Safety-RAG",
    )
    elements = [Paragraph(escape(document_type), _TITLE_STYLE), Spacer(1, 12)]

    if not tables:
        body_text = escape(record["draft"]).replace("\n", "<br/>")
        elements.append(Paragraph(body_text, _BODY_STYLE))
    else:
        for table in tables:
            table_flowable, ai_value_present = _build_table_element(table, doc.width, document_type)
            elements.append(table_flowable)
            if ai_value_present:
                elements.append(Spacer(1, 4))
                elements.append(Paragraph(AI_SCORE_FOOTNOTE, _FOOTNOTE_STYLE))
            elements.append(Spacer(1, 12))

    doc.build(elements)
    return buffer.getvalue()
