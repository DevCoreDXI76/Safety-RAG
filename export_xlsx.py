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

from markdown_tables import parse_markdown_tables

_HEADER_FILL = PatternFill(start_color="E3ECEF", end_color="E3ECEF", fill_type="solid")
_HEADER_FONT = Font(bold=True)
_DATA_HEADER_FILL = PatternFill(start_color="2F5496", end_color="2F5496", fill_type="solid")
_DATA_HEADER_FONT = Font(bold=True, color="FFFFFF")

_THIN_SIDE = Side(style="thin")
_THIN_BORDER = Border(left=_THIN_SIDE, right=_THIN_SIDE, top=_THIN_SIDE, bottom=_THIN_SIDE)

_ALIGN_CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)
_ALIGN_LEFT_CENTER = Alignment(horizontal="left", vertical="center", wrap_text=True)
_ALIGN_LEFT_TOP = Alignment(horizontal="left", vertical="top", wrap_text=True)

_INVALID_SHEET_CHARS_RE = re.compile(r"[:\\/?*\[\]]")
_COMMENT_AUTHOR = "safety-rag"
_AI_SCORE_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*\(AI\s*제안값,\s*현장\s*확인\s*필수\)\s*$")
_AI_SCORE_NOTE = "AI 제안값, 현장 확인 필수"

_DEFAULT_COLUMN_WIDTH = 22

# 문서종류별 열 너비(왼쪽부터). docs/샘플문서/*.xlsx 서식목업 실측값.
_COLUMN_WIDTHS_BY_DOCUMENT_TYPE = {
    "위험성평가표": [6, 20, 32, 8, 8, 8, 46, 10, 10],
    "표준 작업계획서": [16, 26, 30, 34],
    "TBM 일지": [10, 22, 34, 16],
    "안전보건교육일지": [10, 22, 34, 16],
    "산업안전보건관리비 사용명세서": [16, 16, 22, 26, 16, 18, 16],
}

# 표 헤더가(괄호 부연설명 제외) 이 목록에 속하면 가운데 정렬(짧은 값용),
# 아니면 서술형 텍스트로 보고 왼쪽·위 정렬을 쓴다. 5개 서식목업의 데이터 표
# 헤더 전수 실측 기준("단계"·"항목"은 서술형으로 쓰여 왼쪽 정렬이 맞다).
_CENTER_ALIGN_HEADERS = {
    "번호", "순번", "no", "순서", "구분",
    "담당", "서명", "소속/직책", "성명",
    "가능성", "중대성", "위험성", "이행확인", "재평가 필요여부",
    "규격", "수량", "금액", "증빙유형", "사용일자", "소요시간",
    "계상금액", "사용금액", "집행률",
    "작성자", "검토자", "승인자",
    "일자", "날짜", "시간", "인원", "등급",
}

_RISK_SCORE_HEADER = "위험성"
_RISK_HIGH_FILL = PatternFill(start_color="F8CBAD", end_color="F8CBAD", fill_type="solid")
_RISK_MID_FILL = PatternFill(start_color="FFE699", end_color="FFE699", fill_type="solid")
_RISK_LOW_FILL = PatternFill(start_color="C6E0B4", end_color="C6E0B4", fill_type="solid")


def _parse_ai_score_cell(text):
    """
    system_prompt가 위험성/가능성/중대성 점수마다 강제로 붙이는
    '15(AI 제안값, 현장 확인 필수)' 표기를 감지해, 순수 숫자와 안내 문구로
    분리한다. 매치되지 않는 일반 텍스트 셀은 (None, None)을 반환한다.
    """
    match = _AI_SCORE_RE.match(text)
    if not match:
        return None, None
    raw = match.group(1)
    number = float(raw) if "." in raw else int(raw)
    return number, _AI_SCORE_NOTE


def _sheet_title(document_type):
    """엑셀 시트명 제약(31자 이내, : \\ / ? * [ ] 금지)을 만족하도록 정리한다."""
    cleaned = _INVALID_SHEET_CHARS_RE.sub("", document_type)
    return cleaned[:31] or "문서"


