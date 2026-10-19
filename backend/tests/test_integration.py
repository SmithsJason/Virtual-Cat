import asyncio
import json
from datetime import timedelta

import httpx
import pytest
from conftest import family
from sqlalchemy import select

from app.config import get_settings
from app.db import utcnow
from app.main import app
from app.models import (
    Conversation,
    Job,
    MemoryEmbedding,
    Message,
    Pet,
    PetEvent,
    Run,
    Summary,
)
from app.services.agent import execute_chat
from app.services.memory import add_memory, recall
from app.services.pets import perform
from app.worker import extract, process_one


async def test_auth_origin_and_owner_isolation(client, database):
    user, pet, conversation = await family(client)
    assert (await client.get("/api/auth/me")).json()["id"] == user["id"]
    assert (await client.post("/api/pets", json={"name": "另一只"})).status_code == 409
    assert (
        await client.post("/api/auth/logout", headers={"Origin": "https://bad.example"})
    ).status_code == 403
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as other:
        assert (await other.get(f"/api/pets/{pet['id']}/state")).status_code == 401
        await other.post(
            "/api/auth/register", json={"username": "otherhuman", "password": "password123"}
        )
        assert (await other.get(f"/api/pets/{pet['id']}/state")).status_code == 404
        assert (
            await other.get(f"/api/conversations/{conversation['id']}/messages")
        ).status_code == 404
    assert (await client.post("/api/auth/logout")).status_code == 204
    assert (await client.get("/api/auth/me")).status_code == 401
    assert (
        await client.post(
            "/api/auth/login", json={"username": "testhuman", "password": "wrongpass"}
        )
    ).status_code == 401
    assert (
        await client.post(
            "/api/auth/login", json={"username": "testhuman", "password": "password123"}
        )
    ).status_code == 200


async def test_concurrent_actions_exactly_one_event(client, database):
    user, pet, _ = await family(client)

    async def action():
        async with database() as db:
            result = await perform(db, user["id"], pet["id"], "feed", "same-request-key")
            await db.commit()
            return result.id

    results = await asyncio.gather(action(), action())
    assert results[0] == results[1]
    response = await client.get(f"/api/pets/{pet['id']}/state")
    assert response.json()["satiety"] == pytest.approx(99, abs=0.1)
    mismatch = await client.post(
        f"/api/pets/{pet['id']}/actions", json={"action": "play", "request_key": "same-request-key"}
    )
    assert mismatch.status_code == 409
    async with database() as db:
        events = (await db.scalars(select(PetEvent).where(PetEvent.action == "feed"))).all()
        assert len(events) == 1


async def test_memory_update_forget_and_no_resurrection(client, database):
    user, pet, conversation = await family(client)
    async with database() as db:
        message = Message(conversation_id=conversation["id"], role="user", content="以后叫我小林吧")
        db.add(message)
        await db.commit()
        message_id = message.id
    await extract(message_id)
    listed = (await client.get(f"/api/memories?pet_id={pet['id']}")).json()
    assert listed[0]["content"] == "用户希望被称为小林"
    identifier = listed[0]["id"]
    result = await client.patch(
        f"/api/memories/{identifier}", json={"kind": "fact", "content": "用户希望被称为阿林"}
    )
    assert result.status_code == 200
    await extract(message_id)
    listed = (await client.get(f"/api/memories?pet_id={pet['id']}")).json()
    assert [m["content"] for m in listed] == ["用户希望被称为阿林"]
    result = await client.delete(f"/api/memories/{listed[0]['id']}?erase_source=true")
    assert result.status_code == 204
    assert (await client.get(f"/api/memories?pet_id={pet['id']}")).json() == []
    await extract(message_id)
    assert (await client.get(f"/api/memories?pet_id={pet['id']}")).json() == []
    async with database() as db:
        history, _ = await recall(db, user["id"], pet["id"], "以前应该怎么称呼我")
        assert history == []
        assert (await db.get(Message, message_id)).content == "[用户已删除原文]"


