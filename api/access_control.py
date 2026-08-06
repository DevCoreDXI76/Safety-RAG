"""파일 기반 사용자 승인 관리 — allowed_users.json(승인 목록) / pending_requests.json(대기 목록)"""

import os
import sys
import json
import logging
import threading
from datetime import datetime

# 프로젝트 루트의 common.py를 import하기 위한 경로 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common import DATA_DIR, KST
from api.telegram_bot import send_message, approve_reject_keyboard

logger = logging.getLogger("access_control")

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


def add_allowed_user(user_id, username=None, first_name=None, display_name=None):
    with _lock:
        data = _load(ALLOWED_USERS_FILE)
        data[str(user_id)] = {
            "username": username,
            "first_name": first_name,
            "display_name": display_name,
            "name_asked_at": None,
        }
        _save(ALLOWED_USERS_FILE, data)


def backfill_first_name(user_id, first_name):
    """구버전(2키 스키마) 때 승인된 사용자는 allowed_users.json에 first_name이
    없다. Telegram이 이번 호출에서 first_name을 새로 알려줬고, 저장된 레코드에
    아직 first_name이 없을 때만 채워 넣는다. username은 건드리지 않는다.
    저장된 레코드가 없거나(비정상 상태) 이미 first_name이 있거나, 이번에
    들어온 값이 비어있으면 아무 것도 하지 않는다."""
    if not first_name:
        return
    with _lock:
        data = _load(ALLOWED_USERS_FILE)
        record = data.get(str(user_id))
        if record is None or record.get("first_name"):
            return
        record["first_name"] = first_name
        _save(ALLOWED_USERS_FILE, data)


def resolve_display_name(user_id):
    """피드백 로그 등에서 쓸 표시 이름. display_name > username > first_name >
    user_id 문자열 순. display_name은 사용자가 채팅으로 직접 답장해 입력한
    이름(2026-08 추가)."""
    with _lock:
        data = _load(ALLOWED_USERS_FILE)
    record = data.get(str(user_id), {})
    return (
        record.get("display_name")
        or record.get("username")
        or record.get("first_name")
        or str(user_id)
    )


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
        data[str(user_id)] = {
            "username": username,
            "first_name": first_name,
            "display_name": None,
            "name_requested_at": datetime.now(KST).isoformat(),
            "admin_notified": False,
        }
        _save(PENDING_REQUESTS_FILE, data)


def register_pending_request(user_id, username=None, first_name=None):
    """
    대기 등록 + 이름 요청 메시지를 보내는 공용 진입점. "/start" 텍스트
    메시지(webhook.py)와 미니앱 첫 API 호출(telegram_auth.py) 양쪽에서
    동일하게 호출한다. 이미 승인됐거나 이미 대기 중이면 아무 것도 하지
    않고 False를 반환한다.

    관리자 알림은 여기서 보내지 않는다(2026-08 변경) — 이름 답장이
    도착했을 때 record_name_reply()가, 또는 타임아웃이 지나면
    sweep_stale_name_requests()가 보낸다.
    """
    if is_allowed(user_id) or is_pending(user_id):
        return False

    add_pending_request(user_id, username=username, first_name=first_name)
    send_message(
        user_id,
        "사용 신청이 접수되었습니다 🙌\n"
        "승인에 참고할 수 있도록 성함을 답장으로 알려주세요. (예: 홍길동)",
    )
    return True


def remove_pending_request(user_id):
    with _lock:
        data = _load(PENDING_REQUESTS_FILE)
        data.pop(str(user_id), None)
        _save(PENDING_REQUESTS_FILE, data)


_INVALID_NAME_CHARS = (",", "，", "?", "？", ".", "。")


def is_valid_name_reply(text):
    """이름 답장으로 받아들일 수 있는 텍스트인지 검사한다. 20자 이내,
    "/"로 시작하지 않고, 쉼표·물음표·마침표를 포함하지 않으면 True.
    문장형 답장(예: 이름 요청과 피드백 자유의견 대기가 겹쳐 들어온 경우)을
    이름으로 잘못 저장하지 않기 위한 최소 방어."""
    text = (text or "").strip()
    if not text or len(text) > 20:
        return False
    if text.startswith("/"):
        return False
    if any(ch in text for ch in _INVALID_NAME_CHARS):
        return False
    return True


def is_awaiting_name(user_id):
    """이 user_id가 지금 "이름 답장 대기" 상태인지 — 신규 신청(pending에
    있고 display_name 미입력) 또는 기존 승인자 소급 요청(allowed에 있고
    display_name 미입력 + name_asked_at 있음) 둘 중 하나면 True."""
    pending = get_pending_request(user_id)
    if pending is not None and not pending.get("display_name"):
        return True

    with _lock:
        allowed_data = _load(ALLOWED_USERS_FILE)
    record = allowed_data.get(str(user_id))
    if record and not record.get("display_name") and record.get("name_asked_at"):
        return True

    return False


