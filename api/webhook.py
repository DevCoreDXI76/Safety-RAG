"""텔레그램 웹훅 수신 — /start 가입 신청 처리, 승인/거절 인라인 버튼 콜백 처리"""

import os
from fastapi import APIRouter, Request, Header, HTTPException

from api.access_control import (
    ADMIN_TELEGRAM_USER_ID,
    is_allowed,
    is_pending,
    add_pending_request,
    add_allowed_user,
    remove_pending_request,
    get_pending_request,
)
from api.telegram_bot import (
    send_message,
    edit_message_text,
    answer_callback_query,
    approve_reject_keyboard,
)
from api.admin_stats import build_stats_message

TELEGRAM_WEBHOOK_SECRET = os.getenv("TELEGRAM_WEBHOOK_SECRET")

webhook_router = APIRouter()


@webhook_router.post("/telegram/webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str = Header(default=None),
):
    if x_telegram_bot_api_secret_token != TELEGRAM_WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="invalid secret token")

    update = await request.json()

    if "message" in update:
        _handle_message(update["message"])
    elif "callback_query" in update:
        _handle_callback_query(update["callback_query"])

    return {"ok": True}


def _handle_message(message):
    text = message.get("text", "")
    chat_id = message["chat"]["id"]
    user = message["from"]
    user_id = user["id"]

    if text == "/stats":
        if user_id != ADMIN_TELEGRAM_USER_ID:
            return  # 관리자 외에는 조용히 무시 (명령어 존재 자체를 노출하지 않음)
        send_message(chat_id, build_stats_message())
        return

    if text != "/start":
        return

    if is_allowed(user_id):
        send_message(chat_id, "이미 사용 승인이 완료되었습니다. 메뉴 버튼으로 미니앱을 여세요.")
        return

    if is_pending(user_id):
        send_message(chat_id, "사용 신청이 이미 접수되어 승인 대기 중입니다.")
        return

    add_pending_request(user_id, username=user.get("username"), first_name=user.get("first_name"))
    send_message(chat_id, "사용 신청이 접수되었습니다. 관리자 승인 후 이용 가능합니다.")

    if ADMIN_TELEGRAM_USER_ID:
        name = user.get("username") or user.get("first_name") or str(user_id)
        send_message(
            ADMIN_TELEGRAM_USER_ID,
            f"📩 새 사용 신청: {name} (id: {user_id})",
            reply_markup=approve_reject_keyboard(user_id),
        )


def _handle_callback_query(callback_query):
    clicker_id = callback_query["from"]["id"]
    callback_id = callback_query["id"]

    if clicker_id != ADMIN_TELEGRAM_USER_ID:
        answer_callback_query(callback_id, "관리자만 사용할 수 있습니다.")
        return

    action, _, user_id_str = callback_query["data"].partition(":")
    user_id = int(user_id_str)
    message = callback_query["message"]

    if action == "approve":
        pending = get_pending_request(user_id)
        username = pending.get("username") if pending else None
        add_allowed_user(user_id, username=username)
        remove_pending_request(user_id)
        edit_message_text(message["chat"]["id"], message["message_id"], f"✅ 승인 완료 (id: {user_id})")
        send_message(user_id, "✅ 승인되었습니다! 메뉴 버튼으로 미니앱을 사용하실 수 있습니다.")
        answer_callback_query(callback_id, "승인했습니다.")
    elif action == "reject":
        remove_pending_request(user_id)
        edit_message_text(message["chat"]["id"], message["message_id"], f"❌ 거절 완료 (id: {user_id})")
        send_message(user_id, "❌ 사용 신청이 거절되었습니다.")
        answer_callback_query(callback_id, "거절했습니다.")
