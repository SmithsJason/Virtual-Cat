import os

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db import Base, get_db
from app.main import app


@pytest_asyncio.fixture
async def database(monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "openai_api_key", "")
    monkeypatch.setattr(get_settings(), "embedding_api_key", "")
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL to a disposable PostgreSQL database ending in _test")
    assert url.rsplit("/", 1)[-1].endswith("_test"), "Refusing to reset a non-test database"
    engine = create_async_engine(url)
    session = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)

    async def dependency():
        async with session() as db:
            yield db

    app.dependency_overrides[get_db] = dependency
    import app.api.chat as chat
    import app.services.agent as agent
    import app.worker as worker

    monkeypatch.setattr(chat, "Session", session)
    monkeypatch.setattr(agent, "Session", session)
    monkeypatch.setattr(worker, "Session", session)
    yield session
    app.dependency_overrides.clear()
    await engine.dispose()


@pytest_asyncio.fixture
async def client(database):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
        headers={"Origin": "http://localhost:5170"},
    ) as client:
        yield client


async def family(client, username="testhuman"):
    response = await client.post(
        "/api/auth/register", json={"username": username, "password": "password123"}
    )
    assert response.status_code == 201, response.text
    user = response.json()
    response = await client.post("/api/pets", json={"name": "奶糖"})
    assert response.status_code == 201, response.text
    pet = response.json()
    response = await client.post(f"/api/pets/{pet['id']}/conversations")
    return user, pet, response.json()
