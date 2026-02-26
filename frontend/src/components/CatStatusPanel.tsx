/**
 * CatStatusPanel.tsx —— 猫状态展示面板组件。
 *
 * 功能模块：
 *   1. 猫名字 + 头像图片（根据花色映射，未命名显示剪影）
 *   2. 语音气泡（猫"说话"时显示，10s 自动消失）
 *   3. Flash 消息（操作后的浮动提示条，10s 自动消失）
 *   4. 三项状态条（Energy / Happiness / Cleanliness），颜色随数值变化
 *   5. Quick Actions 快捷按钮（Give snack / Play with toy / Freshen up）
 */

import clsx from "clsx";
import { useCallback, useMemo } from "react";

import blackCatImage from "../assets/black-cat.png";
import calicoCatImage from "../assets/calico-cat.png";
import ragDollCatImage from "../assets/rag-doll-cat.png";
import maineCoonCatImage from "../assets/maine-coon-cat.png";
import whiteCatImage from "../assets/white-cat.png";
import unknownCatImage from "../assets/whos-that-cat.png";
import type { CatColorPattern, CatStatePayload } from "../lib/cat";
import { useAppStore } from "../store/useAppStore";

/** 三项状态条的配置 */
const STATUS_CONFIG = [
  { key: "energy", label: "Energy"},
  { key: "happiness", label: "Happiness"},
  { key: "cleanliness", label: "Cleanliness"},
];

type CatStatusPanelProps = {
  onQuickAction?: (message: string) => Promise<void> | void;
  className?: string;
};

type QuickAction = {
  id: string;
  label: string;
  description: string;
  /** 根据猫的当前状态生成预设 prompt */
  prompt: (cat: CatStatePayload) => string;
};

/** 花色 → 图片资源映射表 */
const CAT_IMAGE_BY_PATTERN: Record<CatColorPattern, string> = {
  black: blackCatImage,
  calico: calicoCatImage,
  colorpoint: ragDollCatImage,
  tabby: maineCoonCatImage,
  white: whiteCatImage,
};

/** Quick Action 快捷操作定义，每个按钮生成不同的对话 prompt */
const QUICK_ACTIONS: QuickAction[] = [
  {
    id: "treat",
    label: "Give snack",
    description: "+happiness, +energy",
    prompt: (cat) => `Please give ${cat.name} a crunchy fish treat so they feel cared for.`,
  },
  {
    id: "play",
    label: "Play with toy",
    description: "Burn zoomies",
    prompt: (cat) => `Start a quick play session with ${cat.name} using their favorite ribbon toy.`,
  },
  {
    id: "groom",
    label: "Freshen up",
    description: "Improve cleanliness",
    prompt: (cat) => `Give ${cat.name} a bath to freshen up.`,
  },
];

