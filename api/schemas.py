"""Pydantic 스키마 — API 요청/응답 형식 정의"""

from pydantic import BaseModel
from typing import Optional, List


class DocumentTypeItem(BaseModel):
    id: str
    label: str


class DocumentTypesResponse(BaseModel):
    document_types: List[DocumentTypeItem]


class RecordSummary(BaseModel):
    id: Optional[str] = None
    document_type: str
    project_info: str
    created_at: str


class ProjectSummaryResponse(BaseModel):
    project_name: str
    exists: bool
    records: List[RecordSummary]


class RiskAssessmentListResponse(BaseModel):
    project_name: str
    risk_assessments: List[RecordSummary]


class GenerateRequest(BaseModel):
    document_type: str
    project_info: str
    project_name: Optional[str] = None
    risk_assessment_id: Optional[str] = None  # TBM/작업계획서 생성 시 연동할 위험성평가 id
    work_type: Optional[str] = None  # 표준 작업계획서 생성 시 선택한 작업유형

# /generate는 SSE 스트리밍 응답(text/event-stream)이라 응답 바디에
# response_model을 적용하지 않는다. 이벤트 형태(delta/done/error)는
# api/routes.py의 /generate 엔드포인트 docstring 참고.