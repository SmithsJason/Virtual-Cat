"""
猫状态内存存储 —— 线程级隔离 + asyncio.Lock 并发安全。

设计要点：
  - 每个 ChatKit thread_id 对应一只独立的猫（Dict[str, CatState]）
  - 使用 asyncio.Lock 保证在异步环境下的并发安全
  - load() 返回克隆体，避免外部直接修改内部状态
  - mutate() 接受 mutator 回调函数，在锁内原子地修改状态并返回克隆体

注意：这是内存存储，重启即丢失。生产环境应替换为持久化数据库实现。
"""

from __future__ import annotations

import asyncio
from typing import Callable, Dict

from .cat_state import CatState


class CatStore:
    """按线程 ID 隔离的、线程安全的猫状态内存存储。"""

    def __init__(self) -> None:
        # 以 thread_id 为 key 存储各线程的猫状态
        self._states: Dict[str, CatState] = {}
        # asyncio.Lock 保证并发请求下的状态一致性
        self._lock = asyncio.Lock()

    def _ensure(self, thread_id: str) -> CatState:
        """懒初始化：如果该线程还没有猫状态，则创建默认状态。"""
        state = self._states.get(thread_id)
        if state is None:
            state = CatState()
            self._states[thread_id] = state
        return state

    async def load(self, thread_id: str) -> CatState:
        """
        加载指定线程的猫状态（返回克隆体）。
        返回克隆而非原对象，防止调用方无锁修改导致数据竞争。
        """
        async with self._lock:
            return self._ensure(thread_id).clone()

    async def mutate(self, thread_id: str, mutator: Callable[[CatState], None]) -> CatState:
        """
        在锁内原子地修改猫状态：
          1. 获取/创建状态对象
          2. 调用 mutator 回调就地修改
          3. 返回修改后的克隆体
        """
        async with self._lock:
            state = self._ensure(thread_id)
            mutator(state)
            return state.clone()
