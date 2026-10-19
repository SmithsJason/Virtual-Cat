from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")
    database_url: str = "postgresql+asyncpg://miaoban:miaoban@127.0.0.1:5432/miaoban"
    app_origin: str = "http://localhost:5170"
    cookie_secure: bool = False
    openai_api_key: str = ""
    openai_base_url: str | None = None
    chat_model: str = "gpt-5-mini"
    chat_token_parameter: Literal["max_completion_tokens", "max_tokens"] = "max_completion_tokens"
    embedding_api_key: str = ""
    embedding_base_url: str | None = None
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = Field(default=1536, ge=1, le=2000)
    context_tokens: int = Field(default=8000, ge=1024)
    model_context_window: int = Field(default=128000, ge=4096)
    output_tokens: int = Field(default=1200, ge=128)
    reasoning_reserve: int = Field(default=4096, ge=0)
    session_days: int = 14

    @model_validator(mode="after")
    def budget_fits(self):
        if (
            self.context_tokens + self.output_tokens + self.reasoning_reserve
            > self.model_context_window
        ):
            raise ValueError("上下文输入、输出与推理预留超过模型窗口")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
