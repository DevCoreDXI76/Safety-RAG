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


# 2026-08-04 실제 생성된 TBM일지/표준작업계획서 PDF에서 재현된 버그:
# "3. 중점(One Point) 위험요인"처럼 표가 아니라 서술형 문단인 섹션은 heading만
# 남고 본문이 통째로 사라졌다(parse_markdown_blocks가 heading/table만 인식).
SAMPLE_WITH_PROSE = """## ■ 기본 정보

| 항목 | 내용 |
|------|------|
| 현장명 | 강남지사 |

---

### 3. 중점(One Point) 위험요인

오늘 작업은 활선 근접 작업이 포함되어 있으므로, 작업 전 반드시 무전압 상태를
확인하고 검전기로 재확인한다.
전원 재투입 시에는 전체 인원에게 사전 통보 후 실시한다.

---

### 4. 근로자 준수사항

- 안전모, 절연장갑 착용 필수
- 2인 1조 작업 원칙 준수

## ■ 다음 표

| 항목 | 내용 |
|------|------|
| 결과 | 정상 |
"""


# 2026-08-05 5차 실사용 피드백: TBM 일지 "중점(One Point) 위험요인" 섹션에서
# "**AC 220V/380V 활선 접촉에 의한 감전**"처럼 markdown 굵게(**) 표시가
# 그대로(별표 포함) 렌더링됐다 — 표 셀(_clean_cell)과 달리 서술형 텍스트
# 블록은 굵게 표시를 제거하지 않았던 게 원인.
SAMPLE_WITH_BOLD_PROSE = """## ■ 비고

**AC 220V/380V 활선 접촉에 의한 감전**

- 선정 이유: 중상해 이상 재해로 이어질 가능성이 높음
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

    # --- 표가 아닌 서술형 문단(prose) 섹션도 블록으로 보존됨 ---
    prose_blocks = parse_markdown_blocks(SAMPLE_WITH_PROSE)
    checks.append(("블록 순서: heading,table,heading,text,heading,text,heading,table", [b["type"] for b in prose_blocks] == [
        "heading", "table", "heading", "text", "heading", "text", "heading", "table",
    ]))
    prose_text_blocks = [b for b in prose_blocks if b["type"] == "text"]
    checks.append(("'중점 위험요인' 서술형 본문이 텍스트로 보존됨", "무전압 상태" in prose_text_blocks[0]["text"]))
    checks.append(("여러 줄 문단이 개행으로 이어져 보존됨", "전체 인원에게 사전 통보" in prose_text_blocks[0]["text"]))
    checks.append(("불릿 목록도 텍스트로 보존됨", "2인 1조" in prose_text_blocks[1]["text"]))
    checks.append(("구분선(---)은 텍스트 블록에 섞여 들어가지 않음", not any("---" in b["text"] for b in prose_text_blocks)))

    # --- 서술형 텍스트 블록도 표 셀·헤딩과 동일하게 굵게(**) 표시가 제거됨 ---
    bold_blocks = parse_markdown_blocks(SAMPLE_WITH_BOLD_PROSE)
    bold_text_block = next(b for b in bold_blocks if b["type"] == "text")
    checks.append(("서술형 텍스트 블록에서 굵게(**) 마크다운 기호가 제거됨", "**" not in bold_text_block["text"]))
    checks.append(("굵게 표시를 제거해도 실제 문구는 그대로 보존됨", "AC 220V/380V 활선 접촉에 의한 감전" in bold_text_block["text"]))

    print()
    all_ok = True
    for name, ok in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {name}")
        all_ok = all_ok and ok
    print("\n전체 결과:", "PASS" if all_ok else "FAIL (위 로그 확인)")
    return all_ok


if __name__ == "__main__":
    run()
