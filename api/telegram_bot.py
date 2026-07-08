"""텔레그램 Bot API 호출 헬퍼 (송신 전용) — /start 안내, 승인 요청/결과 알림, 웹훅 등록에 사용"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_WEBHOOK_SECRET = os.getenv("TELEGRAM_WEBHOOK_SECRET")
PUBLIC_APP_URL = os.getenv("PUBLIC_APP_URL")

API_BASE = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"


def send_message(chat_id, text, reply_markup=None):
    payload = {"chat_id": chat_id, "text": text}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    resp = requests.post(f"{API_BASE}/sendMessage", json=payload, timeout=10)
    return resp.json()


def edit_message_text(chat_id, message_id, text, reply_markup=None):
    payload = {"chat_id": chat_id, "message_id": message_id, "text": text}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    resp = requests.post(f"{API_BASE}/editMessageText", json=payload, timeout=10)
    return resp.json()


def answer_callback_query(callback_query_id, text=None):
    payload = {"callback_query_id": callback_query_id}
    if text:
        payload["text"] = text
    resp = requests.post(f"{API_BASE}/answerCallbackQuery", json=payload, timeout=10)
    return resp.json()


def approve_reject_keyboard(user_id):
    """관리자에게 보내는 승인/거절 인라인 키보드. callback_data에 대상 user_id를 담는다."""
    return {
        "inline_keyboard": [[
            {"text": "✅ 승인", "callback_data": f"approve:{user_id}"},
            {"text": "❌ 거절", "callback_data": f"reject:{user_id}"},
        ]]
    }


def set_webhook():
    """서버 기동 시 호출 — 텔레그램에 웹훅 URL과 검증용 secret_token을 등록한다."""
    if not PUBLIC_APP_URL:
        print("[telegram_bot] PUBLIC_APP_URL이 설정되지 않아 웹훅 등록을 건너뜁니다.")
        return None
    url = f"{PUBLIC_APP_URL}/telegram/webhook"
    payload = {"url": url, "secret_token": TELEGRAM_WEBHOOK_SECRET}
    resp = requests.post(f"{API_BASE}/setWebhook", json=payload, timeout=10)
    result = resp.json()
    print(f"[telegram_bot] set_webhook 결과: {result}")
    return result
