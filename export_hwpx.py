"""
저장된 프로젝트 기록(record["draft"]의 Markdown 텍스트)을 파싱해
python-hwpx 문서로 바인딩하고, .hwpx 파일 바이트를 반환한다.

셀 스타일(열너비 비율/헤더·위험등급 배경색/헤더별 정렬)은 document_styles.py의
문서유형별 스펙을 XLSX(export_xlsx.py)·PDF(export_pdf.py)와 공유한다
(docs/superpowers/specs/2026-07-31-공유-스타일-스펙-design.md). 표 폭은 페이지
폭에 맞춘다 — 지정하지 않으면 python-hwpx가 열 개수 x 고정폭(7200 유닛)으로
표를 만들어, 위험성평가표처럼 열이 많은 표는 페이지 폭을 넘어 잘리고 반대로
열이 적은 표는 페이지 폭의 일부만 채우는 문제가 있었다.

2026-08-05: 실기기 검증 순서(PDF→XLSX→HWPX)상 HWPX 차례가 이제 와서,
PDF/XLSX가 그 사이 실기기 피드백으로 먼저 얻은 개선 3가지를 포팅한다 —
(1) 박스 제목(헤딩)·서술형 문단 보존(parse_markdown_tables만 쓰던 탓에
표 없는 헤딩·문단이 통째로 버려지고 있었음), (2) 위험성평가표 콘텐츠 기반
열너비, (3) "(빈칸 - 현장 기재)"류 플레이스홀더 회색 처리. 문자색·볼드는
add_run(bold=, color=)로 가능함을 이번에 확인했다 — 이전 주석의 "검증된
문자색 API를 찾지 못함"은 해소됨. 다만 XLSX 전용 개념인 인쇄배율(엑셀
시트 %)·틀고정은 워드프로세서 자동 페이지네이션 특성상 이식 대상이 아니다.
"""

import re
import unicodedata

from hwpx import HwpxDocument

from document_styles import (
    AI_SCORE_FOOTNOTE, base_header, cell_style_decision, get_style,
    parse_ai_score_cell, resolve_column_weights, risk_grade_column_indices,
)
from markdown_tables import parse_markdown_blocks

_HWP_UNITS_PER_MM = 7200 / 25.4
_PAGE_MARGIN_MM = 15
_PAGE_WIDTH_MM = 297  # A4 landscape

# PDF(fac4312)/XLSX와 동일하게 박스 제목 16pt·굵게, 본문/표 셀 12pt.
_BOX_TITLE_SIZE = 16
_BODY_SIZE = 12

# "(빈칸 - 현장 기재)"류 플레이스홀더는 실제 내용이 아니라 안내문이므로
# PDF(export_pdf.py의 _PLACEHOLDER_RE)/XLSX와 동일하게 연한 회색으로 구분해
# 표시한다.
_PLACEHOLDER_RE = re.compile(r"\([^()]*빈칸[^()]*\)")
_PLACEHOLDER_COLOR = "#999999"

# XLSX(export_xlsx.py)와 동일하게 위험성평가표만 콘텐츠 기반 열너비를 쓴다.
# 다른 문서유형은 계속 document_styles.py의 정적 비율(resolve_column_weights)을
# 쓴다.
_CONTENT_AWARE_WIDTH_DOCUMENT_TYPES = {"위험성평가표"}
_LINE_BREAK_RE = re.compile(r"\n")


def _text_width_units(text):
    """XLSX(export_xlsx.py)의 _text_width_units와 동일한 근사치 — 한글 등
    전각 문자는 2칸, 그 외(영문·숫자 등)는 1칸으로 계산한 가장 넓은 줄의 폭."""
    lines = _LINE_BREAK_RE.split(text) if text else [""]
    widest = 1
    for line in lines:
        units = sum(2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1 for ch in line)
        widest = max(widest, units)
    return widest


def _content_aware_weights(tables, ncols):
    """표 전체에서 각 열의 실제 표시 값(AI 안내문 제거 후) 중 가장 넓은
    내용을 기준으로 열 가중치를 정한다(XLSX의 _content_aware_excel_widths와
    동일 취지). parse_ai_score_cell로 순수값만 재야 한다 — 원본 마크다운
    셀에는 "B(AI 제안값, 현장 확인 필수)"처럼 안내문이 붙어 있어, 그대로
    재면 실제로 한 글자만 들어가는 열(위험등급 등)이 크게 부풀려진다."""
    weights = [1] * ncols
    for rows in tables:
        for row in rows:
            for col in range(min(len(row), ncols)):
                number, _note = parse_ai_score_cell(row[col])
                measure_text = str(number) if number is not None else row[col]
                weights[col] = max(weights[col], _text_width_units(measure_text))
    return weights


def _add_styled_text(paragraph, text, *, bold=False, size=None):
    """플레이스홀더("(빈칸 - 현장 기재)"류)만 회색으로, 나머지는 기본 색으로
    text를 여러 run으로 쪼개 문단에 추가한다. 플레이스홀더가 없으면 run 1개."""
    last_end = 0
    added_any = False
    for m in _PLACEHOLDER_RE.finditer(text):
        if m.start() > last_end:
            paragraph.add_run(text[last_end:m.start()], bold=bold, size=size)
            added_any = True
        paragraph.add_run(m.group(0), bold=bold, size=size, color=_PLACEHOLDER_COLOR)
        added_any = True
        last_end = m.end()
    if last_end < len(text) or not added_any:
        paragraph.add_run(text[last_end:], bold=bold, size=size)