def _base_header(text):
    """헤더 텍스트에서 '위험성(AI 제안값, 현장 확인 필수)' 같은 괄호 부연설명을 제거한다."""
    return re.sub(r"\([^)]*\)", "", text).strip()


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
    record["draft"]에서 Markdown 표를 파싱해 시트에 순서대로 채운다.
    표가 여러 개면 표 사이에 빈 행 하나를 둔다. 표가 없으면 draft 원문을 A1에 넣는다.
    """
    tables = parse_markdown_tables(record["draft"])

    wb = Workbook()
    ws = wb.active
    ws.title = _sheet_title(record["document_type"])

    if not tables:
        ws.cell(row=1, column=1, value=record["draft"])
        _apply_print_settings(ws)
        buffer = io.BytesIO()
        wb.save(buffer)
        return buffer.getvalue()

    column_widths = list(_COLUMN_WIDTHS_BY_DOCUMENT_TYPE.get(record["document_type"], []))
    current_row = 1
    max_col_count = 1
    freeze_row = None
    risk_score_ranges = []  # (col_letter, first_data_row, last_data_row)

    for table_index, table in enumerate(tables):
        header_row = current_row
        headers_base = [_base_header(h) for h in table[0]]
        is_kv_table = len(table[0]) == 2
        risk_col_idx = None
        if not is_kv_table:
            for idx, header_text in enumerate(headers_base, start=1):
                if header_text == _RISK_SCORE_HEADER:
                    risk_col_idx = idx

        for row_offset, row_cells in enumerate(table):
            is_header = row_offset == 0
            for col_idx, value in enumerate(row_cells, start=1):
                number, note = _parse_ai_score_cell(value)
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
                        cell.fill = _HEADER_FILL
                        cell.alignment = _ALIGN_CENTER
                    else:
                        if is_header:
                            cell.font = _HEADER_FONT
                            cell.fill = _HEADER_FILL
                        cell.alignment = _ALIGN_LEFT_CENTER
                elif is_header:
                    cell.font = _DATA_HEADER_FONT
                    cell.fill = _DATA_HEADER_FILL
                    cell.alignment = _ALIGN_CENTER
                else:
                    header_text = headers_base[col_idx - 1] if col_idx - 1 < len(headers_base) else ""
                    cell.alignment = (
                        _ALIGN_CENTER if header_text.lower() in _CENTER_ALIGN_HEADERS else _ALIGN_LEFT_TOP
                    )

            max_col_count = max(max_col_count, len(row_cells))
            current_row += 1

        if risk_col_idx is not None and len(table) > 1:
            risk_score_ranges.append((get_column_letter(risk_col_idx), header_row + 1, current_row - 1))

        if table_index == 1:
            # 5개 서식목업 공통 규칙: 두 번째 표 헤더 바로 아래에서 틀 고정.
            freeze_row = current_row

        current_row += 1  # 표 사이 빈 행

    if freeze_row is None:
        freeze_row = 2  # 표가 1개뿐이면 그 표 헤더 바로 아래에서 고정

    while len(column_widths) < max_col_count:
        column_widths.append(_DEFAULT_COLUMN_WIDTH)
    for col_idx in range(1, max_col_count + 1):
        ws.column_dimensions[get_column_letter(col_idx)].width = column_widths[col_idx - 1]

    ws.freeze_panes = f"A{freeze_row}"

    for col_letter, first_row, last_row in risk_score_ranges:
        cell_range = f"{col_letter}{first_row}:{col_letter}{last_row}"
        ws.conditional_formatting.add(
            cell_range, CellIsRule(operator="greaterThanOrEqual", formula=["10"], fill=_RISK_HIGH_FILL)
        )
        ws.conditional_formatting.add(
            cell_range, CellIsRule(operator="between", formula=["5", "9"], fill=_RISK_MID_FILL)
        )
        ws.conditional_formatting.add(
            cell_range, CellIsRule(operator="lessThanOrEqual", formula=["4"], fill=_RISK_LOW_FILL)
        )

    _apply_print_settings(ws, title_row=freeze_row - 1)

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
