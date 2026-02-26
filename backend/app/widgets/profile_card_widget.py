"""
猫档案卡 Widget 构建器 —— 静态展示型 Widget。

职责：
  - 加载 cat_profile.widget 模板文件
  - 根据猫的状态（名字、花色、年龄等）填充模板数据
  - 根据花色选择对应的头像图片 URL
  - 构建加州风格 "meowing license" 档案卡 Widget
"""

from __future__ import annotations

from chatkit.widgets import WidgetRoot, WidgetTemplate

from ..cat_state import CatState

# 从 .widget 文件加载 Jinja2 模板
cat_profile_widget_template = WidgetTemplate.from_file("cat_profile.widget")


def _format_age_label(age: int) -> str:
    """格式化年龄标签：1 year / N years。"""
    return "1 year" if age == 1 else f"{age} years"


def _format_color_pattern_label(color_pattern: str | None) -> str:
    """格式化花色标签：首字母大写，未命名时显示 N/A。"""
    if color_pattern is None:
        return "N/A"
    return color_pattern.capitalize()


def _format_favorite_toy(favorite_toy: str | None) -> str:
    """格式化喜爱玩具标签：默认 "A laser pointer"。"""
    if favorite_toy is None:
        return "A laser pointer"
    return favorite_toy.capitalize()


def _image_src(state: CatState) -> str:
    """
    根据猫的花色返回对应的头像图片 URL。
    5 种花色各有独立的图片资源，未命名时返回剪影图片。
    """
    if state.color_pattern == "black":
        return "https://files.catbox.moe/pbkakb.png"
    if state.color_pattern == "calico":
        return "https://files.catbox.moe/p2mj4g.png"
    if state.color_pattern == "colorpoint":
        return "https://files.catbox.moe/nrtexw.png"
    if state.color_pattern == "tabby":
        return "https://files.catbox.moe/zn77bd.png"
    if state.color_pattern == "white":
        return "https://files.catbox.moe/zvkhpo.png"
    # 未命名 / 未知花色 —— 返回剪影
    return "https://files.catbox.moe/e42tgh.png"


def build_profile_card_widget(state: CatState, favorite_toy: str | None = None) -> WidgetRoot:
    """
    构建猫档案卡 Widget。
    将猫的名字、头像、年龄、花色、喜爱玩具注入模板，生成 WidgetRoot。
    """
    return cat_profile_widget_template.build(
        data={
            "name": state.name,
            "image_src": _image_src(state),
            "age": _format_age_label(state.age),
            "color_pattern": _format_color_pattern_label(state.color_pattern),
            "favorite_toy": _format_favorite_toy(favorite_toy),
        }
    )


def profile_widget_copy_text(state: CatState) -> str:
    """生成档案卡的纯文本复制内容（用于 ChatKit 的 copy-to-clipboard 功能）。"""
    return f"{state.name}, age {state.age}, is a {state.color_pattern} cat."
