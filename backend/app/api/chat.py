import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..db import Session, get_db
from ..models import Conversation, Message, Pet, Run, User
from ..schemas import MessageInput
from ..services.context import count_tokens
from ..services.memory import enqueue
from .auth import current_user

router = APIRouter(tags=["chat"])


async def owned_conversation(db, user_id, identifier):
    item = await db.scalar(
        select(Conversation).where(Conversation.id == identifier, Conversation.user_id == user_id)
    )
    if not item:
        raise HTTPException(404, "没有找到这个会话")
    return item


@router.get("/conversations/{identifier}/messages")
async def messages(
    identifier: str,
    before: str | None = None,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await owned_conversation(db, user.id, identifier)
    query = select(Message).where(
        Message.conversation_id == identifier, Message.role.in_(["user", "assistant"])
    )
    if before:
        anchor = await db.get(Message, before)
        if not anchor or anchor.conversation_id != identifier:
            raise HTTPException(404, "消息游标无效")
        query = query.where(Message.created_at < anchor.created_at)
    items = list((await db.scalars(query.order_by(Message.created_at.desc()).limit(50))).all())
    return {
        "items": [
            {
                "id": m.id,
                "role": m.role,
                "content": "[这条消息已从记忆上下文中移除]" if m.excluded else m.content,
                "created_at": m.created_at.isoformat(),
            }
            for m in reversed(items)
        ],
        "next": items[-1].id if len(items) == 50 else None,
    }


def run_payload(run: Run):
    return {
        "id": run.id,
        "status": run.status,
        "conversation_id": run.conversation_id,
        "user_message_id": run.user_message_id,
        "assistant_message_id": run.assistant_message_id,
        "trace": run.trace,
        "error": run.error,
    }


async def stream_run(run_id: str, request: Request):
    last, sequence = None, 0
    for _ in range(1200):
        if await request.is_disconnected():
            return
        async with Session() as db:
            run = await db.get(Run, run_id)
            value = run_payload(run)
        encoded = json.dumps(value, ensure_ascii=False)
        if encoded != last:
            sequence += 1
            yield f"id: {sequence}\nevent: run\ndata: {encoded}\n\n"
            last = encoded
        else:
            yield ": heartbeat\n\n"
        if run.status in ("completed", "failed"):
            return
        await asyncio.sleep(0.4)
    yield 'event: timeout\ndata: {"detail":"连接等待超时，请查询运行状态"}\n\n'


@router.post("/conversations/{identifier}/messages")
async def send(
    identifier: str,
    body: MessageInput,
    request: Request,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    if count_tokens(body.text) > get_settings().context_tokens // 2:
        raise HTTPException(422, "消息过长，请分段发送")
    conversation = await owned_conversation(db, user.id, identifier)
    # Serialize submissions for a pet, including across conversations.
    await db.scalar(select(Pet).where(Pet.id == conversation.pet_id).with_for_update())
    run = await db.scalar(
        select(Run).where(Run.conversation_id == identifier, Run.request_key == body.request_key)
    )
    if run:
        original = await db.get(Message, run.user_message_id)
        if original.content != body.text.strip():
            raise HTTPException(409, "同一请求标识不能用于不同消息")
    else:
        active = await db.scalar(
            select(Run).where(
                Run.pet_id == conversation.pet_id, Run.status.in_(["pending", "running"])
            )
        )
        if active:
            raise HTTPException(409, "小猫正在回应上一条消息，请稍等")
        message = Message(conversation_id=identifier, role="user", content=body.text.strip())
        db.add(message)
        await db.flush()
        run = Run(
            user_id=user.id,
            pet_id=conversation.pet_id,
            conversation_id=identifier,
            user_message_id=message.id,
            request_key=body.request_key,
        )
        db.add(run)
        await db.flush()
        if conversation.title == "新的陪伴":
            conversation.title = body.text.strip()[:30]
        await enqueue(db, "chat", f"chat:{run.id}", {"run_id": run.id})
        await enqueue(db, "extract", f"extract:{message.id}", {"message_id": message.id})
    await db.commit()
    return StreamingResponse(
        stream_run(run.id, request),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "X-Run-ID": run.id},
    )


@router.get("/runs/{run_id}")
async def get_run(
    run_id: str, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    run = await db.scalar(select(Run).where(Run.id == run_id, Run.user_id == user.id))
    if not run:
        raise HTTPException(404, "没有找到这次对话")
    return run_payload(run)


@router.get("/conversations/{identifier}/runs")
async def runs(
    identifier: str, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    await owned_conversation(db, user.id, identifier)
    items = list(
        (
            await db.scalars(
                select(Run)
                .where(Run.conversation_id == identifier)
                .order_by(Run.created_at.desc())
                .limit(10)
            )
        ).all()
    )
    return [run_payload(run) for run in items]
