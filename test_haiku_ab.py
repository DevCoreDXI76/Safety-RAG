# -*- coding: utf-8 -*-
"""
Haiku 4.5 vs Sonnet 5 A/B 테스트 하네스.

TBM일지·안전보건교육일지처럼 Haiku 다운그레이드 후보 문서유형에서, 같은
입력으로 두 모델 결과를 나란히 생성하고 기존 인용/구간표/이격거리
체커(모두 _finalize_draft 안에서 이미 자동 적용됨)가 붙인 "자동 검증
알림" 경고 유무로 1차 비교한다. 세부 품질(수치 조작 여부 등)은 저장된
전체 draft를 사람이 직접 읽고 판단해야 한다 — 이 스크립트는 그 판단을
위한 원본 자료를 만드는 역할까지만 한다.

실제 Claude API를 호출하므로 비용이 발생한다 — 온디맨드 스크립트.
generate_document_draft에 user_id="ab_test_*"로 넘겨서, 실사용
토큰/비용 로그(token_usage_log.jsonl)와 섞여도 /stats에서 구분 가능하게
했다. 단, 현재 비용 계산(api/cost_alert.py)은 Sonnet 5 단가로 고정돼
있어 Haiku 호출분의 비용 표시는 부정확(과대 계상)하다 — 실제 Haiku
전환·배포 시점에 함께 손볼 것.

사용 예:
  python test_haiku_ab.py              # 문서유형별 1건씩 (스모크 테스트, 총 4회 호출)
  python test_haiku_ab.py --n 10       # 문서유형별 10건씩 (총 40회 호출)
"""
import sys
import json
import argparse
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from generate_draft import generate_document_draft

HAIKU_MODEL = "claude-haiku-4-5-20251001"
SONNET_MODEL = "claude-sonnet-5"

# Haiku 다운그레이드 후보 문서유형 + 반복 검증용 시나리오
CASES = [
    ("TBM 일지", "광케이블 지중 매설 작업 TBM. 인원 5명, 굴착기 1대 투입."),
    ("안전보건교육일지", "신규 채용자 대상 정기 안전보건교육. 인원 4명."),
]


def run_one(document_type, project_info, model):
    label = "haiku" if model == HAIKU_MODEL else "sonnet"
    draft, _ = generate_document_draft(
        document_type=document_type,
        project_info=project_info,
        project_name=None,
        user_id=f"ab_test_{label}",
        model=model,
    )
    has_warning = "자동 검증 알림" in draft
    warning_lines = [l.strip() for l in draft.split("\n") if "자동 검증 알림" in l]
    return {"draft": draft, "output_length": len(draft), "has_warning": has_warning, "warning_lines": warning_lines}


def run(n):
    print(f"=== Haiku vs Sonnet A/B 테스트 (문서유형별 {n}건씩) ===\n")
    results = []

    # 중간에 죽어도 그때까지 결과는 남도록 건마다 즉시 append (전체 종료 시
    # 일괄 저장하면 크래시 시 진행분이 전부 유실됨 — 2026-07-16 실제로 겪음)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = f"ab_test_results_{ts}.jsonl"

    for document_type, project_info in CASES:
        for i in range(1, n + 1):
            for model in (SONNET_MODEL, HAIKU_MODEL):
                label = "Sonnet 5" if model == SONNET_MODEL else "Haiku 4.5"
                print(f"[{document_type} {i}/{n}] {label} 생성 중...")
                r = run_one(document_type, project_info, model)
                r.update({"document_type": document_type, "model": label, "trial": i})
                results.append(r)
                with open(out_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")
                status = "경고 있음" if r["has_warning"] else "경고 없음"
                print(f"  -> 길이={r['output_length']}자, {status}")

    print("\n" + "=" * 50)
    print(f"전체 draft 저장 위치: {out_path}\n")
    print("=== 요약 (자동 검증 알림 발생률) ===")
    for document_type, _ in CASES:
        for label in ("Sonnet 5", "Haiku 4.5"):
            subset = [r for r in results if r["document_type"] == document_type and r["model"] == label]
            warned = sum(1 for r in subset if r["has_warning"])
            avg_len = sum(r["output_length"] for r in subset) / len(subset) if subset else 0
            print(f"{document_type} / {label}: {warned}/{len(subset)}건 경고, 평균 길이 {avg_len:.0f}자")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=1, help="문서유형별 반복 횟수 (기본 1)")
    args = parser.parse_args()
    run(args.n)
