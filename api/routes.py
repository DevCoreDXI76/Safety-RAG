"""API 엔드포인트 — 기존 generate_draft.py 로직을 HTTP로 감싼다"""

import json
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
import sys
import os

# 프로젝트 루트의 generate_draft.py, common.py를 import하기 위한 경로 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from generate_draft import (
    DOCUMENT_TYPES,
    list_project_records,
    list_risk_assessments,
    get_record_by_id,
    generate_document_draft_stream,
)
from api.schemas import (
    DocumentTypesResponse,
    DocumentTypeItem,
    ProjectSummaryResponse,
    RecordSummary,
    RiskAssessmentListResponse,
    GenerateRequest,
)
from api.telegram_auth import require_telegram_auth
from api.rate_limit import check_and_increment
from api.cost_alert import check_and_alert_daily_cost

router = APIRouter()


@router.get("/document-types", response_model=DocumentTypesResponse)
def get_document_types(telegram_user: dict = Depends(require_telegram_auth)):
    """선택 가능한 문서 종류 목록 반환 ("기타" 항목은 프론트엔드에서 자유 입력 처리)"""
    items = [
        DocumentTypeItem(id=key, label=label)
        for key, label in DOCUMENT_TYPES.items()
    ]
    return DocumentTypesResponse(document_types=items)


@router.get("/projects/{project_name}", response_model=ProjectSummaryResponse)
def get_project_summary(project_name: str, telegram_user: dict = Depends(require_telegram_auth)):
    """현장의 전체 기록 요약 조회"""
    records = list_project_records(telegram_user["user_id"], project_name)
    return ProjectSummaryResponse(
        project_name=project_name,
        exists=len(records) > 0,
        records=[RecordSummary(**r) for r in records],
    )


@router.get("/projects/{project_name}/risk-assessments", response_model=RiskAssessmentListResponse)
def get_risk_assessments(project_name: str, telegram_user: dict = Depends(require_telegram_auth)):
    """TBM 생성 화면에서 선택할 위험성평가 회차 목록"""
    records = list_risk_assessments(telegram_user["user_id"], project_name)
    return RiskAssessmentListResponse(
        project_name=project_name,
        risk_assessments=[RecordSummary(**r) for r in records],
    )


@router.post("/generate")
def generate(req: GenerateRequest, telegram_user: dict = Depends(require_telegram_auth)):
    """
    문서 초안 생성 — SSE(text/event-stream)로 스트리밍한다.
    각 줄은 `data: {...}\\n\\n` 형식이며 JSON payload의 "type"은 다음 중 하나:
      - "delta": {"type": "delta", "text": "..."} — 텍스트 조각 (여러 번)
      - "done":  {"type": "done", "saved_record_id": ..., "linked_risk_assessment_id": ...} — 마지막 1회
      - "error": {"type": "error", "message": "..."} — 스트림 도중 오류 발생 시
    레이트리밋(429)/위험성평가 미존재(404)는 스트림 시작 전 일반 HTTP 에러로 응답한다.
    """
    user_id = telegram_user["user_id"]

    if not check_and_increment(user_id):
        raise HTTPException(status_code=429, detail="오늘 사용 가능한 횟수를 모두 사용했습니다.")

    risk_record = None
    if req.risk_assessment_id and req.project_name:
        risk_record = get_record_by_id(user_id, req.project_name, req.risk_assessment_id)
        if risk_record is None:
            raise HTTPException(status_code=404, detail="지정한 위험성평가 기록을 찾을 수 없습니다.")

    def event_stream():
        try:
            for event in generate_document_draft_stream(
                document_type=req.document_type,
                project_info=req.project_info,
                project_name=req.project_name,
                risk_assessment_record=risk_record,
                user_id=user_id,
                work_type=req.work_type,
            ):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            check_and_alert_daily_cost()
        except Exception as e:
            error_event = {"type": "error", "message": f"생성 중 오류 발생: {str(e)}"}
            yield f"data: {json.dumps(error_event, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")