def record_name_reply(user_id, text):
    """is_awaiting_name(user_id)가 True일 때 호출한다고 가정하고 text를
    이름으로 저장한다. pending(신규 신청) 쪽이면 관리자에게 아직 알림을
    보낸 적이 없을 때만 "새 사용 신청" 알림을 이름과 함께 보낸다(최초 1회).
    allowed(기존 승인자 소급) 쪽이면 이름만 저장하고 알림은 없다."""
    pending = get_pending_request(user_id)
    if pending is not None and not pending.get("display_name"):
        should_notify_admin = False
        with _lock:
            data = _load(PENDING_REQUESTS_FILE)
            record = data.get(str(user_id))
            if record is None:
                return
            record["display_name"] = text
            should_notify_admin = not record.get("admin_notified", False)
            record["admin_notified"] = True
            _save(PENDING_REQUESTS_FILE, data)
        if should_notify_admin and ADMIN_TELEGRAM_USER_ID:
            telegram_label = pending.get("username") or pending.get("first_name") or str(user_id)
            send_message(
                ADMIN_TELEGRAM_USER_ID,
                f"📩 새 사용 신청: {text} (텔레그램: {telegram_label}, id: {user_id})",
                reply_markup=approve_reject_keyboard(user_id),
            )
        return

    with _lock:
        data = _load(ALLOWED_USERS_FILE)
        record = data.get(str(user_id))
        if record is None:
            return
        record["display_name"] = text
        _save(ALLOWED_USERS_FILE, data)


def sweep_stale_name_requests(timeout_minutes=30):
    """pending_requests.json을 훑어 admin_notified가 False이고
    name_requested_at으로부터 timeout_minutes 이상 지난 항목을 찾아
    "(이름 미입력)"으로 관리자 알림을 보내고 admin_notified=True로 표시한다.
    별도 스케줄러 없이 웹훅 이벤트가 들어올 때마다 가볍게 호출된다 —
    pending 목록이 비어 있으면 즉시 반환하므로 비용은 무시할 수준이다.
    실패해도 예외를 삼켜 웹훅 처리 자체를 막지 않는다."""
    try:
        now = datetime.now(KST)
        to_notify = []
        with _lock:
            data = _load(PENDING_REQUESTS_FILE)
            changed = False
            for uid, record in data.items():
                if record.get("admin_notified"):
                    continue
                requested_at_raw = record.get("name_requested_at")
                if not requested_at_raw:
                    continue
                try:
                    requested_at = datetime.fromisoformat(requested_at_raw)
                    elapsed_minutes = (now - requested_at).total_seconds() / 60
                except (TypeError, ValueError):
                    logger.warning(
                        "이름 미입력 타임아웃 폴백: name_requested_at 파싱 실패 — uid=%s value=%r (건너뜀)",
                        uid, requested_at_raw,
                    )
                    continue
                if elapsed_minutes >= timeout_minutes:
                    record["admin_notified"] = True
                    to_notify.append((uid, dict(record)))
                    changed = True
            if changed:
                _save(PENDING_REQUESTS_FILE, data)
        if not ADMIN_TELEGRAM_USER_ID:
            return
        for uid, record in to_notify:
            telegram_label = record.get("username") or record.get("first_name") or uid
            send_message(
                ADMIN_TELEGRAM_USER_ID,
                f"📩 새 사용 신청: (이름 미입력) (텔레그램: {telegram_label}, id: {uid})",
                reply_markup=approve_reject_keyboard(uid),
            )
    except Exception:
        logger.exception("이름 미입력 타임아웃 폴백 처리 실패")


def maybe_ask_backfill_name(user_id):
    """allowed_users.json에서 user_id를 조회해 display_name이 비어 있고
    아직 물어본 적도 없을 때(name_asked_at 없음)만 이름 요청 메시지를
    보내고 name_asked_at을 채운다. require_telegram_auth()의 모든 호출
    경로에서 실행되므로 예외를 삼키고 실패해도 API 응답에 영향을 주지
    않는다(error_alert.py와 동일 원칙)."""
    try:
        with _lock:
            data = _load(ALLOWED_USERS_FILE)
            record = data.get(str(user_id))
            if record is None or record.get("display_name") or record.get("name_asked_at"):
                return
            record["name_asked_at"] = datetime.now(KST).isoformat()
            _save(ALLOWED_USERS_FILE, data)
        send_message(
            user_id,
            "안녕하세요! 베타 테스트에 참여해주셔서 감사합니다 🙏\n"
            "피드백 정리를 위해 성함을 답장으로 알려주시겠어요? (예: 홍길동)",
        )
    except Exception:
        logger.exception("기존 승인자 이름 소급 요청 실패: user_id=%s", user_id)