export function CatStatusPanel({ onQuickAction, className }: CatStatusPanelProps) {
  // 从 Zustand 细粒度订阅：只取需要的字段，避免无关状态变更触发重渲染
  const speech = useAppStore((state) => state.speech);
  const flashMessage = useAppStore((state) => state.flashMessage);
  const cat = useAppStore((state) => state.cat);

  /** 处理 Quick Action 点击：生成预设 prompt 并通过回调发送到 ChatKit */
  const handleQuickAction = useCallback(
    (action: QuickAction) => onQuickAction(action.prompt(cat)),
    [cat]
  );

  /** useMemo 缓存猫图片计算：仅在 colorPattern 变化时重新计算 */
  const catImage = useMemo(() => {
    if (!cat.colorPattern) {
      return unknownCatImage;  // 未命名 → 显示剪影
    }
    return CAT_IMAGE_BY_PATTERN[cat.colorPattern] ?? unknownCatImage;
  }, [cat.colorPattern]);

  return (
    <div
      className={clsx(
        "relative flex h-full w-full flex-col items-center justify-between gap-8 p-8 text-center",
        className,
      )}
    >
      {/* ========== 猫名字 ========== */}
      <div className="space-y-2">
        <h2 className="text-3xl font-semibold text-slate-900 dark:text-white">
          {cat.name}
        </h2>
      </div>

      {/* ========== 猫头像 + 语音气泡 / Flash 消息 ========== */}
      <div className="relative w-full flex items-center justify-center">
        <img
          src={catImage}
          alt="Illustrated cat"
          className="h-48 w-48 object-contain drop-shadow-xl"
        />
        {/* 语音气泡：猫"说话"时显示，带 CSS 三角箭头和淡入动画 */}
        {speech ? (
          <div
            key={speech.id}
            className="absolute flex animate-fade-in items-center justify-center -bottom-10 w-40 rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-800 shadow-lg dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100"
          >
            {speech.message}
            {/* CSS 三角箭头指向猫图片 */}
            <span
              aria-hidden
              className="pointer-events-none absolute -top-2 left-10 block h-4 w-4 rotate-45 border-l border-t border-slate-200 bg-white shadow-[-4px_-4px_10px_-3px_rgba(15,23,42,0.4)] dark:border-slate-700 dark:bg-slate-800"
            />
          </div>
        ) : null}
        {/* Flash 消息：操作后的浮动提示（如 "Fed Miso tuna treats"） */}
        {flashMessage ? (
          <div className="absolute flex items-center justify-center -bottom-1">
            <div
              key={flashMessage}
              className="animate-fade-in rounded-full border px-4 py-1 text-sm font-medium"
              style={{
                backgroundColor: "#fff5f0",
                color: "#923b0f",
                borderColor: "#ff9e6c",
              }}
            >
              {flashMessage}
            </div>
          </div>
        ) : null}
      </div>

      {/* ========== 状态条 + Quick Actions ========== */}
      <div className="w-full space-y-5">
        {/* 三项状态条 */}
        <div className="space-y-3">
          {STATUS_CONFIG.map((status) => (
            <StatusMeter
              key={status.key}
              label={status.label}
              value={cat[status.key as keyof CatStatePayload] as number}
            />
          ))}
        </div>

        {/* Quick Actions 快捷按钮区域 */}
        <div className="mt-auto w-full border-t border-slate-200/80 pt-4 text-left dark:border-slate-800/60">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
            Quick actions
          </p>
          <div className="mt-3 flex flex-col gap-3 sm:flex-row">
            {QUICK_ACTIONS.map((action) => {
              return (
                <button
                  key={action.id}
                  type="button"
                  onClick={() => handleQuickAction(action)}
                  className={clsx(
                    "flex-1 rounded-2xl border px-4 py-3 text-left shadow-sm transition-colors",
                    "border-slate-200 bg-white/80 text-slate-800 hover:border-slate-300 hover:bg-white dark:border-slate-700 dark:bg-slate-900/70 dark:text-slate-100 dark:hover:border-slate-600",
                  )}
                >
                  <div className="text-sm font-semibold">{action.label}</div>
                  <div className="text-xs text-slate-500 dark:text-slate-400">
                    {action.description}
                  </div>
                </button>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}

// ==================== 子组件：状态条 ====================

type StatusMeterProps = {
  label: string;
  value: number;
};

/**
 * StatusMeter —— 单项状态条组件。
 * 根据数值（0-10）显示不同颜色：>= 7 绿色, >= 5 黄色, >= 3 橙色, < 3 红色。
 */
function StatusMeter({ label, value }: StatusMeterProps) {
  const normalized = Math.max(0, Math.min(10, Number(value) || 0));
  const percentage = (normalized / 10) * 100;
  const colorClass = getColor(normalized);

  return (
    <div>
      <div className="flex items-center justify-between text-sm font-medium text-slate-600 dark:text-slate-300">
        <span>{label}</span>
        <span className="text-xs text-slate-400 dark:text-slate-500">
          {normalized} / 10
        </span>
      </div>
      <div className="mt-2 h-3 w-full rounded-full bg-slate-200/70 dark:bg-slate-800">
        <div
          className={clsx("h-full rounded-full transition-all", colorClass)}
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  );
}

/** 根据数值返回对应的 Tailwind 颜色类名 */
function getColor(value: number) {
  if (value >= 7) return "bg-green-500";
  if (value >= 5) return "bg-yellow-400";
  if (value >= 3) return "bg-orange-400";
  return "bg-red-500";
}
