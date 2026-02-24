"""
这是一个用于非 ChatKit 应用数据的存储实现示例。
"""

from __future__ import annotations

import asyncio
from typing import Callable, Dict

from .cat_state import CatState


class CatStore:
    """按线程 ID 区分的、线程安全的猫状态内存存储。"""

    def __init__(self) -> None:
        self._states: Dict[str, CatState] = {}
        self._lock = asyncio.Lock()

    def _ensure(self, thread_id: str) -> CatState:
        state = self._states.get(thread_id)
        if state is None:
            state = CatState()
            self._states[thread_id] = state
        return state

    async def load(self, thread_id: str) -> CatState:
        async with self._lock:
            return self._ensure(thread_id).clone()

    async def mutate(self, thread_id: str, mutator: Callable[[CatState], None]) -> CatState:
        async with self._lock:
            state = self._ensure(thread_id)
            mutator(state)
            return state.clone()