async def test_keyword_recall_temporal_and_empty(client, database):
    user, pet, _ = await family(client)
    async with database() as db:
        old = await add_memory(
            db, user["id"], pet["id"], "preference", "用户喜欢用逗猫棒陪猫玩", "play_preference"
        )
        await db.commit()
        old_id = old.id
        latest = await add_memory(
            db, user["id"], pet["id"], "preference", "用户现在喜欢用小球陪猫玩", "play_preference"
        )
        await add_memory(
            db,
            user["id"],
            pet["id"],
            "fact",
            "用户近期忙着写毕业论文",
            "availability",
            utcnow() - timedelta(days=1),
        )
        await db.commit()
        items, _ = await recall(db, user["id"], pet["id"], "现在喜欢用什么玩具陪你玩")
        assert [m.id for m in items] == [latest.id]
        past, _ = await recall(db, user["id"], pet["id"], "以前喜欢用什么陪你玩")
        assert old_id in [m.id for m in past]
        empty, _ = await recall(db, user["id"], pet["id"], "量子纠缠实验室")
        assert empty == []
        expired, _ = await recall(db, user["id"], pet["id"], "毕业论文")
        assert expired == []


async def test_worker_leases_and_chat_failure_are_durable(client, database, monkeypatch):
    user, pet, conversation = await family(client)
    monkeypatch.setattr(get_settings(), "openai_api_key", "")
    async with database() as db:
        msg = Message(conversation_id=conversation["id"], role="user", content="你好")
        db.add(msg)
        await db.flush()
        run = Run(
            user_id=user["id"],
            pet_id=pet["id"],
            conversation_id=conversation["id"],
            user_message_id=msg.id,
            request_key="worker-request",
        )
        db.add(run)
        await db.flush()
        db.add(Job(kind="chat", dedupe_key="test-chat", payload={"run_id": run.id}))
        await db.commit()
        run_id = run.id
    assert await process_one()
    assert not await process_one()
    result = (await client.get(f"/api/runs/{run_id}")).json()
    assert result["status"] == "failed"
    assert "密钥" in result["error"]


async def test_budgeted_real_sdk_loop_with_mock_provider(client, database, monkeypatch):
    from openai import AsyncOpenAI

    import app.services.agent as agent_module

    user, pet, conversation = await family(client)
    settings = get_settings()
    monkeypatch.setattr(settings, "openai_api_key", "test-placeholder")
    monkeypatch.setattr(settings, "embedding_api_key", "")
    requests = []

    def handler(request):
        data = json.loads(request.content)
        requests.append(data)
        if len(requests) == 1:
            delta = {
                "role": "assistant",
                "tool_calls": [
                    {
                        "index": 0,
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": "care_for_cat", "arguments": '{"action":"feed"}'},
                    }
                ],
            }
            reason = "tool_calls"
        else:
            delta = {"role": "assistant", "content": "喵，吃饱啦，谢谢你！"}
            reason = "stop"
        frames = [
            json.dumps(
                {
                    "id": "chatcmpl_test",
                    "object": "chat.completion.chunk",
                    "created": 1,
                    "model": "gpt-5-mini",
                    "choices": [{"index": 0, "delta": delta, "finish_reason": None}],
                }
            ),
            json.dumps(
                {
                    "id": "chatcmpl_test",
                    "object": "chat.completion.chunk",
                    "created": 1,
                    "model": "gpt-5-mini",
                    "choices": [{"index": 0, "delta": {}, "finish_reason": reason}],
                    "usage": {"prompt_tokens": 200, "completion_tokens": 30, "total_tokens": 230},
                }
            ),
        ]
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            text="".join("data: " + frame + "\n\n" for frame in frames) + "data: [DONE]\n\n",
        )

    def factory(**kwargs):
        return AsyncOpenAI(
            api_key="test-placeholder",
            http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        )

    monkeypatch.setattr(agent_module, "AsyncOpenAI", factory)
    async with database() as db:
        msg = Message(conversation_id=conversation["id"], role="user", content="帮我喂一下小猫")
        db.add(msg)
        await db.flush()
        run = Run(
            user_id=user["id"],
            pet_id=pet["id"],
            conversation_id=conversation["id"],
            user_message_id=msg.id,
            request_key="sdk-mock-request",
        )
        db.add(run)
        await db.commit()
        run_id = run.id
    await execute_chat(run_id)
    result = (await client.get(f"/api/runs/{run_id}")).json()
    assert result["status"] == "completed", result
    assert len(requests) == 2
    assert (
        requests[0]["max_completion_tokens"] == settings.output_tokens + settings.reasoning_reserve
    )
    assert "max_tokens" not in requests[0]
    assert len(result["trace"]["calls"]) == 2
    assert all(
        c["estimated_input_tokens"] <= settings.context_tokens for c in result["trace"]["calls"]
    )
    assert result["trace"]["events"][0]["action"] == "feed"
    assert "吃饱" in result["trace"]["preview"]
    # Replay after completion must not execute a second action.
    await execute_chat(run_id)
    async with database() as db:
        assert len((await db.scalars(select(PetEvent).where(PetEvent.action == "feed"))).all()) == 1


