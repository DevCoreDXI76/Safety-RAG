import io
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from openpyxl import load_workbook
from export_xlsx import record_to_xlsx_bytes

SAMPLE_RECORD = {
    "id": "abc123",
    "document_type": "위험성평가표",
    "project_info": "강남지사 광케이블 지중매설",
    "draft": (
        "# 위험성평가표 초안\n\n"
        "## ■ 기본 정보\n\n"
        "| 항목 | 내용 |\n"
        "|------|------|\n"
        "| **현장명** | 강남지사_광케이블 |\n"
        "| **작성일** | 2026-07-20 |\n\n"
        "## ■ 위험요인\n\n"
        "| 순번 | 위험요인 | 위험성 |\n"
        "|------|----------|--------|\n"
        "| 1 | 추락 | 12 (AI 제안값, 현장 확인 필수) |\n"
        "| 2 | 감전 | 9 (AI 제안값, 현장 확인 필수) |\n"
    ),
    "created_at": "2026-07-22 10:00:00",
}

SAMPLE_RECORD_NO_TABLE = {
    "id": "def456",
    "document_type": "기타",
    "project_info": "표 없는 문서",
    "draft": "이 문서에는 표가 없습니다.",
    "created_at": "2026-07-22 10:00:00",
}


def run():
    results = []

    xlsx_bytes = record_to_xlsx_bytes(SAMPLE_RECORD)
    wb = load_workbook(io.BytesIO(xlsx_bytes))
    ws = wb.active

    results.append(("시트명이 문서종류로 설정됨", ws.title == "위험성평가표"))
    results.append((
        "첫 번째 표 헤더 위치(A1, B1) 확인",
        ws.cell(row=1, column=1).value == "항목" and ws.cell(row=1, column=2).value == "내용",
    ))
    results.append((
        "굵게(**) 제거된 셀 값 확인",
        ws.cell(row=2, column=1).value == "현장명" and ws.cell(row=2, column=2).value == "강남지사_광케이블",
    ))
    results.append((
        "두 번째 표 시작 위치(표1 3행 + 빈행 1 = 5행부터) 확인",
        ws.cell(row=5, column=1).value == "순번" and ws.cell(row=5, column=2).value == "위험요인",
    ))
    results.append(("헤더 행 볼드 스타일 적용 확인", ws.cell(row=1, column=1).font.bold is True))

    xlsx_bytes_empty = record_to_xlsx_bytes(SAMPLE_RECORD_NO_TABLE)
    wb2 = load_workbook(io.BytesIO(xlsx_bytes_empty))
    ws2 = wb2.active
    results.append(("표 없는 문서는 원문 텍스트를 A1에 기록", ws2.cell(row=1, column=1).value == "이 문서에는 표가 없습니다."))

    all_ok = True
    for name, ok in results:
        print(f"[{'PASS' if ok else 'FAIL'}] {name}")
        all_ok = all_ok and ok

    print()
    print("전체 결과:", "PASS" if all_ok else "FAIL (위 로그 확인)")
    return all_ok


if __name__ == "__main__":
    run()
