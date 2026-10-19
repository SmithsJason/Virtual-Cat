import hashlib
import logging
import re
from collections import defaultdict
from datetime import timedelta

import jieba
from fastapi import HTTPException
from openai import AsyncOpenAI
from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..db import utcnow
from ..models import (
    Conversation,
    Job,
    Memory,
    MemoryEmbedding,
    MemorySource,
    Message,
    Run,
    Summary,
    User,
)

jieba.setLogLevel(logging.ERROR)
STOP = {
    "我",
    "你",
    "的",
    "了",
    "吗",
    "呢",
    "是",
    "什么",
    "怎么",
    "还",
    "记得",
    "之前",
    "现在",
    "一下",
    "我们",
    "可以",
    "一个",
    "请",
    "用",
    "和",
    "最",
    "叫",
    "喜欢",
}


def tokens(text: str) -> list[str]:
    words = {
        word.strip().lower()
        for word in jieba.cut_for_search(text)
        if word.strip() and word.strip() not in STOP and re.search(r"[\w\u4e00-\u9fff]", word)
    }
    aliases = {
        "玩": "玩具",
        "玩耍": "玩具",
        "陪玩": "玩具",
        "称呼": "称呼",
        "名字": "称呼",
        "吃": "食物",
        "零食": "食物",
    }
    words.update(value for key, value in aliases.items() if key in text)
    return sorted(words)[:40]


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def fuse(rankings: list[list[str]]) -> list[tuple[str, float]]:
    scores: dict[str, float] = defaultdict(float)
    for ranking in rankings:
        for rank, identifier in enumerate(dict.fromkeys(ranking), start=1):
            scores[identifier] += 1 / (60 + rank)
    return sorted(scores.items(), key=lambda pair: (-pair[1], pair[0]))


async def enqueue(db: AsyncSession, kind: str, key: str, data: dict):
    await db.execute(
        insert(Job)
        .values(kind=kind, dedupe_key=key, payload=data)
        .on_conflict_do_nothing(index_elements=[Job.dedupe_key])
    )


async def embedding(text: str) -> list[float] | None:
    settings = get_settings()
    if not settings.embedding_api_key:
        return None
    async with AsyncOpenAI(
        api_key=settings.embedding_api_key,
        base_url=settings.embedding_base_url or None,
        timeout=12,
        max_retries=0,
    ) as client:
        result = await client.embeddings.create(
            model=settings.embedding_model, input=text, dimensions=settings.embedding_dimensions
        )
    vector = result.data[0].embedding
    if len(vector) != settings.embedding_dimensions:
        raise ValueError("Embedding 维度不匹配，须核对配置并重建向量")
    return vector


async def add_memory(
    db: AsyncSession,
    user_id: str,
    pet_id: str | None,
    kind: str,
    content: str,
    key: str | None = None,
    valid_until=None,
    message_id: str | None = None,
    quote: str | None = None,
    supersedes_id: str | None = None,
) -> Memory | None:
    # Serialize extraction and forget/update for one owner; never hold this lock during model calls.
    owner = await db.scalar(select(User).where(User.id == user_id).with_for_update())
    if message_id:
        source = await db.get(Message, message_id)
        if not source or source.excluded or not quote or quote not in source.content:
            return None
        conversation = await db.get(Conversation, source.conversation_id)
        if not conversation or conversation.user_id != user_id:
            return None
    else:
        source = None
    scope = [Memory.user_id == user_id, Memory.pet_id == pet_id, Memory.status == "active"]
    duplicate = await db.scalar(select(Memory).where(*scope, Memory.content == content))
    if duplicate:
        return duplicate
    if key and key != "other":
        old = list(
            (
                await db.scalars(select(Memory).where(*scope, Memory.key == key).with_for_update())
            ).all()
        )
        if source:
            # Delayed jobs may not overwrite a newer explicitly observed fact.
            if any(previous.created_at > source.created_at for previous in old):
                return None
        for previous in old:
            previous.status = "superseded"
            supersedes_id = previous.id
        if old:
            owner.memory_version += 1
            # Remove stale summaries and source messages from future active context.
            await suppress_sources(db, user_id, [m.id for m in old])
    memory = Memory(
        user_id=user_id,
        pet_id=pet_id,
        kind=kind,
        content=content.strip(),
        key=key,
        valid_until=valid_until,
        supersedes_id=supersedes_id,
        search_text=" ".join(tokens(content)),
        created_at=source.created_at if source else utcnow(),
    )
    db.add(memory)
    await db.flush()
    memory.search_vector = func.to_tsvector("simple", memory.search_text)
    db.add(MemorySource(memory_id=memory.id, message_id=message_id, quote=quote or content))
    await enqueue(
        db, "embed", f"embed:{memory.id}:{content_hash(content)[:16]}", {"memory_id": memory.id}
    )
    return memory