async def test_vector_recall_returns_semantic_candidate_and_filters_owner(client, database):
    from app.services.memory import content_hash

    user, pet, _ = await family(client)
    dimensions = get_settings().embedding_dimensions
    vector = [1.0] + [0.0] * (dimensions - 1)
    other_vector = [0.0, 1.0] + [0.0] * (dimensions - 2)
    async with database() as db:
        target = await add_memory(db, user["id"], pet["id"], "preference", "周末去公园散步")
        distractor = await add_memory(db, user["id"], pet["id"], "preference", "最喜欢蓝色")
        await db.flush()
        for item, values in [(target, vector), (distractor, other_vector)]:
            db.add(
                MemoryEmbedding(
                    memory_id=item.id,
                    model=get_settings().embedding_model,
                    content_hash=content_hash(item.content),
                    embedding=values,
                )
            )
        await db.commit()
        lexical, _ = await recall(db, user["id"], pet["id"], "户外休闲安排")
        assert not lexical
        semantic, trace = await recall(db, user["id"], pet["id"], "户外休闲安排", vector=vector)
        assert [m.id for m in semantic] == [target.id]
        assert trace["mode"] == "hybrid"
        leaked, _ = await recall(db, "another-owner", pet["id"], "户外休闲安排", vector=vector)
        assert leaked == []


async def test_delayed_old_extraction_cannot_replace_new_name(client, database):
    user, pet, conversation = await family(client)
    async with database() as db:
        old = Message(
            conversation_id=conversation["id"],
            role="user",
            content="以后叫我小林吧",
            created_at=utcnow() - timedelta(days=1),
        )
        new = Message(conversation_id=conversation["id"], role="user", content="以后叫我阿林吧")
        db.add_all([old, new])
        await db.commit()
        old_id, new_id = old.id, new.id
    await extract(new_id)
    await extract(old_id)
    items = (await client.get(f"/api/memories?pet_id={pet['id']}")).json()
    assert [m["content"] for m in items] == ["用户希望被称为阿林"]


