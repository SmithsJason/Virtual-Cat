export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api${path}`, {
      ...init,
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", ...init?.headers },
      signal: init?.signal ?? AbortSignal.timeout(20_000),
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError")
      throw error;
    throw new ApiError(0, "暂时连接不上小窝，请稍后重试。");
  }
  if (!response.ok) {
    let detail = "服务暂时不可用，请稍后重试";
    try {
      const data = await response.json();
      detail =
        typeof data.detail === "string"
          ? data.detail
          : "请检查输入内容是否符合要求";
    } catch {
      /* Non-JSON proxy failures. */
    }
    throw new ApiError(response.status, detail);
  }
  return response.status === 204 ? (undefined as T) : response.json();
}

export async function consumeSSE(
  response: Response,
  onEvent: (event: string, data: string) => void,
) {
  if (!response.body) throw new Error("浏览器无法读取响应流");
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let pending = "";
  const consume = () => {
    let boundary: number;
    while ((boundary = pending.indexOf("\n\n")) !== -1) {
      const block = pending.slice(0, boundary);
      pending = pending.slice(boundary + 2);
      const lines = block.split("\n");
      const event =
        lines
          .find((line) => line.startsWith("event:"))
          ?.slice(6)
          .trim() ?? "message";
      const data = lines
        .filter((line) => line.startsWith("data:"))
        .map((line) => line.slice(5).trimStart())
        .join("\n");
      if (data) onEvent(event, data);
    }
  };
  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      pending = (pending + decoder.decode(value, { stream: true })).replace(
        /\r\n/g,
        "\n",
      );
      consume();
    }
    pending += decoder.decode();
    consume();
  } finally {
    reader.releaseLock();
  }
}
