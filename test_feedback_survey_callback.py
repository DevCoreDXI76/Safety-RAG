# -*- coding: utf-8 -*-
"""피드백 버튼 답변 처리 — 다음 질문으로 진행, 마지막 질문 후 자유의견
대기 전환(TBM), 자유의견 없는 체크포인트는 바로 완료, 완료 시 로그·관리자
알림이 나가는지 검증한다.

사용 예:
  python test_feedback_survey_callback.py
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

        edits = []
        admin_messages = []

        def fake_edit(chat_id, message_id, text, reply_markup=None):
            edits.append({"chat_id": chat_id, "text": text, "reply_markup": reply_markup})

        def fake_send(chat_id, text, reply_markup=None):
            if chat_id == 999999:
                admin_messages.append(text)

        feedback_survey.edit_message_text = fake_edit
        feedback_survey.send_message = fake_send

        try:
            # 1) 질문이 1개뿐인 체크포인트(위험성평가표) — 답변하면 바로 완료
            feedback_survey.maybe_trigger_checkpoint(111, "위험성평가표")
            handled = feedback_survey.handle_callback_answer(111, 111, 1, "fb:R:0:1")
            checks.append(("fb: 콜백은 True 반환", handled is True))
            state = feedback_survey._load_state()
            cp = state["111"]["위험성평가표"]
            checks.append(("답변이 answers에 기록됨", cp["answers"]["q1_quality"] == "조금만 수정하면 됨"))
            checks.append(("질문 1개뿐이면 바로 completed", cp["completed"] is True))
            checks.append(("완료 시 edit_message_text 호출됨", len(edits) == 1))
            checks.append(("완료 시 관리자에게 알림 감", len(admin_messages) == 1))

            with open(feedback_survey.FEEDBACK_LOG_FILE, "r", encoding="utf-8") as f:
                log_lines = [json.loads(line) for line in f if line.strip()]
            checks.append(("로그 파일에 1줄 기록됨", len(log_lines) == 1))
            checks.append(("로그에 document_type 기록됨", log_lines[0]["document_type"] == "위험성평가표"))

            # 2) 질문이 2개인 체크포인트(TBM) — 첫 질문 답하면 두 번째 질문으로 진행(아직 미완료)
            feedback_survey.maybe_trigger_checkpoint(222, "TBM 일지")
            edits.clear()
            feedback_survey.handle_callback_answer(222, 222, 1, "fb:T:0:0")
            state = feedback_survey._load_state()
            cp2 = state["222"]["TBM 일지"]
            checks.append(("TBM 1번째 답변 후 미완료", cp2["completed"] is False))
            checks.append(("TBM 1번째 답변 후 다음 질문 텍스트로 편집됨",
                            edits[0]["text"] == feedback_survey.CHECKPOINTS["TBM 일지"]["questions"][1]["text"]))

            # 3) TBM 두 번째(마지막) 질문 답하면 자유의견 대기로 전환(아직 미완료)
            edits.clear()
            feedback_survey.handle_callback_answer(222, 222, 2, "fb:T:1:0")
            state = feedback_survey._load_state()
            cp2 = state["222"]["TBM 일지"]
            checks.append(("TBM 2번째 답변 후에도 미완료(자유의견 대기)", cp2["completed"] is False))
            checks.append(("TBM 2번째 답변 후 awaiting_free_text True", cp2.get("awaiting_free_text") is True))
            checks.append(("자유의견 대기 메시지로 편집됨",
                            edits[0]["text"] == feedback_survey.CHECKPOINTS["TBM 일지"]["free_text_prompt"]))

            # 4) fb: 접두사가 아니면 False 반환(다른 핸들러로 넘겨야 함)
            checks.append(("fb: 접두사 아니면 False 반환", feedback_survey.handle_callback_answer(333, 333, 1, "approve:333") is False))

            # 5) 스킵 콜백 — 자유의견 없이 바로 완료
            edits.clear()
            admin_messages.clear()
            handled_skip = feedback_survey.handle_skip_callback(222, 222, 3, "fbskip:T")
            checks.append(("fbskip: 콜백은 True 반환", handled_skip is True))
            state = feedback_survey._load_state()
            cp2 = state["222"]["TBM 일지"]
            checks.append(("스킵 후 completed True", cp2["completed"] is True))
            checks.append(("스킵해도 관리자 알림 감", len(admin_messages) == 1))
            checks.append(("fbskip: 접두사 아니면 False 반환", feedback_survey.handle_skip_callback(333, 333, 1, "reject:333") is False))
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
