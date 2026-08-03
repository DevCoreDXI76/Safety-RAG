# -*- coding: utf-8 -*-
"""베타1 텔레그램 인앱 피드백 설문 — 문서 타입(위험성평가표/표준 작업계획서/
TBM 일지)별 최초 생성 시 1회, 비차단으로 짧은 질문을 던진다.

'/generate' 성공 직후(api/routes.py)와 api/webhook.py의 콜백·텍스트 핸들러가
이 모듈의 함수를 호출한다. 텔레그램·파일 I/O 실패가 문서 생성 흐름을
절대 깨뜨리면 안 되므로, 트리거·완료 처리 함수는 내부에서 예외를 삼킨다
(api/error_alert.py와 동일 원칙).

설계 배경: docs/superpowers/specs/2026-08-03-베타1-피드백-설문-design.md
"""
import json
import logging
import os
import sys
import threading
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common import DATA_DIR, KST
from api.telegram_bot import send_message, edit_message_text
from api.access_control import resolve_display_name, ADMIN_TELEGRAM_USER_ID

logger = logging.getLogger("feedback_survey")

FEEDBACK_STATE_FILE = os.path.join(DATA_DIR, "feedback_state.json")
FEEDBACK_LOG_FILE = os.path.join(DATA_DIR, "beta1_feedback.jsonl")

_lock = threading.Lock()

# 콜백 데이터(텔레그램 64바이트 제한)에 한글 문서유형을 그대로 못 담아 코드로 축약한다.
DOC_CODES = {"위험성평가표": "R", "표준 작업계획서": "P", "TBM 일지": "T"}
CODE_TO_DOC = {code: doc for doc, code in DOC_CODES.items()}

CHECKPOINTS = {
    "위험성평가표": {
        "questions": [
            {
                "key": "q1_quality",
                "text": "방금 만든 위험성평가표 초안, 어느 정도 쓸만했나요?",
                "options": ["바로 제출 가능", "조금만 수정하면 됨", "많이 고쳐야 함"],
            },
        ],
    },
    "표준 작업계획서": {
        "questions": [
            {
                "key": "q5_order_guide",
                "text": "위험성평가표 다음 작업계획서로 넘어가라는 안내, 도움이 되셨나요?",
                "options": ["도움됐음", "봤지만 헷갈렸음", "못 보고 만듦"],
            },
        ],
    },
    "TBM 일지": {
        "questions": [
            {
                "key": "q2_time_saved",
                "text": "이 도구를 안 썼을 때랑 비교하면 시간이 얼마나 줄었나요?",
                "options": ["많이 줄었음", "조금 줄었음", "비슷함", "오히려 늘었음"],
            },
            {
                "key": "q4_willingness_to_pay",
                "text": "매달 얼마면 계속 쓰실 의향이 있으세요?",
                "options": ["1만원 이하", "1~3만원", "3~5만원", "지불 의향 없음"],
            },
        ],
        "free_text_prompt": "더 해주고 싶은 말씀 있으시면 편하게 적어주세요.",
        "free_text_skip_label": "생략하고 완료",
    },
}


def _load_state():
    with _lock:
        if not os.path.exists(FEEDBACK_STATE_FILE):
            return {}
        with open(FEEDBACK_STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)


