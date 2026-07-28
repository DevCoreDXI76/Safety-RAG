# HWPX·PDF 내보내기 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 저장된 기록을 HWPX와 PDF로도 내보낼 수 있게 한다 — XLSX(`export_xlsx.py`)와 동일한 `parse_markdown_tables()` 파이프라인을 재사용하되, 스타일은 단순 테이블(제목+표+기본 테두리) 수준으로만 구현한다.

**Architecture:** `record["draft"]`(Markdown) → `parse_markdown_tables()`(기존, 변경 없음) → 문서종류별 빌더(`export_hwpx.py`/`export_pdf.py`, 신규) → bytes → FastAPI 라우트 응답. 프론트엔드는 기존 "엑셀 다운로드" 버튼 옆에 버튼 2개를 추가해 동일한 패턴으로 다운로드를 트리거한다.

**Tech Stack:** `python-hwpx`(이미 PoC로 API 검증됨), `reportlab`(내장 CID 폰트로 한글 처리, 별도 폰트 파일 불필요).

참고 설계 문서: `docs/superpowers/specs/2026-07-28-hwpx-pdf-export-design.md`

## Global Constraints

- 스타일은 "단순 테이블"만: 제목 + 표(테두리만) + 기본 정렬. XLSX의 열너비 프로필·헤더 색상·조건부서식은 넣지 않는다.
- 5개 문서종류(위험성평가표·표준 작업계획서·TBM 일지·안전보건교육일지·산업안전보건관리비 사용명세서) 전부에 적용 — 문서종류별 분기 로직을 만들지 않는다(`parse_markdown_tables()`가 이미 문서종류 무관).
- 이 저장소엔 pytest 등 자동화 테스트 프레임워크가 없다 — 기존 관례(`test_hwpx_poc.py`, `test_worktype_citations.py`)를 따라 실행하면 PASS/FAIL을 출력하는 독립 스크립트로 검증한다.
- 표가 없는 draft는 원문 그대로 문단 하나로 넣는다(XLSX의 "표 없으면 A1에 원문" 규칙과 동일 취지) — 표가 있을 때 표 사이의 서술 텍스트를 복원하려 하지 않는다(`parse_markdown_tables()`가애초에 표가 아닌 텍스트는 버리므로 구조적으로 불가능).

---

### Task 1: HWPX 내보내기 (`export_hwpx.py`)

**Files:**
- Create: `export_hwpx.py`
- Create: `test_export_hwpx.py`
- Modify: `requirements.txt` (이 Task에서 `python-hwpx` 추가 — 실제로는 이미 venv에 설치돼 있지만 requirements.txt엔 아직 없었음)

**Interfaces:**
- Consumes: `markdown_tables.parse_markdown_tables(markdown_text) -> list[list[list[str]]]` (기존, 변경 없음). `generate_draft.get_record_by_id(user_id, project_name, record_id) -> dict | None` (기존, 테스트에서만 사용).
- Produces: `export_hwpx.record_to_hwpx_bytes(record: dict) -> bytes` — Task 3(라우트)이 그대로 가져다 쓴다.

**검증된 python-hwpx API** (실제 introspection으로 확인, 추측 아님):
- `HwpxDocument.new() -> HwpxDocument`
- `doc.add_paragraph(text: str) -> HwpxOxmlParagraph`
- `doc.add_table(rows: int, cols: int) -> HwpxOxmlTable`
- `table.set_cell_text(row_index: int, col_index: int, text: str)`
- `doc.to_bytes() -> bytes` (파일 경로 없이 바로 메모리 바이트 반환)
- `HwpxDocument.open(source: bytes) -> HwpxDocument` (bytes를 직접 받음, 파일 경로 불필요)
- `doc2.export_text() -> str`, `doc2.get_table_map() -> dict`(표 개수 확인용, PoC와 동일)

- [ ] **Step 1: 검증 스크립트 작성 (아직 없는 함수를 호출하도록)**

`test_export_hwpx.py` 생성:

