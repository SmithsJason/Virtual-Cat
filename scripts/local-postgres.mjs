/** Optional existing workspace database; does not install software or replace data. */
import { existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { setTimeout as sleep } from "node:timers/promises";
const root = dirname(dirname(fileURLToPath(import.meta.url)));
const { default: EmbeddedPostgres } = await import(
  pathToFileURL(
    join(
      root,
      ".local/postgres-tools/node_modules/embedded-postgres/dist/index.js",
    ),
  ).href
);
const pg = new EmbeddedPostgres({
  databaseDir: join(root, ".local/pgdata"),
  user: "miaoban",
  password: "miaoban",
  port: 55432,
  persistent: true,
  postgresFlags: ["-h", "127.0.0.1"],
  onLog: () => {},
  onError: console.error,
});
let stopping = false;
async function stop() {
  if (stopping) return;
  stopping = true;
  try {
    await pg.stop();
  } catch {}
  process.exit(0);
}
process.once("SIGTERM", () => void stop());
process.once("SIGINT", () => void stop());
if (!existsSync(join(root, ".local/pgdata/PG_VERSION"))) await pg.initialise();
await pg.start();
let client;
for (let attempt = 0; attempt < 100; attempt++) {
  const candidate = pg.getPgClient();
  try {
    await candidate.connect();
    await candidate.query("SELECT 1");
    client = candidate;
    break;
  } catch {
    await candidate.end().catch(() => {});
    await sleep(300);
  }
}
if (!client) {
  console.error("本地数据库恢复超时");
  await stop();
}
for (const name of ["miaoban", "miaoban_test"]) {
  if (
    !(await client.query("SELECT 1 FROM pg_database WHERE datname=$1", [name]))
      .rowCount
  )
    await client.query("CREATE DATABASE " + name);
}
await client.end();
console.log("本地 PostgreSQL 已接受查询（127.0.0.1:55432）");
setInterval(() => {}, 60000);
