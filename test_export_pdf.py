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

from export_pdf import record_to_pdf_bytes
from generate_draft import get_record_by_id

TEST_USER_ID = "xlsx_export_test_user"
TEST_PROJECT_NAME = "xlsx_export_테스트현장"
TEST_RECORD_ID = "20c1c6d12755"


def run():
    print("=== export_pdf.py 스모크 테스트 ===\n")

    record = get_record_by_id(TEST_USER_ID, TEST_PROJECT_NAME, TEST_RECORD_ID)
    assert record is not None, "테스트 픽스처 기록을 찾지 못함 — data/projects 확인 필요"

    print("[1] PDF 바이트 생성...")
    pdf_bytes = record_to_pdf_bytes(record)
    print(f"    -> {len(pdf_bytes)} bytes")

    print("\n[2] PDF 매직바이트 확인...")
    is_pdf = pdf_bytes[:5] == b"%PDF-"
    print(f"    -> %PDF- 로 시작함: {is_pdf}")

    print("\n[3] 텍스트 추출 후 한글 보존 확인...")
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    full_text = "".join(page.extract_text() for page in reader.pages)

    checks = []
    checks.append(("PDF 매직바이트", is_pdf))
    checks.append(("문서종류 제목 보존", record["document_type"] in full_text))
    checks.append(("표 내용(현장명) 보존", "현장명" in full_text and "테스트현장" in full_text))

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