```python
# -*- coding: utf-8 -*-
"""
export_hwpx.py 스모크 테스트 — 실제 저장된 기록(xlsx_export_test_user 프로젝트,
위험성평가표 1건)을 HWPX로 변환해 zip 구조 유효성과 텍스트 보존을 확인한다.
python-hwpx 도입 PoC(test_hwpx_poc.py)와 동일한 검증 방식을 재사용한다.

사용 예:
  python test_export_hwpx.py
"""
import io
import sys
import zipfile

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from hwpx import HwpxDocument

from export_hwpx import record_to_hwpx_bytes
from generate_draft import get_record_by_id

TEST_USER_ID = "xlsx_export_test_user"
TEST_PROJECT_NAME = "xlsx_export_테스트현장"
TEST_RECORD_ID = "20c1c6d12755"


def run():
    print("=== export_hwpx.py 스모크 테스트 ===\n")

    record = get_record_by_id(TEST_USER_ID, TEST_PROJECT_NAME, TEST_RECORD_ID)
    assert record is not None, "테스트 픽스처 기록을 찾지 못함 — data/projects 확인 필요"

    print("[1] HWPX 바이트 생성...")
    hwpx_bytes = record_to_hwpx_bytes(record)
    print(f"    -> {len(hwpx_bytes)} bytes")

    print("\n[2] zip 구조 유효성 확인...")
    with zipfile.ZipFile(io.BytesIO(hwpx_bytes)) as zf:
        bad_file = zf.testzip()
    print(f"    -> 손상 파일: {bad_file}")

    print("\n[3] 재오픈 후 텍스트 보존 확인...")
    doc2 = HwpxDocument.open(hwpx_bytes)
    full_text = doc2.export_text()
    table_map = doc2.get_table_map()

    checks = []
    checks.append(("문서종류 제목 보존", record["document_type"] in full_text))
    checks.append(("표 1개 인식됨", len(table_map) == 1))
    checks.append(("표 내용(현장명) 보존", "현장명" in full_text and "테스트현장" in full_text))
    checks.append(("손상 파일 없음", bad_file is None))

    print()
    all_ok = True
    for name, ok in checks:
        status = "PASS" if ok else "FAIL"
        all_ok = all_ok and ok
        print(f"[{status}] {name}")

    print("\n" + "=" * 50)
    print("전체 결과:", "PASS" if all_ok else "FAIL (위 로그 확인)")


if __name__ == "__main__":
    run()
```

- [ ] **Step 2: 실행해서 실패 확인 (아직 `export_hwpx.py`가 없음)**

Run: `python test_export_hwpx.py`
Expected: `ModuleNotFoundError: No module named 'export_hwpx'`

- [ ] **Step 3: `export_hwpx.py` 구현**

```python
"""
저장된 프로젝트 기록(record["draft"]의 Markdown 텍스트)을 파싱해
python-hwpx 문서로 바인딩하고, .hwpx 파일 바이트를 반환한다.

XLSX(export_xlsx.py)와 동일하게 parse_markdown_tables()를 공용으로 쓴다.
스타일은 단순 테이블(제목 + 표 + 기본 테두리)만 적용한다 — 베타0 피드백에서
HWPX에 대한 명시적 수요 신호가 없었으므로 색상·열너비 등 XLSX 수준의
장식은 넣지 않는다(docs/superpowers/specs/2026-07-28-hwpx-pdf-export-design.md 참고).
"""

from hwpx import HwpxDocument

from markdown_tables import parse_markdown_tables


def record_to_hwpx_bytes(record):
    """
    record["draft"]에서 Markdown 표를 순서대로 파싱해 표로 채운다.
    표가 없으면 draft 원문을 문단 하나로 그대로 넣는다(XLSX의 "표 없으면
    원문 그대로" 규칙과 동일 취지).
    """
    tables = parse_markdown_tables(record["draft"])

    doc = HwpxDocument.new()
    doc.add_paragraph(record["document_type"])
    doc.add_paragraph("")

    if not tables:
        doc.add_paragraph(record["draft"])
        return doc.to_bytes()

    for table in tables:
        rows = len(table)
        cols = max(len(row) for row in table)
        hwpx_table = doc.add_table(rows, cols)
        for row_index, row_cells in enumerate(table):
            for col_index, value in enumerate(row_cells):
                hwpx_table.set_cell_text(row_index, col_index, value)
        doc.add_paragraph("")

    return doc.to_bytes()
```

