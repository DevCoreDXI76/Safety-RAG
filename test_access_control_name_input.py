# -*- coding: utf-8 -*-
"""이름 입력 기능 1단계: 데이터 모델 확장 + 표시 이름 우선순위에 display_name
반영, register_pending_request가 더 이상 즉시 관리자 알림을 보내지 않고
이름을 요청하는지 검증한다. 실제 allowed_users.json/pending_requests.json은
건드리지 않는다.

사용 예:
  python test_access_control_name_input.py
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
    original_admin_id = access_control.ADMIN_TELEGRAM_USER_ID
    original_send_message = access_control.send_message

    with tempfile.TemporaryDirectory() as tmp_dir:
        access_control.ALLOWED_USERS_FILE = os.path.join(tmp_dir, "allowed_users.json")
        access_control.PENDING_REQUESTS_FILE = os.path.join(tmp_dir, "pending_requests.json")
        access_control.ADMIN_TELEGRAM_USER_ID = 999999
        sent = []
        access_control.send_message = lambda *a, **k: sent.append((a, k)) or {}
        try:
            # --- resolve_display_name: display_name이 최우선 ---
            access_control.add_allowed_user(111, username="hong_gd", first_name="홍길동", display_name="홍길동 대리")
            checks.append(("display_name이 있으면 최우선 반환",
                            access_control.resolve_display_name(111) == "홍길동 대리"))

            access_control.add_allowed_user(222, username="kim_cs", first_name="김철수", display_name=None)
            checks.append(("display_name 없으면 기존처럼 username 반환",
                            access_control.resolve_display_name(222) == "kim_cs"))

            # --- add_allowed_user: 새 필드 저장 확인 ---
            data = access_control._load(access_control.ALLOWED_USERS_FILE)
            checks.append(("add_allowed_user가 display_name 저장", data["111"]["display_name"] == "홍길동 대리"))
            checks.append(("add_allowed_user가 name_asked_at을 None으로 초기화", data["111"]["name_asked_at"] is None))

            # --- add_pending_request: 새 필드 기본값 확인 ---
            access_control.add_pending_request(333, username=None, first_name="박영희")
            pending_data = access_control._load(access_control.PENDING_REQUESTS_FILE)
            record = pending_data["333"]
            checks.append(("add_pending_request가 display_name을 None으로 시작", record["display_name"] is None))
            checks.append(("add_pending_request가 name_requested_at을 채움", bool(record["name_requested_at"])))
            checks.append(("add_pending_request가 admin_notified를 False로 시작", record["admin_notified"] is False))

            # --- register_pending_request: 더 이상 즉시 관리자에게 알리지 않는다 ---
            sent.clear()
            result = access_control.register_pending_request(444, username=None, first_name="이순신")
            checks.append(("신규 등록은 True 반환", result is True))
            checks.append(("등록 시 메시지는 정확히 1번(사용자에게 이름 요청)만 나감", len(sent) == 1))
            checks.append(("그 1번은 관리자가 아니라 신청자 본인에게 감", sent[0][0][0] == 444))
            checks.append(("메시지 내용에 이름을 요청하는 문구가 있음", "성함" in sent[0][0][1]))

            pending_data = access_control._load(access_control.PENDING_REQUESTS_FILE)
            checks.append(("등록 직후 display_name은 아직 비어있음", pending_data["444"]["display_name"] is None))

            # 이미 대기 중인 사람은 다시 등록해도 메시지가 추가로 나가지 않음
            sent.clear()
            result2 = access_control.register_pending_request(444, username=None, first_name="이순신")
            checks.append(("이미 대기 중이면 False 반환", result2 is False))
            checks.append(("이미 대기 중이면 메시지도 안 나감", len(sent) == 0))
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
