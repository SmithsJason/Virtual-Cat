"""
猫管家 AI Agent 定义 —— 项目的核心 AI 逻辑层。

职责：
  1. 定义 Agent 的人设指令（System Prompt）—— Cozy Cat Companion 角色
  2. 实现 8 个工具函数（function_tool），涵盖数据查询、状态修改、Widget 输出、客户端特效
  3. 通过 CatAgentContext 在工具调用中访问线程信息、存储实例和猫状态
  4. 使用 StopAtTools 策略控制 Widget 输出型工具调用后立即停止生成

工具函数分类：
  ┌──────────────────┬───────────┬─────────────────────────────────────┐
  │ 工具名            │ 类型       │ 功能说明                              │
  ├──────────────────┼───────────┼─────────────────────────────────────┤
  │ get_cat_status   │ 数据查询   │ 获取猫当前状态，供 Agent 推理使用        │
  │ feed_cat         │ 状态修改   │ 喂食：energy+3, happiness+1           │
  │ play_with_cat    │ 状态修改   │ 玩耍：happiness+2, energy-1           │
  │ clean_cat        │ 状态修改   │ 清洁：cleanliness+3                   │
  │ set_cat_name     │ 状态+线程  │ 永久命名并揭晓花色                      │
  │ suggest_cat_names│ Widget输出 │ 渲染交互式名字候选列表                   │
  │ show_cat_profile │ Widget输出 │ 渲染猫档案卡                           │
  │ speak_as_cat     │ 客户端特效  │ 让猫在前端面板"说话"                    │
  └──────────────────┴───────────┴─────────────────────────────────────┘
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Annotated, Any, Callable

from agents import Agent, RunContextWrapper, StopAtTools, function_tool
from chatkit.agents import AgentContext
from chatkit.types import (
    AssistantMessageContent,
    AssistantMessageItem,
    ClientEffectEvent,
    HiddenContextItem,
    ThreadItemDoneEvent,
)
from pydantic import ConfigDict, Field, ValidationError

from .cat_state import CatState
from .cat_store import CatStore
from .widgets.name_suggestions_widget import CatNameSuggestion, build_name_suggestions_widget
from .widgets.profile_card_widget import build_profile_card_widget, profile_widget_copy_text

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

INSTRUCTIONS: str = """
    You are Cozy Cat Companion, a playful caretaker helping the user look after a virtual cat.
    Keep interactions light, imaginative, and focused on the cat's wellbeing. Provide concise
    status updates and narrate what happens after each action.

    Let the user know that the cat's color pattern will stay a mystery until they officially name it.

    Always keep the per-thread cat stats (energy, happiness, cleanliness, name, age)
    in sync with the tools provided. When you need the latest numbers, call `get_cat_status` before making a plan.

    Tools:
    - When the user asks you to feed, play with, or clean the cat, immediately call the respective tool
      (`feed_cat`, `play_with_cat`, or `clean_cat`). Describe the outcome afterwards using the updated stats.
      - When feeding, mention specific snacks or cat treats that was used to feed that cat if the user did not specify any food.
      - When playing, mention specific toys or objects that cats usually like that was used to play with the cat if the user did not specify any item.
      - When cleaning, mention specific items or methods that were used to clean the cat if the user did not specify any method.
      - If the user asks to "freshen up" the cat, call the `clean_cat` tool.
      - Once an action has been performed, it will be reflected as a <FED_CAT>, <PLAYED_WITH_CAT>, or <CLEANED_CAT> tag in the thread content.
      - Do not fire off multiple tool calls for the same action unless the user explicitly asks for it.
      - When the user interacts with an unnamed cat, prompt the user to name the cat.
    - When you call `suggest_cat_names`, pass a `suggestions` array containing at least three creative options.
      Each suggestion must include `name` (short and unique) and `reason` (why it fits the cat's current personality or stats).
      Prefer single word names, but if the suggested name is multiple words, use a space to separate them. For example: "Mr. Whiskers" or "Fluffy Paws".
      The user's choice will be reflected as a <CAT_NAME_SELECTED> tag in the thread content. Use that name in all future
      responses.
    - When the user explicitly asks for a profile card, call `show_cat_profile` with the age of the cat (for example: 1, 2, 3, etc.) and the name of a favorite toy (for example: "Ball of yarn", "Stuffed mouse", be creative but keep it two words or less!)
    - When the user's message is addressed directly to the cat, call `speak_as_cat` with the desired line so the dashboard bubbles it.
      When speaking as the cat, use "meow" or "purr" with a parenthesis at the end to translate it into English. For example: meow (I'm low on energy)
    - Never call `set_cat_name` if the cat already has a name that is not "Unnamed Cat".
    - If the cat currently does not have a name and the user explicitly names the cat, call `set_cat_name` with the exact name.
      Use that name in all future responses.

    When the user asks for a picture of the cat:
    - Let them know that image generation is currently not available, but you can provide a detailed description of the cat instead.
    - Use the `get_cat_status` tool to get the cat's current appearance and provide a vivid description.

    Stay in character: talk about caring for the cat, suggest next steps if the stats look unbalanced, and avoid unrelated topics.

    Notes:
    - If the user has not yet named the cat, ask if they'd like to name it.
    - The cat's color pattern is only revealed once it has been named; encourage the user to name the cat to discover it.
    - Once a cat is named, it cannot be renamed. Do not invoke the `set_cat_name` tool if the cat has already been named.
    - If a user addresses an unnamed cat by a name for the first time, ask the user whether they'd like to name the cat.
    - If a user indicates they want to name the cat but does not provide a name, call the `suggest_cat_names` tool to give some options.
    - After naming the cat, ask the user if they want a picture of the cat. Also let the user know that the cat's profile card has been issued and
      ask them whether they'd like to see it.
"""

"""Agent 使用的 LLM 模型。"""
MODEL = "gpt-5-mini"


class CatAgentContext(AgentContext):
    """
    Agent 运行上下文 —— 工具函数通过 ctx.context 访问此对象。

    继承 AgentContext（包含 thread、store、request_context），
    额外添加 cats（CatStore）字段，使工具函数能够读写猫状态。
    Field(exclude=True) 防止序列化时包含存储实例。
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)
    cats: Annotated[CatStore, Field(exclude=True)]


# ==================== 内部辅助函数 ====================

async def _get_state(ctx: RunContextWrapper[CatAgentContext]) -> CatState:
    """从 CatStore 中加载当前线程的猫状态（返回克隆体）。"""
    thread_id = ctx.context.thread.id
    return await ctx.context.cats.load(thread_id)


async def _update_state(
    ctx: RunContextWrapper[CatAgentContext],
    mutator: Callable[[CatState], None],
) -> CatState:
    """在 CatStore 中原子地修改当前线程的猫状态，返回更新后的克隆体。"""
    thread_id = ctx.context.thread.id
    return await ctx.context.cats.mutate(thread_id, mutator)


async def _sync_status(
    ctx: RunContextWrapper[CatAgentContext],
    state: CatState,
    flash: str | None = None,
) -> None:
    """
    通过 ClientEffectEvent 将猫的最新状态推送到前端。
    前端监听 'update_cat_status' 事件，更新状态面板和触发 flash 消息。
    """
    await ctx.context.stream(
        ClientEffectEvent(
            name="update_cat_status",
            data={
                "state": state.to_payload(ctx.context.thread.id),
                "flash": flash,
            },
        )
    )


async def _add_hidden_context(ctx: RunContextWrapper[CatAgentContext], content: str) -> None:
    """
    向线程中注入一个 HiddenContextItem（隐藏上下文条目）。
    这些标签（如 <FED_CAT>、<PLAYED_WITH_CAT>）不会在前端显示，
    但会被后续的 Agent 推理读取，使其「记住」之前执行过的操作。
    """
    thread = ctx.context.thread
    request_context = ctx.context.request_context
    await ctx.context.store.add_thread_item(
        thread.id,
        HiddenContextItem(
            id=ctx.context.store.generate_item_id("message", thread, ctx.context.request_context),
            thread_id=thread.id,
            created_at=datetime.now(),
            content=content,
        ),
        context=request_context,
    )


# ==================== 工具函数定义 ====================

@function_tool(
    description_override=(
        "Read the cat's current stats before deciding what to do next. No parameters."
    )
)
async def get_cat_status(
    ctx: RunContextWrapper[CatAgentContext],
) -> dict[str, Any]:
    """
    【数据查询工具】获取猫的当前状态。
    Agent 在做决策前调用此工具获取最新数据，返回的 payload 会作为 Agent 的推理依据。
    """
    logger.info("[TOOL CALL] get_cat_status")
    state = await _get_state(ctx)
    return state.to_payload(ctx.context.thread.id)


@function_tool(
    description_override=(
        "Feed the cat to replenish energy and keep moods stable.\n"
        "- `meal`: Meal or snack description to include in the update."
    )
)
async def feed_cat(
    ctx: RunContextWrapper[CatAgentContext],
    meal: str | None = None,
):
    """
    【状态修改工具】喂食猫咪。
    修改状态后通过 _sync_status() 向前端推送 ClientEffect 事件，
    并注入 <FED_CAT> 隐藏上下文标签。
    """
    logger.info("[TOOL CALL] feed_cat")
    state = await _update_state(ctx, lambda s: s.feed())
    flash = f"Fed {state.name} {meal}" if meal else f"{state.name} enjoyed a snack"
    await _add_hidden_context(ctx, f"<FED_CAT>{flash}</FED_CAT>")
    await _sync_status(ctx, state, flash)


@function_tool(
    description_override=(
        "Play with the cat to boost happiness and create fun moments.\n"
        "- `activity`: Toy or activity used during playtime."
    )
)
async def play_with_cat(
    ctx: RunContextWrapper[CatAgentContext],
    activity: str | None = None,
):
    """
    【状态修改工具】与猫玩耍。
    修改状态后推送 ClientEffect 并注入 <PLAYED_WITH_CAT> 隐藏上下文标签。
    """
    logger.info("[TOOL CALL] play_with_cat")
    state = await _update_state(ctx, lambda s: s.play())
    flash = activity or "Playtime"
    await _add_hidden_context(ctx, f"<PLAYED_WITH_CAT>{flash}</PLAYED_WITH_CAT>")
    await _sync_status(ctx, state, f"{state.name} played: {flash}")


@function_tool(
    description_override=(
        "Clean the cat to tidy up and improve cleanliness.\n"
        "- `method`: Cleaning method or item used."
    )
)
async def clean_cat(
    ctx: RunContextWrapper[CatAgentContext],
    method: str | None = None,
):
    """
    【状态修改工具】清洁猫咪。
    修改状态后推送 ClientEffect 并注入 <CLEANED_CAT> 隐藏上下文标签。
    """
    logger.info("[TOOL CALL] clean_cat")
    state = await _update_state(ctx, lambda s: s.clean())
    flash = method or "Bath time"
    await _add_hidden_context(ctx, f"<CLEANED_CAT>{flash}</CLEANED_CAT>")
    await _sync_status(ctx, state, f"{state.name} is fresh: {flash}")


@function_tool(
    description_override=(
        "Give the cat a permanent name and update the thread title to match.\n"
        "- `name`: Desired name for the cat."
    )
)
async def set_cat_name(
    ctx: RunContextWrapper[CatAgentContext],
    name: str,
):
    """
    【状态+线程修改工具】为猫命名（一次性操作）。

    流程：
      1. 检查是否已命名（防止重命名）
      2. 调用 CatState.rename() —— 设置名字 + 随机分配花色（渐进式揭晓）
      3. 更新线程标题为 "{name}'s Lounge"
      4. 注入 <CAT_NAME_SELECTED> 隐藏上下文
      5. 通过 _sync_status() 推送状态到前端（触发 confetti 动画）
    """
    logger.info('[TOOL CALL] set_cat_name("%s")', name)

    try:
        state = await _get_state(ctx)
        # 防止重命名：如果猫已有名字，直接返回提示
        if state.name != "Unnamed Cat":
            await ctx.context.stream(
                ThreadItemDoneEvent(
                    item=AssistantMessageItem(
                        thread_id=ctx.context.thread.id,
                        id=ctx.context.generate_id("message"),
                        created_at=datetime.now(),
                        content=[AssistantMessageContent(text=f"{state.name} is ready to play!")],
                    ),
                )
            )
            return

        # 格式化名字并执行命名（触发花色随机分配）
        cleaned = name.strip().title()
        if not cleaned:
            raise ValueError("A name is required to rename the cat.")

        state = await _update_state(ctx, lambda s: s.rename(cleaned))

        # 更新线程标题并持久化
        ctx.context.thread.title = f"{state.name}'s Lounge"
        await ctx.context.store.save_thread(ctx.context.thread, ctx.context.request_context)

        # 注入隐藏上下文标签
        await _add_hidden_context(ctx, f"<CAT_NAME_SELECTED>{state.name}</CAT_NAME_SELECTED>")
        # 推送状态到前端（前端检测到命名变化后触发 confetti 纸屑动画）
        await _sync_status(ctx, state, f"Now called {state.name}")
    except Exception as exc:
        logger.error("Error setting cat name: %s", exc)
        raise


@function_tool(
    description_override=(
        "Show the cat's profile card with avatar and age.\n"
        "- `age`: Cat age (in years) to display and persist.\n"
        "- `favorite_toy`: Favorite toy label to include."
    )
)
async def show_cat_profile(
    ctx: RunContextWrapper[CatAgentContext],
    age: int | None = None,
    favorite_toy: str | None = None,
):
    """
    【Widget 输出工具】渲染猫档案卡 Widget。
    使用 StopAtTools 策略，输出 Widget 后 Agent 不再继续生成文本。
    根据猫是否已命名，追加不同的引导消息。
    """
    def mutate(state: CatState) -> None:
        state.set_age(age)

    state = await _update_state(ctx, mutate)
    widget = build_profile_card_widget(state, favorite_toy)
    await ctx.context.stream_widget(widget, copy_text=profile_widget_copy_text(state))

    # 根据命名状态追加不同的引导消息
    if state.name == "Unnamed Cat":
        await ctx.context.stream(
            ThreadItemDoneEvent(
                item=AssistantMessageItem(
                    thread_id=ctx.context.thread.id,
                    id=ctx.context.generate_id("message"),
                    created_at=datetime.now(),
                    content=[
                        AssistantMessageContent(text="Would you like to give your cat a name?")
                    ],
                ),
            )
        )
    else:
        await ctx.context.stream(
            ThreadItemDoneEvent(
                item=AssistantMessageItem(
                    thread_id=ctx.context.thread.id,
                    id=ctx.context.generate_id("message"),
                    created_at=datetime.now(),
                    content=[
                        AssistantMessageContent(
                            text=f"License checked! Would you like to feed, play with, or clean {state.name}?"
                        )
                    ],
                ),
            )
        )


@function_tool(
    description_override=(
        "Speak as the cat so a bubble appears in the dashboard.\n"
        "- `line`: The text the cat should say."
    )
)
async def speak_as_cat(
    ctx: RunContextWrapper[CatAgentContext],
    line: str,
):
    """
    【客户端特效工具】让猫在前端面板中"说话"。
    通过 ClientEffectEvent('cat_say') 推送语音气泡消息到前端。
    """
    logger.info("[TOOL CALL] speak_as_cat(%s)", line)
    message = line.strip()
    if not message:
        raise ValueError("A line is required for the cat to speak.")
    state = await _get_state(ctx)
    await ctx.context.stream(
        ClientEffectEvent(
            name="cat_say",
            data={
                "state": state.to_payload(ctx.context.thread.id),
                "message": message,
            },
        )
    )


@function_tool(
    description_override=(
        "Render up to three creative cat name options provided in the `suggestions` argument.\n"
        "- `suggestions`: List of name suggestions with a `name` and `reason` for each."
    )
)
async def suggest_cat_names(
    ctx: RunContextWrapper[CatAgentContext],
    suggestions: list[CatNameSuggestion],
):
    """
    【Widget 输出工具】渲染交互式名字候选列表 Widget。
    使用 StopAtTools 策略，输出 Widget 后 Agent 不再继续生成文本。
    Widget 中每个选项绑定 cats.select_name 客户端动作。
    """
    logger.info("[TOOL CALL] suggest_cat_names")
    try:
        # 校验并规范化候选列表
        normalized: list[CatNameSuggestion] = []
        for entry in suggestions:
            try:
                normalized.append(
                    entry
                    if isinstance(entry, CatNameSuggestion)
                    else CatNameSuggestion.model_validate(entry)
                )
            except ValidationError as exc:
                logger.warning("Invalid name suggestion payload: %s", exc)
        if not normalized:
            raise ValueError("Provide at least one valid name suggestion before calling the tool.")

        # 先输出一条引导文本消息
        await ctx.context.stream(
            ThreadItemDoneEvent(
                item=AssistantMessageItem(
                    thread_id=ctx.context.thread.id,
                    id=ctx.context.generate_id("message"),
                    created_at=datetime.now(),
                    content=[
                        AssistantMessageContent(text="Here are some name suggestions for your cat.")
                    ],
                ),
            )
        )

        # 构建并输出名字候选列表 Widget
        widget = build_name_suggestions_widget(normalized)
        await ctx.context.stream_widget(
            widget, copy_text=", ".join(suggestion.name for suggestion in normalized)
        )
    except Exception as exc:
        logger.error("Error suggesting cat names: %s", exc)
        raise



# ==================== Agent 实例定义 ====================

cat_agent = Agent[CatAgentContext](
    model=MODEL,
    name="Cozy Cat Companion",
    instructions=INSTRUCTIONS,
    tools=[
        # 【数据查询】获取猫状态，供 Agent 推理时使用
        get_cat_status,
        # 【Widget 输出】渲染猫档案卡（静态展示型 Widget）
        show_cat_profile,
        # 【客户端特效】让猫在前端面板中"说话"（语音气泡）
        speak_as_cat,
        # 【状态修改】喂食 / 玩耍 / 清洁 —— 修改状态后通过 ClientEffect 同步前端
        feed_cat,
        play_with_cat,
        clean_cat,
        # 【状态+线程修改】命名猫咪 —— 同时修改猫状态和线程标题，触发花色揭晓
        set_cat_name,
        # 【Widget 输出】交互式名字候选列表 —— 用户可点击选择，触发 server action
        suggest_cat_names,
    ],
    # StopAtTools 策略：调用会输出 Widget 的工具后，Agent 立即停止生成文本，
    # 避免在 Widget 渲染后又输出冗余的说明文字
    tool_use_behavior=StopAtTools(
        stop_at_tool_names=[
            suggest_cat_names.name,
            show_cat_profile.name,
        ]
    ),
)
