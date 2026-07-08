# SPEC — 안전서류 AI 초안 생성 시스템 (safety-rag)

> Technical Specification
> 최종 업데이트: 2026-07-08

---

## 1. 시스템 아키텍처 개요

```
사용자 입력 (현장명 → 기록 요약 확인 → 문서종류 메뉴 선택 → 프로젝트정보)
        │
        ▼
[검색 쿼리 생성] "{document_type} 작성 관련 {project_info}"
        │
        ▼
[임베딩 모델 라우팅] embed_texts(query, input_type="query", model=...)
   voyage(기본값) / cohere / kure 중 선택
        │
        ▼
[코사인 유사도 검색] embeddings_{model}.json과 비교, top-5 청크 추출
        │
        ▼
[연동 체크] document_type에 "TBM" 포함 + project_name 존재?
        │                                    │
        │ Yes                                │ No
        ▼                                    ▼
같은 현장의 위험성평가 기록이              검색된 청크만 사용
1건이면 자동 사용, 여러 건이면
번호로 선택받아 컨텍스트에 추가
        │                                    │
        └──────────────┬─────────────────────┘
                        ▼
              [Claude API 호출] system prompt + context + user prompt
                        │
                        ▼
              [초안 텍스트 생성]
                        │
                        ▼
    project_name 있으면 projects/{현장명}.json에 결과 저장 (누적)
```

### 1.1 웹 인터페이스 아키텍처 (Phase 4)

```
텔레그램 미니앱 (webapp/index.html, Telegram Web App SDK)
        │  fetch(API_BASE = Railway 배포 URL)
        ▼
FastAPI (api/main.py, CORS 전체 허용)
        │
        ├─ GET  /document-types                          → DOCUMENT_TYPES 목록
        ├─ GET  /projects/{project_name}                  → 현장 전체 기록 요약
        ├─ GET  /projects/{project_name}/risk-assessments → 위험성평가 회차 목록
        └─ POST /generate                                 → 초안 생성 (risk_assessment_id로
                                                              특정 회차 지정 가능)
                        │
                        ▼
        generate_draft.py의 순수 함수들을 그대로 재사용
        (list_project_records, list_risk_assessments, get_record_by_id,
         generate_document_draft — CLI의 input() 기반 함수와 분리됨)
```

CLI(`generate_draft.py` 직접 실행)와 웹(API 경유) 두 진입점이 동일한 핵심 로직을 공유하는
구조. Railway 배포 URL: `https://web-production-9d1bd.up.railway.app`
(`Procfile`: `uvicorn api.main:app --host 0.0.0.0 --port $PORT`)

## 2. 개발 환경

| 항목 | 값 |
|---|---|
| OS | Windows |
| Python | 3.11.9 |
| 가상환경 | `venv` |
| 경로 | `C:\MyProjects\03_Study\safety-rag` |
| 패키지 설치 | `py -m pip install ...` (PowerShell에서 `pip` 단독 인식 안 되는 이슈로 이 방식 고정) |
| IDE | VS Code (인터프리터를 `venv\Scripts\python.exe`로 명시 선택 필요) |

## 3. 폴더 구조

```
safety-rag/
├── .env                                  ← Git 제외 (API 키)
├── .gitignore
├── requirements.txt
├── Procfile                              ← Railway 배포용 (uvicorn 실행 명령)
├── common.py
├── build_knowledge_base.py
├── generate_draft.py                     ← CLI 진입점 + API가 재사용하는 핵심 함수
├── test_search.py
├── migrate_add_ids.py                    ← 일회성 마이그레이션 (기존 레코드에 id 부여)
├── embeddings_voyage.json                ← Git 제외 (재생성 가능, 프로덕션 사용 모델)
├── embeddings_cohere.json                ← Git 제외 (Phase 3 비교 실험용)
├── embeddings_kure.json                  ← Git 제외 (Phase 3 비교 실험용)
├── knowledge_base/
│   ├── 위험성평가_실시규정.txt
│   ├── TBM_서식.txt
│   ├── 안전보건교육_가이드.txt
│   ├── 산업안전보건관리비_가이드.txt
│   └── 표준작업계획서_가이드.txt
├── projects/                             ← Git 제외 여부는 선택 (실험 기록 보존 원하면 포함 가능)
│   └── {현장명}.json
├── api/                                  ← FastAPI 백엔드 (Phase 4)
│   ├── main.py                           ← 앱 진입점, CORS, 헬스체크(`/`)
│   ├── routes.py                         ← 엔드포인트 (generate_draft.py 함수 재사용)
│   └── schemas.py                        ← Pydantic 요청/응답 스키마
├── webapp/                               ← 텔레그램 미니앱 프론트엔드 (Phase 4)
│   └── index.html                        ← 단일 파일 SPA, Telegram Web App SDK 연동
└── docs/
    └── (PRD.md, PLAN.md, SPEC.md 등 문서 보관 위치)
```

