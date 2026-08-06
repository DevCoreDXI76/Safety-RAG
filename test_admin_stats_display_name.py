# -*- coding: utf-8 -*-
"""/stats, /authlog가 display_name > username > first_name > id 순으로
표시하는지 검증한다. 실제 data/*.json은 건드리지 않는다.

사용 예:
  python test_admin_stats_display_name.py
"""
import json
import os
import sys
import tempfile

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import api.admin_stats as admin_stats
import api.access_control as access_control


def run():
    checks = []
    original_allowed = access_control.ALLOWED_USERS_FILE
    original_token_log = admin_stats.TOKEN_USAGE_LOG_PATH
    original_auth_log = admin_stats.AUTH_FAILURE_LOG_PATH

    with tempfile.TemporaryDirectory() as tmp_dir:
        access_control.ALLOWED_USERS_FILE = os.path.join(tmp_dir, "allowed_users.json")
        admin_stats.TOKEN_USAGE_LOG_PATH = os.path.join(tmp_dir, "token_usage_log.jsonl")
        admin_stats.AUTH_FAILURE_LOG_PATH = os.path.join(tmp_dir, "auth_failures.jsonl")
        try:
            # build_stats_message: tier 1, 2, 3, 4 커버
            access_control.add_allowed_user(111, username="hong_gd", first_name="홍길동", display_name="홍길동 대리")
            access_control.add_allowed_user(222, username="kim_cs", first_name=None, display_name=None)
            access_control.add_allowed_user(333, username=None, first_name=None, display_name=None)
            access_control.add_allowed_user(444, username=None, first_name="최민준", display_name=None)

            with open(admin_stats.TOKEN_USAGE_LOG_PATH, "w", encoding="utf-8") as f:
                for uid in (111, 222, 333, 444):
                    f.write(json.dumps({
                        "user_id": uid, "document_type": "위험성평가표",
                        "input_tokens": 100, "output_tokens": 50,
                        "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0,
                    }, ensure_ascii=False) + "\n")

            message = admin_stats.build_stats_message()
            checks.append(("build_stats: tier1 display_name", "홍길동 대리 (id: 111)" in message))
            checks.append(("build_stats: tier2 username", "kim_cs (id: 222)" in message))
            checks.append(("build_stats: tier4 id fallback", "id: 333" in message))
            checks.append(("build_stats: tier3 first_name", "최민준 (id: 444)" in message))

            # build_authlog_message: tier 1, 2, 3, 4, 5 커버
            # tier 2: username만 있음
            access_control.add_allowed_user(555, username="park_jy", first_name=None, display_name=None)
            # tier 3: first_name만 있음
            access_control.add_allowed_user(666, username=None, first_name="이순신", display_name=None)

            with open(admin_stats.AUTH_FAILURE_LOG_PATH, "w", encoding="utf-8") as f:
                # tier 1: display_name (from allowed_users)
                f.write(json.dumps({
                    "timestamp": "2026-08-06T21:00:00+09:00", "reason": "not_allowed",
                    "user_id": 111, "username": None,
                }, ensure_ascii=False) + "\n")
                # tier 2: username from allowed_users record
                f.write(json.dumps({
                    "timestamp": "2026-08-06T21:02:00+09:00", "reason": "not_allowed",
                    "user_id": 555, "username": None,
                }, ensure_ascii=False) + "\n")
                # tier 3: first_name from allowed_users record
                f.write(json.dumps({
                    "timestamp": "2026-08-06T21:03:00+09:00", "reason": "not_allowed",
                    "user_id": 666, "username": None,
                }, ensure_ascii=False) + "\n")
                # tier 4: username from log entry itself (user_id not in allowed_users)
                f.write(json.dumps({
                    "timestamp": "2026-08-06T21:04:00+09:00", "reason": "invalid_signature",
                    "user_id": "unverified:777", "username": "fallback_handle",
                }, ensure_ascii=False) + "\n")
                # tier 5: id fallback (user_id not in allowed_users, no username in log)
                f.write(json.dumps({
                    "timestamp": "2026-08-06T21:05:00+09:00", "reason": "invalid_signature",
                    "user_id": "unverified:999", "username": None,
                }, ensure_ascii=False) + "\n")

            authlog_message = admin_stats.build_authlog_message()
            checks.append(("authlog: tier1 display_name", "홍길동 대리" in authlog_message))
            checks.append(("authlog: tier2 username from allowed_users", "park_jy" in authlog_message))
            checks.append(("authlog: tier3 first_name from allowed_users", "이순신" in authlog_message))
            checks.append(("authlog: tier4 username from log entry", "fallback_handle" in authlog_message))
            checks.append(("authlog: tier5 id fallback", "id: unverified:999" in authlog_message))
        finally:
            access_control.ALLOWED_USERS_FILE = original_allowed
            admin_stats.TOKEN_USAGE_LOG_PATH = original_token_log
            admin_stats.AUTH_FAILURE_LOG_PATH = original_auth_log

    print()
    for name, ok in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    print("=" * 50)
    print("전체 결과:", "PASS" if all(ok for _, ok in checks) else "FAIL (위 로그 확인)")


if __name__ == "__main__":
    run()
