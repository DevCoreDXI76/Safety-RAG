# -*- coding: utf-8 -*-
"""
export_xlsx.py/export_pdf.py/export_hwpx.py 3포맷 스타일 일관성 검증 —
같은 레코드를 세 포맷으로 내려받았을 때 같은 위험성평가표 spec 색상을
쓰는지 교차 확인한다(docs/superpowers/specs/2026-07-31-공유-스타일-스펙-design.md
"테스트 계획" 3번).

사용 예:
  pip install pypdf   # 최초 1회
  python test_export_style_consistency.py
"""
import io
import sys
import zipfile

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from openpyxl import load_workbook

from document_styles import STYLE_SPECS
from export_hwpx import record_to_hwpx_bytes
from export_pdf import _build_table_element, _hex_color
from export_xlsx import record_to_xlsx_bytes
from markdown_tables import parse_markdown_tables
from reportlab.lib.pagesizes import A4, landscape

RECORD = {
    "id": "consistency1",
    "document_type": "위험성평가표",
    "project_info": "일관성 검증용 샘플",
    "draft": (
        "| 위험요인 | 빈도 | 강도 | 위험등급 | 개선후 위험등급 |\n"
        "|----------|------|------|----------|------------------|\n"
        "| 지게차 충돌 | 3(AI 제안값, 현장 확인 필수) | 2(AI 제안값, 현장 확인 필수) | "
        "A(AI 제안값, 현장 확인 필수) | B(AI 제안값, 현장 확인 필수) |\n"
    ),
    "created_at": "2026-07-31 00:00:00",
}


def run():
    print("=== 3포맷 스타일 일관성 검증 ===\n")
    checks = []
    style = STYLE_SPECS["위험성평가표"]

    # XLSX: 위험등급 열(D, 1-indexed 4번째)에 A등급 조건부서식이 걸려있고, 색상이 스펙과 일치하는지
    xlsx_bytes = record_to_xlsx_bytes(RECORD)
    ws = load_workbook(io.BytesIO(xlsx_bytes)).active
    xlsx_a_rule_ok = False
    for rules in ws.conditional_formatting._cf_rules.values():
        for rule in rules:
            if rule.formula == ['"A"'] and hasattr(rule, 'dxf') and rule.dxf and hasattr(rule.dxf, 'fill') and rule.dxf.fill:
                # XLSX에서 fill color는 ARGB 형식 (e.g., '00F8CBAD' — leading '00'은 alpha)
                # 뒤의 6자리 hex가 style spec과 일치하는지 확인
                rgb = rule.dxf.fill.fgColor.rgb
                if rgb.upper().endswith(style.risk_grade_colors["A"]):
                    xlsx_a_rule_ok = True
                    break
    checks.append(("XLSX: 위험등급 A 조건부서식 존재하고 색상이 스펙과 일치", xlsx_a_rule_ok))
    checks.append((
        "XLSX: 열너비가 스펙과 일치(1열=빈도폭이 아니라 위험요인 열 폭)",
        ws.column_dimensions["A"].width == style.column_widths[0],
    ))

    # PDF: 같은 표를 만들 때 위험등급 A 배경색 명령이 들어가고, 색상이 스펙과 일치하는지
    tables = parse_markdown_tables(RECORD["draft"])
    frame_width = landscape(A4)[0] - 2 * 72
    table_flowable, ai_present = _build_table_element(tables[0], frame_width, RECORD["document_type"])
    bg_commands = table_flowable._bkgrndcmds
    checks.append(("PDF: AI 제안값 감지됨", ai_present is True))
    # cmd 구조: ('BACKGROUND', (col, row), (col, row), Color(...))
    # cmd[1] == (3, 1)인 명령을 찾고, cmd[-1] (Color 객체)가 스펙 색상과 일치하는지 확인
    pdf_a_color_ok = any(
        cmd[1] == (3, 1) and cmd[-1] == _hex_color(style.risk_grade_colors["A"])
        for cmd in bg_commands
    )
    checks.append((
        "PDF: 위험등급 A 셀(열3,행1)에 배경색이 스펙과 일치하는 명령 존재",
        pdf_a_color_ok,
    ))

    # HWPX: 같은 hex 색상이 XML에 기록되는지
    hwpx_bytes = record_to_hwpx_bytes(RECORD)
    with zipfile.ZipFile(io.BytesIO(hwpx_bytes)) as zf:
        header_xml = zf.read("Contents/header.xml").decode("utf-8", errors="ignore")
    checks.append((
        "HWPX: 위험등급 A 배경색이 XLSX/PDF와 같은 hex로 기록됨",
        style.risk_grade_colors["A"] in header_xml.upper(),
    ))
    checks.append((
        "HWPX: 위험등급 B 배경색이 XLSX/PDF와 같은 hex로 기록됨",
        style.risk_grade_colors["B"] in header_xml.upper(),
    ))

    print()
    all_ok = True
    for name, ok in checks:
        status = "PASS" if ok else "FAIL"
        all_ok = all_ok and ok
        print(f"[{status}] {name}")

    print("\n" + "=" * 50)
    print("전체 결과:", "PASS" if all_ok else "FAIL (위 로그 확인)")
    return all_ok


if __name__ == "__main__":
    run()
