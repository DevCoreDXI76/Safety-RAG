import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from document_styles import (
    DEFAULT_COLUMN_WIDTH, STYLE_SPECS, CENTER_ALIGN_HEADERS,
    AI_SCORE_NOTE, base_header, get_style, parse_ai_score_cell,
    resolve_column_weights, risk_grade_column_indices, cell_style_decision,
)


def run():
    results = []

    # --- parse_ai_score_cell ---
    results.append((
        "숫자 AI 제안값 파싱",
        parse_ai_score_cell("3(AI 제안값, 현장 확인 필수)") == (3, AI_SCORE_NOTE),
    ))
    results.append((
        "등급(A/B/C) AI 제안값 파싱",
        parse_ai_score_cell("A(AI 제안값, 현장 확인 필수)") == ("A", AI_SCORE_NOTE),
    ))
    results.append((
        "일반 텍스트는 매치되지 않음",
        parse_ai_score_cell("굴착사면 붕괴") == (None, None),
    ))

    # --- base_header ---
    results.append((
        "괄호 부연설명 제거",
        base_header("위험성(AI 제안값, 현장 확인 필수)") == "위험성",
    ))
    results.append(("괄호 없는 헤더는 그대로", base_header("공종") == "공종"))

    # --- get_style ---
    results.append((
        "등록된 문서유형은 스펙 반환",
        get_style("위험성평가표").column_widths == STYLE_SPECS["위험성평가표"].column_widths,
    ))
    results.append((
        "미등록 문서유형은 빈 열너비 기본 스펙 반환",
        get_style("기타 (직접 입력)").column_widths == [],
    ))

    # --- resolve_column_weights ---
    default_style = get_style("기타 (직접 입력)")
    results.append((
        "미등록 문서유형은 모든 열이 기본폭으로 균등",
        resolve_column_weights(default_style, 4) == [DEFAULT_COLUMN_WIDTH] * 4,
    ))
    risk_style = STYLE_SPECS["위험성평가표"]
    results.append((
        "등록된 문서유형은 스펙 값 그대로, 열이 모자라면 기본폭으로 패딩",
        resolve_column_weights(risk_style, 14)
        == list(risk_style.column_widths) + [DEFAULT_COLUMN_WIDTH],
    ))
    results.append((
        "표 열이 스펙보다 적으면 앞에서부터 자름",
        resolve_column_weights(risk_style, 3) == list(risk_style.column_widths[:3]),
    ))

    # --- risk_grade_column_indices ---
    headers = ["공종", "위험등급", "감소대책", "개선후 위험등급"]
    results.append((
        "위험등급 헤더 열 인덱스(0-indexed) 탐지",
        risk_grade_column_indices(risk_style, headers) == [1, 3],
    ))
    results.append((
        "위험등급 헤더가 없으면 빈 리스트",
        risk_grade_column_indices(risk_style, ["공종", "위험성"]) == [],
    ))

    # --- cell_style_decision ---
    kv_headers = ["항목", "내용"]
    results.append((
        "키-값 표: 키 열(0)은 모든 행에서 가운데정렬+kv헤더색",
        cell_style_decision(risk_style, kv_headers, [], True, False, 0, "현장명")
        == (True, risk_style.kv_header_fill),
    ))
    results.append((
        "키-값 표: 값 열(1)은 헤더행에서만 kv헤더색, 왼쪽정렬",
        cell_style_decision(risk_style, kv_headers, [], True, True, 1, "내용")
        == (False, risk_style.kv_header_fill),
    ))
    results.append((
        "키-값 표: 값 열(1)은 데이터행에서 배경색 없음",
        cell_style_decision(risk_style, kv_headers, [], True, False, 1, "강남지사")
        == (False, None),
    ))
    results.append((
        "데이터 표: 헤더행은 항상 가운데정렬+헤더색",
        cell_style_decision(risk_style, headers, [1, 3], False, True, 0, "공종")
        == (True, risk_style.header_fill),
    ))
    results.append((
        "데이터 표: 본문 행 중 CENTER_ALIGN_HEADERS에 속한 열은 가운데정렬",
        cell_style_decision(risk_style, ["빈도", "유해요인"], [], False, False, 0, "2")[0] is True,
    ))
    results.append((
        "데이터 표: 본문 행 중 CENTER_ALIGN_HEADERS에 없는 열은 왼쪽정렬",
        cell_style_decision(risk_style, ["유해요인", "빈도"], [], False, False, 0, "굴착사면 붕괴")[0] is False,
    ))
    results.append((
        "위험등급 열의 A/B/C 값은 등급별 배경색 매칭",
        cell_style_decision(risk_style, headers, [1, 3], False, False, 1, "A")
        == (True, risk_style.risk_grade_colors["A"]),
    ))
    results.append((
        "위험등급 열이라도 A/B/C가 아니면 배경색 없음",
        cell_style_decision(risk_style, headers, [1, 3], False, False, 1, "미정")[1] is None,
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
