# -*- coding: utf-8 -*-
"""'/start <param>' 딥링크 유입 출처를 pending/allowed 레코드에 "source"
필드로 저장하는지 검증한다(베타0/베타1 유입 구분용). 실제
allowed_users.json/pending_requests.json은 건드리지 않는다.

사용 예:
  python test_access_control_source_field.py
"""
import os
import sys
import tempfile

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import api.access_control as access_control


def run():
    checks = []
    original_allowed = access_control.ALLOWED_USERS_FILE
    original_pending = access_control.PENDING_REQUESTS_FILE
    original_send_message = access_control.send_message

    with tempfile.TemporaryDirectory() as tmp_dir:
        access_control.ALLOWED_USERS_FILE = os.path.join(tmp_dir, "allowed_users.json")
        access_control.PENDING_REQUESTS_FILE = os.path.join(tmp_dir, "pending_requests.json")
        sent = []
        access_control.send_message = lambda *a, **k: sent.append((a, k)) or {}
        try:
            # --- add_pending_request: source 저장 ---
            access_control.add_pending_request(111, username=None, first_name="철수", source="beta1")
            pending_data = access_control._load(access_control.PENDING_REQUESTS_FILE)
            checks.append(("add_pending_request가 source를 저장", pending_data["111"]["source"] == "beta1"))

            # --- add_pending_request: source 생략 시 None (기존 호출부 회귀) ---
            access_control.add_pending_request(222, username=None, first_name="영희")
            pending_data = access_control._load(access_control.PENDING_REQUESTS_FILE)
            checks.append(("source 생략하면 None으로 저장", pending_data["222"]["source"] is None))

            # --- register_pending_request: source를 add_pending_request로 전달 ---
            access_control.register_pending_request(333, username=None, first_name="민수", source="beta1")
            pending_data = access_control._load(access_control.PENDING_REQUESTS_FILE)
            checks.append(("register_pending_request가 source를 전달", pending_data["333"]["source"] == "beta1"))

            # --- add_allowed_user: source 저장 ---
            access_control.add_allowed_user(444, username="kim", first_name="영수", source="beta1")
            allowed_data = access_control._load(access_control.ALLOWED_USERS_FILE)
            checks.append(("add_allowed_user가 source를 저장", allowed_data["444"]["source"] == "beta1"))

            # --- add_allowed_user: source 생략 시 None (기존 호출부 회귀) ---
            access_control.add_allowed_user(555, username="lee", first_name="정희")
            allowed_data = access_control._load(access_control.ALLOWED_USERS_FILE)
            checks.append(("source 생략하면 None으로 저장 (allowed)", allowed_data["555"]["source"] is None))
        finally:
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
