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
import xml.etree.ElementTree as ET
import zipfile

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from hwpx import HwpxDocument

from document_styles import STYLE_SPECS
from export_hwpx import record_to_hwpx_bytes

_HP_NS = "{http://www.hancom.co.kr/hwpml/2011/paragraph}"


def _row0_cell_widths(hwpx_bytes):
    """section0.xml 첫 번째 표의 0번째 행 셀 폭을 colAddr 순서로 반환한다
    (test_export_style_consistency.py의 _hwpx_row0_cell_widths와 동일한 방식)."""
    with zipfile.ZipFile(io.BytesIO(hwpx_bytes)) as zf:
        section_xml = zf.read("Contents/section0.xml")
    root = ET.fromstring(section_xml)
    first_table = root.find(f".//{_HP_NS}tbl")
    widths = []
    for tc in first_table.findall(f"{_HP_NS}tr/{_HP_NS}tc"):
        addr = tc.find(f"{_HP_NS}cellAddr")
        sz = tc.find(f"{_HP_NS}cellSz")
        if addr is not None and sz is not None and addr.get("rowAddr") == "0":
            widths.append((int(addr.get("colAddr")), int(sz.get("width"))))
    widths.sort(key=lambda pair: pair[0])
    return [w for _, w in widths]

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

# PDF/XLSX와 동일하게 박스 제목(헤딩)·서술형 문단이 표 사이에 순서대로
# 보존되는지 확인한다(2026-08-05, HWPX가 parse_markdown_tables만 써서 표
# 없는 헤딩·문단을 통째로 버리던 문제).
SAMPLE_RECORD_WITH_HEADING_AND_PROSE = {
    "document_type": "TBM 일지",
    "draft": (
        "# TBM 일지 초안\n\n"
        "## ■ 기본 정보\n\n"
        "| 항목 | 내용 |\n"
        "|------|------|\n"
        "| 현장명 | 강남지사 |\n\n"
        "## ■ 핵심 위험요인\n\n"
        "| 번호 | 유해위험요인 | 대책 |\n"
        "|------|------|------|\n"
        "| 1 | 감전 | 절연장갑 착용 |\n\n"
        "### 3. 중점(One Point) 위험요인\n\n"
        "오늘은 활선 근접 작업이 포함되어 있으므로 무전압 상태를 반드시 확인한다.\n"
    ),
}

# PDF/XLSX와 동일하게 "(빈칸 - 현장 기재)"류 플레이스홀더를 연한 회색으로
# 구분 표시하는지 확인한다.
SAMPLE_RECORD_PLACEHOLDER = {
    "document_type": "TBM 일지",
    "draft": (
        "| 항목 | 내용 |\n|------|------|\n"
        "| 작업일자 | (빈칸 - 현장 기재) |\n"
        "| 작성자 | 김철수, (빈칸 - 현장 기재) |\n\n"
        "## ■ 비고\n\n"
        "특이사항 없음. 서명: (빈칸 - 현장 기재)\n"
    ),
}

# XLSX(export_xlsx.py)와 동일하게 위험성평가표는 열 내용 기반으로 폭을
# 정해야 한다 — 정적 비율([6, 20, 32, ...])을 쓰면 "빈도"(한 글자)가 위치만으로
# "위험성 감소대책 상세 설명"보다 부풀려진다.
SAMPLE_RECORD_RISK_WIDE_NARROW = {
    "document_type": "위험성평가표",
    "draft": (
        "| 단위작업 | 빈도 | 위험성 감소대책 상세 설명 |\n"
        "|------|------|------|\n"
        "| 굴착 | 3 | 흙막이 지보공 설치, 구배 기준 준수, 굴착 깊이 확인 등 상세한 대책을 서술한다 |\n"
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

    # --- 박스 제목(헤딩)·서술형 문단 보존 검증 ---
    hwpx_bytes_heading = record_to_hwpx_bytes(SAMPLE_RECORD_WITH_HEADING_AND_PROSE)
    doc_heading = HwpxDocument.open(hwpx_bytes_heading)
    full_text_heading = doc_heading.export_text()

    checks.append(("박스 제목(■ 기본 정보) 보존", "■ 기본 정보" in full_text_heading))
    checks.append(("박스 제목(■ 핵심 위험요인) 보존", "■ 핵심 위험요인" in full_text_heading))
    checks.append((
        "서술형 문단(표 없는 섹션) 보존",
        "활선 근접 작업이 포함되어 있으므로" in full_text_heading,
    ))

    # --- 플레이스홀더 회색 처리 검증 ---
    hwpx_bytes_ph = record_to_hwpx_bytes(SAMPLE_RECORD_PLACEHOLDER)
    with zipfile.ZipFile(io.BytesIO(hwpx_bytes_ph)) as zf:
        header_xml_ph = zf.read("Contents/header.xml").decode("utf-8", errors="ignore")
    doc_ph = HwpxDocument.open(hwpx_bytes_ph)
    checks.append((
        "플레이스홀더 텍스트 보존",
        "(빈칸 - 현장 기재)" in doc_ph.export_text(),
    ))
    checks.append((
        "플레이스홀더 회색(#999999) charPr가 XML에 기록됨",
        # header.xml 기본 서식(hc:winBrush hatchColor="#999999")과 혼동되지
        # 않도록 textColor 속성으로만 판정한다.
        'textColor="#999999"' in header_xml_ph,
    ))

    # --- 위험성평가표 콘텐츠 기반 열너비 검증 ---
    hwpx_bytes_width = record_to_hwpx_bytes(SAMPLE_RECORD_RISK_WIDE_NARROW)
    widths = _row0_cell_widths(hwpx_bytes_width)
    # widths = [단위작업, 빈도, 위험성 감소대책 상세 설명]. 정적 비율([6, 20, 32, ...])이면
    # 빈도(20)가 단위작업(6)보다 넓어지는 역전이 생긴다 — 콘텐츠 기반이면 짧은 값인
    # "빈도" 열이 서술형 설명 열보다 훨씬 좁아야 한다.
    checks.append((
        "빈도(짧은 값) 열이 서술형 설명 열보다 훨씬 좁음 (콘텐츠 기반 폭)",
        len(widths) == 3 and widths[2] > widths[1] * 3,
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
