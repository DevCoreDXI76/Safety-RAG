"""
문서유형별 렌더링 스타일 스펙 — export_xlsx.py/export_pdf.py/export_hwpx.py
3개 렌더러가 공유한다(docs/superpowers/specs/2026-07-31-공유-스타일-스펙-design.md).

열너비는 절대 단위가 아니라 상대 비율로 취급한다 — XLSX는 openpyxl의 문자폭
단위로 그대로 쓰고, PDF/HWPX는 이 숫자를 비율로 정규화해 각자의 단위(포인트/
HWP유닛)로 변환한다. 색상은 "#" 없는 6자리 hex 문자열로 저장한다(openpyxl
관례) — reportlab에 넘길 때만 "#"을 붙인다.
"""

import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class DocumentStyle:
    column_widths: list
    header_fill: str = "2F5496"
    header_font_color: str = "FFFFFF"
    kv_header_fill: str = "E3ECEF"
    risk_grade_headers: frozenset = field(
        default_factory=lambda: frozenset({"위험등급", "개선후 위험등급"})
    )
    risk_grade_colors: dict = field(
        default_factory=lambda: {"A": "F8CBAD", "B": "FFE699", "C": "C6E0B4"}
    )


DEFAULT_COLUMN_WIDTH = 22

# 문서종류별 열 너비(왼쪽부터, 상대 비율). docs/샘플문서/*.xlsx 서식목업 실측값
# (2026-07 XLSX 서식 개선 작업에서 확정된 값을 그대로 이전).
STYLE_SPECS = {
    "위험성평가표": DocumentStyle(
        column_widths=[6, 20, 32, 18, 22, 6, 6, 10, 38, 12, 12, 14, 10],
    ),
    "표준 작업계획서": DocumentStyle(column_widths=[16, 26, 30, 34]),
    "TBM 일지": DocumentStyle(column_widths=[10, 22, 34, 16]),
    "안전보건교육일지": DocumentStyle(column_widths=[10, 22, 34, 16]),
    "산업안전보건관리비 사용명세서": DocumentStyle(
        column_widths=[16, 16, 22, 26, 16, 18, 16],
    ),
    "협의체 회의록": DocumentStyle(column_widths=[20, 16, 16]),
}

_DEFAULT_STYLE = DocumentStyle(column_widths=[])

# 표 헤더가(괄호 부연설명 제외) 이 목록에 속하면 가운데 정렬(짧은 값용),
# 아니면 서술형 텍스트로 보고 왼쪽 정렬을 쓴다.
CENTER_ALIGN_HEADERS = frozenset({
    "번호", "순번", "no", "순서", "구분",
    "담당", "서명", "소속/직책", "성명",
    "빈도", "강도", "위험등급", "개선후 위험등급", "개선예정일",
    "이행확인", "재평가 필요여부", "재평가필요",
    "규격", "수량", "금액", "증빙유형", "사용일자", "소요시간",
    "계상금액", "사용금액", "집행률",
    "작성자", "검토자", "승인자",
    "일자", "날짜", "시간", "인원", "등급",
})

# 빈도·강도는 숫자(1~3), 위험등급·개선후 위험등급은 문자(A/B/C) — 행렬법
# 전환(2026-07) 이후 둘 다 "N(AI 제안값, 현장 확인 필수)" 형식으로 온다.
_AI_SCORE_RE = re.compile(r"^\s*(\d+(?:\.\d+)?|[A-Ca-c])\s*\(AI\s*제안값,\s*현장\s*확인\s*필수\)\s*$")
_PAREN_RE = re.compile(r"\([^)]*\)")

AI_SCORE_NOTE = "AI 제안값, 현장 확인 필수"
AI_SCORE_FOOTNOTE = f"※ 이 표의 수치·등급 중 일부는 {AI_SCORE_NOTE}입니다."


def parse_ai_score_cell(text):
    """
    '3(AI 제안값, 현장 확인 필수)' / 'A(AI 제안값, 현장 확인 필수)' 표기를
    감지해 순수 값(숫자 또는 등급 문자)과 안내 문구로 분리한다. 매치되지
    않는 일반 텍스트 셀은 (None, None)을 반환한다.
    """
    match = _AI_SCORE_RE.match(text)
    if not match:
        return None, None
    raw = match.group(1)
    if raw.isalpha():
        return raw.upper(), AI_SCORE_NOTE
    number = float(raw) if "." in raw else int(raw)
    return number, AI_SCORE_NOTE


def base_header(text):
    """헤더 텍스트에서 '위험성(AI 제안값, 현장 확인 필수)' 같은 괄호 부연설명을 제거한다."""
    return _PAREN_RE.sub("", text).strip()


def get_style(document_type):
    """스펙에 없는 문서유형(예: '기타 (직접 입력)')이면 빈 열너비 기본 스펙을 반환한다."""
    return STYLE_SPECS.get(document_type, _DEFAULT_STYLE)


def resolve_column_weights(style, ncols):
    """스펙 열너비를 표의 실제 열 개수에 맞춘다. 모자라면 기본폭으로 채우고, 많으면 자른다."""
    weights = list(style.column_widths[:ncols])
    while len(weights) < ncols:
        weights.append(DEFAULT_COLUMN_WIDTH)
    return weights


def risk_grade_column_indices(style, headers_base):
    """헤더 텍스트가 risk_grade_headers에 속하는 열의 0-indexed 위치 리스트."""
    return [i for i, h in enumerate(headers_base) if h in style.risk_grade_headers]


def cell_style_decision(style, headers_base, risk_cols, is_kv_table, is_header_row, col_index, cell_text):
    """
    (center: bool, fill_hex: str | None) 반환 — XLSX(export_xlsx.py)가 이미
    검증한 정렬·배경색 규칙을 PDF/HWPX도 동일하게 따르도록 하는 공용 판정.
    cell_text는 parse_ai_score_cell()로 이미 순수값만 남긴 표시 텍스트여야
    한다(위험등급 열의 배경색 매칭에 쓰임).
    """
    if is_kv_table:
        if col_index == 0:
            return True, style.kv_header_fill
        if is_header_row:
            return False, style.kv_header_fill
        return False, None

    if is_header_row:
        return True, style.header_fill

    header_text = headers_base[col_index] if col_index < len(headers_base) else ""
    center = header_text.lower() in CENTER_ALIGN_HEADERS
    fill_hex = None
    if col_index in risk_cols:
        grade_letter = cell_text.strip().upper()
        fill_hex = style.risk_grade_colors.get(grade_letter)
    return center, fill_hex