## 4. 의존성 (`requirements.txt`)

```
anthropic
voyageai
cohere
numpy
python-dotenv
fastapi
uvicorn[standard]
```

`cohere`는 Phase 3 임베딩 모델 비교 실험을 위해 추가됨. `fastapi`, `uvicorn[standard]`는
Phase 4 웹 API를 위해 추가됨. `sentence-transformers`(KURE-v1 로컬 추론 전용)는
`requirements.txt`에는 포함하지 않음 — `common.py`의 `get_kure_model()` 내부에서 지연
import하므로, 설치돼 있지 않아도 Voyage 기반 프로덕션 경로(CLI·API 공용)는 정상 동작한다.
KURE 비교 실험을 다시 돌리려면 로컬에서 `py -m pip install sentence-transformers`로 별도 설치.

## 5. 환경 변수 (`.env`)

```
ANTHROPIC_API_KEY=<Claude API 키>
VOYAGE_API_KEY=<Voyage AI API 키>
COHERE_API_KEY=<Cohere API 키, Phase 3 비교 실험용>
```

KURE-v1은 API 키가 필요 없는 로컬 모델(Hugging Face `nlpai-lab/KURE-v1`)이라 환경변수 불필요.

## 6. 모듈별 스펙

### 6.1 `common.py`

공통 유틸리티 모듈. 청킹, 다중 임베딩 모델 라우팅, 유사도 검색을 담당.

#### `chunk_text(text, max_chunk_size=800) -> list[str]`
- 문단(`\n\n`) 단위로 분할
- 누적 길이가 `max_chunk_size` 이하인 동안 문단을 이어 붙임
- 문단 하나가 `max_chunk_size`를 초과하면 `". "` 기준 문장 단위로 재분할
- **설계 이유**: 초기 버전은 글자 수 고정 분할(500자 + 50자 overlap)이었으나 문장/항목 중간
  절단 문제 발견 → 문단/문장 경계 우선 분할로 교체 (Phase 1에서 해결)

#### `load_all_documents() -> list[dict]`
- `knowledge_base/` 폴더의 모든 `.txt` 파일을 순회, `chunk_text()`로 분할
- 반환 형식: `[{"source": 파일명, "text": 청크텍스트}, ...]`

#### 임베딩 모델 분기 (Phase 3에서 추가)

- `EMBEDDING_MODELS = {"voyage": ..., "cohere": ..., "kure": ...}` — 지원 모델과 저장 파일명 매핑
- `DEFAULT_MODEL = "voyage"` — 명시적으로 모델을 지정하지 않으면 항상 Voyage 사용
- `embed_with_voyage(texts, input_type)` — Voyage `voyage-3`, `input_type`은 `"document"`/`"query"` 그대로 전달
- `embed_with_cohere(texts, input_type)` — Cohere `embed-multilingual-v3.0`,
  `input_type`을 `search_document`/`search_query`로 변환하여 전달
