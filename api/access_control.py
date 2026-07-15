"""파일 기반 사용자 승인 관리 — allowed_users.json(승인 목록) / pending_requests.json(대기 목록)"""

import os
import sys
import json
import threading

# 프로젝트 루트의 common.py를 import하기 위한 경로 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common import DATA_DIR

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


def remove_pending_request(user_id):
    with _lock:
        data = _load(PENDING_REQUESTS_FILE)
        data.pop(str(user_id), None)
        _save(PENDING_REQUESTS_FILE, data)
