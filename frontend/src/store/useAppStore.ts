import { create } from "zustand";
type Tab = "home" | "diary" | "memories" | "settings";
export const useAppStore = create<{
  tab: Tab;
  setTab: (tab: Tab) => void;
  action: string;
  setAction: (action: string) => void;
}>((set) => ({
  tab: "home",
  setTab: (tab) => set({ tab }),
  action: "idle",
  setAction: (action) => set({ action }),
}));
