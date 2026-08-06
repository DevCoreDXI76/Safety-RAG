# -*- coding: utf-8 -*-
"""webhook.py 최종 통합 리뷰 Finding #3 검증 — 관리자 자신이 이름 대기
상태에 걸려 있어도 이름 대기 분기에 먹히지 않고 관리자 명령이 정상 처리
되어야 한다. 비관리자는 여전히 이름 대기 분기가 그대로 동작해야 한다
(회귀 확인 — 관리자 예외가 전체 사용자에게 새는지 검증).

사용 예:
  python test_webhook_admin_name_exemption.py
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


def run():
    checks = []
    original_allowed = access_control.ALLOWED_USERS_FILE
    original_pending = access_control.PENDING_REQUESTS_FILE
    original_admin_id = webhook.ADMIN_TELEGRAM_USER_ID
    original_send_message = webhook.send_message
    original_build_stats = webhook.build_stats_message

    ADMIN_ID = 999999
    webhook.ADMIN_TELEGRAM_USER_ID = ADMIN_ID
    sent = []
    webhook.send_message = lambda *a, **k: sent.append((a, k)) or {}
    webhook.build_stats_message = lambda: "stats-called"

    with tempfile.TemporaryDirectory() as tmp_dir:
        access_control.ALLOWED_USERS_FILE = os.path.join(tmp_dir, "allowed_users.json")
        access_control.PENDING_REQUESTS_FILE = os.path.join(tmp_dir, "pending_requests.json")
        try:
            # --- 1) 관리자 본인이 이름 대기 상태(pending)여도 /stats는 정상 도달 ---
            access_control.add_pending_request(ADMIN_ID, username=None, first_name="관리자")
            checks.append(("사전조건: 관리자도 이름 대기 상태로 걸림", access_control.is_awaiting_name(ADMIN_ID)))

            sent.clear()
            webhook._handle_message(_message("/stats", user_id=ADMIN_ID))
            checks.append(("관리자는 이름 대기 상태여도 /stats가 처리됨", any("stats-called" in a[1] for a, k in sent)))

            pending_data = access_control._load(access_control.PENDING_REQUESTS_FILE)
            checks.append(
                ("관리자의 /stats 호출이 이름으로 오저장되지 않음",
                 not pending_data[str(ADMIN_ID)].get("display_name")),
            )

            # --- 2) 회귀: 비관리자는 동일한 이름 대기 상태에서 여전히 이름으로 캡처됨 ---
            NON_ADMIN_ID = 12345
            access_control.add_pending_request(NON_ADMIN_ID, username=None, first_name="일반")
            checks.append(("사전조건: 비관리자도 이름 대기 상태", access_control.is_awaiting_name(NON_ADMIN_ID)))

            sent.clear()
            webhook._handle_message(_message("/stats", user_id=NON_ADMIN_ID))
            pending_data = access_control._load(access_control.PENDING_REQUESTS_FILE)
            checks.append(
                ("비관리자는 이름 대기 상태에서 텍스트가 이름으로 캡처됨(회귀)",
                 pending_data[str(NON_ADMIN_ID)]["display_name"] == "/stats" or
                 pending_data[str(NON_ADMIN_ID)]["display_name"] is None),
            )
            # "/stats"는 "/"로 시작하므로 is_valid_name_reply가 거부 → 이름 저장은 안 되지만
            # /stats 명령으로도 처리되면 안 됨(이름 대기 분기가 먼저 소비해야 함).
            checks.append(
                ("비관리자는 /stats가 관리자 명령으로 처리되지 않음(이름 대기 분기가 먼저 소비)",
                 not any("stats-called" in a[1] for a, k in sent)),
            )
            checks.append(
                ("비관리자에게는 형식 오류 재요청 메시지가 감",
                 any("간단히" in a[1] for a, k in sent)),
            )
        finally:
            access_control.ALLOWED_USERS_FILE = original_allowed
            access_control.PENDING_REQUESTS_FILE = original_pending
            webhook.ADMIN_TELEGRAM_USER_ID = original_admin_id
            webhook.send_message = original_send_message
            webhook.build_stats_message = original_build_stats

    print()
    for name, ok in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    print("=" * 50)
    print("전체 결과:", "PASS" if all(ok for _, ok in checks) else "FAIL (위 로그 확인)")


if __name__ == "__main__":
    run()
