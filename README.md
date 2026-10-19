# 喵伴 Miaoban

一个支持持续养成、跨会话个人记忆和受预算约束对话的虚拟猫陪伴系统。

论文暂定题目：**基于大语言模型与长期记忆机制的虚拟宠物陪伴系统设计与实现**。

- [设计架构与技术选型](docs/architecture.md)
- [评估方法与样例数据](evals/README.md)
- [验证记录](docs/verification.md)

## 当前功能

- 注册、登录、退出；账号数据隔离，服务端 Cookie 会话。
- 每个用户一只持续存在的猫，聊天会话与宠物身份解耦。
- 饱腹、精力、心情、清洁、亲密度；时间衰减、离线结算和成长阶段。
- 喂食、玩耍、梳洗、休息；按钮与 Agent 工具共用事务及幂等规则。
- 中文宠物空间、基础二维动作、成长日记、会话切换与历史消息分页。
- 手动个人记忆、对话记忆提取、来源查看、纠正和遗忘。
- 结构化字段、中文关键词、pgvector 向量与 RRF 融合召回。
- 近期消息、阶段摘要与相关记忆分层组装；每次模型调用前检查 token 预算。
- PostgreSQL 持久化任务、租约重试、对话运行状态与断线后查询。

对话、模型提取和摘要需要真实模型配置。**未配置密钥时，登录、领养、照料、日记、手动记忆和关键词检索可用，界面明确提示聊天尚未连接。** 对明确“叫我某某”的消息，后台具备受限的规则提取作为基础路径，不将其宣称为完整模型提取。

## 技术结构

```text
backend/
  app/api/              登录、宠物、记忆、消息与 SSE 接口
  app/services/pets.py   可测试的养成规则与事务
  app/services/memory.py 提取写入、来源抑制、中文与向量召回
  app/services/context.py 分层上下文与 token 计算
  app/services/agent.py  Agents SDK、逐调用预算、共享工具
  app/worker.py         持久化任务消费与租约续期
  app/models.py         关系数据和 pgvector 模型
  alembic/              初始 schema 快照及迁移
  tests/                领域、真实 PostgreSQL、模拟模型协议测试
frontend/
  src/components/       登录、领养、场景、聊天、记忆、日记
  src/lib/              API、SSE、类型及现有猫素材
  e2e/                  桌面与手机浏览器流程
  nginx.conf            同源 API 与 SSE 代理
compose.yaml            PostgreSQL、迁移、API、Worker、Web
```

旧版 ChatKit 协议层、内存存储和示例启动入口已被替换，旧实现可从 Git 历史查看。原来进程内已丢失的猫和对话无法恢复。

## 推荐启动方式

需要 Docker Compose。无需为了体验基础养成先配置模型。

```bash
cp .env.example .env
# 按需要编辑 .env 中的模型配置
# 对外部署前修改 POSTGRES_PASSWORD，设置正确 APP_ORIGIN 和 COOKIE_SECURE

docker compose up --build -d
```