- [ ] **Step 4: 실행해서 통과 확인**

Run: `python test_export_hwpx.py`
Expected: 4개 체크 전부 `[PASS]`, 마지막 줄 `전체 결과: PASS`

- [ ] **Step 5: `requirements.txt`에 의존성 추가**

`requirements.txt` 끝에 한 줄 추가:

```diff
 openpyxl
+python-hwpx
```

- [ ] **Step 6: 커밋**

```bash
git add export_hwpx.py test_export_hwpx.py requirements.txt
git commit -m "feat: HWPX 내보내기 구현 (export_hwpx.py)"
```

---

### Task 2: PDF 내보내기 (`export_pdf.py`)

**Files:**
- Create: `export_pdf.py`
- Create: `test_export_pdf.py`
- Modify: `requirements.txt` (`reportlab` 추가)

**Interfaces:**
- Consumes: `markdown_tables.parse_markdown_tables(markdown_text) -> list[list[list[str]]]` (기존, Task 1과 동일하게 재사용).
- Produces: `export_pdf.record_to_pdf_bytes(record: dict) -> bytes` — Task 3(라우트)이 그대로 가져다 쓴다.

**검증된 reportlab 사용법** (실제로 로컬에서 렌더링 + `pypdf`로 텍스트 추출까지 확인 완료):
- 한글 폰트: `from reportlab.pdfbase.cidfonts import UnicodeCIDFont` + `pdfmetrics.registerFont(UnicodeCIDFont("HYSMyeongJo-Medium"))` — 별도 TTF 파일 없이 한글이 정확히 렌더링·추출됨을 확인함.
- `Table(data)`에 일반 문자열 리스트를 넣으면 XML로 파싱되지 않고 있는 그대로(`<`, `&` 포함) 렌더링됨 — 셀 값 이스케이프 불필요. 행 길이가 들쭉날쭉해도 에러 없이 처리됨(확인 완료).
- `Paragraph(text, style)`는 내부적으로 미니 XML 마크업을 해석하지만, 이번 reportlab 5.0.0에서 `<`, `&`, `<태그처럼보이는텍스트>`가 섞여도 크래시 없이 리터럴로 보존되는 것까지 실측 확인함. 그래도 향후 reportlab 버전 차이·실제 태그(`<b>` 등)와 우연히 겹치는 경우에 대비해 `xml.sax.saxutils.escape()`로 이스케이프한 뒤 넘긴다(표 없는 draft를 그대로 문단에 넣는 경로에서만 필요 — 표 셀은 `Table`이라 이스케이프 불필요).

- [ ] **Step 1: 검증 스크립트 작성**

`test_export_pdf.py` 생성:

