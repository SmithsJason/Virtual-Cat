import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowUp, MessageCircle, Plus, Sparkles } from "lucide-react";
import { api, consumeSSE } from "../lib/api";
import type {
  Conversation,
  Health,
  Message,
  Page,
  Pet,
  Run,
} from "../lib/types";
import { useAppStore } from "../store/useAppStore";

export function Chat({ pet, health }: { pet: Pet; health?: Health }) {
  const client = useQueryClient();
  const [selected, setSelected] = useState<string | null>(() =>
    localStorage.getItem(`conversation:${pet.id}`),
  );
  const [text, setText] = useState("");
  const [sendError, setSendError] = useState("");
  const [sending, setSending] = useState(false);
  const abort = useRef<AbortController | null>(null);
  const scroll = useRef<HTMLDivElement | null>(null);
  const completed = useRef("");
  const seenEvents = useRef(new Set<string>());
  const setAction = useAppStore((s) => s.setAction);
  const conversations = useQuery({
    queryKey: ["conversations", pet.id],
    queryFn: () => api<Conversation[]>(`/pets/${pet.id}/conversations`),
  });
  const conversation = conversations.data?.some((c) => c.id === selected)
    ? selected
    : conversations.data?.[0]?.id;
  const messages = useQuery({
    queryKey: ["messages", conversation],
    queryFn: () =>
      api<Page<Message>>(`/conversations/${conversation}/messages`),
    enabled: !!conversation,
  });
  const runs = useQuery({
    queryKey: ["runs", conversation],
    queryFn: () => api<Run[]>(`/conversations/${conversation}/runs`),
    enabled: !!conversation,
    refetchInterval: (query) =>
      query.state.data?.some(
        (r) => r.status === "pending" || r.status === "running",
      )
        ? 1000
        : 5000,
  });
  const run = runs.data?.[0];
  const active = run?.status === "pending" || run?.status === "running";
  const newConversation = useMutation({
    mutationFn: () =>
      api<Conversation>(`/pets/${pet.id}/conversations`, { method: "POST" }),
    onSuccess: (c) => {
      setSelected(c.id);
      localStorage.setItem(`conversation:${pet.id}`, c.id);
      void client.invalidateQueries({ queryKey: ["conversations", pet.id] });
    },
  });
  useEffect(() => () => abort.current?.abort(), []);
  useEffect(() => {
    if (
      run &&
      (run.status === "completed" || run.status === "failed") &&
      completed.current !== run.id
    ) {
      completed.current = run.id;
      void client.invalidateQueries({ queryKey: ["messages", conversation] });
      void client.invalidateQueries({ queryKey: ["pets"] });
      void client.invalidateQueries({ queryKey: ["events", pet.id] });
      void client.invalidateQueries({ queryKey: ["memories", pet.id] });
    }
  }, [run, client, conversation, pet.id]);
  useEffect(() => {
    const events = run?.trace.events ?? [];
    for (const event of events) {
      if (!seenEvents.current.has(event.id)) {
        seenEvents.current.add(event.id);
        if (Date.now() - new Date(event.created_at).getTime() < 15000)
          setAction(event.action);
      }
    }
    const timer = setTimeout(() => setAction("idle"), 4500);
    return () => clearTimeout(timer);
  }, [run, setAction]);
  useEffect(() => {
    scroll.current?.scrollTo({
      top: scroll.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages.data, run?.trace.preview]);
  async function send(value = text) {
    if (!value.trim() || sending || active || !conversation) return;
    setSending(true);
    setSendError("");
    const controller = new AbortController();
    abort.current = controller;
    const keyName = `pending:${conversation}`;
    const stored = localStorage.getItem(keyName);
    let pending: { text: string; key: string } | null = null;
    try {
      pending = stored ? JSON.parse(stored) : null;
    } catch {
      localStorage.removeItem(keyName);
    }
    const key =
      pending?.text === value.trim() ? pending.key : crypto.randomUUID();
    localStorage.setItem(keyName, JSON.stringify({ text: value.trim(), key }));
    try {
      const response = await fetch(
        `/api/conversations/${conversation}/messages`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "same-origin",
          body: JSON.stringify({ text: value.trim(), request_key: key }),
          signal: controller.signal,
        },
      );
      if (!response.ok) {
        const error = await response.json();
        throw new Error(
          typeof error.detail === "string"
            ? error.detail
            : "消息太长，请分段发送",
        );
      }
      setText("");
      await consumeSSE(response, (event, data) => {
        if (event === "run") {
          const next = JSON.parse(data) as Run;
          client.setQueryData<Run[]>(["runs", conversation], (old) => [
            next,
            ...(old ?? []).filter((r) => r.id !== next.id),
          ]);
          if (next.status === "completed" || next.status === "failed")
            localStorage.removeItem(keyName);
          void client.invalidateQueries({
            queryKey: ["messages", conversation],
          });
        }
        if (event === "timeout") setSendError("回应仍在继续，正在查询结果…");
      });
    } catch (error) {
      if (!(error instanceof DOMException && error.name === "AbortError"))
        setSendError(
          error instanceof Error ? error.message : "连接中断，正在恢复回应…",
        );
    } finally {
      setSending(false);
      void client.invalidateQueries({ queryKey: ["runs", conversation] });
      void client.invalidateQueries({ queryKey: ["conversations", pet.id] });
    }
  }
  const preview = run?.status === "running" ? run.trace.preview : "";
  const items = messages.data?.items ?? [];
  const latestError = run?.status === "failed" ? run.error : null;
  return (
    <section className="chat-card">
      <div className="chat-heading">
        <div className="chat-avatar">
          <MessageCircle size={19} />
        </div>
        <div>
          <h2>和{pet.name}说说话</h2>
          <span>小小回应，认真听你说</span>
        </div>
        <button
          className="icon-button"
          title="开启新会话"
          aria-label="开启新会话"
          onClick={() => newConversation.mutate()}
          disabled={active || sending || newConversation.isPending}
        >
          <Plus size={19} />
        </button>
      </div>
      <div className="conversation-row">
        {conversations.data?.length ? (
          <select
            aria-label="切换会话"
            disabled={active || sending}
            value={conversation ?? ""}
            onChange={(e) => {
              setSelected(e.target.value);
              localStorage.setItem(`conversation:${pet.id}`, e.target.value);
            }}
          >
            {conversations.data.map((c) => (
              <option key={c.id} value={c.id}>
                {c.title}
              </option>
            ))}
          </select>
        ) : (
          <span>为你们留一个聊天的小角落</span>
        )}
        <span className="connection-dot" />
        {health?.chat_available ? "可以聊天" : "等待连接"}
      </div>
      <div className="chat-messages" ref={scroll} aria-live="polite">
        {!items.length && !preview && (
          <div className="chat-empty">
            <span>✳</span>
            <h3>今天，想分享什么？</h3>
            <p>
              开心的事，或是有点累的一天，
              <br />
              {pet.name}都愿意听。
            </p>
            {!conversation && (
              <button
                className="text-button"
                onClick={() => newConversation.mutate()}
                disabled={newConversation.isPending}
              >
                开始第一段对话 <Plus size={14} />
              </button>
            )}
          </div>
        )}
        {messages.data?.next && (
          <button
            className="text-button"
            onClick={async () => {
              const previous = await api<Page<Message>>(
                `/conversations/${conversation}/messages?before=${messages.data.next}`,
              );
              client.setQueryData<Page<Message>>(
                ["messages", conversation],
                (old) => ({
                  items: [...previous.items, ...(old?.items ?? [])],
                  next: previous.next,
                }),
              );
            }}
          >
            查看更早的消息
          </button>
        )}
        {items.map((message) => (
          <div key={message.id} className={`message message-${message.role}`}>
            <span className="message-author">
              {message.role === "user" ? "你" : pet.name}
            </span>
            <p>{message.content}</p>
          </div>
        ))}
        {preview && (
          <div className="message message-assistant">
            <span className="message-author">{pet.name}</span>
            <p>
              {preview}
              <i className="typing-cursor" />
            </p>
          </div>
        )}
        {active && !preview && (
          <div className="thinking">
            <i />
            <i />
            <i />
            <span>
              {run.status === "pending" ? "正在等小猫回应…" : "小猫想了一下…"}
            </span>
          </div>
        )}
        {(sendError ||
          latestError ||
          newConversation.error ||
          messages.error) && (
          <p role="alert" className="error">
            {sendError ||
              latestError ||
              newConversation.error?.message ||
              messages.error?.message}
          </p>
        )}
      </div>
      <div className="chat-bottom">
        {!health?.chat_available && (
          <p className="service-note">
            对话服务尚未连接，照料和记忆记录仍可使用。
          </p>
        )}
        <div className="starter-chips">
          {["今天过得怎么样？", "还记得我吗？"].map((prompt) => (
            <button key={prompt} onClick={() => setText(prompt)}>
              {prompt}
            </button>
          ))}
        </div>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void send();
          }}
        >
          <textarea
            aria-label="给小猫的消息"
            placeholder={`和${pet.name}说点什么…`}
            rows={2}
            maxLength={12000}
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if (
                e.key === "Enter" &&
                !e.shiftKey &&
                !e.nativeEvent.isComposing
              ) {
                e.preventDefault();
                void send();
              }
            }}
          />
          <button
            className="send-button"
            aria-label="发送消息"
            disabled={
              !text.trim() ||
              sending ||
              active ||
              !conversation ||
              !health?.chat_available
            }
          >
            <ArrowUp size={19} />
          </button>
        </form>
        <span className="chat-footnote">
          <Sparkles size={11} /> 重要的话，慢慢记在心里
        </span>
      </div>
    </section>
  );
}
