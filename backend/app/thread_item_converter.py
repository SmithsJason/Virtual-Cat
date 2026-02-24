"""用于将 ChatKit 线程条目转换为更适合模型输入的辅助工具。"""

from __future__ import annotations

from chatkit.agents import ThreadItemConverter
from chatkit.types import HiddenContextItem
from openai.types.responses import ResponseInputTextParam
from openai.types.responses.response_input_item_param import Message


class BasicThreadItemConverter(ThreadItemConverter):
    """为样板 Demo 增加 HiddenContextItem 支持。"""

    async def hidden_context_to_input(self, item: HiddenContextItem):
        return Message(
            type="message",
            content=[
                ResponseInputTextParam(
                    type="input_text",
                    text=item.content,
                )
            ],
            role="user",
        )
