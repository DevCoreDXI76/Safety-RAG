"""
저장된 프로젝트 기록(record["draft"]의 Markdown 텍스트)을 파싱해
reportlab으로 PDF 바이트를 반환한다.

한글은 reportlab 내장 CID 폰트(HYSMyeongJo-Medium)로 렌더링한다 — 별도
TTF 폰트 파일을 저장소에 넣지 않아도 Railway(Linux) 환경에서 그대로
동작한다(docs/superpowers/specs/2026-07-28-hwpx-pdf-export-design.md에서
로컬 렌더링 + pypdf 텍스트 추출로 확인 완료).

셀 스타일(열너비 비율/헤더·위험등급 배경색/헤더별 정렬)은 document_styles.py의
문서유형별 스펙을 XLSX(export_xlsx.py)·HWPX(export_hwpx.py)와 공유한다
(docs/superpowers/specs/2026-07-31-공유-스타일-스펙-design.md). 볼드체·헤더
흰 글자는 CID 폰트에 검증된 볼드 변형이 없어 이번 스코프에서 제외했다 —
배경색·열비율·정렬만 XLSX와 맞춘다.
"""

import io
import re
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4, landscape, portrait
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import Flowable, Indenter, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from document_styles import (
    AI_SCORE_FOOTNOTE, base_header, cell_style_decision, get_style,
    parse_ai_score_cell, risk_grade_column_indices,
)
from markdown_tables import parse_markdown_blocks

_FONT_NAME = "HYSMyeongJo-Medium"
pdfmetrics.registerFont(UnicodeCIDFont(_FONT_NAME))

_BODY_STYLE = ParagraphStyle("body", fontName=_FONT_NAME, fontSize=14, leading=18)
_CELL_STYLE_LEFT = ParagraphStyle("cell_left", fontName=_FONT_NAME, fontSize=14, leading=18, alignment=TA_LEFT)
_CELL_STYLE_CENTER = ParagraphStyle("cell_center", fontName=_FONT_NAME, fontSize=14, leading=18, alignment=TA_CENTER)
_FOOTNOTE_STYLE = ParagraphStyle("footnote", fontName=_FONT_NAME, fontSize=8, leading=10, textColor=colors.grey)
_BOX_TITLE_STYLE = ParagraphStyle(
    "box_title", fontName=_FONT_NAME, fontSize=18, leading=22,
    alignment=TA_LEFT, spaceBefore=14, spaceAfter=6, keepWithNext=True,
)

_CELL_SIDE_PADDING_PT = 3  # LEFTPADDING/RIGHTPADDING 각각 — _CELL_H_PADDING_PT와 반드시 짝이 맞아야 함

_BASE_TABLE_STYLE_COMMANDS = [
    ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
    ("FONTNAME", (0, 0), (-1, -1), _FONT_NAME),
    ("FONTSIZE", (0, 0), (-1, -1), 14),
    ("VALIGN", (0, 0), (-1, -1), "TOP"),
    # reportlab Table의 기본 LEFTPADDING/RIGHTPADDING(각 6pt)을 그대로 두면
    # _content_aware_col_widths가 계산한 "글자가 들어갈 폭"보다 실제 사용
    # 가능한 폭이 더 좁아져 짧은 텍스트도 줄바꿈되는 문제가 있었다(2026-08-04
    # 발견 — "작업단계" 4글자 헤더가 두 줄로 쪼개짐). 패딩을 명시적으로 고정해
    # 폭 계산과 실제 렌더링이 어긋나지 않게 한다.
    ("LEFTPADDING", (0, 0), (-1, -1), _CELL_SIDE_PADDING_PT),
    ("RIGHTPADDING", (0, 0), (-1, -1), _CELL_SIDE_PADDING_PT),
]

# 셀 하나가 페이지 하나보다 커지는 걸 막는 안전 상한(줄 수). document_styles의
# 열비율은 특정 열 개수를 염두에 두고 정한 값이라, 그 열 개수를 벗어나는 표
# (예: 4열 기준 스펙에 12열 표가 들어오면 8개 열이 DEFAULT_COLUMN_WIDTH로
# 채워지며 1열이 극도로 좁아짐)에서 셀 텍스트가 조금만 길어도 reportlab이
# LayoutError로 PDF 생성 자체를 실패시킨다(2026-08-04 베타1 실기기 테스트에서
# 실제 발생·재현·확인, test_export_pdf.py 참고).
_MAX_CELL_LINES = 24

_MIN_COL_WIDTH_PT = 30
# 표 자체의 좌우 패딩(_CELL_SIDE_PADDING_PT 두 배) 위에 여유 4pt를 더한다 —
# 실제 예약되는 패딩보다 작으면 텍스트가 줄바꿈되는 문제가 재발한다.
_CELL_H_PADDING_PT = 2 * _CELL_SIDE_PADDING_PT + 4
_LINE_BREAK_RE = re.compile(r"<br\s*/?>|\n")

