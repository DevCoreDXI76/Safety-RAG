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
            access_control.add_allowed_user(111, username="hong_gd", first_name="홍길동", display_name="홍길동 대리")
            access_control.add_allowed_user(222, username="kim_cs", first_name=None, display_name=None)
            access_control.add_allowed_user(333, username=None, first_name=None, display_name=None)

            with open(admin_stats.TOKEN_USAGE_LOG_PATH, "w", encoding="utf-8") as f:
                for uid in (111, 222, 333):
                    f.write(json.dumps({
                        "user_id": uid, "document_type": "위험성평가표",
                        "input_tokens": 100, "output_tokens": 50,
                        "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0,
                    }, ensure_ascii=False) + "\n")

            message = admin_stats.build_stats_message()
            checks.append(("display_name이 있으면 그걸 표시", "홍길동 대리 (id: 111)" in message))
            checks.append(("display_name 없으면 username 표시", "kim_cs (id: 222)" in message))
            checks.append(("아무 이름도 없으면 id만 표시", "id: 333" in message))

            with open(admin_stats.AUTH_FAILURE_LOG_PATH, "w", encoding="utf-8") as f:
                f.write(json.dumps({
                    "timestamp": "2026-08-06T21:00:00+09:00", "reason": "not_allowed",
                    "user_id": 111, "username": None,
                }, ensure_ascii=False) + "\n")
                f.write(json.dumps({
                    "timestamp": "2026-08-06T21:05:00+09:00", "reason": "invalid_signature",
                    "user_id": "unverified:999", "username": None,
                }, ensure_ascii=False) + "\n")

            authlog_message = admin_stats.build_authlog_message()
            checks.append(("authlog도 display_name 우선 표시", "홍길동 대리" in authlog_message))
            checks.append(("승인 목록에 없는 user_id는 id로 표시",
                            "id: unverified:999" in authlog_message))
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
