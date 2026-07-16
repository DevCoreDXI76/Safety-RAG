"""텔레그램 Mini App initData 검증 + 승인 여부 확인

검증 알고리즘은 텔레그램 공식 사양(Validating data received via the Mini App)을 따른다:
1. initData 쿼리 문자열을 파싱하고 hash 필드를 분리
2. 나머지 필드를 key=value로 정렬해 \\n으로 join한 data_check_string 생성
3. secret_key = HMAC_SHA256(key="WebAppData", msg=봇토큰)
4. computed_hash = HMAC_SHA256(key=secret_key, msg=data_check_string)
5. computed_hash와 수신한 hash를 비교
"""

import os
import sys
import hmac
import hashlib
import json
import threading
from datetime import datetime
from urllib.parse import parse_qsl

from fastapi import Header, HTTPException
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common import DATA_DIR, KST
from api.access_control import is_allowed, register_pending_request

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# 401(서명 검증 실패)/403(미승인) 발생 시 기록 — Railway 서버 로그에 직접
# 접근하지 않고도 "누가·왜 거부됐는지"를 관리자가 /authlog로 바로 조회하기
# 위한 용도. token_usage_log.jsonl과 동일한 append-only 방식.
AUTH_FAILURE_LOG_PATH = os.path.join(DATA_DIR, "auth_failures.jsonl")
_auth_failure_lock = threading.Lock()


def _log_auth_failure(reason, user_id=None, username=None):
    entry = {
        "timestamp": datetime.now(KST).isoformat(),
        "reason": reason,
        "user_id": user_id,
        "username": username,
    }
    with _auth_failure_lock:
        with open(AUTH_FAILURE_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def verify_init_data(init_data: str) -> dict:
    """initData 문자열의 HMAC 서명을 검증하고, 통과하면 파싱된 필드 dict를 반환한다."""
    parsed = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = parsed.pop("hash", None)
    if not received_hash:
        raise ValueError("hash 필드가 없습니다.")

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
    secret_key = hmac.new(b"WebAppData", TELEGRAM_BOT_TOKEN.encode(), hashlib.sha256).digest()
    computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(computed_hash, received_hash):
        raise ValueError("initData 서명이 유효하지 않습니다.")

    return parsed


def require_telegram_auth(x_telegram_init_data: str = Header(...)) -> dict:
    """FastAPI Depends용: initData 검증 후 승인된 사용자만 통과시킨다."""
    try:
        parsed = verify_init_data(x_telegram_init_data)
        user = json.loads(parsed["user"])
    except Exception:
        # 서명 검증 전 단계라 user_id를 신뢰할 수 없다 — 그래도 진단 목적으로
        # 원본 initData에서 claimed user_id를 시도해보되, 검증되지 않은 값임을
        # 로그에 명시한다.
        claimed_user_id = None
        try:
            raw = dict(parse_qsl(x_telegram_init_data, keep_blank_values=True))
            claimed_user_id = json.loads(raw.get("user", "{}")).get("id")
        except Exception:
            pass
        _log_auth_failure("invalid_signature", user_id=f"unverified:{claimed_user_id}")
        raise HTTPException(status_code=401, detail="텔레그램 인증에 실패했습니다.")

    user_id = user["id"]
    if not is_allowed(user_id):
        # "/start"를 몰라도 미니앱을 여는 순간 자동으로 대기 등록 + 관리자
        # 알림이 나가도록 한다(2026-07 개선 — 이전엔 /start 텍스트를 직접
        # 보내야만 등록됐음). 이미 대기 중이면 register_pending_request가
        # 알아서 아무 것도 안 하므로 중복 알림 걱정은 없다.
        newly_registered = register_pending_request(
            user_id, username=user.get("username"), first_name=user.get("first_name")
        )
        _log_auth_failure("not_allowed", user_id=user_id, username=user.get("username"))
        detail = (
            "사용 신청이 접수되었습니다. 관리자 승인 후 다시 시도해주세요."
            if newly_registered
            else "사용 승인 대기 중입니다. 관리자 승인 후 다시 시도해주세요."
        )
        raise HTTPException(status_code=403, detail=detail)

    return {"user_id": user_id, "username": user.get("username"), "first_name": user.get("first_name")}
