"""일일 API 비용 합산 및 임계치 초과 시 텔레그램 알림 (전체 사용자 합산 기준)"""

import os
import sys
import json
from datetime import datetime

# 프로젝트 루트의 common.py를 import하기 위한 경로 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common import DATA_DIR, TOKEN_USAGE_LOG_PATH, KST
from api.telegram_bot import send_message
from api.access_control import ADMIN_TELEGRAM_USER_ID
from generate_draft import MODEL_BY_DOCUMENT_TYPE, DEFAULT_MODEL

# Sonnet 5 도입가(~2026-08-31 기준), 100만 토큰당 USD. 표준가($3/$15) 전환
# 시 갱신 필요.
SONNET5_INPUT_PRICE_PER_MTOK = 2.0
SONNET5_OUTPUT_PRICE_PER_MTOK = 10.0

# Haiku 4.5 단가(변동 계획 없음), 100만 토큰당 USD. generate_draft.py의
# MODEL_BY_DOCUMENT_TYPE에서 Haiku로 라우팅된 문서유형(현재 안전보건교육일지)에
# 적용한다 — 2026-08-07 실측원가 집계 중, 이 구분 없이 전 항목에 Sonnet
# 단가를 적용해 Haiku 항목의 원가를 과대 계상하고 있던 버그를 발견해 수정.
HAIKU_INPUT_PRICE_PER_MTOK = 1.0
HAIKU_OUTPUT_PRICE_PER_MTOK = 5.0

CACHE_WRITE_MULTIPLIER = 2.0  # 1시간 TTL 기준
CACHE_READ_MULTIPLIER = 0.1

# 1단계: 사용자 구분 없는 전체 합산 임계치. 구독 서비스 전환 시 사용자별
# 임계치가 별도로 필요해질 수 있음 — 이건 후속 과제로 남겨둠(개발자
# 체크리스트 C절, 요금제/레이트리밋 로직과 함께 설계할 것).
DAILY_COST_ALERT_THRESHOLD_USD = float(os.getenv("DAILY_COST_ALERT_THRESHOLD_USD", "5.0"))

COST_ALERT_STATE_PATH = os.path.join(DATA_DIR, "cost_alert_state.json")


def _today_kst():
    return datetime.now(KST).strftime("%Y-%m-%d")


def _entry_cost_usd(entry):
    """entry["document_type"]가 MODEL_BY_DOCUMENT_TYPE에서 Haiku로 매핑돼
    있으면 Haiku 단가로, 그 외(매핑 없음 · document_type 키 자체가 없는
    구버전 로그 포함)에는 DEFAULT_MODEL(Sonnet 5) 단가로 계산한다 —
    generate_draft.py의 실제 배포 라우팅과 항상 일치시키기 위해 상수를
    복제하지 않고 그 모듈에서 직접 가져와 참조한다."""
    model = MODEL_BY_DOCUMENT_TYPE.get(entry.get("document_type"), DEFAULT_MODEL)
    if model.startswith("claude-haiku"):
        input_price = HAIKU_INPUT_PRICE_PER_MTOK
        output_price = HAIKU_OUTPUT_PRICE_PER_MTOK
    else:
        input_price = SONNET5_INPUT_PRICE_PER_MTOK
        output_price = SONNET5_OUTPUT_PRICE_PER_MTOK

    input_cost = entry["input_tokens"] / 1_000_000 * input_price
    output_cost = entry["output_tokens"] / 1_000_000 * output_price
    cache_write_cost = (
        entry["cache_creation_input_tokens"] / 1_000_000
        * input_price * CACHE_WRITE_MULTIPLIER
    )
    cache_read_cost = (
        entry["cache_read_input_tokens"] / 1_000_000
        * input_price * CACHE_READ_MULTIPLIER
    )
    return input_cost + output_cost + cache_write_cost + cache_read_cost


def get_daily_cost_usd(date_str=None):
    """date_str(KST, "YYYY-MM-DD") 기준 전체 사용자 합산 비용(USD). 기본값은 오늘."""
    date_str = date_str or _today_kst()
    if not os.path.exists(TOKEN_USAGE_LOG_PATH):
        return 0.0
    total = 0.0
    with open(TOKEN_USAGE_LOG_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            entry = json.loads(line)
            if entry["timestamp"].startswith(date_str):
                total += _entry_cost_usd(entry)
    return total


def _already_alerted_today():
    if not os.path.exists(COST_ALERT_STATE_PATH):
        return False
    with open(COST_ALERT_STATE_PATH, "r", encoding="utf-8") as f:
        state = json.load(f)
    return state.get("date") == _today_kst()


def _mark_alerted_today():
    with open(COST_ALERT_STATE_PATH, "w", encoding="utf-8") as f:
        json.dump({"date": _today_kst()}, f)


def check_and_alert_daily_cost():
    """
    오늘(KST) 누적 비용이 임계치를 넘었고 아직 오늘 알림을 안 보냈으면
    관리자에게 텔레그램 메시지를 보낸다. 하루 1회만 발송.
    """
    if _already_alerted_today():
        return
    total = get_daily_cost_usd()
    if total >= DAILY_COST_ALERT_THRESHOLD_USD:
        send_message(
            ADMIN_TELEGRAM_USER_ID,
            f"⚠️ 오늘(KST) API 비용이 임계치(${DAILY_COST_ALERT_THRESHOLD_USD:.2f})를 "
            f"넘었습니다. 누적: ${total:.2f}",
        )
        _mark_alerted_today()
