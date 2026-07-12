# -*- coding: utf-8 -*-
"""
_finalize_draft()의 3중 경고(조문 인용/위험성 구간표/이격거리)가 모두
정상적으로 draft에 붙는지 API 호출 없이 로컬로 검증한다.

사용 예:
  python test_finalize_draft_local.py
"""
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from generate_draft import _finalize_draft

# 참고자료(컨텍스트)에는 존재하지 않는 조문 번호, 물결표 빠진 구간표,
# 근거 없는 이격거리 수치를 모두 담은 합성 초안.
FAKE_DRAFT = (
    "위험성 점수 구간: 14 낮음 / 59 중간 / 10~25 높음\n"
    "위험요인: 국사 내 지게차 운행 <br>"
    "안전대책: 제999조에 따라 통로 폭과의 여유 공간(좌우 각 최소 30cm 이상)을 확보한다."
)
FAKE_CONTEXT = "이 현장은 정보통신공사 국사 장비 반입 작업이다."  # 위 세 값 전부 미포함


def run():
    draft, saved_record, warning = _finalize_draft(
        FAKE_DRAFT, FAKE_CONTEXT, linked_risk_context="",
        document_type="위험성평가표", project_info="테스트용 project_info",
        project_name=None, user_id=None,
    )

    checks = [
        ("saved_record는 project_name이 없으면 None", saved_record is None),
        ("조문 인용 경고 포함", "제999조" in (warning or "")),
        ("구간표 경고 포함", "1~4" in (warning or "") and "5~9" in (warning or "")),
        ("이격거리 경고 포함", "30cm" in (warning or "")),
        ("draft 끝에 경고 3종이 순서대로 append됨", warning is not None and draft.endswith(warning)),
    ]

    ok = True
    for name, passed in checks:
        print(f"[{'PASS' if passed else 'FAIL'}] {name}")
        ok = ok and passed

    print()
    print("=" * 50)
    print("전체 결과:", "PASS" if ok else "FAIL (위 로그 확인)")


if __name__ == "__main__":
    run()
