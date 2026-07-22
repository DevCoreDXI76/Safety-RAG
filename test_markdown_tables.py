import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from markdown_tables import parse_markdown_tables

SAMPLE_SINGLE_TABLE = """# 위험성평가표 초안

---

## ■ 위험성평가표 (정보통신공사)

| 항목 | 내용 |
|------|------|
| **현장명** | 강남지사_광케이블 |
| **작성일** | 2026-07-20 |
"""

SAMPLE_TWO_TABLES = """## 기본 정보

| 항목 | 내용 |
|------|------|
| 현장명 | A현장 |

## 위험요인

| 순번 | 위험요인 | 위험성 |
|------|----------|--------|
| 1 | 추락 | 12 |
| 2 | 감전 | 9 |
"""

SAMPLE_NO_TABLE = "이 문서에는 표가 없습니다. 그냥 서술문만 있습니다.\n"


def run():
    results = []

    tables = parse_markdown_tables(SAMPLE_SINGLE_TABLE)
    results.append(("단일 표 파싱 (표 1개, 행 3개: 헤더+2행)", len(tables) == 1 and len(tables[0]) == 3))
    results.append(("헤더 행 내용 확인", bool(tables) and tables[0][0] == ["항목", "내용"]))
    results.append(("굵게(**) 마크다운 제거 확인", bool(tables) and tables[0][1] == ["현장명", "강남지사_광케이블"]))

    tables2 = parse_markdown_tables(SAMPLE_TWO_TABLES)
    results.append(("표 2개 분리 파싱", len(tables2) == 2))
    results.append((
        "두 번째 표 셀 값 확인",
        bool(tables2) and len(tables2) > 1
        and tables2[1][0] == ["순번", "위험요인", "위험성"]
        and tables2[1][2] == ["2", "감전", "9"],
    ))

    tables3 = parse_markdown_tables(SAMPLE_NO_TABLE)
    results.append(("표 없는 텍스트는 빈 리스트 반환", tables3 == []))

    all_ok = True
    for name, ok in results:
        print(f"[{'PASS' if ok else 'FAIL'}] {name}")
        all_ok = all_ok and ok

    print()
    print("전체 결과:", "PASS" if all_ok else "FAIL (위 로그 확인)")
    return all_ok


if __name__ == "__main__":
    run()
