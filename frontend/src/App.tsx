/**
 * App.tsx —— 应用根组件，负责页面整体布局。
 *
 * 布局结构：
 *   ┌────────────────────────────────────────────┐
 *   │  Header: "Cozy Cat Lounge" + ThemeToggle   │
 *   ├──────────────────┬─────────────────────────┤
 *   │  ChatKitPanel    │  CatStatusPanel          │
 *   │  (对话聊天框)     │  (猫状态面板 + Quick Actions) │
 *   └──────────────────┴─────────────────────────┘
 *
 * 响应式设计：
 *   - 移动端：flex-col-reverse（猫状态在上，对话在下）
 *   - 桌面端：lg:flex-row（左右并排）
 *
 * 跨面板通信：
 *   Quick Action 按钮通过 chatkitRef.current.sendUserMessage() 将预设 prompt 注入对话
 */

import clsx from "clsx";
import { useCallback, useRef } from "react";

import { CatStatusPanel } from "./components/CatStatusPanel";
import { ChatKitPanel } from "./components/ChatKitPanel";
import type { ChatKit } from "./components/ChatKitPanel";
import { ThemeToggle } from "./components/ThemeToggle";
import { useAppStore } from "./store/useAppStore";

export default function App() {
  // 持有 ChatKit 实例的引用，用于从 CatStatusPanel 发送消息（跨组件通信）
  const chatkitRef = useRef<ChatKit | null>(null);

  // 从 Zustand 获取当前主题色（用于动态 class 切换）
  const scheme = useAppStore((state) => state.scheme);

  /**
   * Quick Action 回调：将 CatStatusPanel 的预设 prompt 通过 ChatKit 发送。
   * 使用 useCallback 缓存，避免 CatStatusPanel 不必要的重渲染。
   */
  const handleQuickAction = useCallback(
    async (message: string) => {
      if (!chatkitRef.current) {
        return;
      }
      await chatkitRef.current.sendUserMessage({ text: message });
    },
    []
  );

  // 根据主题动态切换渐变背景色
  const containerClass = clsx(
    "h-full bg-gradient-to-br transition-colors duration-300",
    scheme === "dark"
      ? "from-slate-900 via-slate-950 to-slate-850 text-slate-100"
      : "from-slate-100 via-white to-slate-200 text-slate-900"
  );
  // Header 栏：毛玻璃效果 + 吸顶
  const headerBarClass = clsx(
    "sticky top-0 z-30 w-full border-b backdrop-blur",
    scheme === "dark"
      ? "bg-slate-950/80 border-slate-800/70 text-slate-100"
      : "bg-white/90 border-slate-200/70 text-slate-900"
  );

  return (
    <div className={containerClass}>
      {/* ========== 顶部导航栏 ========== */}
      <div className={headerBarClass}>
        <div className="relative mx-auto flex w-full max-w-6xl flex-col gap-4 px-6 py-5 pr-20 sm:flex-row sm:items-center sm:gap-6 lg:py-6">
          <h1 className="text-lg font-semibold uppercase tracking-wide">Cozy cat lounge</h1>
          <p className="flex-1 text-sm text-slate-600 dark:text-slate-300">
            Chat with the agent to keep the cat happy.
          </p>
          {/* 亮暗主题切换按钮 */}
          <div className="absolute right-6 top-4">
            <ThemeToggle />
          </div>
        </div>
      </div>
      {/* ========== 双面板主体区域 ========== */}
      <div className="mx-auto flex w-full max-w-6xl flex-col-reverse gap-10 px-6 pb-10 pt-6 md:py-10 lg:flex-row">
        {/* 左侧：ChatKit 对话面板 */}
        <ChatKitPanel
          className="relative w-full md:w-[45%] h-[calc(90vh-100px)] overflow-hidden rounded-3xl bg-white/80 shadow-[0_45px_90px_-45px_rgba(15,23,42,0.6)] ring-1 ring-slate-200/60 backdrop-blur md:h-[calc(90vh-100px)] dark:bg-slate-900/70 dark:shadow-[0_45px_90px_-45px_rgba(15,23,42,0.85)] dark:ring-slate-800/60"
          onChatKitReady={(chatkit) => (chatkitRef.current = chatkit)}
        />
        {/* 右侧：猫状态面板（图片 + 状态条 + Quick Actions） */}
        <CatStatusPanel
          className="relative flex-1 w-full md:w-[45%] h-[calc(90vh-100px)] overflow-hidden rounded-3xl bg-white/80 shadow-[0_45px_90px_-45px_rgba(15,23,42,0.6)] ring-1 ring-slate-200/60 backdrop-blur md:h-[calc(90vh-100px)] dark:bg-slate-900/70 dark:shadow-[0_45px_90px_-45px_rgba(15,23,42,0.85)] dark:ring-slate-800/60"
          onQuickAction={handleQuickAction}
        />
      </div>
    </div>
  );
}
