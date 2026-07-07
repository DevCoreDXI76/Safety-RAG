"""
안전서류 초안 생성 스크립트
- 문서 종류를 메뉴에서 선택 (자유 텍스트 오입력 문제 차단)
- 위험성평가표 생성 시 projects/{현장명}.json에 결과 저장
- TBM 일지 생성 시, 같은 현장명에 여러 위험성평가 기록이 있으면 선택 가능
"""

import os
import json
from datetime import datetime
from common import search_similar_chunks, claude_client

PROJECTS_DIR = "projects"

DOCUMENT_TYPES = {
    "1": "위험성평가표",
    "2": "TBM 일지",
    "3": "안전보건교육일지",
    "4": "산업안전보건관리비 사용명세서",
    "5": "표준 작업계획서",
    "6": "기타 (직접 입력)",
}


def ensure_projects_dir():
    if not os.path.exists(PROJECTS_DIR):
        os.makedirs(PROJECTS_DIR)


def choose_document_type():
    print("생성할 문서 종류를 선택하세요:")
    for key, label in DOCUMENT_TYPES.items():
        print(f"  {key}. {label}")
    while True:
        choice = input("번호 입력: ").strip()
        if choice in DOCUMENT_TYPES:
            if choice == "6":
                custom = input("문서 종류를 직접 입력하세요: ").strip()
                return custom if custom else "기타 문서"
            return DOCUMENT_TYPES[choice]
        print("잘못된 입력입니다. 목록에 있는 번호를 입력하세요.")


def load_project_data(project_name):
    filepath = os.path.join(PROJECTS_DIR, f"{project_name}.json")
    if not os.path.exists(filepath):
        return None
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def save_project_record(project_name, document_type, project_info, draft):
    ensure_projects_dir()
    filepath = os.path.join(PROJECTS_DIR, f"{project_name}.json")
    data = load_project_data(project_name) or {"project_name": project_name, "records": []}
    data["records"].append({
        "document_type": document_type,
        "project_info": project_info,
        "draft": draft,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    })
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def list_risk_assessments(project_name):
    """같은 현장명의 위험성평가표 기록을 전부 반환 (오래된 순)"""
    data = load_project_data(project_name)
    if data is None:
        return []
    return [r for r in data["records"] if "위험성평가" in r["document_type"]]


def choose_risk_assessment(project_name):
    """
    같은 현장의 위험성평가 기록이 여러 건이면 선택하게 하고,
    1건이면 자동 사용, 0건이면 None 반환.
    """
    records = list_risk_assessments(project_name)
    if not records:
        print(f"[연동] '{project_name}' 현장의 위험성평가 기록을 찾지 못했습니다. "
              f"일반 지식베이스만 참고합니다.\n")
        return None

    if len(records) == 1:
        print(f"[연동] '{project_name}' 현장의 기존 위험성평가표를 참조합니다 "
              f"(생성일: {records[0]['created_at']})\n")
        return records[0]

    print(f"\n[연동] '{project_name}' 현장에 위험성평가 기록이 {len(records)}건 있습니다. "
          f"참조할 기록을 선택하세요:")
    for i, r in enumerate(records, 1):
        preview = r["project_info"][:40]
        print(f"  {i}. {r['created_at']} - {preview}...")
    print(f"  0. 참조하지 않음")

    while True:
        choice = input("번호 입력: ").strip()
        if choice == "0":
            return None
        if choice.isdigit() and 1 <= int(choice) <= len(records):
            return records[int(choice) - 1]
        print("잘못된 입력입니다.")


def show_project_summary(project_name):
    """현장 기록 조회 - 어떤 문서가 몇 건 있는지 요약 출력"""
    data = load_project_data(project_name)
    if data is None:
        print(f"'{project_name}' 현장의 기록이 없습니다. 새로 시작합니다.\n")
        return
    print(f"\n[{project_name} 현장 기록 — 총 {len(data['records'])}건]")
    for r in data["records"]:
        print(f"  - {r['created_at']} | {r['document_type']} | {r['project_info'][:40]}...")
    print()


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

    linked_risk_context = ""
    if "TBM" in document_type and project_name:
        risk_record = choose_risk_assessment(project_name)
        if risk_record:
            linked_risk_context = (
                f"\n\n---\n\n[이 현장에서 실제로 작성된 위험성평가표 — 이 내용을 우선 근거로 사용할 것]\n"
                f"{risk_record['draft']}"
            )

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

    project_name = input("현장명을 입력하세요 (연동 저장용, 생략하려면 엔터): ").strip() or None

    if project_name:
        show_project_summary(project_name)

    document_type = choose_document_type()
    project_info = input("프로젝트/작업 정보를 입력하세요: ").strip()

    print("\n초안 생성 중...\n")
    draft = generate_document_draft(document_type, project_info, project_name)

    print("=" * 50)
    print(draft)
    print("=" * 50)

    if project_name:
        print(f"\n'{project_name}' 현장 기록이 projects/{project_name}.json에 저장되었습니다.")