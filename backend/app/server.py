"""
CatAssistantServer —— ChatKit 服务器核心实现。

职责：
  1. 继承 ChatKitServer[dict]，实现 respond / action / get_stream_options 等必要方法
  2. respond()：接收用户消息 → 加载对话历史 → 转换为 Agent 输入 → 流式运行 Agent → 返回 SSE 事件流
  3. action()：处理 Widget 客户端动作（如用户点击名字候选列表选择名字）
  4. 协调 CatStore（猫状态存储）、MemoryStore（对话存储）、Agent Runner 三者之间的交互

架构关系：
  前端 ChatKit 组件 ←SSE→ FastAPI /chatkit ←→ CatAssistantServer ←→ Agent Runner + CatStore
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, AsyncIterator

from agents import Runner
from chatkit.agents import ResponseStreamConverter, stream_agent_response
from chatkit.server import ChatKitServer
from chatkit.types import (
    Action,
    AssistantMessageContent,
    AssistantMessageItem,
    Attachment,
    HiddenContextItem,
    StreamOptions,
    ThreadItemDoneEvent,
    ThreadItemReplacedEvent,
    ThreadMetadata,
    ThreadStreamEvent,
    UserMessageItem,
    WidgetItem,
)
from openai.types.responses import ResponseInputContentParam

from .cat_agent import CatAgentContext, cat_agent
from .cat_store import CatStore
from .memory_store import MemoryStore
from .thread_item_converter import BasicThreadItemConverter
from .widgets.name_suggestions_widget import (
    CatNameSuggestion,
    build_name_suggestions_widget,
)

logging.basicConfig(level=logging.INFO)


class CatAssistantServer(ChatKitServer[dict[str, Any]]):
    """
    虚拟猫管家 ChatKit 服务器。

    持有两个存储实例：
      - store (MemoryStore)  — ChatKit 标准的对话线程 & 消息存储
      - cat_store (CatStore) — 猫状态存储（按 thread_id 隔离）
    """

    def __init__(self) -> None:
        self.store: MemoryStore = MemoryStore()
        super().__init__(self.store)

        # 猫状态存储和线程条目转换器
        self.cat_store = CatStore()
        self.thread_item_converter = BasicThreadItemConverter()

    # ==================== 必须实现的接口方法 ====================

    async def action(
        self,
        thread: ThreadMetadata,
        action: Action[str, Any],
        sender: WidgetItem | None,
        context: dict[str, Any],
    ) -> AsyncIterator[ThreadStreamEvent]:
        """
        处理 Widget 客户端动作。
        目前仅处理 cats.select_name 类型（用户从候选列表中选择猫名字）。
        """
        if action.type == "cats.select_name":
            async for event in self._handle_select_name_action(
                thread,
                action.payload,
                sender,
                context,
            ):
                yield event
            return

        return

    async def respond(
        self,
        thread: ThreadMetadata,
        item: UserMessageItem | None,
        context: dict[str, Any],
    ) -> AsyncIterator[ThreadStreamEvent]:
        """
        处理用户发来的对话消息，流式返回 Agent 的响应。

        流程：
          1. 构建 CatAgentContext（包含线程信息、存储引用、猫状态存储）
          2. 从 MemoryStore 加载最近 20 条线程条目作为对话上下文
          3. 通过 BasicThreadItemConverter 将条目转换为 Agent 可理解的输入格式
          4. 调用 Runner.run_streamed() 流式运行 Agent（gpt-5-mini）
          5. 通过 stream_agent_response() 将 Agent 输出转为 ChatKit SSE 事件流
        """
        # Agent 上下文：工具调用时通过 ctx.context 访问存储和线程信息
        agent_context = CatAgentContext(
            thread=thread,
            store=self.store,
            cats=self.cat_store,
            request_context=context,
        )

        # 加载最近 20 条对话历史，倒序取出后翻转（Runner 期望最新消息在列表最后）
        items_page = await self.store.load_thread_items(
            thread.id,
            after=None,
            limit=20,
            order="desc",
            context=context,
        )
        items = list(reversed(items_page.data))

        # 将 ChatKit ThreadItem 转换为 OpenAI Agent 可处理的输入格式
        input_items = await self.thread_item_converter.to_agent_input(items)

        # 流式运行 Agent
        result = Runner.run_streamed(
            cat_agent,
            input_items,
            context=agent_context,
        )

        # 将 Agent 的流式输出转换为 ChatKit SSE 事件并逐个 yield
        async for event in stream_agent_response(
            agent_context, result, converter=ResponseStreamConverter(partial_images=3)
        ):
            yield event
        return

    def get_stream_options(self, thread: ThreadMetadata, context: dict[str, Any]) -> StreamOptions:
        """
        流式选项配置：禁止中途取消。
        因为猫屋的工具调用会修改猫状态，中途取消可能导致状态不一致。
        """
        return StreamOptions(allow_cancel=False)

    async def to_message_content(self, _input: Attachment) -> ResponseInputContentParam:
        """附件转消息内容 —— 本示例暂不支持文件附件。"""
        raise RuntimeError("此示例暂不支持文件附件。")

    # ==================== 私有辅助方法 ====================

    async def _handle_select_name_action(
        self,
        thread: ThreadMetadata,
        payload: dict[str, Any],
        sender: WidgetItem | None,
        context: dict[str, Any],
    ) -> AsyncIterator[ThreadStreamEvent]:
        """
        处理「选择猫名字」的 Widget 动作。

        流程：
          1. 解析用户选择的名字和所有候选选项
          2. 检查猫是否已命名（防止重命名）
          3. 重建 Widget 并标记选中项，通过 ThreadItemReplacedEvent 替换原 Widget
          4. 将名字保存到 CatStore，更新线程标题
          5. 注入 HiddenContextItem，让后续 Agent 推理知道名字已选定
          6. 返回确认消息
        """
        name = payload["name"].strip()
        if not name or not sender:
            return

        # 解析候选选项列表
        options = [CatNameSuggestion(**option) for option in payload["options"]]
        current_state = await self.cat_store.load(thread.id)
        is_already_named = current_state.name != "Unnamed Cat"
        selection = current_state.name if is_already_named else name

        # 重建 Widget：标记选中项，禁用其他选项
        widget = build_name_suggestions_widget(options, selected=selection)

        # 用更新后的 Widget 替换原来的 Widget（选中态 UI 更新）
        yield ThreadItemReplacedEvent(
            item=sender.model_copy(update={"widget": widget}),
        )

        # 如果已命名，返回提示信息并终止
        if is_already_named:
            message_item = AssistantMessageItem(
                id=self.store.generate_item_id("message", thread, context),
                thread_id=thread.id,
                created_at=datetime.now(),
                content=[
                    AssistantMessageContent(
                        text=f"{current_state.name} already has a name, so we can't rename them."
                    )
                ],
            )
            yield ThreadItemDoneEvent(item=message_item)
            return

        # 保存名字到 CatStore（触发花色随机分配），并更新线程标题
        state = await self.cat_store.mutate(thread.id, lambda s: s.rename(name))
        title = f"{state.name}'s Lounge"
        thread.title = title
        await self.store.save_thread(thread, context)

        # 注入隐藏上下文，让后续 Agent 推理知道用户已从候选列表中选定了名字
        await self.store.add_thread_item(
            thread.id,
            HiddenContextItem(
                id=self.store.generate_item_id("message", thread, context),
                thread_id=thread.id,
                created_at=datetime.now(),
                content=f"<CAT_NAME_SELECTED>{state.name}</CAT_NAME_SELECTED>",
            ),
            context=context,
        )

        # 返回确认消息
        message_item = AssistantMessageItem(
            id=self.store.generate_item_id("message", thread, context),
            thread_id=thread.id,
            created_at=datetime.now(),
            content=[
                AssistantMessageContent(
                    text=f"Love that choice. {state.name}'s profile card is now ready. Would you like to check it out?"
                )
            ],
        )
        yield ThreadItemDoneEvent(item=message_item)


def create_chatkit_server() -> CatAssistantServer | None:
    """工厂函数：创建并返回 ChatKit 服务器实例。"""
    return CatAssistantServer()