# document_styles의 공유 header_fill(진한 남색, XLSX/HWPX와 동일)보다 연하게
# — 흰색 쪽으로 45% 블렌드한 톤. PDF 전용이며 document_styles.py는 건드리지
# 않는다(XLSX/HWPX 헤더색은 그대로 유지).
_PDF_HEADER_FILL = "8DA1C5"

# 기본(reportlab 기본값 72pt=1인치)이 너무 넓다는 피드백으로 4방 모두 축소.
_PAGE_MARGIN_PT = 15

# 박스 제목(헤딩) 바로 아래 표·본문을 이 폭만큼 들여써서, 제목에 속한
# 내용이라는 게 시각적으로 드러나게 한다("모두 가운데정렬처럼 보인다" —
# 들여쓰기 없이 제목과 본문이 같은 왼쪽 기준선에서 시작해 위계가 안
# 드러나던 문제, 2026-08-04 피드백).
_CONTENT_INDENT_PT = 14

# "참석자 명단(서명 필수)" 같은 서명란 표는 LLM이 만들어주는 빈 행 개수가
# 들쭉날쭉해 실사용에 부족한 경우가 있었다(2026-08-04 요청 — 최소 10명 분량
# 확보 + 손글씨로 쓸 수 있을 만큼 행 높이 확대). 프롬프트에 의존하지 않고
# 렌더링 단계에서 결정적으로 보장한다.
_SIGNATURE_TABLE_KEYWORDS = ("참석자", "서명")
_SIGNATURE_TABLE_MIN_ROWS = 10
_SIGNATURE_ROW_HEIGHT_PT = 26


def _is_signature_heading(heading_text):
    return heading_text is not None and any(k in heading_text for k in _SIGNATURE_TABLE_KEYWORDS)


def _pad_table_rows(table, min_data_rows):
    """헤더를 제외한 데이터 행 수가 min_data_rows보다 적으면 빈 행으로 채운다."""
    ncols = max(len(row) for row in table)
    data_row_count = len(table) - 1
    if data_row_count >= min_data_rows:
        return table
    padded = [list(row) for row in table]
    for _ in range(min_data_rows - data_row_count):
        padded.append([""] * ncols)
    return padded


# 위험성평가표는 열이 많은 표(최대 13열)라 가로형을 유지해야 하지만,
# 표준 작업계획서·TBM 일지는 대부분 서술형 문단 + 좁은 표라 세로형이 더
# 자연스럽다(2026-08-04 요청).
_PORTRAIT_DOCUMENT_TYPES = {"표준 작업계획서", "TBM 일지"}


def _page_size_for(document_type):
    return portrait(A4) if document_type in _PORTRAIT_DOCUMENT_TYPES else landscape(A4)


_TITLE_FONT_SIZE = 28


def _center_x(text_width, avail_width):
    """가운데 정렬 x좌표. 텍스트가 가용폭보다 넓으면 0(음수 좌표 방지)."""
    return max((avail_width - text_width) / 2, 0)


class _TitleFlowable(Flowable):
    """
    문서 제목: 가운데정렬 + 밑줄 + 28pt + 굵게.
    CID 폰트(HYSMyeongJo-Medium)에는 검증된 Bold 변형이 없어(파일 상단 설명
    참고), 같은 텍스트를 아주 살짝(0.4pt) 겹쳐서 두 번 그리는 faux-bold로
    굵게 보이게 한다. 밑줄은 텍스트 폭만큼 직접 선을 그어 구현한다.
    """

    def __init__(self, text, font_name=None, font_size=_TITLE_FONT_SIZE):
        super().__init__()
        self.text = text
        self.font_name = font_name or _FONT_NAME
        self.font_size = font_size
        self._text_width = pdfmetrics.stringWidth(text, self.font_name, font_size)
        self._bold_offset = 0.4
        self.width = 0
        self.height = font_size * 1.6

    def wrap(self, availWidth, availHeight):
        self.width = availWidth
        return availWidth, self.height

    def draw(self):
        canv = self.canv
        canv.setFont(self.font_name, self.font_size)
        x = _center_x(self._text_width, self.width)
        baseline_y = self.height - self.font_size
        canv.drawString(x, baseline_y, self.text)
        canv.drawString(x + self._bold_offset, baseline_y, self.text)
        underline_y = baseline_y - 4
        canv.setLineWidth(1.1)
        canv.line(x, underline_y, x + self._text_width + self._bold_offset, underline_y)


def _hex_color(hex_str):
    return colors.HexColor("#" + hex_str)