打开 [http://localhost:5170](http://localhost:5170)。`migrate` 在数据库就绪后运行，API 和 Worker 等待迁移完成。数据库持久化在 `postgres-data` 卷中。

```bash
docker compose logs -f api worker
docker compose down
```

`down` 保留数据卷；不要为日常重启使用 `down -v`。

## 本地开发

需要 **Node.js 22.12+、Python 3.12+、PostgreSQL 17 与 pgvector**。

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r backend/requirements.lock
.venv/bin/pip install --no-deps -e ./backend
npm ci
npm --prefix frontend ci
cp .env.example .env
```

数据库可以单独由 Compose 启动：

```bash
docker compose up -d db
.venv/bin/alembic -c backend/alembic.ini upgrade head
npm run dev
```

`npm run dev` 会在后台启动 API、Worker 和前端，等待数据库查询、迁移和前端代理全部就绪后才返回成功。启动不依赖编辑器或临时执行会话；结束启动命令所在终端不会停止服务。重复执行不会启动多份进程。前端支持热更新，修改后端后可停止再启动。如果使用已有数据库，先修改 `DATABASE_URL`。API 文档在 `http://127.0.0.1:8000/docs`。

```bash
npm run dev:start    # 与 npm run dev 相同
npm run dev:status   # 检查受管理的进程和 /api/health
npm run dev:stop     # 仅停止该启动器创建的服务，保留数据库文件
```

日志保存到 `.local/dev.log`。启动器优先使用当前的 Node.js 22.12+，也支持已安装的 nvm 版本、桌面提供的运行时或 `MIAOBAN_NODE` 指定的可执行文件。它不会安装运行时、重置数据库或停止其他程序占用的端口。

首次使用 tiktoken 会下载对应 tokenizer 词表。离线部署应预先缓存；后端 Docker 镜像在构建时预热默认 `o200k_base`。

本次开发环境没有 Docker，使用忽略目录 `.local/` 下已有的 PostgreSQL 17 和 pgvector 进行真实数据库验证，端口为 `55432`；本机 `.env` 使用该端口，未提交。当配置指向本地 `55432` 且已有验证工具时，启动器会通过 `scripts/local-postgres.mjs` 启动该实例；其恢复完成后才执行迁移。仓库不会携带或自动下载数据库二进制。正式复现优先使用 Compose 或已安装的 PostgreSQL。

## 模型配置

```dotenv
OPENAI_API_KEY=填写对话密钥
OPENAI_BASE_URL=
CHAT_MODEL=gpt-5-mini
CHAT_TOKEN_PARAMETER=max_completion_tokens
EMBEDDING_API_KEY=填写向量密钥
EMBEDDING_BASE_URL=
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIMENSIONS=1536
```

两个密钥可使用同一个账号，但必须显式配置。空端点使用官方服务地址；代理必须支持对应的 Chat Completions、流式工具调用或 Embeddings 能力。旧协议代理若只支持 `max_tokens`，显式修改 `CHAT_TOKEN_PARAMETER=max_tokens`。

`OUTPUT_TOKENS` 与 `REASONING_RESERVE` 合并为模型的 completion 上限，并从窗口容量中共同预留；输入另由 `CONTEXT_TOKENS` 约束。tiktoken 统计加保守余量仍是模型相关的估算，不能替代所用服务的真实窗口与返回用量。未知模型使用默认编码，切换代理后需要联调校准。

修改 `EMBEDDING_DIMENSIONS` 必须同步迁移向量列，不能直接混用不同维度；更换 Embedding 模型需要重建现有向量。无向量服务时词法召回继续工作，但不会冒充语义召回。

## 记忆与数据

- 宠物状态来自规则与数据库，历史消息不能覆盖当前状态。
- 记忆保存来源原文，模型提取还需经过结构与原文引用校验；引用校验无法数学保证语义真实性，用户可查看并纠正。
- 普通纠正/遗忘使相关源消息退出后续上下文，清除相关摘要与失效向量，防止后台重提取。来自同一消息的其他事实可能一并退出，以避免间接复活。
- 遗忘可选择同时删除原文。原文删除不可恢复；相关派生回答退出上下文。已发送给外部模型的历史请求无法撤回。
- 任务在数据库中保存，独立 Worker 必须运行。Embedding 未配置时任务跳过向量生成；配置服务后可运行下方命令重建。

```bash
.venv/bin/python -m app.cli reindex
```

## 测试和评估

```bash
.venv/bin/ruff check backend evals
npm --prefix frontend run lint
npm --prefix frontend run build
npm --prefix frontend test
.venv/bin/pytest backend/tests/test_domain.py
```

数据库测试**会重建测试数据库中的业务表**。必须使用独立的、名称以 `_test` 结尾的数据库；不设置时数据库测试跳过。

```bash
# 先创建独立 miaoban_test 数据库，并安装 vector 扩展
TEST_DATABASE_URL=postgresql+asyncpg://miaoban:miaoban@localhost:5432/miaoban_test \
  .venv/bin/pytest backend/tests
```

浏览器测试需要 API、Worker 和 Web 已启动。测试创建独立账号，不删除现有用户；覆盖桌面和手机流程。默认使用安装的 Chrome，也可以调整 Playwright 配置为下载的 Chromium。

```bash
npm --prefix frontend run test:e2e
```

检索评估：

```bash
TEST_DATABASE_URL=postgresql+asyncpg://miaoban:miaoban@localhost:5432/miaoban_test \
  .venv/bin/python evals/recall_benchmark.py
```

默认无外部 API 请求；需显式 `--allow-remote` 才评估真实 Embedding。样例集用于检查评估管道，不能作为毕业论文的准确率或陪伴效果结论。

## 当前限制

- 真实模型与向量服务需要用户密钥；验证记录区分模拟协议测试、控制向量测试与真实外部联调。
- 第一版为单宠物、基础二维动作，复用原有插画；图片资源仍较大。
- 小规模先使用精确向量检索，尚无大规模负载结论。
- 摘要采用有来源的近期历史窗口；超长材料保留原文，后台跳过超预算摘要，不声称完整覆盖所有历史。
- Compose 配置已提供，当前机器无 Docker，尚未实际构建运行容器。
