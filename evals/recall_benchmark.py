"""Retrieval-only smoke benchmark; never present these examples as thesis findings.
Usage: TEST_DATABASE_URL=..._test python evals/recall_benchmark.py [--allow-remote]
"""

import argparse
import asyncio
import json
import os
from pathlib import Path

from app.config import get_settings
from app.db import Base, new_id
from app.models import Job, MemoryEmbedding, Pet, User
from app.services.memory import add_memory, content_hash, embedding, recall
from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


async def main(remote: bool):
    url = os.environ.get("TEST_DATABASE_URL", "")
    if not url.rsplit("/", 1)[-1].endswith("_test"):
        raise SystemExit("必须提供以 _test 结尾的独立 TEST_DATABASE_URL")
    engine = create_async_engine(url)
    session = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await connection.run_sync(Base.metadata.create_all)
    cases = json.loads(Path(__file__).with_name("recall_cases.json").read_text())
    report = {
        "dataset": "small-authored-smoke-set",
        "live_embeddings": remote and bool(get_settings().embedding_api_key),
        "results": [],
    }
    for case in cases:
        async with session() as db:
            user = User(
                username="eval_" + new_id().replace("-", ""),
                password_hash="unusable-eval-account",
            )
            db.add(user)
            await db.flush()
            pet = Pet(user_id=user.id, name="评估小猫")
            db.add(pet)
            await db.flush()
            mapping = {}
            for fact in case["memories"]:
                memory = await add_memory(
                    db,
                    user.id,
                    None if fact.get("key") == "preferred_name" else pet.id,
                    fact["kind"],
                    fact["content"],
                    fact.get("key"),
                )
                mapping[memory.id] = fact["id"]
            await db.commit()
            try:
                vector = None
                if report["live_embeddings"]:
                    for identifier in mapping:
                        from app.models import Memory

                        memory = await db.get(Memory, identifier)
                        values = await embedding(memory.content)
                        db.add(
                            MemoryEmbedding(
                                memory_id=identifier,
                                model=get_settings().embedding_model,
                                content_hash=content_hash(memory.content),
                                embedding=values,
                            )
                        )
                    await db.commit()
                    vector = await embedding(case["query"])
                for mode in (
                    ["lexical", "hybrid"] if vector is not None else ["lexical"]
                ):
                    found, trace = await recall(
                        db, user.id, pet.id, case["query"], vector=vector, mode=mode
                    )
                    actual = [mapping[m.id] for m in found]
                    expected = set(case["expected"])
                    hits = len(set(actual) & expected)
                    report["results"].append(
                        {
                            "case": case["id"],
                            "split": case["split"],
                            "mode": trace["mode"],
                            "expected": sorted(expected),
                            "actual": actual,
                            "recall_at_5": hits / len(expected) if expected else None,
                            "precision_at_5": hits / len(actual) if actual else None,
                            "unanswerable_false_positive": bool(actual)
                            if not expected
                            else None,
                        }
                    )
            finally:
                await db.execute(
                    delete(Job).where(
                        Job.payload["memory_id"].as_string().in_(list(mapping))
                    )
                )
                await db.execute(delete(User).where(User.id == user.id))
                await db.commit()
    await engine.dispose()
    destination = Path(__file__).parents[1] / ".local" / "recall-report.json"
    destination.parent.mkdir(exist_ok=True)
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"Saved {len(report['results'])} retrieval checks to {destination}")
    print("样例集仅验证评估管道；正式论文需独立扩充测试集并实际调用模型评估回答。")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-remote", action="store_true")
    asyncio.run(main(parser.parse_args().allow_remote))
