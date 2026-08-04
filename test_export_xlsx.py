import io
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from openpyxl import load_workbook
from export_xlsx import record_to_xlsx_bytes

SAMPLE_RECORD = {
    "id": "abc123",
    "document_type": "위험성평가표",
    "project_info": "강남지사 광케이블 지중매설",
    "draft": (
        "# 위험성평가표 초안\n\n"
        "## ■ 기본 정보\n\n"
        "| 항목 | 내용 |\n"
        "|------|------|\n"
        "| **현장명** | 강남지사_광케이블 |\n"
        "| **작성일** | 2026-07-20 |\n\n"
        "## ■ 위험요인\n\n"
        "| 순번 | 위험요인 | 위험성 |\n"
        "|------|----------|--------|\n"
        "| 1 | 추락 | 12 (AI 제안값, 현장 확인 필수) |\n"
        "| 2 | 감전 | 9 (AI 제안값, 현장 확인 필수) |\n"
    ),
    "created_at": "2026-07-22 10:00:00",
}

# 2026-08-05 실사용 XLSX 피드백: 박스 제목(헤딩)이 통째로 사라지고, 표가 아닌
# 서술형 섹션도 사라지며, kv표(항목/내용)와 다중열표의 박스 가로 크기가
# 서로 달라 보이는 문제.
SAMPLE_RECORD_WITH_HEADING_AND_PROSE = {
    "id": "heading1",
    "document_type": "TBM 일지",
    "project_info": "박스 제목/서술형 섹션 검증용",
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
    "created_at": "2026-08-05 10:00:00",
}

SAMPLE_RECORD_NO_TABLE = {
    "id": "def456",
    "document_type": "기타",
    "project_info": "표 없는 문서",
    "draft": "이 문서에는 표가 없습니다.",
    "created_at": "2026-07-22 10:00:00",
}

SAMPLE_RECORD_WITH_SCORE = {
    "id": "score1",
    "document_type": "위험성평가표",
    "project_info": "테스트용 점수 셀",
    "draft": (
        "| 위험요인 | 빈도 | 강도 | 위험등급 | 개선후 위험등급 |\n"
        "|----------|------|------|----------|------------------|\n"
        "| 지게차 충돌 | 3(AI 제안값, 현장 확인 필수) | 2(AI 제안값, 현장 확인 필수) | "
        "A(AI 제안값, 현장 확인 필수) | B(AI 제안값, 현장 확인 필수) |\n"
    ),
    "created_at": "2026-07-22 10:00:00",
}


