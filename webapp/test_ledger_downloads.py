import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import os
from playwright.sync_api import sync_playwright

INDEX_HTML = os.path.join(os.path.dirname(__file__), "index.html")

RECORDS_WITH_ID = [
    {"id": "rec-1", "document_type": "위험성평가표", "project_info": "광케이블 지중 매설", "created_at": "2026-08-04 09:00"},
    {"id": "rec-2", "document_type": "표준 작업계획서", "project_info": "광케이블 지중 매설", "created_at": "2026-08-04 09:10"},
]

RECORD_WITHOUT_ID = [
    {"id": None, "document_type": "TBM 일지", "project_info": "구버전 레코드", "created_at": "2026-07-01 08:00"},
]


def run():
    results = []

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(f"file:///{INDEX_HTML.replace(os.sep, '/')}")

        # --- id가 있는 과거 기록에는 3개(엑셀/한글/PDF) 다운로드 버튼이 붙는다 ---
        page.evaluate(
            "(records) => { state.projectRecords = records; renderLedger('테스트현장'); }",
            RECORDS_WITH_ID,
        )
        buttons = page.query_selector_all(".ledger-dl")
        results.append(("기록 2건 × 형식 3개 = 다운로드 버튼 6개 생성", len(buttons) == 6))

        # --- 버튼 클릭 시 해당 record의 id/document_type/format으로 downloadRecord가 호출된다 ---
        page.evaluate(
            """() => {
                window.__calls = [];
                window.downloadRecord = (projectName, recordId, docLabel, format, btn) => {
                    window.__calls.push([projectName, recordId, docLabel, format]);
                };
            }"""
        )
        first_hwpx_btn = page.query_selector(".ledger-dl[data-format='hwpx']")
        first_hwpx_btn.click()
        call = page.evaluate("window.__calls[0]")
        results.append((
            "첫 기록의 '한글' 버튼 클릭 시 해당 record.id로 downloadRecord 호출",
            call == ["테스트현장", "rec-1", "위험성평가표", "hwpx"],
        ))

        # --- id가 없는 구버전 레코드는 다운로드 버튼을 만들지 않는다 ---
        page.evaluate(
            "(records) => { state.projectRecords = records; renderLedger('테스트현장'); }",
            RECORD_WITHOUT_ID,
        )
        results.append(("id 없는 레코드는 다운로드 버튼이 없다", page.query_selector(".ledger-dl") is None))

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
