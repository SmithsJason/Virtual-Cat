"""
线程条目 → Agent 输入格式转换器。

职责：
  将 ChatKit 的 ThreadItem（包括用户消息、助手消息、Widget、HiddenContextItem 等）
  转换为 OpenAI Agents SDK Runner 所需的输入格式。

  默认的 ThreadItemConverter 已经处理了大部分条目类型，
  这里扩展了对 HiddenContextItem 的支持 ——
  将隐藏上下文（如 <FED_CAT>、<CAT_NAME_SELECTED> 标签）转为 user role 的文本输入，
  让 Agent 在后续推理中能「记住」之前执行过的操作。
"""

from __future__ import annotations

from chatkit.agents import ThreadItemConverter
from chatkit.types import HiddenContextItem
from openai.types.responses import ResponseInputTextParam
from openai.types.responses.response_input_item_param import Message


class BasicThreadItemConverter(ThreadItemConverter):
    """扩展默认转换器，增加 HiddenContextItem → Agent 输入的转换逻辑。"""

    async def hidden_context_to_input(self, item: HiddenContextItem):
        """
        将 HiddenContextItem 转为 user 角色的文本消息。
        这些隐藏上下文不会在前端显示，但会作为 Agent 的推理输入，
        使其能感知之前执行过的操作（如喂食、命名等）。
        """
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
