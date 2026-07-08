"""텔레그램 Mini App initData 검증 + 승인 여부 확인

검증 알고리즘은 텔레그램 공식 사양(Validating data received via the Mini App)을 따른다:
1. initData 쿼리 문자열을 파싱하고 hash 필드를 분리
2. 나머지 필드를 key=value로 정렬해 \\n으로 join한 data_check_string 생성
3. secret_key = HMAC_SHA256(key="WebAppData", msg=봇토큰)
4. computed_hash = HMAC_SHA256(key=secret_key, msg=data_check_string)
5. computed_hash와 수신한 hash를 비교
"""

import os
import hmac
import hashlib
import json
from urllib.parse import parse_qsl

from fastapi import Header, HTTPException
from dotenv import load_dotenv

from api.access_control import is_allowed

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")


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
        raise HTTPException(status_code=401, detail="텔레그램 인증에 실패했습니다.")

    user_id = user["id"]
    if not is_allowed(user_id):
        raise HTTPException(
            status_code=403,
            detail="사용 승인이 필요합니다. 봇에게 /start를 먼저 보내세요.",
        )

    return {"user_id": user_id, "username": user.get("username"), "first_name": user.get("first_name")}
