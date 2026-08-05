"""
저장된 프로젝트 기록(record["draft"]의 Markdown 텍스트)을 파싱해
python-hwpx 문서로 바인딩하고, .hwpx 파일 바이트를 반환한다.

셀 스타일(열너비 비율/헤더·위험등급 배경색/헤더별 정렬)은 document_styles.py의
문서유형별 스펙을 XLSX(export_xlsx.py)·PDF(export_pdf.py)와 공유한다
(docs/superpowers/specs/2026-07-31-공유-스타일-스펙-design.md).

2026-08-05: 실기기 검증 순서(PDF→XLSX→HWPX)상 HWPX 차례가 이제 와서,
PDF/XLSX가 그 사이 실기기 피드백으로 먼저 얻은 개선을 포팅한다 —
(1) 박스 제목(헤딩)·서술형 문단 보존(parse_markdown_tables만 쓰던 탓에
표 없는 헤딩·문단이 통째로 버려지고 있었음), (2) 위험성평가표 콘텐츠 기반
열너비(water-filling — 단순 비례 배분은 실제 13열 스펙에서 "빈도"·"강도"류
좁은 헤더가 세로로 한 글자씩 찌그러지는 회귀를 낳아 최소폭 보장 방식으로
교체), (3) "(빈칸 - 현장 기재)"류 플레이스홀더 회색 처리, (4) 위험성 추정
행렬처럼 헤더명이 "위험등급"이 아니어도 셀 값 자체가 등급 문자(A/B/C)면
같은 색 적용, (5) 결재란·서명란 등은 콘텐츠 기반이 아니라 균등폭, (6) 문서
제목 28pt·밑줄·가운데정렬, (7) 표준 작업계획서·TBM 일지는 세로형(portrait)
A4로 전환(PDF/XLSX와 동일 — document_styles.PORTRAIT_DOCUMENT_TYPES 공유).
문자색·볼드는 add_run(bold=, color=)로 가능함을 이번에 확인했다 — 이전
주석의 "검증된 문자색 API를 찾지 못함"은 해소됨. 인쇄배율(엑셀 전용
개념)·틀고정은 워드프로세서 자동 페이지네이션 특성상 이식 대상이 아니다.
"""

import re
import unicodedata

from hwpx import HwpxDocument

from document_styles import (
    AI_SCORE_FOOTNOTE, PORTRAIT_DOCUMENT_TYPES, base_header, cell_style_decision,
    get_style, parse_ai_score_cell, resolve_column_weights, risk_grade_column_indices,
)
from markdown_tables import parse_markdown_blocks

_HWP_UNITS_PER_MM = 7200 / 25.4
_HWP_UNITS_PER_PT = 100  # 1pt = 1/72in = 7200/72
_PAGE_MARGIN_MM = 15
_A4_WIDTH_MM = {"landscape": 297, "portrait": 210}

# PDF(fac4312)/XLSX와 동일하게 문서 제목 28pt·밑줄·굵게·가운데정렬, 박스
# 제목 16pt·굵게, 본문/표 셀 12pt.
_DOC_TITLE_SIZE = 28
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

# PDF(aaf80a9/d88b89a)와 동일하게 "결재란"·"서명"·"참여 확인" 박스 바로
# 아래 표는 콘텐츠 기반이 아니라 균등폭을 쓴다 — 이런 표는 대부분 빈 칸
# "(빈칸)"이라 콘텐츠 기반 배분에 맡기면 폭이 거의 안 나온다.
_EQUAL_WIDTH_HEADING_KEYWORDS = ("참석자", "서명", "참여 확인", "결재란")