```python
# -*- coding: utf-8 -*-
"""
export_pdf.py 스모크 테스트 — 실제 저장된 기록(xlsx_export_test_user 프로젝트,
위험성평가표 1건)을 PDF로 변환해 파일 유효성과 한글 텍스트 보존을 확인한다.
텍스트 추출은 pypdf를 쓴다(런타임 의존성 아님 — 이 스크립트 실행 전
`pip install pypdf`로 별도 설치 필요, requirements.txt엔 넣지 않음).

사용 예:
  pip install pypdf   # 최초 1회
  python test_export_pdf.py
"""
import io
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import pypdf

from export_pdf import record_to_pdf_bytes
from generate_draft import get_record_by_id

TEST_USER_ID = "xlsx_export_test_user"
TEST_PROJECT_NAME = "xlsx_export_테스트현장"
TEST_RECORD_ID = "20c1c6d12755"


def run():
    print("=== export_pdf.py 스모크 테스트 ===\n")

    record = get_record_by_id(TEST_USER_ID, TEST_PROJECT_NAME, TEST_RECORD_ID)
    assert record is not None, "테스트 픽스처 기록을 찾지 못함 — data/projects 확인 필요"

    print("[1] PDF 바이트 생성...")
    pdf_bytes = record_to_pdf_bytes(record)
    print(f"    -> {len(pdf_bytes)} bytes")

    print("\n[2] PDF 매직바이트 확인...")
    is_pdf = pdf_bytes[:5] == b"%PDF-"
    print(f"    -> %PDF- 로 시작함: {is_pdf}")

    print("\n[3] 텍스트 추출 후 한글 보존 확인...")
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    full_text = "".join(page.extract_text() for page in reader.pages)

    checks = []
    checks.append(("PDF 매직바이트", is_pdf))
    checks.append(("문서종류 제목 보존", record["document_type"] in full_text))
    checks.append(("표 내용(현장명) 보존", "현장명" in full_text and "테스트현장" in full_text))

    print()
    all_ok = True
    for name, ok in checks:
        status = "PASS" if ok else "FAIL"
        all_ok = all_ok and ok
        print(f"[{status}] {name}")

    print("\n" + "=" * 50)
    print("전체 결과:", "PASS" if all_ok else "FAIL (위 로그 확인)")


if __name__ == "__main__":
    run()
```

- [ ] **Step 2: 실행해서 실패 확인**

Run: `pip install pypdf` (스모크 테스트 전용, requirements.txt엔 추가하지 않음), 이어서 `python test_export_pdf.py`
Expected: `ModuleNotFoundError: No module named 'export_pdf'`

- [ ] **Step 3: `export_pdf.py` 구현**

```python
"""
저장된 프로젝트 기록(record["draft"]의 Markdown 텍스트)을 파싱해
reportlab으로 PDF 바이트를 반환한다.

한글은 reportlab 내장 CID 폰트(HYSMyeongJo-Medium)로 렌더링한다 — 별도
TTF 폰트 파일을 저장소에 넣지 않아도 Railway(Linux) 환경에서 그대로
동작한다(docs/superpowers/specs/2026-07-28-hwpx-pdf-export-design.md에서
로컬 렌더링 + pypdf 텍스트 추출로 확인 완료).
"""

import io
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from markdown_tables import parse_markdown_tables

_FONT_NAME = "HYSMyeongJo-Medium"
pdfmetrics.registerFont(UnicodeCIDFont(_FONT_NAME))

_TITLE_STYLE = ParagraphStyle("title", fontName=_FONT_NAME, fontSize=14, leading=18, spaceAfter=12)
_BODY_STYLE = ParagraphStyle("body", fontName=_FONT_NAME, fontSize=10.5, leading=15)

_TABLE_STYLE = TableStyle([
    ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
    ("FONTNAME", (0, 0), (-1, -1), _FONT_NAME),
    ("FONTSIZE", (0, 0), (-1, -1), 9),
    ("VALIGN", (0, 0), (-1, -1), "TOP"),
])


def record_to_pdf_bytes(record):
    """
    record["draft"]에서 Markdown 표를 순서대로 파싱해 표로 채운다.
    표가 없으면 draft 원문을 문단 하나로 그대로 넣는다(XLSX/HWPX와 동일 규칙).
    표 셀은 Table이 리터럴로 그리므로 이스케이프하지 않지만, 문단(Paragraph)은
    내부적으로 미니 XML을 해석하므로 원문을 그대로 넣기 전에 escape()한다.
    """
    tables = parse_markdown_tables(record["draft"])

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4))
    elements = [Paragraph(escape(record["document_type"]), _TITLE_STYLE), Spacer(1, 12)]

    if not tables:
        body_text = escape(record["draft"]).replace("\n", "<br/>")
        elements.append(Paragraph(body_text, _BODY_STYLE))
    else:
        for table in tables:
            elements.append(Table(table, style=_TABLE_STYLE))
            elements.append(Spacer(1, 12))

    doc.build(elements)
    return buffer.getvalue()
```

- [ ] **Step 4: 실행해서 통과 확인**

Run: `python test_export_pdf.py`
Expected: 3개 체크 전부 `[PASS]`, 마지막 줄 `전체 결과: PASS`

