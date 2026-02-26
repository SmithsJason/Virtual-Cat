"""
ChatKit Store 的内存实现 —— 管理对话线程和消息条目。

职责：
  - 实现 ChatKit SDK 要求的 Store[dict] 接口
  - 支持线程（Thread）的 CRUD：创建/读取/更新/删除
  - 支持线程条目（ThreadItem）的 CRUD：添加/读取/更新/删除
  - 提供通用的游标分页方法 _paginate()

注意：纯内存实现，进程重启即丢失。生产环境应替换为数据库（如 PostgreSQL、Redis）。
"""

from __future__ import annotations

from collections import defaultdict

from chatkit.store import NotFoundError, Store
from chatkit.types import Attachment, Page, ThreadItem, ThreadMetadata


class MemoryStore(Store[dict]):
    """
    基于字典的内存存储，实现 ChatKit Store 完整接口。

    数据结构：
      threads: Dict[thread_id, ThreadMetadata]  — 线程元信息
      items:   Dict[thread_id, List[ThreadItem]] — 每个线程的消息/Widget/隐藏上下文条目列表
    """

    def __init__(self):
        self.threads: dict[str, ThreadMetadata] = {}
        self.items: dict[str, list[ThreadItem]] = defaultdict(list)

    # ==================== 线程操作 ====================

    async def load_thread(self, thread_id: str, context: dict) -> ThreadMetadata:
        """加载单个线程元信息，不存在则抛出 NotFoundError。"""
        if thread_id not in self.threads:
            raise NotFoundError(f"Thread {thread_id} not found")
        return self.threads[thread_id]

    async def save_thread(self, thread: ThreadMetadata, context: dict) -> None:
        """保存/更新线程元信息（如更新标题）。"""
        self.threads[thread.id] = thread

    async def load_threads(
        self, limit: int, after: str | None, order: str, context: dict
    ) -> Page[ThreadMetadata]:
        """分页加载线程列表，按创建时间排序。"""
        threads = list(self.threads.values())
        return self._paginate(
            threads, after, limit, order, sort_key=lambda t: t.created_at, cursor_key=lambda t: t.id
        )

    async def delete_thread(self, thread_id: str, context: dict) -> None:
        """删除线程及其所有条目。"""
        self.threads.pop(thread_id, None)
        self.items.pop(thread_id, None)

    # ==================== 线程条目操作 ====================

    async def load_thread_items(
        self, thread_id: str, after: str | None, limit: int, order: str, context: dict
    ) -> Page[ThreadItem]:
        """分页加载指定线程的条目（消息、Widget、隐藏上下文等）。"""
        items = self.items.get(thread_id, [])
        return self._paginate(
            items, after, limit, order, sort_key=lambda i: i.created_at, cursor_key=lambda i: i.id
        )

    async def add_thread_item(self, thread_id: str, item: ThreadItem, context: dict) -> None:
        """向线程追加一个新条目。"""
        self.items[thread_id].append(item)

    async def save_item(self, thread_id: str, item: ThreadItem, context: dict) -> None:
        """更新已有条目（按 id 匹配），若不存在则追加。"""
        items = self.items[thread_id]
        for idx, existing in enumerate(items):
            if existing.id == item.id:
                items[idx] = item
                return
        items.append(item)

    async def load_item(self, thread_id: str, item_id: str, context: dict) -> ThreadItem:
        """按 id 加载单个条目。"""
        for item in self.items.get(thread_id, []):
            if item.id == item_id:
                return item
        raise NotFoundError(f"Item {item_id} not found in thread {thread_id}")

    async def delete_thread_item(self, thread_id: str, item_id: str, context: dict) -> None:
        """按 id 删除指定条目。"""
        self.items[thread_id] = [
            item for item in self.items.get(thread_id, []) if item.id != item_id
        ]

    # ==================== 通用分页 ====================

    def _paginate(
        self, rows: list, after: str | None, limit: int, order: str, sort_key, cursor_key
    ):
        """
        通用游标分页方法：
          1. 按 sort_key 排序（支持正序/倒序）
          2. 如果有 after 游标，定位到该游标之后的位置
          3. 截取 limit 条数据
          4. 计算 has_more 和 next_after 游标
        """
        sorted_rows = sorted(rows, key=sort_key, reverse=order == "desc")
        start = 0
        if after:
            for idx, row in enumerate(sorted_rows):
                if cursor_key(row) == after:
                    start = idx + 1
                    break
        data = sorted_rows[start : start + limit]
        has_more = start + limit < len(sorted_rows)
        next_after = cursor_key(data[-1]) if has_more and data else None
        return Page(data=data, has_more=has_more, after=next_after)

    # ==================== 附件操作（未实现）====================

    async def save_attachment(self, attachment: Attachment, context: dict) -> None:
        raise NotImplementedError()

    async def load_attachment(self, attachment_id: str, context: dict) -> Attachment:
        raise NotImplementedError()

    async def delete_attachment(self, attachment_id: str, context: dict) -> None:
        raise NotImplementedError()
