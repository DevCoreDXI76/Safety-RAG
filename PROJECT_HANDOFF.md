# 안전서류 RAG(safety-rag) — 통합 핸드오프 문서

> 최종 갱신: 2026-07-09
> Phase 1~3.5 배경/상세는 `docs/PRD.md`, `docs/PLAN.md`, `docs/SPEC.md` 참고.
> 이 문서 하나로 Phase 4(텔레그램 미니앱화) + Phase 5(가입 승인 플로우 + Railway Volume) + 배포 후 디버깅 과정을 모두 다룹니다. (이전에 문서가 여러 개로 나뉘어 있었으나 이 파일로 통합, 기존 파일들은 더 이상 관리하지 않아도 됩니다.)

---

## 1. Phase별 완료 현황

| Phase | 내용 | 상태 |
|---|---|---|
| Phase 1 | RAG 파이프라인 구축 (청킹→임베딩→검색→생성) | ✅ 완료 |
| Phase 2 | 본인 검증, 지식베이스 5종 확장 | ✅ 완료 |
| Phase 3 | 임베딩 모델 비교 실험 (Voyage/Cohere/KURE-v1) → Voyage 채택 | ✅ 완료 |
| Phase 3.5 | 개인용 CLI 다듬기 (메뉴 선택, 다중 회차 선택) | ✅ 완료 |
| Phase 4 | 텔레그램 미니앱화 | ✅ MVP 완료, 검증됨 (2절) |
| Phase 5 | 가입 승인 플로우 + Railway Volume | ✅ 코드 적용 완료, 배포 후 디버깅 진행 중 (5절, 8절) |

---

## 2. Phase 4 — 텔레그램 미니앱화

### 2-1. 배경 및 결정

- 기존 CLI 도구는 텍스트 초안만 터미널에 출력되어 실사용에 불편함을 느낌
- **결정**: 텔레그램 미니앱(Telegram Mini App)으로 전환 — 데일리 리추얼 봇 프로젝트에서 Telegram Bot API + Railway + Volume 조합을 검증해둔 경험을 재활용
- **백엔드 프레임워크는 FastAPI 선택** (Flask 대비): Swagger 자동 문서화, Pydantic 스키마 검증, async 지원, Mini App 관련 레퍼런스가 FastAPI 기준으로 많음

### 2-2. 아키텍처

```
[Telegram 클라이언트]
      │ (메뉴 버튼 클릭 → Web App 오픈)
      ▼
[프론트엔드: webapp/index.html — HTML/JS + Telegram WebApp SDK]
      │ (fetch API 호출)
      ▼
[백엔드 API: FastAPI (api/)]
      │
      ▼
[기존 로직 재사용: common.py 검색, generate_draft.py 생성/저장]
```

핵심 설계 원칙: **기존 CLI 로직(common.py, generate_draft.py)을 새로 짜지 않고 그대로 재사용.** API는 이 로직을 HTTP로 감싸는 얇은 레이어로만 구현.

봇과 API는 **하나의 FastAPI 프로세스(단일 Railway 서비스)** 로 통합되어 있음 — 별도 폴링 프로세스 없음 (자세한 근거는 5-1절 참고).

### 2-3. 백엔드 API 구현 완료 내역

**`api/__init__.py`** — 빈 파일 (패키지 인식용)

**`api/main.py`** — FastAPI 앱 진입점
- CORS 미들웨어 (`allow_origins=["*"]`)
- 라우터 등록
- `StaticFiles(directory="webapp", html=True)`를 `/app` 경로에 마운트 → 프론트엔드를 API와 같은 서버에서 서빙
- `GET /` 헬스체크 엔드포인트

**`api/schemas.py`** — Pydantic 요청/응답 모델
- `DocumentTypeItem`, `DocumentTypesResponse`
- `RecordSummary`
- `ProjectSummaryResponse`
- `RiskAssessmentListResponse`
- `GenerateRequest` (document_type, project_info, project_name, risk_assessment_id)
- `GenerateResponse` (draft, saved_record_id, linked_risk_assessment_id)

**`api/routes.py`** — 엔드포인트 4개
- `GET /document-types` — 문서종류 목록
- `GET /projects/{project_name}` — 현장 기록 요약 조회
- `GET /projects/{project_name}/risk-assessments` — 위험성평가 회차 목록
- `POST /generate` — 문서 생성 (기존 `generate_document_draft()` 재사용)

**`api/telegram_auth.py`** — 텔레그램 인증 (initData HMAC 검증, 5절에서 파일 기반 방식으로 교체 예정)

### 2-4. `generate_draft.py` 리팩터링 (CLI/API 공용화)

