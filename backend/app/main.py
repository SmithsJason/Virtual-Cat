"""FastAPI 入口文件，用于连接 ChatKit 服务器以及 REST 接口。"""

from __future__ import annotations

import os
from typing import Any

# 在导入任何OpenAI相关模块之前禁用tracing
os.environ["OPENAI_DISABLE_TRACING"] = "true"

from chatkit.server import StreamingResult
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import Response, StreamingResponse
from starlette.responses import JSONResponse

# 导入配置以确保OpenAI客户端正确初始化
from . import config
from .server import CatAssistantServer, create_chatkit_server

app = FastAPI(title="ChatKit API")

_chatkit_server: CatAssistantServer | None = create_chatkit_server()


def get_chatkit_server() -> CatAssistantServer:
    if _chatkit_server is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "ChatKit dependencies are missing. Install the ChatKit Python "
                "package to enable the conversational endpoint."
            ),
        )
    return _chatkit_server


@app.post("/chatkit")
async def chatkit_endpoint(
    request: Request, server: CatAssistantServer = Depends(get_chatkit_server)
) -> Response:
    payload = await request.body()
    result = await server.process(payload, {"request": request})
    if isinstance(result, StreamingResult):
        return StreamingResponse(result, media_type="text/event-stream")
    if hasattr(result, "json"):
        return Response(content=result.json, media_type="application/json")
    return JSONResponse(result)


@app.get("/cats/{thread_id}")
async def read_cat_state(
    thread_id: str,
    server: CatAssistantServer = Depends(get_chatkit_server),
) -> dict[str, Any]:
    state = await server.cat_store.load(thread_id)
    return {"cat": state.to_payload(thread_id)}
