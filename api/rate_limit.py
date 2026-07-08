"""인당 일일 사용량 제한 — KST(한국 시간) 기준으로 자정 리셋"""

import os
import sys
import json
import threading
from datetime import datetime, timezone, timedelta

# 프로젝트 루트의 common.py를 import하기 위한 경로 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common import DATA_DIR
from api.access_control import DAILY_LIMIT

KST = timezone(timedelta(hours=9))
USAGE_LOG_FILE = os.path.join(DATA_DIR, "usage_log.json")

_lock = threading.Lock()


def _today_kst():
    return datetime.now(KST).strftime("%Y-%m-%d")


def _load():
    if not os.path.exists(USAGE_LOG_FILE):
        return {}
    with open(USAGE_LOG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(data):
    with open(USAGE_LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_usage_count(user_id):
    with _lock:
        data = _load()
    entry = data.get(str(user_id))
    if not entry or entry.get("date") != _today_kst():
        return 0
    return entry.get("count", 0)


def check_and_increment(user_id):
    """오늘 사용 가능하면 카운트를 올리고 True, 한도(DAILY_LIMIT) 초과면 False."""
    today = _today_kst()
    with _lock:
        data = _load()
        entry = data.get(str(user_id))
        if not entry or entry.get("date") != today:
            entry = {"date": today, "count": 0}
        if entry["count"] >= DAILY_LIMIT:
            return False
        entry["count"] += 1
        data[str(user_id)] = entry
        _save(data)
    return True
