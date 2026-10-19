import { useInfiniteQuery } from "@tanstack/react-query";
import { Apple, BookOpen, Brush, Heart, Moon, Mouse } from "lucide-react";
import { api } from "../lib/api";
import type { Page, Pet, PetEvent } from "../lib/types";
const icons: Record<string, typeof Heart> = {
  feed: Apple,
  play: Mouse,
  clean: Brush,
  rest: Moon,
  adopt: Heart,
};
export function Diary({ pet }: { pet: Pet }) {
  const events = useInfiniteQuery({
    queryKey: ["events", pet.id],
    queryFn: ({ pageParam }) =>
      api<Page<PetEvent>>(
        `/pets/${pet.id}/events${pageParam ? `?before=${pageParam}` : ""}`,
      ),
    initialPageParam: "",
    getNextPageParam: (last) => last.next ?? undefined,
  });
  return (
    <section className="content-page">
      <div className="page-title">
        <div>
          <span className="eyebrow">EVERYDAY, TOGETHER</span>
          <h1>成长日记</h1>
          <p>一些小事，因为一起发生，所以值得记住。</p>
        </div>
        <BookOpen className="page-decoration" size={35} />
      </div>
      {events.error && <p className="error">{events.error.message}</p>}
      <div className="diary-list">
        {events.data?.pages
          .flatMap((p) => p.items)
          .map((event) => {
            const Icon = icons[event.action] ?? Heart;
            return (
              <article className="diary-entry" key={event.id}>
                <div className={`diary-icon ${event.action}`}>
                  <Icon size={20} />
                </div>
                <div>
                  <time>
                    {new Date(event.created_at).toLocaleString("zh-CN", {
                      month: "long",
                      day: "numeric",
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </time>
                  <h3>{event.text}</h3>
                  <p>
                    {event.action === "adopt"
                      ? "相遇的第一天，未来还有很多很多天。"
                      : `心情 ${Math.round(event.state.happiness)} · 精力 ${Math.round(event.state.energy)} · 亲密度 ${Math.round(event.state.affection)}`}
                  </p>
                </div>
              </article>
            );
          })}
      </div>
      {events.isPending && <p>正在翻开日记…</p>}
      {events.hasNextPage && (
        <button
          className="secondary"
          disabled={events.isFetchingNextPage}
          onClick={() => void events.fetchNextPage()}
        >
          再往前翻一页
        </button>
      )}
    </section>
  );
}