# 콘텐츠 기반 열너비의 최소 보장폭(약 12mm — 한글 2~3자가 세로로 찌그러지지
# 않고 들어갈 정도). 2026-08-05 실기기 검증: 13열 실스펙에서 "빈도"·"강도"·
# "위험등급"처럼 헤더가 2~4글자인 좁은 열이 옆의 훨씬 긴 서술형 열 때문에
# 단순 비례 배분으로는 세로로 한 글자씩 줄바꿈되는 문제가 발견됨 — PDF의
# water-filling 알고리즘(자연폭보다 좁게 배분되는 열이 없도록, 남는 예산만
# 더 필요한 열끼리 초과분 비례로 나눔)을 HWP 유닛 단위로 옮겨온다.
_MIN_COL_WIDTH_UNITS = round(12 * _HWP_UNITS_PER_MM)
_CELL_H_PADDING_UNITS = round(3 * _HWP_UNITS_PER_MM)
_FULLWIDTH_CHAR_EM_RATIO = 1.0
_HALFWIDTH_CHAR_EM_RATIO = 0.55


def _measure_natural_width_units(text, font_size_pt):
    """text의 가장 넓은 줄이 font_size_pt(HWP 문자height=pt*100 관례)로
    표시될 때 필요한 폭(HWP 유닛, 좌우 패딩 포함)을 근사한다. 한글 등
    전각 문자는 1em, 그 외(영문·숫자 등)는 0.55em으로 어림한다."""
    lines = _LINE_BREAK_RE.split(text) if text else [""]
    widest_em = 0.0
    for line in lines:
        em = sum(
            _FULLWIDTH_CHAR_EM_RATIO if unicodedata.east_asian_width(ch) in ("W", "F")
            else _HALFWIDTH_CHAR_EM_RATIO
            for ch in line
        )
        widest_em = max(widest_em, em)
    return widest_em * font_size_pt * _HWP_UNITS_PER_PT + _CELL_H_PADDING_UNITS


def _content_aware_weights(tables, ncols, usable_width):
    """표 전체에서 각 열의 실제 표시 값(AI 안내문 제거 후) 기준 자연폭을
    구하고, water-filling으로 열 너비를 배분한다(export_pdf.py의
    _content_aware_col_widths와 동일 알고리즘 — 자연폭이 작은 열부터 정렬해
    "남은 예산을 남은 열 수로 균등 배분했을 때" 그 안에 들어오는 열은 자기
    자연폭을 그대로 받고, 그 이상을 요구하는 열들만 남은 예산을 초과분
    비례로 나눠 갖는다). 합계는 항상 usable_width와 같다."""
    natural = [_MIN_COL_WIDTH_UNITS] * ncols
    for rows in tables:
        for row in rows:
            for col in range(min(len(row), ncols)):
                number, _note = parse_ai_score_cell(row[col])
                measure_text = str(number) if number is not None else row[col]
                natural[col] = max(natural[col], _measure_natural_width_units(measure_text, _BODY_SIZE))

    result = [0.0] * ncols
    order = sorted(range(ncols), key=lambda i: natural[i])
    remaining_budget = usable_width
    remaining_count = ncols
    settled = set()

    for i in order:
        fair_share = remaining_budget / remaining_count
        if natural[i] > fair_share:
            break
        result[i] = natural[i]
        remaining_budget -= natural[i]
        remaining_count -= 1
        settled.add(i)

    unsettled = [i for i in range(ncols) if i not in settled]
    if unsettled:
        floor = min(_MIN_COL_WIDTH_UNITS, remaining_budget / len(unsettled))
        reserved = floor * len(unsettled)
        surplus = max(remaining_budget - reserved, 0)
        extra_need = {i: max(natural[i] - floor, 0) for i in unsettled}
        total_extra_need = sum(extra_need.values())
        for i in unsettled:
            if total_extra_need == 0:
                result[i] = floor + surplus / len(unsettled)
            else:
                result[i] = floor + surplus * (extra_need[i] / total_extra_need)
    elif remaining_budget > 0:
        total_natural = sum(natural)
        for i in range(ncols):
            result[i] += remaining_budget * (natural[i] / total_natural if total_natural else 1 / ncols)

    return result


def _wants_equal_width_columns(heading_text):
    return heading_text is not None and any(k in heading_text for k in _EQUAL_WIDTH_HEADING_KEYWORDS)


