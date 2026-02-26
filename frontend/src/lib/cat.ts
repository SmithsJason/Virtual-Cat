/**
 * cat.ts —— 猫状态相关的 TypeScript 类型定义和默认值。
 *
 * 这些类型与后端 CatState.to_payload() 输出的 JSON 结构对应（驼峰命名）。
 */

/** 猫的 5 种花色（与后端 COLOR_PATTERNS 对应） */
export type CatColorPattern = "black" | "calico" | "colorpoint" | "tabby" | "white";

/** 猫状态 payload —— 前后端通信的数据契约 */
export type CatStatePayload = {
  threadId?: string | null;
  name: string;
  energy: number;       // 精力值 [0-10]
  happiness: number;    // 快乐值 [0-10]
  cleanliness: number;  // 清洁度 [0-10]
  age: number;
  colorPattern: CatColorPattern | null;  // null 表示未命名 / 剪影状态
  updatedAt: string;    // ISO 8601 时间戳
};

/** 猫语音气泡的 payload */
export type CatSpeechPayload = {
  message: string;
  mood?: string;
};

/** 默认猫状态：未命名、三项属性 6/10、无花色 */
export const DEFAULT_CAT_STATE: CatStatePayload = {
  threadId: null,
  name: "Unnamed Cat",
  energy: 6,
  happiness: 6,
  cleanliness: 6,
  age: 2,
  colorPattern: null,
  updatedAt: new Date().toISOString(),
};