핵심 변경: `generate_document_draft()`가 더 이상 내부에서 대화형으로 위험성평가 회차를 고르지 않고, **이미 선택된 `risk_assessment_record`를 인자로 받도록** 변경. 반환값도 `(draft, saved_record)` 튜플로 변경 (API가 저장된 레코드의 `id`를 응답에 담기 위함).

추가/변경된 함수:
- `load_project_data(project_name)` — JSON 로드
- `save_project_record(...)` — **각 레코드에 `uuid.uuid4().hex[:12]` 형태의 `id` 필드 추가** (API에서 특정 회차를 지정 조회하기 위함)
- `list_project_records(project_name)`
- `list_risk_assessments(project_name)`
- `get_record_by_id(project_name, record_id)` — API의 `risk_assessment_id`로 특정 기록 조회
- CLI 전용: `choose_document_type()`, `choose_risk_assessment()`, `show_project_summary()` — 그대로 유지, `__main__` 블록에서 사용

**마이그레이션 이슈**: 위 `id` 필드 추가 이전에 저장된 기존 레코드들에는 `id`가 없어서 API에서 특정 회차를 지정 조회할 때 404 발생 → `migrate_add_ids.py`(1회성 스크립트) 작성/실행, 기존 레코드에 일괄로 `id` 부여 완료.

### 2-5. 프론트엔드 (`webapp/index.html`)

단일 HTML 파일, 바닐라 JS + `marked.js`(CDN, 마크다운→HTML 렌더링용).

**디자인 컨셉**: 실제 안전서류의 위험등급 색상 체계(🔴🟠🟡🟢)를 앱의 시각 언어로 채택. 헤더는 명조(Noto Serif KR, 공문서 느낌), 본문은 산세리프(Noto Sans KR), 문서번호/시각은 모노스페이스(IBM Plex Mono). "공문서 대장" 스타일의 기록 리스트 UI.

**화면 구성 (섹션 순서)**:
1. 현장 — 현장명 입력 + 조회 버튼 → 기록 목록(대장 스타일)
2. 문서 종류 — 5종 카드 선택 (자유입력 "기타"는 MVP 범위에서 제외, 미구현 상태로 남음)
3. 위험성평가 연동 — TBM 선택 시에만 노출, 회차 라디오 선택 (기본값: 최근 회차 자동 선택)
4. 작업 정보 — 텍스트 입력
5. 생성 버튼 → 로딩 → 결과 (마크다운 렌더링, 복사 버튼)

**`API_BASE` 상수**: Railway 배포 후 `https://web-production-9d1bd.up.railway.app`로 변경 완료 (본인 확인함).

**텔레그램 SDK 연동**: `<script src="https://telegram.org/js/telegram-web-app.js">` 추가, JS에서 `tg.ready(); tg.expand();` 호출하여 텔레그램 안에서 열렸을 때 화면이 꽉 차게 표시되도록 처리. 브라우저 단독 실행 시엔 `window.Telegram`이 없어서 조용히 무시됨(에러 없음).

### 2-6. 로컬 테스트 (Swagger UI)

Swagger UI(`/docs`): 각 엔드포인트를 펼치기 → "Try it out" → 값 입력 → "Execute" → Response body 확인. `GET /document-types` → `GET /projects/{project_name}` → `GET /projects/{project_name}/risk-assessments` → `POST /generate` 순서로 검증 완료.

### 2-7. Railway 배포

- `Procfile`:
  ```
  web: uvicorn api.main:app --host 0.0.0.0 --port $PORT
  ```
- GitHub 저장소 연결 → Railway가 push 감지 시 자동 재배포
- **배포 도메인**: `https://web-production-9d1bd.up.railway.app`
- 환경변수(Variables 탭)에 `ANTHROPIC_API_KEY`, `VOYAGE_API_KEY` 등록 (Cohere/KURE는 프로덕션 미사용이라 생략)
- 헬스체크(`/`), Swagger(`/docs`), 프론트엔드(`/app/`) 모두 정상 동작 확인 완료

### 2-8. 텔레그램 봇 등록 및 미니앱 연동

- **BotFather로 신규 봇 생성** (데일리 리추얼 봇과 별개, safety-rag 전용)
  - 봇 이름: `안전서류 초안 생성기` / 유저네임: `@safety_rag_bot`
  - 토큰을 `.env`의 `TELEGRAM_BOT_TOKEN`에 저장
- **Menu Button 설정**: BotFather → `/mybots` → 봇 선택 → Bot Settings → Menu Button → Configure menu button
  - Web App URL: `https://web-production-9d1bd.up.railway.app/app/` / 버튼 텍스트: "서류 생성"
- **실기기 테스트 완료** (데스크톱 + 모바일 텔레그램):
  - 메뉴 버튼 클릭 → 미니앱 정상 오픈 → 현장 조회(기록 9건 표시) → TBM 선택 시 위험성평가 연동 섹션 등장 → 초안 생성(연동 내용 정확히 반영) → 복사 버튼 정상 동작

