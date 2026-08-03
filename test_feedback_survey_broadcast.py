# -*- coding: utf-8 -*-
"""/broadcast_feedback 관리자 명령의 핵심 로직 — 트리거는 됐지만 completed가
아닌 (user_id, document_type)에만 현재 대기 중인 질문(또는 자유의견 프롬프트)을
재발송하고, 완료된 항목은 건드리지 않는지 검증한다.

사용 예:
  python test_feedback_survey_broadcast.py
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
            # 완료됨 — 재발송 대상 아님
            feedback_survey.maybe_trigger_checkpoint(111, "위험성평가표")
            feedback_survey.handle_callback_answer(111, 111, 1, "fb:R:0:0")

            # 트리거만 되고 미응답 — 질문[0] 재발송 대상
            feedback_survey.maybe_trigger_checkpoint(222, "표준 작업계획서")

            # TBM 1번째만 답하고 미완료 — 질문[1] 재발송 대상
            feedback_survey.maybe_trigger_checkpoint(333, "TBM 일지")
            feedback_survey.handle_callback_answer(333, 333, 1, "fb:T:0:0")

            # TBM 자유의견 대기 중 — 자유의견 프롬프트 재발송 대상
            feedback_survey.maybe_trigger_checkpoint(444, "TBM 일지")
            feedback_survey.handle_callback_answer(444, 444, 1, "fb:T:0:0")
            feedback_survey.handle_callback_answer(444, 444, 2, "fb:T:1:0")

            sent = []
            feedback_survey.send_message = lambda chat_id, text, reply_markup=None: sent.append((chat_id, text))

            feedback_survey.broadcast_pending_reminders()

            sent_chat_ids = {chat_id for chat_id, _ in sent}
            checks.append(("완료된 111은 재발송 대상 아님", 111 not in sent_chat_ids))
            checks.append(("미응답 222는 재발송 대상", 222 in sent_chat_ids))
            checks.append(("222에게 질문[0] 텍스트 재발송",
                            any(chat_id == 222 and text == feedback_survey.CHECKPOINTS["표준 작업계획서"]["questions"][0]["text"]
                                for chat_id, text in sent)))
            checks.append(("TBM 1번째만 답한 333은 재발송 대상", 333 in sent_chat_ids))
            checks.append(("333에게 질문[1](2번째) 텍스트 재발송",
                            any(chat_id == 333 and text == feedback_survey.CHECKPOINTS["TBM 일지"]["questions"][1]["text"]
                                for chat_id, text in sent)))
            checks.append(("자유의견 대기 중인 444는 재발송 대상", 444 in sent_chat_ids))
            checks.append(("444에게 자유의견 프롬프트 재발송",
                            any(chat_id == 444 and text == feedback_survey.CHECKPOINTS["TBM 일지"]["free_text_prompt"]
                                for chat_id, text in sent)))
            checks.append(("재발송 대상은 정확히 3명", len(sent_chat_ids) == 3))
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
