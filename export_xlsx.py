"""
저장된 프로젝트 기록(record["draft"]의 Markdown 텍스트)을 파싱해
openpyxl 워크북으로 바인딩하고, xlsx 파일 바이트를 반환한다.

셀 스타일(열너비/줄바꿈/테두리/조건부서식/인쇄설정)은 docs/샘플문서/의 5개
서식목업(위험성평가표·표준 작업계획서·TBM 일지·안전보건교육일지·
산업안전보건관리비 사용명세서)을 실측해 그대로 반영했다.
"""

import io
import re

from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from document_styles import (
    DEFAULT_COLUMN_WIDTH, base_header, get_style, parse_ai_score_cell,
    CENTER_ALIGN_HEADERS,
)
from markdown_tables import parse_markdown_blocks

_HEADER_FONT = Font(bold=True)
_BOX_TITLE_FONT = Font(size=18, bold=True, color="000000")
_ALIGN_TITLE = Alignment(horizontal="left", vertical="center")

_THIN_SIDE = Side(style="thin")
_THIN_BORDER = Border(left=_THIN_SIDE, right=_THIN_SIDE, top=_THIN_SIDE, bottom=_THIN_SIDE)

_ALIGN_CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)
_ALIGN_LEFT_CENTER = Alignment(horizontal="left", vertical="center", wrap_text=True)
_ALIGN_LEFT_TOP = Alignment(horizontal="left", vertical="top", wrap_text=True)

_INVALID_SHEET_CHARS_RE = re.compile(r"[:\\/?*\[\]]")
_COMMENT_AUTHOR = "safety-rag"


def _fill(hex_color):
    return PatternFill(start_color=hex_color, end_color=hex_color, fill_type="solid")


def _sheet_title(document_type):
    """엑셀 시트명 제약(31자 이내, : \\ / ? * [ ] 금지)을 만족하도록 정리한다."""
    cleaned = _INVALID_SHEET_CHARS_RE.sub("", document_type)
    return cleaned[:31] or "문서"


def _apply_print_settings(ws, title_row=None):
    """5개 서식목업 공통 인쇄설정: 가로방향, 폭 1페이지 맞춤, 여백."""
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_margins.left = 0.75
    ws.page_margins.right = 0.75
    ws.page_margins.top = 1.0
    ws.page_margins.bottom = 1.0
    ws.page_margins.header = 0.5
    ws.page_margins.footer = 0.5
    if title_row is not None:
        ws.print_title_rows = f"{title_row}:{title_row}"