- [ ] **Step 5: `requirements.txt`에 의존성 추가**

```diff
 openpyxl
 python-hwpx
+reportlab
```

- [ ] **Step 6: 커밋**

```bash
git add export_pdf.py test_export_pdf.py requirements.txt
git commit -m "feat: PDF 내보내기 구현 (export_pdf.py)"
```

---

### Task 3: API 라우트 추가 (`api/routes.py`)

**Files:**
- Modify: `api/routes.py`
- Create: `test_export_routes.py`

**Interfaces:**
- Consumes: `export_hwpx.record_to_hwpx_bytes(record) -> bytes` (Task 1), `export_pdf.record_to_pdf_bytes(record) -> bytes` (Task 2), 기존 `get_record_by_id`, `require_telegram_auth`.
- Produces: 라우트 `GET /projects/{project_name}/records/{record_id}/export.hwpx`, `GET /projects/{project_name}/records/{record_id}/export.pdf` — Task 4(프론트엔드)가 그대로 호출한다.

기존 `export_record_xlsx`(`api/routes.py:109-124`) 바로 아래에 두 라우트를 추가한다. 인증(`require_telegram_auth`)·404·파일명 인코딩(`quote()` + `filename*=UTF-8''`) 패턴은 기존 라우트와 동일하게 따른다.

- [ ] **Step 1: 검증 스크립트 작성 (아직 없는 라우트를 호출하도록)**

`test_export_routes.py` 생성 — `require_telegram_auth` 의존성을 오버라이드해 실제 텔레그램 인증 없이 라우트 자체를 검증한다:

```python
# -*- coding: utf-8 -*-
"""
export.hwpx / export.pdf 라우트 스모크 테스트 — TestClient로 인증 의존성을
오버라이드하고, 실제 저장된 기록을 대상으로 두 엔드포인트가 200과 올바른
매직바이트를 반환하는지 확인한다.

사용 예:
  python test_export_routes.py
"""
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from fastapi.testclient import TestClient

from api.main import app
from api.telegram_auth import require_telegram_auth

TEST_PROJECT_NAME = "xlsx_export_테스트현장"
TEST_RECORD_ID = "20c1c6d12755"

app.dependency_overrides[require_telegram_auth] = lambda: {
    "user_id": "xlsx_export_test_user", "username": None, "first_name": None,
}
client = TestClient(app, raise_server_exceptions=False)


def check(name, condition):
    print(f"[{'PASS' if condition else 'FAIL'}] {name}")
    return condition


def run():
    print("=== export.hwpx / export.pdf 라우트 스모크 테스트 ===\n")
    all_ok = True

    r = client.get(f"/projects/{TEST_PROJECT_NAME}/records/{TEST_RECORD_ID}/export.hwpx")
    all_ok &= check("export.hwpx 200 응답", r.status_code == 200)
    all_ok &= check("export.hwpx zip 매직바이트(PK)", r.content[:2] == b"PK")

    r = client.get(f"/projects/{TEST_PROJECT_NAME}/records/{TEST_RECORD_ID}/export.pdf")
    all_ok &= check("export.pdf 200 응답", r.status_code == 200)
    all_ok &= check("export.pdf 매직바이트(%PDF-)", r.content[:5] == b"%PDF-")

    r = client.get(f"/projects/{TEST_PROJECT_NAME}/records/nonexistent-id/export.hwpx")
    all_ok &= check("존재하지 않는 record_id -> 404", r.status_code == 404)

    print("\n" + "=" * 50)
    print("전체 결과:", "PASS" if all_ok else "FAIL (위 로그 확인)")


if __name__ == "__main__":
    run()
```

- [ ] **Step 2: 실행해서 실패 확인 (아직 라우트가 없음)**

Run: `python test_export_routes.py`
Expected: `export.hwpx`/`export.pdf` 요청이 404(라우트 자체가 없어서)로 응답 — `[FAIL] export.hwpx 200 응답` 등이 찍힘

- [ ] **Step 3: 라우트 구현**

`api/routes.py` 상단 import에 추가:

