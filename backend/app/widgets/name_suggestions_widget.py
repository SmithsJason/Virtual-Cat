"""
定义一个交互式 widget，引导用户为猫选择一个名字。
该 widget 内部关联了两个客户端动作配置。
"""

from __future__ import annotations

from chatkit.widgets import WidgetRoot, WidgetTemplate
from pydantic import BaseModel, Field


class CatNameSuggestion(BaseModel):
    """名字建议，同时附带一小段说明，描述这个名字适合怎样的猫。"""

    name: str
    reason: str | None = None


class CatNameSelectionPayload(BaseModel):
    """当用户从候选名字中做出选择时发送的载荷。"""

    name: str
    options: list[CatNameSuggestion] = Field(default_factory=list)


name_suggestions_widget_template = WidgetTemplate.from_file("cat_name_suggestions.widget")


def build_name_suggestions_widget(
    names: list[CatNameSuggestion],
    selected: str | None = None,
) -> WidgetRoot:
    """渲染一个可选择的列表 widget，用于展示猫名字的候选项。"""
    print(f"Building name suggestions widget with selected: {selected}")
    print(f"Names: {names}")
    return name_suggestions_widget_template.build(
        data={
            "items": [suggestion.model_dump() for suggestion in names],
            "selected": selected.strip().title() if selected else None,
        }
    )
