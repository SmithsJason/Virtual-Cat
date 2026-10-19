import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, Heart } from "lucide-react";
import { api } from "../lib/api";
import { cats } from "../lib/cats";
export function Adoption() {
  const [name, setName] = useState("奶糖");
  const [color, setColor] = useState("calico");
  const [personality, setPersonality] = useState("温柔好奇");
  const client = useQueryClient();
  const mutation = useMutation({
    mutationFn: () =>
      api("/pets", {
        method: "POST",
        body: JSON.stringify({ name, color, personality }),
      }),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ["pets"] });
    },
  });
  return (
    <main className="adoption-page">
      <section className="adoption-card">
        <span className="eyebrow">NICE TO MEET YOU</span>
        <h1>这次相遇，会有一点不同。</h1>
        <p>选一只小猫，给它一个名字，开始你们的故事。</p>
        <div className="adoption-picture">
          <img src={cats[color].image} alt={cats[color].label} />
          <Heart className="adoption-heart" size={24} />
        </div>
        <div className="color-options">
          {Object.entries(cats).map(([key, cat]) => (
            <button
              key={key}
              className={key === color ? "chosen" : ""}
              onClick={() => setColor(key)}
            >
              <i style={{ background: cat.swatch }} />
              {cat.label}
            </button>
          ))}
        </div>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            mutation.mutate();
          }}
        >
          <label>
            给小猫取个名字
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              maxLength={30}
            />
          </label>
          <label>
            它的小性格
            <select
              value={personality}
              onChange={(e) => setPersonality(e.target.value)}
            >
              {["温柔好奇", "活泼黏人", "安静独立"].map((p) => (
                <option key={p}>{p}</option>
              ))}
            </select>
          </label>
          {mutation.error && (
            <p role="alert" className="error">
              {mutation.error.message}
            </p>
          )}
          <button className="primary" disabled={mutation.isPending}>
            {mutation.isPending ? "正在准备小窝…" : "带它回家"}
            <ArrowRight size={18} />
          </button>
        </form>
      </section>
    </main>
  );
}
