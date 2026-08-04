import io
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from openpyxl import load_workbook
from document_styles import STYLE_SPECS
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

# 2026-08-05 요청: 위험성평가표는 열 폭을 셀 내용 글자수 기반으로 조정.
# "빈도" 열은 짧은 숫자만, "위험성 감소대책"은 긴 서술형 문장 — 폭이 크게
# 달라야 한다.
SAMPLE_RECORD_RISK_WIDE_NARROW = {
    "id": "widthtest1",
    "document_type": "위험성평가표",
    "project_info": "열 폭 자동조절 검증용",
    "draft": (
        "| 단위작업 | 빈도 | 위험성 감소대책 상세 설명 |\n"
        "|------|------|------|\n"
        "| 굴착 | 3 | 흙막이 지보공 설치, 구배 기준 준수, 굴착 깊이 확인 등 상세한 대책을 서술한다 |\n"
    ),
    "created_at": "2026-08-05 10:00:00",
}

SAMPLE_RECORD_OTHER_DOC_TYPE = {
    "id": "widthtest2",
    "document_type": "TBM 일지",
    "project_info": "다른 문서유형은 정적 스펙 유지 확인용",
    "draft": (
        "| 항목 | 내용 |\n"
        "|------|------|\n"
        "| 일자 | 2026-08-05 |\n"
    ),
    "created_at": "2026-08-05 10:00:00",
}


