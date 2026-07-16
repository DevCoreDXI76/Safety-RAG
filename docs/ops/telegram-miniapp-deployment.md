# 텔레그램 미니앱 배포 인프라 인계문서

- 문서 종류: 인계문서
- 작성일: 2026-07-09
- 관련 프로젝트: 안전서류 AI 초안 생성 시스템 (safety-rag)
- 범위: Phase 4(텔레그램 미니앱 프론트엔드) 배포 과정에서 확인/정리된 인프라 구조

---

## 1. 전체 구조 요약

이 프로젝트는 서로 다른 3개 시스템이 연결된 구조다.

1. **BotFather** — 텔레그램 봇 계정과 미니앱을 등록하는 곳. 최종적으로 공유 가능한 링크(`t.me/봇이름/앱`)를 발급한다.
2. **Railway** — 실제 프로그램이 돌아가는 곳. FastAPI 백엔드(`api/`)와 정적 프론트엔드(`webapp/`)가 함께 배포되어 있다.
3. **사용자의 텔레그램 앱** — 링크를 클릭하면 텔레그램이 `webapp/index.html`을 자기 앱 안에서 띄워주는 "창" 역할을 한다. 사용자는 텔레그램이 설치되어 있어야 미니앱을 열 수 있다(일반 웹사이트처럼 아무 브라우저에서나 바로 열리지 않음).

## 2. 준비 단계 (최초 1회, 완료됨)

1. **BotFather → `/newbot`**
   봇 표시 이름과 username(`_bot`으로 끝나야 함)을 지정해 봇 계정 생성.

2. **Railway → 백엔드 + 프론트엔드 배포**
   - FastAPI 백엔드(`api/`)와 미니앱 프론트엔드(`webapp/`)를 같은 Railway 프로젝트에 함께 배포.
   - `api/main.py`에서 `app.mount("/app", StaticFiles(directory="webapp", html=True), name="webapp")`로 `webapp/` 디렉터리를 `/app` 경로에 마운트. 즉 `https://<railway-domain>/app`으로 접속하면 `webapp/index.html`이 서빙된다.
   - 배포 주소(예시): `https://web-production-9d1bd.up.railway.app`
   - 미니앱 URL: `https://web-production-9d1bd.up.railway.app/app`

3. **BotFather → `/newapp`**
   - 대상 봇 선택 → 미니앱 제목/짧은 설명/배너 사진(640×360) 입력 → Web App URL에 위 미니앱 URL 입력 → short name(예: `app`) 지정.
   - 등록 완료 시 최종 공유 링크 `t.me/봇이름/app` 발급됨.

4. (선택) **`/mybots` → Bot Settings → Menu Button**
   미니앱을 봇 채팅창 메뉴 버튼에도 연결 가능.

## 3. 재배포 시 유의사항

- Railway는 재배포해도 **도메인 주소가 유지**된다. 코드를 고치고 Railway에 재배포하기만 하면, 기존에 공유한 `t.me/봇이름/app` 링크는 그대로 최신 버전을 보여준다. 링크를 다시 보낼 필요 없음.
- 링크를 다시 발급해야 하는 예외 상황(거의 발생하지 않음):
  - Railway 프로젝트 자체를 삭제하고 새로 만든 경우
  - 커스텀 도메인으로 교체하며 기존 도메인을 없앤 경우
  - BotFather에서 Web App URL 자체를 변경한 경우

## 4. 정리한 이슈: 루트 `index.html` 중복 파일

- 프로젝트 루트에 구버전 `index.html`(589줄)이 남아있었으나, `api/main.py`는 `webapp/` 디렉터리만 `/app`에 마운트하고 있어 **루트 파일은 실제로 서빙되지 않는 미사용 파일**이었음.
- 루트 `index.html`에는 `X-Telegram-Init-Data` 인증 헤더를 붙이는 코드가 없어 혼란의 소지가 있었음 (실제 서빙 파일인 `webapp/index.html`은 헤더를 정상적으로 포함).
- 2026-07-09, 루트 `index.html` 삭제 완료. 실제 서비스 동작에는 영향 없음.

## 5. 참고 값

| 항목 | 값 |
|---|---|
| Railway 배포 주소 | `https://web-production-9d1bd.up.railway.app` |
| 미니앱 Web App URL | `https://web-production-9d1bd.up.railway.app/app` |
| 실제 서빙 프론트엔드 파일 | `webapp/index.html` |
| 정적 파일 마운트 코드 위치 | `api/main.py` — `app.mount("/app", StaticFiles(directory="webapp", html=True), ...)` |
| 최종 공유 링크 형식 | `t.me/<봇 username>/app` |
