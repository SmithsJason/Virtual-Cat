import { useState, type FormEvent } from "react";
import { ArrowRight, Cat, Heart, Sparkles } from "lucide-react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import type { User } from "../lib/types";
import { LoginCat } from "./LoginCat";

export function Auth() {
  const [register, setRegister] = useState(false);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const client = useQueryClient();
  const mutation = useMutation({
    mutationFn: () =>
      api<User>(`/auth/${register ? "register" : "login"}`, {
        method: "POST",
        body: JSON.stringify({ username, password }),
      }),
    onSuccess: (user) => {
      client.removeQueries({
        predicate: (query) => query.queryKey[0] !== "me",
      });
      client.setQueryData(["me"], user);
    },
  });
  function submit(event: FormEvent) {
    event.preventDefault();
    mutation.mutate();
  }
  return (
    <main className="auth-page">
      <div className="auth-story">
        <a className="brand" href="/">
          <span className="brand-mark">
            <Cat size={23} />
          </span>
          <span>
            喵伴<span className="brand-en">MIAOBAN</span>
          </span>
        </a>
        <div className="auth-intro">
          <span className="eyebrow">A LITTLE CAT. A LOT OF LOVE.</span>
          <h1>
            生活很大，
            <br />
            留一个小角落
            <br />
            给彼此。
          </h1>
          <p>
            领养一只属于你的小猫。一起吃饭、玩耍，
            <br />
            把平凡的每一天，变成值得记住的事。
          </p>
          <LoginCat />
        </div>
        <span className="auth-foot">一点点照料，慢慢变成很多陪伴。</span>
      </div>
      <section className="auth-form-wrap">
        <div className="auth-form">
          <div className="tiny-icon">
            <Sparkles size={23} />
          </div>
          <h2>{register ? "故事，从这里开始" : "欢迎回到小猫身边"}</h2>
          <p>
            {register
              ? "创建账号，遇见你的小伙伴。"
              : "熟悉的小角落，和一直等你的它。"}
          </p>
          <form onSubmit={submit}>
            <label>
              用户名
              <input
                autoComplete="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
                minLength={3}
                maxLength={40}
                placeholder="至少 3 个字母、数字或汉字"
              />
            </label>
            <label>
              密码
              <input
                type="password"
                autoComplete={register ? "new-password" : "current-password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={8}
                maxLength={128}
                placeholder="至少 8 位字符"
              />
            </label>
            {mutation.error && (
              <p className="error" role="alert">
                {mutation.error.message}
              </p>
            )}
            <button className="primary" disabled={mutation.isPending}>
              {mutation.isPending
                ? "稍等一下…"
                : register
                  ? "开启陪伴"
                  : "回到小窝"}
              <ArrowRight size={18} />
            </button>
          </form>
          <p className="auth-switch">
            {register ? "已经有账号？" : "还没有小伙伴？"}{" "}
            <button
              onClick={() => {
                setRegister(!register);
                mutation.reset();
              }}
            >
              {register ? "去登录" : "创建账号"}
            </button>
          </p>
          <div className="auth-promise">
            <Heart size={15} /> 你的故事与记忆，只属于你和小猫。
          </div>
        </div>
      </section>
    </main>
  );
}
