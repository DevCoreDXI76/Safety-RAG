# -*- coding: utf-8 -*-
"""
python-hwpx PoC — 실제 발주처 .hwpx 서식 없이, 라이브러리 자체 기능만 검증.

확인 목표 (개발자 체크리스트 D-15):
1. 한컴오피스 설치 없이 순수 파이썬으로 .hwpx 문서를 새로 만들 수 있는가
2. 표를 만들고 셀에 텍스트를 채워 넣을 수 있는가 (표준작업계획서/위험성평가표의
   핵심 요구사항 — [작업단계-유해위험요인-안전조치-위험도] 표 채우기)
3. 저장된 파일이 유효한 .hwpx(zip+XML) 형식이고, 다시 열어서 읽으면
   방금 쓴 내용이 그대로 나오는가 (왕복 검증)

API 출처: pip install python-hwpx (3.0.0) 설치 후 hwpx.HwpxDocument /
hwpx.document.HwpxOxmlTable을 실제 introspection으로 확인한 메서드만 사용
— 추측으로 작성하지 않음.

사용 예:
  python test_hwpx_poc.py
"""
import sys
import zipfile

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from hwpx import HwpxDocument

OUTPUT_PATH = "hwpx_poc_output.hwpx"

TITLE = "표준 작업계획서 (굴착작업) — python-hwpx PoC"

TABLE_HEADER = ["작업단계", "유해·위험요인", "안전조치", "위험도"]
TABLE_ROWS = [
    ["사전조사", "매설물 손상(가스·전력·상수도)", "매설물 관리기관 확인 및 이설·보호대책 수립", "높음"],
    ["굴착", "토사 붕괴", "흙막이 지보공 설치, 구배 기준 준수", "높음"],
    ["되메우기", "장비 협착", "신호수 배치, 출입 통제", "중간"],
]


def build_document():
    doc = HwpxDocument.new()
    doc.add_paragraph(TITLE)
    doc.add_paragraph("")

    rows = len(TABLE_ROWS) + 1  # 헤더 포함
    cols = len(TABLE_HEADER)
    table = doc.add_table(rows, cols)

    for col_index, header in enumerate(TABLE_HEADER):
        table.set_cell_text(0, col_index, header)

    for row_offset, row_data in enumerate(TABLE_ROWS, start=1):
        for col_index, value in enumerate(row_data):
            table.set_cell_text(row_offset, col_index, value)

    doc.add_paragraph("")
    doc.add_paragraph("작성자: ______________   검토자: ______________   승인자: ______________")

    doc.save_to_path(OUTPUT_PATH)
    return OUTPUT_PATH


def verify_zip_structure(path):
    """.hwpx가 실제로 유효한 zip 컨테이너인지 (한컴오피스 없이도 이 정도는 확인 가능)"""
    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()
        bad_file = zf.testzip()
        return names, bad_file


def verify_roundtrip(path):
    """저장한 파일을 다시 열어서, 방금 쓴 제목·표 내용이 그대로 읽히는지 확인"""
    doc2 = HwpxDocument.open(path)
    full_text = doc2.export_text()
    table_map = doc2.get_table_map()
    return full_text, table_map


def run():
    print("=== python-hwpx PoC ===\n")

    print("[1] 문서 생성 + 표 채우기...")
    path = build_document()
    print(f"    -> 저장 완료: {path}")

    print("\n[2] zip(.hwpx) 구조 유효성 확인...")
    names, bad_file = verify_zip_structure(path)
    print(f"    -> zip 내부 파일 수: {len(names)}, 손상 파일: {bad_file}")
    for n in names[:8]:
        print(f"       - {n}")

    print("\n[3] 재오픈 후 왕복(round-trip) 검증...")
    full_text, table_map = verify_roundtrip(path)

    checks = []
    checks.append(("제목 텍스트 보존", TITLE in full_text))
    checks.append(("헤더 텍스트 보존", all(h in full_text for h in TABLE_HEADER)))
    checks.append(("데이터 셀 텍스트 보존", all(row[1] in full_text for row in TABLE_ROWS)))
    checks.append(("표 1개 인식됨", len(table_map) == 1))

    print()
    all_ok = True
    for name, ok in checks:
        status = "PASS" if ok else "FAIL"
        if ok is None:
            status = "SKIP(구조 확인 필요)"
        else:
            all_ok = all_ok and ok
        print(f"[{status}] {name}")

    print("\n" + "=" * 50)
    print("전체 결과:", "PASS" if all_ok else "FAIL (위 로그 확인)")
    print(f"\n생성된 파일: {path} (실제 한글/한컴오피스로도 직접 열어서 육안 확인 권장)")


if __name__ == "__main__":
    run()
