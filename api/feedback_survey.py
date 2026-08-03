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
