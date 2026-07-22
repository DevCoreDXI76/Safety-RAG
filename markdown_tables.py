"""
GFM 파이프 테이블(`| a | b |` 형식) 파서.

generate_draft.py가 만드는 draft 필드는 구조화 JSON이 아니라 Markdown 텍스트다.
XLSX/HWPX/PDF 등 "생성된 문서 → 템플릿" 변환 기능은 모두 이 파서를 공용으로 쓴다.
"""

import re

_TABLE_ROW_RE = re.compile(r"^\|(.+)\|\s*$")
_SEPARATOR_CELL_RE = re.compile(r"^\s*:?-{3,}:?\s*$")
_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")


def _split_row(line):
    """'| a | b |' -> ['a', 'b']"""
    inner = line.strip()[1:-1]
    return [cell.strip() for cell in inner.split("|")]


def _is_separator_row(cells):
    return len(cells) > 0 and all(_SEPARATOR_CELL_RE.match(c) for c in cells)


def _clean_cell(text):
    """마크다운 강조(**bold**)만 제거한다. 그 외 셀 내용은 그대로 둔다."""
    return _BOLD_RE.sub(r"\1", text).strip()


def parse_markdown_tables(markdown_text):
    """
    markdown_text 안의 모든 GFM 파이프 테이블을 순서대로 파싱해
    list[list[list[str]]](표 여러 개 x 행 여러 개 x 셀 여러 개)로 반환한다.
    헤더 구분선(|---|---|)은 결과에서 제외되고, 헤더 행은 첫 행으로 포함된다.
    표가 아닌 나머지 텍스트(제목, 안내문 등)는 무시한다.
    """
    tables = []
    current_rows = []

    for line in markdown_text.splitlines():
        match = _TABLE_ROW_RE.match(line)
        if not match:
            if current_rows:
                tables.append(current_rows)
                current_rows = []
            continue

        cells = _split_row(line)
        if _is_separator_row(cells):
            continue  # 헤더 구분선은 표 블록을 끊지 않고 그냥 버린다
        current_rows.append([_clean_cell(c) for c in cells])

    if current_rows:
        tables.append(current_rows)

    return tables