def _save_state(data):
    with _lock:
        with open(FEEDBACK_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


def _now_iso():
    return datetime.now(KST).isoformat()


def _build_keyboard(document_type, question_index, question):
    code = DOC_CODES[document_type]
    return {
        "inline_keyboard": [[
            {"text": opt, "callback_data": f"fb:{code}:{question_index}:{i}"}
            for i, opt in enumerate(question["options"])
        ]]
    }


def _skip_keyboard(document_type):
    code = DOC_CODES[document_type]
    label = CHECKPOINTS[document_type]["free_text_skip_label"]
    return {"inline_keyboard": [[{"text": label, "callback_data": f"fbskip:{code}"}]]}


def maybe_trigger_checkpoint(user_id, document_type):
    """document_type이 CHECKPOINTS에 없으면 아무 것도 안 한다.
    이미 이 user_id·document_type 조합이 상태 파일에 있으면(완료/진행중 무관)
    재발송하지 않는다. 실패해도 예외를 삼키고 로그만 남긴다."""
    if document_type not in CHECKPOINTS:
        return
    try:
        state = _load_state()
        if document_type in state.get(str(user_id), {}):
            return
        question = CHECKPOINTS[document_type]["questions"][0]
        send_message(user_id, question["text"], reply_markup=_build_keyboard(document_type, 0, question))
        state.setdefault(str(user_id), {})[document_type] = {
            "triggered_at": _now_iso(),
            "answers": {},
            "completed": False,
        }
        _save_state(state)
    except Exception:
        logger.exception(
            "피드백 체크포인트 트리거 실패: user_id=%s document_type=%s", user_id, document_type
        )


def _mark_completed(checkpoint_state):
    checkpoint_state["completed"] = True
    checkpoint_state["completed_at"] = _now_iso()
    checkpoint_state.pop("awaiting_free_text", None)


def _append_log(user_id, document_type, answers, free_text):
    entry = {
        "user_id": user_id,
        "display_name": resolve_display_name(user_id),
        "document_type": document_type,
        "answers": answers,
        "free_text": free_text,
        "completed_at": _now_iso(),
    }
    with open(FEEDBACK_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _notify_admin(user_id, document_type, answers, free_text):
    if not ADMIN_TELEGRAM_USER_ID:
        return
    try:
        name = resolve_display_name(user_id)
        lines = [f"📝 피드백 완료: {name} ({document_type})"]
        for key, value in answers.items():
            lines.append(f"- {key}: {value}")
        if free_text:
            lines.append(f"- 자유의견: {free_text}")
        send_message(ADMIN_TELEGRAM_USER_ID, "\n".join(lines))
    except Exception:
        logger.exception(
            "피드백 관리자 알림 발송 실패: user_id=%s document_type=%s", user_id, document_type
        )


def _complete_and_notify(user_id, document_type, checkpoint_state):
    _mark_completed(checkpoint_state)
    _append_log(user_id, document_type, checkpoint_state["answers"], checkpoint_state.get("free_text"))
    _notify_admin(user_id, document_type, checkpoint_state["answers"], checkpoint_state.get("free_text"))


def handle_callback_answer(user_id, chat_id, message_id, callback_data):
    """callback_data 형식: "fb:<doc_code>:<question_index>:<option_index>".
    이 형식이 아니면 아무 것도 하지 않고 False를 반환한다(호출자가 다른
    핸들러로 넘기게 하기 위함)."""
    if not callback_data.startswith("fb:"):
        return False
    try:
        _, code, q_index_str, opt_index_str = callback_data.split(":")
        document_type = CODE_TO_DOC[code]
        q_index = int(q_index_str)
        opt_index = int(opt_index_str)
        checkpoint = CHECKPOINTS[document_type]
        question = checkpoint["questions"][q_index]
        answer_text = question["options"][opt_index]

        state = _load_state()
        checkpoint_state = state.setdefault(str(user_id), {}).setdefault(
            document_type, {"triggered_at": _now_iso(), "answers": {}, "completed": False}
        )
        checkpoint_state["answers"][question["key"]] = answer_text

        questions = checkpoint["questions"]
        next_index = q_index + 1
        if next_index < len(questions):
            next_question = questions[next_index]
            reply_text = next_question["text"]
            reply_markup = _build_keyboard(document_type, next_index, next_question)
        elif "free_text_prompt" in checkpoint:
            checkpoint_state["awaiting_free_text"] = True
            reply_text = checkpoint["free_text_prompt"]
            reply_markup = _skip_keyboard(document_type)
        else:
            _complete_and_notify(user_id, document_type, checkpoint_state)
            reply_text = "답변 감사합니다!"
            reply_markup = None

        _save_state(state)
        edit_message_text(chat_id, message_id, reply_text, reply_markup=reply_markup)
    except Exception:
        logger.exception("피드백 콜백 처리 실패: user_id=%s data=%s", user_id, callback_data)
    return True


def handle_skip_callback(user_id, chat_id, message_id, callback_data):
    """callback_data 형식: "fbskip:<doc_code>". 이 형식이 아니면 False 반환."""
    if not callback_data.startswith("fbskip:"):
        return False
    try:
        _, code = callback_data.split(":")
        document_type = CODE_TO_DOC[code]
        state = _load_state()
        checkpoint_state = state.get(str(user_id), {}).get(document_type)
        if checkpoint_state and not checkpoint_state.get("completed"):
            _complete_and_notify(user_id, document_type, checkpoint_state)
            _save_state(state)
        edit_message_text(chat_id, message_id, "답변 감사합니다!")
    except Exception:
        logger.exception("피드백 스킵 처리 실패: user_id=%s data=%s", user_id, callback_data)
    return True
