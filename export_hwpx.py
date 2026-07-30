"""
저장된 프로젝트 기록(record["draft"]의 Markdown 텍스트)을 파싱해
python-hwpx 문서로 바인딩하고, .hwpx 파일 바이트를 반환한다.

XLSX(export_xlsx.py)와 동일하게 parse_markdown_tables()를 공용으로 쓴다.
스타일은 단순 테이블(제목 + 표 + 기본 테두리)만 적용한다 — 베타0 피드백에서
HWPX에 대한 명시적 수요 신호가 없었으므로 색상 등 XLSX 수준의 장식은 넣지
않는다(docs/superpowers/specs/2026-07-28-hwpx-pdf-export-design.md 참고).
표 폭만은 예외로 페이지 폭에 맞춘다 — 지정하지 않으면 python-hwpx가 열 개수
x 고정폭(7200 유닛)으로 표를 만들어, 위험성평가표처럼 열이 많은 표는 페이지
폭을 넘어 잘리고 반대로 열이 적은 표는 페이지 폭의 일부만 채우는 문제가
있었다(export_pdf.py가 frame_width 기준으로 colWidths를 계산하는 것과 동일한
문제 — PDF는 커밋 945966b에서 수정됨).
"""

from hwpx import HwpxDocument

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

    doc.add_paragraph(record["document_type"])
    doc.add_paragraph("")

    if not tables:
        doc.add_paragraph(record["draft"])
        return doc.to_bytes()

    for table in tables:
        rows = len(table)
        cols = max(len(row) for row in table)
        # width를 지정해야 열 너비가 usable_width 안에서 균등 분배된다
        # (_distribute_size) — 미지정 시 열 개수와 무관하게 고정폭이 쓰인다.
        hwpx_table = doc.add_table(rows, cols, width=usable_width)
        # 표가 페이지 경계를 넘어갈 때 헤더 행(0번째 행)이 다음 페이지에도
        # 반복되도록 한다. python-hwpx 고수준 API엔 없지만, HWPX 표 XML이
        # 이미 이 속성을 지원한다(기본값 "0" 확인, "1"로 저장 후 재오픈해도
        # 유지되는 것 검증 완료).
        hwpx_table.element.set("repeatHeader", "1")
        for row_index, row_cells in enumerate(table):
            for col_index, value in enumerate(row_cells):
                hwpx_table.set_cell_text(row_index, col_index, value)
        doc.add_paragraph("")

    return doc.to_bytes()
