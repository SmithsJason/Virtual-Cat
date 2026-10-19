import hashlib
import secrets
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pwdlib import PasswordHash
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from ..config import get_settings
from ..db import get_db, utcnow
from ..models import AuthSession, User
from ..schemas import Credentials

router = APIRouter(prefix="/auth", tags=["auth"])
passwords = PasswordHash.recommended()
COOKIE = "miaoban_session"
DUMMY_HASH = passwords.hash("not-a-real-user-password")


def digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def current_user(request: Request, db: AsyncSession = Depends(get_db)) -> User:
    raw = request.cookies.get(COOKIE, "")
    user = await db.scalar(
        select(User)
        .join(AuthSession)
        .where(AuthSession.token_hash == digest(raw), AuthSession.expires_at > utcnow())
    )
    if not user:
        raise HTTPException(401, "请先登录，和小猫再次相见")
    return user


async def sign_in(db: AsyncSession, response: Response, user: User):
    settings = get_settings()
    token = secrets.token_urlsafe(32)
    db.add(
        AuthSession(
            token_hash=digest(token),
            user_id=user.id,
            expires_at=utcnow() + timedelta(days=settings.session_days),
        )
    )
    await db.commit()
    response.set_cookie(
        COOKIE,
        token,
        max_age=settings.session_days * 86400,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )
    return {"id": user.id, "username": user.username}


@router.post("/register", status_code=201)
async def register(body: Credentials, response: Response, db: AsyncSession = Depends(get_db)):
    user = User(
        username=body.username.lower(),
        password_hash=await run_in_threadpool(passwords.hash, body.password),
    )
    db.add(user)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "这个用户名已经有人使用了") from None
    return await sign_in(db, response, user)


@router.post("/login")
async def login(body: Credentials, response: Response, db: AsyncSession = Depends(get_db)):
    user = await db.scalar(select(User).where(User.username == body.username.lower()))
    valid = await run_in_threadpool(
        passwords.verify, body.password, user.password_hash if user else DUMMY_HASH
    )
    if not user or not valid:
        raise HTTPException(401, "用户名或密码不正确")
    return await sign_in(db, response, user)


@router.get("/me")
async def me(user: User = Depends(current_user)):
    return {"id": user.id, "username": user.username}


@router.post("/logout", status_code=204)
async def logout(request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    await db.execute(
        delete(AuthSession).where(AuthSession.token_hash == digest(request.cookies.get(COOKIE, "")))
    )
    await db.commit()
    response.delete_cookie(COOKIE, path="/")
