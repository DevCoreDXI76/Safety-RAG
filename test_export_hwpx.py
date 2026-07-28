# -*- coding: utf-8 -*-
"""
export_hwpx.py 스모크 테스트 — 실제 저장된 기록(xlsx_export_test_user 프로젝트,
위험성평가표 1건)을 HWPX로 변환해 zip 구조 유효성과 텍스트 보존을 확인한다.
python-hwpx 도입 PoC(test_hwpx_poc.py)와 동일한 검증 방식을 재사용한다.

사용 예:
  python test_export_hwpx.py
"""
import io
import sys
import zipfile

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from hwpx import HwpxDocument

from export_hwpx import record_to_hwpx_bytes
from generate_draft import get_record_by_id

TEST_USER_ID = "xlsx_export_test_user"
TEST_PROJECT_NAME = "xlsx_export_테스트현장"
TEST_RECORD_ID = "20c1c6d12755"


def run():
    print("=== export_hwpx.py 스모크 테스트 ===\n")

    record = get_record_by_id(TEST_USER_ID, TEST_PROJECT_NAME, TEST_RECORD_ID)
    assert record is not None, "테스트 픽스처 기록을 찾지 못함 — data/projects 확인 필요"

    print("[1] HWPX 바이트 생성...")
    hwpx_bytes = record_to_hwpx_bytes(record)
    print(f"    -> {len(hwpx_bytes)} bytes")

    print("\n[2] zip 구조 유효성 확인...")
    with zipfile.ZipFile(io.BytesIO(hwpx_bytes)) as zf:
        bad_file = zf.testzip()
    print(f"    -> 손상 파일: {bad_file}")

    print("\n[3] 재오픈 후 텍스트 보존 확인...")
    doc2 = HwpxDocument.open(hwpx_bytes)
    full_text = doc2.export_text()
    table_map = doc2.get_table_map()

    checks = []
    checks.append(("문서종류 제목 보존", record["document_type"] in full_text))
    checks.append(("표 1개 인식됨", len(table_map) == 1))
    checks.append(("표 내용(현장명) 보존", "현장명" in full_text and "테스트현장" in full_text))
    checks.append(("손상 파일 없음", bad_file is None))

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