```diff
 from export_xlsx import record_to_xlsx_bytes
+from export_hwpx import record_to_hwpx_bytes
+from export_pdf import record_to_pdf_bytes
```

기존 `export_record_xlsx` 함수(`api/routes.py:109-124`) 바로 뒤에 추가:

```python
@router.get("/projects/{project_name}/records/{record_id}/export.hwpx")
def export_record_hwpx(project_name: str, record_id: str, telegram_user: dict = Depends(require_telegram_auth)):
    """저장된 기록 하나를 hwpx로 내보낸다. 스타일은 단순 테이블(제목+표+기본 테두리) 수준."""
    user_id = telegram_user["user_id"]
    record = get_record_by_id(user_id, project_name, record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="지정한 기록을 찾을 수 없습니다.")

    hwpx_bytes = record_to_hwpx_bytes(record)
    filename = f"{project_name}_{record['document_type']}.hwpx"
    return Response(
        content=hwpx_bytes,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f"attachment; filename=\"export.hwpx\"; filename*=UTF-8''{quote(filename)}",
        },
    )


@router.get("/projects/{project_name}/records/{record_id}/export.pdf")
def export_record_pdf(project_name: str, record_id: str, telegram_user: dict = Depends(require_telegram_auth)):
    """저장된 기록 하나를 pdf로 내보낸다. 스타일은 단순 테이블(제목+표+기본 테두리) 수준."""
    user_id = telegram_user["user_id"]
    record = get_record_by_id(user_id, project_name, record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="지정한 기록을 찾을 수 없습니다.")

    pdf_bytes = record_to_pdf_bytes(record)
    filename = f"{project_name}_{record['document_type']}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=\"export.pdf\"; filename*=UTF-8''{quote(filename)}",
        },
    )
```

- [ ] **Step 4: 실행해서 통과 확인**

Run: `python test_export_routes.py`
Expected: 5개 체크 전부 `[PASS]`, 마지막 줄 `전체 결과: PASS`

- [ ] **Step 5: 커밋**

```bash
git add api/routes.py test_export_routes.py
git commit -m "feat: HWPX/PDF 내보내기 API 라우트 추가"
```

---

### Task 4: 프론트엔드 다운로드 버튼 (`webapp/index.html`)

**Files:**
- Modify: `webapp/index.html`

**Interfaces:**
- Consumes: Task 3의 `GET .../export.hwpx`, `GET .../export.pdf`. 기존 `state.lastRecordId`/`state.lastProjectName`/`state.selectedTypeLabel`(파일명용)/`apiFetch()`(기존 `downloadXlsx()`가 쓰는 것과 동일).
- Produces: 없음(최종 사용자 화면 기능).

기존 `downloadXlsx()`(`webapp/index.html` 약 794행)와 `btn-download-xlsx` 버튼(약 417행)을 그대로 복제해 확장자·경로·버튼 라벨만 바꾼다.

- [ ] **Step 1: 버튼 마크업 추가**

`result-meta` 영역의 기존 `btn-download-xlsx` 버튼 바로 뒤에 추가:

```diff
       <button class="btn-secondary" id="btn-download-xlsx" style="padding:5px 10px; font-size:11.5px;">엑셀 다운로드</button>
+      <button class="btn-secondary" id="btn-download-hwpx" style="padding:5px 10px; font-size:11.5px;">한글 다운로드</button>
+      <button class="btn-secondary" id="btn-download-pdf" style="padding:5px 10px; font-size:11.5px;">PDF 다운로드</button>
       <button class="btn-secondary" id="btn-edit" style="padding:5px 10px; font-size:11.5px;">편집</button>
```

- [ ] **Step 2: 다운로드 함수 추가**

기존 `downloadXlsx()` 함수 바로 뒤에 추가 (동일한 구조, `path`와 확장자만 다름):

