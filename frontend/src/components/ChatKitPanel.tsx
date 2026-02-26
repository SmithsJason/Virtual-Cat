/**
 * ChatKitPanel.tsx —— ChatKit 对话面板组件。
 *
 * 核心职责：
 *   1. 集成 @openai/chatkit-react，配置 SSE 流式端点、主题、起始屏幕
 *   2. 监听三类事件：
 *      - onAction:       处理 Widget 客户端动作（选择名字、请求更多名字）
 *      - onEffect:       处理服务端推送的 ClientEffect（状态更新、猫说话）
 *      - onThreadChange: 线程切换时同步猫状态
 *   3. 通过 chatkitRef 暴露 ChatKit 实例，供外部（App.tsx）调用 sendUserMessage
 */

import { ChatKit, useChatKit } from "@openai/chatkit-react";
import clsx from "clsx";
import type { Widgets } from "@openai/chatkit";
import { useCallback, useRef } from "react";

import {
  CHATKIT_API_DOMAIN_KEY,
  CHATKIT_API_URL,
  GREETING,
  STARTER_PROMPTS,
  getPlaceholder,
} from "../lib/config";
import type { CatStatePayload } from "../lib/cat";
import { useAppStore } from "../store/useAppStore";

/** 导出 ChatKit 类型，供 App.tsx 中 chatkitRef 使用 */
export type ChatKit = ReturnType<typeof useChatKit>;

type ChatKitPanelProps = {
  onChatKitReady: (chatkit: ChatKit) => void;
  className?: string;
};

export function ChatKitPanel({
  onChatKitReady,
  className,
}: ChatKitPanelProps) {
  const chatkitRef = useRef<ReturnType<typeof useChatKit> | null>(null);

  // ---- 从 Zustand 细粒度订阅所需状态 ----
  const theme = useAppStore((state) => state.scheme);
  const activeThread = useAppStore((state) => state.threadId);
  const setSpeech = useAppStore((state) => state.setSpeech);
  const setFlashMessage = useAppStore((state) => state.setFlashMessage);
  const setThreadId = useAppStore((state) => state.setThreadId);
  const cat = useAppStore((state) => state.cat);
  const refresh = useAppStore((state) => state.refreshCat);
  const applyUpdate = useAppStore((state) => state.applyCatUpdate);

  /**
   * 处理服务端推送的猫状态更新。
   * 调用 applyCatUpdate 触发 Zustand 状态变更（可能触发 confetti 动画）。
   */
  const handleStatusUpdate = useCallback(
    (state: CatStatePayload, flash?: string) => {
      applyUpdate(state);

      if (flash) {
        setFlashMessage(flash);
      }
    },
    [applyUpdate, setFlashMessage]
  );

  /**
   * Widget 动作处理器 —— 拦截 Widget 内用户的点击交互。
   *
   * 支持两种动作类型：
   *   - cats.more_names:  发送用户消息请求 Agent 生成更多名字建议
   *   - cats.select_name: 调用 sendCustomAction 将选择结果回传服务端，
   *                       然后 refresh() 拉取最新猫状态，完成双向交互闭环
   */
  const handleWidgetAction = useCallback(
    async (
      action: { type: string; payload?: Record<string, unknown> },
      widgetItem: { id: string; widget: Widgets.Card | Widgets.ListView }
    ) => {
      const chatkit = chatkitRef.current;
      if (!chatkit) {
        return;
      }
      // "请求更多名字" —— 直接发一条用户消息触发 Agent
      if (action.type === "cats.more_names") {
        await chatkit.sendUserMessage({ text: "More name suggestions, please" });
        return;
      }
      // "选择名字" —— 发送 server action + 拉取最新状态
      if (action.type === "cats.select_name") {
        if (!activeThread) {
          console.warn("Ignoring name selection without an active thread.");
          return;
        }
        await chatkit.sendCustomAction(action, widgetItem.id);
        const data = await refresh();
        if (data) {
          handleStatusUpdate(data, `Now called ${data.name}`);
        }
        return;
      }
    },
    [refresh, handleStatusUpdate, activeThread]
  );

  /**
   * ClientEffect 事件处理器 —— 接收服务端通过 SSE 推送的客户端特效。
   *
   * 支持两种特效：
   *   - update_cat_status: 更新猫状态 + 显示 flash 消息
   *   - cat_say:           显示猫的语音气泡
   */
  const handleClientEffect = useCallback(({name, data}: {
    name: string;
    data: Record<string, unknown>;
  }) => {
      if (name === "update_cat_status") {
        const catState = data.state as CatStatePayload | undefined;
        if (catState) {
          handleStatusUpdate(catState, data.flash as string | undefined);
        }
      }

      if (name === "cat_say") {
        const message = String(data.message ?? "");
        if (message) {
          setSpeech({message});
        }
      }
    }, [])

  // ---- 初始化 ChatKit 实例 ----
  const chatkit = useChatKit({
    // SSE 流式端点配置
    api: { url: CHATKIT_API_URL, domainKey: CHATKIT_API_DOMAIN_KEY },
    // 主题配置：spacious 密度、圆角、根据暗色模式调整色调
    theme: {
      density: "spacious",
      colorScheme: theme,
      color: {
        grayscale: {
          hue: 220,
          tint: 6,
          shade: theme === "dark" ? -1 : -4,
        },
        accent: {
          primary: theme === "dark" ? "#f1f5f9" : "#0f172a",
          level: 1,
        },
      },
      radius: "round",
    },
    // 起始引导屏：欢迎语 + 预设 prompt 快捷按钮
    startScreen: {
      greeting: GREETING,
      prompts: STARTER_PROMPTS,
    },
    // 动态输入框占位符（根据猫是否已命名显示不同文案）
    composer: {
      placeholder: getPlaceholder(cat.name),
    },
    // 禁用消息反馈按钮
    threadItemActions: {
      feedback: false,
    },
    // Widget 动作回调
    widgets: {
      onAction: handleWidgetAction,
    },
    // 线程切换时同步猫状态
    onThreadChange: ({ threadId }) => setThreadId(threadId),
    onError: ({ error }) => {
      console.error("ChatKit error", error);
    },
    // ChatKit 就绪后暴露实例给父组件
    onReady: () => {
      onChatKitReady?.(chatkit);
    },
    // 客户端特效回调
    onEffect: handleClientEffect,
  });
  chatkitRef.current = chatkit;

  return (
    <div className={clsx("relative h-full w-full overflow-hidden", className)}>
      <ChatKit control={chatkit.control} className="block h-full w-full" />
    </div>
  );
}
