from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..models import Conversation, Pet, PetEvent, User
from ..schemas import ActionInput, Adoption
from ..services.pets import event_payload, owned_pet, payload, perform, settle
from .auth import current_user

router = APIRouter(prefix="/pets", tags=["pets"])


@router.get("")
async def list_pets(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    pets = list(
        (await db.scalars(select(Pet).where(Pet.user_id == user.id).with_for_update())).all()
    )
    for pet in pets:
        settle(pet)
    await db.commit()
    return [payload(pet) for pet in pets]


@router.post("", status_code=201)
async def adopt(
    body: Adoption, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    await db.scalar(select(User).where(User.id == user.id).with_for_update())
    if await db.scalar(select(Pet.id).where(Pet.user_id == user.id)):
        raise HTTPException(409, "你已经有一位小伙伴啦")
    pet = Pet(user_id=user.id, **body.model_dump())
    db.add(pet)
    await db.flush()
    db.add(
        PetEvent(
            pet_id=pet.id,
            request_key="adoption",
            action="adopt",
            text=f"你和{pet.name}的故事，从今天开始。",
            state=payload(pet),
        )
    )
    await db.commit()
    return payload(pet)


@router.get("/{pet_id}/state")
async def state(
    pet_id: str, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    pet = await owned_pet(db, user.id, pet_id, lock=True)
    settle(pet)
    await db.commit()
    return payload(pet)


@router.post("/{pet_id}/actions")
async def action(
    pet_id: str,
    body: ActionInput,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    event = await perform(db, user.id, pet_id, body.action, body.request_key)
    await db.commit()
    return event_payload(event)


@router.get("/{pet_id}/events")
async def events(
    pet_id: str,
    before: str | None = None,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await owned_pet(db, user.id, pet_id)
    query = select(PetEvent).where(PetEvent.pet_id == pet_id)
    if before:
        anchor = await db.get(PetEvent, before)
        if not anchor or anchor.pet_id != pet_id:
            raise HTTPException(404, "日记游标无效")
        query = query.where(PetEvent.created_at < anchor.created_at)
    items = list((await db.scalars(query.order_by(PetEvent.created_at.desc()).limit(50))).all())
    return {
        "items": [event_payload(e) for e in items],
        "next": items[-1].id if len(items) == 50 else None,
    }


@router.get("/{pet_id}/conversations")
async def conversations(
    pet_id: str, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    await owned_pet(db, user.id, pet_id)
    items = list(
        (
            await db.scalars(
                select(Conversation)
                .where(Conversation.pet_id == pet_id, Conversation.user_id == user.id)
                .order_by(Conversation.created_at.desc())
                .limit(50)
            )
        ).all()
    )
    return [{"id": c.id, "title": c.title, "created_at": c.created_at.isoformat()} for c in items]


@router.post("/{pet_id}/conversations", status_code=201)
async def new_conversation(
    pet_id: str, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    await owned_pet(db, user.id, pet_id)
    item = Conversation(user_id=user.id, pet_id=pet_id)
    db.add(item)
    await db.commit()
    return {"id": item.id, "title": item.title, "created_at": item.created_at.isoformat()}
