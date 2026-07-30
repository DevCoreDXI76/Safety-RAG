# -*- coding: utf-8 -*-
"""
구식 위험성 점수 구간표(곱셈법 시절 "1~4"/"5~9"/"10~25") 잔존 감지 체커의
회귀 테스트 — API 호출 없이 로컬에서 완결되는 순수 함수 테스트.

배경: 2026-07, 위험성평가표의 위험성 추정 방식을 곱셈법(가능성×중대성=1~25
숫자)에서 행렬법(빈도×강도 → A/B/C 등급, 위험성평가_실시규정.txt 3절 참고)
으로 전환했다. 전환 직후 가장 현실적인 회귀는 모델이 예전 학습 패턴대로
구식 숫자 구간표를 다시 출력하는 것이다. 이 체커는 그 잔존 여부만 본다
(찾으면 경고 — 예전 체커와 반대 방향: 예전엔 "정확한 라벨이 없으면" 경고).

이 테스트는 _finalize_draft() 자체를 호출해서 게이팅·체커 양쪽이 실제로
동작하는지 확인한다(체커 함수 단독 테스트로는 게이팅 회귀를 못 잡음).

사용 예:
  python test_risk_score_range_checker.py
"""
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from generate_draft import _finalize_draft

WARNING_MARKER = "구식 위험성 점수 구간표"

# 실제 리포트된 표준 작업계획서 사례를 축약 재현: 위험성평가표가 아닌
# 문서는 참조 문장만 있어도(구식 라벨이 우연히 등장해도) 검사 대상이 아니다.
DRAFT_WORK_PLAN_REFERENCE_ONLY = (
    "4. 위험요인 및 안전대책\n"
    "본 작업계획서는 별도로 작성된 위험성평가표의 위험등급 판정 결과를 "
    "참고하여 작성되었으며, 각 위험요인의 판정 결과는 아래와 같다.\n"
    "| 위험요인 | 판정 |\n"
    "|---|---|\n"
    "| 지게차 협착 위험 | B(위험) |\n"
    "| 통로 폭 부족 | C(주의관리요) |"
)

# 위험성평가표인데 모델이 예전 곱셈법 구간표를 그대로 재출력한 경우(회귀) —
# 이 체크는 반드시 잡아야 한다.
DRAFT_RISK_ASSESSMENT_REGRESSED = (
    "5. 위험성 추정 및 결정\n"
    "위험요인 3: 위험성 점수 12 (가능성 3 x 중대성 4) (AI 제안값, 현장 확인 필수)\n"
    "위험성 점수 구간: 1~4 낮음 / 5~9 중간 / 10~25 높음"
)

# 위험성평가표에서 행렬법(A/B/C)으로 정상 작성된 경우 — 오탐이 없어야 한다.
DRAFT_RISK_ASSESSMENT_OK = (
    "3. 위험성 추정 기준\n"
    "빈도(가능성) 척도: 1(낮음) / 2(보통) / 3(높음)\n"
    "강도(중대성) 척도: 1(낮음) / 2(보통) / 3(높음)\n"
    "5. 위험성 추정 및 결정\n"
    "| 유해·위험요인 | 빈도 | 강도 | 위험등급 |\n"
    "|---|---|---|---|\n"
    "| 지게차 협착 | 3(AI 제안값, 현장 확인 필수) | 2(AI 제안값, 현장 확인 필수) | "
    "A(AI 제안값, 현장 확인 필수) |"
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

    results.append(check(
        "표준 작업계획서 — A/B/C 등급 참조 문장만 있음 (검사 대상 아님)",
        DRAFT_WORK_PLAN_REFERENCE_ONLY,
        document_type="표준 작업계획서",
        expect_warning=False,
    ))

    results.append(check(
        "위험성평가표 — 구식 곱셈법 구간표 잔존(회귀) 탐지",
        DRAFT_RISK_ASSESSMENT_REGRESSED,
        document_type="위험성평가표",
        expect_warning=True,
    ))

    results.append(check(
        "위험성평가표 — 행렬법(A/B/C) 정상 작성은 통과",
        DRAFT_RISK_ASSESSMENT_OK,
        document_type="위험성평가표",
        expect_warning=False,
    ))

    print()
    print("=" * 50)
    print("전체 결과:", "PASS" if all(results) else "FAIL (위 로그 확인)")


if __name__ == "__main__":
    run()
