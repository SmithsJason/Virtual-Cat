import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  BookHeart,
  Check,
  Clock,
  Pencil,
  Plus,
  Search,
  Trash2,
  X,
} from "lucide-react";
import { api } from "../lib/api";
import type { Memory, Pet } from "../lib/types";
const kinds = {
  fact: "关于你",
  preference: "小偏好",
  promise: "我们的约定",
  episode: "共同经历",
};
export function Memories({ pet }: { pet: Pet }) {
  const client = useQueryClient();
  const [editor, setEditor] = useState<Memory | "new" | null>(null);
  const [content, setContent] = useState("");
  const [kind, setKind] = useState<Memory["kind"]>("preference");
  const [deleting, setDeleting] = useState<Memory | null>(null);
  const [erase, setErase] = useState(false);
  const [query, setQuery] = useState("");
  const [search, setSearch] = useState("");
  const memories = useQuery({
    queryKey: ["memories", pet.id],
    queryFn: () => api<Memory[]>(`/memories?pet_id=${pet.id}`),
    refetchInterval: 10000,
  });
  const results = useQuery({
    queryKey: ["memory-search", pet.id, search],
    queryFn: () =>
      api<{ items: Memory[]; trace: { mode: string; warning?: string } }>(
        `/memories/search?pet_id=${pet.id}&q=${encodeURIComponent(search)}`,
      ),
    enabled: !!search,
  });
  const refresh = () => {
    void client.invalidateQueries({ queryKey: ["memories", pet.id] });
    void client.invalidateQueries({ queryKey: ["memory-search", pet.id] });
  };
  const save = useMutation({
    mutationFn: () =>
      api(
        editor === "new"
          ? `/memories?pet_id=${pet.id}`
          : `/memories/${(editor as Memory).id}`,
        {
          method: editor === "new" ? "POST" : "PATCH",
          body: JSON.stringify({ content, kind }),
        },
      ),
    onSuccess: () => {
      setEditor(null);
      setContent("");
      refresh();
    },
  });
  const remove = useMutation({
    mutationFn: () =>
      api(`/memories/${deleting?.id}?erase_source=${erase}`, {
        method: "DELETE",
      }),
    onSuccess: () => {
      setDeleting(null);
      setErase(false);
      refresh();
    },
  });
  const items = search ? results.data?.items : memories.data;
  return (
    <section className="content-page">
      <div className="page-title">
        <div>
          <span className="eyebrow">LITTLE THINGS WE REMEMBER</span>
          <h1>共同记忆</h1>
          <p>你的偏好，我们的约定，还有一起走过的小小日常。</p>
        </div>
        <button
          className="primary compact"
          onClick={() => {
            setEditor("new");
            setContent("");
            save.reset();
          }}
        >
          <Plus size={16} /> 留下一条记忆
        </button>
      </div>
      <form
        className="memory-search"
        onSubmit={(e) => {
          e.preventDefault();
          setSearch(query);
        }}
      >
        <Search size={18} />
        <input
          aria-label="搜索记忆"
          placeholder="试着问：我喜欢用什么陪你玩？"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          maxLength={2000}
        />
        {search && (
          <button
            type="button"
            className="icon-button"
            aria-label="清除搜索"
            onClick={() => {
              setSearch("");
              setQuery("");
            }}
          >
            <X size={17} />
          </button>
        )}
        <button type="submit" className="text-button">
          寻找记忆
        </button>
      </form>
      {search && results.data && (
        <p className="muted">
          {results.data.items.length
            ? `找到 ${results.data.items.length} 条可能相关的记忆`
            : "暂时没有找到相关记忆，我不会假装记得。"}
          {results.data.trace.warning && ` · ${results.data.trace.warning}`}
        </p>
      )}
      {(memories.error || results.error) && (
        <p className="error" role="alert">
          {memories.error?.message || results.error?.message}
        </p>
      )}
      {memories.isPending ? (
        <p className="muted">翻开记忆本…</p>
      ) : (
        <div className="memory-grid">
          {items?.map((memory) => (
            <article className="memory-card" key={memory.id}>
              <div className="memory-top">
                <span className={`kind kind-${memory.kind}`}>
                  <BookHeart size={13} />
                  {kinds[memory.kind]}
                </span>
                <div>
                  <button
                    className="icon-button"
                    title="纠正记忆"
                    aria-label={`纠正：${memory.content}`}
                    onClick={() => {
                      setEditor(memory);
                      setContent(memory.content);
                      setKind(memory.kind);
                      save.reset();
                    }}
                  >
                    <Pencil size={15} />
                  </button>
                  <button
                    className="icon-button"
                    title="遗忘记忆"
                    aria-label={`遗忘：${memory.content}`}
                    onClick={() => {
                      setDeleting(memory);
                      remove.reset();
                    }}
                  >
                    <Trash2 size={15} />
                  </button>
                </div>
              </div>
              <p>{memory.content}</p>
              {memory.sources.length > 0 && (
                <details>
                  <summary>记忆从这里来</summary>
                  {memory.sources.map((source, i) => (
                    <blockquote key={i}>
                      {source.quote}
                      <small>
                        {source.message_id ? "来自我们的对话" : "由你亲自记录"}
                      </small>
                    </blockquote>
                  ))}
                </details>
              )}
              <footer>
                <Clock size={12} />
                {new Date(memory.created_at).toLocaleDateString("zh-CN")}
                {memory.valid_until && <span> · 近期记忆</span>}
              </footer>
            </article>
          ))}
        </div>
      )}
      {!memories.isPending && !items?.length && !search && (
        <div className="empty-state">
          <BookHeart size={36} />
          <h3>记忆本的第一页，留给你。</h3>
          <p>聊聊你的称呼或偏好，也可以亲手记录一件小事。</p>
        </div>
      )}
      {editor && (
        <div className="modal-backdrop">
          <section
            className="modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="memory-title"
          >
            <button
              className="modal-close icon-button"
              aria-label="关闭"
              onClick={() => setEditor(null)}
            >
              <X />
            </button>
            <h2 id="memory-title">
              {editor === "new"
                ? "留下一点值得记住的事"
                : "把记忆更新成现在的样子"}
            </h2>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                save.mutate();
              }}
            >
              <label>
                记忆类型
                <select
                  value={kind}
                  onChange={(e) => setKind(e.target.value as Memory["kind"])}
                >
                  {Object.entries(kinds).map(([key, label]) => (
                    <option key={key} value={key}>
                      {label}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                想让小猫记住什么？
                <textarea
                  autoFocus
                  required
                  maxLength={500}
                  rows={4}
                  value={content}
                  onChange={(e) => setContent(e.target.value)}
                  placeholder="比如：以后叫我小林，我喜欢用逗猫棒陪你玩。"
                />
              </label>
              {save.error && (
                <p className="error" role="alert">
                  {save.error.message}
                </p>
              )}
              <button
                className="primary"
                disabled={save.isPending || !content.trim()}
              >
                <Check size={17} />
                {save.isPending ? "记下来…" : "好好记住"}
              </button>
            </form>
          </section>
        </div>
      )}
      {deleting && (
        <div className="modal-backdrop">
          <section
            className="modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="forget-title"
          >
            <h2 id="forget-title">让这条记忆轻轻离开？</h2>
            <p>之后的对话将不再使用它。相关对话来源也会从记忆上下文中移除。</p>
            <blockquote>{deleting.content}</blockquote>
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={erase}
                onChange={(e) => setErase(e.target.checked)}
              />{" "}
              同时删除相关消息原文（无法恢复）
            </label>
            {remove.error && <p className="error">{remove.error.message}</p>}
            <div className="modal-actions">
              <button className="secondary" onClick={() => setDeleting(null)}>
                再想想
              </button>
              <button
                className="primary"
                disabled={remove.isPending}
                onClick={() => remove.mutate()}
              >
                遗忘这条记忆
              </button>
            </div>
          </section>
        </div>
      )}
    </section>
  );
}
