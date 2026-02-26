"""
OpenAI 客户端全局配置模块。

职责：
  1. 从 .env 文件加载 OPENAI_API_KEY 和 OPENAI_BASE_URL
  2. 创建 AsyncOpenAI 客户端（支持中转/代理 API 的 base_url）
  3. 将该客户端设置为 OpenAI Agents SDK 的全局默认客户端
  4. 强制使用 chat_completions API（而非 Responses API），以兼容中转服务
  5. 禁用 tracing，避免代理 API 不支持上报时报错
"""

import os
from dotenv import load_dotenv

# 在任何 OpenAI 导入之前就禁用 tracing，防止模块初始化时触发上报
os.environ["OPENAI_DISABLE_TRACING"] = "true"

from openai import AsyncOpenAI
from agents import set_default_openai_client, set_default_openai_api

# 加载项目根目录的 .env 文件中的环境变量
load_dotenv()

# 从环境变量读取 API Key 和可选的 Base URL（用于中转服务）
API_KEY = os.getenv("OPENAI_API_KEY")
BASE_URL = os.getenv("OPENAI_BASE_URL")

if not API_KEY:
    raise ValueError("OPENAI_API_KEY environment variable is required")

# 创建异步 OpenAI 客户端，若配置了 BASE_URL 则请求将发往中转服务
client = AsyncOpenAI(
    api_key=API_KEY,
    base_url=BASE_URL,
)

# 将此客户端注册为 Agents SDK 的默认客户端，use_for_tracing=False 明确禁用 tracing
set_default_openai_client(client=client, use_for_tracing=False)
# 指定使用 ChatCompletions API（非 Responses API），以保证与中转服务的兼容性
set_default_openai_api("chat_completions")

print(f"✅ OpenAI client configured with base_url: {BASE_URL}")
print(f"✅ API Key: {API_KEY[:10]}..." if API_KEY else "❌ API Key: NOT FOUND")
print("✅ Tracing disabled for proxy API compatibility")