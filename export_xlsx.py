"""
저장된 프로젝트 기록(record["draft"]의 Markdown 텍스트)을 파싱해
openpyxl 워크북으로 바인딩하고, xlsx 파일 바이트를 반환한다.

셀 스타일(열너비/줄바꿈/테두리/조건부서식/인쇄설정)은 docs/샘플문서/의 5개
서식목업(위험성평가표·표준 작업계획서·TBM 일지·안전보건교육일지·
산업안전보건관리비 사용명세서)을 실측해 그대로 반영했다.
"""

import io
import re
import unicodedata

from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from document_styles import (
    AI_SCORE_FOOTNOTE, DEFAULT_COLUMN_WIDTH, base_header, get_style, parse_ai_score_cell,
    CENTER_ALIGN_HEADERS,
)
from markdown_tables import parse_markdown_blocks

_TITLE_FONT = Font(size=28, bold=True, underline="single")
_ALIGN_TITLE_DOC = Alignment(horizontal="center", vertical="center")

_BOX_TITLE_FONT = Font(size=16, bold=True, color="000000")
_ALIGN_TITLE = Alignment(horizontal="left", vertical="center")

_BODY_FONT_SIZE = 12
_HEADER_FONT = Font(size=_BODY_FONT_SIZE, bold=True)
_BODY_FONT = Font(size=_BODY_FONT_SIZE)
_FOOTNOTE_FONT = Font(size=9, color="808080")
_ALIGN_FOOTNOTE = Alignment(horizontal="left", vertical="center")

_THIN_SIDE = Side(style="thin")
_THIN_BORDER = Border(left=_THIN_SIDE, right=_THIN_SIDE, top=_THIN_SIDE, bottom=_THIN_SIDE)

_ALIGN_CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)
_ALIGN_LEFT_CENTER = Alignment(horizontal="left", vertical="center", wrap_text=True)
_ALIGN_LEFT_TOP = Alignment(horizontal="left", vertical="top", wrap_text=True)

_INVALID_SHEET_CHARS_RE = re.compile(r"[:\\/?*\[\]]")
_COMMENT_AUTHOR = "safety-rag"

# 모든 내용을 B열부터 쓰고 A열은 공란(여백)으로 남긴다(2026-08-05 요청).
_COL_OFFSET = 1
_COL_A_WIDTH = 3

_CONTENT_AWARE_WIDTH_DOCUMENT_TYPES = {"위험성평가표"}
_MIN_EXCEL_COL_WIDTH = 6
_MAX_EXCEL_COL_WIDTH = 60
_EXCEL_COL_WIDTH_PADDING = 2
_LINE_BREAK_RE = re.compile(r"<br\s*/?>|\n")


def _text_width_units(text):
    """한글 등 전각 문자는 2칸, 그 외(영문·숫자 등)는 1칸으로 계산한 근사 폭."""
    lines = _LINE_BREAK_RE.split(text) if text else [""]
    widest = 0
    for line in lines:
        units = sum(2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1 for ch in line)
        widest = max(widest, units)
    return widest


def _content_aware_excel_widths(table_blocks, ncols):
    """
    표 전체(같은 열 위치를 공유하는 모든 표)에서 각 열의 가장 넓은 셀 내용을
    기준으로 엑셀 열 폭을 정한다(2026-08-05 요청, 위험성평가표 전용).
    """
    widths = [_MIN_EXCEL_COL_WIDTH] * ncols
    for tb in table_blocks:
        for row in tb["rows"]:
            for col in range(min(len(row), ncols)):
                widths[col] = max(widths[col], _text_width_units(row[col]))
    return [min(w + _EXCEL_COL_WIDTH_PADDING, _MAX_EXCEL_COL_WIDTH) for w in widths]


# 엑셀은 "병합된" 셀에서는 wrap_text가 켜져 있어도 행 높이를 자동으로 늘려주지
# 않는다(잘 알려진 엑셀 제약) — 그래서 긴 문단이 한 줄로 눌려 보이거나, 심하면
# 스크롤하다 "내용이 통째로 빠졌다"고 오해하기 쉽다(2026-08-05 실사용 피드백).
# 행 높이를 직접 계산해서 지정한다.
_EXCEL_LINE_HEIGHT_PT = 15
_EXCEL_ROW_HEIGHT_PADDING_PT = 5