def _measure_max_line_width(text, font_size):
    """
    셀 텍스트에 <br>/개행이 있으면 줄 단위로 나눠 가장 긴 한 줄의 렌더 폭을,
    없으면 전체 텍스트의 폭을 그대로 잰다. 여러 줄짜리 셀을 한 줄로 보고
    폭을 과대 측정하는 걸 막기 위함이다.
    """
    lines = _LINE_BREAK_RE.split(text) if text else [""]
    if not lines:
        lines = [""]
    return max(pdfmetrics.stringWidth(line, _FONT_NAME, font_size) for line in lines)


def _content_aware_col_widths(raw_rows, ncols, frame_width, font_size):
    """
    각 열의 '자연 폭'(그 열에서 가장 긴 한 줄의 렌더 폭 + 좌우 여백)을 측정해
    열 너비를 정한다. water-filling 방식: 자연폭이 작은 열부터 정렬해,
    "남은 예산을 남은 열 수로 균등 배분했을 때" 그 안에 들어오는 열은 자기
    자연폭을 그대로 받는다(예: "작업단계" 4글자 헤더는 옆에 아주 긴 서술형
    열이 있어도 절대 안 눌린다 — 2026-08-04, 폰트를 14pt로 키운 뒤 짧은 열이
    눌려 줄바꿈되는 회귀가 재현돼 알고리즘을 다시 설계함). 어느 열이든 균등
    배분보다 더 필요로 하는 순간부터는, 남은 열들이 "남은 예산"을 자연폭
    초과분에 비례해서만 나눠 갖는다(최소폭 바닥 보장 포함 — 12열 표에서 셀
    하나가 다른 열을 다 눌러버리던 문제의 재발 방지). 합계는 항상
    frame_width와 같다.
    """
    natural = []
    for col in range(ncols):
        widest = 0.0
        for row in raw_rows:
            text = row[col] if col < len(row) else ""
            widest = max(widest, _measure_max_line_width(text, font_size))
        natural.append(widest + _CELL_H_PADDING_PT)

    result = [0.0] * ncols
    order = sorted(range(ncols), key=lambda i: natural[i])
    remaining_budget = frame_width
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
        floor = min(_MIN_COL_WIDTH_PT, remaining_budget / len(unsettled))
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
        # 모든 열이 자연폭 안에서 넉넉히 들어간 경우(작은 표) — 남는 예산을
        # 그냥 버리면 표가 frame_width를 다 못 채운다. 자연폭 비례로 전 열에
        # 추가 배분해 항상 frame_width를 꽉 채우게 한다.
        total_natural = sum(natural)
        if total_natural > 0:
            for i in range(ncols):
                result[i] += remaining_budget * (natural[i] / total_natural)
        else:
            for i in range(ncols):
                result[i] += remaining_budget / ncols

    return result


def _fit_cell_text(text, col_width, font_size):
    """
    셀 폭 대비 텍스트가 _MAX_CELL_LINES줄을 넘어갈 만큼 길면 잘라낸다.
    CID 폰트(한글 완전폭)에서 글자당 폭 ≈ font_size이므로 이를 그대로
    글자당 폭 근사치로 쓴다.
    """
    chars_per_line = max(1, int(col_width / font_size))
    max_chars = chars_per_line * _MAX_CELL_LINES
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"


def _build_table_element(table, frame_width, document_type, is_signature_table=False):
    """
    Markdown에서 파싱한 표 1개(list[list[str]])를 프레임 폭에 맞춰 wrap되는
    Table 플로어블로 만든다. document_styles의 문서유형별 열비율·헤더/위험등급
    배경색·헤더별 정렬을 적용하고, AI 제안값이 하나라도 있었는지 함께 반환한다.
    is_signature_table=True면 데이터 행을 최소 _SIGNATURE_TABLE_MIN_ROWS개까지
    빈 행으로 채우고, 각 행 높이를 서명 가능한 정도로 키운다.
    """
    if is_signature_table:
        table = _pad_table_rows(table, _SIGNATURE_TABLE_MIN_ROWS)

    ncols = max(len(row) for row in table)
    style = get_style(document_type)

    col_widths = _content_aware_col_widths(table, ncols, frame_width, _CELL_STYLE_LEFT.fontSize)

    is_kv_table = ncols == 2
    headers_base = [base_header(h) for h in table[0]]
    risk_cols = [] if is_kv_table else risk_grade_column_indices(style, headers_base)

    table_style_commands = list(_BASE_TABLE_STYLE_COMMANDS)
    data = []
    ai_value_present = False

    for row_index, row in enumerate(table):
        is_header_row = row_index == 0
        row_cells = []
        for col_index in range(ncols):
            raw = row[col_index] if col_index < len(row) else ""
            value, note = parse_ai_score_cell(raw)
            text = str(value) if value is not None else raw
            if note:
                ai_value_present = True

            center, fill_hex = cell_style_decision(
                style, headers_base, risk_cols, is_kv_table, is_header_row, col_index, text
            )
            # 다중열 표(위험성평가표 등)의 헤더 행 색(style.header_fill)은
            # document_styles의 공유 스펙(XLSX/HWPX와 동일)이라 진한 남색이다.
            # XLSX/HWPX는 건드리지 않고 PDF에서만 더 연한 톤으로 바꿔 쓴다
            # (2026-08-04 실사용 PDF 확인 후 "너무 진하다"는 피드백으로 추가).
            if fill_hex == style.header_fill:
                fill_hex = _PDF_HEADER_FILL
            cell_style = _CELL_STYLE_CENTER if center else _CELL_STYLE_LEFT
            safe_text = _fit_cell_text(text, col_widths[col_index], cell_style.fontSize)
            row_cells.append(Paragraph(escape(safe_text), cell_style))

            if fill_hex:
                table_style_commands.append(
                    ("BACKGROUND", (col_index, row_index), (col_index, row_index), _hex_color(fill_hex))
                )
        data.append(row_cells)

    # repeatRows=1: 표가 페이지 경계를 넘어가면 0번째 행(헤더)을 다음
    # 페이지에도 반복해서 그린다.
    row_heights = None
    if is_signature_table:
        row_heights = [None] + [_SIGNATURE_ROW_HEIGHT_PT] * (len(table) - 1)

    table_flowable = Table(
        data, colWidths=col_widths, rowHeights=row_heights, hAlign="LEFT",
        style=TableStyle(table_style_commands), repeatRows=1,
    )
    return table_flowable, ai_value_present


