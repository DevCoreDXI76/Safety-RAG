# SPEC — 안전서류 AI 초안 생성 시스템 (safety-rag)

> Technical Specification
> 최종 업데이트: 2026-07-05

---

## 1. 시스템 아키텍처 개요

```
사용자 입력 (문서종류, 프로젝트정보, 현장명)
        │
        ▼
[검색 쿼리 생성] "{document_type} 작성 관련 {project_info}"
        │
        ▼
[Voyage AI 임베딩] query embedding 생성
        │
        ▼
[코사인 유사도 검색] knowledge_base 임베딩(embeddings.json)과 비교, top-5 청크 추출
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
├── embeddings.json                       ← Git 제외 (재생성 가능)
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
numpy
python-dotenv
```

Phase 3 착수 시 `cohere` 패키지 추가 예정.

## 5. 환경 변수 (`.env`)

```
ANTHROPIC_API_KEY=<Claude API 키>
VOYAGE_API_KEY=<Voyage AI API 키>
```

Phase 3 착수 시 `COHERE_API_KEY` 추가 예정.

## 6. 모듈별 스펙

### 6.1 `common.py`

공통 유틸리티 모듈. 청킹, 임베딩 저장/로드, 유사도 검색을 담당.

#### `chunk_text(text, max_chunk_size=800) -> list[str]`
- 문단(`\n\n`) 단위로 분할
- 누적 길이가 `max_chunk_size` 이하인 동안 문단을 이어 붙임
- 문단 하나가 `max_chunk_size`를 초과하면 `". "` 기준 문장 단위로 재분할
- **설계 이유**: 초기 버전은 글자 수 고정 분할(500자 + 50자 overlap)이었으나 문장/항목 중간
  절단 문제 발견 → 문단/문장 경계 우선 분할로 교체 (Phase 1에서 해결)

#### `load_all_documents() -> list[dict]`
- `knowledge_base/` 폴더의 모든 `.txt` 파일을 순회, `chunk_text()`로 분할
- 반환 형식: `[{"source": 파일명, "text": 청크텍스트}, ...]`

#### `save_embeddings(data)` / `load_embeddings()`
- `embeddings.json`에 대한 JSON 직렬화/역직렬화 래퍼

#### `cosine_similarity(vec_a, vec_b) -> float`
- numpy 기반 코사인 유사도 계산

#### `search_similar_chunks(query, top_k=5) -> list[dict]`
- Voyage AI로 쿼리 임베딩 생성 (`input_type="query"`)
- 저장된 모든 청크와 코사인 유사도 계산 후 상위 `top_k`개 반환
- `embeddings.json`이 없으면 `FileNotFoundError` 발생

### 6.2 `build_knowledge_base.py`

- `load_all_documents()` → 청크 리스트 확보
- Voyage AI `voyage-3` 모델로 일괄 임베딩 (`input_type="document"`)
- `save_embeddings()`로 `embeddings.json` 저장
- **지식베이스 문서를 추가/수정할 때마다 반드시 재실행 필요** (청킹 로직 변경 시에도 동일)

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
2. `search_similar_chunks(query, top_k=5)` 호출, 결과를 콘솔에 디버그 출력
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
- 문서 생성 없이 `search_similar_chunks()` 결과(출처, 텍스트 앞부분)만 출력
- **도입 이유**: `generate_draft.py`는 "문서 종류 + 프로젝트 정보" 2단 입력 구조라, 순수 검색
  품질만 확인하려는 의도로 질의 하나만 입력하면 입력값이 잘못 매칭되는 문제가 실제 발생 →
  검색 전용 테스트 경로 분리

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

## 8. 임베딩 모델 스펙 (현재: Phase 1 기준)

| 항목 | 값 |
|---|---|
| 제공사 | Voyage AI |
| 모델 | voyage-3 |
| 문서 임베딩 시 | `input_type="document"` |
| 쿼리 임베딩 시 | `input_type="query"` |
| 선택 이유 | Anthropic 공식 추천 파트너, 생태계 일관성, 학습 목적에 충분 |

Phase 3에서 Cohere embed-multilingual-v3, 한국어 특화 오픈소스(KURE-v1) 대비 비교 실험 예정
(`PLAN.md` 참조).

## 9. 알려진 한계 및 미해결 이슈

| 이슈 | 상태 |
|---|---|
| `산업안전보건관리비_가이드.txt`가 굴착 관련 질의에서 top-5 밖으로 밀림 | 미해결, Phase 3 관찰 대상 |
| `document_type` 문자열 포함 매칭 방식의 오탐 가능성 | 인지됨, 별도 개선 미착수 |
| 다중 위험성평가 기록 시 항상 최신 1건만 참조 (여러 건 종합 불가) | 설계상 의도된 단순화, 필요 시 확장 가능 |
| 위험성평가 결과가 구조화되지 않고 텍스트 원문 그대로 저장됨 | 설계상 의도된 단순화 (파싱 비용 대비 이득 낮다고 판단) |

## 10. 버전 관리

- `.gitignore` 제외 대상: `.env`, `venv/`, `__pycache__/`, `*.pyc`, `embeddings.json`, `projects/`
- **주의**: `.gitignore` 작성 전에 `git add .`를 먼저 실행하면 `venv/`가 스테이징에 남는 문제
  발생 가능 → 이 경우 `git reset`으로 스테이징만 초기화 후 재확인 필요 (실제 발생 및 해결 사례)