**→ Phase 4의 핵심 목표(텍스트 전용 CLI → 텔레그램 미니앱)가 실제로 달성되고 검증됨.**

---

## 3. Phase 4에서 발견하고 해결한 버그/이슈

| # | 이슈 | 원인 | 해결 |
|---|---|---|---|
| 1 | `ModuleNotFoundError: sentence_transformers` | `common.py` 최상단에서 무조건 import — Voyage만 쓰는 상황에서도 패키지 없으면 전체가 죽음 | `get_kure_model()` 함수 내부로 import 이동 (지연 로딩). Voyage 경로는 이 패키지 설치 여부와 무관해짐 |
| 2 | `POST /generate`에서 `risk_assessment_id`로 404 | 마이그레이션 이전에 저장된 기존 레코드에는 `id`가 없음 | `migrate_add_ids.py` 작성/1회 실행, 기존 레코드에 `id` 일괄 부여 |
| 3 | `webapp/index.html`을 브라우저에서 열 수 없음 (404) | FastAPI에 정적 파일 서빙 라우트가 없었음 | `api/main.py`에 `app.mount("/app", StaticFiles(directory="webapp", html=True))` 추가. **라우터를 먼저 include하고 그 뒤에 mount해야** API 경로가 정적 파일 마운트에 가로채이지 않음 |
| 4 | 생성된 위험성평가표에 현장명·공종 등 세부 정보 누락 | `project_name`이 파일 저장 용도로만 쓰이고 실제 Claude 프롬프트엔 전달 안 됨 | 프롬프트에 `site_line = f"현장명: {project_name}\n"` 추가, system prompt에도 "현장명이 있으면 반드시 채워 넣어라" 지시 추가 |
| 5 | 위험성 점수(가능성×중대성)가 매번 있다가 없다가 함 | "추측 금지" 원칙과 "위험성 점수 산정"이 상충 | system prompt에 "위험성 점수는 반드시 채우되 `(AI 제안값, 현장 확인 필수)`라고 명시하라"는 지시 추가 (제품 결정, 4절-5 참고) |
| 6 | 로컬 PC 저장공간 부담 우려 | `sentence-transformers`가 딸려오는 `torch`가 1~2GB | 실제로는 이미 삭제되어 있었음(`pip list` 확인). `requirements.txt`에서 `sentence-transformers` 제거 권고만 진행 |
| 7 | `.gitignore`에 옛 파일명(`embeddings.json`)만 있고 현재 파일명(`embeddings_voyage.json`) 언급 없음 | Phase 3 멀티모델 구조 전환 시 `.gitignore` 미갱신 | `embeddings_voyage.json`은 이미 Git 커밋 확인됨(`git ls-files`), 실질 문제 없었음. `.gitignore`에서 옛 이름 제거, 실험용 파일만 계속 제외 |
| 8 | Git pre-commit 훅이 자꾸 작동 안 함 | PowerShell로 훅 파일 생성 시 인코딩/개행문자(CRLF) 문제, 실행권한 누락, `git diff` 출력의 `\r`이 `grep` 앵커 매칭 실패시킴 | Git Bash에서 `cat > ... << 'EOF'` heredoc으로 훅 생성 + `chmod +x`. grep 로직도 `tr -d '\r'`로 정리 후 느슨하게 매칭. 실제 커밋으로 검증 완료 |

---

## 4. Phase 4 주요 기술적/제품적 결정과 이유

