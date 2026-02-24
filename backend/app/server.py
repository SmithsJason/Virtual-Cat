"""
CatAssistantServer 实现了 ChatKitServer 接口。
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
    """与虚拟猫管家功能相连的 ChatKit 服务器实现。"""

    def __init__(self) -> None:
        self.store: MemoryStore = MemoryStore()
        super().__init__(self.store)

        # 定义一些额外的实例变量以便于使用
        self.cat_store = CatStore()
        self.thread_item_converter = BasicThreadItemConverter()

    # -- 必须实现的方法 ----------------------------------------------------
    async def action(
        self,
        thread: ThreadMetadata,
        action: Action[str, Any],
        sender: WidgetItem | None,
        context: dict[str, Any],
    ) -> AsyncIterator[ThreadStreamEvent]:
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
        # agent 上下文中包含了工具调用时需要访问的信息。
        # 这些内容不会作为输入发送给模型本身。
        agent_context = CatAgentContext(
            thread=thread,
            store=self.store,
            cats=self.cat_store,
            request_context=context,
        )

        # 将线程中的所有条目加载出来作为输入给 agent，
        # 这样在生成回复时，agent 可以了解完整的对话上下文。
        items_page = await self.store.load_thread_items(
            thread.id,
            after=None,
            limit=20,
            order="desc",
            context=context,
        )

        # Runner 期望“最新的消息”位于列表最后。
        items = list(reversed(items_page.data))

        # 将 ChatKit 的线程条目转换为 agent 可理解的输入格式。
        input_items = await self.thread_item_converter.to_agent_input(items)

        result = Runner.run_streamed(
            cat_agent,
            input_items,
            context=agent_context,
        )

        async for event in stream_agent_response(
            agent_context, result, converter=ResponseStreamConverter(partial_images=3)
        ):
            yield event
        return

    def get_stream_options(self, thread: ThreadMetadata, context: dict[str, Any]) -> StreamOptions:
        # 不允许在流式输出中途取消，因为大多数猫屋交互都会更新猫的状态。
        return StreamOptions(allow_cancel=False)

    async def to_message_content(self, _input: Attachment) -> ResponseInputContentParam:
        raise RuntimeError("此示例暂不支持文件附件。")

    # -- 辅助方法 ----------------------------------------------------
    async def _handle_select_name_action(
        self,
        thread: ThreadMetadata,
        payload: dict[str, Any],
        sender: WidgetItem | None,
        context: dict[str, Any],
    ) -> AsyncIterator[ThreadStreamEvent]:
        name = payload["name"].strip()
        if not name or not sender:
            return

        options = [CatNameSuggestion(**option) for option in payload["options"]]
        current_state = await self.cat_store.load(thread.id)
        is_already_named = current_state.name != "Unnamed Cat"
        selection = current_state.name if is_already_named else name
        widget = build_name_suggestions_widget(options, selected=selection)

        yield ThreadItemReplacedEvent(
            item=sender.model_copy(update={"widget": widget}),
        )

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

        # 将名字保存在 cat_store 中，并在 chatkit 的线程存储里更新标题。
        state = await self.cat_store.mutate(thread.id, lambda s: s.rename(name))
        title = f"{state.name}’s Lounge"
        thread.title = title
        await self.store.save_thread(thread, context)

        # 添加一个隐藏上下文条目，让之后的 agent 输入能够知道
        # 用户已经从候选列表中选定了名字。
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

        message_item = AssistantMessageItem(
            id=self.store.generate_item_id("message", thread, context),
            thread_id=thread.id,
            created_at=datetime.now(),
            content=[
                AssistantMessageContent(
                    text=f"Love that choice. {state.name}’s profile card is now ready. Would you like to check it out?"
                )
            ],
        )
        yield ThreadItemDoneEvent(item=message_item)


def create_chatkit_server() -> CatAssistantServer | None:
    """如果依赖安装完整，则返回配置好的 ChatKit 服务器实例。"""
    return CatAssistantServer()