def run():
    results = []

    xlsx_bytes = record_to_xlsx_bytes(SAMPLE_RECORD)
    wb = load_workbook(io.BytesIO(xlsx_bytes))
    ws = wb.active

    results.append(("시트명이 문서종류로 설정됨", ws.title == "위험성평가표"))

    # --- 공통 1: 문서 제목(PDF와 동일하게 28pt·굵게·밑줄)이 맨 위에 렌더링됨 ---
    results.append(("문서 제목이 1행 B열에 렌더링됨", ws.cell(row=1, column=2).value == "위험성평가표"))
    results.append(("문서 제목 폰트 28pt·굵게·밑줄", (
        ws.cell(row=1, column=2).font.size == 28
        and ws.cell(row=1, column=2).font.bold is True
        and ws.cell(row=1, column=2).font.underline == "single"
    )))
    results.append(("문서 제목이 가운데정렬됨", ws.cell(row=1, column=2).alignment.horizontal == "center"))

    # --- 공통 3: A열은 공란, 모든 내용은 B열부터 ---
    results.append(("A열(1열)은 어느 행에도 값이 없음(공란)", not any(
        ws.cell(row=r, column=1).value not in (None, "") for r in range(1, ws.max_row + 1)
    )))

    # --- 박스 제목(헤딩)이 표 앞에 렌더링됨, 이제 B열부터 + 16pt(공통 2) ---
    results.append(("첫 박스 제목(헤딩)이 2행 B열에 렌더링됨", ws.cell(row=2, column=2).value == "■ 기본 정보"))
    results.append(("박스 제목 폰트 16pt·굵게·검정", (
        ws.cell(row=2, column=2).font.size == 16
        and ws.cell(row=2, column=2).font.bold is True
        and ws.cell(row=2, column=2).font.color.rgb.endswith("000000")
    )))
    results.append(("레벨1 제목('위험성평가표 초안')은 렌더링 안 됨(문서 제목과 중복)", not any(
        ws.cell(row=r, column=2).value == "위험성평가표 초안" for r in range(1, 15)
    )))

    results.append((
        "첫 번째 표 헤더 위치(헤딩 다음 행인 3행, B3/C3) 확인",
        ws.cell(row=3, column=2).value == "항목" and ws.cell(row=3, column=3).value == "내용",
    ))
    results.append((
        "굵게(**) 제거된 셀 값 확인(표 헤더 다음 행인 4행)",
        ws.cell(row=4, column=2).value == "현장명" and ws.cell(row=4, column=3).value == "강남지사_광케이블",
    ))
    results.append(("표 헤더 행(3행) 볼드+12pt 스타일 적용 확인", (
        ws.cell(row=3, column=2).font.bold is True and ws.cell(row=3, column=2).font.size == 12
    )))
    results.append(("표 데이터 셀(4행)도 12pt", ws.cell(row=4, column=3).font.size == 12))

    # --- 두 번째 박스는 첫 박스(헤딩1+표3행+빈행1=4행) 다음인 7행부터 ---
    results.append(("두 번째 박스 제목이 7행 B열에 렌더링됨", ws.cell(row=7, column=2).value == "■ 위험요인"))
    results.append((
        "두 번째 표 헤더 위치(헤딩 다음 행인 8행) 확인",
        ws.cell(row=8, column=2).value == "순번" and ws.cell(row=8, column=3).value == "위험요인",
    ))

    # --- kv표(항목/내용, 2열)와 다른 표(3열)가 섞여 있으면, kv표의 "내용" 칸을
    # 전체 표 중 가장 넓은 열 개수만큼 병합해서 박스 가로 크기를 맞춘다
    # (B열부터 시작하므로 병합 범위도 한 칸씩 밀림: C3:D3, C4:D4) ---
    merge_ranges = [str(r) for r in ws.merged_cells.ranges]
    results.append(("kv표 헤더 행의 '내용' 칸이 C3:D3로 병합되어 3열 표와 폭이 맞음", "C3:D3" in merge_ranges))
    results.append(("kv표 데이터 행(4행)의 값 칸도 C4:D4로 병합됨", "C4:D4" in merge_ranges))
    results.append(("박스 제목도 B열부터 전체 폭만큼 병합됨(B2:D2)", "B2:D2" in merge_ranges))

    # --- 표가 아예 없는(서술형 텍스트만 있는) 문서도 제목·B열 규칙을 그대로 따름 ---
    xlsx_bytes_empty = record_to_xlsx_bytes(SAMPLE_RECORD_NO_TABLE)
    wb2 = load_workbook(io.BytesIO(xlsx_bytes_empty))
    ws2 = wb2.active
    results.append(("표 없는 문서도 1행 B열에 문서 제목 렌더링", ws2.cell(row=1, column=2).value == "기타"))
    results.append((
        "표 없는 문서의 원문 텍스트는 제목 다음 행(2행) B열에 기록",
        ws2.cell(row=2, column=2).value == "이 문서에는 표가 없습니다.",
    ))

    # --- 표가 아닌 서술형 섹션("3. 중점(One Point) 위험요인" 등)도 사라지지
    # 않고 렌더링됨(2026-08-05 실사용 XLSX에서 통째로 빠졌던 버그) ---
    xlsx_bytes_prose = record_to_xlsx_bytes(SAMPLE_RECORD_WITH_HEADING_AND_PROSE)
    wb_prose = load_workbook(io.BytesIO(xlsx_bytes_prose))
    ws_prose = wb_prose.active
    all_values_prose = [
        ws_prose.cell(row=r, column=2).value
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
    # kv표(항목/내용)도 C:D로 병합돼 폭이 맞아야 한다(B열 시작 기준).
    prose_merge_ranges = [str(r) for r in ws_prose.merged_cells.ranges]
    results.append((
        "박스 너비가 다른 표들과 안 맞던 kv표도 C:D 병합으로 폭이 맞춰짐",
        "C4:D4" in prose_merge_ranges,
    ))

    xlsx_bytes_score = record_to_xlsx_bytes(SAMPLE_RECORD_WITH_SCORE)
    wb3 = load_workbook(io.BytesIO(xlsx_bytes_score))
    ws3 = wb3.active

    # 이 표는 헤딩 없이 표 하나뿐 — 1행 제목, 2행 표헤더, 3행부터 데이터 (B열부터)
    results.append((
        "빈도·강도 AI 제안값이 순수 숫자로 저장됨(3행, C/D열)",
        ws3.cell(row=3, column=3).value == 3
        and ws3.cell(row=3, column=4).value == 2
        and isinstance(ws3.cell(row=3, column=3).value, int),
    ))
    results.append((
        "위험등급·개선후 위험등급 AI 제안값이 순수 등급 문자로 저장됨(E/F열)",
        ws3.cell(row=3, column=5).value == "A"
        and ws3.cell(row=3, column=6).value == "B",
    ))
    results.append((
        "AI 제안값 안내 문구는 셀 메모(comment)로 보존됨",
        ws3.cell(row=3, column=5).comment is not None
        and "AI 제안값" in ws3.cell(row=3, column=5).comment.text,
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
        "점수가 아닌 일반 텍스트 셀은 그대로 문자열 유지(B열)",
        ws3.cell(row=3, column=2).value == "지게차 충돌"
        and ws3.cell(row=3, column=2).comment is None,
    ))

    # --- 위험성평가표 전용: 열 폭을 셀 내용 글자수 기반으로 자동조절 ---
    xlsx_bytes_width = record_to_xlsx_bytes(SAMPLE_RECORD_RISK_WIDE_NARROW)
    wb4 = load_workbook(io.BytesIO(xlsx_bytes_width))
    ws4 = wb4.active
    # 표만 있고 헤딩 없음 → 1행 제목, 2행 표헤더 → 열: B=단위작업, C=빈도, D=위험성 감소대책
    narrow_width = ws4.column_dimensions["C"].width  # 빈도 (짧은 숫자)
    wide_width = ws4.column_dimensions["D"].width  # 위험성 감소대책 (긴 문장)
    results.append(("위험성평가표: 내용이 짧은 '빈도' 열보다 긴 '위험성 감소대책' 열이 훨씬 넓음", wide_width > narrow_width * 3))
    static_spec_widths = STYLE_SPECS["위험성평가표"].column_widths
    results.append((
        "위험성평가표 열폭은 정적 스펙 그대로가 아니라 실제 조정됨",
        [ws4.column_dimensions[c].width for c in ("B", "C", "D")] != static_spec_widths[:3],
    ))

    # --- 다른 문서유형(TBM 일지 등)은 여전히 정적 스펙을 그대로 씀(스코프 밖) ---
    xlsx_bytes_other = record_to_xlsx_bytes(SAMPLE_RECORD_OTHER_DOC_TYPE)
    wb5 = load_workbook(io.BytesIO(xlsx_bytes_other))
    ws5 = wb5.active
    tbm_spec_widths = STYLE_SPECS["TBM 일지"].column_widths
    results.append((
        "TBM 일지 등은 여전히 document_styles의 정적 열폭 스펙을 그대로 씀",
        ws5.column_dimensions["B"].width == tbm_spec_widths[0]
        and ws5.column_dimensions["C"].width == tbm_spec_widths[1],
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
