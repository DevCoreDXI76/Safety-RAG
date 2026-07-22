"""
저장된 프로젝트 기록(record["draft"]의 Markdown 텍스트)을 파싱해
openpyxl 워크북으로 바인딩하고, xlsx 파일 바이트를 반환한다.
"""

import io
import re

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

from markdown_tables import parse_markdown_tables

_HEADER_FILL = PatternFill(start_color="E3ECEF", end_color="E3ECEF", fill_type="solid")
_HEADER_FONT = Font(bold=True)
_INVALID_SHEET_CHARS_RE = re.compile(r"[:\\/?*\[\]]")
_COLUMN_WIDTH = 30


def _sheet_title(document_type):
    """엑셀 시트명 제약(31자 이내, : \\ / ? * [ ] 금지)을 만족하도록 정리한다."""
    cleaned = _INVALID_SHEET_CHARS_RE.sub("", document_type)
    return cleaned[:31] or "문서"


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
    else:
        current_row = 1
        max_col_count = 1
        for table in tables:
            header_row = current_row
            for row_cells in table:
                for col_idx, value in enumerate(row_cells, start=1):
                    ws.cell(row=current_row, column=col_idx, value=value)
                max_col_count = max(max_col_count, len(row_cells))
                current_row += 1
            for col_idx in range(1, len(table[0]) + 1):
                cell = ws.cell(row=header_row, column=col_idx)
                cell.font = _HEADER_FONT
                cell.fill = _HEADER_FILL
            current_row += 1  # 표 사이 빈 행

        for col_idx in range(1, max_col_count + 1):
            ws.column_dimensions[get_column_letter(col_idx)].width = _COLUMN_WIDTH
        ws.freeze_panes = "A2"

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
