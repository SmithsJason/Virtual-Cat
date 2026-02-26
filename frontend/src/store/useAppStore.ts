/**
 * useAppStore.ts —— Zustand 全局状态管理。
 *
 * 管理的状态：
 *   - scheme:       亮/暗主题（同步 localStorage + document.classList）
 *   - threadId:     当前活跃的 ChatKit 线程 ID
 *   - cat:          猫状态 payload（name, energy, happiness, cleanliness, colorPattern...）
 *   - speech:       猫语音气泡状态（10s 自动消失）
 *   - flashMessage: 操作后的浮动提示消息（10s 自动消失，与 speech 互斥）
 *
 * 特效触发：
 *   - 命名揭晓时（name: "Unnamed Cat" → 有名字）触发 canvas-confetti 纸屑动画
 *   - 三项属性全满（10/10/10）时触发心形纸屑动画
 *
 * 设计要点：
 *   - 各组件通过 useAppStore(state => state.xxx) 细粒度订阅，避免无关重渲染
 *   - speech 和 flash 各维护独立定时器，互斥显示，线程切换时严格清理防止内存泄漏
 */

import { create } from "zustand";

import { CAT_STATE_API_URL, THEME_STORAGE_KEY } from "../lib/config";
import type { CatSpeechPayload, CatStatePayload } from "../lib/cat";
import { DEFAULT_CAT_STATE } from "../lib/cat";
import confetti from "canvas-confetti";

export type ColorScheme = "light" | "dark";

/** 语音气泡状态：包含消息内容和唯一 ID（用于 React key 触发动画） */
type SpeechState = (CatSpeechPayload & { id: number }) | null;

type AppState = {
  scheme: ColorScheme;
  setScheme: (scheme: ColorScheme) => void;
  threadId: string | null;
  setThreadId: (threadId: string | null) => void;
  cat: CatStatePayload;
  refreshCat: (overrideId?: string | null) => Promise<CatStatePayload | undefined>;
  applyCatUpdate: (update: Partial<CatStatePayload>) => void;
  speech: SpeechState;
  setSpeech: (payload: CatSpeechPayload) => void;
  flashMessage: string | null;
  setFlashMessage: (message: string | null) => void;
};

/** 语音气泡和 Flash 消息的自动消失时间 */
const SPEECH_TIMEOUT_MS = 10_000;
const FLASH_TIMEOUT_MS = 10_000;

// 模块级定时器引用，用于严格管理生命周期
let speechTimer: ReturnType<typeof setTimeout> | null = null;
let flashTimer: ReturnType<typeof setTimeout> | null = null;

function clearSpeechTimer() {
  if (speechTimer) {
    clearTimeout(speechTimer);
    speechTimer = null;
  }
}

function clearFlashTimer() {
  if (flashTimer) {
    clearTimeout(flashTimer);
    flashTimer = null;
  }
}

/**
 * 获取初始主题：
 *   1. 优先读取 localStorage 中的持久化偏好
 *   2. 其次 fallback 到浏览器的 prefers-color-scheme 媒体查询
 *   3. 默认 light
 */
