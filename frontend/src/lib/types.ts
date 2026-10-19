export type User = { id: string; username: string };
export type Pet = {
  id: string;
  name: string;
  color: string;
  personality: string;
  satiety: number;
  energy: number;
  happiness: number;
  cleanliness: number;
  affection: number;
  stage: string;
  version: number;
  created_at: string;
};
export type PetEvent = {
  id: string;
  action: string;
  text: string;
  state: Pet;
  created_at: string;
};
export type Conversation = { id: string; title: string; created_at: string };
export type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
};
export type Memory = {
  id: string;
  kind: "fact" | "preference" | "promise" | "episode";
  content: string;
  key: string | null;
  status: string;
  valid_until: string | null;
  created_at: string;
  sources: { message_id: string | null; quote: string }[];
};
export type Run = {
  id: string;
  status: "pending" | "running" | "completed" | "failed";
  conversation_id: string;
  user_message_id: string;
  assistant_message_id: string | null;
  error: string | null;
  trace: {
    preview?: string;
    selected_ids?: string[];
    events?: PetEvent[];
    warning?: string;
  };
};
export type Page<T> = { items: T[]; next: string | null };
export type Health = {
  database: boolean;
  chat_available: boolean;
  embedding_available: boolean;
};
