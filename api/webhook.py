"""텔레그램 웹훅 수신 — /start 가입 신청 처리, 승인/거절 인라인 버튼 콜백 처리"""

import os
from fastapi import APIRouter, Request, Header, HTTPException

from api.access_control import (
    ADMIN_TELEGRAM_USER_ID,
    is_allowed,
    is_pending,
    is_awaiting_name,
    is_valid_name_reply,
    record_name_reply,
    sweep_stale_name_requests,
    register_pending_request,
    add_allowed_user,
    remove_pending_request,
    get_pending_request,
    remove_allowed_user,
)
from api.telegram_bot import (
    send_message,
    edit_message_text,
    answer_callback_query,
)
from api.admin_stats import build_stats_message, build_authlog_message
from api import feedback_survey

TELEGRAM_WEBHOOK_SECRET = os.getenv("TELEGRAM_WEBHOOK_SECRET")

webhook_router = APIRouter()


@webhook_router.post("/telegram/webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str = Header(default=None),
):
    if x_telegram_bot_api_secret_token != TELEGRAM_WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="invalid secret token")

    # 별도 스케줄러 없이, 웹훅 이벤트가 들어올 때마다 이름 미입력 타임아웃을
    # 가볍게 확인한다 — pending 목록이 비어 있으면 즉시 반환한다.
    sweep_stale_name_requests()

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

    if is_awaiting_name(user_id) and user_id != ADMIN_TELEGRAM_USER_ID and not feedback_survey.is_awaiting_free_text(user_id):
        stripped = text.strip() if text else ""
        if is_valid_name_reply(stripped):
            record_name_reply(user_id, stripped)
            send_message(chat_id, f"감사합니다, {stripped}님으로 등록했습니다 🙌")
        else:
            send_message(chat_id, "이름만 간단히 입력해주세요 (예: 홍길동)")
        return

    if text == "/stats":
        if user_id != ADMIN_TELEGRAM_USER_ID:
            return  # 관리자 외에는 조용히 무시 (명령어 존재 자체를 노출하지 않음)
        send_message(chat_id, build_stats_message())
        return

    if text == "/authlog":
        if user_id != ADMIN_TELEGRAM_USER_ID:
            return
        send_message(chat_id, build_authlog_message())
        return

    if text.startswith("/revoke"):
        if user_id != ADMIN_TELEGRAM_USER_ID:
            return
        _handle_revoke_command(chat_id, text)
        return

    if text == "/broadcast_feedback":
        if user_id != ADMIN_TELEGRAM_USER_ID:
            return
        feedback_survey.broadcast_pending_reminders()
        send_message(chat_id, "미응답 테스터에게 피드백 질문을 재발송했습니다.")
        return

    if text != "/start":
        if text and feedback_survey.handle_free_text(user_id, chat_id, text):
            return
        return

    if is_allowed(user_id):
        send_message(chat_id, "이미 사용 승인이 완료되었습니다. 메뉴 버튼으로 미니앱을 여세요.")
        return

    if is_pending(user_id):
        send_message(chat_id, "사용 신청이 이미 접수되어 승인 대기 중입니다.")
        return

    register_pending_request(user_id, username=user.get("username"), first_name=user.get("first_name"))


def _handle_revoke_command(chat_id, text):
    """"/revoke <user_id>" — 승인 취소. 대상 user_id는 /stats 조회 결과에서 확인 가능."""
    parts = text.split()
    if len(parts) != 2 or not parts[1].isdigit():
        send_message(chat_id, "사용법: /revoke <user_id>\n(user_id는 /stats로 확인)")
        return

    user_id = int(parts[1])
    if remove_allowed_user(user_id):
        send_message(chat_id, f"✅ 승인 취소 완료 (id: {user_id})")
        send_message(user_id, "이용 승인이 취소되었습니다. 다시 이용하시려면 /start로 재신청해주세요.")
    else:
        send_message(chat_id, f"승인 목록에 없는 id입니다: {user_id}")


def _handle_callback_query(callback_query):
    clicker_id = callback_query["from"]["id"]
    callback_id = callback_query["id"]
    data = callback_query["data"]
    message = callback_query["message"]

    if data.startswith("fb:"):
        feedback_survey.handle_callback_answer(clicker_id, message["chat"]["id"], message["message_id"], data)
        answer_callback_query(callback_id)
        return

    if data.startswith("fbskip:"):
        feedback_survey.handle_skip_callback(clicker_id, message["chat"]["id"], message["message_id"], data)
        answer_callback_query(callback_id)
        return

    if clicker_id != ADMIN_TELEGRAM_USER_ID:
        answer_callback_query(callback_id, "관리자만 사용할 수 있습니다.")
        return

    action, _, user_id_str = data.partition(":")
    user_id = int(user_id_str)

    if action == "approve":
        pending = get_pending_request(user_id)
        username = pending.get("username") if pending else None
        first_name = pending.get("first_name") if pending else None
        display_name = pending.get("display_name") if pending else None
        add_allowed_user(user_id, username=username, first_name=first_name, display_name=display_name)
        remove_pending_request(user_id)
        edit_message_text(message["chat"]["id"], message["message_id"], f"✅ 승인 완료 (id: {user_id})")
        send_message(user_id, "✅ 승인되었습니다! 메뉴 버튼으로 미니앱을 사용하실 수 있습니다.")
        answer_callback_query(callback_id, "승인했습니다.")
    elif action == "reject":
        remove_pending_request(user_id)
        edit_message_text(message["chat"]["id"], message["message_id"], f"❌ 거절 완료 (id: {user_id})")
        send_message(user_id, "❌ 사용 신청이 거절되었습니다.")
        answer_callback_query(callback_id, "거절했습니다.")
