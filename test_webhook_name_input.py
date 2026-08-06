# -*- coding: utf-8 -*-
"""webhook.py의 텍스트 우선순위(이름 대기 상태가 관리자 명령·/start·피드백
자유의견보다 먼저 소비되는지), 승인 콜백이 display_name을 함께 넘기는지,
웹훅 진입 시 sweep_stale_name_requests가 호출되는지 검증한다. 실제
텔레그램 API 호출은 하지 않는다.

사용 예:
  python test_webhook_name_input.py
"""
import asyncio
import os
import sys
import tempfile

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import api.webhook as webhook
import api.access_control as access_control


class _FakeRequest:
    def __init__(self, payload):
        self._payload = payload

    async def json(self):
        return self._payload


def _message(text, user_id=12345):
    return {
        "text": text,
        "chat": {"id": user_id},
        "from": {"id": user_id, "username": None, "first_name": "테스터"},
    }


def _callback_query(data, clicker_id=999999):
    return {
        "from": {"id": clicker_id},
        "id": "cbq1",
        "data": data,
        "message": {"chat": {"id": clicker_id}, "message_id": 1},
    }


def run():
    checks = []
    original_allowed = access_control.ALLOWED_USERS_FILE
    original_pending = access_control.PENDING_REQUESTS_FILE
    original_admin_id = webhook.ADMIN_TELEGRAM_USER_ID
    original_send_message = webhook.send_message
    original_edit_message_text = webhook.edit_message_text
    original_answer_cb = webhook.answer_callback_query
    original_secret = webhook.TELEGRAM_WEBHOOK_SECRET
    original_sweep = webhook.sweep_stale_name_requests

    webhook.ADMIN_TELEGRAM_USER_ID = 999999
    sent = []
    webhook.send_message = lambda *a, **k: sent.append((a, k)) or {}
    webhook.edit_message_text = lambda *a, **k: {}
    webhook.answer_callback_query = lambda *a, **k: {}

    with tempfile.TemporaryDirectory() as tmp_dir:
        access_control.ALLOWED_USERS_FILE = os.path.join(tmp_dir, "allowed_users.json")
        access_control.PENDING_REQUESTS_FILE = os.path.join(tmp_dir, "pending_requests.json")
        try:
            # --- 1) 이름 대기 상태면 최우선으로 소비 (유효한 이름) ---
            access_control.add_pending_request(11111, username=None, first_name="철수")
            sent.clear()
            webhook._handle_message(_message("이철수", user_id=11111))
            pending_data = access_control._load(access_control.PENDING_REQUESTS_FILE)
            checks.append(("유효한 이름 답장이 저장됨", pending_data["11111"]["display_name"] == "이철수"))
            checks.append(("등록 감사 메시지 발송", any("이철수" in a[1] for a, k in sent)))

            # --- 2) 이름 대기 상태에서 형식이 잘못된 답장은 재요청, 저장 안 함 ---
            access_control.add_pending_request(22222, username=None, first_name="영희")
            sent.clear()
            webhook._handle_message(_message("이거 어떻게 쓰는건가요?", user_id=22222))
            pending_data = access_control._load(access_control.PENDING_REQUESTS_FILE)
            checks.append(("형식이 잘못된 답장은 저장 안 됨", pending_data["22222"]["display_name"] is None))
            checks.append(("재요청 메시지 발송", any("간단히" in a[1] for a, k in sent)))

            # --- 3) 이름 대기 상태가 아니면 기존 로직으로 정상 진행(회귀) ---
            sent.clear()
            free_text_calls = []
            original_handle_free_text = webhook.feedback_survey.handle_free_text
            webhook.feedback_survey.handle_free_text = lambda *a: free_text_calls.append(a) or True
            try:
                webhook._handle_message(_message("현장에서 잘 썼습니다.", user_id=33333))
                checks.append(("대기 상태 아닌 텍스트는 기존처럼 자유의견 핸들러로", len(free_text_calls) == 1))
            finally:
                webhook.feedback_survey.handle_free_text = original_handle_free_text

            # --- 4) 승인 콜백이 pending의 display_name을 allowed로 넘김 ---
            access_control.add_pending_request(44444, username=None, first_name="민수")
            access_control.record_name_reply(44444, "김민수")
            webhook._handle_callback_query(_callback_query("approve:44444", clicker_id=webhook.ADMIN_TELEGRAM_USER_ID))
            allowed_data = access_control._load(access_control.ALLOWED_USERS_FILE)
            checks.append(("승인 시 display_name이 allowed_users로 이어짐",
                            allowed_data["44444"]["display_name"] == "김민수"))

            # --- 5) 웹훅 진입 시 sweep_stale_name_requests 호출 ---
            webhook.TELEGRAM_WEBHOOK_SECRET = "test-secret"
            sweep_calls = []
            webhook.sweep_stale_name_requests = lambda: sweep_calls.append(True)
            asyncio.run(webhook.telegram_webhook(
                _FakeRequest({"message": _message("/authlog", user_id=55555)}),
                x_telegram_bot_api_secret_token="test-secret",
            ))
            checks.append(("웹훅 요청마다 sweep_stale_name_requests 호출됨", len(sweep_calls) == 1))
        finally:
            access_control.ALLOWED_USERS_FILE = original_allowed
            access_control.PENDING_REQUESTS_FILE = original_pending
            webhook.ADMIN_TELEGRAM_USER_ID = original_admin_id
            webhook.send_message = original_send_message
            webhook.edit_message_text = original_edit_message_text
            webhook.answer_callback_query = original_answer_cb
            webhook.TELEGRAM_WEBHOOK_SECRET = original_secret
            webhook.sweep_stale_name_requests = original_sweep

    print()
    for name, ok in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    print("=" * 50)
    print("전체 결과:", "PASS" if all(ok for _, ok in checks) else "FAIL (위 로그 확인)")


if __name__ == "__main__":
    run()
