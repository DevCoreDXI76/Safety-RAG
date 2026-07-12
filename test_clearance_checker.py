# -*- coding: utf-8 -*-
"""
find_unverified_clearance_values() 회귀 테스트 — API 호출 없이 로컬에서
완결되는 순수 함수 테스트. common.py나 이 체커의 앵커 키워드/정규식을
바꿀 때마다 실행할 것.

사용 예:
  python test_clearance_checker.py
"""
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from common import find_unverified_clearance_values

# 2026-07-12 C-2 재관찰 테스트에서 실제로 나온 위험성평가표 초안의 발췌.
# 위험요인 6 — KB에 없는 "30cm"가 창작된 실제 사례.
DRAFT_FABRICATED_CLEARANCE = (
    "③ [관리적 대책] 지게차 포크 및 캐비닛 외곽 치수를 실측하고, "
    "통로 폭과의 여유 공간(좌우 각 최소 30cm 이상)을 사전 확인 "
    "<br>④ [관리적 대책] 케이블 트레이 높이와 캐비닛 최고점 높이를 "
    "비교하여 상부 간섭 여부 사전 확인"
)

# 위험요인 3 — 같은 초안에서 활선설비 이격거리는 수치 없이
# "사전 실측"으로만 서술된 개선된 케이스 (수치 자체가 없으므로 검사 대상 없음)
DRAFT_NO_NUMBER_CLEARANCE = (
    "④ [공학적 대책] 지게차 최대 하물 높이(포크 상단 포함)와 활선설비 "
    "사이의 이격거리를 사전 실측하고 안전 여유 확보 여부 확인"
)

# 위험요인 1 — 이격거리와 무관한 기계적 수치(스코프 밖, 앵커 키워드 없음)
DRAFT_UNRELATED_NUMBER = (
    "② [공학적 대책] 지게차 포크 높이를 주행 시 지면에서 15~20cm로 "
    "제한하여 하중 무게중심을 낮게 유지"
)

# 표준작업계획서_법정별표.txt(굴착작업 섹션)에 실제로 있는 문장 —
# "이격거리"와 "1m"이 함께 등장하고, 컨텍스트에도 동일하게 존재해야
# 정상적으로 통과(미검증 아님)해야 한다.
KB_GROUNDED_TEXT = (
    "매설물 인근 이격거리 기준: 중장비(굴착기 등)에서 인력굴착으로 "
    "전환해야 하는 기준은 굴착 깊이가 아니라 매설물까지의 수평 거리다. "
    "가스배관 등 주요 매설물 인근은 실무에서 통상 수평 1m 이내 구간을 "
    "인력굴착 전환 기준으로 참고하는 경우가 많다."
)


def check(name, draft, reference_context, expected):
    result = find_unverified_clearance_values(draft, reference_context)
    status = "PASS" if result == expected else "FAIL"
    print(f"[{status}] {name}: got={result} expected={expected}")
    return status == "PASS"


def run():
    results = []

    # 1. KB에 없는 "30cm"는 미검증으로 잡혀야 한다
    results.append(check(
        "창작된 이격거리(30cm) 탐지",
        DRAFT_FABRICATED_CLEARANCE,
        reference_context="",
        expected=["30cm"],
    ))

    # 2. 수치가 없으면 검사 대상 자체가 없다
    results.append(check(
        "수치 없는 이격거리 언급은 통과",
        DRAFT_NO_NUMBER_CLEARANCE,
        reference_context="",
        expected=[],
    ))

    # 3. 앵커 키워드가 없으면 스코프 밖 — KB에 없어도 안 잡혀야 한다
    results.append(check(
        "무관한 수치(앵커 키워드 없음)는 스코프 밖",
        DRAFT_UNRELATED_NUMBER,
        reference_context="",
        expected=[],
    ))

    # 4. 컨텍스트에 동일한 값이 있으면 정상 통과(오탐 아님)
    results.append(check(
        "KB에 근거 있는 이격거리(1m)는 통과",
        KB_GROUNDED_TEXT,
        reference_context=KB_GROUNDED_TEXT,
        expected=[],
    ))

    print()
    print("=" * 50)
    print("전체 결과:", "PASS" if all(results) else "FAIL (위 로그 확인)")


if __name__ == "__main__":
    run()
