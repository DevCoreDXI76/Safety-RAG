# -*- coding: utf-8 -*-
"""
export_hwpx.py 스모크 테스트 — 실제 저장된 기록을 HWPX로 변환해 zip 구조
유효성·텍스트 보존·문서유형별 스타일(열비율/배경색) 적용을 확인한다.
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

from document_styles import STYLE_SPECS
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

SAMPLE_RECORD_WITH_SCORE = {
    "document_type": "위험성평가표",
    "draft": (
        "| 위험요인 | 빈도 | 강도 | 위험등급 | 개선후 위험등급 |\n"
        "|----------|------|------|----------|------------------|\n"
        "| 지게차 충돌 | 3(AI 제안값, 현장 확인 필수) | 2(AI 제안값, 현장 확인 필수) | "
        "A(AI 제안값, 현장 확인 필수) | B(AI 제안값, 현장 확인 필수) |\n"
    ),
}


def run():
    print("=== export_hwpx.py 스모크 테스트 ===\n")

    checks = []

    hwpx_bytes = record_to_hwpx_bytes(SAMPLE_RECORD)

    with zipfile.ZipFile(io.BytesIO(hwpx_bytes)) as zf:
        bad_file = zf.testzip()

    doc2 = HwpxDocument.open(hwpx_bytes)
    full_text = doc2.export_text()
    table_map = doc2.get_table_map()

    checks.append(("문서종류 제목 보존", SAMPLE_RECORD["document_type"] in full_text))
    checks.append(("표 1개 인식됨", len(table_map) == 1))
    checks.append(("표 내용(작업단계/감소대책) 보존", "작업단계" in full_text and "매설물 관리기관" in full_text))
    checks.append(("손상 파일 없음", bad_file is None))

    # --- 스타일(열비율/배경색/AI 제안값 각주) 검증 ---
    # HWPX는 색상이 Contents/header.xml에 borderFill 정의로 저장된다 — 색상
    # 문자열이 실제로 XML에 쓰였는지로 셀 음영 적용 여부를 확인한다.
    risk_style = STYLE_SPECS["위험성평가표"]
    hwpx_bytes_score = record_to_hwpx_bytes(SAMPLE_RECORD_WITH_SCORE)
    with zipfile.ZipFile(io.BytesIO(hwpx_bytes_score)) as zf:
        header_xml = zf.read("Contents/header.xml").decode("utf-8", errors="ignore")

    checks.append((
        "헤더 배경색(header_fill)이 XML에 기록됨",
        risk_style.header_fill in header_xml.upper(),
    ))
    checks.append((
        "위험등급 A 배경색이 XML에 기록됨",
        risk_style.risk_grade_colors["A"] in header_xml.upper(),
    ))
    checks.append((
        "위험등급 B 배경색이 XML에 기록됨",
        risk_style.risk_grade_colors["B"] in header_xml.upper(),
    ))

    doc_score = HwpxDocument.open(hwpx_bytes_score)
    full_text_score = doc_score.export_text()
    checks.append((
        "AI 제안값 셀은 순수값만 표시(안내문구는 셀에 없음)",
        "AI 제안값" not in full_text_score.split("※")[0],
    ))
    checks.append(("AI 제안값 각주가 표 아래에 1회 표기됨", full_text_score.count("AI 제안값") == 1))

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
