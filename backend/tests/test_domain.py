from datetime import timedelta

import pytest

from app.config import Settings
from app.db import utcnow
from app.models import Pet
from app.services.context import count_tokens, estimate, truncate
from app.services.memory import explicit_memories, fuse
from app.services.pets import settle


def make_pet():
    return Pet(
        name="奶糖",
        satiety=80,
        energy=80,
        happiness=80,
        cleanliness=80,
        affection=5,
        settled_at=utcnow(),
    )


def test_offline_decay_caps_at_one_day_and_is_idempotent():
    pet = make_pet()
    now = pet.settled_at + timedelta(days=30)
    settle(pet, now)
    assert pet.satiety == 32
    assert pet.affection == 5
    before = pet.energy
    settle(pet, now)
    assert pet.energy == before
    settle(pet, now - timedelta(hours=3))
    assert pet.energy == before
    assert pet.settled_at == now


def test_budget_must_include_output_and_reasoning():
    with pytest.raises(ValueError):
        Settings(context_tokens=8000, model_context_window=9000, output_tokens=1200)


def test_token_budget_handles_chinese_and_tool_overhead():
    text = "我们一起玩耍吧。" * 1000
    assert count_tokens(truncate(text, 50)) <= 50
    assert estimate(
        "规则", [{"role": "user", "content": "你好"}], [{"name": "feed", "description": text}]
    ) > count_tokens(text)


def test_explicit_memory_avoids_hypothetical_and_respects_name():
    assert explicit_memories("以后叫我小林吧，我喜欢逗猫棒")[0]["content"] == "用户希望被称为小林"
    assert explicit_memories("假如以后叫我小王吧") == []
    assert explicit_memories("不要记住，叫我小王") == []


def test_rrf_uses_ranking_and_deduplicates_per_retriever():
    assert fuse([["a", "b"], ["b", "c"]])[0][0] == "b"
    assert fuse([["a", "a"]]) == fuse([["a"]])
