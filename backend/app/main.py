from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from .api import auth, chat, memories, pets
from .config import get_settings
from .db import Session, engine


@asynccontextmanager
async def lifespan(app):
    yield
    await engine.dispose()


app = FastAPI(title="喵伴 API", version="0.2.0", lifespan=lifespan)


@app.middleware("http")
async def origin_check(request: Request, call_next):
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        origin = request.headers.get("origin")
        if origin and origin != get_settings().app_origin:
            return JSONResponse({"detail": "请求来源不被允许"}, status_code=403)
        if not origin and request.headers.get("sec-fetch-site") == "cross-site":
            return JSONResponse({"detail": "请求来源不被允许"}, status_code=403)
    return await call_next(request)


@app.exception_handler(SQLAlchemyError)
async def database_error(request, exc):
    return JSONResponse({"detail": "数据库暂时不可用，请检查服务与迁移状态"}, status_code=503)


@app.get("/api/health")
async def health():
    try:
        async with Session() as db:
            await db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return JSONResponse(
            {"database": False, "detail": "数据库不可用，请运行迁移并检查连接"}, status_code=503
        )
    settings = get_settings()
    return {
        "database": True,
        "chat_available": bool(settings.openai_api_key),
        "embedding_available": bool(settings.embedding_api_key),
        "version": "0.2.0",
    }


for router in (auth.router, pets.router, memories.router, chat.router):
    app.include_router(router, prefix="/api")