def _add_styled_text(paragraph, text, *, bold=False, size=None, underline=False):
    """플레이스홀더("(빈칸 - 현장 기재)"류)만 회색으로, 나머지는 기본 색으로
    text를 여러 run으로 쪼개 문단에 추가한다. 플레이스홀더가 없으면 run 1개."""
    last_end = 0
    added_any = False
    for m in _PLACEHOLDER_RE.finditer(text):
        if m.start() > last_end:
            paragraph.add_run(text[last_end:m.start()], bold=bold, size=size, underline=underline)
            added_any = True
        paragraph.add_run(m.group(0), bold=bold, size=size, underline=underline, color=_PLACEHOLDER_COLOR)
        added_any = True
        last_end = m.end()
    if last_end < len(text) or not added_any:
        paragraph.add_run(text[last_end:], bold=bold, size=size, underline=underline)


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

    # 위험성평가표처럼 열이 많은 문서는 가로형이 필요하지만, 표준 작업계획서·
    # TBM 일지는 서술형 문단 + 좁은 표 위주라 세로형이 더 자연스럽다
    # (PDF/XLSX와 동일 — document_styles.PORTRAIT_DOCUMENT_TYPES 공유).
    orientation = "portrait" if document_type in PORTRAIT_DOCUMENT_TYPES else "landscape"

    doc = HwpxDocument.new()
    doc.set_page_setup(
        paper_size="A4",
        orientation=orientation,
        margins_mm={
            "left": _PAGE_MARGIN_MM, "right": _PAGE_MARGIN_MM,
            "top": _PAGE_MARGIN_MM, "bottom": _PAGE_MARGIN_MM,
        },
    )
    usable_width = round((_A4_WIDTH_MM[orientation] - 2 * _PAGE_MARGIN_MM) * _HWP_UNITS_PER_MM)

    # 문서 전체에서 재사용할 정렬 문단속성 id. ensure_paragraph_alignment는
    # 같은 정렬이면 기존 id를 재사용하므로 문서당 한 번씩만 만들면 된다.
    # left_para_id를 명시적으로 지정하지 않으면 왼쪽정렬 셀/문단이 문서 기본
    # 문단속성(JUSTIFY)을 그대로 물려받아 XLSX(horizontal="left")·
    # PDF(TA_LEFT)와 어긋난다.
    center_para_id = doc.headers[0].ensure_paragraph_alignment("CENTER")
    left_para_id = doc.headers[0].ensure_paragraph_alignment("LEFT")

    # 문서 제목: 가운데정렬 + 밑줄 + 28pt + 굵게(PDF/XLSX와 동일).
    title_p = doc.add_paragraph("", include_run=False, para_pr_id_ref=center_para_id)
    title_p.add_run(document_type, bold=True, size=_DOC_TITLE_SIZE, underline=True)
    doc.add_paragraph("")

    if not blocks:
        doc.add_paragraph(record["draft"])
        return doc.to_bytes()

    table_blocks = [b["rows"] for b in blocks if b["type"] == "table"]
    content_aware = document_type in _CONTENT_AWARE_WIDTH_DOCUMENT_TYPES
    last_heading_text = None

    for block in blocks:
        if block["type"] == "heading":
            last_heading_text = block["text"]
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

        if _wants_equal_width_columns(last_heading_text):
            weights = [1] * cols
        elif content_aware:
            weights = _content_aware_weights(table_blocks, cols, usable_width)
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
                if not fill_hex and not is_header_row and not is_kv_table and col_index not in risk_cols:
                    # "위험성 추정 행렬" 참고표처럼 헤더명이 "위험등급"이 아니라
                    # risk_grade_column_indices로는 안 잡히지만, 셀 값 자체가
                    # 등급 문자(A/B/C)인 표도 본문과 같은 색으로 칠한다
                    # (PDF 6c8cb5a/XLSX 63590a2와 동일).
                    grade = text.strip().upper()
                    if grade in style.risk_grade_colors:
                        fill_hex = style.risk_grade_colors[grade]
                        center = True

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
