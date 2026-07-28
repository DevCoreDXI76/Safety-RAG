# HWPX·PDF 내보내기 Design

**작성일**: 2026-07-28
**배경**: 개발자 체크리스트 D절 — HWPX 내보내기(D-16, PoC만 완료)와 PDF 내보내기(D-17, 미착수)를 실제 서비스에 반영한다. XLSX 내보내기(`export_xlsx.py`)가 이미 같은 패턴으로 구현·QA돼 있어 이를 그대로 미러링한다.

## 범위

- **문서종류**: 5개 전부 (위험성평가표·표준 작업계획서·TBM 일지·안전보건교육일지·산업안전보건관리비 사용명세서) — `parse_markdown_tables()`가 문서종류와 무관하게 동작하므로 XLSX와 동일하게 전체 적용.
- **스타일 수준**: 단순 테이블(제목 + 표 + 테두리)만. XLSX처럼 열너비 프로필·헤더 색상·조건부서식은 넣지 않는다 — 베타0 피드백에서 HWPX/PDF에 대한 명시적 수요 신호가 없었으므로 YAGNI. 실사용자 요청이 들어오면 그때 XLSX 수준으로 개선.
- **다운로드 UI**: 결과 화면의 기존 "엑셀 다운로드" 버튼 옆에 "한글 다운로드"/"PDF 다운로드" 버튼 2개를 추가. 드롭다운 등 UI 통합은 하지 않는다.

## 아키텍처

기존 XLSX 파이프라인을 그대로 복제한다:

```
record["draft"] (Markdown)
    → parse_markdown_tables()  (기존, markdown_tables.py, 변경 없음)
    → [HWPX 빌더 | PDF 빌더]
    → bytes
    → FastAPI Response (Content-Disposition 파일명 인코딩)
```

### HWPX (`export_hwpx.py`, 신규)

- `record_to_hwpx_bytes(record) -> bytes`
- 라이브러리: `python-hwpx` (PoC `test_hwpx_poc.py`에서 검증된 API만 사용 — `HwpxDocument.new()`, `doc.add_paragraph(text)`, `doc.add_table(rows, cols)`, `table.set_cell_text(row, col, text)`, `doc.save_to_path()`/바이트 저장).
- `parse_markdown_tables()`가 반환한 표마다 `add_table` 호출 + 헤더/데이터 셀 채우기. 표 사이·앞뒤의 일반 텍스트(표가 없는 draft 등)는 `add_paragraph`로 순서대로 삽입.
- 스타일: python-hwpx 기본 표 스타일 그대로(테두리만, 색상 없음).
- 저장은 임시 경로에 `save_to_path()` 후 파일을 바이트로 읽어 반환 (PoC와 동일한 API 사용 — 메모리 버퍼 직접 저장 API가 없다면 `tempfile`로 처리).

### PDF (`export_pdf.py`, 신규)

- `record_to_pdf_bytes(record) -> bytes`
- 라이브러리: `reportlab`. 한글은 내장 CID 폰트(`reportlab.pdfbase.cidfonts.UnicodeCIDFont`, 예: `HYSMyeongJo-Medium`)를 `pdfmetrics.registerFont`로 등록해 사용 — 별도 TTF 폰트 파일 번들 불필요, Railway(Linux)에 시스템 폰트 의존 없음.
- `reportlab.platypus.SimpleDocTemplate` + `Table`/`Paragraph` flowable로 문서 구성. 표가 없으면 `draft` 원문을 `Paragraph`로 넣는다(XLSX의 "표 없으면 A1에 원문" 규칙과 동일 취지).
- 표 스타일: `TableStyle`로 GRID 테두리만 적용, 헤더 색상 등은 넣지 않는다(스코프 결정 반영).
- 페이지 방향: 표 열이 많은 문서(위험성평가표 등)를 고려해 가로(landscape) A4 기본값 사용 — XLSX가 가로 인쇄인 것과 일관.

### 라우트 (`api/routes.py`)

기존 `export_record_xlsx`를 참고해 두 엔드포인트 추가:

```
GET /projects/{project_name}/records/{record_id}/export.hwpx
GET /projects/{project_name}/records/{record_id}/export.pdf
```

- 인증(`require_telegram_auth`), 404 처리(`get_record_by_id` 결과 None), 파일명 인코딩(`quote()` + `filename*=UTF-8''`) 모두 기존 패턴 그대로.
- media_type: HWPX는 `application/hwp+zip`(정확한 공식 MIME이 불명확하면 `application/octet-stream`으로 폴백 — 구현 시 python-hwpx 문서·실제 한/글 인식 여부로 확인), PDF는 `application/pdf`.

### 의존성 (`requirements.txt`)

`python-hwpx`, `reportlab` 추가.

### 프론트엔드 (`webapp/index.html`)

- `result-meta` 영역에 `btn-download-hwpx`("한글 다운로드"), `btn-download-pdf`("PDF 다운로드") 버튼 추가 (기존 `btn-download-xlsx` 스타일 그대로 복제).
- `downloadHwpx()`, `downloadPdf()` 함수 — 기존 `downloadXlsx()`를 복제해 경로(`export.hwpx`/`export.pdf`)·파일 확장자만 교체. `state.lastRecordId`/`state.lastProjectName` 체크 로직 동일.

## 에러 처리

기존 패턴 재사용 — 레코드 없으면 404. 빌더 내부 예외(라이브러리 오류 등)는 이번 세션에 추가한 전역 예외 핸들러(`api/error_alert.py`)가 로그+텔레그램 알림으로 자동 포착하므로 별도 처리를 추가하지 않는다.

## 테스트

- `test_hwpx_poc.py`와 동일한 형태의 스모크 스크립트로, 실제 저장된 기록(`data/projects/` 아래 기존 데이터 또는 합성 레코드) 하나를 HWPX/PDF로 변환해:
  - HWPX: zip 구조 유효성 + 재오픈 후 텍스트 보존(PoC와 동일 검증).
  - PDF: reportlab이 예외 없이 생성 완료 + 파일 매직바이트(`%PDF-`)로 최소 유효성 확인, 가능하면 텍스트 추출 라이브러리로 한글 보존 확인.
- 자동화 테스트 프레임워크가 없는 저장소이므로(기존 관례와 동일), 커밋 전 수동/스크립트 검증으로 대체한다.

## 스코프 밖 (의도적 제외)

- HWPX/PDF의 스타일 고도화(색상·조건부서식·열너비 프로필)는 이번 스코프에 넣지 않는다.
- 표준작업계획서 등 문서유형별 특화 레이아웃(법정 별표 인용 강조 등)도 넣지 않는다 — XLSX와 동일하게 markdown 표를 그대로 옮기는 수준.
