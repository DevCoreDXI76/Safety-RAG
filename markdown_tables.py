"""
GFM 파이프 테이블(`| a | b |` 형식) 파서.

generate_draft.py가 만드는 draft 필드는 구조화 JSON이 아니라 Markdown 텍스트다.
XLSX/HWPX/PDF 등 "생성된 문서 → 템플릿" 변환 기능은 모두 이 파서를 공용으로 쓴다.
"""

import re

_TABLE_ROW_RE = re.compile(r"^\|(.+)\|\s*$")
_SEPARATOR_CELL_RE = re.compile(r"^\s*:?-{3,}:?\s*$")
_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
_HEADING_RE = re.compile(r"^#{2,6}\s+(.+?)\s*$")
_SEPARATOR_LINE_RE = re.compile(r"^\s*-{3,}\s*$")


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


def parse_markdown_blocks(markdown_text):
    """
    markdown_text를 헤딩(레벨 2~6)·표·서술형 문단(prose)을 순서대로 보존한
    블록 리스트로 반환한다. parse_markdown_tables와 달리 표가 아닌 텍스트를
    버리지 않는다 — "3. 중점(One Point) 위험요인"처럼 표가 아니라 문단인
    섹션도 실제로 존재하기 때문이다(2026-08-04, 실제 생성된 PDF에서 헤딩만
    남고 본문이 사라지는 버그로 발견). PDF가 표 앞에 "박스 제목"을 그리기
    위해 필요하다(export_pdf.py 전용, XLSX/HWPX는 계속 parse_markdown_tables를
    쓴다). 레벨 1(# ...)과 구분선(---)은 각각 문서 제목과 중복/장식용이라
    제외한다.
    각 블록은 {"type": "heading", "text": str} / {"type": "table", "rows":
    list[list[str]]} / {"type": "text", "text": str}(여러 줄이면 "\\n"으로 이음).
    """
    blocks = []
    current_rows = []
    current_text_lines = []

    def flush_table():
        if current_rows:
            blocks.append({"type": "table", "rows": current_rows[:]})
            current_rows.clear()

    def flush_text():
        # 표 셀(_clean_cell)과 동일하게 굵게(**) 마크다운 표시를 제거한다 —
        # 안 그러면 "**AC 220V/380V ...**"처럼 별표가 그대로 렌더링된다
        # (2026-08-05 5차 실사용 피드백).
        text = _BOLD_RE.sub(r"\1", "\n".join(current_text_lines)).strip()
        if text:
            blocks.append({"type": "text", "text": text})
        current_text_lines.clear()

    for line in markdown_text.splitlines():
        table_match = _TABLE_ROW_RE.match(line)
        if table_match:
            flush_text()
            cells = _split_row(line)
            if _is_separator_row(cells):
                continue
            current_rows.append([_clean_cell(c) for c in cells])
            continue

        flush_table()

        heading_match = _HEADING_RE.match(line)
        if heading_match:
            flush_text()
            blocks.append({"type": "heading", "text": heading_match.group(1).strip()})
            continue

        if _SEPARATOR_LINE_RE.match(line):
            continue

        stripped = line.strip()
        if stripped.startswith("#"):
            # 레벨 1 제목 등 — 문서 제목과 중복이라 제외(기존 동작 유지)
            continue

        current_text_lines.append(stripped)

    flush_table()
    flush_text()
    return blocks