async def suppress_sources(db: AsyncSession, user_id: str, memory_ids: list[str], erase=False):
    sources = list(
        (await db.scalars(select(MemorySource).where(MemorySource.memory_id.in_(memory_ids)))).all()
    )
    ids = [source.message_id for source in sources if source.message_id]
    if ids:
        affected_conversations = select(Message.conversation_id).where(Message.id.in_(ids))
        await db.execute(
            update(Message)
            .where(
                Message.conversation_id.in_(affected_conversations),
                Message.role.in_(["assistant", "tool_history"]),
            )
            .values(excluded=True, **({"content": "[关联回答已随原文删除]"} if erase else {}))
        )
        await db.execute(
            update(Message)
            .where(Message.id.in_(ids))
            .values(excluded=True, **({"content": "[用户已删除原文]"} if erase else {}))
        )
        # Exclude sibling facts extracted from the same source to avoid resurfacing via another fact.
        siblings = select(MemorySource.memory_id).where(MemorySource.message_id.in_(ids))
        await db.execute(
            update(Memory)
            .where(Memory.user_id == user_id, Memory.id.in_(siblings), Memory.status == "active")
            .values(status="forgotten")
        )
        if erase:
            await db.execute(
                update(MemorySource)
                .where(MemorySource.message_id.in_(ids))
                .values(quote="[用户已删除原文]")
            )
    runs = list((await db.scalars(select(Run).where(Run.user_id == user_id))).all())
    for run in runs:
        if set(run.trace.get("selected_ids", [])) & set(memory_ids):
            if run.assistant_message_id:
                await db.execute(
                    update(Message)
                    .where(Message.id == run.assistant_message_id)
                    .values(excluded=True)
                )
            run.trace = {**run.trace, "preview": "", "memory_invalidated": True}
    conversations = select(Conversation.id).where(Conversation.user_id == user_id)
    await db.execute(delete(Summary).where(Summary.conversation_id.in_(conversations)))
    await db.execute(
        delete(MemoryEmbedding).where(
            MemoryEmbedding.memory_id.in_(
                select(Memory.id).where(Memory.user_id == user_id, Memory.status != "active")
            )
        )
    )


async def forget(db: AsyncSession, user_id: str, identifier: str, erase=False):
    owner = await db.scalar(select(User).where(User.id == user_id).with_for_update())
    memory = await db.scalar(
        select(Memory).where(Memory.id == identifier, Memory.user_id == user_id).with_for_update()
    )
    if not memory:
        raise HTTPException(404, "没有找到这条记忆")
    owner.memory_version += 1
    related = {memory.id: memory}
    ancestor = memory.supersedes_id
    while ancestor and ancestor not in related:
        previous = await db.scalar(
            select(Memory).where(Memory.id == ancestor, Memory.user_id == user_id)
        )
        if not previous:
            break
        related[previous.id] = previous
        ancestor = previous.supersedes_id
    if memory.key and memory.key != "other":
        versions = list(
            (
                await db.scalars(
                    select(Memory).where(
                        Memory.user_id == user_id,
                        Memory.pet_id == memory.pet_id,
                        Memory.key == memory.key,
                    )
                )
            ).all()
        )
        related.update({item.id: item for item in versions})
    for item in related.values():
        item.status = "forgotten"
    await db.flush()
    await suppress_sources(db, user_id, list(related), erase)
    if erase:
        for item in related.values():
            item.content = "[用户已删除记忆]"
            item.search_text = ""
            item.search_vector = None
        await db.execute(
            update(MemorySource)
            .where(MemorySource.memory_id.in_(list(related)))
            .values(quote="[用户已删除原文]")
        )


