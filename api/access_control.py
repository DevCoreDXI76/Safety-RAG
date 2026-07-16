"""파일 기반 사용자 승인 관리 — allowed_users.json(승인 목록) / pending_requests.json(대기 목록)"""

import os
import sys
import json
import threading

# 프로젝트 루트의 common.py를 import하기 위한 경로 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common import DATA_DIR
from api.telegram_bot import send_message, approve_reject_keyboard

ADMIN_TELEGRAM_USER_ID = int(os.getenv("ADMIN_TELEGRAM_USER_ID", "0"))
DAILY_LIMIT = 5

ALLOWED_USERS_FILE = os.path.join(DATA_DIR, "allowed_users.json")
PENDING_REQUESTS_FILE = os.path.join(DATA_DIR, "pending_requests.json")

_lock = threading.Lock()


def _load(filepath):
    if not os.path.exists(filepath):
        return {}
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(filepath, data):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def is_allowed(user_id):
    if int(user_id) == ADMIN_TELEGRAM_USER_ID:
        return True
    with _lock:
        data = _load(ALLOWED_USERS_FILE)
    return str(user_id) in data


def add_allowed_user(user_id, username=None):
    with _lock:
        data = _load(ALLOWED_USERS_FILE)
        data[str(user_id)] = {"username": username}
        _save(ALLOWED_USERS_FILE, data)


def get_allowed_users():
    with _lock:
        return _load(ALLOWED_USERS_FILE)


def remove_allowed_user(user_id):
    """승인을 취소한다. 목록에 없었으면 False, 제거했으면 True."""
    with _lock:
        data = _load(ALLOWED_USERS_FILE)
        if str(user_id) not in data:
            return False
        data.pop(str(user_id))
        _save(ALLOWED_USERS_FILE, data)
        return True


def is_pending(user_id):
    with _lock:
        data = _load(PENDING_REQUESTS_FILE)
    return str(user_id) in data


def get_pending_request(user_id):
    """대기 목록에서 해당 user_id의 신청 정보(username, first_name)를 반환. 없으면 None."""
    with _lock:
        data = _load(PENDING_REQUESTS_FILE)
    return data.get(str(user_id))


def add_pending_request(user_id, username=None, first_name=None):
    with _lock:
        data = _load(PENDING_REQUESTS_FILE)
        data[str(user_id)] = {"username": username, "first_name": first_name}
        _save(PENDING_REQUESTS_FILE, data)


def register_pending_request(user_id, username=None, first_name=None):
    """
    대기 등록 + 신청자 확인 메시지 + 관리자 알림을 한 번에 처리하는 공용 진입점.
    "/start" 텍스트 메시지(webhook.py)와 미니앱 첫 API 호출(telegram_auth.py)
    양쪽에서 동일하게 호출한다 — 사용자가 /start를 몰라도 미니앱을 여는 순간
    자동으로 등록되도록 하기 위함(2026-07 개선). 이미 승인됐거나 이미 대기
    중이면 아무 것도 하지 않고 False를 반환한다.
    """
    if is_allowed(user_id) or is_pending(user_id):
        return False

    add_pending_request(user_id, username=username, first_name=first_name)
    send_message(user_id, "사용 신청이 접수되었습니다. 관리자 승인 후 이용 가능합니다.")

    if ADMIN_TELEGRAM_USER_ID:
        name = username or first_name or str(user_id)
        send_message(
            ADMIN_TELEGRAM_USER_ID,
            f"📩 새 사용 신청: {name} (id: {user_id})",
            reply_markup=approve_reject_keyboard(user_id),
        )
    return True


def remove_pending_request(user_id):
    with _lock:
        data = _load(PENDING_REQUESTS_FILE)
        data.pop(str(user_id), None)
        _save(PENDING_REQUESTS_FILE, data)
