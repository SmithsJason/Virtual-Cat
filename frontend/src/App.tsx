import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import {
  ArrowRight,
  BookHeart,
  BookOpen,
  Cat,
  Heart,
  Home,
  LogOut,
  Settings,
  Sparkles,
} from "lucide-react";
import { Auth } from "./components/Auth";
import { Adoption } from "./components/Adoption";
import { Chat } from "./components/Chat";
import { Diary } from "./components/Diary";
import { Memories } from "./components/Memories";
import { PetSpace } from "./components/PetSpace";
import { api, ApiError } from "./lib/api";
import { cats } from "./lib/cats";
import type { Health, Page, Pet, PetEvent, User } from "./lib/types";
import { useAppStore } from "./store/useAppStore";
const tabs = [
  { id: "home", label: "宠物空间", icon: Home },
  { id: "diary", label: "成长日记", icon: BookOpen },
  { id: "memories", label: "共同记忆", icon: BookHeart },
  { id: "settings", label: "小窝设置", icon: Settings },
] as const;

function SettingsPage({ user, health }: { user: User; health?: Health }) {
  const client = useQueryClient();
  const logout = useMutation({
    mutationFn: () => api("/auth/logout", { method: "POST" }),
    onSuccess: () => {
      client.clear();
      window.location.reload();
    },
  });
  return (
    <section className="content-page">
      <div className="page-title">
        <div>
          <span className="eyebrow">MAKE YOURSELF AT HOME</span>
          <h1>小窝设置</h1>
          <p>安心地陪伴，也安心地照顾自己的空间。</p>
        </div>
      </div>
      <div className="settings-card">
        <h3>你的账号</h3>
        <p>{user.username}</p>
        <div className="settings-line">
          <span>小窝数据</span>
          <span className="status-label">
            {health?.database ? "已妥善保存" : "暂时无法连接"}
          </span>
        </div>
        <div className="settings-line">
          <span>对话服务</span>
          <span className="status-label">
            {health?.chat_available ? "已连接" : "尚未连接"}
          </span>
        </div>
        <p className="muted">
          你可以在「共同记忆」中查看、纠正或遗忘记录。开启新会话后，小猫和有效记忆依然保留。
        </p>
        <button
          className="secondary"
          disabled={logout.isPending}
          onClick={() => logout.mutate()}
        >
          <LogOut size={16} />
          退出登录
        </button>
        {logout.error && <p className="error">{logout.error.message}</p>}
      </div>
    </section>
  );
}

