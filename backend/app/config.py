"""用于通过代理 / 中转服务访问 OpenAI 的客户端配置。"""

import os
from dotenv import load_dotenv

# 在任何OpenAI导入之前就禁用tracing
os.environ["OPENAI_DISABLE_TRACING"] = "true"

from openai import AsyncOpenAI
from agents import set_default_openai_client, set_default_openai_api

# 加载.env文件中的环境变量
load_dotenv()

# 从环境变量读取配置
API_KEY = os.getenv("OPENAI_API_KEY")
BASE_URL = os.getenv("OPENAI_BASE_URL")

if not API_KEY:
    raise ValueError("OPENAI_API_KEY environment variable is required")

# 创建自定义OpenAI客户端，支持中转API
client = AsyncOpenAI(
    api_key=API_KEY,
    base_url=BASE_URL,  # 使用中转API的base_url
)

# 设置为agents库的默认客户端，明确禁用tracing
set_default_openai_client(client=client, use_for_tracing=False)
set_default_openai_api("chat_completions")

print(f"✅ OpenAI client configured with base_url: {BASE_URL}")
print(f"✅ API Key: {API_KEY[:10]}..." if API_KEY else "❌ API Key: NOT FOUND")
print("✅ Tracing disabled for proxy API compatibility")