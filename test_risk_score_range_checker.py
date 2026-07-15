# -*- coding: utf-8 -*-
"""
위험성 추정 기준(척도 1~5, 구간 1~4/5~9/10~25) 체커의 회귀 테스트 —
API 호출 없이 로컬에서 완결되는 순수 함수 테스트.

배경 (오탐, 2026-07 베타 0 사전 테스트):
find_broken_risk_score_ranges()가 draft에 "위험성 점수"와 "구간" 단어가
함께 등장하면 정확한 라벨이 없다고 "누락"으로 판정했다. 표준 작업계획서
등 위험성평가표가 아닌 문서는 system_prompt 지시상 "위험성평가표 참조"
처럼 단어만 언급하고 구체 수치는 적지 않는 게 정상 동작이라, 이 경우까지
오탐이 발생했다. 1차 수정: _finalize_draft()에서
document_type == "위험성평가표"일 때만 이 체크를 실행하도록 게이팅.

배경 (놓침, 같은 세션 재테스트):
1차 수정 후에도 실사용 재현에서, 위험성평가표인데 모델이 "판정구간" 대신
"위험성 수준"이라는 표현을 써서 draft에 "구간"이라는 글자 자체가 없는
경우가 나왔다 — 이때 체커 내부의 "위험성 점수"+"구간" 트리거 조건이
안 걸려서 실제로 깨진 표기("가능성 15" ← "1~5" 물결표 누락)를 놓쳤다.
2차 수정: document_type 게이팅이 이미 호출부에 있으므로 함수 내부의
트리거 단어 조건을 제거하고, 감시 라벨에 척도("1~5")도 추가.

이 테스트는 _finalize_draft() 자체를 호출해서 게이팅·체커 양쪽이 실제로
동작하는지 확인한다(체커 함수 단독 테스트로는 게이팅 회귀를 못 잡음).

사용 예:
  python test_risk_score_range_checker.py
"""
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from generate_draft import _finalize_draft

WARNING_MARKER = "구간 표기"

# 실제 리포트된 표준 작업계획서 사례를 축약 재현: "위험성 점수"·"구간"
# 단어는 참조 문장에 등장하지만, 정확한 라벨(1~4/5~9/10~25)은 애초에
# 나올 필요가 없는 문서.
DRAFT_WORK_PLAN_REFERENCE_ONLY = (
    "4. 위험요인 및 안전대책\n"
    "본 작업계획서는 별도로 작성된 위험성평가표의 위험성 점수 및 판정 "
    "구간을 참고하여 작성되었으며, 각 위험요인의 판정 결과는 아래와 같다.\n"
    "| 위험요인 | 판정 |\n"
    "|---|---|\n"
    "| 지게차 협착 위험 | 높음(High) |\n"
    "| 통로 폭 부족 | 중간(Medium) |"
)

# 위험성평가표 자체에서 라벨이 실제로 깨진 경우(물결표 누락) — 이 체크는
# 계속 잡아야 한다.
DRAFT_RISK_ASSESSMENT_BROKEN = (
    "5. 위험성 추정 및 결정\n"
    "위험요인 3: 위험성 점수 14 (가능성 2 x 중대성 7) (AI 제안값, 현장 확인 필수)\n"
    "위험성 점수 구간: 14 낮음 / 59 중간 / 1025 높음"
)

# 위험성평가표에서 라벨이 정상 표기된 경우(척도·구간 전부) — 오탐이 없어야 한다.
DRAFT_RISK_ASSESSMENT_OK = (
    "3. 위험성 추정 기준\n"
    "가능성(빈도) 척도: 1~5, 중대성(강도) 척도: 1~5\n"
    "5. 위험성 추정 및 결정\n"
    "위험요인 3: 위험성 점수 14 (가능성 2 x 중대성 7) (AI 제안값, 현장 확인 필수)\n"
    "위험성 점수 구간: 1~4 낮음 / 5~9 중간 / 10~25 높음"
)

# 실제 리포트된 놓침 사례를 축약 재현: "구간" 대신 "위험성 수준"이라는
# 표현을 써서 "구간" 글자 자체가 draft에 없고, 척도(1~5)의 물결표도
# 깨져 있음("가능성 15"). 트리거 단어 방식이었다면 놓쳤을 케이스.
DRAFT_RISK_ASSESSMENT_NO_TRIGGER_WORD = (
    "1. 평가 개요\n"
    "위험성 점수(가능성·중대성·위험성)는 위험성평가_실시규정.txt의 추정 "
    "기준(가능성 15 × 중대성 15, 14 낮음/59 중간/10~25 높음)에 따라 산정된 "
    "AI 제안값이며, 모든 항목에 대해 반드시 현장 확인 및 담당자 검토가 "
    "필요합니다.\n"
    "2. 유해·위험요인 파악 및 위험성 추정·결정\n"
    "| No | 유해·위험요인 | 가능성 | 중대성 | 위험성 | 위험성 수준 |\n"
    "|---|---|---|---|---|---|\n"
    "| 1 | 협착 위험 | 3 | 4 | 12 | 높음 |"
)


def check(name, draft, document_type, expect_warning):
    _, _, warning = _finalize_draft(
        draft=draft,
        context="",
        linked_risk_context="",
        document_type=document_type,
        project_info="테스트",
        project_name=None,
        user_id=None,
    )
    got_warning = bool(warning) and WARNING_MARKER in warning
    status = "PASS" if got_warning == expect_warning else "FAIL"
    print(f"[{status}] {name}: warning_present={got_warning} expected={expect_warning}")
    return status == "PASS"


def run():
    results = []

    # 1. 회귀 케이스: 표준 작업계획서는 참조 문장에 단어만 있어도 경고 없어야 함
    results.append(check(
        "표준 작업계획서 — 참조 문장만 있고 표는 없음 (오탐 회귀 확인)",
        DRAFT_WORK_PLAN_REFERENCE_ONLY,
        document_type="표준 작업계획서",
        expect_warning=False,
    ))

    # 2. 위험성평가표에서 실제로 깨진 표기는 여전히 잡혀야 함
    results.append(check(
        "위험성평가표 — 물결표 깨진 구간표는 탐지",
        DRAFT_RISK_ASSESSMENT_BROKEN,
        document_type="위험성평가표",
        expect_warning=True,
    ))

    # 3. 위험성평가표에서 정상 표기는 경고 없어야 함
    results.append(check(
        "위험성평가표 — 정상 구간표는 통과",
        DRAFT_RISK_ASSESSMENT_OK,
        document_type="위험성평가표",
        expect_warning=False,
    ))

    # 4. 회귀 케이스: "구간" 단어가 없어도(표현이 달라도) 깨진 척도(1~5)를 잡아야 함
    results.append(check(
        "위험성평가표 — '구간' 단어 없이도 깨진 척도(1~5) 탐지 (놓침 회귀 확인)",
        DRAFT_RISK_ASSESSMENT_NO_TRIGGER_WORD,
        document_type="위험성평가표",
        expect_warning=True,
    ))

    print()
    print("=" * 50)
    print("전체 결과:", "PASS" if all(results) else "FAIL (위 로그 확인)")


if __name__ == "__main__":
    run()
