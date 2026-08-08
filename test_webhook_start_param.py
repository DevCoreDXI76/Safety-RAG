# -*- coding: utf-8 -*-
""""/start <param>" 딥링크 파라미터를 webhook.py가 파싱해 유입 출처(source)로
저장하는지, 파라미터 없는 순수 "/start"는 기존과 동일하게 동작하는지(회귀),
승인 콜백이 pending의 source를 allowed_users로 이어받는지 검증한다. 실제
텔레그램 API 호출은 하지 않는다.

사용 예:
  python test_webhook_start_param.py
"""
import os
import sys
import tempfile

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import api.webhook as webhook
import api.access_control as access_control


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

    webhook.ADMIN_TELEGRAM_USER_ID = 999999
    sent = []
    webhook.send_message = lambda *a, **k: sent.append((a, k)) or {}
    webhook.edit_message_text = lambda *a, **k: {}
    webhook.answer_callback_query = lambda *a, **k: {}

    with tempfile.TemporaryDirectory() as tmp_dir:
        access_control.ALLOWED_USERS_FILE = os.path.join(tmp_dir, "allowed_users.json")
        access_control.PENDING_REQUESTS_FILE = os.path.join(tmp_dir, "pending_requests.json")
        try:
            # --- 1) "/start beta1" → source가 저장됨 ---
            webhook._handle_message(_message("/start beta1", user_id=11111))
            pending_data = access_control._load(access_control.PENDING_REQUESTS_FILE)
            checks.append(("'/start beta1'가 신규 가입 신청을 등록함", "11111" in pending_data))
            checks.append(("파라미터가 source로 저장됨", pending_data["11111"]["source"] == "beta1"))

            # --- 2) 파라미터 없는 "/start"는 기존과 동일 (회귀) ---
            webhook._handle_message(_message("/start", user_id=22222))
            pending_data = access_control._load(access_control.PENDING_REQUESTS_FILE)
            checks.append(("파라미터 없는 '/start'도 정상 등록(회귀)", "22222" in pending_data))
            checks.append(("파라미터 없으면 source는 None", pending_data["22222"]["source"] is None))

            # --- 3) 승인 콜백이 pending의 source를 allowed로 이어받음 ---
            webhook._handle_callback_query(_callback_query("approve:11111", clicker_id=webhook.ADMIN_TELEGRAM_USER_ID))
            allowed_data = access_control._load(access_control.ALLOWED_USERS_FILE)
            checks.append(("승인 시 source가 allowed_users로 이어짐",
                            allowed_data["11111"]["source"] == "beta1"))
        finally:
            access_control.ALLOWED_USERS_FILE = original_allowed
            access_control.PENDING_REQUESTS_FILE = original_pending
            webhook.ADMIN_TELEGRAM_USER_ID = original_admin_id
            webhook.send_message = original_send_message
            webhook.edit_message_text = original_edit_message_text
            webhook.answer_callback_query = original_answer_cb

    print()
    for name, ok in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    print("=" * 50)
    print("전체 결과:", "PASS" if all(ok for _, ok in checks) else "FAIL (위 로그 확인)")


if __name__ == "__main__":
    run()
