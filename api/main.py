"""FastAPI 앱 진입점"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from api.routes import router
from api.webhook import webhook_router
from api.telegram_bot import set_webhook
from api.error_alert import report_error

app = FastAPI(
    title="safety-rag API",
    description="정보통신공사 현장 안전서류 초안 생성 API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# API 라우터를 먼저 등록해야 함 — 정적 파일 마운트가 경로를 가로채지 않도록 순서 중요
app.include_router(router)
app.include_router(webhook_router)

# 프론트엔드(webapp/) 정적 파일 서빙. /app 하위 경로로 접근.
app.mount("/app", StaticFiles(directory="webapp", html=True), name="webapp")


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    # HTTPException(429/404 등)은 Starlette 기본 핸들러가 먼저 처리하므로 여기엔
    # 오지 않는다 — 여기 걸리는 건 전부 예기치 못한 서버 오류.
    report_error(f"{request.method} {request.url.path}", exc)
    return JSONResponse(status_code=500, content={"detail": "서버 오류가 발생했습니다."})


@app.get("/")
def health_check():
    return {"status": "ok", "service": "safety-rag API"}


@app.on_event("startup")
def register_telegram_webhook():
    set_webhook()