# -*- coding: utf-8 -*-
"""webhook.py가 피드백 버튼("fb:", "fbskip:")·자유의견 텍스트를
feedback_survey로 위임하는지, 기존 승인/거절·관리자 전용 게이트는 그대로
유지되는지 검증한다. 실제 텔레그램 API 호출은 하지 않는다.

사용 예:
  python test_webhook_feedback_routing.py
"""
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import api.webhook as webhook


def _callback_query(data, clicker_id=12345):
    return {
        "from": {"id": clicker_id},
        "id": "cbq1",
        "data": data,
        "message": {"chat": {"id": clicker_id}, "message_id": 1},
    }


def _message(text, user_id=12345):
    return {
        "text": text,
        "chat": {"id": user_id},
        "from": {"id": user_id, "username": None, "first_name": "테스터"},
    }


def run():
    checks = []
    original_admin_id = webhook.ADMIN_TELEGRAM_USER_ID
    original_answer_cb = webhook.answer_callback_query
    original_handle_callback_answer = webhook.feedback_survey.handle_callback_answer
    original_handle_skip = webhook.feedback_survey.handle_skip_callback
    original_handle_free_text = webhook.feedback_survey.handle_free_text
    original_send_message = webhook.send_message

    webhook.ADMIN_TELEGRAM_USER_ID = 999999  # 아래 clicker_id(12345)는 비관리자

    answer_cb_calls = []
    webhook.answer_callback_query = lambda cb_id, text=None: answer_cb_calls.append((cb_id, text))

    try:
        # 1) 비관리자가 fb: 버튼을 눌러도 "관리자만" 거절 없이 feedback_survey로 위임됨
        fb_calls = []
        webhook.feedback_survey.handle_callback_answer = lambda *a: fb_calls.append(a) or True
        webhook._handle_callback_query(_callback_query("fb:R:0:0", clicker_id=12345))
        checks.append(("비관리자 fb: 콜백이 handle_callback_answer로 위임됨", len(fb_calls) == 1))
        checks.append(("비관리자 fb: 콜백에 '관리자만' 거절 없음",
                        not any(t == "관리자만 사용할 수 있습니다." for _, t in answer_cb_calls)))

        # 2) 비관리자가 fbskip: 버튼을 눌러도 위임됨
        answer_cb_calls.clear()
        skip_calls = []
        webhook.feedback_survey.handle_skip_callback = lambda *a: skip_calls.append(a) or True
        webhook._handle_callback_query(_callback_query("fbskip:T", clicker_id=12345))
        checks.append(("비관리자 fbskip: 콜백이 handle_skip_callback으로 위임됨", len(skip_calls) == 1))

        # 3) 비관리자가 approve: 버튼을 누르면 여전히 거절됨(회귀 확인)
        answer_cb_calls.clear()
        webhook._handle_callback_query(_callback_query("approve:12345", clicker_id=12345))
        checks.append(("비관리자 approve: 콜백은 여전히 거절됨",
                        any(t == "관리자만 사용할 수 있습니다." for _, t in answer_cb_calls)))

        # 4) 자유의견 대기 중인 텍스트는 feedback_survey.handle_free_text로 위임되고, 그러면
        #    이후 (예: /start 등록) 흐름으로 안 넘어감
        free_text_calls = []
        webhook.feedback_survey.handle_free_text = lambda *a: free_text_calls.append(a) or True
        webhook._handle_message(_message("현장에서 편하게 잘 썼습니다.", user_id=54321))
        checks.append(("자유의견 텍스트가 handle_free_text로 위임됨", len(free_text_calls) == 1))

        # 5) handle_free_text가 False(대기 중 아님)면 기존처럼 무시됨(예외 없이 리턴)
        webhook.feedback_survey.handle_free_text = lambda *a: False
        try:
            webhook._handle_message(_message("아무 잡담", user_id=54321))
            checks.append(("자유의견 대기 아닌 일반 텍스트는 예외 없이 무시됨", True))
        except Exception:
            checks.append(("자유의견 대기 아닌 일반 텍스트는 예외 없이 무시됨", False))
    finally:
        webhook.ADMIN_TELEGRAM_USER_ID = original_admin_id
        webhook.answer_callback_query = original_answer_cb
        webhook.feedback_survey.handle_callback_answer = original_handle_callback_answer
        webhook.feedback_survey.handle_skip_callback = original_handle_skip
        webhook.feedback_survey.handle_free_text = original_handle_free_text
        webhook.send_message = original_send_message

    print()
    for name, ok in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    print("=" * 50)
    print("전체 결과:", "PASS" if all(ok for _, ok in checks) else "FAIL (위 로그 확인)")


if __name__ == "__main__":
    run()