async def test_forgetting_invalidates_sources_summary_and_answer(client, database):
    user, pet, conversation = await family(client)
    async with database() as db:
        source = Message(conversation_id=conversation["id"], role="user", content="我喜欢小球")
        answer = Message(
            conversation_id=conversation["id"], role="assistant", content="记住啦，你喜欢小球"
        )
        db.add_all([source, answer])
        await db.flush()
        memory = await add_memory(
            db,
            user["id"],
            pet["id"],
            "preference",
            "用户喜欢小球",
            message_id=source.id,
            quote="我喜欢小球",
        )
        db.add(
            Summary(
                conversation_id=conversation["id"], content="用户喜欢小球", source_ids=[source.id]
            )
        )
        run = Run(
            user_id=user["id"],
            pet_id=pet["id"],
            conversation_id=conversation["id"],
            request_key="derived-output",
            user_message_id=source.id,
            assistant_message_id=answer.id,
            status="completed",
            trace={"selected_ids": [memory.id], "preview": answer.content},
        )
        db.add(run)
        await db.commit()
        memory_id = memory.id
        source_id = source.id
        answer_id = answer.id
        run_id = run.id
    assert (await client.delete(f"/api/memories/{memory_id}?erase_source=true")).status_code == 204
    async with database() as db:
        assert (await db.get(Message, source_id)).content == "[用户已删除原文]"
        assert (await db.get(Message, answer_id)).excluded
        assert await db.get(Summary, conversation["id"]) is None
        assert (await db.get(Run, run_id)).trace["preview"] == ""
    await extract(source_id)
    assert (await client.get(f"/api/memories?pet_id={pet['id']}")).json() == []


async def test_context_stays_bounded_when_history_is_large(client, database):
    from app.services.context import build, estimate

    user, pet, conversation = await family(client)
    async with database() as db:
        now = utcnow()
        db.add_all(
            [
                Message(
                    conversation_id=conversation["id"],
                    role="user" if i % 2 == 0 else "assistant",
                    content="很长的历史对话。" * 800,
                    created_at=now - timedelta(minutes=120 - i),
                )
                for i in range(100)
            ]
        )
        current = Message(
            conversation_id=conversation["id"], role="user", content="你好", created_at=now
        )
        db.add(current)
        await db.flush()
        system, items, trace = await build(
            db,
            user["id"],
            await db.get(Pet, pet["id"]),
            await db.get(Conversation, conversation["id"]),
            current,
        )
        assert estimate(system, items) < get_settings().context_tokens - 2000
        assert trace["history_count"] < 100
        assert items[-1]["content"] == "你好"


async def test_expired_final_job_lease_unblocks_chat(client, database):
    user, pet, conversation = await family(client)
    async with database() as db:
        message = Message(conversation_id=conversation["id"], role="user", content="你好")
        db.add(message)
        await db.flush()
        run = Run(
            user_id=user["id"],
            pet_id=pet["id"],
            conversation_id=conversation["id"],
            user_message_id=message.id,
            request_key="abandoned-run",
            status="running",
        )
        db.add(run)
        await db.flush()
        db.add(
            Job(
                kind="chat",
                dedupe_key="abandoned-job",
                payload={"run_id": run.id},
                status="running",
                attempts=4,
                lease_until=utcnow() - timedelta(seconds=1),
            )
        )
        await db.commit()
        run_id = run.id
    await process_one()
    result = (await client.get(f"/api/runs/{run_id}")).json()
    assert result["status"] == "failed"


async def test_message_sse_retry_is_persistent_and_idempotent(client, database):
    _, pet, conversation = await family(client)
    done = False

    async def work():
        while not done:
            await process_one()
            await asyncio.sleep(0.01)

    worker = asyncio.create_task(work())
    try:
        body = {"text": "你好", "request_key": "sse-request-key"}
        first = await client.post(f"/api/conversations/{conversation['id']}/messages", json=body)
        assert first.status_code == 200
        assert "event: run" in first.text
        assert '"status": "failed"' in first.text
        second = await client.post(f"/api/conversations/{conversation['id']}/messages", json=body)
        assert first.headers["x-run-id"] == second.headers["x-run-id"]
        mismatch = await client.post(
            f"/api/conversations/{conversation['id']}/messages", json={**body, "text": "另一句话"}
        )
        assert mismatch.status_code == 409
        messages = (await client.get(f"/api/conversations/{conversation['id']}/messages")).json()
        assert len(messages["items"]) == 1
        another = (await client.post(f"/api/pets/{pet['id']}/conversations")).json()
        assert another["id"] != conversation["id"]
        assert (await client.get("/api/pets")).json()[0]["id"] == pet["id"]
    finally:
        done = True
        await worker