- `embed_with_kure(texts, input_type)` — 로컬 `sentence-transformers` 모델(`nlpai-lab/KURE-v1`),
  전역 변수로 지연 로딩(최초 호출 시에만 모델 로드), 공식 권장 프리픽스(`query: `/`passage: `)
  적용 후 정규화된 임베딩 반환. **`sentence_transformers` import 자체도 이 함수 내부에서
  수행** — 파일 상단에서 import하면 해당 패키지가 설치되어 있지 않을 때 Voyage만 쓰려는
  상황에서도 전체 스크립트가 `ModuleNotFoundError`로 죽는 문제가 실제로 발생해 수정함
- `embed_texts(texts, input_type, model=DEFAULT_MODEL)` — 위 세 함수로 라우팅하는 단일 진입점.
  `build_knowledge_base.py`, `search_similar_chunks()` 모두 이 함수를 거쳐 모델에 무관하게
  동일한 인터페이스로 동작

#### `save_embeddings(data, model=DEFAULT_MODEL)` / `load_embeddings(model=DEFAULT_MODEL)`
- `get_embeddings_filepath(model)`로 결정된 `embeddings_{model}.json`에 대한 JSON
  직렬화/역직렬화 래퍼. 모델별로 파일이 분리되어 있어 여러 모델의 임베딩 결과를 동시에
  보관하고 비교할 수 있다.

#### `cosine_similarity(vec_a, vec_b) -> float`
- numpy 기반 코사인 유사도 계산

#### `search_similar_chunks(query, top_k=5, model=DEFAULT_MODEL) -> list[dict]`
- `embed_texts()`로 쿼리 임베딩 생성 (`input_type="query"`, 모델 지정 가능)
- 지정 모델의 `embeddings_{model}.json`을 로드하여 저장된 모든 청크와 코사인 유사도 계산 후
  상위 `top_k`개 반환
- 해당 모델의 임베딩 파일이 없으면 `FileNotFoundError` 발생 (재빌드 안내 메시지 포함)

### 6.2 `build_knowledge_base.py`

- CLI 인자 `--model {voyage|cohere|kure}`로 임베딩 모델 선택 (기본값: `voyage`)
- `load_all_documents()` → 청크 리스트 확보
- `embed_texts(texts, input_type="document", model=...)`로 일괄 임베딩
- `save_embeddings(data, model=...)`로 `embeddings_{model}.json` 저장
- **지식베이스 문서를 추가/수정할 때마다, 그리고 청킹 로직을 변경할 때마다, 사용 중인 모든
  모델에 대해 재실행 필요** (Phase 3에서 3개 모델을 나란히 비교하려면 3번 모두 재실행)

### 6.3 `generate_draft.py`

#### 문서 종류 선택 (메뉴 방식)

```python
DOCUMENT_TYPES = {
    "1": "위험성평가표",
    "2": "TBM 일지",
    "3": "안전보건교육일지",
    "4": "산업안전보건관리비 사용명세서",
    "5": "표준 작업계획서",
    "6": "기타 (직접 입력)",
}
```

- `choose_document_type()`가 번호 입력을 받아 매칭. `6`을 선택하면 자유 텍스트 입력 허용
- **도입 이유**: 기존에는 `document_type`을 자유 텍스트로 입력받았는데, 문자열 포함 매칭
  (`"TBM" in document_type` 등)과 결합되어 질문형 문장을 잘못 입력하면 오동작하는 문제가
  실제로 발생함. 메뉴 선택으로 바꿔 입력값 자체를 통제함으로써 이 문제를 원천 차단

#### 데이터 저장 구조 (`projects/{project_name}.json`)

```json
{
  "project_name": "강남지사_광케이블",
  "records": [
    {
      "document_type": "위험성평가표",
      "project_info": "정보통신공사, 광케이블 지중 매설 작업, 인원 5명, 굴착 작업 포함",
      "draft": "<생성된 전체 초안 텍스트>",
      "created_at": "2026-07-05 23:01:42"
    },
    {
      "document_type": "TBM 일지",
      "project_info": "...",
      "draft": "...",
      "created_at": "..."
    }
  ]
}
```

- 문서 종류 구분 없이 모든 생성 기록을 시간순으로 누적 (`records` 배열에 append)
- 파싱을 하지 않고 생성된 텍스트 원문을 그대로 저장 — 구조화 파싱은 복잡도 대비 이득이 적어
  현재 범위에서 제외

