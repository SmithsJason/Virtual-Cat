"""
猫状态数据模型 —— 单只虚拟猫的核心领域对象。

设计要点：
  - 使用 dataclass 而非 Pydantic，因为需要可变（mutable）的就地修改
  - 三项属性（energy / happiness / cleanliness）全部限制在 [0, 10] 区间
  - 各操作之间带有 **随机交叉扣减**（50% 概率），使三项难以同时满值，增加博弈趣味
  - 花色（color_pattern）在命名时随机分配 —— 这是「渐进式揭晓」机制的核心
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime
from random import choice
from typing import Any

# 状态值的上下限
STATUS_MIN = 0
STATUS_MAX = 10

# 5 种可选花色
COLOR_PATTERNS = ("black", "calico", "colorpoint", "tabby", "white")

# 每种花色对应的文字描述，用于 Agent 生成自然语言回复和档案卡展示
DESCRIPTIONS = {
    "black": "A black cat with large pale yellow eyes.",
    "calico": "A calico cat with pale green eyes, cream paws, and orange and black spots.",
    "colorpoint": "A ragdoll cat with blue eyes and colorpoint coat. Cream fur with darker patches on the ears, face, paws, and tail.",
    "tabby": "A shaggy orange tabby cat with a striped coat and a temper.",
    "white": "A white smily cat with odd eyes - right eye yellow, left eye blue. Pink inner ears.",
}


def _clamp(value: int) -> int:
    """将数值限制在 [STATUS_MIN, STATUS_MAX] 区间内。"""
    return max(STATUS_MIN, min(STATUS_MAX, value))


@dataclass
class CatState:
    """
    表示一只虚拟猫的完整状态，每个 ChatKit 线程拥有独立的 CatState 实例。

    属性：
      name          - 猫的名字，默认 "Unnamed Cat"，命名后不可修改
      energy        - 精力值 [0-10]，喂食增加，玩耍消耗
      happiness     - 快乐值 [0-10]，玩耍增加，清洁可能扣减
      cleanliness   - 清洁度 [0-10]，清洁增加，喂食/玩耍可能扣减
      age           - 年龄（岁），用于档案卡展示
      color_pattern - 花色，命名时随机分配（None 表示尚未命名 / 剪影状态）
      description   - 花色对应的文字描述
      updated_at    - 最后更新时间戳
    """
    name: str = "Unnamed Cat"
    energy: int = 6
    happiness: int = 6
    cleanliness: int = 6
    age: int = 2
    color_pattern: str | None = None
    description: str | None = None
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def touch(self) -> None:
        """更新 updated_at 时间戳，每次状态变更后调用。"""
        self.updated_at = datetime.now()

    def feed(self, amount: int = 3) -> None:
        """
        喂食操作：energy +amount, happiness +1。
        50% 概率 cleanliness -1（随机交叉扣减，增加博弈性）。
        """
        self.energy = _clamp(self.energy + amount)
        self.happiness = _clamp(self.happiness + 1)
        if choice([True, False]):
            self.cleanliness = _clamp(self.cleanliness - 1)
        self.touch()

    def play(self, boost: int = 2) -> None:
        """
        玩耍操作：happiness +boost, energy -1。
        50% 概率 cleanliness -1（随机交叉扣减）。
        """
        self.happiness = _clamp(self.happiness + boost)
        self.energy = _clamp(self.energy - 1)
        if choice([True, False]):
            self.cleanliness = _clamp(self.cleanliness - 1)
        self.touch()

    def clean(self, boost: int = 3) -> None:
        """
        清洁操作：cleanliness +boost。
        50% 概率 happiness -1（随机交叉扣减）。
        """
        self.cleanliness = _clamp(self.cleanliness + boost)
        if choice([True, False]):
            self.happiness = _clamp(self.happiness - 1)
        self.touch()

    def rename(self, value: str) -> None:
        """
        命名操作（一次性）：
          - 设置猫的名字
          - 如果尚无花色，随机从 COLOR_PATTERNS 中分配一个
          - 这是「渐进式揭晓」机制的核心 —— 花色只有命名后才揭晓
        """
        print(f"Renaming cat to {value}")
        self.name = value
        if not self.color_pattern:
            print(f"Choosing random color pattern for {value}")
            self.color_pattern = choice(COLOR_PATTERNS)
            self.description = DESCRIPTIONS[self.color_pattern]
            print(f"Color pattern: {self.color_pattern}")
        self.touch()

    def set_age(self, value: int | None) -> None:
        """设置猫的年龄，限制在 [1, 15] 范围。"""
        if value and isinstance(value, int):
            self.age = min(max(value, 1), 15)
            self.touch()

    def clone(self) -> "CatState":
        """返回当前状态的浅拷贝，用于安全地将状态暴露给外部（避免直接修改原对象）。"""
        return replace(self)

    def to_payload(self, thread_id: str | None = None) -> dict[str, Any]:
        """
        将状态序列化为前端可用的 JSON payload（驼峰命名）。
        可选传入 thread_id 以便前端关联线程。
        """
        payload: dict[str, Any] = {
            "name": self.name,
            "energy": self.energy,
            "happiness": self.happiness,
            "cleanliness": self.cleanliness,
            "age": self.age,
            "colorPattern": self.color_pattern,
            "description": self.description,
            "updatedAt": self.updated_at.isoformat(),
        }
        if thread_id:
            payload["threadId"] = thread_id
        return payload
