# PHASE 5 — 가입 승인 플로우 + Railway Volume (설계·구현 계획)

> Technical Design & Implementation Plan
> 최종 업데이트: 2026-07-08
> 이 문서는 `PROJECT_HANDOFF.md` 5절("진행 중: 가입 승인 플로우 + Railway Volume") 내용에,
> 코드 착수 전 실제 파일 대조 검증 결과와 파일 단위 구현 계획을 더해 종합한 Phase 5 전용
> 상세 설계 문서다. `PRD.md`/`PLAN.md`/`SPEC.md`에는 이 문서의 요약만 반영되어 있고, 실제
> 구현 시 참고할 상세 스펙(함수 시그니처, 파일 경로, 알고리즘)은 이 문서를 기준으로 한다.

---

## 1. 배경 및 목표

Phase 4에서 텔레그램 미니앱화(CLI → 웹 UI 전환)는 실기기 테스트까지 완료해 검증됐다. 다만
배포 URL과 봇 링크가 공개된 상태에서 다음 세 가지 리스크가 있다 (`PROJECT_HANDOFF.md` 4절-7):

1. API 비용이 사용자 수에 비례해 증가한다 (Claude/Voyage 호출)
2. 안전서류 도메인 특성상 검증 없는 완전 공개는 오남용 리스크가 있다
3. 데이터 구조가 유저별로 분리되어 있지 않아, 같은 현장명을 쓰면 서로 다른 사용자의 기록이
   섞인다

**목표**: "완전 공개" 대신 **비공개 베타(소수 초대)** 로 전환한다. 구체적으로:

- 텔레그램 봇을 통한 자체 가입 승인 플로우(관리자가 인라인 버튼으로 승인/거절)
- 사용자별 데이터 격리 (`user_id` 기준 저장소 분리)
- 인당 일일 사용량 제한 (기본 5회)
- Railway Volume을 이용한 영구 저장소 확보 (재배포 시 데이터 유실 방지)

---

## 2. 확정된 아키텍처 결정

이미 확정되어 별도 재논의가 필요 없는 사항들 (`PROJECT_HANDOFF.md` 5-1절 근거 유지):

| 결정 | 내용 | 근거 |
|---|---|---|
| Railway Volume | 유일한 서비스 `web`(봇+API 통합 프로세스)에 Attach, mount path `/data`. `RAILWAY_VOLUME_MOUNT_PATH` 자동 주입 확인됨 | 재배포 시 데이터 유실 방지 |
| 데이터 경로 방식 | `RAILWAY_VOLUME_MOUNT_PATH` 자동 주입 값을 코드에서 직접 참조 (Variables 탭 수동 입력 안 함) | 오타/누락 리스크 제거 |
| 봇 아키텍처 | **웹훅(webhook) 방식** (폴링 아님) | `Procfile`이 `uvicorn api.main:app` 단일 프로세스만 실행하고, 폴링 루프 스크립트가 원래 없었음. `/start`·승인 콜백은 이번에 신규 추가되는 기능이라 웹훅이 자연스러움. (참고: "폴링이라 Railway를 썼다"는 메모는 별개 프로젝트인 데일리 리추얼 봇 — 매일 밤 선제적 발송이 필요한 구조 — 관련일 가능성이 높고, safety-rag는 사용자가 먼저 메시지를 보내야 반응하는 구조라 무관) |
| 봇/API 프로세스 통합 | 하나의 FastAPI 프로세스로 완전 통합, Volume도 서비스 1개에만 부착 | 별도 폴링 프로세스가 없으므로 분리할 이유 없음 |

---

## 3. 착수 전 코드 현황 검증 결과 (2026-07-08)

실제 구현에 들어가기 전, `PROJECT_HANDOFF.md`가 설명하는 현재 코드 상태가 실제 파일과
일치하는지 전수 대조했다. 대부분 일치했으나 **한 가지 중요한 불일치**를 발견했다.

