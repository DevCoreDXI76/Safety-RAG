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

            # --- backfill_first_name: 구버전(2키 스키마) 기존 승인자 보강 ---

            # (a) first_name이 없던 레코드는 텔레그램이 알려준 값으로 채워진다
            access_control.add_allowed_user(444, username=None, first_name=None)
            access_control.backfill_first_name(444, "박영희")
            checks.append(("first_name 없던 레코드가 backfill로 채워짐",
                            access_control.resolve_display_name(444) == "박영희"))

            # (b) 이미 first_name이 있으면 다른 값으로 덮어쓰지 않는다(비파괴적)
            access_control.add_allowed_user(555, username=None, first_name="원래이름")
            access_control.backfill_first_name(555, "다른이름")
            checks.append(("기존 first_name은 backfill로 덮어써지지 않음",
                            access_control.resolve_display_name(555) == "원래이름"))

            # (c) username이 이미 있는 사용자는 backfill과 무관(username 우선순위 그대로)
            access_control.add_allowed_user(666, username="already_set", first_name=None)
            access_control.backfill_first_name(666, "새이름")
            data_after = access_control._load(access_control.ALLOWED_USERS_FILE)
            checks.append(("username은 backfill로 건드려지지 않음",
                            data_after["666"]["username"] == "already_set"))
            checks.append(("username이 있어도 first_name 자체는 backfill됨(표시엔 영향 없음)",
                            data_after["666"]["first_name"] == "새이름"))
            checks.append(("username이 있으면 표시 이름은 여전히 username",
                            access_control.resolve_display_name(666) == "already_set"))

            # (d) 승인 목록에 아예 없는 user_id는 backfill이 아무 것도 하지 않는다(예외도 없음)
            access_control.backfill_first_name(777, "유령")
            checks.append(("목록에 없는 user_id는 backfill해도 새로 생기지 않음",
                            "777" not in access_control._load(access_control.ALLOWED_USERS_FILE)))

            # (e) 텔레그램이 이번 호출에 first_name을 안 줬으면(빈 값) 아무 것도 하지 않는다
            access_control.add_allowed_user(888, username=None, first_name=None)
            access_control.backfill_first_name(888, None)
            checks.append(("빈 first_name으로 backfill 호출해도 그대로 없음",
                            access_control.resolve_display_name(888) == "888"))
        finally:
            access_control.ALLOWED_USERS_FILE = original_path

    print()
    for name, ok in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    print("=" * 50)
    print("전체 결과:", "PASS" if all(ok for _, ok in checks) else "FAIL (위 로그 확인)")


if __name__ == "__main__":
    run()
