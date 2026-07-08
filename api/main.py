"""FastAPI 앱 진입점"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from api.routes import router

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

# 프론트엔드(webapp/) 정적 파일 서빙. /app 하위 경로로 접근.
app.mount("/app", StaticFiles(directory="webapp", html=True), name="webapp")


@app.get("/")
def health_check():
    return {"status": "ok", "service": "safety-rag API"}