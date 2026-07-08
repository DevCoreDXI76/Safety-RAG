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
    risk_assessment_id: Optional[str] = None  # TBM 생성 시 연동할 위험성평가 id


class GenerateResponse(BaseModel):
    draft: str
    saved_record_id: Optional[str] = None
    linked_risk_assessment_id: Optional[str] = None