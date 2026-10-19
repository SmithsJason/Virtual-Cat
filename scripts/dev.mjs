/** Manage local development services independently of an editor/agent terminal. */
import { spawn, spawnSync } from "node:child_process";
import { randomUUID } from "node:crypto";
import {
  existsSync,
  mkdirSync,
  openSync,
  readFileSync,
  readdirSync,
  rmSync,
  writeFileSync,
  closeSync,
} from "node:fs";
import { createConnection } from "node:net";
import { dirname, delimiter, join } from "node:path";
import { fileURLToPath } from "node:url";
import { setTimeout as sleep } from "node:timers/promises";

const script = fileURLToPath(import.meta.url);
const root = dirname(dirname(script));
const local = join(root, ".local");
const stateFile = join(local, "dev-process.json");
const logFile = join(local, "dev.log");
const lock = join(local, "dev-start.lock");
const python = join(root, ".venv", "bin", "python");
mkdirSync(local, { recursive: true });

function state() {
  try {
    return JSON.parse(readFileSync(stateFile, "utf8"));
  } catch {
    return null;
  }
}
function save(value) {
  writeFileSync(stateFile, JSON.stringify(value, null, 2), { mode: 0o600 });
}
function alive(pid) {
  try {
    process.kill(pid, 0);
    return true;
  } catch {
    return false;
  }
}
function managed(value) {
  if (!value?.pid || !value.token || !alive(value.pid)) return false;
  const command =
    spawnSync("ps", ["-p", String(value.pid), "-o", "command="], {
      encoding: "utf8",
    }).stdout ?? "";
  return (
    command.includes(script) && command.includes(`supervise ${value.token}`)
  );
}
function nodeRuntime() {
  const candidates = [process.env.MIAOBAN_NODE, process.execPath];
  const nvm = process.env.NVM_DIR || join(process.env.HOME || "", ".nvm");
  const versions = join(nvm, "versions", "node");
  if (existsSync(versions)) {
    for (const version of readdirSync(versions).sort((a, b) =>
      b.localeCompare(a, undefined, { numeric: true }),
    ))
      candidates.push(join(versions, version, "bin", "node"));
  }
  // An optional desktop-provided runtime; standard Node installations remain preferred.
  candidates.push(
    join(
      process.env.HOME || "",
      ".cache",
      "codex-runtimes",
      "codex-primary-runtime",
      "dependencies",
      "node",
      "bin",
      "node",
    ),
  );
  for (const candidate of candidates.filter(Boolean)) {
    const result = spawnSync(candidate, ["-p", "process.versions.node"], {
      encoding: "utf8",
    });
    const [major, minor] = (result.stdout || "").trim().split(".").map(Number);
    if (result.status === 0 && (major > 22 || (major === 22 && minor >= 12)))
      return candidate;
  }
  throw new Error(
    "需要 Node.js 22.12+。请安装 .nvmrc 指定版本，或设置 MIAOBAN_NODE。",
  );
}
function configuration() {
  if (!existsSync(python))
    throw new Error("缺少 .venv，请先按 README 安装 Python 依赖。");
  const result = spawnSync(
    python,
    [
      "-c",
      'import json; from urllib.parse import urlsplit; from app.config import get_settings; s=get_settings(); d=urlsplit(s.database_url); print(json.dumps({"host":d.hostname,"port":d.port or 5432,"origin":s.app_origin}))',
    ],
    { cwd: root, encoding: "utf8" },
  );
  if (result.status !== 0)
    throw new Error("无法读取后端配置，请检查 .env 和 Python 依赖。");
  return JSON.parse(result.stdout);
}
function portOpen(host, port) {
  return new Promise((resolve) => {
    const socket = createConnection({ host, port });
    socket.setTimeout(800);
    const finish = (value) => {
      socket.destroy();
      resolve(value);
    };
    socket.once("connect", () => finish(true));
    socket.once("error", () => finish(false));
    socket.once("timeout", () => finish(false));
  });
}
function databaseReady() {
  const probe = `import asyncio, asyncpg
from app.config import get_settings
async def check():
    connection = await asyncpg.connect(get_settings().database_url.replace("postgresql+asyncpg://", "postgresql://"), timeout=1)
    await connection.execute("SELECT 1")
    await connection.close()
asyncio.run(check())`;
  return new Promise((resolve) => {
    const child = spawn(python, ["-c", probe], { cwd: root, stdio: "ignore" });
    child.once("error", () => resolve(false));
    child.once("exit", (code) => resolve(code === 0));
  });
}
async function health(url) {
  try {
    const response = await fetch(url, { signal: AbortSignal.timeout(2000) });
    const value = await response.json();
    return response.ok && value.database === true && value.version === "0.2.0";
  } catch {
    return false;
  }
}
async function waitFor(
  check,
  description,
  stopped = () => false,
  attempts = 80,
) {
  for (let i = 0; i < attempts; i++) {
    if (stopped())
      throw new Error(`${description}时有服务提前退出，请查看 ${logFile}`);
    if (await check()) return;
    await sleep(250);
  }
  throw new Error(`${description}超时，请查看 ${logFile}`);
}
async function supervise(token) {
  const node = nodeRuntime();
  const config = configuration();
  const env = {
    ...process.env,
    PATH: dirname(node) + delimiter + process.env.PATH,
    PYTHONUNBUFFERED: "1",
  };
  const info = {
    pid: process.pid,
    token,
    status: "starting",
    started_at: new Date().toISOString(),
    url: "http://localhost:5170",
    children: {},
  };
  const children = [];
  let stopping = false;
  save(info);
  async function stop(error = null) {
    if (stopping) return;
    stopping = true;
    if (error) console.error(error);
    const owned = [...children].reverse();
    for (const child of owned)
      if (child.exitCode === null) child.kill("SIGTERM");
    await Promise.race([
      Promise.all(
        owned.map((child) =>
          child.exitCode !== null || child.signalCode
            ? Promise.resolve()
            : new Promise((resolve) => child.once("exit", resolve)),
        ),
      ),
      sleep(5000),
    ]);
    for (const child of owned)
      if (child.exitCode === null && !child.signalCode) child.kill("SIGKILL");
    save({
      ...info,
      status: error ? "failed" : "stopped",
      error,
      stopped_at: new Date().toISOString(),
    });
    process.exit(error ? 1 : 0);
  }
  function launch(name, command, args, cwd = root) {
    if (stopping) throw new Error("启动已中止");
    const child = spawn(command, args, { cwd, env, stdio: "inherit" });
    children.push(child);
    info.children[name] = child.pid;
    save(info);
    child.once("error", () => void stop(`${name} 无法启动`));
    child.once("exit", (code, signal) => {
      if (!stopping) void stop(`${name} 意外停止（${signal || code}）`);
    });
    return child;
  }
  process.once("SIGTERM", () => void stop());
  process.once("SIGINT", () => void stop());
  try {
    if (
      (await portOpen("127.0.0.1", 5170)) ||
      (await portOpen("127.0.0.1", 8000))
    )
      throw new Error("5170 或 8000 端口已占用；未停止任何外部进程。");
    if (!(await portOpen(config.host, config.port))) {
      const helper = join(root, "scripts", "local-postgres.mjs");
      if (
        ["localhost", "127.0.0.1"].includes(config.host) &&
        config.port === 55432 &&
        existsSync(
          join(local, "postgres-tools", "node_modules", "embedded-postgres"),
        )
      ) {
        launch("database", node, [helper]);
        await waitFor(databaseReady, "启动本地数据库", () => stopping);
      } else {
        throw new Error(
          "数据库未运行。请先启动配置的 PostgreSQL，或执行 docker compose up -d db。",
        );
      }
    }
    await waitFor(databaseReady, "等待数据库接受查询", () => stopping);
    const migration = launch("migration", python, [
      "-m",
      "alembic",
      "-c",
      "backend/alembic.ini",
      "upgrade",
      "head",
    ]);
    // A successful one-shot migration must not be treated as a failed long-running service.
    migration.removeAllListeners("exit");
    const migrationCode = await new Promise((resolve) =>
      migration.once("exit", resolve),
    );
    if (migrationCode !== 0)
      throw new Error("数据库迁移失败，请查看开发日志。");
    delete info.children.migration;
    save(info);
    launch("api", python, [
      "-m",
      "uvicorn",
      "app.main:app",
      "--host",
      "127.0.0.1",
      "--port",
      "8000",
    ]);
    await waitFor(
      () => health("http://127.0.0.1:8000/api/health"),
      "等待后端就绪",
      () => stopping,
    );
    launch("worker", python, ["-m", "app.worker"]);
    launch(
      "web",
      node,
      [
        join(root, "frontend", "node_modules", "vite", "bin", "vite.js"),
        "--strictPort",
      ],
      join(root, "frontend"),
    );
    await waitFor(
      () => health("http://127.0.0.1:5170/api/health"),
      "等待前端代理就绪",
      () => stopping,
    );
    info.status = "ready";
    save(info);
    console.log(`喵伴已就绪：http://localhost:5170（PID ${process.pid}）`);
    console.log(`写请求允许来源：${config.origin}`);
  } catch (error) {
    await stop(error.message);
  }
}
async function start() {
  const existing = state();
  if (managed(existing)) {
    if (existing.status === "starting") {
      await waitFor(
        async () =>
          state()?.status === "ready" &&
          (await health("http://127.0.0.1:5170/api/health")),
        "等待正在启动的服务",
        () => !managed(state()),
        200,
      );
    } else if (!(await health("http://127.0.0.1:5170/api/health"))) {
      throw new Error(
        "服务进程存在，但健康检查未通过，请查看 npm run dev:status 与开发日志。",
      );
    }
    console.log(
      `开发服务已在运行（${existing.status}，PID ${existing.pid}）：http://localhost:5170`,
    );
    return;
  }
  try {
    mkdirSync(lock);
    writeFileSync(join(lock, "pid"), String(process.pid));
  } catch {
    const owner = Number(
      existsSync(join(lock, "pid"))
        ? readFileSync(join(lock, "pid"), "utf8")
        : 0,
    );
    if (owner && alive(owner))
      throw new Error(
        "另一个启动命令仍在运行，请使用 npm run dev:status 查看状态。",
      );
    rmSync(lock, { recursive: true, force: true });
    return start();
  }
  try {
    const node = nodeRuntime();
    configuration();
    const token = randomUUID();
    const log = openSync(logFile, "a", 0o600);
    const child = spawn(node, [script, "supervise", token], {
      cwd: root,
      env: process.env,
      detached: true,
      stdio: ["ignore", log, log],
    });
    closeSync(log);
    child.unref();
    await waitFor(
      async () => {
        const current = state();
        if (current?.token === token && current.status === "failed")
          throw new Error(current.error);
        return (
          current?.token === token &&
          current.status === "ready" &&
          (await health("http://127.0.0.1:5170/api/health"))
        );
      },
      "启动开发服务",
      () => !alive(child.pid),
      200,
    );
    console.log(
      `喵伴已启动：http://localhost:5170\n日志：${logFile}\n停止：npm run dev:stop`,
    );
  } finally {
    rmSync(lock, { recursive: true, force: true });
  }
}
async function stopManaged() {
  const current = state();
  if (!managed(current)) {
    console.log("没有受管理的开发服务正在运行。");
    return;
  }
  process.kill(current.pid, "SIGTERM");
  await waitFor(async () => !managed(current), "停止开发服务");
  console.log("开发服务已停止，数据库文件保留。");
}
async function status() {
  const current = state();
  const running = managed(current);
  const ready = running && (await health("http://127.0.0.1:5170/api/health"));
  console.log(
    JSON.stringify(
      {
        status: ready
          ? "ready"
          : running
            ? current.status === "ready"
              ? "unhealthy"
              : current.status
            : "stopped",
        pid: running ? current.pid : null,
        url: "http://localhost:5170",
        children: running ? current.children : {},
        log: logFile,
      },
      null,
      2,
    ),
  );
  if (!ready) process.exitCode = 1;
}
try {
  const command = process.argv[2] || "start";
  if (command === "supervise") await supervise(process.argv[3]);
  else if (command === "start") await start();
  else if (command === "stop") await stopManaged();
  else if (command === "status") await status();
  else throw new Error("支持的命令：start、stop、status");
} catch (error) {
  console.error(error.message);
  process.exitCode = 1;
}