| 항목 | 문서 설명 | 실제 상태 |
|---|---|---|
| `common.py`의 `DATA_DIR` | 미적용 (계획만 있음) | ✅ 일치 — 없음 |
| `generate_draft.py` 구조 (`risk_assessment_record` 인자, `(draft, saved_record)` 튜플 반환, `id` 필드) | 리팩터링 완료 | ✅ 일치 |
| `generate_draft.py`의 `user_id` 인식 | 미적용 (계획만 있음) | ✅ 일치 — 저장 경로는 여전히 `projects/{현장명}.json`, 어떤 함수도 `user_id`를 받지 않음 |
| **`api/telegram_auth.py`** | "기존 파일 — initData HMAC 검증 구현되어 있음, 파일 기반 방식으로 **교체 예정**" | ❌ **불일치 — 파일 자체가 존재하지 않는다.** API 레이어에 인증 로직이 전혀 없고 `routes.py`의 모든 엔드포인트가 인증 없이 열려 있음 |
| `api/main.py`, `routes.py`, `schemas.py` | 문서 설명대로 | ✅ 일치 |
| `api/telegram_bot.py`, `access_control.py`, `rate_limit.py`, `webhook.py` | 아직 없음 (예정) | ✅ 일치 |
| `requirements.txt`의 `requests` | (문서에 명시 없음이지만 `telegram_bot.py` 구현에 필요) | ❌ 없음 — 추가 필요 |
| `.gitignore`의 `data/` | 권장 (미적용) | ✅ 일치 |
| `projects/` 데이터의 `id` 필드 | 마이그레이션 완료 | ✅ 일치 — 확인됨, `user_id` 필드는 당연히 아직 없음 |

**시사점**: 4번-⑥(`api/telegram_auth.py` 수정)은 "기존 파일 교체"가 아니라 **처음부터 새로
작성**해야 한다 (initData HMAC 검증 + `access_control.is_allowed()` 연동을 한 번에 구현).
나머지 항목은 문서 설명이 정확하므로 그대로 진행한다.

---

## 4. 구현 계획 — 파일별 상세 스펙

### ① `common.py` — `DATA_DIR` 추가

```python
DATA_DIR = os.environ.get("RAILWAY_VOLUME_MOUNT_PATH", "./data")
os.makedirs(DATA_DIR, exist_ok=True)
```

로컬 개발 시엔 `./data` 하위에 자동 생성되고, Railway에서는 `/data`로 자동 매핑된다.

### ② `generate_draft.py` — `user_id` 인식 리팩터링

- `PROJECTS_DIR = os.path.join(DATA_DIR, "projects")` (기존 `PROJECTS_DIR = "projects"`에서 변경)
- 저장 경로: `{DATA_DIR}/projects/{user_id}/{현장명}.json` (기존 `{DATA_DIR}/projects/{현장명}.json`에서 변경 — 다중 사용자 데이터 격리)
- `user_id` 파라미터 추가 대상: `load_project_data`, `save_project_record`, `list_project_records`,
  `list_risk_assessments`, `get_record_by_id`, `generate_document_draft`
- CLI(`__main__`) 하위 호환: `CLI_USER_ID = "cli_local"` 고정값을 정의해 CLI 실행 시 이 값을
  `user_id`로 사용 (터미널 사용자는 텔레그램 계정이 없으므로)

### ③ `api/telegram_bot.py` (신규)

텔레그램 Bot API 호출 헬퍼를 모아둔 모듈. `requests` 라이브러리 사용.

- `send_message(chat_id, text, reply_markup=None)`
- `edit_message_text(chat_id, message_id, text, reply_markup=None)`
- `answer_callback_query(callback_query_id, text=None)`
- `approve_reject_keyboard(user_id)` — `callback_data`를 `approve:{user_id}` / `reject:{user_id}` 형식으로 인코딩한 인라인 키보드 반환
- `set_webhook()` — `PUBLIC_APP_URL` + `/telegram/webhook`을 텔레그램에 등록, `TELEGRAM_WEBHOOK_SECRET`을 `secret_token`으로 전달

### ④ `api/access_control.py` (신규)

파일 기반 승인/대기 목록 관리.

