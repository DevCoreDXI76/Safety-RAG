# -*- coding: utf-8 -*-
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from markdown_tables import parse_markdown_blocks

SAMPLE = """# 위험성평가표 초안

---

## ■ 위험성평가표 (정보통신공사)

| 항목 | 내용 |
|------|------|
| 현장명 | 강남지사 |

---

### 작업 1. 굴착 작업 중 지반 붕괴

| 유해요인 | 대책 |
|------|------|
| 붕괴 | 흙막이 설치 |
"""


def run():
    checks = []
    blocks = parse_markdown_blocks(SAMPLE)

    checks.append(("레벨1 제목(# ...)은 블록에 안 들어감(문서 제목과 중복)", not any(
        b["type"] == "heading" and "초안" in b["text"] for b in blocks
    )))
    checks.append(("레벨2 헤딩이 heading 블록으로 들어감", any(
        b == {"type": "heading", "text": "■ 위험성평가표 (정보통신공사)"} for b in blocks
    )))
    checks.append(("레벨3 헤딩도 heading 블록으로 들어감", any(
        b == {"type": "heading", "text": "작업 1. 굴착 작업 중 지반 붕괴"} for b in blocks
    )))
    table_blocks = [b for b in blocks if b["type"] == "table"]
    checks.append(("표가 2개 들어감", len(table_blocks) == 2))
    checks.append(("첫 표 내용이 정확히 파싱됨", table_blocks[0]["rows"] == [["항목", "내용"], ["현장명", "강남지사"]]))
    checks.append(("순서 보존: heading -> table -> heading -> table", [b["type"] for b in blocks] == [
        "heading", "table", "heading", "table",
    ]))

    print()
    all_ok = True
    for name, ok in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {name}")
        all_ok = all_ok and ok
    print("\n전체 결과:", "PASS" if all_ok else "FAIL (위 로그 확인)")
    return all_ok


if __name__ == "__main__":
    run()