```javascript
  async function downloadHwpx() {
    if (!state.lastRecordId || !state.lastProjectName) {
      showError("현장명을 입력하고 생성해야 한글 파일로 내려받을 수 있습니다.");
      return;
    }
    $("btn-download-hwpx").disabled = true;
    try {
      const path = `/projects/${encodeURIComponent(state.lastProjectName)}/records/${encodeURIComponent(state.lastRecordId)}/export.hwpx`;
      const res = await apiFetch(path);
      if (!res.ok) throw new Error("한글 파일을 만들지 못했습니다.");
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${state.lastProjectName}_${state.selectedTypeLabel || "문서"}.hwpx`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (e) {
      showError(e.message);
    } finally {
      $("btn-download-hwpx").disabled = false;
    }
  }

  async function downloadPdf() {
    if (!state.lastRecordId || !state.lastProjectName) {
      showError("현장명을 입력하고 생성해야 PDF로 내려받을 수 있습니다.");
      return;
    }
    $("btn-download-pdf").disabled = true;
    try {
      const path = `/projects/${encodeURIComponent(state.lastProjectName)}/records/${encodeURIComponent(state.lastRecordId)}/export.pdf`;
      const res = await apiFetch(path);
      if (!res.ok) throw new Error("PDF 파일을 만들지 못했습니다.");
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${state.lastProjectName}_${state.selectedTypeLabel || "문서"}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (e) {
      showError(e.message);
    } finally {
      $("btn-download-pdf").disabled = false;
    }
  }
```

- [ ] **Step 3: 이벤트 바인딩 추가**

기존 `$("btn-download-xlsx").addEventListener("click", downloadXlsx);` 바로 뒤에 추가:

```diff
   $("btn-download-xlsx").addEventListener("click", downloadXlsx);
+  $("btn-download-hwpx").addEventListener("click", downloadHwpx);
+  $("btn-download-pdf").addEventListener("click", downloadPdf);
   $("btn-edit").addEventListener("click", toggleEdit);
```

- [ ] **Step 4: 브라우저에서 수동 검증**

자동화 테스트 프레임워크(Playwright 등)가 없으므로 기존 관례대로 로컬 서버 + `dev_login_helper.py`로 수동 확인한다:

1. `venv/Scripts/uvicorn api.main:app --port 8000` 실행
2. `python dev_login_helper.py` 실행 후 출력된 JS 코드를 브라우저 devtools 콘솔에 붙여넣어 인증 우회
3. `http://localhost:8000/app/` 접속, 문서 하나 생성
4. "한글 다운로드" 클릭 → `.hwpx` 파일이 다운로드되는지, 한/글(또는 한/글이 없으면 압축 프로그램으로 열어 zip 구조가 정상인지) 확인
5. "PDF 다운로드" 클릭 → `.pdf` 파일이 다운로드되고, PDF 뷰어로 열었을 때 한글이 정상적으로 보이는지(깨진 글자 없는지) 확인

Expected: 두 버튼 모두 정상적으로 파일을 내려받고, 파일 내용에 한글이 깨지지 않고 표시됨.

- [ ] **Step 5: 커밋**

```bash
git add webapp/index.html
git commit -m "feat: 결과 화면에 한글/PDF 다운로드 버튼 추가"
```

---

## Self-Review 메모

- **스펙 커버리지**: design 문서의 5개 섹션(HWPX/PDF 모듈, 라우트, 의존성, 프론트엔드, 에러 처리) 전부 Task 1~4에 매핑됨. 에러 처리는 별도 코드 없이 기존 `api/error_alert.py` 전역 핸들러가 자동으로 커버(design에서 이미 확정).
- **타입 일관성**: `record_to_hwpx_bytes(record) -> bytes`, `record_to_pdf_bytes(record) -> bytes` 시그니처가 Task 1/2에서 정의된 그대로 Task 3에서 사용됨. 프론트엔드 함수명(`downloadHwpx`/`downloadPdf`)도 Task 4 전체에서 일관됨.
- **의존성 검증 완료**: `python-hwpx`의 `to_bytes()`/`HwpxDocument.open(bytes)`, `reportlab`의 `UnicodeCIDFont` 한글 렌더링과 `Table`/`Paragraph`의 특수문자 처리 방식을 모두 실제 로컬 실행으로 확인한 뒤 코드에 반영함 — 추측으로 작성된 API 호출 없음.