function getInitialScheme(): ColorScheme {
  if (typeof window === "undefined") {
    return "light";
  }
  const stored = window.localStorage.getItem(THEME_STORAGE_KEY) as ColorScheme | null;
  if (stored === "light" || stored === "dark") {
    return stored;
  }
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

/**
 * 同步主题到 DOM 和 localStorage：
 *   - 操作 document.documentElement.classList 切换 Tailwind 的 dark 类
 *   - 持久化到 localStorage 以便下次访问时恢复
 */
function syncSchemeWithDocument(scheme: ColorScheme) {
  if (typeof document === "undefined" || typeof window === "undefined") {
    return;
  }
  const root = document.documentElement;
  if (scheme === "dark") {
    root.classList.add("dark");
  } else {
    root.classList.remove("dark");
  }
  window.localStorage.setItem(THEME_STORAGE_KEY, scheme);
}

/** 命名揭晓时触发的纸屑庆祝动画 */
function celebrateReveal() {
  confetti({
    particleCount: 50,
    spread: 100,
    origin: { y: 0.7 },
    zIndex: 1000,
    scalar: 0.9,
  });
}

// ==================== Zustand Store 定义 ====================

export const useAppStore = create<AppState>((set, get) => {
  // 初始化时同步主题到 DOM
  const initialScheme = getInitialScheme();
  syncSchemeWithDocument(initialScheme);

  return {
    // ---- 主题管理 ----
    scheme: initialScheme,
    setScheme: (scheme) => {
      syncSchemeWithDocument(scheme);
      set({ scheme });
    },

    // ---- 线程管理 ----
    threadId: null,
    setThreadId: (threadId) => {
      const previousId = get().threadId;
      if (previousId === threadId) {
        return;
      }
      // 切换线程时清理定时器和临时状态，防止内存泄漏
      clearSpeechTimer();
      clearFlashTimer();
      set({ threadId, speech: null, flashMessage: null });
      // 自动拉取新线程的猫状态
      void get().refreshCat(threadId ?? null);
    },

    // ---- 猫状态管理 ----
    cat: DEFAULT_CAT_STATE,

    /**
     * 应用猫状态更新（来自 ClientEffect 或 Widget action）。
     * 检测特殊状态变化并触发 confetti 动画：
     *   1. 命名揭晓：name 从 "Unnamed Cat" 变为其他值 → 纸屑动画
     *   2. 三项全满：energy/happiness/cleanliness 全部达到 10 → 心形动画
     */
    applyCatUpdate: (update) => {
      const prev = get().cat
      // 检测命名揭晓 → 触发纸屑庆祝
      if (prev.name === "Unnamed Cat" && update.name !== prev.name) {
        celebrateReveal();
      }

      // 检测三项全满 → 触发心形特效
      if (
        (prev.energy < 10 || prev.happiness < 10 || prev.cleanliness < 10) &&
        (update.energy === 10 && update.happiness === 10 && update.cleanliness === 10)) {
        const heart = confetti.shapeFromText({ text: '❤️', scalar: 2 });
        confetti({
          scalar: 2,
          particleCount: 10,
          flat: true,
          gravity: 0.5,
          spread: 120,
          origin: { y: 0.7 },
          zIndex: 1000,
          shapes: [heart],
        });
      }

      set((state) => ({
        cat: {
          ...state.cat,
          ...update,
          updatedAt: update.updatedAt ?? new Date().toISOString(),
        },
      }));
    },

    /**
     * 从服务端 GET /cats/{threadId} 拉取猫状态。
     * 在线程切换时自动调用，也可手动调用（如 Widget action 后刷新）。
     */
    refreshCat: async (overrideId) => {
      const id = overrideId ?? get().threadId;
      if (!id) {
        // 无活跃线程时重置为默认状态
        set({
          cat: {
            ...DEFAULT_CAT_STATE,
            threadId: null,
            updatedAt: new Date().toISOString(),
          },
        });
        return;
      }
      try {
        const response = await fetch(`${CAT_STATE_API_URL}/${encodeURIComponent(id)}`);
        if (!response.ok) {
          throw new Error(`Failed to load cat state (${response.status})`);
        }
        const data = (await response.json()) as { cat?: CatStatePayload };
        if (data?.cat) {
          const prev = get().cat
          // 同样检测命名揭晓
          if (prev.name === "Unnamed Cat" && data.cat.name !== prev.name) {
            celebrateReveal();
          }

          set({ cat: data.cat });
          return data.cat;
        }
      } catch (error) {
        console.error("Failed to fetch cat state", error);
      }
    },

    // ---- 语音气泡管理 ----
    speech: null,
    /**
     * 显示猫的语音气泡。
     * 互斥：显示 speech 时清除 flash。
     * 10s 后自动消失（通过定时器）。
     */
    setSpeech: (payload) => {
      const speechPayload: SpeechState =
        payload ? { ...payload, id: Date.now() } : null;

      clearSpeechTimer();
      clearFlashTimer();
      set({ speech: speechPayload, flashMessage: null });

      if (!speechPayload) {
        return;
      }

      speechTimer = setTimeout(() => {
        set({ speech: null });
        speechTimer = null;
      }, SPEECH_TIMEOUT_MS);
    },

    // ---- Flash 消息管理 ----
    flashMessage: null,
    /**
     * 显示操作后的浮动提示消息。
     * 互斥：显示 flash 时清除 speech。
     * 10s 后自动消失（通过定时器）。
     */
    setFlashMessage: (message) => {
      if (!message) {
        clearFlashTimer();
        set({ flashMessage: null });
        return;
      }

      clearFlashTimer();
      clearSpeechTimer();
      set({ flashMessage: message, speech: null });

      flashTimer = setTimeout(() => {
        set({ flashMessage: null });
        flashTimer = null;
      }, FLASH_TIMEOUT_MS);
    },
  };
});
