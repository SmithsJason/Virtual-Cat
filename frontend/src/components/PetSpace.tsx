import { useEffect, useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Apple, Brush, Heart, Moon, Mouse, Sparkles, Sun } from "lucide-react";
import { api, ApiError } from "../lib/api";
import { cats } from "../lib/cats";
import type { Pet, PetEvent } from "../lib/types";
import { useAppStore } from "../store/useAppStore";
const actions = [
  { id: "feed", label: "喂点好吃的", note: "一口小满足", icon: Apple },
  { id: "play", label: "一起玩耍", note: "快乐加一点", icon: Mouse },
  { id: "clean", label: "梳理毛毛", note: "蓬松又干净", icon: Brush },
  { id: "rest", label: "好好休息", note: "做个甜甜的梦", icon: Moon },
];
const stats = [
  { key: "satiety", label: "饱腹", color: "#d6a56e" },
  { key: "energy", label: "精力", color: "#9da8d1" },
  { key: "happiness", label: "心情", color: "#dba0a0" },
  { key: "cleanliness", label: "清洁", color: "#8eafa2" },
] as const;
export function PetSpace({ pet }: { pet: Pet }) {
  const client = useQueryClient();
  const action = useAppStore((s) => s.action);
  const setAction = useAppStore((s) => s.setAction);
  const [note, setNote] = useState("你来啦，陪我待一会儿吧。");
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pending = useRef<{ action: string; key: string } | null>(null);
  useEffect(
    () => () => {
      if (timer.current) clearTimeout(timer.current);
    },
    [],
  );
  const mutation = useMutation({
    mutationFn: (kind: string) => {
      if (!pending.current || pending.current.action !== kind)
        pending.current = { action: kind, key: crypto.randomUUID() };
      return api<PetEvent>(`/pets/${pet.id}/actions`, {
        method: "POST",
        body: JSON.stringify({
          action: kind,
          request_key: pending.current.key,
        }),
      });
    },
    onSuccess: (event) => {
      pending.current = null;
      setNote(event.text);
      setAction(event.action);
      if (timer.current) clearTimeout(timer.current);
      timer.current = setTimeout(() => setAction("idle"), 4500);
      void client.invalidateQueries({ queryKey: ["pets"] });
      void client.invalidateQueries({ queryKey: ["events", pet.id] });
      void client.invalidateQueries({ queryKey: ["recent-events", pet.id] });
    },
    onError: (error) => {
      if (error instanceof ApiError && error.status < 500)
        pending.current = null;
      void client.invalidateQueries({ queryKey: ["pets"] });
    },
  });
  const mood =
    pet.energy < 20
      ? "有点困，想靠着你休息"
      : pet.satiety < 25
        ? "肚子咕噜咕噜，等一口好吃的"
        : "今天的阳光和你，都刚刚好";
  return (
    <section className="pet-space">
      <div className="section-heading">
        <div>
          <span className="eyebrow">OUR LITTLE CORNER</span>
          <h2>
            {pet.name}的小窝 <span className="live-dot" />
          </h2>
        </div>
        <span className="soft-badge">
          <Sun size={14} /> 宜陪伴
        </span>
      </div>
      <div className={`cat-scene scene-${action}`}>
        <div className="scene-window">
          <i />
          <i />
          <i />
          <i />
        </div>
        <div className="sunbeam" />
        <span className="scene-plant">🌿</span>
        <div className="scene-wall-label">HOME IS WHERE YOU ARE</div>
        <div className="cat-bubble">
          {action === "rest" ? "呼噜呼噜… 💤" : note}
        </div>
        <div className="cat-rug" />
        <div className="cat-shadow" />
        <img
          className="scene-cat"
          src={(cats[pet.color] ?? cats.calico).image}
          alt={`${pet.name}，${pet.personality}的小猫`}
        />
        <div className="scene-bowl">
          <span />
        </div>
        <span className="scene-toy">✦</span>
        {action === "play" && <span className="play-spark">✧</span>}
        {action === "clean" && <Sparkles className="clean-spark" />}
        {action === "rest" && <span className="sleep-symbol">z Z</span>}
        <span className="scene-caption">
          <Heart size={13} />
          {mood}
        </span>
      </div>
      <div className="pet-stats">
        {stats.map((stat) => (
          <div className="stat" key={stat.key}>
            <div>
              <span>{stat.label}</span>
              <strong>
                {Math.round(pet[stat.key])}
                <small>/100</small>
              </strong>
            </div>
            <div className="stat-track">
              <i
                style={{ width: `${pet[stat.key]}%`, background: stat.color }}
              />
            </div>
          </div>
        ))}
      </div>
      <div className="care-actions">
        {actions.map((item) => (
          <button
            key={item.id}
            disabled={mutation.isPending}
            onClick={() => mutation.mutate(item.id)}
          >
            <span className={`action-icon ${item.id}`}>
              <item.icon size={21} />
            </span>
            <strong>{item.label}</strong>
            <small>{item.note}</small>
          </button>
        ))}
      </div>
      {mutation.error && (
        <p className="error inline-error" role="alert">
          {mutation.error.message}
        </p>
      )}
    </section>
  );
}