def record_to_hwpx_bytes(record):
    """
    record["draft"]에서 헤딩(박스 제목)·표·서술형 문단을 순서대로 문서에
    채운다(PDF/XLSX와 동일 취지 — parse_markdown_blocks 사용). 표가
    하나도 없으면 draft 원문을 문단 하나로 그대로 넣는다(XLSX의 "표 없으면
    원문 그대로" 규칙과 동일 취지).
    """
    blocks = parse_markdown_blocks(record["draft"])
    document_type = record["document_type"]
    style = get_style(document_type)

    doc = HwpxDocument.new()
    # 위험성평가표 등 열이 많은 문서를 고려해 export_pdf.py와 동일하게
    # 가로(landscape) A4를 기본값으로 쓴다.
    doc.set_page_setup(
        paper_size="A4",
        orientation="landscape",
        margins_mm={
            "left": _PAGE_MARGIN_MM, "right": _PAGE_MARGIN_MM,
            "top": _PAGE_MARGIN_MM, "bottom": _PAGE_MARGIN_MM,
        },
    )
    usable_width = round((_PAGE_WIDTH_MM - 2 * _PAGE_MARGIN_MM) * _HWP_UNITS_PER_MM)

    doc.add_paragraph(document_type)
    doc.add_paragraph("")

    if not blocks:
        doc.add_paragraph(record["draft"])
        return doc.to_bytes()

    # 문서 전체에서 재사용할 정렬 문단속성 id. ensure_paragraph_alignment는
    # 같은 정렬이면 기존 id를 재사용하므로 문서당 한 번씩만 만들면 된다.
    # left_para_id를 명시적으로 지정하지 않으면 왼쪽정렬 셀/문단이 문서 기본
    # 문단속성(JUSTIFY)을 그대로 물려받아 XLSX(horizontal="left")·
    # PDF(TA_LEFT)와 어긋난다.
    center_para_id = doc.headers[0].ensure_paragraph_alignment("CENTER")
    left_para_id = doc.headers[0].ensure_paragraph_alignment("LEFT")

    table_blocks = [b["rows"] for b in blocks if b["type"] == "table"]
    max_col_count = max((len(row) for rows in table_blocks for row in rows), default=1)
    content_aware = document_type in _CONTENT_AWARE_WIDTH_DOCUMENT_TYPES

    for block in blocks:
        if block["type"] == "heading":
            p = doc.add_paragraph("", include_run=False, para_pr_id_ref=left_para_id)
            _add_styled_text(p, block["text"], bold=True, size=_BOX_TITLE_SIZE)
            continue

        if block["type"] == "text":
            p = doc.add_paragraph("", include_run=False, para_pr_id_ref=left_para_id)
            _add_styled_text(p, block["text"], size=_BODY_SIZE)
            doc.add_paragraph("")
            continue

        table = block["rows"]
        rows = len(table)
        cols = max(len(row) for row in table)
        is_kv_table = cols == 2
        headers_base = [base_header(h) for h in table[0]]
        risk_cols = [] if is_kv_table else risk_grade_column_indices(style, headers_base)

        if content_aware:
            weights = _content_aware_weights(table_blocks, cols)
        else:
            weights = resolve_column_weights(style, cols)

        # width를 지정해야 열 너비가 usable_width 안에서 균등 분배된다
        # (_distribute_size) — 미지정 시 열 개수와 무관하게 고정폭이 쓰인다.
        hwpx_table = doc.add_table(rows, cols, width=usable_width)
        hwpx_table.set_column_widths(weights)
        # 표가 페이지 경계를 넘어갈 때 헤더 행(0번째 행)이 다음 페이지에도
        # 반복되도록 한다.
        hwpx_table.element.set("repeatHeader", "1")

        ai_value_present = False
        for row_index, row_cells in enumerate(table):
            is_header_row = row_index == 0
            for col_index in range(cols):
                raw = row_cells[col_index] if col_index < len(row_cells) else ""
                value, note = parse_ai_score_cell(raw)
                text = str(value) if value is not None else raw
                if note:
                    ai_value_present = True

                center, fill_hex = cell_style_decision(
                    style, headers_base, risk_cols, is_kv_table, is_header_row, col_index, text
                )

                cell = hwpx_table.cell(row_index, col_index)
                p = cell.paragraphs[0]
                p.clear_text()
                # center든 아니든 항상 명시적으로 지정해야 한다 — 그렇지
                # 않으면 문서 기본 문단속성(JUSTIFY)을 물려받아 XLSX/PDF의
                # 왼쪽정렬과 어긋난다.
                p.para_pr_id_ref = center_para_id if center else left_para_id
                _add_styled_text(p, text, bold=is_header_row, size=_BODY_SIZE)
                if fill_hex:
                    hwpx_table.set_cell_shading(row_index, col_index, fill_hex)

        doc.add_paragraph("")
        if ai_value_present:
            doc.add_paragraph(AI_SCORE_FOOTNOTE)
            doc.add_paragraph("")

    return doc.to_bytes()