- 저장 파일: `{DATA_DIR}/allowed_users.json`, `{DATA_DIR}/pending_requests.json`
- 함수: `is_allowed(user_id)`, `add_allowed_user(user_id, username=None)`, `is_pending(user_id)`,
  `add_pending_request(user_id, username=None, first_name=None)`, `remove_pending_request(user_id)`
- 상수: `ADMIN_TELEGRAM_USER_ID`(환경변수에서 로드, 관리자는 `is_allowed`에서 항상 `True`),
  `DAILY_LIMIT = 5`
- ⚠️ **동시성 주의**: 여러 사용자가 거의 동시에 `/start`를 보내면 JSON 파일 동시 쓰기가
  발생할 수 있음 → 파일 읽기/쓰기 구간을 `threading.Lock`으로 감싼다 (1인 개발 규모엔
  별도 라이브러리 없이 이 정도로 충분)

### ⑤ `api/rate_limit.py` (신규)

- 저장 파일: `{DATA_DIR}/usage_log.json`
- `access_control.DAILY_LIMIT` 참조
- `check_and_increment(user_id) -> bool` — 사용 가능하면 카운트 증가 후 `True`, 한도 초과 시 `False`
- `get_usage_count(user_id) -> int`
- ⚠️ **시간대 주의**: "하루" 기준을 **KST(한국 시간)** 로 명시 고정 (`timezone(timedelta(hours=9))`
  사용, 외부 tz 데이터베이스 의존 없이 처리). Railway 서버는 기본 UTC라 이 처리를 안 하면
  자정 리셋이 실제로는 한국 시간 오전 9시에 일어나 사용자가 혼란스러울 수 있음

### ⑥ `api/telegram_auth.py` (신규 — 문서는 "수정"이라 했지만 실제로는 새로 작성)

텔레그램 공식 initData 검증 알고리즘 구현:

1. `initData` 쿼리 문자열을 파싱, `hash` 필드 분리
2. 나머지 필드를 `key=value` 형태로 정렬해 `\n`으로 join한 `data_check_string` 생성
3. `secret_key = HMAC_SHA256(key="WebAppData", msg=봇토큰)`
4. `computed_hash = HMAC_SHA256(key=secret_key, msg=data_check_string)`
5. `computed_hash`와 수신한 `hash`를 `hmac.compare_digest`로 비교

- `verify_init_data(init_data: str) -> dict` — 검증 통과 시 파싱된 필드 반환, 실패 시 예외
- `require_telegram_auth(x_telegram_init_data: str = Header(...)) -> dict` — FastAPI `Depends`용.
  검증 → `user` 필드 파싱 → `access_control.is_allowed(user_id)` 확인(미승인 시 403) →
  `{"user_id", "username", "first_name"}` 반환

### ⑦ `api/webhook.py` (신규)

`POST /telegram/webhook` 엔드포인트.

- 요청 헤더 `X-Telegram-Bot-Api-Secret-Token`이 `TELEGRAM_WEBHOOK_SECRET`과 일치하는지 검증
  (불일치 시 401)
- `message`(`/start`) 수신 시: 이미 승인됨 → 안내 / 대기 중 → 안내 / 처음 → 대기 목록 등록 +
  관리자에게 `approve_reject_keyboard`와 함께 알림 전송
- `callback_query`(승인/거절 버튼) 수신 시: 클릭자가 관리자인지 확인 → 승인이면 허용 목록
  추가 + 신청자 알림, 거절이면 신청자 알림, 어느 쪽이든 관리자 메시지를 `edit_message_text`로
  갱신하고 `answer_callback_query`로 로딩 스피너 해제

### ⑧ `api/main.py` 수정

- `from api.webhook import webhook_router` + `app.include_router(webhook_router)`
- `@app.on_event("startup")`에서 `set_webhook()` 자동 호출 (서버 기동 시 텔레그램에 웹훅
  URL 자동 등록, 수동 등록 불필요)

### ⑨ `api/routes.py` 수정

- 4개 엔드포인트 모두 `telegram_user: dict = Depends(require_telegram_auth)` 추가
- `telegram_user["user_id"]`를 `generate_draft.py` 함수 호출 시 전달 (프론트엔드가 임의로
  `user_id`를 조작할 수 없도록 — body/쿼리로 받지 않고 검증된 값만 사용)
