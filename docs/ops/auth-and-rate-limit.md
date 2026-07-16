# 인증 및 사용량 제한 구조 인계문서

- 문서 종류: 인계문서
- 작성일: 2026-07-09
- 관련 프로젝트: 안전서류 AI 초안 생성 시스템 (safety-rag)
- 범위: 텔레그램 initData 인증, 1인당 하루 5회 사용량 제한 구조 확인 및 검증 기록

---

## 1. 인증 흐름 (initData → HMAC 검증 → user_id)

**1) 프론트엔드 — `webapp/index.html`**

```js
function telegramInitData() {
  return (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.initData) || "";
}
function apiFetch(path, options = {}) {
  const headers = Object.assign({}, options.headers, {
    "X-Telegram-Init-Data": telegramInitData(),
  });
  return fetch(`${API_BASE}${path}`, Object.assign({}, options, { headers }));
}
```

텔레그램 미니앱 SDK가 앱 실행 시 자동 주입하는 `window.Telegram.WebApp.initData`(사용자별로 서로 다른 서명된 문자열)를 모든 API 요청(`/document-types`, `/projects/...`, `/generate`)에 `X-Telegram-Init-Data` 헤더로 첨부한다. 텔레그램 밖 일반 브라우저에서 열면 이 값이 빈 문자열이 되어 인증에 실패한다(의도된 동작).

**2) 백엔드 검증 — `api/telegram_auth.py`**

```python
def require_telegram_auth(x_telegram_init_data: str = Header(...)) -> dict:
    parsed = verify_init_data(x_telegram_init_data)   # HMAC-SHA256 서명 검증 (봇 토큰 기반)
    user = json.loads(parsed["user"])
    user_id = user["id"]                               # 텔레그램 고유 사용자 ID
    if not is_allowed(user_id): ...
    return {"user_id": user_id, ...}
```

`verify_init_data`가 텔레그램 공식 서명 검증 알고리즘(봇 토큰으로 만든 HMAC 키)을 구현하고 있어, 클라이언트가 `user_id`를 임의로 조작해서 보낼 수 없다(봇 토큰 없이는 유효한 hash 생성 불가).

## 2. 사용량 제한 구조

**제한값 정의 — `api/access_control.py`**

```python
DAILY_LIMIT = 5
```

- `ADMIN_TELEGRAM_USER_ID`도 같은 파일에 정의. 관리자 계정은 카운트는 동일하게 기록되지만 한도 판정에서는 제외되어 항상 통과됨(반복 테스트 중 관리자 본인이 한도에 걸리던 문제 해결 목적, 커밋 `ddc5adf`).

**카운트 체크/증가 로직 — `api/rate_limit.py`**

- KST(한국 시간) 자정 기준으로 리셋
- 사용 기록은 `data/usage_log.json`에 `{user_id: {"date": "YYYY-MM-DD", "count": N}}` 형태로 저장
- `check_and_increment(user_id)`: 오늘 사용 가능하면 카운트 +1 후 `True`, `DAILY_LIMIT` 초과 시 `False` 반환

**실제 적용 지점 — `api/routes.py:66-69`**

```python
user_id = telegram_user["user_id"]
if not check_and_increment(user_id):
    raise HTTPException(status_code=429, detail="오늘 사용 가능한 횟수를 모두 사용했습니다.")
```

- 제한 범위: `POST /generate`(문서 초안 생성) 요청만 카운트됨. 조회성 엔드포인트(`/projects/...` 등)는 제한 없음.
- `usage_log.json`에는 검증된 실제 텔레그램 고유 ID(`str(user_id)`)로 기록되므로, "인당 5회"가 실제로 사용자별로 독립 작동함.

## 3. 프론트엔드 에러 처리 검증

`webapp/index.html`의 `generateDraft()`:

```
백엔드 HTTPException(429, detail="오늘 사용...")
→ 프론트 res.ok가 false
→ err.detail 파싱
→ throw new Error(err.detail)
→ catch에서 showError(e.message)
→ 화면에 표시
```

2026-07-09 실제 사용 중 "오늘 사용 가능한 횟수를 모두 사용했습니다." 메시지가 정상적으로 화면에 노출되는 것을 확인함. 인증 → HMAC 검증 → 카운트 체크 → 프론트 에러 표시까지 전체 파이프라인이 실사용 조건에서 정상 작동함을 확인.

## 4. 향후 개선 아이디어 (미착수, 참고용)

- `err = await res.json()` 부분이 만약 백엔드가 JSON이 아닌 응답(예: 502 등)을 반환하면 파싱 실패로 사용자에게 알아보기 어려운 JS 에러가 노출될 수 있음. `try { err = await res.json() } catch { err = {} }`로 감싸는 방어 코드 추가를 권장.
- 현재 access_control / rate_limit은 파일 기반(`data/usage_log.json`) 저장이며, Railway 재배포 시 볼륨이 영속되는지 별도 확인 필요(Railway Volume 설정 여부 확인 권장).
