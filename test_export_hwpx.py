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
    print("=== export_hwpx.py 스모크 테스트 ===\n")

    record = SAMPLE_RECORD

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
    checks.append(("표 내용(작업단계/감소대책) 보존", "작업단계" in full_text and "매설물 관리기관" in full_text))
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