def run():
    results = []

    xlsx_bytes = record_to_xlsx_bytes(SAMPLE_RECORD)
    wb = load_workbook(io.BytesIO(xlsx_bytes))
    ws = wb.active

    results.append(("시트명이 문서종류로 설정됨", ws.title == "위험성평가표"))

    # --- 박스 제목(헤딩)이 표 앞에 렌더링됨(2026-08-05 요청) ---
    results.append(("첫 박스 제목(헤딩)이 1행에 렌더링됨", ws.cell(row=1, column=1).value == "■ 기본 정보"))
    results.append(("박스 제목 폰트 18pt·굵게·검정", (
        ws.cell(row=1, column=1).font.size == 18
        and ws.cell(row=1, column=1).font.bold is True
        and ws.cell(row=1, column=1).font.color.rgb.endswith("000000")
    )))
    results.append(("레벨1 제목('위험성평가표 초안')은 렌더링 안 됨(문서 제목과 중복)", not any(
        ws.cell(row=r, column=1).value == "위험성평가표 초안" for r in range(1, 15)
    )))

    results.append((
        "첫 번째 표 헤더 위치(헤딩 다음 행인 2행, A2/B2) 확인",
        ws.cell(row=2, column=1).value == "항목" and ws.cell(row=2, column=2).value == "내용",
    ))
    results.append((
        "굵게(**) 제거된 셀 값 확인(표 헤더 다음 행인 3행)",
        ws.cell(row=3, column=1).value == "현장명" and ws.cell(row=3, column=2).value == "강남지사_광케이블",
    ))
    results.append(("표 헤더 행(2행) 볼드 스타일 적용 확인", ws.cell(row=2, column=1).font.bold is True))

    # --- 두 번째 박스(헤딩+표)는 첫 박스(헤딩1+표3행+빈행1=4행) 다음인 6행부터 ---
    results.append(("두 번째 박스 제목이 6행에 렌더링됨", ws.cell(row=6, column=1).value == "■ 위험요인"))
    results.append((
        "두 번째 표 헤더 위치(헤딩 다음 행인 7행) 확인",
        ws.cell(row=7, column=1).value == "순번" and ws.cell(row=7, column=2).value == "위험요인",
    ))

    # --- kv표(항목/내용, 2열)와 다른 표(3열)가 섞여 있으면, kv표의 "내용" 칸을
    # 전체 표 중 가장 넓은 열 개수만큼 병합해서 박스 가로 크기를 맞춘다 ---
    kv_merge_ranges = [str(r) for r in ws.merged_cells.ranges]
    results.append((
        "kv표 헤더 행의 '내용' 칸이 B2:C2로 병합되어 3열 표와 폭이 맞음",
        "B2:C2" in kv_merge_ranges,
    ))
    results.append((
        "kv표 데이터 행(3행)의 값 칸도 B3:C3로 병합됨",
        "B3:C3" in kv_merge_ranges,
    ))

    xlsx_bytes_empty = record_to_xlsx_bytes(SAMPLE_RECORD_NO_TABLE)
    wb2 = load_workbook(io.BytesIO(xlsx_bytes_empty))
    ws2 = wb2.active
    results.append(("표 없는 문서는 원문 텍스트를 A1에 기록", ws2.cell(row=1, column=1).value == "이 문서에는 표가 없습니다."))

    # --- 표가 아닌 서술형 섹션("3. 중점(One Point) 위험요인" 등)도 사라지지
    # 않고 렌더링됨(2026-08-05 실사용 XLSX에서 통째로 빠졌던 버그) ---
    xlsx_bytes_prose = record_to_xlsx_bytes(SAMPLE_RECORD_WITH_HEADING_AND_PROSE)
    wb_prose = load_workbook(io.BytesIO(xlsx_bytes_prose))
    ws_prose = wb_prose.active
    all_values_prose = [
        ws_prose.cell(row=r, column=1).value
        for r in range(1, ws_prose.max_row + 1)
    ]
    results.append((
        "'3. 중점(One Point) 위험요인' 박스 제목이 렌더링됨",
        "3. 중점(One Point) 위험요인" in all_values_prose,
    ))
    results.append((
        "서술형 본문 내용('무전압 상태')이 실제로 렌더링됨",
        any(v is not None and "무전압 상태" in str(v) for v in all_values_prose),
    ))
    # 두 번째 박스(핵심 위험요인, 3열)가 있으므로 max_col_count=3 — 첫 박스의
    # kv표(항목/내용)도 B:C로 병합돼 폭이 맞아야 한다.
    prose_merge_ranges = [str(r) for r in ws_prose.merged_cells.ranges]
    results.append((
        "박스 너비가 다른 표들과 안 맞던 kv표도 B:C 병합으로 폭이 맞춰짐",
        "B3:C3" in prose_merge_ranges,
    ))

    xlsx_bytes_score = record_to_xlsx_bytes(SAMPLE_RECORD_WITH_SCORE)
    wb3 = load_workbook(io.BytesIO(xlsx_bytes_score))
    ws3 = wb3.active

    results.append((
        "빈도·강도 AI 제안값이 순수 숫자로 저장됨",
        ws3.cell(row=2, column=2).value == 3
        and ws3.cell(row=2, column=3).value == 2
        and isinstance(ws3.cell(row=2, column=2).value, int),
    ))
    results.append((
        "위험등급·개선후 위험등급 AI 제안값이 순수 등급 문자로 저장됨",
        ws3.cell(row=2, column=4).value == "A"
        and ws3.cell(row=2, column=5).value == "B",
    ))
    results.append((
        "AI 제안값 안내 문구는 셀 메모(comment)로 보존됨",
        ws3.cell(row=2, column=4).comment is not None
        and "AI 제안값" in ws3.cell(row=2, column=4).comment.text,
    ))
    results.append((
        "위험등급 열에 A/B/C 등급 조건부서식이 걸림",
        any(
            rule.formula == ['"A"']
            for rules in ws3.conditional_formatting._cf_rules.values()
            for rule in rules
        ),
    ))
    results.append((
        "점수가 아닌 일반 텍스트 셀은 그대로 문자열 유지",
        ws3.cell(row=2, column=1).value == "지게차 충돌"
        and ws3.cell(row=2, column=1).comment is None,
    ))

    all_ok = True
    for name, ok in results:
        print(f"[{'PASS' if ok else 'FAIL'}] {name}")
        all_ok = all_ok and ok

    print()
    print("전체 결과:", "PASS" if all_ok else "FAIL (위 로그 확인)")
    return all_ok


if __name__ == "__main__":
    run()