def _build_elements(blocks, document_type, doc_width):
    """
    parse_markdown_blocks()의 결과를 reportlab 플로어블 리스트로 바꾼다.
    박스 제목(헤딩) 바로 다음에 오는 내용(표·본문)은 Indenter로
    _CONTENT_INDENT_PT만큼 들여써서, 제목에 종속된 내용임이 시각적으로
    드러나게 한다. 표에 실제로 배정되는 폭도 그만큼 줄어든다(안 그러면
    표가 페이지 우측 여백을 넘어간다).
    """
    elements = [_TitleFlowable(document_type), Spacer(1, 12)]

    if not blocks:
        return elements

    indent_open = False
    last_heading_text = None
    for block in blocks:
        if block["type"] == "heading":
            if indent_open:
                elements.append(Indenter(left=-_CONTENT_INDENT_PT))
            last_heading_text = block["text"]
            elements.append(Paragraph(escape(block["text"]), _BOX_TITLE_STYLE))
            elements.append(Indenter(left=_CONTENT_INDENT_PT))
            indent_open = True
        elif block["type"] == "text":
            body_text = escape(block["text"]).replace("\n", "<br/>")
            elements.append(Paragraph(body_text, _BODY_STYLE))
            elements.append(Spacer(1, 8))
        else:
            effective_width = doc_width - (_CONTENT_INDENT_PT if indent_open else 0)
            table_flowable, ai_value_present = _build_table_element(
                block["rows"], effective_width, document_type,
                is_signature_table=_is_signature_heading(last_heading_text),
            )
            elements.append(table_flowable)
            if ai_value_present:
                elements.append(Spacer(1, 4))
                elements.append(Paragraph(AI_SCORE_FOOTNOTE, _FOOTNOTE_STYLE))
            elements.append(Spacer(1, 12))

    if indent_open:
        elements.append(Indenter(left=-_CONTENT_INDENT_PT))

    return elements


def record_to_pdf_bytes(record):
    """
    record["draft"]에서 헤딩(박스 제목)·표·서술형 문단을 순서대로 파싱해
    문서를 만든다. 표 셀은 Paragraph로 감싸 렌더링하므로 원문을 그대로
    넣기 전에 escape()한다. draft가 완전히 비어있는 경우(이론상 거의 없음)만
    원문 그대로 한 문단으로 넣는다.
    """
    blocks = parse_markdown_blocks(record["draft"])
    document_type = record["document_type"]

    buffer = io.BytesIO()
    # title/author: reportlab이 PDF 메타데이터(Author/Title)에 그대로 채워
    # 넣는 표준 생성자 인자 — 이전 QA에서 지적된 "메타데이터 공란" 문제 해결.
    doc = SimpleDocTemplate(
        buffer, pagesize=_page_size_for(document_type),
        title=document_type, author="Safety-RAG",
        topMargin=_PAGE_MARGIN_PT, bottomMargin=_PAGE_MARGIN_PT,
        leftMargin=_PAGE_MARGIN_PT, rightMargin=_PAGE_MARGIN_PT,
    )

    elements = _build_elements(blocks, document_type, doc.width)
    if not blocks:
        elements.append(Paragraph(escape(record["draft"]).replace("\n", "<br/>"), _BODY_STYLE))

    doc.build(elements)
    return buffer.getvalue()
