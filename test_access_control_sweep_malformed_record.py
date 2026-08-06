# -*- coding: utf-8 -*-
"""sweep_stale_name_requests의 최종 통합 리뷰 Finding #2 검증 — 한 레코드의
name_requested_at이 파싱 불가(naive timestamp/깨진 문자열)여도 다른 정상
레코드의 타임아웃 폴백 처리를 막지 않아야 한다.

사용 예:
  python test_access_control_sweep_malformed_record.py
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
    original_pending = access_control.PENDING_REQUESTS_FILE
    original_admin_id = access_control.ADMIN_TELEGRAM_USER_ID
    original_send_message = access_control.send_message

    with tempfile.TemporaryDirectory() as tmp_dir:
        access_control.PENDING_REQUESTS_FILE = os.path.join(tmp_dir, "pending_requests.json")
        access_control.ADMIN_TELEGRAM_USER_ID = 999999
        sent = []
        access_control.send_message = lambda *a, **k: sent.append((a, k)) or {}

        try:
            # 정상: 45분 지난 유효한 타임스탬프 레코드
            access_control.add_pending_request(111, username=None, first_name="정상")
            data = access_control._load(access_control.PENDING_REQUESTS_FILE)
            stale_time = datetime.now(KST) - timedelta(minutes=45)
            data["111"]["name_requested_at"] = stale_time.isoformat()

            # 깨진: naive timestamp(타임존 정보 없음) — KST(aware)와 뺄셈 시 TypeError 유발
            data["222"] = {
                "username": None,
                "first_name": "깨짐naive",
                "display_name": None,
                "name_requested_at": "2026-08-01T12:00:00",  # naive
                "admin_notified": False,
            }

            # 깨진: 아예 파싱 불가한 문자열
            data["333"] = {
                "username": None,
                "first_name": "깨짐문자열",
                "display_name": None,
                "name_requested_at": "이것은-날짜가-아님",
                "admin_notified": False,
            }
            access_control._save(access_control.PENDING_REQUESTS_FILE, data)

            sent.clear()
            exc = None
            try:
                access_control.sweep_stale_name_requests(timeout_minutes=30)
            except Exception as e:  # noqa: BLE001
                exc = e

            checks.append(("스윕 호출이 예외 없이 완료됨", exc is None))
            checks.append(("정상 레코드는 타임아웃 폴백 알림 발송됨", len(sent) == 1))
            checks.append(("폴백 알림 대상은 관리자", sent and sent[0][0][0] == access_control.ADMIN_TELEGRAM_USER_ID))

            after = access_control._load(access_control.PENDING_REQUESTS_FILE)
            checks.append(("정상 레코드 admin_notified=True로 갱신됨", after["111"]["admin_notified"] is True))
            checks.append(("naive timestamp 레코드는 크래시 없이 건너뜀(admin_notified 그대로 False)",
                            after["222"]["admin_notified"] is False))
            checks.append(("파싱 불가 문자열 레코드도 건너뜀(admin_notified 그대로 False)",
                            after["333"]["admin_notified"] is False))
        finally:
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
