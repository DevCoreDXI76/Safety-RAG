"""예외 발생 시 관리자에게 텔레그램으로 알림.

Sentry 등 전용 에러 모니터링 SaaS는 도입하지 않기로 결정(개발자 체크리스트
E-19, 2026-07-28) — 계정 가입·SDK 설치·무료티어 한도 관리가 필요하고 외부
서비스 의존이 하나 늘어나는 데 비해, 베타 단계 트래픽 규모에선 기존
텔레그램 봇 인프라(cost_alert.py와 동일 패턴)를 재사용하는 쪽이 비용 0원에
더 간단하다.
"""

import json
import logging
import os
import traceback
from datetime import datetime

from common import DATA_DIR, KST
from api.telegram_bot import send_message
from api.access_control import ADMIN_TELEGRAM_USER_ID

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("error_alert")

ERROR_ALERT_STATE_PATH = os.path.join(DATA_DIR, "error_alert_state.json")
# 같은 오류가 연달아 발생해도 관리자 텔레그램이 도배되지 않도록 최소 간격을 둔다.
# 쿨다운 중에도 로그(stdout, Railway 로그 뷰어)에는 매번 트레이스백까지 남는다.
ALERT_COOLDOWN_SECONDS = int(os.getenv("ERROR_ALERT_COOLDOWN_SECONDS", "600"))


def _last_alert_at():
    if not os.path.exists(ERROR_ALERT_STATE_PATH):
        return None
    with open(ERROR_ALERT_STATE_PATH, "r", encoding="utf-8") as f:
        state = json.load(f)
    ts = state.get("last_alert_at")
    return datetime.fromisoformat(ts) if ts else None


def _mark_alerted_now():
    with open(ERROR_ALERT_STATE_PATH, "w", encoding="utf-8") as f:
        json.dump({"last_alert_at": datetime.now(KST).isoformat()}, f)


def report_error(context, exc):
    """예외를 로그에 기록하고, 쿨다운이 지났으면 관리자에게 텔레그램 알림도 보낸다."""
    logger.error("[%s] %s\n%s", context, exc, traceback.format_exc())

    if not ADMIN_TELEGRAM_USER_ID:
        return

    now = datetime.now(KST)
    last = _last_alert_at()
    if last is not None and (now - last).total_seconds() < ALERT_COOLDOWN_SECONDS:
        return

    # 알림 발송 자체가 실패해도(텔레그램 네트워크 오류 등) 원래 예외 처리 흐름을
    # 절대 깨뜨리면 안 된다 — 여기서 발생하는 예외는 로그만 남기고 삼킨다.
    try:
        send_message(
            ADMIN_TELEGRAM_USER_ID,
            f"🚨 서버 오류 발생 [{context}]\n{type(exc).__name__}: {exc}\n"
            f"(동일 알림은 {ALERT_COOLDOWN_SECONDS // 60}분에 한 번만 발송됩니다 — 전체 내역은 Railway 로그 참고)",
        )
        _mark_alerted_now()
    except Exception:
        logger.error("텔레그램 오류 알림 발송 자체가 실패함:\n%s", traceback.format_exc())
