from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


class Credentials(BaseModel):
    username: str = Field(min_length=3, max_length=40, pattern=r"^[\w\-]+$")
    password: str = Field(min_length=8, max_length=128)


class Adoption(BaseModel):
    name: str = Field(min_length=1, max_length=30, pattern=r".*\S.*")
    color: Literal["calico", "black", "white", "tabby", "colorpoint"] = "calico"
    personality: Literal["温柔好奇", "活泼黏人", "安静独立"] = "温柔好奇"


class ActionInput(BaseModel):
    action: Literal["feed", "play", "clean", "rest"]
    request_key: str = Field(min_length=8, max_length=100)


class MessageInput(BaseModel):
    text: str = Field(min_length=1, max_length=12000, pattern=r".*\S.*")
    request_key: str = Field(min_length=8, max_length=100)


class MemoryInput(BaseModel):
    kind: Literal["fact", "preference", "promise", "episode"] = "preference"
    content: str = Field(min_length=1, max_length=500, pattern=r".*\S.*")
    key: str | None = Field(default=None, max_length=100)
    valid_until: AwareDatetime | None = None


class ExtractedMemory(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["fact", "preference", "promise", "episode"]
    content: str = Field(max_length=300)
    key: Literal["preferred_name", "play_preference", "food_preference", "availability", "other"]
    quote: str = Field(min_length=1, max_length=500)
    temporary: bool = False


class Extraction(BaseModel):
    memories: list[ExtractedMemory] = Field(default_factory=list, max_length=5)
