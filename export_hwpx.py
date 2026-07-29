"""
저장된 프로젝트 기록(record["draft"]의 Markdown 텍스트)을 파싱해
python-hwpx 문서로 바인딩하고, .hwpx 파일 바이트를 반환한다.

XLSX(export_xlsx.py)와 동일하게 parse_markdown_tables()를 공용으로 쓴다.
스타일은 단순 테이블(제목 + 표 + 기본 테두리)만 적용한다 — 베타0 피드백에서
HWPX에 대한 명시적 수요 신호가 없었으므로 색상·열너비 등 XLSX 수준의
장식은 넣지 않는다(docs/superpowers/specs/2026-07-28-hwpx-pdf-export-design.md 참고).
"""

from hwpx import HwpxDocument

from markdown_tables import parse_markdown_tables


def record_to_hwpx_bytes(record):
    """
    record["draft"]에서 Markdown 표를 순서대로 파싱해 표로 채운다.
    표가 없으면 draft 원문을 문단 하나로 그대로 넣는다(XLSX의 "표 없으면
    원문 그대로" 규칙과 동일 취지).
    """
    tables = parse_markdown_tables(record["draft"])

    doc = HwpxDocument.new()
    doc.add_paragraph(record["document_type"])
    doc.add_paragraph("")

    if not tables:
        doc.add_paragraph(record["draft"])
        return doc.to_bytes()

    for table in tables:
        rows = len(table)
        cols = max(len(row) for row in table)
        hwpx_table = doc.add_table(rows, cols)
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