def record_to_xlsx_bytes(record):
    """
    record["draft"]에서 헤딩(박스 제목)·표·서술형 문단을 순서대로 시트에
    채운다. 표가 여러 개면 표 사이에 빈 행 하나를 둔다. draft가 완전히
    비어있는 경우(이론상 거의 없음)만 원문 그대로 A1에 넣는다.
    """
    blocks = parse_markdown_blocks(record["draft"])
    style = get_style(record["document_type"])

    header_fill = _fill(style.header_fill)
    data_header_font = Font(bold=True, color=style.header_font_color)
    kv_header_fill = _fill(style.kv_header_fill)
    risk_fills = {grade: _fill(hex_color) for grade, hex_color in style.risk_grade_colors.items()}

    wb = Workbook()
    ws = wb.active
    ws.title = _sheet_title(record["document_type"])

    if not blocks:
        ws.cell(row=1, column=1, value=record["draft"])
        _apply_print_settings(ws)
        buffer = io.BytesIO()
        wb.save(buffer)
        return buffer.getvalue()

    # 박스 가로 크기를 모든 표가 동일하게 쓰도록, 시트 전체에서 가장 열이 많은
    # 표 기준으로 폭을 맞춘다(2026-08-05 요청) — kv표(항목/내용, 2열)의 "내용"
    # 칸은 이 값까지 병합해서 다른 표와 박스 너비가 맞아 보이게 한다.
    table_blocks = [b for b in blocks if b["type"] == "table"]
    max_col_count = max((len(row) for tb in table_blocks for row in tb["rows"]), default=1)

    column_widths = list(style.column_widths)
    current_row = 1
    table_index = 0
    freeze_row = None
    risk_score_ranges = []  # (col_letter, first_data_row, last_data_row)

    for block in blocks:
        if block["type"] == "heading":
            title_cell = ws.cell(row=current_row, column=1, value=block["text"])
            title_cell.font = _BOX_TITLE_FONT
            title_cell.alignment = _ALIGN_TITLE
            if max_col_count > 1:
                ws.merge_cells(
                    start_row=current_row, start_column=1, end_row=current_row, end_column=max_col_count
                )
            current_row += 1
            continue

        if block["type"] == "text":
            text_cell = ws.cell(row=current_row, column=1, value=block["text"])
            text_cell.alignment = _ALIGN_LEFT_TOP
            if max_col_count > 1:
                ws.merge_cells(
                    start_row=current_row, start_column=1, end_row=current_row, end_column=max_col_count
                )
            current_row += 2  # 다음 블록과 구분되도록 빈 행 하나
            continue

        table = block["rows"]
        header_row = current_row
        headers_base = [base_header(h) for h in table[0]]
        is_kv_table = len(table[0]) == 2
        risk_grade_col_idxs = []
        if not is_kv_table:
            for idx, header_text in enumerate(headers_base, start=1):
                if header_text in style.risk_grade_headers:
                    risk_grade_col_idxs.append(idx)

        for row_offset, row_cells in enumerate(table):
            is_header = row_offset == 0
            for col_idx, value in enumerate(row_cells, start=1):
                number, note = parse_ai_score_cell(value)
                cell = ws.cell(
                    row=current_row, column=col_idx,
                    value=number if number is not None else value,
                )
                if note:
                    cell.comment = Comment(note, _COMMENT_AUTHOR)
                cell.border = _THIN_BORDER

                if is_kv_table:
                    if col_idx == 1:
                        cell.font = _HEADER_FONT
                        cell.fill = kv_header_fill
                        cell.alignment = _ALIGN_CENTER
                    else:
                        if is_header:
                            cell.font = _HEADER_FONT
                            cell.fill = kv_header_fill
                        cell.alignment = _ALIGN_LEFT_CENTER
                elif is_header:
                    cell.font = data_header_font
                    cell.fill = header_fill
                    cell.alignment = _ALIGN_CENTER
                else:
                    header_text = headers_base[col_idx - 1] if col_idx - 1 < len(headers_base) else ""
                    cell.alignment = (
                        _ALIGN_CENTER if header_text.lower() in CENTER_ALIGN_HEADERS else _ALIGN_LEFT_TOP
                    )

            if is_kv_table and max_col_count > 2:
                ws.merge_cells(
                    start_row=current_row, start_column=2, end_row=current_row, end_column=max_col_count
                )

            current_row += 1

            if table_index == 1 and is_header:
                freeze_row = current_row

        if risk_grade_col_idxs and len(table) > 1:
            for idx in risk_grade_col_idxs:
                risk_score_ranges.append((get_column_letter(idx), header_row + 1, current_row - 1))

        table_index += 1
        current_row += 1  # 표 사이 빈 행

    if freeze_row is None:
        freeze_row = 2

    while len(column_widths) < max_col_count:
        column_widths.append(DEFAULT_COLUMN_WIDTH)
    for col_idx in range(1, max_col_count + 1):
        ws.column_dimensions[get_column_letter(col_idx)].width = column_widths[col_idx - 1]

    ws.freeze_panes = f"A{freeze_row}"

    for col_letter, first_row, last_row in risk_score_ranges:
        cell_range = f"{col_letter}{first_row}:{col_letter}{last_row}"
        for grade, fill in risk_fills.items():
            ws.conditional_formatting.add(
                cell_range, CellIsRule(operator="equal", formula=[f'"{grade}"'], fill=fill)
            )

    _apply_print_settings(ws, title_row=freeze_row - 1)

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