def _wrapped_line_count(text, span_width_units):
    """span_width_units 폭에 줄바꿈해서 넣을 때 필요한 줄 수(최소 1)."""
    if not text:
        return 1
    total = 0
    for line in _LINE_BREAK_RE.split(str(text)):
        width = _text_width_units(line)
        total += max(1, -(-width // max(span_width_units, 1)))  # 올림 나눗셈
    return max(total, 1)


def _set_row_height(ws, row, cell_texts_and_widths):
    """그 행의 셀들 중 가장 많은 줄 수가 필요한 셀 기준으로 행 높이를 지정한다."""
    max_lines = max(
        (_wrapped_line_count(text, width) for text, width in cell_texts_and_widths), default=1
    )
    ws.row_dimensions[row].height = max_lines * _EXCEL_LINE_HEIGHT_PT + _EXCEL_ROW_HEIGHT_PADDING_PT


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
    채운다. 맨 위에 문서 제목(PDF와 동일하게 28pt·굵게·밑줄)을 두고, 모든
    내용은 A열을 공란으로 남긴 채 B열부터 쓴다(2026-08-05 요청). 표가
    여러 개면 표 사이에 빈 행 하나를 둔다. draft가 완전히 비어있는
    경우(이론상 거의 없음)만 원문 그대로 A1에 넣는다.
    """
    blocks = parse_markdown_blocks(record["draft"])
    document_type = record["document_type"]
    style = get_style(document_type)

    header_fill = _fill(style.header_fill)
    data_header_font = Font(size=_BODY_FONT_SIZE, bold=True, color=style.header_font_color)
    kv_header_fill = _fill(style.kv_header_fill)
    risk_fills = {grade: _fill(hex_color) for grade, hex_color in style.risk_grade_colors.items()}

    wb = Workbook()
    ws = wb.active
    ws.title = _sheet_title(document_type)

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

    if document_type in _CONTENT_AWARE_WIDTH_DOCUMENT_TYPES:
        column_widths = _content_aware_excel_widths(table_blocks, max_col_count)
    else:
        column_widths = list(style.column_widths)
        while len(column_widths) < max_col_count:
            column_widths.append(DEFAULT_COLUMN_WIDTH)

    ws.column_dimensions["A"].width = _COL_A_WIDTH

    title_cell = ws.cell(row=1, column=1 + _COL_OFFSET, value=document_type)
    title_cell.font = _TITLE_FONT
    title_cell.alignment = _ALIGN_TITLE_DOC
    ws.merge_cells(
        start_row=1, start_column=1 + _COL_OFFSET, end_row=1, end_column=max_col_count + _COL_OFFSET
    )

    current_row = 2
    table_index = 0
    freeze_row = None
    risk_score_ranges = []  # (col_letter, first_data_row, last_data_row)

    for block in blocks:
        if block["type"] == "heading":
            title_cell = ws.cell(row=current_row, column=1 + _COL_OFFSET, value=block["text"])
            title_cell.font = _BOX_TITLE_FONT
            title_cell.alignment = _ALIGN_TITLE
            if max_col_count > 1:
                ws.merge_cells(
                    start_row=current_row, start_column=1 + _COL_OFFSET,
                    end_row=current_row, end_column=max_col_count + _COL_OFFSET,
                )
            _set_row_height(ws, current_row, [(block["text"], sum(column_widths[:max_col_count]))])
            current_row += 1
            continue

        if block["type"] == "text":
            text_cell = ws.cell(row=current_row, column=1 + _COL_OFFSET, value=block["text"])
            text_cell.font = _BODY_FONT
            text_cell.alignment = _ALIGN_LEFT_TOP
            if max_col_count > 1:
                ws.merge_cells(
                    start_row=current_row, start_column=1 + _COL_OFFSET,
                    end_row=current_row, end_column=max_col_count + _COL_OFFSET,
                )
            _set_row_height(ws, current_row, [(block["text"], sum(column_widths[:max_col_count]))])
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

        ai_value_present = False

        for row_offset, row_cells in enumerate(table):
            is_header = row_offset == 0
            row_texts_and_widths = []
            for col_idx, value in enumerate(row_cells, start=1):
                number, note = parse_ai_score_cell(value)
                display_value = number if number is not None else value
                cell = ws.cell(row=current_row, column=col_idx + _COL_OFFSET, value=display_value)
                if note:
                    cell.comment = Comment(note, _COMMENT_AUTHOR)
                    ai_value_present = True
                cell.border = _THIN_BORDER

                if is_kv_table and col_idx >= 2:
                    span_width = sum(column_widths[1:max_col_count])
                else:
                    span_width = column_widths[col_idx - 1] if col_idx - 1 < len(column_widths) else DEFAULT_COLUMN_WIDTH
                row_texts_and_widths.append((str(display_value) if display_value is not None else "", span_width))

                if is_kv_table:
                    if col_idx == 1:
                        cell.font = _HEADER_FONT
                        cell.fill = kv_header_fill
                        cell.alignment = _ALIGN_CENTER
                    else:
                        if is_header:
                            cell.font = _HEADER_FONT
                            cell.fill = kv_header_fill
                        else:
                            cell.font = _BODY_FONT
                        cell.alignment = _ALIGN_LEFT_CENTER
                elif is_header:
                    cell.font = data_header_font
                    cell.fill = header_fill
                    cell.alignment = _ALIGN_CENTER
                else:
                    cell.font = _BODY_FONT
                    header_text = headers_base[col_idx - 1] if col_idx - 1 < len(headers_base) else ""
                    cell.alignment = (
                        _ALIGN_CENTER if header_text.lower() in CENTER_ALIGN_HEADERS else _ALIGN_LEFT_TOP
                    )
                    if col_idx not in risk_grade_col_idxs:
                        # "위험성 추정 행렬" 참고표처럼 헤더명이 "위험등급"이 아니라
                        # risk_grade_column_indices로는 안 잡히지만, 셀 값 자체가
                        # 등급 문자(A/B/C)인 표도 본문과 같은 색으로 칠한다
                        # (2026-08-05 요청).
                        grade = str(display_value).strip().upper() if display_value is not None else ""
                        if grade in risk_fills:
                            cell.fill = risk_fills[grade]
                            cell.alignment = _ALIGN_CENTER

            if is_kv_table and max_col_count > 2:
                ws.merge_cells(
                    start_row=current_row, start_column=2 + _COL_OFFSET,
                    end_row=current_row, end_column=max_col_count + _COL_OFFSET,
                )

            _set_row_height(ws, current_row, row_texts_and_widths)
            current_row += 1

            if table_index == 1 and is_header:
                freeze_row = current_row

        if risk_grade_col_idxs and len(table) > 1:
            for idx in risk_grade_col_idxs:
                risk_score_ranges.append(
                    (get_column_letter(idx + _COL_OFFSET), header_row + 1, current_row - 1)
                )

        # AI 제안값이 있었던 표는 PDF/HWPX와 동일하게 각주를 표 바로 아래에 남긴다
        # (2026-08-05 요청 — XLSX만 이 각주가 빠져 있었음).
        if ai_value_present:
            footnote_cell = ws.cell(row=current_row, column=1 + _COL_OFFSET, value=AI_SCORE_FOOTNOTE)
            footnote_cell.font = _FOOTNOTE_FONT
            footnote_cell.alignment = _ALIGN_FOOTNOTE
            if max_col_count > 1:
                ws.merge_cells(
                    start_row=current_row, start_column=1 + _COL_OFFSET,
                    end_row=current_row, end_column=max_col_count + _COL_OFFSET,
                )
            current_row += 1

        table_index += 1
        current_row += 1  # 표 사이 빈 행

    if freeze_row is None:
        freeze_row = 2

    for col_idx in range(1, max_col_count + 1):
        ws.column_dimensions[get_column_letter(col_idx + _COL_OFFSET)].width = column_widths[col_idx - 1]

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