- `POST /generate`에 `rate_limit.check_and_increment(user_id)` 적용, 초과 시 429 반환

### ⑩ `webapp/index.html` 수정 — **문서 5-2절에 없던 필수 보완사항**

문서 5-2절 어디에도 프론트엔드 변경이 언급되지 않지만, ⑨에서 `Depends(require_telegram_auth)`를
걸면 프론트엔드가 `X-Telegram-Init-Data` 헤더를 보내지 않는 한 모든 API 호출이 401로 막힌다.
따라서 모든 `fetch()` 호출에 `Telegram.WebApp.initData` 값을 `X-Telegram-Init-Data` 헤더로
추가하는 수정이 반드시 함께 필요하다. **⑨과 ⑩은 반드시 같은 배포에 묶어서 반영한다** —
따로 배포하면 그 사이에 미니앱이 즉시 깨진다.

### 그 외

- `requirements.txt`에 `requests` 추가
- `.gitignore`에 `data/` 추가

---

## 5. Railway 설정 변경사항

- **Volume**: ✅ 완료 (`web` 서비스, mount path `/data`)
- **환경변수 추가 필요**: `ADMIN_TELEGRAM_USER_ID`(본인 텔레그램 ID), `TELEGRAM_WEBHOOK_SECRET`(임의의 긴 문자열), `PUBLIC_APP_URL=https://web-production-9d1bd.up.railway.app`
  (`DATA_DIR`은 자동 주입되는 `RAILWAY_VOLUME_MOUNT_PATH`를 코드에서 직접 참조하므로 별도 추가 불필요)
- **환경변수 제거**: 기존 `ALLOWED_TELEGRAM_USER_ID`/`ALLOWED_TELEGRAM_USER_IDS` (파일 기반 방식으로 대체되어 불필요)

---

## 6. 테스트 절차 (미실행)

1. 배포 후 Railway 로그에서 웹훅이 정상 등록됐는지 확인
2. 본인 계정(관리자)은 `ADMIN_TELEGRAM_USER_ID` 덕분에 바로 미니앱 사용 가능한지 확인
3. 다른 텔레그램 계정으로 봇 링크(`https://t.me/safety_rag_bot`) 접속 → `/start` 전송
4. 그 계정에 "사용 신청이 접수되었습니다" 메시지가 오는지 확인
5. 관리자(본인) 계정에 "📩 새 사용 신청" + [승인][거절] 버튼 메시지가 오는지 확인
6. [승인] 클릭 → 신청자에게 "✅ 승인되었습니다!" 메시지가 가는지, 그 사람이 메뉴 버튼으로
   미니앱을 실제로 열 수 있는지 확인
7. 하루 5회 사용량 제한이 실제로 걸리는지 확인 (선택 사항, 급하지 않음)

**참고**: 인증이 걸리면 Swagger UI(`/docs`)로는 더 이상 엔드포인트를 직접 테스트할 수 없다
(`X-Telegram-Init-Data` 헤더를 Swagger에서 만들 수 없음). 위 실기기 테스트가 사실상 유일한
검증 경로가 된다.

---

## 7. 남은 작업 (우선순위 낮음, 참고용)

- `PRD.md` "타깃 사용자" — "나 혼자" → "초대받은 소수(비공개 베타)" (이번 문서 작업에서 반영)
- 기존 `projects/` 데이터(9건, `user_id` 없음) 마이그레이션 여부 — 이번 Phase 5 범위에서는
  다루지 않음. 새 구조(`DATA_DIR/projects/{user_id}/...`)로 넘어가면 기존 로컬 테스트 기록은
  그대로 남고 신규 기록과는 분리된 상태로 유지됨
- 프론트엔드 "기타(직접 입력)" 문서종류 옵션 — MVP 범위에서 제외, 필요시 추가
- 결과 다운로드/편집 기능 — 현재는 복사 버튼만 있음
- 텔레그램 테마 색상 연동(`tg.themeParams`) — 현재는 고정 색상, 선택적 개선사항