1. **FastAPI 채택** — Swagger 자동 문서화, Pydantic 검증, async, Mini App 생태계 친화성
2. **기존 CLI 로직 재사용** — `generate_document_draft()`를 CLI와 API가 공유. 새 로직을 만들지 않고 감싸기만 함으로써 버그 표면 최소화
3. **정적 파일도 FastAPI가 직접 서빙** — 별도 정적 호스팅 없이 단일 Railway 서비스로 API+프론트엔드 함께 배포
4. **로컬 개발 환경 유지, 무거운 의존성만 제거** — 초기 개발 단계엔 로컬 테스트가 피드백 루프가 빠름. `sentence-transformers`/`torch`처럼 프로덕션에 불필요한 패키지만 제거
5. **위험성 점수는 "AI 제안값"으로 명시 라벨링** — 완전히 빈칸(정직) vs AI가 채움(편의성) 사이에서, **후자를 택하되 "(AI 제안값, 현장 확인 필수)" 표시를 강제**. 날짜·서명 등은 여전히 추측 금지 — 위험성 점수만 예외로 명확히 구분
6. **보안: 텔레그램 initData HMAC 검증 도입** — 배포 URL 공개 시 누구나 Claude/Voyage API를 호출해 비용 발생 가능한 위험 인지, HMAC-SHA256 봇 토큰 기반 서명 검증 적용
7. **"완전 공개" 대신 "비공개 베타(소수 초대)"로 시작** — 이유: (a) API 비용이 사용자 수에 비례 증가 (b) 안전서류 도메인 특성상 검증 없는 공개는 오남용 리스크 (c) 데이터 구조가 유저별 분리 안 돼있어 같은 현장명 사용 시 데이터 섞임 (5절에서 수정)
8. **가입 승인은 텔레그램 봇 자체 안에서 처리** (Railway 콘솔에 매번 안 들어가도 되도록) — 관리자에게 텔레그램 메시지로 승인 요청, 인라인 버튼([승인]/[거절])으로 허용 목록 자동 등록
9. **일일 사용량 제한: 인당 5회** — `api/access_control.py`의 `DAILY_LIMIT` 상수로 조정 가능 (코드 변경이므로 git push는 필요)
10. **지속 저장소는 Railway Volume + JSON 파일 유지** (별도 DB 도입 안 함) — "학습 목적, 가벼운 구조 유지" 철학과 일관
11. **Git pre-commit 훅으로 "지식베이스 수정 후 재빌드 깜빡함" 방지** — Windows에서는 PowerShell보다 **Git Bash로 훅 파일을 만들어야** 인코딩/줄바꿈 문제 없음
12. **같은 pre-commit 훅에 "인용 검증 스크립트 실행 리마인더" 추가** (Phase 6, 표준작업계획서 굴착작업 법령 검토 후) — `표준작업계획서_법정별표.txt`, `generate_draft.py`, `common.py` 중 하나라도 staged면 `python test_worktype_citations.py` 실행을 안내. 임베딩 체크와 달리 **하드 블록이 아닌 안내만**(API 비용 발생 스크립트를 pre-commit에서 강제 실행시키지 않기 위함)

---

## 5. 진행 중: 가입 승인 플로우 + Railway Volume

### 5-1. 지금까지 확정/완료된 것

- **Railway Volume 연결 완료** — 유일한 서비스인 `web`(봇+API가 한 프로세스)에 Attach Volume, mount path `/data`. `RAILWAY_VOLUME_MOUNT_PATH`, `RAILWAY_VOLUME_NAME` 환경변수 자동 주입 확인됨.
- **데이터 경로 방식 확정**: `RAILWAY_VOLUME_MOUNT_PATH` 자동 주입 값을 그대로 사용하기로 결정 (Variables 탭에 수동으로 값 넣을 필요 없음, 오타/누락 리스크 제거).
- **아키텍처 확정: 웹훅(webhook) 방식** (폴링 아님). 근거:
  - `Procfile`이 `uvicorn api.main:app`만 실행 — 별도 폴링 루프 프로세스 없음
  - 파일 구조 어디에도 `bot.py`/폴링 스크립트 없음, 기존 봇 역할은 "메뉴 버튼 → 미니앱 오픈"뿐(서버 로직 불필요)
  - `/start` 및 승인 콜백은 이번에 처음 추가되는 기능이며 `api/webhook.py` + `set_webhook()` 기반 웹훅으로 설계 — 봇과 API가 하나의 FastAPI 프로세스로 완전 통합되므로 Volume도 서비스 1개에만 붙이면 충분
  - (참고) "폴링 아키텍처라서 Railway 선택"이라는 메모는 별개 프로젝트인 데일리 리추얼 봇(매일 밤 선제적으로 메시지를 보내야 하는 구조) 관련일 가능성이 높음. safety-rag는 사용자가 먼저 메시지를 보내야 반응하는 구조라 웹훅이 자연스럽게 맞음
- **`API_BASE`가 Railway 도메인으로 정상 반영됨** 확인 완료

### 5-2. 적용된 코드 (✅ 1~9번 전부 적용 완료)

> 적용 과정에서 발견된 버그와 추가 수정 사항은 8절 참고.

1. **`common.py`에 `DATA_DIR` 추가**
   ```python
   import os
   DATA_DIR = os.environ.get("RAILWAY_VOLUME_MOUNT_PATH", "./data")
   os.makedirs(DATA_DIR, exist_ok=True)
   ```
   로컬 개발 시엔 `./data` 하위 폴더에 자동으로 떨어지고(`.gitignore`에 `data/` 추가 권장), Railway에서는 `/data`로 자동 매핑됨.

2. **`generate_draft.py`를 `user_id` 인식하도록 리팩터링**
   - 저장 경로를 `{DATA_DIR}/projects/{현장명}.json` → `{DATA_DIR}/projects/{user_id}/{현장명}.json`으로 변경 (다중 사용자 데이터 격리)
   - `load_project_data`, `save_project_record`, `list_project_records`, `list_risk_assessments`, `get_record_by_id`, `generate_document_draft` 전부 `user_id` 파라미터 추가

