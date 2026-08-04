import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import os
from playwright.sync_api import sync_playwright

INDEX_HTML = os.path.join(os.path.dirname(__file__), "index.html")

DOCUMENT_TYPES = [
    {"id": "1", "label": "위험성평가표"},
    {"id": "5", "label": "표준 작업계획서"},
    {"id": "2", "label": "TBM 일지"},
]

# 완료된 문서 종류에 이어, 순서안내 CTA가 다음으로 무엇을 제안해야 하는지.
# 베타0에서 위험성평가표->작업계획서 전환만 구현돼 있고 작업계획서->TBM일지
# 전환에는 CTA가 없었다(순서안내가 안 뜬다는 피드백의 유력 원인).
EXPECTED_NEXT = {
    "위험성평가표": "표준 작업계획서",
    "표준 작업계획서": "TBM 일지",
    "TBM 일지": None,
}


def check_cta_after(page, completed_label):
    """completed_label 문서 생성이 막 끝난 상태를 흉내내고, 렌더된 CTA의 텍스트를 돌려준다."""
    page.evaluate(
        """(label) => {
            const existing = document.getElementById("order-guide-cta");
            if (existing) existing.remove();
            state.selectedTypeLabel = label;
            const next = nextDocumentLabelAfter(label);
            if (next) offerNextDocumentCta(next);
        }""",
        completed_label,
    )
    cta = page.query_selector("#order-guide-cta")
    return cta.text_content() if cta else None


def run():
    results = []

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(f"file:///{INDEX_HTML.replace(os.sep, '/')}")
        page.evaluate("(types) => { state.documentTypes = types; }", DOCUMENT_TYPES)

        for completed_label, expected_next in EXPECTED_NEXT.items():
            try:
                cta_text = check_cta_after(page, completed_label)
            except Exception as e:
                results.append((f"{completed_label} 완료 후 CTA 판정", False))
                print(f"  -> 예외: {e}")
                continue

            if expected_next is None:
                ok = cta_text is None
                results.append((f"{completed_label} 완료 후에는 CTA가 뜨지 않는다", ok))
            else:
                ok = cta_text is not None and expected_next in cta_text
                results.append((f"{completed_label} 완료 후 CTA는 '{expected_next}'을 제안한다", ok))

        browser.close()

    all_ok = True
    for name, ok in results:
        print(f"[{'PASS' if ok else 'FAIL'}] {name}")
        all_ok = all_ok and ok

    print()
    print("전체 결과:", "PASS" if all_ok else "FAIL (위 로그 확인)")
    return all_ok


if __name__ == "__main__":
    run()
