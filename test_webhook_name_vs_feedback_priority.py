# -*- coding: utf-8 -*-
"""webhook.py의 텍스트 우선순위 재검토(최종 통합 리뷰 Finding #1) 검증.

이름 답장 대기 상태(is_awaiting_name)와 피드백 자유의견 대기 상태
(feedback_survey.is_awaiting_free_text)가 동시에 걸려 있을 때, 피드백
자유의견이 우선해서 소비되어야 한다 — 그렇지 않으면 자유의견 문장이
이름으로 오저장되고 피드백도 유실된다.

또한 이름만 대기 중(자유의견 대기 아님)인 경우는 기존처럼 이름으로
캡처되어야 한다(회귀 확인).

사용 예:
  python test_webhook_name_vs_feedback_priority.py
"""
import os
import sys
import tempfile

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import api.webhook as webhook
import api.access_control as access_control
import api.feedback_survey as feedback_survey


def _message(text, user_id=12345):
    return {
        "text": text,
        "chat": {"id": user_id},
        "from": {"id": user_id, "username": None, "first_name": "테스터"},
    }


def run():
    checks = []
    original_allowed = access_control.ALLOWED_USERS_FILE
    original_pending = access_control.PENDING_REQUESTS_FILE
    original_admin_id = webhook.ADMIN_TELEGRAM_USER_ID
    original_send_message = webhook.send_message
    original_state_file = feedback_survey.FEEDBACK_STATE_FILE
    original_log_file = feedback_survey.FEEDBACK_LOG_FILE
    original_fb_send_message = feedback_survey.send_message
    original_fb_admin_id = feedback_survey.ADMIN_TELEGRAM_USER_ID

    webhook.ADMIN_TELEGRAM_USER_ID = 999999
    feedback_survey.ADMIN_TELEGRAM_USER_ID = 999999
    sent = []
    webhook.send_message = lambda *a, **k: sent.append((a, k)) or {}
    feedback_survey.send_message = lambda *a, **k: sent.append((a, k)) or {}

    with tempfile.TemporaryDirectory() as tmp_dir:
        access_control.ALLOWED_USERS_FILE = os.path.join(tmp_dir, "allowed_users.json")
        access_control.PENDING_REQUESTS_FILE = os.path.join(tmp_dir, "pending_requests.json")
        feedback_survey.FEEDBACK_STATE_FILE = os.path.join(tmp_dir, "feedback_state.json")
        feedback_survey.FEEDBACK_LOG_FILE = os.path.join(tmp_dir, "beta1_feedback.jsonl")
        try:
            # --- 1) 이름 대기 + 자유의견 대기가 동시에 걸린 경우: 자유의견이 우선 ---
            user_id = 70001
            # 기존 승인자 + 이름 소급 요청 중(allowed에 있고 display_name 없음, name_asked_at 있음)
            access_control.add_allowed_user(user_id, username=None, first_name="철수")
            allowed_data = access_control._load(access_control.ALLOWED_USERS_FILE)
            from datetime import datetime
            from common import KST
            allowed_data[str(user_id)]["name_asked_at"] = datetime.now(KST).isoformat()
            access_control._save(access_control.ALLOWED_USERS_FILE, allowed_data)

            # TBM 두 질문 모두 답해 자유의견 대기 상태로 만든다
            feedback_survey.maybe_trigger_checkpoint(user_id, "TBM 일지")
            feedback_survey.handle_callback_answer(user_id, user_id, 1, "fb:T:0:0")
            feedback_survey.handle_callback_answer(user_id, user_id, 2, "fb:T:1:0")

            checks.append(("사전조건: 이름 대기 상태", access_control.is_awaiting_name(user_id)))
            checks.append(("사전조건: 자유의견 대기 상태", feedback_survey.is_awaiting_free_text(user_id)))

            sent.clear()
            webhook._handle_message(_message("표가 좀 좁아요", user_id=user_id))

            fb_state = feedback_survey._load_state()
            cp = fb_state[str(user_id)]["TBM 일지"]
            checks.append(("동시 대기 시 자유의견으로 캡처됨", cp.get("free_text") == "표가 좀 좁아요"))
            checks.append(("동시 대기 시 자유의견 처리 후 completed", cp.get("completed") is True))

            allowed_after = access_control._load(access_control.ALLOWED_USERS_FILE)
            checks.append(
                ("동시 대기 시 display_name은 오저장되지 않음(비어있음 유지)",
                 not allowed_after[str(user_id)].get("display_name")),
            )

            # --- 2) 역방향 회귀: 이름만 대기 중(자유의견 대기 아님)이면 여전히 이름으로 캡처 ---
            user_id2 = 70002
            access_control.add_pending_request(user_id2, username=None, first_name="영희")
            checks.append(("사전조건: user2는 이름 대기 상태", access_control.is_awaiting_name(user_id2)))
            checks.append(("사전조건: user2는 자유의견 대기 아님", not feedback_survey.is_awaiting_free_text(user_id2)))

            sent.clear()
            webhook._handle_message(_message("이영희", user_id=user_id2))
            pending_data = access_control._load(access_control.PENDING_REQUESTS_FILE)
            checks.append(
                ("자유의견 대기 없을 때는 여전히 이름으로 캡처됨(회귀)",
                 pending_data[str(user_id2)]["display_name"] == "이영희"),
            )
        finally:
            access_control.ALLOWED_USERS_FILE = original_allowed
            access_control.PENDING_REQUESTS_FILE = original_pending
            webhook.ADMIN_TELEGRAM_USER_ID = original_admin_id
            webhook.send_message = original_send_message
            feedback_survey.FEEDBACK_STATE_FILE = original_state_file
            feedback_survey.FEEDBACK_LOG_FILE = original_log_file
            feedback_survey.send_message = original_fb_send_message
            feedback_survey.ADMIN_TELEGRAM_USER_ID = original_fb_admin_id

    print()
    for name, ok in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    print("=" * 50)
    print("전체 결과:", "PASS" if all(ok for _, ok in checks) else "FAIL (위 로그 확인)")


if __name__ == "__main__":
    run()