3. **`api/telegram_bot.py` (신규)** — `send_message`, `answer_callback_query`, `edit_message_text`, `approve_reject_keyboard`, `set_webhook` 함수. `requests` 라이브러리 사용 (requirements.txt에 추가 필요)

4. **`api/access_control.py` (신규)** — `allowed_users.json`(승인 목록), `pending_requests.json`(대기 목록) 파일 기반 관리. `is_allowed`, `add_allowed_user`, `is_pending`, `add_pending_request`, `remove_pending_request`. `ADMIN_TELEGRAM_USER_ID`(관리자는 항상 허용), `DAILY_LIMIT = 5` 상수도 이 파일에 정의.
   - ⚠️ **동시성 주의**: 여러 사용자가 거의 동시에 `/start`를 보내면 JSON 파일에 동시 쓰기가 발생할 수 있음 → `threading.Lock`으로 파일 쓰기 구간을 감싸서 저장 (별도 라이브러리 불필요, 1인개발 규모엔 이 정도로 충분)

5. **`api/rate_limit.py`** — `DATA_DIR` 반영 + `access_control.py`의 `DAILY_LIMIT` 참조. `usage_log.json`에 인당 하루 사용 횟수 기록
   - ⚠️ **시간대 주의**: "하루" 기준을 명시적으로 **KST(한국 시간)** 로 고정할 것. Railway 서버는 기본 UTC라, 이 처리를 안 하면 자정 리셋이 실제로는 한국시간 오전 9시에 일어나 사용자가 헷갈릴 수 있음

6. **`api/telegram_auth.py` 수정** — 기존 "환경변수 허용 목록" 방식에서 `access_control.is_allowed()`(파일 기반) 방식으로 변경

7. **`api/webhook.py` (신규)** — `POST /telegram/webhook` 엔드포인트
   - `message`(예: `/start`) 수신 시: 이미 승인됐으면 안내, 대기 중이면 대기 안내, 처음이면 대기 목록 등록 + 관리자에게 승인/거절 인라인 버튼과 함께 알림 전송
   - `callback_query`(승인/거절 버튼 클릭) 수신 시: 클릭한 사람이 관리자인지 확인 → 승인이면 허용 목록 추가 + 신청자에게 알림, 거절이면 신청자에게 알림
   - 텔레그램이 보내는 `X-Telegram-Bot-Api-Secret-Token` 헤더로 웹훅 요청 자체의 진위 검증

8. **`api/main.py` 수정** — `webhook_router` include, `@app.on_event("startup")`에서 `set_webhook()` 자동 호출 (서버 시작 시 텔레그램에 웹훅 URL 자동 등록)

9. **`api/routes.py` 수정** — 각 엔드포인트가 `telegram_user: dict = Depends(require_telegram_auth)`에서 얻은 실제 검증된 `user_id`를 `generate_draft.py` 함수 호출 시 전달 (프론트엔드가 임의로 `user_id`를 조작할 수 없도록)

### 5-3. Railway 설정

- **Volume**: ✅ 완료 (`web` 서비스, mount path `/data`)
- **환경변수 등록 완료**: `ADMIN_TELEGRAM_USER_ID`, `TELEGRAM_WEBHOOK_SECRET`, `PUBLIC_APP_URL=https://web-production-9d1bd.up.railway.app`, `TELEGRAM_BOT_TOKEN`
  - ⚠️ `TELEGRAM_BOT_TOKEN`은 처음엔 로컬 `.env`에만 있고 Railway엔 없어서 누락되었던 것을 뒤늦게 발견/등록함. `TELEGRAM_WEBHOOK_SECRET`도 처음 값에 텔레그램이 허용 안 하는 문자가 섞여 있어 재발급함. 자세한 경위는 8-1절 참고
  - `DATA_DIR`은 자동 주입되는 `RAILWAY_VOLUME_MOUNT_PATH`를 코드에서 직접 참조하므로 별도 등록 불필요 (계획대로)
- **환경변수 제거 완료**: 기존 `ALLOWED_TELEGRAM_USER_ID`/`ALLOWED_TELEGRAM_USER_IDS` 삭제

### 5-4. 테스트 절차

