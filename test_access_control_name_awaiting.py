# -*- coding: utf-8 -*-
"""is_valid_name_reply(형식 검증)와 is_awaiting_name(이름 대기 상태 판별)을
검증한다. 신규 신청(pending)과 기존 승인자 소급(allowed) 두 경로가
독립적으로 판별되는지 확인한다.

사용 예:
  python test_access_control_name_awaiting.py
"""
import os
import sys
import tempfile

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import api.access_control as access_control


def run():
    checks = []

    # --- is_valid_name_reply: 파일 I/O 없는 순수 함수 ---
    checks.append(("일반 한글 이름은 통과", access_control.is_valid_name_reply("홍길동") is True))
    checks.append(("공백 포함 짧은 이름도 통과", access_control.is_valid_name_reply("홍길동 대리") is True))
    checks.append(("20자 초과는 거부", access_control.is_valid_name_reply("가" * 21) is False))
    checks.append(("정확히 20자는 통과", access_control.is_valid_name_reply("가" * 20) is True))
    checks.append(("빈 문자열은 거부", access_control.is_valid_name_reply("") is False))
    checks.append(("공백만 있으면 거부", access_control.is_valid_name_reply("   ") is False))
    checks.append(("/로 시작하면 거부(명령어로 오인 방지)", access_control.is_valid_name_reply("/stats") is False))
    checks.append(("쉼표 포함이면 거부(문장형 답장 방어)",
                    access_control.is_valid_name_reply("표 순서가 헷갈려요, 좁아요") is False))
    checks.append(("물음표 포함이면 거부", access_control.is_valid_name_reply("이게 맞나요?") is False))
    checks.append(("마침표 포함이면 거부", access_control.is_valid_name_reply("홍길동.") is False))

    # --- is_awaiting_name: pending/allowed 두 경로 ---
    original_allowed = access_control.ALLOWED_USERS_FILE
    original_pending = access_control.PENDING_REQUESTS_FILE
    with tempfile.TemporaryDirectory() as tmp_dir:
        access_control.ALLOWED_USERS_FILE = os.path.join(tmp_dir, "allowed_users.json")
        access_control.PENDING_REQUESTS_FILE = os.path.join(tmp_dir, "pending_requests.json")
        try:
            # 신규 신청: pending에 있고 display_name이 아직 없음 → 대기 중
            access_control.add_pending_request(111, username=None, first_name="철수")
            checks.append(("신규 신청 직후엔 이름 대기 상태", access_control.is_awaiting_name(111) is True))

            # 이름을 받은 뒤엔 더 이상 대기 상태 아님
            data = access_control._load(access_control.PENDING_REQUESTS_FILE)
            data["111"]["display_name"] = "이철수"
            access_control._save(access_control.PENDING_REQUESTS_FILE, data)
            checks.append(("이름을 받으면 대기 상태 해제(pending)", access_control.is_awaiting_name(111) is False))

            # 기존 승인자: allowed에 있지만 아직 이름을 물어본 적 없음(name_asked_at 없음) → 대기 아님
            access_control.add_allowed_user(222, username=None, first_name="영희")
            checks.append(("아직 안 물어본 기존 승인자는 대기 상태 아님", access_control.is_awaiting_name(222) is False))

            # 소급 요청을 보낸 뒤(name_asked_at 채워짐)엔 대기 상태
            data = access_control._load(access_control.ALLOWED_USERS_FILE)
            data["222"]["name_asked_at"] = "2026-08-06T21:00:00+09:00"
            access_control._save(access_control.ALLOWED_USERS_FILE, data)
            checks.append(("소급 요청 발송 후엔 이름 대기 상태(allowed)", access_control.is_awaiting_name(222) is True))

            # 이름을 받은 뒤엔 다시 해제
            data = access_control._load(access_control.ALLOWED_USERS_FILE)
            data["222"]["display_name"] = "박영희"
            access_control._save(access_control.ALLOWED_USERS_FILE, data)
            checks.append(("이름을 받으면 대기 상태 해제(allowed)", access_control.is_awaiting_name(222) is False))

            # 아무 관련도 없는 user_id는 항상 대기 상태 아님
            checks.append(("등록된 적 없는 user_id는 대기 상태 아님", access_control.is_awaiting_name(999) is False))
        finally:
            access_control.ALLOWED_USERS_FILE = original_allowed
            access_control.PENDING_REQUESTS_FILE = original_pending

    print()
    for name, ok in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    print("=" * 50)
    print("전체 결과:", "PASS" if all(ok for _, ok in checks) else "FAIL (위 로그 확인)")


if __name__ == "__main__":
    run()