#### `load_project_data(project_name)` / `save_project_record(...)`
- 현장별 JSON 파일 로드/저장. 기존 파일 있으면 로드 후 append, 없으면 신규 생성

#### `show_project_summary(project_name)`
- CLI 시작 시 현장명을 입력하면 그 현장에 어떤 기록이 몇 건 있는지(문서종류, 생성일시,
  프로젝트정보 일부) 바로 보여줌
- **도입 이유**: 기존에는 `projects/` 폴더를 직접 열어보지 않으면 어떤 기록이 있는지 알 방법이
  없었음

#### `list_risk_assessments(project_name)` / `choose_risk_assessment(project_name)`
- 같은 현장명의 위험성평가 기록(`document_type`에 "위험성평가" 포함)을 전부 조회
- 기록이 0건이면 연동 없이 진행, **1건이면 자동 사용**, **2건 이상이면 번호로 선택**하게 함
  (생성일시 + 프로젝트정보 앞부분을 보여줘 어떤 회차인지 구분 가능), `0` 입력 시 연동 안 함
- **도입 이유**: 기존에는 항상 "가장 최신 1건"만 자동으로 참조했는데, 한 현장에 서로 다른
  작업(굴착 작업용, 맨홀 작업용 등) 위험성평가가 여러 건 쌓이면 최신 것이 원하는 회차가
  아닐 수 있음. 실제 테스트에서 3건 중 의도한 회차(맨홀 접속 작업)를 정확히 골라 TBM에
  반영되는 것을 확인함

#### `generate_document_draft(document_type, project_info, project_name=None) -> str`
1. 검색 쿼리 생성: `f"{document_type} 작성 관련 {project_info}"`
2. `search_similar_chunks(query, top_k=5)` 호출 (기본 모델 Voyage 사용), 결과를 콘솔에 디버그 출력
3. **연동 분기**: `document_type`에 "TBM" 포함 & `project_name` 존재 시
   `choose_risk_assessment()` 호출 → 선택(또는 자동 선택)된 기록이 있으면
   `linked_risk_context`로 프롬프트에 추가
4. system prompt: 참고자료 기반 작성, 실제 위험성평가표 있으면 우선 반영, 추측 금지,
   결과 하단에 법적 고지 문구 강제 포함
5. Claude API 호출 (`model="claude-sonnet-4-6"`, `max_tokens=4000`)
6. `project_name` 있으면 결과를 `save_project_record()`로 저장 후 반환

#### CLI 흐름 (`__main__`)
`project_name`(선택, 입력 시 현장 기록 요약 출력) → `document_type`(메뉴 선택) →
`project_info`(자유 텍스트) 순으로 입력받아 초안 생성 후 콘솔 출력.

> 이전 버전은 `document_type` → `project_info` → `project_name` 순서였으나, 현장 기록을 먼저
> 확인하고 문서 종류를 고르는 흐름이 더 자연스러워 현장명을 가장 먼저 입력받도록 순서 변경.

### 6.4 `test_search.py`

- 검색 품질만 독립적으로 확인하는 반복 입력형 스크립트
- CLI 인자 `--model {voyage|cohere|kure}`로 비교할 모델 선택 (기본값: `voyage`)
- 문서 생성 없이 `search_similar_chunks()` 결과(출처, 텍스트 앞부분)만 출력
- **도입 이유**: `generate_draft.py`는 "문서 종류 + 프로젝트 정보" 2단 입력 구조라, 순수 검색
  품질만 확인하려는 의도로 질의 하나만 입력하면 입력값이 잘못 매칭되는 문제가 실제 발생 →
  검색 전용 테스트 경로 분리
- Phase 3에서 이 스크립트로 Voyage/Cohere/KURE-v1 3파전 비교 실험 수행

### 6.5 `api/` — FastAPI 백엔드 (Phase 4)