1. ✅ 배포 후 웹훅 정상 등록 확인 (`getWebhookInfo`로 확인, 등록 과정에서 겪은 이슈는 8-1절)
2. ✅ 관리자 계정 — `ADMIN_TELEGRAM_USER_ID` 덕분에 승인 절차 없이 바로 미니앱 사용 가능함을 확인. 메뉴 버튼으로 미니앱 오픈도 Phase 4와 동일하게 정상 동작
3. ⬜ 다른 텔레그램 계정으로 봇 링크(`https://t.me/safety_rag_bot`) 접속 → `/start` 전송 — **다음에 이어서 할 것**
4. ⬜ 그 계정에 "사용 신청이 접수되었습니다" 메시지가 오는지 확인
5. ⬜ 관리자(본인) 계정에 "📩 새 사용 신청" + [승인][거절] 버튼 메시지가 오는지 확인
6. ⬜ [승인] 클릭 → 신청자에게 "✅ 승인되었습니다!" 메시지가 가는지, 그 사람이 메뉴 버튼으로 미니앱을 실제로 열 수 있는지 확인
7. ⬜ 데이터 격리 확인 — 관리자 계정과 승인된 계정이 같은 현장명으로 각각 기록을 만들었을 때 서로 안 섞이는지 (이번 `user_id` 리팩터링의 핵심 동기였던 버그)
8. ⬜ Volume 영속성 확인 — 테스트 기록이 있는 상태에서 재배포(`git commit --allow-empty` 등) 후에도 기록이 남아있는지
9. △ 하루 5회 사용량 제한 — 관리자는 예외 처리를 적용해 무제한으로 바꿈(8-3절 표 6번). 일반 승인 사용자 기준 제한이 실제로 걸리는지는 아직 미확인 (선택, 급하지 않음)

### 5-5. 그 외 남은 작업 (우선순위 낮음, 참고용)

- `PRD.md` 갱신 — "타깃 사용자"를 "나 혼자" → "초대받은 소수(비공개 베타)"로 수정
- `PLAN.md`/`SPEC.md`에 Phase 4 상세 내역 반영 (이 문서를 소스로 활용 가능)
- 프론트엔드 "기타(직접 입력)" 문서종류 옵션 — MVP 범위에서 제외했던 것, 필요시 추가
- 결과 다운로드/편집 기능 — 현재는 복사 버튼만 있음
- 텔레그램 테마 색상 연동(`tg.themeParams`) — 현재는 고정 색상, 선택적 개선사항

---

## 6. 배포 후 디버깅 — 웹훅 등록부터 위험성평가표 리트리벌 버그까지

5절의 코드를 적용하고 실제로 테스트해보는 과정에서 겪은 문제들과 원인 진단 과정을 정리합니다. 특히 4번(위험성평가표 부실 문제)은 여러 차례 잘못된 가설을 거쳐 원인을 좁혀나간 과정이라, 나중에 비슷한 증상이 재발하면 이 표부터 참고하면 좋습니다.

| # | 증상 | 기각된 가설 | 실제 원인 | 해결 |
|---|---|---|---|---|
| 1 | `getWebhookInfo` 결과 `url`이 빈 문자열 — 웹훅이 텔레그램에 등록 안 됨 | — | Railway 로그에서 `set_webhook` 결과 `404 Not Found` 확인 → `TELEGRAM_BOT_TOKEN`이 로컬 `.env`에만 있고 **Railway Variables에는 등록된 적이 없었음** (로컬 `.env`와 Railway Variables는 완전히 분리된 저장소) | Railway Variables에 `TELEGRAM_BOT_TOKEN` 신규 등록 |
| 2 | 토큰 등록 후 `set_webhook`이 `400 Bad Request: secret token contains unallowed characters` | — | `TELEGRAM_WEBHOOK_SECRET` 값에 `+`, `/`, `=` 등 텔레그램이 허용하지 않는 문자가 포함됨 (base64 계열 생성 방식이 원인). 텔레그램 secret_token은 영문 대소문자·숫자·`-`·`_`만 허용 | `python -c "import secrets; print(secrets.token_urlsafe(32))"`로 재생성 후 교체 |
| 3 | 위험성평가표 생성이 문장 중간에 끊김 | — | `max_tokens=4000`으로는 표+감소대책까지 합친 분량을 감당 못함 | `max_tokens`를 8192로 상향 |
| 4 | 끊김은 해결됐지만 결과 내용이 "부실" — 위험성 점수가 거의 6점/4점 두 값에만 몰리고, 감소대책에 `[제거/대체][공학적][관리적][보호구]` 라벨이 없음 | ① 지식베이스 파일에 남아있던 "테스트용 임시 문장" 오염이 원인일 것 → 오염 위치(8번 항목, 파일 맨 끝)가 문제되는 섹션(3번 척도, 4번 우선순위)과 무관해 기각 ② `embeddings_voyage.json` 미재생성이 원인일 것 → `git log`로 확인해보니 문제되는 섹션 텍스트는 애초에 한 번도 변경된 적이 없어 임베딩도 처음부터 정확했음, 기각 | 검색 로그(`[search] 파일명 (유사도점수)`)를 직접 찍어서 확인한 결과: **`top_k=5`가 knowledge_base 5개 파일 전체를 대상으로 무차별 유사도 검색**을 하다 보니, "3. 위험성 추정 기준"·"4. 위험성 감소대책 우선순위"처럼 정의·규정 성격의 건조한 텍스트가 다른 파일들의 서술형 "현장 특화 예시" 청크들에 밀려 top_5 밖으로 빠져나감 | `document_type`이 "위험성평가표"일 때는 `위험성평가_실시규정.txt`를 유사도 검색 대상에서 제외하고, **파일 전체를 프롬프트에 그대로 포함**하도록 리트리벌 로직 변경. 검색 로그로 재확인 → 결과물에서 1~5점 척도·라벨링 정상 복원까지 확인 완료 |
| 5 | 위험성 점수 구간 표기에서 물결표(`~`) 일부 누락 (`1~4`, `5~9`가 `14`, `59`로 붙어서 출력) | — | system prompt에 구간 표기 형식에 대한 지시가 없었음 | system prompt에 "숫자 구간 표기 시 물결표(~)를 절대 생략하지 마" 지시 추가 (적용 후 재검증은 다음 생성 때 확인 예정) |
| 6 | 디버깅 중 관리자 계정이 "오늘 사용 가능한 횟수를 모두 사용했습니다"에 걸림 | — | 반복 테스트로 관리자 본인이 일일 5회 제한을 소진 | `rate_limit.py`에서 `user_id == ADMIN_TELEGRAM_USER_ID`면 제한 체크를 건너뛰도록 예외 처리 추가 |

