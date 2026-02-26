/**
 * config.ts —— 前端全局配置常量。
 *
 * 包含：
 *   - API 端点 URL（支持 VITE_* 环境变量覆盖，默认走 Vite 反向代理）
 *   - ChatKit domain key
 *   - 主题 localStorage key
 *   - 起始屏幕的欢迎语和预设 prompt
 *   - 动态占位符文案
 */

import { StartScreenPrompt } from "@openai/chatkit";
import { DEFAULT_CAT_STATE } from "./cat";

/** ChatKit SSE 流式端点（默认 /chatkit，由 Vite 代理到后端 8000 端口） */
export const CHATKIT_API_URL =
  import.meta.env.VITE_CHATKIT_API_URL ?? "/chatkit";

/** ChatKit domain key（开发环境使用本地 key，生产环境通过环境变量配置） */
export const CHATKIT_API_DOMAIN_KEY =
  import.meta.env.VITE_CHATKIT_API_DOMAIN_KEY ?? "domain_pk_localhost_dev";

/** 猫状态 REST API 端点（默认 /cats，由 Vite 代理到后端） */
export const CAT_STATE_API_URL =
  import.meta.env.VITE_CAT_STATE_API_URL ?? "/cats";

/** 主题偏好在 localStorage 中的存储 key */
export const THEME_STORAGE_KEY = "chatkit-boilerplate-theme";

/** 起始屏幕欢迎语 */
export const GREETING = "Welcome to the cozy cat lounge";

/** 起始屏幕预设 prompt 快捷按钮（用户点击后直接发送对应消息） */
export const STARTER_PROMPTS: StartScreenPrompt[] = [
  {
    label: "Name ideas",
    prompt: "Could you suggest some fun names for the cat?",
    icon: "book-open",
  },
  {
    label: "Check on the cat",
    prompt: "How is the cat doing today?",
    icon: "circle-question",
  },
  {
    label: "Feed time",
    prompt: "Please feed the cat something tasty.",
    icon: "sparkle",
  },
  {
    label: "Play time",
    prompt: "Please play with the cat using a fun toy.",
    icon: "confetti",
  },
  {
    label: "Profile card",
    prompt: "Can you show me the cat's profile card?",
    icon: "square-text",
  },
];

/** 输入框动态占位符：根据猫是否已命名显示不同文案 */
export const getPlaceholder = (catName: string | null) => {
  return catName === DEFAULT_CAT_STATE.name ? "Ask how the cat feels or what it needs" : `${catName}, what would you like to do?`;
};