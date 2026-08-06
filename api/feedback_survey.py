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


def _read_state_file():
    """잠금 없는 파일 I/O. 호출자가 이미 _lock을 쥐고 있거나(쓰기와 묶어야
    할 때), 잠금 없이 읽어도 되는 순수 조회 용도일 때 사용한다."""
    if not os.path.exists(FEEDBACK_STATE_FILE):
        return {}
    with open(FEEDBACK_STATE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_state_file(data):
    """잠금 없는 파일 I/O. 호출자가 이미 _lock을 쥐고 있어야 한다."""
    with open(FEEDBACK_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _load_state():
    """읽기 전용 호출자(예: broadcast_pending_reminders)를 위한 잠금 포함
    편의 래퍼. load→check→mutate→save를 한 번에 하는 함수는 이걸 쓰지 말고
    _read_state_file/_write_state_file을 직접 하나의 with _lock: 블록 안에서
    호출해 read-modify-write 전체 구간의 원자성을 보장해야 한다."""
    with _lock:
        return _read_state_file()


def _now_iso():
    return datetime.now(KST).isoformat()


def _build_keyboard(document_type, question_index, question):
    # 옵션마다 한 줄(버튼 1개)로 배치한다 — 한 줄에 다 몰아넣으면 모바일에서
    # 라벨이 잘릴 수 있고, 특히 지불 의향 질문(q4_willingness_to_pay)처럼
    # 비즈니스적으로 중요한 응답이 잘리면 안 되기 때문이다.
    code = DOC_CODES[document_type]
    return {
        "inline_keyboard": [
            [{"text": opt, "callback_data": f"fb:{code}:{question_index}:{i}"}]
            for i, opt in enumerate(question["options"])
        ]
    }


def _skip_keyboard(document_type):
    code = DOC_CODES[document_type]
    label = CHECKPOINTS[document_type]["free_text_skip_label"]
    return {"inline_keyboard": [[{"text": label, "callback_data": f"fbskip:{code}"}]]}


def maybe_trigger_checkpoint(user_id, document_type):
    """document_type이 CHECKPOINTS에 없으면 아무 것도 안 한다.
    이미 이 user_id·document_type 조합이 상태 파일에 있으면(완료/진행중 무관)
    재발송하지 않는다. 실패해도 예외를 삼키고 로그만 남긴다.

    읽기(트리거 여부 확인)부터 쓰기(상태 저장)까지 전체 구간을 _lock 하나로
    감싼다 — 그렇지 않으면 같은 user_id·document_type에 대한 동시 호출이
    둘 다 "아직 트리거 안 됨"을 보고 중복 발송할 수 있다."""
    if document_type not in CHECKPOINTS:
        return
    try:
        with _lock:
            state = _read_state_file()
            if document_type in state.get(str(user_id), {}):
                return
            question = CHECKPOINTS[document_type]["questions"][0]
            send_message(user_id, question["text"], reply_markup=_build_keyboard(document_type, 0, question))
            state.setdefault(str(user_id), {})[document_type] = {
                "triggered_at": _now_iso(),
                "answers": {},
                "completed": False,
            }
            _write_state_file(state)
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
    핸들러로 넘기게 하기 위함).

    읽기(완료 여부 확인)부터 쓰기(답변 저장)까지 전체 구간을 _lock 하나로
    감싼다 — 그렇지 않으면 같은 user_id의 거의 동시 콜백 두 건이 서로의
    답변을 덮어쓰거나(last-writer-wins), 완료 여부 확인이 서로 stale한
    상태를 볼 수 있다."""
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

        with _lock:
            state = _read_state_file()
            checkpoint_state = state.setdefault(str(user_id), {}).setdefault(
                document_type, {"triggered_at": _now_iso(), "answers": {}, "completed": False}
            )
            if checkpoint_state.get("completed"):
                # 이미 완료된 체크포인트에 대한 중복 콜백(웹훅 재전송, 더블탭 등).
                # 재처리하면 로그·관리자 알림이 중복되므로 조용히 무시한다.
                return True
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

            _write_state_file(state)
            edit_message_text(chat_id, message_id, reply_text, reply_markup=reply_markup)
    except Exception:
        logger.exception("피드백 콜백 처리 실패: user_id=%s data=%s", user_id, callback_data)
    return True


def handle_skip_callback(user_id, chat_id, message_id, callback_data):
    """callback_data 형식: "fbskip:<doc_code>". 이 형식이 아니면 False 반환.
    handle_callback_answer와 동일한 이유로 읽기~쓰기 전체를 _lock으로 감싼다."""
    if not callback_data.startswith("fbskip:"):
        return False
    try:
        _, code = callback_data.split(":")
        document_type = CODE_TO_DOC[code]
        with _lock:
            state = _read_state_file()
            checkpoint_state = state.get(str(user_id), {}).get(document_type)
            if checkpoint_state and not checkpoint_state.get("completed"):
                _complete_and_notify(user_id, document_type, checkpoint_state)
                _write_state_file(state)
            edit_message_text(chat_id, message_id, "답변 감사합니다!")
    except Exception:
        logger.exception("피드백 스킵 처리 실패: user_id=%s data=%s", user_id, callback_data)
    return True


def handle_free_text(user_id, chat_id, text):
    """이 user_id가 지금 어떤 체크포인트에서 자유의견을 기다리는 중이면
    처리하고 True를 반환한다. 아니면 아무 것도 하지 않고 False를 반환한다
    (호출자가 기존 텍스트 핸들링으로 넘기게 하기 위함).
    handle_callback_answer와 동일한 이유로 읽기~쓰기 전체를 _lock으로 감싼다."""
    try:
        with _lock:
            state = _read_state_file()
            user_state = state.get(str(user_id), {})
            for document_type, checkpoint_state in user_state.items():
                if checkpoint_state.get("awaiting_free_text"):
                    checkpoint_state["free_text"] = text
                    _complete_and_notify(user_id, document_type, checkpoint_state)
                    _write_state_file(state)
                    send_message(chat_id, "답변 감사합니다!")
                    return True
    except Exception:
        logger.exception("피드백 자유의견 처리 실패: user_id=%s", user_id)
        return True
    return False


def is_awaiting_free_text(user_id):
    """이 user_id가 지금 어떤 체크포인트에서든 자유의견을 기다리는 중인지
    순수 조회한다. 텍스트 우선순위 판단용(webhook.py) — 실패해도 예외를
    삼키고 False를 반환해 안전한 기본값(자유의견 대기 아님)으로 처리한다."""
    try:
        state = _load_state().get(str(user_id), {})
        return any(cp.get("awaiting_free_text") for cp in state.values())
    except Exception:
        logger.exception("자유의견 대기 조회 실패: user_id=%s", user_id)
        return False


def _resend_pending_question(user_id, document_type, checkpoint_state):
    if checkpoint_state.get("awaiting_free_text"):
        send_message(
            int(user_id), CHECKPOINTS[document_type]["free_text_prompt"],
            reply_markup=_skip_keyboard(document_type),
        )
        return
    answered_count = len(checkpoint_state.get("answers", {}))
    questions = CHECKPOINTS[document_type]["questions"]
    if answered_count >= len(questions):
        return  # 이미 다 답했는데 completed만 안 된 극히 드문 상태 — 안전하게 건너뜀
    question = questions[answered_count]
    send_message(
        int(user_id), question["text"],
        reply_markup=_build_keyboard(document_type, answered_count, question),
    )


def broadcast_pending_reminders():
    """트리거는 됐지만 completed가 아닌 모든 (user_id, document_type)에
    현재 대기 중인 질문(또는 자유의견 프롬프트)을 재발송한다. 관리자 전용
    명령(/broadcast_feedback)에서만 호출된다."""
    state = _load_state()
    for user_id_str, user_state in state.items():
        for document_type, checkpoint_state in user_state.items():
            if checkpoint_state.get("completed"):
                continue
            try:
                _resend_pending_question(user_id_str, document_type, checkpoint_state)
            except Exception:
                logger.exception(
                    "피드백 재발송 실패: user_id=%s document_type=%s", user_id_str, document_type
                )
