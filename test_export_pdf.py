# -*- coding: utf-8 -*-
"""
export_pdf.py 스모크 테스트 — 실제 저장된 기록(xlsx_export_test_user 프로젝트,
위험성평가표 1건)을 PDF로 변환해 파일 유효성과 한글 텍스트 보존을 확인한다.
텍스트 추출은 pypdf를 쓴다(런타임 의존성 아님 — 이 스크립트 실행 전
`pip install pypdf`로 별도 설치 필요, requirements.txt엔 넣지 않음).

사용 예:
  pip install pypdf   # 최초 1회
  python test_export_pdf.py
"""
import io
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import pypdf
from reportlab.lib.pagesizes import A4, landscape

from export_pdf import _build_table_element, record_to_pdf_bytes
from markdown_tables import parse_markdown_tables

SAMPLE_RECORD = {
    "document_type": "위험성평가표",
    "draft": (
        "| 작업단계 | 유해위험요인 | 감소대책 | 위험성 |\n"
        "|------|------|------|------|\n"
        "| 사전조사 | 매설물 손상(가스·전력·상수도) | 매설물 관리기관 확인 및 이설·보호대책 수립, "
        "굴착 착수 전 관계 기관(한국가스공사, 한전, 상수도사업본부 등) 협의 후 착공계 제출 | 9 |\n"
        "| 굴착 | 토사 붕괴 | 흙막이 지보공 설치, 구배 기준 준수, 굴착 깊이 2m 이상 시 사다리 등 승강설비 설치 | 12 |\n"
        "| 되메우기 | 장비 협착 | 신호수 배치, 출입 통제, 후진 경고음 확인 | 6 |\n"
    ),
}


def run():
    print("=== export_pdf.py 스모크 테스트 ===\n")

    record = SAMPLE_RECORD

    print("[1] PDF 바이트 생성...")
    pdf_bytes = record_to_pdf_bytes(record)
    print(f"    -> {len(pdf_bytes)} bytes")

    print("\n[2] PDF 매직바이트 확인...")
    is_pdf = pdf_bytes[:5] == b"%PDF-"
    print(f"    -> %PDF- 로 시작함: {is_pdf}")

    print("\n[3] 텍스트 추출 후 한글 보존 확인...")
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    full_text = "".join(page.extract_text() for page in reader.pages)

    print("\n[4] 표가 페이지 폭 안에 들어가는지(clipping 없음) 확인...")
    # export_pdf.py가 실제로 표를 만드는 함수(_build_table_element)를 그대로 호출해
    # wrap() 결과 폭을 검사한다 — 이 테스트 안에서 colWidths 로직을 별도로
    # 재구현하면 production 코드가 회귀해도(예: colWidths를 빼먹는 실수) 테스트가
    # 이를 감지하지 못하는 tautology가 되므로, 반드시 실제 production 함수를 호출한다.
    tables = parse_markdown_tables(SAMPLE_RECORD["draft"])
    frame_width = landscape(A4)[0] - 2 * 72  # reportlab 기본 여백(~1인치) 기준, SimpleDocTemplate 기본값과 일치
    fits = True
    for table in tables:
        w, h = _build_table_element(table, frame_width).wrap(frame_width, 10000)
        if w > frame_width + 1:  # +1pt: 부동소수점 오차 허용
            fits = False

    checks = []
    checks.append(("PDF 매직바이트", is_pdf))
    checks.append(("문서종류 제목 보존", record["document_type"] in full_text))
    checks.append(("표 내용(작업단계/감소대책) 보존", "작업단계" in full_text and "매설물 관리기관" in full_text))
    checks.append(("모든 표가 페이지 폭 안에 들어감(clipping 없음)", fits))

    print()
    all_ok = True
    for name, ok in checks:
        status = "PASS" if ok else "FAIL"
        all_ok = all_ok and ok
        print(f"[{status}] {name}")

    print("\n" + "=" * 50)
    print("전체 결과:", "PASS" if all_ok else "FAIL (위 로그 확인)")


if __name__ == "__main__":
    run()
