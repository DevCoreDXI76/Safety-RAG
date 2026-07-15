"""
표준 작업계획서 4개 작업유형 회귀 테스트 스크립트.
KB(knowledge_base/표준작업계획서_법정별표.txt)나 generate_draft.py의
system_prompt/인용 검증 로직을 바꿀 때마다 커밋 전에 실행할 것.

실제 Claude API를 호출하므로 비용이 발생한다 — CI 자동 실행 대상이 아니라
개발자가 직접 실행하는 온디맨드 스크립트다.

사용 예:
  python test_worktype_citations.py
"""

import sys

# Windows 콘솔 기본 코드페이지(cp949)는 em-dash(—) 등 일부 유니코드 문자를
# 인코딩하지 못해 print()에서 UnicodeEncodeError가 나는 경우가 있다.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from generate_draft import generate_document_draft
from common import find_unverified_citations, WORK_TYPE_SECTION_MARKERS

CASES = [
    ("굴착작업", "정보통신공사 현장에서 광케이블 지중 매설을 위한 굴착 작업. 인원 5명, 굴착기 1대 투입."),
    ("중량물의 취급 작업", "통신주(전주) 및 케이블 드럼 하역·운반 작업. 인원 4명, 크레인 1대 투입."),
    ("차량계 건설기계를 사용하는 작업", "굴착기(포크레인)를 이용한 지중관로 매설 작업. 인원 3명."),
    ("전기작업", "국사 내 전원 인입 작업, 380V 배전반 연계 작업. 인원 2명."),
    ("차량계 하역운반기계등을 사용하는 작업", "국사 내 지게차를 이용한 통신장비 반입 작업. 인원 4명, 지게차 1대 투입."),
]

# 굴착작업에서 이번에 실제로 확인해야 할 최소 기대 사실
EXCAVATION_EXPECTED_FACTS = [
    "굴착공사정보지원센터",
    "제345조",
    "제346조",
    "제347조",
    "수평",
]

# 컨텍스트에 실제로 있는 벌칙 조항 — system_prompt의 "지어내지 마" 지시가
# 과잉 일반화되어 있는 근거까지 빼버리는 회귀(2026-07-11 발견)를 감시한다.
EXCAVATION_PENALTY_FACTS = [
    "제167조",
    "제168조",
    "제50조",
]

# 맨홀작업(§34) 특별교육이 밀폐공간(§35)과 혼동되지 않는지 - 예전엔 RAG
# top-k 순위에 따라 등장 여부가 갈렸던 항목이라(2026-07-11 발견), 직접주입
# 이후에는 매번 안정적으로 "맨홀작업"·"제34호"가 등장해야 한다.
EXCAVATION_EDUCATION_FACTS = [
    "맨홀작업",
    "34호",
]

# 이번에 지적받은 오류가 문자 그대로 재발하지 않는지 직접 고정 (간접적으로는
# find_unverified_citations가 잡아주지만, 신고된 버그는 리터럴로도 고정해둔다)
EXCAVATION_KNOWN_BAD_PATTERNS = [
    "제34조", "제35조", "제36조", "제37조",  # 흙막이 지보공 조문 환각(정답: 345~347조)
]

# "법정 전체 목록"(표준작업계획서_법정별표.txt 15~33행)의 순번(전기작업=5번째,
# 중량물 취급=11번째)을 실제 법정 "호" 번호로 오인하는 환각. system_prompt가
# 굴착작업(6번째) 사례로 이미 이 패턴을 금지하고 있음에도(292~295행) 다른
# 작업유형에서 재발 확인됨(2026-07-16 실사용 테스트 리포트로 발견,
# find_unverified_citations가 정상적으로 감지·경고했음 — 체커 결함 아님).
ELECTRICAL_WORK_KNOWN_BAD_PATTERNS = ["제38조제1항제5호"]
HEAVY_LOAD_KNOWN_BAD_PATTERNS = ["제38조제1항제11호"]

KNOWN_BAD_PATTERNS_BY_WORK_TYPE = {
    "전기작업": ELECTRICAL_WORK_KNOWN_BAD_PATTERNS,
    "중량물의 취급 작업": HEAVY_LOAD_KNOWN_BAD_PATTERNS,
}


def check_excavation_facts(draft):
    missing = [f for f in EXCAVATION_EXPECTED_FACTS if f not in draft]
    missing_penalty = [f for f in EXCAVATION_PENALTY_FACTS if f not in draft]
    missing_education = [f for f in EXCAVATION_EDUCATION_FACTS if f not in draft]
    bad_hits = [p for p in EXCAVATION_KNOWN_BAD_PATTERNS if p in draft]
    depth_based_isolation = "굴착 깊이" in draft and "0.5m" in draft
    return missing, missing_penalty, missing_education, bad_hits, depth_based_isolation


