from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import utcnow
from ..models import Pet, PetEvent

STATS = ("satiety", "energy", "happiness", "cleanliness", "affection")
DECAY = {"satiety": 2.0, "energy": 1.3, "happiness": 0.8, "cleanliness": 1.0}
ACTIONS = {
    "feed": {"satiety": 24, "energy": 4, "happiness": 3, "cleanliness": -2},
    "play": {"energy": -12, "happiness": 18, "cleanliness": -4},
    "clean": {"cleanliness": 28, "energy": -3, "happiness": 2},
    "rest": {"energy": 22, "satiety": -4, "happiness": 2},
}
TEXTS = {
    "feed": "吃完小鱼干，心满意足地舔了舔爪子。",
    "play": "追着玩具跑了一圈，尾巴都开心地翘起来了。",
    "clean": "梳好了毛，变成一只蓬松的小猫。",
    "rest": "在软垫上打了个盹，又恢复了一些精神。",
}


def settle(pet: Pet, now: datetime | None = None) -> None:
    now = now or utcnow()
    elapsed = min(24.0, max(0, (now - pet.settled_at).total_seconds() / 3600))
    for key, rate in DECAY.items():
        setattr(pet, key, max(0, getattr(pet, key) - rate * elapsed))
    pet.settled_at = max(pet.settled_at, now)


def payload(pet: Pet) -> dict:
    return {
        "id": pet.id,
        "name": pet.name,
        "color": pet.color,
        "personality": pet.personality,
        **{key: round(getattr(pet, key), 1) for key in STATS},
        "stage": "默契伙伴"
        if pet.affection >= 60
        else "渐渐熟悉"
        if pet.affection >= 20
        else "初次相遇",
        "version": pet.version,
        "created_at": pet.created_at.isoformat(),
    }


async def owned_pet(db: AsyncSession, user_id: str, pet_id: str, lock=False) -> Pet:
    query = select(Pet).where(Pet.id == pet_id, Pet.user_id == user_id)
    pet = await db.scalar(query.with_for_update() if lock else query)
    if not pet:
        raise HTTPException(404, "没有找到这只猫")
    return pet


async def perform(db: AsyncSession, user_id: str, pet_id: str, action: str, key: str) -> PetEvent:
    pet = await owned_pet(db, user_id, pet_id, lock=True)
    previous = await db.scalar(
        select(PetEvent).where(PetEvent.pet_id == pet_id, PetEvent.request_key == key)
    )
    if previous:
        if previous.action != action:
            raise HTTPException(409, "同一请求标识不能用于不同动作")
        return previous
    if action not in ACTIONS:
        raise HTTPException(422, "不支持的动作")
    settle(pet)
    if action == "feed" and pet.satiety >= 90:
        raise HTTPException(409, "已经吃得很饱啦，晚一点再喂吧")
    if action == "play" and (pet.energy < 15 or pet.satiety < 10):
        raise HTTPException(409, "先吃点东西、休息一下，再一起玩吧")
    if action == "clean" and pet.cleanliness >= 95:
        raise HTTPException(409, "毛毛已经很干净啦")
    if action == "rest" and pet.energy >= 95:
        raise HTTPException(409, "现在精神很好，还不想睡觉")
    last = await db.scalar(
        select(PetEvent)
        .where(PetEvent.pet_id == pet.id, PetEvent.action == action)
        .order_by(PetEvent.created_at.desc())
        .limit(1)
    )
    if last and (utcnow() - last.created_at).total_seconds() < 5:
        raise HTTPException(429, "让我缓一小会儿，再继续吧")
    for stat, change in ACTIONS[action].items():
        setattr(pet, stat, max(0, min(100, getattr(pet, stat) + change)))
    # Affection only accrues once in a ten-minute window, including across different actions.
    recent = await db.scalar(
        select(PetEvent)
        .where(PetEvent.pet_id == pet.id, PetEvent.action != "adopt")
        .order_by(PetEvent.created_at.desc())
        .limit(1)
    )
    if not recent or (utcnow() - recent.created_at).total_seconds() >= 600:
        pet.affection = min(100, pet.affection + 1)
    pet.version += 1
    event = PetEvent(
        pet_id=pet.id,
        action=action,
        request_key=key,
        text=pet.name + TEXTS[action],
        state=payload(pet),
    )
    db.add(event)
    await db.flush()
    return event


def event_payload(event: PetEvent) -> dict:
    return {
        "id": event.id,
        "action": event.action,
        "text": event.text,
        "state": event.state,
        "created_at": event.created_at.isoformat(),
    }
