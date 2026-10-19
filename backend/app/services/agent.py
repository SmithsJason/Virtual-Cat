import json
from dataclasses import dataclass, field

from agents import (
    Agent,
    ModelSettings,
    OpenAIChatCompletionsModel,
    RunContextWrapper,
    Runner,
    function_tool,
    set_tracing_disabled,
)
from fastapi import HTTPException
from openai import AsyncOpenAI
from sqlalchemy import select

from ..config import get_settings
from ..db import Session, utcnow
from ..models import Conversation, Message, Run, User
from .context import build, estimate, truncate
from .memory import enqueue
from .pets import event_payload, owned_pet, payload, perform, settle

set_tracing_disabled(True)


@dataclass
class ChatContext:
    user_id: str
    pet_id: str
    run_id: str
    events: list[dict] = field(default_factory=list)


@function_tool
async def care_for_cat(ctx: RunContextWrapper[ChatContext], action: str) -> str:
    """照料小猫。action 只能是 feed（喂食）、play（玩耍）、clean（梳洗）或 rest（休息）。每种动作每个请求最多一次。"""
    context = ctx.context
    async with Session() as db:
        try:
            event = await perform(
                db, context.user_id, context.pet_id, action, f"{context.run_id}:{action}"
            )
            await db.commit()
            result = event_payload(event)
            context.events.append(result)
            await publish(context.run_id, {"events": list(context.events)})
            return truncate(json.dumps(result, ensure_ascii=False), 600)
        except HTTPException as error:
            await db.rollback()
            return json.dumps({"success": False, "reason": error.detail}, ensure_ascii=False)


@function_tool
async def get_cat_status(ctx: RunContextWrapper[ChatContext]) -> str:
    """读取小猫最新真实状态。"""
    async with Session() as db:
        pet = await owned_pet(db, ctx.context.user_id, ctx.context.pet_id, lock=True)
        settle(pet)
        await db.commit()
        return json.dumps(payload(pet), ensure_ascii=False)


async def publish(run_id: str, patch: dict):
    async with Session() as db:
        run = await db.scalar(select(Run).where(Run.id == run_id).with_for_update())
        if run:
            run.trace = {**run.trace, **patch}
            await db.commit()


class BudgetedModel(OpenAIChatCompletionsModel):
    """The SDK calls this boundary for each turn, including turns after tool execution."""

    def __init__(self, run_id: str, **kwargs):
        super().__init__(**kwargs)
        self.run_id = run_id
        self.calls: list[dict] = []

    async def stream_response(self, *args, **kwargs):
        system = kwargs.get("system_instructions", args[0] if args else "") or ""
        items = kwargs.get("input", args[1] if len(args) > 1 else [])
        tools = kwargs.get("tools", [])
        schemas = [
            {
                "name": t.name,
                "description": t.description,
                "parameters": getattr(t, "params_json_schema", {}),
            }
            for t in tools
        ]
        measured = estimate(system, items, schemas)
        if measured > get_settings().context_tokens:
            raise ValueError("本轮上下文达到预算上限，请开启新会话继续；宠物和记忆会保留")
        if len(self.calls) >= 5:
            raise ValueError("本次交互已达到工具轮数上限")
        call = {"estimated_input_tokens": measured}
        self.calls.append(call)
        await publish(self.run_id, {"calls": list(self.calls)})
        async for event in super().stream_response(*args, **kwargs):
            if event.type == "response.completed":
                usage = getattr(event.response, "usage", None)
                if usage:
                    call["usage"] = usage.model_dump()
                    await publish(self.run_id, {"calls": list(self.calls)})
            yield event


async def execute_chat(run_id: str):
    settings = get_settings()
    if not settings.openai_api_key:
        await fail(run_id, "还没有配置对话模型密钥。你仍可以照料小猫、记录和管理记忆。")
        return
    context: ChatContext | None = None
    try:
        async with Session() as db:
            run = await db.get(Run, run_id)
            if not run or run.status == "completed":
                return
            run.status = "running"
            run.trace = {**run.trace, "preview": ""}
            conversation = await db.get(Conversation, run.conversation_id)
            current = await db.get(Message, run.user_message_id)
            pet = await owned_pet(db, run.user_id, run.pet_id, lock=True)
            settle(pet)
            await db.commit()
            context = ChatContext(run.user_id, run.pet_id, run.id)
            system, items, trace = await build(db, run.user_id, pet, conversation, current)
            run.trace = {**run.trace, **trace}
            await db.commit()
        async with AsyncOpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url or None,
            timeout=45,
            max_retries=1,
        ) as client:
            model = BudgetedModel(run_id, model=settings.chat_model, openai_client=client)
            agent = Agent(
                name="喵伴",
                instructions=system,
                model=model,
                tools=[get_cat_status, care_for_cat],
                model_settings=ModelSettings(
                    parallel_tool_calls=False,
                    extra_args={
                        settings.chat_token_parameter: settings.output_tokens
                        + settings.reasoning_reserve
                    },
                ),
            )
            result = Runner.run_streamed(agent, input=items, context=context, max_turns=5)
            preview, last_size = "", 0
            async for event in result.stream_events():
                if (
                    event.type == "raw_response_event"
                    and event.data.type == "response.output_text.delta"
                ):
                    preview += event.data.delta
                    if len(preview) - last_size >= 24:
                        await publish(run_id, {"preview": preview})
                        last_size = len(preview)
            answer = str(result.final_output or preview)
            if not answer:
                answer = "喵，我在这里。"
        async with Session() as db:
            owner = await db.scalar(
                select(User).where(User.id == context.user_id).with_for_update()
            )
            run = await db.scalar(select(Run).where(Run.id == run_id).with_for_update())
            # Forget/correction can invalidate a running request; never persist stale output.
            source = await db.get(Message, run.user_message_id)
            if source.excluded or owner.memory_version != run.trace.get("memory_version"):
                raise ValueError("记忆已更新，本次回答已停止，请重新发送")
            message = Message(conversation_id=run.conversation_id, role="assistant", content=answer)
            db.add(
                Message(
                    conversation_id=run.conversation_id,
                    role="tool_history",
                    content=json.dumps(
                        [item.to_input_item() for item in result.new_items],
                        ensure_ascii=False,
                        default=str,
                    ),
                )
            )
            db.add(message)
            await db.flush()
            run.assistant_message_id = message.id
            run.status, run.finished_at = "completed", utcnow()
            run.trace = {
                **run.trace,
                "preview": answer,
                "events": context.events,
                "duration_ms": int((utcnow() - run.created_at).total_seconds() * 1000),
            }
            await enqueue(
                db, "extract", f"extract:{run.user_message_id}", {"message_id": run.user_message_id}
            )
            await enqueue(
                db, "summary", f"summary:{run.id}", {"conversation_id": run.conversation_id}
            )
            await db.commit()
    except Exception as error:
        safe = (
            str(error)
            if isinstance(error, ValueError)
            else "对话服务暂时不可用，请稍后重试。已经完成的照料会保留在日记中。"
        )
        await fail(run_id, safe)


async def fail(run_id: str, error: str):
    async with Session() as db:
        run = await db.get(Run, run_id)
        if run:
            run.status, run.error, run.finished_at = "failed", error, utcnow()
            run.trace = {**run.trace, "preview": ""}
            await db.commit()