#### `api/main.py`
- `FastAPI` 앱 생성, `CORSMiddleware`로 모든 origin 허용(텔레그램 미니앱에서 호출하기 위함,
  배포 도메인이 확정되면 좁히는 것을 권장)
- `GET /` — 헬스체크, `{"status": "ok", "service": "safety-rag API"}` 반환
- `app.include_router(router)`로 `api/routes.py`의 엔드포인트 등록
- **알려진 갭**: `webapp/index.html`을 서빙하는 라우트/`StaticFiles` 마운트가 없음 — 프론트엔드는
  별도로 열거나 다른 정적 호스팅이 필요 (9번 "알려진 한계" 참조)

#### `api/routes.py`
- `generate_draft.py`의 순수 함수(`list_project_records`, `list_risk_assessments`,
  `get_record_by_id`, `generate_document_draft`, `DOCUMENT_TYPES`)를 그대로 import해 재사용 —
  CLI와 로직 이중 구현을 피함
- `GET /document-types` — `DOCUMENT_TYPES` 딕셔너리를 리스트 형태로 변환해 반환
- `GET /projects/{project_name}` — 현장의 전체 기록 요약 (`exists` 플래그 포함)
- `GET /projects/{project_name}/risk-assessments` — TBM 생성 화면에서 선택할 위험성평가 회차 목록
- `POST /generate` — `risk_assessment_id`가 있으면 `get_record_by_id()`로 해당 회차를 찾아
  `generate_document_draft()`에 전달(없으면 404), 생성 실패 시 500과 함께 에러 메시지 반환

#### `api/schemas.py`
- Pydantic 모델: `DocumentTypeItem`/`DocumentTypesResponse`, `RecordSummary`,
  `ProjectSummaryResponse`, `RiskAssessmentListResponse`, `GenerateRequest`, `GenerateResponse`
- `RecordSummary.id`는 `Optional` — `migrate_add_ids.py` 적용 전 레코드와의 호환을 위함

### 6.6 `migrate_add_ids.py`

- `projects/*.json`의 레코드 중 `id`가 없는 것에 `uuid4().hex[:12]`를 부여하는 일회성
  마이그레이션 스크립트
- **도입 이유**: API의 `risk_assessment_id` 기반 회차 지정 기능을 쓰려면 모든 레코드에 고유
  id가 있어야 하는데, id 필드 도입 이전에 생성된 기존 레코드에는 없었음
- 재실행해도 안전(이미 id가 있으면 건드리지 않음), 적용 후 삭제해도 무방

## 7. 시스템 프롬프트 원문 (생성 규칙)

```
너는 정보통신공사 현장의 안전서류 작성을 돕는 보조 도구야.
제공된 참고 자료(법령, 표준 서식, 그리고 있다면 이 현장의 실제 위험성평가표)를
근거로 문서 초안을 작성해.
만약 실제 위험성평가표가 함께 제공되었다면, 일반 가이드보다 그 내용을 우선적으로 반영해.
참고 자료에 없는 내용은 추측해서 만들어내지 말고,
실제 서류처럼 항목과 형식을 갖춰서 작성해.
마지막에 반드시 '※ 이 초안은 참고용이며, 최종 검토 및 승인은 안전관리자가 직접
수행해야 합니다'라는 문구를 포함해.
```

## 8. 임베딩 모델 스펙 (Phase 3 비교 실험 완료)

### 프로덕션 사용 모델

| 항목 | 값 |
|---|---|
| 제공사 | Voyage AI |
| 모델 | voyage-3 |
| 문서 임베딩 시 | `input_type="document"` |
| 쿼리 임베딩 시 | `input_type="query"` |
| 선택 이유 | Phase 3 비교 실험 결과 Cohere/KURE-v1 대비 유의미한 성능 차이 없음 → Anthropic 생태계 일관성, 추가 API/로컬 호스팅 부담 없음을 근거로 최종 채택 |

### 비교 실험 대상 (실험용, 프로덕션 미사용)

