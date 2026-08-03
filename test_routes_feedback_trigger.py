# -*- coding: utf-8 -*-
"""'/generate' 성공(SSE 'done' 이벤트) 직후 feedback_survey.maybe_trigger_checkpoint가
올바른 인자로 호출되는지, 텔레그램 발송이 실패해도 스트림 자체(done 이벤트)는
깨지지 않는지 검증한다. 실제 Claude API를 호출하지 않도록
generate_document_draft_stream을 가짜로 바꿔치기한다.

주의: `/generate`는 `api/rate_limit.py`의 1일 5회 제한(`DAILY_LIMIT`)을 거친다.
같은 user_id로 반복 실행하면 재실행 시 429로 실패할 수 있으므로, 실행마다
고유한 user_id를 만들어 쓴다(`uuid4`).

사용 예:
  python test_routes_feedback_trigger.py
"""
import json
import os
import sys
import tempfile
import uuid

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from fastapi.testclient import TestClient

import api.routes as routes
import api.feedback_survey as feedback_survey
from api.main import app
from api.telegram_auth import require_telegram_auth

# 실제 텔레그램 user_id는 항상 숫자다(api/telegram_auth.py의 user["id"]).
# api/rate_limit.py:check_and_increment가 int(user_id)로 변환하므로 문자열 ID를
# 쓰면 무관한 사유(ValueError)로 500이 나 이 테스트의 의도(피드백 트리거 검증)를
# 가린다 — 그래서 브리프의 접두어 문자열 대신 숫자 문자열을 쓴다.
TEST_USER_ID = str(uuid.uuid4().int % 900000000 + 100000000)

REQUEST_BODY = {
    "document_type": "위험성평가표",
    "project_info": "테스트용 project_info",
    "project_name": None,
    "risk_assessment_id": None,
    "work_type": None,
}


def _fake_stream(**kwargs):
    yield {"type": "delta", "text": "안녕"}
    yield {"type": "done", "saved_record_id": "fake-record-1", "linked_risk_assessment_id": None}


def _parse_sse(body_text):
    events = []
    for line in body_text.splitlines():
        if line.startswith("data: "):
            events.append(json.loads(line[len("data: "):]))
    return events


def run():
    checks = []
    app.dependency_overrides[require_telegram_auth] = lambda: {
        "user_id": TEST_USER_ID, "username": None, "first_name": None,
    }
    client = TestClient(app, raise_server_exceptions=False)

    original_stream_fn = routes.generate_document_draft_stream
    original_send_message = feedback_survey.send_message
    original_state_file = feedback_survey.FEEDBACK_STATE_FILE

    with tempfile.TemporaryDirectory() as tmp_dir:
        try:
            routes.generate_document_draft_stream = lambda **kwargs: _fake_stream(**kwargs)

            # 1) 정상 케이스: 실제 maybe_trigger_checkpoint가 호출되어 텔레그램 발송 + 상태 기록
            feedback_survey.FEEDBACK_STATE_FILE = os.path.join(tmp_dir, "state1.json")
            sent = []
            feedback_survey.send_message = lambda *a, **k: sent.append((a, k))

            r = client.post("/generate", json=REQUEST_BODY)
            events = _parse_sse(r.text)
            checks.append(("응답 200", r.status_code == 200))
            checks.append(("done 이벤트 정상 전달", any(e.get("type") == "done" for e in events)))
            checks.append(("체크포인트 트리거로 텔레그램 발송 1회", len(sent) == 1))

            state = feedback_survey._load_state()
            checks.append(("상태 파일에 기록됨", "위험성평가표" in state.get(TEST_USER_ID, {})))

            # 2) 텔레그램 발송이 실패해도 done 이벤트는 정상 전달(다른 user로 재트리거)
            feedback_survey.FEEDBACK_STATE_FILE = os.path.join(tmp_dir, "state2.json")

            def failing_send(*a, **k):
                raise RuntimeError("텔레그램 전송 실패 시뮬레이션")
            feedback_survey.send_message = failing_send

            r2 = client.post("/generate", json=REQUEST_BODY)
            events2 = _parse_sse(r2.text)
            checks.append(("텔레그램 발송 실패해도 응답 200", r2.status_code == 200))
            checks.append(("텔레그램 발송 실패해도 done 이벤트 정상 전달", any(e.get("type") == "done" for e in events2)))
        finally:
            routes.generate_document_draft_stream = original_stream_fn
            feedback_survey.send_message = original_send_message
            feedback_survey.FEEDBACK_STATE_FILE = original_state_file
            app.dependency_overrides.clear()

    print()
    for name, ok in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    print("=" * 50)
    print("전체 결과:", "PASS" if all(ok for _, ok in checks) else "FAIL (위 로그 확인)")


if __name__ == "__main__":
    run()
