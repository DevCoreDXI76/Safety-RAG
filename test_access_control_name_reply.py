# -*- coding: utf-8 -*-
"""record_name_reply(이름 저장 + 신규 신청 시 관리자 최초 1회 알림),
sweep_stale_name_requests(타임아웃 폴백), maybe_ask_backfill_name(기존
승인자 소급 1회 요청)을 검증한다. 실제 텔레그램 발송은 하지 않는다.

사용 예:
  python test_access_control_name_reply.py
"""
import os
import sys
import tempfile
from datetime import datetime, timedelta

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import api.access_control as access_control
from common import KST


def run():
    checks = []
    original_allowed = access_control.ALLOWED_USERS_FILE
    original_pending = access_control.PENDING_REQUESTS_FILE
    original_admin_id = access_control.ADMIN_TELEGRAM_USER_ID
    original_send_message = access_control.send_message

    with tempfile.TemporaryDirectory() as tmp_dir:
        access_control.ALLOWED_USERS_FILE = os.path.join(tmp_dir, "allowed_users.json")
        access_control.PENDING_REQUESTS_FILE = os.path.join(tmp_dir, "pending_requests.json")
        access_control.ADMIN_TELEGRAM_USER_ID = 999999
        sent = []
        access_control.send_message = lambda *a, **k: sent.append((a, k)) or {}
        try:
            # --- record_name_reply: 신규 신청(pending) 경로 ---
            access_control.add_pending_request(111, username=None, first_name="철수")
            sent.clear()
            access_control.record_name_reply(111, "이철수")
            pending_data = access_control._load(access_control.PENDING_REQUESTS_FILE)
            checks.append(("이름이 pending 레코드에 저장됨", pending_data["111"]["display_name"] == "이철수"))
            checks.append(("최초 이름 응답 시 관리자에게 1번 알림", len(sent) == 1))
            checks.append(("알림 대상은 관리자", sent[0][0][0] == access_control.ADMIN_TELEGRAM_USER_ID))
            checks.append(("알림 문구에 이름이 포함됨", "이철수" in sent[0][0][1]))
            checks.append(("admin_notified가 True로 갱신됨", pending_data["111"]["admin_notified"] is True))

            # 같은 사람이 이름을 또 답장해도(극단적 상황) 관리자에게 또 알리지 않음
            sent.clear()
            access_control.record_name_reply(111, "또다른이름")
            checks.append(("이미 admin_notified면 재알림 없음", len(sent) == 0))

            # --- record_name_reply: 기존 승인자 소급(allowed) 경로 ---
            access_control.add_allowed_user(222, username=None, first_name="영희")
            data = access_control._load(access_control.ALLOWED_USERS_FILE)
            data["222"]["name_asked_at"] = datetime.now(KST).isoformat()
            access_control._save(access_control.ALLOWED_USERS_FILE, data)

            sent.clear()
            access_control.record_name_reply(222, "박영희")
            allowed_data = access_control._load(access_control.ALLOWED_USERS_FILE)
            checks.append(("이름이 allowed 레코드에 저장됨", allowed_data["222"]["display_name"] == "박영희"))
            checks.append(("기존 승인자 소급 응답은 관리자 알림 없음", len(sent) == 0))

            # --- sweep_stale_name_requests: 타임아웃 폴백 ---
            access_control.add_pending_request(333, username=None, first_name="김민수")
            data = access_control._load(access_control.PENDING_REQUESTS_FILE)
            stale_time = datetime.now(KST) - timedelta(minutes=31)
            data["333"]["name_requested_at"] = stale_time.isoformat()
            access_control._save(access_control.PENDING_REQUESTS_FILE, data)

            sent.clear()
            access_control.sweep_stale_name_requests(timeout_minutes=30)
            checks.append(("31분 지난 미응답 신청은 폴백 알림 발송", len(sent) == 1))
            checks.append(("폴백 알림은 관리자에게", sent[0][0][0] == access_control.ADMIN_TELEGRAM_USER_ID))
            checks.append(("폴백 알림 문구에 '이름 미입력' 표시", "이름 미입력" in sent[0][0][1]))
            data = access_control._load(access_control.PENDING_REQUESTS_FILE)
            checks.append(("폴백 발송 후 admin_notified=True로 갱신", data["333"]["admin_notified"] is True))

            # 같은 항목을 다시 훑어도 중복 발송 안 함
            sent.clear()
            access_control.sweep_stale_name_requests(timeout_minutes=30)
            checks.append(("이미 폴백 발송된 항목은 재발송 안 함", len(sent) == 0))

            # 아직 30분이 안 지난 항목은 건드리지 않음
            access_control.add_pending_request(444, username=None, first_name="최수")
            sent.clear()
            access_control.sweep_stale_name_requests(timeout_minutes=30)
            checks.append(("30분이 안 지난 항목은 폴백 발송 안 함", len(sent) == 0))

            # --- maybe_ask_backfill_name: 기존 승인자 1회성 요청 ---
            access_control.add_allowed_user(555, username=None, first_name="정다은")
            sent.clear()
            access_control.maybe_ask_backfill_name(555)
            checks.append(("이름 없는 기존 승인자에게 1번 요청 발송", len(sent) == 1))
            allowed_data = access_control._load(access_control.ALLOWED_USERS_FILE)
            checks.append(("발송 후 name_asked_at이 채워짐", bool(allowed_data["555"]["name_asked_at"])))

            # 같은 사람에게 다시 호출해도 재발송 안 함(name_asked_at이 이미 있으므로)
            sent.clear()
            access_control.maybe_ask_backfill_name(555)
            checks.append(("이미 요청한 적 있으면 재발송 안 함", len(sent) == 0))

            # 이미 display_name이 있는 사람에게는 애초에 요청 안 함
            access_control.add_allowed_user(666, username=None, first_name="한지민", display_name="한지민")
            sent.clear()
            access_control.maybe_ask_backfill_name(666)
            checks.append(("이미 이름이 있으면 요청 자체를 안 함", len(sent) == 0))

            # 승인 목록에 없는 user_id(예: 관리자 본인)는 조용히 무시
            sent.clear()
            access_control.maybe_ask_backfill_name(777)
            checks.append(("승인 목록에 없는 user_id는 예외 없이 무시됨", len(sent) == 0))
        finally:
            access_control.ALLOWED_USERS_FILE = original_allowed
            access_control.PENDING_REQUESTS_FILE = original_pending
            access_control.ADMIN_TELEGRAM_USER_ID = original_admin_id
            access_control.send_message = original_send_message

    print()
    for name, ok in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    print("=" * 50)
    print("전체 결과:", "PASS" if all(ok for _, ok in checks) else "FAIL (위 로그 확인)")


if __name__ == "__main__":
    run()
