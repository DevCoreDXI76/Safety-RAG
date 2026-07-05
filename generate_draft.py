"""
안전서류 초안 생성 스크립트
- 위험성평가표 생성 시 projects/{현장명}.json에 결과 저장
- TBM 일지 생성 시, 같은 현장명의 위험성평가 기록이 있으면 그 내용을 직접 컨텍스트로 사용
"""

import os
import json
from datetime import datetime
from common import search_similar_chunks, claude_client

PROJECTS_DIR = "projects"


def ensure_projects_dir():
    if not os.path.exists(PROJECTS_DIR):
        os.makedirs(PROJECTS_DIR)


def save_project_record(project_name, document_type, project_info, draft):
    """현장명 기준으로 최근 생성 기록을 저장. 같은 현장명이면 문서 종류별로 누적."""
    ensure_projects_dir()
    filepath = os.path.join(PROJECTS_DIR, f"{project_name}.json")

    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = {"project_name": project_name, "records": []}

    data["records"].append({
        "document_type": document_type,
        "project_info": project_info,
        "draft": draft,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    })

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_latest_risk_assessment(project_name):
    """같은 현장명의 가장 최근 위험성평가표 기록을 찾아 반환. 없으면 None."""
    filepath = os.path.join(PROJECTS_DIR, f"{project_name}.json")
    if not os.path.exists(filepath):
        return None

    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    risk_records = [r for r in data["records"] if "위험성평가" in r["document_type"]]
    if not risk_records:
        return None

    return risk_records[-1]  # 가장 최근 기록


def generate_document_draft(document_type, project_info, project_name=None):
    query = f"{document_type} 작성 관련 {project_info}"
    relevant_chunks = search_similar_chunks(query, top_k=5)

    print("\n[검색된 근거 청크]")
    for i, c in enumerate(relevant_chunks, 1):
        print(f"{i}. 출처: {c['source']}")
        print(f"   내용 일부: {c['text'][:80]}...")
    print()

    context = "\n\n---\n\n".join(
        f"[출처: {c['source']}]\n{c['text']}" for c in relevant_chunks
    )

    # TBM 일지를 생성하는 경우, 같은 현장의 실제 위험성평가 기록이 있으면 함께 참조
    linked_risk_context = ""
    if "TBM" in document_type and project_name:
        risk_record = load_latest_risk_assessment(project_name)
        if risk_record:
            print(f"[연동] '{project_name}' 현장의 기존 위험성평가표를 참조합니다 "
                  f"(생성일: {risk_record['created_at']})\n")
            linked_risk_context = (
                f"\n\n---\n\n[이 현장에서 실제로 작성된 위험성평가표 — 이 내용을 우선 근거로 사용할 것]\n"
                f"{risk_record['draft']}"
            )
        else:
            print(f"[연동] '{project_name}' 현장의 위험성평가 기록을 찾지 못했습니다. "
                  f"일반 지식베이스만 참고합니다.\n")

    system_prompt = (
        "너는 정보통신공사 현장의 안전서류 작성을 돕는 보조 도구야. "
        "제공된 참고 자료(법령, 표준 서식, 그리고 있다면 이 현장의 실제 위험성평가표)를 "
        "근거로 문서 초안을 작성해. "
        "만약 실제 위험성평가표가 함께 제공되었다면, 일반 가이드보다 그 내용을 우선적으로 반영해. "
        "참고 자료에 없는 내용은 추측해서 만들어내지 말고, "
        "실제 서류처럼 항목과 형식을 갖춰서 작성해. "
        "마지막에 반드시 '※ 이 초안은 참고용이며, 최종 검토 및 승인은 안전관리자가 직접 수행해야 합니다'라는 문구를 포함해."
    )

    user_prompt = (
        f"다음은 {document_type} 작성에 참고할 자료입니다:\n\n{context}"
        f"{linked_risk_context}\n\n"
        f"---\n\n"
        f"이 프로젝트 정보를 바탕으로 {document_type} 초안을 작성해줘:\n{project_info}"
    )

    response = claude_client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4000,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )

    draft = response.content[0].text.strip()

    if project_name:
        save_project_record(project_name, document_type, project_info, draft)

    return draft


if __name__ == "__main__":
    print("=== 안전서류 초안 생성기 (MVP) ===\n")
    document_type = input("문서 종류 (예: 위험성평가표 / TBM 일지): ").strip()
    project_info = input("프로젝트/작업 정보를 입력하세요: ").strip()
    project_name = input("현장명을 입력하세요 (연동 저장용, 생략하려면 엔터): ").strip() or None

    print("\n초안 생성 중...\n")
    draft = generate_document_draft(document_type, project_info, project_name)

    print("=" * 50)
    print(draft)
    print("=" * 50)

    if project_name:
        print(f"\n'{project_name}' 현장 기록이 projects/{project_name}.json에 저장되었습니다.")