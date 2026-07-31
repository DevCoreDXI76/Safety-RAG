"""
저장된 프로젝트 기록(record["draft"]의 Markdown 텍스트)을 파싱해
python-hwpx 문서로 바인딩하고, .hwpx 파일 바이트를 반환한다.

셀 스타일(열너비 비율/헤더·위험등급 배경색/헤더별 정렬)은 document_styles.py의
문서유형별 스펙을 XLSX(export_xlsx.py)·PDF(export_pdf.py)와 공유한다
(docs/superpowers/specs/2026-07-31-공유-스타일-스펙-design.md). 표 폭은 페이지
폭에 맞춘다 — 지정하지 않으면 python-hwpx가 열 개수 x 고정폭(7200 유닛)으로
표를 만들어, 위험성평가표처럼 열이 많은 표는 페이지 폭을 넘어 잘리고 반대로
열이 적은 표는 페이지 폭의 일부만 채우는 문제가 있었다. 볼드체·헤더 흰 글자는
검증된 문자색 API를 찾지 못해 이번 스코프에서 제외했다 — 배경색·열비율·정렬만
XLSX와 맞춘다.
"""

from hwpx import HwpxDocument

from document_styles import (
    AI_SCORE_FOOTNOTE, base_header, cell_style_decision, get_style,
    parse_ai_score_cell, resolve_column_weights, risk_grade_column_indices,
)
from markdown_tables import parse_markdown_tables

_HWP_UNITS_PER_MM = 7200 / 25.4
_PAGE_MARGIN_MM = 15
_PAGE_WIDTH_MM = 297  # A4 landscape


def record_to_hwpx_bytes(record):
    """
    record["draft"]에서 Markdown 표를 순서대로 파싱해 표로 채운다.
    표가 없으면 draft 원문을 문단 하나로 그대로 넣는다(XLSX의 "표 없으면
    원문 그대로" 규칙과 동일 취지).
    """
    tables = parse_markdown_tables(record["draft"])
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

    if not tables:
        doc.add_paragraph(record["draft"])
        return doc.to_bytes()

    # 문서 전체에서 재사용할 정렬 문단속성 id. ensure_paragraph_alignment는
    # 같은 정렬이면 기존 id를 재사용하므로 문서당 한 번씩만 만들면 된다.
    # left_para_id를 명시적으로 지정하지 않으면 왼쪽정렬 셀이 문서 기본
    # 문단속성(JUSTIFY)을 그대로 물려받아 XLSX(horizontal="left")·
    # PDF(TA_LEFT)와 어긋난다.
    center_para_id = doc.headers[0].ensure_paragraph_alignment("CENTER")
    left_para_id = doc.headers[0].ensure_paragraph_alignment("LEFT")

    for table in tables:
        rows = len(table)
        cols = max(len(row) for row in table)
        is_kv_table = cols == 2
        headers_base = [base_header(h) for h in table[0]]
        risk_cols = [] if is_kv_table else risk_grade_column_indices(style, headers_base)

        # width를 지정해야 열 너비가 usable_width 안에서 균등 분배된다
        # (_distribute_size) — 미지정 시 열 개수와 무관하게 고정폭이 쓰인다.
        hwpx_table = doc.add_table(rows, cols, width=usable_width)
        hwpx_table.set_column_widths(resolve_column_weights(style, cols))
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
                cell.set_text(text)
                # set_text 직후에도 셀의 첫 문단은 그대로 유지된다(비어 있어도
                # 항상 1개 존재) — add_paragraph로 새로 추가하면 빈 문단이
                # 하나 더 생겨 텍스트 앞에 빈 줄이 생기므로, 기존 첫 문단의
                # 정렬 속성만 바꿔치기한다. center든 아니든 항상 명시적으로
                # 지정해야 한다 — 그렇지 않으면 문서 기본 문단속성(JUSTIFY)을
                # 물려받아 XLSX/PDF의 왼쪽정렬과 어긋난다.
                cell.paragraphs[0].para_pr_id_ref = center_para_id if center else left_para_id
                if fill_hex:
                    hwpx_table.set_cell_shading(row_index, col_index, fill_hex)

        doc.add_paragraph("")
        if ai_value_present:
            doc.add_paragraph(AI_SCORE_FOOTNOTE)
            doc.add_paragraph("")

    return doc.to_bytes()