export default function App() {
  const [today] = useState(() => new Date());
  const tab = useAppStore((s) => s.tab);
  const setTab = useAppStore((s) => s.setTab);
  const user = useQuery({
    queryKey: ["me"],
    queryFn: () => api<User>("/auth/me"),
    retry: false,
  });
  const pets = useQuery({
    queryKey: ["pets"],
    queryFn: () => api<Pet[]>("/pets"),
    enabled: !!user.data,
    refetchInterval: 30000,
  });
  const health = useQuery({
    queryKey: ["health"],
    queryFn: () => api<Health>("/health"),
    retry: false,
    refetchInterval: 30000,
  });
  const pet = pets.data?.[0];
  const recent = useQuery({
    queryKey: ["recent-events", pet?.id],
    queryFn: () => api<Page<PetEvent>>(`/pets/${pet?.id}/events`),
    enabled: !!pet,
    refetchInterval: 10000,
  });
  if (user.isPending)
    return (
      <div className="loading-screen">
        <Cat size={36} />
        <p>正在打开你们的小窝…</p>
      </div>
    );
  if (user.error) {
    if (user.error instanceof ApiError && user.error.status === 401)
      return <Auth />;
    return (
      <div className="loading-screen">
        <Cat size={36} />
        <h2>小窝暂时还没准备好</h2>
        <p className="error">{user.error.message}</p>
        <button className="secondary" onClick={() => void user.refetch()}>
          再试一次
        </button>
      </div>
    );
  }
  if (pets.isPending)
    return (
      <div className="loading-screen">
        <Cat size={36} />
        <p>小猫正走过来…</p>
      </div>
    );
  if (pets.error)
    return (
      <div className="loading-screen">
        <p className="error">{pets.error.message}</p>
        <button className="secondary" onClick={() => void pets.refetch()}>
          重新连接
        </button>
      </div>
    );
  if (!pet) return <Adoption />;
  const days = Math.max(
    1,
    Math.floor(
      (today.getTime() - new Date(pet.created_at).getTime()) / 86400000,
    ) + 1,
  );
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a href="/" className="brand">
          <span className="brand-mark">
            <Cat size={24} />
          </span>
          <span>
            喵伴<span className="brand-en">MIAOBAN</span>
          </span>
        </a>
        <div className="nav-label">OUR LITTLE WORLD</div>
        <nav aria-label="主要导航">
          {tabs.map((item) => (
            <button
              key={item.id}
              className={tab === item.id ? "active" : ""}
              onClick={() => setTab(item.id)}
            >
              <item.icon size={19} />
              <span>{item.label}</span>
              {item.id === "home" && <span className="nav-dot" />}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="sidebar-note">
            <Heart size={18} />
            <p>
              陪伴不需要很盛大，
              <br />
              每天一点点就很好。
            </p>
            <span>little moments, lasting love.</span>
          </div>
          <div className="user-chip">
            <span>{user.data?.username.slice(0, 1).toUpperCase()}</span>
            <div>
              <strong>{user.data?.username}</strong>
              <small>{pet.name}的专属家人</small>
            </div>
            <Heart size={15} />
          </div>
        </div>
      </aside>
      <main className="main-area">
        <header className="topbar">
          <span>生活里的小小陪伴</span>
          <div>
            <span className="today-date">
              {new Date().toLocaleDateString("zh-CN", {
                month: "long",
                day: "numeric",
                weekday: "long",
              })}
            </span>
            <span className="topbar-avatar">
              {user.data?.username.slice(0, 1).toUpperCase()}
            </span>
          </div>
        </header>
        {tab === "home" ? (
          <div className="home-page">
            <div className="welcome">
              <div>
                <span className="eyebrow">HELLO, MY FAVORITE HUMAN</span>
                <h1>
                  今天，也一起慢慢长大<span>。</span>
                </h1>
                <p>欢迎回来。{pet.name}已经把最舒服的位置留给你了。</p>
              </div>
              <span className="together-badge">
                <Heart size={16} />
                相伴的第 <strong>{days}</strong> 天
              </span>
            </div>
            <div className="home-grid">
              <PetSpace pet={pet} />
              <Chat pet={pet} health={health.data} />
            </div>
            <div className="home-bottom">
              <section className="bond-card">
                <span className="bond-icon">
                  <Heart size={22} />
                </span>
                <div>
                  <span className="eyebrow">A BOND THAT GROWS</span>
                  <h3>{pet.stage}</h3>
                  <p>每一次认真陪伴，都会让我们更靠近。</p>
                </div>
                <div className="bond-number">
                  {Math.round(pet.affection)}
                  <small>亲密度</small>
                </div>
              </section>
              <section className="moment-card">
                <div>
                  <Sparkles size={17} />
                  <h3>最近的小确幸</h3>
                </div>
                <p>
                  {recent.data?.items[0]?.text ??
                    "你来到了这里，故事就开始了。"}
                </p>
                <button className="text-button" onClick={() => setTab("diary")}>
                  翻翻日记
                  <ArrowRight size={14} />
                </button>
              </section>
            </div>
            <footer className="home-footer">
              <img src={cats[pet.color].image} alt="" />
              平凡的日子，也值得被好好记住。
            </footer>
          </div>
        ) : tab === "diary" ? (
          <Diary pet={pet} />
        ) : tab === "memories" ? (
          <Memories pet={pet} />
        ) : (
          <SettingsPage user={user.data!} health={health.data} />
        )}
      </main>
    </div>
  );
}
