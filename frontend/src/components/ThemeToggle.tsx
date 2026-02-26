/**
 * ThemeToggle.tsx —— 亮暗主题切换按钮组件。
 *
 * 使用 lucide-react 的 Sun / Moon 图标，当前激活的主题按钮高亮显示。
 * 点击按钮调用 Zustand 的 setScheme，触发：
 *   1. document.documentElement.classList 切换 dark 类
 *   2. localStorage 持久化主题偏好
 *   3. ChatKit 组件的 colorScheme 同步更新
 */

import clsx from "clsx";
import { Moon, Sun } from "lucide-react";
import { useAppStore } from "../store/useAppStore";

/** 按钮基础样式：圆形、固定尺寸、过渡动画 */
const buttonBase =
  "inline-flex h-9 w-9 items-center justify-center rounded-full text-[0.7rem] transition-colors duration-200";

export function ThemeToggle() {
  const scheme = useAppStore((state) => state.scheme);
  const setScheme = useAppStore((state) => state.setScheme);
  return (
    <div className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-white/60 p-1 shadow-sm backdrop-blur-sm dark:border-slate-800 dark:bg-slate-900/60">
      {/* 亮色主题按钮 */}
      <button
        type="button"
        onClick={() => setScheme("light")}
        className={clsx(
          buttonBase,
          scheme === "light"
            ? "bg-slate-900 text-white shadow-sm dark:bg-slate-100 dark:text-slate-900"
            : "text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-100"
        )}
        aria-label="Use light theme"
        aria-pressed={scheme === "light"}
      >
        <Sun className="h-4 w-4" aria-hidden />
      </button>
      {/* 暗色主题按钮 */}
      <button
        type="button"
        onClick={() => setScheme("dark")}
        className={clsx(
          buttonBase,
          scheme === "dark"
            ? "bg-slate-900 text-white shadow-sm dark:bg-slate-100 dark:text-slate-900"
            : "text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-100"
        )}
        aria-label="Use dark theme"
        aria-pressed={scheme === "dark"}
      >
        <Moon className="h-4 w-4" aria-hidden />
      </button>
    </div>
  );
}
