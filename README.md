## 项目简介

**virtual-cat** 一个基于虚拟猫互动应用。  
用户可以在浏览器中与“猫管家”对话，通过自然语言来喂猫、陪玩、清洁、给猫取名字，并实时看到猫的状态变化和形象揭晓。

### 核心特性

- **对话驱动交互**：通过 ChatKit 聊天框和 Agent 工具调用来控制猫的状态（能量、快乐、清洁度等）。
- **每个会话一只猫**：不同 Chat 线程对应不同猫的独立状态。
- **可视化状态面板**：展示猫的名字、形象、状态条，以及“猫说话”气泡和闪烁提示。
- **Widget 组件**：例如“名字候选列表”“猫档案卡片”等，通过 ChatKit widgets 与前端 UI 联动。

---

## 技术栈概览

- **前端**
  - React + TypeScript
  - Vite 开发/构建
  - Tailwind CSS 负责样式与暗色/亮色主题
  - Zustand 维护全局应用状态（线程 ID、猫状态、主题、提示气泡等）
  - `@openai/chatkit-react` 负责对话 UI 与 ChatKit 协议

- **后端**
  - FastAPI 提供 HTTP 接口（`/chatkit`、`/cats/{thread_id}`）
  - ChatKit Server 实现（`CatAssistantServer`）对接 Agent 与线程存储
  - 自定义 Agent（`cat_agent`），使用工具函数管理猫状态和 widgets
  - OpenAI/代理 API 客户端（通过 `OPENAI_API_KEY` 和可选的 `OPENAI_BASE_URL` 配置）

---

## 目录结构

```text
backend/
  app/
    main.py              # FastAPI 入口 & HTTP 路由
    server.py            # ChatKit Server 实现 (CatAssistantServer)
    cat_agent.py         # Agent 定义与工具函数（喂食/玩耍/清洁/命名等）
    cat_state.py         # 猫状态数据模型（能量、快乐、清洁度、花色等）
    cat_store.py         # 基于线程 ID 的猫状态内存存储
    config.py            # OpenAI 客户端与代理配置
    widgets/             # ChatKit widgets 模板与构建工具

frontend/
  src/
    main.tsx             # React 入口
    App.tsx              # 页面布局：聊天面板 + 猫状态面板
    components/
      ChatKitPanel.tsx   # 集成 ChatKit，对接后端 /chatkit
      CatStatusPanel.tsx # 展示猫状态、图片、quick actions
      ThemeToggle.tsx    # 亮/暗色主题切换
    lib/
      config.ts          # 前端环境变量与 ChatKit/猫状态接口地址
      cat.ts             # 猫状态类型定义与默认值
    store/
      useAppStore.ts     # Zustand 全局状态（主题、线程、猫状态等）
    assets/              # 猫图片资源（不同花色 + 未揭晓状态）
```

---

## 本地运行说明

### 1. 启动后端

在 `backend` 目录下：

```bash
uv sync
export OPENAI_API_KEY="sk-..."        # 必填：OpenAI 或代理密钥
# 可选：如果使用代理 / 中转服务，则设置：
# export OPENAI_BASE_URL="https://your-proxy-url"

uv run uvicorn app.main:app --reload --port 8000
```

启动后：
- ChatKit 接口：`http://127.0.0.1:8000/chatkit`
- 猫状态接口：`http://127.0.0.1:8000/cats/{thread_id}`

### 2. 启动前端

在 `frontend` 目录下：

```bash
npm install

export VITE_CHATKIT_API_URL="http://127.0.0.1:8000/chatkit"
export VITE_CAT_STATE_API_URL="http://127.0.0.1:8000/cats"
export VITE_CHATKIT_API_DOMAIN_KEY="domain_pk_local_dev"  # 本地任意非空字符串即可

npm run dev
```

默认 Vite 开发服务器运行在 `http://127.0.0.1:5170`。

---

## 使用体验简介

- 打开页面后，可以看到：
  - 左/右两个卡片：一侧是 ChatKit 聊天框，一侧是猫状态面板。
  - 顶部可以切换暗色/亮色主题。
- 通过输入自然语言（例如“帮我喂猫”“跟猫玩一会”）或点击 Quick actions 按钮，即可触发 Agent 工具：
  - 状态条会实时变化，猫会弹出“说话”气泡。
  - 当你给猫取了名字后，会有小小的烟花动画，猫的花色图片也会被“揭晓”。

如果你计划二次开发，可以从以下文件入手：
- 前端交互：`App.tsx`、`ChatKitPanel.tsx`、`CatStatusPanel.tsx`
- Agent 逻辑与工具：`backend/app/cat_agent.py`
- 猫状态模型与存储：`backend/app/cat_state.py`、`backend/app/cat_store.py`