### 6-1. 보안 사고 기록 — 봇 토큰 노출

`getWebhookInfo` 확인용 URL을 채팅에 그대로 붙여넣으면서 `TELEGRAM_BOT_TOKEN` 원본이 노출된 적 있음. 즉시 BotFather에서 토큰 재발급(Revoke)하고 Railway Variables도 새 토큰으로 교체 완료.

**향후 원칙**: 토큰·시크릿이 URL에 포함된 API 응답을 공유할 때는 토큰 부분을 `<TOKEN>`으로 가리고, 결과(성공/실패 여부, 에러 메시지)만 전달할 것.

### 6-2. 이번 디버깅에서 얻은 원칙 (SPEC.md 반영 권장)

> **규정성 문서는 검색이 아니라 전체 포함**: 척도표·우선순위 정의처럼 "정의/규정" 성격의 텍스트는 특정 현장 쿼리와 문장 구조가 안 맞아 유사도 검색에서 밀리기 쉽다. 이런 문서는 `document_type`별로 검색 없이 파일 전체를 프롬프트에 포함시키는 방식이 안전하다. (지식베이스 파일을 앞으로 추가할 때 — 예: "기타" 문서종류 — 이 원칙을 먼저 검토할 것)

> **로컬 `.env`와 Railway Variables는 완전히 분리된 저장소**: 로컬에서 동작 확인이 됐다고 Railway에도 그 환경변수가 있다고 가정하면 안 됨. 코드에 새 환경변수를 추가할 때마다 Railway Variables 등록 여부를 체크리스트에 넣을 것.

### 6-3. 현재 상태

위 문제들을 해결한 뒤 강남지사_광케이블 현장으로 위험성평가표를 재생성해 최종 검증 완료 — 1~5점 척도, `[제거/대체][공학적][관리적][보호구]` 라벨링, 4~15점의 다양한 점수 분포까지 모두 정상. 다음으로 이어갈 것은 5-4절 테스트 절차의 3번(다른 텔레그램 계정으로 미승인 사용자 흐름)부터입니다.

---

## 7. 현재 파일/코드 구조 전체

