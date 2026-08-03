# -*- coding: utf-8 -*-
"""자유의견 대기 중인 체크포인트에 일반 텍스트 메시지가 오면 가로채 완료
처리하는지, 대기 중이 아니면 False를 반환해 다른 핸들링에 넘기는지 검증한다.

사용 예:
  python test_feedback_survey_free_text.py
"""
import json
import os
import sys
import tempfile

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import api.feedback_survey as feedback_survey


def run():
    checks = []
    original_state_file = feedback_survey.FEEDBACK_STATE_FILE
    original_log_file = feedback_survey.FEEDBACK_LOG_FILE
    original_send_message = feedback_survey.send_message
    original_edit_message_text = feedback_survey.edit_message_text
    original_admin_id = feedback_survey.ADMIN_TELEGRAM_USER_ID

    with tempfile.TemporaryDirectory() as tmp_dir:
        feedback_survey.FEEDBACK_STATE_FILE = os.path.join(tmp_dir, "feedback_state.json")
        feedback_survey.FEEDBACK_LOG_FILE = os.path.join(tmp_dir, "beta1_feedback.jsonl")
        feedback_survey.ADMIN_TELEGRAM_USER_ID = 999999

        sent = []
        feedback_survey.send_message = lambda chat_id, text, reply_markup=None: sent.append((chat_id, text))
        feedback_survey.edit_message_text = lambda chat_id, message_id, text, reply_markup=None: None

        try:
            # TBM 두 질문을 모두 답해 자유의견 대기 상태로 만든다
            feedback_survey.maybe_trigger_checkpoint(444, "TBM 일지")
            feedback_survey.handle_callback_answer(444, 444, 1, "fb:T:0:0")
            feedback_survey.handle_callback_answer(444, 444, 2, "fb:T:1:0")
            state = feedback_survey._load_state()
            checks.append(("사전조건: 자유의견 대기 상태", state["444"]["TBM 일지"].get("awaiting_free_text") is True))

            sent.clear()
            handled = feedback_survey.handle_free_text(444, 444, "전체적으로 만족스러웠습니다.")
            checks.append(("대기 중이면 True 반환", handled is True))
            state = feedback_survey._load_state()
            cp = state["444"]["TBM 일지"]
            checks.append(("free_text가 기록됨", cp["free_text"] == "전체적으로 만족스러웠습니다."))
            checks.append(("처리 후 completed True", cp["completed"] is True))
            checks.append(("처리 후 awaiting_free_text 제거됨", "awaiting_free_text" not in cp))
            checks.append(("사용자에게 완료 메시지 발송", any(c[0] == 444 for c in sent)))

            with open(feedback_survey.FEEDBACK_LOG_FILE, "r", encoding="utf-8") as f:
                log_lines = [json.loads(line) for line in f if line.strip()]
            checks.append(("로그에 free_text 포함", log_lines[-1]["free_text"] == "전체적으로 만족스러웠습니다."))

            # 자유의견 대기 중이 아닌 user_id는 False
            checks.append(("대기 중 아니면 False 반환", feedback_survey.handle_free_text(555, 555, "아무 말이나") is False))

            # 멱등성 테스트: 같은 사용자가 자유의견을 두 번 보내면 두 번째는 무시되는지 확인
            print("\n--- 멱등성 테스트 ---")
            feedback_survey.maybe_trigger_checkpoint(666, "TBM 일지")
            feedback_survey.handle_callback_answer(666, 666, 1, "fb:T:0:0")
            feedback_survey.handle_callback_answer(666, 666, 2, "fb:T:1:0")

            sent.clear()
            # 첫 번째 자유의견 발송
            result1 = feedback_survey.handle_free_text(666, 666, "첫 번째 의견")
            checks.append(("첫 번째 자유의견 처리: True 반환", result1 is True))
            first_sent_count = len(sent)

            # 두 번째 자유의견 발송 (멱등성 - 처리되면 안 됨)
            result2 = feedback_survey.handle_free_text(666, 666, "두 번째 의견 - 무시되어야 함")
            checks.append(("두 번째 자유의견 처리: False 반환", result2 is False))
            checks.append(("두 번째 발송 시 메시지 추가 안 됨", len(sent) == first_sent_count))

            # 로그 파일 확인: 중복 로그 없음
            with open(feedback_survey.FEEDBACK_LOG_FILE, "r", encoding="utf-8") as f:
                all_log_lines = [json.loads(line) for line in f if line.strip()]
            user_666_logs = [log for log in all_log_lines if log["user_id"] == 666]
            checks.append(("user_id 666의 로그 1개만 존재 (중복 없음)", len(user_666_logs) == 1))
            checks.append(("로그의 free_text는 첫 번째 내용", user_666_logs[0]["free_text"] == "첫 번째 의견"))
        finally:
            feedback_survey.FEEDBACK_STATE_FILE = original_state_file
            feedback_survey.FEEDBACK_LOG_FILE = original_log_file
            feedback_survey.send_message = original_send_message
            feedback_survey.edit_message_text = original_edit_message_text
            feedback_survey.ADMIN_TELEGRAM_USER_ID = original_admin_id

    print()
    for name, ok in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    print("=" * 50)
    print("전체 결과:", "PASS" if all(ok for _, ok in checks) else "FAIL (위 로그 확인)")


if __name__ == "__main__":
    run()
