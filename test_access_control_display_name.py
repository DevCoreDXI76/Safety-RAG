# -*- coding: utf-8 -*-
"""승인 시 first_name 보존 + 표시 이름 폴백(username > first_name > user_id) 검증.
실제 data/allowed_users.json을 건드리지 않기 위해 ALLOWED_USERS_FILE을
테스트 동안만 임시 경로로 바꿔치기한다.

사용 예:
  python test_access_control_display_name.py
"""
import os
import sys
import tempfile

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import api.access_control as access_control


def run():
    checks = []
    original_path = access_control.ALLOWED_USERS_FILE
    with tempfile.TemporaryDirectory() as tmp_dir:
        access_control.ALLOWED_USERS_FILE = os.path.join(tmp_dir, "allowed_users.json")
        try:
            access_control.add_allowed_user(111, username="hong_gd", first_name="홍길동")
            checks.append(("username 있으면 username 반환", access_control.resolve_display_name(111) == "hong_gd"))

            access_control.add_allowed_user(222, username=None, first_name="김철수")
            checks.append(("username 없으면 first_name 반환", access_control.resolve_display_name(222) == "김철수"))

            access_control.add_allowed_user(333, username=None, first_name=None)
            checks.append(("둘 다 없으면 user_id 문자열 반환", access_control.resolve_display_name(333) == "333"))

            checks.append(("승인 목록에 없는 user_id도 user_id 문자열 반환", access_control.resolve_display_name(999) == "999"))
        finally:
            access_control.ALLOWED_USERS_FILE = original_path

    print()
    for name, ok in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    print("=" * 50)
    print("전체 결과:", "PASS" if all(ok for _, ok in checks) else "FAIL (위 로그 확인)")


if __name__ == "__main__":
    run()
