"""
名字候选列表 Widget 构建器。

职责：
  - 定义 CatNameSuggestion（名字建议）和 CatNameSelectionPayload（选择载荷）数据模型
  - 加载 .widget 模板文件（JSON + Jinja2），注入候选数据后构建交互式 ListView Widget
  - Widget 中每个选项绑定 cats.select_name 客户端动作
  - 支持 selected 参数标记已选中的名字（选中后其他选项变灰、按钮禁用）
"""

from __future__ import annotations

from chatkit.widgets import WidgetRoot, WidgetTemplate
from pydantic import BaseModel, Field


class CatNameSuggestion(BaseModel):
    """单个名字建议，包含名字和可选的理由说明。"""

    name: str
    reason: str | None = None


class CatNameSelectionPayload(BaseModel):
    """用户从候选列表中选择名字时，发送给服务端的 action payload。"""

    name: str
    options: list[CatNameSuggestion] = Field(default_factory=list)


# 从 .widget 文件加载 Jinja2 模板（在模块初始化时一次性加载）
name_suggestions_widget_template = WidgetTemplate.from_file("cat_name_suggestions.widget")


def build_name_suggestions_widget(
    names: list[CatNameSuggestion],
    selected: str | None = None,
) -> WidgetRoot:
    """
    构建名字候选列表 Widget。

    参数：
      names    - 候选名字列表（由 Agent suggest_cat_names 工具生成）
      selected - 已选中的名字（None 表示尚未选择）

    返回：
      WidgetRoot —— 可序列化为 JSON 的 Widget 树，前端 ChatKit 自动渲染
    """
    print(f"Building name suggestions widget with selected: {selected}")
    print(f"Names: {names}")
    return name_suggestions_widget_template.build(
        data={
            "items": [suggestion.model_dump() for suggestion in names],
            "selected": selected.strip().title() if selected else None,
        }
    )
