import { describe, it, expect, vi, afterEach } from "vitest";
import { api, consumeSSE } from "./api";

afterEach(() => vi.unstubAllGlobals());

it("explains unavailable services without exposing browser network errors", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockRejectedValue(new TypeError("Failed to fetch")),
  );
  await expect(api("/auth/me")).rejects.toMatchObject({
    status: 0,
    message: "暂时连接不上小窝，请稍后重试。",
  });
});

describe("SSE transport", () => {
  it("preserves Chinese and CRLF split across arbitrary network chunks", async () => {
    const encoded = new TextEncoder().encode(
      'event: run\r\ndata: {"text":"你好，小猫"}\r\n\r\n: heartbeat\r\n\r\nevent: run\r\ndata: {"status":"completed"}\r\n\r\n',
    );
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        for (let i = 0; i < encoded.length; i += 1)
          controller.enqueue(encoded.slice(i, i + 1));
        controller.close();
      },
    });
    const events: string[][] = [];
    await consumeSSE(new Response(stream), (event, data) =>
      events.push([event, data]),
    );
    expect(events).toEqual([
      ["run", '{"text":"你好，小猫"}'],
      ["run", '{"status":"completed"}'],
    ]);
  });
  it("joins multi-line data and ignores comments", async () => {
    const events: string[][] = [];
    await consumeSSE(
      new Response(":hello\n\nevent: sample\ndata: one\ndata: two\n\n"),
      (e, d) => events.push([e, d]),
    );
    expect(events).toEqual([["sample", "one\ntwo"]]);
  });
});
