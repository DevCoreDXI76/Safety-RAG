# -*- coding: utf-8 -*-
"""문서 타입별 피드백 체크포인트가 최초 1회만 트리거되는지, 발송 실패 시
상태가 기록되지 않아 다음 생성 때 재시도 여지가 남는지 검증한다.
실제 텔레그램 발송은 하지 않는다 — send_message를 가짜 함수로 바꿔치기한다.

사용 예:
  python test_feedback_survey_trigger.py
"""
import os
import sys
import tempfile

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import api.feedback_survey as feedback_survey


def run():
    checks = []
    original_state_file = feedback_survey.FEEDBACK_STATE_FILE
    original_send_message = feedback_survey.send_message
    with tempfile.TemporaryDirectory() as tmp_dir:
        feedback_survey.FEEDBACK_STATE_FILE = os.path.join(tmp_dir, "feedback_state.json")
        try:
            calls = []
            feedback_survey.send_message = lambda *a, **k: calls.append((a, k))

            feedback_survey.maybe_trigger_checkpoint(111, "위험성평가표")
            state = feedback_survey._load_state()
            checks.append(("정상 발송 시 send_message 1회 호출", len(calls) == 1))
            checks.append(("상태 파일에 document_type 키 생성", "위험성평가표" in state.get("111", {})))
            checks.append(("초기 completed는 False", state["111"]["위험성평가표"]["completed"] is False))
            checks.append(("초기 answers는 빈 dict", state["111"]["위험성평가표"]["answers"] == {}))

            feedback_survey.maybe_trigger_checkpoint(111, "위험성평가표")
            checks.append(("이미 트리거된 조합은 재발송 안 함", len(calls) == 1))

            def failing_send(*a, **k):
                raise RuntimeError("텔레그램 전송 실패 시뮬레이션")
            feedback_survey.send_message = failing_send
            feedback_survey.maybe_trigger_checkpoint(222, "표준 작업계획서")
            state = feedback_survey._load_state()
            checks.append(("발송 실패해도 예외가 밖으로 전파되지 않음(여기 도달)", True))
            checks.append(("발송 실패 시 상태에 기록되지 않음(재시도 여지)", "표준 작업계획서" not in state.get("222", {})))

            calls.clear()
            feedback_survey.send_message = lambda *a, **k: calls.append((a, k))
            feedback_survey.maybe_trigger_checkpoint(333, "안전보건교육일지")
            checks.append(("체크포인트 대상 아닌 문서 타입은 무시됨", len(calls) == 0))
        finally:
            feedback_survey.FEEDBACK_STATE_FILE = original_state_file
            feedback_survey.send_message = original_send_message

    print()
    for name, ok in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    print("=" * 50)
    print("전체 결과:", "PASS" if all(ok for _, ok in checks) else "FAIL (위 로그 확인)")


if __name__ == "__main__":
    run()