| 모델 | 제공사 | 임베딩 방식 | 비고 |
|---|---|---|---|
| embed-multilingual-v3.0 | Cohere | API, `search_document`/`search_query` | 별도 API 키 필요 |
| KURE-v1 | nlpai-lab (Hugging Face) | 로컬 추론 (sentence-transformers), `query: `/`passage: ` 프리픽스 | API 키 불필요, 최초 실행 시 약 1.3GB 다운로드 |

### 비교 실험 결론
- 5개 문서 규모의 지식베이스에서는 3개 모델 간 검색 품질 차이가 통계적으로 유의미하지 않음
- "관리비 문서 top-5 누락" 경계 케이스가 3개 모델 모두에서 재현됨 → 임베딩 모델이 아니라
  **문서의 청킹 단위(문단 구조)가 원인**임을 시사
- 해당 문서의 문단 구조를 항목별로 분리하자 3개 모델 모두 즉시 개선(top-1으로 상승) →
  가설 검증 완료 (`PLAN.md` Phase 3 섹션 참조)

## 9. 알려진 한계 및 미해결 이슈

| 이슈 | 상태 |
|---|---|
| `산업안전보건관리비_가이드.txt`가 굴착 관련 질의에서 top-5 밖으로 밀림 | ✅ 해결 — 문단을 항목별로 분리하여 3개 모델 모두에서 top-1으로 개선 확인 |
| `document_type` 문자열 포함 매칭 방식의 오탐 가능성 | ✅ 해결 — 자유 텍스트 입력을 번호 선택 메뉴로 교체하여 오입력 자체를 차단 |
| 다중 위험성평가 기록 시 항상 최신 1건만 참조 (여러 건 종합 불가) | ✅ 해결 — `choose_risk_assessment()`로 2건 이상일 때 번호로 선택 가능하도록 개선, 실제 3건 중 의도한 회차 선택 테스트 완료 |
| 위험성평가 결과가 구조화되지 않고 텍스트 원문 그대로 저장됨 | 설계상 의도된 단순화 (파싱 비용 대비 이득 낮다고 판단) |
| `api/main.py`에 `webapp/index.html` 정적 서빙 라우트가 없어 로컬에서 `/`, `/index.html` 등으로 직접 접근 시 404 | 미해결 — Phase 4 다음 액션으로 `StaticFiles` 마운트 추가 예정 |
| 현재 API에 인증이 없어 현장명만 알면 누구나 해당 현장 기록을 조회·생성 가능 | 설계상 의도(개인용 실사용 단계) — 다중 사용자로 확대 시 재검토 필요 |

## 10. 지식베이스 작성 원칙 (Phase 3 교훈 반영)

Phase 3 실험을 통해 확인된, 향후 지식베이스 문서를 추가/수정할 때 지켜야 할 원칙:

- 여러 개별 항목(예: 비용 항목, 위험요인, 체크리스트 등)을 하이픈 나열식으로 한 문단에
  몰아넣지 않는다 — `chunk_text()`가 문단 단위로 청크를 나누기 때문에, 이렇게 묶으면 특정
  항목의 핵심 키워드 신호가 다른 항목들에 희석되어 검색에서 누락될 수 있다
- 검색에서 반드시 잡혀야 하는 핵심 키워드가 있는 항목은 **독립된 문단**으로 분리하고,
  가능하면 해당 키워드를 문장 안에서 자연스럽게 반복 노출한다
- 검색 품질 이슈가 발견되면, 임베딩 모델 교체보다 **먼저 문서 구조(청킹 단위)를 의심**한다 —
  여러 모델에서 동일한 문서가 반복적으로 실패한다면 모델이 아니라 문서 쪽 문제일 가능성이 높다

## 11. 버전 관리

- `.gitignore` 제외 대상: `.env`, `venv/`, `__pycache__/`, `*.pyc`, `embeddings_voyage.json`,
  `embeddings_cohere.json`, `embeddings_kure.json`, `projects/`
- **주의**: `.gitignore` 작성 전에 `git add .`를 먼저 실행하면 `venv/`가 스테이징에 남는 문제
  발생 가능 → 이 경우 `git reset`으로 스테이징만 초기화 후 재확인 필요 (실제 발생 및 해결 사례)
