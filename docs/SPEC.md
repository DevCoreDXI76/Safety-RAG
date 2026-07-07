# SPEC — 안전서류 AI 초안 생성 시스템 (safety-rag)

> Technical Specification
> 최종 업데이트: 2026-07-06

---

## 1. 시스템 아키텍처 개요

```
사용자 입력 (문서종류, 프로젝트정보, 현장명)
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
projects/{현장명}.json에서               검색된 청크만 사용
최근 위험성평가 기록 조회 후
컨텍스트에 추가
        │                                    │
        └──────────────┬─────────────────────┘
                        ▼
              [Claude API 호출] system prompt + context + user prompt
                        │
                        ▼
              [초안 텍스트 생성]
                        │
                        ▼
    project_name 있으면 projects/{현장명}.json에 결과 저장
```

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
├── common.py
├── build_knowledge_base.py
├── generate_draft.py
├── test_search.py
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
└── docs/
    └── (PRD.md, PLAN.md, SPEC.md 등 문서 보관 위치)
```

## 4. 의존성 (`requirements.txt`)

```
anthropic
voyageai
cohere
sentence-transformers
numpy
python-dotenv
```

`cohere`, `sentence-transformers`는 Phase 3 임베딩 모델 비교 실험을 위해 추가됨.
`sentence-transformers`는 KURE-v1 로컬 추론 전용이며, 프로덕션 경로(`generate_draft.py`)는
Voyage만 사용하므로 최소 설치만 필요하다면 생략 가능.

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
  적용 후 정규화된 임베딩 반환
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

#### `save_project_record(project_name, document_type, project_info, draft)`
- 기존 파일 있으면 로드 후 append, 없으면 신규 생성

#### `load_latest_risk_assessment(project_name) -> dict | None`
- 같은 현장명 기록 중 `document_type`에 "위험성평가"가 포함된 가장 최근 레코드 1건 반환
- 기록이 없으면 `None`

#### `generate_document_draft(document_type, project_info, project_name=None) -> str`
1. 검색 쿼리 생성: `f"{document_type} 작성 관련 {project_info}"`
2. `search_similar_chunks(query, top_k=5)` 호출 (기본 모델 Voyage 사용), 결과를 콘솔에 디버그 출력
3. **연동 분기**: `document_type`에 "TBM" 포함 & `project_name` 존재 시
   `load_latest_risk_assessment()` 조회 → 있으면 `linked_risk_context`로 프롬프트에 추가,
   콘솔에 연동 여부 출력
4. system prompt: 참고자료 기반 작성, 실제 위험성평가표 있으면 우선 반영, 추측 금지,
   결과 하단에 법적 고지 문구 강제 포함
5. Claude API 호출 (`model="claude-sonnet-4-6"`, `max_tokens=4000`)
6. `project_name` 있으면 결과를 `save_project_record()`로 저장 후 반환

**주의**: `document_type` 매칭이 문자열 포함 여부(`"TBM" in document_type`,
`"위험성평가" in r["document_type"]`)로 이루어지므로, 사용자가 문서 종류를 자유 텍스트로
입력하면 오탐/누락 가능성이 있음 (예: "정보통신공사 현장에서 안전 관련해서 뭐부터 준비해야
해?"처럼 질문형 문장을 `document_type` 자리에 입력하면 의도와 다르게 동작 — 실제 발생 사례
있음, `test_search.py`로 검색 전용 테스트를 분리해 해결).

#### CLI 흐름 (`__main__`)
`document_type`, `project_info`, `project_name`(선택) 순으로 입력받아 초안 생성 후 콘솔 출력.

### 6.4 `test_search.py`

- 검색 품질만 독립적으로 확인하는 반복 입력형 스크립트
- CLI 인자 `--model {voyage|cohere|kure}`로 비교할 모델 선택 (기본값: `voyage`)
- 문서 생성 없이 `search_similar_chunks()` 결과(출처, 텍스트 앞부분)만 출력
- **도입 이유**: `generate_draft.py`는 "문서 종류 + 프로젝트 정보" 2단 입력 구조라, 순수 검색
  품질만 확인하려는 의도로 질의 하나만 입력하면 입력값이 잘못 매칭되는 문제가 실제 발생 →
  검색 전용 테스트 경로 분리
- Phase 3에서 이 스크립트로 Voyage/Cohere/KURE-v1 3파전 비교 실험 수행

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
| `document_type` 문자열 포함 매칭 방식의 오탐 가능성 | 인지됨, 별도 개선 미착수 |
| 다중 위험성평가 기록 시 항상 최신 1건만 참조 (여러 건 종합 불가) | 설계상 의도된 단순화, 필요 시 확장 가능 |
| 위험성평가 결과가 구조화되지 않고 텍스트 원문 그대로 저장됨 | 설계상 의도된 단순화 (파싱 비용 대비 이득 낮다고 판단) |

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
