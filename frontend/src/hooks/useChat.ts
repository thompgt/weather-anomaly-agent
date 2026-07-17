import { useCallback, useState } from "react";
import { postChat } from "../api/client";
import type { ChatMessage } from "../types";

let idCounter = 0;
function nextId(): string {
  idCounter += 1;
  return `msg-${idCounter}-${Date.now()}`;
}

export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [sending, setSending] = useState(false);

  const sendMessage = useCallback(async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed) return;

    const userMessage: ChatMessage = { id: nextId(), role: "user", text: trimmed };
    const pendingId = nextId();
    setMessages((prev) => [
      ...prev,
      userMessage,
      { id: pendingId, role: "agent", text: "Thinking...", pending: true },
    ]);
    setSending(true);

    try {
      const { response } = await postChat(trimmed);
      setMessages((prev) =>
        prev.map((m) => (m.id === pendingId ? { id: pendingId, role: "agent", text: response } : m))
      );
    } catch (err) {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === pendingId
            ? {
                id: pendingId,
                role: "agent",
                text: err instanceof Error ? err.message : "Something went wrong.",
                error: true,
              }
            : m
        )
      );
    } finally {
      setSending(false);
    }
  }, []);

  return { messages, sendMessage, sending };
}
