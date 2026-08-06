# -*- coding: utf-8 -*-
"""require_telegram_auth()가 승인된 사용자에게 maybe_ask_backfill_name을
호출해 이름이 없으면 소급 요청을 보내는지 검증한다. 실제 텔레그램 발송은
하지 않는다.

사용 예:
  python test_telegram_auth_backfill_name.py
"""
import hashlib
import hmac
import json
import os
import sys
import tempfile
from urllib.parse import urlencode

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import api.telegram_auth as telegram_auth
import api.access_control as access_control

FAKE_BOT_TOKEN = "123456:FAKE-TOKEN-FOR-TESTS"


def _build_init_data(user, auth_date="1700000000"):
    payload = {"auth_date": auth_date, "user": json.dumps(user, ensure_ascii=False)}
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(payload.items()))
    secret_key = hmac.new(b"WebAppData", FAKE_BOT_TOKEN.encode(), hashlib.sha256).digest()
    computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    payload["hash"] = computed_hash
    return urlencode(payload)


def run():
    checks = []
    original_token = telegram_auth.TELEGRAM_BOT_TOKEN
    original_allowed = access_control.ALLOWED_USERS_FILE
    original_pending = access_control.PENDING_REQUESTS_FILE
    original_send_message = access_control.send_message

    telegram_auth.TELEGRAM_BOT_TOKEN = FAKE_BOT_TOKEN
    with tempfile.TemporaryDirectory() as tmp_dir:
        access_control.ALLOWED_USERS_FILE = os.path.join(tmp_dir, "allowed_users.json")
        access_control.PENDING_REQUESTS_FILE = os.path.join(tmp_dir, "pending_requests.json")
        sent = []
        access_control.send_message = lambda *a, **k: sent.append((a, k)) or {}
        try:
            access_control.add_allowed_user(111, username=None, first_name="철수")
            init_data = _build_init_data({"id": 111, "first_name": "철수"})

            sent.clear()
            result = telegram_auth.require_telegram_auth(x_telegram_init_data=init_data)
            checks.append(("승인된 사용자는 정상 통과", result["user_id"] == 111))
            checks.append(("이름 없는 승인자는 접속 시 소급 요청 발송", len(sent) == 1))

            data = access_control._load(access_control.ALLOWED_USERS_FILE)
            checks.append(("소급 요청 발송 후 name_asked_at 채워짐", bool(data["111"]["name_asked_at"])))

            # 같은 사람이 API를 또 호출해도(같은 세션 내 여러 호출) 재발송 안 함
            sent.clear()
            telegram_auth.require_telegram_auth(x_telegram_init_data=init_data)
            checks.append(("같은 세션에서 다시 호출해도 재발송 안 함", len(sent) == 0))

            # 이미 이름이 있는 승인자는 애초에 요청 안 함
            access_control.add_allowed_user(222, username=None, first_name="영희", display_name="김영희")
            init_data_222 = _build_init_data({"id": 222, "first_name": "영희"})
            sent.clear()
            telegram_auth.require_telegram_auth(x_telegram_init_data=init_data_222)
            checks.append(("이미 이름이 있으면 소급 요청 안 보냄", len(sent) == 0))
        finally:
            telegram_auth.TELEGRAM_BOT_TOKEN = original_token
            access_control.ALLOWED_USERS_FILE = original_allowed
            access_control.PENDING_REQUESTS_FILE = original_pending
            access_control.send_message = original_send_message

    print()
    for name, ok in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    print("=" * 50)
    print("전체 결과:", "PASS" if all(ok for _, ok in checks) else "FAIL (위 로그 확인)")


if __name__ == "__main__":
    run()