```
safety-rag/
├── .env                          (Git 제외 — ANTHROPIC_API_KEY, VOYAGE_API_KEY, TELEGRAM_BOT_TOKEN 등)
├── .gitignore                    (data/ 추가 권장 — DATA_DIR 로컬 폴백 경로)
├── requirements.txt
├── Procfile                      (Railway 배포용 — uvicorn 실행 명령)
├── common.py                     (청킹, 멀티모델 임베딩 라우팅, 코사인 유사도 검색, DATA_DIR 정의 예정)
├── build_knowledge_base.py       (--model {voyage|cohere|kure} 인자 지원)
├── generate_draft.py             (문서 생성 핵심 로직 — CLI/API 공용, user_id 인식, document_type별 지식베이스 전체 포함 로직 포함)
├── test_search.py                (--model 인자 지원, 검색 품질 단독 테스트)
├── test_worktype_citations.py    (Phase 6 추가 — 표준작업계획서 작업유형별 인용 검증 회귀 테스트, API 비용 발생하는 온디맨드 스크립트)
├── migrate_add_ids.py            (1회성 스크립트, 이미 실행 완료 — 재실행해도 안전)
├── embeddings_voyage.json        (Git 포함 — 프로덕션 검색 인덱스)
├── embeddings_cohere.json        (Git 제외 — Phase 3 실험용, 현재 안 씀)
├── embeddings_kure.json          (Git 제외 — Phase 3 실험용, 현재 안 씀)
├── knowledge_base/
│   ├── 위험성평가_실시규정.txt
│   ├── TBM_서식.txt
│   ├── 안전보건교육_가이드.txt
│   ├── 산업안전보건관리비_가이드.txt
│   └── 표준작업계획서_가이드.txt
├── projects/                     (Git 제외 — 현장별 생성 기록, {DATA_DIR}/projects/{user_id}/{현장명}.json 구조로 적용됨)
├── usage_log.json                (Git 제외 — 인당 하루 사용 횟수 기록, 관리자는 예외 처리로 무제한)
├── api/
│   ├── __init__.py
│   ├── main.py                   (FastAPI 앱, CORS, 라우터 등록, 정적파일 마운트 /app, webhook_router include, startup 시 set_webhook 자동 호출)
│   ├── routes.py                 (4개 엔드포인트, require_telegram_auth로 검증된 user_id 전달)
│   ├── schemas.py                (Pydantic 모델)
│   ├── telegram_auth.py          (initData HMAC 검증, access_control.is_allowed() 파일 기반 방식 적용)
│   ├── telegram_bot.py           (send_message, answer_callback_query, edit_message_text, approve_reject_keyboard, set_webhook)
│   ├── access_control.py         (allowed_users.json/pending_requests.json 관리, ADMIN_TELEGRAM_USER_ID 예외, DAILY_LIMIT=5)
│   ├── rate_limit.py             (일일 사용량 체크, 관리자 예외 처리 적용됨)
│   └── webhook.py                (POST /telegram/webhook — message/callback_query 처리, X-Telegram-Bot-Api-Secret-Token 검증)
├── webapp/
│   └── index.html                (프론트엔드 단일 파일 — API_BASE는 Railway 도메인)
├── docs/
│   ├── PRD.md
│   ├── PLAN.md
│   └── SPEC.md
└── (Git 훅) .git/hooks/pre-commit  (knowledge_base 수정 시 embeddings_voyage.json 동반 커밋 강제 + Phase 6부터 표준작업계획서_법정별표.txt/generate_draft.py/common.py 변경 시 test_worktype_citations.py 실행 안내)
```

### 로컬 개발 환경 참고사항

- Python 3.11.9, `venv` 가상환경
- PowerShell 활성화: `venv\Scripts\Activate.ps1` / Git Bash 활성화: `source venv/Scripts/activate` (경로 구분자 다름 주의)
- pip는 `py -m pip install` 사용 (PowerShell 경로 이슈 회피)
- VS Code + venv, Pylance 임포트 경고는 `Python: Select Interpreter`로 venv 선택해서 해결
- `sentence-transformers`/`torch`는 현재 설치되어 있지 않음 — `common.py`의 `get_kure_model()` 내부에서 지연 import하므로 없어도 Voyage 경로는 문제없음
- Git 훅은 **Git Bash로 생성해야** 인코딩/줄바꿈 문제가 없음 (PowerShell로 만들면 깨질 수 있음)
- 완성된 파일은 부분 diff보다 전체 내용으로 받는 걸 선호

### 배포/외부 서비스 정보

| 항목 | 값 |
|---|---|
| Railway 배포 도메인 | `https://web-production-9d1bd.up.railway.app` |
| 텔레그램 봇 유저네임 | `@safety_rag_bot` |
| 미니앱 진입 경로 | `/app/` |
| Railway Volume | ✅ 완료 — `web` 서비스에 `/data`로 마운트 |
| 데이터 경로 방식 | `RAILWAY_VOLUME_MOUNT_PATH` 자동 주입 값 사용 (확정) |
| 봇 아키텍처 | 웹훅 방식 (확정, 폴링 아님) |
| 텔레그램 웹훅 | ✅ 완료 — 등록 과정에서 겪은 이슈는 6-1절 참고 |

---

## 8. Claude Code에서 시작할 때 이렇게 말씀하시면 됩니다

> "이 핸드오프 문서 읽고, 5-4절 테스트 절차 3번(다른 텔레그램 계정으로 미승인 사용자 흐름)부터 이어서 진행해줘. 6절에 지금까지 겪은 버그/원인 정리돼 있으니 참고해줘."

라고 하시면서 이 파일을 프로젝트 루트에 두고 시작하시면 됩니다. 5절 코드(①~⑨)는 이미 전부 적용 완료 상태이고, 6절에 배포 후 실제로 겪은 버그와 원인 진단 과정이 정리되어 있으니 비슷한 증상이 재발하면 거기부터 참고하면 됩니다.
