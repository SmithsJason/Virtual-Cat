"""Maintenance commands; no external request is made by enqueueing tasks."""

import argparse
import asyncio

from sqlalchemy import select

from .db import Session, new_id
from .models import Memory
from .services.memory import enqueue


async def reindex():
    async with Session() as db:
        memories = list((await db.scalars(select(Memory).where(Memory.status == "active"))).all())
        batch = new_id()
        for memory in memories:
            await enqueue(db, "embed", f"reindex:{batch}:{memory.id}", {"memory_id": memory.id})
        await db.commit()
    print(f"Queued {len(memories)} active memories; the worker needs an Embedding configuration.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["reindex"])
    parser.parse_args()
    asyncio.run(reindex())
