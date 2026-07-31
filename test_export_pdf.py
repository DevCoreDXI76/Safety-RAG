# -*- coding: utf-8 -*-
"""
export_pdf.py 스모크 테스트 — 실제 저장된 기록을 PDF로 변환해 파일 유효성·
한글 텍스트 보존·문서유형별 스타일(열비율/배경색/정렬) 적용을 확인한다.
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
    print("=== export_pdf.py 스모크 테스트 ===\n")

    checks = []

    pdf_bytes = record_to_pdf_bytes(SAMPLE_RECORD)
    is_pdf = pdf_bytes[:5] == b"%PDF-"
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    full_text = "".join(page.extract_text() for page in reader.pages)

    tables = parse_markdown_tables(SAMPLE_RECORD["draft"])
    frame_width = landscape(A4)[0] - 2 * 72
    fits = True
    for table in tables:
        table_flowable, _ = _build_table_element(table, frame_width, SAMPLE_RECORD["document_type"])
        w, h = table_flowable.wrap(frame_width, 10000)
        if w > frame_width + 1:  # +1pt: 부동소수점 오차 허용
            fits = False

    checks.append(("PDF 매직바이트", is_pdf))
    checks.append(("문서종류 제목 보존", SAMPLE_RECORD["document_type"] in full_text))
    checks.append(("표 내용(작업단계/감소대책) 보존", "작업단계" in full_text and "매설물 관리기관" in full_text))
    checks.append(("모든 표가 페이지 폭 안에 들어감(clipping 없음)", fits))

    # --- 스타일(열비율/배경색/AI 제안값 각주) 검증 ---
    score_tables = parse_markdown_tables(SAMPLE_RECORD_WITH_SCORE["draft"])
    score_table = score_tables[0]
    score_flowable, ai_present = _build_table_element(
        score_table, frame_width, SAMPLE_RECORD_WITH_SCORE["document_type"]
    )
    checks.append(("AI 제안값이 있는 표는 ai_value_present=True", ai_present is True))

    bg_commands = score_flowable._bkgrndcmds
    checks.append((
        "헤더 행에 header_fill 배경색 적용",
        any(cmd[1] == (0, 0) for cmd in bg_commands),
    ))
    checks.append((
        "위험등급 'A' 셀에 A등급 배경색 적용 (열3=위험등급, 행1)",
        any(cmd[1] == (3, 1) for cmd in bg_commands),
    ))
    checks.append((
        "개선후 위험등급 'B' 셀에 B등급 배경색 적용 (열4=개선후 위험등급, 행1)",
        any(cmd[1] == (4, 1) for cmd in bg_commands),
    ))

    pdf_bytes_score = record_to_pdf_bytes(SAMPLE_RECORD_WITH_SCORE)
    reader_score = pypdf.PdfReader(io.BytesIO(pdf_bytes_score))
    full_text_score = "".join(page.extract_text() for page in reader_score.pages)
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