async def memory_payload(db: AsyncSession, memory: Memory) -> dict:
    sources = list(
        (await db.scalars(select(MemorySource).where(MemorySource.memory_id == memory.id))).all()
    )
    return {
        "id": memory.id,
        "kind": memory.kind,
        "content": memory.content,
        "key": memory.key,
        "status": memory.status,
        "valid_until": memory.valid_until.isoformat() if memory.valid_until else None,
        "created_at": memory.created_at.isoformat(),
        "sources": [{"message_id": s.message_id, "quote": s.quote} for s in sources],
    }


async def recall(
    db: AsyncSession,
    user_id: str,
    pet_id: str,
    query: str,
    *,
    vector: list[float] | None = None,
    mode="hybrid",
    limit=5,
) -> tuple[list[Memory], dict]:
    historical = any(word in query for word in ("以前", "过去", "曾经", "当时", "最初"))
    scope = [
        Memory.user_id == user_id,
        or_(Memory.pet_id == pet_id, Memory.pet_id.is_(None)),
        Memory.status.in_(["active", "superseded"] if historical else ["active"]),
    ]
    if not historical:
        scope.append(or_(Memory.valid_until.is_(None), Memory.valid_until > utcnow()))
    ranks: list[list[str]] = []
    candidates: dict[str, Memory] = {}
    requested_key = (
        "preferred_name"
        if any(w in query for w in ("称呼", "叫什么", "叫我", "我的名字"))
        else None
    )
    if requested_key:
        direct = list(
            (
                await db.scalars(
                    select(Memory)
                    .where(*scope, Memory.key == requested_key)
                    .order_by(Memory.created_at.desc())
                    .limit(5)
                )
            ).all()
        )
        candidates.update({m.id: m for m in direct})
        ranks.append([m.id for m in direct])
    words = tokens(query)
    if words:
        tsquery = func.to_tsquery(
            "simple", " | ".join(re.sub(r"[^\w\u4e00-\u9fff]", "", w) for w in words)
        )
        lexical = list(
            (
                await db.scalars(
                    select(Memory)
                    .where(*scope, Memory.search_vector.op("@@")(tsquery))
                    .order_by(
                        func.ts_rank_cd(Memory.search_vector, tsquery).desc(),
                        Memory.created_at.desc(),
                    )
                    .limit(20)
                )
            ).all()
        )
        candidates.update({m.id: m for m in lexical})
        ranks.append([m.id for m in lexical])
    settings = get_settings()
    if vector is not None and mode == "hybrid":
        distance = MemoryEmbedding.embedding.cosine_distance(vector)
        semantic = list(
            (
                await db.scalars(
                    select(Memory)
                    .join(MemoryEmbedding)
                    .where(
                        *scope, MemoryEmbedding.model == settings.embedding_model, distance < 0.65
                    )
                    .order_by(distance)
                    .limit(20)
                )
            ).all()
        )
        candidates.update({m.id: m for m in semantic})
        ranks.append([m.id for m in semantic])
    ranked = fuse(ranks)
    comparing = any(word in query for word in ("变化", "区别", "对比", "现在"))
    past_keys = {
        m.key
        for m in candidates.values()
        if m.status == "superseded" and m.key and m.key != "other"
    }
    selected, seen = [], set()
    for identifier, _ in ranked:
        item = candidates[identifier]
        if historical and not comparing and item.status == "active" and item.key in past_keys:
            continue
        # Historical queries can include past values; current queries retain one effective fact per key.
        group = item.content if historical or not item.key or item.key == "other" else item.key
        if group not in seen:
            selected.append(item)
            seen.add(group)
        if len(selected) >= limit:
            break
    return selected, {
        "mode": "hybrid" if vector is not None and mode == "hybrid" else "lexical",
        "historical": historical,
        "candidates": len(candidates),
        "selected_ids": [m.id for m in selected],
    }


def explicit_memories(text: str) -> list[dict]:
    if any(word in text for word in ("假如", "假设", "如果", "比如", "不要记", "别记")):
        return []
    result = []
    name = re.search(
        r"(?:以后|请|可以)?叫我[\s]*([\w\u4e00-\u9fff]{1,12}?)(?:吧|就好|[，。！!\s]|$)", text
    )
    if name:
        result.append(
            {
                "kind": "fact",
                "key": "preferred_name",
                "content": "用户希望被称为" + name.group(1),
                "quote": name.group(0),
                "temporary": False,
            }
        )
    return result


def expiry(temporary: bool):
    return utcnow() + timedelta(days=14) if temporary else None
