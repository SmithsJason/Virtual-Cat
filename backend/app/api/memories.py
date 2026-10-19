from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..models import Memory, User
from ..schemas import MemoryInput
from ..services.memory import (
    add_memory,
    embedding,
    explicit_memories,
    forget,
    memory_payload,
    recall,
)
from ..services.pets import owned_pet
from .auth import current_user

router = APIRouter(prefix="/memories", tags=["memories"])


@router.get("")
async def memories(
    pet_id: str, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    await owned_pet(db, user.id, pet_id)
    items = list(
        (
            await db.scalars(
                select(Memory)
                .where(
                    Memory.user_id == user.id,
                    (Memory.pet_id == pet_id) | Memory.pet_id.is_(None),
                    Memory.status == "active",
                )
                .order_by(Memory.created_at.desc())
                .limit(200)
            )
        ).all()
    )
    return [await memory_payload(db, m) for m in items]


@router.post("", status_code=201)
async def create(
    body: MemoryInput,
    pet_id: str,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await owned_pet(db, user.id, pet_id)
    values = body.model_dump()
    explicit = explicit_memories(body.content)
    if not values["key"] and explicit:
        values["key"] = explicit[0]["key"]
    item = await add_memory(
        db, user.id, None if values["key"] == "preferred_name" else pet_id, **values
    )
    await db.commit()
    return await memory_payload(db, item)


@router.patch("/{identifier}")
async def correct(
    identifier: str,
    body: MemoryInput,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await db.scalar(select(User).where(User.id == user.id).with_for_update())
    old = await db.scalar(select(Memory).where(Memory.id == identifier, Memory.user_id == user.id))
    if not old or old.status != "active":
        raise HTTPException(404, "这条记忆已经失效")
    pet_id, key = old.pet_id, body.key or old.key
    await forget(db, user.id, identifier)
    old.status = "superseded"
    item = await add_memory(
        db,
        user.id,
        pet_id,
        body.kind,
        body.content,
        key,
        body.valid_until,
        supersedes_id=identifier,
    )
    await db.commit()
    return await memory_payload(db, item)


@router.delete("/{identifier}", status_code=204)
async def remove(
    identifier: str,
    erase_source: bool = False,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await forget(db, user.id, identifier, erase=erase_source)
    await db.commit()


@router.get("/search")
async def search(
    pet_id: str,
    q: str,
    mode: str = "hybrid",
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    if len(q) > 2000 or mode not in ("hybrid", "lexical"):
        raise HTTPException(422, "查询过长或检索方式无效")
    await owned_pet(db, user.id, pet_id)
    vector, error = None, None
    if mode == "hybrid":
        try:
            vector = await embedding(q)
        except Exception:
            error = "向量服务不可用，已使用关键词检索"
    items, trace = await recall(db, user.id, pet_id, q, vector=vector, mode=mode)
    return {
        "items": [await memory_payload(db, m) for m in items],
        "trace": {**trace, "warning": error},
    }