def run_case(work_type, project_info):
    """단일 작업유형 1건 생성 + 검증. all_ok(bool)를 반환."""
    ok = True
    print(f"--- {work_type} ---")
    draft, _ = generate_document_draft(
        document_type="표준 작업계획서",
        project_info=project_info,
        work_type=work_type,
    )

    # system_prompt가 항상 이 문구로 마무리하도록 강제하므로, 문서 끝부분에
    # 이 문구가 없으면 max_tokens 등으로 중간에 잘렸을 가능성이 높다는 신호로 쓴다.
    if "최종 검토 및 승인은 안전관리자가 직접 수행해야 합니다" not in draft[-300:]:
        print("  [FAIL] 마무리 문구가 끝부분에 없음 — 문서가 중간에 잘렸을 가능성 (max_tokens 등 확인)")
        ok = False
    else:
        print("  [OK] 문서가 마무리 문구까지 완결됨 (잘림 없음)")

    # generate_document_draft가 이미 draft 안에 경고문을 붙여주지만,
    # 여기서는 별도로 다시 계산해서 원본 context 없이도 draft 자체를 관찰한다.
    has_warning = "자동 검증 알림" in draft
    print(f"  [인용 경고] {'있음 - 아래 내용 확인' if has_warning else '없음'}")
    if has_warning:
        warn_line = [l for l in draft.split("\n") if "자동 검증 알림" in l]
        for l in warn_line:
            print(f"    {l.strip()}")
        ok = False

    bad_patterns = KNOWN_BAD_PATTERNS_BY_WORK_TYPE.get(work_type)
    if bad_patterns:
        bad_hits = [p for p in bad_patterns if p in draft]
        if bad_hits:
            print(f"  [FAIL] 재발 금지 오류 패턴 발견(목록 순번→법정 호 번호 오인): {bad_hits}")
            ok = False
        else:
            print("  [OK] 목록 순번→법정 호 번호 오인 패턴 재발 없음")

    if work_type == "굴착작업":
        missing, missing_penalty, missing_education, bad_hits, depth_based = check_excavation_facts(draft)
        if missing:
            print(f"  [FAIL] 기대 사실 누락: {missing}")
            ok = False
        else:
            print("  [OK] 기대 사실(사전신고/제345~347조/수평 이격거리) 모두 포함")

        if missing_penalty:
            print(f"  [FAIL] 벌칙 조항 누락(과잉교정 회귀 가능성): {missing_penalty}")
            ok = False
        else:
            print("  [OK] 벌칙 조항(제167조/제168조/제50조) 모두 포함")

        if missing_education:
            print(f"  [FAIL] 맨홀작업 특별교육(§34) 언급 누락(밀폐공간과 혼동 가능성): {missing_education}")
            ok = False
        else:
            print("  [OK] 맨홀작업 특별교육(§34) 정상 언급 (밀폐공간과 혼동 없음)")

        if bad_hits:
            print(f"  [FAIL] 재발 금지 오류 패턴 발견: {bad_hits}")
            ok = False
        else:
            print("  [OK] 흙막이 지보공 조문 환각(제34~37조) 재발 없음")

        if depth_based:
            print("  [FAIL] '굴착 깊이'와 '0.5m'가 함께 등장 - 이격거리를 깊이 기준으로 서술했을 가능성, 육안 확인 필요")
            ok = False
        else:
            print("  [OK] 이격거리를 깊이 기준으로 서술한 흔적 없음")

        if "**안전보건" in draft or draft.rstrip().endswith("**"):
            print("  [관찰] 표/문서가 잘린 것으로 보이는 패턴 발견 - 육안으로 재확인 필요")

    print()
    return ok


def run():
    print("=== 표준 작업계획서 작업유형별 인용 검증 회귀 테스트 ===\n")
    all_ok = True
    for work_type, project_info in CASES:
        if work_type not in WORK_TYPE_SECTION_MARKERS:
            print(f"[SKIP] {work_type}: WORK_TYPE_SECTION_MARKERS에 없음")
            continue
        if not run_case(work_type, project_info):
            all_ok = False

    print("=" * 50)
    print("전체 결과:", "PASS" if all_ok else "FAIL (위 로그 확인)")


def run_repeat(work_type, n):
    """지정한 작업유형을 n회 반복 생성해 변동성(회귀) 자체를 관찰한다."""
    project_info = dict(CASES)[work_type]
    print(f"=== {work_type} {n}회 반복 검증 (변동성 확인) ===\n")
    results = []
    for i in range(1, n + 1):
        print(f"[반복 {i}/{n}]")
        results.append(run_case(work_type, project_info))
    print("=" * 50)
    print(f"{n}회 중 통과: {sum(results)}회, 실패: {results.count(False)}회")


if __name__ == "__main__":
    if "--repeat" in sys.argv:
        idx = sys.argv.index("--repeat")
        n = int(sys.argv[idx + 1]) if idx + 1 < len(sys.argv) else 4
        target = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else "굴착작업"
        run_repeat(target, n)
    else:
        run()
