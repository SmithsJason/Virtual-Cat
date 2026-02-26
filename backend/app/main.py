"""
FastAPI 入口文件 —— 应用的 HTTP 层。

职责：
  1. 创建 FastAPI 应用实例，挂载路由
  2. POST /chatkit  → 接收 ChatKit 协议 payload，委托给 CatAssistantServer 处理，
                       返回 SSE 流式响应或 JSON
  3. GET  /cats/{thread_id} → 返回指定线程对应的猫状态（供前端轮询/线程切换时使用）
"""

from __future__ import annotations

import os
from typing import Any

# ---- 在导入任何 OpenAI 相关模块之前禁用 tracing ----
# 这样做是为了兼容中转/代理 API 服务，避免 SDK 尝试上报 trace 失败
os.environ["OPENAI_DISABLE_TRACING"] = "true"

from chatkit.server import StreamingResult
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import Response, StreamingResponse
from starlette.responses import JSONResponse

# 导入配置模块，触发 OpenAI 客户端的初始化（设置 API Key / Base URL）
from . import config  # noqa: F401
from .server import CatAssistantServer, create_chatkit_server

# ==================== FastAPI 应用实例 ====================
app = FastAPI(title="ChatKit API")

# 在模块加载时就创建唯一的 ChatKit 服务器单例，所有请求共用
_chatkit_server: CatAssistantServer | None = create_chatkit_server()


def get_chatkit_server() -> CatAssistantServer:
    """FastAPI 依赖注入：获取 ChatKit 服务器单例，如果不可用则返回 503。"""
    if _chatkit_server is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "ChatKit dependencies are missing. Install the ChatKit Python "
                "package to enable the conversational endpoint."
            ),
        )
    return _chatkit_server


# ==================== 路由定义 ====================

@app.post("/chatkit")
async def chatkit_endpoint(
    request: Request, server: CatAssistantServer = Depends(get_chatkit_server)
) -> Response:
    """
    ChatKit 协议端点：
      - 接收前端 ChatKit 组件发来的请求体（包含对话消息、Widget 动作等）
      - 交由 server.process() 处理后，根据返回类型选择 SSE 流式或 JSON 响应
    """
    payload = await request.body()
    result = await server.process(payload, {"request": request})
    # 如果是流式结果，以 SSE (text/event-stream) 形式返回
    if isinstance(result, StreamingResult):
        return StreamingResponse(result, media_type="text/event-stream")
    # 兼容已序列化的 JSON 字符串
    if hasattr(result, "json"):
        return Response(content=result.json, media_type="application/json")
    return JSONResponse(result)


@app.get("/cats/{thread_id}")
async def read_cat_state(
    thread_id: str,
    server: CatAssistantServer = Depends(get_chatkit_server),
) -> dict[str, Any]:
    """
    REST 端点：返回指定线程的猫状态 payload。
    前端在切换线程时调用此接口来同步猫的最新状态。
    """
    state = await server.cat_store.load(thread_id)
    return {"cat": state.to_payload(thread_id)}
